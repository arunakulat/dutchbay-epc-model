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
   the service, leave the other quarters with no ratio, and cover each instalment over
   its calculation period, so flat CFADS gives every instalment the annual DSCR; the
   bridge lands in year 1 alone; a lumpy tax quarter shows its dip. A quarter the
   placement gives zero weight is never an instalment, whatever the float residual.
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
from finance.subannual_rows_v14 import RECONCILIATION_ULP_TOLERANCE, allocate_flow
from finance.subperiod_coverage_v14 import (
    COVENANT_USE,
    DEBT_ENRICHMENT_KEYS,
    _allocate_on_placement,
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
        "balloon_interest_paid": [0.0] * (len(rows) + 1),
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


def _carried_balloon_years(debt: Dict[str, Any]) -> List[Tuple[int, float]]:
    """(year index, interest paid on the carried balloon) for each year that pays some."""
    paid = debt["balloon_interest_paid"]
    carried = []
    for index, entry in enumerate(debt["annual_row_debt_period_map"]):
        period = int(entry["debt_period"])
        value = float(paid[period]) if period < len(paid) else 0.0
        if value > 0.0:
            carried.append((index, value))
    return carried


def test_balloon_interest_after_the_tenor_is_shown_outside_the_dscr(
    sized_lender,
) -> None:
    """A carried balloon's interest is debt cash with no ratio, as in ``dscr_by_year``.

    It is read from the debt result, so rows passed without the pipeline's enrichment
    keys (which the view accepts) still show it.
    """
    debt, rows = sized_lender
    bare_rows = [
        {key: value for key, value in row.items() if key not in DEBT_ENRICHMENT_KEYS}
        for row in rows
    ]
    carried = _carried_balloon_years(debt)
    assert carried, "the lender case carries its balloon past the tenor"
    for given in (rows, bare_rows):
        view = build_subperiod_coverage(given, debt, _calendar(ALL_EVEN))
        for year_index, want in carried:
            assert want == float(rows[year_index]["balloon_interest_paid_usd"])
            quarters = _year(view, year_index)
            got = math.fsum(q["balloon_interest_paid_usd"] for q in quarters)
            assert _within_ulp(got, want)
            assert all(q["debt_service_usd"] == 0.0 for q in quarters)
            assert all(q["dscr"] is None for q in quarters)
            year = debt["annual_row_debt_period_map"][year_index]["year"]
            assert debt["dscr_by_year"][year] is None
        others = [i for i in range(len(rows)) if i not in dict(carried)]
        assert all(
            q["balloon_interest_paid_usd"] == 0.0
            for i in others
            for q in _year(view, i)
        )
    total = math.fsum(p["balloon_interest_paid_usd"] for p in view.periods)
    assert total > 0.0


def test_balloon_interest_follows_the_declared_instalment_dates(sized_lender) -> None:
    debt, rows = sized_lender
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": [2, 4]}})
    )
    for year_index, want in _carried_balloon_years(debt):
        q1, q2, q3, q4 = _year(view, year_index)
        assert q1["balloon_interest_paid_usd"] == q3["balloon_interest_paid_usd"] == 0.0
        assert q2["balloon_interest_paid_usd"] == want / 2.0
        assert _within_ulp(
            q2["balloon_interest_paid_usd"] + q4["balloon_interest_paid_usd"], want
        )


def test_a_debt_result_without_balloon_interest_is_refused(sized_lender) -> None:
    debt, rows = sized_lender
    stripped = {k: v for k, v in debt.items() if k != "balloon_interest_paid"}
    with pytest.raises(ValueError, match="balloon_interest_paid"):
        build_subperiod_coverage(rows, stripped, _calendar(ALL_EVEN))


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
    assert view.min_subperiod_dscr is not None
    assert view.min_subperiod_dscr != debt["min_dscr"]
    # Named apart from the headline so a consumer cannot read one for the other.
    assert not hasattr(view, "min_dscr")


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
    """Each instalment is covered by the cash since the previous one, not one quarter's."""
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=400_000.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": [2, 4]}})
    )
    q1, q2, q3, q4 = _year(view, 3)
    assert q1["debt_service_usd"] == q3["debt_service_usd"] == 0.0
    assert q1["dscr"] is None and q3["dscr"] is None
    assert q1["calculation_periods"] is None and q3["calculation_periods"] is None
    assert q2["debt_service_usd"] == q4["debt_service_usd"] == 500_000.0
    assert q2["interest_usd"] == 200_000.0
    assert q2["dscr"] == math.fsum([q1["cfads_usd"], q2["cfads_usd"]]) / 500_000.0
    assert q4["dscr"] == math.fsum([q3["cfads_usd"], q4["cfads_usd"]]) / 500_000.0
    assert q2["calculation_periods"] == q4["calculation_periods"] == 2.0
    assert view.min_subperiod_dscr == min(
        p["dscr"] for p in view.periods if p["dscr"] is not None
    )


@pytest.mark.parametrize("periods", [[1, 2, 3, 4], [2, 4], [4]])
def test_flat_cfads_gives_every_instalment_the_annual_dscr(
    sized_lender, periods: List[int]
) -> None:
    """The analytic oracle for declared dates: with CFADS flat through the year, each
    instalment's calculation-period cover equals the annual DSCR, however many there are.
    """
    _, rows = sized_lender
    no_tax_year = next(i for i, row in enumerate(rows) if float(row["tax_lkr"]) == 0.0)
    service = float(rows[no_tax_year]["cfads_usd"]) / 1.30
    debt = _synthetic_debt(rows, service=service, interest=service / 3.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": periods}})
    )
    # Each list ends on Q4, so no calculation period crosses the year end; that case
    # has its own test below.
    quarters = _year(view, no_tax_year)
    paid = [quarters[p - 1] for p in periods]
    for quarter in paid:
        assert math.isclose(quarter["dscr"], 1.30, rel_tol=1e-14), quarter
    assert [q["calculation_periods"] for q in paid] == [
        float(b - a) for a, b in zip([0] + periods[:-1], periods)
    ]


def test_cash_after_the_last_instalment_counts_towards_the_next_years_first(
    sized_lender,
) -> None:
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=1_000_000.0, interest=0.0)
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": [1, 3]}})
    )
    first = _year(view, 0)
    assert first[0]["calculation_periods"] == 1.0
    assert first[2]["calculation_periods"] == 2.0
    previous, current = _year(view, 2), _year(view, 3)
    assert current[0]["calculation_periods"] == 2.0
    want = math.fsum([previous[3]["cfads_usd"], current[0]["cfads_usd"]]) / 500_000.0
    assert current[0]["dscr"] == want


#: Placements whose last quarter has zero weight and whose weights do not multiply back
#: exactly, so A2's allocate_flow would leave a ~1e-9 USD residual on that quarter
#: (#1556 domain DOM-8). Dyadic splits such as [2, 4] are exact and would hide it.
ZERO_WEIGHT_LAST = [
    {"periods": [1, 2, 3]},
    {"periods": [1, 3], "weights": [0.7, 0.3]},
]

#: An amount whose weighted parts do not sum back exactly under either placement above,
#: so A2's allocate_flow leaves about 9.3e-10 on Q4 (most amounts give exactly zero).
RESIDUAL_SERVICE = 7_321_208.521842453


@pytest.mark.parametrize("placement", ZERO_WEIGHT_LAST, ids=["1-2-3", "1-3-70-30"])
def test_a_zero_weight_quarter_is_never_an_instalment(
    sized_lender, placement: Dict[str, Any]
) -> None:
    """The residual closes on the last instalment, so Q4 carries exactly nothing, and
    each following Q1 is covered by the two quarters since the previous instalment."""
    debt, rows = sized_lender
    view = build_subperiod_coverage(
        rows,
        debt,
        _calendar({**ALL_EVEN, "debt_service": placement, "bridge_service": placement}),
    )
    mapping = debt["annual_row_debt_period_map"]
    serviced = [
        year_index
        for year_index, entry in enumerate(mapping)
        if float(debt["debt_service_total"][int(entry["debt_period"])]) > 0.0
    ]
    assert len(serviced) >= 10, "the lender case services most years"
    for year_index in range(len(mapping)):
        q4 = _year(view, year_index)[3]
        for key in (
            "scheduled_service_usd",
            "bridge_service_usd",
            "debt_service_usd",
            "interest_usd",
            "principal_usd",
            "balloon_interest_paid_usd",
        ):
            assert q4[key] == 0.0, (year_index, key, q4[key])
        assert q4["dscr"] is None and q4["calculation_periods"] is None
    for year_index in serviced:
        q1 = _year(view, year_index)[0]
        assert q1["calculation_periods"] == (1.0 if year_index == 0 else 2.0)
        # Ties to the annual engine: the quarters still re-aggregate.
        period = int(mapping[year_index]["debt_period"])
        scheduled = math.fsum(
            q["scheduled_service_usd"] for q in _year(view, year_index)
        )
        assert _within_ulp(scheduled, float(debt["debt_service_total"][period]))


def test_a_zero_weight_residual_cannot_halve_the_view_minimum(sized_lender) -> None:
    """The domain lane's synthetic case: with [1, 3] at [0.7, 0.3] and a year of heavier
    service, every instalment after year 1 is a two-quarter cover, so no residual can
    reset a window and halve the minimum."""
    _, rows = sized_lender
    debt = _synthetic_debt(rows, service=RESIDUAL_SERVICE, interest=1_000_000.0)
    debt["debt_service_total"][6] *= 1.2
    # The case is only a control if A2's rule would leave a residual on Q4.
    assert allocate_flow(RESIDUAL_SERVICE, (0.7, 0.0, 0.3, 0.0))[3] != 0.0
    view = build_subperiod_coverage(
        rows,
        debt,
        _calendar({**ALL_EVEN, "debt_service": ZERO_WEIGHT_LAST[1]}),
    )
    for year_index in range(1, len(rows)):
        quarters = _year(view, year_index)
        assert quarters[3]["dscr"] is None
        q1 = quarters[0]
        previous_q4 = _year(view, year_index - 1)[3]
        want = (
            math.fsum([previous_q4["cfads_usd"], q1["cfads_usd"]])
            - math.fsum([previous_q4["senior_fee_usd"], q1["senior_fee_usd"]])
        ) / q1["debt_service_usd"]
        assert q1["dscr"] == want
    ratios = [p["dscr"] for p in view.periods if p["dscr"] is not None]
    assert view.min_subperiod_dscr == min(ratios)
    assert all(
        p["calculation_periods"] == 2.0
        for p in view.periods[4:]
        if p["dscr"] is not None
    )


@pytest.mark.parametrize(
    "weights",
    [
        (0.25, 0.25, 0.25, 0.25),
        (0.0, 0.5, 0.0, 0.5),
        (0.0, 0.0, 0.0, 1.0),
        (1 / 3, 1 / 3, 1 / 3, 0.0),
        (0.7, 0.0, 0.3, 0.0),
        (0.0, 1.0, 0.0, 0.0),
    ],
)
def test_debt_cash_closes_on_the_last_positive_weight_quarter(weights) -> None:
    value = RESIDUAL_SERVICE
    parts = _allocate_on_placement(value, weights)
    assert [part == 0.0 for part in parts] == [weight == 0.0 for weight in weights]
    assert _within_ulp(math.fsum(parts), value)
    if weights[-1] > 0:
        # Where the last quarter carries weight, this is A2's rule, float for float.
        assert parts == allocate_flow(value, weights)


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
    assert dated.min_subperiod_dscr is not None
    assert spread.min_subperiod_dscr is not None
    assert dated.min_subperiod_dscr < spread.min_subperiod_dscr
    assert math.isclose(spread.min_subperiod_dscr, debt["min_dscr"], rel_tol=1e-14)


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
    assert COVENANT_USE == (
        "barred (F-5): an allocation of the annual engine plus declared or assumed "
        "dates; not for a covenant, lender or IC representation"
    )


def test_the_period_labels_are_zero_based_and_carried_from_the_rows(
    sized_lender,
) -> None:
    debt, rows = sized_lender
    view = build_subperiod_coverage(rows, debt, _calendar(ALL_EVEN))
    assert [p["period_index"] for p in view.periods] == [
        float(index) for index in range(len(view.periods))
    ]
    assert [p["period_in_year"] for p in view.periods] == [0.0, 1.0, 2.0, 3.0] * len(
        rows
    )
    assert [p["year"] for p in view.periods[::4]] == [float(r["year"]) for r in rows]


def test_the_live_fee_accrues_evenly_and_nets_over_the_whole_calculation_period(
    sized_lender,
) -> None:
    """The lender case carries a senior fee. It accrues evenly whatever the instalment
    dates, and each instalment nets every quarter's fee in its calculation period."""
    debt, rows = sized_lender
    view = build_subperiod_coverage(
        rows, debt, _calendar({**ALL_EVEN, "debt_service": {"periods": [2, 4]}})
    )
    mapping = debt["annual_row_debt_period_map"]
    feed = [
        year_index
        for year_index, entry in enumerate(mapping)
        # Year 1 also carries the bridge, on every quarter under ALL_EVEN.
        if year_index > 0
        and float(debt["senior_fee_usd"][int(entry["debt_period"])]) > 0.0
        and float(debt["debt_service_total"][int(entry["debt_period"])]) > 0.0
    ]
    assert feed, "the lender case carries a senior fee in serviced years"
    for year_index in feed:
        quarters = _year(view, year_index)
        fee = float(debt["senior_fee_usd"][int(mapping[year_index]["debt_period"])])
        for quarter in quarters:
            assert math.isclose(quarter["senior_fee_usd"], fee / 4.0, rel_tol=1e-12)
        for paid, window in (
            (quarters[1], quarters[0:2]),
            (quarters[3], quarters[2:4]),
        ):
            cash = math.fsum(q["cfads_usd"] for q in window)
            fees = math.fsum(q["senior_fee_usd"] for q in window)
            assert paid["calculation_periods"] == 2.0
            assert paid["dscr"] == (cash - fees) / paid["debt_service_usd"]


def test_debt_service_is_a_calendar_kind_without_a_default_date() -> None:
    assert EVENT_KINDS["debt_service"] is None
    assert "debt_service" not in DEFAULT_EVENT_PERIODS
    calendar = _calendar({"debt_service": {"periods": [2, 4]}})
    assert calendar.placements["debt_service"] == (0.0, 0.5, 0.0, 0.5)
    assert "debt_service" not in calendar.assumed
    assert "debt_service" not in _calendar({}).placements


@pytest.mark.parametrize("kind", ["debt_service", "bridge_service"])
def test_a_debt_kind_cannot_be_declared_as_profile(kind: str) -> None:
    """Debt cash falls on instalment dates; ``profile`` would be read as some other
    spread, so it is refused rather than accepted and silently evened."""
    with pytest.raises(ValueError, match=f"{kind} cannot be 'profile'"):
        _calendar({kind: "profile"})
