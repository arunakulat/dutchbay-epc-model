"""Central Scenario Evaluator for V14 - WACC-Integrated."""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from analytics.contracts_v14 import ScenarioResult, WaccComponents, WaccResult
from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer
from finance.wacc_v14 import compute_wacc_from_config

logger = logging.getLogger(__name__)

DEFAULT_DISCOUNT_RATE = 0.10


def _evaluate_loaded_config(
    config: Dict[str, Any],
    config_path: str,
    scenario_name: Optional[str],
    validation_mode: str,
) -> ScenarioResult:
    """
    Internal helper: run the full v14 pipeline on an already loaded config.

    This is the single place that:
      - Runs validate_config_for_v14
      - Computes WACC
      - Builds cashflows and applies debt
      - Calculates KPIs
      - Constructs ScenarioResult
    """

    # Pre-flight schema guard (strict modules list including WACC)
    validate_config_for_v14(
        config,
        config_path=config_path,
        modules=["cashflow", "debt", "wacc"],
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
        logger.info(
            "No WACC config; using default discount rate: %.1f%%",
            DEFAULT_DISCOUNT_RATE * 100,
        )

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

    # Use scenario name from config or filename fallback
    if scenario_name is None:
        scenario_name = config.get("scenario_name") or Path(config_path).stem

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
        result.discount_rate_used * 100,
    )

    return result


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

    # Single pre-flight guard path lives in _evaluate_loaded_config
    return _evaluate_loaded_config(
        config=config,
        config_path=str(config_path),
        scenario_name=scenario_name,
        validation_mode=validation_mode,
    )


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
        "validation_mode": result.validation_mode,
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


# =============================================================================
# Phase 3: Sensitivity Analysis Gateway
# =============================================================================


def evaluate_with_overrides(
    config_path: str,
    overrides: Dict[str, Any] | None = None,
    validation_mode: str = "strict",
) -> Dict[str, Any]:
    """
    Single scenario evaluation with parameter overrides.

    This is the ONLY gateway that sensitivity_v14.py should use to access
    the v14 pipeline. It wraps evaluate_scenario with override support.

    Args:
        config_path: Path to base scenario YAML/JSON file.
        overrides: Nested dict of parameter overrides, e.g.
                   {"project": {"capex_usd_per_kw": 900.0}}
                   None = no overrides (base case).
        validation_mode: "strict" or "relaxed" - passes through to evaluation.

    Returns:
        KPI dict with standardized keys:
        - project_irr: float
        - equity_irr: float
        - project_npv: float
        - dscr_min: float
        - llcr: float
        - plcr: float
        - max_debt_usd: float

    Raises:
        FileNotFoundError: If config_path doesn't exist.
        ValidationError: If config fails v14 validation.
        ValueError: If evaluation fails.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Load base config
    raw_config = load_scenario_config(str(config_file))

    # Apply overrides if provided
    if overrides:
        config = _apply_nested_overrides(copy.deepcopy(raw_config), overrides)
    else:
        config = raw_config

    # Re-use the core evaluation helper (includes schema guard + WACC + KPIs)
    result = _evaluate_loaded_config(
        config=config,
        config_path=str(config_file),
        scenario_name=config.get("name", "sensitivity_eval"),
        validation_mode=validation_mode,
    )

    # Extract KPIs (standardized interface)
    return {
        "project_irr": result.project_irr,
        "equity_irr": result.kpis.get("equity_irr", 0.0),
        "project_npv": result.project_npv,
        "dscr_min": result.min_dscr,
        "llcr": result.kpis.get("llcr", 0.0),
        "plcr": result.kpis.get("plcr", 0.0),
        "max_debt_usd": result.max_debt_usd,
    }


def _apply_nested_overrides(
    config: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Apply nested parameter overrides to config dict.

    Args:
        config: Base configuration dict.
        overrides: Nested overrides (e.g., {"project": {"capex_usd_per_kw": 900}}).

    Returns:
        Config with overrides applied (same dict, mutated in-place).
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and key in config:
            # Recursive merge for nested dicts
            config[key] = _apply_nested_overrides(config[key], value)
        else:
            # Direct assignment for leaf values or new branches
            config[key] = value

    return config
    