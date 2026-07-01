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

        # Risk haircut relationship (audit D6, #572): the haircut removes
        # ``h * |posttax|`` of cash and always moves CFADS adversely, so the
        # amount is sign-independent (this config is loss-making, posttax < 0).
        posttax = row["posttax_cfads_lkr"]
        haircut_pct = row["risk_haircut_pct"]
        haircut_amt = row["risk_haircut_amount_lkr"]

        assert haircut_pct >= 0.0
        assert haircut_amt == pytest.approx(abs(posttax) * haircut_pct)
        assert row["cfads_final_lkr"] == pytest.approx(posttax - haircut_amt)
        # The haircut never softens a loss: |final| >= |posttax| when posttax < 0.
        if posttax < 0:
            assert abs(row["cfads_final_lkr"]) >= abs(posttax) - 1e-6


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


def test_risk_haircut_is_conservative_on_losses() -> None:
    """The haircut must WORSEN CFADS regardless of sign (audit D6, #572).

    The old ``cfads * (1 - h)`` form softened a loss (``-1000 -> -900``), inverting
    the conservatism. The fix worsens a loss (``-1000 -> -1100``) while staying
    byte-identical for non-negative CFADS.
    """
    from finance.cashflow_v14_production import _apply_risk_haircut

    # Non-negative CFADS: unchanged reduction toward zero (byte-identical).
    assert _apply_risk_haircut(1000.0, 0.10) == pytest.approx(900.0)
    assert _apply_risk_haircut(0.0, 0.10) == pytest.approx(0.0)

    # Loss year: the haircut deepens the loss instead of softening it.
    assert _apply_risk_haircut(-1000.0, 0.10) == pytest.approx(-1100.0)

    # Property: a risk haircut never improves CFADS in any direction.
    for cfads in (-5000.0, -1.0, 0.0, 1.0, 5000.0):
        out = _apply_risk_haircut(cfads, 0.15)
        assert out <= cfads + 1e-9  # never larger than the un-haircut value
        assert abs(out) >= abs(cfads) - 1e-9 if cfads < 0 else abs(out) <= abs(cfads)


def test_validate_parameters_fails_when_capacity_missing() -> None:
    """Validate that obvious missing required fields raise a clear error."""
    bad = copy.deepcopy(BASE_CONFIG)
    bad["project"].pop("capacity_mw", None)

    with pytest.raises(ValueError) as excinfo:
        validate_parameters(bad)

    msg = str(excinfo.value)
    assert "capacity_mw" in msg
    assert "invalid" in msg or "missing" in msg
