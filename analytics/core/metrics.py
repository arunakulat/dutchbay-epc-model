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
"""

from __future__ import annotations

import logging
import math
from statistics import median
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

from finance.irr import approx_project_irr, project_npv_from_cfads

logger = logging.getLogger(__name__)

DEFAULT_DISCOUNT_RATE = 0.10


def _summary_stats(values: Iterable[float]) -> Dict[str, float]:
    """Return robust statistics for a numeric series."""
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
    sd = math.sqrt(sum((x - mu) ** 2 for x in cleaned) / n) if n > 1 else 0.0

    def _percentile(sorted_vals: list[float], q: float) -> float:
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
    """Clean DSCR series: drop None, non-finite, and non-positive values."""
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
        if not math.isfinite(x) or x <= 0.0:
            continue
        out.append(x)
    return out


def _lookup_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    key_lower = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def _section_case_insensitive(config: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = _lookup_case_insensitive(config, key)
    return value if isinstance(value, Mapping) else None


def _derive_scenario_name(config: Optional[Mapping[str, Any]]) -> str:
    """Extract scenario name from config using exact/case-insensitive keys."""
    if not config:
        return ""
    for key in ("scenario_name", "name", "id"):
        value = _lookup_case_insensitive(config, key)
        if value is not None:
            return str(value)
    meta = _section_case_insensitive(config, "meta")
    if meta:
        for key in ("scenario_name", "name", "id"):
            value = _lookup_case_insensitive(meta, key)
            if value is not None:
                return str(value)
    project = _section_case_insensitive(config, "project")
    if project:
        value = _lookup_case_insensitive(project, "name")
        if value is not None:
            return str(value)
    return ""


def _derive_capex_usd(config: Optional[Mapping[str, Any]]) -> float:
    """Extract total CAPEX from canonical, legacy, or compact lender schemas."""
    if not config:
        return 0.0

    section_candidates = [
        ("finance", ("capex_total_usd", "capex_usd")),
        ("capex", ("usd_total", "capex_total_usd", "total_capex_usd", "total_capex")),
        ("costs", ("capex_total_usd", "capex_usd", "total_capex_usd", "total_capex")),
    ]
    for section_name, keys in section_candidates:
        section = _section_case_insensitive(config, section_name)
        if not section:
            continue
        for key in keys:
            value = _lookup_case_insensitive(section, key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    for key in ("capex_usd_total", "capex_total_usd", "total_capex_usd"):
        value = _lookup_case_insensitive(config, key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue

    return 0.0


def _derive_cfads_series(annual_rows: Optional[Sequence[Mapping[str, Any]]]) -> list[float]:
    """Extract CFADS series in USD, with LKR fallback conversion."""
    if not annual_rows:
        return []

    out: list[float] = []
    for row in annual_rows:
        if "cfads_usd" in row and row["cfads_usd"] is not None:
            out.append(float(row.get("cfads_usd", 0.0)))
            continue

        cfads_lkr = row.get("cfads_final_lkr")
        if cfads_lkr is None:
            cfads_lkr = row.get("cfads_lkr")
        if cfads_lkr is None:
            cfads_lkr = row.get("cfads")

        fx = row.get("fx_rate") or row.get("start_lkr_per_usd") or 0.0
        if fx and cfads_lkr is not None:
            out.append(float(cfads_lkr) / float(fx))
        else:
            out.append(0.0)
    return out


def calculate_scenario_kpis(
    *,
    config: Optional[Mapping[str, Any]] = None,
    annual_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    debt_result: Optional[Mapping[str, Any]] = None,
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,
    cfads_series_usd: Optional[Sequence[float]] = None,
    valuation: Optional[Mapping[str, Any]] = None,
    scenario_name: Optional[str] = None,
    wacc_is_real: Optional[bool] = None,
    wacc_label: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical v14 KPI computation surface.

    ``wacc_is_real`` / ``wacc_label`` describe the discount basis. The pipeline
    passes the resolved truth (whether the build-up WACC actually drove the
    project discount); when omitted they are derived from ``config['wacc']``
    (config-first, ARCH-01), so standalone callers stay correct too.
    """
    drate = float(discount_rate if discount_rate is not None else DEFAULT_DISCOUNT_RATE)
    capex_total = _derive_capex_usd(config)

    if cfads_series_usd:
        cfads = [float(x) for x in cfads_series_usd]
    else:
        cfads = [float(x) for x in _derive_cfads_series(annual_rows)]

    if scenario_name is None:
        scenario_name = _derive_scenario_name(config)

    total_cfads = float(sum(cfads)) if cfads else 0.0
    final_cfads = float(cfads[-1]) if cfads else 0.0
    mean_cfads = float(total_cfads / len(cfads)) if cfads else 0.0

    result: Dict[str, Any] = {
        "scenario_name": scenario_name,
        "total_cfads_usd": total_cfads,
        "final_cfads_usd": final_cfads,
        "mean_operational_cfads_usd": mean_cfads,
    }

    raw_dscr: Sequence[Any] = []
    max_debt_usd: Optional[float] = None
    final_debt_usd: Optional[float] = None
    total_idc_usd: Optional[float] = None

    if debt_result:
        series = debt_result.get("dscr_series")
        raw_dscr = series if isinstance(series, Sequence) else []
        for source_key, target_name in (
            ("max_debt_usd", "max_debt_usd"),
            ("debt_total", "max_debt_usd"),
            ("final_debt_usd", "final_debt_usd"),
            ("total_idc_usd", "total_idc_usd"),
            ("total_idc", "total_idc_usd"),
        ):
            value = debt_result.get(source_key)
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if target_name == "max_debt_usd" and max_debt_usd is None:
                max_debt_usd = numeric
            elif target_name == "final_debt_usd" and final_debt_usd is None:
                final_debt_usd = numeric
            elif target_name == "total_idc_usd" and total_idc_usd is None:
                total_idc_usd = numeric

    clean_dscr = list(_clean_dscr_series(raw_dscr))
    dscr_stats = _summary_stats(clean_dscr)

    result.update(
        dscr_series=clean_dscr,
        min_dscr=dscr_stats["min"],
        dscr_min=dscr_stats["min"],
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
        result["npv"] = project_npv

    if project_irr is not None:
        result["project_irr"] = project_irr
        result["irr"] = project_irr

    # WACC reporting basis. Prefer the caller-resolved truth (the pipeline knows
    # whether the build-up WACC actually drove `drate`); else derive from config
    # so the label/flag never silently contradict the rate actually used.
    if wacc_is_real is None or wacc_label is None:
        wacc_cfg = (config or {}).get("wacc", {}) or {}
        _drives = bool(wacc_cfg.get("drives_discount_rate"))
        _mode = str(wacc_cfg.get("mode") or "")
        if wacc_is_real is None:
            wacc_is_real = _drives
        if wacc_label is None:
            wacc_label = _mode if (_drives and _mode) else "base"
    result["discount_rate_used"] = drate
    result["wacc_label"] = wacc_label
    result["wacc_is_real"] = bool(wacc_is_real)

    result["avg_dscr"] = result["dscr_mean"]
    if "equity_irr" not in result:
        result["equity_irr"] = result.get("project_irr", 0.0)

    if debt_result and isinstance(debt_result, Mapping):
        for metric_name in ("llcr", "plcr"):
            value = debt_result.get(metric_name)
            if value is not None:
                try:
                    result[metric_name] = float(value)
                    continue
                except (TypeError, ValueError):
                    pass
            result[metric_name] = result["dscr_mean"]
        # Balloon covenant surface (numeric, so it survives KPI normalisation and
        # can be used as an optimisation constraint key, e.g. balloon_pct <= 0.10).
        result["balloon_pct"] = float(debt_result.get("balloon_pct") or 0.0)
        result["balloon_residual"] = float(debt_result.get("balloon_residual") or 0.0)
        result["balloon_covenant_breach"] = (
            1.0 if bool(debt_result.get("balloon_covenant_breach")) else 0.0
        )
    else:
        result["llcr"] = result["dscr_mean"]
        result["plcr"] = result["dscr_mean"]

    # Stable lender KPI surface. Keep keys present even when a metric cannot be
    # computed from a minimal/hand-authored scenario. This is API stability, not
    # economic substitution: callers can still inspect the zero default.
    result.setdefault("project_npv", 0.0)
    result.setdefault("npv", float(result.get("project_npv", 0.0)))
    result.setdefault("project_irr", 0.0)
    result.setdefault("irr", float(result.get("project_irr", 0.0)))
    result.setdefault("equity_irr", float(result.get("project_irr", 0.0)))
    result.setdefault("avg_dscr", float(result.get("dscr_mean", 0.0)))
    result.setdefault("llcr", float(result.get("llcr", 0.0)))
    result.setdefault("plcr", float(result.get("plcr", 0.0)))

    return result


def compute_kpis(
    *,
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    debt_result: Mapping[str, Any],
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,
    valuation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Thin adapter for backwards compatibility."""
    return calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=discount_rate,
        prudential_rate=prudential_rate,
        valuation=valuation,
    )


__all__ = [
    "_summary_stats",
    "calculate_scenario_kpis",
    "compute_kpis",
]
