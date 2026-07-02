"""End-to-end FX-hedge behaviour pinned on the LIVE canonical lender case.

Rather than commit a ~700-line hedged clone of ``dutchbay_lendercase_2025Q4.yaml`` (a
duplication / stale-KPI footgun), this test loads the real committed lender case and
overlays ``fx.hedge_ratio`` / ``fx.spread_bps`` in-memory, so the hedged comparison always
tracks the live scenario. It guards two things:

1. BYTE-IDENTITY at hedge_ratio == 0: the committed lender KPIs are reproduced exactly, so
   the feature is inert until a scenario opts in.
2. DIRECTION: the sign of the hedged KPI move is asserted SELF-CONSISTENTLY against the
   forward-vs-spot relationship computed from the scenario's own rates — not a hardcoded
   "helps/hurts". For the canonical rates the CIP forward drift (r_lkr vs r_usd) is just
   below the spot ``annual_depr`` (because r_lkr was built as additive UIP = usd + drift),
   so the forward is less depreciated than spot and hedging RAISES project IRR / NPV.

Honest finding this guards (verified 2026-07-02): hedging the canonical lender case is
near-neutral / marginally positive, NOT the downside the original design note assumed
(which presumed r_usd ~ 6%). See finance/cashflow_v14_fx.py::_forward_curve.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14_fx import _cip_forward_rates

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# Committed lender-case pins (argv-correct, kpi_oracle).
BASE_PROJECT_IRR = 0.02683686114665262
BASE_EQUITY_IRR = -0.048585780806075674
BASE_MIN_DSCR = 1.2999999999999998
BASE_PROJECT_NPV = -65455817.14404039


@pytest.fixture(scope="module")
def base_cfg() -> Dict[str, Any]:
    return load_scenario_config(str(SCENARIO))


def _run(cfg: Dict[str, Any], hedge_ratio: float, spread_bps: float) -> Dict[str, Any]:
    c = copy.deepcopy(cfg)
    c.setdefault("fx", {})
    c["fx"]["hedge_ratio"] = hedge_ratio
    c["fx"]["spread_bps"] = spread_bps
    return run_v14_pipeline(config=c)["kpis"]


def test_forward_is_less_depreciated_than_spot(base_cfg: Dict[str, Any]) -> None:
    """Precondition for the direction assertions below (config-derived, not assumed)."""
    r_lkr, r_usd = _cip_forward_rates(base_cfg)
    forward_drift = (1.0 + r_lkr) / (1.0 + r_usd) - 1.0
    spot_drift = float(base_cfg["fx"]["annual_depr"])
    assert forward_drift < spot_drift


def test_hedge_ratio_zero_is_byte_identical(base_cfg: Dict[str, Any]) -> None:
    kpis = _run(base_cfg, 0.0, 0.0)
    assert kpis["project_irr"] == pytest.approx(BASE_PROJECT_IRR, rel=1e-12)
    assert kpis["equity_irr"] == pytest.approx(BASE_EQUITY_IRR, rel=1e-12)
    assert kpis["min_dscr"] == pytest.approx(BASE_MIN_DSCR, rel=1e-12)
    assert kpis["project_npv"] == pytest.approx(BASE_PROJECT_NPV, rel=1e-9)


def test_full_hedge_raises_project_irr(base_cfg: Dict[str, Any]) -> None:
    """Forward below spot -> more USD per LKR -> higher project IRR / NPV."""
    kpis = _run(base_cfg, 1.0, 0.0)
    assert kpis["project_irr"] > BASE_PROJECT_IRR
    assert kpis["project_npv"] > BASE_PROJECT_NPV


def test_partial_hedge_between_base_and_full(base_cfg: Dict[str, Any]) -> None:
    full = _run(base_cfg, 1.0, 0.0)["project_irr"]
    half = _run(base_cfg, 0.5, 25.0)["project_irr"]
    assert BASE_PROJECT_IRR < half < full


def test_min_dscr_invariant_under_hedge(base_cfg: Dict[str, Any]) -> None:
    """Debt auto-sizes to target DSCR, so the hedge surfaces in IRR/NPV, not min DSCR."""
    for h in (0.0, 0.5, 1.0):
        assert _run(base_cfg, h, 0.0)["min_dscr"] == pytest.approx(
            BASE_MIN_DSCR, rel=1e-9
        )
