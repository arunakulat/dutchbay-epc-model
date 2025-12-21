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
    - scenario_result: Complete ScenarioResult with lender metrics
    - kpis: All calculated KPIs (IRR, NPV, DSCR, LLCR, PLCR)
    - annual_rows: Annual cashflow schedule
    - debt_result: Debt structuring with DSCR series
    - metrics: Pipeline execution metrics (if monitoring enabled)

GWTF Compliance:
- R3: Hydra-only (no argparse)
- CLI-01: Hydra-based architecture
- CLI-03: JSON-first outputs
- R24: Google-style docstrings
- CCCDIR: All config from YAML files

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 2.1.0 (Lender-Grade Pipeline)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
from omegaconf import DictConfig

# CRITICAL FIX: Import lender-grade pipeline (was: analytics.pipeline_v14)
from analytics.pipeline_v14_enhanced import run_v14_pipeline

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="run_full_pipeline_v14",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI entry point for complete lender-grade pipeline.
    
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
        
    Output Structure:
        {
          "status": "success",
          "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
          "validation_mode": "strict",
          "scenario_result": {
            "scenario_name": "dutchbay_lendercase_2025Q4",
            "project_irr": 0.145,
            "project_npv": 45000000.0,
            "min_dscr": 1.45,
            "dscr_series": [1.5, 1.6, 1.45, ...],
            "max_debt_usd": 150000000.0,
            ...
          },
          "kpis": {
            "project_irr": 0.145,
            "equity_irr": 0.185,
            "min_dscr": 1.45,
            "avg_dscr": 1.52,
            "llcr": 1.85,
            "plcr": 2.10,
            ...
          },
          "annual_rows": [
            {"year": 1, "cf_pre_debt": 15000000, "debt_service_total": 8000000, ...},
            ...
          ],
          "debt_result": {
            "min_dscr": 1.45,
            "dscr_series": [1.5, 1.6, ...],
            "balloon_remaining": 0.0,
            ...
          },
          "metrics": {
            "total_runtime_sec": 2.5,
            "annual_rows_count": 25,
            "kpis_count": 15,
            ...
          }
        }
        
    Example:
        >>> # From command line
        >>> python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
        >>> 
        >>> # Output includes lender-grade metrics:
        >>> {
        >>>   "status": "success",
        >>>   "kpis": {
        >>>     "project_irr": 0.145,
        >>>     "min_dscr": 1.45,
        >>>     "llcr": 1.85
        >>>   },
        >>>   "annual_rows": [...],
        >>>   "debt_result": {...}
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
        # Run the lender-grade pipeline (now correctly wired)
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
