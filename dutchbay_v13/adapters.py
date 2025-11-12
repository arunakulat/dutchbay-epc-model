from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

# Core finance primitives live in finance/*
from .finance.irr import irr, npv
from .finance.debt import apply_debt_layer


# -----------------------
# small safe-read helpers
# -----------------------
def _get(d: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


# ---------------
# param utilities
# ---------------
def _capacity_mw(p: Dict[str, Any]) -> float:
    val = _get(p, ["project", "capacity_mw"])
    if val is None:
        val = p.get("capacity_mw")
    return float(val) if val is not None else 1.0


def _lifetime_years(p: Dict[str, Any]) -> int:
    yrs = _get(p, ["project", "timeline", "lifetime_years"])
    if yrs is None:
        yrs = p.get("lifetime_years")
    return int(_as_float(yrs, 25) or 25)


def _capex_usd_total(p: Dict[str, Any]) -> float:
    # Prefer explicit capex.usd_total; otherwise derive from usd_per_mw * capacity.
    total = _get(p, ["capex", "usd_total"])
    if total is not None:
        return float(total)
    per_mw = _as_float(_get(p, ["capex", "usd_per_mw"]), None)
    if per_mw is not None:
        return float(per_mw) * _capacity_mw(p)
    # Last resort: look for legacy keys
    legacy_total = p.get("capex_musd")
    if legacy_total is not None:
        return float(legacy_total) * 1_000_000.0
    # If nothing is provided, treat as 0 to avoid None math
    return 0.0


# -------------------------
# public adapter entrypoint
# -------------------------
def run_irr(params: Dict[str, Any], annual: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    High-level orchestration for IRR/NPV:
      * Uses provided annual rows if passed (expects 'cfads_usd' per year).
      * If debt_ratio > 0, applies the debt layer and subtracts debt service to form equity cashflows.
      * Computes project IRR on [-CAPEX] + CFADS; equity IRR on [-equity_contrib] + equity_CF.

    Returns a mapping with:
      equity_irr, project_irr, npv_12 (discount from params.metrics.npv_discount_rate or 0.12),
      dscr_min, balloon_remaining, debt_service, and normalized annual rows with equity_cf.
    """
    years = _lifetime_years(params)
    capex = _capex_usd_total(params)

    # normalize 'annual' rows to the model horizon
    rows: List[Dict[str, float]] = []
    if annual and isinstance(annual, list):
        for i in range(years):
            r = annual[i] if i < len(annual) else {}
            cfads = _as_float(r.get("cfads_usd"), 0.0) or 0.0
            rows.append({"year": float(i + 1), "cfads_usd": float(cfads)})
    else:
        # no builder here; if nothing is given we fall back to zeros to keep function total
        for i in range(years):
            rows.append({"year": float(i + 1), "cfads_usd": 0.0})

    # financing terms (can be under Financing_Terms or financing)
    fin = (params.get("Financing_Terms") or params.get("financing") or {})
    debt_ratio = _as_float(fin.get("debt_ratio"), 0.0) or 0.0

    # --------------------------
    # build equity cashflows
    # --------------------------
    equity_cf: List[float] = []
    debt_service: List[float] = []
    dscr_min: Optional[float] = None
    balloon: float = 0.0

    if debt_ratio > 0.0:
        # Let the debt layer do its job (sculpt/annuity, DSRA/guarantees, etc.).
        # Contract: it returns aligned 'equity_cf' and 'debt_service' arrays (length == years).
        debt_out = apply_debt_layer(
            params,
            [{"cfads_usd": r["cfads_usd"]} for r in rows],  # minimal signal needed by the debt layer
        ) or {}

        equity_cf = [float(x) for x in (debt_out.get("equity_cf") or [])]
        debt_service = [float(x) for x in (debt_out.get("debt_service") or [])]
        dscr_min = _as_float(debt_out.get("dscr_min"))
        balloon = float(_as_float(debt_out.get("balloon_remaining"), 0.0) or 0.0)

        # Fallback if the debt layer didn't provide equity_cf but did provide debt_service
        if (not equity_cf) and debt_service:
            equity_cf = [
                max(0.0, rows[i]["cfads_usd"] - debt_service[i]) for i in range(min(len(rows), len(debt_service)))
            ]
            # pad if needed
            if len(equity_cf) < years:
                equity_cf.extend([0.0] * (years - len(equity_cf)))
    else:
        # equity-only: equity_CF == CFADS
        equity_cf = [r["cfads_usd"] for r in rows]

    # Ensure alignment
    if len(equity_cf) < years:
        equity_cf = equity_cf + [0.0] * (years - len(equity_cf))
    elif len(equity_cf) > years:
        equity_cf = equity_cf[:years]

    # --------------------------
    # construct cashflow series
    # --------------------------
    # Project cashflows = [-CAPEX] + [CFADS]
    project_cfs: List[float] = [-float(capex)] + [float(r["cfads_usd"]) for r in rows]

    # Equity cashflows = [-EquityContrib] + [equity_CF]
    # Simple approximation: equity injected at t0 equals (1 - debt_ratio) * CAPEX.
    equity_contrib = float(capex) * max(0.0, 1.0 - float(debt_ratio))
    equity_cfs: List[float] = [-equity_contrib] + [float(x) for x in equity_cf]

    # --------------------------
    # metrics
    # --------------------------
    eq_irr = irr(equity_cfs)
    pr_irr = irr(project_cfs)
    discount = _as_float(_get(params, ["metrics", "npv_discount_rate"]), 0.12) or 0.12
    pv_12 = npv(float(discount), project_cfs)

    # ship a normalized annual table (always includes equity_cf)
    annual_out = []
    for i, r in enumerate(rows):
        row = dict(r)
        row["equity_cf"] = float(equity_cf[i]) if i < len(equity_cf) else 0.0
        annual_out.append(row)

    return {
        "equity_irr": eq_irr,
        "project_irr": pr_irr,
        "npv_12": pv_12,
        "annual": annual_out,
        "debt_service": debt_service,
        "dscr_min": dscr_min,
        "balloon_remaining": balloon,
    }

    