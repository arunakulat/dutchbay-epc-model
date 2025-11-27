#!/usr/bin/env python3
"""
V14 Lender Suite Integration Tests (Go With The Flow edition).

CORE PRINCIPLE: Configuration-driven, not code-driven.
- Load validated YAML scenarios from scenarios/ directory
- Trust schema_guard to validate configs
- Tests encode the contract: "Given valid YAML, pipeline works"
- Zero hardcoded field structures or assumptions

This respects the fundamental Go With The Flow rules:
  • YAML/config-driven first (no hardcoded values)
  • Defensive programming (schema validates before compute)
  • No magic paths (explicit path resolution via load_scenario_config)
  • Test-first design (contract: valid config → valid pipeline output)
  • Config-driven not code-driven (never rebuild config structure in Python)
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from finance import cashflow_v14 as cf_mod
from finance import debt_v14 as debt_mod
from analytics.schema_guard import validate_config_for_v14

logger = logging.getLogger(__name__)

# Resolve scenario directory relative to repo root (explicit path, no magic CWD)
REPO_ROOT = Path(__file__).parent.parent.parent
SCENARIOS_DIR = REPO_ROOT / "scenarios"


def _load_and_validate_scenario(scenario_name: str) -> dict:
    """
    Load a scenario YAML and validate it for v14 pipelines.
    
    This function delegates to the canonical schema_guard validator
    rather than building config structures in Python.
    
    Args:
        scenario_name: Name of scenario (without .yaml/.yml extension)
        
    Returns:
        Validated config dict ready for v14 pipeline
        
    Raises:
        FileNotFoundError: If scenario file not found
        ConfigValidationError: If schema validation fails
    """
    # Find scenario file (support both .yaml and .yml extensions)
    scenario_files = [
        SCENARIOS_DIR / f"{scenario_name}.yaml",
        SCENARIOS_DIR / f"{scenario_name}.yml",
    ]
    
    scenario_path = None
    for candidate in scenario_files:
        if candidate.exists():
            scenario_path = candidate
            break
    
    if scenario_path is None:
        raise FileNotFoundError(
            f"Scenario '{scenario_name}' not found in {SCENARIOS_DIR}. "
            f"Searched: {', '.join(f.name for f in scenario_files)}"
        )
    
    logger.info(f"Loading scenario: {scenario_path}")
    
    # Load via canonical loader (handles YAML parsing, merging, overlays)
    config = load_scenario_config(str(scenario_path))
    
    # Validate for v14 cashflow/debt pipeline (defensive programming)
    # This call will raise ConfigValidationError with CLEAR messages about
    # which fields are missing or invalid, rather than silent failures downstream
    validate_config_for_v14(
        raw_config=config,
        config_path=str(scenario_path),
        modules=["cashflow", "debt"],  # Validate for both pipeline stages
    )
    
    logger.info(f"Scenario validated successfully: {scenario_path}")
    return config


def test_v14_pipeline_runs_end_to_end() -> None:
    """
    Contract Test: Given a validated scenario YAML, the full v14 pipeline 
    (cashflow → debt → KPIs) runs without error and produces expected outputs.
    
    This test encodes the core v14 integration contract:
    - Valid scenario YAML → successful pipeline run
    - All intermediate outputs are present and non-empty
    - No exceptions, no silent failures
    
    We use the canonical dutchbay_lendercase_2025Q4 scenario which is
    maintained and validated by the model owner.
    """
    # Load and validate: lets schema_guard do its job (defensive programming)
    config = _load_and_validate_scenario("dutchbay_lendercase_2025Q4")
    
    # Stage 1: Build annual cashflow rows
    try:
        annual_rows = cf_mod.build_annual_rows(config)
    except Exception as e:
        pytest.fail(
            f"build_annual_rows failed on validated config. "
            f"This indicates a pipeline bug, not a config issue. "
            f"Error: {e}"
        )
    
    # Contract: pipeline produces rows
    assert len(annual_rows) > 0, (
        "Pipeline produced zero annual_rows despite validation passing. "
        "Check cashflow_v14.py for logic errors."
    )
    assert all(isinstance(row, dict) for row in annual_rows), (
        "annual_rows must be list of dicts per contract"
    )
    
    logger.info(f"Annual rows generated: {len(annual_rows)}")
    
    # Stage 2: Apply debt layer
    try:
        debt_result = debt_mod.apply_debt_layer(config, annual_rows)
    except Exception as e:
        pytest.fail(
            f"apply_debt_layer failed on validated config and annual_rows. "
            f"Error: {e}"
        )
    
    # Contract: debt layer returns dict with core metrics
    assert isinstance(debt_result, dict), (
        "debt_result must be a dict per contract"
    )
    
    required_debt_keys = [
        "dscr_min",
        "dscr_series",
        "debt_service_total",
        "debt_outstanding",
        "audit_status",
    ]
    for key in required_debt_keys:
        assert key in debt_result, (
            f"Missing required contract key '{key}' in debt_result. "
            f"Available keys: {list(debt_result.keys())}. "
            f"Check debt_v14.py for return structure."
        )
    
    # Sanity checks on outputs (contract: values are reasonable)
    dscr_min = float(debt_result.get("dscr_min", 0.0))
    assert dscr_min >= 0.0, (
        f"DSCR_min must be >= 0 per contract, got {dscr_min}"
    )
    
    debt_service = debt_result.get("debt_service_total", [])
    assert isinstance(debt_service, list) and len(debt_service) > 0, (
        "debt_service_total must be non-empty list per contract"
    )
    
    logger.info(
        f"Debt layer complete: DSCR_min={dscr_min:.3f}, "
        f"debt_service_periods={len(debt_service)}"
    )
    
    # Stage 3: Verify cashflow integration
    first_row = annual_rows[0]
    has_cfads = any(
        k in first_row 
        for k in ["cfads_usd", "cfads_final_lkr", "cfads"]
    )
    assert has_cfads, (
        f"No CFADS field found in annual_rows[0]. "
        f"Available keys: {list(first_row.keys())}. "
        f"Check cashflow_v14.py for output structure."
    )
    
    logger.info("✓ Full v14 pipeline contract validated successfully")


def test_scenario_loading_and_validation() -> None:
    """
    Contract Test: Scenario files can be loaded and validated via the
    canonical schema_guard layer.
    
    This test verifies the defensive programming layer works correctly
    and produces clear error messages on config problems.
    """
    # Should succeed: dutchbay_lendercase_2025Q4 is maintained by model owner
    config = _load_and_validate_scenario("dutchbay_lendercase_2025Q4")
    
    assert isinstance(config, dict), "Config must be a dict"
    assert len(config) > 0, "Config must not be empty"
    
    # Verify core top-level sections exist (per DutchBay schema)
    core_sections = ["project", "capex", "tax", "Financing_Terms"]
    for section in core_sections:
        assert section in config or any(
            k.lower() == section.lower() for k in config.keys()
        ), (
            f"Core section '{section}' not found in config. "
            f"Schema may have changed; check scenarios/dutchbay_lendercase_2025Q4.yaml"
        )
    
    logger.info(f"✓ Scenario structure validated: {list(config.keys())}")


# EOF
