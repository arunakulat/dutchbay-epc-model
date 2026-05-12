#!/usr/bin/env python3
"""
Complete analysis runner for DutchBay EPC Model.

Runs full pipeline with all modules:
- Cashflow analysis
- Debt structuring  
- WACC calculation
- KPI metrics
- Refinancing analysis
- Equity distribution
- FX risk analysis
"""
import json
import logging
import sys
from pathlib import Path
from typing import Any

from analytics.pipeline_v14 import run_v14_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("analysis_run.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def save_results(results: dict[str, Any], output_path: Path) -> None:
    """Save analysis results to JSON file.
    
    Parameters
    ----------
    results : dict
        Analysis results from pipeline
    output_path : Path
        Path to save JSON output
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info("Results saved to: %s", output_path)


def print_summary(results: dict[str, Any]) -> None:
    """Print analysis summary to console.
    
    Parameters
    ----------
    results : dict
        Analysis results from pipeline
    """
    print("\n" + "="*80)
    print("ANALYSIS SUMMARY")
    print("="*80)
    
    config_path = results.get('config_path', 'Unknown')
    print(f"\nScenario: {config_path}")
    
    kpis = results.get('kpis', {})
    print(f"\nProject NPV: ${kpis.get('project_npv', 0):,.0f}")
    print(f"Project IRR: {kpis.get('project_irr', 0)*100:.2f}%")
    print(f"Max Debt (USD): ${kpis.get('max_debt_usd', 0):,.0f}")
    
    debt_result = results.get('debt_result', {})
    print(f"\nMin DSCR: {debt_result.get('min_dscr', 0):.2f}")
    print(f"Balloon Remaining: ${debt_result.get('balloon_remaining', 0):,.0f}")
    
    # Refinancing results
    refi = results.get('refinancing_result')
    if refi:
        print(f"\nRefinancing Triggered: {refi.get('refinancing_triggered', False)}")
        if refi.get('refinancing_triggered'):
            print(f"Net Benefit: ${refi.get('net_benefit', 0):,.0f}")
            print(f"New Interest Rate: {refi.get('new_interest_rate', 0)*100:.2f}%")
    
    # Equity distribution results
    eq_dist = results.get('equity_distribution_result')
    if eq_dist:
        print(f"\nEquity Distribution Enabled: {eq_dist.get('distribution_enabled', False)}")
        if eq_dist.get('distribution_enabled'):
            print(f"Total Distribution: ${eq_dist.get('total_equity_distribution', 0):,.0f}")
            print(f"Class A Distribution: ${eq_dist.get('class_a_distribution', 0):,.0f}")
            print(f"Class B Distribution: ${eq_dist.get('class_b_distribution', 0):,.0f}")
    
    # FX analysis
    scenario_result = results.get('scenario_result', {})
    fx_block = scenario_result.get('fx_block')
    if fx_block:
        print(f"\nFX Strategy: {fx_block.get('strategy', 'N/A')}")
        print(f"FX Match Ratio: {fx_block.get('fx_match_ratio', 0):.1f}")
        print(f"Hedging Coverage: {fx_block.get('hedging_coverage_pct', 0):.1f}%")
    
    annual_rows = results.get('annual_rows', [])
    print(f"\nTimeline: {len(annual_rows)} years")
    
    print("\n" + "="*80)


def main():
    """Run complete analysis."""
    # Default scenario path
    scenario_path = Path("scenarios/base_case.yaml")
    
    # Check if custom scenario provided
    if len(sys.argv) > 1:
        scenario_path = Path(sys.argv[1])
    
    if not scenario_path.exists():
        logger.error("Scenario file not found: %s", scenario_path)
        print(f"\nUsage: python {sys.argv[0]} [scenario_path]")
        print(f"Default: {scenario_path}")
        sys.exit(1)
    
    logger.info("Starting complete analysis for: %s", scenario_path)
    
    try:
        # Run full pipeline with all modules enabled
        results = run_v14_pipeline(
            config=scenario_path,
            validation_mode="strict",
            validation_modules=["cashflow", "debt"],
            allow_fx_degradation=True,  # Continue even if FX fails
        )
        
        # Save results
        output_path = Path("out") / f"{scenario_path.stem}_results.json"
        save_results(results, output_path)
        
        # Print summary
        print_summary(results)
        
        logger.info("Analysis complete!")
        return 0
        
    except Exception as e:
        logger.error("Analysis failed: %s", e, exc_info=True)
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
