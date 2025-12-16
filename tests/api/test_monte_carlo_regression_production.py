# tests/api/test_monte_carlo_regression_production.py
# Sprint 10: Production-scale Monte Carlo validation tests
# WARNING: These tests take 10-15 minutes to run!
# Use pytest marker: pytest -m "production" to run only these

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.monte_carlo_v14 import run_monte_carlo

# ---------------------------------------------------------------------------
# Production-scale configs (3000 iterations, 10-15 minutes)
# ---------------------------------------------------------------------------

MC_CONFIG_PATH = Path("config/monte_carlo_regression_production.yaml")
BASE_SCENARIO_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


# ---------------------------------------------------------------------------
# Helper to pretty-print MonteCarloResult objects
# ---------------------------------------------------------------------------


def _result_to_dict(mc_result: Any) -> Dict[str, Any]:
    """
    Convert MonteCarloResult (pydantic/dataclass) into a plain dict for
    debugging and assertion messages.
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
# Production Tests (3000 iterations, 10-15 minutes)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_production_base_case_stability() -> None:
    """
    Production-scale regression validation for BASE CASE.

    Configuration:
    - 3000 iterations (statistical confidence for P10/P50/P90)
    - Base case scenario (lender assumptions)
    - Seed fixed at 42 for reproducibility
    - Expected runtime: 10-15 minutes

    This test validates:
    - Monte Carlo convergence across 3000 samples
    - P50 IRR/NPV stability (locked in regression band)
    - P10 DSCR within lender covenant range

    For lender submissions and risk board presentations.
    """
    print("\n" + "=" * 80)
    print("PRODUCTION TEST: Base Case (3000 iterations, 10-15 min)")
    print("=" * 80)

    start_time = time.time()

    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=True,  # Production: save all outputs
    )

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

    # Validate results exist
    assert results, "Monte Carlo returned no scenario results"
    assert (
        "base_case" in results
    ), f"Expected 'base_case' in results; got {list(results.keys())}"

    mc_result = results["base_case"]
    data = _result_to_dict(mc_result)

    print(f"\nBase Case Results:")
    print(f"  IRR P10:     {data.get('project_irr_p10', 'N/A'):.4f}")
    print(f"  IRR P50:     {data.get('project_irr_p50', 'N/A'):.4f}")
    print(f"  IRR P90:     {data.get('project_irr_p90', 'N/A'):.4f}")
    print(f"  NPV P50:     {data.get('project_npv_p50', 'N/A'):.0f}")
    print(f"  DSCR P10:    {data.get('dscr_min_p10', 'N/A'):.4f}")
    print(f"  Success Rate: {data.get('success_rate()', 'N/A'):.1%}")
    print(f"  Failed Iters: {data.get('failed_iterations', 'N/A')}")

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

    # Regression band assertions
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
    - 3000 iterations (statistical confidence for P10/P50/P90)
    - Upside scenario (improved operating assumptions)
    - Seed fixed at 42 for reproducibility & CRN vs base case
    - Expected runtime: 10-15 minutes

    Upside scenario assumptions:
    - Higher capacity factor (48% mode vs 45%)
    - Lower OPEX (17 vs 18 USD/kW/year)
    - Faster construction (22 vs 24 months)

    This test validates scenario comparative analysis.
    """
    print("\n" + "=" * 80)
    print("PRODUCTION TEST: Upside Case (3000 iterations, 10-15 min)")
    print("=" * 80)

    start_time = time.time()

    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        scenario_name="upside_case",
        write_output=True,  # Production: save all outputs
    )

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

    # Validate results exist
    assert results, "Monte Carlo returned no scenario results"
    assert (
        "upside_case" in results
    ), f"Expected 'upside_case' in results; got {list(results.keys())}"

    mc_result = results["upside_case"]
    data = _result_to_dict(mc_result)

    print(f"\nUpside Case Results:")
    print(f"  IRR P10:     {data.get('project_irr_p10', 'N/A'):.4f}")
    print(f"  IRR P50:     {data.get('project_irr_p50', 'N/A'):.4f}")
    print(f"  IRR P90:     {data.get('project_irr_p90', 'N/A'):.4f}")
    print(f"  NPV P50:     {data.get('project_npv_p50', 'N/A'):.0f}")
    print(f"  DSCR P10:    {data.get('dscr_min_p10', 'N/A'):.4f}")
    print(f"  Success Rate: {data.get('success_rate()', 'N/A'):.1%}")
    print(f"  Failed Iters: {data.get('failed_iterations', 'N/A')}")

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

    # Regression band assertions
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

    With 3000 iterations, the SEs should be quite tight.
    """
    print("\n" + "=" * 80)
    print("PRODUCTION TEST: Precision Fields Validation")
    print("=" * 80)

    results = run_monte_carlo(
        mc_config_path=str(MC_CONFIG_PATH),
        base_config_path=str(BASE_SCENARIO_CONFIG),
        write_output=False,
    )

    assert results, "Monte Carlo returned no scenario results"

    mc_result = results.get("base_case") or next(iter(results.values()))
    data = _result_to_dict(mc_result)

    print(f"\nPrecision Metrics (Standard Errors):")

    for field in ("project_irr_se", "project_npv_se", "dscr_min_se"):
        value = data.get(field)
        print(f"  {field}: {value}")

        # Validation
        assert isinstance(
            value, (int, float)
        ), f"{field} missing or not numeric: {value!r}"
        assert not math.isnan(value), f"{field} is NaN"
        assert math.isfinite(value), f"{field} is not finite: {value!r}"
        assert value >= 0.0, f"{field} is negative: {value!r}"

        # With 3000 iterations, SE should be reasonably small
        if "irr" in field:
            assert value < 0.01, (
                f"{field} seems too large for 3000 iterations: {value:.6f}"
            )

    print("\n✅ All precision fields valid and within expected ranges.")
