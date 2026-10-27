"""#1397 (audit P2-F4-01): debt is sized, and coverage reported, on levered-tax CFADS.

Before this, ``run_v14_pipeline`` built its sizing rows with ``interest_expense=0`` and
handed those to ``plan_debt``, so the facility was sculpted against -- and DSCR, LLCR and
PLCR reported from -- CFADS bearing tax the SPV does not pay. Over the lender case's 20
operating rows the SPV incurs LKR 39.38bn of interest that was deducted nowhere in that
pass; on a like-for-like basis that is USD 16.44M of CFADS (USD 175.55M unlevered against
USD 191.99M levered, both pre-fee, measured at this head).

A DSCR is a cash-coverage ratio with no WACC in it, so there is nothing for the interest
shield to double count against. The double-count argument holds for project NPV and
project IRR against an after-tax WACC, where the shield already sits inside the cost of
debt, and those keep their unlevered basis -- which is what
:func:`test_the_project_pass_keeps_its_unlevered_basis` pins.

**The interest is the only input this change touches.** The sizing rows carry no senior
credit-support fee, exactly as before #1397, so a scenario with
``tax.interest_deductibility`` off is byte-identical to the pre-change engine. That is
pinned by :func:`test_deductibility_off_reproduces_the_pre_change_sizing_exactly`, and it
is what makes the KPI delta in ``tests/_canon.py`` attributable to the tax basis alone.

The oracle in :func:`test_levered_cfads_uplift_equals_the_rate_times_deductible_interest`
is independent of the tax engine: it computes the expected CFADS uplift as the statutory
rate times the deductible interest, net of the risk haircut, from the scenario's own
``corporate_tax_rate`` and the debt schedule's interest, and never reads the engine's tax
output on the expectation side.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.pipeline_v14_enhanced import (
    _CFADS_FIXED_POINT_MAX_ITERATIONS,
    PipelineValidationError,
    _operating_interest_lkr_series,
    _senior_fee_lkr_series,
    _size_debt_on_levered_cfads,
    run_v14_pipeline,
)
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def lender_config() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(str(LENDER))))


@pytest.fixture(scope="module")
def lender_run() -> Dict[str, Any]:
    return run_v14_pipeline(config=str(LENDER), validation_mode="strict")


def _size(cfg: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]], int]:
    return _size_debt_on_levered_cfads(
        cfg, build_annual_rows=build_annual_rows, forbid_toy_fallback=False
    )


def test_levered_cfads_uplift_equals_the_rate_times_deductible_interest(
    lender_config: Dict[str, Any],
) -> None:
    """Closed-form oracle, computed without reading the engine's tax output.

    ``calculate_tax`` deducts interest from taxable income, so where taxable income stays
    positive on BOTH bases the whole deduction converts at the statutory rate and the
    post-tax uplift is exactly ``rate x interest``. The risk haircut then scales what
    survives into ``cfads_final_lkr``, so the oracle on the reported series is
    ``rate x interest x (1 - risk_haircut_pct)``. That factor is linear only on the
    haircut's non-negative branch (``_apply_risk_haircut`` makes a *negative* CFADS more
    negative, by ``1 + h``), so years that are post-tax negative on either basis are
    excluded along with the non-positive taxable-income years, where the deduction is
    clamped at zero or banked as a carried-forward loss instead of converting this year.

    Both sides are built WITHOUT the senior fee, which is how the sizing pass builds and
    what keeps the comparison a comparison of the tax basis alone.

    Measured at the lender case's operating year 6: tax saved is exactly 30% of the
    interest, the haircut is 10%, and the uplift in the reported CFADS is 90% of the tax
    saved. Withholding tax on that interest is reported on the row but does not reduce
    CFADS, so it is correctly absent here.
    """
    # Loss carry-forward off, so the deduction converts in its own year instead of
    # displacing a banked vintage into a later one. With it on, the lender case's
    # five-year plant depreciation banks losses that the interest deduction then
    # reshuffles across years -- measured at 27% rather than 30% in operating year 12 --
    # which is the loss machinery working correctly, not the shield being mispriced.
    cfg = copy.deepcopy(lender_config)
    cfg["tax"] = dict(cfg["tax"])
    cfg["tax"]["loss_carryforward_years"] = 0

    rate = float(cfg["tax"]["corporate_tax_rate"])
    assert rate > 0.0, "the oracle is vacuous at a zero tax rate"

    _, sizing_rows, _ = _size(cfg)
    interest_lkr = _operating_interest_lkr_series(sizing_rows)
    unlevered = build_annual_rows(cfg)

    checked = 0
    for levered_row, unlevered_row, interest in zip(
        sizing_rows, unlevered, interest_lkr, strict=True
    ):
        if levered_row.get("tax_holiday_applied") or unlevered_row.get(
            "tax_holiday_applied"
        ):
            continue
        if (
            float(levered_row["taxable_income_lkr"]) <= 0.0
            or float(unlevered_row["taxable_income_lkr"]) <= 0.0
        ):
            continue
        if (
            float(levered_row["posttax_cfads_lkr"]) < 0.0
            or float(unlevered_row["posttax_cfads_lkr"]) < 0.0
        ):
            continue
        haircut = float(levered_row["risk_haircut_pct"])
        assert haircut == float(unlevered_row["risk_haircut_pct"]), (
            f"year {levered_row['year']}: the two bases carry different risk haircuts, "
            "so the closed form below does not apply"
        )
        uplift = float(levered_row["cfads_final_lkr"]) - float(
            unlevered_row["cfads_final_lkr"]
        )
        expected = rate * interest * (1.0 - haircut)
        assert uplift == pytest.approx(expected, rel=1e-9), (
            f"year {levered_row['year']}: CFADS uplift {uplift:,.2f} is not the "
            f"statutory {rate:.0%} of LKR {interest:,.2f} of deductible interest "
            f"net of the {haircut:.0%} risk haircut"
        )
        checked += 1

    assert checked >= 5, (
        f"only {checked} fully-taxable operating year(s) exercised the oracle; the "
        "assertion above would pass vacuously on a schedule this thin"
    )


def test_the_sizing_pass_bears_the_real_interest_and_the_project_pass_does_not(
    lender_config: Dict[str, Any], lender_run: Dict[str, Any]
) -> None:
    """The sizing basis and the pre-#1397 basis differ in the tax basis and nothing else.

    The published rows are the PROJECT pass, so their ``interest_expense_lkr`` is 0.0 --
    that is the basis project NPV and project IRR need. Comparing the sizing rows against
    a plain unlevered build (also fee-free) isolates the shield: both carry the same fee
    treatment, so the whole difference is the interest deduction.
    """
    rows = lender_run["annual_rows"]
    assert rows, "the lender case produced no operating rows"
    assert all(float(r.get("interest_expense_lkr") or 0.0) == 0.0 for r in rows)

    incurred = sum(
        float(r.get("interest_usd") or 0.0) * float(r.get("fx_rate") or 0.0)
        for r in rows
    )
    assert incurred > 0.0, "a case with no debt interest cannot exercise this"

    _, sizing_rows, _ = _size(lender_config)
    coverage_total = sum(float(r["cfads_usd"]) for r in sizing_rows)
    unlevered_total = sum(
        float(r.get("cfads_usd") or 0.0) for r in build_annual_rows(lender_config)
    )
    assert coverage_total > unlevered_total


def test_every_row_publishes_both_cfads_bases(lender_run: Dict[str, Any]) -> None:
    """A reader can see which CFADS carries which claim instead of inferring it."""
    for row in lender_run["annual_rows"]:
        assert "cfads_usd" in row
        assert "cfads_coverage_usd" in row
        assert isinstance(row["cfads_coverage_usd"], float)


def test_the_project_pass_keeps_its_unlevered_basis(
    lender_config: Dict[str, Any], lender_run: Dict[str, Any]
) -> None:
    """Project NPV/IRR read CFADS that excludes the interest shield.

    ``analytics.core.metrics`` derives project NPV and IRR from the rows' ``cfads_usd``,
    and compares them against an after-tax WACC whose cost of debt already carries the
    shield. Deducting interest here as well would double count it. The published rows
    must therefore equal a plain unlevered build carrying the senior fee of the sized
    facility -- which is how the pre-#1397 code built them, from its own sized facility.
    """
    debt_result, sizing_rows, _ = _size(lender_config)
    fee_lkr = _senior_fee_lkr_series(debt_result, sizing_rows)
    expected = build_annual_rows(lender_config, senior_fee_lkr_series=fee_lkr)

    published = lender_run["annual_rows"]
    assert len(published) == len(expected)
    for got, want in zip(published, expected, strict=True):
        assert float(got["cfads_usd"]) == pytest.approx(
            float(want["cfads_usd"]), rel=1e-12
        )


def test_the_fixed_point_converges_on_the_lender_case(
    lender_config: Dict[str, Any],
) -> None:
    """It settles, and well inside the ceiling rather than against it."""
    _, _, iterations = _size(lender_config)
    assert 1 < iterations < _CFADS_FIXED_POINT_MAX_ITERATIONS


def test_the_fixed_point_refuses_a_schedule_it_has_not_settled(
    lender_config: Dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """CESSPIT: an unsettled schedule is a failure, never a truncated last pass.

    Negative control for the ceiling. With one iteration allowed the loop cannot reach
    its own convergence test, and it must raise rather than return whatever the first
    pass held -- which is exactly the unlevered answer this change exists to replace.
    """
    monkeypatch.setattr(
        "analytics.pipeline_v14_enhanced._CFADS_FIXED_POINT_MAX_ITERATIONS", 1
    )
    with pytest.raises(PipelineValidationError, match="did not converge"):
        _size(lender_config)


def test_deductibility_off_reproduces_the_pre_change_sizing_exactly(
    lender_config: Dict[str, Any],
) -> None:
    """The one configuration this change must leave byte-identical, pinned as such.

    The pre-#1397 code deducted no interest anywhere, so a scenario that says interest is
    not deductible must size exactly as it did before: ``plan_debt`` over a plain
    ``build_annual_rows``. This is the oracle that proves the change is confined to the
    tax basis -- if the senior fee, the row set or the sizing order had moved as well,
    this would fail even with the shield switched off.
    """
    cfg = copy.deepcopy(lender_config)
    cfg["tax"] = dict(cfg["tax"])
    cfg["tax"]["interest_deductibility"] = False

    debt_result, sizing_rows, iterations = _size(cfg)
    assert iterations == 1
    assert all(float(r.get("interest_expense_lkr") or 0.0) == 0.0 for r in sizing_rows)

    pre_change = plan_debt(
        annual_rows=build_annual_rows(cfg), config=cfg, forbid_toy_fallback=False
    )
    for key in ("debt_total", "balloon_remaining", "balloon_pct", "min_dscr"):
        assert float(debt_result[key]) == float(pre_change[key]), key
    assert [None if x is None else float(x) for x in debt_result["dscr_series"]] == [
        None if x is None else float(x) for x in pre_change["dscr_series"]
    ]


def test_the_senior_fee_never_enters_the_sizing_pass(
    lender_config: Dict[str, Any],
) -> None:
    """The fee stays where it was: derived from the sized facility, used in reporting.

    Pinning this is the control on a 2-cycle. Feeding each pass's fee back into the next
    row build makes ``debt_total`` alternate between two adjacent 0.0025 gearing steps
    and never settle, so folding the fee into this loop is not available as a shortcut
    for RS-A8 ("debt sized on pre-fee unlevered rows, reported on rebuilt rows"). Sizing
    on pre-fee rows does overstate capacity; that is RS-A8's finding, left untouched here
    so this change's KPI delta stays attributable to the tax basis.
    """
    debt_result, sizing_rows, _ = _size(lender_config)
    assert all(float(r.get("senior_fee_lkr") or 0.0) == 0.0 for r in sizing_rows)

    fee = _senior_fee_lkr_series(debt_result, sizing_rows)
    assert fee is not None, "the lender case declares credit-support fees"
    assert any(value > 0.0 for value in fee), "a zero fee cannot exercise this"
