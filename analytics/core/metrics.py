"""Core metrics and KPI calculations for DutchBay EPC model.

This module centralises financial KPI logic so that both the v14 analytics
pipeline and the legacy/v13-style callers can share a single, well-tested
implementation.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Sequence, Union, Optional, List

import numpy_financial as npf

from constants import DEFAULT_DISCOUNT_RATE
from finance.utils import as_float, get_nested

Number = Union[int, float]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _to_float(value: Any, default: float = 0.0) -> float:
    """Coerce arbitrary input to a plain float, never None."""
    raw = as_float(value, default)
    if raw is None:
        return float(default)
    return float(raw)


def _summary_stats(values: Sequence[Number]) -> Dict[str, Optional[float]]:
    """Return basic summary stats (min, max, mean, median) for a numeric series."""
    cleaned: List[float] = []
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(f):
            continue
        cleaned.append(f)

    if not cleaned:
        return {"min": None, "max": None, "mean": None, "median": None}

    cleaned.sort()
    n = len(cleaned)
    mean = sum(cleaned) / n
    if n % 2 == 1:
        median = cleaned[n // 2]
    else:
        median = 0.5 * (cleaned[n // 2 - 1] + cleaned[n // 2])

    return {
        "min": cleaned[0],
        "max": cleaned[-1],
        "mean": float(mean),
        "median": float(median),
    }


# ---------------------------------------------------------------------------
# Canonical KPI calculator (v14)
# ---------------------------------------------------------------------------


def calculate_scenario_kpis(
    annual_rows: Optional[Sequence[Dict[str, Any]]] = None,
    debt_result: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    discount_rate: Optional[float] = None,
    *,
    scenario_name: Optional[str] = None,
    valuation: Optional[Dict[str, Any]] = None,
    cfads_series_usd: Optional[Sequence[Number]] = None,
) -> Dict[str, Any]:
    """Unified KPI calculator used by the v14 analytics pipeline and tests."""
    if debt_result is None:
        raise ValueError("debt_result is required")

    # 1) CFADS series – always List[float]
    if cfads_series_usd is not None:
        cfads_series_clean: List[float] = [
            _to_float(v, 0.0) for v in cfads_series_usd
        ]
    elif annual_rows is not None:
        cfads_series_clean = [
            _to_float(row.get("cfads_usd", 0.0), 0.0) for row in annual_rows
        ]
    else:
        dscr_len = len(debt_result.get("dscr_series") or [])
        cfads_series_clean = [0.0] * dscr_len

    # 2) DSCR series – cleaned to List[float]
    raw_dscr = debt_result.get("dscr_series") or []
    dscr_clean: List[float] = []

    for v in raw_dscr:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(f):
            continue
        if f <= 0.0:
            continue
        dscr_clean.append(f)

    if dscr_clean:
        dscr_stats = _summary_stats(dscr_clean)
    else:
        dscr_stats = {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
        }

    # 3) Valuation (NPV / IRR)
    npv_value: Optional[float]
    irr_value: Optional[float]

    if valuation is not None:
        npv_raw = valuation.get("npv")
        irr_raw = valuation.get("irr")
        npv_value = float(npv_raw) if npv_raw is not None else None
        irr_value = float(irr_raw) if irr_raw is not None else None
    else:
        cfg: Dict[str, Any] = config or {}
        if discount_rate is None:
            discount_rate = DEFAULT_DISCOUNT_RATE

        capex_total = _to_float(get_nested(cfg, ["capex", "usd_total"]), 0.0)
        principal_series = debt_result.get("principal_series") or []
        debt_raised = sum(_to_float(p, 0.0) for p in principal_series)
        equity_investment = capex_total - debt_raised

        cash_flows: List[float] = [-equity_investment] + list(cfads_series_clean)

        irr_value = None
        npv_value = None
        try:
            irr_val = npf.irr(cash_flows)
            if irr_val is not None and not math.isnan(float(irr_val)):
                irr_value = float(irr_val)
        except Exception:
            pass

        try:
            npv_val = npf.npv(discount_rate, cash_flows)
            if npv_val is not None and not math.isnan(float(npv_val)):
                npv_value = float(npv_val)
        except Exception:
            pass

    # 4) Debt and CFADS stats / aggregates
    max_debt_usd = _to_float(debt_result.get("max_debt_usd"), 0.0)
    final_debt_usd = _to_float(debt_result.get("final_debt_usd"), 0.0)
    total_idc_usd = _to_float(debt_result.get("total_idc_usd"), 0.0)

    cfads_stats = _summary_stats(cfads_series_clean)

    if cfads_stats["min"] is not None and cfads_stats["max"] is not None:
        cfads_spread: Optional[float] = cfads_stats["max"] - cfads_stats["min"]
    else:
        cfads_spread = None

    if cfads_series_clean:
        total_cfads_usd: Optional[float] = float(sum(cfads_series_clean))
        final_cfads_usd: Optional[float] = float(cfads_series_clean[-1])
        mean_operational_cfads_usd: Optional[float] = (
            float(sum(cfads_series_clean)) / len(cfads_series_clean)
        )
    else:
        total_cfads_usd = None
        final_cfads_usd = None
        mean_operational_cfads_usd = None

    result: Dict[str, Any] = {
        "npv": npv_value,
        "irr": irr_value,
        "dscr_min": dscr_stats["min"],
        "dscr_max": dscr_stats["max"],
        "dscr_mean": dscr_stats["mean"],
        "dscr_median": dscr_stats["median"],
        "dscr_series": dscr_clean,
        "max_debt_usd": max_debt_usd,
        "final_debt_usd": final_debt_usd,
        "total_idc_usd": total_idc_usd,
        "cfads_min": cfads_stats["min"],
        "cfads_max": cfads_stats["max"],
        "cfads_mean": cfads_stats["mean"],
        "cfads_median": cfads_stats["median"],
        "cfads_spread": cfads_spread,
        "total_cfads_usd": total_cfads_usd,
        "final_cfads_usd": final_cfads_usd,
        "mean_operational_cfads_usd": mean_operational_cfads_usd,
    }

    if scenario_name is not None:
        result["scenario_name"] = scenario_name

    return result


# ---------------------------------------------------------------------------
# Backwards-compatible adapter for ScenarioAnalytics
# ---------------------------------------------------------------------------


def compute_kpis(
    config: Dict[str, Any],
    annual_rows: Sequence[Dict[str, Any]],
    debt_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Compatibility layer used by analytics.scenario_analytics."""
    scenario_name: Optional[str] = None
    if config is not None:
        scenario_name = config.get("name")

    return calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config,
        scenario_name=scenario_name,
    )

    