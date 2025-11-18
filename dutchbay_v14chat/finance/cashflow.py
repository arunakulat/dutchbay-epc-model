"""
DutchBay EPC Wind v14 Cashflow Module
- Handles 2 construction years, 1 transition, 20 operational in a unified 23-period annual cashflow.
- CLI and modular workflow compliant.
"""

from typing import Dict, Any, List

HOURS_PER_YEAR = 8760.0

def _get(d: Dict[str, Any], path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def _as_float(x, default=None):
    try:
        return float(x) if x is not None else default
    except Exception:
        return default

def _int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default

def _capacity_mw(p: Dict[str, Any]) -> float:
    v = _get(p, ["project", "capacity_mw"])
    if v is None:
        v = p.get("capacity_mw")
    return _as_float(v, 1.0) or 1.0

def _availability(p: Dict[str, Any]) -> float:
    v = _as_float(p.get("availability_pct"), 95.0) or 95.0
    return max(0.0, min(1.0, v / 100.0))

def _loss_factor(p: Dict[str, Any]) -> float:
    v = _as_float(p.get("loss_factor"), 0.0) or 0.0
    return max(0.0, min(1.0, v))

def _fx_curve(p: Dict[str, Any], n: int) -> List[float]:
    explicit = _get(p, ["fx", "curve_lkr_per_usd"])
    if isinstance(explicit, list) and explicit:
        if len(explicit) >= n:
            return [float(x) for x in explicit[:n]]
        return [float(x) for x in explicit] + [float(explicit[-1])] * (n - len(explicit))
    start = _as_float(_get(p, ["fx", "start_lkr_per_usd"]), 300.0) or 300.0
    depr = _as_float(_get(p, ["fx", "annual_depr"]), 0.03) or 0.03
    out: List[float] = []
    cur = float(start)
    for _ in range(max(1, n)):
        out.append(cur)
        cur *= (1.0 + depr)
    return out

def _opex_usd_per_year(p: Dict[str, Any]) -> float:
    floor = _as_float(_get(p, ["opex", "floor_usd_per_year"]), 300_000.0) or 300_000.0
    v = _as_float(_get(p, ["opex", "usd_per_year"]), floor) or floor
    return max(v, floor)

def kwh_per_year(p: Dict[str, Any]) -> float:
    cap = _capacity_mw(p)
    cf = p.get("project", {}).get("capacity_factor", p.get("capacity_factor", None))
    cap_factor = _as_float(cf, _availability(p))
    loss = _loss_factor(p)
    return cap * 1000.0 * HOURS_PER_YEAR * cap_factor * (1.0 - loss)

def build_annual_rows_v14(p: Dict[str, Any]) -> List[Dict[str, float]]:
    # Always return 23 periods: 2 construction, 1 transition, 20 operational
    construction_periods = int(_get(p, ["Financing_Terms", "construction_periods"], 2))
    ops_years = 20
    transition_years = 1
    periods = construction_periods + transition_years + ops_years

    fx = _fx_curve(p, periods)
    deg = float(_get(p, ["project", "degradation"], 0.0))
    opex_flat = _opex_usd_per_year(p)
    base_kwh = kwh_per_year(p)
    tariff_lkr = float(_get(p, ["tariff", "lkr_per_kwh"], 0.0))

    rows: List[Dict[str, float]] = []
    for t in range(periods):
        # Construction periods: no production, only capex/opex/IDC if needed
        if t < construction_periods:
            rows.append({
                "year": t + 1,
                "revenue_usd": 0.0,
                "opex_usd": 0.0,
                "cfads_usd": 0.0,
                "label": "construction"
            })
        # Transition period: partial production (50% assumed by default)
        elif t < construction_periods + transition_years:
            degraded_kwh = base_kwh * 0.5  # Overridable if your config prefers
            fx_rate = fx[t]
            revenue_lkr = degraded_kwh * tariff_lkr
            revenue_usd = revenue_lkr / fx_rate if fx_rate > 0 else 0.0
            opex_usd = opex_flat
            cfads = revenue_usd - opex_usd
            rows.append({
                "year": t + 1,
                "revenue_usd": revenue_usd,
                "opex_usd": opex_usd,
                "cfads_usd": cfads,
                "label": "transition"
            })
        # Operational: full production, apply degradation
        else:
            ops_index = t - (construction_periods + transition_years)
            degraded_kwh = base_kwh * ((1 - deg) ** ops_index)
            fx_rate = fx[t]
            revenue_lkr = degraded_kwh * tariff_lkr
            revenue_usd = revenue_lkr / fx_rate if fx_rate > 0 else 0.0
            opex_usd = opex_flat
            cfads = revenue_usd - opex_usd
            rows.append({
                "year": t + 1,
                "revenue_usd": revenue_usd,
                "opex_usd": opex_usd,
                "cfads_usd": cfads,
                "label": "operational"
            })
    return rows
