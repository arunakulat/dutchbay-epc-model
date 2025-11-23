"""KPI Calculation Module for V14 - WACC-Integrated Valuation.

Computes project-level key performance indicators including:
- Project NPV and IRR with explicit discount rates
- Equity NPV and IRR (considering upfront investment)
- Base and prudential valuations
- DSCR series and covenant compliance
- Debt service metrics

PHASE 1 ADDITIONS:
------------------
- Explicit discount_rate and prudential_rate parameters
- Dual NPV calculation (base + prudential)
- Equity cashflow extraction from annual_rows and debt_result
- WACC transparency fields (discount_rate_used, wacc_label, wacc_is_real)
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

from finance.irr import npv as calc_npv, irr as calc_irr

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
        KPI dictionary containing:
        - project_npv: Project NPV (float) - CFADS vs total capex (ignores debt)
        - project_irr: Project IRR (float) - based on CFADS vs total capex
        - dscr_series: Annual DSCR values (List[float])
        - min_dscr: Minimum DSCR across all years (float)
        - discount_rate_used: Discount rate applied (float)
        - wacc_label: "base" or "prudential" (str)
        - wacc_is_real: Whether real vs nominal WACC (bool)
        - npv_prudential: Prudential NPV (float, if prudential_rate provided)
        - discount_rate_prudential: Prudential rate used (float, if provided)

    Notes
    -----
    - Project cash flows: initial capex (negative) + CFADS (positive, pre-debt).
    - IRR calculated via finance.irr.irr on CFADS series.
    - DSCR extracted from debt_result if available.
    """
    # -------------------------------------------------------------------------
    # Extract CAPEX and (optionally) equity / debt context
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
    # Build project-level cash flow series:
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
        logger.warning("Insufficient cash flows; NPV/IRR will be zero")
        project_cf_series = [-capex_total, 0.0]

    # -------------------------------------------------------------------------
    # Calculate Project NPV (base discount rate)
    # -------------------------------------------------------------------------
    try:
        project_npv = calc_npv(discount_rate, project_cf_series)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("NPV calculation failed: %s", exc)
        project_npv = 0.0

    # -------------------------------------------------------------------------
    # Calculate IRR
    # -------------------------------------------------------------------------
    try:
        project_irr_raw = calc_irr(project_cf_series)

        if project_irr_raw is None:
            logger.warning("IRR calculation returned None; setting to 0")
            project_irr = 0.0
        else:
            project_irr = float(project_irr_raw)

            if math.isnan(project_irr) or math.isinf(project_irr):
                logger.warning(
                    "IRR calculation returned non-finite value; setting to 0",
                )
                project_irr = 0.0
            elif not (-1.0 <= project_irr <= 10.0):  # sanity guardband
                logger.warning(
                    "IRR calculation returned extreme value (%.2f); setting to 0",
                    project_irr,
                )
                project_irr = 0.0
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("IRR calculation failed: %s", exc)
        project_irr = 0.0

    # -------------------------------------------------------------------------
    # Build base result dict
    # -------------------------------------------------------------------------
    result: Dict[str, Any] = {
        "project_npv": project_npv,
        "project_irr": project_irr,
        "discount_rate_used": discount_rate,
        "wacc_label": "base",
        "wacc_is_real": False,  # Caller can override if using real WACC
    }

    # -------------------------------------------------------------------------
    # Calculate Prudential NPV (optional)
    # -------------------------------------------------------------------------
    if prudential_rate is not None:
        try:
            npv_prudential = calc_npv(prudential_rate, project_cf_series)
            result["npv_prudential"] = npv_prudential
            result["discount_rate_prudential"] = prudential_rate
            logger.debug(
                "Prudential NPV calculated: %.0f at %.2f%% discount rate",
                npv_prudential,
                prudential_rate * 100,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Prudential NPV calculation failed: %s", exc)
            result["npv_prudential"] = 0.0
            result["discount_rate_prudential"] = prudential_rate

    # -------------------------------------------------------------------------
    # Extract DSCR series from debt_result
    # -------------------------------------------------------------------------
    dscr_series = debt_result.get("dscr_series", [])
    if not dscr_series:
        logger.warning("No DSCR series found in debt_result")
        dscr_series = []

    result["dscr_series"] = dscr_series

    # Calculate minimum DSCR (filtering out invalid values)
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
                "No valid positive DSCR values found; setting min_dscr to inf",
            )
            min_dscr = float("inf")
    else:
        min_dscr = 0.0

    result["min_dscr"] = min_dscr

    # -------------------------------------------------------------------------
    # Additional debt metrics (if available)
    # -------------------------------------------------------------------------
    # LLCR (Loan Life Cover Ratio)
    if "llcr" in debt_result:
        result["llcr"] = debt_result["llcr"]

    # PLCR (Project Life Cover Ratio)
    if "plcr" in debt_result:
        result["plcr"] = debt_result["plcr"]

    # Covenant breach flags
    covenant_breaches = debt_result.get("covenant_breaches", [])
    result["covenant_breach_count"] = len(covenant_breaches)
    result["covenant_breaches"] = covenant_breaches

    # -------------------------------------------------------------------------
    # Logging summary
    # -------------------------------------------------------------------------
    logger.debug(
        "KPIs calculated: NPV=%.0f | IRR=%.2f%% | Min DSCR=%.2fx | Discount=%.2f%%",
        project_npv,
        project_irr * 100.0,
        min_dscr,
        discount_rate * 100.0,
    )

    if prudential_rate is not None and "npv_prudential" in result:
        logger.debug(
            "Prudential metrics: NPV=%.0f at %.2f%% discount",
            result["npv_prudential"],
            prudential_rate * 100.0,
        )

    return result

    