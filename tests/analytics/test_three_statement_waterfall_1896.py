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
