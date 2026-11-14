"""#1539: the WHT gross-up is charged on balloon interest PAID, not interest accrued.

#1526 made the grossed-up interest WHT in ``finance/equity_distribution_v14_hydra.py``
include ``balloon_interest_paid_usd``. Its assurance lane (A-4) found no test that tells
paid from accrued: the existing WHT test runs the refinance lender case, where the two
are equal in every year, so a mutant that reads ``balloon_interest_accrued_usd`` (M13)
survives.

This test runs a capitalising ``cash_sweep`` case, the base case, where post-maturity
cash does not cover the balloon interest, so interest paid is below interest accrued.
WHT arises on payment, so the charge must follow the paid column. No committed scenario
enables ``wht_gross_up``; the override turns it on for this test only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = str(REPO_ROOT / "scenarios" / "dutchbay_basecase_2025Q4.yaml")
RATE = 0.10

# The gap between the two candidate bases must dwarf the comparison tolerance, or the
# test could not tell them apart. USD 1 is the tolerance; the gap required is 1,000x.
TOLERANCE_USD = 1.0
MIN_GAP_USD = 1_000.0 * TOLERANCE_USD


@pytest.fixture(scope="module")
def run() -> Dict[str, Any]:
    full = evaluate_with_overrides(
        BASE,
        overrides={
            "debt.balloon_treatment": "cash_sweep",
            "tax.wht_on_interest_to_nonresidents": RATE,
            "tax.wht_gross_up": True,
        },
        return_full_result=True,
    )
    assert isinstance(full, dict)
    return full


def _column(rows: List[Dict[str, Any]], key: str) -> List[float]:
    return [float(r.get(key) or 0.0) for r in rows]


def test_the_case_capitalises_so_paid_and_accrued_differ(run: Dict[str, Any]) -> None:
    """Precondition: without a paid/accrued gap this case could not catch M13."""
    rows = run["annual_rows"]
    paid = _column(rows, "balloon_interest_paid_usd")
    accrued = _column(rows, "balloon_interest_accrued_usd")
    gaps = [a - p for p, a in zip(paid, accrued, strict=True)]
    # A capitalising sweep never pays more than has accrued plus earlier capitalised
    # interest, and here it pays less in at least one year by far more than the tolerance.
    assert max(gaps) * RATE > MIN_GAP_USD


def test_wht_gross_up_follows_interest_paid(run: Dict[str, Any]) -> None:
    rows = run["annual_rows"]
    dist = run["equity_distribution"]["annual_distributions"]
    assert len(rows) == len(dist)
    for row, d in zip(rows, dist, strict=True):
        paid_base = float(row["interest_usd"]) + float(
            row.get("balloon_interest_paid_usd") or 0.0
        )
        assert d["wht_on_interest_usd"] == pytest.approx(
            paid_base * RATE, abs=TOLERANCE_USD
        )


def test_wht_gross_up_does_not_follow_interest_accrued(run: Dict[str, Any]) -> None:
    """The M13 mutant's base must be rejected in every year where the two differ."""
    rows = run["annual_rows"]
    dist = run["equity_distribution"]["annual_distributions"]
    distinguishing = 0
    for row, d in zip(rows, dist, strict=True):
        paid = float(row.get("balloon_interest_paid_usd") or 0.0)
        accrued = float(row.get("balloon_interest_accrued_usd") or 0.0)
        if abs(accrued - paid) * RATE <= MIN_GAP_USD:
            continue
        distinguishing += 1
        accrued_base = (float(row["interest_usd"]) + accrued) * RATE
        assert abs(d["wht_on_interest_usd"] - accrued_base) > MIN_GAP_USD
    assert distinguishing >= 1
