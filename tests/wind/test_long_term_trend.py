"""Tests for the long-term resource & trend feature (issue #178).

Trend maths + classifier + report rendering are unit-tested on synthetic series; the
lender-workbook wiring is tested via openpyxl. No live CDS is exercised.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from wind_resource import era5_retrieval
from wind_resource.era5_retrieval import ERA5RequestConfig
from wind_resource.long_term_trend import (
    MIN_TREND_YEARS,
    TrendResult,
    _classify,
    analyze_long_term_resource,
    compute_trend,
    period_aep_table,
    recommend_p50,
    reference_periods,
)


def _annual(vals, start=2005):
    return pd.Series(
        list(vals), index=pd.Index(range(start, start + len(vals))), dtype=float
    )


def _ws_series(start, end, scale=8.0):
    idx = pd.date_range(f"{start}-01-01", f"{end}-12-31 23:00", freq="h")
    rng = np.random.default_rng(7)
    return pd.DataFrame({"ws_150m": rng.weibull(2.5, len(idx)) * scale}, index=idx)


def _trend(classification):
    return TrendResult(
        start_year=2005,
        end_year=2024,
        n_years=20,
        mean_ws_ms=7.4,
        cov_pct=3.0,
        mk_tau=-0.2,
        mk_pvalue=0.04,
        significant=True,
        sen_slope_per_decade=-0.07,
        sen_ci_low_per_decade=-0.13,
        sen_ci_high_per_decade=-0.01,
        ols_slope_per_decade=-0.06,
        ols_r2=0.07,
        decade_means={"2010-2019": 7.5},
        classification=classification,
        classification_note="x",
    )


def test_classify_logic():
    assert _classify(0.04, 0.07)[0] == "decadal_regime_shift"  # significant + weak
    assert _classify(0.04, 0.30)[0] == "secular_trend"  # significant + strong
    assert _classify(0.20, 0.05)[0] == "decadal_variability"  # not significant


def test_compute_trend_declining():
    t = compute_trend(_annual([8.0 - 0.04 * i for i in range(20)]))
    assert t.significant
    assert t.mk_tau < 0 and t.sen_slope_per_decade < 0
    assert t.n_years == 20


def test_compute_trend_flat_not_significant():
    rng = np.random.default_rng(1)
    t = compute_trend(_annual([7.5 + rng.normal(0, 0.1) for _ in range(20)]))
    assert not t.significant
    assert t.classification == "decadal_variability"


def test_reference_periods_clamped():
    pers = reference_periods(2020, 2024)  # only 5 yr of record
    # every window start is clamped to the record start
    assert all(s >= 2020 for (s, _e, _k, _r) in pers)


def test_period_aep_table_positive():
    cfg = ERA5RequestConfig(
        project_name="T",
        latitude=8.27,
        longitude=79.75,
        start_year=2005,
        end_year=2024,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )
    table = period_aep_table(_ws_series(2005, 2024), cfg, reference_periods(2005, 2024))
    assert len(table) >= 3
    assert all(r["net_aep_p50_gwh"] > 0 and 0 < r["capacity_factor"] < 1 for r in table)


def test_recommend_p50_by_classification():
    table = [
        {
            "key": "recent_5yr",
            "net_aep_p50_gwh": 396,
            "capacity_factor": 0.30,
            "role": "d",
        },
        {
            "key": "current_decade",
            "net_aep_p50_gwh": 402,
            "capacity_factor": 0.31,
            "role": "c",
        },
        {
            "key": "longterm_20yr",
            "net_aep_p50_gwh": 422,
            "capacity_factor": 0.32,
            "role": "l",
        },
    ]
    assert (
        recommend_p50(_trend("decadal_regime_shift"), table)["central_basis"]
        == "current_decade"
    )
    assert (
        recommend_p50(_trend("secular_trend"), table)["central_basis"] == "recent_5yr"
    )
    assert (
        recommend_p50(_trend("decadal_variability"), table)["central_basis"]
        == "longterm_20yr"
    )
    r = recommend_p50(_trend("decadal_regime_shift"), table)
    assert (r["p50_gwh"], r["downside_gwh"], r["upside_gwh"]) == (402, 396, 422)


def test_analyze_renders_markdown_and_dataframe():
    cfg = ERA5RequestConfig(
        project_name="T",
        latitude=8.27,
        longitude=79.75,
        start_year=2005,
        end_year=2024,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )
    out = analyze_long_term_resource(cfg, series=_ws_series(2005, 2024))
    md = out["markdown"]
    assert "## Long-Term Wind Resource & Trend" in md
    assert "IEC 61400-15" in md
    assert "Recommended P50 basis" in md
    sdf = out["summary_df"]
    assert list(sdf.columns) == ["Metric", "Value"]
    assert (sdf["Metric"] == "Recommended P50 (GWh)").any()
    assert (sdf["Metric"] == "Bankability basis").any()


def test_executive_workbook_resource_trend_sheet(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from analytics.executive_workbook import build_executive_workbook

    d = pd.DataFrame({"a": [1, 2, 3]})
    trend_df = pd.DataFrame(
        {"Metric": ["Classification"], "Value": ["decadal regime shift"]}
    )
    out = build_executive_workbook(
        d, d, d, d, d, tmp_path / "wb.xlsx", resource_trend_df=trend_df
    )
    assert "ResourceTrend" in openpyxl.load_workbook(out).sheetnames
    # backward-compatible: omitting it creates no such sheet
    out2 = build_executive_workbook(d, d, d, d, d, tmp_path / "wb2.xlsx")
    assert "ResourceTrend" not in openpyxl.load_workbook(out2).sheetnames


# ---------------------------------------------------------------------------
# Live invocation on the wind-assessment path (era5_retrieval.run) — #656.
# The trend is computed on the SAME already-retrieved hub-height series (no second
# CDS fetch), is opt-in (analyze_trend), and never changes the frozen AEP/KPIs.
# ---------------------------------------------------------------------------


def _wire_fake_retrieval(monkeypatch, series, calls):
    """Patch run()'s retrieval stages to synthetic outputs and count CDS retrievals."""
    from pathlib import Path

    def _fake_retrieve(c):
        calls["retrieve"] = calls.get("retrieve", 0) + 1
        return Path("/tmp/sentinel.nc")

    def _fake_build(nc, c):
        calls["build"] = calls.get("build", 0) + 1
        return series

    def _fake_validate(s, c):
        return {
            "actual_hours": len(s),
            "expected_hours": len(s),
            "coverage_complete": True,
            "missing_hours": 0,
        }

    monkeypatch.setattr(era5_retrieval, "retrieve_era5_timeseries", _fake_retrieve)
    monkeypatch.setattr(era5_retrieval, "build_hub_height_series", _fake_build)
    monkeypatch.setattr(era5_retrieval, "validate_coverage", _fake_validate)
    # NOTE: compute_site_aep is deliberately NOT mocked — it runs on the synthetic series
    # (no CDS), and analyze_long_term_resource's period_aep_table calls the real one, so a
    # simplified stub would break its contract. The retrieval stages above are what would hit
    # the network; leaving compute real keeps the AEP figures internally consistent.


def _run_cfg(analyze_trend, start=2005, end=2024):
    return ERA5RequestConfig(
        project_name="T",
        latitude=8.27,
        longitude=79.75,
        start_year=start,
        end_year=end,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        analyze_trend=analyze_trend,
    )


def test_run_default_omits_trend(monkeypatch):
    """analyze_trend defaults OFF: run() attaches no trend and stays byte-identical."""
    calls: dict = {}
    _wire_fake_retrieval(monkeypatch, _ws_series(2005, 2024), calls)
    result = era5_retrieval.run(_run_cfg(analyze_trend=False))
    assert "long_term_trend" not in result
    # Only the retrieval + AEP happened; the trend added no work.
    assert calls == {"retrieve": 1, "build": 1}


def test_run_analyze_trend_reuses_series_no_second_fetch(monkeypatch):
    """Opt-in trend runs on the already-retrieved series — exactly ONE CDS retrieval."""
    calls: dict = {}
    _wire_fake_retrieval(monkeypatch, _ws_series(2005, 2024), calls)
    baseline_aep = era5_retrieval.run(_run_cfg(analyze_trend=False))["net_aep_p50_gwh"]
    calls.clear()
    result = era5_retrieval.run(_run_cfg(analyze_trend=True))
    # The trend must NOT trigger a second retrieve/build (it reuses run()'s series).
    assert calls["retrieve"] == 1
    assert calls["build"] == 1
    trend = result["long_term_trend"]
    assert trend["analyzed"] is True
    assert "## Long-Term Wind Resource & Trend" in trend["markdown"]
    # run() attaches a JSON-safe projection (records), not the raw DataFrame: each row is a
    # {"Metric": ..., "Value": ...} dict verbatim from trend_summary_dataframe.
    assert isinstance(trend["summary_df"], list)
    assert all(set(row) == {"Metric", "Value"} for row in trend["summary_df"])
    # The TrendResult dataclass is likewise projected to a plain (JSON-safe) dict.
    assert isinstance(trend["trend"], dict)
    assert trend["trend"]["n_years"] == 20
    # Report/VALIDATE-only: the headline frozen AEP is unchanged by the trend disclosure.
    assert result["net_aep_p50_gwh"] == baseline_aep


def test_run_short_series_degrades_explicitly(monkeypatch):
    """A record shorter than the trend minimum degrades explicitly, not silently."""
    calls: dict = {}
    short = _ws_series(2021, 2024)  # 4 yr < MIN_TREND_YEARS
    _wire_fake_retrieval(monkeypatch, short, calls)
    result = era5_retrieval.run(_run_cfg(analyze_trend=True, start=2021, end=2024))
    trend = result["long_term_trend"]
    assert trend["analyzed"] is False
    assert str(MIN_TREND_YEARS) in trend["reason"]
    assert "markdown" not in trend


def test_run_analyze_trend_result_is_json_serializable(monkeypatch):
    """The whole run() result round-trips through json.dumps with the trend attached (#656).

    Regression for the Fable blocker: the trend block carried a TrendResult dataclass and a
    pandas DataFrame, so main()'s json.dumps(result) crashed with 'Object of type TrendResult
    is not JSON serializable' AFTER a full CDS retrieval + analysis. run() must now attach a
    JSON-safe projection so the success path serializes cleanly.
    """
    calls: dict = {}
    _wire_fake_retrieval(monkeypatch, _ws_series(2005, 2024), calls)  # 20 yr >= minimum
    result = era5_retrieval.run(_run_cfg(analyze_trend=True))
    assert result["long_term_trend"]["analyzed"] is True

    # Round-trips without a TypeError, and the projection survives the round-trip intact.
    round_tripped = json.loads(json.dumps(result))
    rt_trend = round_tripped["long_term_trend"]
    assert rt_trend["trend"]["n_years"] == 20
    assert rt_trend["summary_df"] and all(
        set(row) == {"Metric", "Value"} for row in rt_trend["summary_df"]
    )
    assert "## Long-Term Wind Resource & Trend" in rt_trend["markdown"]


def test_run_analyze_trend_does_not_mutate_committed_aep(monkeypatch):
    """Disclose-don't-mutate: the frozen net AEP is identical with the trend on and off (#656)."""
    calls: dict = {}
    _wire_fake_retrieval(monkeypatch, _ws_series(2005, 2024), calls)
    off = era5_retrieval.run(_run_cfg(analyze_trend=False))
    on = era5_retrieval.run(_run_cfg(analyze_trend=True))
    for key in ("net_aep_p50_gwh", "net_aep_p90_gwh", "capacity_factor_p50"):
        assert on[key] == off[key]
    # The trend is purely additive: the only new top-level key is the disclosure block.
    assert set(on) - set(off) == {"long_term_trend"}
