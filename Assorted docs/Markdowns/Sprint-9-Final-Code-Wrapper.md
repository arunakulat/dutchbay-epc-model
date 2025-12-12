# Sprint 9 Final Integration: The Wrapper Pattern
## Revised Implementation for run_full_pipeline_v14.py

---

## CONTEXT: WHY THIS CHANGE?
You uploaded `pipeline_v14.py`, which already implements the core DCF logic (Phase 2). Instead of re-writing that logic, we will **import** it. This ensures that `run_full_pipeline_v14.py` is a true **Orchestrator** (Manager), delegating the heavy lifting to specialized workers (`pipeline_v14`, `sensitivity_v14`, `monte_carlo_v14`).

This reduces code size, eliminates duplication bugs, and adheres strictly to the **Single Responsibility Principle**.

---

## FILE: `run_full_pipeline_v14.py` (REVISED - Wrapper Pattern)

```python
"""
Full v14 Pipeline Orchestrator (Wrapper Implementation).

This module orchestrates the entire analytical stack by:
1. Delegating core DCF execution to `analytics.pipeline_v14`
2. Delegating sensitivity analysis to `analytics.sensitivity_v14`
3. Delegating Monte Carlo simulation to `analytics.monte_carlo_v14`
4. Merging all results into a unified `FullAnalysisResult` contract

Pattern: Wrapper / Facade
Ref: Sprint 9 Integration Strategy
"""

from __future__ import annotations

import logging
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

# === 1. The Core Worker (Existing) ===
from analytics.pipeline_v14 import run_pipeline as run_core_pipeline

# === 2. The Risk Workers (Sprint 9) ===
from analytics.sensitivity_v14 import build_sensitivity_suite
from analytics.monte_carlo_v14 import run_monte_carlo_suite

# === 3. The Helpers ===
from analytics.scenarioloader import load_scenario_config
from analytics.schema_guard import validate_config

logger = logging.getLogger(__name__)


@dataclass
class FullAnalysisResult:
    """Unified result contract for the full pipeline."""
    scenario_name: str
    timestamp: str

    # Core Results (from pipeline_v14)
    core: Dict[str, Any]

    # Analytics Results
    sensitivity: Optional[Dict[str, Any]] = None
    monte_carlo: Optional[Dict[str, Any]] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


def run_full_pipeline(
    config_path_or_dict: str | dict,
    overrides: dict[str, Any] | None = None,
    validation_mode: str = "strict"
) -> Dict[str, Any]:
    """
    Execute the full DutchBay analysis stack.

    Flow:
    Config -> Core DCF -> Sensitivity -> Monte Carlo -> Merge -> Result
    """
    start_time = datetime.now()
    logger.info(f"Starting analysis at {start_time.isoformat()}")

    # --- Phase 1: Configuration ---
    config = _resolve_config(config_path_or_dict, overrides)
    _validate_config(config, mode=validation_mode)

    # --- Phase 2: Core DCF Pipeline ---
    logger.info(">> Phase 2: Running Core DCF Pipeline...")
    # run_core_pipeline returns a ScenarioResult or dict. We convert to dict for storage.
    core_output = run_core_pipeline(config)

    # Extract key metrics for downstream risk engines
    # Note: Adapting to whatever shape pipeline_v14 returns (dict or object)
    if hasattr(core_output, "model_dump"):
        core_dict = core_output.model_dump() # Pydantic v2
    elif hasattr(core_output, "dict"):
        core_dict = core_output.dict()       # Pydantic v1
    elif hasattr(core_output, "to_dict"):
        core_dict = core_output.to_dict()    # Custom
    elif dataclass and hasattr(core_output, "__dataclass_fields__"):
        core_dict = asdict(core_output)      # Dataclass
    else:
        core_dict = dict(core_output)        # Raw dict

    base_irr = core_dict.get("metrics", {}).get("project_irr", 0.0)
    base_dscr = core_dict.get("metrics", {}).get("min_dscr", 0.0)

    # --- Phase 3: Sensitivity Analysis (Always Run) ---
    logger.info(">> Phase 3: Running Sensitivity Analysis...")
    sensitivity_suite = build_sensitivity_suite(
        config=config,
        base_project_irr=base_irr,
        base_min_dscr=base_dscr
    )
    # Convert Suite object to exportable dict
    sensitivity_dict = sensitivity_suite.to_dict() if hasattr(sensitivity_suite, "to_dict") else asdict(sensitivity_suite)

    # --- Phase 4: Monte Carlo (Conditional) ---
    mc_dict = None
    if config.get("analytics", {}).get("enable_monte_carlo", False):
        logger.info(">> Phase 4: Running Monte Carlo Simulation...")
        mc_suite = run_monte_carlo_suite(config)
        mc_dict = mc_suite.to_dict() if hasattr(mc_suite, "to_dict") else asdict(mc_suite)
    else:
        logger.info(">> Phase 4: Skipping Monte Carlo (disabled in config)")

    # --- Phase 5: Merging & Export ---
    logger.info(">> Phase 5: Aggregating Results...")

    full_result = FullAnalysisResult(
        scenario_name=config.get("project", {}).get("name", "Unknown"),
        timestamp=datetime.now().isoformat(),
        core=core_dict,
        sensitivity=sensitivity_dict,
        monte_carlo=mc_dict,
        metadata={
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "pipeline_version": "v14.0.1",
            "overrides_applied": bool(overrides)
        }
    )

    logger.info("Analysis complete successfully.")
    return asdict(full_result)


def _resolve_config(src: str | dict, overrides: dict | None) -> dict:
    """Load config from file or use provided dict, then apply overrides."""
    if isinstance(src, str):
        config = load_scenario_config(src)
    else:
        config = src.copy()

    if overrides:
        _deep_update(config, overrides)

    return config

def _validate_config(config: dict, mode: str):
    """Run schema validation."""
    errors = validate_config(config, mode=mode)
    if errors and mode == "strict":
        raise ValueError(f"Config validation failed: {errors}")
    elif errors:
        logger.warning(f"Config validation warnings: {errors}")

def _deep_update(base: dict, update: dict):
    """Recursive dict update."""
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_update(base[k], v)
        else:
            base[k] = v

# === CLI Entry Point ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Full DutchBay v14 Pipeline")
    parser.add_argument("config_file", help="Path to scenario YAML")
    parser.add_argument("--output", default="analysis_results.json", help="Output JSON path")
    parser.add_argument("--mc", action="store_true", help="Force enable Monte Carlo")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Construct overrides if flags set
    overrides = {}
    if args.mc:
        overrides["analytics"] = {"enable_monte_carlo": True}

    try:
        result = run_full_pipeline(args.config_file, overrides=overrides)

        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n✅ Success! Results saved to: {args.output}")
        print(f"   - Scenario: {result['scenario_name']}")
        print(f"   - IRR: {result['core']['metrics']['project_irr']:.2%}")
        if result['monte_carlo']:
            print(f"   - MC VaR (95%): {result['monte_carlo']['value_at_risk']:.2f} M USD")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")
        exit(1)
```

---

## IMPLEMENTATION NOTES

1.  **Imports:**
    *   `from analytics.pipeline_v14 import run_pipeline`: This is the key. We leverage your existing file.
    *   `from analytics.scenarioloader import load_scenario_config`: Using the alias we created to satisfy the linter.

2.  **Data Flow:**
    *   `Config` -> `pipeline_v14` -> `Core Result`
    *   `Core Result` (IRR/DSCR) -> `sensitivity_v14` -> `Sensitivity Result`
    *   `Config` -> `monte_carlo_v14` -> `MC Result`

3.  **Result Structure (`FullAnalysisResult`):**
    *   Top-level keys: `core`, `sensitivity`, `monte_carlo`, `metadata`.
    *   This is cleaner than a flat dict. It avoids key collisions (namespacing).

4.  **Flexibility:**
    *   Handles Pydantic models, Dataclasses, or Dicts returned by `pipeline_v14`. This makes it robust against changes in the core pipeline return type.

5.  **CLI:**
    *   Added a `--mc` flag to force Monte Carlo execution even if disabled in the YAML. This is great for ad-hoc testing.

---

## NEXT STEPS FOR YOU

1.  **Update `run_full_pipeline_v14.py`** with the code above.
2.  **Verify Imports:** Ensure `analytics.pipeline_v14` is importable (i.e., `__init__.py` exposes it or file is in path).
3.  **Run it:** `python run_full_pipeline_v14.py scenarios/example_a.yaml --mc`

This wrapper pattern is the "cleanest" way to integrate because it respects the boundaries of the modules you've already built. It is pure orchestration logic.
