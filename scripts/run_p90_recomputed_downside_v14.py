#!/usr/bin/env python3
"""Hydra CLI: the recomputed P90 downside beside the sizing downside and the CFADS-ratio method (#1836).

For every scenario matching ``p90_downside.scenarios_glob`` that declares an
``expected_results`` P50/P90 pair, runs
:func:`analytics.finance.p90_recomputed_downside.recomputed_p90_downside` and prints one
JSON object (CLI-01, CLI-03). Each entry carries the SHA-256 of the scenario bytes it was
computed from, so a stale summary is detectable. The committed results are
``docs/finance/p90_recomputed_downside_summary.json``. No scenario input, sizing or KPI
changes.

Usage::

    .venv/bin/python scripts/run_p90_recomputed_downside_v14.py
    .venv/bin/python scripts/run_p90_recomputed_downside_v14.py \\
        p90_downside.summary_json=docs/finance/p90_recomputed_downside_summary.json
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.finance.p90_recomputed_downside import (
    LABEL,
    p90_energy_ratio,
    recomputed_p90_downside,
)
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[1]


def run(scenarios_glob: str) -> Dict[str, Any]:
    """The summary for every matching scenario with a P50/P90 pair."""
    scenarios: Dict[str, Any] = {}
    for path in sorted(REPO_ROOT.glob(scenarios_glob)):
        raw_bytes = path.read_bytes()
        try:
            config = load_scenario_config(path, verified_bytes=raw_bytes)
        except (
            Exception
        ):  # noqa: BLE001 - not a loadable scenario (e.g. multi-document)
            continue
        if p90_energy_ratio(config) is None:
            continue
        result = recomputed_p90_downside(config)
        result["scenario_sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        scenarios[path.relative_to(REPO_ROOT).as_posix()] = result
    return {
        "issue": 1836,
        "label": LABEL,
        "scenarios_glob": scenarios_glob,
        "scenarios": scenarios,
    }


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="p90_recomputed_downside"
)
def main(cfg: DictConfig) -> None:
    """Run the analysis, print one JSON object, and write it when asked.

    Args:
        cfg: Hydra config composed from ``conf/p90_recomputed_downside.yaml``.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.WARNING)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    block = raw["p90_downside"]
    result = run(str(block["scenarios_glob"]))
    text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    out = block.get("summary_json")
    if out:
        target = Path(str(out))
        if not target.is_absolute():
            target = REPO_ROOT / target
        target.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
