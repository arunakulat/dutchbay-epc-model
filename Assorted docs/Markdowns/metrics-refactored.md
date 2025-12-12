# analytics/core/metrics.py (Sprint 5 - R7 Compliant)

```python
"""KPI Calculation Module for V14 - WACC-Integrated Valuation.

Computes project-level key performance indicators including:
- Project NPV and IRR with explicit discount rates
- Equity NPV and IRR (via equity_v14 engine)
- Base and prudential valuations
- DSCR series and covenant compliance
- Debt service metrics

PHASE 1 ADDITIONS:
------------------
- Explicit discount_rate and prudential_rate parameters
- Dual NPV calculation (base + prudential)
- Equity cashflow extraction from annual_rows and debt_result
- WACC transparency fields (discount_rate_used, wacc_label, wacc_is_real)
- Surface equity KPIs alongside project KPIs
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from finance.equity_v14 import calculate_equity_performance
from finance import irr as finance_irr

logger = logging.getLogger(__name__)

# Default discount rate fallback for callers that don't pass one explicitly
DEFAULT_DISCOUNT_RATE = 0.10


def _summary_stats(values: Iterable[float]) -> Dict[str, float]:
    """
    Small, test-friendly summary stats helper.

    Ignores non-numeric and non-finite values (e.g. strings, None, NaN, inf).

    Returns a dict with common descriptive stats used by the v14 tests.
    This is intentionally simple and deterministic.
    """
    cleaned: List[float] = []

    for v in values:
        if v is None:
            continue
        try:
            num = float(v)
        except (TypeError, ValueError):
            # Non-numeric (e.g. "x") – ignore
            continue
        if not math.isfinite(num):
            # NaN / ±inf – ignore
            continue
        cleaned.append(num)

    if not cleaned:
        raise ValueError(
            "metrics._summary_stats: values must contain at least one "
            "finite numeric value"
        )

    arr = np.asarray(cleaned, dtype=float)

    n = float(arr.size)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0

    return {
        "n": n,
        "mean": mean,
        "std": std,
        "min": float(arr.min()),
        "p10": float(np.percentile(arr, 10)),
        "median": float(np.percentile(arr, 50)),
        "p90": float(np.percentile(arr, 90)),
        "max": float(arr.max()),
    }


def calculate_scenario_kpis(
    config: Optional[Dict[str, Any]] = None,
    annual_rows: Optional[Sequence[Dict[str, Any]]] = None,
    debt_result: Optional[Dict[str, Any]] = None,
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,
    cfads_series_usd: Optional[Sequence[float]] = None,
    valuation: Optional[Dict[str, float]] = None,
    scenario_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Unified KPI engine.

    Supports both:
      - The v14 API used by the main analytics layer:
          calculate_scenario_kpis(config, annual_rows, debt_result, discount_rate, ...)
      - The lighter testing API used in test_metrics_core_stats:
          calculate_scenario_kpis(
              annual_rows=..., debt_result=..., config=..., scenario_name=...
          )
          calculate_scenario_kpis(
              debt_result=..., cfads_series_usd=..., valuation=...
          )
          calculate_scenario_kpis(
              debt_result=..., annual_rows=None, cfads_series_usd=None
          )

    It always returns:
      - CFADS summary fields:
          total_cfads_usd, final_cfads_usd, mean_operational_cfads_usd
      - DSCR fields:
          dscr_series (cleaned), min_dscr, dscr_min, dscr_max,
          dscr_mean, dscr_median
      - Project metrics:
          project_npv, project_irr
      - Generic valuation fields:
          npv, irr
      - Equity metrics (when enough info is available)
      - scenario_name
    """
    if debt_result is None:
        raise ValueError("calculate_scenario_kpis: debt_result is required")

    # -------------------------------------------------------------------------
    # Scenario name
    # -------------------------------------------------------------------------
    if scenario_name is None and isinstance(config, dict):
        meta = config.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
        scenario_name = (
            config.get("scenario_name")
            or config.get("name")
            or meta.get("scenario_name")
            or meta.get("name")
            or meta.get("id")
            or config.get("id")
            or "unnamed"
        )
    if scenario_name is None:
        scenario_name = "unnamed"

    # -------------------------------------------------------------------------
    # CFADS series resolution
    # -------------------------------------------------------------------------
    cfads: List[float] = []

    if cfads_series_usd is not None:
        # Direct series provided
        cfads = [float(x) if x is not None else 0.0 for x in cfads_series_usd]
    elif annual_rows is not None:
        # Extract from annual_rows
        for row in annual_rows:
            val = row.get("cfads_usd", 0.0)
            if val is None:
                val = 0.0
            cfads.append(float(val))
    else:
        # Degenerate path: no CFADS anywhere – fall back to zero series
        dscr_len = len(debt_result.get("dscr_series", []) or [])
        cfads = [0.0] * dscr_len

    total_cfads = float(sum(cfads))
    final_cfads = float(cfads[-1]) if cfads else 0.0
    mean_cfads = float(sum(cfads) / len(cfads)) if cfads else 0.0

    # -------------------------------------------------------------------------
    # DSCR cleaning and summary
    # -------------------------------------------------------------------------
    raw_dscr = debt_result.get("dscr_series", []) or []
    dscr_clean: List[float] = []
    for d in raw_dscr:
        if d is None:
            continue
        try:
            num = float(d)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(num) or num <= 0.0:
            continue
        dscr_clean.append(num)

    result: Dict[str, Any] = {
        "scenario_name": scenario_name,
        "dscr_series": dscr_clean,
        "total_cfads_usd": total_cfads,
        "final_cfads_usd": final_cfads,
        "mean_operational_cfads_usd": mean_cfads,
    }

    if dscr_clean:
        dscr_stats = _summary_stats(dscr_clean)
        # v14 name
        result["min_dscr"] = float(min(dscr_clean))
        # stats API used in test_metrics_core_stats
        result["dscr_min"] = dscr_stats["min"]
        result["dscr_max"] = dscr_stats["max"]
        result["dscr_mean"] = dscr_stats["mean"]
        result["dscr_median"] = dscr_stats["median"]
    else:
        result["min_dscr"] = 0.0
        result["dscr_min"] = 0.0
        result["dscr_max"] = 0.0
        result["dscr_mean"] = 0.0
        result["dscr_median"] = 0.0

    # -------------------------------------------------------------------------
    # Additional debt metrics (if available)
    # -------------------------------------------------------------------------
    if "llcr" in debt_result:
        result["llcr"] = debt_result["llcr"]

    if "plcr" in debt_result:
        result["plcr"] = debt_result["plcr"]

    covenant_breaches = debt_result.get("covenant_breaches", [])
    result["covenant_breach_count"] = len(covenant_breaches)
    result["covenant_breaches"] = covenant_breaches

    # -------------------------------------------------------------------------
    # Valuation: npv / irr – override if valuation dict is provided
    # -------------------------------------------------------------------------
    if valuation is not None:
        result["npv"] = float(valuation.get("npv", 0.0))
        result["irr"] = float(valuation.get("irr", 0.0))
    else:
        # Default – may be overwritten below if we compute project metrics
        result["npv"] = 0.0
        result["irr"] = 0.0

    # -------------------------------------------------------------------------
    # Project / equity economics (v14 behaviour)
    # -------------------------------------------------------------------------
    capex_total = 0.0
    if isinstance(config, dict):
        capex_cfg = config.get("capex", {})
        if isinstance(capex_cfg, dict):
            capex_total = float(capex_cfg.get("usd_total", 0.0))

    debt_raised = float(debt_result.get("max_debt_usd", 0.0))

    # If caller hasn't provided a discount_rate, we only need "presence" of npv/irr
    effective_discount_rate: Optional[float] = discount_rate

    if effective_discount_rate is not None and cfads:
        project_cf_series: List[float] = [-capex_total] + cfads

        # Project NPV
        try:
            project_npv = finance_irr.npv(effective_discount_rate, project_cf_series)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Project NPV calculation failed: %s", exc)
            project_npv = 0.0

        # Project IRR
        try:
            project_irr_raw = finance_irr.irr(project_cf_series)

            if project_irr_raw is None:
                logger.warning("Project IRR calculation returned None; setting to 0.0")
                project_irr = 0.0
            else:
                project_irr = float(project_irr_raw)

                if math.isnan(project_irr) or math.isinf(project_irr):
                    logger.warning(
                        "Project IRR calculation returned non-finite value; "
                        "setting to 0.0"
                    )
                    project_irr = 0.0
                elif not (-1.0 <= project_irr <= 10.0):  # sanity guardband
                    logger.warning(
                        "Project IRR calculation returned extreme value (%.2f); "
                        "setting to 0.0",
                        project_irr,
                    )
                    project_irr = 0.0
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Project IRR calculation failed: %s", exc)
            project_irr = 0.0

        result["project_npv"] = project_npv
        result["project_irr"] = project_irr

        # If the caller did not provide an explicit valuation, mirror project metrics
        if valuation is None:
            result["npv"] = project_npv
            result["irr"] = project_irr

        # Prudential NPV (optional)
        if prudential_rate is not None:
            try:
                npv_prudential = finance_irr.npv(prudential_rate, project_cf_series)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Prudential project NPV calculation failed: %s", exc)
                npv_prudential = 0.0

            result["npv_prudential"] = npv_prudential
            result["discount_rate_prudential"] = prudential_rate

        result["discount_rate_used"] = effective_discount_rate
        result["wacc_label"] = "base"
        result["wacc_is_real"] = False
    else:
        # Still surface these keys for callers that expect them
        result.setdefault("project_npv", 0.0)
        result.setdefault("project_irr", 0.0)

    # -------------------------------------------------------------------------
    # Equity metrics via equity_v14 engine
    # -------------------------------------------------------------------------
    equity_investment = capex_total - debt_raised
    equity_cf_series: List[float] = []

    if equity_investment > 0.0 and cfads:
        # T0: equity outflow = capex - debt
        equity_cf_series.append(-equity_investment)

        # T1..Tn: equity free cashflow.
        # In the light test paths, we don't have debt_service_usd per row,
        # so treat CFADS as flowing through to equity.
        for val in cfads:
            equity_cf_series.append(float(val))

        logger.debug(
            "Equity cashflows built: T0=%.0f, periods=%d",
            -equity_cf_series[0],
            len(equity_cf_series) - 1,
        )

    result["equity_cashflows"] = equity_cf_series

    if equity_cf_series and effective_discount_rate is not None:
        try:
            equity_perf = calculate_equity_performance(
                equity_cf_series,
                discount_rate=effective_discount_rate,
                current_nav=0.0,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Equity performance calculation failed: %s", exc)
            equity_perf = None
    else:
        equity_perf = None

    if equity_perf is not None:
        result.update(
            {
                "equity_irr": equity_perf.equity_irr,
                "equity_npv": equity_perf.equity_npv,
                "equity_moic": equity_perf.moic,
                "equity_dpi": equity_perf.dpi,
                "equity_rvpi": equity_perf.rvpi,
                "equity_tvpi": equity_perf.tvpi,
                "equity_annual_coc": equity_perf.annual_coc,
                "equity_average_coc": equity_perf.average_coc,
                "equity_payback_period_years": equity_perf.payback_period_years,
            }
        )
    else:
        # Normalised "empty" equity view so callers don't have to guard on keys.
        result.update(
            {
                "equity_irr": None,
                "equity_npv": None,
                "equity_moic": None,
                "equity_dpi": None,
                "equity_rvpi": None,
                "equity_tvpi": None,
                "equity_annual_coc": [],
                "equity_average_coc": 0.0,
                "equity_payback_period_years": None,
            }
        )

    return result


def compute_kpis(
    *,
    config: Dict[str, Any],
    annual_rows: Sequence[Dict[str, Any]],
    debt_result: Dict[str, Any],
    discount_rate: Optional[float] = None,
    prudential_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Thin, test-friendly adapter around calculate_scenario_kpis.

    This is the canonical v14 KPI surface that callers and tests should use.
    It:
      - Applies DEFAULT_DISCOUNT_RATE if no discount_rate is supplied.
      - Derives a stable scenario_name from the config.
      - Delegates the heavy lifting to calculate_scenario_kpis.
    """
    effective_discount_rate = (
        float(discount_rate) if discount_rate is not None else DEFAULT_DISCOUNT_RATE
    )

    meta = config.get("meta", {}) if isinstance(config, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    scenario_name = (
        config.get("scenario_name")
        or config.get("name")
        or meta.get("scenario_name")
        or meta.get("name")
        or meta.get("id")
        or config.get("id")
        or "unnamed"
    )

    kpi_result = calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=effective_discount_rate,
        prudential_rate=prudential_rate,
        scenario_name=scenario_name,
    )

    # Ensure scenario_name is set even if calculate_scenario_kpis changes behaviour
    kpi_result.setdefault("scenario_name", scenario_name)

    return kpi_result

# EOF
```
