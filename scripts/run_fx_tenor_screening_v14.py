#!/usr/bin/env python3
"""Hydra CLI: dual-currency financing, FX and tenor-tail screening for any scenario.

Reads ``conf/fx_tenor_screening.yaml`` (method text) and the scenario named by
``scenario=<path>``, and prints one JSON object (CLI-01, CLI-03). The screening assumptions
come from the scenario's ``financing_screening`` block (#1754); capex, tariff, O&M, FX at
close, timeline, tax and the gearing cap come from the scenario itself. A scenario without the
block prints ``"status": "not_applicable"`` with the reason. Does not modify any file.

HOLD (F-5, #1110, v15.6.1): screening indicators only, never lender terms (#1629).

Usage::

    .venv/bin/python scripts/run_fx_tenor_screening_v14.py scenario=scenarios/<file>.yaml
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from analytics.finance.fx_tenor_screening import run_fx_tenor_screening_for_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]
METHOD_SCHEMA = "fx_tenor_screening_method_v1"
METHOD_KEYS = {"hold_caveat", "engine_path_status", "engine_path_note", "limitations"}


def run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the method config, load the scenario and run the screening."""
    if raw.get("schema_version") != METHOD_SCHEMA:
        raise ValueError(f"schema_version must be {METHOD_SCHEMA}")
    method = raw.get("method")
    if not isinstance(method, dict) or set(method) != METHOD_KEYS:
        raise ValueError(f"method must hold exactly {sorted(METHOD_KEYS)}")
    scenario_arg = raw.get("scenario")
    if not scenario_arg:
        raise ValueError("scenario=<path> is required")
    scenario_path = Path(str(scenario_arg))
    if not scenario_path.is_absolute():
        scenario_path = REPO_ROOT / scenario_path
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict):
        raise ValueError(f"scenario {scenario_arg} must be a YAML mapping")
    return run_fx_tenor_screening_for_scenario(
        scenario, method, scenario_label=str(scenario_arg)
    )


@hydra.main(version_base="1.3", config_path="../conf", config_name="fx_tenor_screening")
def main(cfg: DictConfig) -> None:
    """Run the screening and print JSON."""
    logging.disable(logging.WARNING)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    print(json.dumps(run(raw), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
