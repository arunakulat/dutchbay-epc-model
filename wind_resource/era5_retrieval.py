"""Config-driven ERA5 retrieval + site AEP for any RE project location.

Retrieves the Copernicus CDS ERA5 single-levels TIMESERIES product (ARCO/Zarr) for a
single lat/lon point, builds a clean hourly hub-height wind series, and computes net
AEP through the project's canonical power curve via :class:`EnergyCalculator`.

Generalises the wind-resource pipeline beyond DutchBay: any user supplies their own
Copernicus CDS key (in ``~/.cdsapirc``) and a project centre (lat/lon), and the tool
fetches + computes for that site. See issue #177.

Reference period (issue #178 follow-up):
- ``mode: latest`` resolves the most recent ``n_years`` *complete* ERA5 final-data years
  at assessment time (``end_year = current_year - end_year_lag``, lag 2 covers the ~2-3
  month final-data latency), then **freezes** the resolved window into the result's
  ``vintage`` block for reproducibility. ``mode: fixed`` pins an explicit span.
- A **coverage guard** asserts the retrieved series fully covers the requested window
  (leap-aware), so a partial/latency-truncated series never silently passes.

GWTF: config-first (YAML), fully typed, no hardcoded site constants, no ``argparse``
or ``input()``. Credentials live ONLY in ``~/.cdsapirc`` (cdsapi default) and are NEVER
written to the repo.

Typical usage:
    >>> from wind_resource.era5_retrieval import ERA5RequestConfig, run
    >>> cfg = ERA5RequestConfig.from_yaml(
    ...     "wind_resource/config/era5_request_kalpitiya.yaml")
    >>> result = run(cfg)            # downloads + validates coverage + computes
    >>> print(result["net_aep_p50_gwh"], result["vintage"])
"""

from __future__ import annotations

import datetime as _dt
import glob
import json
import logging
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# CDS ARCO point-timeseries product + the variables needed for hub-height winds.
ERA5_TIMESERIES_DATASET = "reanalysis-era5-single-levels-timeseries"
ERA5_WIND_VARIABLES: Tuple[str, ...] = (
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "100m_u_component_of_wind",
    "100m_v_component_of_wind",
    "surface_pressure",
)


class ERA5CoverageError(RuntimeError):
    """Raised when a retrieved ERA5 series does not fully cover the requested window."""


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def expected_hours_for_years(start_year: int, end_year: int) -> int:
    """Total hours in the calendar-year span ``[start, end]`` (leap-aware)."""
    return sum((366 if _is_leap(y) else 365) * 24 for y in range(start_year, end_year + 1))


def _resolve_reference(download: Dict[str, Any]) -> Tuple[int, int, str]:
    """Resolve ``(start_year, end_year, mode)`` from a ``download`` config block.

    Supports:
      ``reference: {mode: latest, n_years: 20, end_year_lag: 2}`` -- rolling, frozen per run
      ``reference: {mode: fixed, start: 2005, end: 2024}``
      ``years: {start: 2005, end: 2024}`` -- legacy, treated as fixed

    For ``latest``, ``end_year = current_year - end_year_lag`` (default lag 2 guarantees
    complete ERA5 *final* data given the ~2-3 month publication latency); the resolved
    window is then frozen into the run's vintage for reproducibility.
    """
    ref = download.get("reference")
    if ref and str(ref.get("mode")) == "latest":
        n_years = int(ref.get("n_years", 20))
        lag = int(ref.get("end_year_lag", 2))
        end_year = _dt.date.today().year - lag
        return end_year - n_years + 1, end_year, "latest"
    if ref and str(ref.get("mode")) == "fixed":
        return int(ref["start"]), int(ref["end"]), "fixed"
    years = download.get("years", {})
    return int(years["start"]), int(years["end"]), "fixed"


@dataclass(frozen=True)
class ERA5RequestConfig:
    """Immutable ERA5 retrieval request for one RE project site.

    Every field is config-supplied (CCCDIR); no hardcoded site constants. The year span
    may be resolved from a ``latest`` reference at load time, then frozen here.
    """

    project_name: str
    latitude: float
    longitude: float
    start_year: int
    end_year: int
    hub_height_m: float = 150.0
    reference_height_low_m: float = 10.0
    reference_height_high_m: float = 100.0
    alpha_min: float = 0.05
    alpha_max: float = 0.40
    output_dir: str = "/tmp/era5_cache"
    turbine_model: str = "envision_en171_6p5"
    num_turbines: int = 23
    reference_mode: str = "fixed"
    resolved_at: str = ""
    strict_coverage: bool = True

    @classmethod
    def from_yaml(cls, path: str) -> "ERA5RequestConfig":
        """Load a request config from YAML (``project:`` / ``download:`` / ``turbine:``)."""
        with open(path) as f:
            raw = yaml.safe_load(f)
        proj = raw.get("project", {})
        dl = raw.get("download", {})
        turb = raw.get("turbine", {})
        start_year, end_year, mode = _resolve_reference(dl)
        return cls(
            project_name=str(proj["name"]),
            latitude=float(proj["latitude"]),
            longitude=float(proj["longitude"]),
            start_year=start_year,
            end_year=end_year,
            # Turbine identity is config-required (ARCH-01) — no EN-171/23/150 m
            # fallbacks that would silently compute AEP for the wrong machine.
            hub_height_m=float(turb["hub_height_m"]),
            alpha_min=float(dl.get("alpha_min", 0.05)),
            alpha_max=float(dl.get("alpha_max", 0.40)),
            output_dir=str(dl.get("output_dir", "outputs/era5_cache")),
            turbine_model=str(turb["model"]),
            num_turbines=int(turb["num_turbines"]),
            reference_mode=mode,
            resolved_at=_dt.datetime.now().isoformat(timespec="seconds"),
            strict_coverage=bool(dl.get("strict_coverage", True)),
        )

    @property
    def date_range(self) -> str:
        """CDS ``date`` range string, e.g. ``2005-01-01/2024-12-31``."""
        return f"{self.start_year}-01-01/{self.end_year}-12-31"

    @property
    def expected_hours(self) -> int:
        """Leap-aware hour count for the full requested year span."""
        return expected_hours_for_years(self.start_year, self.end_year)


def ensure_cdsapirc(
    url: str | None = None,
    key: str | None = None,
    path: str | None = None,
) -> Path:
    """Ensure a ``~/.cdsapirc`` exists; optionally write it from explicit credentials.

    Credentials are resolved in order: explicit ``url``/``key`` args, then the
    ``CDSAPI_URL`` / ``CDSAPI_KEY`` environment variables. If neither is supplied and
    the file is absent, raises with setup instructions. The key is NEVER committed --
    it is written only to the user's ``~/.cdsapirc`` with ``0600`` perms.
    """
    rc = Path(path or os.path.expanduser("~/.cdsapirc"))
    url = url or os.environ.get("CDSAPI_URL")
    key = key or os.environ.get("CDSAPI_KEY")
    if url and key:
        rc.write_text(f"url: {url}\nkey: {key}\n")
        rc.chmod(0o600)
        logger.info("Wrote CDS credentials to %s (0600)", rc)
    elif not rc.exists():
        raise FileNotFoundError(
            f"No CDS credentials at {rc}. Get an API token at "
            "https://cds.climate.copernicus.eu (profile -> API token), then create "
            "~/.cdsapirc (lines 'url:' and 'key:') or set CDSAPI_URL and CDSAPI_KEY."
        )
    return rc


def retrieve_era5_timeseries(config: ERA5RequestConfig) -> Path:
    """Download the ERA5 point timeseries for the configured site; return the .nc path.

    Uses the ARCO ``reanalysis-era5-single-levels-timeseries`` product, which returns a
    zipped NetCDF; this unpacks it and returns the extracted NetCDF path. Requires the
    optional ``[wind]`` extra (cdsapi) and valid ``~/.cdsapirc`` credentials.
    """
    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "ERA5 retrieval requires the [wind] extra: pip install cdsapi xarray netcdf4"
        ) from exc

    ensure_cdsapirc()
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = config.project_name.lower().replace(" ", "_")
    zip_path = out_dir / f"era5_{safe}_{config.start_year}_{config.end_year}.zip"

    logger.info(
        "Retrieving ERA5 timeseries for %s (%.4f, %.4f) %s",
        config.project_name,
        config.latitude,
        config.longitude,
        config.date_range,
    )
    client = cdsapi.Client()
    client.retrieve(
        ERA5_TIMESERIES_DATASET,
        {
            "variable": list(ERA5_WIND_VARIABLES),
            "location": {"longitude": config.longitude, "latitude": config.latitude},
            "date": [config.date_range],
            "data_format": "netcdf",
        },
        str(zip_path),
    )

    extract_dir = out_dir / f"{safe}_{config.start_year}_{config.end_year}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    ncs = sorted(glob.glob(str(extract_dir / "*.nc")))
    if not ncs:
        raise RuntimeError(f"No NetCDF found in CDS response {zip_path}")
    logger.info("Extracted %s", ncs[0])
    return Path(ncs[0])


def build_hub_height_series(nc_path: Path, config: ERA5RequestConfig) -> pd.DataFrame:
    """Convert an ERA5 point NetCDF to an hourly hub-height wind series.

    Computes ws10/ws100 from u/v components, derives per-hour wind shear ``alpha``
    (clipped to the config bounds), and extrapolates to ``hub_height_m`` via the power
    law. Returns a DataFrame indexed by timestamp with a ``ws_<hub>m`` column.
    """
    import xarray as xr

    ds = xr.open_dataset(nc_path)
    tname = "valid_time" if "valid_time" in ds.coords else "time"
    times = pd.to_datetime(ds[tname].values)

    def comp(*names: str) -> np.ndarray:
        for n in names:
            if n in ds:
                return np.asarray(ds[n].values, dtype="float64").ravel()
        raise KeyError(f"None of {names} in ERA5 dataset {list(ds.data_vars)}")

    ws10 = np.hypot(comp("u10"), comp("v10"))
    ws100 = np.hypot(comp("u100"), comp("v100"))
    h_lo = config.reference_height_low_m
    h_hi = config.reference_height_high_m
    h_t = config.hub_height_m
    with np.errstate(divide="ignore", invalid="ignore"):
        alpha = np.log(ws100 / ws10) / np.log(h_hi / h_lo)
    alpha = np.clip(
        np.nan_to_num(alpha, nan=config.alpha_min), config.alpha_min, config.alpha_max
    )
    ws_hub = ws100 * (h_t / h_hi) ** alpha

    col = f"ws_{int(h_t)}m"
    df = pd.DataFrame({col: ws_hub, "wind_shear_alpha": alpha}, index=times)
    df.index.name = "timestamp"
    logger.info(
        "Built %d-h hub series for %s: mean %.2f m/s (%.2f yr)",
        len(df),
        config.project_name,
        float(df[col].mean()),
        len(df) / 8760.0,
    )
    return df


def validate_coverage(series: pd.DataFrame, config: ERA5RequestConfig) -> Dict[str, Any]:
    """Assert the retrieved series fully covers the requested window (no silent partials).

    Compares the row count against the leap-aware expected hours for the year span. On a
    shortfall, raises :class:`ERA5CoverageError` (if ``strict_coverage``) or warns -- the
    common cause is ERA5 publication latency at the recent edge (the 8760-vs-8640 case).
    """
    got = int(len(series))
    expected = config.expected_hours
    complete = got == expected
    if not complete:
        span = f"{series.index.min()} .. {series.index.max()}" if got else "(empty)"
        msg = (
            f"ERA5 coverage incomplete for {config.project_name} "
            f"{config.start_year}-{config.end_year}: got {got} h, expected {expected} h "
            f"(missing {expected - got}). Retrieved span {span}. Likely ERA5 publication "
            "latency at the recent edge -- pin an earlier end year (or raise end_year_lag)."
        )
        if config.strict_coverage:
            raise ERA5CoverageError(msg)
        logger.warning(msg)
    return {
        "actual_hours": got,
        "expected_hours": expected,
        "coverage_complete": complete,
        "missing_hours": max(0, expected - got),
    }


def compute_site_aep(series: pd.DataFrame, config: ERA5RequestConfig) -> Dict[str, Any]:
    """Compute net AEP from a hub-height series via :class:`EnergyCalculator`."""
    from wind_resource.energy_calculator import EnergyCalculator

    col = f"ws_{int(config.hub_height_m)}m"
    calc = EnergyCalculator(
        df=series,
        ws_column=col,
        turbine_model=config.turbine_model,
        num_turbines=config.num_turbines,
    )
    net = calc.calculate_net_aep()
    return {
        "project": config.project_name,
        "latitude": config.latitude,
        "longitude": config.longitude,
        "hours": int(len(series)),
        "years": round(len(series) / 8760.0, 2),
        "mean_ws_hub_ms": round(float(series[col].mean()), 3),
        "net_aep_p50_gwh": round(net["net_aep_p50_mwh"] / 1000.0, 1),
        "net_aep_p90_gwh": round(net["net_aep_p90_mwh"] / 1000.0, 1),
        "capacity_factor_p50": round(net["capacity_factor_net_p50"] / 100.0, 4),
    }


def run(config: ERA5RequestConfig) -> Dict[str, Any]:
    """End-to-end: retrieve -> hub series -> coverage guard -> net AEP (+ frozen vintage)."""
    nc_path = retrieve_era5_timeseries(config)
    series = build_hub_height_series(nc_path, config)
    coverage = validate_coverage(series, config)  # raises on a silent partial (strict)
    result = compute_site_aep(series, config)
    result["coverage"] = coverage
    result["vintage"] = {
        "reference_mode": config.reference_mode,
        "start_year": config.start_year,
        "end_year": config.end_year,
        "resolved_at": config.resolved_at,
        "dataset": ERA5_TIMESERIES_DATASET,
        "latitude": config.latitude,
        "longitude": config.longitude,
        "expected_hours": config.expected_hours,
        "actual_hours": coverage["actual_hours"],
        "coverage_complete": coverage["coverage_complete"],
    }
    logger.info(
        "%s: %.1f GWh P50 (CF %.1f%%) from %s vintage %d-%d (%d h, %s)",
        config.project_name,
        result["net_aep_p50_gwh"],
        result["capacity_factor_p50"] * 100,
        config.reference_mode,
        config.start_year,
        config.end_year,
        coverage["actual_hours"],
        "complete" if coverage["coverage_complete"] else "INCOMPLETE",
    )
    return result


def main() -> None:
    """Config-driven entry point (no argparse; honours ``ERA5_REQUEST_CONFIG``)."""
    cfg_path = os.environ.get(
        "ERA5_REQUEST_CONFIG", "wind_resource/config/era5_request_kalpitiya.yaml"
    )
    result = run(ERA5RequestConfig.from_yaml(cfg_path))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
