#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEBUG test script for three-scenario Monte Carlo analysis.

This version includes extensive logging to diagnose why all scenarios
produce identical IRR values.

CESSPIT-CASPER-GWTF Compliant (CCCDIR).

Author: CESSPIT Integration Team
Date: 2025-12-10
Version: 14.2 (DEBUG)
"""

import logging
from pathlib import Path

from analytics.monte_carlo_v14 import run_monte_carlo_analysis
from analytics.scenario_loader import load_scenario_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Test Configuration
# ══════════════════════════════════════════════════════════════════════════════


SCENARIOS = {
    "lender": {
        "base_config": "scenarios/dutchbay_lendercase_2025Q4.yaml",
        "mc_config": "monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml",
        "scenario_name": "dutchbay_lendercase_2025Q4",
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
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Helper: Debug Config Loading
# ══════════════════════════════════════════════════════════════════════════════


def debug_config_file(config_path: str, label: str) -> dict:
    """
    Load and log key parameters from a config file.

    Parameters
    ----------
    config_path : str
        Path to YAML config file
    label : str
        Label for logging (e.g., "Lender Base", "Optimistic MC")

    Returns
    -------
    dict
        Loaded configuration
    """
    path = Path(config_path)

    logger.info(f"\n{'='*80}")
    logger.info(f"DEBUG: Loading {label} Config")
    logger.info(f"{'='*80}")
    logger.info(f"File path: {config_path}")
    logger.info(f"Absolute path: {path.resolve()}")
    logger.info(f"File exists: {path.exists()}")

    if not path.exists():
        logger.error(f"❌ FILE NOT FOUND: {config_path}")
        logger.error(f"   Expected at: {path.resolve()}")
        logger.error(f"   Current directory: {Path.cwd()}")
        return {}

    config = load_scenario_config(path)

    # Extract and log key parameters
    project = config.get("project", {})
    capex = config.get("capex", {})
    opex = config.get("opex", {})
    scenario_result = config.get("scenario_result", {})

    logger.info(f"\n📊 Key Parameters from {label}:")
    logger.info(f"  Scenario Name: {scenario_result.get('scenario_name', 'NOT SET')}")
    logger.info(f"  Capacity Factor: {project.get('capacity_factor', 'NOT SET')}")
    logger.info(f"  Capacity (MW): {project.get('capacity_mw', 'NOT SET')}")
    logger.info(f"  Degradation: {project.get('degradation', 'NOT SET')}")
    logger.info(f"  CAPEX Total: ${capex.get('usd_total', 'NOT SET'):,}")
    logger.info(f"  OPEX/year: ${opex.get('usd_per_year', 'NOT SET'):,}")
    logger.info(
        f"  Grid Loss %: {config.get('regulatory', {}).get('grid_loss_pct', 'NOT SET')}"
    )

    return config


# ══════════════════════════════════════════════════════════════════════════════
# Main Test Function
# ══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Run three-scenario Monte Carlo with extensive debugging."""

    logger.info("\n")
    logger.info("=" * 80)
    logger.info("THREE-SCENARIO MONTE CARLO DEBUG TEST (CCCDIR)")
    logger.info("=" * 80)
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info("\n")

    results = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Step 1: Verify all config files exist
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: CONFIG FILE VERIFICATION")
    logger.info("=" * 80)

    for scenario_key, config in SCENARIOS.items():
        base_path = Path(config["base_config"])
        mc_path = Path(config["mc_config"])

        logger.info(f"\n{scenario_key.upper()} Scenario:")
        logger.info(
            f"  Base config: {base_path} → {'✅ EXISTS' if base_path.exists() else '❌ MISSING'}"
        )
        logger.info(
            f"  MC config: {mc_path} → {'✅ EXISTS' if mc_path.exists() else '❌ MISSING'}"
        )

        if not base_path.exists():
            logger.error(f"❌ CRITICAL: {scenario_key} base config missing!")
            logger.error(f"   Expected: {base_path.resolve()}")

        if not mc_path.exists():
            logger.error(f"❌ CRITICAL: {scenario_key} MC config missing!")
            logger.error(f"   Expected: {mc_path.resolve()}")

    # ──────────────────────────────────────────────────────────────────────────
    # Step 2: Load and inspect base configs
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: BASE CONFIG INSPECTION")
    logger.info("=" * 80)

    base_configs = {}
    for scenario_key, config in SCENARIOS.items():
        base_configs[scenario_key] = debug_config_file(
            config["base_config"], f"{scenario_key.upper()} Base"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Step 3: Compare base config parameters
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("\n" + "=" * 80)
    logger.info("STEP 3: BASE CONFIG COMPARISON")
    logger.info("=" * 80)

    lender_cf = base_configs["lender"].get("project", {}).get("capacity_factor")
    optimistic_cf = base_configs["optimistic"].get("project", {}).get("capacity_factor")
    pessimistic_cf = (
        base_configs["pessimistic"].get("project", {}).get("capacity_factor")
    )

    lender_capex = base_configs["lender"].get("capex", {}).get("usd_total")
    optimistic_capex = base_configs["optimistic"].get("capex", {}).get("usd_total")
    pessimistic_capex = base_configs["pessimistic"].get("capex", {}).get("usd_total")

    logger.info(f"\nCapacity Factor Comparison:")
    logger.info(f"  Lender:     {lender_cf}")
    logger.info(
        f"  Optimistic: {optimistic_cf} {'✅ DIFFERENT' if optimistic_cf != lender_cf else '❌ SAME AS LENDER'}"
    )
    logger.info(
        f"  Pessimistic: {pessimistic_cf} {'✅ DIFFERENT' if pessimistic_cf != lender_cf else '❌ SAME AS LENDER'}"
    )

    logger.info(f"\nCAPEX Comparison:")
    logger.info(
        f"  Lender:     ${lender_capex:,}" if lender_capex else "  Lender:     NOT SET"
    )
    logger.info(
        f"  Optimistic: ${optimistic_capex:,} {'✅ DIFFERENT' if optimistic_capex != lender_capex else '❌ SAME AS LENDER'}"
        if optimistic_capex
        else "  Optimistic: NOT SET"
    )
    logger.info(
        f"  Pessimistic: ${pessimistic_capex:,} {'✅ DIFFERENT' if pessimistic_capex != lender_capex else '❌ SAME AS LENDER'}"
        if pessimistic_capex
        else "  Pessimistic: NOT SET"
    )

    if lender_cf == optimistic_cf == pessimistic_cf:
        logger.error(
            "\n❌ CRITICAL ERROR: All base configs have IDENTICAL capacity factors!"
        )
        logger.error("   This will produce identical IRR values.")
        logger.error(
            "   Action: Create separate dutchbay_optimistic_2025Q4.yaml and dutchbay_pessimistic_2025Q4.yaml files"
        )
        return

    # ──────────────────────────────────────────────────────────────────────────
    # Step 4: Run Monte Carlo for each scenario
    # ──────────────────────────────────────────────────────────────────────────

    logger.info("\n" + "=" * 80)
    logger.info("STEP 4: MONTE CARLO EXECUTION")
    logger.info("=" * 80)

    for scenario_key, config in SCENARIOS.items():
        logger.info(f"\n{'─'*80}")
        logger.info(f"Running Monte Carlo for {scenario_key.upper()}")
        logger.info(f"{'─'*80}")
        logger.info(f"Base config: {config['base_config']}")
        logger.info(f"MC config: {config['mc_config']}")
        logger.info(f"Scenario name: {config['scenario_name']}")

        try:
            mc_results = run_monte_carlo_analysis(
                base_config_path=config["base_config"],
                scenario_config_path=config["mc_config"],
                scenario_name=config["scenario_name"],
            )

            result = mc_results.get(config["scenario_name"])
            if result is None:
                logger.error(f"❌ No result for {config['scenario_name']}")
                logger.error(f"   Available scenarios: {list(mc_results.keys())}")
                continue

            results[scenario_key] = result

            logger.info(f"\n✅ {scenario_key.upper()} Results:")
            logger.info(
                f"   P10 IRR: {result.project_irr_p10:.6f} ({result.project_irr_p10*100:.4f}%)"
            )
            logger.info(
                f"   P50 IRR: {result.project_irr_p50:.6f} ({result.project_irr_p50*100:.4f}%)"
            )
            logger.info(
                f"   P90 IRR: {result.project_irr_p90:.6f} ({result.project_irr_p90*100:.4f}%)"
            )
            logger.info(f"   Iterations: {result.n_iterations}")
            logger.info(f"   Success rate: {result.success_rate*100:.2f}%")

        except Exception as e:
            logger.error(f"❌ {scenario_key} Monte Carlo failed: {e}")
            import traceback

            logger.error(traceback.format_exc())

    # ──────────────────────────────────────────────────────────────────────────
    # Step 5: Final comparison
    # ──────────────────────────────────────────────────────────────────────────

    if len(results) < 3:
        logger.error(f"\n❌ INCOMPLETE: Only {len(results)}/3 scenarios completed")
        return

    logger.info("\n" + "=" * 80)
    logger.info("STEP 5: FINAL COMPARISON")
    logger.info("=" * 80)

    p50_values = {k: v.project_irr_p50 for k, v in results.items()}

    logger.info(f"\nP50 IRR Values:")
    logger.info(
        f"  Lender:      {p50_values['lender']:.6f} ({p50_values['lender']*100:.4f}%)"
    )
    logger.info(
        f"  Optimistic:  {p50_values['optimistic']:.6f} ({p50_values['optimistic']*100:.4f}%)"
    )
    logger.info(
        f"  Pessimistic: {p50_values['pessimistic']:.6f} ({p50_values['pessimistic']*100:.4f}%)"
    )

    logger.info(f"\nDifferences from Lender:")
    logger.info(
        f"  Optimistic:  {(p50_values['optimistic'] - p50_values['lender'])*100:+.4f} percentage points"
    )
    logger.info(
        f"  Pessimistic: {(p50_values['pessimistic'] - p50_values['lender'])*100:+.4f} percentage points"
    )

    # Check if all values are identical
    if len(set(p50_values.values())) == 1:
        logger.error("\n❌ FAIL: All three scenarios have IDENTICAL P50 IRR!")
        logger.error("   This indicates:")
        logger.error("   1. Base config files are identical, OR")
        logger.error("   2. Base config files don't exist and same default is used, OR")
        logger.error("   3. Config overrides are not being applied")
        logger.error("\n   ACTION REQUIRED:")
        logger.error(
            "   - Verify dutchbay_optimistic_2025Q4.yaml exists with CF=0.43, CAPEX=$140M"
        )
        logger.error(
            "   - Verify dutchbay_pessimistic_2025Q4.yaml exists with CF=0.35, CAPEX=$160M"
        )
        return False
    else:
        logger.info("\n✅ SUCCESS: Scenarios show different IRR distributions!")

        # Validate expected ordering
        if p50_values["pessimistic"] < p50_values["lender"] < p50_values["optimistic"]:
            logger.info("✅ Ordering correct: Pessimistic < Lender < Optimistic")
            return True
        else:
            logger.warning("⚠️ WARNING: Unexpected ordering of P50 values")
            return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
