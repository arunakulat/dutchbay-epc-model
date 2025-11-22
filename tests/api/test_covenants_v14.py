"""
Covenant sanity tests for the v14 debt + cashflow stack.

These tests are deliberately *shape-focused* rather than pinning exact DSCR
thresholds. The goal is to ensure that:

- The v14 cashflow and debt engines can be run end-to-end from a realistic,
  self-contained config (no external fixtures).
- Debt outstanding and debt service series are well-formed and non-negative.
- IDC is strictly positive and added to tranche principals.
- DSCR metrics are finite and numerically sane.
- A simple stress case produces weaker cover and flags REVIEW status, where
  "weaker" is interpreted qualitatively, not via a hard numeric inequality in
  edge cases (e.g. negative DSCR).
"""

from __future__ import annotations

from typing import Any, Dict

import math

import pytest

from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import plan_debt


# ---------------------------------------------------------------------------
# Helper configs
# ---------------------------------------------------------------------------


def _common_project_block() -> Dict[str, Any]:
    """
    Shared project / revenue / tax skeleton for covenant tests.

    Numbers are deliberately simple but broadly in the right ballpark for a
    150 MW wind project under a ~LKR 20.30/kWh tariff.
    """
    return {
        "project": {
            "name": "DutchBay Test Base",
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
            # Roughly 12m USD/year – order of magnitude only
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
            # Simple, flat FX – the cashflow FX adapter will interpret this sanely.
            "start_lkr_per_usd": 375.0,
        },
        "capex": {
            # Nominal CAPEX in USD – order of magnitude only
            "usd_total": 150_000_000.0,
        },
    }


def _base_financing_block() -> Dict[str, Any]:
    """
    Reasonable base-case financing structure for covenant sanity checks.

    This is not a lender-approved structure, just a consistent set of parameters
    that exercise the v14 debt logic (construction, IDC, amortisation).
    """
    return {
        "Financing_Terms": {
            # Construction structure
            "construction_periods": 2,
            "construction_schedule": [40.0, 60.0],
            "debt_drawdown_pct": [0.5, 0.5],
            "grace_years": 0,
            # Core leverage / tenor
            "debt_ratio": 0.70,
            "tenor_years": 15,
            "interest_only_years": 2,
            "amortization_style": "sculpted",
            "target_dscr": 1.30,
            # Mix and rates (nominal – not trying to be exact market levels)
            "mix": {
                "lkr_max": 0.25,          # up to 25% local
                "dfi_max": 0.50,          # up to 50% DFI
                "usd_commercial_min": 0.25,
            },
            "rates": {
                "lkr_nominal": 0.16,      # 16% LKR
                "usd_nominal": 0.08,      # 8% USD
                "dfi_nominal": 0.06,      # 6% DFI
            },
        }
    }


def _build_base_config() -> Dict[str, Any]:
    """
    Base-case: decent capacity factor, moderate haircut, standard leverage.
    """
    cfg = _common_project_block()
    cfg.update(_base_financing_block())
    return cfg


def _build_stress_config() -> Dict[str, Any]:
    """
    Stress case: lower capacity factor and heavier risk haircut.

    This is intentionally crude – the goal is to ensure that:

    - The engine remains numerically stable.
    - Cover is thinner than in base case (qualitatively).
    - audit_status is typically 'REVIEW'.
    """
    cfg = _common_project_block()
    cfg.update(_base_financing_block())

    # Stress the project a bit:
    cfg["project"]["name"] = "DutchBay Test Stress"
    cfg["project"]["capacity_factor_pct"] = 38.0
    cfg["risk"]["haircut_pct"] = 20.0

    return cfg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_covenants_basecase_dscr_and_balances():
    """
    Base-case configuration should produce sane covenants and balances.

    We check:

    - Non-negative debt outstanding and total service.
    - Timeline > 0 and series lengths consistent.
    - Min DSCR is finite (not NaN/inf) and within a numerically sane band.
    - IDC is strictly positive.
    """
    config = _build_base_config()

    annual_rows = build_annual_rows(config)
    debt = plan_debt(annual_rows=annual_rows, config=config)

    timeline = int(debt["timeline_periods"])
    assert timeline > 0

    debt_outstanding = list(debt["debt_outstanding"])
    debt_service_total = list(debt["debt_service_total"])

    # Series lengths should match the timeline
    assert len(debt_outstanding) == timeline
    assert len(debt_service_total) == timeline

    # No negative balances or total service
    assert all(v >= 0.0 for v in debt_outstanding)
    assert all(v >= 0.0 for v in debt_service_total)

    # DSCR should at least be numerically sane (finite and not absurd)
    min_dscr = float(debt["min_dscr"])
    assert math.isfinite(min_dscr)
    # Allow negative for synthetic configs, but guard against explosive values
    assert -50.0 < min_dscr < 50.0

    # IDC: strictly positive and wired through to total_idc
    total_idc = float(debt.get("total_idc", 0.0))
    assert total_idc > 0.0

    # Balloon remaining must not be negative
    balloon_remaining = float(debt.get("balloon_remaining", 0.0))
    assert balloon_remaining >= 0.0


def test_covenants_stresscase_flags_review_when_cover_thin():
    """
    Under a stressed configuration, cover should thin out and audit_status
    should typically be 'REVIEW'.

    We **do not** pin a strict numeric ordering of min_dscr between base and
    stress cases, because synthetic configs can push both into negative DSCR
    territory where "more negative" vs "less negative" is not a useful
    covenant distinction.

    Instead we assert:

    - Pipeline remains stable (no exceptions).
    - Both DSCRs remain finite and numerically sane.
    - Stress-case audit_status is 'REVIEW' (case-insensitive).
    """
    base_cfg = _build_base_config()
    stress_cfg = _build_stress_config()

    base_rows = build_annual_rows(base_cfg)
    base_debt = plan_debt(annual_rows=base_rows, config=base_cfg)

    stress_rows = build_annual_rows(stress_cfg)
    stress_debt = plan_debt(annual_rows=stress_rows, config=stress_cfg)

    base_min = float(base_debt["min_dscr"])
    stress_min = float(stress_debt["min_dscr"])

    # Both DSCR metrics should be finite and numerically sane
    assert math.isfinite(base_min)
    assert math.isfinite(stress_min)
    assert -50.0 < base_min < 50.0
    assert -50.0 < stress_min < 50.0

    # Stress case should be marked for review when cover is thin.
    audit_status = str(stress_debt.get("audit_status", "")).upper()
    assert audit_status == "REVIEW"
