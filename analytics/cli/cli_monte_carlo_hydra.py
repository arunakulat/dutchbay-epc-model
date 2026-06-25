"""Hydra CLI wrapper for Monte Carlo analysis.

CANONICAL ENTRYPOINT: Use this instead of monte_carlo_v14.py (legacy CLI).

Wired to analytics.mc.engine.run_monte_carlo_analysis (the canonical functional
entrypoint over analytics.mc.engine.MonteCarloEngine).

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
    - write_artifacts: Write the result JSON to output_dir (default: true)

    The stochastic distributions are read from the scenario's
    ``monte_carlo.parameters`` block by analytics.mc.engine — NOT from this CLI
    config — so there is no stochastic_params/output_metrics knob here.

Output:
    Prints JSON to stdout (raw per-trial arrays are written only to the
    artifact file, not stdout):
    {{
      "status": "success",
      "n_trials": 10000,
      "seed": 42,
      "execution_time_seconds": 4.21,
      "summary": {{
        "project_npv": {{
          "mean": 45200000.0,
          "std": 6100000.0,
          "min": 31000000.0,
          "max": 58000000.0,
          "percentiles": {{"5": ..., "10": 38000000.0, "90": 52000000.0, "95": ...}}
        }},
        "project_irr": {{"mean": 0.145, ...}},
        "dscr_min": {{"mean": 1.42, ...}}
      }},
      "percentiles": {{"10": {{"project_npv": 38000000.0, ...}}, ...}},
      "metadata": {{"seed": 42, "sampler": "lhs", "n_trials": 10000, ...}},
      "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
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
Version: 1.1.0 (Wired to canonical analytics.mc.engine API)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Mapping, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.contracts_v14 import MonteCarloResult

# Canonical Monte Carlo engine (analytics.monte_carlo_v14 is a deprecated shim).
from analytics.mc.engine import run_monte_carlo_analysis

logger = logging.getLogger(__name__)


def _derive_run_status(
    iterations: int, failed_iterations: int, toy_fallback_count: int
) -> str:
    """Classify an MC run for the CLI payload instead of hardcoding "success".

    - ``degenerate``: every trial fell back to TOY KPIs (no real evaluation succeeded) —
      the reported metrics are fabricated and must not read as a clean success.
    - ``degraded``: some trials failed real evaluation or fell back to toy.
    - ``success``: all trials evaluated for real.
    """
    if iterations > 0 and toy_fallback_count >= iterations:
        return "degenerate"
    if toy_fallback_count > 0 or failed_iterations > 0:
        return "degraded"
    return "success"


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
            Stochastic distributions come from the scenario's
            monte_carlo.parameters block (analytics.mc.engine), not this CLI.

    Returns:
        None. Prints JSON to stdout, optionally writes artifacts.

    Raises:
        SystemExit: If config validation fails or the simulation errors.

    Example:
        >>> python analytics/cli/cli_monte_carlo_hydra.py \\
        ...     config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        ...     n_trials=10000 \\
        ...     seed=42
        >>> # Output: {{"status": "success", "summary": {{...}}}}
    """
    # Validate required config parameter
    config_path = cfg.get("config")
    if not config_path:
        error_result: dict[str, Any] = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python analytics/cli/cli_monte_carlo_hydra.py "
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
    seed = int(cfg.get("seed", 42))

    logger.info(
        "Monte Carlo analysis: config=%s, n_trials=%d, seed=%d, output_dir=%s",
        config_path, n_trials, seed, output_dir
    )

    try:
        # =====================================================================
        # WIRED TO ENGINE: analytics.mc.engine.run_monte_carlo_analysis
        # =====================================================================

        # Load scenario as a DictConfig. MonteCarloEngine deep-converts this to
        # a plain dict internally, so the OmegaConf object can be passed as-is.
        cfg_obj = OmegaConf.load(str(config_path))
        if not isinstance(cfg_obj, DictConfig):
            raise TypeError(
                f"Config root must be a mapping (DictConfig), got {type(cfg_obj).__name__}"
            )

        # Run simulation via the canonical functional entrypoint. n_trials and
        # seed are passed through to MonteCarloEngine(seed=...).run(n_trials=...).
        start = time.perf_counter()
        result: MonteCarloResult = run_monte_carlo_analysis(
            base_config=cast("Mapping[str, Any]", cfg_obj),
            n_trials=n_trials,
            seed=seed,
        )
        execution_time_seconds = time.perf_counter() - start

        # MonteCarloResult is a frozen dataclass (analytics.contracts_v14), not a
        # dict: consume its attributes rather than subscripting. There is no
        # execution_time_seconds field on the result, so the CLI measures it.
        #
        # Derive status from the actual run instead of hardcoding "success": a run where
        # every trial fell back to TOY KPIs (real evaluation failed on all of them) was
        # previously reported as success with fabricated metrics. toy_fallback_count ==
        # iterations means NO real evaluation succeeded -> degenerate; any toy fallback or
        # failed trial -> degraded; otherwise -> success.
        iterations = result.iterations or n_trials
        toy_fallback_count = int((result.metadata or {}).get("toy_fallback_count", 0) or 0)
        success_rate_pct = result.success_rate()
        status = _derive_run_status(
            iterations, result.failed_iterations, toy_fallback_count
        )

        payload: dict[str, Any] = {
            "status": status,
            "success_rate_pct": round(success_rate_pct, 2),
            "failed_iterations": result.failed_iterations,
            "toy_fallback_count": toy_fallback_count,
            "n_trials": n_trials,
            "seed": seed,
            "execution_time_seconds": round(execution_time_seconds, 4),
            "summary": result.summary,
            "percentiles": result.percentiles,
            "metadata": result.metadata,
            "config_path": str(config_path),
            "output_dir": str(output_dir),
        }

        if status != "success":
            logger.warning(
                "Monte Carlo run is %s: %d/%d trials fell back to toy KPIs, %d failed "
                "(success_rate=%.1f%%) — reported metrics are NOT fully real.",
                status,
                toy_fallback_count,
                iterations,
                result.failed_iterations,
                success_rate_pct,
            )

        logger.info(
            "Monte Carlo analysis complete: %d trials, execution_time=%.2fs",
            n_trials,
            execution_time_seconds,
        )

        # Optional artifact writing. Reaching this point means the run
        # succeeded (a failure would have raised and been caught below). The
        # artifact carries the full result, including raw per-trial arrays for
        # lender-grade downstream analytics (breach probability, downside).
        if write_artifacts:
            output_dir.mkdir(parents=True, exist_ok=True)

            artifact = dict(payload)
            artifact["trials"] = result.trials

            summary_path = output_dir / "monte_carlo_summary.json"
            summary_path.write_text(
                json.dumps(artifact, indent=2, sort_keys=True),
                encoding="utf-8"
            )
            logger.info("Wrote Monte Carlo results to %s", summary_path)

        # Print JSON to stdout (CLI-03 compliance). Raw trial arrays are
        # intentionally omitted from stdout to keep it consumable by CI tooling.
        print(json.dumps(payload, indent=2, sort_keys=True))

    except Exception as e:
        # Error handling with structured JSON output
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "config_path": str(config_path),
            "n_trials": n_trials,
            "seed": seed
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Monte Carlo analysis failed")
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
