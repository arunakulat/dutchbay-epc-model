#!/usr/bin/env python
"""
Monte Carlo Lender Pack Example

Demonstrates complete end-to-end workflow for generating lender-grade
Monte Carlo risk analytics using the Sprint 18 MC refactoring.

Workflow:
1. Load base scenario configuration
2. Run Monte Carlo simulation with LHS sampling + optional correlation
3. Generate lender risk table with covenant breach metrics
4. Build CASPER-ready payload blocks
5. Export to Excel for lender packs

Usage:
    python examples/monte_carlo_lender_pack_example.py \
      --config scenarios/dutchbay_lendercase_2025Q4.yaml \
      --n-trials 1000 \
      --dscr-floor 1.30 \
      --output lender_pack.xlsx

Requirements:
    - analytics.mc (Sprint 18 refactored MC engine)
    - pandas (for DataFrame exports)
    - openpyxl (for Excel export)

Framework Compliance:
    GWTF R24: Docstring-first, minimal external docs
    CASPER: Pure workflow, no hidden side effects
    CESSPIT: Fail-fast on missing data
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Install with: pip install pandas")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

from analytics.mc import (
    run_monte_carlo_analysis,
    build_lender_risk_table,
    build_casper_risk_blocks,
    CovenantSpec,
    load_correlation_from_config,
)


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML configuration file.

    Args:
        config_path: Path to scenario YAML file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config is invalid YAML
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)

    if not isinstance(cfg, dict):
        raise ValueError(f"Config must be a dictionary, got {type(cfg)}")

    return cfg


def run_monte_carlo_simulation(
    *,
    config: Dict[str, Any],
    n_trials: int,
    seed: int,
) -> Any:
    """Run Monte Carlo simulation.

    Args:
        config: Base scenario configuration
        n_trials: Number of Monte Carlo trials
        seed: Random seed for reproducibility

    Returns:
        MonteCarloResult with raw trials + summary statistics

    Note:
        This function wraps analytics.mc.run_monte_carlo_analysis()
        and adds progress reporting.
    """
    print(f"\nRunning {n_trials} Monte Carlo trials...")

    # Load optional correlation from config
    correlation = load_correlation_from_config(config)
    if correlation and correlation.enabled:
        print(f"  ✓ Correlation enabled ({correlation.method})")

    # Run simulation
    result = run_monte_carlo_analysis(
        base_config=config,
        n_trials=n_trials,
        seed=seed,
        common_random_numbers=True,
        correlation=correlation,
    )

    print("  ✓ Simulation complete\n")
    return result


def generate_lender_pack(
    *,
    result: Any,
    covenant_floor: float,
    output_path: Path,
) -> None:
    """Generate lender pack Excel file.

    Args:
        result: MonteCarloResult from simulation
        covenant_floor: DSCR covenant floor (e.g., 1.30)
        output_path: Path for Excel output

    Creates:
        Excel file with multiple sheets:
        - Risk Table: P50/P90/P95 metrics + covenant stats
        - Covenant Summary: Breach probability and worst-case metrics
        - Metadata: Simulation parameters and execution info
    """
    print("Generating lender pack...")

    # Build CASPER-ready blocks
    covenant_spec = CovenantSpec(dscr_floor=covenant_floor)
    blocks = build_casper_risk_blocks(result, covenant=covenant_spec)

    # Extract components
    risk_table = blocks["lender_risk_table"]
    covenant_metrics = blocks["covenant"]

    # Display risk table
    print("\nLender Risk Table:")
    print(risk_table.to_string(index=False))

    # Display covenant metrics
    print("\nCovenant Metrics:")
    print(f"  DSCR Floor: {covenant_metrics['dscr_floor']:.2f}")
    print(f"  Breach Probability: {covenant_metrics['prob_breach']:.1%}")
    print(f"  Worst-Year DSCR (P95 downside): {covenant_metrics['worst_year_dscr_p95_downside']:.2f}")
    print(f"  Number of Trials: {covenant_metrics['n_trials']}")

    # Export to Excel
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Sheet 1: Risk Table
            risk_table.to_excel(writer, sheet_name='Risk Table', index=False)

            # Sheet 2: Covenant Summary
            covenant_df = pd.DataFrame([
                {"Metric": k, "Value": v}
                for k, v in covenant_metrics.items()
            ])
            covenant_df.to_excel(writer, sheet_name='Covenant Summary', index=False)

            # Sheet 3: Metadata
            metadata = result.metadata
            metadata_df = pd.DataFrame([
                {"Parameter": k, "Value": str(v)}
                for k, v in metadata.items()
            ])
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)

        print(f"\n✓ Lender pack exported to: {output_path}\n")

    except Exception as e:
        print(f"\nWARNING: Excel export failed: {e}")
        print("Ensure openpyxl is installed: pip install openpyxl\n")


def main() -> None:
    """Main entry point for lender pack generation."""
    parser = argparse.ArgumentParser(
        description="Generate Monte Carlo lender pack with covenant breach analytics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with 1000 trials
  python examples/monte_carlo_lender_pack_example.py \
    --config scenarios/dutchbay_lendercase_2025Q4.yaml \
    --n-trials 1000
  
  # Custom DSCR floor and output path
  python examples/monte_carlo_lender_pack_example.py \
    --config scenarios/dutchbay_lendercase_2025Q4.yaml \
    --n-trials 5000 \
    --dscr-floor 1.25 \
    --output custom_lender_pack.xlsx
  
  # Reproducible results with seed
  python examples/monte_carlo_lender_pack_example.py \
    --config scenarios/dutchbay_lendercase_2025Q4.yaml \
    --n-trials 1000 \
    --seed 42
        """
    )

    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to scenario YAML configuration"
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=1000,
        help="Number of Monte Carlo trials (default: 1000)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=123,
        help="Random seed for reproducibility (default: 123)"
    )
    parser.add_argument(
        "--dscr-floor",
        type=float,
        default=1.30,
        help="DSCR covenant floor (default: 1.30)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output Excel path (default: lender_pack_<scenario>_<date>.xlsx)"
    )

    args = parser.parse_args()

    # Banner
    print("="*50)
    print("  Monte Carlo Lender Pack Generator")
    print("  Sprint 18 - Lender-Grade Risk Analytics")
    print("="*50)

    try:
        # 1. Load configuration
        print(f"\nLoading config: {args.config}")
        config = load_config(args.config)
        scenario_name = config.get("scenario_name", args.config.stem)
        print(f"  ✓ Scenario: {scenario_name}")

        # 2. Run Monte Carlo
        result = run_monte_carlo_simulation(
            config=config,
            n_trials=args.n_trials,
            seed=args.seed,
        )

        # 3. Determine output path
        if args.output is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            output_path = Path(f"lender_pack_{scenario_name}_{timestamp}.xlsx")
        else:
            output_path = args.output

        # 4. Generate lender pack
        generate_lender_pack(
            result=result,
            covenant_floor=args.dscr_floor,
            output_path=output_path,
        )

        print("="*50)
        print("  ✓ Lender Pack Generation Complete")
        print("="*50)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
