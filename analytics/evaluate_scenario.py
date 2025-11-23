"""Central Scenario Evaluator for V14 - WACC-Integrated."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from analytics.contracts_v14 import ScenarioResult, WaccComponents, WaccResult
from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.wacc_v14 import compute_wacc_from_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer

logger = logging.getLogger(__name__)

DEFAULT_DISCOUNT_RATE = 0.10


def evaluate_scenario(
    config_path: str,
    scenario_name: Optional[str] = None,
    validation_mode: str = "strict",
) -> ScenarioResult:
    """Evaluate a single scenario through the v14 pipeline with WACC valuation.
    
    Parameters
    ----------
    config_path : str
        Path to YAML/JSON scenario config.
    scenario_name : Optional[str]
        Override scenario name (default: use from config or filename).
    validation_mode : str
        "strict" or "relaxed" - config validation mode.
    
    Returns
    -------
    ScenarioResult
        Complete evaluation result with WACC, KPIs, and debt analysis.
    """
    path_obj = Path(config_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    logger.info("Loading scenario: %s", config_path)
    config = load_scenario_config(config_path)

    # Validate config schema
    validate_config_for_v14(
        config,
        config_path=config_path,
        modules=["cashflow", "debt"],
    )

    # Compute WACC if present in config
    wacc_dict = compute_wacc_from_config(config)
    wacc_result: Optional[WaccResult] = None
    discount_rate = DEFAULT_DISCOUNT_RATE
    prudential_rate: Optional[float] = None
    wacc_label = "default"
    wacc_is_real = False

    if wacc_dict:
        # Build WaccComponents from dict
        wacc_comp = WaccComponents(**wacc_dict)
        
        # Use nominal WACC as base discount rate
        discount_rate = wacc_comp.wacc_nominal
        prudential_rate = wacc_comp.wacc_prudential
        wacc_label = "base"
        wacc_is_real = False
        
        # If real WACC available and user prefers it, switch
        if wacc_comp.wacc_real is not None:
            # For now, default to nominal; Phase 2 can add user preference
            wacc_is_real = False
        
        wacc_result = WaccResult(
            base=wacc_comp,
            prudential_rate=prudential_rate,
            prudential_npv=None,  # Will be filled after KPI calculation
        )
        wacc_result.meta = {"calculated_from": "config"}

        logger.info(
            "Using WACC: nominal=%.2f%%, prudential=%.2f%%",
            discount_rate * 100,
            prudential_rate * 100 if prudential_rate else 0,
        )
    else:
        logger.info("No WACC config; using default discount rate: %.1f%%", DEFAULT_DISCOUNT_RATE * 100)

    # Build cashflows
    annual_rows = build_annual_rows(config)
    
    # Apply debt layer
    debt_result = apply_debt_layer(config, annual_rows)

    # Calculate KPIs with explicit discount rates
    kpis = calculate_scenario_kpis(
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=discount_rate,
        prudential_rate=prudential_rate,
    )

    # Enrich WACC result with prudential NPV if calculated
    if wacc_result and "npv_prudential" in kpis:
        wacc_result.prudential_npv = kpis["npv_prudential"]

    # Extract core metrics
    project_npv = kpis.get("project_npv", 0.0)
    project_irr = kpis.get("project_irr", 0.0)
    min_dscr = kpis.get("min_dscr", 0.0)
    max_debt_usd = debt_result.get("total_debt_usd", 0.0)
    dscr_series = debt_result.get("dscr_series", [])

    # Use scenario name from config or filename
    if scenario_name is None:
        scenario_name = config.get("scenario_name", path_obj.stem)

    result = ScenarioResult(
        scenario_name=scenario_name,
        config_path=str(config_path),
        project_npv=project_npv,
        project_irr=project_irr,
        dscr_series=dscr_series,
        min_dscr=min_dscr,
        max_debt_usd=max_debt_usd,
        wacc=wacc_result,
        discount_rate_used=discount_rate,
        wacc_label=wacc_label,
        wacc_is_real=wacc_is_real,
        validation_mode=validation_mode,
        config=config,
        annual_rows=annual_rows,
        debt_result=debt_result,
        kpis=kpis,
    )

    logger.info(
        "Scenario '%s': NPV=%.2fM, IRR=%.2f%%, MinDSCR=%.2f (rate=%s %.2f%%)",
        scenario_name,
        project_npv / 1e6,
        project_irr * 100,
        min_dscr,
        wacc_label,
        discount_rate * 100,
    )

    return result


def evaluate_scenario_as_dict(
    config_path: str,
    validation_mode: str = "strict",
) -> Dict[str, Any]:
    """Adapter function for backward compatibility with run_full_pipeline_v14.py.
    
    Returns a flat dict instead of ScenarioResult dataclass.
    """
    result = evaluate_scenario(config_path=config_path, validation_mode=validation_mode)

    # Flatten to dict for legacy consumers
    out: Dict[str, Any] = {
        "scenario_name": result.scenario_name,
        "config_path": result.config_path,
        "validation_mode": result.validation_mode,  # ← ADDED FOR v14
        "project_npv": result.project_npv,
        "project_irr": result.project_irr,
        "min_dscr": result.min_dscr,
        "max_debt_usd": result.max_debt_usd,
        "dscr_series": result.dscr_series,
        "discount_rate_used": result.discount_rate_used,
        "wacc_label": result.wacc_label,
        "wacc_is_real": result.wacc_is_real,
        "config": result.config,
        "annual_rows": result.annual_rows,
        "debt_result": result.debt_result,
        "kpis": result.kpis,
    }

    # Flatten WACC if present
    if result.wacc:
        wacc_base = result.wacc.base
        out["wacc"] = {
            "mode": wacc_base.mode,
            "wacc_nominal": wacc_base.wacc_nominal,
            "wacc_real": wacc_base.wacc_real,
            "wacc_prudential": wacc_base.wacc_prudential,
            "risk_free_rate": wacc_base.risk_free_rate,
            "market_risk_premium": wacc_base.market_risk_premium,
            "asset_beta": wacc_base.asset_beta,
            "prudential_rate": result.wacc.prudential_rate,
            "prudential_npv": result.wacc.prudential_npv,
        }

    return out
