"""Contract tests for the sub-period coverage view (:mod:`finance.subperiod_coverage_v14`).

A3 dolphin (c) of #1395: debt service, coverage CFADS and DSCR on one sub-period index.
The owner chose a quarterly view with the headline unchanged (2026-10-31). Five
properties carry the weight here:

1. It ties to the annual engine. On the live lender case every operating year's quarters
   re-aggregate to the debt engine's own CFADS, fee and service, and the re-aggregated
   coverage reproduces ``dscr_by_year`` for every year, the bridge-folded year 1
   included.
2. It moves nothing. The debt result is not mutated and the headline ``min_dscr`` is
   untouched; the view's own minimum is a separate, labelled field.
3. The arithmetic is right where it can be worked by hand. An even spread over a year
   with no events gives every quarter the annual DSCR; declared instalment periods carry
   the service and leave the other quarters with no ratio; the bridge lands in year 1
   alone; a lumpy tax quarter shows its dip.
4. It divides the right CFADS. Project-basis rows, and rows that do not match the debt
   result one to one, are refused.
5. Assumptions are flagged. An even spread used in place of a declared date is recorded
   and warned, and every figure carries the F-5 bar.
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any, Dict, List, Tuple

import pytest

from analytics.pipeline_v14_enhanced import _size_debt_on_levered_cfads
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.event_calendar_v14 import (
    DEFAULT_EVENT_PERIODS,
    EVENT_KINDS,
    EventCalendar,
    resolve_event_calendar,
)
from finance.period_grid_v14 import PeriodGrid
from finance.subannual_rows_v14 import RECONCILIATION_ULP_TOLERANCE
from finance.subperiod_coverage_v14 import (
    COVENANT_USE,
    DEBT_ENRICHMENT_KEYS,
    build_subperiod_coverage,
)

QUARTERLY = PeriodGrid(resolution="quarterly", periods_per_year=4)
LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"

#: Every placement declared, so nothing is assumed: CFADS items on A2's profile and the
#: debt cash evenly over the year, written out.
ALL_EVEN = {
    "tax": "profile",
    "bess_augmentation_capex": "profile",
    "debt_service": {"periods": [1, 2, 3, 4]},
    "bridge_service": {"periods": [1, 2, 3, 4]},
}

_LOGGER = "finance.subperiod_coverage_v14"


def _calendar(entries: Dict[str, Any]) -> EventCalendar:
    calendar = resolve_event_calendar(
        {"cashflow": {"resolution": "quarterly", "event_calendar": entries}}, QUARTERLY
    )
    assert calendar is not None
    return calendar


@pytest.fixture(scope="module")
def lender_config() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(LENDER_CASE)))


@pytest.fixture(scope="module")
def sized_lender(
    lender_config: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    debt_result, sizing_rows, _ = _size_debt_on_levered_cfads(
        copy.deepcopy(lender_config),
        build_annual_rows=build_annual_rows,
        forbid_toy_fallback=False,
    )
    return debt_result, sizing_rows


def _synthetic_debt(
    rows: List[Dict[str, Any]], service: float, interest: float, bridge: float = 0.0
) -> Dict[str, Any]:
    """A flat debt result over ``rows``: period 0 is a bridge, period k+1 is year k+1."""
    return {
        "annual_row_debt_period_map": [
            {
                "annual_row_index": index,
                "year": float(index + 1),
                "debt_period": index + 1,
                "cfads_usd": float(row["cfads_usd"]),
            }
            for index, row in enumerate(rows)
        ],
        "debt_service_total": [bridge] + [service] * len(rows),
        "interest_total": [bridge / 2.0] + [interest] * len(rows),
        "senior_fee_usd": [0.0] * (len(rows) + 1),
        "cfads_bridge_debt_period": 0 if bridge else None,
    }


def _within_ulp(got: float, want: float, ulps: float = RECONCILIATION_ULP_TOLERANCE):
    return abs(got - want) <= ulps * math.ulp(want)


def _year(view: Any, year_index: int) -> List[Dict[str, Any]]:
    return list(view.periods[year_index * 4 : (year_index + 1) * 4])


# ---------------------------------------------------------------------------
# It ties to the annual engine
# ---------------------------------------------------------------------------


def test_lender_quarters_reaggregate_to_the_debt_engine_and_dscr_by_year(
    sized_lender,
) -> None:
    debt, rows = sized_lender
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    mapping = debt["annual_row_debt_period_map"]
    bridge = int(debt["cfads_bridge_debt_period"])
    bridge_service = float(debt["debt_service_total"][bridge])
    assert bridge_service > 0.0, "the lender case folds a bridge into year 1"
    assert len(view.periods) == 4 * len(mapping)

    for year_index, entry in enumerate(mapping):
        quarters = _year(view, year_index)
        period = int(entry["debt_period"])
        scheduled = math.fsum(q["scheduled_service_usd"] for q in quarters)
        assert _within_ulp(scheduled, float(debt["debt_service_total"][period]))
        fee = math.fsum(q["senior_fee_usd"] for q in quarters)
        assert _within_ulp(fee, float(debt["senior_fee_usd"][period]))
        cfads = math.fsum(q["cfads_usd"] for q in quarters)
        assert _within_ulp(cfads, float(entry["cfads_usd"]))
        bridged = math.fsum(q["bridge_service_usd"] for q in quarters)
        assert (
            _within_ulp(bridged, bridge_service) if year_index == 0 else bridged == 0.0
        )

        want = debt["dscr_by_year"][entry["year"]]
        service = math.fsum(q["debt_service_usd"] for q in quarters)
        if service == 0.0:
            # After the tenor: no service, so neither table carries a ratio.
            assert want is None and all(q["dscr"] is None for q in quarters)
            continue
        got = (cfads - fee) / service
        assert math.isclose(got, want, rel_tol=1e-14), (year_index, got, want)
    assert any(q["dscr"] is None for q in view.periods), "the tail is past the tenor"


def test_the_folded_year_one_is_the_headline_and_the_quarters_carry_it(
    sized_lender,
) -> None:
    """Even debt cash and profile CFADS give each year-1 quarter the folded ratio."""
    debt, rows = sized_lender
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    folded = debt["dscr_by_year"][debt["annual_row_debt_period_map"][0]["year"]]
    assert folded == debt["min_dscr"], "year 1's fold sets the lender headline"
    for quarter in _year(view, 0):
        assert math.isclose(quarter["dscr"], folded, rel_tol=1e-14)


def test_interest_and_principal_split_each_quarters_service(sized_lender) -> None:
    debt, rows = sized_lender
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    for quarter in view.periods:
        assert (
            quarter["interest_usd"] + quarter["principal_usd"]
            == quarter["debt_service_usd"]
        )
        assert (
            quarter["debt_service_usd"]
            == quarter["scheduled_service_usd"] + quarter["bridge_service_usd"]
        )
    interest = math.fsum(q["interest_usd"] for q in _year(view, 1))
    period = int(debt["annual_row_debt_period_map"][1]["debt_period"])
    assert _within_ulp(interest, float(debt["interest_total"][period]))


# ---------------------------------------------------------------------------
# It moves nothing
# ---------------------------------------------------------------------------


def test_the_debt_result_and_headline_are_untouched(sized_lender) -> None:
    debt, rows = sized_lender
    before_debt = copy.deepcopy(debt)
    before_rows = copy.deepcopy(rows)
    view = build_subperiod_coverage(rows, debt, _calendar({}))
    assert debt == before_debt
    assert rows == before_rows
    assert view.min_dscr is not None and view.min_dscr != debt["min_dscr"]


# ---------------------------------------------------------------------------
# Worked by hand
# ---------------------------------------------------------------------------


def test_an_eventless_even_year_gives_every_quarter_the_annual_dscr(
    sized_lender,
) -> None:
    _, rows = sized_lender
    no_tax_year = next(i for i, row in enumerate(rows) if float(row["tax_lkr"]) == 0.0)
    service = float(rows[no_tax_year]["cfads_usd"]) / 1.25
    debt = _synthetic_debt(rows, service=service, interest=service / 3.0)
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    for quarter in _year(view, no_tax_year):
        assert math.isclose(quarter["dscr"], 1.25, rel_tol=1e-14)
        assert quarter["bridge_service_usd"] == 0.0


def test_declared_instalments_carry_the_service_and_leave_gaps(sized_lender) -> None:
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=400_000.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": [2, 4]}})
    )
    q1, q2, q3, q4 = _year(view, 3)
    assert q1["debt_service_usd"] == q3["debt_service_usd"] == 0.0
    assert q1["dscr"] is None and q3["dscr"] is None
    assert q2["debt_service_usd"] == q4["debt_service_usd"] == 500_000.0
    assert q2["interest_usd"] == 200_000.0
    assert q2["dscr"] == q2["cfads_usd"] / 500_000.0
    assert view.min_dscr == min(p["dscr"] for p in view.periods if p["dscr"])


def test_the_bridge_lands_in_year_one_on_its_declared_quarter(sized_lender) -> None:
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=0.0, bridge=600_000.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "bridge_service": {"periods": [1]}})
    )
    q1, q2, q3, q4 = _year(view, 0)
    assert q1["bridge_service_usd"] == 600_000.0
    assert q1["debt_service_usd"] == 850_000.0
    assert q1["interest_usd"] == 300_000.0
    assert q2["bridge_service_usd"] == q3["bridge_service_usd"] == 0.0
    assert q4["bridge_service_usd"] == 0.0
    assert all(q["bridge_service_usd"] == 0.0 for q in view.periods[4:])


def test_a_bridge_that_maps_to_an_operating_row_is_not_folded(sized_lender) -> None:
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=0.0, bridge=600_000.0)
    debt["cfads_bridge_debt_period"] = 1  # year 1's own period: nothing orphaned
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    assert all(q["bridge_service_usd"] == 0.0 for q in view.periods)


def test_a_year_end_tax_payment_shows_its_dip(sized_lender) -> None:
    """Tax on its default date (the year's last quarter) lowers that quarter's DSCR.

    The lender case pays no tax until its holiday ends, so the first tax year's Q4 bears
    the whole year's payment. Spread on the profile instead, the dip disappears.
    """
    debt, rows = sized_lender
    first_tax = next(i for i, row in enumerate(rows) if float(row["tax_lkr"]) > 0.0)
    calendar = _calendar(
        {key: ALL_EVEN[key] for key in ("debt_service", "bridge_service")}
    )
    assert calendar.assumed == frozenset(DEFAULT_EVENT_PERIODS)
    dated = build_subperiod_coverage(rows, debt, calendar)
    spread = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))

    q1, q2, q3, q4 = _year(dated, first_tax)
    annual = debt["dscr_by_year"][debt["annual_row_debt_period_map"][first_tax]["year"]]
    assert q4["dscr"] < annual < q1["dscr"]
    assert q1["dscr"] == q2["dscr"] == q3["dscr"]
    assert dated.min_dscr is not None and spread.min_dscr is not None
    assert dated.min_dscr < spread.min_dscr
    assert math.isclose(spread.min_dscr, debt["min_dscr"], rel_tol=1e-14)


# ---------------------------------------------------------------------------
# It divides the right CFADS
# ---------------------------------------------------------------------------


def test_project_basis_rows_are_refused(sized_lender, lender_config) -> None:
    debt, _ = sized_lender
    project_rows = build_annual_rows(copy.deepcopy(lender_config))
    with pytest.raises(ValueError, match="coverage \\(sizing\\) rows"):
        build_subperiod_coverage(project_rows, debt, _calendar(ALL_EVEN))


def test_a_row_count_that_does_not_match_the_debt_result_is_refused(
    sized_lender,
) -> None:
    debt, rows = sized_lender
    with pytest.raises(ValueError, match="maps 20 operating years"):
        build_subperiod_coverage(rows[:-1], debt, _calendar(ALL_EVEN))


def test_the_sizing_rows_carry_exactly_the_stripped_enrichment_keys(
    sized_lender,
) -> None:
    """If enrichment stops adding a key, the strip list is stale; if it adds a new one,
    A2 refuses it as unclassified and the live tests above fail loud."""
    _, rows = sized_lender
    assert DEBT_ENRICHMENT_KEYS <= set(rows[0])


# ---------------------------------------------------------------------------
# Assumptions are flagged
# ---------------------------------------------------------------------------


def test_even_debt_cash_is_recorded_and_warned_as_assumed(sized_lender, caplog) -> None:
    debt, rows = sized_lender
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        view = build_subperiod_coverage(
            rows,
            debt,
            _calendar({"tax": "profile", "bess_augmentation_capex": "profile"}),
        )
    assert set(view.assumptions) == {"debt_service", "bridge_service"}
    assert "ASSUMED" in caplog.text and "#920" in caplog.text and "F-5" in caplog.text


def test_declared_debt_cash_assumes_nothing_and_warns_nothing(
    sized_lender, caplog
) -> None:
    debt, rows = sized_lender
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    assert view.assumptions == {}
    assert caplog.text == ""


def test_no_bridge_means_no_bridge_assumption(sized_lender) -> None:
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=0.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({"tax": "profile", "bess_augmentation_capex": "profile"})
    )
    assert set(view.assumptions) == {"debt_service"}


def test_every_view_carries_the_f5_bar(sized_lender) -> None:
    debt, rows = sized_lender
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    assert view.covenant_use == COVENANT_USE
    assert "F-5" in COVENANT_USE and "covenant" in COVENANT_USE


def test_debt_service_is_a_calendar_kind_without_a_default_date() -> None:
    assert EVENT_KINDS["debt_service"] is None
    assert "debt_service" not in DEFAULT_EVENT_PERIODS
    calendar = _calendar({"debt_service": {"periods": [2, 4]}})
    assert calendar.placements["debt_service"] == (0.0, 0.5, 0.0, 0.5)
    assert "debt_service" not in calendar.assumed
    assert "debt_service" not in _calendar({}).placements
