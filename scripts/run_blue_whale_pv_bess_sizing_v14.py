#!/usr/bin/env python3
"""Hydra CLI: seeded Monte Carlo sizing of the Blue Whale solar + BESS unit.

Reads ``conf/blue_whale_pv_bess_sizing.yaml`` (and through it PR 2's unit config, the cited
pricing config and the Blue Whale scenario) and prints one JSON object (CLI-01, CLI-03):
the run spec with its seed and its requested and effective evaluation counts
(``MRM-01``, ``TEST-03``), every grid point's fit, inverter match, base case and
distribution summary, the recommendation and the curtailment scenario. Per-trial values
are not written; ``output.summary_json`` writes the same summary to a file. The spec names
the code that ran by content (``code_sha256``) as well as by commit (``git_sha``), because a
squash merge leaves the run's commit outside ``main`` (MRM-02).

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

Since 2026-11-07 that run also chooses the battery (the owner's 5 MW / 20 MWh of PR 7 is
no longer fixed, and its child config is retired); its ``sensitivities`` block adds the
one-at-a-time cases and the break-even values to the summary.

The run itself lives in :mod:`solar_resource.pv_bess_sizing_runner` (#1578 U3); this script
passes it this site's config label and stated limitations. Any scenario with a
``solar_storage_sizing`` block runs the project sizing through
``scripts/run_solar_bess_sizing_v14.py``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Mapping

import hydra
from omegaconf import DictConfig, OmegaConf

from solar_resource import pv_bess_sizing_runner as _runner
from solar_resource.pv_bess_sizing_runner import (  # noqa: F401 - re-exported
    GRID_COLUMNS,
    REPO_ROOT,
    code_sha256,
    concise_project_summary,
    loaded_repo_modules,
)

#: The stated limitations of this site's runs (every run, then a project run only).
LIMITATIONS = (
    "Placeholder site (PR 1) and placeholder O&M, financing and grid inputs.",
    "Ordinary-suite tests exercise reduced grids only; this run is not tail-adequacy, "
    "convergence, lender or bankability evidence (TEST-03).",
    "BESS priced per kWh on a 4 h basis at every duration.",
)
PROJECT_LIMITATIONS = (
    "The 10 MW limit's reading, and whether the turbine on the same lot counts "
    "against it, are open legal questions; both readings are reported.",
    "The BESS container footprint is a 6 h product's (power-bound at 4 h), so the "
    "land maximum is conservative for large batteries.",
)


def run(
    cfg: Mapping[str, Any], config_name: str = "blue_whale_pv_bess_sizing"
) -> Dict[str, Any]:
    """Run the sizing and return the JSON-ready summary.

    A config with the project schema runs
    :func:`~solar_resource.pv_bess_sizing.run_project_sizing`; any other runs PR 3's
    :func:`~solar_resource.pv_bess_sizing.run_sizing`
    (:func:`solar_resource.pv_bess_sizing_runner.run`).
    """
    return _runner.run(
        cfg,
        config_label=f"conf/{config_name}.yaml",
        script=Path(__file__),
        limitations=LIMITATIONS,
        project_limitations=PROJECT_LIMITATIONS,
    )


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
