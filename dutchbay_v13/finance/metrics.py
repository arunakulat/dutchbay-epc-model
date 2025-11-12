# dutchbay_v13/finance/metrics.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

# Single point of truth for IRR math lives in finance/irr.py
from .irr import irr, build_project_cashflows, build_equity_cashflows

__all__ = [
    "compute_dscr_series",
    "summarize_dscr",
    "compute_llcr_plcr",
    "summarize_project_metrics",
]


def _to_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(x) if x is not None else default
    except Exception:
        return default


def compute_dscr_series(annual_rows: List[Dict[str, Any]]) -> List[Optional[float]]:
    """
    DSCR_t = CFADS_t / DebtService_t
    Expects per-row:
      - 'cfads_usd' (preferred)
      - 'debt_service' (interest + principal)
    Returns None for years where DSCR is undefined (e.g., no debt service).
    """
    series: List[Optional[float]] = []
    for row in annual_rows:
        ds = _to_float(row.get("debt_service"))
        cfads = _to_float(row.get("cfads_usd"))
        if ds is None or ds == 0 or cfads is None:
            series.append(None)
        else:
            series.append(cfads / ds)
    return series


def summarize_dscr(
    dscr_series: Iterable[Optional[float]],
    min_dscr: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    vals = [v for v in dscr_series if isinstance(v, (int, float))]
    if not vals:
        return {"dscr_min": None, "dscr_avg": None, "dscr_breach_years": None}
    dscr_min = min(vals)
    dscr_avg = sum(vals) / len(vals)
    breaches = None if min_dscr is None else sum(1 for v in vals if v < float(min_dscr))
    return {"dscr_min": dscr_min, "dscr_avg": dscr_avg, "dscr_breach_years": breaches}


def _pv(cashflows: Iterable[float], discount_rate: float) -> float:
    total = 0.0
    r = float(discount_rate)
    for t, cf in enumerate(cashflows, start=1):
        total += float(cf) / ((1.0 + r) ** t)
    return total


def compute_llcr_plcr(
    annual_rows: List[Dict[str, Any]],
    discount_rate: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """
    LLCR ≈ PV(CFADS over debt tenor) / Opening Debt
    PLCR ≈ PV(CFADS over project life) / Opening Debt
    Requires:
      - 'cfads_usd' in rows,
      - opening debt balance in the first ops year: one of
        'debt_opening_balance' | 'opening_debt_usd' | 'debt_balance_start'
      - discount_rate (if None → (None, None))
    """
    if discount_rate is None:
        return (None, None)

    cfads_all = [ _to_float(r.get("cfads_usd"), 0.0) or 0.0 for r in annual_rows ]
    if not any(cfads_all):
        return (None, None)

    opening_debt: Optional[float] = None
    for r in annual_rows:
        opening_debt = (
            _to_float(r.get("debt_opening_balance"))
            or _to_float(r.get("opening_debt_usd"))
            or _to_float(r.get("debt_balance_start"))
        )
        if opening_debt is not None:
            break

    if opening_debt is None or opening_debt <= 0:
        return (None, None)

    pv_full = _pv(cfads_all, float(discount_rate))
    cfads_tenor = [
        (_to_float(r.get("cfads_usd"), 0.0) or 0.0)
        for r in annual_rows
        if r.get("in_debt_tenor") is True
    ]
    pv_tenor = _pv(cfads_tenor, float(discount_rate)) if cfads_tenor else pv_full

    llcr = pv_tenor / opening_debt
    plcr = pv_full / opening_debt
    return (llcr, plcr)


def summarize_project_metrics(
    *,
    capex_t0_usd: float,
    annual_rows: List[Dict[str, Any]],
    discount_rate: Optional[float] = None,
    min_dscr: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Summary pack for reporting: IRRs + DSCR + optional LLCR/PLCR.
    Expects 'equity_cf' and 'cfads_usd' in rows for IRR/DSCR; optional tenor markers for LLCR.
    """
    proj_cfs = build_project_cashflows(capex_t0_usd, annual_rows)
    eq_cfs = build_equity_cashflows(capex_t0_usd, annual_rows)

    project_irr = irr(proj_cfs)
    equity_irr = irr(eq_cfs)

    dscr_series = compute_dscr_series(annual_rows)
    dscr_summary = summarize_dscr(dscr_series, min_dscr=min_dscr)

    llcr, plcr = compute_llcr_plcr(annual_rows, discount_rate)

    return {
        "equity_irr": equity_irr,
        "project_irr": project_irr,
        "dscr_min": dscr_summary["dscr_min"],
        "dscr_avg": dscr_summary["dscr_avg"],
        "dscr_breach_years": dscr_summary["dscr_breach_years"],
        "llcr": llcr,
        "plcr": plcr,
    }

    