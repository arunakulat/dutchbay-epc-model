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
    
    Custom artifact location (CI):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            export_dir=_out/release_run \\
            write_artifacts=true

Output:
    JSON to stdout with:
    - status: 'success' or 'error'
    - scenario_result: Complete ScenarioResult with lender metrics
    - kpis: All calculated KPIs (IRR, NPV, DSCR, LLCR, PLCR)
    - annual_rows: Annual cashflow schedule
    - debt_result: Debt structuring with DSCR series
    - metrics: Pipeline execution metrics (if monitoring enabled)
    
    Optional file artifacts (if write_artifacts=true):
    - summary.json: Full pipeline result
    - kpis.json: KPI dictionary
    - debt_result.json: Debt structuring
    - annual_rows.csv: Cashflow schedule

GWTF Compliance:
- R3: Hydra-only (no argparse)
- CLI-01: Hydra-based architecture
- CLI-03: JSON-first outputs + optional files
- R24: Google-style docstrings
- CCCDIR: All config from YAML files

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 2.2.0 (Lender-Grade Pipeline + Artifact Writing)
"""

from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig

# CRITICAL FIX: Import lender-grade pipeline (was: analytics.pipeline_v14)
from analytics.pipeline_v14_enhanced import run_v14_pipeline

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


# ═════════════════════════════════════════════════════════════════════════════
# Artifact Writing Helpers (stdlib only - CI-safe)
# ═════════════════════════════════════════════════════════════════════════════


def _safe_mkdir(path: Path) -> None:
    """Create directory if it doesn't exist (mkdir -p behavior).
    
    Args:
        path: Directory path to create.
        
    Returns:
        None. Creates directory with parents if needed.
    """
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    """Write Python object as formatted JSON file.
    
    Args:
        path: File path for JSON output.
        payload: Python object to serialize (must be JSON-serializable).
        
    Returns:
        None. Writes file with indent=2, sorted keys.
    """
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8"
    )


def _write_annual_rows_csv(path: Path, annual_rows: Any) -> None:
    """Write annual cashflow rows as CSV (stdlib csv module - no pandas).
    
    Args:
        path: File path for CSV output.
        annual_rows: List of dicts representing annual cashflow rows.
        
    Returns:
        None. Writes CSV with header row derived from all dict keys.
        
    Notes:
        - Uses stdlib csv module for CI stability (no pandas dependency)
        - Handles heterogeneous row schemas (union of all keys)
        - Sorts fieldnames for deterministic column order
        - Skips non-dict entries silently
    """
    if not isinstance(annual_rows, list) or not annual_rows:
        return
    
    # Filter to dict entries only
    dict_rows = [row for row in annual_rows if isinstance(row, dict)]
    if not dict_rows:
        return
    
    # Union of keys across all rows for stable columns
    fieldnames: list[str] = sorted(
        {k for row in dict_rows for k in row.keys()}
    )
    
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in dict_rows:
            writer.writerow(row)


# ═════════════════════════════════════════════════════════════════════════════
# Hydra CLI Entry Point
# ═════════════════════════════════════════════════════════════════════════════


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
                - export_dir: Where to write artifacts (default: _out/run_full_pipeline_v14)
                - write_artifacts: Write files (default: true)
                
    Returns:
        None. Prints JSON result to stdout. Optionally writes artifacts.
        
    Raises:
        SystemExit: If config validation fails or errors occur.
        
    Output Structure:
        {{
          "status": "success",
          "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
          "validation_mode": "strict",
          "scenario_result": {{
            "scenario_name": "dutchbay_lendercase_2025Q4",
            "project_irr": 0.145,
            "project_npv": 45000000.0,
            "min_dscr": 1.45,
            "dscr_series": [1.5, 1.6, 1.45, ...],
            "max_debt_usd": 150000000.0,
            ...
          }},
          "kpis": {{
            "project_irr": 0.145,
            "equity_irr": 0.185,
            "min_dscr": 1.45,
            "avg_dscr": 1.52,
            "llcr": 1.85,
            "plcr": 2.10,
            ...
          }},
          "annual_rows": [
            {{"year": 1, "cf_pre_debt": 15000000, "debt_service_total": 8000000, ...}},
            ...
          ],
          "debt_result": {{
            "min_dscr": 1.45,
            "dscr_series": [1.5, 1.6, ...],
            "balloon_remaining": 0.0,
            ...
          }},
          "metrics": {{
            "total_runtime_sec": 2.5,
            "annual_rows_count": 25,
            "kpis_count": 15,
            ...
          }}
        }}
        
    Example:
        >>> # From command line
        >>> python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml
        >>> 
        >>> # Output includes lender-grade metrics:
        >>> {{
        >>>   "status": "success",
        >>>   "kpis": {{
        >>>     "project_irr": 0.145,
        >>>     "min_dscr": 1.45,
        >>>     "llcr": 1.85
        >>>   }},
        >>>   "annual_rows": [...],
        >>>   "debt_result": {{}}
        >>> }}
        >>> 
        >>> # Artifacts written to: _out/run_full_pipeline_v14/
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
                "config=scenarios/example_a.yaml "
                "[validation_mode=strict] "
                "[validation_modules=cashflow,debt] "
                "[export_dir=_out/release_run] "
                "[write_artifacts=true]"
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

        # Optional artifact writing (CI/release-run)
        write_artifacts = bool(cfg.get("write_artifacts", False))
        export_dir_raw = cfg.get("export_dir", "_out/run_full_pipeline_v14")

        if write_artifacts:
            export_dir = Path(str(export_dir_raw))
            _safe_mkdir(export_dir)

            # Always write summary.json (the whole result)
            _write_json(export_dir / "summary.json", result)
            logger.info("Wrote summary.json to %s", export_dir / "summary.json")

            # Optional component outputs if present
            if isinstance(result, dict):
                if "kpis" in result:
                    _write_json(export_dir / "kpis.json", result.get("kpis"))
                    logger.info("Wrote kpis.json to %s", export_dir / "kpis.json")
                
                if "debt_result" in result:
                    _write_json(export_dir / "debt_result.json", result.get("debt_result"))
                    logger.info("Wrote debt_result.json to %s", export_dir / "debt_result.json")
                
                if "annual_rows" in result:
                    _write_annual_rows_csv(export_dir / "annual_rows.csv", result.get("annual_rows"))
                    logger.info("Wrote annual_rows.csv to %s", export_dir / "annual_rows.csv")

            logger.info("All artifacts written to: %s", str(export_dir.resolve()))

        # Emit JSON for CI/tooling (CLI-03 compliance)
        # Note: This is always emitted, even when write_artifacts=true
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
