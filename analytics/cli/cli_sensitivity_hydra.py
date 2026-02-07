"""Hydra CLI wrapper for sensitivity analysis.

CANONICAL ENTRYPOINT: Use this instead of cli_sensitivity.py (legacy argparse).

Wired to analytics.sensitivity_runner.run_sensitivity_analysis() engine.

Usage:
    python analytics/cli/cli_sensitivity_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        output_dir=_out/sensitivity \\
        write_artifacts=true

Config:
    See conf/cli_sensitivity.yaml for all parameters:
    - config: Scenario YAML file path (required)
    - output_dir: Where to write results
    - shocks: Parameter variations (capex, tariff, capacity_factor)
    - metrics: KPIs to track (IRRs, DSCRs, etc.)

Output:
    Prints JSON to stdout:
    {{
      "status": "success",
      "baseline": {{...}},
      "sensitivity_results": [[{{"param": "capex", "shock": -0.1, ...}}],
      "output_dir": "_out/sensitivity"
    }}

GWTF:
    - R3: Hydra-only (no argparse)
    - CLI-03: JSON outputs
    - R24: Google-style docstrings

CASPER:
    - Deterministic: Config-driven sensitivity
    - Traceable: Logged shock parameters
    - Reproducible: Same config → same results

DSGCCCG:
    Dolphins Swim Gracefully Capturing Clean Current Groups
    Step 3B - Wired to sensitivity_runner engine

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (Wired)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

# Import engine function
from analytics.sensitivity_runner import run_sensitivity_analysis

logger = logging.getLogger(__name__)


@hydra.main(
    version_base="1.3",
    config_path="../../conf",
    config_name="cli_sensitivity",
)
def main(cfg: DictConfig) -> None:
    """Hydra entrypoint for sensitivity analysis.
    
    Args:
        cfg: Hydra configuration from conf/cli_sensitivity.yaml.
            Required:
                - config: Path to scenario YAML file
            Optional:
                - output_dir: Output directory (default: _out/sensitivity)
                - write_artifacts: Write files (default: true)
                - shocks: Parameter variations
                - metrics: KPIs to track
                
    Returns:
        None. Prints JSON to stdout, optionally writes artifacts.
        
    Raises:
        SystemExit: If config validation fails.
        
    Example:
        >>> python analytics/cli/cli_sensitivity_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     output_dir=_out/sensitivity
        >>> # Output: {{"status": "success", "sensitivity_results": [...]}}
    """
    # Validate required config parameter
    config_path = cfg.get("config")
    if not config_path:
        error_result = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python analytics/cli/cli_sensitivity_hydra.py "
                "config=scenarios/example.yaml "
                "[output_dir=_out/sensitivity] "
                "[write_artifacts=true]"
            )
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    # Extract parameters from config
    output_dir = Path(str(cfg.get("output_dir", "_out/sensitivity")))
    write_artifacts = bool(cfg.get("write_artifacts", True))
    shocks = OmegaConf.to_container(cfg.get("shocks", {}), resolve=True)
    metrics = list(cfg.get("metrics", []))

    # Default metric if not specified
    metric = metrics[0] if metrics else "project_irr"

    logger.info(
        "Sensitivity analysis: config=%s, metric=%s, output_dir=%s",
        config_path, metric, output_dir
    )

    try:
        # =====================================================================
        # WIRED TO ENGINE: analytics.sensitivity_runner.run_sensitivity_analysis
        # =====================================================================

        # Call sensitivity engine
        suite = run_sensitivity_analysis(
            str(config_path),
            metric=metric
        )

        # Convert dataclass to dict for JSON serialization
        result: dict[str, Any] = asdict(suite)

        # Add status and metadata
        result["status"] = "success"
        result["config_path"] = str(config_path)
        result["output_dir"] = str(output_dir)
        result["metric_analyzed"] = metric

        logger.info(
            "Sensitivity analysis complete: %d variations analyzed",
            len(result.get("variations", []))
        )

        # Optional artifact writing
        if write_artifacts:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write summary JSON
            summary_path = output_dir / "sensitivity_summary.json"
            summary_path.write_text(
                json.dumps(result, indent=2, sort_keys=True),
                encoding="utf-8"
            )
            logger.info("Wrote sensitivity results to %s", summary_path)

        # Print JSON to stdout (CLI-03 compliance)
        print(json.dumps(result, indent=2, sort_keys=True))

    except Exception as e:
        # Error handling with structured JSON output
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "config_path": str(config_path),
            "metric": metric
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Sensitivity analysis failed")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
