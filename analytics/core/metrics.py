"""Core metrics and KPI calculations for DutchBay EPC model.

This module centralises financial KPI logic so that both the v14 analytics
pipeline and the legacy/v13-style callers can share a single, well-tested
implementation.

Key responsibilities:
- Clean and summarise DSCR series coming from the debt model
- Derive CFADS statistics and aggregates
- Compute or pass-through NPV / IRR on equity cashflows
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float, returning *default* on error."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _summary_stats(values: Sequence[Number]) -> Dict[str, Optional[float]]:
    """Return basic summary stats (min, max, mean, median) for a numeric series.

    Empty input returns all-None.
    """
    seq = [float(v) for v in values if v is not None]
    if not seq:
        return {"min": None, "max": None, "mean": None, "median": None}

    seq_sorted = sorted(seq)
    n = len(seq_sorted)

    min_v = seq_sorted[0]
    max_v = seq_sorted[-1]
    mean_v = sum(seq_sorted) / n

    if n % 2 == 1:
        median_v = seq_sorted[n // 2]
    else:
        mid = n // 2
        median_v = (seq_sorted[mid - 1] + seq_sorted[mid]) / 2.0

    return {
        "min": min_v,
        "max": max_v,
        "mean": mean_v,
        "median": median_v,
    }


# ---------------------------------------------------------------------------
# Unified KPI calculator
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
    """
    Unified KPI calculator used by both the v14 analytics pipeline and the
    standalone unit tests.

    It supports two call styles:

    1) ScenarioAnalytics-style (pipeline):

        calculate_scenario_kpis(
            annual_rows=annual_rows,
            debt_result=debt_result,
            config=config,
            discount_rate=0.08,
        )

    2) Unit-test / functional-style (tests/test_scenario_analytics_smoke.py):

        calculate_scenario_kpis(
            scenario_name="example",
            valuation={"npv": ..., "irr": ...},
            debt_result={"dscr_series": [...], ...},
            cfads_series_usd=[...],
        )

    Arguments
    ---------
    annual_rows:
        Optional sequence of annual cashflow rows. When provided and
        ``cfads_series_usd`` is not given, CFADS will be derived from
        ``row["cfads_usd"]`` in each row.
    debt_result:
        Debt model outputs; must contain at least ``"dscr_series"``. Additional
        keys such as ``"max_debt_usd"``, ``"final_debt_usd"`` and
        ``"total_idc_usd"`` are passed through.
    config:
        Scenario configuration dictionary. Used to derive project meta and,
        when ``valuation`` is not provided, the initial equity investment.
    discount_rate:
        Optional override for the discount rate. Defaults to
        ``DEFAULT_DISCOUNT_RATE`` when IRR/NPV are computed here.
    scenario_name:
        Optional label used for logging and downstream reporting. Not required
        by the implementation but accepted for compatibility with tests.
    valuation:
        Optional pre-computed valuation dict containing ``"npv"`` and ``"irr"``.
        If provided, those values are passed through; otherwise they are
        computed inside this function from the equity cashflow series.
    cfads_series_usd:
        Optional explicit CFADS series (one value per year). If omitted,
        CFADS is derived from ``annual_rows``.

    Returns
    -------
    Dict[str, Any]
        A dictionary containing at least:
          - "npv", "irr"
          - "dscr_min", "dscr_max", "dscr_mean", "dscr_median"
          - "dscr_series" (cleaned)
          - CFADS aggregates and stats
          - Selected debt stats used by the reporting layer.
    """
    if debt_result is None:
        raise ValueError("debt_result is required")

    # ------------------------------------------------------------------
    # 1) CFADS series
    # ------------------------------------------------------------------
    if cfads_series_usd is not None:
        cfads_series_clean: List[float] = [as_float(v, 0.0) for v in cfads_series_usd]
    elif annual_rows is not None:
        cfads_series_clean = [
            as_float(row.get("cfads_usd", 0.0), 0.0) for row in annual_rows
        ]
    else:
        # No CFADS provided anywhere – use a degenerate zero series sized to DSCR
        dscr_len = len(debt_result.get("dscr_series", []) or [])
        cfads_series_clean = [0.0] * dscr_len

    # ------------------------------------------------------------------
    # 2) DSCR series – clean per unit-test expectations
    # ------------------------------------------------------------------
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
            # Drop +/-inf and NaN
            continue
        if f <= 0.0:
            # Drop zero or negative DSCRs – tests expect this behaviour
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

    # ------------------------------------------------------------------
    # 3) Valuation (NPV / IRR)
    # ------------------------------------------------------------------
    if valuation is not None:
        npv_value = valuation.get("npv")
        irr_value = valuation.get("irr")
    else:
        # Compute equity investment from config + debt_result when possible.
        config = config or {}
        if discount_rate is None:
            discount_rate = DEFAULT_DISCOUNT_RATE

        capex_total = as_float(get_nested(config, ["capex", "usd_total"]), 0.0)
        principal_series = debt_result.get("principal_series") or []
        debt_raised = sum(as_float(p, 0.0) for p in principal_series)
        equity_investment = capex_total - debt_raised

        # Build equity cashflow series: time-0 equity outflow + annual CFADS
        cash_flows = [-equity_investment] + list(cfads_series_clean)

        try:
            irr_value = float(npf.irr(cash_flows))  # type: ignore[arg-type]
        except Exception:
            irr_value = None

        try:
            npv_value = float(npf.npv(discount_rate, cash_flows))  # type: ignore[arg-type]
        except Exception:
            npv_value = None

    # ------------------------------------------------------------------
    # 4) Debt and CFADS stats / aggregates
    # ------------------------------------------------------------------
    max_debt_usd = as_float(debt_result.get("max_debt_usd"), 0.0)
    final_debt_usd = as_float(debt_result.get("final_debt_usd"), 0.0)
    total_idc_usd = as_float(debt_result.get("total_idc_usd"), 0.0)

    cfads_stats = _summary_stats(cfads_series_clean)

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
        # Valuation
        "npv": npv_value,
        "irr": irr_value,
        # DSCR stats
        "dscr_min": dscr_stats["min"],
        "dscr_max": dscr_stats["max"],
        "dscr_mean": dscr_stats["mean"],
        "dscr_median": dscr_stats["median"],
        # Keep the cleaned DSCR series for downstream use / debugging
        "dscr_series": dscr_clean,
        # Debt stats
        "max_debt_usd": max_debt_usd,
        "final_debt_usd": final_debt_usd,
        "total_idc_usd": total_idc_usd,
        # CFADS stats
        "cfads_min": cfads_stats["min"],
        "cfads_max": cfads_stats["max"],
        "cfads_mean": cfads_stats["mean"],
        "cfads_median": cfads_stats["median"],
        # CFADS aggregates expected by the scenario_analytics smoke test
        "total_cfads_usd": total_cfads_usd,
        "final_cfads_usd": final_cfads_usd,
        "mean_operational_cfads_usd": mean_operational_cfads_usd,
    }

    # Pass-through hook: include scenario_name if supplied so callers can
    # attach the KPI block to a specific scenario in a flat structure.
    if scenario_name is not None:
        result["scenario_name"] = scenario_name

    return result


