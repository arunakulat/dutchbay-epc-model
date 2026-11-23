"""Monthly CFADS cascade, dolphin 1: CFADS computed month by month (default-off).

Owner request of 2026-11-22: produce CFADS from a monthly cash-flow cascade. This module
is the first of four dolphins (design proposal approved 2026-11-22):

1. **this module**: a monthly cascade that reconciles to the annual engine, moving no KPI;
2. timing effects (receivables and payables days, tax instalment dates, FX and
   indexation dates, discrete events in their month), R3;
3. quarterly debt sculpting on instalment dates, with a true-length bridge, R3;
4. the F-5 exit evidence pack.

Nothing reads this module yet. No pipeline, KPI, report, workbook or debt path calls it,
so every committed figure is unchanged by construction. It runs only for a caller that
asks for it, and only on a config that declares ``cashflow.monthly``.

What is computed and what is not, per line
------------------------------------------
Every monthly row carries the same lines as an annual row, and :data:`LINE_BASIS` says
how each one is produced. There are three bases:

* ``computed``: worked out for the month from the month's own drivers. Energy is the
  year's net energy times the month's ENERGY-SHAPE weight (the seasonal share of the
  year's generation). Generation revenue is that energy times the tariff in force, and
  the statutory charges are their rates applied to the month's revenue. EBITDA,
  post-tax cash flow, the risk haircut, CFADS and the USD views follow from those lines
  by the annual engine's own arithmetic.
* ``time_accrued``: a cost or income that accrues with the calendar, not with energy,
  spread by the month's share of the year's DAYS. Fixed O&M, the senior credit-support
  fee and a BESS capacity charge are paid for time, so a 31-day month carries more than
  a 28-day one.
* ``allocated``: still the annual figure spread by days, because its real date is a
  dolphin-2 input. Income tax is paid on instalment dates and augmentation capex falls
  in one month; until dolphin 2 places them, they are spread and labelled as such.

So the seasonal profile of revenue and CFADS is real: a low-wind month shows lower
revenue and lower CFADS, which the annual engine cannot show and A2's allocation
(:mod:`finance.subannual_rows_v14`) only shows when someone supplies the shape of the
answer. The annual inputs (one tariff, one FX rate and one opex escalation step per
operating year) are unchanged in dolphin 1, which is what makes the months add back.

Reconciliation is enforced, not hoped for
-----------------------------------------
:func:`build_monthly_cascade` sums each line over the 12 months of each year and refuses
the result unless every sum equals the annual engine's figure within
:data:`RECONCILIATION_REL_TOLERANCE` of the year's revenue. It also refuses a year whose
annual generation revenue is not the year's net energy times the tariff it resolved,
because then the monthly revenue would rest on a different tariff from the annual one.

The F-5 hold applies
--------------------
Every figure here is subject to F-5: no monthly CFADS or intra-year DSCR may support a
covenant, lender or IC representation until F-5's own authority path records an exit.
:data:`COVENANT_USE` says so in the output itself.

Configuration (``cashflow.monthly``)
------------------------------------
.. code-block:: yaml

    cashflow:
      monthly:
        cod_month: 7          # calendar month (1-12) in which operating month 1 falls
        energy_shape:         # optional: share of a year's net energy, Jan..Dec, sum 1
          [0.06, 0.05, 0.05, 0.05, 0.10, 0.12, 0.13, 0.12, 0.10, 0.08, 0.07, 0.07]

* ``cod_month`` anchors operating months to calendar months, so a calendar-month shape
  and calendar day counts land in the right operating month. Without it, months are
  equal twelfths and the cascade says so in :attr:`MonthlyCascade.assumptions`.
* ``energy_shape`` is by CALENDAR month (seasons are calendar facts). Without it,
  energy follows the days, which is flat generation, and the cascade says so. A shape
  without ``cod_month`` is refused: it could not be placed.
* The scenario owns its shape. Nothing here is site-specific (owner rule of
  2026-11-16). A shape taken from private measurements does not belong in a committed
  scenario; where no measured data exists the shape is a modelled one, and a report
  that uses it must say so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .cashflow_v14 import _prepare_cashflow_context, build_annual_rows
from .cashflow_v14_fx import _hedged_usd
from .cashflow_v14_production import _calculate_statutory_deductions
from .cashflow_v14_utils import get_nested
from .period_grid_v14 import PeriodGrid, require_mapping_node
from .subannual_rows_v14 import validate_profile_weights
from .tariff_indexation import tariff_lkr_per_kwh_for_year

__all__ = [
    "COVENANT_USE",
    "LINE_BASIS",
    "MONTHLY_KEY",
    "MONTHS_PER_YEAR",
    "MAX_RECEIVABLE_DAYS",
    "RECEIVABLES_KEY",
    "RECONCILIATION_REL_TOLERANCE",
    "MonthlyCascade",
    "MonthlySpec",
    "apply_receivables_lag",
    "build_monthly_cascade",
    "receivables_balances",
    "operating_month_weights",
    "resolve_monthly_spec",
]

MONTHS_PER_YEAR = 12

#: Dotted config path of the cascade's node, for error messages.
MONTHLY_KEY = "cashflow.monthly"
_MONTHLY_PATH: Sequence[str] = ("cashflow", "monthly")

_ALLOWED_KEYS = frozenset({"cod_month", "energy_shape", "receivable_days"})

#: Longest receivables lag accepted, in days. A lag over a year would carry a whole
#: year's revenue unpaid, which is a default, not a payment term.
MAX_RECEIVABLE_DAYS = 365

#: A 12-period grid, used only to validate a shape through the shared profile contract.
_MONTHLY_GRID = PeriodGrid(resolution="monthly", periods_per_year=MONTHS_PER_YEAR)

#: Calendar day counts, January..December, on a 365-day operating year. A leap day is
#: not modelled: the annual engine's year is 8,760 hours.
_DAYS_IN_CALENDAR_MONTH: Tuple[int, ...] = (
    31,
    28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
)

#: How far a year's 12-month sum of a line may sit from the annual engine's figure, as a
#: share of the year's revenue (or 1 LKR, whichever is larger). Twelve products and a
#: sum carry a few ULPs of rounding, about 1e-15 relative; 1e-12 leaves three orders of
#: margin for that and none for a real error, which would be a whole share of a line.
RECONCILIATION_REL_TOLERANCE = 1e-12

#: The annual and monthly row key for the change in offtaker receivables (dolphin 2).
#: Positive means cash tied up (receivables grew), and it is deducted from CFADS.
RECEIVABLES_KEY = "receivables_change_lkr"

#: How a monthly figure may be used while F-5 stands.
COVENANT_USE = (
    "F-5 HOLD: monthly CFADS and any intra-year DSCR built on it support no covenant, "
    "lender or IC representation until F-5's own authority path records an exit."
)

COMPUTED = "computed"
TIME_ACCRUED = "time_accrued"
ALLOCATED = "allocated"

#: Every line a monthly row carries, and how it is produced. See the module docstring.
LINE_BASIS: Dict[str, str] = {
    "gross_kwh": COMPUTED,
    "grid_loss": COMPUTED,
    "net_kwh": COMPUTED,
    "generation_revenue_lkr": COMPUTED,
    "bess_revenue_lkr": TIME_ACCRUED,
    "revenue_lkr": COMPUTED,
    "success_fee_lkr": COMPUTED,
    "env_surcharge_lkr": COMPUTED,
    "social_levy_lkr": COMPUTED,
    "total_statutory_deductions_lkr": COMPUTED,
    "opex_usd": TIME_ACCRUED,
    "opex_lkr": TIME_ACCRUED,
    "senior_fee_lkr": TIME_ACCRUED,
    "ebitda_lkr": COMPUTED,
    "tax_lkr": ALLOCATED,
    "posttax_cfads_lkr": COMPUTED,
    "risk_haircut_amount_lkr": COMPUTED,
    "bess_augmentation_capex_lkr": ALLOCATED,
    "receivables_change_lkr": COMPUTED,
    "cfads_final_lkr": COMPUTED,
    "revenue_usd": COMPUTED,
    "cfads_usd": COMPUTED,
}


@dataclass(frozen=True)
class MonthlySpec:
    """The resolved ``cashflow.monthly`` node.

    Attributes:
        cod_month: Calendar month (1-12) of operating month 1, or ``None``.
        energy_shape: Share of a year's net energy per CALENDAR month, January first,
            or ``None`` for energy that follows the days.
    """

    cod_month: Optional[int]
    energy_shape: Optional[Tuple[float, ...]]
    receivable_days: int = 0


@dataclass(frozen=True)
class MonthlyCascade:
    """The cascade's output.

    Attributes:
        rows: One row per operating month, ``12 * years`` rows in order. Each carries
            every :data:`LINE_BASIS` line plus ``year``, ``month_in_year`` (1-12),
            ``calendar_month`` (1-12, or ``None`` without ``cod_month``),
            ``period_index`` (0-based), ``is_year_end`` and the year's ``fx_rate``.
        annual_rows: The annual engine's rows the months reconcile to.
        energy_weights: The 12 operating-month energy weights used.
        time_weights: The 12 operating-month day-count weights used.
        assumptions: Each default the cascade fell back on, in words.
        line_basis: :data:`LINE_BASIS`, carried so the output explains itself.
        covenant_use: :data:`COVENANT_USE`.
    """

    rows: List[Dict[str, Any]]
    annual_rows: List[Dict[str, float]]
    energy_weights: Tuple[float, ...]
    time_weights: Tuple[float, ...]
    assumptions: Tuple[str, ...]
    line_basis: Dict[str, str] = field(default_factory=lambda: dict(LINE_BASIS))
    covenant_use: str = COVENANT_USE


def resolve_monthly_spec(config: Mapping[str, Any] | None) -> Optional[MonthlySpec]:
    """Resolve ``cashflow.monthly``; ``None`` when it is absent.

    Raises:
        ValueError: If the node is not a mapping, carries an unknown key, a
            ``cod_month`` that is not a whole number 1-12, an ``energy_shape`` that is
            not 12 non-negative finite weights summing to 1, or a shape without a
            ``cod_month`` to place it.
    """
    if config is None:
        return None
    require_mapping_node(config, _MONTHLY_PATH, MONTHLY_KEY)
    raw = get_nested(dict(config), _MONTHLY_PATH)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(
            f"{MONTHLY_KEY} must be a mapping with keys {sorted(_ALLOWED_KEYS)}; "
            f"got {type(raw).__name__}."
        )
    unknown = sorted(str(key) for key in raw if key not in _ALLOWED_KEYS)
    if unknown:
        raise ValueError(
            f"{MONTHLY_KEY} carries unknown key(s) {unknown}; accepted keys are "
            f"{sorted(_ALLOWED_KEYS)}. A misspelt key would otherwise be ignored and "
            "the cascade would fall back to a default without saying why."
        )

    cod_month = raw.get("cod_month")
    if cod_month is not None:
        if isinstance(cod_month, bool) or not isinstance(cod_month, int):
            raise ValueError(
                f"{MONTHLY_KEY}.cod_month must be a whole calendar month 1-12; "
                f"got {cod_month!r}."
            )
        if not 1 <= cod_month <= MONTHS_PER_YEAR:
            raise ValueError(
                f"{MONTHLY_KEY}.cod_month must be 1-12 (January = 1); got {cod_month}."
            )

    shape_raw = raw.get("energy_shape")
    shape: Optional[Tuple[float, ...]] = None
    if shape_raw is not None:
        if cod_month is None:
            raise ValueError(
                f"{MONTHLY_KEY}.energy_shape is by calendar month, so it needs "
                f"{MONTHLY_KEY}.cod_month to say which calendar month operating month 1 "
                "falls in. Without it the seasons could not be placed."
            )
        shape = validate_profile_weights(
            shape_raw, _MONTHLY_GRID, f"{MONTHLY_KEY}.energy_shape"
        )

    days_raw = raw.get("receivable_days", 0)
    if isinstance(days_raw, bool) or not isinstance(days_raw, int):
        raise ValueError(
            f"{MONTHLY_KEY}.receivable_days must be a whole number of days; "
            f"got {days_raw!r}."
        )
    if not 0 <= days_raw <= MAX_RECEIVABLE_DAYS:
        raise ValueError(
            f"{MONTHLY_KEY}.receivable_days must be 0-{MAX_RECEIVABLE_DAYS}; "
            f"got {days_raw}."
        )

    return MonthlySpec(
        cod_month=cod_month, energy_shape=shape, receivable_days=days_raw
    )


def operating_month_weights(
    spec: MonthlySpec,
) -> Tuple[Tuple[float, ...], Tuple[float, ...], Tuple[Optional[int], ...], List[str]]:
    """Return ``(energy_weights, time_weights, calendar_months, assumptions)``.

    Each weight tuple has 12 entries in OPERATING-month order and sums to 1. The
    calendar shape is rotated so operating month 1 takes ``cod_month``'s weight.
    """
    assumptions: List[str] = []
    if spec.cod_month is None:
        time_weights = tuple(1.0 / MONTHS_PER_YEAR for _ in range(MONTHS_PER_YEAR))
        calendar: Tuple[Optional[int], ...] = tuple(
            None for _ in range(MONTHS_PER_YEAR)
        )
        assumptions.append(
            f"{MONTHLY_KEY}.cod_month not declared: each operating month is an equal "
            "twelfth of the year, with no calendar day counts."
        )
    else:
        months = tuple(
            (spec.cod_month - 1 + k) % MONTHS_PER_YEAR + 1
            for k in range(MONTHS_PER_YEAR)
        )
        calendar = months
        days = [_DAYS_IN_CALENDAR_MONTH[m - 1] for m in months]
        total_days = float(sum(days))
        time_weights = tuple(d / total_days for d in days)

    if spec.energy_shape is None:
        energy_weights = time_weights
        assumptions.append(
            f"{MONTHLY_KEY}.energy_shape not declared: energy follows the days "
            "(flat generation through the year), so revenue shows no seasonality."
        )
    else:
        if spec.cod_month is None:
            # resolve_monthly_spec refuses this; a directly built spec must too.
            raise ValueError(
                f"{MONTHLY_KEY}.energy_shape needs {MONTHLY_KEY}.cod_month to place it."
            )
        shape = spec.energy_shape
        energy_weights = tuple(
            shape[(spec.cod_month - 1 + k) % MONTHS_PER_YEAR]
            for k in range(MONTHS_PER_YEAR)
        )

    return energy_weights, time_weights, calendar, assumptions


def _split(value: float, weights: Sequence[float]) -> List[float]:
    """Split ``value`` by ``weights``, closing the residual on the last month.

    The residual goes on the last POSITIVE-weight month, so a zero-weight month never
    shows a rounding-sized phantom value.
    """
    parts = [value * w for w in weights]
    last = max(i for i, w in enumerate(weights) if w > 0.0)
    parts[last] = 0.0
    parts[last] = value - math.fsum(parts)
    return parts


def build_monthly_cascade(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    extra_depreciable_usd: Optional[float] = None,
    senior_fee_lkr_series: Optional[List[float]] = None,
    interest_paid_series: Optional[List[float]] = None,
) -> MonthlyCascade:
    """Build the monthly CFADS cascade for a scenario that declares ``cashflow.monthly``.

    The arguments are those of :func:`finance.cashflow_v14.build_annual_rows` and are
    passed to it unchanged, so a caller builds the monthly view of exactly the annual
    basis it needs (for example the levered-tax coverage rows the facility is sized on).

    Raises:
        ValueError: If the config does not declare ``cashflow.monthly``, if the node is
            malformed (:func:`resolve_monthly_spec`), or if the months fail to reconcile
            to the annual engine.
    """
    spec = resolve_monthly_spec(config)
    if spec is None:
        raise ValueError(
            f"{MONTHLY_KEY} is not declared. The monthly cascade is opt-in; declare "
            f"{MONTHLY_KEY} (at least an empty mapping) to build it."
        )
    energy_w, time_w, calendar, assumptions = operating_month_weights(spec)

    annual_rows = build_annual_rows(
        config,
        fx_curve=fx_curve,
        capex_depreciable_lkr=capex_depreciable_lkr,
        interest_expense_series=interest_expense_series,
        extra_depreciable_usd=extra_depreciable_usd,
        senior_fee_lkr_series=senior_fee_lkr_series,
        interest_paid_series=interest_paid_series,
    )
    # A fresh context for the per-year drivers the annual rows do not carry (the tariff
    # in force and the FX hedge). It is built from the same config the same way, so it
    # resolves the same values; _check_tariff below proves that for the tariff.
    params, _fx, _cap, _int, _years, _tp, _dep, fx_hedge, _fee = (
        _prepare_cashflow_context(
            config,
            fx_curve,
            capex_depreciable_lkr,
            interest_expense_series,
            extra_depreciable_usd=extra_depreciable_usd,
            senior_fee_lkr_series=senior_fee_lkr_series,
        )
    )

    balances = receivables_balances(annual_rows, spec)
    rows: List[Dict[str, Any]] = []
    for year_index, annual in enumerate(annual_rows):
        start = year_index * MONTHS_PER_YEAR
        receivables_change = [
            balances[start + k] - (balances[start + k - 1] if start + k > 0 else 0.0)
            for k in range(MONTHS_PER_YEAR)
        ]
        tariff = tariff_lkr_per_kwh_for_year(
            float(params["tariff_lkr_per_kwh"]),
            params.get("tariff_om_indexation"),
            year_index,
        )
        _check_tariff(annual, tariff, year_index)
        forward = fx_hedge.forward_curve[year_index] if fx_hedge.forward_curve else 0.0
        months = _cascade_year(
            annual,
            tariff=tariff,
            energy_w=energy_w,
            time_w=time_w,
            params=params,
            hedge_ratio=fx_hedge.hedge_ratio,
            spread=fx_hedge.spread,
            forward=forward,
            receivables_change=receivables_change,
        )
        for k, line_values in enumerate(months):
            row: Dict[str, Any] = {
                "year": float(annual.get("year", year_index + 1)),
                "month_in_year": k + 1,
                "calendar_month": calendar[k],
                "period_index": year_index * MONTHS_PER_YEAR + k,
                "is_year_end": 1.0 if k == MONTHS_PER_YEAR - 1 else 0.0,
                "fx_rate": float(annual["fx_rate"]),
            }
            row.update(line_values)
            rows.append(row)
        _check_reconciliation(annual, months, year_index)

    return MonthlyCascade(
        rows=rows,
        annual_rows=annual_rows,
        energy_weights=energy_w,
        time_weights=time_w,
        assumptions=tuple(assumptions)
        + (
            "tax_lkr and bess_augmentation_capex_lkr are the annual figures spread by "
            "days until dolphin 2 places them on their dates.",
        ),
    )


def _cascade_year(
    annual: Mapping[str, float],
    *,
    tariff: float,
    energy_w: Sequence[float],
    time_w: Sequence[float],
    params: Mapping[str, Any],
    hedge_ratio: float,
    spread: float,
    forward: float,
    receivables_change: Sequence[float] = (0.0,) * MONTHS_PER_YEAR,
) -> List[Dict[str, float]]:
    """Run the cascade for the 12 months of one operating year."""
    fx_rate = float(annual["fx_rate"])
    gross = _split(float(annual["gross_kwh"]), energy_w)
    net = _split(float(annual["net_kwh"]), energy_w)
    bess = _split(float(annual["bess_revenue_lkr"]), time_w)
    opex_usd = _split(float(annual["opex_usd"]), time_w)
    opex_lkr = _split(float(annual["opex_lkr"]), time_w)
    fee = _split(float(annual["senior_fee_lkr"]), time_w)
    tax = _split(float(annual["tax_lkr"]), time_w)
    aug = _split(float(annual["bess_augmentation_capex_lkr"]), time_w)
    haircut_pct = float(annual["risk_haircut_pct"])
    # The haircut is a risk adjustment on the YEAR's post-tax cash flow, adverse in the
    # year's direction (finance.cashflow_v14_production._apply_risk_haircut). A month's
    # sign can differ from its year's; applying the year's factor keeps the months
    # adding back to the year and keeps the adjustment one per year, as the engine has it.
    year_posttax = float(annual["posttax_cfads_lkr"])
    factor = (1.0 - haircut_pct) if year_posttax >= 0.0 else (1.0 + haircut_pct)

    out: List[Dict[str, float]] = []
    for k in range(MONTHS_PER_YEAR):
        gen_rev = net[k] * tariff
        revenue = gen_rev + bess[k]
        statutory = _calculate_statutory_deductions(
            revenue,
            float(params["success_fee_pct"]),
            float(params["env_surcharge_pct"]),
            float(params["social_levy_pct"]),
        )
        ebitda = (
            revenue - statutory["total_statutory_deductions"] - opex_lkr[k] - fee[k]
        )
        posttax = ebitda - tax[k]
        after_haircut = posttax * factor
        cfads_lkr = after_haircut - aug[k] - receivables_change[k]
        if fx_rate > 0.0:
            revenue_usd = _hedged_usd(revenue, fx_rate, forward, hedge_ratio, spread)
            cfads_usd = _hedged_usd(cfads_lkr, fx_rate, forward, hedge_ratio, spread)
        else:
            revenue_usd = 0.0
            cfads_usd = 0.0
        out.append(
            {
                "gross_kwh": gross[k],
                "grid_loss": gross[k] - net[k],
                "net_kwh": net[k],
                "generation_revenue_lkr": gen_rev,
                "bess_revenue_lkr": bess[k],
                "revenue_lkr": revenue,
                "success_fee_lkr": statutory["success_fee"],
                "env_surcharge_lkr": statutory["environmental_surcharge"],
                "social_levy_lkr": statutory["social_services_levy"],
                "total_statutory_deductions_lkr": statutory[
                    "total_statutory_deductions"
                ],
                "opex_usd": opex_usd[k],
                "opex_lkr": opex_lkr[k],
                "senior_fee_lkr": fee[k],
                "ebitda_lkr": ebitda,
                "tax_lkr": tax[k],
                "posttax_cfads_lkr": posttax,
                "risk_haircut_amount_lkr": posttax - after_haircut,
                "bess_augmentation_capex_lkr": aug[k],
                RECEIVABLES_KEY: receivables_change[k],
                "cfads_final_lkr": cfads_lkr,
                "revenue_usd": revenue_usd,
                "cfads_usd": cfads_usd,
            }
        )
    return out


def _tolerance(annual: Mapping[str, float]) -> float:
    scale = max(abs(float(annual.get("revenue_lkr", 0.0))), 1.0)
    return RECONCILIATION_REL_TOLERANCE * scale


def _check_tariff(annual: Mapping[str, float], tariff: float, year_index: int) -> None:
    """Refuse a year whose annual revenue is not its energy times this tariff."""
    expected = float(annual["net_kwh"]) * tariff
    got = float(annual["generation_revenue_lkr"])
    if abs(expected - got) > _tolerance(annual):
        raise ValueError(
            f"Operating year {year_index + 1}: the annual engine's generation revenue "
            f"({got!r} LKR) is not its net energy times the tariff the cascade resolved "
            f"({expected!r} LKR). The monthly revenue would rest on a different tariff "
            "from the annual one, so the cascade refuses to build."
        )


def _check_reconciliation(
    annual: Mapping[str, float],
    months: Sequence[Mapping[str, float]],
    year_index: int,
) -> None:
    """Refuse a year whose 12 months do not add back to the annual engine's figures.

    CFADS is checked in both currencies; the USD view uses the same conversion as the
    annual engine, so it too must add back.
    """
    tol = _tolerance(annual)
    for line in LINE_BASIS:
        if line not in annual:
            if any(float(m.get(line, 0.0)) != 0.0 for m in months):
                raise ValueError(
                    f"Operating year {year_index + 1}: the months carry {line} but the "
                    "annual engine's row does not; refusing to return the cascade."
                )
            continue
        total = math.fsum(float(m[line]) for m in months)
        want = float(annual[line])
        if line in {"gross_kwh", "net_kwh", "grid_loss"}:
            line_tol = RECONCILIATION_REL_TOLERANCE * max(abs(want), 1.0)
        elif line in {"revenue_usd", "cfads_usd", "opex_usd"}:
            fx = float(annual["fx_rate"]) or 1.0
            line_tol = tol / fx
        else:
            line_tol = tol
        if abs(total - want) > line_tol:
            raise ValueError(
                f"Operating year {year_index + 1}: the 12 monthly {line} values sum to "
                f"{total!r}, but the annual engine reports {want!r} (difference "
                f"{total - want!r}, tolerance {line_tol!r}). The monthly cascade must "
                "reconcile to the annual figures; refusing to return it."
            )


def receivables_balances(
    annual_rows: Sequence[Mapping[str, float]], spec: Optional[MonthlySpec]
) -> List[float]:
    """Month-end offtaker receivables (LKR), one per operating month, in order.

    A month-end balance is the revenue invoiced over the trailing ``receivable_days``,
    walking back through earlier months at each month's daily rate, and never before
    the first operating month (nothing is owed before COD). Generation revenue is placed
    by the energy weights and a BESS capacity charge by the day weights, as in the
    cascade. The project's last month-end balance is 0: what is still owed at the end of
    operations is assumed collected in the final month, so the lag defers cash and never
    loses it.

    With no spec or a zero lag every balance is 0.
    """
    n = len(annual_rows) * MONTHS_PER_YEAR
    if spec is None or spec.receivable_days == 0 or n == 0:
        return [0.0] * n
    energy_w, time_w, _calendar, _assumptions = operating_month_weights(spec)
    days = [w * 365.0 for w in time_w]
    revenue: List[float] = []
    for annual in annual_rows:
        gen = float(annual["generation_revenue_lkr"])
        bess = float(annual["bess_revenue_lkr"])
        revenue.extend(
            gen * energy_w[k] + bess * time_w[k] for k in range(MONTHS_PER_YEAR)
        )
    balances: List[float] = []
    for i in range(n):
        remaining = float(spec.receivable_days)
        balance = 0.0
        j = i
        while remaining > 0.0 and j >= 0:
            month_days = days[j % MONTHS_PER_YEAR]
            take = min(remaining, month_days)
            balance += revenue[j] * (take / month_days)
            remaining -= take
            j -= 1
        balances.append(balance)
    balances[-1] = 0.0
    return balances


def apply_receivables_lag(
    rows: List[Dict[str, float]], config: Mapping[str, Any], fx_hedge: Any
) -> List[Dict[str, float]]:
    """Deduct the change in offtaker receivables from each annual row's CFADS.

    Dolphin 2 of #1893. Called by every annual row builder in
    :mod:`finance.cashflow_v14`, so the debt sizing, the covenant tests and the equity
    waterfall all see cash as COLLECTED, not as invoiced. Without
    ``cashflow.monthly.receivable_days`` (or with 0) the rows are returned untouched,
    byte for byte, and carry no :data:`RECEIVABLES_KEY`.

    The change is a working-capital movement: it is not a cost, so it moves neither
    EBITDA nor taxable income, and it sits after the risk haircut, like augmentation
    capex. Its USD view uses the year's own conversion (spot, or the hedge blend).
    """
    spec = resolve_monthly_spec(config)
    if spec is None or spec.receivable_days == 0 or not rows:
        return rows
    balances = receivables_balances(rows, spec)
    previous = 0.0
    for year_index, row in enumerate(rows):
        closing = balances[(year_index + 1) * MONTHS_PER_YEAR - 1]
        change = closing - previous
        previous = closing
        row[RECEIVABLES_KEY] = change
        row["cfads_final_lkr"] = row["cfads_final_lkr"] - change
        row["cfads_risk_adjusted_lkr"] = row["cfads_final_lkr"]
        fx_rate = float(row["fx_rate"])
        if fx_rate > 0.0:
            forward = (
                fx_hedge.forward_curve[year_index] if fx_hedge.forward_curve else 0.0
            )
            row["cfads_usd"] = row["cfads_usd"] - _hedged_usd(
                change, fx_rate, forward, fx_hedge.hedge_ratio, fx_hedge.spread
            )
    return rows
