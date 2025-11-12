# dutchbay_v13/core.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


__all__ = [
    "equity_only_cashflows",
    "compute_irr",
    "kwh_per_year",
    "revenue_usd_per_year",
    "opex_usd_per_year",
]

# -------------------------------
# Internal safe-access utilities
# -------------------------------

def _get(d: Dict[str, Any], path: Iterable[str], default: Any = None) -> Any:
    """Nested dict getter: _get(p, ['project','capacity_mw'])."""
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


# -------------------------------
# Parameter readers (no policy)
# -------------------------------

def capacity_mw(p: Dict[str, Any]) -> float:
    """project.capacity_mw or legacy capacity_mw; default 0.0 (policy lives in YAML)."""
    return _as_float(_get(p, ["project", "capacity_mw"]), _as_float(p.get("capacity_mw"), 0.0)) or 0.0


def lifetime_years(p: Dict[str, Any]) -> int:
    """project.timeline.lifetime_years or legacy lifetime_years; default 0."""
    val = _as_float(_get(p, ["project", "timeline", "lifetime_years"]), _as_float(p.get("lifetime_years"), 0.0))
    return int(val or 0)


def availability_frac(p: Dict[str, Any]) -> float:
    """availability_pct (%) → fraction; default 0.0."""
    pct = _as_float(p.get("availability_pct"), 0.0) or 0.0
    return max(0.0, min(1.0, pct / 100.0))


def loss_factor(p: Dict[str, Any]) -> float:
    """loss_factor is already a fraction; default 0.0."""
    lf = _as_float(p.get("loss_factor"), 0.0) or 0.0
    return max(0.0, min(1.0, lf))


def tariff_usd_per_kwh(p: Dict[str, Any]) -> float:
    """Prefer 'tariff_usd_per_kwh'; fallback to legacy 'tariff' if already USD/kWh; default 0.0."""
    return _as_float(p.get("tariff_usd_per_kwh"), _as_float(p.get("tariff"), 0.0)) or 0.0


def capex_usd_total(p: Dict[str, Any]) -> float:
    """
    capex.usd_total if present; else capex.usd_per_mw * capacity.
    Defaults are 0.0—any floors/guardrails belong in YAML or validation.
    """
    total = _get(p, ["capex", "usd_total"])
    if total is not None:
        return float(total)
    per_mw = _as_float(_get(p, ["capex", "usd_per_mw"]), 0.0) or 0.0
    return per_mw * capacity_mw(p)


def opex_usd_per_year(p: Dict[str, Any]) -> float:
    """opex.usd_per_year (no floors here; policy in YAML)."""
    return _as_float(_get(p, ["opex", "usd_per_year"]), 0.0) or 0.0


# -------------------------------
# Simple production & cashflows
# -------------------------------

def kwh_per_year(p: Dict[str, Any]) -> float:
    """
    Annual gross production (kWh) = capacity * 8760 * availability * (1 - loss).
    No curtailment/capacity degradation modeling here—keep this core module simple.
    """
    cap = capacity_mw(p)
    avail = availability_frac(p)
    loss = loss_factor(p)
    mwh = cap * 8760.0 * avail * max(0.0, 1.0 - loss)
    return mwh * 1000.0


def revenue_usd_per_year(p: Dict[str, Any]) -> float:
    """USD revenue per year = tariff_usd_per_kwh * kWh."""
    return tariff_usd_per_kwh(p) * kwh_per_year(p)


def equity_only_cashflows(p: Dict[str, Any]) -> List[float]:
    """
    Equity-only cash flow vector:
      t0 = -capex
      years 1..N = (revenue - opex)
    Debt layering, reserves, fees, etc. are handled in finance/debt.py.
    """
    n = lifetime_years(p)
    capex = capex_usd_total(p)
    annual_net = revenue_usd_per_year(p) - opex_usd_per_year(p)
    if n <= 0:
        return [-float(capex)]
    return [-float(capex)] + [float(annual_net)] * n


# -------------------------------
# IRR utility (with graceful fallback)
# -------------------------------

def compute_irr(cashflows: List[float]) -> float:
    """
    IRR for a vector like [-capex, cf1, cf2, ...].
    Uses numpy-financial if available; otherwise Newton-style fallback.
    """
    if not cashflows:
        return 0.0

    # Preferred: numpy_financial
    try:
        import numpy_financial as npf  # type: ignore
        val = npf.irr(cashflows)
        return float(val) if val is not None else 0.0
    except Exception:
        pass

    # Minimal fallback: secant / Newton-esque (tolerant, not fancy)
    def _npv(rate: float) -> float:
        total = 0.0
        for i, cf in enumerate(cashflows):
            total += cf / ((1.0 + rate) ** i)
        return total

    r0, r1 = 0.05, 0.15  # two starting guesses
    for _ in range(100):
        f0, f1 = _npv(r0), _npv(r1)
        denom = (f1 - f0)
        if abs(denom) < 1e-12:
            break
        r2 = r1 - f1 * (r1 - r0) / denom
        if abs(r2 - r1) < 1e-9:
            return float(r2)
        r0, r1 = r1, r2
    return float(r1)

    