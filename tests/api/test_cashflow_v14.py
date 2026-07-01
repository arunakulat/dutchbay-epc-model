import copy

import pytest

from finance.cashflow_v14 import (
    build_annual_cfads,
    build_annual_rows,
    validate_parameters,
)

# Minimal but realistic v14-style config for DutchBay
BASE_CONFIG: dict = {
    "project": {
        "project_life_years": 5,
        "capacity_mw": 150.0,
        "capacity_factor_pct": 40.0,
        "degradation_pct": 0.5,
        "grid_loss_pct": 2.0,
        "corporate_tax_rate_pct": 24.0,
    },
    "tariff": {
        "lkr_per_kwh": 20.30,
    },
    "opex": {
        "usd_per_year": 4_000_000.0,
    },
    "statutory": {
        "success_fee_pct": 1.0,
        "env_surcharge_pct": 0.25,
        "social_levy_pct": 0.25,
    },
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_start_year": 1,
        "depreciation_years": 20,
        "enhanced_allowance_applies": False,
        "enhanced_capital_allowance_multiple": 1.0,  # multiplier (100%), not percent
        "loss_carryforward_years": 25,
        "tax_holiday_start_year": 1,
        "tax_holiday_years": 0,
        "wht_on_interest_to_nonresidents": 0.0,
        "wht_on_interest_enabled": False,
        "wht_gross_up": False,
    },
    "risk": {
        "haircut_pct": 10.0,
    },
    "fx": {
        "start_lkr_per_usd": 375.0,
        "annual_depr_pct": 3.0,
    },
    "capex": {
        "usd_total": 120_000_000.0,
    },
}


def test_cashflow_basic_consistency() -> None:
    """CFADS list and annual rows should be aligned and self-consistent."""
    cfg = copy.deepcopy(BASE_CONFIG)

    assert validate_parameters(cfg) == []

    cfads = build_annual_cfads(cfg)
    rows = build_annual_rows(cfg)

    assert len(cfads) == cfg["project"]["project_life_years"]
    assert len(rows) == cfg["project"]["project_life_years"]

    for i, row in enumerate(rows):
        assert cfads[i] == pytest.approx(row["cfads_final_lkr"])

        posttax = row["posttax_cfads_lkr"]
        haircut_pct = row["risk_haircut_pct"]
        haircut_amt = row["risk_haircut_amount_lkr"]

        assert haircut_pct >= 0.0
        # Audit D6 (#572): haircut removes h * |posttax| and always worsens CFADS,
        # so the amount is sign-independent (this config is loss-making).
        assert haircut_amt == pytest.approx(abs(posttax) * haircut_pct)
        assert row["cfads_final_lkr"] == pytest.approx(posttax - haircut_amt)


def test_cashflow_zero_risk_haircut_means_posttax_equals_cfads() -> None:
    """With zero risk haircut, CFADS should equal post-tax CFADS."""
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["risk"]["haircut_pct"] = 0.0

    cfads = build_annual_cfads(cfg)
    rows = build_annual_rows(cfg)

    for i, row in enumerate(rows):
        assert row["risk_haircut_pct"] == pytest.approx(0.0)
        assert row["risk_haircut_amount_lkr"] == pytest.approx(0.0)
        assert row["cfads_final_lkr"] == pytest.approx(row["posttax_cfads_lkr"])
        assert cfads[i] == pytest.approx(row["posttax_cfads_lkr"])


def test_validate_parameters_fails_when_capacity_missing() -> None:
    """Validate that obvious missing required fields raise a clear error."""
    bad = copy.deepcopy(BASE_CONFIG)
    bad["project"].pop("capacity_mw", None)

    with pytest.raises(ValueError) as excinfo:
        validate_parameters(bad)

    msg = str(excinfo.value)
    assert "capacity_mw" in msg
    assert "invalid" in msg or "missing" in msg
