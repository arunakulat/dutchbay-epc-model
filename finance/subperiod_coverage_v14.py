"""A3 dolphin (c) — debt service, CFADS and DSCR on one sub-period index (#1395).

The debt engine works in its own PERIOD space: construction periods, a synthetic
half-year bridge period, then one period per operating year. ``dscr_by_year`` folds the
bridge period's scheduled service into operating year 1, and the headline ``min_dscr`` is
the conservative minimum over that fold and the operating-period series. Nothing in that
space says where in a year the cash falls.

This module puts the three on the operating SUB-PERIOD index that A1/A2 and the event
calendar (dolphin (b)) use. For each sub-period of each operating year it reports the
coverage CFADS, the senior fee, the scheduled debt service, the bridge service, the
interest and principal split, and the sub-period's DSCR.

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

An even spread is an assumption, not evidence: the real instalment dates are term-sheet
facts (#920). Each one used is recorded in :attr:`SubperiodCoverage.assumptions` and
named in a warning, as (b) does for its default dates.

Reconciliation
--------------
Every allocated series closes on the annual engine's own figure by A2's closing-residual
rule, so each operating year's sub-periods re-aggregate to the debt period's CFADS,
fee, service and interest within 1 ULP, and year 1's bridge parts to the bridge
period's service. A year's re-aggregated coverage, ``(CFADS - fee) / service``, therefore
reproduces ``dscr_by_year`` for that year, the folded year 1 included.
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
            ``year``, ``period_index``, ``period_in_year``, ``cfads_usd``,
            ``senior_fee_usd``, ``scheduled_service_usd``, ``bridge_service_usd``,
            ``debt_service_usd``, ``interest_usd``, ``principal_usd`` and ``dscr``
            (``None`` where the sub-period carries no debt service).
        assumptions: Each debt-cash placement that used the even default rather than a
            declared date, mapped to what was assumed.
        min_dscr: The lowest sub-period DSCR, for disclosure only. It is not, and must
            not be read as, the headline ``min_dscr``.
        covenant_use: :data:`COVENANT_USE`.
    """

    periods: Tuple[Mapping[str, Optional[float]], ...]
    assumptions: Mapping[str, str] = field(default_factory=dict)
    min_dscr: Optional[float] = None
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
            ``debt_service_total``, ``interest_total``, ``senior_fee_usd`` and
            ``cfads_bridge_debt_period``.
        calendar: The resolved event calendar; its grid is the sub-period grid.
        profile: The within-year profile for A2. Defaults to an even split.

    Returns:
        The sub-period view.

    Raises:
        ValueError: If the rows do not match the debt result one to one, or their
            ``cfads_usd`` is not the CFADS the debt engine divided.
    """
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
    fees = debt_result.get("senior_fee_usd") or [0.0] * len(service_total)

    periods: List[Dict[str, Optional[float]]] = []
    for year_index, entry in enumerate(mapping):
        debt_period = int(entry["debt_period"])
        year_rows = placed[year_index * per_year : (year_index + 1) * per_year]
        service = _at(service_total, debt_period)
        interest = _at(interest_total, debt_period)
        fee = _at(fees, debt_period)

        scheduled = allocate_flow(service, service_weights)
        scheduled_interest = allocate_flow(interest, service_weights)
        fee_parts = allocate_flow(fee, even_profile(grid))
        if year_index == 0:
            bridge_parts = allocate_flow(bridge_service, bridge_weights)
            bridge_interest_parts = allocate_flow(bridge_interest, bridge_weights)
        else:
            bridge_parts = [0.0] * per_year
            bridge_interest_parts = [0.0] * per_year

        for position, row in enumerate(year_rows):
            total = scheduled[position] + bridge_parts[position]
            interest_part = (
                scheduled_interest[position] + bridge_interest_parts[position]
            )
            cfads = float(row["cfads_usd"])
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
                    "dscr": (
                        (cfads - fee_parts[position]) / total if total > 0 else None
                    ),
                }
            )

    ratios = [p["dscr"] for p in periods if p["dscr"] is not None]
    finite = [value for value in ratios if math.isfinite(value)]
    return SubperiodCoverage(
        periods=tuple(periods),
        assumptions=assumptions,
        min_dscr=min(finite) if finite else None,
    )


def _weights(
    calendar: EventCalendar, kind: str, assumptions: Dict[str, str]
) -> Tuple[float, ...]:
    """The declared placement of ``kind``, or the even spread, recorded as assumed.

    ``profile`` places nothing for a debt kind, so it falls to the even spread too.
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
