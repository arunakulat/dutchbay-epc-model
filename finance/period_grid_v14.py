"""A1 — the operating-period grid: the single resolver for cashflow resolution.

This module is the one place that answers "how many cashflow periods are there in an
operating year, and which year does period *p* belong to?". It is pure arithmetic over
a resolution name: it holds no cashflow, no debt and no config beyond the one key it
resolves, and it imports nothing from the engine.

**Default-off and byte-identical.** With ``cashflow.resolution`` absent — every committed
scenario — :func:`resolve_period_grid` returns :data:`ANNUAL` (``periods_per_year == 1``),
under which every helper here is an identity or a no-op regrouping. Nothing in the
committed canon changes by shipping this module.

Sub-annual is NOT yet consumed by the engine
--------------------------------------------
``cashflow.resolution: quarterly`` parses and validates here, but the cashflow engine is
still annual by construction (``finance.cashflow_v14.build_annual_rows``). Rather than
accept the flag and silently produce annual output — a config that lies — the engine-side
gate :func:`require_engine_support` raises. The sub-annual operating rows land in A2, at
which point ``quarterly`` joins :data:`ENGINE_SUPPORTED_RESOLUTIONS`. Until then the
strictest honest behaviour is to fail loud (CESSPIT: no silent default that changes, or
fails to change, an output).

The three index spaces — read this before aligning anything
-----------------------------------------------------------
The model now carries three distinct axes. They are NOT interchangeable, and the debt
layer already documents a live index-space collision between two of its own series
(see the ``plan_debt`` docstring in :mod:`finance.debt_v14`). This module deliberately
does not add a fourth ambiguous space:

1. **Debt PERIOD space** (owned by :mod:`finance.debt_v14`, the F-6 taxonomy) —
   ``[construction] * construction_periods`` + an optional synthetic ``bridge`` period +
   one period per operating row + post-tenor padding. ``raw_dscr_series`` and the debt
   service / outstanding series are positional in this space.
2. **Operating YEAR space** — the annual cashflow rows, ``year`` 1..``project_life_years``.
   ``dscr_by_year`` is keyed here.
3. **Operating SUB-PERIOD space** (this module, new) — a subdivision of space 2 **only**.

Space 3 subdivides operating years and nothing else: it has no construction periods and
no bridge period, because construction pre-dates the operating rows this grid partitions.
``period_count(n_years) == n_years * periods_per_year`` exactly, with no padding.

**The sanctioned alignment chain** from a sub-period to a debt period is therefore two
hops, and never one::

    sub-period p  --year_index_for_period-->  operating row index
                  --debt_result["annual_row_debt_period_map"]-->  debt period

Do not index any debt series with a value from this module. In particular, never index
``debt_result["dscr_series"]`` positionally at all — it is the COMPACTED lender-facing
series and carries no period or year meaning (again, see the ``plan_debt`` docstring).

Flows versus balances
---------------------
Aggregation back to the annual axis differs by variable kind, and getting it wrong is a
silent value error rather than a crash. Two helpers make the choice explicit at the call
site: :func:`aggregate_flows_to_annual` sums (revenue, opex, CFADS — anything measured
*over* a period) and :func:`aggregate_balances_to_annual` takes the period-end value
(debt outstanding, reserve balances — anything measured *at* an instant). There is
deliberately no generic ``aggregate``; the caller must say which kind it holds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from .cashflow_v14_utils import get_nested

__all__ = [
    "ANNUAL",
    "CASHFLOW_RESOLUTION_KEY",
    "ENGINE_SUPPORTED_RESOLUTIONS",
    "SUPPORTED_RESOLUTIONS",
    "PeriodGrid",
    "aggregate_balances_to_annual",
    "aggregate_flows_to_annual",
    "period_count",
    "periods_for_year",
    "require_engine_support",
    "resolve_period_grid",
    "year_index_for_period",
]

# Config path of the resolution flag, as a dotted string for error messages and as the
# key sequence get_nested consumes. Kept together so the two can never drift.
CASHFLOW_RESOLUTION_KEY = "cashflow.resolution"
_RESOLUTION_PATH: Sequence[str] = ("cashflow", "resolution")

# Every resolution this grid can describe arithmetically.
SUPPORTED_RESOLUTIONS: Dict[str, int] = {
    "annual": 1,
    "quarterly": 4,
}

# The subset the CASHFLOW ENGINE can actually produce rows for today. This is the gate
# that A2 widens to include "quarterly"; SUPPORTED_RESOLUTIONS above is only about the
# arithmetic, which is already complete.
ENGINE_SUPPORTED_RESOLUTIONS = frozenset({"annual"})


@dataclass(frozen=True)
class PeriodGrid:
    """An operating-period grid: a resolution name and its periods-per-year.

    Immutable and comparable, so it can be passed down a call chain and asserted on
    without any risk of a consumer re-deriving a different grid mid-pipeline (CESSPIT
    single-resolver discipline — :func:`resolve_period_grid` is the only constructor
    callers should use).

    Attributes:
        resolution: The canonical lower-case resolution name, e.g. ``"annual"``.
        periods_per_year: Cashflow periods in one operating year; ``>= 1``.
    """

    resolution: str
    periods_per_year: int

    @property
    def is_annual(self) -> bool:
        """True when this grid is the degenerate one-period-per-year case."""
        return self.periods_per_year == 1


#: The default grid. Every committed scenario resolves to exactly this.
ANNUAL = PeriodGrid(resolution="annual", periods_per_year=1)


def resolve_period_grid(config: Mapping[str, Any] | None) -> PeriodGrid:
    """Resolve the operating-period grid from ``cashflow.resolution``.

    Absent or ``None`` yields :data:`ANNUAL`, so the committed canon is untouched. A
    present-but-unrecognised value fails loud rather than falling back to annual: a
    scenario asking for a resolution the model does not have must not be silently
    demoted to one it does (#585 fail-loud).

    Args:
        config: The raw scenario config, or ``None``.

    Returns:
        The resolved :class:`PeriodGrid`.

    Raises:
        ValueError: If ``cashflow.resolution`` is present but is not a string, is
            blank, or names a resolution outside :data:`SUPPORTED_RESOLUTIONS`.
    """
    if config is None:
        return ANNUAL

    raw = get_nested(dict(config), _RESOLUTION_PATH)
    if raw is None:
        return ANNUAL

    if not isinstance(raw, str):
        raise ValueError(
            f"{CASHFLOW_RESOLUTION_KEY} must be a string naming a resolution "
            f"({_supported_list()}); got {type(raw).__name__}."
        )

    name = raw.strip().lower()
    if not name:
        raise ValueError(
            f"{CASHFLOW_RESOLUTION_KEY} is empty — supply one of {_supported_list()}, "
            "or omit the key entirely for the default annual grid."
        )
    if name not in SUPPORTED_RESOLUTIONS:
        raise ValueError(
            f"{CASHFLOW_RESOLUTION_KEY}={raw!r} is not a supported resolution. "
            f"Supported: {_supported_list()}."
        )

    return PeriodGrid(resolution=name, periods_per_year=SUPPORTED_RESOLUTIONS[name])


def require_engine_support(grid: PeriodGrid) -> None:
    """Assert the cashflow engine can actually produce rows on ``grid``.

    :func:`resolve_period_grid` validates that a resolution is *describable*; this
    asserts it is *buildable*. The two are separate because the grid arithmetic lands
    (A1) one dolphin before the sub-annual operating rows that consume it (A2), and in
    between, a config naming ``quarterly`` must not quietly receive annual output.

    Args:
        grid: The resolved grid.

    Raises:
        ValueError: If the engine cannot yet build rows at this resolution.
    """
    if grid.resolution in ENGINE_SUPPORTED_RESOLUTIONS:
        return
    raise ValueError(
        f"{CASHFLOW_RESOLUTION_KEY}={grid.resolution!r} is a valid resolution but the "
        "cashflow engine does not yet build sub-annual rows, so the run would silently "
        "produce ANNUAL output under a sub-annual label. Engine-supported today: "
        f"{sorted(ENGINE_SUPPORTED_RESOLUTIONS)}. Omit the key for the annual grid."
    )


def period_count(project_life_years: int, grid: PeriodGrid = ANNUAL) -> int:
    """Total operating sub-periods across the project life.

    Exactly ``project_life_years * grid.periods_per_year`` — this axis subdivides the
    operating years and carries no construction, bridge or padding periods.

    Args:
        project_life_years: Operating-year count; ``>= 0``.
        grid: The operating-period grid.

    Returns:
        The sub-period count.

    Raises:
        ValueError: If ``project_life_years`` is negative.
    """
    if project_life_years < 0:
        raise ValueError(f"project_life_years must be >= 0; got {project_life_years}.")
    return int(project_life_years) * grid.periods_per_year


def year_index_for_period(period_index: int, grid: PeriodGrid = ANNUAL) -> int:
    """Zero-based operating-row index owning ``period_index``.

    The first hop of the sanctioned alignment chain (see the module docstring): map a
    sub-period to its operating ROW, then map that row to a debt period via
    ``debt_result["annual_row_debt_period_map"]``. Never map a sub-period straight onto
    a debt series.

    Args:
        period_index: Zero-based sub-period index.
        grid: The operating-period grid.

    Returns:
        The zero-based operating-row index.

    Raises:
        ValueError: If ``period_index`` is negative.
    """
    if period_index < 0:
        raise ValueError(f"period_index must be >= 0; got {period_index}.")
    return int(period_index) // grid.periods_per_year


def periods_for_year(year_index: int, grid: PeriodGrid = ANNUAL) -> List[int]:
    """The sub-period indices belonging to operating row ``year_index``, in order.

    Exact inverse of :func:`year_index_for_period`: every returned index maps back to
    ``year_index``, and the returned lists partition the axis with no gaps or overlaps.

    Args:
        year_index: Zero-based operating-row index.
        grid: The operating-period grid.

    Returns:
        The sub-period indices, ascending. Length is ``grid.periods_per_year``.

    Raises:
        ValueError: If ``year_index`` is negative.
    """
    if year_index < 0:
        raise ValueError(f"year_index must be >= 0; got {year_index}.")
    start = int(year_index) * grid.periods_per_year
    return list(range(start, start + grid.periods_per_year))


def aggregate_flows_to_annual(
    values: Sequence[float], grid: PeriodGrid = ANNUAL
) -> List[float]:
    """Sum a FLOW series from the sub-period axis back to the annual axis.

    For quantities measured *over* a period — revenue, opex, CFADS, debt service, tax.
    Under :data:`ANNUAL` this is an order-preserving copy, which is what makes the
    annual path byte-identical when the flag is off.

    Args:
        values: Sub-period flow values, positional on the sub-period axis.
        grid: The operating-period grid.

    Returns:
        One value per operating row: the sum of that row's sub-periods.

    Raises:
        ValueError: If ``len(values)`` is not a whole number of operating years — a
            ragged series means the caller's axis and this grid disagree, which would
            otherwise silently drop or misattribute a partial year.
    """
    chunks = _whole_years(values, grid, kind="flow")
    return [float(sum(chunk)) for chunk in chunks]


def aggregate_balances_to_annual(
    values: Sequence[float], grid: PeriodGrid = ANNUAL
) -> List[float]:
    """Take the period-END value of a BALANCE series back to the annual axis.

    For quantities measured *at* an instant — debt outstanding, DSRA/MMRA balances,
    carried-forward losses. Summing these would be meaningless, which is why this is a
    separate function rather than a flag on :func:`aggregate_flows_to_annual`.

    Args:
        values: Sub-period balance values, positional on the sub-period axis.
        grid: The operating-period grid.

    Returns:
        One value per operating row: that row's closing (last sub-period) balance.

    Raises:
        ValueError: If ``len(values)`` is not a whole number of operating years.
    """
    chunks = _whole_years(values, grid, kind="balance")
    return [float(chunk[-1]) for chunk in chunks]


def _whole_years(
    values: Sequence[float], grid: PeriodGrid, *, kind: str
) -> List[Sequence[float]]:
    """Split ``values`` into per-operating-year chunks, rejecting a ragged tail."""
    per_year = grid.periods_per_year
    length = len(values)
    if length % per_year != 0:
        raise ValueError(
            f"Cannot aggregate a {kind} series of length {length} on the "
            f"{grid.resolution!r} grid: it is not a whole number of operating years "
            f"({per_year} periods each). The caller's axis and this grid disagree."
        )
    return [values[i : i + per_year] for i in range(0, length, per_year)]


def _supported_list() -> str:
    """Render the supported resolution names for an error message."""
    return ", ".join(repr(name) for name in sorted(SUPPORTED_RESOLUTIONS))
