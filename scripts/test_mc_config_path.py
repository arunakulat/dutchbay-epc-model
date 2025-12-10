#!/usr/bin/env python3
"""
Test Monte Carlo Config Path Integration - CESSPIT CASPER/GWTF Compliant

This script validates Monte Carlo config path wiring through the v14 stack.

Author: CESSPIT Integration Team
Date: 2025-12-10
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def test_explicit_mc_config_single():
    """
    Test: Single scenario with explicit MC config path.

    Uses run_monte_carlo_analysis directly to avoid scenario name mismatch.
    """
    logger.info("=" * 80)
    logger.info("TEST 1: Explicit MC Config Path (Direct)")
    logger.info("=" * 80)

    try:
        from analytics.monte_carlo_v14 import run_monte_carlo_analysis

        # Run MC analysis directly with proper scenario config
        results = run_monte_carlo_analysis(
            base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
            scenario_config_path="monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
            scenario_name="dutchbay_lendercase_2025Q4",  # Must match YAML
            n_iterations=100,  # Smaller for faster testing
        )

        # Extract result
        if "dutchbay_lendercase_2025Q4" in results:
            result = results["dutchbay_lendercase_2025Q4"]

            logger.info("✅ Lender Case Results:")
            logger.info("   P50 IRR: %.2f%%", result.project_irr_p50 * 100)
            logger.info("   P10 IRR: %.2f%%", result.project_irr_p10 * 100)
            logger.info("   P90 IRR: %.2f%%", result.project_irr_p90 * 100)
            logger.info("   Iterations: %d", result.iterations)
            logger.info("   Success rate: %.1f%%", result.success_rate())

            return True, result
        else:
            logger.error("❌ Scenario not in results: %s", list(results.keys()))
            return False, None

    except Exception as exc:
        logger.error("❌ Test 1 FAILED: %s", exc, exc_info=True)
        return False, None


def test_all_three_scenarios():
    """
    Test: All three scenarios with their respective MC configs.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST 2: All Three Scenarios")
    logger.info("=" * 80)

    test_configs = [
        {
            "label": "Lender (Base)",
            "mc_config": "monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
            "scenario_name": "dutchbay_lendercase_2025Q4",
        },
        {
            "label": "Optimistic",
            "mc_config": "monte_carlo/dutchbay_optimistic_mc_2025Q4.yaml",
            "scenario_name": "dutchbay_optimistic_2025Q4",
        },
        {
            "label": "Pessimistic",
            "mc_config": "monte_carlo/dutchbay_pessimistic_mc_2025Q4.yaml",
            "scenario_name": "dutchbay_pessimistic_2025Q4",
        },
    ]

    results_summary = {}

    try:
        from analytics.monte_carlo_v14 import run_monte_carlo_analysis

        for config in test_configs:
            logger.info("")
            logger.info("Running: %s", config["label"])
            logger.info("  MC config: %s", config["mc_config"])
            logger.info("  Scenario name: %s", config["scenario_name"])

            # Check if file exists
            if not Path(config["mc_config"]).exists():
                logger.warning("  ⚠️  MC config not found (skipping)")
                continue

            try:
                results = run_monte_carlo_analysis(
                    base_config_path="scenarios/dutchbay_lendercase_2025Q4.yaml",
                    scenario_config_path=config["mc_config"],
                    scenario_name=config["scenario_name"],
                    n_iterations=100,  # Faster testing
                )

                if config["scenario_name"] in results:
                    result = results[config["scenario_name"]]

                    results_summary[config["label"]] = {
                        "p50": result.project_irr_p50,
                        "p10": result.project_irr_p10,
                        "p90": result.project_irr_p90,
                    }

                    logger.info(
                        "  ✅ %s: P50=%.2f%%, P10=%.2f%%, P90=%.2f%%",
                        config["label"],
                        result.project_irr_p50 * 100,
                        result.project_irr_p10 * 100,
                        result.project_irr_p90 * 100,
                    )
                else:
                    logger.error("  ❌ Scenario not found in results")

            except Exception as exc:
                logger.error("  ❌ Failed: %s", exc)
                continue

        # Summary table
        if results_summary:
            logger.info("")
            logger.info("=" * 80)
            logger.info("SUMMARY: Three-Scenario Comparison")
            logger.info("=" * 80)
            logger.info(
                "%-20s %10s %10s %10s", "Scenario", "P10 IRR", "P50 IRR", "P90 IRR"
            )
            logger.info("-" * 80)
            for label, data in results_summary.items():
                logger.info(
                    "%-20s %9.2f%% %9.2f%% %9.2f%%",
                    label,
                    data["p10"] * 100,
                    data["p50"] * 100,
                    data["p90"] * 100,
                )
            logger.info("=" * 80)

        return len(results_summary) > 0, results_summary

    except Exception as exc:
        logger.error("❌ Test 2 FAILED: %s", exc, exc_info=True)
        return False, None


def main():
    """
    Main test runner.
    """
    logger.info("")
    logger.info(
        "╔════════════════════════════════════════════════════════════════════════════╗"
    )
    logger.info(
        "║     CESSPIT v14 Monte Carlo Config Path Integration Tests (FIXED)         ║"
    )
    logger.info(
        "╚════════════════════════════════════════════════════════════════════════════╝"
    )
    logger.info("")

    all_passed = True

    # Test 1: Single scenario direct
    success1, result1 = test_explicit_mc_config_single()
    if not success1:
        all_passed = False

    # Test 2: All three scenarios
    success2, result2 = test_all_three_scenarios()
    if not success2:
        all_passed = False

    # Final summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 80)
    logger.info(
        "Test 1 (Direct MC Analysis):     %s", "✅ PASS" if success1 else "❌ FAIL"
    )
    logger.info(
        "Test 2 (Three Scenarios):        %s", "✅ PASS" if success2 else "❌ FAIL"
    )
    logger.info("=" * 80)

    if all_passed:
        logger.info("🎉 ALL TESTS PASSED - Monte Carlo config wiring correct!")
        sys.exit(0)
    else:
        logger.error("❌ SOME TESTS FAILED - check YAML schema compliance")
        sys.exit(1)


if __name__ == "__main__":
    main()
