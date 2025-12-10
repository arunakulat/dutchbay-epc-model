#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for three-scenario Monte Carlo analysis.

This module validates that:
  1. Lender/Optimistic/Pessimistic scenarios produce different IRR distributions
  2. Monte Carlo config paths are properly loaded and applied
  3. Base scenario configs are correctly separated

CESSPIT-CASPER-GWTF Compliant.

Author: CESSPIT Integration Team
Date: 2025-12-10
Version: 14.2
"""

import logging
from pathlib import Path

import pytest

from analytics.monte_carlo_v14 import run_monte_carlo_analysis

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Test Configuration
# ══════════════════════════════════════════════════════════════════════════════


SCENARIOS = {
    "lender": {
        "base_config": "scenarios/dutchbay_lendercase_2025Q4.yaml",
        "mc_config": "monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
        "scenario_name": "dutchbay_lendercase_2025Q4",
        "expected_p50_min": 0.17,  # Expect ~17.88%
        "expected_p50_max": 0.19,
    },
    "optimistic": {
        "base_config": "scenarios/dutchbay_optimistic_2025Q4.yaml",
        "mc_config": "monte_carlo/dutchbay_optimistic_mc_2025Q4.yaml",
        "scenario_name": "dutchbay_optimistic_2025Q4",
        "expected_p50_min": 0.24,  # ← NEW: reflects improved scenario
        "expected_p50_max": 0.25,  # ← NEW: allows +/- 0.5% tolerance
    },
    "pessimistic": {
        "base_config": "scenarios/dutchbay_pessimistic_2025Q4.yaml",
        "mc_config": "monte_carlo/dutchbay_pessimistic_mc_2025Q4.yaml",
        "scenario_name": "dutchbay_pessimistic_2025Q4",
        "expected_p50_min": 0.13,  # Expect ~14.2%
        "expected_p50_max": 0.16,
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Test: Individual Scenario Execution
# ══════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "scenario_key",
    ["lender", "optimistic", "pessimistic"],
)
def test_single_scenario_monte_carlo(scenario_key: str) -> None:
    """
    Test that each scenario runs successfully and produces expected IRR range.

    This validates:
      - Correct base config file is loaded
      - Correct MC config file is loaded
      - Results fall within expected P50 IRR range for that scenario
    """
    config = SCENARIOS[scenario_key]

    # Check files exist
    base_path = Path(config["base_config"])
    mc_path = Path(config["mc_config"])

    if not base_path.exists():
        pytest.skip(f"Base config not found: {base_path}")
    if not mc_path.exists():
        pytest.skip(f"MC config not found: {mc_path}")

    logger.info("\n" + "=" * 80)
    logger.info(f"Testing {scenario_key.upper()} scenario")
    logger.info("=" * 80)
    logger.info(f"Base config: {config['base_config']}")
    logger.info(f"MC config: {config['mc_config']}")
    logger.info(f"Scenario name: {config['scenario_name']}")

    # Run Monte Carlo
    results = run_monte_carlo_analysis(
        base_config_path=config["base_config"],
        scenario_config_path=config["mc_config"],
        scenario_name=config["scenario_name"],
    )

    # Extract result
    result = results.get(config["scenario_name"])
    assert result is not None, (
        f"No result for scenario '{config['scenario_name']}'. "
        f"Available: {list(results.keys())}"
    )

    # Log results
    logger.info(
        f"✓ P50 IRR: {result.project_irr_p50:.4f} "
        f"(P10={result.project_irr_p10:.4f}, P90={result.project_irr_p90:.4f})"
    )

    # Validate P50 in expected range
    assert (
        config["expected_p50_min"]
        <= result.project_irr_p50
        <= config["expected_p50_max"]
    ), (
        f"{scenario_key} P50 IRR {result.project_irr_p50:.4f} outside expected range "
        f"[{config['expected_p50_min']:.4f}, {config['expected_p50_max']:.4f}]"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test: Cross-Scenario Comparison
# ══════════════════════════════════════════════════════════════════════════════


def test_three_scenarios_are_different() -> None:
    """
    Test that all three scenarios produce DIFFERENT IRR distributions.

    This is the critical validation that:
      - Base configs are actually different
      - MC parameter overrides are being applied
      - The system isn't using the same config for all scenarios

    Expected ordering:
      Pessimistic P50 < Lender P50 < Optimistic P50
    """
    results = {}

    for scenario_key, config in SCENARIOS.items():
        base_path = Path(config["base_config"])
        mc_path = Path(config["mc_config"])

        if not base_path.exists() or not mc_path.exists():
            pytest.skip(
                f"Skipping three-scenario test: missing configs for {scenario_key}"
            )

        logger.info(f"\nRunning {scenario_key.upper()}: {config['scenario_name']}")

        mc_results = run_monte_carlo_analysis(
            base_config_path=config["base_config"],
            scenario_config_path=config["mc_config"],
            scenario_name=config["scenario_name"],
        )

        result = mc_results.get(config["scenario_name"])
        assert result is not None, f"No result for {config['scenario_name']}"

        results[scenario_key] = result
        logger.info(
            f"  P50 IRR: {result.project_irr_p50:.4f} "
            f"(P10={result.project_irr_p10:.4f}, P90={result.project_irr_p90:.4f})"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Validation: All P50 values must be different
    # ──────────────────────────────────────────────────────────────────────────

    p50_values = {k: v.project_irr_p50 for k, v in results.items()}

    logger.info("\n" + "=" * 80)
    logger.info("CROSS-SCENARIO VALIDATION")
    logger.info("=" * 80)
    logger.info(f"Lender P50:     {p50_values['lender']:.4f}")
    logger.info(f"Optimistic P50: {p50_values['optimistic']:.4f}")
    logger.info(f"Pessimistic P50: {p50_values['pessimistic']:.4f}")

    # Check no two scenarios are identical
    assert p50_values["lender"] != p50_values["optimistic"], (
        "❌ FAIL: Lender and Optimistic have IDENTICAL P50 IRR! "
        "Check that base configs are different."
    )
    assert p50_values["lender"] != p50_values["pessimistic"], (
        "❌ FAIL: Lender and Pessimistic have IDENTICAL P50 IRR! "
        "Check that base configs are different."
    )
    assert p50_values["optimistic"] != p50_values["pessimistic"], (
        "❌ FAIL: Optimistic and Pessimistic have IDENTICAL P50 IRR! "
        "Check that base configs are different."
    )

    # Check expected ordering
    assert p50_values["pessimistic"] < p50_values["lender"], (
        f"Expected Pessimistic ({p50_values['pessimistic']:.4f}) < "
        f"Lender ({p50_values['lender']:.4f})"
    )
    assert p50_values["lender"] < p50_values["optimistic"], (
        f"Expected Lender ({p50_values['lender']:.4f}) < "
        f"Optimistic ({p50_values['optimistic']:.4f})"
    )

    logger.info("\n✅ PASS: All three scenarios show different IRR distributions")
    logger.info(f"Ordering: Pessimistic < Lender < Optimistic ✓")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone Execution (for manual testing)
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Run all tests manually (outside pytest)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger.info("\n")
    logger.info("=" * 80)
    logger.info("THREE-SCENARIO MONTE CARLO ANALYSIS (CCCDIR)")
    logger.info("=" * 80)
    logger.info("\n")

    # Run individual scenario tests
    for scenario_key in ["lender", "optimistic", "pessimistic"]:
        try:
            test_single_scenario_monte_carlo(scenario_key)
        except Exception as e:
            logger.error(f"❌ {scenario_key} test failed: {e}")

    # Run cross-scenario comparison
    try:
        test_three_scenarios_are_different()
    except Exception as e:
        logger.error(f"❌ Cross-scenario test failed: {e}")


if __name__ == "__main__":
    main()
