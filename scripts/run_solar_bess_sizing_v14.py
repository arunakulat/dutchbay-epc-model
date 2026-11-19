#!/usr/bin/env python3
"""Hydra CLI: seeded Monte Carlo sizing of a solar + BESS project, for any scenario.

Reads ``conf/solar_bess_sizing.yaml`` (method inputs: the Monte Carlo settings and the
objective) and the scenario named by ``scenario=<path>``, and prints one JSON object (CLI-01,
CLI-03). The site inputs come from the scenario's ``solar_storage_sizing`` block (#1754);
a scenario without the block prints ``"status": "not_applicable"`` with the reason. Every
trial is evaluated through :func:`analytics.evaluation_v14.evaluate_with_overrides`
(ARCH-04) on the scenario itself. ``output.summary_json`` also writes the concise summary.

Usage::

    .venv/bin/python scripts/run_solar_bess_sizing_v14.py scenario=scenarios/<file>.yaml
    .venv/bin/python scripts/run_solar_bess_sizing_v14.py scenario=scenarios/<file>.yaml \\
        method.monte_carlo.n_trials=8
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from solar_resource.pv_bess_sizing_runner import run_solar_bess_sizing_for_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_SCHEMA = "solar_bess_sizing_method_v1"


def run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the method config, load the scenario and run the sizing."""
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
    output = raw.get("output") or {}
    target = output.get("summary_json") if isinstance(output, dict) else None
    return run_solar_bess_sizing_for_scenario(
        scenario,
        method,
        scenario_label=str(scenario_arg),
        script=Path(__file__),
        summary_json=str(target) if target else None,
    )


@hydra.main(version_base="1.3", config_path="../conf", config_name="solar_bess_sizing")
def main(cfg: DictConfig) -> None:
    """Size the scenario's solar + BESS project and print one JSON object."""
    logging.disable(logging.WARNING)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    print(json.dumps(run(raw), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
