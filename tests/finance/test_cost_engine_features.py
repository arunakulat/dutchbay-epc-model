"""Unit tests for the granular-cost engine features.

1. capex.derive_from_breakdown -> CAPEX is the SUM of capex.breakdown line items
   (bottom-up, single source of truth), cross-asserted against usd_total.
2. opex.escalation_pct -> OPEX inflates in USD year-on-year, on top of the FX curve.

Both are opt-in and default-off, so existing scenarios are unchanged.
"""

from __future__ import annotations

import pytest

from finance.cashflow_v14_params import _build_cashflow_params
from finance.debt_v14 import _extract_capex_usd


# --- CAPEX: derive-from-breakdown ------------------------------------------------

def test_capex_derives_from_breakdown_sum() -> None:
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "usd_total": 207_500_000,
            "breakdown": {
                "wtg_supply_usd": 143_200_000,
                "balance_of_plant_usd": 33_200_000,
                "grid_connection_usd": 16_600_000,
                "development_owners_usd": 7_300_000,
                "financing_fees_usd": 4_100_000,
                "contingency_usd": 3_100_000,
            },
        }
    }
    assert _extract_capex_usd(cfg) == pytest.approx(207_500_000, rel=1e-9)


def test_capex_breakdown_total_mismatch_raises() -> None:
    """A >0.5% gap between the breakdown sum and the stated usd_total is rejected."""
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "usd_total": 159_600_000,  # stale; breakdown sums to 207.5M
            "breakdown": {"a_usd": 200_000_000, "b_usd": 7_500_000},
        }
    }
    with pytest.raises(ValueError, match="mismatch"):
        _extract_capex_usd(cfg)


def test_capex_flag_off_uses_flat_total() -> None:
    """Without the flag, the flat usd_total is used (breakdown ignored) — backward-compat."""
    cfg = {
        "capex": {
            "usd_total": 159_600_000,
            "breakdown": {"a_usd": 140_000_000, "b_usd": 10_000_000},  # sums to 150M, ignored
        }
    }
    assert _extract_capex_usd(cfg) == pytest.approx(159_600_000, rel=1e-9)


# --- OPEX: escalation ------------------------------------------------------------

def _params(raw: dict):
    return _build_cashflow_params(raw)


def test_opex_escalation_pct_resolves_to_decimal() -> None:
    p = _params(
        {
            "project": {
                "capacity_mw": 100,
                "capacity_factor": 0.35,
                "construction_years": 2,
                "operating_years": 20,
            },
            "tariff": {"lkr_per_kwh": 20.0},
            "opex": {"usd_per_year": 3_000_000, "escalation_pct": 2.5},
        }
    )
    assert p.opex_escalation_pct == pytest.approx(0.025, abs=1e-9)


def test_opex_escalation_defaults_to_zero() -> None:
    p = _params(
        {
            "project": {
                "capacity_mw": 100,
                "capacity_factor": 0.35,
                "construction_years": 2,
                "operating_years": 20,
            },
            "tariff": {"lkr_per_kwh": 20.0},
            "opex": {"usd_per_year": 3_000_000},
        }
    )
    assert p.opex_escalation_pct == 0.0
