"""Wind Analytics Package.

This package provides wind resource analysis and integration utilities for
the DutchBay v14 financial model, including AEP (Annual Energy Production)
loading, Monte Carlo uncertainty quantification, and configuration integration.

Modules:
    wind_integration: High-level wind-to-finance integration bridge.
                     Provides AEP loading, Monte Carlo simulation,
                     and config injection functions.

    pipeline_aep_v14: AEP pipeline integration for v14 model.
                     Orchestrates wind → AEP → revenue chain with
                     config-driven resource loading.

Public API:
    # AEP Loading
    load_aep_for_project: Load AEP data from Data Lake with provenance

    # Monte Carlo
    run_aep_monte_carlo: Run MC simulation for AEP uncertainty
    compute_aep_p_values: Extract P-values from MC results

    # Configuration
    integrate_aep_into_config: Inject AEP data into finance config
    integrate_aep_pipeline: Full pipeline integration (config-driven)
    validate_turbine_specs: Validate turbine consistency
    derive_capacity_factor_from_aep: Reverse-engineer CF from AEP

    # Constants
    WIND_MODULES_AVAILABLE: Flag for optional wind analytics availability

Usage:
    # AEP Loading
    from analytics.wind import load_aep_for_project

    aep_data = load_aep_for_project(
        aep_summary_path='tests/mocks/aep_summary_dutchbay.json'
    )

    # Monte Carlo Uncertainty
    from analytics.wind import run_aep_monte_carlo

    mc_results = run_aep_monte_carlo(
        aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        n_scenarios=100000
    )

    # Config Integration
    from analytics.wind import integrate_aep_into_config

    config_updated = integrate_aep_into_config(
        config=base_config,
        aep_data=aep_data
    )

    # Full Pipeline (Config-Driven)
    from analytics.wind import integrate_aep_pipeline

    config = integrate_aep_pipeline(config)  # GWTF ARCH-01 compliant

Framework Compliance:
    - GWTF ARCH-01: Config-driven (no hardcoded values)
    - GWTF R3: Type-safe with comprehensive docstrings
    - CASPER: Lender-grade AEP provenance tracking
    - CESSPIT: Fail-fast validation, clear error messages

Migration:
    - Priority 4 (Wind Modules)
    - 2 files moved from analytics/ root
    - 2 backward compatibility shims created
    - Clean isolation of wind analytics subsystem

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from __future__ import annotations

# Public API: Pipeline Integration Functions
from analytics.wind.pipeline_aep_v14 import (
    integrate_aep_pipeline,
    validate_turbine_specs,
)

# Public API: Wind Integration Functions
from analytics.wind.wind_integration import (
    WIND_MODULES_AVAILABLE,
    compute_aep_p_values,
    derive_capacity_factor_from_aep,
    integrate_aep_into_config,
    load_aep_for_project,
    run_aep_monte_carlo,
)

__all__ = [
    # Constants
    "WIND_MODULES_AVAILABLE",
    # AEP Loading
    "load_aep_for_project",
    # Monte Carlo
    "run_aep_monte_carlo",
    "compute_aep_p_values",
    # Configuration
    "integrate_aep_into_config",
    "derive_capacity_factor_from_aep",
    # Pipeline
    "integrate_aep_pipeline",
    "validate_turbine_specs",
]
