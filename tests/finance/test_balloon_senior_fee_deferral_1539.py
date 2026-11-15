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

from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from finance.debt_v14 import _balloon_resolution_path

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
