"""Hydra CLI for Complete Wind-to-Finance Pipeline.

Entrypoint for running the complete DutchBay wind farm assessment and
financial analysis. Integrates:
- Wind resource assessment (ERA5 data)
- Statistical analysis (Weibull, variability)
- Energy production calculations
- Financial modeling (cashflow, IRR, NPV)
- Monte Carlo uncertainty analysis

Usage:
    Basic (uses default validation):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml
    
    With explicit validation options:
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            validation_mode=strict \\
            validation_modules=cashflow,debt
    
    Skip validation (faster, for debugging):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            validation_mode=off

Output:
    JSON to stdout with:
    - status: 'success' or 'error'
    - wind_assessment: Complete wind resource analysis
    - aep_p50/p75/p90_mwh: Net AEP at different confidence levels
    - revenue_annual_p75_usd: Annual revenue (lender base case)
    - capacity_factor: Net capacity factor
    - output_files: Paths to detailed reports

GWTF Compliance:
- R3: Hydra-only (no argparse)
- CLI-01: Hydra-based architecture
- CLI-03: JSON-first outputs
- R24: Google-style docstrings
- CCCDIR: All config from YAML files

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 2.0.0 (Integrated wind_resource)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
from omegaconf import DictConfig

from analytics.pipeline_v14 import run_v14_pipeline

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="run_full_pipeline_v14",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI entry point for complete pipeline.
    
    Args:
        cfg: Hydra configuration from conf/run_full_pipeline_v14.yaml.
            Required fields:
                - config: Path to scenario YAML file
            Optional fields:
                - validation_mode: 'strict' or 'off' (default: 'strict')
                - validation_modules: Comma-separated list or array
                
    Returns:
        None. Prints JSON result to stdout.
        
    Raises:
        SystemExit: If config validation fails or errors occur.
        
    Example:
        >>> # From command line
        >>> python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
        >>> 
        >>> # Output (JSON):
        >>> {
        >>>   "status": "success",
        >>>   "aep_p75_mwh": 286300,
        >>>   "revenue_annual_p75_usd": 19430000,
        >>>   "capacity_factor_net_p75": 33.6
        >>> }
    """
    # Undo Hydra's job-chdir so relative scenario paths still work from repo root.
    os.chdir(_ORIG_CWD)

    # Validate required config parameter
    config = cfg.get("config")
    if not config:
        error_result = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python run_full_pipeline_v14.py "
                "config=scenarios/example_a.yaml [validation_mode=strict] "
                "[validation_modules=cashflow,debt]"
            )
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    # Extract validation parameters
    validation_mode = cfg.get("validation_mode", "strict")

    # Parse validation_modules (can be string or list)
    modules_raw = cfg.get("validation_modules", None)
    if isinstance(modules_raw, str):
        validation_modules = [m.strip() for m in modules_raw.split(",") if m.strip()]
    elif modules_raw is None:
        validation_modules = None
    else:
        validation_modules = list(modules_raw)

    try:
        # Run the integrated pipeline
        result = run_v14_pipeline(
            config=str(config),
            validation_mode=str(validation_mode),
            validation_modules=validation_modules,
        )

        # Emit JSON for CI/tooling (CLI-03 compliance)
        print(json.dumps(result, indent=2, sort_keys=True))
        
    except Exception as e:
        # Error handling with structured JSON output
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "config": str(config)
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Pipeline execution failed")
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli()
