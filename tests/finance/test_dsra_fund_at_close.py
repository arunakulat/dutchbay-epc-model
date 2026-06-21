"""DSRA funded at financial close + a Sources-and-Uses statement — gap #6.

Previously dsra_months and financing_fees_usd were decorative config read by nobody, the
DSRA existed only as an operating-cash drag, and there was no sources-and-uses anywhere.
This adds an explicit S&U (always reported) and an opt-in Financing_Terms.dsra.fund_at_close
that funds the reserve up front with additional equity (seeded at t0 so the operating
top-up only rebuilds after a drawdown). Default-off preserves canonical economics exactly.
"""

from __future__ import annotations

import copy
import warnings
from pathlib import Path

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

warnings.filterwarnings("ignore")
REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _run(dsra=None, **fin_overrides):
    cfg = dict(load_scenario_config(LENDER))
    cfg["Financing_Terms"] = {**cfg["Financing_Terms"], **fin_overrides}
    if dsra is not None:
        cfg["Financing_Terms"]["dsra"] = dsra
    r = run_v14_pipeline(config=copy.deepcopy(cfg))
    return r["kpis"], (r.get("debt_result") or {}).get("funding") or {}


def test_default_off_preserves_canonical() -> None:
    kpis, f = _run()
    assert kpis["project_irr"] == pytest.approx(0.0543, abs=0.003)
    assert kpis["equity_irr"] == pytest.approx(0.0145, abs=0.001)
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
    assert f["fund_at_close"] is False
    assert f["initial_dsra_usd"] == 0.0
    # the S&U is always reported and always balances
    assert f["sources_and_uses"]["balanced"] is True


def test_fund_at_close_funds_dsra_and_modestly_lowers_eqirr() -> None:
    base_kpis, _ = _run()
    kpis, f = _run(dsra={"fund_at_close": True, "target_months": 6})
    assert f["fund_at_close"] is True
    assert f["initial_dsra_usd"] > 0.0  # ~6 months of yr-1 debt service
    assert f["sources_and_uses"]["balanced"] is True
    # the reserve is funded by additional equity at close -> eqIRR no higher than base
    assert kpis["equity_irr"] <= base_kpis["equity_irr"] + 1e-6
    # project-level economics are debt-structure independent
    assert kpis["project_irr"] == pytest.approx(base_kpis["project_irr"], abs=1e-4)


def test_sources_equal_uses() -> None:
    for dsra in (None, {"fund_at_close": True, "target_months": 9}):
        _, f = _run(dsra=dsra)
        su = f["sources_and_uses"]
        assert su["uses_total_usd"] == pytest.approx(su["sources_total_usd"], abs=1.0)
        # uses = capex + idc + dsra
        u = su["uses"]
        assert su["uses_total_usd"] == pytest.approx(
            u["capex_usd"] + u["idc_usd"] + u["initial_dsra_usd"], abs=1.0
        )


def test_legacy_dsra_months_key_is_wired() -> None:
    # the previously-decorative Financing_Terms.dsra_months now feeds target_months
    _, f = _run(dsra={"fund_at_close": True}, dsra_months=12)
    assert f["dsra_target_months"] == pytest.approx(12.0)
    _, f6 = _run(dsra={"fund_at_close": True}, dsra_months=6)
    # twice the months -> ~twice the reserve
    assert f["initial_dsra_usd"] == pytest.approx(2.0 * f6["initial_dsra_usd"], rel=0.01)


def test_api_surfaces_funding_block() -> None:
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert resp.funding.balanced is True
    assert resp.funding.fund_at_close is False
    assert resp.funding.capex_usd == pytest.approx(159_600_000, rel=1e-4)
    assert resp.funding.equity_usd is not None and resp.funding.equity_usd > 0
