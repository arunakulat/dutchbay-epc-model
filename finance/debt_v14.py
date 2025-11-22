"""Debt Planning Module for DutchBay V14 Project Finance

ENHANCEMENTS IN V14:
--------------------
- Multi-year construction period with debt drawdown
- Interest During Construction (IDC) capitalization
- 23-period timeline (construction + transition + operations)
- Grace period handling for operations
- Enhanced DSCR calculation

ORIGINAL V13 FEATURES:
----------------------
- Multi-currency tranches: LKR, USD commercial, DFI
- Interest-only (grace) period, annuity/sculpted amortization
- YAML-driven validation for all banking covenants
- Balloon payment refinancing analysis

Author: DutchBay V14 Team, Nov 2025
Version: 3.0 (V14 construction period support)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Sequence

from finance.utils import as_float, get_nested

logger = logging.getLogger("dutchbay.v14chat.finance.debt")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    """Backward-compatible shim over finance.utils.get_nested."""
    return get_nested(d, path, default)


def _as_float(v: Any, default: Optional[float] = None) -> float:
    """Backward-compatible shim over finance.utils.as_float."""
    return float(as_float(v, default or 0.0))


def _pmt(rate: float, nper: int, pv: float) -> float:
    """Calculate annuity payment (Excel PMT equivalent)."""
    if rate == 0:
        return pv / nper if nper > 0 else 0.0
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)


# ============================================================================
# NEW V14: CONSTRUCTION PERIOD FUNCTIONS
# ============================================================================


def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float],
) -> List[float]:
    """
    Calculate debt drawdown during construction periods.

    Parameters
    ----------
    total_debt:
        Total debt amount available.
    construction_schedule:
        Capex per construction year [Year1, Year2, ...] – used for sanity only.
    drawdown_pct_per_year:
        Fraction of total debt to draw each year [0.5, 0.5, ...].

    Returns
    -------
    list[float]
        Drawn amount per construction period.
    """
    drawn_schedule: List[float] = []
    cumulative_drawn = 0.0

    for year_idx, _capex in enumerate(construction_schedule):
        if year_idx < len(drawdown_pct_per_year):
            drawn_this_year = total_debt * float(drawdown_pct_per_year[year_idx])
        else:
            drawn_this_year = 0.0

        drawn_schedule.append(drawn_this_year)
        cumulative_drawn += drawn_this_year

    if cumulative_drawn > total_debt:
        logger.warning(
            "Total drawn %.2f exceeds total debt %.2f", cumulative_drawn, total_debt
        )

    return drawn_schedule


def calculate_idc(
    debt_drawn_schedule: List[float],
    interest_rate: float,
    construction_periods: int,
) -> Tuple[List[float], float]:
    """
    Calculate Interest During Construction (IDC), capitalized into the balance.

    Parameters
    ----------
    debt_drawn_schedule:
        Debt drawn each construction period.
    interest_rate:
        Annual interest rate for tranche.
    construction_periods:
        Number of construction periods.

    Returns
    -------
    (idc_schedule, total_idc_capitalized)
    """
    idc_schedule: List[float] = []
    outstanding_balance = 0.0
    total_idc_capitalized = 0.0

    for period in range(len(debt_drawn_schedule)):
        outstanding_balance += debt_drawn_schedule[period]
        idc_this_period = outstanding_balance * interest_rate
        idc_schedule.append(idc_this_period)

        if period < construction_periods:
            total_idc_capitalized += idc_this_period
            outstanding_balance += idc_this_period

    return idc_schedule, total_idc_capitalized


# ============================================================================
# TRANCHE DEFINITION
# ============================================================================


class Tranche:
    """Represents a single debt tranche."""

    __slots__ = ("name", "rate", "principal", "years_io")

    def __init__(self, name: str, rate: float, principal: float, years_io: int) -> None:
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)


def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    """Solve tranche mix based on YAML constraints (v13 logic preserved)."""
    mix = p.get("mix", {})
    rates = p.get("rates", {})

    mix_lkr_max = _as_float(mix.get("lkr_max"), 0.0)
    mix_dfi_max = _as_float(mix.get("dfi_max"), 0.0)
    mix_usd_min = _as_float(mix.get("usd_commercial_min"), 0.0)

    r_lkr = _as_float(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _as_float(rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0)
    r_dfi = _as_float(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)

    # Base allocation
    lkr_amt = min(debt_total * mix_lkr_max, debt_total)
    dfi_amt = min(debt_total * mix_dfi_max, max(0.0, debt_total - lkr_amt))
    usd_amt = max(0.0, debt_total - lkr_amt - dfi_amt)

    # Enforce USD minimum
    min_usd_amt = debt_total * mix_usd_min
    if usd_amt < min_usd_amt:
        need = min_usd_amt - usd_amt

        pull_lkr = min(need, lkr_amt)
        lkr_amt -= pull_lkr
        need -= pull_lkr

        if need > 0:
            pull_dfi = min(need, dfi_amt)
            dfi_amt -= pull_dfi

        usd_amt = max(0.0, debt_total - lkr_amt - dfi_amt)

    years_io = int(_as_float(p.get("interest_only_years"), 0) or 0)

    return {
        "LKR": Tranche("LKR", r_lkr, lkr_amt, years_io),
        "USD": Tranche("USD", r_usd, usd_amt, years_io),
        "DFI": Tranche("DFI", r_dfi, dfi_amt, years_io),
    }


# ============================================================================
# AMORTIZATION SCHEDULES
# ============================================================================


def _annuity_schedule(tr: Tranche, amort_years: int) -> List[Tuple[float, float, float]]:
    """
    Build annuity schedule.

    Returns rows as (interest, principal, total_service).
    """
    n = amort_years
    bal = tr.principal
    rows: List[Tuple[float, float, float]] = []

    # Interest-only period
    for _ in range(tr.years_io):
        interest = bal * tr.rate
        rows.append((interest, 0.0, interest))

    # Amortization period
    if n > 0:
        pmt = _pmt(tr.rate, n, bal)
        for _ in range(n):
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
    """
    Build sculpted schedule targeting DSCR.

    Returns mapping: tranche_name -> list of (interest, principal, total_service).
    """
    obals = {k: tr.principal for k, tr in tranches.items()}
    schedules: Dict[str, List[Tuple[float, float, float]]] = {k: [] for k in tranches}
    io_years = max(tr.years_io for tr in tranches.values())
    year_index = 0

    # Interest-only period
    for _ in range(io_years):
        for k, tr in tranches.items():
            bal = obals[k]
            interest = bal * tr.rate
            schedules[k].append((interest, 0.0, interest))
        year_index += 1

    # Amortization period
    for _ in range(amort_years):
        if cfads:
            cf = cfads[year_index] if year_index < len(cfads) else cfads[-1]
        else:
            cf = 0.0

        target_service = max(0.0, cf / dscr_target) if dscr_target > 0 else 0.0

        interest_map = {k: obals[k] * tranches[k].rate for k in tranches}
        total_interest = sum(interest_map.values())
        principal_total = max(0.0, target_service - total_interest)

        total_bal = sum(obals.values()) or 1.0
        for k, tr in tranches.items():
            bal = obals[k]
            prorata = bal / total_bal if total_bal > 0 else 0.0
            principal_k = min(bal, principal_total * prorata)
            interest_k = interest_map[k]
            obals[k] = max(0.0, bal - principal_k)
            schedules[k].append((interest_k, principal_k, interest_k + principal_k))

        year_index += 1

    return schedules


# ============================================================================
# CORE ENGINE (V14)
# ============================================================================


def apply_debt_layer(params: Dict[str, Any], annual_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply debt financing layer with V14 construction period support.

    Parameters
    ----------
    params:
        Scenario configuration dictionary; must contain a Financing_Terms / financing
        block and a capex.usd_total field.
    annual_rows:
        Per-period rows produced by v14 cashflow (build_annual_rows).

    Returns
    -------
    Dict[str, Any]
        Core engine outputs used by higher layers and tests.
    """
    # Extract financing params
    p = params.get("Financing_Terms", params.get("financing", params))

    # ---------- CONSTRUCTION PARAMETERS ----------
    construction_periods = int(_as_float(p.get("construction_periods"), 2))
    construction_schedule = p.get("construction_schedule", [40.0, 60.0])
    drawdown_pct = p.get("debt_drawdown_pct", [0.5, 0.5])
    grace_years = int(_as_float(p.get("grace_years"), 0))

    # ---------- STANDARD PARAMETERS ----------
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = int(_as_float(p.get("tenor_years"), 15))
    years_io = int(_as_float(p.get("interest_only_years"), 0))
    amortization = (p.get("amortization_style", "sculpted") or "sculpted").lower()
    target_dscr = _as_float(p.get("target_dscr"), 1.30)

    capex = float(params.get("capex", {}).get("usd_total", 100.0))
    debt_total = capex * debt_ratio

    logger.info(
        "V14 Debt Planning: %d-year construction, %d-year tenor",
        construction_periods,
        tenor,
    )

    # ---------- TRANCHE MIX + IDC ----------
    tranches = _solve_mix(p, debt_total)

    idc_schedule: Dict[str, List[float]] = {}
    total_idc_by_tranche: Dict[str, float] = {}

    for tranche_name, tranche in tranches.items():
        drawn = calculate_construction_drawdowns(
            tranche.principal,
            construction_schedule,
            drawdown_pct,
        )

        idc_per_period, total_idc_cap = calculate_idc(
            drawn,
            tranche.rate,
            construction_periods,
        )

        idc_schedule[tranche_name] = idc_per_period
        total_idc_by_tranche[tranche_name] = total_idc_cap

        tranche.principal += total_idc_cap
        logger.info(
            "  %s: Principal $%.2fM (IDC: $%.2fM)",
            tranche_name,
            tranche.principal,
            total_idc_cap,
        )

    principal_after_idc = {name: tr.principal for name, tr in tranches.items()}

    # ---------- EXTEND CFADS TO 23 PERIODS ----------
    cfads = [a.get("cfads_usd", 0.0) for a in annual_rows]

    cfads_extended: List[float] = []
    # Construction periods: 0 CFADS
    for _ in range(construction_periods):
        cfads_extended.append(0.0)

    # Transition period: partial CFADS (50%)
    if cfads:
        cfads_extended.append(cfads[0] * 0.5)
    else:
        cfads_extended.append(0.0)

    # Operational periods: full CFADS
    cfads_extended.extend(cfads)

    # Ensure exactly 23 periods
    while len(cfads_extended) < 23:
        cfads_extended.append(cfads[-1] if cfads else 0.0)
    cfads_extended = cfads_extended[:23]

    # ---------- BUILD SCHEDULES ----------
    if amortization in ("annuity", "fixed"):
        schedules: Dict[str, List[Tuple[float, float, float]]] = {
            k: _annuity_schedule(tr, tenor - tr.years_io) for k, tr in tranches.items()
        }
    else:
        schedules = _sculpted_schedule(
            tranches,
            tenor - years_io,
            cfads_extended[construction_periods:],
            target_dscr,
        )

    # Pad schedules with construction-period zeros
    for k in schedules:
        padded = [(0.0, 0.0, 0.0)] * construction_periods + schedules[k]
        schedules[k] = padded

    # ---------- COMPUTE METRICS OVER 23 PERIODS ----------
    dscr_series: List[float] = []
    debt_service_total: List[float] = []
    debt_outstanding: List[float] = []

    outstanding_balances = {k: tr.principal for k, tr in tranches.items()}

    for period in range(23):
        total_outstanding = sum(outstanding_balances.values())
        debt_outstanding.append(total_outstanding)

        total_service = 0.0
        for k in schedules:
            if period < len(schedules[k]):
                interest, principal, service = schedules[k][period]
                total_service += service
                outstanding_balances[k] = max(
                    0.0, outstanding_balances[k] - principal
                )

        debt_service_total.append(total_service)

        if period < len(cfads_extended):
            cfads_this_period = cfads_extended[period]
        else:
            cfads_this_period = 0.0

        if period >= construction_periods and total_service > 0:
            dscr = cfads_this_period / total_service
        else:
            dscr = float("inf")

        dscr_series.append(dscr)

    dscr_operational = [
        d for i, d in enumerate(dscr_series) if i >= construction_periods and d < float("inf")
    ]
    dscr_min = min(dscr_operational) if dscr_operational else 0.0

    balloon_remaining = sum(outstanding_balances.values())
    total_idc_capitalized = sum(total_idc_by_tranche.values())

    logger.info(
        "V14 Results: Min DSCR=%.2f, Total IDC=$%.2fM",
        dscr_min,
        total_idc_capitalized,
    )

    audit_status = "PASS" if dscr_min >= 1.30 else "REVIEW"

    return {
        # Time-series metrics
        "dscr_series": dscr_series,
        "dscr_min": dscr_min,
        "debt_service_total": debt_service_total,
        "debt_outstanding": debt_outstanding,
        "balloon_remaining": balloon_remaining,
        # V14 structural fields
        "construction_periods": construction_periods,
        "construction_schedule": construction_schedule,
        "idc_schedule": idc_schedule,
        "idc_by_tranche": total_idc_by_tranche,
        "principal_after_idc": principal_after_idc,
        "total_idc_capitalized": total_idc_capitalized,
        "grace_periods": grace_years,
        "timeline_periods": 23,
        "tenor_years": tenor,
        "cfads_extended": cfads_extended,
        "debt_schedules": schedules,
        # Validation / diagnostics
        "validation_warnings": [],
        "dscr_violations": [],
        "balloon_warnings": [],
        "audit_status": audit_status,
    }


# ============================================================================
# PUBLIC V14 ENTRY POINT (USED BY TESTS)
# ============================================================================


def plan_debt(
    *,
    annual_rows: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stable v14 debt-planning API.

    This is a thin wrapper around ``apply_debt_layer`` that:

      * feeds the raw scenario config into the engine,
      * derives construction / tenor years, and
      * exposes tranche-level principal + IDC totals in a pinned shape.

    It is what tests/api/test_debt_construction_idc_regression.py calls.
    """
    # 1) Run core engine
    core = apply_debt_layer(params=config, annual_rows=list(annual_rows))

    # 2) High-level timeline
    construction_years = int(core.get("construction_periods", 0))
    tenor_years = int(core.get("tenor_years", 0))
    timeline_periods = int(core.get("timeline_periods", 0))

    if tenor_years <= 0 and timeline_periods > 0:
        tenor_years = max(timeline_periods - construction_years, 0)

    # 3) Tranche-level aggregates
    principal_by_tranche: Dict[str, float] = {
        k: float(v) for k, v in (core.get("principal_after_idc", {}) or {}).items()
    }
    idc_by_tranche: Dict[str, float] = {
        k: float(v) for k, v in (core.get("idc_by_tranche", {}) or {}).items()
    }

    def _p(tranche: str) -> float:
        return float(principal_by_tranche.get(tranche, 0.0))

    def _i(tranche: str) -> float:
        return float(idc_by_tranche.get(tranche, 0.0))

    lkr_principal = _p("LKR")
    usd_principal = _p("USD")
    dfi_principal = _p("DFI")

    lkr_idc = _i("LKR")
    usd_idc = _i("USD")
    dfi_idc = _i("DFI")

    total_idc = lkr_idc + usd_idc + dfi_idc
    if "total_idc_capitalized" in core:
        total_idc = float(core.get("total_idc_capitalized", total_idc))

    min_dscr = float(core.get("dscr_min", 0.0))

    # 4) Shape the result to match the regression tests' expectations
    result: Dict[str, Any] = {
        # Pinned high-level fields
        "construction_years": construction_years,
        "tenor_years": tenor_years,
        "timeline_periods": timeline_periods,
        # Nested tranche summaries (what _extract_tranche(...) expects)
        "lkr": {
            "principal": lkr_principal,
            "principal_m": lkr_principal,
            "idc": lkr_idc,
            "idc_m": lkr_idc,
        },
        "usd": {
            "principal": usd_principal,
            "principal_m": usd_principal,
            "idc": usd_idc,
            "idc_m": usd_idc,
        },
        "dfi": {
            "principal": dfi_principal,
            "principal_m": dfi_principal,
            "idc": dfi_idc,
            "idc_m": dfi_idc,
        },
        "total_idc": total_idc,
        "min_dscr": min_dscr,
        # Compatibility / richer fields
        "construction_periods": core.get("construction_periods"),
        "grace_periods": core.get("grace_periods"),
        "construction_schedule": core.get("construction_schedule"),
        "principal_by_tranche": principal_by_tranche,
        "idc_by_tranche": idc_by_tranche,
        "cfads_extended": core.get("cfads_extended"),
        "debt_schedules": core.get("debt_schedules"),
        "debt_outstanding": core.get("debt_outstanding"),
        "debt_service_total": core.get("debt_service_total"),
        "balloon_remaining": core.get("balloon_remaining"),
        "audit_status": core.get("audit_status", "REVIEW"),
        # Extra flat fields for analytics / workbook layers
        "lkr_principal": lkr_principal,
        "usd_principal": usd_principal,
        "dfi_principal": dfi_principal,
        "lkr_idc": lkr_idc,
        "usd_idc": usd_idc,
        "dfi_idc": dfi_idc,
        "total_idc_capitalized": total_idc,
    }

    return result
