"""A senior fee the period's cash cannot pay is deferred and carried forward (#1539).

Owner ruling on #1539 (2026-11-15): on a capitalising cash sweep, when the senior
credit-support fee due exceeds the period's available cash, the unpaid part is deferred
and carried forward. It is paid first from later cash, carries no interest, and any
amount still unpaid at the horizon is published as a residual. Before this the full fee
was charged even when it exceeded the period's cash, so equity could be asked for more
than the period generated.

The oracles are hand-computed on a small schedule, independent of the engine.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from finance.debt_v14 import _balloon_resolution_path
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    build_equity_distribution_schedule,
)

# Index 0 construction, 1-2 scheduled service, maturity at period 3, then 3-6 post-maturity.
_DS = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0, 0.0]
_N = len(_DS)


def _path(
    treatment: str, cfads: List[float], *, fee_rate: float, tenor: int = 0
) -> Dict[str, Any]:
    return _balloon_resolution_path(
        treatment=treatment,
        balloon=100.0,
        cfads_ext=cfads,
        debt_service_total=_DS,
        construction_periods=1,
        timeline_periods=_N,
        avg_rate=0.10,
        refi_tenor_years=tenor,
        refi_rate_premium=0.0,
        senior_fee_rate=fee_rate,
    )


def test_unpaid_fee_is_deferred_then_paid_first_from_later_cash() -> None:
    """Negative control: before #1539 the p3 fee was 20.0 against 5.0 of cash."""
    # p3: fee due 20 (20% of 100), cash 5 -> pay 5, defer 15; nothing reaches the
    #     balloon, which capitalises 10 of interest -> 110.
    # p4: fee due 22 + 15 = 37, cash 5 -> pay 5, defer 32; balloon -> 121.
    # p5: fee due 24.2 + 32 = 56.2, cash 100 -> pay it all; 43.8 sweeps the balloon,
    #     settling the 21 capitalised and 12.1 accrued interest first -> 89.3.
    # p6: fee due 17.86, cash 100 -> pay it; 82.14 sweeps 98.23 due -> 16.09 left.
    cfads = [0.0, 0.0, 0.0, 5.0, 5.0, 100.0, 100.0]
    path = _path("cash_sweep", cfads, fee_rate=0.20)
    assert path["outstanding"][3:] == pytest.approx([100.0, 110.0, 121.0, 89.3])
    assert path["senior_fee"][3:] == pytest.approx([5.0, 5.0, 56.2, 17.86])
    assert path["senior_fee_deferred"][3:] == pytest.approx([15.0, 32.0, 0.0, 0.0])
    assert path["resolution"][3:] == pytest.approx([0.0, 0.0, 43.8, 82.14])
    assert path["interest_paid"][3:] == pytest.approx([0.0, 0.0, 33.1, 8.93])
    assert path["residual"] == pytest.approx(16.09)
    assert path["senior_fee_deferred_residual"] == pytest.approx(0.0)


def test_equity_is_never_asked_for_more_than_the_period_generates() -> None:
    cfads = [0.0, 0.0, 0.0, 5.0, 5.0, 100.0, 100.0]
    path = _path("cash_sweep", cfads, fee_rate=0.20)
    for p in range(3, _N):
        assert path["senior_fee"][p] + path["resolution"][p] <= cfads[p] + 1e-9


def test_fee_is_conserved_between_paid_and_deferred() -> None:
    cfads = [0.0, 0.0, 0.0, 5.0, 5.0, 100.0, 100.0]
    path = _path("cash_sweep", cfads, fee_rate=0.20)
    charged = sum(0.20 * path["outstanding"][p] for p in range(3, _N))
    paid = sum(path["senior_fee"][3:])
    assert paid + path["senior_fee_deferred_residual"] == pytest.approx(charged)


def test_fee_never_paid_is_published_as_a_residual() -> None:
    # 1.0 of cash a period: deferred 19, 40, 63.2, 88.82; the balloon capitalises
    # 10% a period: 100 -> 110 -> 121 -> 133.1 -> 146.41.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0], fee_rate=0.20)
    assert path["senior_fee"][3:] == pytest.approx([1.0] * 4)
    assert path["senior_fee_deferred"][3:] == pytest.approx([19.0, 40.0, 63.2, 88.82])
    assert path["senior_fee_deferred_residual"] == pytest.approx(88.82)
    assert path["residual"] == pytest.approx(146.41)


def test_a_fee_the_cash_covers_is_unchanged_and_never_deferred() -> None:
    # Same figures as test_balloon_post_maturity_carry's 2% case.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0], fee_rate=0.02)
    assert path["senior_fee"] == pytest.approx([None, None, None, 2.0, 1.04, 0.0, 0.0])
    assert path["senior_fee_deferred"] == [None, None, None, 0.0, 0.0, 0.0, 0.0]
    assert path["senior_fee_deferred_residual"] == 0.0


@pytest.mark.parametrize(("treatment", "tenor"), [("bullet", 0), ("refinance", 3)])
def test_other_treatments_defer_nothing(treatment: str, tenor: int) -> None:
    path = _path(treatment, [0.0] * _N, fee_rate=0.20, tenor=tenor)
    governed = [p for p in range(_N) if path["outstanding"][p] is not None]
    assert governed
    assert all(path["senior_fee_deferred"][p] == 0.0 for p in governed)
    assert all(
        path["senior_fee_deferred"][p] is None for p in range(_N) if p not in governed
    )
    assert path["senior_fee_deferred_residual"] == 0.0


def test_debt_result_publishes_the_deferral_for_the_lender_case() -> None:
    debt = run_v14_pipeline("scenarios/dutchbay_lendercase_2025Q4.yaml")["debt_result"]
    assert "senior_fee_deferred_usd" in debt
    assert debt["senior_fee_deferred_residual"] == 0.0


def test_a_negative_cash_period_pays_no_fee_and_defers_it_all() -> None:
    """Assurance A-2, mutant M1: a negative period must not book a negative fee."""
    # p3: fee due 20, cash -10 -> pay 0, defer 20; balloon capitalises 10 -> 110.
    # p4: fee due 22 + 20 = 42, cash 5 -> pay 5, defer 37; balloon -> 121.
    # p5: fee due 24.2 + 37 = 61.2, cash 100 -> pay it; 38.8 settles the 21
    #     capitalised and 12.1 accrued interest first -> 94.3.
    # p6: fee due 18.86, cash 100 -> pay it; 81.14 sweeps 103.73 due -> 22.59 left.
    cfads = [0.0, 0.0, 0.0, -10.0, 5.0, 100.0, 100.0]
    path = _path("cash_sweep", cfads, fee_rate=0.20)
    assert path["senior_fee"][3:] == pytest.approx([0.0, 5.0, 61.2, 18.86])
    assert path["senior_fee_deferred"][3:] == pytest.approx([20.0, 37.0, 0.0, 0.0])
    assert path["resolution"][3:] == pytest.approx([0.0, 0.0, 38.8, 81.14])
    assert path["residual"] == pytest.approx(22.59)


# ── The equity waterfall settles the arrears ahead of equity (domain DOM-1) ────────


def _waterfall(
    deferred: List[Optional[float]],
    cash: List[float],
    *,
    service: Optional[List[float]] = None,
    **config: Any,
) -> List[Dict[str, Any]]:
    service = service or [0.0] * len(cash)
    rows = []
    for i, (d, c, ds) in enumerate(zip(deferred, cash, service, strict=True)):
        row: Dict[str, Any] = {
            "year": i + 1,
            "cf_pre_debt": c,
            "debt_service_total": ds,
        }
        row["senior_fee_deferred_usd"] = d
        rows.append(row)
    settings = {"min_reserve_months": 0, "min_dscr_threshold": 0.0}
    settings.update(config)
    return build_equity_distribution_schedule(
        annual_rows=rows,
        debt_result={},
        distribution_config=EquityDistributionConfig(**settings),
    )


def _col(schedule: List[Dict[str, Any]], key: str) -> List[float]:
    return [row[key] for row in schedule]


def test_waterfall_pays_arrears_before_any_distribution() -> None:
    # y1: no arrears -> 10 to equity. y2: 4 owed -> paid, 6 to equity.
    # y3: the engine carries 15, 11 of it new; 10 of cash pays 10 -> 1 owed, nothing
    #     to equity. y4: the row is not governed, so 15 carries; 1 paid, 9 to equity.
    schedule = _waterfall([None, 4.0, 15.0, None], [10.0] * 4)
    assert _col(schedule, "senior_fee_arrears_settled_usd") == pytest.approx(
        [0.0, 4.0, 10.0, 1.0]
    )
    assert _col(schedule, "senior_fee_arrears_usd") == pytest.approx(
        [0.0, 0.0, 1.0, 0.0]
    )
    assert _col(schedule, "equity_distribution_usd") == pytest.approx(
        [10.0, 6.0, 0.0, 9.0]
    )


def test_waterfall_returns_arrears_the_engine_pays_again() -> None:
    # y1: 5 owed -> paid from equity cash. y2: the engine's own later cash paid the
    # arrears (its balance is 0), so the 5 is handed back rather than paid twice.
    schedule = _waterfall([5.0, 0.0], [10.0, 10.0])
    assert _col(schedule, "senior_fee_arrears_settled_usd") == pytest.approx(
        [5.0, -5.0]
    )
    assert _col(schedule, "equity_distribution_usd") == pytest.approx([5.0, 15.0])


def test_waterfall_uses_spv_held_cash_and_never_calls_equity() -> None:
    # 50% holdback: y1 and y2 each retain 5. y3 owes 30: 10 of cash, then the 10
    # retained -> 10 still owed, no distribution and no cash call.
    schedule = _waterfall([None, None, 30.0], [10.0] * 3, holdback_pct=50.0)
    assert _col(schedule, "senior_fee_arrears_settled_usd") == pytest.approx(
        [0.0, 0.0, 20.0]
    )
    assert schedule[-1]["senior_fee_arrears_usd"] == pytest.approx(10.0)
    assert _col(schedule, "equity_distribution_usd") == pytest.approx([5.0, 5.0, 0.0])


def test_horizon_arrears_take_the_terminal_release_first_and_warn(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 12-month reserve on 6 of service: y1 funds 6 and distributes 8. y2's cash meets
    # only its service, so the 10 owed stays. At the horizon the reserve's 6 pays the
    # arrears before any release -> 4 unpaid, nothing released to the sponsor.
    with caplog.at_level(logging.WARNING):
        schedule = _waterfall(
            [None, 10.0], [20.0, 6.0], service=[6.0, 6.0], min_reserve_months=12
        )
    assert _col(schedule, "senior_fee_arrears_settled_usd") == pytest.approx([0.0, 6.0])
    assert schedule[-1]["senior_fee_arrears_usd"] == pytest.approx(4.0)
    assert schedule[-1]["terminal_release_usd"] == 0.0
    # #1736 item 7 (M13): the reserve the settlement used is not reported as still held.
    assert schedule[-1]["reserve_balance_usd"] == 0.0
    assert _col(schedule, "equity_distribution_usd") == pytest.approx([8.0, 0.0])
    assert "still unpaid at the horizon" in caplog.text


def test_arrears_in_a_cash_call_year_come_from_spv_held_cash_only() -> None:
    """#1736 item 7 (M14): a year whose cash for equity is negative pays no arrears
    from that cash; they come from cash the SPV holds, and the cash call stands."""
    # y1: 50% holdback retains 5. y2: 10 of cash against a 15 balloon payment (a
    # bullet, so a cash call of 5); 3 owed -> 3 from the 5 retained, 2 left.
    rows = [
        {"year": 1, "cf_pre_debt": 10.0, "debt_service_total": 0.0},
        {
            "year": 2,
            "cf_pre_debt": 10.0,
            "debt_service_total": 0.0,
            "balloon_resolution": 15.0,
            "senior_fee_deferred_usd": 3.0,
        },
    ]
    schedule = build_equity_distribution_schedule(
        annual_rows=rows,
        debt_result={"balloon_treatment": "bullet"},
        distribution_config=EquityDistributionConfig(
            min_reserve_months=0, min_dscr_threshold=0.0, holdback_pct=50.0
        ),
    )
    assert _col(schedule, "senior_fee_arrears_settled_usd") == pytest.approx([0.0, 3.0])
    assert schedule[-1]["senior_fee_arrears_usd"] == pytest.approx(0.0)
    # y1 pays 5 out; y2 is a cash call of 5, and the 2 still retained is released at
    # the horizon into the same year.
    assert _col(schedule, "equity_distribution_usd") == pytest.approx([5.0, -5.0 + 2.0])


def test_no_arrears_leave_the_waterfall_unchanged() -> None:
    cash = [10.0, -3.0, 12.0]
    service = [4.0, 4.0, 4.0]
    base = _waterfall([None] * 3, cash, service=service, holdback_pct=20.0)
    zero = _waterfall([0.0] * 3, cash, service=service, holdback_pct=20.0)
    assert base == zero
    assert all(row["senior_fee_arrears_settled_usd"] == 0.0 for row in base)


# ── End to end: a cash sweep with a fee its cash cannot pay (A-2, DOM-1, DOM-2) ─────


@pytest.fixture(scope="module")
def stressed_run(tmp_path_factory: pytest.TempPathFactory) -> Dict[str, Any]:
    """The base case on a cash sweep with a 5% guarantee fee. A synthetic stress, not
    a committed scenario: no committed scenario reaches a deferral."""
    config = yaml.safe_load(Path("scenarios/dutchbay_basecase_2025Q4.yaml").read_text())
    terms = config["Financing_Terms"]
    terms["balloon_treatment"] = "cash_sweep"
    fees = terms.setdefault("fees", {})
    fees["guarantee_fee_pct_per_year"] = 0.05
    fees["pri_premium_pct_per_year"] = 0.0
    path = tmp_path_factory.mktemp("fee1539") / "stress.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    return run_v14_pipeline(str(path))


def test_plan_debt_publishes_a_real_deferral(stressed_run: Dict[str, Any]) -> None:
    """Assurance A-2, mutant M4: plan_debt must publish the path's deferral."""
    debt = stressed_run["debt_result"]
    assert any((v or 0.0) > 0.0 for v in debt["senior_fee_deferred_usd"])
    assert debt["senior_fee_deferred_residual"] > 0.0


def test_no_distribution_while_arrears_are_owed(stressed_run: Dict[str, Any]) -> None:
    rows = stressed_run["equity_distribution"]["annual_distributions"]
    # #1736: the engine's sweep reads this waterfall's cash, so the engine defers only
    # what that cash cannot pay and the waterfall has nothing left to settle (up to the
    # pipeline's fixed-point tolerance of USD 0.01 a period).
    assert sum(row["senior_fee_arrears_settled_usd"] for row in rows) == pytest.approx(
        0.0, abs=0.01 * len(rows)
    )
    assert any(row["senior_fee_arrears_usd"] > 1e-6 for row in rows)
    for row in rows:
        if row["senior_fee_arrears_usd"] > 1e-6:
            assert row["equity_distribution_usd"] <= 0.0, row["year"]


def test_unpaid_fee_is_on_the_kpi_surface(stressed_run: Dict[str, Any]) -> None:
    debt = stressed_run["debt_result"]
    summary = stressed_run["equity_distribution"]["equity_summary"]
    unpaid = stressed_run["kpis"]["senior_fee_deferred_residual"]
    assert unpaid == pytest.approx(summary["senior_fee_unpaid_at_horizon_usd"])
    # Charged = paid by the engine + settled by the waterfall + unpaid.
    assert unpaid == pytest.approx(
        debt["senior_fee_deferred_residual"]
        - summary["total_senior_fee_arrears_settled_usd"]
    )
    # #1736 item 5: on one cash basis the KPI and the engine's figure are the same.
    assert unpaid == pytest.approx(debt["senior_fee_deferred_residual"], abs=0.1)
    assert unpaid > 0.0
