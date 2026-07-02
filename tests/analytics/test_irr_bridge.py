"""Unit tests for the project→equity IRR bridge (#621).

The bridge is a disclosure-only reconciliation of the engine's published project IRR to its
published equity IRR. These tests pin the two load-bearing invariants — (1) legs + residual
reconcile EXACTLY to ``equity_irr − project_irr``, (2) the endpoints are the passed-in published
KPIs, never recomputed — plus the edge cases the acceptance criteria call out (undefined IRR,
zero debt, zero equity) and the ``from_run`` gating (additive / default-off).
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from analytics.contracts_v14 import IrrBridgeComponent, ProjectEquityIrrBridge
from analytics.irr_bridge import (
    LEG_COST_OF_DEBT,
    LEG_LEVERAGE,
    LEG_TAX_SHIELD,
    build_project_equity_irr_bridge,
    build_project_equity_irr_bridge_from_run,
)
from finance.irr import irr as _irr


def _levered_case() -> Dict[str, Any]:
    """A small but realistic levered case: capex 100, equity 30, 10 years of cash."""
    cfads = [18.0] * 10
    interest = [3.0, 2.7, 2.4, 2.1, 1.8, 1.5, 1.2, 0.9, 0.6, 0.3]
    tax = [0.3] * 10
    # Engine's authoritative equity vector: equity out at close, then cash net of debt service.
    debt_service = [i + 7.0 for i in interest]  # interest + principal (illustrative)
    equity_cf = [-30.0] + [c - d for c, d in zip(cfads, debt_service)]
    project_irr = _irr([-100.0] + cfads)
    equity_irr = _irr(equity_cf)
    return {
        "project_irr": project_irr,
        "equity_irr": equity_irr,
        "equity_investment_usd": 30.0,
        "capex_usd": 100.0,
        "cfads_usd": cfads,
        "interest_usd": interest,
        "effective_tax_rate": tax,
        "equity_cashflows_usd": equity_cf,
        "construction_years": 0,
    }


def test_bridge_reconciles_exactly() -> None:
    """sum(leg contributions) + residual == equity_irr − project_irr (to tolerance)."""
    bridge = build_project_equity_irr_bridge(**_levered_case())
    assert bridge.reconciled is True
    assert bridge.total_uplift is not None
    named = sum(c.contribution for c in bridge.components)
    assert named + bridge.residual == pytest.approx(bridge.total_uplift, abs=1e-9)
    # And the uplift is exactly the published gap, not a recomputed one.
    assert bridge.total_uplift == pytest.approx(
        bridge.equity_irr - bridge.project_irr, abs=0.0
    )


def test_endpoints_are_the_published_kpis_not_recomputed() -> None:
    """The bridge reports the passed-in IRRs verbatim; it never re-derives them."""
    case = _levered_case()
    # Feed deliberately "wrong" published endpoints; the bridge must echo them, not fix them.
    case["project_irr"] = 0.11111
    case["equity_irr"] = 0.22222
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.project_irr == 0.11111
    assert bridge.equity_irr == 0.22222
    assert bridge.total_uplift == pytest.approx(0.22222 - 0.11111, abs=1e-12)
    named = sum(c.contribution for c in bridge.components)
    assert named + bridge.residual == pytest.approx(bridge.total_uplift, abs=1e-9)


def test_named_legs_have_expected_signs() -> None:
    """Leverage lifts (>0), cost of debt drags (<0), tax shield restores (>0)."""
    bridge = build_project_equity_irr_bridge(**_levered_case())
    legs = {c.name: c.contribution for c in bridge.components}
    assert set(legs) == {LEG_LEVERAGE, LEG_COST_OF_DEBT, LEG_TAX_SHIELD}
    assert legs[LEG_LEVERAGE] > 0.0
    assert legs[LEG_COST_OF_DEBT] < 0.0
    assert legs[LEG_TAX_SHIELD] > 0.0


def test_leg_intermediate_irrs_walk_from_project_to_equity() -> None:
    """Each leg's ``irr_after`` is the cumulative-substitution IRR (the bridge's bars)."""
    bridge = build_project_equity_irr_bridge(**_levered_case())
    lev = next(c for c in bridge.components if c.name == LEG_LEVERAGE)
    cod = next(c for c in bridge.components if c.name == LEG_COST_OF_DEBT)
    ts = next(c for c in bridge.components if c.name == LEG_TAX_SHIELD)
    assert lev.irr_after is not None and cod.irr_after is not None
    assert ts.irr_after is not None
    # contribution == step delta of the cumulative IRR.
    assert lev.contribution == pytest.approx(
        lev.irr_after - bridge.project_irr, abs=1e-12
    )
    assert cod.contribution == pytest.approx(cod.irr_after - lev.irr_after, abs=1e-12)
    assert ts.contribution == pytest.approx(ts.irr_after - cod.irr_after, abs=1e-12)


def test_zero_debt_all_equity_is_reconciled() -> None:
    """An all-equity project (equity == capex, no interest): uplift ≈ 0, still reconciles."""
    cfads = [15.0] * 8
    case = {
        "project_irr": _irr([-100.0] + cfads),
        "equity_irr": _irr([-100.0] + cfads),
        "equity_investment_usd": 100.0,  # equity == capex → no leverage
        "capex_usd": 100.0,
        "cfads_usd": cfads,
        "interest_usd": [0.0] * 8,  # no debt → no interest
        "effective_tax_rate": [0.3] * 8,
        "equity_cashflows_usd": [-100.0] + cfads,
        "construction_years": 0,
    }
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.reconciled is True
    named = sum(c.contribution for c in bridge.components)
    assert named + bridge.residual == pytest.approx(bridge.total_uplift, abs=1e-9)
    # No leverage, no interest → the leverage and cost-of-debt legs are ~0.
    legs = {c.name: c.contribution for c in bridge.components}
    assert legs[LEG_LEVERAGE] == pytest.approx(0.0, abs=1e-9)
    assert legs[LEG_COST_OF_DEBT] == pytest.approx(0.0, abs=1e-9)


def test_zero_equity_investment_attributes_all_to_residual() -> None:
    """Degenerate zero equity: no leverage vector exists → whole uplift lands in the residual."""
    cfads = [15.0] * 8
    case = {
        "project_irr": _irr([-100.0] + cfads),
        "equity_irr": 0.25,  # published, whatever it is
        "equity_investment_usd": 0.0,  # cannot form a leverage vector
        "capex_usd": 100.0,
        "cfads_usd": cfads,
        "interest_usd": [2.0] * 8,
        "effective_tax_rate": [0.3] * 8,
        "equity_cashflows_usd": [0.0] + cfads,
        "construction_years": 0,
    }
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.reconciled is True
    assert all(c.contribution == 0.0 for c in bridge.components)
    assert bridge.residual == pytest.approx(bridge.total_uplift, abs=1e-12)


def test_undefined_equity_irr_reports_none_without_fabricating() -> None:
    """When equity_irr is None (undefined), uplift/residual are None/0 and it is unreconciled."""
    case = _levered_case()
    case["equity_irr"] = None
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.equity_irr is None
    assert bridge.total_uplift is None
    assert bridge.residual == 0.0
    assert bridge.reconciled is False


def test_undefined_project_irr_reports_none_without_fabricating() -> None:
    """When project_irr is None (undefined), uplift is None and the bridge is unreconciled."""
    case = _levered_case()
    case["project_irr"] = None
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.project_irr is None
    assert bridge.total_uplift is None
    assert bridge.reconciled is False


def test_short_interest_stream_does_not_truncate_operating_years() -> None:
    """A too-short interest/tax stream is zero-padded, not silently dropping later CFADS years."""
    cfads = [15.0] * 8
    case = {
        "project_irr": _irr([-100.0] + cfads),
        "equity_irr": 0.10,
        "equity_investment_usd": 30.0,
        "capex_usd": 100.0,
        "cfads_usd": cfads,
        "interest_usd": [3.0, 2.0],  # deliberately short (2 of 8)
        "effective_tax_rate": [0.3],  # deliberately short (1 of 8)
        "equity_cashflows_usd": [-30.0] + [10.0] * 8,
        "construction_years": 0,
    }
    bridge = build_project_equity_irr_bridge(**case)
    # Padding means the leverage leg still sees all 8 CFADS years (its IRR is defined & positive).
    lev = next(c for c in bridge.components if c.name == LEG_LEVERAGE)
    assert lev.irr_after is not None
    assert bridge.reconciled is True


def test_construction_lag_shared_by_both_bases() -> None:
    """The construction-year zeros are applied so both the project and levered bases share a lag."""
    cfads = [18.0] * 10
    case = {
        "project_irr": _irr([-100.0, 0.0, 0.0] + cfads),
        "equity_irr": 0.08,
        "equity_investment_usd": 30.0,
        "capex_usd": 100.0,
        "cfads_usd": cfads,
        "interest_usd": [2.0] * 10,
        "effective_tax_rate": [0.3] * 10,
        "equity_cashflows_usd": [-30.0, 0.0, 0.0] + [11.0] * 10,
        "construction_years": 2,
    }
    bridge = build_project_equity_irr_bridge(**case)
    assert bridge.metadata["construction_years"] == 2
    # The reproduced project IRR (with the same 2-year lag) matches the published one.
    assert bridge.metadata["reproduced_project_irr"] == pytest.approx(
        case["project_irr"], abs=1e-9
    )
    assert bridge.reconciled is True


# --------------------------------------------------------------------------------------------
# from_run gating (additive / default-off)
# --------------------------------------------------------------------------------------------


def _minimal_run_result() -> Dict[str, Any]:
    cfads = [18.0] * 10
    annual_rows: List[Dict[str, Any]] = [
        {"cfads_usd": 18.0, "interest_usd": 2.0, "effective_tax_rate": 0.3}
        for _ in range(10)
    ]
    return {
        "kpis": {"project_irr": _irr([-100.0] + cfads), "equity_irr": 0.05},
        "annual_rows": annual_rows,
        "debt_result": {"construction_years": 0},
        "equity_distribution": {
            "status": "computed",
            "equity_summary": {"equity_investment_usd": 30.0},
            "equity_cashflows_usd": [-30.0] + [11.0] * 10,
        },
        "scenario_result": {"config": {"finance": {"capex_usd": 100.0}}},
    }


def test_from_run_builds_when_equity_distribution_present() -> None:
    run = _minimal_run_result()
    bridge = build_project_equity_irr_bridge_from_run(run)
    assert isinstance(bridge, ProjectEquityIrrBridge)
    assert bridge.reconciled is True
    assert bridge.metadata["capex_usd"] == pytest.approx(100.0)


def test_from_run_returns_none_without_equity_distribution() -> None:
    run = _minimal_run_result()
    run.pop("equity_distribution")
    assert build_project_equity_irr_bridge_from_run(run) is None


def test_from_run_returns_none_when_equity_distribution_failed() -> None:
    run = _minimal_run_result()
    run["equity_distribution"]["status"] = "failed"
    assert build_project_equity_irr_bridge_from_run(run) is None


def test_from_run_returns_none_when_capex_unresolvable() -> None:
    run = _minimal_run_result()
    run["scenario_result"] = {"config": {}}  # no capex → cannot form the project base
    assert build_project_equity_irr_bridge_from_run(run) is None


def test_from_run_returns_none_without_annual_rows() -> None:
    run = _minimal_run_result()
    run["annual_rows"] = []
    assert build_project_equity_irr_bridge_from_run(run) is None


def test_component_and_bridge_are_frozen_contracts() -> None:
    """The result types are frozen dataclasses (CCCDIR immutability)."""
    comp = IrrBridgeComponent(name="x", contribution=0.1)
    with pytest.raises(Exception):
        comp.contribution = 0.2  # type: ignore[misc]
    bridge = build_project_equity_irr_bridge(**_levered_case())
    with pytest.raises(Exception):
        bridge.residual = 0.0  # type: ignore[misc]
