"""Quarterly debt sculpting on the monthly CFADS cascade (dolphin 3 of #1893).

Opt-in (`cashflow.monthly.quarterly_sculpting.enabled: true`), default-off on every
committed scenario. Builds quarterly CFADS from :mod:`finance.monthly_cascade_v14` under
the month-level adverse risk haircut rule (``month_adverse``), prices a true-length
sub-annual bridge period, accrues senior credit-support fees on the time-weighted
outstanding balance per quarter, sculpts principal on declared (or assumed) instalment
dates, and reports quarterly instalment DSCR beside the annual covenant ``dscr_by_year``.

Non-reliance (F-5)
------------------
Every figure produced here is subject to the F-5 hold: not a lender representation; F-5
stays in force until F-5's own authority path records an exit (:data:`COVENANT_USE`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.debt.constants import _AMORT_ANNUITY_STYLES
from finance.debt.schedules import Tranche
from finance.monthly_cascade_v14 import (
    _DAYS_IN_CALENDAR_MONTH,
    DEFAULT_BRIDGE_MONTHS,
    DEFAULT_INSTALMENT_QUARTERS,
    HAIRCUT_RULE_MONTH_ADVERSE,
    MONTHLY_KEY,
    MONTHS_PER_YEAR,
    QUARTERS_PER_YEAR,
    MonthlyCascade,
    MonthlySpec,
    build_monthly_cascade_from_annual_rows,
    resolve_monthly_spec,
)

__all__ = [
    "COVENANT_USE",
    "QuarterlySculptingResult",
    "build_quarterly_sculpted_schedule",
    "is_quarterly_sculpting_enabled",
    "true_bridge_length_years",
]

#: Explicit F-5 non-reliance statement carried on every quarterly sculpting output.
COVENANT_USE = (
    "Not a lender representation; F-5 stays in force. Quarterly sculpted debt service, "
    "true-length bridge and quarterly DSCR built on the monthly cascade support no "
    "covenant, lender or IC representation until F-5's own authority path records an exit."
)

_MONTHS_PER_QUARTER = 3


@dataclass(frozen=True)
class QuarterlySculptingResult:
    """Quarterly sculpted debt schedule, true-length bridge, and quarterly DSCR view."""

    instalment_quarters: Tuple[int, ...]
    bridge_months: int
    bridge_length_years: float
    bridge_period: Optional[Dict[str, Any]]
    operating_quarters: Tuple[Dict[str, Any], ...]
    quarterly_dscr_min: Optional[float]
    annual_covenant_dscr_by_year: Dict[Any, Optional[float]]
    annual_covenant_dscr_min: Optional[float]
    time_weighted_senior_fee_total_usd: float
    annual_aggregated_schedules: Dict[str, List[Tuple[float, float, float]]]
    annual_opening_balances_usd: List[float]
    annual_senior_fees_usd: List[float]
    annual_cfads_usd: List[float]
    balloon_remaining_usd: float
    mixed_sign_haircut_excess_lkr: Tuple[float, ...]
    assumptions: Tuple[str, ...]
    risk_haircut_rule: str = HAIRCUT_RULE_MONTH_ADVERSE
    covenant_use: str = COVENANT_USE

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly dictionary for ``debt_result['quarterly_sculpting']``."""
        return {
            "covenant_use": self.covenant_use,
            "risk_haircut_rule": self.risk_haircut_rule,
            "instalment_quarters": list(self.instalment_quarters),
            "bridge_months": self.bridge_months,
            "bridge_length_years": self.bridge_length_years,
            "bridge_period": (
                dict(self.bridge_period) if self.bridge_period is not None else None
            ),
            "operating_quarters": [dict(row) for row in self.operating_quarters],
            "quarterly_dscr_min": self.quarterly_dscr_min,
            "annual_covenant_dscr_by_year": dict(self.annual_covenant_dscr_by_year),
            "annual_covenant_dscr_min": self.annual_covenant_dscr_min,
            "time_weighted_senior_fee_total_usd": (
                self.time_weighted_senior_fee_total_usd
            ),
            "balloon_remaining_usd": self.balloon_remaining_usd,
            "mixed_sign_haircut_excess_lkr": list(self.mixed_sign_haircut_excess_lkr),
            "assumptions": list(self.assumptions),
        }


def is_quarterly_sculpting_enabled(config: Mapping[str, Any] | None) -> bool:
    """Return True only when ``cashflow.monthly.quarterly_sculpting.enabled`` is True."""
    spec = resolve_monthly_spec(config)
    return (
        spec is not None
        and spec.quarterly_sculpting is not None
        and spec.quarterly_sculpting.enabled
    )


def true_bridge_length_years(spec: MonthlySpec, bridge_months: int) -> float:
    """Return the true sub-annual length of the lead-in bridge in years.

    When ``cod_month`` is declared, sums the exact 365-day calendar lengths of the
    ``bridge_months`` calendar months immediately preceding COD. Otherwise uses
    ``bridge_months / 12``. Returns ``0.0`` when ``bridge_months == 0``.
    """
    if bridge_months == 0:
        return 0.0
    if spec.cod_month is None:
        return bridge_months / float(MONTHS_PER_YEAR)
    days = sum(
        _DAYS_IN_CALENDAR_MONTH[(spec.cod_month - 1 - offset) % MONTHS_PER_YEAR]
        for offset in range(1, bridge_months + 1)
    )
    return days / 365.0


def _resolve_sculpting_assumptions(
    spec: MonthlySpec,
) -> Tuple[Tuple[int, ...], int, List[str]]:
    """Return ``(instalment_quarters, bridge_months, assumptions)``."""
    q_spec = spec.quarterly_sculpting
    assert q_spec is not None
    assumptions: List[str] = []
    if q_spec.instalment_quarters is None:
        instalment_quarters = DEFAULT_INSTALMENT_QUARTERS
        assumptions.append(
            f"{MONTHLY_KEY}.quarterly_sculpting.instalment_quarters not declared: "
            "assumed quarterly end-of-quarter instalments [1, 2, 3, 4] (placeholder "
            "until term-sheet dates from #1399/#1400 are settled)."
        )
    else:
        instalment_quarters = q_spec.instalment_quarters

    if q_spec.bridge_months is None:
        bridge_months = DEFAULT_BRIDGE_MONTHS
        assumptions.append(
            f"{MONTHLY_KEY}.quarterly_sculpting.bridge_months not declared: assumed "
            f"{DEFAULT_BRIDGE_MONTHS} months (half-year bridge)."
        )
    else:
        bridge_months = q_spec.bridge_months

    return instalment_quarters, bridge_months, assumptions


def _quarterly_cfads_and_weights(
    cascade: MonthlyCascade,
    n_years: int,
    scale: float,
) -> Tuple[List[List[float]], Tuple[float, ...]]:
    """Group 12 monthly CFADS and time weights per year into 4 operating quarters."""
    dt_quarters = tuple(
        math.fsum(
            cascade.time_weights[
                q * _MONTHS_PER_QUARTER : (q + 1) * _MONTHS_PER_QUARTER
            ]
        )
        for q in range(QUARTERS_PER_YEAR)
    )
    quarter_cfads: List[List[float]] = []
    for y in range(n_years):
        year_rows = cascade.rows[y * MONTHS_PER_YEAR : (y + 1) * MONTHS_PER_YEAR]
        qs = [
            scale
            * math.fsum(
                float(year_rows[q * _MONTHS_PER_QUARTER + m]["cfads_usd"])
                for m in range(_MONTHS_PER_QUARTER)
            )
            for q in range(QUARTERS_PER_YEAR)
        ]
        quarter_cfads.append(qs)
    return quarter_cfads, dt_quarters


def _sculpt_bridge(
    *,
    tranches: Mapping[str, Tranche],
    obals: Dict[str, float],
    dt_bridge: float,
    bridge_months: int,
    first_year_cfads_usd: float,
    years_io: int,
    target_dscr: float,
) -> Tuple[Dict[str, Any], Dict[str, Tuple[float, float, float]]]:
    """Compute debt service on the true-length bridge period."""
    open_bal = sum(obals.values())
    bridge_cfads = dt_bridge * first_year_cfads_usd
    interest_map = {k: obals[k] * tr.rate * dt_bridge for k, tr in tranches.items()}
    interest_total = sum(interest_map.values())
    # Bridge carries 0.0 senior fee, matching finance.debt.layer (the bridge maps to no
    # operating row, so an operating-row fee there could never reach cashflow_v14).
    bridge_fee = 0.0

    if years_io > 0:
        principal_map = {k: 0.0 for k in tranches}
    else:
        target_svc = (
            max(0.0, (bridge_cfads - bridge_fee) / target_dscr)
            if target_dscr > 0.0
            else 0.0
        )
        principal_total = max(0.0, target_svc - interest_total)
        total_bal = sum(obals.values())
        principal_map = {}
        for k in tranches:
            prorata = obals[k] / total_bal if total_bal > 0.0 else 0.0
            principal_k = min(obals[k], principal_total * prorata)
            obals[k] = max(0.0, obals[k] - principal_k)
            principal_map[k] = principal_k

    principal_sum = sum(principal_map.values())
    service_total = interest_total + principal_sum
    dscr = (bridge_cfads - bridge_fee) / service_total if service_total > 0.0 else None
    close_bal = sum(obals.values())
    bridge_row: Dict[str, Any] = {
        "period_index": 0,
        "period_kind": "bridge",
        "operating_year": None,
        "quarter_in_year": None,
        "period_length_years": dt_bridge,
        "bridge_months": bridge_months,
        "is_instalment": True,
        "opening_balance_usd": open_bal,
        "closing_balance_usd": close_bal,
        "cfads_usd": bridge_cfads,
        "senior_fee_usd": bridge_fee,
        "interest_accrued_usd": interest_total,
        "interest_paid_usd": interest_total,
        "principal_paid_usd": principal_sum,
        "debt_service_usd": service_total,
        "dscr": dscr,
        "calculation_quarters": None,
    }
    tranche_sched = {
        k: (interest_map[k], principal_map[k], interest_map[k] + principal_map[k])
        for k in tranches
    }
    return bridge_row, tranche_sched


def build_quarterly_sculpted_schedule(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    tranches: Mapping[str, Tranche],
    tenor_years: int,
    years_io: int,
    target_dscr: float,
    senior_fee_rate: float = 0.0,
    amortization_style: str = "auto",
    quarterly_cfads_scale: float = 1.0,
) -> QuarterlySculptingResult:
    """Build a quarterly sculpted debt schedule on the monthly CFADS cascade.

    Raises:
        ValueError: If ``cashflow.monthly.quarterly_sculpting.enabled`` is not True,
            if ``amortization_style`` is an annuity style, or if ``senior_fee_rate > 0``
            when ``annual_rows`` already carry non-zero ``senior_fee_lkr``.
    """
    spec = resolve_monthly_spec(config)
    if (
        spec is None
        or spec.quarterly_sculpting is None
        or not spec.quarterly_sculpting.enabled
    ):
        raise ValueError(
            f"{MONTHLY_KEY}.quarterly_sculpting.enabled must be true to build a "
            "quarterly sculpted schedule."
        )
    if str(amortization_style or "").lower() in _AMORT_ANNUITY_STYLES:
        raise ValueError(
            f"Quarterly debt sculpting requires a sculpted amortization_style; "
            f"got {amortization_style!r}."
        )
    if senior_fee_rate > 0.0 and any(
        abs(float(row.get("senior_fee_lkr", 0.0))) > 0.0 for row in annual_rows
    ):
        raise ValueError(
            "annual_rows already carry non-zero senior_fee_lkr while senior_fee_rate "
            "> 0; refusing to double-count credit-support fees inside quarterly sculpting."
        )
    if not math.isfinite(quarterly_cfads_scale) or quarterly_cfads_scale <= 0.0:
        raise ValueError(
            f"quarterly_cfads_scale must be finite and > 0; got {quarterly_cfads_scale!r}."
        )

    instalment_quarters, bridge_months, q_assumptions = _resolve_sculpting_assumptions(
        spec
    )
    instalment_set = frozenset(instalment_quarters)

    cascade = build_monthly_cascade_from_annual_rows(
        config,
        annual_rows,
        risk_haircut_rule=HAIRCUT_RULE_MONTH_ADVERSE,
    )
    n_years = len(annual_rows)
    quarter_cfads, dt_quarters = _quarterly_cfads_and_weights(
        cascade, n_years, quarterly_cfads_scale
    )

    obals = {k: float(tr.principal) for k, tr in tranches.items()}
    annual_aggregated_schedules: Dict[str, List[Tuple[float, float, float]]] = {
        k: [] for k in tranches
    }
    annual_opening_balances_usd: List[float] = []
    annual_senior_fees_usd: List[float] = []
    annual_cfads_usd: List[float] = []

    dt_bridge = true_bridge_length_years(spec, bridge_months)
    bridge_row: Optional[Dict[str, Any]] = None
    next_period_idx = 0

    if bridge_months > 0 and n_years > 0:
        first_year_cfads = math.fsum(quarter_cfads[0])
        bridge_row, bridge_tranche_sched = _sculpt_bridge(
            tranches=tranches,
            obals=obals,
            dt_bridge=dt_bridge,
            bridge_months=bridge_months,
            first_year_cfads_usd=first_year_cfads,
            years_io=years_io,
            target_dscr=target_dscr,
        )
        bridge_row["period_index"] = next_period_idx
        next_period_idx += 1
        annual_opening_balances_usd.append(float(bridge_row["opening_balance_usd"]))
        annual_senior_fees_usd.append(0.0)
        annual_cfads_usd.append(float(bridge_row["cfads_usd"]))
        for k in tranches:
            annual_aggregated_schedules[k].append(bridge_tranche_sched[k])
    else:
        dt_bridge = 0.0

    io_quarters = max(0, min(tenor_years, years_io)) * QUARTERS_PER_YEAR
    operating_quarters: List[Dict[str, Any]] = []
    annual_service_by_year_idx: List[float] = []
    annual_fee_by_year_idx: List[float] = []

    window_cfads = 0.0
    window_fee = 0.0
    window_interest = {k: 0.0 for k in tranches}
    window_quarters = 0

    for y in range(tenor_years):
        year_label = int(annual_rows[y].get("year", y + 1)) if y < n_years else (y + 1)
        annual_opening_balances_usd.append(sum(obals.values()))
        year_cfads = math.fsum(quarter_cfads[y]) if y < n_years else 0.0
        annual_cfads_usd.append(year_cfads)
        year_fee_total = 0.0
        year_service_total = 0.0
        year_tranche_interest = {k: 0.0 for k in tranches}
        year_tranche_principal = {k: 0.0 for k in tranches}

        for q_idx in range(QUARTERS_PER_YEAR):
            quarter_num = q_idx + 1
            op_q_idx = y * QUARTERS_PER_YEAR + q_idx
            dt_q = dt_quarters[q_idx]
            open_bal_q = sum(obals.values())
            cf_q = quarter_cfads[y][q_idx] if y < n_years else 0.0

            # Time-weighted outstanding balance senior fee accrual (#1893 design note 2).
            fee_q = senior_fee_rate * dt_q * open_bal_q
            year_fee_total += fee_q

            accrued_q = {k: obals[k] * tr.rate * dt_q for k, tr in tranches.items()}
            window_cfads += cf_q
            window_fee += fee_q
            for k in tranches:
                window_interest[k] += accrued_q[k]
            window_quarters += 1

            is_instalment = quarter_num in instalment_set
            if not is_instalment:
                int_paid = {k: 0.0 for k in tranches}
                princ_paid = {k: 0.0 for k in tranches}
                svc_paid = 0.0
                dscr_q: Optional[float] = None
                calc_q: Optional[int] = None
            else:
                int_paid = {k: window_interest[k] for k in tranches}
                int_sum = sum(int_paid.values())
                if op_q_idx < io_quarters:
                    princ_paid = {k: 0.0 for k in tranches}
                else:
                    cf_net = window_cfads - window_fee
                    target_svc = (
                        max(0.0, cf_net / target_dscr) if target_dscr > 0.0 else 0.0
                    )
                    princ_total = max(0.0, target_svc - int_sum)
                    total_bal = sum(obals.values())
                    princ_paid = {}
                    for k in tranches:
                        prorata = obals[k] / total_bal if total_bal > 0.0 else 0.0
                        p_k = min(obals[k], princ_total * prorata)
                        obals[k] = max(0.0, obals[k] - p_k)
                        princ_paid[k] = p_k
                svc_paid = int_sum + sum(princ_paid.values())
                dscr_q = (
                    (window_cfads - window_fee) / svc_paid if svc_paid > 0.0 else None
                )
                calc_q = window_quarters
                window_cfads = 0.0
                window_fee = 0.0
                window_interest = {k: 0.0 for k in tranches}
                window_quarters = 0

            for k in tranches:
                year_tranche_interest[k] += int_paid[k]
                year_tranche_principal[k] += princ_paid[k]
            year_service_total += svc_paid

            operating_quarters.append(
                {
                    "period_index": next_period_idx,
                    "period_kind": "operating",
                    "operating_year": year_label,
                    "quarter_in_year": quarter_num,
                    "period_length_years": dt_q,
                    "is_instalment": is_instalment,
                    "opening_balance_usd": open_bal_q,
                    "closing_balance_usd": sum(obals.values()),
                    "cfads_usd": cf_q,
                    "senior_fee_usd": fee_q,
                    "interest_accrued_usd": sum(accrued_q.values()),
                    "interest_paid_usd": sum(int_paid.values()),
                    "principal_paid_usd": sum(princ_paid.values()),
                    "debt_service_usd": svc_paid,
                    "dscr": dscr_q,
                    "calculation_quarters": calc_q,
                }
            )
            next_period_idx += 1

        annual_senior_fees_usd.append(year_fee_total)
        annual_service_by_year_idx.append(year_service_total)
        annual_fee_by_year_idx.append(year_fee_total)
        for k in tranches:
            annual_aggregated_schedules[k].append(
                (
                    year_tranche_interest[k],
                    year_tranche_principal[k],
                    year_tranche_interest[k] + year_tranche_principal[k],
                )
            )

    # Append post-tenor operating years' CFADS so cfads_ext matches full operating life.
    for y in range(tenor_years, n_years):
        annual_cfads_usd.append(math.fsum(quarter_cfads[y]))

    # Annual covenant DSCR beside quarterly DSCR (bridge folded into operating year 1).
    bridge_service = (
        float(bridge_row["debt_service_usd"]) if bridge_row is not None else 0.0
    )
    annual_covenant_dscr_by_year: Dict[Any, Optional[float]] = {}
    for y in range(n_years):
        year_key = annual_rows[y].get("year", y + 1)
        if y >= tenor_years:
            annual_covenant_dscr_by_year[year_key] = None
            continue
        y_cfads = math.fsum(quarter_cfads[y])
        y_fee = annual_fee_by_year_idx[y]
        y_svc = annual_service_by_year_idx[y]
        denom = y_svc + (bridge_service if y == 0 else 0.0)
        annual_covenant_dscr_by_year[year_key] = (
            ((y_cfads - y_fee) / denom) if denom > 0.0 else None
        )

    op_dscrs = [
        float(row["dscr"])
        for row in operating_quarters
        if row["dscr"] is not None and math.isfinite(float(row["dscr"]))
    ]
    cov_dscrs = [
        float(val)
        for val in annual_covenant_dscr_by_year.values()
        if val is not None and math.isfinite(float(val))
    ]
    time_weighted_fee_total = math.fsum(
        float(row["senior_fee_usd"]) for row in operating_quarters
    )

    return QuarterlySculptingResult(
        instalment_quarters=instalment_quarters,
        bridge_months=bridge_months,
        bridge_length_years=dt_bridge,
        bridge_period=bridge_row,
        operating_quarters=tuple(operating_quarters),
        quarterly_dscr_min=min(op_dscrs) if op_dscrs else None,
        annual_covenant_dscr_by_year=annual_covenant_dscr_by_year,
        annual_covenant_dscr_min=min(cov_dscrs) if cov_dscrs else None,
        time_weighted_senior_fee_total_usd=time_weighted_fee_total,
        annual_aggregated_schedules=annual_aggregated_schedules,
        annual_opening_balances_usd=annual_opening_balances_usd,
        annual_senior_fees_usd=annual_senior_fees_usd,
        annual_cfads_usd=annual_cfads_usd,
        balloon_remaining_usd=sum(obals.values()),
        mixed_sign_haircut_excess_lkr=cascade.mixed_sign_haircut_excess_lkr,
        assumptions=cascade.assumptions + tuple(q_assumptions),
    )
