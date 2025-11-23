"""Canonical CLI for DutchBay V14 Pipeline - WACC-Integrated.

Single entry point for all v14 scenario evaluation modes:
- base: Single scenario evaluation
- sensitivity: Tornado/one-at-a-time analysis
- montecarlo: Stochastic simulation
- optimize: Parameter optimization

PHASE 1 ENHANCEMENTS:
---------------------
- WACC transparency in logging (discount_rate_used, real/nominal)
- Prudential NPV surfacing when available
- Enhanced export fields (discount rates, WACC components)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from analytics.evaluate_scenario import evaluate_scenario

logger = logging.getLogger(__name__)

# Mode registry for extensibility
MODE_REGISTRY = {
    "base": "Base scenario evaluation",
    "sensitivity": "Sensitivity analysis (not yet implemented)",
    "montecarlo": "Monte Carlo simulation (not yet implemented)",
    "optimize": "Parameter optimization (not yet implemented)",
}


def run_base_mode(config_path: str, validation_mode: str, export_path: str | None) -> int:
    """
    Run base scenario evaluation mode with WACC-integrated valuation.

    Parameters
    ----------
    config_path : str
        Path to scenario YAML/JSON config.
    validation_mode : str
        Schema validation strictness ("strict", "relaxed", "none").
    export_path : str | None
        Optional path to export results (JSON format).

    Returns
    -------
    int
        Exit code (0 = success, 1 = failure).
    """
    try:
        logger.info("=" * 80)
        logger.info("Running base scenario evaluation: %s", config_path)
        logger.info("=" * 80)

        # Evaluate scenario through v14 pipeline with WACC
        result = evaluate_scenario(
            config_path=config_path,
            validation_mode=validation_mode,
        )

        # =====================================================================
        # PHASE 1: Enhanced logging with WACC fields
        # =====================================================================
        logger.info("")
        logger.info("=" * 80)
        logger.info("SCENARIO RESULTS: %s", result.scenario_name)
        logger.info("=" * 80)

        # Project valuation
        logger.info("Project NPV:        %s", f"{result.project_npv:,.0f}")
        logger.info("Project IRR:        %.2f%%", result.project_irr * 100)

        # WACC and discount rate transparency
        if result.discount_rate_used is not None:
            wacc_type = "real" if result.wacc_is_real else "nominal"
            logger.info(
                "Discount Rate:      %.2f%% (%s)",
                result.discount_rate_used * 100,
                wacc_type,
            )
        
        # Prudential valuation (if WACC configured)
        if result.wacc is not None:
            logger.info("")
            logger.info("WACC Components:")
            logger.info("  Mode:             %s", result.wacc.base.mode)
            if result.wacc.base.mode == "capm":
                logger.info("  Risk-free rate:   %.2f%%", result.wacc.base.risk_free_rate * 100)
                logger.info("  Equity beta:      %.2f", result.wacc.base.equity_beta_levered)
                logger.info("  Cost of equity:   %.2f%%", result.wacc.base.cost_of_equity * 100)
                logger.info("  Cost of debt:     %.2f%%", result.wacc.base.cost_of_debt_pretax * 100)
                logger.info("  Gearing (D/V):    %.1f%%", result.wacc.base.target_debt_to_value * 100)
            
            if result.wacc.prudential_npv is not None and result.wacc.prudential_rate is not None:
                logger.info("")
                logger.info("Prudential Valuation:")
                logger.info(
                    "  Discount Rate:    %.2f%% (base + %d bps)",
                    result.wacc.prudential_rate * 100,
                    result.wacc.base.prudential_spread_bps,
                )
                logger.info("  NPV (prudential): %s", f"{result.wacc.prudential_npv:,.0f}")
                npv_delta = result.wacc.prudential_npv - result.project_npv
                logger.info("  NPV delta:        %s", f"{npv_delta:,.0f}")

        # Debt metrics
        logger.info("")
        logger.info("Debt Metrics:")
        logger.info("  Min DSCR:         %.2fx", result.min_dscr)
        logger.info("  Max Debt (USD):   %s", f"{result.max_debt_usd:,.0f}")

        logger.info("=" * 80)
        logger.info("")

        # =====================================================================
        # PHASE 1: Enhanced export with WACC fields
        # =====================================================================
        if export_path:
            export_data = {
                # Core results
                "scenario_name": result.scenario_name,
                "config_path": result.config_path,
                "project_npv": result.project_npv,
                "project_irr": result.project_irr,
                "min_dscr": result.min_dscr,
                "max_debt_usd": result.max_debt_usd,
                
                # WACC and discount rate fields (Phase 1)
                "discount_rate_used": result.discount_rate_used,
                "wacc_label": result.wacc_label,
                "wacc_is_real": result.wacc_is_real,
            }

            # Add WACC components if present
            if result.wacc is not None:
                export_data["wacc"] = {
                    "mode": result.wacc.base.mode,
                    "wacc_nominal": result.wacc.base.wacc_nominal,
                    "wacc_real": result.wacc.base.wacc_real,
                    "wacc_prudential": result.wacc.base.wacc_prudential,
                }
                
                if result.wacc.base.mode == "capm":
                    export_data["wacc"]["components"] = {
                        "risk_free_rate": result.wacc.base.risk_free_rate,
                        "market_risk_premium": result.wacc.base.market_risk_premium,
                        "asset_beta": result.wacc.base.asset_beta,
                        "equity_beta_levered": result.wacc.base.equity_beta_levered,
                        "cost_of_equity": result.wacc.base.cost_of_equity,
                        "cost_of_debt_pretax": result.wacc.base.cost_of_debt_pretax,
                        "cost_of_debt_aftertax": result.wacc.base.cost_of_debt_aftertax,
                        "target_gearing": result.wacc.base.target_debt_to_value,
                        "tax_rate": result.wacc.base.tax_rate,
                    }
                
                # Prudential valuation
                if result.wacc.prudential_npv is not None:
                    export_data["prudential"] = {
                        "discount_rate": result.wacc.prudential_rate,
                        "npv": result.wacc.prudential_npv,
                        "npv_delta": result.wacc.prudential_npv - result.project_npv,
                    }

            export_path_obj = Path(export_path)
            export_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            with open(export_path_obj, "w") as f:
                json.dump(export_data, f, indent=2)
            
            logger.info("Results exported to: %s", export_path)

        logger.info("✓ Base scenario evaluation completed successfully")
        return 0

    except Exception as exc:
        logger.error("Base scenario evaluation failed: %s", exc, exc_info=True)
        return 1


def run_sensitivity_mode(config_path: str, knobs_path: str, export_path: str | None) -> int:
    """Run sensitivity analysis mode (placeholder for Phase 3)."""
    logger.error("Sensitivity mode not yet implemented (Phase 3)")
    return 1


def run_montecarlo_mode(config_path: str, dists_path: str, export_path: str | None) -> int:
    """Run Monte Carlo simulation mode (placeholder for Phase 3)."""
    logger.error("Monte Carlo mode not yet implemented (Phase 3)")
    return 1


def run_optimize_mode(config_path: str, opt_config_path: str, export_path: str | None) -> int:
    """Run optimization mode (placeholder for Phase 4)."""
    logger.error("Optimize mode not yet implemented (Phase 4)")
    return 1


def main() -> int:
    """Main CLI entry point with mode registry."""
    parser = argparse.ArgumentParser(
        description="DutchBay V14 Pipeline - Canonical Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available modes:
{chr(10).join(f'  {mode:12s} - {desc}' for mode, desc in MODE_REGISTRY.items())}

Examples:
  # Base scenario evaluation
  python run_full_pipeline.py --mode base --config scenarios/base_case.yaml
  
  # With export
  python run_full_pipeline.py --mode base --config scenarios/base_case.yaml \\
      --export outputs/base_results.json
  
  # Skip validation
  python run_full_pipeline.py --mode base --config scenarios/test.yaml \\
      --validation none
        """,
    )

    parser.add_argument(
        "--mode",
        type=str,
        required=True,
        choices=list(MODE_REGISTRY.keys()),
        help="Pipeline execution mode",
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to scenario config file (YAML/JSON)",
    )
    parser.add_argument(
        "--validation",
        type=str,
        default="strict",
        choices=["strict", "relaxed", "none"],
        help="Schema validation mode (default: strict)",
    )
    parser.add_argument(
        "--export",
        type=str,
        default=None,
        help="Path to export results (JSON format)",
    )
    
    # Mode-specific arguments
    parser.add_argument(
        "--knobs",
        type=str,
        help="Path to sensitivity knobs config (for sensitivity mode)",
    )
    parser.add_argument(
        "--dists",
        type=str,
        help="Path to distributions config (for montecarlo mode)",
    )
    parser.add_argument(
        "--opt-config",
        type=str,
        help="Path to optimization config (for optimize mode)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Dispatch to mode handler
    mode = args.mode
    config_path = args.config
    validation_mode = args.validation
    export_path = args.export

    if mode == "base":
        return run_base_mode(config_path, validation_mode, export_path)
    elif mode == "sensitivity":
        if not args.knobs:
            logger.error("--knobs required for sensitivity mode")
            return 1
        return run_sensitivity_mode(config_path, args.knobs, export_path)
    elif mode == "montecarlo":
        if not args.dists:
            logger.error("--dists required for montecarlo mode")
            return 1
        return run_montecarlo_mode(config_path, args.dists, export_path)
    elif mode == "optimize":
        if not args.opt_config:
            logger.error("--opt-config required for optimize mode")
            return 1
        return run_optimize_mode(config_path, args.opt_config, export_path)
    else:
        logger.error("Unknown mode: %s", mode)
        return 1


if __name__ == "__main__":
    sys.exit(main())


