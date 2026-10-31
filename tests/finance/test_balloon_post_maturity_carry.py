"""The balloon after maturity: it accrues interest and bears the fee on what is left.

#1503: ``cash_sweep`` and ``bullet`` used to retire the balloon interest-free.
#1504: ``debt_outstanding`` and the senior credit-support fee stayed on the structural
balloon to the end of the timeline, even after the balloon was repaid.

The oracles here are hand-computed on small schedules, independent of the engine's own
arithmetic, and the scenario checks tie the published series to one another.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

import pytest

from finance.debt_v14 import _balloon_resolution_path

# Three scheduled periods (index 0 construction, 1-2 service), maturity at period 3,
# then four post-maturity periods.
_DS = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0, 0.0]
_N = len(_DS)


def _path(
    treatment: str,
    cfads: List[float],
    *,
    rate: float = 0.10,
    fee_rate: float = 0.0,
    tenor: int = 0,
    premium: float = 0.0,
) -> Dict[str, Any]:
    return _balloon_resolution_path(
        treatment=treatment,
        balloon=100.0,
        cfads_ext=cfads,
        debt_service_total=_DS,
        construction_periods=1,
        timeline_periods=_N,
        avg_rate=rate,
        refi_tenor_years=tenor,
        refi_rate_premium=premium,
        senior_fee_rate=fee_rate,
    )


def test_cash_sweep_pays_interest_first_and_clears() -> None:
    # 60 of cash a period: p3 opens 100, accrues 10, pays 60 -> 50;
    # p4 opens 50, accrues 5, pays 55 and clears; p5-p6 carry nothing.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0])
    assert path["outstanding"] == [None, None, None, 100.0, 50.0, 0.0, 0.0]
    assert path["interest"] == pytest.approx([0, 0, 0, 10.0, 5.0, 0, 0])
    assert path["resolution"] == pytest.approx([0, 0, 0, 60.0, 55.0, 0, 0])
    assert path["residual"] == 0.0


def test_cash_sweep_capitalises_interest_the_cash_cannot_pay() -> None:
    # 4 of cash a period against 10% on 100: the balance grows by 6, 6.6, 7.26, 7.986.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 4.0, 4.0, 4.0, 4.0])
    opening = [100.0, 106.0, 112.6, 119.86]
    assert path["outstanding"][3:] == pytest.approx(opening)
    assert path["resolution"][3:] == pytest.approx([4.0] * 4)
    assert path["residual"] == pytest.approx(119.86 * 1.1 - 4.0)
    # Cash conserves: paid + residual == balloon + accrued interest.
    assert sum(path["resolution"]) + path["residual"] == pytest.approx(
        100.0 + sum(path["interest"])
    )


def test_cash_sweep_fee_is_on_the_balance_outstanding() -> None:
    # 2% fee: p3 fee 2.0 on 100, so 58 of the 60 is swept: 100 + 10 - 58 = 52;
    # p4 fee 1.04 on 52, due 57.2, available 58.96, so it clears.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0], fee_rate=0.02)
    assert path["senior_fee"] == pytest.approx([None, None, None, 2.0, 1.04, 0.0, 0.0])
    assert path["resolution"][3:5] == pytest.approx([58.0, 57.2])
    assert path["residual"] == 0.0


def test_bullet_repays_the_balloon_with_one_period_of_interest() -> None:
    path = _path("bullet", [0.0] * _N, fee_rate=0.02)
    assert path["resolution"] == pytest.approx([0, 0, 0, 110.0, 0, 0, 0])
    assert path["interest"] == pytest.approx([0, 0, 0, 10.0, 0, 0, 0])
    assert path["outstanding"] == [None, None, None, 100.0, 0.0, 0.0, 0.0]
    assert path["senior_fee"] == pytest.approx([None, None, None, 2.0, 0.0, 0.0, 0.0])


def test_refinance_amortises_and_the_fee_follows_the_balance() -> None:
    # 2 years at 10% + 0%: annuity 57.619..., balances 100 -> 52.38... -> 0.
    path = _path("refinance", [0.0] * _N, fee_rate=0.01, tenor=2)
    annuity = 100.0 * 0.1 * 1.1**2 / (1.1**2 - 1.0)
    second = 100.0 * 1.1 - annuity
    assert path["resolution"][3:5] == pytest.approx([annuity, annuity])
    assert path["outstanding"][3:] == pytest.approx([100.0, second, 0.0, 0.0])
    assert path["interest"][3:5] == pytest.approx([10.0, second * 0.1])
    assert path["senior_fee"][3:] == pytest.approx([1.0, second * 0.01, 0.0, 0.0])


@pytest.mark.parametrize("treatment", ["legacy_ignore", "amortize"])
def test_treatments_without_a_stream_govern_no_period(treatment: str) -> None:
    path = _path(treatment, [50.0] * _N, fee_rate=0.02)
    assert all(v is None for v in path["outstanding"])
    assert all(v is None for v in path["senior_fee"])
    assert sum(path["resolution"]) == 0.0 and sum(path["interest"]) == 0.0


def _lender(treatment: Optional[str]) -> Dict[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides

    overrides = (
        {} if treatment is None else {"Financing_Terms.balloon_treatment": treatment}
    )
    return cast(
        Dict[str, Any],
        evaluate_with_overrides(
            "scenarios/dutchbay_lendercase_2025Q4.yaml",
            overrides=overrides,
            return_full_result=True,
        ),
    )


@pytest.mark.parametrize("treatment", [None, "cash_sweep", "bullet"])
def test_published_fee_is_charged_on_the_published_balance(
    treatment: Optional[str],
) -> None:
    """After maturity, fee == rate x opening outstanding, and the balance is the real one.

    The lender case carries a 1.75% guarantee + PRI fee and a USD 28.63M balloon, so
    every post-maturity period tests the overlay. Before #1504 the balance stayed at
    the balloon and the fee at USD 501,011 in every period to the horizon.
    """
    debt = _lender(treatment)["debt_result"]
    rate = debt["senior_fee_rate"]
    maturity = max(i for i, s in enumerate(debt["debt_service_total"]) if s > 1.0) + 1
    outstanding = debt["debt_outstanding"]
    fees = debt["senior_fee_usd"]
    assert outstanding[maturity] == pytest.approx(debt["balloon_remaining"], rel=1e-12)
    for p in range(maturity, len(outstanding)):
        assert fees[p] == pytest.approx(rate * outstanding[p], rel=1e-12, abs=1e-9)
        # The balance rolls forward: opening + interest - payment.
        if p + 1 < len(outstanding):
            rolled = (
                outstanding[p]
                + debt["balloon_interest"][p]
                - debt["balloon_resolution"][p]
            )
            assert outstanding[p + 1] == pytest.approx(rolled, rel=1e-9, abs=1e-6)
    if debt["balloon_residual"] == 0.0:
        assert outstanding[-1] == pytest.approx(0.0, abs=1.0)


def test_capitalising_sweep_still_ties_out_the_three_statements() -> None:
    """A sweep whose cash cannot cover the interest grows the debt, and the books tie."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.scenario_loader import load_scenario_config
    from analytics.three_statement import build_three_statement_from_run

    path = "scenarios/dutchbay_basecase_2025Q4.yaml"
    result = run_v14_pipeline(config=path, validation_mode="strict")
    debt = result["debt_result"]
    # The base case's post-maturity cash does not cover the interest, so it capitalises.
    assert debt["balloon_residual"] > debt["balloon_remaining"]
    statements = build_three_statement_from_run(result, load_scenario_config(path))
    assert statements is not None
    tie = statements.tie_outs
    assert tie.debt_retires_to_residual is True
    assert tie.balance_sheet_balances is True
    assert tie.cashflow_reconciles is True
