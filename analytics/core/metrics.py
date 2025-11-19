"""Core analytics metrics for DutchBay scenario analysis.

This module computes high-level KPIs (NPV, IRR, DSCR stats, debt stats, CFADS stats)
for use by the scenario_analytics pipeline.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Optional, Union

import numpy_financial as npf  # type: ignore
import numpy as np
import pandas as pd

from finance.utils import as_float, get_nested
from constants import DEFAULT_DISCOUNT_RATE


Number = Union[int, float]


def _to_rows(annual_rows: Union[Sequence[Dict[str, Any]], Any]) -> List[Dict[str, Any]]:
    """Normalise annual_rows to a list of dicts."""
    if hasattr(annual_rows, "to_dict"):
        # Assume pandas DataFrame-like
        try:
            return list(annual_rows.to_dict(orient="records"))
        except TypeError:
            pass
    # Already a list/sequence of dict-like objects
    return [dict(row) for row in annual_rows]

def _clean_dscr_series(dscr_raw) -> pd.Series:
    """
    Normalize DSCR per-year values:

    - Convert list → Series
    - Replace +/-inf with NaN
    - Drop zero-debt-service years (where DSCR is undefined)
    """
    if not isinstance(dscr_raw, pd.Series):
        dscr = pd.Series(dscr_raw)
    else:
        dscr = dscr_raw.copy()

    # Remove +/-inf (zero debt service → inf)
    dscr = dscr.replace([np.inf, -np.inf], np.nan)

    # Drop NaN entries
    dscr = dscr.dropna()

    return dscr

def _clean_series(raw: Sequence[Any]) -> List[float]:
    """Convert a raw sequence to a list of finite floats."""
    out: List[float] = []
    for v in raw:
        fv = as_float(v)
        if fv is None:
            continue
        if isinstance(fv, (float, int)) and not math.isnan(fv):
            out.append(float(fv))
    return out


def _summary_stats(values: Sequence[Number]) -> Dict[str, Optional[float]]:
    """Return min / max / mean / median for a numeric series."""
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return {"min": None, "max": None, "mean": None, "median": None}
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    _min = vals_sorted[0]
    _max = vals_sorted[-1]
    _mean = sum(vals_sorted) / n
    if n % 2 == 1:
        _median = vals_sorted[n // 2]
    else:
        _median = 0.5 * (vals_sorted[n // 2 - 1] + vals_sorted[n // 2])
    return {"min": _min, "max": _max, "mean": _mean, "median": _median}

def calculate_scenario_kpis(
    annual_rows: Union[Sequence[Dict[str, Any]], Any],
    debt_result: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    discount_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate comprehensive KPIs for a scenario.

    This is intentionally V14-centric but accepts a generic annual_rows/debt_result
    pair so it can evolve with the finance layer.

    Args:
        annual_rows: Per-year summary rows (list of dicts or DataFrame).
        debt_result: Output from apply_debt_layer (must at least expose
            'dscr_series' and 'debt_outstanding').
        config: Normalised scenario config (from analytics.scenario_loader).
        discount_rate: Discount rate for NPV; falls back to DEFAULT_DISCOUNT_RATE.

    Returns:
        Dict with at least: npv, irr, dscr_min, dscr_max, dscr_mean, dscr_median,
        max_debt_usd, final_debt_usd, total_idc_usd, total_cfads_usd,
        final_cfads_usd, mean_operational_cfads_usd, dscr_series.
    """
    rows = _to_rows(annual_rows)

    # ------------------------------------------------------------------
    # CFADS series (USD)
    # ------------------------------------------------------------------
    cfads_series: List[float] = []
    for row in rows:
        cf = as_float(row.get("cfads_usd"), 0.0)
        cfads_series.append(cf if cf is not None else 0.0)

    # ------------------------------------------------------------------
    # Debt / DSCR series (from debt_result – canonical in V14)
    # ------------------------------------------------------------------
    raw_dscr = debt_result.get("dscr_series", [])
    dscr_series = _clean_dscr_series(raw_dscr)

    # DSCR stats on the cleaned series
    if hasattr(dscr_series, "empty") and dscr_series.empty:
        dscr_min = None
        dscr_max = None
        dscr_mean = None
        dscr_median = None
    elif not raw_dscr:
        dscr_min = None
        dscr_max = None
        dscr_mean = None
        dscr_median = None
    else:
        dscr_min = float(dscr_series.min())
        dscr_max = float(dscr_series.max())
        dscr_mean = float(dscr_series.mean())
        dscr_median = float(dscr_series.median())

    # Debt outstanding series (USD)
    debt_outstanding = _clean_series(debt_result.get("debt_outstanding", []))
    max_debt = max(debt_outstanding) if debt_outstanding else 0.0
    final_debt = debt_outstanding[-1] if debt_outstanding else 0.0

    # IDC – try a couple of common keys, defaulting to 0 if absent
    total_idc_usd = 0.0
    for key in ("total_idc_usd", "idc_total_usd", "idc_usd", "total_idc"):
        val = debt_result.get(key)
        if val is not None:
            fv = as_float(val, 0.0)
            if fv is not None:
                total_idc_usd = fv
            break

    # ------------------------------------------------------------------
    # CFADS aggregates
    # ------------------------------------------------------------------
    total_cfads_usd = sum(cfads_series)
    final_cfads_usd = cfads_series[-1] if cfads_series else 0.0

    # Crude "operational years" heuristic:
    # - Prefer explicit phase/is_operational flags if present,
    # - otherwise treat years after year 3 as operational (2-yr construction + 1 buffer).
    ops_cfads: List[float] = []
    for idx, row in enumerate(rows):
        phase = str(row.get("phase", "")).lower()
        is_ops_flag = row.get("is_operational")
        year = row.get("year") or (idx + 1)

        is_ops = False
        if is_ops_flag is True:
            is_ops = True
        elif phase in {"ops", "operation", "operations"}:
            is_ops = True
        elif isinstance(year, (int, float)) and year > 3:
            is_ops = True

        if is_ops:
            ops_cfads.append(cfads_series[idx])

    if not ops_cfads:
        ops_cfads = cfads_series

    mean_operational_cfads_usd = (
        sum(ops_cfads) / len(ops_cfads) if ops_cfads else 0.0
    )

    # ------------------------------------------------------------------
    # Equity investment / NPV / IRR
    # ------------------------------------------------------------------
    if discount_rate is None:
        discount_rate = DEFAULT_DISCOUNT_RATE

    capex_total_usd = as_float(
        get_nested(config, ["capex", "usd_total"], default=None) if config else None,
        default=0.0,
    )

    principal_series = _clean_series(debt_result.get("principal_series", []))
    debt_raised = sum(principal_series)

    equity_investment = capex_total_usd - debt_raised
    # If we don't have a sensible equity number, fall back to using total capex.
    if equity_investment <= 0 and capex_total_usd > 0:
        equity_investment = capex_total_usd

    cash_flows: List[float] = []
    if equity_investment != 0:
        cash_flows.append(-equity_investment)
    else:
        # Avoid the "all non-negative cashflows" IRR pathology – inject a tiny
        # negative at t=0 so the function has a sign change.
        cash_flows.append(-1e-6)
    cash_flows.extend(cfads_series)

    # NPV (always computable, even if IRR isn't)
    try:
        npv_value = float(npf.npv(discount_rate, cash_flows))
    except Exception:
        npv_value = 0.0

    # IRR – can legitimately fail or return nan; treat those as None.
    try:
        irr_value = float(npf.irr(cash_flows))
        if math.isnan(irr_value) or math.isinf(irr_value):
            irr_value = None  # type: ignore[assignment]
    except Exception:
        irr_value = None  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Final KPI dict (scalar stats + cleaned DSCR series)
    # ------------------------------------------------------------------
    kpis: Dict[str, Any] = {
        "npv": npv_value,
        "irr": irr_value,
        "dscr_min": dscr_min,
        "dscr_max": dscr_max,
        "dscr_mean": dscr_mean,
        "dscr_median": dscr_median,
        "max_debt_usd": max_debt,
        "final_debt_usd": final_debt,
        "total_idc_usd": total_idc_usd,
        "total_cfads_usd": total_cfads_usd,
        "final_cfads_usd": final_cfads_usd,
        "mean_operational_cfads_usd": mean_operational_cfads_usd,
        # keep a JSON-/Excel-friendly copy of the DSCR curve
        "dscr_series": list(dscr_series) if hasattr(dscr_series, "__iter__") else [],
    }

    return kpis
def format_kpi_summary(kpis: Dict[str, Any], scenario_name: str) -> str:
    """
    Render a human-friendly multi-line summary for console output.

    This mirrors the lender-style printout used in the scenario_analytics suite.
    """
    npv_value = kpis.get("npv")
    irr_value = kpis.get("irr")

    dscr_min = kpis.get("dscr_min")
    dscr_max = kpis.get("dscr_max")
    dscr_mean = kpis.get("dscr_mean")
    dscr_median = kpis.get("dscr_median")

    max_debt = kpis.get("max_debt_usd")
    final_debt = kpis.get("final_debt_usd")
    total_idc = kpis.get("total_idc_usd")

    total_cfads = kpis.get("total_cfads_usd")
    final_cfads = kpis.get("final_cfads_usd")
    mean_ops_cfads = kpis.get("mean_operational_cfads_usd")

    lines: List[str] = []
    lines.append("\n" + "=" * 60)
    lines.append(f"Scenario: {scenario_name}")
    lines.append("=" * 60 + "\n")

    # Valuation
    lines.append("Valuation Metrics:")
    if isinstance(npv_value, (int, float)):
        lines.append(f"  NPV (USD):{npv_value:>26,.2f}")
    else:
        lines.append("  NPV (USD):                N/A")

    if isinstance(irr_value, (int, float)):
        lines.append(f"  IRR:{irr_value * 100:>31.2f}%")
    else:
        lines.append("  IRR:                       N/A")

    lines.append("")  # blank line

    # DSCR
    lines.append("DSCR Statistics:")
    if dscr_min is not None:
        lines.append(f"  Minimum DSCR:{dscr_min:>22.2f}")
        lines.append(f"  Maximum DSCR:{(dscr_max or 0):>22.2f}")
        lines.append(f"  Mean DSCR:{(dscr_mean or 0):>25.2f}")
        lines.append(f"  Median DSCR:{(dscr_median or 0):>23.2f}")
    else:
        lines.append("  (no DSCR data available)")
    lines.append("")

    # Debt
    lines.append("Debt Statistics:")
    if isinstance(max_debt, (int, float)):
        lines.append(f"  Max Debt (USD):{max_debt:>17,.2f}")
    if isinstance(final_debt, (int, float)):
        lines.append(f"  Final Debt (USD):{final_debt:>15,.2f}")
    if isinstance(total_idc, (int, float)):
        lines.append(f"  Total IDC (USD):{total_idc:>16,.2f}")
    lines.append("")

    # CFADS
    lines.append("CFADS Statistics:")
    if isinstance(total_cfads, (int, float)):
        lines.append(f"  Total CFADS (USD):{total_cfads:>12,.2f}")
    if isinstance(final_cfads, (int, float)):
        lines.append(f"  Final Year CFADS:{final_cfads:>14,.2f}")
    if isinstance(mean_ops_cfads, (int, float)):
        lines.append(f"  Mean Operational:{mean_ops_cfads:>16,.2f}")

    return "\n".join(lines)
