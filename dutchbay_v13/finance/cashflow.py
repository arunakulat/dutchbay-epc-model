# dutchbay_v13/finance/cashflow.py
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
    # Prefer explicit ops timeline; else fallback to lifetime_years
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

def _energy_series_mwh(p: Dict[str, Any], years: int, ops_start: int) -> List[float]:
    # 1) explicit list
    explicit = _get(p, ["energy", "mwh_per_year"])
    if isinstance(explicit, list) and len(explicit) >= years:
        ser = [float(x) for x in explicit[:years]]
        for i in range(min(ops_start, years)):
            ser[i] = 0.0
        return ser
    # 2) explicit scalar
    if explicit is not None and not isinstance(explicit, list):
        val = float(explicit)
        return [0.0]*ops_start + [val]*(years - ops_start)
    # 3) capacity factor
    cf = _as_float(_get(p, ["energy", "capacity_factor"]), None)
    cap = _capacity_mw(p)
    lf = _loss_factor(p)
    av = _availability(p)
    if cf is not None:
        net_cf = max(0.0, min(1.0, cf)) * max(0.0, min(1.0, 1.0 - lf)) * max(0.0, min(1.0, av))
        mwh = cap * HOURS_PER_YEAR * net_cf
        return [0.0]*ops_start + [mwh]*(years - ops_start)
    # 4) derive from availability and losses only (last resort)
    net_cf = max(0.0, min(1.0, av * (1.0 - lf)))
    mwh = cap * HOURS_PER_YEAR * net_cf
    return [0.0]*ops_start + [mwh]*(years - ops_start)

def _tariff_mode(p: Dict[str, Any]) -> str:
    if _get(p, ["tariff_usd_per_kwh"]) is not None or _get(p, ["tariff", "usd_per_kwh"]) is not None:
        return "USD"
    return "LKR"

def _tariff_usd_per_kwh(p: Dict[str, Any], fx: List[float], t: int) -> float:
    usd = _get(p, ["tariff", "usd_per_kwh"])
    if usd is None:
        usd = _get(p, ["tariff_usd_per_kwh"])
    if usd is not None:
        return float(usd)
    lkr = _get(p, ["tariff", "lkr_per_kwh"])
    if lkr is None:
        lkr = _get(p, ["tariff_lkr_per_kwh"])
    lkr_val = _as_float(lkr, None)
    if lkr_val is None:
        return 0.0
    # unindexed LKR tariff → convert each year at that year's FX
    return float(lkr_val) / float(fx[t])

def _opex_usd_per_year(p: Dict[str, Any]) -> float:
    floor = _as_float(_get(p, ["opex", "floor_usd_per_year"]), 300_000.0) or 300_000.0
    v = _as_float(_get(p, ["opex", "usd_per_year"]), floor) or floor
    return max(v, floor)

def build_annual_rows(p: Dict[str, Any]) -> List[Dict[str, float]]:
    years = _years_total(p)
    ops_start = _ops_start_index(p)
    fx = _fx_curve(p, years)
    mwh = _energy_series_mwh(p, years, ops_start)
    opex_flat = _opex_usd_per_year(p)

    rows: List[Dict[str, float]] = []
    for t in range(years):
        if t < ops_start:
            rows.append({"year": t+1, "revenue_usd": 0.0, "opex_usd": 0.0, "cfads_usd": 0.0})
            continue
        tariff_usd = _tariff_usd_per_kwh(p, fx, t)
        revenue_usd = (mwh[t] * tariff_usd) / 1_000.0  # kWh = MWh*1000 → divide by 1000
        opex_usd = opex_flat
        cfads = revenue_usd - opex_usd
        rows.append({"year": t+1, "revenue_usd": revenue_usd, "opex_usd": opex_usd, "cfads_usd": cfads})
    return rows

    