"""One cash basis decides the post-maturity sweep and the senior-fee deferral (#1736).

Owner ruling on #1736 (2026-11-15): "One cash basis". The debt engine's cash sweep and
fee deferral, and the equity waterfall, must agree on the cash the SPV has after
maturity. The basis taken is the waterfall's: the cash after scheduled service and
interest WHT on the equity-facing rows (the tax the SPV pays), plus the cash the SPV
holds (the reserve, lockup-trapped cash and retentions). The pipeline iterates the
engine's sweep and that cash to a fixed point.

``TEST-01`` oracles that did not originate in this change: the equity waterfall's own
schedule (what it holds and what it pays), the engine's published fee and balloon
series, and the rows' own fee and EBITDA columns. The base case and the lender case
are committed scenarios; the fee and WHT stresses are synthetic, since no committed
scenario defers a fee.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from analytics.pipeline_v14_enhanced import (
    _interest_paid_lkr_series,
    run_v14_pipeline,
)
from analytics.three_statement import build_three_statement_from_run
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import _balloon_resolution_path
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    build_equity_distribution_schedule,
    waterfall_sweep_cash,
)

BASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")
LENDER = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")
# The pipeline settles the sweep on the waterfall's cash to USD 0.01 a period.
TOL = 0.01


def _load(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _run(config: Dict[str, Any], tmp_path: Path, name: str) -> Dict[str, Any]:
    path = tmp_path / f"{name}.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return run_v14_pipeline(str(path))


def _fee_stress(fee: float = 0.05) -> Dict[str, Any]:
    """The base case on a cash sweep with a guarantee fee its cash cannot pay."""
    config = _load(BASE)
    terms = config["Financing_Terms"]
    terms["balloon_treatment"] = "cash_sweep"
    fees = terms.setdefault("fees", {})
    fees["guarantee_fee_pct_per_year"] = fee
    fees["pri_premium_pct_per_year"] = 0.0
    return config


def _governed_rows(run: Dict[str, Any]) -> List[tuple[int, int]]:
    """(row index, period) for every row whose period the balloon path governs."""
    debt = run["debt_result"]
    deferred = debt["senior_fee_deferred_usd"]
    out = []
    for mapping in debt["annual_row_debt_period_map"]:
        period = int(mapping["debt_period"])
        if period < len(deferred) and deferred[period] is not None:
            out.append((int(mapping["annual_row_index"]), period))
    assert out, "the run must reach the post-maturity sweep"
    return out


@pytest.fixture(scope="module")
def fee_run(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    return _run(_fee_stress(), tmp_path_factory.mktemp("f7"), "fee")


@pytest.fixture(scope="module")
def base_run() -> Dict[str, Any]:
    return run_v14_pipeline(str(BASE))


# ── One basis, end to end ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("which", ["fee", "base"])
def test_the_sweep_takes_exactly_the_cash_the_waterfall_holds(
    which: str, fee_run: Dict[str, Any], base_run: Dict[str, Any]
) -> None:
    """While the balloon is unpaid, the engine pays out all the waterfall's cash.

    The engine pays the fee first, then the balloon; the rows are already net of the
    fee it paid, so the waterfall's cash for the balloon is the engine's resolution.
    """
    run = fee_run if which == "fee" else base_run
    debt = run["debt_result"]
    schedule = run["equity_distribution"]["annual_distributions"]
    for row_index, period in _governed_rows(run):
        row = schedule[row_index]
        if debt["debt_outstanding"][period] <= 0.0:
            continue
        held = row["cash_available_for_balloon_usd"]
        assert debt["balloon_resolution"][period] == pytest.approx(
            max(0.0, held), abs=TOL
        ), row["year"]
        assert row["equity_distribution_usd"] == pytest.approx(0.0, abs=TOL)
        assert row["sponsor_cure_usd"] == pytest.approx(0.0, abs=TOL)
    assert debt["balloon_residual"] > 0.0


def test_the_reserve_and_spv_held_cash_go_to_the_balloon(
    base_run: Dict[str, Any],
) -> None:
    """The committed base case: at maturity the reserve and the trapped cash are swept.

    Before #1736 the year the balloon fell due released the reserve and the
    lockup-trapped cash to equity while the balloon stayed unpaid.
    """
    schedule = base_run["equity_distribution"]["annual_distributions"]
    first_row, period = _governed_rows(base_run)[0]
    row, prior = schedule[first_row], schedule[first_row - 1]
    assert prior["reserve_balance_usd"] > 0.0
    assert row["cash_available_for_balloon_usd"] > (
        row["cf_after_debt_usd"] + prior["reserve_balance_usd"]
    )
    assert row["spv_cash_applied_usd"] > 0.0
    assert base_run["debt_result"]["balloon_resolution"][period] == pytest.approx(
        row["cash_available_for_balloon_usd"], abs=TOL
    )
    assert row["equity_distribution_usd"] == pytest.approx(0.0, abs=TOL)


def test_the_waterfall_has_nothing_left_to_settle(fee_run: Dict[str, Any]) -> None:
    debt = fee_run["debt_result"]
    summary = fee_run["equity_distribution"]["equity_summary"]
    assert debt["senior_fee_deferred_residual"] > 0.0
    assert summary["total_senior_fee_arrears_settled_usd"] == pytest.approx(
        0.0, abs=TOL * len(fee_run["annual_rows"])
    )
    # Item 5: the KPI and the engine's figure are the same number.
    assert fee_run["kpis"]["senior_fee_deferred_residual"] == pytest.approx(
        debt["senior_fee_deferred_residual"], abs=0.1
    )


def test_every_fee_paid_reaches_the_rows_the_covers_and_the_statements(
    fee_run: Dict[str, Any],
) -> None:
    """The fee the engine paid is the fee the rows charge, so tax and NPV (which read
    the rows), PLCR (which re-nets on `senior_fee_usd`) and the statements (whose EBITDA
    is the rows') all carry it on one basis."""
    debt = fee_run["debt_result"]
    rows = fee_run["annual_rows"]
    deferred_any = False
    for mapping in debt["annual_row_debt_period_map"]:
        index, period = int(mapping["annual_row_index"]), int(mapping["debt_period"])
        row = rows[index]
        assert row["senior_fee_lkr"] / row["fx_rate"] == pytest.approx(
            debt["senior_fee_usd"][period], rel=1e-9, abs=1e-6
        )
        deferred_any |= (debt["senior_fee_deferred_usd"][period] or 0.0) > 0.0
    assert deferred_any
    statements = build_three_statement_from_run(fee_run, _fee_stress())
    assert statements is not None
    for row, line in zip(rows, statements.income_statement, strict=True):
        assert line.ebitda == pytest.approx(row["ebitda_lkr"] / row["fx_rate"])
    assert statements.tie_outs.balance_sheet_balances


def test_wht_gross_up_is_inside_the_one_basis(tmp_path: Path) -> None:
    """With the interest WHT grossed up the SPV pays it before the sweep; the engine
    sweeps what is left, so the waterfall never calls equity for it."""
    config = _fee_stress(0.02)
    tax = config.setdefault("tax", {})
    tax["wht_on_interest_enabled"] = True
    tax["wht_on_interest_to_nonresidents"] = 0.14
    tax["wht_gross_up"] = True
    run = _run(config, tmp_path, "wht")
    debt = run["debt_result"]
    schedule = run["equity_distribution"]["annual_distributions"]
    wht_after_maturity = 0.0
    for row_index, period in _governed_rows(run):
        row = schedule[row_index]
        if debt["debt_outstanding"][period] <= 0.0:
            continue
        wht_after_maturity += row["wht_on_interest_usd"]
        assert debt["balloon_resolution"][period] == pytest.approx(
            max(0.0, row["cash_available_for_balloon_usd"]), abs=TOL
        )
        assert row["sponsor_cure_usd"] == pytest.approx(0.0, abs=TOL)
    assert wht_after_maturity > 0.0


def test_other_treatments_are_not_iterated(base_run: Dict[str, Any]) -> None:
    lender = run_v14_pipeline(str(LENDER))
    assert lender["debt_result"]["balloon_treatment"] == "refinance"
    assert (
        waterfall_sweep_cash(
            config=_load(LENDER),
            annual_rows=lender["annual_rows"],
            debt_result=lender["debt_result"],
        )
        is None
    )
    assert base_run["debt_result"]["balloon_treatment"] == "cash_sweep"


def test_horizon_warning_comes_from_the_engine_without_the_waterfall(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Item 6 and mutant M12: with distributions off, the engine still warns, and the
    KPI is the engine's figure (the metrics line)."""
    config = _fee_stress()
    config.setdefault("equity_distribution", {})["enabled"] = False
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        run = _run(config, tmp_path, "off")
    assert run["equity_distribution"]["status"] == "disabled"
    residual = run["debt_result"]["senior_fee_deferred_residual"]
    assert residual > 0.0
    assert run["kpis"]["senior_fee_deferred_residual"] == pytest.approx(residual)
    assert any(
        "still unpaid at the horizon" in record.getMessage()
        and record.name == "finance.debt_v14"
        for record in caplog.records
    )


# ── Units ──────────────────────────────────────────────────────────────────────────

# Index 0 construction, 1-2 scheduled service, maturity at period 3, then 3-5.
_DS = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0]


def _sweep(sweep_cash: Optional[List[Optional[float]]]) -> Dict[str, Any]:
    return _balloon_resolution_path(
        treatment="cash_sweep",
        balloon=100.0,
        cfads_ext=[0.0, 20.0, 20.0, 30.0, 30.0, 30.0],
        debt_service_total=_DS,
        construction_periods=1,
        timeline_periods=len(_DS),
        avg_rate=0.0,
        refi_tenor_years=0,
        refi_rate_premium=0.0,
        senior_fee_rate=0.10,
        sweep_cash=sweep_cash,
    )


def test_the_engine_reads_the_supplied_cash_and_falls_back_per_period() -> None:
    # Period 3 reads 50 (fee 10, sweep 40); period 4 has no figure, so it reads the
    # sizing CFADS of 30 (fee 6, sweep 24); period 5 reads 4 (fee due 3.6, sweep 0.4).
    path = _sweep([None, None, None, 50.0, None, 4.0])
    assert path["senior_fee"][3:] == pytest.approx([10.0, 6.0, 3.6])
    assert path["resolution"][3:] == pytest.approx([40.0, 24.0, 0.4])
    assert path["residual"] == pytest.approx(35.6)
    # Without a supplied basis every period reads the sizing CFADS of 30: fees 10, 8
    # and 5.8 on the falling balance.
    assert _sweep(None)["resolution"][3:] == pytest.approx([20.0, 22.0, 24.2])


def _waterfall(
    rows: List[Dict[str, Any]], debt_result: Dict[str, Any], **config: Any
) -> List[Dict[str, Any]]:
    settings: Dict[str, Any] = {"min_reserve_months": 0, "min_dscr_threshold": 0.0}
    settings.update(config)
    return build_equity_distribution_schedule(
        annual_rows=rows,
        debt_result=debt_result,
        distribution_config=EquityDistributionConfig(**settings),
    )


def test_the_sweep_draws_locked_cash_before_retentions_and_calls_no_equity() -> None:
    """Mutant M7's order, for the sweep: lockup-trapped cash first, then retentions."""
    # y1: DSCR 1.0 under a 1.3 lockup traps the 10 left after service.
    # y2: unlocked, 50% holdback: 10 of cash -> 5 out, 5 retained; the 10 locked is
    #     released into it first, so 20 available -> 10 out, 10 retained.
    # y3: no service; the sweep takes 25 against 5 of cash: 5, then locked 0, then
    #     retained 10 -> 10 still short, a cash call of 10.
    rows = [
        {"year": 1, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 1.0},
        {"year": 2, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 2.0},
        {
            "year": 3,
            "cf_pre_debt": 5.0,
            "debt_service_total": 0.0,
            "balloon_resolution": 25.0,
        },
    ]
    sweep = _waterfall(
        rows,
        {"balloon_treatment": "cash_sweep"},
        min_dscr_threshold=1.3,
        holdback_pct=50.0,
    )
    other = _waterfall(
        rows, {"balloon_treatment": "bullet"}, min_dscr_threshold=1.3, holdback_pct=50.0
    )
    assert [r["cash_available_for_balloon_usd"] for r in sweep] == pytest.approx(
        [10.0, 20.0, 15.0]
    )
    assert sweep[2]["spv_cash_applied_usd"] == pytest.approx(10.0)
    assert sweep[2]["equity_distribution_usd"] == pytest.approx(-10.0)
    # Other treatments keep their cash call and the retention reaches the sponsor.
    assert other[2]["spv_cash_applied_usd"] == 0.0
    assert other[2]["equity_distribution_usd"] == pytest.approx(-20.0 + 10.0)


def test_locked_cash_is_drawn_before_retained_cash() -> None:
    # y1 locked (DSCR 1.0): 10 trapped. y2 locked: 10 more trapped -> 20 locked, and
    # 20% of nothing retained. y3 (no service): the sweep takes 15 of a 0 cash year
    # from the 20 locked, leaving 5, which the unlocked year then releases.
    rows = [
        {"year": 1, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 1.0},
        {"year": 2, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 1.0},
        {
            "year": 3,
            "cf_pre_debt": 0.0,
            "debt_service_total": 0.0,
            "balloon_resolution": 15.0,
        },
    ]
    schedule = _waterfall(
        rows, {"balloon_treatment": "cash_sweep"}, min_dscr_threshold=1.3
    )
    assert schedule[2]["spv_cash_applied_usd"] == pytest.approx(15.0)
    assert schedule[2]["equity_distribution_usd"] == pytest.approx(5.0)


def test_with_both_balances_held_the_sweep_takes_locked_cash_first() -> None:
    """Mutant M6: the order matters only when both balances are held at the sweep."""
    # y1 unlocked, 50% holdback: 10 after service -> 5 out, 5 retained.
    # y2 locked (DSCR 1.0): 10 trapped. The SPV now holds 10 locked and 5 retained.
    # y3 (no service, unlocked): the sweep takes 8 from the 10 locked, leaving 2,
    #    which the unlocked year releases under the holdback (1 out, 1 retained).
    #    Retentions first would leave 7 locked and release 3.5 here instead.
    # y4 (end): the 5 + 1 retained is released.
    rows = [
        {"year": 1, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 2.0},
        {"year": 2, "cf_pre_debt": 20.0, "debt_service_total": 10.0, "dscr": 1.0},
        {
            "year": 3,
            "cf_pre_debt": 0.0,
            "debt_service_total": 0.0,
            "balloon_resolution": 8.0,
        },
        {"year": 4, "cf_pre_debt": 0.0, "debt_service_total": 0.0},
    ]
    schedule = _waterfall(
        rows,
        {"balloon_treatment": "cash_sweep"},
        min_dscr_threshold=1.3,
        holdback_pct=50.0,
    )
    assert schedule[2]["spv_cash_applied_usd"] == pytest.approx(8.0)
    assert [r["equity_distribution_usd"] for r in schedule] == pytest.approx(
        [5.0, 0.0, 1.0, 6.0]
    )


def test_waterfall_sweep_cash_adds_back_the_fee_the_rows_paid() -> None:
    rows = [
        {"year": 1, "cf_pre_debt": 20.0, "debt_service_total": 10.0},
        {"year": 2, "cf_pre_debt": 7.0, "debt_service_total": 0.0},
    ]
    debt_result = {
        "balloon_treatment": "cash_sweep",
        "senior_fee_deferred_usd": [None, None, 0.0],
        "senior_fee_usd": [0.0, 1.0, 3.0],
        "annual_row_debt_period_map": [
            {"annual_row_index": 0, "debt_period": 1},
            {"annual_row_index": 1, "debt_period": 2},
        ],
    }
    config = {"equity_distribution": {"min_reserve_months": 0}}
    cash = waterfall_sweep_cash(
        config=config, annual_rows=rows, debt_result=debt_result
    )
    assert cash == [None, None, pytest.approx(10.0)]
    assert (
        waterfall_sweep_cash(
            config=config,
            annual_rows=rows,
            debt_result={**debt_result, "senior_fee_deferred_usd": [None] * 3},
        )
        is None
    )


# ── #1539 DOM-4: the reported interest WHT is on interest paid ────────────────────


def test_reported_wht_is_on_interest_paid() -> None:
    config = _load(LENDER)
    deducted = [1_000.0] * 30
    paid = [400.0] * 30
    rows = build_annual_rows(config, interest_expense_series=deducted)
    paid_rows = build_annual_rows(
        config, interest_expense_series=deducted, interest_paid_series=paid
    )
    rate = rows[0]["wht_on_interest"] / 1_000.0
    assert rate > 0.0
    for row, paid_row in zip(rows, paid_rows, strict=True):
        assert paid_row["wht_on_interest"] == pytest.approx(400.0 * rate)
        assert paid_row["cfads_final_lkr"] == row["cfads_final_lkr"]
        assert paid_row["tax_lkr"] == row["tax_lkr"]


def test_the_paid_basis_passes_no_separate_series() -> None:
    rows = [{"interest_usd": 1.0, "balloon_interest_paid_usd": 2.0, "fx_rate": 300.0}]
    assert _interest_paid_lkr_series(rows, "paid") is None
    assert _interest_paid_lkr_series(rows, "accrued") == pytest.approx([900.0])
    assert _interest_paid_lkr_series(rows, "none") == pytest.approx([900.0])
