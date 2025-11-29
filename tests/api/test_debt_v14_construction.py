"""
Debt v14 construction tests - refactored for v14 tranche-based API.

Purpose: Validate that plan_debt() produces well-formed output with correct
construction timeline and tranche structure.

v14 API now returns aggregates by tranche instead of flat time-series.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

# ============================================================================
# Test helpers
# ============================================================================


def _make_simple_financing_config() -> Dict[str, Any]:
    """Minimal financing config for construction debt testing."""
    return {
        "Financing_Terms": {
            "construction_periods": 2,
            "construction_schedule": [50.0, 50.0],
            "debt_drawdown_pct": [0.5, 0.5],
            "grace_years": 0,
            "debt_ratio": 0.70,
            "tenor_years": 15,
            "interest_only_years": 2,
            "amortization_style": "sculpted",
            "target_dscr": 1.30,
            "mix": {
                "lkr_max": 0.25,
                "dfi_max": 0.50,
                "usd_commercial_min": 0.25,
            },
            "rates": {
                "lkr_nominal": 0.16,
                "usd_nominal": 0.08,
                "dfi_nominal": 0.06,
            },
        },
        "project": {
            "name": "Test Project",
            "capacity_mw": 150.0,
            "capacity_factor_pct": 45.0,
            "degradation_pct": 0.5,
            "grid_loss_pct": 2.0,
            "life_years": 20,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 12_000_000.0,
        },
        "statutory": {
            "success_fee_pct": 2.0,
            "env_surcharge_pct": 0.25,
            "social_levy_pct": 0.25,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
            "depreciation_years": 20,
            "tax_holiday_years": 10,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 150.0,
        },
        "risk": {
            "haircut_pct": 10.0,
        },
        "fx": {
            "start_lkr_per_usd": 375.0,
        },
        "capex": {
            "usd_total": 150_000_000.0,
        },
    }


def _make_simple_annual_rows() -> list:
    """Create synthetic annual CFADS rows for testing."""
    cfg = _make_simple_financing_config()
    return build_annual_rows(cfg)


# ============================================================================
# Tests
# ============================================================================


def test_plan_debt_construction_timeline_and_idc():
    """
    v14 API: Verify plan_debt returns correct construction timeline and aggregates.

    The v14 API returns aggregated tranche data instead of flat time-series.
    We verify the timeline shape and that tranche aggregates are internally
    consistent.
    """
    cfg = _make_simple_financing_config()
    annual_rows = _make_simple_annual_rows()

    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # High-level timeline shape
    assert result["construction_years"] == 2
    assert result["timeline_periods"] == 23
    assert result["tenor_years"] == 15

    # v14 plan_debt no longer exposes a flat `debt_outstanding` series.
    # Instead we expose per-tranche aggregates plus a total IDC.
    # Verify that tranche aggregates are internally consistent with total_idc.
    principal_by = result["principal_by_tranche"]
    idc_by = result["idc_by_tranche"]

    # Three tranches and non-empty books
    assert set(principal_by.keys()) == {"lkr", "usd", "dfi"}
    assert all(v > 0.0 for v in principal_by.values()), "All tranches should be drawn"

    # total_idc must reconcile with the tranche IDC breakdown
    assert result["total_idc"] == pytest.approx(sum(idc_by.values()))


def test_plan_debt_dscr_and_audit_status():
    """
    v14 API: Verify min_dscr and audit_status are present and numerically sane.
    """
    cfg = _make_simple_financing_config()
    annual_rows = _make_simple_annual_rows()

    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # Min DSCR must be finite (not NaN/inf)
    import math

    min_dscr = float(result["min_dscr"])
    assert math.isfinite(min_dscr), "min_dscr must be finite"

    # Sanity band: allow negative for synthetic cases, but guard against explosions
    assert -50.0 < min_dscr < 50.0, f"min_dscr out of sensible range: {min_dscr}"

    # audit_status should be PASS or REVIEW
    audit_status = str(result.get("audit_status", "")).upper()
    assert audit_status in (
        "PASS",
        "REVIEW",
    ), f"Unexpected audit_status: {audit_status}"

    # If min_dscr >= 1.30, should be PASS
    if min_dscr >= 1.30:
        assert audit_status == "PASS", "min_dscr >= 1.30 should be PASS"
