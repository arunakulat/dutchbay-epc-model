#!/usr/bin/env python3
"""Hydra CLI for the governed #1073 synthetic AEP/QSTS output record."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.grid.synthetic_aep_qsts_output_records import (
    SyntheticQSTSOutputConfig,
    cli_summary,
    generate_synthetic_aep_qsts_output_records,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(version_base="1.3", config_path="../conf", config_name="synthetic_aep_qsts")
def main(cfg: DictConfig) -> None:
    """Authenticate #1077, execute 8,760 OpenDSS steps, and publish #1073."""

    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, Mapping):
        raise TypeError("Resolved #1073 Hydra config must be a mapping.")
    config = SyntheticQSTSOutputConfig.from_mapping(cast(Mapping[str, Any], raw))
    record, digest = generate_synthetic_aep_qsts_output_records(
        config=config,
        repo_root=REPO_ROOT,
    )
    print(
        json.dumps(cli_summary(record, digest, config), sort_keys=True, allow_nan=False)
    )


if __name__ == "__main__":
    main()
