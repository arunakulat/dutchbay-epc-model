"""A2 — sub-annual operating rows, allocated from the annual engine.

Turns the annual cashflow rows into a finer operating grid so a consumer can see
within-year cash timing. Default-off: without ``cashflow.resolution`` nothing here runs
and the annual path is untouched.

Allocation, NOT re-derivation — read this before trusting a number
------------------------------------------------------------------
These rows are the ANNUAL engine's output **allocated** across sub-periods by a declared
within-year profile. They are not an independent sub-annual computation, and the
distinction is material to anyone reading a quarterly figure:

  * Degradation, opex escalation and the FX curve are annual series in the engine
    (:func:`finance.cashflow_v14.calculate_single_year_cfads` takes one ``fx_rate`` per
    year). Every sub-period of a year therefore inherits that year's single rate; the
    quarterly series does not model intra-year FX or escalation drift.
  * Tax, depreciation and the loss carry-forward are computed ANNUALLY and then spread.
    A quarterly ``tax_lkr`` is a share of the year's liability, not a quarter's own
    computed charge. A4 owns that allocation rule formally; this module implements the
    spread and says so here rather than letting a reader assume otherwise.
  * ``bess_augmentation_capex_lkr`` is a DISCRETE event within its year, but no
    within-year event calendar exists, so it spreads like any other flow. The annual sum
    is right; the within-year dip is smoothed and therefore understated.

What the allocation buys is real even so: with a non-even profile the quarters differ,
and once A3 maps quarterly debt service onto them, an intra-year DSCR trough appears that
the annual series structurally cannot show. What it does not buy is a second opinion on
the annual numbers — it cannot disagree with them, by construction.

Reconciliation — exact on the default profile, 1 ULP in general
---------------------------------------------------------------
Aggregating the sub-annual rows back to the annual axis reproduces the engine's own
figures:

* **exactly**, at float equality, under the default EVEN profile — measured across the
  committed lendercase at 540 of 540 (every allocated flow, every year). An even split
  by a power-of-two period count is exact in binary, so the closing residual has nothing
  left to absorb;
* **to within one unit in the last place** under an arbitrary profile — 510 of 540 exact
  and 30 at one ULP on a 0.35/0.15/0.15/0.35 seasonal split, never worse.

The closing sub-period of each year takes the residual ``value - fsum(earlier periods)``,
which parks all rounding in one declared place. Exactness cannot be promised beyond that:
the parts are independently rounded floats, so their exact sum can straddle a rounding
boundary that no choice of closing value reaches. :func:`allocate_flow` carries the
worked case.

One ULP at these magnitudes is under a millionth of a rupee on a multi-billion rupee
flow. The bound is asserted as an ULP count rather than a relative tolerance, because a
tolerance loose enough to absorb a genuine allocation bug would defeat the check that
A3's quarterly debt service is going to rest on.

Every key is classified, and an unknown key fails loud
------------------------------------------------------
Each of the annual row's keys is declared either a FLOW (allocated) or YEAR-LEVEL
(carried unchanged onto every sub-period). A key in neither set raises. This is the point
of the module's strictness: if the engine gains a row key later, this fails rather than
silently summing a rate or spreading a stock — the failure mode that would be invisible
in the output and wrong in the totals.

YEAR-LEVEL keys are carried, not divided, and remain year-level facts: ``fx_rate`` is the
year's rate, ``carried_forward_losses`` is the year-END balance repeated on each
sub-period for convenience, not a period-end balance. Read the closing period
(``is_year_end == 1.0``) when a year-end stock is what you want.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .cashflow_v14_utils import get_nested
from .period_grid_v14 import ANNUAL, PeriodGrid, require_engine_support

__all__ = [
    "FLOW_KEYS",
    "RECONCILIATION_ULP_TOLERANCE",
    "WITHIN_YEAR_PROFILE_KEY",
    "YEAR_LEVEL_KEYS",
    "allocate_flow",
    "build_subannual_rows",
    "even_profile",
    "resolve_within_year_profile",
]

WITHIN_YEAR_PROFILE_KEY = "cashflow.within_year_profile"
_PROFILE_PATH: Sequence[str] = ("cashflow", "within_year_profile")

#: Sum-of-weights tolerance. A profile is a share split, so it must sum to 1; the
#: tolerance admits ordinary decimal-literal rounding (``0.3 + 0.3 + 0.2 + 0.2``) without
#: admitting a profile that is meaningfully off.
_PROFILE_SUM_TOL = 1e-9

#: Units-in-the-last-place a re-aggregated year may differ from the engine's own annual
#: figure. See :func:`allocate_flow` for why this is 1 rather than 0.
RECONCILIATION_ULP_TOLERANCE = 1

#: Keys measured OVER a period — allocated across the year's sub-periods.
FLOW_KEYS: frozenset[str] = frozenset(
    {
        "gross_kwh",
        "grid_loss",
        "net_kwh",
        "revenue_lkr",
        "generation_revenue_lkr",
        "bess_revenue_lkr",
        "success_fee_lkr",
        "env_surcharge_lkr",
        "social_levy_lkr",
        "total_statutory_deductions_lkr",
        "opex_usd",
        "opex_lkr",
        "senior_fee_lkr",
        "ebitda_lkr",
        "pretax_cfads_lkr",
        "total_depreciation_lkr",
        "interest_expense_lkr",
        "taxable_income_lkr",
        "tax_lkr",
        "posttax_cfads_lkr",
        "risk_haircut_amount_lkr",
        "bess_augmentation_capex_lkr",
        "cfads_final_lkr",
        "cfads_risk_adjusted_lkr",
        "revenue_usd",
        "cfads_usd",
        "wht_on_interest",
    }
)

#: Keys that are a rate, a flag or a year-END stock — carried unchanged, never divided.
YEAR_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "fx_rate",
        "risk_haircut_pct",
        "effective_tax_rate",
        "tax_holiday_applied",
        "carried_forward_losses",
    }
)

#: The row's own year index, handled separately from both sets above.
_YEAR_KEY = "year"


def even_profile(grid: PeriodGrid) -> Tuple[float, ...]:
    """The default within-year profile: equal shares across the grid's periods."""
    share = 1.0 / grid.periods_per_year
    return tuple(share for _ in range(grid.periods_per_year))


def resolve_within_year_profile(
    config: Mapping[str, Any] | None, grid: PeriodGrid
) -> Tuple[float, ...]:
    """Resolve the within-year allocation profile for ``grid``.

    Absent yields :func:`even_profile`. A present profile must have exactly
    ``grid.periods_per_year`` non-negative, finite weights summing to 1.

    Args:
        config: The raw scenario config, or ``None``.
        grid: The resolved operating-period grid.

    Returns:
        The weights, in period order.

    Raises:
        ValueError: If the profile is not a sequence of the right length, or carries a
            non-numeric, negative or non-finite weight, or does not sum to 1.
    """
    if config is None:
        return even_profile(grid)

    raw = get_nested(dict(config), _PROFILE_PATH)
    if raw is None:
        return even_profile(grid)

    if isinstance(raw, (str, bytes, Mapping)) or not isinstance(raw, Sequence):
        raise ValueError(
            f"{WITHIN_YEAR_PROFILE_KEY} must be a sequence of "
            f"{grid.periods_per_year} weights; got {type(raw).__name__}."
        )

    if len(raw) != grid.periods_per_year:
        raise ValueError(
            f"{WITHIN_YEAR_PROFILE_KEY} has {len(raw)} weights but the "
            f"{grid.resolution!r} grid has {grid.periods_per_year} periods per year. "
            "Supply one weight per period, or omit the key for an even split."
        )

    weights: List[float] = []
    for position, value in enumerate(raw):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(
                f"{WITHIN_YEAR_PROFILE_KEY}[{position}] must be a number; "
                f"got {type(value).__name__}."
            )
        weight = float(value)
        if not math.isfinite(weight):
            raise ValueError(
                f"{WITHIN_YEAR_PROFILE_KEY}[{position}] must be finite; got {weight!r}."
            )
        if weight < 0.0:
            raise ValueError(
                f"{WITHIN_YEAR_PROFILE_KEY}[{position}] must be >= 0; got {weight!r}. "
                "A negative share would move cash between periods rather than split it."
            )
        weights.append(weight)

    total = math.fsum(weights)
    if abs(total - 1.0) > _PROFILE_SUM_TOL:
        raise ValueError(
            f"{WITHIN_YEAR_PROFILE_KEY} weights sum to {total!r}, not 1.0. The profile "
            "splits a year's flow into shares, so a sum other than 1 would silently "
            "scale every allocated figure."
        )

    return tuple(weights)


def allocate_flow(value: float, profile: Sequence[float]) -> List[float]:
    """Split one annual flow across a year's sub-periods.

    Earlier periods take their weighted share; the CLOSING period takes the residual
    ``value - fsum(earlier)``, which puts all the rounding in one declared place instead
    of smearing it across the year.

    Accuracy — 1 ULP, not exact, and the difference is deliberate
    ------------------------------------------------------------
    Re-aggregating the parts reproduces ``value`` to within **one unit in the last
    place**. It is not exact, and cannot be made exact: the parts are independently
    rounded floats, so their exact real sum generally falls strictly between two
    representable neighbours of ``value``. On the committed lendercase's year-2 CFADS
    (7,175,292,510.270228 LKR) the exact sum straddles a rounding boundary, and pushing
    the closing period by one ULP simply oscillates the re-sum between ``value - 1 ULP``
    and ``value + 1 ULP`` without ever landing on it.

    One ULP at that magnitude is 9.5e-7 LKR — under a millionth of a rupee on a 7.2
    billion rupee figure — so the bound is immaterial in cash terms. It is stated
    precisely rather than hidden behind a loose relative tolerance, because a tolerance
    wide enough to absorb a real allocation bug would defeat the check that A3's debt
    service depends on.

    Args:
        value: The annual flow.
        profile: Within-year weights, summing to 1.

    Returns:
        One value per sub-period, in order.
    """
    if len(profile) == 1:
        # The annual grid: an identity, and deliberately the same float object.
        return [value]

    parts = [value * weight for weight in profile[:-1]]
    parts.append(value - math.fsum(parts))
    return parts


def build_subannual_rows(
    annual_rows: Sequence[Mapping[str, Any]],
    grid: PeriodGrid = ANNUAL,
    profile: Sequence[float] | None = None,
) -> List[Dict[str, float]]:
    """Allocate annual cashflow rows onto the sub-annual operating grid.

    Args:
        annual_rows: Rows from :func:`finance.cashflow_v14.build_annual_rows`.
        grid: The operating-period grid. Defaults to :data:`ANNUAL`, under which each
            annual row yields exactly one sub-period row carrying the same values.
        profile: Within-year weights. Defaults to an even split.

    Returns:
        ``len(annual_rows) * grid.periods_per_year`` rows, each carrying the allocated
        flows, the year-level keys unchanged, and the positional keys ``year``,
        ``period_index``, ``period_in_year`` and ``is_year_end``.

    Raises:
        ValueError: If the grid is not one the engine supports, if ``profile`` has the
            wrong length, or if any row carries a key that is neither a declared flow
            nor a declared year-level key.
    """
    require_engine_support(grid)

    weights = tuple(profile) if profile is not None else even_profile(grid)
    if len(weights) != grid.periods_per_year:
        raise ValueError(
            f"profile has {len(weights)} weights but the {grid.resolution!r} grid has "
            f"{grid.periods_per_year} periods per year."
        )

    rows: List[Dict[str, float]] = []
    for year_index, annual in enumerate(annual_rows):
        _reject_unclassified_keys(annual, year_index)

        allocated = {
            key: allocate_flow(float(annual[key]), weights)
            for key in annual
            if key in FLOW_KEYS
        }

        for period_in_year in range(grid.periods_per_year):
            row: Dict[str, float] = {
                _YEAR_KEY: float(annual.get(_YEAR_KEY, year_index + 1)),
                "period_index": float(
                    year_index * grid.periods_per_year + period_in_year
                ),
                "period_in_year": float(period_in_year),
                "is_year_end": (
                    1.0 if period_in_year == grid.periods_per_year - 1 else 0.0
                ),
            }
            for key, parts in allocated.items():
                row[key] = parts[period_in_year]
            for key in annual:
                if key in YEAR_LEVEL_KEYS:
                    row[key] = float(annual[key])
            rows.append(row)

    return rows


def _reject_unclassified_keys(row: Mapping[str, Any], year_index: int) -> None:
    """Fail loud on a row key that is neither a declared flow nor year-level.

    An unclassified key is the one failure this module cannot make visible in its output:
    silently dropping it loses information, and silently allocating it would divide a
    rate or spread a stock. Both produce plausible numbers, so neither is acceptable.
    """
    unknown = sorted(
        key
        for key in row
        if key != _YEAR_KEY and key not in FLOW_KEYS | YEAR_LEVEL_KEYS
    )
    if not unknown:
        return
    raise ValueError(
        f"Annual row {year_index} carries key(s) {unknown} that "
        "finance.subannual_rows_v14 does not classify. Add each to FLOW_KEYS (measured "
        "over a period, so it is allocated) or YEAR_LEVEL_KEYS (a rate, flag or "
        "year-end stock, so it is carried unchanged). Refusing to guess: allocating a "
        "rate or carrying a flow would both produce plausible, wrong numbers."
    )
