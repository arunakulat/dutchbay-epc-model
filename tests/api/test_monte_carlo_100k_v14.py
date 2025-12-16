"""
tests/api/test_monte_carlo_100k_v14.py

Sprint 12 Phase 3: Production-scale Monte Carlo test with optimization.

Contract requirement: Enhance sensitivity analysis with 100,000 iteration capability
(upgraded from 3,000 baseline per Sprint 12 Phase 3 deliverables).

Optimization:
- Default: 20,000 iterations (fast CI/local runs, ~3-5 min)
- Full capability: 100,000 iterations (opt-in via DUTCHBAY_FULL_100K=1 env var)
- write_output=False to skip I/O overhead
- Simple Monte Carlo config (no heavy tariff solving)

Purpose:
- Validate Monte Carlo convergence at scale
- Calculate VaR, CVaR, P10-P90 percentile distributions
- Measure runtime performance
- Support board presentations and lender submissions

Design:
- Leverages existing analytics.sensitivity_tail_risk functions
- Uses Hydra/OmegaConf for configuration (GWTF v3.0)
- Pydantic validation on all inputs/outputs
- Comprehensive error handling and logging

Author: DutchBay EPC Model Team
Version: 1.1 (Sprint 12 Phase 3 - Optimized)
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest

from analytics.monte_carlo_v14 import run_monte_carlo
from analytics.sensitivity_tail_risk import (
    TailRiskStats,
    _compute_tail_risk_stats,
    build_tail_risk_snapshot,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Iteration scaling: default for fast CI, full for contracted capability
DEFAULT_ITERATIONS = 20_000           # Fast CI/local runs (~3-5 min)
CONTRACT_ITERATIONS = 100_000         # Full contracted capability

# Environment variable to opt-in to full 100K production run
PRODUCTION_ITERATIONS_100K = (
    CONTRACT_ITERATIONS
    if os.getenv("DUTCHBAY_FULL_100K") == "1"
    else DEFAULT_ITERATIONS
)

# Path to Monte Carlo configuration YAML (use simple regression config, no heavy solvers)
MC_CONFIG_PATH = "config/monte_carlo_regression_production.yaml"

# Path to base scenario for evaluation
BASE_SCENARIO_CONFIG = "scenarios/dutchbay_lendercase_2025Q4.yaml"

# Risk analyzer configuration
CONFIDENCE_LEVEL_95 = 0.95
CONFIDENCE_LEVEL_99 = 0.99

# Runtime constraints
MAX_RUNTIME_SECONDS = 300.0  # 5 minutes


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def _result_to_dict(mc_result: Any) -> Dict[str, Any]:
    """
    Convert MonteCarloResult to plain dict for assertions and logging.

    Handles pydantic, dataclass, and generic object serialization.
    """
    if hasattr(mc_result, "model_dump"):
        return mc_result.model_dump()
    if hasattr(mc_result, "dict"):
        return mc_result.dict()  # type: ignore[call-arg]
    if hasattr(mc_result, "__dict__"):
        return dict(mc_result.__dict__)
    return {"_repr": repr(mc_result)}


def _format_risk_report(
    risk_stats_95: TailRiskStats,
    risk_stats_99: TailRiskStats,
    metric_name: str,
    runtime_seconds: float,
    iterations: int,
) -> str:
    """
    Format comprehensive risk metrics report for logging.

    Parameters:
        risk_stats_95: Risk metrics at 95% confidence
        risk_stats_99: Risk metrics at 99% confidence
        metric_name: Name of metric (e.g., "Project IRR")
        runtime_seconds: Execution time in seconds
        iterations: Number of iterations run

    Returns:
        Formatted report string
    """
    report = f"""
╔═══════════════════════════════════════════════════════════════════════════╗
║ MONTE CARLO RISK METRICS REPORT                                          ║
║ Metric: {metric_name:<59} ║
╚═══════════════════════════════════════════════════════════════════════════╝

EXECUTION METRICS
  Runtime: {runtime_seconds:.2f} seconds
  Iterations: {iterations:,}
  Target: <{MAX_RUNTIME_SECONDS:.0f} seconds ✅

95% CONFIDENCE LEVEL
  P10 (10th percentile): {risk_stats_95.p10:>12.4f}
  P90 (90th percentile): {risk_stats_95.p90:>12.4f}
  VaR (5% worst case):   {risk_stats_95.var:>12.4f}
  CVaR (expected tail):  {risk_stats_95.cvar:>12.4f}

99% CONFIDENCE LEVEL
  VaR (1% worst case):   {risk_stats_99.var:>12.4f}
  CVaR (expected tail):  {risk_stats_99.cvar:>12.4f}

───────────────────────────────────────────────────────────────────────────
"""
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Production Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_production_scale_irr() -> None:
    """
    Production-scale Monte Carlo for IRR distribution.

    Contract: Sprint 12 Phase 3 - Enhanced Sensitivity Analysis
    Requirement: 100,000 iteration capability (opt-in via DUTCHBAY_FULL_100K=1)

    Validates:
    - Monte Carlo convergence at scale
    - IRR distribution statistics and tail risk
    - VaR/CVaR calculations at 95% and 99% confidence
    - Runtime performance (<5 minutes)

    Expected runtime: 3-5 minutes (at DEFAULT_ITERATIONS=20K)
    """
    logger.info(f"🚀 Starting Monte Carlo production test for IRR ({PRODUCTION_ITERATIONS_100K:,} iterations)")
    start_time = time.time()

    # Run Monte Carlo with optimized settings
    mc_results = run_monte_carlo(
        mc_config_path=MC_CONFIG_PATH,
        base_config_path=BASE_SCENARIO_CONFIG,
        n_iterations=PRODUCTION_ITERATIONS_100K,
        random_seed=42,  # Fixed seed for reproducibility
        write_output=False,  # Skip I/O overhead
    )

    elapsed_time = time.time() - start_time

    # Results should be a dict mapping scenario names to MonteCarloResult
    assert isinstance(mc_results, dict), f"Expected dict, got {type(mc_results)}"
    assert len(mc_results) > 0, "Monte Carlo produced no scenarios"

    # Get first scenario result
    scenario_name = list(mc_results.keys())[0]
    mc_result = mc_results[scenario_name]

    # Convert result to dict for assertions
    result_dict = _result_to_dict(mc_result)
    logger.info(f"Monte Carlo result keys: {list(result_dict.keys())}")

    # Extract IRR samples from result
    assert "raw_results" in result_dict, \
        f"IRR samples not found in result. Available: {list(result_dict.keys())}"

    raw_results = result_dict.get("raw_results", [])
    assert len(raw_results) > 0, "No raw results returned"

    # Extract IRR values from raw results
    irr_samples = [r.get("project_irr", 0.0) for r in raw_results if isinstance(r, dict)]
    irr_array = np.asarray(irr_samples, dtype=float)

    # Verify we have enough samples (allow 20% failure rate)
    expected_min_samples = PRODUCTION_ITERATIONS_100K * 0.8
    assert len(irr_array) >= expected_min_samples, \
        f"Expected at least {expected_min_samples} samples, got {len(irr_array)}"

    # Calculate risk metrics at 95% and 99% confidence
    risk_stats_95 = _compute_tail_risk_stats(irr_array, confidence=CONFIDENCE_LEVEL_95)
    risk_stats_99 = _compute_tail_risk_stats(irr_array, confidence=CONFIDENCE_LEVEL_99)

    # Validate risk metrics structure
    assert isinstance(risk_stats_95, TailRiskStats), "Invalid risk stats type at 95%"
    assert isinstance(risk_stats_99, TailRiskStats), "Invalid risk stats type at 99%"

    # Validate percentile ordering (P10 < P90)
    assert risk_stats_95.p10 < risk_stats_95.p90, \
        f"Percentile ordering broken: P10={risk_stats_95.p10}, P90={risk_stats_95.p90}"

    # Validate VaR/CVaR relationship
    assert risk_stats_95.cvar <= risk_stats_95.var or \
           abs(risk_stats_95.cvar - risk_stats_95.var) < 0.001, \
        f"CVaR/VaR relationship broken: CVaR={risk_stats_95.cvar}, VaR={risk_stats_95.var}"

    # Performance validation - hard runtime guard
    assert elapsed_time < MAX_RUNTIME_SECONDS, \
        f"Runtime {elapsed_time:.1f}s exceeds {MAX_RUNTIME_SECONDS:.0f}s target at {PRODUCTION_ITERATIONS_100K} iterations"

    # Sanity checks on IRR values
    mean_irr = float(np.mean(irr_array))
    assert 0.10 <= mean_irr <= 0.30, \
        f"Mean IRR {mean_irr:.2%} out of reasonable range [10%, 30%]"

    # Generate and log report
    report = _format_risk_report(risk_stats_95, risk_stats_99, "Project IRR", elapsed_time, PRODUCTION_ITERATIONS_100K)
    logger.info(report)
    print("\n" + report)

    logger.info(f"✅ Monte Carlo IRR test PASSED in {elapsed_time:.2f}s")


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_production_scale_dscr() -> None:
    """
    Production-scale Monte Carlo for Minimum DSCR distribution.

    Validates:
    - DSCR distribution across iterations
    - Covenant breach probability (DSCR < 1.20)
    - VaR/CVaR for covenant risk assessment
    - Risk metrics for lender presentations

    Expected runtime: 3-5 minutes (at DEFAULT_ITERATIONS=20K)
    """
    logger.info(f"🚀 Starting Monte Carlo production test for Min DSCR ({PRODUCTION_ITERATIONS_100K:,} iterations)")
    start_time = time.time()

    # Run Monte Carlo with optimized settings
    mc_results = run_monte_carlo(
        mc_config_path=MC_CONFIG_PATH,
        base_config_path=BASE_SCENARIO_CONFIG,
        n_iterations=PRODUCTION_ITERATIONS_100K,
        random_seed=42,
        write_output=False,  # Skip I/O overhead
    )

    elapsed_time = time.time() - start_time

    # Get first scenario result
    scenario_name = list(mc_results.keys())[0]
    mc_result = mc_results[scenario_name]

    # Extract DSCR samples
    result_dict = _result_to_dict(mc_result)
    assert "raw_results" in result_dict, "DSCR samples not found in result"

    raw_results = result_dict.get("raw_results", [])
    dscr_samples = [r.get("dscr_min", 1.0) for r in raw_results if isinstance(r, dict)]
    dscr_array = np.asarray(dscr_samples, dtype=float)
    
    assert len(dscr_array) > 0, "No DSCR samples extracted"

    # Calculate risk metrics
    risk_stats = _compute_tail_risk_stats(dscr_array, confidence=CONFIDENCE_LEVEL_95)

    # Validate risk metrics
    assert isinstance(risk_stats, TailRiskStats)
    assert risk_stats.p10 < risk_stats.p90

    # Calculate covenant breach probability (DSCR < 1.20 = breach threshold)
    covenant_threshold = 1.20
    breach_count = float(np.sum(dscr_array < covenant_threshold))
    breach_probability = breach_count / len(dscr_array)

    assert 0.0 <= breach_probability <= 1.0, \
        f"Breach probability {breach_probability} out of range"

    logger.info(
        f"DSCR Statistics: P10={risk_stats.p10:.2f}, P90={risk_stats.p90:.2f}, "
        f"Breach Prob={breach_probability:.2%}"
    )
    print(f"\n✅ Covenant Breach Probability (DSCR < {covenant_threshold}): {breach_probability:.2%}")

    # Performance validation - hard runtime guard
    assert elapsed_time < MAX_RUNTIME_SECONDS, \
        f"Runtime {elapsed_time:.1f}s exceeds {MAX_RUNTIME_SECONDS:.0f}s target at {PRODUCTION_ITERATIONS_100K} iterations"

    logger.info(f"✅ Monte Carlo DSCR test PASSED in {elapsed_time:.2f}s")


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_convergence_validation() -> None:
    """
    Validate Monte Carlo convergence at scale.

    Runs two independent simulations and compares their P50 estimates.
    At scaled iterations, convergence should be tight (<0.5% variation).

    Expected runtime: 6-10 minutes (two runs at DEFAULT_ITERATIONS=20K each)
    """
    logger.info(f"🚀 Starting convergence validation ({PRODUCTION_ITERATIONS_100K:,} iterations per run)")

    # Run first simulation
    start_1 = time.time()
    mc_results_1 = run_monte_carlo(
        mc_config_path=MC_CONFIG_PATH,
        base_config_path=BASE_SCENARIO_CONFIG,
        n_iterations=PRODUCTION_ITERATIONS_100K,
        random_seed=42,
        write_output=False,
    )
    time_1 = time.time() - start_1

    # Run second simulation (different seed for independence)
    start_2 = time.time()
    mc_results_2 = run_monte_carlo(
        mc_config_path=MC_CONFIG_PATH,
        base_config_path=BASE_SCENARIO_CONFIG,
        n_iterations=PRODUCTION_ITERATIONS_100K,
        random_seed=43,  # Different seed
        write_output=False,
    )
    time_2 = time.time() - start_2

    # Extract and compare
    scenario_name_1 = list(mc_results_1.keys())[0]
    scenario_name_2 = list(mc_results_2.keys())[0]

    result_dict_1 = _result_to_dict(mc_results_1[scenario_name_1])
    result_dict_2 = _result_to_dict(mc_results_2[scenario_name_2])

    raw_1 = result_dict_1.get("raw_results", [])
    raw_2 = result_dict_2.get("raw_results", [])

    irr_samples_1 = [r.get("project_irr", 0.0) for r in raw_1 if isinstance(r, dict)]
    irr_samples_2 = [r.get("project_irr", 0.0) for r in raw_2 if isinstance(r, dict)]

    irr_array_1 = np.asarray(irr_samples_1, dtype=float)
    irr_array_2 = np.asarray(irr_samples_2, dtype=float)

    # Calculate medians
    p50_1 = float(np.percentile(irr_array_1, 50))
    p50_2 = float(np.percentile(irr_array_2, 50))

    variation = abs(p50_1 - p50_2) / ((p50_1 + p50_2) / 2) if (p50_1 + p50_2) > 0 else 0.0

    logger.info(
        f"Convergence Check: P50_1={p50_1:.4f}, P50_2={p50_2:.4f}, "
        f"Variation={variation:.2%}"
    )

    # At scaled iterations, variation should be <0.5%
    assert variation < 0.005, \
        f"Convergence too loose: variation={variation:.2%} (target <0.5%)"

    print(f"\n✅ Monte Carlo Convergence: {variation:.3%} variation (excellent!)")
    logger.info(f"✅ Convergence validation PASSED")
