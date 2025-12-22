"""Hydra CLI wrapper for Monte Carlo analysis.

CANONICAL ENTRYPOINT: Use this instead of monte_carlo_v14.py (legacy).

This is a minimal Hydra stub. Local devs should wire it to the actual
Monte Carlo engine by replacing the TODO section in main().

Usage:
    python analytics/cli_monte_carlo_hydra.py \\
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
      "results": {{
        "project_irr": {{"mean": 0.14, "std": 0.02, "p10": 0.11, "p90": 0.17}},
        "min_dscr": {{"mean": 1.45, "std": 0.15, "p10": 1.25, "p90": 1.65}}
      }},
      "output_dir": "_out/monte_carlo"
    }}

Implementation Status:
    STUB - Needs engine wiring. TODO:
    1. Find actual Monte Carlo engine function
    2. Call engine with config + distributions + n_trials + seed
    3. Process results into JSON with statistics
    4. Write artifacts if requested

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
    Step 3 - Wrapper stub for local dev implementation

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 0.1.0 (Stub)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger(__name__)


@hydra.main(
    version_base="1.3",
    config_path="../conf",
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
        >>> python analytics/cli_monte_carlo_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     n_trials=10000 \\
        ...     seed=42
        >>> # Output: {{"status": "stub", ...}}
    """
    # Validate required config parameter
    config_path = cfg.get("config")
    if not config_path:
        error_result = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python analytics/cli_monte_carlo_hydra.py "
                "config=scenarios/example.yaml "
                "[n_trials=10000] "
                "[seed=42] "
                "[output_dir=_out/monte_carlo]"
            )
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)
    
    # Extract parameters from config
    output_dir = Path(str(cfg.get("output_dir", "_out/monte_carlo")))
    write_artifacts = bool(cfg.get("write_artifacts", True))
    n_trials = int(cfg.get("n_trials", 10000))
    seed = cfg.get("seed", 42)
    stochastic_params = OmegaConf.to_container(
        cfg.get("stochastic_params", {}), resolve=True
    )
    output_metrics = list(cfg.get("output_metrics", []))
    
    logger.info(
        "Monte Carlo analysis CLI (stub): config=%s, n_trials=%d, seed=%s, output_dir=%s",
        config_path, n_trials, seed, output_dir
    )
    
    # =========================================================================
    # TODO: Wire to actual Monte Carlo engine
    # =========================================================================
    # 
    # Local dev instructions:
    # 1. Find the actual Monte Carlo function:
    #    grep -rn "def.*monte_carlo" analytics/
    # 
    # 2. Import and call it, e.g.:
    #    from analytics.monte_carlo_v14_enhanced import run_monte_carlo
    #    results = run_monte_carlo(
    #        config_path=str(config_path),
    #        n_trials=n_trials,
    #        seed=seed,
    #        stochastic_params=stochastic_params,
    #        output_metrics=output_metrics
    #    )
    # 
    # 3. Replace the stub result below with actual results
    # 
    # 4. Test:
    #    python analytics/cli_monte_carlo_hydra.py \\
    #      config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
    #      n_trials=100 seed=42
    # 
    # =========================================================================
    
    # STUB RESULT (replace with actual engine output)
    result: dict[str, Any] = {
        "status": "stub",
        "message": "TODO: Wire to actual Monte Carlo engine",
        "config_path": str(config_path),
        "output_dir": str(output_dir),
        "n_trials": n_trials,
        "seed": seed,
        "stochastic_params_configured": (
            list(stochastic_params.keys()) 
            if isinstance(stochastic_params, dict) 
            else []
        ),
        "output_metrics_configured": output_metrics,
        "implementation_needed": [
            "1. Find Monte Carlo engine function (check monte_carlo_v14_enhanced.py)",
            "2. Call engine with config + n_trials + seed + distributions",
            "3. Process results: compute statistics (mean, std, percentiles)",
            "4. Write artifacts if write_artifacts=true",
        ]
    }
    
    # Optional artifact writing (when engine is wired)
    if write_artifacts and result.get("status") != "stub":
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write summary JSON
        summary_path = output_dir / "monte_carlo_summary.json"
        summary_path.write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8"
        )
        logger.info("Wrote Monte Carlo results to %s", summary_path)
    
    # Print JSON to stdout (CLI-03 compliance)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
