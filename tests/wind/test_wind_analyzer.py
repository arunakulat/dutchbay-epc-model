"""Tests for the wind-resource statistical analyzer (wind_resource.wind_analyzer).

Weibull MLE fitting, temporal/seasonal/diurnal patterns, inter-annual
variability, summary stats, and the text report are unit-tested on small
deterministic synthetic wind series. No network or live data is exercised.

KNOWN BUG: config quality_control.ws_min/ws_max are loaded but never applied,
so out-of-range speeds still reach the Weibull MLE. The correct-behaviour QC
filtering test is xfail'd as a visible fix-me.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wind_resource.wind_analyzer import WindAnalyzer


def _ws_frame(
    start: str = "2010-01-01",
    end: str = "2014-12-31 23:00",
    scale: float = 8.0,
    shape: float = 2.5,
    seed: int = 7,
    column: str = "ws_150m",
) -> pd.DataFrame:
    """Build an hourly DataFrame with a 'timestamp' column and a Weibull series."""
    idx = pd.date_range(start, end, freq="h")
    rng = np.random.default_rng(seed)
    ws = rng.weibull(shape, len(idx)) * scale
    return pd.DataFrame({"timestamp": idx, column: ws})


def _seasonal_frame() -> pd.DataFrame:
    """Hourly frame whose monthly mean is a known, deterministic ramp.

    Month m gets a constant wind speed of (5 + m) m/s so that December (17 m/s)
    is unambiguously windiest and January (6 m/s) unambiguously calmest.
    """
    idx = pd.date_range("2012-01-01", "2012-12-31 23:00", freq="h")
    months = idx.month.to_numpy(dtype=float)
    ws = 5.0 + months
    return pd.DataFrame({"timestamp": idx, "ws_150m": ws})


@pytest.fixture
def analyzer() -> WindAnalyzer:
    return WindAnalyzer(_ws_frame())


# --------------------------------------------------------------------------- #
# Construction / validation
# --------------------------------------------------------------------------- #
def test_init_sets_index_and_config(analyzer: WindAnalyzer) -> None:
    assert isinstance(analyzer.df.index, pd.DatetimeIndex)
    # 'timestamp' is consumed into the index, not left as a column.
    assert "timestamp" not in analyzer.df.columns
    assert analyzer.ws_column == "ws_150m"
    # Default config values surfaced as attributes.
    assert analyzer.weibull_method == "mle"
    assert analyzer.ws_min == 0.0
    assert analyzer.ws_max == 50.0


def test_init_accepts_datetimeindex_without_timestamp_column() -> None:
    df = _ws_frame().set_index("timestamp")
    a = WindAnalyzer(df)
    assert isinstance(a.df.index, pd.DatetimeIndex)
    assert a.ws_column == "ws_150m"


def test_init_does_not_mutate_caller_frame() -> None:
    df = _ws_frame()
    cols_before = list(df.columns)
    WindAnalyzer(df)
    # __init__ copies; caller's frame keeps its 'timestamp' column intact.
    assert list(df.columns) == cols_before


def test_init_custom_ws_column() -> None:
    df = _ws_frame(column="ws_120m")
    a = WindAnalyzer(df, ws_column="ws_120m")
    assert a.ws_column == "ws_120m"
    assert a.fit_weibull()["mean_ws"] > 0


def test_init_missing_ws_column_raises() -> None:
    df = _ws_frame()
    with pytest.raises(ValueError, match="not found in DataFrame"):
        WindAnalyzer(df, ws_column="ws_999m")


def test_init_missing_timestamp_and_index_raises() -> None:
    df = _ws_frame().reset_index(drop=True)
    df = df.drop(columns=["timestamp"])  # no timestamp col, RangeIndex
    with pytest.raises(ValueError, match="timestamp"):
        WindAnalyzer(df)


def test_init_bad_config_path_raises() -> None:
    df = _ws_frame()
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        WindAnalyzer(df, config_path="/nonexistent/era5_config.yaml")


def test_init_missing_config_key_raises(tmp_path) -> None:
    cfg = tmp_path / "bad.yaml"
    # Missing the entire 'weibull' section -> KeyError surfaced from _load_config.
    cfg.write_text("quality_control:\n  ws_min: 0.0\n  ws_max: 50.0\n")
    with pytest.raises(KeyError, match="Missing required config key"):
        WindAnalyzer(_ws_frame(), config_path=str(cfg))


# --------------------------------------------------------------------------- #
# Weibull fitting
# --------------------------------------------------------------------------- #
def test_fit_weibull_recovers_known_parameters() -> None:
    # Large sample drawn from a known Weibull -> MLE should recover k, c well.
    a = WindAnalyzer(_ws_frame(scale=9.0, shape=2.2, seed=11))
    res = a.fit_weibull()
    assert set(res) == {"shape_k", "scale_c", "r_squared", "ks_pvalue", "mean_ws"}
    assert res["shape_k"] == pytest.approx(2.2, abs=0.15)
    assert res["scale_c"] == pytest.approx(9.0, abs=0.4)
    # Fit on data drawn from the same family must be excellent.
    assert res["r_squared"] > 0.99
    assert res["mean_ws"] > 0


def test_fit_weibull_outputs_are_floats(analyzer: WindAnalyzer) -> None:
    res = analyzer.fit_weibull()
    assert all(isinstance(v, float) for v in res.values())
    assert 0.0 <= res["ks_pvalue"] <= 1.0


def test_fit_weibull_mean_matches_data(analyzer: WindAnalyzer) -> None:
    expected = analyzer.df["ws_150m"].dropna().mean()
    assert analyzer.fit_weibull()["mean_ws"] == pytest.approx(expected, rel=1e-9)


def test_fit_weibull_ignores_nan() -> None:
    df = _ws_frame()
    df.loc[df.index[:50], "ws_150m"] = np.nan
    a = WindAnalyzer(df)
    res = a.fit_weibull()
    # mean_ws is computed on the NaN-dropped data.
    assert res["mean_ws"] == pytest.approx(a.df["ws_150m"].dropna().mean(), rel=1e-9)
    assert np.isfinite(res["shape_k"]) and np.isfinite(res["scale_c"])


def test_fit_weibull_unsupported_method_raises(tmp_path) -> None:
    cfg = tmp_path / "mom.yaml"
    cfg.write_text(
        "weibull:\n  method: method_of_moments\n"
        "quality_control:\n  ws_min: 0.0\n  ws_max: 50.0\n"
    )
    a = WindAnalyzer(_ws_frame(), config_path=str(cfg))
    with pytest.raises(ValueError, match="Unsupported Weibull method"):
        a.fit_weibull()


def test_fit_weibull_filters_out_of_range_speeds() -> None:
    """Speeds outside [ws_min, ws_max] are excluded before the MLE.

    Regression: the quality_control ws_min/ws_max bounds were loaded in __init__
    but never applied; out-of-range spikes reached the fit and dragged scale_c.

    We inject a block of absurd 500 m/s spikes (well above ws_max=50). A QC
    filter would drop them and leave the fit close to the clean one; without
    it, scale_c is dragged far above the clean value.
    """
    clean = WindAnalyzer(_ws_frame(scale=8.0, seed=3)).fit_weibull()

    df = _ws_frame(scale=8.0, seed=3)
    df.loc[df.index[:200], "ws_150m"] = 500.0  # above ws_max == 50.0
    polluted = WindAnalyzer(df).fit_weibull()

    # If QC filtering worked, the contaminated fit would match the clean one.
    assert polluted["scale_c"] == pytest.approx(clean["scale_c"], rel=0.05)


# --------------------------------------------------------------------------- #
# Temporal patterns
# --------------------------------------------------------------------------- #
def test_temporal_patterns_structure_and_extremes() -> None:
    a = WindAnalyzer(_seasonal_frame())
    res = a.analyze_temporal_patterns()
    assert set(res) == {
        "monthly",
        "seasonal",
        "hourly",
        "windiest_month",
        "calmest_month",
        "monthly_range_ratio",
    }
    # Monthly means are the deterministic ramp 5 + month.
    assert res["monthly"][12] == pytest.approx(17.0)
    assert res["monthly"][1] == pytest.approx(6.0)
    assert res["windiest_month"] == 12
    assert res["calmest_month"] == 1
    assert res["monthly_range_ratio"] == pytest.approx(17.0 / 6.0)


def test_temporal_patterns_full_coverage() -> None:
    a = WindAnalyzer(_ws_frame())  # multi-year hourly => all months/hours present
    res = a.analyze_temporal_patterns()
    assert sorted(res["monthly"]) == list(range(1, 13))
    assert sorted(res["hourly"]) == list(range(0, 24))
    assert set(res["seasonal"]) == {"DJF", "MAM", "JJA", "SON"}


@pytest.mark.parametrize(
    ("month", "season"),
    [
        (12, "DJF"),
        (1, "DJF"),
        (2, "DJF"),
        (3, "MAM"),
        (5, "MAM"),
        (6, "JJA"),
        (8, "JJA"),
        (9, "SON"),
        (11, "SON"),
    ],
)
def test_month_to_season(month: int, season: str) -> None:
    assert WindAnalyzer._month_to_season(month) == season


# --------------------------------------------------------------------------- #
# Inter-annual variability
# --------------------------------------------------------------------------- #
def test_interannual_variability_known_means() -> None:
    # Build a frame where each whole year has a distinct constant wind speed.
    frames = []
    yearly = {2010: 7.0, 2011: 8.0, 2012: 9.0}
    for year, ws in yearly.items():
        idx = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h")
        frames.append(pd.DataFrame({"timestamp": idx, "ws_150m": ws}))
    df = pd.concat(frames, ignore_index=True)
    res = WindAnalyzer(df).calculate_interannual_variability()

    annual = np.array([7.0, 8.0, 9.0])
    assert res["mean_annual_ws"] == pytest.approx(annual.mean())
    assert res["std_annual_ws"] == pytest.approx(annual.std(ddof=1))  # pandas std
    assert res["cov_annual_ws"] == pytest.approx(
        annual.std(ddof=1) / annual.mean() * 100
    )
    assert res["min_year"] == 2010 and res["max_year"] == 2012
    assert res["min_year_ws"] == pytest.approx(7.0)
    assert res["max_year_ws"] == pytest.approx(9.0)
    assert isinstance(res["min_year"], int) and isinstance(res["max_year"], int)


# --------------------------------------------------------------------------- #
# Summary stats / analyze_all / report
# --------------------------------------------------------------------------- #
def test_summary_stats_match_pandas() -> None:
    a = WindAnalyzer(_ws_frame())
    res = a._calculate_summary_stats()
    ws = a.df["ws_150m"]
    assert res["mean"] == pytest.approx(ws.mean())
    assert res["std"] == pytest.approx(ws.std())
    assert res["min"] == pytest.approx(ws.min())
    assert res["max"] == pytest.approx(ws.max())
    assert res["p10"] == pytest.approx(ws.quantile(0.10))
    assert res["p50"] == pytest.approx(ws.quantile(0.50))
    assert res["p90"] == pytest.approx(ws.quantile(0.90))
    assert res["count"] == len(ws)
    assert res["p10"] <= res["p50"] <= res["p90"]


def test_analyze_all_aggregates_sections(analyzer: WindAnalyzer) -> None:
    res = analyzer.analyze_all()
    assert set(res) == {"weibull", "temporal", "variability", "summary_stats"}
    # Sub-results equal the individually-computed ones (deterministic data).
    assert res["weibull"] == analyzer.fit_weibull()
    assert res["summary_stats"] == analyzer._calculate_summary_stats()
    assert res["temporal"]["windiest_month"] in range(1, 13)


def test_generate_summary_report_contents(analyzer: WindAnalyzer) -> None:
    report = analyzer.generate_summary_report()
    assert isinstance(report, str)
    for header in (
        "WIND RESOURCE ANALYSIS SUMMARY",
        "WEIBULL DISTRIBUTION",
        "SUMMARY STATISTICS",
        "TEMPORAL PATTERNS",
        "INTER-ANNUAL VARIABILITY",
    ):
        assert header in report
    # Numbers from the analysis are rendered into the report body.
    wb = analyzer.fit_weibull()
    assert f"Shape k: {wb['shape_k']:.3f}" in report
