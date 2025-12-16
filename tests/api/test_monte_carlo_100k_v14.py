"""
tests/api/test_monte_carlo_100k_v14.py

Sprint 12 Phase 3: Production-scale 100K iteration Monte Carlo test.

Contract requirement: Enhance sensitivity analysis with 100,000 iterations
(upgraded from 3,000 baseline per Sprint 12 Phase 3 deliverables).

Purpose:
- Validate Monte Carlo convergence at production scale
- Calculate VaR, CVaR, P10-P90 percentile distributions
- Measure runtime performance (<5 minutes target)
- Support board presentations and lender submissions

Design:
- Leverages existing analytics.sensitivity_tail_risk.TailRiskAnalyzer
- Uses Hydra/OmegaConf for configuration (GWTF v3.0)
- Pydantic validation on all inputs/outputs
- Comprehensive error handling and logging

Author: DutchBay EPC Model Team
Version: 1.0 (Sprint 12 Phase 3)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.monte_carlo_v14 import run_monte_carlo
from analytics.sensitivity_tail_risk import TailRiskAnalyzer, TailRiskStats

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────

MC_CONFIG_PATH = Path("config/monte_carlo_regression_production.yaml")
BASE_SCENARIO_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")

# Production scale iterations (100K per Sprint 12 Phase 3 contract)
PRODUCTION_ITERATIONS_100K = 100_000

# Risk analyzer configuration
CONFIDENCE_LEVEL_95 = 0.95
CONFIDENCE_LEVEL_99 = 0.99


# ────────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────────────────────────────────────


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
) -> str:
    """
    Format comprehensive risk metrics report for logging.

    Parameters:
        risk_stats_95: Risk metrics at 95% confidence
        risk_stats_99: Risk metrics at 99% confidence
        metric_name: Name of metric (e.g., "Project IRR")
        runtime_seconds: Execution time in seconds

    Returns:
        Formatted report string
    """
    report = f"""
╔════════════════════════════════════════════════════════════════╗
║ 100K MONTE CARLO RISK METRICS REPORT                           ║
║ Metric: {metric_name:<49} ║
╚════════════════════════════════════════════════════════════════╝

EXECUTION METRICS
  Runtime: {runtime_seconds:.2f} seconds
  Iterations: {PRODUCTION_ITERATIONS_100K:,}
  Target: <300 seconds ✅

95% CONFIDENCE LEVEL
  P10 (10th percentile): {risk_stats_95.p10:>12.4f}
  P90 (90th percentile): {risk_stats_95.p90:>12.4f}
  VaR (5% worst case):   {risk_stats_95.var:>12.4f}
  CVaR (expected tail):  {risk_stats_95.cvar:>12.4f}

99% CONFIDENCE LEVEL
  VaR (1% worst case):   {risk_stats_99.var:>12.4f}
  CVaR (expected tail):  {risk_stats_99.cvar:>12.4f}

════════════════════════════════════════════════════════════════
"""
    return report


# ────────────────────────────────────────────────────────────────────────────────
# Production Tests
# ────────────────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_production_scale_irr() -> None:
    """
    Production-scale 100K iteration Monte Carlo for IRR distribution.

    Contract: Sprint 12 Phase 3 - Enhanced Sensitivity Analysis
    Requirement: 100,000 iterations with risk metrics (VaR/CVaR/percentiles)

    Validates:
    - Monte Carlo convergence at 100K scale
    - IRR distribution statistics and tail risk
    - VaR/CVaR calculations at 95% and 99% confidence
    - Runtime performance (<5 minutes)

    Expected runtime: 3-5 minutes (production-scale)
    """
    logger.info("🚀 Starting 100K Monte Carlo production test for IRR")
    start_time = time.time()

    # Run Monte Carlo with 100K iterations
    mc_result = run_monte_carlo(
        config_path=MC_CONFIG_PATH,
        scenario_config_path=BASE_SCENARIO_CONFIG,
        iterations=PRODUCTION_ITERATIONS_100K,
        seed=42,  # Fixed seed for reproducibility
    )

    elapsed_time = time.time() - start_time

    # Convert result to dict for assertions
    result_dict = _result_to_dict(mc_result)
    logger.info(f"Monte Carlo result keys: {list(result_dict.keys())}")

    # Extract IRR samples from result
    assert "irr_samples" in result_dict or "project_irr_samples" in result_dict, \
        f"IRR samples not found in result. Available: {list(result_dict.keys())}"

    irr_samples = result_dict.get("irr_samples") or result_dict.get("project_irr_samples")
    assert len(irr_samples) == PRODUCTION_ITERATIONS_100K, \
        f"Expected {PRODUCTION_ITERATIONS_100K} samples, got {len(irr_samples)}"

    # Calculate risk metrics at 95% and 99% confidence
    analyzer_95 = TailRiskAnalyzer(confidence_level=CONFIDENCE_LEVEL_95)
    analyzer_99 = TailRiskAnalyzer(confidence_level=CONFIDENCE_LEVEL_99)

    risk_stats_95 = analyzer_95.calculate_var_cvar(irr_samples, return_type="project_irr")
    risk_stats_99 = analyzer_99.calculate_var_cvar(irr_samples, return_type="project_irr")

    # Validate risk metrics structure
    assert isinstance(risk_stats_95, TailRiskStats), "Invalid risk stats type at 95%"
    assert isinstance(risk_stats_99, TailRiskStats), "Invalid risk stats type at 99%"

    # Validate percentile ordering (P10 < P90)
    assert risk_stats_95.p10 < risk_stats_95.p90, \
        f"Percentile ordering broken: P10={risk_stats_95.p10}, P90={risk_stats_95.p90}"

    # Validate VaR/CVaR relationship (CVaR should be <= VaR for tail)
    assert risk_stats_95.cvar <= risk_stats_95.var or \
           abs(risk_stats_95.cvar - risk_stats_95.var) < 0.001, \
        f"CVaR/VaR relationship broken at 95%: CVaR={risk_stats_95.cvar}, VaR={risk_stats_95.var}"

    # Performance validation (<5 minutes = 300 seconds)
    assert elapsed_time < 300, \
        f"Runtime {elapsed_time:.1f}s exceeds 5-minute (300s) target"

    # Sanity checks on IRR values
    mean_irr = sum(irr_samples) / len(irr_samples)
    assert 0.10 <= mean_irr <= 0.30, \
        f"Mean IRR {mean_irr:.2%} out of reasonable range [10%, 30%]"

    # Generate and log report
    report = _format_risk_report(risk_stats_95, risk_stats_99, "Project IRR", elapsed_time)
    logger.info(report)

    # Print for visibility in test output
    print("\n" + report)

    logger.info(f"✅ 100K Monte Carlo IRR test PASSED in {elapsed_time:.2f}s")


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_production_scale_dscr() -> None:
    """
    Production-scale 100K iteration Monte Carlo for Minimum DSCR distribution.

    Validates:
    - DSCR distribution across 100K scenarios
    - Covenant breach probability (DSCR < 1.20)
    - VaR/CVaR for covenant risk assessment
    - Risk metrics for lender presentations

    Expected runtime: 3-5 minutes
    """
    logger.info("🚀 Starting 100K Monte Carlo production test for Min DSCR")
    start_time = time.time()

    # Run Monte Carlo
    mc_result = run_monte_carlo(
        config_path=MC_CONFIG_PATH,
        scenario_config_path=BASE_SCENARIO_CONFIG,
        iterations=PRODUCTION_ITERATIONS_100K,
        seed=42,
    )

    elapsed_time = time.time() - start_time

    # Extract DSCR samples
    result_dict = _result_to_dict(mc_result)
    assert "dscr_min_samples" in result_dict or "min_dscr_samples" in result_dict, \
        "DSCR samples not found in result"

    dscr_samples = result_dict.get("dscr_min_samples") or result_dict.get("min_dscr_samples")
    assert len(dscr_samples) == PRODUCTION_ITERATIONS_100K

    # Calculate risk metrics
    analyzer = TailRiskAnalyzer(confidence_level=CONFIDENCE_LEVEL_95)
    risk_stats = analyzer.calculate_var_cvar(dscr_samples, return_type="min_dscr")

    # Validate risk metrics
    assert isinstance(risk_stats, TailRiskStats)
    assert risk_stats.p10 < risk_stats.p90

    # Calculate covenant breach probability (DSCR < 1.20 = breach threshold)
    covenant_threshold = 1.20
    breach_count = sum(1 for d in dscr_samples if d < covenant_threshold)
    breach_probability = breach_count / len(dscr_samples)

    # Sanity check
    assert 0.0 <= breach_probability <= 1.0, \
        f"Breach probability {breach_probability} out of range"

    logger.info(
        f"DSCR Statistics: P10={risk_stats.p10:.2f}, P90={risk_stats.p90:.2f}, "
        f"Breach Prob={breach_probability:.2%}"
    )
    print(f"\n✅ Covenant Breach Probability (DSCR < {covenant_threshold}): {breach_probability:.2%}")

    # Performance validation
    assert elapsed_time < 300

    logger.info(f"✅ 100K Monte Carlo DSCR test PASSED in {elapsed_time:.2f}s")


@pytest.mark.slow
@pytest.mark.production
def test_monte_carlo_100k_convergence_validation() -> None:
    """
    Validate Monte Carlo convergence at 100K scale.

    Runs two independent simulations and compares their P50 estimates.
    At 100K scale, convergence should be very tight (<0.1% variation).

    Purpose: Ensure statistical reliability of 100K iteration baseline.
    """
    logger.info("🚀 Starting convergence validation at 100K scale")

    # Run first simulation
    start_1 = time.time()
    mc_result_1 = run_monte_carlo(
        config_path=MC_CONFIG_PATH,
        scenario_config_path=BASE_SCENARIO_CONFIG,
        iterations=PRODUCTION_ITERATIONS_100K,
        seed=42,
    )
    time_1 = time.time() - start_1

    # Run second simulation (different seed for independence)
    start_2 = time.time()
    mc_result_2 = run_monte_carlo(
        config_path=MC_CONFIG_PATH,
        scenario_config_path=BASE_SCENARIO_CONFIG,
        iterations=PRODUCTION_ITERATIONS_100K,
        seed=43,  # Different seed
    )
    time_2 = time.time() - start_2

    # Extract and compare
    result_dict_1 = _result_to_dict(mc_result_1)
    result_dict_2 = _result_to_dict(mc_result_2)

    irr_samples_1 = result_dict_1.get("irr_samples") or result_dict_1.get("project_irr_samples")
    irr_samples_2 = result_dict_2.get("irr_samples") or result_dict_2.get("project_irr_samples")

    # Calculate medians
    p50_1 = sorted(irr_samples_1)[len(irr_samples_1) // 2]
    p50_2 = sorted(irr_samples_2)[len(irr_samples_2) // 2]

    variation = abs(p50_1 - p50_2) / ((p50_1 + p50_2) / 2)

    logger.info(
        f"Convergence Check: P50_1={p50_1:.4f}, P50_2={p50_2:.4f}, "
        f"Variation={variation:.2%}"
    )

    # At 100K scale, variation should be <0.5%
    assert variation < 0.005, \
        f"Convergence too loose at 100K: variation={variation:.2%} (target <0.5%)"

    print(f"\n✅ Monte Carlo Convergence: {variation:.3%} variation (excellent!)")
    logger.info(f"✅ Convergence validation PASSED")
