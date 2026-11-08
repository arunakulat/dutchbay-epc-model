"""Interest paid on the balloon after maturity is deducted in the levered tax pass (#1505).

The levered tax pass deducted ``interest_usd``, which is scheduled interest only, so the
interest paid on the balloon after maturity (inside ``balloon_resolution``) reduced no
taxable income, although the three-statement P&L books it as an expense. The project
owner decided the basis on 2026-11-01: balloon interest is deductible when it is PAID,
and the basis is a scenario input, ``tax.balloon_interest_tax_basis`` (``paid`` |
``accrued`` | ``none``), so a site whose tax law differs sets its own.

The engine oracles are hand-computed on a small schedule. The scenario checks tie the
deduction to the published series and pin ``none`` to the pre-#1505 canon.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.pipeline_v14_enhanced import (
    BALLOON_INTEREST_TAX_BASES,
    PipelineValidationError,
    _balloon_interest_tax_basis,
    _operating_interest_lkr_series,
)
from finance.debt_v14 import _balloon_resolution_path
from tests._canon import LENDER_EQUITY_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Three scheduled periods (index 0 construction, 1-2 service), maturity at period 3,
# then four post-maturity periods. Balloon 100 at 10%.
_DS = [0.0, 10.0, 10.0, 0.0, 0.0, 0.0, 0.0]
_N = len(_DS)

# The canonical lender-case equity IRR before #1505 (#1504's canon, tests/_canon.py at
# #1510). With the basis set to `none` the engine must reproduce it exactly: the only
# thing #1505 changes is which interest the levered tax pass deducts.
# Re-measured by #1577 (14 turbines, 2026-11-08): the `none` basis on the 14-turbine lender
# case is -26.73% (it was -26.44% on 15). The pin is the engine's output with the #1505
# deduction switched off, so it moves with the scenario, not with #1505.
_PRE_1505_LENDER_EQUITY_IRR = -0.26733287852795706


def _path(treatment: str, cfads: List[float], **kw: Any) -> Dict[str, Any]:
    return _balloon_resolution_path(
        treatment=treatment,
        balloon=100.0,
        cfads_ext=cfads,
        debt_service_total=_DS,
        construction_periods=1,
        timeline_periods=_N,
        avg_rate=0.10,
        refi_tenor_years=kw.get("tenor", 0),
        refi_rate_premium=kw.get("premium", 0.0),
        senior_fee_rate=0.0,
    )


# ── Engine: the interest a payment settles ──────────────────────────────────────


def test_sweep_that_pays_its_interest_settles_it_as_it_accrues() -> None:
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 60.0, 60.0, 60.0, 60.0])
    assert path["interest_paid"] == pytest.approx(path["interest"])


def test_sweep_settles_capitalised_interest_first_when_the_cash_arrives() -> None:
    # p3: opens 100, accrues 10, cash 4 -> settles 4, capitalises 6 (balance 106).
    # p4: opens 106, accrues 10.6, cash 4 -> settles 4 of the 16.6 owed (12.6 left).
    # p5: opens 112.6, accrues 11.26, cash 200 pays all 123.86 -> settles the 12.6
    #     capitalised and the period's 11.26, 23.86 of interest.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 4.0, 4.0, 200.0, 0.0])
    assert path["interest"] == pytest.approx([0, 0, 0, 10.0, 10.6, 11.26, 0])
    assert path["interest_paid"] == pytest.approx([0, 0, 0, 4.0, 4.0, 23.86, 0])
    assert path["residual"] == 0.0
    # Once the balloon clears, every unit of interest accrued has been paid.
    assert sum(path["interest_paid"]) == pytest.approx(sum(path["interest"]))


def test_sweep_that_never_clears_pays_only_interest_and_leaves_the_rest_unpaid() -> (
    None
):
    # Cash below the interest every period: all of it settles interest, none principal.
    path = _path("cash_sweep", [0.0, 0.0, 0.0, 4.0, 4.0, 4.0, 4.0])
    assert path["interest_paid"] == pytest.approx(path["resolution"])
    unpaid_interest = sum(path["interest"]) - sum(path["interest_paid"])
    # The residual is the original balloon plus the interest never paid.
    assert path["residual"] == pytest.approx(100.0 + unpaid_interest)


def test_bullet_and_refinance_pay_their_interest_as_it_accrues() -> None:
    bullet = _path("bullet", [0.0] * _N)
    assert bullet["interest_paid"] == pytest.approx(bullet["interest"])
    assert bullet["interest_paid"][3] == pytest.approx(10.0)
    refi = _path("refinance", [0.0] * _N, tenor=3, premium=0.02)
    assert refi["interest_paid"] == pytest.approx(refi["interest"])
    assert sum(refi["interest_paid"]) > 0.0


@pytest.mark.parametrize("treatment", ["legacy_ignore", "amortize"])
def test_treatments_without_a_stream_pay_no_balloon_interest(treatment: str) -> None:
    path = _path(treatment, [60.0] * _N)
    assert path["interest_paid"] == [0.0] * _N


# ── The basis input ─────────────────────────────────────────────────────────────


def test_basis_defaults_to_paid_and_reads_the_yaml_key() -> None:
    assert BALLOON_INTEREST_TAX_BASES == ("paid", "accrued", "none")
    assert _balloon_interest_tax_basis({"tax": {}}) == "paid"
    assert _balloon_interest_tax_basis({}) == "paid"
    for basis in BALLOON_INTEREST_TAX_BASES:
        cfg = {"tax": {"balloon_interest_tax_basis": basis.upper()}}
        assert _balloon_interest_tax_basis(cfg) == basis


def test_an_unknown_basis_fails_loud() -> None:
    with pytest.raises(PipelineValidationError, match="balloon_interest_tax_basis"):
        _balloon_interest_tax_basis({"tax": {"balloon_interest_tax_basis": "cash"}})


def test_each_basis_deducts_its_own_column() -> None:
    rows = [
        {
            "interest_usd": 5.0,
            "balloon_interest_accrued_usd": 3.0,
            "balloon_interest_paid_usd": 1.0,
            "fx_rate": 300.0,
        },
        {"interest_usd": 2.0, "fx_rate": 310.0},  # a row with no balloon columns
    ]
    assert _operating_interest_lkr_series(rows, balloon_basis="paid") == [
        pytest.approx(6.0 * 300.0),
        pytest.approx(2.0 * 310.0),
    ]
    assert _operating_interest_lkr_series(rows, balloon_basis="accrued") == [
        pytest.approx(8.0 * 300.0),
        pytest.approx(2.0 * 310.0),
    ]
    assert _operating_interest_lkr_series(rows, balloon_basis="none") == [
        pytest.approx(5.0 * 300.0),
        pytest.approx(2.0 * 310.0),
    ]


# ── The lender case (refinance) ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def lender_runs() -> Dict[str, Dict[str, Any]]:
    return {
        basis: evaluate_with_overrides(
            LENDER,
            overrides={"tax.balloon_interest_tax_basis": basis},
            return_full_result=True,
        )
        for basis in ("paid", "none")
    }


def test_rows_carry_the_balloon_interest_the_engine_published(
    lender_runs: Dict[str, Dict[str, Any]],
) -> None:
    full = lender_runs["paid"]
    debt = full["debt_result"]
    rows = full["annual_rows"]
    paid_total = sum(float(v or 0.0) for v in debt["balloon_interest_paid"])
    # The refinance pays its interest as it accrues, and there is some to pay.
    assert paid_total > 1_000_000.0
    assert debt["balloon_interest_paid"] == pytest.approx(debt["balloon_interest"])
    # Every period of it lands on an operating row through the period map.
    assert sum(r["balloon_interest_paid_usd"] for r in rows) == pytest.approx(
        paid_total
    )


def test_none_reproduces_the_pre_1505_canon(
    lender_runs: Dict[str, Dict[str, Any]],
) -> None:
    eq_irr = lender_runs["none"]["kpis"]["equity_irr"]
    assert eq_irr == pytest.approx(_PRE_1505_LENDER_EQUITY_IRR, abs=1e-12)


def test_paid_is_the_canon_and_lowers_the_tax_equity_bears(
    lender_runs: Dict[str, Dict[str, Any]],
) -> None:
    paid, none = lender_runs["paid"], lender_runs["none"]
    # The default basis is the canon (tests/_canon.py).
    assert paid["kpis"]["equity_irr"] == pytest.approx(LENDER_EQUITY_IRR, abs=1e-12)
    assert paid["kpis"]["equity_irr"] > none["kpis"]["equity_irr"]


def test_the_basis_reaches_the_sizing_pass(
    lender_runs: Dict[str, Dict[str, Any]],
) -> None:
    # The levered-tax CFADS the facility is covenanted on rises in the years the
    # balloon interest is paid, and nowhere falls.
    rows_paid = lender_runs["paid"]["annual_rows"]
    rows_none = lender_runs["none"]["annual_rows"]
    deltas = [
        float(p["cfads_coverage_usd"]) - float(n["cfads_coverage_usd"])
        for p, n in zip(rows_paid, rows_none, strict=True)
    ]
    assert min(deltas) >= -1e-6
    assert max(deltas) > 0.0


def test_interest_deductibility_off_switches_the_balloon_deduction_off_too() -> None:
    off_paid = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.interest_deductibility": False,
            "tax.balloon_interest_tax_basis": "paid",
        },
    )
    off_none = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.interest_deductibility": False,
            "tax.balloon_interest_tax_basis": "none",
        },
    )
    assert off_paid["equity_irr"] == pytest.approx(off_none["equity_irr"], abs=1e-12)


# ── WHT gross-up on the interest paid ───────────────────────────────────────────


def test_wht_gross_up_charges_the_balloon_interest_paid() -> None:
    rate = 0.10
    full = evaluate_with_overrides(
        LENDER,
        overrides={
            "tax.wht_on_interest_to_nonresidents": rate,
            "tax.wht_gross_up": True,
        },
        return_full_result=True,
    )
    rows = full["annual_rows"]
    dist = full["equity_distribution"]["annual_distributions"]
    balloon_years = [r for r in rows if float(r["balloon_interest_paid_usd"]) > 0.0]
    assert balloon_years, "the lender case pays balloon interest after maturity"
    for row, d in zip(rows, dist, strict=True):
        expected = (
            float(row["interest_usd"]) + float(row["balloon_interest_paid_usd"])
        ) * rate
        assert d["wht_on_interest_usd"] == pytest.approx(expected, abs=1.0)
