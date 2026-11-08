"""A3 dolphin (c) — debt service, CFADS and DSCR on one sub-period index (#1395).

The debt engine works in its own PERIOD space: construction periods, a synthetic
half-year bridge period, then one period per operating year. ``dscr_by_year`` folds the
bridge period's scheduled service into operating year 1, and the headline ``min_dscr`` is
the conservative minimum over that fold and the operating-period series. Nothing in that
space says where in a year the cash falls.

This module puts the three on the operating SUB-PERIOD index that A1/A2 and the event
calendar (dolphin (b)) use. For each sub-period of each operating year it reports the
coverage CFADS, the senior fee, the scheduled debt service, the bridge service, the
interest and principal split, and, where an instalment falls, its DSCR over its
calculation period.

A view beside the annual figures, never a replacement
-----------------------------------------------------
The owner chose (#1395 (c), 2026-10-31) a quarterly view with the headline unchanged.
Nothing here feeds ``min_dscr``, ``dscr_by_year``, the sculpt, or any KPI: the module reads
the debt engine's finished result and returns a separate object. Its sub-period DSCRs are
an allocation of the annual engine plus declared or assumed dates, so the F-5 hold
applies to every one of them: no figure here may support a covenant, lender or IC
representation (:data:`COVENANT_USE`).

The CFADS it divides
--------------------
The DSCR series divides COVERAGE CFADS: the levered-tax rows the facility was sized on
(#1397), not the project-basis ``cfads_usd`` an ordinary pipeline row carries. The caller
passes those rows. Their ``cfads_usd`` equals ``annual_row_debt_period_map[*].cfads_usd``
exactly, and :func:`build_subperiod_coverage` refuses rows that do not, because a view
divided by the wrong CFADS would look plausible and tie to nothing. The rows go through
A2 and then the event calendar, so augmentation and tax land where (b) places them.

When the debt cash falls
------------------------
* Scheduled service of an operating year is placed by the calendar's ``debt_service``
  kind when the scenario declares it (for example ``periods: [2, 4]`` for semi-annual
  instalments). Otherwise it is spread evenly over the year's sub-periods.
* The bridge period's service lands in operating year 1, where ``dscr_by_year`` already
  counts it. It follows the calendar's ``bridge_service`` kind when declared, and is
  otherwise spread evenly over year 1.
* The senior fee accrues on the outstanding balance through the year, so it is spread
  evenly.
* Interest paid on a balloon carried past maturity (#1503, #1504) is real debt cash in
  the years after the tenor, but the engine keeps it out of ``debt_service_total`` and so
  out of ``dscr_by_year``. The view reads it from the debt result
  (``balloon_interest_paid`` at the year's debt period, as the pipeline's enrichment
  does), reports it per sub-period as ``balloon_interest_paid_usd`` on the
  ``debt_service`` placement, and keeps it out of the DSCR the same way. A year after the
  tenor therefore shows that cash with no ratio rather than looking debt-free.

An even spread is an assumption, not evidence: the real instalment dates are term-sheet
facts (#920). Each one used is recorded in :attr:`SubperiodCoverage.assumptions` and
named in a warning, as (b) does for its default dates.

What a sub-period DSCR measures
-------------------------------
An instalment is paid out of the cash earned since the previous one, so a sub-period's
DSCR is its instalment's cover over its CALCULATION PERIOD: the coverage CFADS less the
senior fee, accumulated over every sub-period since the previous instalment (or since
the first operating sub-period), divided by the debt service paid in this sub-period. A
sub-period with no debt service carries no ratio, and its cash counts towards the next
instalment, across a year end if need be. ``calculation_periods`` names how many
sub-periods each ratio covers. With an instalment in every sub-period (the even default)
the calculation period is the sub-period itself. With semi-annual instalments
(``periods: [2, 4]``) and flat CFADS, each instalment's cover equals the annual DSCR,
where a one-quarter numerator would have read half of it.

Which sub-periods are instalments
---------------------------------
A sub-period carries an instalment when the placement gives it a positive weight and
the amount being placed is positive. That is decided from the declared WEIGHTS, never
from whether an allocated float came out non-zero. A2's :func:`allocate_flow` closes its
rounding residual on the year's last sub-period whatever that sub-period's weight, so a
placement that leaves the last sub-period at zero weight (``periods: [1, 2, 3]``, or
``[1, 3]`` with weights ``[0.7, 0.3]``) would put about 1e-9 USD there in many years. Read
as an instalment, that residual would reset the calculation period and roughly halve the
next real instalment's cover (#1556 domain DOM-8). The debt cash is therefore allocated
by :func:`_allocate_on_placement`, which applies the same closing-residual rule but
closes on the last POSITIVE-weight sub-period, so a zero-weight sub-period carries
exactly ``0.0`` of every debt series.

Two consequences of the dates follow and are worth stating. When ``debt_service`` is
declared but ``bridge_service`` is not, the bridge takes the even-spread assumption, so
each of year 1's sub-periods becomes an instalment and year 1's declared instalments are
covered by less cash than their dates imply; declare the bridge on the same dates as the
scheduled service. And the first calculation period starts at the first operating
sub-period, because no pre-COD cash or DSRA funding is modelled here, so an instalment
declared in year 1's first sub-period is covered by that one sub-period's cash. A
zero-service year inside the tenor (a grace period) would carry its cash into the next
instalment's window; the committed lender case has none.

Reconciliation
--------------
Every allocated series closes on the annual engine's own figure by A2's closing-residual
rule (on the last positive-weight sub-period for the debt series), so each operating year's sub-periods re-aggregate to the debt period's CFADS,
fee, service and interest within 1 ULP, and year 1's bridge parts to the bridge
period's service. A year's re-aggregated coverage, ``(CFADS - fee) / service``, therefore
reproduces ``dscr_by_year`` for that year, the folded year 1 included.

Labels
------
``year``, ``period_index`` and ``period_in_year`` are carried from A2's rows, as floats
like every other figure. ``period_in_year`` is 0-BASED (``0.0`` is the year's first
sub-period, ``3.0`` a quarterly year's fourth), whereas ``cashflow.event_calendar``
declares periods 1-based. ``period_index`` counts sub-periods from the first operating
one, also from 0.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .event_calendar_v14 import EventCalendar, apply_event_calendar
from .subannual_rows_v14 import allocate_flow, build_subannual_rows, even_profile

__all__ = [
    "COVENANT_USE",
    "DEBT_ENRICHMENT_KEYS",
    "SubperiodCoverage",
    "build_subperiod_coverage",
]

logger = logging.getLogger(__name__)

#: How a sub-period DSCR may be used while F-5 stands.
COVENANT_USE = (
    "barred (F-5): an allocation of the annual engine plus declared or assumed dates; "
    "not for a covenant, lender or IC representation"
)

#: Keys the pipeline's debt enrichment adds to a sizing row. This view recomputes debt
#: service from the debt result itself, so it drops them before A2, which would
#: otherwise refuse them as unclassified. A new enrichment key fails loud in A2.
DEBT_ENRICHMENT_KEYS = frozenset(
    {
        "balloon_interest_accrued_usd",
        "balloon_interest_paid_usd",
        "balloon_resolution",
        "cf_after_debt",
        "cf_pre_debt",
        "debt_service_total",
        "interest_usd",
    }
)


@dataclass(frozen=True)
class SubperiodCoverage:
    """Debt service, coverage CFADS and DSCR on the operating sub-period index.

    Attributes:
        periods: One dict per sub-period of every operating year, in order, with
            ``year``, ``period_index`` and ``period_in_year`` (0-based; see the module
            docstring's Labels), ``cfads_usd``, ``senior_fee_usd``,
            ``scheduled_service_usd``, ``bridge_service_usd``, ``debt_service_usd``,
            ``interest_usd``, ``principal_usd``, ``balloon_interest_paid_usd`` (outside
            the DSCR, as in ``dscr_by_year``), ``dscr`` (the instalment's cover over its
            calculation period, ``None`` where the sub-period carries no debt service)
            and ``calculation_periods`` (how many sub-periods that ratio covers,
            ``None`` with it).
        assumptions: Each debt-cash placement that used the even default rather than a
            declared date, mapped to what was assumed.
        min_subperiod_dscr: The lowest sub-period DSCR, for disclosure only. It is not,
            and must not be read as, the headline ``min_dscr``, so it is named apart.
        covenant_use: :data:`COVENANT_USE`.
    """

    periods: Tuple[Mapping[str, Optional[float]], ...]
    assumptions: Mapping[str, str] = field(default_factory=dict)
    min_subperiod_dscr: Optional[float] = None
    covenant_use: str = COVENANT_USE


def build_subperiod_coverage(
    coverage_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
    calendar: EventCalendar,
    profile: Optional[Sequence[float]] = None,
) -> SubperiodCoverage:
    """Place the debt engine's result on the calendar's sub-period grid.

    Args:
        coverage_rows: The annual rows the facility was sized on (levered tax), one per
            ``debt_result['annual_row_debt_period_map']`` entry, with or without the
            pipeline's debt-enrichment keys.
        debt_result: The debt engine's result. Reads ``annual_row_debt_period_map``,
            ``debt_service_total``, ``interest_total``, ``senior_fee_usd``,
            ``balloon_interest_paid`` and ``cfads_bridge_debt_period``.
        calendar: The resolved event calendar; its grid is the sub-period grid.
        profile: The within-year profile for A2. Defaults to an even split.

    Returns:
        The sub-period view.

    Raises:
        ValueError: If the rows do not match the debt result one to one, their
            ``cfads_usd`` is not the CFADS the debt engine divided, or the debt result
            carries no ``balloon_interest_paid`` series.
    """
    if "balloon_interest_paid" not in debt_result:
        raise ValueError(
            "build_subperiod_coverage needs the debt result's balloon_interest_paid "
            "series (#1505): without it, interest paid on a balloon carried past "
            "maturity would show as zero and a post-tenor year would look debt-free."
        )
    mapping = list(debt_result["annual_row_debt_period_map"])
    if len(coverage_rows) != len(mapping):
        raise ValueError(
            f"build_subperiod_coverage got {len(coverage_rows)} rows for a debt result "
            f"that maps {len(mapping)} operating years."
        )
    for entry in mapping:
        row = coverage_rows[int(entry["annual_row_index"])]
        if float(row["cfads_usd"]) != float(entry["cfads_usd"]):
            raise ValueError(
                f"Row {entry['annual_row_index']} carries cfads_usd "
                f"{float(row['cfads_usd'])!r}, but the debt engine divided "
                f"{float(entry['cfads_usd'])!r}. Pass the coverage (sizing) rows the "
                "facility was sized on, not the project-basis rows."
            )

    grid = calendar.grid
    per_year = grid.periods_per_year
    rows = [
        {key: value for key, value in row.items() if key not in DEBT_ENRICHMENT_KEYS}
        for row in coverage_rows
    ]
    placed = apply_event_calendar(
        build_subannual_rows(rows, grid, profile), rows, calendar
    )

    assumptions: Dict[str, str] = {}
    service_weights = _weights(calendar, "debt_service", assumptions)
    bridge_service, bridge_interest = _bridge(debt_result)
    bridge_weights = (
        _weights(calendar, "bridge_service", assumptions)
        if bridge_service
        else even_profile(grid)
    )
    if assumptions:
        logger.warning(
            "Sub-period coverage: %s placed on an ASSUMED even spread. These are not "
            "evidenced instalment dates (#920); declare them in cashflow.event_calendar. "
            "Sub-period DSCR is %s.",
            ", ".join(sorted(assumptions)),
            COVENANT_USE,
        )

    service_total = debt_result["debt_service_total"]
    interest_total = debt_result["interest_total"]
    balloon_paid_total = debt_result["balloon_interest_paid"] or []
    fees = debt_result.get("senior_fee_usd") or [0.0] * len(service_total)

    periods: List[Dict[str, Optional[float]]] = []
    # The calculation period of the next instalment: cash and fee accumulated since the
    # previous one, across a year end if need be.
    window_cash: List[float] = []
    window_fee: List[float] = []
    for year_index, entry in enumerate(mapping):
        debt_period = int(entry["debt_period"])
        year_rows = placed[year_index * per_year : (year_index + 1) * per_year]
        service = _at(service_total, debt_period)
        interest = _at(interest_total, debt_period)
        fee = _at(fees, debt_period)

        scheduled = _allocate_on_placement(service, service_weights)
        scheduled_interest = _allocate_on_placement(interest, service_weights)
        fee_parts = allocate_flow(fee, even_profile(grid))
        balloon_parts = _allocate_on_placement(
            _at(balloon_paid_total, debt_period), service_weights
        )
        paying = [service > 0 and weight > 0 for weight in service_weights]
        if year_index == 0:
            bridge_parts = _allocate_on_placement(bridge_service, bridge_weights)
            bridge_interest_parts = _allocate_on_placement(
                bridge_interest, bridge_weights
            )
            paying = [
                pays or (bridge_service > 0 and weight > 0)
                for pays, weight in zip(paying, bridge_weights, strict=True)
            ]
        else:
            bridge_parts = [0.0] * per_year
            bridge_interest_parts = [0.0] * per_year

        for position, row in enumerate(year_rows):
            total = scheduled[position] + bridge_parts[position]
            interest_part = (
                scheduled_interest[position] + bridge_interest_parts[position]
            )
            cfads = float(row["cfads_usd"])
            window_cash.append(cfads)
            window_fee.append(fee_parts[position])
            dscr: Optional[float] = None
            covered: Optional[float] = None
            if paying[position]:
                # Decided from the placement weights (see "Which sub-periods are
                # instalments"), not from ``total``, so no residual is an instalment.
                dscr = (math.fsum(window_cash) - math.fsum(window_fee)) / total
                covered = float(len(window_cash))
                window_cash, window_fee = [], []
            periods.append(
                {
                    "year": float(row["year"]),
                    "period_index": float(row["period_index"]),
                    "period_in_year": float(row["period_in_year"]),
                    "cfads_usd": cfads,
                    "senior_fee_usd": fee_parts[position],
                    "scheduled_service_usd": scheduled[position],
                    "bridge_service_usd": bridge_parts[position],
                    "debt_service_usd": total,
                    "interest_usd": interest_part,
                    "principal_usd": total - interest_part,
                    "balloon_interest_paid_usd": balloon_parts[position],
                    "dscr": dscr,
                    "calculation_periods": covered,
                }
            )

    ratios = [p["dscr"] for p in periods if p["dscr"] is not None]
    finite = [value for value in ratios if math.isfinite(value)]
    return SubperiodCoverage(
        periods=tuple(periods),
        assumptions=assumptions,
        min_subperiod_dscr=min(finite) if finite else None,
    )


def _allocate_on_placement(value: float, weights: Sequence[float]) -> List[float]:
    """Allocate debt cash over a placement, closing on its last positive-weight period.

    The same closing-residual rule as A2's :func:`allocate_flow`, and the same floats
    wherever the last sub-period has positive weight. A sub-period with zero weight gets
    exactly ``0.0``, and the residual closes on the last sub-period that has a positive
    weight, so a placement such as ``[1, 2, 3]`` never leaves a rounding residual on a
    sub-period with no instalment (#1556 domain DOM-8).

    Args:
        value: The annual (or bridge) amount to place.
        weights: The placement's weights, one per sub-period, summing to 1.

    Returns:
        One value per sub-period, in order.
    """
    positive = [index for index, weight in enumerate(weights) if weight > 0]
    if not positive or len(weights) == 1:
        return allocate_flow(value, weights)
    parts = [0.0] * len(weights)
    for index in positive[:-1]:
        parts[index] = value * weights[index]
    parts[positive[-1]] = value - math.fsum(parts[index] for index in positive[:-1])
    return parts


def _weights(
    calendar: EventCalendar, kind: str, assumptions: Dict[str, str]
) -> Tuple[float, ...]:
    """The declared placement of ``kind``, or the even spread, recorded as assumed.

    The calendar refuses ``profile`` for a debt kind, so an absent placement here means
    the kind was not declared.
    """
    declared = calendar.placements.get(kind)
    if declared is not None:
        return tuple(declared)
    per_year = calendar.grid.periods_per_year
    assumptions[kind] = f"even over the {per_year} periods of the year"
    return tuple(even_profile(calendar.grid))


def _bridge(debt_result: Mapping[str, Any]) -> Tuple[float, float]:
    """The bridge period's service and interest, or zero when there is no bridge.

    ``dscr_by_year`` folds the bridge into year 1 only when the bridge maps to no
    operating row, which is how the engine always builds it; the same test is applied
    here so the view folds exactly what the covenant table folds.
    """
    bridge = debt_result.get("cfads_bridge_debt_period")
    if bridge is None:
        return 0.0, 0.0
    mapped = {int(m["debt_period"]) for m in debt_result["annual_row_debt_period_map"]}
    if int(bridge) in mapped:
        return 0.0, 0.0
    return (
        _at(debt_result["debt_service_total"], int(bridge)),
        _at(debt_result["interest_total"], int(bridge)),
    )


def _at(series: Sequence[Any], index: int) -> float:
    return float(series[index]) if 0 <= index < len(series) else 0.0
