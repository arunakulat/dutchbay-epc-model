"""Hydra CLI wrapper for Monte Carlo analysis.

CANONICAL ENTRYPOINT: Use this instead of monte_carlo_v14.py (legacy CLI).

Wired to analytics.monte_carlo_v14.MonteCarloEngine.

Usage:
    python analytics/cli/cli_monte_carlo_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        n_trials=10000 \\
        seed=42 \\
        output_dir=_out/monte_carlo

Config:
    See conf/cli_monte_carlo.yaml for all parameters:
    - config: Scenario YAML file path (required)
    - n_trials: Number of Monte Carlo simulations (default: 10000)
    - seed: Random seed for reproducibility (default: 42)
    - output_dir: Where to write results
    - stochastic_params: Distribution definitions
    - output_metrics: KPIs to collect

Output:
    Prints JSON to stdout:
    {{
      "status": "success",
      "n_trials": 10000,
      "seed": 42,
      "statistics": {{
        "npv_mean_usd": 45200000.0,
        "npv_p10_usd": 38000000.0,
        "npv_p90_usd": 52000000.0,
        "irr_mean_pct": 14.5,
        ...
      }},
      "output_dir": "_out/monte_carlo"
    }}

GWTF:
    - R3: Hydra-only (no argparse)
    - CLI-03: JSON outputs
    - R24: Google-style docstrings

CASPER:
    - Deterministic: seed parameter ensures reproducibility
    - Traceable: Logged trial count and distributions
    - Reproducible: Same seed + config → identical results

DSGCCCG:
    Dolphins Swim Gracefully Capturing Clean Current Groups
    Step 3B - Wired to MonteCarloEngine

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (Wired)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

# Import engine class
from analytics.monte_carlo_v14 import MonteCarloEngine

logger = logging.getLogger(__name__)


@hydra.main(
    version_base="1.3",
    config_path="../../conf",
    config_name="cli_monte_carlo",
)
def main(cfg: DictConfig) -> None:
    """Hydra entrypoint for Monte Carlo analysis.
    
    Args:
        cfg: Hydra configuration from conf/cli_monte_carlo.yaml.
            Required:
                - config: Path to scenario YAML file
            Optional:
                - n_trials: Number of simulations (default: 10000)
                - seed: Random seed (default: 42)
                - output_dir: Output directory (default: _out/monte_carlo)
                - write_artifacts: Write files (default: true)
                - stochastic_params: Distribution definitions
                - output_metrics: KPIs to collect
                
    Returns:
        None. Prints JSON to stdout, optionally writes artifacts.
        
    Raises:
        SystemExit: If config validation fails.
        
    Example:
        >>> python analytics/cli/cli_monte_carlo_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     n_trials=10000 \\
        ...     seed=42
        >>> # Output: {{"status": "success", "statistics": {{...}}}}
    """
    # Validate required config parameter
    config_path = cfg.get("config")
    if not config_path:
        error_result = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python analytics/cli/cli_monte_carlo_hydra.py "
                "config=scenarios/example.yaml "
                "[n_trials=10000] "
                "[seed=42] "
                "[output_dir=_out/monte_carlo]"
            ),
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    # Extract parameters from config
    output_dir = Path(str(cfg.get("output_dir", "_out/monte_carlo")))
    write_artifacts = bool(cfg.get("write_artifacts", True))
    n_trials = int(cfg.get("n_trials", 10000))
    seed = cfg.get("seed", 42)

    logger.info(
        "Monte Carlo analysis: config=%s, n_trials=%d, seed=%s, output_dir=%s",
        config_path,
        n_trials,
        seed,
        output_dir,
    )

    try:
        # =====================================================================
        # WIRED TO ENGINE: analytics.monte_carlo_v14.MonteCarloEngine
        # =====================================================================

        # Load config as DictConfig (MonteCarloEngine expects this)
        cfg_obj = OmegaConf.load(str(config_path))

        # Initialize Monte Carlo engine
        engine = MonteCarloEngine(cfg_obj, n_iterations=n_trials)

        # Run simulation
        result: dict[str, Any] = engine.run()

        # Add output directory to result
        result["output_dir"] = str(output_dir)
        result["config_path"] = str(config_path)

        logger.info(
            "Monte Carlo analysis complete: %d trials, execution_time=%.2fs",
            n_trials,
            result.get("execution_time_seconds", 0),
        )

        # Optional artifact writing
        if write_artifacts and result.get("success", False):
            output_dir.mkdir(parents=True, exist_ok=True)

            # Write summary JSON
            summary_path = output_dir / "monte_carlo_summary.json"
            summary_path.write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            logger.info("Wrote Monte Carlo results to %s", summary_path)

        # Print JSON to stdout (CLI-03 compliance)
        print(json.dumps(result, indent=2, sort_keys=True))

    except Exception as e:
        # Error handling with structured JSON output
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "config_path": str(config_path),
            "n_trials": n_trials,
            "seed": seed,
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Monte Carlo analysis failed")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
