"""Tests for the long-term resource & trend feature (issue #178).

Trend maths + classifier + report rendering are unit-tested on synthetic series; the
lender-workbook wiring is tested via openpyxl. No live CDS is exercised.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wind_resource.era5_retrieval import ERA5RequestConfig
from wind_resource.long_term_trend import (
    TrendResult,
    _classify,
    analyze_long_term_resource,
    compute_trend,
    period_aep_table,
    recommend_p50,
    reference_periods,
)


def _annual(vals, start=2005):
    return pd.Series(list(vals), index=pd.Index(range(start, start + len(vals))), dtype=float)


def _ws_series(start, end, scale=8.0):
    idx = pd.date_range(f"{start}-01-01", f"{end}-12-31 23:00", freq="h")
    rng = np.random.default_rng(7)
    return pd.DataFrame({"ws_150m": rng.weibull(2.5, len(idx)) * scale}, index=idx)


def _trend(classification):
    return TrendResult(
        start_year=2005, end_year=2024, n_years=20, mean_ws_ms=7.4, cov_pct=3.0,
        mk_tau=-0.2, mk_pvalue=0.04, significant=True, sen_slope_per_decade=-0.07,
        sen_ci_low_per_decade=-0.13, sen_ci_high_per_decade=-0.01,
        ols_slope_per_decade=-0.06, ols_r2=0.07,
        decade_means={"2010-2019": 7.5}, classification=classification, classification_note="x",
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
    cfg = ERA5RequestConfig(project_name="T", latitude=8.27, longitude=79.75,
                            start_year=2005, end_year=2024,
                            hub_height_m=150.0, turbine_model="iea_reference_10mw",
                            num_turbines=15)
    table = period_aep_table(_ws_series(2005, 2024), cfg, reference_periods(2005, 2024))
    assert len(table) >= 3
    assert all(r["net_aep_p50_gwh"] > 0 and 0 < r["capacity_factor"] < 1 for r in table)


def test_recommend_p50_by_classification():
    table = [
        {"key": "recent_5yr", "net_aep_p50_gwh": 396, "capacity_factor": 0.30, "role": "d"},
        {"key": "current_decade", "net_aep_p50_gwh": 402, "capacity_factor": 0.31, "role": "c"},
        {"key": "longterm_20yr", "net_aep_p50_gwh": 422, "capacity_factor": 0.32, "role": "l"},
    ]
    assert recommend_p50(_trend("decadal_regime_shift"), table)["central_basis"] == "current_decade"
    assert recommend_p50(_trend("secular_trend"), table)["central_basis"] == "recent_5yr"
    assert recommend_p50(_trend("decadal_variability"), table)["central_basis"] == "longterm_20yr"
    r = recommend_p50(_trend("decadal_regime_shift"), table)
    assert (r["p50_gwh"], r["downside_gwh"], r["upside_gwh"]) == (402, 396, 422)


def test_analyze_renders_markdown_and_dataframe():
    cfg = ERA5RequestConfig(project_name="T", latitude=8.27, longitude=79.75,
                            start_year=2005, end_year=2024,
                            hub_height_m=150.0, turbine_model="iea_reference_10mw",
                            num_turbines=15)
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
    trend_df = pd.DataFrame({"Metric": ["Classification"], "Value": ["decadal regime shift"]})
    out = build_executive_workbook(d, d, d, d, d, tmp_path / "wb.xlsx", resource_trend_df=trend_df)
    assert "ResourceTrend" in openpyxl.load_workbook(out).sheetnames
    # backward-compatible: omitting it creates no such sheet
    out2 = build_executive_workbook(d, d, d, d, d, tmp_path / "wb2.xlsx")
    assert "ResourceTrend" not in openpyxl.load_workbook(out2).sheetnames
