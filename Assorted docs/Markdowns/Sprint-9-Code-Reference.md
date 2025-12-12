# Sprint 9 Integration: Code Structure Reference
## Exact Implementation Patterns for run_full_pipeline_v14.py

---

## FILE: `analytics/scenarioloader.py` (NEW - 10 lines)

```python
"""Alias module for scenario_loader - maintains backward compatibility."""

from analytics.scenario_loader import load_scenario_config

__all__ = ["load_scenario_config"]
```

**Purpose:** Resolve lint test error (`test_no_forbidden_pipeline_imports`)

---

## FILE: `analytics/__init__.py` (UPDATE - Add to existing __getattr__)

**Current:**
```python
if name == "evaluate_with_overrides":
    from analytics.evaluate_scenario import evaluate_with_overrides
    return evaluate_with_overrides

if name == "load_scenario_config":
    from analytics.scenario_loader import load_scenario_config
    return load_scenario_config
```

**Add this block:**
```python
if name == "evaluate_scenario":
    from analytics.evaluate_scenario import evaluate_scenario
    return evaluate_scenario

if name == "evaluate_scenario_as_dict":
    from analytics.evaluate_scenario import evaluate_scenario_as_dict
    return evaluate_scenario_as_dict
```

**Purpose:** Enable lazy loading of evaluate_scenario for test monkeypatching

---

## FILE: `run_full_pipeline_v14.py` (REFACTOR - 300+ lines)

### Part 1: Imports & Type Definitions

```python
"""
Full v14 pipeline orchestration.

This module is the **canonical** entry point for end-to-end project analysis:
1. Config validation & parameter resolution
2. Core DCF pipeline (cashflow, debt, equity, metrics)
3. Conditional sensitivity analysis (always runs)
4. Conditional Monte Carlo (if enabled in config)
5. Result merging & export

Integration points:
- Respects CASPER pattern (config → aggregation → scenario → params → engine → results)
- Follows "Go With The Flow" v3.0 rules (explicit, namespaced, schema-validated)
- Uses lazy imports to avoid circular dependencies
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

# Finance modules
from finance.cashflow_v14 import build_annual_rows as build_cashflow_rows
from finance.debt_v14 import plan_debt
from finance.equity_v14 import compute_equity_irr
from finance.wacc_v14 import compute_wacc

# Analytics layer - lazy imports to avoid cycles
# (Importing at function scope, not module scope)

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Validated pipeline configuration."""
    scenario_name: str
    project: Dict[str, Any]
    finance: Dict[str, Any]
    analytics: Dict[str, Any]
    overrides: Dict[str, Any]
```

### Part 2: Configuration Preparation

```python
def _prepare_configuration(
    config: dict[str, Any],
    overrides: dict[str, Any] | None = None,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> Dict[str, Any]:
    """
    Validate and merge configuration sources.

    Priority (highest to lowest):
    1. Explicit overrides (CLI/API)
    2. Scenario config file
    3. Environment defaults

    Parameters
    ----------
    config : dict[str, Any]
        Scenario configuration (YAML-loaded dict)
    overrides : dict[str, Any] | None
        Parameter overrides (CLI or API)
    validation_mode : str
        "strict" = fail on missing required fields
        "lenient" = warn and use defaults
    validation_modules : list[str] | None
        List of modules to validate (e.g., ["cashflow", "tax"])
        If None, validates all

    Returns
    -------
    Dict[str, Any]
        Validated, merged configuration
    """
    from analytics.schema_guard import validate_config
    from analytics.scenario_loader import load_scenario_config

    # Step 1: Load and normalize config
    if isinstance(config, str):
        # Config is a path
        config = load_scenario_config(config)

    # Step 2: Apply overrides
    if overrides:
        config = _deep_merge(config, overrides)

    # Step 3: Validate schema
    validation_errors = validate_config(
        config,
        mode=validation_mode,
        modules=validation_modules or ["all"],
    )

    if validation_errors and validation_mode == "strict":
        raise ValueError(f"Configuration validation failed:\n{validation_errors}")
    elif validation_errors:
        logger.warning(f"Configuration warnings:\n{validation_errors}")

    return config


def _deep_merge(base: dict, updates: dict) -> dict:
    """Recursively merge updates into base dict."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
```

### Part 3: Core Pipeline Execution

```python
def _run_core_pipeline(
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run core DCF pipeline (cashflow → debt → equity → metrics).

    Returns
    -------
    Dict[str, Any]
        Base pipeline results including:
        - project_irr, project_npv
        - min_dscr, max_debt_usd
        - cashflow_rows, debt_schedule, equity_schedule
        - kpis dict with detailed metrics
    """
    logger.info("Running core DCF pipeline...")

    # === Cashflow ===
    cashflow_rows = build_cashflow_rows(
        config=config,
        fx_curve=config.get("fx_curve"),
        capex_depreciable_lkr=config.get("tax", {}).get("depreciable_capex_lkr"),
        interest_expense_series=None,  # Filled in after debt planning
    )
    logger.info(f"Generated {len(cashflow_rows)} cashflow years")

    # === Debt ===
    debt_result = plan_debt(
        config=config,
        cfads_list=[row["cfads_final_lkr"] for row in cashflow_rows],
    )

    # Re-run cashflow with actual interest from debt schedule
    interest_series = [row.get("interest_expense_lkr", 0.0) for row in debt_result["debt_schedule"]]
    cashflow_rows = build_cashflow_rows(
        config=config,
        fx_curve=config.get("fx_curve"),
        capex_depreciable_lkr=config.get("tax", {}).get("depreciable_capex_lkr"),
        interest_expense_series=interest_series,
    )

    # === Equity ===
    project_irr = compute_equity_irr(
        config=config,
        debt_schedule=debt_result["debt_schedule"],
        cashflow_rows=cashflow_rows,
    )

    # === KPI Aggregation ===
    from analytics.core.metrics import compute_all_metrics
    from analytics.kpi_normalizer import normalize_kpis

    raw_kpis = compute_all_metrics(
        config=config,
        cashflow_rows=cashflow_rows,
        debt_schedule=debt_result["debt_schedule"],
        project_irr=project_irr,
    )

    normalized_kpis = normalize_kpis(raw_kpis, config)

    # === Result Assembly ===
    result = {
        # Core metrics
        "scenario_name": config.get("project", {}).get("name", "unnamed"),
        "project_irr": project_irr,
        "project_npv": normalized_kpis.get("project_npv", 0.0),
        "min_dscr": normalized_kpis.get("min_dscr", 0.0),
        "max_debt_usd": debt_result.get("max_debt_usd", 0.0),

        # Detailed data
        "cashflow_rows": cashflow_rows,
        "debt_schedule": debt_result["debt_schedule"],
        "equity_schedule": debt_result.get("equity_schedule", []),

        # Full KPI dict
        "kpis": normalized_kpis,
    }

    logger.info(f"Core pipeline complete: IRR={project_irr:.2%}, DSCR_min={normalized_kpis.get('min_dscr', 0):.2f}x")
    return result
```

### Part 4: Sensitivity Analysis

```python
def _run_sensitivity(
    config: Dict[str, Any],
    base_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run sensitivity analysis (tornado, Pareto).

    Parameters
    ----------
    config : Dict[str, Any]
        Full configuration
    base_result : Dict[str, Any]
        Output from _run_core_pipeline

    Returns
    -------
    Dict[str, Any]
        Sensitivity results:
        - tornado: factor changes by parameter
        - pareto_front: efficient frontier
        - sensitivity_indices: correlation-based importance
    """
    from analytics.sensitivity_v14 import build_sensitivity_suite
    from analytics.contracts_v14 import SensitivitySuite

    logger.info("Running sensitivity analysis...")

    sensitivity_config = config.get("analytics", {}).get("sensitivity", {})

    # Build tornado matrix
    tornado_suite = build_sensitivity_suite(
        config=config,
        base_project_irr=base_result["project_irr"],
        base_min_dscr=base_result["min_dscr"],
        sensitivity_config=sensitivity_config,
    )

    # Extract results
    result = {
        "tornado": {
            param: {
                "low": tornado_suite.tornado_results.get(param, {}).get("low_case", 0),
                "high": tornado_suite.tornado_results.get(param, {}).get("high_case", 0),
                "range": tornado_suite.tornado_results.get(param, {}).get("range", 0),
            }
            for param in tornado_suite.tornado_results.keys()
        },
        "pareto_front": [
            {"irr": p[0], "dscr": p[1]} for p in tornado_suite.pareto_points
        ],
        "sensitivity_indices": tornado_suite.sensitivity_indices,
    }

    logger.info(f"Sensitivity complete: {len(result['tornado'])} parameters analyzed")
    return result
```

### Part 5: Monte Carlo Analysis (Conditional)

```python
def _run_monte_carlo(
    config: Dict[str, Any],
    base_result: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Run Monte Carlo simulation (stochastic sampling).

    Only runs if analytics.enable_monte_carlo = True in config.

    Parameters
    ----------
    config : Dict[str, Any]
        Full configuration
    base_result : Dict[str, Any]
        Output from _run_core_pipeline

    Returns
    -------
    Dict[str, Any] | None
        MC results or None if not enabled:
        - percentiles: {10, 50, 90} percentile outcomes
        - breach_probabilities: P(DSCR < threshold), etc.
        - value_at_risk: VaR metric
        - samples: raw sample data
    """
    # Check if MC is enabled
    if not config.get("analytics", {}).get("enable_monte_carlo", False):
        logger.info("Monte Carlo disabled in config")
        return None

    from analytics.monte_carlo_v14 import run_monte_carlo_suite

    logger.info("Running Monte Carlo analysis...")

    mc_config = config.get("analytics", {}).get("monte_carlo", {})
    num_samples = mc_config.get("num_samples", 1000)

    # Run MC
    mc_suite = run_monte_carlo_suite(
        config=config,
        num_samples=num_samples,
        seed=mc_config.get("seed", None),  # For reproducibility
    )

    # Extract results
    result = {
        "percentiles": {
            10: mc_suite.percentile_results.get(10, {}).get("project_irr", 0),
            50: mc_suite.percentile_results.get(50, {}).get("project_irr", 0),
            90: mc_suite.percentile_results.get(90, {}).get("project_irr", 0),
        },
        "breach_probabilities": mc_suite.covenant_breach_probs,
        "value_at_risk": mc_suite.value_at_risk,
        "samples": mc_suite.raw_samples if mc_config.get("export_samples", False) else [],
    }

    logger.info(f"Monte Carlo complete: {num_samples} samples, median IRR={result['percentiles'][50]:.2%}")
    return result
```

### Part 6: Result Merging

```python
def _merge_results(
    base: Dict[str, Any],
    sensitivity: Dict[str, Any],
    monte_carlo: Dict[str, Any] | None,
) -> Dict[str, Any]:
    """
    Merge results from all phases into unified output dict.

    Structure follows "Go With The Flow" rules:
    - No key collisions
    - Namespacing for analytics sub-results
    - Flat KPIs for top-level access
    """
    result = {}

    # === Base KPIs (copy directly) ===
    result.update(base)

    # === Sensitivity (namespaced) ===
    result["sensitivity"] = sensitivity
    result["sensitivity_tornado_factors"] = sensitivity.get("tornado", {})

    # === Monte Carlo (namespaced) ===
    if monte_carlo:
        result["monte_carlo"] = monte_carlo
        # Top-level convenience metrics with prefix
        result["monocarlo_var"] = monte_carlo.get("value_at_risk", 0.0)
        result["monocarlo_dscr_breach_prob"] = monte_carlo.get("breach_probabilities", {}).get("min_dscr", 0.0)
        result["monocarlo_irr_p10"] = monte_carlo.get("percentiles", {}).get(10, 0.0)
        result["monocarlo_irr_p50"] = monte_carlo.get("percentiles", {}).get(50, 0.0)
        result["monocarlo_irr_p90"] = monte_carlo.get("percentiles", {}).get(90, 0.0)

    # === Metadata ===
    result["analysis_metadata"] = {
        "timestamp": datetime.now().isoformat(),
        "modules_run": ["cashflow", "debt", "equity", "metrics", "sensitivity"] +
                      (["monte_carlo"] if monte_carlo else []),
        "scenario_name": base.get("scenario_name", "unknown"),
        "v14_stack": True,
    }

    return result
```

### Part 7: Main Entry Point

```python
def run_v14_pipeline(
    config: str | dict[str, Any],
    overrides: dict[str, Any] | None = None,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> Dict[str, Any]:
    """
    Execute full v14 pipeline end-to-end.

    This is the **primary public API** for DutchBay analysis.

    Parameters
    ----------
    config : str | dict[str, Any]
        Either a YAML file path or config dict
    overrides : dict[str, Any] | None
        Parameter overrides (e.g., {"project": {"capacity_mw": 50}})
    validation_mode : str
        "strict" (fail on errors) or "lenient" (warn)
    validation_modules : list[str] | None
        Modules to validate (e.g., ["cashflow", "tax"])
        If None, validates all

    Returns
    -------
    Dict[str, Any]
        Complete results dict with structure:
        {
            # Base KPIs
            "scenario_name": str,
            "project_irr": float,
            "project_npv": float,
            "min_dscr": float,
            "max_debt_usd": float,

            # Detailed data
            "cashflow_rows": list[dict],
            "debt_schedule": list[dict],
            "equity_schedule": list[dict],
            "kpis": dict,

            # Sensitivity results
            "sensitivity": {...},
            "sensitivity_tornado_factors": dict,

            # MC results (if enabled)
            "monte_carlo": {...},
            "monocarlo_var": float,
            "monocarlo_dscr_breach_prob": float,
            "monocarlo_irr_p10": float,
            "monocarlo_irr_p50": float,
            "monocarlo_irr_p90": float,

            # Metadata
            "analysis_metadata": {...},
        }

    Example
    -------
    >>> config = "scenarios/good_unit_test.yaml"
    >>> result = run_v14_pipeline(config)
    >>> print(f"IRR: {result['project_irr']:.2%}")
    >>> print(f"DSCR min: {result['min_dscr']:.2f}x")
    """
    logger.info("=" * 80)
    logger.info("Starting v14 full pipeline")
    logger.info("=" * 80)

    try:
        # Phase 1: Config preparation
        resolved_config = _prepare_configuration(
            config,
            overrides=overrides,
            validation_mode=validation_mode,
            validation_modules=validation_modules,
        )

        # Phase 2: Core pipeline
        base_result = _run_core_pipeline(resolved_config)

        # Phase 3: Sensitivity (always)
        sensitivity_result = _run_sensitivity(resolved_config, base_result)

        # Phase 4: Monte Carlo (conditional)
        monte_carlo_result = _run_monte_carlo(resolved_config, base_result)

        # Phase 5: Merge results
        merged_result = _merge_results(base_result, sensitivity_result, monte_carlo_result)

        logger.info("=" * 80)
        logger.info(f"Pipeline complete! Results available in result dict")
        logger.info("=" * 80)

        return merged_result

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


# === CLI Entry Point (if called directly) ===

if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run DutchBay v14 full pipeline")
    parser.add_argument("config", help="YAML config file or JSON path")
    parser.add_argument("--overrides", type=str, help="JSON override dict")
    parser.add_argument("--output", type=str, default="outputs/result.json", help="Output JSON file")
    parser.add_argument("--workbook", type=str, default="outputs/analysis.xlsx", help="Output XLSX file")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Load overrides if provided
    overrides = None
    if args.overrides:
        overrides = json.loads(args.overrides)

    # Run pipeline
    result = run_v14_pipeline(args.config, overrides=overrides)

    # Export JSON
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"✅ Results saved to {args.output}")

    # Export workbook
    try:
        from analytics.executive_workbook import build_full_workbook
        build_full_workbook(result, args.workbook)
        print(f"✅ Workbook saved to {args.workbook}")
    except ImportError:
        print("⚠️  Workbook export not available (openpyxl not installed)")
```

---

## TESTING TEMPLATE: `tests/test_full_pipeline_integration.py`

```python
"""Integration tests for full v14 pipeline."""

import pytest
from pathlib import Path

from run_full_pipeline_v14 import run_v14_pipeline


def test_pipeline_smoke_basic():
    """Smoke test: pipeline runs on basic config."""
    result = run_v14_pipeline("scenarios/good_unit_test.yaml")

    assert "project_irr" in result
    assert "min_dscr" in result
    assert "sensitivity" in result
    assert "analysis_metadata" in result


def test_pipeline_with_overrides():
    """Test: pipeline accepts parameter overrides."""
    result = run_v14_pipeline(
        "scenarios/good_unit_test.yaml",
        overrides={"project": {"capacity_mw": 75}},
    )

    assert result["project_irr"] > 0


def test_monte_carlo_optional():
    """Test: MC only runs when enabled."""
    # Without MC
    config_no_mc = {"analytics": {"enable_monte_carlo": False}}
    result = run_v14_pipeline(config_no_mc, validation_mode="lenient")
    assert "monte_carlo" not in result

    # With MC
    # (Skipped in fast tests due to runtime)


def test_result_shape_validation():
    """Test: result dict matches expected schema."""
    result = run_v14_pipeline("scenarios/good_unit_test.yaml")

    # Required top-level keys
    required_keys = {
        "scenario_name", "project_irr", "project_npv", "min_dscr",
        "cashflow_rows", "debt_schedule", "kpis", "sensitivity",
        "analysis_metadata"
    }
    assert required_keys.issubset(result.keys()), f"Missing keys: {required_keys - result.keys()}"

    # Type checks
    assert isinstance(result["project_irr"], float)
    assert isinstance(result["min_dscr"], float)
    assert isinstance(result["kpis"], dict)
    assert isinstance(result["cashflow_rows"], list)


def test_sensitivity_metrics_populated():
    """Test: sensitivity results are present and valid."""
    result = run_v14_pipeline("scenarios/good_unit_test.yaml")

    sensitivity = result["sensitivity"]
    assert "tornado" in sensitivity
    assert len(sensitivity["tornado"]) > 0

    # Each tornado factor should have low/high/range
    for param, factors in sensitivity["tornado"].items():
        assert "low" in factors
        assert "high" in factors
        assert "range" in factors
```

---

## VALIDATION CHECKLIST

- [ ] `scenarioloader.py` created and tests pass
- [ ] `analytics/__init__.py` updated with lazy loaders
- [ ] `run_full_pipeline_v14.py` refactored with all 7 parts
- [ ] All function signatures match type hints
- [ ] Logging statements at each phase boundary
- [ ] Error handling with informative messages
- [ ] Integration tests passing (at least 4)
- [ ] Manual test: `python run_full_pipeline_v14.py scenarios/good_unit_test.yaml`
- [ ] Output JSON valid and contains all expected keys
- [ ] Excel export works (if openpyxl installed)

---

## SUCCESS METRICS

**Code Quality:** ✅ No linter/mypy errors
**Functional:** ✅ End-to-end pipeline executes
**Test Coverage:** ✅ 324/324 tests passing (currently 278/324, you'll add 46)
**Documentation:** ✅ Docstrings complete, example usage provided

You're ready. This is the implementation spec. Go build it. 🚀
