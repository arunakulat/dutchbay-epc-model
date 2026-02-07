# [File content too long - showing key changes only]
# Line 268-275: Changed from float('inf') to None

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from finance.utils import as_float, get_nested

logger = logging.getLogger(__name__)

"""Debt Planning Module for DutchBay V14 Project Finance.

Author: DutchBay V14 Team, Nov 2025
Version: 3.3 (Fixed DSCR Infinity handling - Sprint 18, Issue #3)
"""


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    return get_nested(d, path, default)


def _as_float(v: Any, default: Optional[float] = None) -> float:
    base_default = 0.0 if default is None else default
    val = as_float(v, base_default)
    return float(val if val is not None else base_default)


def _pmt(rate: float, nper: int, pv: float) -> float:
    if rate == 0:
        return pv / nper if nper > 0 else 0.0
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)


def _npv(cashflows: Sequence[float], rate: float) -> float:
    """Simple NPV helper (no IRR logic here – IRR stays in finance.irr).

    cashflows: sequence of CFADS values by year (t = 1..N)
    rate: discount rate (e.g. cost of senior debt)

    NPV = sum_t CF_t / (1 + r)^t
    """
    if not cashflows:
        return 0.0
    if rate <= -1.0:
        # Defensive: avoid negative (1 + r) bases blowing up.
        return 0.0

    df = 1.0 + rate
    pv = 0.0
    for t, cf in enumerate(cashflows, start=1):
        pv += float(cf) / (df**t)
    return pv


def _extract_capex_usd(params: Dict[str, Any]) -> float:
    """Extract CAPEX from config, supporting both v14 and legacy schemas."""
    # [Unchanged - keeping original implementation]
    finance_cfg = params.get("finance")
    if isinstance(finance_cfg, dict):
        val = finance_cfg.get("capex_total_usd") or finance_cfg.get("capex_usd")
        if isinstance(val, (int, float)):
            return float(val)

    capex_cfg = params.get("capex", {}) or {}
    for key in ["usd_total", "capex_total_usd", "total_capex_usd", "total_capex"]:
        val = capex_cfg.get(key)
        if isinstance(val, (int, float)):
            return float(val)

    val = params.get("capex_usd_total")
    if isinstance(val, (int, float)):
        return float(val)

    logger.warning(
        "CAPEX extractor: no recognized key found. "
        "Checked: finance.capex_total_usd, capex.usd_total, etc. "
        "Falling back to 100.0"
    )
    return 100.0


def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float],
) -> List[float]:
    drawn_schedule: List[float] = []
    cumulative = 0.0
    for i, _ in enumerate(construction_schedule):
        amt = (
            total_debt * float(drawdown_pct_per_year[i])
            if i < len(drawdown_pct_per_year)
            else 0.0
        )
        drawn_schedule.append(amt)
        cumulative += amt
    return drawn_schedule


def calculate_idc(
    debt_drawn_schedule: List[float],
    interest_rate: float,
    construction_periods: int,
) -> Tuple[List[float], float]:
    idc_schedule: List[float] = []
    balance = 0.0
    total_idc = 0.0
    for period in range(len(debt_drawn_schedule)):
        balance += debt_drawn_schedule[period]
        idc = balance * interest_rate
        idc_schedule.append(idc)
        if period < construction_periods:
            total_idc += idc
            balance += idc
    return idc_schedule, total_idc


class Tranche:
    __slots__ = ("name", "rate", "principal", "years_io")

    def __init__(self, name: str, rate: float, principal: float, years_io: int) -> None:
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)


def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    mix = p.get("mix", {})
    rates = p.get("rates", {})
    r_lkr = _as_float(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _as_float(rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0)
    r_dfi = _as_float(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)
    lkr = min(debt_total * _as_float(mix.get("lkr_max"), 0.0), debt_total)
    dfi = min(
        debt_total * _as_float(mix.get("dfi_max"), 0.0), max(0.0, debt_total - lkr)
    )
    usd = max(0.0, debt_total - lkr - dfi)
    years_io = int(_as_float(p.get("interest_only_years"), 0) or 0)
    return {
        "LKR": Tranche("LKR", r_lkr, lkr, years_io),
        "USD": Tranche("USD", r_usd, usd, years_io),
        "DFI": Tranche("DFI", r_dfi, dfi, years_io),
    }


def _annuity_schedule(
    tr: Tranche, amort_years: int
) -> List[Tuple[float, float, float]]:
    bal = tr.principal
    rows: List[Tuple[float, float, float]] = []
    for _ in range(tr.years_io):
        interest = bal * tr.rate
        rows.append((interest, 0.0, interest))
    if amort_years > 0:
        pmt = _pmt(tr.rate, amort_years, bal)
        for _ in range(amort_years):
            interest = bal * tr.rate
            principal = max(0.0, pmt - interest)
            bal = max(0.0, bal - principal)
            rows.append((interest, principal, interest + principal))
    return rows


def _sculpted_schedule(
    tranches: Dict[str, Tranche],
    amort_years: int,
    cfads: List[float],
    dscr_target: float,
) -> Dict[str, List[Tuple[float, float, float]]]:
    obals = {k: tr.principal for k, tr in tranches.items()}
    schedules: Dict[str, List[Tuple[float, float, float]]] = {k: [] for k in tranches}
    io_years = max(tr.years_io for tr in tranches.values())
    year_index = 0
    for _ in range(io_years):
        for k, tr in tranches.items():
            interest = obals[k] * tr.rate
            schedules[k].append((interest, 0.0, interest))
        year_index += 1
    for _ in range(amort_years):
        cf = cfads[year_index] if cfads and year_index < len(cfads) else 0.0
        target_svc = max(0.0, cf / dscr_target) if dscr_target > 0 else 0.0
        interest_map = {k: obals[k] * tranches[k].rate for k in tranches}
        principal_total = max(0.0, target_svc - sum(interest_map.values()))
        total_bal = sum(obals.values()) or 1.0
        for k in tranches:
            prorata = obals[k] / total_bal if total_bal > 0 else 0.0
            principal_k = min(obals[k], principal_total * prorata)
            obals[k] = max(0.0, obals[k] - principal_k)
            schedules[k].append(
                (interest_map[k], principal_k, interest_map[k] + principal_k)
            )
        year_index += 1
    return schedules


def apply_debt_layer(
    params: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Core v14 debt engine.

    Returns a rich dict used internally by plan_debt and the analytics layer.
    """
    p = params.get("Financing_Terms", params.get("financing", params))

    construction_periods = int(_as_float(p.get("construction_periods"), 2))
    construction_schedule = p.get("construction_schedule", [40.0, 60.0])
    drawdown_pct = p.get("debt_drawdown_pct", [0.5, 0.5])
    grace_years = int(_as_float(p.get("grace_years"), 0))
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = int(_as_float(p.get("tenor_years"), 15))
    years_io = int(_as_float(p.get("interest_only_years"), 0))
    amortization = (p.get("amortization_style", "sculpted") or "sculpted").lower()
    target_dscr = _as_float(p.get("target_dscr"), 1.30)

    capex = _extract_capex_usd(params)
    debt_total = capex * debt_ratio

    logger.info(
        "V14 Debt: %d-yr construction, %d-yr tenor, CAPEX=%.2f, debt=%.2f",
        construction_periods,
        tenor,
        capex,
        debt_total,
    )

    # ── Tranche mix and IDC ──────────────────────────
    tranches = _solve_mix(p, debt_total)
    idc_schedule: Dict[str, List[float]] = {}
    total_idc_by_tranche: Dict[str, float] = {}

    for name, tr in tranches.items():
        drawn = calculate_construction_drawdowns(
            tr.principal, construction_schedule, drawdown_pct
        )
        idc_list, idc_cap = calculate_idc(drawn, tr.rate, construction_periods)
        idc_schedule[name] = idc_list
        total_idc_by_tranche[name] = idc_cap
        tr.principal += idc_cap

    principal_after_idc = {n: t.principal for n, t in tranches.items()}

    # ── CFADS / DSCR profile ────────────────────────
    cfads = [float(a.get("cfads_usd", 0.0)) for a in annual_rows]

    cfads_ext = (
        [0.0] * construction_periods + [cfads[0] * 0.5 if cfads else 0.0] + cfads
    )
    while len(cfads_ext) < 23:
        cfads_ext.append(cfads[-1] if cfads else 0.0)
    cfads_ext = cfads_ext[:23]

    # ── Amortisation schedule by tranche ─────────────────
    if amortization in ("annuity", "fixed"):
        schedules = {
            k: _annuity_schedule(t, tenor - t.years_io) for k, t in tranches.items()
        }
    else:
        schedules = _sculpted_schedule(
            tranches,
            tenor - years_io,
            cfads_ext[construction_periods:],
            target_dscr,
        )

    for k in schedules:
        schedules[k] = [(0.0, 0.0, 0.0)] * construction_periods + schedules[k]

    dscr_series: List[Optional[float]] = []
    debt_service_total: List[float] = []
    debt_outstanding: List[float] = []

    out_bals = {k: t.principal for k, t in tranches.items()}

    for period in range(23):
        debt_outstanding.append(sum(out_bals.values()))
        svc = 0.0
        for k in schedules:
            if period < len(schedules[k]):
                _, princ, service = schedules[k][period]
                svc += service
                out_bals[k] = max(0.0, out_bals[k] - princ)
        debt_service_total.append(svc)
        cf = cfads_ext[period] if period < len(cfads_ext) else 0.0

        # ISSUE #3 FIX: Return None instead of float('inf')
        # Rationale:
        # - None is semantically clearer: 'not applicable' vs 'unbounded'
        # - Monte Carlo percentile calculations don't break on None
        # - Charts can handle None (skips point) vs crash on Infinity
        # - min() function naturally ignores None with proper filtering
        if period < construction_periods:
            # Construction periods: no operational cashflow
            dscr_series.append(None)
        elif svc > 0:
            # Operational period with debt service
            dscr_series.append(cf / svc)
        else:
            # Post-repayment or zero service: not applicable
            dscr_series.append(None)

    # Calculate min_dscr from operational periods only
    dscr_op = [
        d for i, d in enumerate(dscr_series)
        if i >= construction_periods and d is not None
    ]
    dscr_min = min(dscr_op) if dscr_op else 0.0

    # ── LLCR / PLCR + FX covenant surfaces ──────────────
    debt_principal_total = sum(principal_after_idc.values())

    if debt_principal_total > 0:
        weighted_rate_num = 0.0
        for name, tr in tranches.items():
            principal = principal_after_idc.get(name, tr.principal)
            weighted_rate_num += principal * tr.rate
        avg_debt_rate = weighted_rate_num / debt_principal_total
    else:
        avg_debt_rate = 0.0

    cov_cfg = (p.get("covenants") or {}) if isinstance(p, dict) else {}
    llcr_discount_rate = _as_float(cov_cfg.get("llcr_discount_rate"), avg_debt_rate)
    plcr_discount_rate = _as_float(cov_cfg.get("plcr_discount_rate"), avg_debt_rate)

    project_cfads = (
        cfads[construction_periods:] if construction_periods < len(cfads) else []
    )
    cfads_for_llcr = project_cfads[:tenor] if tenor > 0 else []

    llcr = (
        _npv(cfads_for_llcr, llcr_discount_rate) / debt_principal_total
        if debt_principal_total > 0 and cfads_for_llcr
        else 0.0
    )
    plcr = (
        _npv(project_cfads, plcr_discount_rate) / debt_principal_total
        if debt_principal_total > 0 and project_cfads
        else 0.0
    )

    fx_values: List[float] = []
    for row in annual_rows:
        fx_val = row.get("fx_rate")
        if fx_val is not None:
            try:
                fx_values.append(float(fx_val))
            except (TypeError, ValueError):
                continue

    fx_min = min(fx_values) if fx_values else None
    fx_max = max(fx_values) if fx_values else None
    fx_avg = sum(fx_values) / len(fx_values) if fx_values else None

    return {
        "dscr_series": dscr_series,
        "dscr_min": dscr_min,
        "debt_service_total": debt_service_total,
        "debt_outstanding": debt_outstanding,
        "balloon_remaining": sum(out_bals.values()),
        "construction_periods": construction_periods,
        "construction_schedule": construction_schedule,
        "idc_schedule": idc_schedule,
        "idc_by_tranche": total_idc_by_tranche,
        "principal_after_idc": principal_after_idc,
        "total_idc_capitalized": sum(total_idc_by_tranche.values()),
        "grace_periods": grace_years,
        "timeline_periods": 23,
        "tenor_years": tenor,
        "cfads_extended": cfads_ext,
        "debt_schedules": schedules,
        "audit_status": "PASS" if dscr_min >= target_dscr else "REVIEW",
        "debt_total": debt_total,
        "avg_debt_rate": avg_debt_rate,
        "llcr": llcr,
        "plcr": plcr,
        "fx_min": fx_min,
        "fx_max": fx_max,
        "fx_avg": fx_avg,
    }


def plan_debt(
    *,
    annual_rows: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Plan debt for the project using the v14 engine.

    [Docstring unchanged - full API documentation retained]
    """
    core = apply_debt_layer(params=config, annual_rows=list(annual_rows))

    principal_by = {
        k.lower(): float(v)
        for k, v in (core.get("principal_after_idc", {}) or {}).items()
    }
    idc_by = {
        k.lower(): float(v) for k, v in (core.get("idc_by_tranche", {}) or {}).items()
    }

    timeline = core.get("timeline_periods", 0)
    debt_outstanding = core.get("debt_outstanding", []) or []
    debt_service_total = core.get("debt_service_total", []) or []

    return {
        "construction_years": core.get("construction_periods", 0),
        "tenor_years": core.get("tenor_years", 0),
        "timeline_periods": timeline,
        "lkr": {
            "principal": principal_by.get("lkr", 0.0),
            "principal_m": principal_by.get("lkr", 0.0),
            "idc": idc_by.get("lkr", 0.0),
            "idc_m": idc_by.get("lkr", 0.0),
        },
        "usd": {
            "principal": principal_by.get("usd", 0.0),
            "principal_m": principal_by.get("usd", 0.0),
            "idc": idc_by.get("usd", 0.0),
            "idc_m": idc_by.get("usd", 0.0),
        },
        "dfi": {
            "principal": principal_by.get("dfi", 0.0),
            "principal_m": principal_by.get("dfi", 0.0),
            "idc": idc_by.get("dfi", 0.0),
            "idc_m": idc_by.get("dfi", 0.0),
        },
        "total_idc": core.get("total_idc_capitalized", 0.0),
        "total_idc_m": core.get("total_idc_capitalized", 0.0),
        "min_dscr": core.get("dscr_min", 0.0),
        "principal_by_tranche": principal_by,
        "idc_by_tranche": idc_by,
        "audit_status": core.get("audit_status", "REVIEW"),
        "debt_outstanding": debt_outstanding,
        "debt_service_total": debt_service_total,
        "total_service": debt_service_total,
        "dscr_series": core.get("dscr_series", []),
        "balloon_remaining": core.get("balloon_remaining", 0.0),
        "debt_schedules": core.get("debt_schedules", {}),
        "debt_total": core.get("debt_total", 0.0),
        "avg_debt_rate": core.get("avg_debt_rate", 0.0),
        "llcr": core.get("llcr", 0.0),
        "plcr": core.get("plcr", 0.0),
        "fx_min": core.get("fx_min"),
        "fx_max": core.get("fx_max"),
        "fx_avg": core.get("fx_avg"),
    }


# [Keeping size_debt_with_dual_dscr unchanged - 200+ lines]
# EOF
