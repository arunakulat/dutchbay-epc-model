#!/usr/bin/env python3
"""Hydra CLI: battery options for a wind project, for any scenario.

Reads ``conf/wind_bess_options.yaml`` (method inputs) and the scenario named by
``scenario=<path>``, and prints one JSON object (CLI-01, CLI-03). The site inputs come from
the scenario's ``storage_options`` block (#1754) and the wind tariff from the scenario
itself; a scenario without the block prints ``"status": "not_applicable"`` with the reason.
Every KPI comes from :func:`analytics.evaluation_v14.evaluate_with_overrides` (ARCH-04).
Does not modify any file.

A scenario with the block needs the public NASA POWER hourly reference its block names:
``DUTCHBAY_NASA_POWER_DIR`` (or the variable the reference config names) must point outside
the repository. Nothing private is read.

Usage::

    DUTCHBAY_NASA_POWER_DIR=/path/to/power \\
        .venv/bin/python scripts/run_wind_bess_options_v14.py scenario=scenarios/<file>.yaml
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from analytics.wind.wind_bess_options_runner import (
    json_clean,
    run_wind_bess_options_for_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_SCHEMA = "wind_bess_options_method_v1"


def run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the method config, load the scenario and run the analysis."""
    if raw.get("schema_version") != METHOD_SCHEMA:
        raise ValueError(f"schema_version must be {METHOD_SCHEMA}")
    method = raw.get("method")
    if not isinstance(method, dict):
        raise ValueError("method must be a mapping")
    scenario_arg = raw.get("scenario")
    if not scenario_arg:
        raise ValueError("scenario=<path> is required")
    scenario_path = Path(str(scenario_arg))
    if not scenario_path.is_absolute():
        scenario_path = REPO_ROOT / scenario_path
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict):
        raise ValueError(f"scenario {scenario_arg} must be a YAML mapping")
    return run_wind_bess_options_for_scenario(
        scenario, method, scenario_label=str(scenario_arg)
    )


@hydra.main(version_base="1.3", config_path="../conf", config_name="wind_bess_options")
def main(cfg: DictConfig) -> None:
    """Run every option for the scenario and print one JSON object."""
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    print(json.dumps(json_clean(run(raw)), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
