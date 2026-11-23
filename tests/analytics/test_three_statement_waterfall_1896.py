"""Regression tests for three-statement <-> equity waterfall tie-out (#1896, #924 study O-1).

Verifies across every runnable committed scenario that statement distributions, DSRA reserve
balances/movements, lock-up/retention cash, and closing cash equal the equity waterfall
period by period — including Year 1 DSRA funding, covenant lock-ups, sponsor cures, and
refinance / cash-sweep years — with non-negative closing cash and explicit negative controls.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.three_statement import (
    ThreeStatementResult,
    build_three_statement_from_run,
    verify_three_statement_waterfall_tieout,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"

# Intentionally incomplete / negative-fixture YAMLs under scenarios/ that fail schema
# validation by design. Any other top-level scenario YAML must run and reconcile.
_NON_RUNNABLE_SCENARIOS = frozenset(
    {
        "bad_missing_tax.yaml",
        "contracts_edgecase_base_v14.yaml",
        "dscr_sensitivity_example.yaml",
        "dutchbay_mc_enhanced_2025Q4.yaml",
        "dutchbay_sprint17_enhanced.yaml",
        "example_fx_structured_blocks.yaml",
        "kolonnawa_epc_100mw.yaml",
        "sensitivity_parameters_examples.yaml",
    }
)


def _runnable_scenarios() -> List[Path]:
    paths = [
        p
        for p in sorted(SCENARIOS_DIR.glob("*.yaml"))
        if p.name not in _NON_RUNNABLE_SCENARIOS
    ]
    assert len(paths) >= 32, f"Expected >= 32 runnable scenarios, found {len(paths)}"
    return paths


@pytest.mark.parametrize(
    "scenario_path",
    _runnable_scenarios(),
    ids=lambda p: p.stem,
)
def test_all_runnable_committed_scenarios_reconcile_to_equity_waterfall(
    scenario_path: Path,
) -> None:
    """Every runnable scenario ties distributions, DSRA reserves, and cash to the waterfall."""
    result = run_v14_pipeline(config=str(scenario_path), validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ed = result["equity_distribution"]
    assert ed["status"] in ("computed", "defaulted")

    ts_full = build_three_statement_from_run(result, cfg)
    ts_report_path = build_three_statement_from_run(
        {"annual_rows": result["annual_rows"], "debt_result": result["debt_result"]},
        cfg,
    )
    assert ts_full is not None and ts_report_path is not None
    assert ts_full == ts_report_path

    funding = (result["debt_result"] or {}).get("funding") or {}
    opening_cash = (
        float(funding.get("initial_dsra_usd") or 0.0)
        if bool(funding.get("fund_at_close"))
        else 0.0
    )
    verify_three_statement_waterfall_tieout(ts_full, ed, opening_cash=opening_cash)

    assert ts_full.tie_outs is not None
    assert ts_full.tie_outs.all_pass
    assert ts_full.tie_outs.waterfall_reconciles
    assert ts_full.tie_outs.balance_sheet_balances
    assert ts_full.tie_outs.debt_retires_to_residual
    assert ts_full.tie_outs.cashflow_reconciles
    assert ts_full.tie_outs.retained_earnings_rolls
    assert all(cf.closing_cash >= -1e-6 for cf in ts_full.cash_flow)


def test_lendercase_year1_dsra_and_refinance_lockup_cash_nonnegative() -> None:
    """Lender case funds DSRA in year 1 (0 distribution) and holds lockup cash for refi."""
    path = SCENARIOS_DIR / "dutchbay_lendercase_2025Q4.yaml"
    result = run_v14_pipeline(config=str(path), validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ts = build_three_statement_from_run(result, cfg)
    assert ts is not None
    verify_three_statement_waterfall_tieout(ts, result["equity_distribution"])

    # Year 1 builds DSRA rather than over-distributing free cash.
    yr1 = ts.cash_flow[0]
    assert -yr1.distributions == pytest.approx(0.0, abs=1e-6)
    assert yr1.reserve_balance > 4_000_000.0
    assert yr1.reserve_movement == pytest.approx(yr1.reserve_balance, abs=1e-6)
    assert yr1.closing_cash == pytest.approx(yr1.reserve_balance, abs=1e-6)

    # Refinance years (years 15-17) draw down DSRA + trapped cash with non-negative cash.
    for idx in (14, 15, 16):
        cf = ts.cash_flow[idx]
        assert cf.closing_cash >= -1e-6
        assert cf.locked_cash_balance > 0.0
    # Year 18 cures and releases trapped lockup cash.
    assert ts.cash_flow[17].locked_cash_balance == pytest.approx(0.0, abs=1e-6)
    assert -ts.cash_flow[17].distributions > 2_000_000.0


def test_basecase_lockup_traps_and_pays_sweep_nonnegative() -> None:
    """Base case traps lockup cash in years 11-14 and funds year-15 sweep without negative cash."""
    path = SCENARIOS_DIR / "dutchbay_basecase_2025Q4.yaml"
    result = run_v14_pipeline(config=str(path), validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ts = build_three_statement_from_run(result, cfg)
    assert ts is not None
    verify_three_statement_waterfall_tieout(ts, result["equity_distribution"])

    for idx in (10, 11, 12, 13):
        cf = ts.cash_flow[idx]
        assert cf.locked_cash_balance > 0.0
        assert cf.closing_cash == pytest.approx(
            cf.reserve_balance + cf.locked_cash_balance, abs=1e-4
        )
    assert all(cf.closing_cash >= -1e-6 for cf in ts.cash_flow)


def test_nso250_year1_sponsor_cure_matches_waterfall() -> None:
    """Sponsor cure in Year 1 appears as positive financing inflow and non-negative cash."""
    path = SCENARIOS_DIR / "nso250_ltl_portfolio_base.yaml"
    result = run_v14_pipeline(config=str(path), validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ts = build_three_statement_from_run(result, cfg)
    assert ts is not None
    verify_three_statement_waterfall_tieout(ts, result["equity_distribution"])

    yr1_ed = result["equity_distribution"]["annual_distributions"][0]
    assert yr1_ed["equity_distribution_usd"] < -1_000_000.0
    assert ts.cash_flow[0].distributions == pytest.approx(
        -yr1_ed["equity_distribution_usd"], abs=1e-4
    )
    assert ts.cash_flow[0].closing_cash >= -1e-6


def test_fund_at_close_holdback_wht_gross_up_and_hedge_tie_out() -> None:
    """Exercise fund_at_close DSRA, holdback, grossed-up WHT, FX hedge, and equity_cfads_match."""
    raw: Dict[str, Any] = copy.deepcopy(
        dict(
            load_scenario_config(str(SCENARIOS_DIR / "dutchbay_lendercase_2025Q4.yaml"))
        )
    )
    raw.setdefault("Financing_Terms", {}).setdefault("dsra", {})["fund_at_close"] = True
    raw["Financing_Terms"]["bridge_period_treatment"] = "equity_cfads_match"
    raw.setdefault("equity_distribution", {})["holdback_pct"] = 20.0
    raw.setdefault("tax", {})["wht_gross_up"] = True
    raw.setdefault("fx", {})["hedge_ratio"] = 0.5

    result = run_v14_pipeline(config=raw, validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ed = result["equity_distribution"]
    funding = result["debt_result"]["funding"]
    opening_cash = float(funding["initial_dsra_usd"])
    assert funding["fund_at_close"] is True and opening_cash > 0.0

    ts = build_three_statement_from_run(result, cfg)
    assert ts is not None
    verify_three_statement_waterfall_tieout(ts, ed, opening_cash=opening_cash)

    # Opening cash is reflected in Year 1 paid-in equity & DSRA reserve movement.
    assert ts.cash_flow[0].reserve_movement == pytest.approx(
        ed["annual_distributions"][0]["reserve_balance_usd"] - opening_cash, abs=1e-4
    )
    assert any(cf.retained_cash_balance > 0.0 for cf in ts.cash_flow[:-1])
    assert ts.cash_flow[-1].closing_cash == pytest.approx(0.0, abs=1e-4)


def test_negative_control_diverging_distribution_or_reserve_fails_tieout() -> None:
    """Negative control: diverging distributions/reserves/cash fails even when BS balances."""
    path = SCENARIOS_DIR / "dutchbay_lendercase_2025Q4.yaml"
    result = run_v14_pipeline(config=str(path), validation_mode="strict")
    cfg = result["scenario_result"]["config"]
    ed = result["equity_distribution"]
    ts = build_three_statement_from_run(result, cfg)
    assert ts is not None

    # Control 1: Mutant ThreeStatementResult with Year 1 over-distribution (the pre-#1896 bug)
    # and matching balance-sheet retained earnings so the balance sheet check still passes.
    bad_cf_yr1 = replace(
        ts.cash_flow[0],
        distributions=-5_995_905.0,
        closing_cash=ts.cash_flow[0].closing_cash - 5_995_905.0,
    )
    bad_ts = ThreeStatementResult(
        currency=ts.currency,
        income_statement=ts.income_statement,
        cash_flow=[bad_cf_yr1, *ts.cash_flow[1:]],
        balance_sheet=ts.balance_sheet,
        tie_outs=ts.tie_outs,
    )
    with pytest.raises(ValueError, match="statement distribution"):
        verify_three_statement_waterfall_tieout(bad_ts, ed)

    # Control 2: Mutant equity_distribution row (distribution perturbed by +$500k) passed to
    # build_three_statement_from_run -> balance_sheet_balances stays True (equity is the plug),
    # while waterfall_reconciles and all_pass MUST fail.
    bad_result = copy.deepcopy(result)
    bad_result["equity_distribution"]["annual_distributions"][0][
        "equity_distribution_usd"
    ] += 500_000.0
    flagged_ts = build_three_statement_from_run(bad_result, cfg)
    assert flagged_ts is not None and flagged_ts.tie_outs is not None
    assert flagged_ts.tie_outs.balance_sheet_balances is True
    assert flagged_ts.tie_outs.waterfall_reconciles is False
    assert flagged_ts.tie_outs.all_pass is False
    with pytest.raises(ValueError, match="Three-statement tie-outs failed"):
        verify_three_statement_waterfall_tieout(
            flagged_ts, bad_result["equity_distribution"]
        )

    # Control 3: Mutant CashFlowRow reserve_balance/movement divergence is caught.
    bad_res_cf = replace(
        ts.cash_flow[0],
        reserve_balance=ts.cash_flow[0].reserve_balance + 250_000.0,
    )
    bad_res_ts = ThreeStatementResult(
        currency=ts.currency,
        income_statement=ts.income_statement,
        cash_flow=[bad_res_cf, *ts.cash_flow[1:]],
        balance_sheet=ts.balance_sheet,
        tie_outs=ts.tie_outs,
    )
    with pytest.raises(ValueError, match="reserve_balance"):
        verify_three_statement_waterfall_tieout(bad_res_ts, ed)

    # Control 4: Broken SPV cash partition (reserve + locked + retained != closing_cash)
    # is caught by verify_three_statement_waterfall_tieout even when totals balance.
    bad_part_cf = replace(
        ts.cash_flow[0],
        retained_cash_balance=ts.cash_flow[0].retained_cash_balance + 50_000.0,
    )
    bad_part_ts = ThreeStatementResult(
        currency=ts.currency,
        income_statement=ts.income_statement,
        cash_flow=[bad_part_cf, *ts.cash_flow[1:]],
        balance_sheet=ts.balance_sheet,
        tie_outs=ts.tie_outs,
    )
    with pytest.raises(ValueError, match="SPV cash partition"):
        verify_three_statement_waterfall_tieout(bad_part_ts, ed)


def test_covenant_locked_drawdown_of_prior_retained_cash_preserves_partition() -> None:
    """Locked drawdown of prior holdback/retained cash keeps partition == closing_cash."""
    from finance.equity_distribution_v14_hydra import (
        EquityDistributionConfig,
        build_equity_distribution_schedule,
    )

    # Year 1: unlocked, CFADS 40 vs DS 20 -> 50% holdback retains 10, distributes 10.
    # Year 2: locked (DSCR 1.15 < 1.25), CFADS 23 vs DS 20 -> traps 3 in locked_cash.
    # Year 3: locked shortfall (DSCR 0.75 < 1.25), CFADS 15 vs DS 20 -> draws locked 3
    #         first, then 2 from prior retained -> retained drops 10 -> 8, locked -> 0.
    # Year 4: unlocked, CFADS 30 vs DS 20 -> terminal release of remaining 8.
    annual_rows = [
        {
            "year": 1,
            "revenue_lkr": 4000.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 4000.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 5.0,
            "debt_service_total": 20.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 40.0,
            "dscr": 2.0,
        },
        {
            "year": 2,
            "revenue_lkr": 2300.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 2300.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 5.0,
            "debt_service_total": 20.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 23.0,
            "dscr": 1.15,
        },
        {
            "year": 3,
            "revenue_lkr": 1500.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 1500.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 5.0,
            "debt_service_total": 20.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 15.0,
            "dscr": 0.75,
        },
        {
            "year": 4,
            "revenue_lkr": 3000.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 3000.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 5.0,
            "debt_service_total": 20.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 30.0,
            "dscr": 1.5,
        },
    ]
    debt_result: Dict[str, Any] = {
        "debt_total": 60.0,
        "total_idc": 0.0,
        "balloon_residual": 0.0,
    }
    dist_cfg = EquityDistributionConfig(
        project_life_years=4,
        min_dscr_threshold=1.25,
        min_reserve_months=0,
        holdback_pct=50.0,
        allow_default_equity_investment=True,
        default_equity_investment_usd=40.0,
    )
    schedule = build_equity_distribution_schedule(
        annual_rows=annual_rows,
        debt_result=debt_result,
        distribution_config=dist_cfg,
    )
    pipeline_result = {
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "equity_distribution": {
            "status": "computed",
            "annual_distributions": schedule,
        },
    }
    config: Dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        "equity_distribution": {
            "project_life_years": 4,
            "min_dscr_threshold": 1.25,
            "min_reserve_months": 0,
            "holdback_pct": 50.0,
        },
    }
    ts = build_three_statement_from_run(pipeline_result, config)
    assert ts is not None and ts.tie_outs is not None
    assert ts.tie_outs.all_pass is True
    assert ts.tie_outs.waterfall_reconciles is True
    verify_three_statement_waterfall_tieout(ts, pipeline_result["equity_distribution"])

    # Verify exact partition at every year:
    # Yr 1: closing=10 (res=0, locked=0, retained=10)
    # Yr 2: closing=13 (res=0, locked=3, retained=10)
    # Yr 3: closing=8  (res=0, locked=0, retained=8)  <- locked exhausted first, then retained
    # Yr 4: closing=0  (res=0, locked=0, retained=0)
    assert ts.cash_flow[0].closing_cash == pytest.approx(10.0)
    assert ts.cash_flow[0].retained_cash_balance == pytest.approx(10.0)
    assert ts.cash_flow[0].locked_cash_balance == pytest.approx(0.0)

    assert ts.cash_flow[1].closing_cash == pytest.approx(13.0)
    assert ts.cash_flow[1].locked_cash_balance == pytest.approx(3.0)
    assert ts.cash_flow[1].retained_cash_balance == pytest.approx(10.0)

    assert ts.cash_flow[2].closing_cash == pytest.approx(8.0)
    assert ts.cash_flow[2].locked_cash_balance == pytest.approx(0.0)
    assert ts.cash_flow[2].retained_cash_balance == pytest.approx(8.0)

    assert ts.cash_flow[3].closing_cash == pytest.approx(0.0)
    assert ts.cash_flow[3].locked_cash_balance == pytest.approx(0.0)
    assert ts.cash_flow[3].retained_cash_balance == pytest.approx(0.0)


def test_unlocked_bullet_shortfall_preserves_prior_locked_cash() -> None:
    """Unlocked bullet shortfall after an earlier lock-up preserves locked cash without false tie-out failure."""
    from finance.equity_distribution_v14_hydra import (
        EquityDistributionConfig,
        build_equity_distribution_schedule,
    )

    # Yr 1: locked (DSCR 1.20 < 1.25), CFADS 30 vs DS 25 -> traps 5.0 in locked_cash.
    # Yr 2: unlocked (DSCR 2.00 >= 1.25), CFADS 20 vs DS 10 + bullet balloon 15 -> -5.0 cash call;
    #       under bullet treatment, prior locked_cash (5.0) remains held in SPV cash.
    # Yr 3: unlocked, CFADS 20 vs DS 0 -> releases prior locked_cash (5.0) + Yr 3 cash (20.0).
    annual_rows = [
        {
            "year": 1,
            "revenue_lkr": 3000.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 3000.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 5.0,
            "debt_service_total": 25.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 30.0,
            "dscr": 1.20,
        },
        {
            "year": 2,
            "revenue_lkr": 2000.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 2000.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 2.0,
            "debt_service_total": 10.0,
            "balloon_resolution": 15.0,
            "cf_pre_debt": 20.0,
            "dscr": 2.00,
        },
        {
            "year": 3,
            "revenue_lkr": 2000.0,
            "opex_lkr": 0.0,
            "ebitda_lkr": 2000.0,
            "total_depreciation_lkr": 1000.0,
            "tax_lkr": 0.0,
            "fx_rate": 100.0,
            "interest_usd": 0.0,
            "debt_service_total": 0.0,
            "balloon_resolution": 0.0,
            "cf_pre_debt": 20.0,
        },
    ]
    debt_result: Dict[str, Any] = {
        "debt_total": 43.0,
        "total_idc": 0.0,
        "balloon_residual": 0.0,
        "balloon_treatment": "bullet",
    }
    dist_cfg = EquityDistributionConfig(
        project_life_years=3,
        min_dscr_threshold=1.25,
        min_reserve_months=0,
        allow_default_equity_investment=True,
        default_equity_investment_usd=57.0,
    )
    schedule = build_equity_distribution_schedule(
        annual_rows=annual_rows,
        debt_result=debt_result,
        distribution_config=dist_cfg,
    )
    pipeline_result = {
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "equity_distribution": {
            "status": "computed",
            "annual_distributions": schedule,
        },
    }
    config: Dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        "equity_distribution": {
            "project_life_years": 3,
            "min_dscr_threshold": 1.25,
            "min_reserve_months": 0,
        },
    }
    ts = build_three_statement_from_run(pipeline_result, config)
    assert ts is not None and ts.tie_outs is not None
    assert ts.tie_outs.all_pass is True
    assert ts.tie_outs.waterfall_reconciles is True
    verify_three_statement_waterfall_tieout(ts, pipeline_result["equity_distribution"])

    assert ts.cash_flow[0].closing_cash == pytest.approx(5.0)
    assert ts.cash_flow[0].locked_cash_balance == pytest.approx(5.0)
    assert ts.cash_flow[1].closing_cash == pytest.approx(5.0)
    assert ts.cash_flow[1].locked_cash_balance == pytest.approx(5.0)
    assert -ts.cash_flow[1].distributions == pytest.approx(-5.0)
    assert ts.cash_flow[2].closing_cash == pytest.approx(0.0)
    assert -ts.cash_flow[2].distributions == pytest.approx(25.0)
