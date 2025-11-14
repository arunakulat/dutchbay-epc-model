from __future__ import annotations
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

def _years_total(p: Dict[str, Any]) -> int:
    ops_years = _int(_get(p, ["project", "timeline", "ops_years"]), None)
    if ops_years is not None:
        pre = _int(_get(p, ["project", "timeline", "ppa_to_fc_years"]), 0) \
            + _int(_get(p, ["project", "timeline", "construction_years"]), 0)
        return pre + ops_years
    return _int(_get(p, ["project", "timeline", "lifetime_years"]), 20)

def _ops_start_index(p: Dict[str, Any]) -> int:
    return _int(_get(p, ["project", "timeline", "ppa_to_fc_years"]), 0) \
         + _int(_get(p, ["project", "timeline", "construction_years"]), 0)

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

# CORRECTED: Pulls explicit project.capacity_factor, falls back to availability if missing
def kwh_per_year(p: Dict[str, Any]) -> float:
    """
    Correct wind production: Use 'project.capacity_factor' if present
    Else use availability (%), then default to 0.95, just for backcompat
    """
    cap = _capacity_mw(p)
    # Try both project.capacity_factor, then global capacity_factor
    cf = None
    if 'project' in p and 'capacity_factor' in p['project']:
        cf = _as_float(p['project']['capacity_factor'], None)
    elif 'capacity_factor' in p:
        cf = _as_float(p['capacity_factor'], None)
    # Fallback: Use availability if no capacity_factor explicitly present
    if cf is not None:
        cap_factor = cf
        origin = f"project.capacity_factor={cf}"
    else:
        cap_factor = _availability(p)
        origin = f"availability={cap_factor} (default if no capacity_factor)"
    loss = _loss_factor(p)
    print(f"Diagnostic: cap={cap} MW, cap_factor={cap_factor}, hours=8760, loss={loss}, origin: {origin}")
    kwh = cap * 1000.0 * HOURS_PER_YEAR * cap_factor * (1.0 - loss)
    print(f"Diagnostic Gross production: {cap} MW x 1000 x 8760 x {cap_factor} x (1-loss) = {kwh:,.2f} kWh")
    return kwh

def revenue_usd_per_year(p: Dict[str, Any], year: int=0) -> float:
    kwh = kwh_per_year(p)
    tariff_lkr = float(_get(p, ["tariff", "lkr_per_kwh"], 0.0))
    fx_curve = _fx_curve(p, _years_total(p))
    fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
    revenue_lkr = kwh * tariff_lkr
    revenue_usd = revenue_lkr / fx_rate if fx_rate > 0 else 0.0
    print(f"Diagnostic [Year {year+1}]: kwh={kwh}, tariff_lkr={tariff_lkr}, fx_rate={fx_rate}, revenue_lkr={revenue_lkr}, revenue_usd={revenue_usd}")
    return revenue_usd

def build_annual_rows(p: Dict[str, Any]) -> List[Dict[str, float]]:
    years = _years_total(p)
    ops_start = _ops_start_index(p)
    fx = _fx_curve(p, years)
    deg = float(_get(p, ["project", "degradation"], 0.0))
    opex_flat = _opex_usd_per_year(p)
    base_kwh = kwh_per_year(p)
    rows: List[Dict[str, float]] = []
    for t in range(years):
        # Apply degradation after ops start
        degraded_kwh = base_kwh * ((1 - deg) ** t) if t >= ops_start else 0.0
        tariff_lkr = float(_get(p, ["tariff", "lkr_per_kwh"], 0.0))
        fx_rate = fx[t] if t < len(fx) else fx[-1]
        revenue_lkr = degraded_kwh * tariff_lkr
        revenue_usd = revenue_lkr / fx_rate if fx_rate > 0 else 0.0
        opex_usd = opex_flat
        cfads = revenue_usd - opex_usd
        diagnostic = ''
        if cfads < 0:
            diagnostic = '<NEGATIVE CFADS>'
        print(f"Year {t+1}: degraded_kwh={degraded_kwh}, tariff_lkr={tariff_lkr}, fx_rate={fx_rate}, revenue_usd={revenue_usd}, opex_usd={opex_usd}, cfads={cfads} {diagnostic}")
        rows.append({"year": t+1, "revenue_usd": revenue_usd, "opex_usd": opex_usd, "cfads_usd": cfads})
    return rows
