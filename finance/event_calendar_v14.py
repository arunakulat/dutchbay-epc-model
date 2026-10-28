"""A3 dolphin (b) — the within-year event calendar (#1395).

A2 (:mod:`finance.subannual_rows_v14`) spreads every annual flow across a year's
sub-periods by one within-year profile. That is right for a flow that accrues through
the year, such as revenue or opex. It is wrong for a cash item that falls on a date: a
BESS augmentation payment, a tax installment, the bridge period's debt service. Spread
like a flow, a discrete payment's dip is smoothed away, which is the gap the F-5 bar
names ("bess_augmentation_capex_lkr is a discrete event that A2 spreads like a flow").

This module lets a scenario say *which sub-periods* such an item falls in, and places it
there instead of spreading it. Everything else still follows the profile.

Default-off and byte-identical
------------------------------
With ``cashflow.event_calendar`` absent, which is every committed scenario,
:func:`resolve_event_calendar` returns ``None`` and nothing here runs. The annual engine
never reads this module, so the annual canon cannot move by shipping it. A calendar is
only meaningful on a sub-annual grid, so one declared on the annual grid is refused
rather than ignored.

Dates are declared, never assumed
---------------------------------
No placement has a default. When tax installments fall, when augmentation is paid and
when the bridge loan is serviced are project and contract facts this repository does not
hold evidence for (#920). A code default would be read as one. So an event kind is
placed only when the scenario declares its periods, and an undeclared kind keeps A2's
profile spread, exactly as before.

What is placed, and what follows from it
----------------------------------------
Three kinds, each with a declared list of 1-based periods within the year and optional
weights across them:

* ``bess_augmentation_capex`` places the row key ``bess_augmentation_capex_lkr``.
* ``tax`` places the row key ``tax_lkr``, the tax CASH payment. ``taxable_income_lkr``
  still accrues on the profile: income is earned through the year and paid on a date.
* ``bridge_service`` places the bridge period's scheduled debt service (USD), which the
  debt engine computes in its own PERIOD space and ``dscr_by_year`` folds into operating
  year 1. It is not an annual-row key, so it is placed by
  :func:`build_bridge_service_events` into year 1's sub-periods. Aligning the rest of
  debt service onto the sub-period axis is dolphin (c), not this one.

Moving a placed key moves the CFADS lines that the annual engine derives from it, or the
period would stop adding up. :func:`apply_event_calendar` therefore re-derives, per
period, ``posttax_cfads_lkr`` (pretax less tax), ``cfads_final_lkr`` and its alias
``cfads_risk_adjusted_lkr`` (post-tax less the risk haircut less augmentation), and
``cfads_usd`` (``cfads_final_lkr`` at the year's own LKR-to-USD factor). The risk haircut
stays on the profile: the engine computes it once per year on the annual post-tax CFADS,
so it is an allocated year-level figure, not a computed quarterly one (A4, #1395 (d)).

``working_capital`` is refused. The engine has no working-capital flow, so a working-
capital date has nothing to place, and silently accepting one would suggest it does
(``FRAMEWORK-02``).

Reconciliation
--------------
Every placed and re-derived flow re-aggregates to the annual engine's figure within the
same one-ULP bound A2 states, because each is built by the same closing-residual rule:
the earlier periods carry their computed values and the closing period takes
``annual - fsum(earlier)``. The bridge events re-aggregate to the bridge period's own
service the same way.

F-5 is untouched. A quarterly figure built with a calendar is still an allocation of the
annual engine plus declared dates, and no quarterly CFADS or intra-year DSCR figure may
support a covenant, lender or IC representation while that hold stands.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .cashflow_v14_utils import get_nested
from .period_grid_v14 import PeriodGrid, require_mapping_node
from .subannual_rows_v14 import allocate_flow, validate_profile_weights

__all__ = [
    "EVENT_CALENDAR_KEY",
    "EVENT_KINDS",
    "EventCalendar",
    "apply_event_calendar",
    "build_bridge_service_events",
    "resolve_event_calendar",
]

EVENT_CALENDAR_KEY = "cashflow.event_calendar"
_CALENDAR_PATH: Sequence[str] = ("cashflow", "event_calendar")

#: Event kind -> the annual-row key it places, or ``None`` for an event that is not an
#: annual-row key (the bridge service lives in the debt engine's period space).
EVENT_KINDS: Mapping[str, Optional[str]] = {
    "bess_augmentation_capex": "bess_augmentation_capex_lkr",
    "tax": "tax_lkr",
    "bridge_service": None,
}

#: Kinds a scenario might reasonably name that the engine has no flow for. Each is
#: refused with its reason rather than lumped in with typos.
_NOT_MODELLED: Mapping[str, str] = {
    "working_capital": (
        "the engine has no working-capital flow (no receivables, payables or inventory "
        "line), so there is nothing to place on a date"
    ),
}

_EVENT_FIELDS = frozenset({"periods", "weights"})


@dataclass(frozen=True)
class EventCalendar:
    """Resolved within-year placements, one weight vector per declared event kind.

    Attributes:
        grid: The sub-annual grid the placements are measured on.
        placements: Event kind -> weights over ALL of the grid's periods in a year
            (zeros outside the declared periods), summing to 1.
    """

    grid: PeriodGrid
    placements: Mapping[str, Tuple[float, ...]]

    @property
    def placed_row_keys(self) -> Dict[str, Tuple[float, ...]]:
        """Annual-row key -> placement, for the kinds that place an annual-row key."""
        return {
            row_key: self.placements[kind]
            for kind, row_key in EVENT_KINDS.items()
            if row_key is not None and kind in self.placements
        }


def resolve_event_calendar(
    config: Mapping[str, Any] | None, grid: PeriodGrid
) -> Optional[EventCalendar]:
    """Resolve ``cashflow.event_calendar`` against ``grid``.

    Args:
        config: The raw scenario config, or ``None``.
        grid: The resolved operating-period grid.

    Returns:
        ``None`` when no calendar is declared, otherwise the resolved calendar.

    Raises:
        ValueError: If the calendar is declared on the annual grid; if it, or an event
            entry, is not a mapping; if it names an unknown or unmodelled event kind, or
            an unknown field; or if an entry's periods or weights are malformed.
    """
    if config is None:
        return None

    require_mapping_node(config, _CALENDAR_PATH, EVENT_CALENDAR_KEY)
    raw = get_nested(dict(config), _CALENDAR_PATH)
    if raw is None:
        return None

    if grid.is_annual:
        raise ValueError(
            f"{EVENT_CALENDAR_KEY} is declared but cashflow.resolution is annual, which "
            "has one period per year and so no within-year date to place an event on. "
            "Set cashflow.resolution to a sub-annual grid, or remove the calendar."
        )
    if not isinstance(raw, dict):
        raise ValueError(
            f"{EVENT_CALENDAR_KEY} must be a mapping of event kind to its periods; got "
            f"{type(raw).__name__}."
        )

    placements: Dict[str, Tuple[float, ...]] = {}
    for kind, entry in raw.items():
        label = f"{EVENT_CALENDAR_KEY}.{kind}"
        if kind in _NOT_MODELLED:
            raise ValueError(
                f"{label} is not modelled: {_NOT_MODELLED[kind]} (FRAMEWORK-02). "
                "Remove the entry."
            )
        if kind not in EVENT_KINDS:
            raise ValueError(
                f"{label} is not a known event kind. Known: "
                f"{', '.join(sorted(EVENT_KINDS))}."
            )
        placements[str(kind)] = _resolve_entry(entry, grid, label)

    return EventCalendar(grid=grid, placements=placements)


def _resolve_entry(entry: Any, grid: PeriodGrid, label: str) -> Tuple[float, ...]:
    """Turn one event entry into weights over all of a year's periods."""
    if not isinstance(entry, dict):
        raise ValueError(
            f"{label} must be a mapping with 'periods' (and optional 'weights'); got "
            f"{type(entry).__name__}."
        )
    unknown = sorted(str(key) for key in entry if key not in _EVENT_FIELDS)
    if unknown:
        raise ValueError(
            f"{label} has unknown field(s) {unknown}; allowed: "
            f"{sorted(_EVENT_FIELDS)}."
        )

    periods = entry.get("periods")
    if (
        isinstance(periods, (str, bytes, Mapping))
        or not isinstance(periods, Sequence)
        or not periods
    ):
        raise ValueError(
            f"{label}.periods must be a non-empty list of 1-based periods within the "
            f"year (1..{grid.periods_per_year}); got {periods!r}."
        )
    positions: List[int] = []
    for period in periods:
        if (
            isinstance(period, bool)
            or not isinstance(period, int)
            or not 1 <= period <= grid.periods_per_year
        ):
            raise ValueError(
                f"{label}.periods entries must be whole numbers from 1 to "
                f"{grid.periods_per_year} on the {grid.resolution!r} grid; got "
                f"{period!r}."
            )
        positions.append(period - 1)
    if len(set(positions)) != len(positions):
        raise ValueError(f"{label}.periods lists a period more than once: {periods!r}.")

    raw_weights = entry.get("weights")
    if raw_weights is None:
        share = 1.0 / len(positions)
        weights: Tuple[float, ...] = tuple(share for _ in positions)
    else:
        # The same weight contract as a within-year profile, measured against the
        # declared periods rather than the whole year.
        weights = validate_profile_weights(
            raw_weights,
            PeriodGrid(resolution=f"{label}.periods", periods_per_year=len(positions)),
            f"{label}.weights",
        )

    full = [0.0] * grid.periods_per_year
    for position, weight in zip(positions, weights, strict=True):
        full[position] = weight
    return tuple(full)


def apply_event_calendar(
    rows: Sequence[Mapping[str, float]],
    annual_rows: Sequence[Mapping[str, Any]],
    calendar: EventCalendar,
) -> List[Dict[str, float]]:
    """Re-place a calendar's annual-row events onto sub-annual rows.

    ``rows`` are :func:`finance.subannual_rows_v14.build_subannual_rows` output for
    ``annual_rows`` on ``calendar.grid``. Each placed key is re-allocated by its event
    weights instead of the profile, and the CFADS lines derived from it are re-derived
    per period (see the module docstring). Every other key is returned unchanged.

    Args:
        rows: The profile-allocated sub-annual rows.
        annual_rows: The annual rows they were built from.
        calendar: The resolved calendar.

    Returns:
        New rows; the inputs are not mutated.

    Raises:
        ValueError: If ``rows`` is not ``len(annual_rows)`` whole years on the
            calendar's grid.
    """
    per_year = calendar.grid.periods_per_year
    if len(rows) != len(annual_rows) * per_year:
        raise ValueError(
            f"apply_event_calendar got {len(rows)} sub-annual rows for "
            f"{len(annual_rows)} annual rows on the {calendar.grid.resolution!r} grid "
            f"({per_year} periods each); the two do not describe the same years."
        )

    placed = calendar.placed_row_keys
    out = [dict(row) for row in rows]
    if not placed:
        return out

    for year_index, annual in enumerate(annual_rows):
        year_rows = out[year_index * per_year : (year_index + 1) * per_year]
        _place_year(year_rows, annual, placed)
    return out


def _place_year(
    year_rows: List[Dict[str, float]],
    annual: Mapping[str, Any],
    placed: Mapping[str, Tuple[float, ...]],
) -> None:
    """Place one year's events and re-derive its CFADS lines, in place."""
    tax = _parts(year_rows, "tax_lkr")
    aug = _parts(year_rows, "bess_augmentation_capex_lkr")
    for key, weights in placed.items():
        parts = allocate_flow(float(annual[key]), weights)
        if key == "tax_lkr":
            tax = parts
        else:
            aug = parts

    pretax = _parts(year_rows, "pretax_cfads_lkr")
    haircut = _parts(year_rows, "risk_haircut_amount_lkr")

    posttax = _closing_residual(
        float(annual["posttax_cfads_lkr"]),
        [pretax[i] - tax[i] for i in range(len(year_rows))],
    )
    cfads_final = _closing_residual(
        float(annual["cfads_final_lkr"]),
        [posttax[i] - haircut[i] - aug[i] for i in range(len(year_rows))],
    )
    factor = _usd_factor(annual)
    cfads_usd = _closing_residual(
        float(annual["cfads_usd"]), [value * factor for value in cfads_final]
    )

    for position, row in enumerate(year_rows):
        row["tax_lkr"] = tax[position]
        row["bess_augmentation_capex_lkr"] = aug[position]
        row["posttax_cfads_lkr"] = posttax[position]
        row["cfads_final_lkr"] = cfads_final[position]
        row["cfads_risk_adjusted_lkr"] = cfads_final[position]
        row["cfads_usd"] = cfads_usd[position]


def _parts(year_rows: Sequence[Mapping[str, float]], key: str) -> List[float]:
    return [float(row[key]) for row in year_rows]


def _closing_residual(annual_value: float, computed: Sequence[float]) -> List[float]:
    """Keep the earlier periods' computed values and close the year on the residual.

    The same rule as :func:`finance.subannual_rows_v14.allocate_flow`: all rounding lands
    in the closing period, so the year re-aggregates to ``annual_value`` within 1 ULP.
    """
    earlier = list(computed[:-1])
    return earlier + [annual_value - math.fsum(earlier)]


def _usd_factor(annual: Mapping[str, Any]) -> float:
    """The year's LKR-to-USD factor for CFADS.

    The engine converts with :func:`finance.cashflow_v14_fx._hedged_usd`, which is linear
    in the LKR amount for a year's fixed spot, forward, hedge ratio and spread. So the
    year's own ``cfads_usd / cfads_final_lkr`` is the factor for any part of it, hedged or
    not. When the year's CFADS is exactly zero the ratio is undefined, and the null-hedge
    factor ``1 / fx_rate`` is used; with no positive rate the engine reports 0 USD.
    """
    lkr = float(annual["cfads_final_lkr"])
    if lkr != 0.0:
        return float(annual["cfads_usd"]) / lkr
    fx_rate = float(annual.get("fx_rate", 0.0))
    return 1.0 / fx_rate if fx_rate > 0.0 else 0.0


def build_bridge_service_events(
    debt_result: Mapping[str, Any], calendar: EventCalendar
) -> List[Dict[str, float]]:
    """Place the bridge period's scheduled debt service into operating year 1.

    The debt engine prepends a synthetic bridge period to its timeline. Its service is
    real, maps to no operating row, and ``dscr_by_year`` folds it into year 1. This
    returns that service as dated events on year 1's sub-periods, split into interest and
    principal, so a reader can see when the bridge cash falls rather than only that it
    was folded.

    Args:
        debt_result: The debt engine's result. Reads ``cfads_bridge_debt_period``,
            ``debt_service_total`` and ``interest_total``.
        calendar: The resolved calendar.

    Returns:
        One event per year-1 sub-period, with ``year`` (1.0), ``period_index``,
        ``period_in_year``, ``debt_service_usd``, ``interest_usd`` and
        ``principal_usd``. Empty when the calendar does not declare
        ``bridge_service`` or the timeline carries no bridge.
    """
    weights = calendar.placements.get("bridge_service")
    bridge = debt_result.get("cfads_bridge_debt_period")
    if weights is None or bridge is None:
        return []

    period = int(bridge)
    service = float(debt_result["debt_service_total"][period])
    interest = float(debt_result["interest_total"][period])
    principal = service - interest

    service_parts = allocate_flow(service, weights)
    interest_parts = allocate_flow(interest, weights)
    principal_parts = _closing_residual(
        principal,
        [s - i for s, i in zip(service_parts, interest_parts, strict=True)],
    )
    return [
        {
            "year": 1.0,
            "period_index": float(position),
            "period_in_year": float(position),
            "debt_service_usd": service_parts[position],
            "interest_usd": interest_parts[position],
            "principal_usd": principal_parts[position],
        }
        for position in range(calendar.grid.periods_per_year)
    ]
