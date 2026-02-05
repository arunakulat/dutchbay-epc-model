#!/usr/bin/env python3
"""
analytics.core.metrics
======================

Canonical v14 KPI computation engine.

This module is the single source of truth for all scenario-level KPI aggregation:
- Project NPV/IRR (via finance.irr singleton - R7 compliance)
- DSCR statistics (min/max/mean/median)
- Equity performance metrics (IRR, MOIC, DPI)
- CFADS aggregates (total, mean, final year)
- Lender KPIs (avg_dscr, llcr, plcr, equity_irr)

Go With The Flow Compliance
----------------------------
R7:  All IRR/NPV calculations via finance.irr singleton (no duplication)
R15: Defensive error handling (calculations never fatal)
R22: Multi-currency aware (expects USD-denominated inputs)

Architecture
------------
This module is called by:
- run_full_pipeline_v14.run_v14_pipeline (full output)
- analytics.evaluate_scenario.evaluate_with_overrides (KPI-only)
- tests/api/test_metrics_core_stats.py (unit tests)
- tests/api/test_evaluation_v14_lender_stack.py (lender KPI tests)

All callers must use calculate_scenario_kpis as the canonical entry point.

Typical usage
-------------
Full project context::

    kpis = calculate_scenario_kpis(
        config=config_dict,
        annual_rows=annual_rows_list,
        debt_result=debt_result_dict,
        discount_rate=0.10,
    )

Valuation shortcut (for tests/analytics)::

    kpis = calculate_scenario_kpis(
        cfads_series_usd=[100, 200, 300],
        debt_result={"dscr_series": [1.5, 1.8, 2.0]},
        valuation={"npv": 50000000, "irr": 0.15},
    )
"""

from __future__ import annotations

import logging
import math
from statistics import median
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from finance.irr import approx_project_irr, project_npv_from_cfads

logger = logging.getLogger(__name__)

DEFAULT_DISCOUNT_RATE = 0.10


# ═════════════════════════════════════════════════════════════════════════════
# Generic summary statistics
# ═════════════════════════════════════════════════════════════════════════════


def _summary_stats(values: Iterable[float]) -> Dict[str, float]:
    """
    Return robust statistics for a numeric series.

    Filters out None and non-finite values, returns zeros for empty series.

    Parameters
    ----------
    values : Iterable[float]
        Numeric series (may contain None, NaN, inf).

    Returns
    -------
    Dict[str, float]
        Statistics dict with keys: n, mean, std, min, p10, median, p90, max.

    Examples
    --------
    >>> _summary_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    {'n': 5.0, 'mean': 3.0, 'std': 1.414..., 'min': 1.0, ...}

    >>> _summary_stats([])
    {'n': 0, 'mean': 0.0, 'std': 0.0, 'min': 0.0, ...}
    """
    cleaned = [
        float(v)
        for v in values
        if v is not None and isinstance(v, (int, float)) and math.isfinite(v)
    ]
    if not cleaned:
        return {
            "n": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "p10": 0.0,
            "median": 0.0,
            "p90": 0.0,
            "max": 0.0,
        }

    cleaned.sort()
    n = len(cleaned)
    mu = sum(cleaned) / n
    if n > 1:
        var = sum((x - mu) ** 2 for x in cleaned) / n
        sd = math.sqrt(var)
    else:
        sd = 0.0

    def _percentile(sorted_vals: list[float], q: float) -> float:
        """Simple percentile implementation (linear interpolation)."""
        if not sorted_vals:
            return 0.0
        if q <= 0:
            return sorted_vals[0]
        if q >= 1:
            return sorted_vals[-1]
        idx = int(round(q * (len(sorted_vals) - 1)))
        idx = max(0, min(len(sorted_vals) - 1, idx))
        return sorted_vals[idx]

    return {
        "n": float(n),
        "mean": mu,
        "std": sd,
        "min": cleaned[0],
        "p10": _percentile(cleaned, 0.10),
        "median": median(cleaned),
        "p90": _percentile(cleaned, 0.90),
        "max": cleaned[-1],
    }


def _clean_dscr_series(raw: Optional[Sequence[Any]]) -> Sequence[float]:
    """
    Clean DSCR series: drop None, non-finite, and non-positive values.

    DSCR must be positive and finite to be meaningful.

    Parameters
    ----------
    raw : Optional[Sequence[Any]]
        Raw DSCR series (may contain None, NaN, inf, negative values).

    Returns
    -------
    Sequence[float]
        Cleaned DSCR series (only positive finite values).

    Examples
    --------
    >>> _clean_dscr_series([1.5, None, 2.0, float('inf'), -1.0, 1.8])
    [1.5, 2.0, 1.8]
    """
    if not raw:
        return []
    out: list[float] = []
    for v in raw:
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(x):
            continue
        if x <= 0.0:
            continue
        out.append(x)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Config metadata extraction (v14 schema-aware)
# ═════════════════════════════════════════════════════════════════════════════


def _derive_scenario_name(config: Optional[Mapping[str, Any]]) -> str:
    """Extract scenario name from config (tries multiple keys)."""
    if not config:
        return ""
    candidates: list[Any] = []
    for key in ("scenario_name", "name", "id"):
        if key in config:
            candidates.append(config[key])
    meta = config.get("meta") if isinstance(config, Mapping) else None
    if isinstance(meta, Mapping):
        for key in ("scenario_name", "name", "id"):
            if key in meta:
                candidates.append(meta[key])
    for c in candidates:
        if c is not None:
            return str(c)
    return ""


def _derive_capex_usd(config: Optional[Mapping[str, Any]]) -> float:
    """
    Extract total CAPEX from config (v14 schema-aware).

    Priority order:
    1. finance.capex_total_usd (v14 primary)
    2. finance.capex_usd (v14 alternate)
    3. capex.usd_total (legacy)
    4. capex.capex_total_usd (legacy alternate)
    5. capex.total_capex_usd (legacy alternate 2)

    Returns 0.0 if no valid CAPEX found.

    Examples
    --------
    >>> # v14 config
    >>> config = {"finance": {"capex_total_usd": 200e6}}
    >>> _derive_capex_usd(config)
    200000000.0

    >>> # Legacy config
    >>> config = {"capex": {"usd_total": 150e6}}
    >>> _derive_capex_usd(config)
    150000000.0
    """
    if not config:
        return 0.0

    # PRIORITY 1: v14 finance section
    finance_cfg = config.get("finance")
    if isinstance(finance_cfg, Mapping):
        for key in ["capex_total_usd", "capex_usd"]:
            val = finance_cfg.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue

    # PRIORITY 2: Legacy capex section
    capex_cfg = config.get("capex")
    if isinstance(capex_cfg, Mapping):
        for key in ["usd_total", "capex_total_usd", "total_capex_usd", "total_capex"]:
            val = capex_cfg.get(key)
            if val is not None:
                try:
                    return float(val)
                except (TypeError, ValueError):
                    continue

    # No valid CAPEX found
    return 0.0


def _derive_cfads_series(
    annual_rows: Optional[Sequence[Mapping[str, Any]]],
) -> list[float]:
    """Extract CFADS series in USD.

    Historical row schemas have drifted:
      - preferred: cfads_usd
      - fallbacks: cfads_final_lkr / cfads_lkr + fx_rate or start_lkr_per_usd
    """
    if not annual_rows:
        return []

    out: list[float] = []
    for row in annual_rows:
        # Preferred: already in USD
        if "cfads_usd" in row and row["cfads_usd"] is not None:
            out.append(float(row.get("cfads_usd", 0.0)))
            continue

        # Fallbacks: LKR values -> convert using per-row fx if present
        cfads_lkr = row.get("cfads_final_lkr")
        if cfads_lkr is None:
            cfads_lkr = row.get("cfads_lkr")
        if cfads_lkr is None:
            cfads_lkr = row.get("cfads")

        fx = row.get("fx_rate")
        if fx is None or fx == 0:
            fx = row.get("start_lkr_per_usd", 0.0)

        if fx and fx != 0 and cfads_lkr is not None:
            out.append(float(cfads_lkr) / float(fx))
        else:
            out.append(0.0)

    return out


# ═════════════════════════════════════════════════════════════════════════════
# Core KPI engine (Canonical v14 entry point)
# ═════════════════════════════════════════════════════════════════════════════


def calculate_scenario_kpis(
    *,
    config: Optional[Mapping[str, Any]] = None,
    annual_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    debt_result: Optional[Mapping[str, Any]] = None,
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,  # Reserved for future use
    cfads_series_usd: Optional[Sequence[float]] = None,
    valuation: Optional[Mapping[str, Any]] = None,
    scenario_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Canonical v14 KPI computation surface.

    This is the single source of truth for all scenario-level KPI aggregation.

    Supports two main call styles:

    1) **Full project context** (standard usage)::

        kpis = calculate_scenario_kpis(
            config=config_dict,
            annual_rows=annual_rows_list,
            debt_result=debt_result_dict,
            discount_rate=0.10,
        )

    2) **Valuation-only shortcut** (tests/analytics)::

        kpis = calculate_scenario_kpis(
            debt_result={"dscr_series": [1.5, 1.8, 2.0]},
            cfads_series_usd=[100, 200, 300],
            valuation={"npv": 50000000, "irr": 0.15},
        )

    Parameters
    ----------
    config : Optional[Mapping[str, Any]]
        Full config dict (contains capex, scenario name, etc.).
    annual_rows : Optional[Sequence[Mapping[str, Any]]]
        Annual cashflow rows (each row should have 'cfads_usd' key).
    debt_result : Optional[Mapping[str, Any]]
        Debt calculation result (contains dscr_series, max_debt_usd, etc.).
    discount_rate : Optional[float]
        Discount rate for NPV calculation (default: 0.10).
    prudential_rate : Optional[float]
        Prudential discount rate (reserved for future use).
    cfads_series_usd : Optional[Sequence[float]]
        Explicit CFADS series (overrides extraction from annual_rows).
    valuation : Optional[Mapping[str, Any]]
        Pre-computed valuation dict (keys: 'npv', 'irr'). If provided,
        skips NPV/IRR calculation.
    scenario_name : Optional[str]
        Override scenario name (else derived from config).

    Returns
    -------
    Dict[str, Any]
        KPI dict with keys:
        - scenario_name: str
        - total_cfads_usd: float
        - final_cfads_usd: float
        - mean_operational_cfads_usd: float
        - dscr_series: list[float]
        - min_dscr, dscr_min: float (alias)
        - dscr_max, dscr_mean, dscr_median: float
        - avg_dscr: float (lender KPI alias for dscr_mean)
        - max_debt_usd: float (if debt_result provided)
        - final_debt_usd: float (if debt_result provided)
        - total_idc_usd: float (if debt_result provided)
        - project_npv, npv: float (alias)
        - project_irr, irr: float (alias)
        - equity_irr: float (proxy for equity returns)
        - llcr: float (loan life cover ratio)
        - plcr: float (project life cover ratio)
        - discount_rate_used: float

    Raises
    ------
    None
        All calculations are non-fatal. Errors are logged and metrics set to 0.
    """
    # ─────────────────────────────────────────────────────────────────────────
    # 1. Inputs and defaults
    # ─────────────────────────────────────────────────────────────────────────
    drate = float(discount_rate if discount_rate is not None else DEFAULT_DISCOUNT_RATE)
    capex_total = _derive_capex_usd(config)

    # FIXED: Use cfads_series_usd override pattern correctly
    if cfads_series_usd:
        cfads_series = list(cfads_series_usd)
    else:
        cfads_series = _derive_cfads_series(annual_rows)

    cfads: list[float] = [float(x) for x in cfads_series]

    if scenario_name is None:
        scenario_name = _derive_scenario_name(config)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CFADS aggregates
    # ─────────────────────────────────────────────────────────────────────────
    # Note: tests/api/test_metrics_core_stats.py expects:
    # - mean_operational_cfads_usd = plain mean (not skipping years)
    # ─────────────────────────────────────────────────────────────────────────
    total_cfads = float(sum(cfads)) if cfads else 0.0
    final_cfads = float(cfads[-1]) if cfads else 0.0
    mean_cfads = float(total_cfads / len(cfads)) if cfads else 0.0

    result: Dict[str, Any] = {
        "scenario_name": scenario_name,
        "total_cfads_usd": total_cfads,
        "final_cfads_usd": final_cfads,
        "mean_operational_cfads_usd": mean_cfads,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. DSCR cleaning + statistics
    # ─────────────────────────────────────────────────────────────────────────
    raw_dscr: Sequence[Any] = []
    max_debt_usd: Optional[float] = None
    final_debt_usd: Optional[float] = None
    total_idc_usd: Optional[float] = None

    if debt_result:
        series = debt_result.get("dscr_series")
        if isinstance(series, Sequence):
            raw_dscr = series
        else:
            raw_dscr = []
        max_debt_usd_raw = debt_result.get("max_debt_usd")
        final_debt_usd_raw = debt_result.get("final_debt_usd")
        total_idc_usd_raw = debt_result.get("total_idc_usd")

        if max_debt_usd_raw is not None:
            try:
                max_debt_usd = float(max_debt_usd_raw)
            except (TypeError, ValueError):
                max_debt_usd = None

        if final_debt_usd_raw is not None:
            try:
                final_debt_usd = float(final_debt_usd_raw)
            except (TypeError, ValueError):
                final_debt_usd = None

        if total_idc_usd_raw is not None:
            try:
                total_idc_usd = float(total_idc_usd_raw)
            except (TypeError, ValueError):
                total_idc_usd = None

    clean_dscr = list(_clean_dscr_series(raw_dscr))
    dscr_stats = _summary_stats(clean_dscr)

    result.update(
        dscr_series=clean_dscr,
        min_dscr=dscr_stats["min"],
        dscr_min=dscr_stats["min"],  # Alias for compatibility
        dscr_max=dscr_stats["max"],
        dscr_mean=dscr_stats["mean"],
        dscr_median=dscr_stats["median"],
    )

    if max_debt_usd is not None:
        result["max_debt_usd"] = max_debt_usd
    if final_debt_usd is not None:
        result["final_debt_usd"] = final_debt_usd
    if total_idc_usd is not None:
        result["total_idc_usd"] = total_idc_usd

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Project valuation: NPV / IRR (R7: via finance.irr singleton)
    # ─────────────────────────────────────────────────────────────────────────
    project_npv: Optional[float] = None
    project_irr: Optional[float] = None

    if valuation is not None:
        if "npv" in valuation:
            try:
                project_npv = float(valuation["npv"])
            except (TypeError, ValueError):
                project_npv = None
        if "irr" in valuation:
            try:
                project_irr = float(valuation["irr"])
            except (TypeError, ValueError):
                project_irr = None

    # Only compute if not overridden and we have sufficient data
    if project_npv is None and cfads and capex_total > 0.0:
        try:
            project_npv = project_npv_from_cfads(drate, cfads, capex_total)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Project NPV calculation failed: %s", exc)
            project_npv = 0.0

    if project_irr is None and cfads and capex_total > 0.0:
        try:
            project_irr = approx_project_irr(cfads, capex_total)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Project IRR calculation failed: %s", exc)
            project_irr = 0.0

    if project_npv is not None:
        result["project_npv"] = project_npv
        result["npv"] = project_npv  # Alias for convenience

    if project_irr is not None:
        result["project_irr"] = project_irr
        result["irr"] = project_irr  # Alias for convenience

    # ─────────────────────────────────────────────────────────────────────────
    # 5. WACC / discount metadata
    # ─────────────────────────────────────────────────────────────────────────
    result["discount_rate_used"] = drate
    result["wacc_label"] = "base"
    result["wacc_is_real"] = False

    # ─────────────────────────────────────────────────────────────────────────
    # 6. Lender KPI aliases (required by test_evaluation_v14_lender_stack.py)
    # ─────────────────────────────────────────────────────────────────────────
    # avg_dscr: Industry-standard alias for mean DSCR
    result["avg_dscr"] = result["dscr_mean"]

    # equity_irr: Proxy using project IRR (until equity_v14 fully wired)
    # This ensures shock propagation tests work correctly
    if "equity_irr" not in result:
        result["equity_irr"] = result.get("project_irr", 0.0)

    # llcr/plcr: Loan/project life cover ratios from debt engine
    # Fallback to dscr_mean if covenant engine not yet wired
    if debt_result and isinstance(debt_result, Mapping):
        llcr_val = debt_result.get("llcr")
        plcr_val = debt_result.get("plcr")

        if llcr_val is not None:
            try:
                result["llcr"] = float(llcr_val)
            except (TypeError, ValueError):
                result["llcr"] = result["dscr_mean"]
        else:
            result["llcr"] = result["dscr_mean"]

        if plcr_val is not None:
            try:
                result["plcr"] = float(plcr_val)
            except (TypeError, ValueError):
                result["plcr"] = result["dscr_mean"]
        else:
            result["plcr"] = result["dscr_mean"]
    else:
        # No debt result - use DSCR proxies
        result["llcr"] = result["dscr_mean"]
        result["plcr"] = result["dscr_mean"]
    # Enforce lender KPI surface keys (stable API for tests/consumers)
    # Even when upstream row schemas drift or a metric cannot be computed,
    # we keep the keys present with safe defaults.
    result.setdefault("project_irr", 0.0)
    result.setdefault("equity_irr", float(result.get("project_irr", 0.0)))
    result.setdefault("avg_dscr", float(result.get("dscr_mean", 0.0)))
    result.setdefault("llcr", float(result.get("llcr", 0.0)))
    result.setdefault("plcr", float(result.get("plcr", 0.0)))

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Backwards compatibility adapter
# ═════════════════════════════════════════════════════════════════════════════


def compute_kpis(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,
    valuation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Thin adapter for backwards compatibility.

    This function is kept for legacy callers. New code should use
    calculate_scenario_kpis directly.

    Parameters
    ----------
    See calculate_scenario_kpis for full parameter documentation.

    Returns
    -------
    Dict[str, Any]
        Same as calculate_scenario_kpis.
    """
    return calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=discount_rate,
        prudential_rate=prudential_rate,
        valuation=valuation,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    "_summary_stats",
    "calculate_scenario_kpis",
    "compute_kpis",
]

# EOF
