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
    # Canonical after PR B (group-C #3): LKR debt rate -> UIP-implied 13.39%. projIRR ~2.68%
    # is unchanged (debt-structure independent), minDSCR 1.30. The costlier LKR tranche takes
    # equity IRR to ~-4.86% at the flat-LKR tariff.
    assert kpis["project_irr"] == pytest.approx(0.02684, abs=0.003)
    assert kpis["equity_irr"] == pytest.approx(-0.048586, abs=0.001)
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
    assert f["fund_at_close"] is False
    assert f["initial_dsra_usd"] == 0.0
    # the S&U is always reported and always balances
    assert f["sources_and_uses"]["balanced"] is True


def test_fund_at_close_funds_dsra_and_is_roughly_eqirr_neutral() -> None:
    base_kpis, _ = _run()
    kpis, f = _run(dsra={"fund_at_close": True, "target_months": 6})
    assert f["fund_at_close"] is True
    assert f["initial_dsra_usd"] > 0.0  # ~6 months of yr-1 debt service
    assert f["sources_and_uses"]["balanced"] is True
    # The DSRA is now RECOVERED by the sponsor at maturity (Wave-1 equity-waterfall fix), so
    # pre-funding it from equity at close is roughly timing-neutral versus diverting early
    # operating cash to build it — the two eqIRRs differ only marginally (here fund_at_close
    # is a few bps higher because early operating cash is no longer diverted into the reserve).
    assert kpis["equity_irr"] == pytest.approx(base_kpis["equity_irr"], abs=0.002)
    # project-level economics are debt-structure independent
    assert kpis["project_irr"] == pytest.approx(base_kpis["project_irr"], abs=1e-4)


def test_dsra_sized_off_operating_year_1_not_the_bridge_period() -> None:
    """Round-2 audit: the fund-at-close DSRA must be sized off OPERATING YEAR 1's debt
    service, not the synthetic half-year "bridge" lead-in period.

    `debt_service_total` is on the debt timeline built by `_build_cfads_timeline`: when a
    bridge period is present it sits at index `construction_periods` and operating year 1 is
    at `construction_periods + 1`. `_build_funding` used to index `construction_periods`
    directly, grabbing the bridge -- only a half-year of interest when
    `interest_only_years < 2` -- and under-reserving the DSRA (~50% low at io=0). The
    canonical lender case uses `interest_only_years: 2` (bridge == op-year-1, which masks
    the bug), so this test forces io=0 to make the two periods differ.
    """
    cfg = dict(load_scenario_config(LENDER))
    cfg["Financing_Terms"] = {
        **cfg["Financing_Terms"],
        "interest_only_years": 0,
        "dsra": {"fund_at_close": True, "target_months": 6},
    }
    r = run_v14_pipeline(config=copy.deepcopy(cfg))
    debt = r["debt_result"] or {}
    funding = debt.get("funding") or {}
    ds = debt["debt_service_total"]
    period_map = debt["annual_row_debt_period_map"]
    op_year1_period = int(period_map[0]["debt_period"])
    bridge_period = op_year1_period - 1  # the synthetic half-year lead-in

    # Precondition: at io=0 the bridge really is materially smaller than operating year 1,
    # so the fix is genuinely exercised (guards against the test silently passing on io=2).
    assert ds[op_year1_period] > 1.4 * ds[bridge_period]

    # The DSRA is sized off operating year 1's debt service ...
    assert funding["initial_dsra_usd"] == pytest.approx(
        (6.0 / 12.0) * ds[op_year1_period], rel=1e-6
    )
    # ... and is materially larger than the old, bridge-based reserve would have been.
    buggy_bridge_dsra = (6.0 / 12.0) * ds[bridge_period]
    assert funding["initial_dsra_usd"] > 1.4 * buggy_bridge_dsra


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
    assert f["initial_dsra_usd"] == pytest.approx(
        2.0 * f6["initial_dsra_usd"], rel=0.01
    )


def test_reserves_nested_dsra_months_is_wired() -> None:
    # Audit #95: the canonical nesting Financing_Terms.reserves.dsra_months must drive DSRA
    # sizing. The prior resolver only read dsra.target_months / top-level dsra_months, so a
    # reserves-nested value was silently ignored and matched the 6.0 default only by
    # coincidence. (Canonical sets reserves.dsra_months: 6, so default-off is unchanged.)
    _, f12 = _run(dsra={"fund_at_close": True}, reserves={"dsra_months": 12})
    assert f12["dsra_target_months"] == pytest.approx(12.0)
    _, f6 = _run(dsra={"fund_at_close": True}, reserves={"dsra_months": 6})
    assert f12["initial_dsra_usd"] == pytest.approx(
        2.0 * f6["initial_dsra_usd"], rel=0.02
    )
    # An explicit dsra.target_months still takes precedence over the reserves nesting.
    _, f_override = _run(
        dsra={"fund_at_close": True, "target_months": 6}, reserves={"dsra_months": 12}
    )
    assert f_override["dsra_target_months"] == pytest.approx(6.0)


def test_api_surfaces_funding_block() -> None:
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert resp.funding.balanced is True
    assert resp.funding.fund_at_close is False
    assert resp.funding.capex_usd == pytest.approx(159_600_000, rel=1e-4)
    assert resp.funding.equity_usd is not None and resp.funding.equity_usd > 0
