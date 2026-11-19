#!/usr/bin/env python3
"""Hydra CLI: battery options for the separate 9.5 MW Blue Whale wind project (no solar).

Reads ``conf/blue_whale_wind_bess_options.yaml`` and prints one JSON object (CLI-01, CLI-03).
Every KPI comes from :func:`analytics.evaluation_v14.evaluate_with_overrides` on the wind
scenario (ARCH-04); :mod:`analytics.wind.wind_bess_options` builds each scenario and
:mod:`analytics.wind.wind_bess_options_runner` runs them (#1578 U2). The same evaluation runs
for any scenario that declares a ``storage_options`` block through
``scripts/run_wind_bess_options_v14.py scenario=<path>``; this single-site script stays, with
byte-identical output, until that runner replaces it.

One input comes from outside the repository: the public NASA POWER hourly reference at the
turbine point, content-checked against the pins in ``conf/blue_whale_met_mast_transfer.yaml``.
It only shapes the hour-by-hour charge and export headroom; the engine keeps the scenario's
own energy. Nothing private is read.

``DUTCHBAY_NASA_POWER_DIR`` must point outside the repository and hold one file per year in the
point's subdirectory, ``power_t2/wsd_<year>.json`` for 2015 to 2025, each as the NASA POWER
hourly point API returns it (GeoJSON with ``properties.parameter.WS50M``).

Usage::

    DUTCHBAY_NASA_POWER_DIR=/path/to/power \\
        .venv/bin/python scripts/run_blue_whale_wind_bess_options_v14.py \\
        output.summary_json=docs/blue_whale/wind_bess_options_summary.json
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, Mapping

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.wind import wind_bess_options as wbo
from analytics.wind import wind_bess_options_runner as runner

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "conf" / "blue_whale_wind_bess_options.yaml"
KPIS = ("project_npv", "equity_npv", "min_dscr", "project_irr", "equity_irr")
HOLD = (
    "SCREENING ONLY, not lender-grade. PUCSL's BESS tariff names solar PV only: every wind + "
    "BESS revenue basis here is a working assumption. The wind yield carries the met-mast "
    "HOLD (no measured Dutch Bay wind, no P90 for lenders); the hourly shape is a generic "
    "curve on a reanalysis; F-5 (no quarterly CFADS or intra-year DSCR figure supports a "
    "lender representation), #1110 and v15.6.1 stand. The 40 MW black-start battery is "
    "UNCONFIRMED (PUCSL discussions only, no document)."
)


# The evaluation moved to analytics.wind.wind_bess_options_runner (#1578 U2,
# REFACTOR-01). These names stay so existing callers and tests keep working.
json_clean = runner.json_clean
_repo_path = runner.repo_path
_nasa_dir = runner.nasa_dir
_kpis = runner.kpis
_rate = runner.rate_parts
_bisect = runner.bisect_root

#: The output level whose share of evening-window hours the profile checks report.
HIGH_OUTPUT_CHECK_MW = 9.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_profile(
    cfg: Mapping[str, Any], scenario: Mapping[str, Any]
) -> Dict[str, Any]:
    """Hourly turbine output (MW at the connection point) and the checks behind it.

    Raises:
        ValueError: If the committed yield does not reproduce the scenario's capacity factor.
    """
    return runner.build_profile(
        cfg, scenario, high_output_check_mw=HIGH_OUTPUT_CHECK_MW
    )


def run(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    """Evaluate every option under every reading and revenue basis; return the summary."""
    figures = runner.run_options(
        cfg,
        schema_version=wbo.SCHEMA_VERSION,
        # Looked up at call time, so a test may replace this module's build_profile.
        profile_builder=lambda c, s: build_profile(c, s),
    )
    return {
        "schema": "blue_whale_wind_bess_options_summary_v1",
        "hold": HOLD,
        "config_sha256": _sha256(CONFIG),
        "scenario_sha256": _sha256(_repo_path(cfg["scenario"])),
        "transfer_summary_sha256": _sha256(
            _repo_path(cfg["profile"]["transfer_summary"])
        ),
        "model_version": (REPO_ROOT / "VERSION").read_text().strip(),
    } | figures


def _refuse_overrides(raw: Mapping[str, Any]) -> None:
    """Refuse to write a summary from a config that differs from the committed file.

    The summary pins ``config_sha256``, the file's bytes. A command-line override other than
    ``output.*`` would change the figures under the same digest, so it is refused when a
    summary is written; printing to stdout stays open for exploration.

    Raises:
        ValueError: If any setting outside ``output`` differs from the config file.
    """
    committed: Any = OmegaConf.to_container(OmegaConf.load(CONFIG), resolve=True)
    if not isinstance(committed, dict):
        raise TypeError("expected the config file to resolve to a mapping")
    # Hydra consumes ``defaults`` and ``hydra``; neither reaches the composed config.
    skip = {"output", "defaults", "hydra"}
    ran = {k: v for k, v in raw.items() if k not in skip}
    pinned = {k: v for k, v in committed.items() if k not in skip}
    if ran != pinned:
        raise ValueError(
            "a summary is written only from the committed config; drop the overrides "
            "outside output.* or leave output.summary_json empty"
        )


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_wind_bess_options",
)
def main(cfg: DictConfig) -> None:
    """Run every option and print one JSON object."""
    logging.disable(logging.WARNING)
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    summary_path = raw["output"]["summary_json"]
    if summary_path:
        _refuse_overrides(raw)
    out = json_clean(run(copy.deepcopy(raw)))
    text = json.dumps(out, sort_keys=True, allow_nan=False)
    if summary_path:
        _repo_path(summary_path).write_text(
            json.dumps(out, sort_keys=True, indent=1, allow_nan=False) + "\n"
        )
    print(text)


if __name__ == "__main__":
    main()
