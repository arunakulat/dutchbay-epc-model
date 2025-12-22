"""Hydra CLI wrapper for sensitivity analysis.

CANONICAL ENTRYPOINT: Use this instead of cli_sensitivity.py (legacy argparse).

This is a minimal Hydra stub. Local devs should wire it to the actual
sensitivity engine by replacing the TODO section in main().

Usage:
    python analytics/cli_sensitivity_hydra.py \\
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
      "sensitivity_results": [{{"param": "capex", "shock": -0.1, ...}}],
      "output_dir": "_out/sensitivity"
    }}

Implementation Status:
    STUB - Needs engine wiring. TODO:
    1. Find actual sensitivity engine function
    2. Call engine with config + shocks
    3. Process results into JSON structure
    4. Write artifacts if requested

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
        >>> python analytics/cli_sensitivity_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     output_dir=_out/sensitivity
        >>> # Output: {{"status": "stub", ...}}
    """
    # Validate required config parameter
    config_path = cfg.get("config")
    if not config_path:
        error_result = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python analytics/cli_sensitivity_hydra.py "
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
    
    logger.info(
        "Sensitivity analysis CLI (stub): config=%s, output_dir=%s",
        config_path, output_dir
    )
    
    # =========================================================================
    # TODO: Wire to actual sensitivity engine
    # =========================================================================
    # 
    # Local dev instructions:
    # 1. Find the actual sensitivity analysis function:
    #    grep -rn "def.*sensitivity" analytics/
    # 
    # 2. Import and call it, e.g.:
    #    from analytics.sensitivity_engine import run_sensitivity
    #    results = run_sensitivity(
    #        config_path=str(config_path),
    #        shocks=shocks,
    #        metrics=metrics
    #    )
    # 
    # 3. Replace the stub result below with actual results
    # 
    # 4. Test:
    #    python analytics/cli_sensitivity_hydra.py \\
    #      config=scenarios/dutchbay_lendercase_2025Q4.yaml
    # 
    # =========================================================================
    
    # STUB RESULT (replace with actual engine output)
    result: dict[str, Any] = {
        "status": "stub",
        "message": "TODO: Wire to actual sensitivity engine",
        "config_path": str(config_path),
        "output_dir": str(output_dir),
        "shocks_configured": list(shocks.keys()) if isinstance(shocks, dict) else [],
        "metrics_configured": metrics,
        "implementation_needed": [
            "1. Find sensitivity engine function",
            "2. Call engine with config + shocks",
            "3. Process results into structured JSON",
            "4. Write artifacts if write_artifacts=true",
        ]
    }
    
    # Optional artifact writing (when engine is wired)
    if write_artifacts and result.get("status") != "stub":
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


if __name__ == "__main__":
    main()
