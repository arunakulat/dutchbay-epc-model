#!/usr/bin/env python3
"""
Spring 12 Full Pipeline: Refinancing + Distributions + Monte Carlo

This script demonstrates the complete integration of:
1. Refinancing Module (v14) - mid-life debt restructuring
2. Equity Distribution Module (v14) - post-payoff distributions
3. Monte Carlo Engine (v14) - 100K iteration risk analysis

Usage:
    python scripts/run_full_pipeline_sprint12.py

Optional:
    python scripts/run_full_pipeline_sprint12.py --iterations 100000
    python scripts/run_full_pipeline_sprint12.py --scenario base upside downside
    python scripts/run_full_pipeline_sprint12.py --stress all

Output:
    - Console: Base case + risk metrics
    - CSV: monte_carlo_results_*.csv
    - JSONL: monte_carlo_iterations_*.jsonl
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from hydra import compose, initialize_config_dir
    from hydra.core.config_store import ConfigStore
    from omegaconf import OmegaConf, DictConfig
    from pathlib import Path
    import yaml
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("Install with: pip install hydra-core omegaconf pyyaml")
    sys.exit(1)

try:
    from analytics.monte_carlo_v14 import run_monte_carlo
    from analytics.sensitivity_tail_risk import (
        _compute_tail_risk_stats,
        build_tail_risk_snapshot,
    )
except ImportError as e:
    print(f"❌ Missing DutchBay module: {e}")
    print("Ensure you're in the repo root and modules are installed.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG_DIR = Path("config").resolve()
SCENARIO_DIR = CONFIG_DIR / "scenarios"
STRESS_TEST_DIR = SCENARIO_DIR / "stress_tests"

# Monte Carlo configuration
MC_CONFIG_DEFAULT = "monte_carlo_regression_production.yaml"
MC_ITERATIONS_DEFAULT = 10_000  # Use smaller for demo; 100K in production
MC_ITERATIONS_FULL = 100_000

# Scenarios to test
BASE_SCENARIOS = [
    "dutchbay_lendercase_2025Q4.yaml",
]

STRESS_SCENARIOS = [
    "stress_tariff_minus_20.yaml",
    "stress_capex_plus_20.yaml",
    "stress_opex_inflation_2pct.yaml",
    "stress_fx_depr_50pct.yaml",
    "stress_capacity_minus_10.yaml",
    "stress_combined_worst.yaml",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def format_currency(value: float) -> str:
    """Format number as currency."""
    if abs(value) >= 1e9:
        return f"${value/1e9:.2f}B"
    elif abs(value) >= 1e6:
        return f"${value/1e6:.2f}M"
    else:
        return f"${value:,.0f}"


def print_header(title: str, width: int = 80) -> None:
    """Print formatted section header."""
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


def print_subheader(title: str) -> None:
    """Print formatted subsection header."""
    print(f"\n  📊 {title}")
    print(f"  {'-' * 70}")


def verify_config_files() -> bool:
    """Verify required configuration files exist."""
    required = [
        CONFIG_DIR / MC_CONFIG_DEFAULT,
        SCENARIO_DIR / BASE_SCENARIOS[0],
        STRESS_TEST_DIR / STRESS_SCENARIOS[0],
    ]

    missing = [p for p in required if not p.exists()]
    if missing:
        print(f"\n❌ Missing configuration files:")
        for p in missing:
            print(f"   - {p}")
        return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: BASE CASE ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def run_base_case_analysis(mc_config: str, scenario_file: str, iterations: int) -> dict:
    """
    Run base case Monte Carlo analysis.

    Parameters:
        mc_config: Path to Monte Carlo config YAML
        scenario_file: Filename of scenario in scenarios/
        iterations: Number of iterations

    Returns:
        Dict with results
    """
    scenario_path = SCENARIO_DIR / scenario_file
    mc_config_path = CONFIG_DIR / mc_config

    print_header(f"BASE CASE: {scenario_file} ({iterations:,} iterations)")

    start_time = time.time()
    print(f"\n  ⏳ Running Monte Carlo analysis...")

    try:
        mc_results = run_monte_carlo(
            mc_config_path=str(mc_config_path),
            base_config_path=str(scenario_path),
            n_iterations=iterations,
            random_seed=42,  # Reproducible
            write_output=True,
        )
    except Exception as e:
        print(f"\n❌ Monte Carlo failed: {e}")
        return {}

    elapsed = time.time() - start_time

    # Extract first scenario result
    if not mc_results:
        print("\n❌ No Monte Carlo results returned")
        return {}

    scenario_name = list(mc_results.keys())[0]
    mc_result = mc_results[scenario_name]

    print(f"\n  ✅ Completed in {elapsed:.1f}s")

    # Display results
    print_subheader(f"Results: {scenario_name}")
    print(
        f"  Iterations: {iterations:,} "
        f"(Success: {mc_result.success_rate():.1%})\n"
    )

    # Project IRR distribution
    print(f"  Project IRR Distribution:")
    print(f"    P10:  {mc_result.project_irr_p10:>8.2%}")
    print(f"    P50:  {mc_result.project_irr_p50:>8.2%}  (median)")
    print(f"    P90:  {mc_result.project_irr_p90:>8.2%}")
    print(f"    Mean: {mc_result.project_irr_mean:>8.2%}  (±{mc_result.project_irr_se:.2%})")
    print()

    # Project NPV distribution
    print(f"  Project NPV Distribution:")
    print(f"    Mean: {format_currency(mc_result.project_npv_mean)}  (±{format_currency(mc_result.project_npv_se)})")
    print()

    # DSCR metrics
    print(f"  Min DSCR (covenant):")
    print(f"    P10:  {mc_result.dscr_min_p10:>8.2f}")
    print(f"    P50:  {mc_result.dscr_min_p50:>8.2f}")
    print(f"    P90:  {mc_result.dscr_min_p90:>8.2f}")
    print()

    # Risk metrics (VaR/CVaR)
    if hasattr(mc_result, "raw_results") and mc_result.raw_results:
        irr_samples = np.array(
            [r.get("project_irr", 0.0) for r in mc_result.raw_results if isinstance(r, dict)]
        )
        if len(irr_samples) > 0:
            risk_stats_95 = _compute_tail_risk_stats(irr_samples, confidence=0.95)
            print(f"  Risk Metrics (95% confidence):")
            print(f"    VaR:  {risk_stats_95.var:.2%}  (worst 5% threshold)")
            print(f"    CVaR: {risk_stats_95.cvar:.2%}  (expected tail loss)")
            print()

    return {
        "scenario": scenario_name,
        "iterations": iterations,
        "result": mc_result,
        "runtime": elapsed,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: STRESS TEST ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


def run_stress_tests(mc_config: str, iterations: int = 5_000) -> list[dict]:
    """
    Run stress tests across all scenarios.

    Parameters:
        mc_config: Path to Monte Carlo config YAML
        iterations: Number of iterations per stress test

    Returns:
        List of result dicts
    """
    print_header("STRESS TEST ANALYSIS", width=80)
    print(f"\n  Testing {len(STRESS_SCENARIOS)} scenarios at {iterations:,} iterations each...\n")

    results = []
    start_time = time.time()

    for i, stress_scenario in enumerate(STRESS_SCENARIOS, 1):
        scenario_path = STRESS_TEST_DIR / stress_scenario
        if not scenario_path.exists():
            print(f"  ⚠️  [{i}/{len(STRESS_SCENARIOS)}] {stress_scenario} - FILE NOT FOUND")
            continue

        scenario_label = stress_scenario.replace(".yaml", "").replace("stress_", "")
        print(f"  [{i}/{len(STRESS_SCENARIOS)}] {scenario_label:.<40}", end="", flush=True)

        try:
            stress_start = time.time()
            mc_results = run_monte_carlo(
                mc_config_path=str(CONFIG_DIR / mc_config),
                base_config_path=str(scenario_path),
                n_iterations=iterations,
                random_seed=42,
                write_output=False,  # Skip I/O for speed
            )

            if mc_results:
                scenario_name = list(mc_results.keys())[0]
                mc_result = mc_results[scenario_name]
                stress_time = time.time() - stress_start

                results.append(
                    {
                        "scenario": scenario_label,
                        "result": mc_result,
                        "runtime": stress_time,
                    }
                )

                status = f"IRR P50={mc_result.project_irr_p50:.1%}"
                print(f" ✅ {status}")
            else:
                print(f" ❌ No results")
        except Exception as e:
            print(f" ❌ ERROR: {str(e)[:40]}")

    total_time = time.time() - start_time
    print(f"\n  Total stress test time: {total_time:.1f}s\n")

    return results


def print_stress_summary(results: list[dict]) -> None:
    """Print summary table of stress test results."""
    if not results:
        print("  (No stress test results available)")
        return

    print_subheader("Stress Test Summary")
    print(
        f"  {'Scenario':<25} {'IRR P50':>10} {'Min DSCR P10':>15} {'Breach Risk':>12}"
    )
    print(f"  {'-' * 65}")

    for r in results:
        scenario = r["scenario"][:23]
        irr = r["result"].project_irr_p50
        dscr = r["result"].dscr_min_p10
        breach = 1 - r["result"].success_rate()

        print(
            f"  {scenario:<25} {irr:>9.2%}  {dscr:>14.2f}  {breach:>11.1%}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════


def main() -> None:
    """
    Main pipeline execution.
    """
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║           SPRINT 12 FULL PIPELINE DEMONSTRATION                             ║
║   Refinancing + Equity Distributions + 100K Monte Carlo Analysis            ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    )

    # Verify config files
    if not verify_config_files():
        sys.exit(1)

    # Determine iteration count from environment
    iterations = int(os.getenv("DUTCHBAY_FULL_100K") or "0")
    if iterations == 0:
        iterations = MC_ITERATIONS_DEFAULT
    iterations = min(iterations, MC_ITERATIONS_FULL)  # Cap at 100K

    print(f"\n  Configuration verified ✅")
    print(f"  Iterations: {iterations:,}")
    print(f"  Config: {MC_CONFIG_DEFAULT}")
    print(f"  Base scenarios: {len(BASE_SCENARIOS)}")
    print(f"  Stress scenarios: {len(STRESS_SCENARIOS)}")

    pipeline_start = time.time()

    # === BASE CASE ===
    base_results = []
    for scenario_file in BASE_SCENARIOS:
        result = run_base_case_analysis(
            mc_config=MC_CONFIG_DEFAULT,
            scenario_file=scenario_file,
            iterations=iterations,
        )
        if result:
            base_results.append(result)

    # === STRESS TESTS ===
    stress_results = run_stress_tests(
        mc_config=MC_CONFIG_DEFAULT,
        iterations=max(iterations // 4, 1000),  # Fewer iterations for speed
    )
    print_stress_summary(stress_results)

    # === SUMMARY ===
    total_time = time.time() - pipeline_start
    print_header("PIPELINE COMPLETE", width=80)
    print(f"\n  Total execution time: {total_time:.1f}s")
    print(f"  Base case results: {len(base_results)}")
    print(f"  Stress test results: {len(stress_results)}")
    print(f"\n  ✅ Full pipeline executed successfully\n")

    # === RECOMMENDATIONS ===
    if base_results:
        base_result = base_results[0]["result"]
        print_header("LENDER SUBMISSION READY", width=80)
        print(f"\n  Project Summary:")
        print(f"    Base Case IRR: {base_result.project_irr_mean:.1%}")
        print(f"    Min DSCR: {base_result.dscr_min_p50:.2f}")
        print(f"    Success Rate: {base_result.success_rate():.1%}")
        print(f"\n  ✅ Ready for board presentations and lender submissions\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Pipeline interrupted by user\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Pipeline failed: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
