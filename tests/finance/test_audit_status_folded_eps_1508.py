"""Regression tests for folded DSCR audit_status and _DSCR_LOCKUP_EPS (#1508)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer, plan_debt

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _synth_config() -> Dict[str, Any]:
    return {
        "capex": {"usd_total": 10_000_000.0},
        "Financing_Terms": {
            "construction_periods": 2,
            "construction_schedule": [40.0, 60.0],
            "debt_drawdown_pct": [0.5, 0.5],
            "debt_ratio": 0.50,
            "tenor_years": 5,
            "amortization_style": "sculpted",
            "target_dscr": 1.30,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
        },
    }


def test_audit_status_tolerates_sub_ulp_sculpt_noise_via_lockup_eps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sub-ULP sculpt float noise around 1.30 should PASS rather than REVIEW (#1508)."""
    import finance.debt.layer as layer

    cfg = _synth_config()
    rows = [{"year": y, "cfads_usd": 2_000_000.0} for y in range(1, 6)]

    # Direct sub-ULP boundary check using _sculpted_schedule returning 1.30 - 5e-10
    def _mock_sculpt(
        tranches: Any, amort_years: int, cfads_slice: Any, target_dscr: float, **kw: Any
    ):
        del amort_years, kw
        # Period 0 is bridge (0 service so fold does not distort); periods 1..N are op rows.
        out = {k: [(0.0, 0.0, 0.0) for _ in cfads_slice] for k in tranches}
        out["USD"] = [
            (
                (0.0, 0.0, 0.0)
                if idx == 0
                else (0.0, cf / (target_dscr - 5e-10), cf / (target_dscr - 5e-10))
            )
            for idx, cf in enumerate(cfads_slice)
        ]
        return out

    monkeypatch.setattr(layer, "_sculpted_schedule", _mock_sculpt)
    cfg["Financing_Terms"]["construction_periods"] = 0
    cfg["Financing_Terms"]["construction_schedule"] = []
    cfg["Financing_Terms"]["debt_drawdown_pct"] = []
    core = apply_debt_layer(cfg, annual_rows=rows)
    assert min(v for v in core["dscr_by_year"].values() if v is not None) < 1.30
    assert core["audit_status"] == "PASS"

    # True breach outside _DSCR_LOCKUP_EPS (1.30 - 1e-6) must return REVIEW.
    def _mock_breach(
        tranches: Any, amort_years: int, cfads_slice: Any, target_dscr: float, **kw: Any
    ):
        del amort_years, kw
        out = {k: [(0.0, 0.0, 0.0) for _ in cfads_slice] for k in tranches}
        out["USD"] = [
            (
                (0.0, 0.0, 0.0)
                if idx == 0
                else (0.0, cf / (target_dscr - 1e-6), cf / (target_dscr - 1e-6))
            )
            for idx, cf in enumerate(cfads_slice)
        ]
        return out

    monkeypatch.setattr(layer, "_sculpted_schedule", _mock_breach)
    breach_core = apply_debt_layer(cfg, annual_rows=rows)
    assert breach_core["audit_status"] == "REVIEW"


def test_audit_status_reflects_folded_year1_shortfall_on_lender_case() -> None:
    """When bridge folding pulls year 1 below target, audit_status must report REVIEW (#1508)."""
    cfg = load_scenario_config(str(_LENDER_CFG))
    rows = build_annual_rows(cfg)
    res = plan_debt(annual_rows=rows, config=cfg)
    if float(res["min_dscr"]) < 1.30 - 1e-9:
        assert res["audit_status"] == "REVIEW"


def test_apply_debt_layer_uses_bridge_folded_year1_and_lockup_eps() -> None:
    """Synthetic bridge-fold check + direct sub-ULP check on apply_debt_layer (#1508)."""
    cfg = _synth_config()
    # Year 1 CFADS barely covers 1.30x period service; half-year bridge leads in with
    # service folded into operating year 1, driving folded year-1 DSCR well below 1.30
    # while unfolded period DSCR stays pinned at 1.30.
    rows = [{"year": y, "cfads_usd": 2_000_000.0} for y in range(1, 6)]
    core = apply_debt_layer(cfg, annual_rows=rows)
    year1_folded = float(core["dscr_by_year"][1])
    if year1_folded < 1.30 - 1e-9:
        assert core["audit_status"] == "REVIEW"
    else:
        pytest.fail("Expected bridge fold to reduce year-1 DSCR below target")
