#!/usr/bin/env python3
"""Hydra CLI: run one site analysis for any scenario, and optionally commit its summary.

Reads ``conf/site_analysis_run.yaml`` and runs ``analysis=<block>`` for ``scenario=<path>``
through :func:`analytics.site_analysis_runs.run_site_analysis` (#1824). The result carries the
code and config digests it ran with. With ``write=true`` it is written to
``docs/site_analyses/<scenario file stem>/<block>.json``, where a report reads it and marks it
stale once either digest no longer matches the tree; otherwise it is printed as one JSON
object (CLI-01, CLI-03).

The wind battery options read a public reference held outside the repository; see
``scripts/run_wind_bess_options_v14.py`` for the variable it needs.

Usage::

    .venv/bin/python scripts/run_site_analysis_v14.py \\
        analysis=storage_options scenario=scenarios/<file>.yaml write=true
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

from analytics.site_analysis_runs import (
    SITE_ANALYSIS_RUNS,
    json_ready,
    run_site_analysis,
    summary_path,
    write_summary,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the arguments, run the analysis and write or return its result."""
    block = raw.get("analysis")
    if block not in SITE_ANALYSIS_RUNS:
        raise ValueError(f"analysis must be one of {sorted(SITE_ANALYSIS_RUNS)}")
    scenario_arg = raw.get("scenario")
    if not scenario_arg:
        raise ValueError("scenario=<path> is required")
    scenario_path = Path(str(scenario_arg))
    if not scenario_path.is_absolute():
        scenario_path = REPO_ROOT / scenario_path
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(scenario, dict):
        raise ValueError(f"scenario {scenario_arg} must be a YAML mapping")
    result = run_site_analysis(str(block), scenario, scenario_path)
    if raw.get("write") is True:
        if "provenance" not in result:
            raise ValueError(
                f"{scenario_arg} declares no {block} block; there is no summary to write"
            )
        target = summary_path(scenario_path, str(block))
        write_summary(result, target)
        return {"written": target.relative_to(REPO_ROOT).as_posix()}
    return result


@hydra.main(version_base="1.3", config_path="../conf", config_name="site_analysis_run")
def main(cfg: DictConfig) -> None:
    """Run the analysis and print its result, or the path it was written to."""
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    print(json.dumps(json_ready(run(raw)), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
