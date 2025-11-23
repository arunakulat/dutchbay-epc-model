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
from typing import Any, Dict, List, Optional, Sequence

from finance.irr import npv as calc_npv, irr as calc_irr
from finance.equity_v14 import calculate_equity_performance

logger = logging.getLogger(__name__)

# Default discount rate fallback
DEFAULT_DISCOUNT_RATE = 0.10


def calculate_scenario_kpis(
    config: Dict[str, Any],
    annual_rows: Sequence[Dict[str, Any]],
    debt_result: Dict[str, Any],
    discount_rate: float,
    prudential_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Calculate comprehensive KPIs for a single scenario with WACC-aware valuation.

    Parameters
    ----------
    config : Dict[str, Any]
        Full scenario configuration (for context/metadata).
    annual_rows : Sequence[Dict[str, Any]]
        Annual cashflow rows from build_annual_rows().
    debt_result : Dict[str, Any]
        Debt layer results from apply_debt_layer().
    discount_rate : float
        Base discount rate (typically WACC nominal) for NPV calculation.
    prudential_rate : Optional[float]
        Prudential discount rate (e.g., WACC + 100 bps) for conservative valuation.
        If provided, calculates npv_prudential.

    Returns
    -------
    Dict[str, Any]
        KPI dictionary containing at least:
        - project_npv: Project NPV (float) - CFADS vs total capex (ignores debt)
        - project_irr: Project IRR (float) - based on CFADS vs total capex
        - dscr_series: Annual DSCR values (List[float])
        - min_dscr: Minimum DSCR across all years (float)
        - discount_rate_used: Discount rate applied (float)
        - wacc_label: "base" (str)
        - wacc_is_real: Whether real vs nominal WACC (bool)
        - npv_prudential: Prudential NPV (float, if prudential_rate provided)
        - discount_rate_prudential: Prudential rate used (float, if provided)

        And, where possible, equity metrics:
        - equity_irr
        - equity_npv
        - equity_moic
        - equity_dpi, equity_rvpi, equity_tvpi
        - equity_annual_coc, equity_average_coc
        - equity_payback_period_years
        - equity_cashflows (raw series used)
    """
    # -------------------------------------------------------------------------
    # Extract CAPEX and debt context
    # -------------------------------------------------------------------------
    capex_total = 0.0
    capex_cfg = config.get("capex", {})
    if isinstance(capex_cfg, dict):
        capex_total = float(capex_cfg.get("usd_total", 0.0))

    debt_raised = float(debt_result.get("max_debt_usd", 0.0))

    logger.debug(
        "Project economics: Capex=%.0f | Debt raised=%.0f",
        capex_total,
        debt_raised,
    )

    # -------------------------------------------------------------------------
    # Project-level cash flow series:
    #   T0: -capex_total
    #   T1..Tn: CFADS (pre-debt, pre-equity distributions)
    # -------------------------------------------------------------------------
    project_cf_series: List[float] = [-capex_total]

    for row in annual_rows:
        cfads_usd = row.get("cfads_usd", 0.0)
        if cfads_usd is None:
            cfads_usd = 0.0
        project_cf_series.append(float(cfads_usd))

    if len(project_cf_series) <= 1:
        logger.warning("Insufficient cash flows; NPV/IRR will be zero for project series")
        project_cf_series = [-capex_total, 0.0]

    # -------------------------------------------------------------------------
    # Project NPV (base discount rate)
    # -------------------------------------------------------------------------
    try:
        project_npv = calc_npv(discount_rate, project_cf_series)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Project NPV calculation failed: %s", exc)
        project_npv = 0.0

    # -------------------------------------------------------------------------
    # Project IRR
    # -------------------------------------------------------------------------
    try:
        project_irr_raw = calc_irr(project_cf_series)

        if project_irr_raw is None:
            logger.warning("Project IRR calculation returned None; setting to 0.0")
            project_irr = 0.0
        else:
            project_irr = float(project_irr_raw)

            if math.isnan(project_irr) or math.isinf(project_irr):
                logger.warning("Project IRR calculation returned non-finite value; setting to 0.0")
                project_irr = 0.0
            elif not (-1.0 <= project_irr <= 10.0):  # sanity guardband
                logger.warning(
                    "Project IRR calculation returned extreme value (%.2f); setting to 0.0",
                    project_irr,
                )
                project_irr = 0.0
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Project IRR calculation failed: %s", exc)
        project_irr = 0.0

    # -------------------------------------------------------------------------
    # Build base result dict (project KPIs)
    # -------------------------------------------------------------------------
    result: Dict[str, Any] = {
        "project_npv": project_npv,
        "project_irr": project_irr,
        "discount_rate_used": discount_rate,
        "wacc_label": "base",
        "wacc_is_real": False,  # Caller can override if using real WACC
    }

    # -------------------------------------------------------------------------
    # Prudential NPV (optional)
    # -------------------------------------------------------------------------
    if prudential_rate is not None:
        try:
            npv_prudential = calc_npv(prudential_rate, project_cf_series)
            result["npv_prudential"] = npv_prudential
            result["discount_rate_prudential"] = prudential_rate
            logger.debug(
                "Prudential project NPV calculated: %.0f at %.2f%% discount rate",
                npv_prudential,
                prudential_rate * 100.0,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Prudential project NPV calculation failed: %s", exc)
            result["npv_prudential"] = 0.0
            result["discount_rate_prudential"] = prudential_rate

    # -------------------------------------------------------------------------
    # DSCR series from debt_result
    # -------------------------------------------------------------------------
    dscr_series = debt_result.get("dscr_series", [])
    if not dscr_series:
        logger.warning("No DSCR series found in debt_result")
        dscr_series = []

    result["dscr_series"] = dscr_series

    # Minimum DSCR (filtering out bad values but preserving genuine low numbers)
    if dscr_series:
        valid_dscrs = [
            d
            for d in dscr_series
            if d is not None
            and isinstance(d, (int, float))
            and math.isfinite(d)
            and d > 0.0  # Only positive DSCRs are meaningful
        ]
        if valid_dscrs:
            min_dscr = float(min(valid_dscrs))
        else:
            logger.warning(
                "No valid positive DSCR values found; setting min_dscr to inf "
                "(likely construction-only or malformed series).",
            )
            min_dscr = float("inf")
    else:
        min_dscr = 0.0

    result["min_dscr"] = min_dscr

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
    # Equity metrics via equity_v14 engine
    # -------------------------------------------------------------------------
    equity_investment = capex_total - debt_raised
    equity_cf_series: List[float] = []

    if equity_investment > 0.0:
        # T0: equity outflow = capex - debt
        equity_cf_series.append(-equity_investment)

        # T1..Tn: equity free cashflow = CFADS - debt service
        for row in annual_rows:
            cfads_usd = row.get("cfads_usd", 0.0)
            debt_service_usd = row.get("debt_service_usd", 0.0)

            if cfads_usd is None:
                cfads_usd = 0.0
            if debt_service_usd is None:
                debt_service_usd = 0.0

            equity_cf = float(cfads_usd) - float(debt_service_usd)
            equity_cf_series.append(equity_cf)

        logger.debug(
            "Equity cashflows built: T0=%.0f, periods=%d",
            -equity_cf_series[0],
            len(equity_cf_series) - 1,
        )
    else:
        logger.debug(
            "Equity investment <= 0 (Capex=%.0f, Debt=%.0f); "
            "skipping equity KPI calculation.",
            capex_total,
            debt_raised,
        )

    # Always surface the raw equity series for downstream analytics, even if empty
    result["equity_cashflows"] = equity_cf_series

    if equity_cf_series:
        equity_perf = calculate_equity_performance(
            equity_cf_series,
            discount_rate=discount_rate,
            current_nav=0.0,
        )
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

    # -------------------------------------------------------------------------
    # Logging summary
    # -------------------------------------------------------------------------
    logger.debug(
        "KPIs calculated: "
        "Proj NPV=%.0f | Proj IRR=%.2f%% | Min DSCR=%.2fx | Discount=%.2f%%",
        project_npv,
        project_irr * 100.0,
        min_dscr,
        discount_rate * 100.0,
    )

    if prudential_rate is not None and "npv_prudential" in result:
        logger.debug(
            "Prudential project NPV=%.0f at %.2f%% discount",
            result["npv_prudential"],
            prudential_rate * 100.0,
        )

    if equity_perf is not None:
        logger.debug(
            "Equity KPIs: IRR=%s | NPV=%s | MOIC=%s | DPI=%s | TVPI=%s",
            equity_perf.equity_irr,
            equity_perf.equity_npv,
            equity_perf.moic,
            equity_perf.dpi,
            equity_perf.tvpi,
        )

    return result

    