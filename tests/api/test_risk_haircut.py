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
        "capacity_factor_pct": 40.0,  # percent, converted to 0.40
        "degradation_pct": 0.5,  # percent/year
        "grid_loss_pct": 2.0,  # percent
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
        "depreciation_years": 20,
        "holiday_years": 5,
        "holiday_start_year": 1,
        "enhanced_capital_allowance_pct": 100.0,
    },
    "risk": {
        "haircut_pct": 10.0,  # percent, becomes 0.10
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

    # Should validate cleanly
    assert validate_parameters(cfg) == []

    cfads = build_annual_cfads(cfg)
    rows = build_annual_rows(cfg)

    # Horizon consistency
    assert len(cfads) == cfg["project"]["project_life_years"]
    assert len(rows) == cfg["project"]["project_life_years"]

    # Row-wise consistency
    for i, row in enumerate(rows):
        assert cfads[i] == pytest.approx(row["cfads_final_lkr"])

        # Risk haircut relationship:
        # cfads_final = posttax_cfads * (1 - risk_haircut_pct)
        posttax = row["posttax_cfads_lkr"]  # ✅ FIXED: _lkr suffix
        haircut_pct = row["risk_haircut_pct"]
        haircut_amt = row["risk_haircut_amount_lkr"]  # ✅ FIXED: _lkr suffix

        assert haircut_pct >= 0.0
        assert haircut_amt == pytest.approx(posttax * haircut_pct)
        assert row["cfads_final_lkr"] == pytest.approx(posttax - haircut_amt)


def test_cashflow_zero_risk_haircut_means_posttax_equals_cfads() -> None:
    """With zero risk haircut, CFADS should equal post-tax CFADS."""
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["risk"]["haircut_pct"] = 0.0

    cfads = build_annual_cfads(cfg)
    rows = build_annual_rows(cfg)

    for i, row in enumerate(rows):
        assert row["risk_haircut_pct"] == pytest.approx(0.0)
        assert row["risk_haircut_amount_lkr"] == pytest.approx(
            0.0
        )  # ✅ FIXED: _lkr suffix
        assert row["cfads_final_lkr"] == pytest.approx(
            row["posttax_cfads_lkr"]
        )  # ✅ FIXED: _lkr suffix
        assert cfads[i] == pytest.approx(
            row["posttax_cfads_lkr"]
        )  # ✅ FIXED: _lkr suffix


def test_validate_parameters_fails_when_capacity_missing() -> None:
    """Validate that obvious missing required fields raise a clear error."""
    bad = copy.deepcopy(BASE_CONFIG)
    bad["project"].pop("capacity_mw", None)

    with pytest.raises(ValueError) as excinfo:
        validate_parameters(bad)

    msg = str(excinfo.value)
    assert "capacity_mw" in msg
    assert "invalid" in msg or "missing" in msg
