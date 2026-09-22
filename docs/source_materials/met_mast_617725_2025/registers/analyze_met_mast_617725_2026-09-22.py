"""Profile and evaluate the private immutable met-mast export 617725.

The source is already a machine-readable tab-delimited export. This register
therefore reads its hash-pinned private copy and emits deterministic summaries
into the public DutchBay EPC evidence package without rewriting or publishing
the interval observations. It treats the embedded text only as data.

Run from any directory with the governed DutchBay Python environment::

    DUTCHBAY_MET_MAST_617725_SOURCE=/private/path/617725数据导出.txt \
      python analyze_met_mast_617725_2026-09-22.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.projections.polar import PolarAxes
from scipy.stats import weibull_min

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "extracted"
SOURCE_ENV = "DUTCHBAY_MET_MAST_617725_SOURCE"
SOURCE_SHA256 = "a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46"
SOURCE_SIZE_BYTES = 8_758_675
SOURCE_REPOSITORY = "arunakulat/DutchBay_RAG"
SOURCE_COMMIT = "52ae2fecb05f84497a68d00affbd95f4b0c18986"
SOURCE_RELATIVE_PATH = "corpus/met_mast_617725_2025/raw/617725数据导出.txt"
INGRESS_DATE = "2026-09-22"
ASSESSMENT_START = pd.Timestamp("2025-03-21 18:00:00")
TEN_MINUTES = pd.Timedelta(minutes=10)
HEIGHTS = (30, 50, 80, 100, 120)
SPEED_AVG = {height: f"Speed {height} m Avg [m/s]" for height in HEIGHTS}
SECTOR_LABELS = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)


def resolve_source_path() -> Path:
    """Resolve the private source from an explicit environment variable."""
    raw_value = os.environ.get(SOURCE_ENV)
    if not raw_value:
        raise RuntimeError(
            f"{SOURCE_ENV} must name the private hash-pinned source file; "
            "the interval series is intentionally absent from this public repository"
        )
    path = Path(raw_value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"private met-mast source does not exist: {path}")
    return path


def sha256_path(path: Path) -> str:
    """Return the SHA-256 digest of *path* without altering it."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_fullmatch(pattern: str, value: str, label: str) -> re.Match[str]:
    """Return a full regex match or raise a field-specific source error."""
    match = re.fullmatch(pattern, value)
    if match is None:
        raise ValueError(f"source header field does not match {label}: {value!r}")
    return match


def parse_source_header(path: Path) -> dict[str, Any]:
    """Parse and preserve every source-header line before the TSV header."""
    with path.open(encoding="utf-8", newline="") as handle:
        header_lines = [handle.readline().rstrip("\r\n") for _ in range(12)]

    created = required_fullmatch(r"Created (.+)", header_lines[0], "creation time")
    latitude = required_fullmatch(
        r"Latitude = N ([0-9.]+)", header_lines[2], "latitude"
    )
    longitude = required_fullmatch(
        r"Longitude = E ([0-9.]+)", header_lines[3], "longitude"
    )
    elevation = required_fullmatch(
        r"Elevation = ([0-9.]+)m", header_lines[4], "elevation"
    )
    calm = required_fullmatch(
        r"Calm threshold = ([0-9.]+)m/s", header_lines[5], "calm threshold"
    )
    included = required_fullmatch(
        r"Included flags: (.*)", header_lines[7], "included flags"
    )
    excluded = required_fullmatch(
        r"Excluded flags:(.*)", header_lines[8], "excluded flags"
    )

    included_value = included.group(1).strip()
    excluded_value = excluded.group(1).strip()
    return {
        "raw_header_lines_1_to_12": header_lines,
        "embedded_export_created": created.group(1),
        "latitude_deg_n": float(latitude.group(1)),
        "longitude_deg_e": float(longitude.group(1)),
        "elevation_m": float(elevation.group(1)),
        "calm_threshold_ms": float(calm.group(1)),
        "included_flags_raw": included_value,
        "excluded_flags_raw": excluded_value,
        "timestamp_semantics": header_lines[10],
    }


def load_source(path: Path) -> pd.DataFrame:
    """Load the fixed UTF-8 TSV source and enforce its immutable identity."""
    actual_size = path.stat().st_size
    if actual_size != SOURCE_SIZE_BYTES:
        raise ValueError(
            f"source size mismatch: expected {SOURCE_SIZE_BYTES}, got {actual_size}"
        )
    actual_sha = sha256_path(path)
    if actual_sha != SOURCE_SHA256:
        raise ValueError(
            f"source hash mismatch: expected {SOURCE_SHA256}, got {actual_sha}"
        )

    frame = pd.read_csv(path, sep="\t", skiprows=12, low_memory=False)
    if frame.shape != (33_456, 57):
        raise ValueError(f"unexpected source shape: {frame.shape!r}")
    frame["Date/Time"] = pd.to_datetime(frame["Date/Time"], errors="raise")
    for column in frame.columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")

    timestamps = frame["Date/Time"]
    if timestamps.duplicated().any() or not timestamps.is_monotonic_increasing:
        raise ValueError("timestamps must be unique and increasing")
    if timestamps.iloc[0] != pd.Timestamp("2025-03-20 23:40:00"):
        raise ValueError("unexpected first timestamp")
    if timestamps.iloc[-1] != pd.Timestamp("2025-11-08 23:50:00"):
        raise ValueError("unexpected last timestamp")
    return frame


def json_value(value: Any) -> Any:
    """Convert pandas/numpy values into strict JSON values without NaN."""
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON with strict non-NaN values."""
    path.write_text(
        json.dumps(json_value(payload), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )


def classify_column(column: str) -> tuple[str, int | None, str, str]:
    """Return measurement family, height, statistic, and unit from a source header."""
    if column == "Date/Time":
        return "timestamp", None, "timestamp", "undocumented timezone"
    match = re.fullmatch(
        r"(Speed|Direction|Temp|RH|Pressure) ([0-9]+) m (Avg|Min|Max|SD) \[(.+)]",
        column,
    )
    if not match:
        raise ValueError(f"unrecognised column header: {column}")
    family_map = {
        "Speed": "wind_speed",
        "Direction": "wind_direction",
        "Temp": "temperature",
        "RH": "relative_humidity",
        "Pressure": "pressure",
    }
    return (
        family_map[match.group(1)],
        int(match.group(2)),
        match.group(3).lower(),
        match.group(4),
    )


def profile_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Profile every source column without dropping sparse or empty channels."""
    rows: list[dict[str, Any]] = []
    total = len(frame)
    for column_index, column in enumerate(frame.columns, start=1):
        family, height, statistic, unit = classify_column(column)
        if column == "Date/Time":
            rows.append(
                {
                    "column_index": column_index,
                    "column": column,
                    "family": family,
                    "height_m": "",
                    "statistic": statistic,
                    "unit": unit,
                    "non_null_count": total,
                    "null_count": 0,
                    "completeness_pct": 100.0,
                    "distinct_count": frame[column].nunique(),
                    "first_non_null_timestamp": frame[column].min(),
                    "last_non_null_timestamp": frame[column].max(),
                }
            )
            continue

        series = frame[column]
        valid = series.dropna()
        valid_timestamps = frame.loc[series.notna(), "Date/Time"]
        record: dict[str, Any] = {
            "column_index": column_index,
            "column": column,
            "family": family,
            "height_m": height,
            "statistic": statistic,
            "unit": unit,
            "non_null_count": int(series.notna().sum()),
            "null_count": int(series.isna().sum()),
            "completeness_pct": 100 * series.notna().mean(),
            "distinct_count": int(series.nunique(dropna=True)),
            "zero_count": int((series == 0).sum()),
            "negative_count": int((series < 0).sum()),
            "first_non_null_timestamp": (
                valid_timestamps.iloc[0] if not valid.empty else ""
            ),
            "last_non_null_timestamp": (
                valid_timestamps.iloc[-1] if not valid.empty else ""
            ),
        }
        for name, value in (
            ("min", valid.min()),
            ("p01", valid.quantile(0.01)),
            ("p05", valid.quantile(0.05)),
            ("p25", valid.quantile(0.25)),
            ("median", valid.median()),
            ("mean", valid.mean()),
            ("p75", valid.quantile(0.75)),
            ("p95", valid.quantile(0.95)),
            ("p99", valid.quantile(0.99)),
            ("max", valid.max()),
            ("std", valid.std()),
        ):
            record[name] = value
        rows.append(record)
    return pd.DataFrame(rows)


def contiguous_ranges(timestamps: Iterable[pd.Timestamp]) -> list[dict[str, Any]]:
    """Collapse sorted ten-minute timestamps into inclusive contiguous ranges."""
    ordered = sorted(pd.Timestamp(value) for value in timestamps)
    if not ordered:
        return []
    ranges: list[dict[str, Any]] = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if current - previous != TEN_MINUTES:
            ranges.append(
                {
                    "start": start,
                    "end": previous,
                    "interval_count": int((previous - start) / TEN_MINUTES) + 1,
                }
            )
            start = current
        previous = current
    ranges.append(
        {
            "start": start,
            "end": previous,
            "interval_count": int((previous - start) / TEN_MINUTES) + 1,
        }
    )
    return ranges


def channel_missing_ranges(
    frame: pd.DataFrame, column: str, expected_index: pd.DatetimeIndex
) -> list[dict[str, Any]]:
    """Return null-channel runs, excluding timestamps absent from the entire export."""
    indexed = frame.set_index("Date/Time")
    present = pd.Series(False, index=expected_index)
    present.loc[indexed.index] = True
    values = indexed[column].reindex(expected_index)
    return contiguous_ranges(expected_index[present & values.isna()])


def wind_statistics(
    assessment: pd.DataFrame, expected_count: int
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Compute per-height distributions and the concurrent vertical profile."""
    results: list[dict[str, Any]] = []
    for height in HEIGHTS:
        column = SPEED_AVG[height]
        series = assessment[column].dropna()
        shape, _location, scale = weibull_min.fit(series, floc=0)
        results.append(
            {
                "height_m": height,
                "valid_count": len(series),
                "expected_interval_coverage_pct": 100 * len(series) / expected_count,
                "mean_ms": series.mean(),
                "median_ms": series.median(),
                "std_ms": series.std(),
                "min_ms": series.min(),
                "p01_ms": series.quantile(0.01),
                "p05_ms": series.quantile(0.05),
                "p25_ms": series.quantile(0.25),
                "p75_ms": series.quantile(0.75),
                "p95_ms": series.quantile(0.95),
                "p99_ms": series.quantile(0.99),
                "max_ms": series.max(),
                "weibull_shape_k_mle": shape,
                "weibull_scale_a_ms_mle": scale,
            }
        )
    common = assessment.dropna(subset=list(SPEED_AVG.values())).copy()
    return results, common


def monthly_statistics(
    assessment: pd.DataFrame, assessment_end: pd.Timestamp
) -> pd.DataFrame:
    """Return long-form monthly wind statistics with explicit interval coverage."""
    frame = assessment.copy()
    frame["month"] = frame["Date/Time"].dt.to_period("M").astype(str)
    rows: list[dict[str, Any]] = []
    for month, group in frame.groupby("month", sort=True):
        month_label = str(month)
        period = pd.Period(month_label)
        start = max(ASSESSMENT_START, period.start_time)
        end = min(assessment_end, period.end_time.floor("10min"))
        expected = len(pd.date_range(start, end, freq="10min"))
        for height in HEIGHTS:
            series = group[SPEED_AVG[height]].dropna()
            rows.append(
                {
                    "month": month_label,
                    "month_is_partial": month_label in {"2025-03", "2025-11"},
                    "height_m": height,
                    "expected_intervals": expected,
                    "valid_count": len(series),
                    "coverage_pct": 100 * len(series) / expected,
                    "mean_ms": series.mean(),
                    "median_ms": series.median(),
                    "std_ms": series.std(),
                    "p05_ms": series.quantile(0.05),
                    "p95_ms": series.quantile(0.95),
                    "max_ms": series.max(),
                }
            )
    return pd.DataFrame(rows)


def direction_statistics(
    assessment: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Compute a 16-sector 80 m wind rose using the most complete direction channel."""
    frame = assessment.dropna(
        subset=["Direction 80 m Avg [°]", "Speed 80 m Avg [m/s]"]
    ).copy()
    radians = np.deg2rad(frame["Direction 80 m Avg [°]"])
    sin_mean = np.sin(radians).mean()
    cos_mean = np.cos(radians).mean()
    circular_mean = (np.rad2deg(np.arctan2(sin_mean, cos_mean)) + 360) % 360
    resultant_length = np.hypot(sin_mean, cos_mean)

    indices = ((frame["Direction 80 m Avg [°]"] + 11.25) // 22.5).astype(int) % 16
    frame["sector"] = [SECTOR_LABELS[index] for index in indices]
    cube_total = float((frame["Speed 80 m Avg [m/s]"] ** 3).sum())
    rows: list[dict[str, Any]] = []
    for index, label in enumerate(SECTOR_LABELS):
        subset = frame[frame["sector"] == label]
        rows.append(
            {
                "sector_index": index,
                "sector": label,
                "centre_deg": index * 22.5,
                "count": len(subset),
                "frequency_pct": 100 * len(subset) / len(frame),
                "mean_speed_ms": subset["Speed 80 m Avg [m/s]"].mean(),
                "speed_cubed_share_pct": (
                    100
                    * float((subset["Speed 80 m Avg [m/s]"] ** 3).sum())
                    / cube_total
                ),
            }
        )
    summary = {
        "basis": "80 m average direction paired with 80 m average speed",
        "valid_count": len(frame),
        "circular_mean_deg": circular_mean,
        "mean_resultant_length": resultant_length,
        "dominant_occurrence_sectors": ["SW", "WSW"],
        "sw_plus_wsw_frequency_pct": 100 * frame["sector"].isin(["SW", "WSW"]).mean(),
        "sw_plus_wsw_speed_cubed_share_pct": sum(
            row["speed_cubed_share_pct"]
            for row in rows
            if row["sector"] in {"SW", "WSW"}
        ),
    }
    return summary, pd.DataFrame(rows)


def shear_and_turbulence(
    assessment: pd.DataFrame, common: pd.DataFrame
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Calculate transparent partial-period shear and turbulence summaries."""
    speed_columns = [SPEED_AVG[height] for height in HEIGHTS]
    fit_mask = common[speed_columns].min(axis=1) >= 3.0
    fit = common.loc[fit_mask, speed_columns]
    alpha_30_120 = np.log(fit[SPEED_AVG[120]] / fit[SPEED_AVG[30]]) / np.log(120 / 30)

    log_heights = np.log(np.asarray(HEIGHTS, dtype=float))
    centred_height = log_heights - log_heights.mean()
    log_speeds = np.log(fit.to_numpy())
    alphas = (
        (log_speeds - log_speeds.mean(axis=1, keepdims=True)) * centred_height
    ).sum(axis=1) / (centred_height**2).sum()
    shear = {
        "filter": "all five mean speeds >= 3 m/s",
        "valid_count": len(fit),
        "alpha_30_to_120_mean": alpha_30_120.mean(),
        "alpha_30_to_120_median": alpha_30_120.median(),
        "alpha_30_to_120_p05": alpha_30_120.quantile(0.05),
        "alpha_30_to_120_p95": alpha_30_120.quantile(0.95),
        "alpha_five_height_ols_mean": alphas.mean(),
        "alpha_five_height_ols_median": np.median(alphas),
        "alpha_five_height_ols_p05": np.quantile(alphas, 0.05),
        "alpha_five_height_ols_p95": np.quantile(alphas, 0.95),
        "negative_alpha_pct": 100 * float((alphas < 0).mean()),
    }

    turbulence: list[dict[str, Any]] = []
    for height in HEIGHTS:
        average = assessment[SPEED_AVG[height]]
        standard_deviation = assessment[f"Speed {height} m SD [m/s]"]
        mask = average.notna() & standard_deviation.notna() & (average >= 3.0)
        ti = standard_deviation[mask] / average[mask]
        turbulence.append(
            {
                "height_m": height,
                "filter": "mean speed >= 3 m/s",
                "valid_count": int(mask.sum()),
                "mean_ti": ti.mean(),
                "median_ti": ti.median(),
                "p90_ti": ti.quantile(0.90),
                "p95_ti": ti.quantile(0.95),
            }
        )
    return shear, turbulence


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 coordinate pairs."""
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(value))


def outage_adjusted_sensitivity(
    assessment: pd.DataFrame, median_alpha: float
) -> dict[str, Any]:
    """Estimate the impact of selective 120 m missingness without replacing source data."""
    speed_120 = assessment[SPEED_AVG[120]]
    speed_100 = assessment[SPEED_AVG[100]]
    ratio_mask = (
        speed_120.notna() & speed_100.notna() & (speed_120 >= 3) & (speed_100 >= 3)
    )
    ratio = (speed_120[ratio_mask] / speed_100[ratio_mask]).median()
    proxy_120 = speed_120.copy()
    fill_mask = speed_120.isna() & speed_100.notna()
    proxy_120.loc[fill_mask] = speed_100.loc[fill_mask] * ratio

    pre_mask = (
        speed_120.notna()
        & speed_100.notna()
        & (assessment["Date/Time"] < pd.Timestamp("2025-10-13 02:20:00"))
    )
    post_mask = (
        speed_120.notna()
        & speed_100.notna()
        & (assessment["Date/Time"] >= pd.Timestamp("2025-10-28 16:10:00"))
    )
    slope, intercept = np.polyfit(speed_100[pre_mask], speed_120[pre_mask], 1)
    post_error = speed_120[post_mask] - (intercept + slope * speed_100[post_mask])

    observed_130 = speed_120.dropna() * (130 / 120) ** median_alpha
    proxy_130 = proxy_120.dropna() * (130 / 120) ** median_alpha
    return {
        "purpose": "sensitivity only; no source values are replaced",
        "concurrent_high_wind_median_120_to_100_ratio": ratio,
        "filled_120m_interval_count": int(fill_mask.sum()),
        "raw_available_120m_mean_ms": speed_120.mean(),
        "ratio_proxy_full_window_120m_mean_ms": proxy_120.mean(),
        "raw_available_130m_extrapolated_mean_ms": observed_130.mean(),
        "ratio_proxy_full_window_130m_extrapolated_mean_ms": proxy_130.mean(),
        "five_height_median_alpha_used": median_alpha,
        "pre_outage_linear_validation": {
            "slope": slope,
            "intercept_ms": intercept,
            "post_return_count": int(post_mask.sum()),
            "post_return_mean_error_ms": post_error.mean(),
            "post_return_mae_ms": post_error.abs().mean(),
            "post_return_rmse_ms": np.sqrt((post_error**2).mean()),
        },
        "envision_kalpitiya_proposal_mean_130m_ms": 8.97,
        "proxy_vs_proposal_pct": 100 * (proxy_130.mean() / 8.97 - 1),
    }


def qc_events(
    frame: pd.DataFrame, assessment: pd.DataFrame, expected: pd.DatetimeIndex
) -> pd.DataFrame:
    """Build a concise event register for material source-quality conditions."""
    events: list[dict[str, Any]] = []

    def add(
        event_id: str,
        severity: str,
        channel: str,
        start: Any,
        end: Any,
        interval_count: int,
        finding: str,
        treatment: str,
    ) -> None:
        events.append(
            {
                "event_id": event_id,
                "severity": severity,
                "channel": channel,
                "start": start,
                "end": end,
                "interval_count": interval_count,
                "finding": finding,
                "analysis_treatment": treatment,
            }
        )

    add(
        "QC-001",
        "high",
        "multiple",
        frame["Date/Time"].min(),
        pd.Timestamp("2025-03-21 17:50:00"),
        int((frame["Date/Time"] < ASSESSMENT_START).sum()),
        "commissioning/start-up block: missing averages and -40.9 C, 0% RH, and 49.48 kPa sentinels",
        "excluded from assessment window; raw bytes retained",
    )

    full_expected = pd.date_range(
        frame["Date/Time"].min(), frame["Date/Time"].max(), freq="10min"
    )
    for index, missing_range in enumerate(
        contiguous_ranges(
            full_expected.difference(pd.DatetimeIndex(frame["Date/Time"]))
        ),
        start=1,
    ):
        add(
            f"QC-01{index}",
            "medium",
            "timestamp",
            missing_range["start"],
            missing_range["end"],
            missing_range["interval_count"],
            "timestamp intervals absent from export",
            "reported as missing; not interpolated",
        )

    event_number = 20
    for column in (
        SPEED_AVG[120],
        "Direction 120 m Avg [°]",
        "Temp 120 m Avg [℃]",
    ):
        for missing_range in channel_missing_ranges(assessment, column, expected):
            add(
                f"QC-{event_number:03d}",
                "high" if column != "Direction 120 m Avg [°]" else "medium",
                column,
                missing_range["start"],
                missing_range["end"],
                missing_range["interval_count"],
                "channel is null while the export has records for other channels",
                "excluded per channel; no imputation in reported observations",
            )
            event_number += 1

    temperature_10 = assessment[
        ["Date/Time", "Temp 10 m Avg [℃]", "Temp 10 m Min [℃]", "Temp 10 m Max [℃]"]
    ]
    invalid_10 = temperature_10[
        (temperature_10["Temp 10 m Avg [℃]"] < 10)
        | (temperature_10["Temp 10 m Avg [℃]"] > 45)
        | (temperature_10["Temp 10 m Min [℃]"] < 10)
        | (temperature_10["Temp 10 m Max [℃]"] > 45)
    ]
    add(
        "QC-030",
        "high",
        "Temp 10 m",
        invalid_10["Date/Time"].min(),
        invalid_10["Date/Time"].max(),
        len(invalid_10),
        "three reset/glitch rows include -40.92 C and maxima above 130 C",
        "excluded from temperature interpretation; raw bytes retained",
    )

    invalid_120 = assessment[
        (assessment["Temp 120 m Avg [℃]"].notna())
        & (
            (assessment["Temp 120 m Avg [℃]"] < 10)
            | (assessment["Temp 120 m Avg [℃]"] > 45)
            | (assessment["Temp 120 m Min [℃]"] < 10)
            | (assessment["Temp 120 m Max [℃]"] > 45)
        )
    ]
    add(
        "QC-031",
        "high",
        "Temp 120 m",
        invalid_120["Date/Time"].min(),
        invalid_120["Date/Time"].max(),
        len(invalid_120),
        "non-null transition/glitch rows include -40.92 C and a 133.24 C maximum",
        "excluded from temperature interpretation; raw bytes retained",
    )

    empty_columns = [column for column in frame.columns if frame[column].isna().all()]
    add(
        "QC-040",
        "high",
        "; ".join(empty_columns),
        frame["Date/Time"].min(),
        frame["Date/Time"].max(),
        len(empty_columns),
        "eight channels are entirely empty",
        "retained and profiled as unusable; never silently dropped",
    )
    near_empty = [
        column
        for column in frame.columns[1:]
        if 0 < frame[column].notna().mean() < 0.01
    ]
    add(
        "QC-041",
        "high",
        "; ".join(near_empty),
        frame["Date/Time"].min(),
        pd.Timestamp("2025-03-21 06:40:00"),
        43,
        "six channels have only 43 commissioning rows, containing invalid -40.9 C or 49.47 kPa values",
        "retained and profiled as unusable",
    )
    return pd.DataFrame(events)


def create_figure(
    monthly: pd.DataFrame,
    direction: pd.DataFrame,
    availability: pd.DataFrame,
    common: pd.DataFrame,
) -> None:
    """Create a compact visual QA summary; numeric CSV/JSON remain authoritative."""
    plt.style.use("seaborn-v0_8-whitegrid")
    colours = ["#4C78A8", "#59A14F", "#F28E2B", "#B279A2", "#E15759"]
    figure = plt.figure(figsize=(15, 11), constrained_layout=True)
    grid = figure.add_gridspec(2, 2)

    axis_month = figure.add_subplot(grid[0, 0])
    for colour, height in zip(colours, HEIGHTS, strict=True):
        subset = monthly[monthly["height_m"] == height]
        axis_month.plot(
            subset["month"],
            subset["mean_ms"],
            marker="o",
            linewidth=2,
            color=colour,
            label=f"{height} m",
        )
    axis_month.set_title(
        "Monsoon months dominate this partial record", fontweight="bold"
    )
    axis_month.set_ylabel("Monthly mean wind speed (m/s)")
    axis_month.set_xlabel("Month (* March and November are partial)")
    labels = [
        f"{value}*" if value in {"2025-03", "2025-11"} else value
        for value in sorted(monthly["month"].unique())
    ]
    axis_month.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    axis_month.legend(ncol=3, frameon=False)
    axis_month.spines[["top", "right"]].set_visible(False)

    axis_availability = figure.add_subplot(grid[0, 1])
    selected = availability[
        availability["column"].isin(
            [
                *[SPEED_AVG[height] for height in HEIGHTS],
                "Direction 30 m Avg [°]",
                "Direction 80 m Avg [°]",
                "Direction 120 m Avg [°]",
                "Temp 10 m Avg [℃]",
                "Temp 120 m Avg [℃]",
                "RH 10 m Avg [%]",
                "Pressure 10 m Avg [kPa]",
            ]
        )
    ].copy()
    short_names = {SPEED_AVG[height]: f"WS {height}m" for height in HEIGHTS} | {
        "Direction 30 m Avg [°]": "WD 30m",
        "Direction 80 m Avg [°]": "WD 80m",
        "Direction 120 m Avg [°]": "WD 120m",
        "Temp 10 m Avg [℃]": "T 10m",
        "Temp 120 m Avg [℃]": "T 120m",
        "RH 10 m Avg [%]": "RH 10m",
        "Pressure 10 m Avg [kPa]": "P 10m",
    }
    selected["label"] = selected["column"].map(short_names)
    selected = selected.sort_values("assessment_coverage_pct")
    axis_availability.barh(
        selected["label"], selected["assessment_coverage_pct"], color="#4C78A8"
    )
    axis_availability.axvline(95, color="#E15759", linestyle="--", linewidth=1)
    axis_availability.set_xlim(0, 101)
    axis_availability.set_xlabel("Coverage of expected 10-minute intervals (%)")
    axis_availability.set_title(
        "120 m channels carry material outages", fontweight="bold"
    )
    axis_availability.spines[["top", "right"]].set_visible(False)

    axis_rose = cast(PolarAxes, figure.add_subplot(grid[1, 0], projection="polar"))
    theta = np.deg2rad(direction["centre_deg"].to_numpy())
    axis_rose.bar(
        theta,
        direction["frequency_pct"],
        width=np.deg2rad(20),
        color="#59A14F",
        edgecolor="white",
        linewidth=0.8,
    )
    axis_rose.set_theta_zero_location("N")
    axis_rose.set_theta_direction(-1)
    axis_rose.set_xticks(
        np.deg2rad(np.arange(0, 360, 45)), ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    )
    axis_rose.set_title(
        "80 m occurrence is concentrated in SW–WSW", fontweight="bold", pad=20
    )

    axis_profile = figure.add_subplot(grid[1, 1])
    means = [common[SPEED_AVG[height]].mean() for height in HEIGHTS]
    axis_profile.plot(means, HEIGHTS, marker="o", linewidth=2.5, color="#F28E2B")
    axis_profile.set_xlim(0, max(means) * 1.15)
    axis_profile.set_xlabel("Concurrent mean wind speed (m/s)")
    axis_profile.set_ylabel("Sensor height (m)")
    axis_profile.set_title(
        f"Concurrent profile uses {len(common):,} intervals", fontweight="bold"
    )
    for x_value, y_value in zip(means, HEIGHTS, strict=True):
        axis_profile.annotate(
            f"{x_value:.2f}",
            (x_value, y_value),
            xytext=(6, 0),
            textcoords="offset points",
        )
    axis_profile.spines[["top", "right"]].set_visible(False)

    figure.suptitle(
        "Met-mast export 617725: strong primary evidence, incomplete annual basis",
        fontsize=16,
        fontweight="bold",
    )
    figure.text(
        0.5,
        -0.01,
        "Assessment window 21 Mar–8 Nov 2025; timezone, calibration, sensor/boom metadata and maintenance log are absent. "
        "Values are not long-term corrected and are not a lender-grade annual resource assessment.",
        ha="center",
        fontsize=9,
    )
    figure.savefig(
        OUT / "met_mast_617725_qc_overview.png",
        dpi=160,
        bbox_inches="tight",
        metadata={"Software": "matplotlib"},
    )
    plt.close(figure)


def main() -> None:
    """Generate all deterministic extracts, analysis summaries, and QA outputs."""
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = resolve_source_path()
    metadata = parse_source_header(raw_path)
    frame = load_source(raw_path)
    timestamps = frame["Date/Time"]
    full_expected = pd.date_range(timestamps.min(), timestamps.max(), freq="10min")
    full_missing = full_expected.difference(pd.DatetimeIndex(timestamps))
    if len(full_missing) != 98:
        raise ValueError(
            f"expected 98 missing source intervals, found {len(full_missing)}"
        )

    assessment = frame[frame["Date/Time"] >= ASSESSMENT_START].copy()
    assessment_end = assessment["Date/Time"].max()
    assessment_expected = pd.date_range(ASSESSMENT_START, assessment_end, freq="10min")
    assessment_missing = assessment_expected.difference(
        pd.DatetimeIndex(assessment["Date/Time"])
    )

    # All complete wind rows must retain their source ordering invariants.
    for height in HEIGHTS:
        average = assessment[SPEED_AVG[height]]
        minimum = assessment[f"Speed {height} m Min [m/s]"]
        maximum = assessment[f"Speed {height} m Max [m/s]"]
        standard_deviation = assessment[f"Speed {height} m SD [m/s]"]
        complete = (
            average.notna()
            & minimum.notna()
            & maximum.notna()
            & standard_deviation.notna()
        )
        invalid = complete & (
            (minimum < 0)
            | (minimum > average)
            | (average > maximum)
            | (maximum > 60)
            | (standard_deviation < 0)
        )
        if invalid.any():
            raise ValueError(f"wind source-order invariant failed at {height} m")

    column_profile = profile_columns(frame)
    wind, common = wind_statistics(assessment, len(assessment_expected))
    monthly = monthly_statistics(assessment, assessment_end)
    direction_summary, direction_sectors = direction_statistics(assessment)
    shear, turbulence = shear_and_turbulence(assessment, common)
    sensitivity = outage_adjusted_sensitivity(
        assessment, float(shear["alpha_five_height_ols_median"])
    )

    availability_rows: list[dict[str, Any]] = []
    for column in frame.columns[1:]:
        count = int(assessment[column].notna().sum())
        availability_rows.append(
            {
                "column": column,
                "valid_count": count,
                "assessment_expected_count": len(assessment_expected),
                "assessment_coverage_pct": 100 * count / len(assessment_expected),
            }
        )
    availability = pd.DataFrame(availability_rows)
    qc = qc_events(frame, assessment, assessment_expected)

    metadata.update(
        {
            "schema": "dutchbay.epc.met_mast_source_metadata.v1",
            "source_filename": raw_path.name,
            "source_sha256": SOURCE_SHA256,
            "source_size_bytes": raw_path.stat().st_size,
            "source_repository": SOURCE_REPOSITORY,
            "source_commit": SOURCE_COMMIT,
            "source_relative_path": SOURCE_RELATIVE_PATH,
            "encoding": "utf-8",
            "delimiter": "tab",
            "header_row_one_based": 13,
            "data_row_count": len(frame),
            "column_count_including_timestamp": len(frame.columns),
            "measurement_column_count": len(frame.columns) - 1,
            "record_start": timestamps.min(),
            "record_end": timestamps.max(),
            "timezone": None,
            "timezone_status": "not stated in source",
            "ingress_date": INGRESS_DATE,
            "ingress_note": "source was supplied by the project owner; no supplier/transmittal metadata accompanied it",
        }
    )
    write_json(OUT / "source_metadata.json", metadata)

    column_profile.to_csv(
        OUT / "column_profile.csv",
        index=False,
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    availability.to_csv(
        OUT / "channel_availability.csv", index=False, lineterminator="\n"
    )
    monthly.to_csv(
        OUT / "monthly_wind_statistics.csv", index=False, lineterminator="\n"
    )
    direction_sectors.to_csv(
        OUT / "wind_direction_80m_sectors.csv", index=False, lineterminator="\n"
    )
    qc.to_csv(OUT / "qc_events.csv", index=False, lineterminator="\n")

    lat = float(metadata["latitude_deg_n"])
    lon = float(metadata["longitude_deg_e"])
    distances = {
        "envision_kalpitiya_60mw_proposal_centre_km": haversine_km(
            lat, lon, 8.203515, 79.701195
        ),
        "dutchbay_model_centroid_km": haversine_km(lat, lon, 8.27, 79.75),
        "nrel_narakkalliya_km": haversine_km(lat, lon, 8.01, 79.43),
        "nrel_karathivu_km": haversine_km(lat, lon, 8.13, 79.48),
        "nrel_puttalam_met_km": haversine_km(lat, lon, 8.02, 79.50),
        "nrel_wellammalal_km": haversine_km(lat, lon, 8.14, 79.44),
    }
    empty_columns = [column for column in frame.columns if frame[column].isna().all()]
    near_empty_columns = [
        column
        for column in frame.columns[1:]
        if 0 < frame[column].notna().mean() < 0.01
    ]
    summary = {
        "schema": "dutchbay.epc.met_mast_analysis_summary.v1",
        "source_sha256": SOURCE_SHA256,
        "source_identity": {
            "repository": SOURCE_REPOSITORY,
            "commit": SOURCE_COMMIT,
            "relative_path": SOURCE_RELATIVE_PATH,
            "filename_token_617725_status": "undocumented; not assumed to be a mast identifier",
            "project_binding": "not stated in source",
            "coordinates": {"latitude_deg_n": lat, "longitude_deg_e": lon},
            "elevation_m": metadata["elevation_m"],
        },
        "record": {
            "embedded_export_created": metadata["embedded_export_created"],
            "start": timestamps.min(),
            "end": timestamps.max(),
            "timezone": None,
            "rows": len(frame),
            "columns_including_timestamp": len(frame.columns),
            "expected_ten_minute_intervals": len(full_expected),
            "present_intervals": len(frame),
            "timestamp_completeness_pct": 100 * len(frame) / len(full_expected),
            "missing_interval_count": len(full_missing),
            "missing_interval_ranges": contiguous_ranges(full_missing),
            "included_flags_raw": metadata["included_flags_raw"],
            "excluded_flags_raw": metadata["excluded_flags_raw"],
        },
        "assessment_window": {
            "start": ASSESSMENT_START,
            "end": assessment_end,
            "reason": "begins after the multi-channel commissioning transition at 2025-03-21 17:50",
            "expected_intervals": len(assessment_expected),
            "present_intervals": len(assessment),
            "timestamp_completeness_pct": 100
            * len(assessment)
            / len(assessment_expected),
            "missing_interval_count": len(assessment_missing),
            "missing_interval_ranges": contiguous_ranges(assessment_missing),
            "duration_days": (assessment_end - ASSESSMENT_START).total_seconds()
            / 86_400,
        },
        "wind_speed_by_height": wind,
        "concurrent_vertical_profile": {
            "valid_count": len(common),
            "expected_interval_coverage_pct": 100
            * len(common)
            / len(assessment_expected),
            "means_ms": {
                str(height): common[SPEED_AVG[height]].mean() for height in HEIGHTS
            },
            "medians_ms": {
                str(height): common[SPEED_AVG[height]].median() for height in HEIGHTS
            },
            "correlations": common[list(SPEED_AVG.values())].corr().to_dict(),
        },
        "shear": shear,
        "turbulence_intensity": turbulence,
        "direction_80m": direction_summary,
        "outage_adjusted_sensitivity": sensitivity,
        "distance_context": distances,
        "quality": {
            "all_null_column_count": len(empty_columns),
            "all_null_columns": empty_columns,
            "near_empty_column_count": len(near_empty_columns),
            "near_empty_columns": near_empty_columns,
            "qc_event_count": len(qc),
            "wind_min_avg_max_order_violations": 0,
            "source_is_filtered_export": True,
            "filter_basis": "Included flags: <Unflagged data>; excluded flags field is blank",
        },
        "evidence_disposition": {
            "classification": "primary met-mast export; partial-period and incompletely documented",
            "usable_for": [
                "preliminary wind-regime characterisation",
                "sensor-level data-quality assessment",
                "directional and vertical-profile screening",
                "future MCP work once timestamp timezone and reference data are supplied",
            ],
            "not_usable_as_standalone_for": [
                "annual long-term mean wind speed",
                "bankable P50/P75/P90",
                "direct validation of the 16.4 km-distant Kalpitiya proposal site",
                "direct validation of the 24.2 km-distant Dutch Bay model centroid",
                "warranty or certified power-performance assessment",
            ],
            "missing_controls": [
                "mast/site identity and project binding",
                "timezone and clock/DST convention",
                "sensor manufacturer, model, serial and calibration certificates",
                "boom orientation and mounting geometry",
                "logger make, scan rate and averaging method",
                "maintenance, icing/lightning/fault and sensor-change log",
                "flag definitions and the rows excluded before export",
                "at least one complete annual cycle",
                "concurrent long-term reference and MCP method",
            ],
            "model_input_status": "HOLD - not promoted into any scenario or lender output",
        },
    }
    write_json(OUT / "analysis_summary.json", summary)
    create_figure(monthly, direction_sectors, availability, common)

    print(f"source_sha256={SOURCE_SHA256}")
    print(f"rows={len(frame)} columns={len(frame.columns)}")
    print(
        "record={}..{} missing_intervals={}".format(
            timestamps.min(), timestamps.max(), len(full_missing)
        )
    )
    print(
        "assessment={}..{} expected={} present={} coverage={:.4f}%".format(
            ASSESSMENT_START,
            assessment_end,
            len(assessment_expected),
            len(assessment),
            100 * len(assessment) / len(assessment_expected),
        )
    )
    print(
        "mean_ws_ms="
        + ",".join(f"{row['height_m']}m:{row['mean_ms']:.5f}" for row in wind)
    )
    print(
        "outage_adjusted_130m_sensitivity_ms={:.5f}".format(
            sensitivity["ratio_proxy_full_window_130m_extrapolated_mean_ms"]
        )
    )
    print(f"qc_events={len(qc)}")


if __name__ == "__main__":
    main()
