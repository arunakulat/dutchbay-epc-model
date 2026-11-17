#!/usr/bin/env python3
"""Hydra CLI: equipment-cost parity benchmark and cost-buildup check for any scenario.

Reads ``conf/equipment_parity.yaml`` (method inputs) and the scenario named by
``scenario=<path>``, and prints one JSON object (CLI-01, CLI-03). The site inputs come
from the scenario's ``equipment_cost_parity`` block (#1754); a scenario without it
prints ``"status": "not_applicable"`` with the reason. Does not modify any file.

Usage::

    .venv/bin/python scripts/run_equipment_parity_v14.py scenario=scenarios/<file>.yaml
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from analytics.wind.equipment_parity import run_equipment_parity_for_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_SCHEMA = "equipment_parity_method_v1"


def run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the method config, load the scenario and run the analysis."""
    if raw.get("schema_version") != METHOD_SCHEMA:
        raise ValueError(f"schema_version must be {METHOD_SCHEMA}")
    scenario_arg = raw.get("scenario")
    if not scenario_arg:
        raise ValueError("scenario=<path> is required")
    scenario_path = Path(str(scenario_arg))
    if not scenario_path.is_absolute():
        scenario_path = REPO_ROOT / scenario_path
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict):
        raise ValueError(f"scenario {scenario_arg} must be a YAML mapping")
    out = run_equipment_parity_for_scenario(
        scenario, raw["method"], REPO_ROOT, scenario_label=str(scenario_arg)
    )
    out["scenario"] = str(scenario_arg)
    return out


@hydra.main(version_base="1.3", config_path="../conf", config_name="equipment_parity")
def main(cfg: DictConfig) -> None:
    """Run the parity benchmark and cost-buildup checks and print JSON."""
    logging.disable(logging.WARNING)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    print(json.dumps(run(raw), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
