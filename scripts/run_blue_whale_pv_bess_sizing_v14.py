#!/usr/bin/env python3
"""Hydra CLI: seeded Monte Carlo sizing of the Blue Whale solar + BESS unit.

Reads ``conf/blue_whale_pv_bess_sizing.yaml`` (and through it PR 2's unit config, the cited
pricing config and the Blue Whale scenario) and prints one JSON object (CLI-01, CLI-03):
the run spec with its seed and its requested and effective evaluation counts
(``MRM-01``, ``TEST-03``), every grid point's fit, inverter match, base case and
distribution summary, the recommendation and the curtailment scenario. Per-trial values
are not written; ``output.summary_json`` writes the same summary to a file.

Usage::

    .venv/bin/python scripts/run_blue_whale_pv_bess_sizing_v14.py
    .venv/bin/python scripts/run_blue_whale_pv_bess_sizing_v14.py \\
        output.summary_json=docs/blue_whale/pv_bess_sizing_summary.json
    .venv/bin/python scripts/run_blue_whale_pv_bess_sizing_v14.py \\
        monte_carlo.n_trials=8 'grid.dc_ac_ratios=[1.2]' 'grid.bess_energy_mwh=[30.0]'

PR 4 sizes the separate solar + BESS project from its own config (schema
``blue_whale_solar_bess_project_sizing_v1``) under both readings of the 10 MW limit::

    .venv/bin/python scripts/run_blue_whale_pv_bess_sizing_v14.py \\
        --config-name blue_whale_solar_bess_project_sizing \\
        output.summary_json=docs/blue_whale/solar_bess_project_sizing_summary.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Mapping

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

from solar_resource.pv_bess_sizing import run_project_sizing, run_sizing, site_context

REPO_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(rel: str) -> Path:
    """Resolve a config path against the repository root."""
    p = Path(rel)
    return p if p.is_absolute() else REPO_ROOT / p


def _read(rel: str) -> Any:
    """Read a repository JSON or YAML file."""
    text = _repo_path(rel).read_text()
    return (
        json.loads(text)
        if rel.endswith((".json", ".geojson"))
        else yaml.safe_load(text)
    )


def _sha256(rel: str) -> str:
    return hashlib.sha256(_repo_path(rel).read_bytes()).hexdigest()


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


PROJECT_SCHEMA = "blue_whale_solar_bess_project_sizing_v1"


def run(
    cfg: Mapping[str, Any], config_name: str = "blue_whale_pv_bess_sizing"
) -> Dict[str, Any]:
    """Run the sizing and return the JSON-ready summary.

    A config with the PR 4 project schema runs
    :func:`~solar_resource.pv_bess_sizing.run_project_sizing`; any other runs PR 3's
    :func:`~solar_resource.pv_bess_sizing.run_sizing`.
    """
    started = time.time()
    unit_cfg = _read(str(cfg["unit_config"]))
    pricing_cfg = _read(str(cfg["pricing_config"]))
    scenario = _read(str(cfg["scenario"]))
    sizing_cfg = {k: v for k, v in cfg.items() if k != "hydra"}
    project = cfg.get("schema_version") == PROJECT_SCHEMA
    inputs = ["unit_config", "pricing_config", "scenario"]
    if project:
        inputs.append("regulatory_config")
        result = run_project_sizing(
            sizing_cfg,
            unit_cfg=unit_cfg,
            pricing_cfg=pricing_cfg,
            regulatory_cfg=_read(str(cfg["regulatory_config"])),
            scenario=scenario,
            site=site_context(unit_cfg, _read),
        )
    else:
        result = run_sizing(
            sizing_cfg,
            unit_cfg=unit_cfg,
            pricing_cfg=pricing_cfg,
            scenario=scenario,
            site=site_context(unit_cfg, _read),
        )
    spec = dict(result.spec)
    spec["inputs_sha256"] = {str(cfg[k]): _sha256(str(cfg[k])) for k in inputs}
    spec["sizing_config_sha256"] = hashlib.sha256(
        json.dumps(
            {
                k: v
                for k, v in sizing_cfg.items()
                if k not in ("output", "recommendation")
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    spec["git_sha"] = _git_head()
    spec["model_version"] = (REPO_ROOT / "VERSION").read_text().strip()
    spec["limitations"] = [
        "Placeholder site (PR 1) and placeholder O&M, financing and grid inputs.",
        "Ordinary-suite tests exercise reduced grids only; this run is not tail-adequacy, "
        "convergence, lender or bankability evidence (TEST-03).",
        "BESS priced per kWh on a 4 h basis at every duration.",
    ]
    if project:
        spec["limitations"] += [
            "The 10 MW limit's reading, and whether the turbine on the same lot counts "
            "against it, are open legal questions; both readings are reported.",
            "The BESS container footprint is a 6 h product's (power-bound at 4 h), so the "
            "land maximum is conservative for large batteries.",
        ]
    sens_key = "sensitivities" if project else "curtailment_scenario"
    out: Dict[str, Any] = {
        "config": f"conf/{config_name}.yaml",
        "statistics_convention": (
            "p50 median; p90 exceeded in 90% of trials (10th percentile); "
            "p10 exceeded in 10% (90th percentile)"
        ),
        "spec": spec,
        "recommendation": result.recommendation,
        "points": result.points,
        sens_key: result.curtailment,
    }
    text = json.dumps(out, sort_keys=True, allow_nan=False, indent=1)
    spec["result_sha256"] = hashlib.sha256(text.encode()).hexdigest()
    spec["runtime_s"] = round(time.time() - started, 1)
    target = cfg["output"]["summary_json"]
    if target:
        path = _repo_path(str(target))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(out, sort_keys=True, allow_nan=False, indent=1) + "\n"
        )
    return out


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="blue_whale_pv_bess_sizing"
)
def main(cfg: DictConfig) -> None:
    """Run the sizing and print one JSON object.

    Args:
        cfg: Hydra-composed config.

    Raises:
        TypeError: If the config does not resolve to a mapping.
    """
    logging.disable(logging.WARNING)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    from hydra.core.hydra_config import HydraConfig

    name = HydraConfig.get().job.config_name or "blue_whale_pv_bess_sizing"
    print(json.dumps(run(raw, config_name=name), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
