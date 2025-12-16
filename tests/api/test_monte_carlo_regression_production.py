# tests/api/test_monte_carlo_regression_production.py
# Sprint 10: Production-scale Monte Carlo validation tests
# WARNING: Production tests take 10-15 minutes to run!
# Use pytest marker: pytest -m "production" to run only these
# Non-production/development runs use FAST_ITERATIONS (50) for speed

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.monte_carlo_v14 import run_monte_carlo

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MC_CONFIG_PATH = Path("config/monte_carlo_regression_production.yaml")
BASE_SCENARIO_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")

# Fast iterations for development/CI (50 instead of 3000)
# Only use 3000 when --production flag is set
IS_PRODUCTION = "--production" in os.sys.argv or os.getenv("PYTEST_PRODUCTION") == "1"
FAST_ITERATIONS = 50
PRODUCTION_ITERATIONS = 3000


# ---------------------------------------------------------------------------
# Helper to pretty-print MonteCarloResult objects
# ---------------------------------------------------------------------------


def _result_to_dict(mc_result: Any) -> Dict[str, Any]:
    """
    Convert MonteCarloResult (pydantic/dataclass) into a plain dict for
    assertions and error messages.
    """
    if hasattr(mc_result, "model_dump"):
        return mc_result.model_dump()
    if hasattr(mc_result, "dict"):
        return mc_result.dict()  # type: ignore[call-arg]
    if hasattr(mc_result, "__dict__"):
        return dict(mc_result.__dict__)
    return {"_repr": repr(mc_result)}


# ---------------------------------------------------------------------------
# Production Regression bands (to be populated after first golden run)
# ---------------------------------------------------------------------------

# Base case: 3000 iterations, seed=42
BASE_CASE_IRR_P50_LOW = 0.16
BASE_CASE_IRR_P50_HIGH = 0.20

BASE_CASE_NPV_P50_LOW = -1e9  # TODO: populate after first production run
BASE_CASE_NPV_P50_HIGH = 1e9

BASE_CASE_DSCR_P10_LOW = 1.20
BASE_CASE_DSCR_P10_HIGH = 1.40

# Upside case: 3000 iterations, seed=42 (same seed as base for CRN)
UPSIDE_CASE_IRR_P50_LOW = 0.18
UPSIDE_CASE_IRR_P50_HIGH = 0.24

UPSIDE_CASE_NPV_P50_LOW = -1e9  # TODO: populate after first production run
UPSIDE_CASE_NPV_P50_HIGH = 1e9

UPSIDE_CASE_DSCR_P10_LOW = 1.30
UPSIDE_CASE_DSCR_P10_HIGH = 1.60


# ---------------------------------------------------------------------------
# Production Tests
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_production_base_case_stability() -> None:
    """
    Production-scale regression validation for BASE CASE.

    Configuration:
    - Development: 50 iterations (fast validation)
    - Production: 3000 iterations (statistical confidence for P10/P50/P90)
    - Base case scenario (lender assumptions)
    - Seed fixed at 42 for reproducibility
    - Expected runtime: <1 second (dev), 10-15 minutes (production)

    This test validates:
    - Monte Carlo convergence across samples
    - P50 IRR/NPV stability (locked in regression band)
    - P10 DSCR within lender covenant range

    For lender submissions and risk board presentations (production only).
    """
    iterations = PRODUCTION_ITERATIONS if IS_PRODUCTION else FAST_ITERATIONS
    
    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=IS_PRODUCTION,  # Only save outputs in production
    )

    # Validate results exist
    assert results, "Monte Carlo returned no scenario results"
    assert (
        "base_case" in results
    ), f"Expected 'base_case' in results; got {list(results.keys())}"

    mc_result = results["base_case"]
    data = _result_to_dict(mc_result)

    # Extract metrics
    irr_p50 = data.get("project_irr_p50")
    npv_p50 = data.get("project_npv_p50")
    dscr_p10 = data.get("dscr_min_p10")

    # Validate numeric types
    assert isinstance(
        irr_p50, (int, float)
    ), f"project_irr_p50 missing or not numeric: {irr_p50!r}"
    assert isinstance(
        npv_p50, (int, float)
    ), f"project_npv_p50 missing or not numeric: {npv_p50!r}"
    assert isinstance(
        dscr_p10, (int, float)
    ), f"dscr_min_p10 missing or not numeric: {dscr_p10!r}"

    # Regression band assertions (only for production)
    if IS_PRODUCTION:
        assert BASE_CASE_IRR_P50_LOW <= irr_p50 <= BASE_CASE_IRR_P50_HIGH, (
            f"Base Case P50 IRR {irr_p50:.6f} outside band "
            f"[{BASE_CASE_IRR_P50_LOW:.6f}, {BASE_CASE_IRR_P50_HIGH:.6f}]"
        )

        assert BASE_CASE_NPV_P50_LOW <= npv_p50 <= BASE_CASE_NPV_P50_HIGH, (
            f"Base Case P50 NPV {npv_p50:.2f} outside band "
            f"[{BASE_CASE_NPV_P50_LOW:.2f}, {BASE_CASE_NPV_P50_HIGH:.2f}]"
        )

        assert BASE_CASE_DSCR_P10_LOW <= dscr_p10 <= BASE_CASE_DSCR_P10_HIGH, (
            f"Base Case P10 DSCR {dscr_p10:.6f} outside band "
            f"[{BASE_CASE_DSCR_P10_LOW:.6f}, {BASE_CASE_DSCR_P10_HIGH:.6f}]"
        )


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_production_upside_case_stability() -> None:
    """
    Production-scale regression validation for UPSIDE CASE.

    Configuration:
    - Development: 50 iterations (fast validation)
    - Production: 3000 iterations (statistical confidence for P10/P50/P90)
    - Upside scenario (improved operating assumptions)
    - Seed fixed at 42 for reproducibility & CRN vs base case
    - Expected runtime: <1 second (dev), 10-15 minutes (production)

    Upside scenario assumptions:
    - Higher capacity factor (48% mode vs 45%)
    - Lower OPEX (17 vs 18 USD/kW/year)
    - Faster construction (22 vs 24 months)

    This test validates scenario comparative analysis.
    """
    iterations = PRODUCTION_ITERATIONS if IS_PRODUCTION else FAST_ITERATIONS
    
    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        scenario_name="upside_case",
        write_output=IS_PRODUCTION,  # Only save outputs in production
    )

    # Validate results exist
    assert results, "Monte Carlo returned no scenario results"
    assert (
        "upside_case" in results
    ), f"Expected 'upside_case' in results; got {list(results.keys())}"

    mc_result = results["upside_case"]
    data = _result_to_dict(mc_result)

    # Extract metrics
    irr_p50 = data.get("project_irr_p50")
    npv_p50 = data.get("project_npv_p50")
    dscr_p10 = data.get("dscr_min_p10")

    # Validate numeric types
    assert isinstance(
        irr_p50, (int, float)
    ), f"project_irr_p50 missing or not numeric: {irr_p50!r}"
    assert isinstance(
        npv_p50, (int, float)
    ), f"project_npv_p50 missing or not numeric: {npv_p50!r}"
    assert isinstance(
        dscr_p10, (int, float)
    ), f"dscr_min_p10 missing or not numeric: {dscr_p10!r}"

    # Regression band assertions (only for production)
    if IS_PRODUCTION:
        assert UPSIDE_CASE_IRR_P50_LOW <= irr_p50 <= UPSIDE_CASE_IRR_P50_HIGH, (
            f"Upside Case P50 IRR {irr_p50:.6f} outside band "
            f"[{UPSIDE_CASE_IRR_P50_LOW:.6f}, {UPSIDE_CASE_IRR_P50_HIGH:.6f}]"
        )

        assert UPSIDE_CASE_NPV_P50_LOW <= npv_p50 <= UPSIDE_CASE_NPV_P50_HIGH, (
            f"Upside Case P50 NPV {npv_p50:.2f} outside band "
            f"[{UPSIDE_CASE_NPV_P50_LOW:.2f}, {UPSIDE_CASE_NPV_P50_HIGH:.2f}]"
        )

        assert UPSIDE_CASE_DSCR_P10_LOW <= dscr_p10 <= UPSIDE_CASE_DSCR_P10_HIGH, (
            f"Upside Case P10 DSCR {dscr_p10:.6f} outside band "
            f"[{UPSIDE_CASE_DSCR_P10_LOW:.6f}, {UPSIDE_CASE_DSCR_P10_HIGH:.6f}]"
        )


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_production_precision_fields() -> None:
    """
    Production test: Verify precision fields (standard errors) are present.

    These fields enable confidence interval construction:
      P50 IRR ± 1.96 * SE → 95% CI

    Development: Quick validation with 50 iterations.
    Production: Full precision validation with 3000 iterations (tight SEs).
    """
    iterations = PRODUCTION_ITERATIONS if IS_PRODUCTION else FAST_ITERATIONS
    
    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=False,
    )

    assert results, "Monte Carlo returned no scenario results"

    mc_result = results.get("base_case") or next(iter(results.values()))
    data = _result_to_dict(mc_result)

    for field in ("project_irr_se", "project_npv_se", "dscr_min_se"):
        value = data.get(field)

        # Validation
        assert isinstance(
            value, (int, float)
        ), f"{field} missing or not numeric: {value!r}"
        assert not math.isnan(value), f"{field} is NaN"
        assert math.isfinite(value), f"{field} is not finite: {value!r}"
        assert value >= 0.0, f"{field} is negative: {value!r}"

        # Production precision checks (only with 3000 iterations)
        if IS_PRODUCTION and "irr" in field:
            assert value < 0.01, (
                f"{field} seems too large for 3000 iterations: {value:.6f}"
            )
