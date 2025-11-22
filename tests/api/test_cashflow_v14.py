"""
Regression tests for the v14 cashflow engine.

Focus:
- Basic shape of build_annual_rows on a self-contained config.
- Project life extraction, including the heuristic path.
- FX curve behaviour when using the mapping-style configuration.
"""

from dutchbay_v14chat.finance.cashflow import (
    build_annual_rows,
    _extract_project_life_years,
    _fx_curve,
)


def _make_basic_v14_cashflow_config():
    """
    Minimal but realistic v14-style cashflow configuration.

    Uses:
    - project.life_years as the explicit project life
    - FX mapping with start + annual_depr_pct
    - Standard BOI tax settings with a holiday and enhanced allowance
    """
    return {
        "project": {
            "capacity_mw": 150.0,
            "capacity_factor_pct": 40.0,
            "degradation_pct": 0.5,
            "grid_loss_pct": 2.0,
            "life_years": 20,
        },
        "tariff": {
            "lkr_per_kwh": 50.0,
        },
        "opex": {
            "usd_per_year": 10_000_000.0,
        },
        "statutory": {
            "success_fee_pct": 2.0,
            "env_surcharge_pct": 0.25,
            "social_levy_pct": 0.25,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
            "depreciation_years": 20,
            "tax_holiday_years": 5,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 150.0,
        },
        "risk": {
            "haircut_pct": 5.0,
        },
        "fx": {
            "start_lkr_per_usd": 375.0,
            "annual_depr_pct": 3.0,
        },
        "capex": {
            "usd_total": 150_000_000.0,
        },
    }


def test_build_annual_rows_v14_basic_shape():
    cfg = _make_basic_v14_cashflow_config()
    rows = build_annual_rows(cfg)

    life = cfg["project"]["life_years"]
    assert len(rows) == life

    first = rows[0]

    # Core CFADS fields should be present and non-negative
    assert "cfads_final_lkr" in first
    assert "cfads_usd" in first
    assert first["cfads_final_lkr"] >= 0.0
    assert first["cfads_usd"] >= 0.0

    # FX / revenue sanity checks
    assert first["fx_rate"] > 0.0
    assert first["revenue_lkr"] > 0.0
    assert first["gross_kwh"] > 0.0
    assert first["net_kwh"] > 0.0


def test_extract_project_life_years_heuristic_path():
    """
    Exercise the heuristic project life extraction where no explicit
    project.life_years / parameters.project_life_years fields exist.
    """
    cfg = {
        "meta": {
            "life_horizon_years": 25,
        }
    }
    life = _extract_project_life_years(cfg)
    assert life == 25


def test_fx_curve_mapping_form_increases_over_time():
    """
    The mapping-style FX configuration with start_lkr_per_usd + annual_depr_pct
    should produce a curve of the requested length with monotonic growth
    when the depreciation rate is positive.
    """
    cfg = {
        "fx": {
            "start_lkr_per_usd": 300.0,
            "annual_depr_pct": 3.0,
        }
    }
    curve = _fx_curve(cfg, 5)

    assert len(curve) == 5
    assert curve[0] == 300.0
    # simple monotonic check: last > first when depreciation is positive
    assert curve[-1] > curve[0]
