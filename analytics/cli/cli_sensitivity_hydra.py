"""Hydra CLI wrapper for sensitivity analysis.

CANONICAL ENTRYPOINT: Use this instead of cli_sensitivity.py (legacy argparse).

Wired to analytics.core.sensitivity_runner.run_sensitivity_analysis() engine.

Usage:
    python analytics/cli/cli_sensitivity_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        output_dir=_out/sensitivity \\
        write_artifacts=true

Config:
    See conf/cli_sensitivity.yaml for all parameters:
    - config: Scenario YAML file path (required)
    - output_dir: Where to write results
    - metrics: KPIs to track; the first is the tornado target metric

Output:
    Prints the result payload as JSON to stdout with sorted keys:
    ``dataclasses.asdict(SensitivitySuite)`` plus four CLI metadata keys
    (``status``, ``config_path``, ``output_dir``, ``metric_analyzed``).
    Top-level shape:
    {
      "analysis_timestamp": "2026-07-02T07:06:36+00:00",
      "base_config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
      "base_kpis": {"project_irr": 0.0268, ...},
      "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
      "metadata": {"flat_metric": false},
      "metric": "project_irr",
      "metric_analyzed": "project_irr",
      "output_dir": "_out/sensitivity",
      "scenario_name": "DutchBay Wind Farm",
      "status": "success",
      "tornado_results": [
        {"metric_name": "CAPEX", "base_metric": 0.0268, "impact_abs": ...,
         "label": "CAPEX", "metadata": {}, "shock_results": [...]}
      ]
    }
    On failure prints {"status": "error", "error": ..., "error_type": ...,
    "config_path": ..., "metric": ...} and exits 1. Note: Hydra job logging
    (INFO records) precedes the JSON on stdout under the default logging
    config; consumers should parse from the first "{" line.

GWTF:
    - R3: Hydra-only (no argparse)
    - CLI-03: JSON outputs
    - R24: Google-style docstrings

CASPER:
    - Deterministic: Config-driven sensitivity
    - Traceable: Logged shock parameters
    - Reproducible: Same config → same results

Author: Dutch Bay Wind Farm Team
Date: December 2025
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

import hydra
from omegaconf import DictConfig

# Import engine function
from analytics.core.sensitivity_runner import run_sensitivity_analysis
from analytics.output_paths import DEFAULT_SENSITIVITY_OUTPUT_ROOT, resolve_output_dir

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
                - metrics: KPIs to track (first is the tornado target metric)
                - run_scoped: Group artifacts under a per-run subdirectory of
                  output_dir (#735 slice-2; default false → path unchanged,
                  byte-identical).
                - run_id: Explicit run-scope subdirectory name; defaults to
                  analytics.output_paths.default_run_id() when run_scoped is set
                  and this is omitted. Ignored when run_scoped is false.
                
    Returns:
        None. Prints JSON to stdout, optionally writes artifacts.
        
    Raises:
        SystemExit: If config validation fails.
        
    Example:
        >>> python analytics/cli/cli_sensitivity_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     output_dir=_out/sensitivity
        >>> # Output: {"status": "success", "tornado_results": [...], ...}
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
            ),
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    # Extract parameters from config. #735 slice-2: route output_dir through the single-source
    # resolver so this CLI's artifacts co-scope with the rest of a run. At the default
    # (run_scoped=False) the resolver returns the configured root unchanged
    # (DEFAULT_SENSITIVITY_OUTPUT_ROOT == "_out/sensitivity"), so existing runs write to the same
    # path — byte-identical; opt-in run_scoped/run_id cfg knobs (default off/none) group the run
    # under a per-run subdirectory.
    output_dir = resolve_output_dir(
        cfg.get("output_dir", DEFAULT_SENSITIVITY_OUTPUT_ROOT),
        run_scoped=bool(cfg.get("run_scoped", False)),
        run_id=cfg.get("run_id", None),
    )
    write_artifacts = bool(cfg.get("write_artifacts", True))
    metrics = list(cfg.get("metrics", []))

    # Default metric if not specified
    metric = metrics[0] if metrics else "project_irr"

    logger.info(
        "Sensitivity analysis: config=%s, metric=%s, output_dir=%s",
        config_path,
        metric,
        output_dir,
    )

    try:
        # =====================================================================
        # WIRED TO ENGINE: analytics.core.sensitivity_runner.run_sensitivity_analysis
        # =====================================================================

        # Call sensitivity engine
        suite = run_sensitivity_analysis(str(config_path), metric=metric)

        # Convert dataclass to dict for JSON serialization
        result: dict[str, Any] = asdict(suite)

        # Add status and metadata
        result["status"] = "success"
        result["config_path"] = str(config_path)
        result["output_dir"] = str(output_dir)
        result["metric_analyzed"] = metric

        logger.info(
            "Sensitivity analysis complete: %d tornado(s) analyzed",
            len(result.get("tornado_results", [])),
        )

        # Optional artifact writing
        if write_artifacts:
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write summary JSON
            summary_path = output_dir / "sensitivity_summary.json"
            summary_path.write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
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
            "metric": metric,
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Sensitivity analysis failed")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
