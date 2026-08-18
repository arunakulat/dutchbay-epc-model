#!/usr/bin/env python3
"""Hydra CLI for the controlled Issue #923 synthetic feeder placeholder."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.grid.synthetic_feeder_placeholder import (
    SyntheticFeederPlaceholderConfig,
    cli_summary,
    generate_synthetic_feeder_placeholder,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="synthetic_feeder_placeholder",
)
def main(cfg: DictConfig) -> None:
    """Generate one governed package and print one concise JSON receipt.

    Args:
        cfg: Hydra-composed synthetic feeder generator configuration.

    Raises:
        TypeError: If Hydra does not resolve the configuration to a mapping.
        ValueError: If a controlled configuration or package invariant fails.
    """

    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError(
            f"Expected the Hydra config to resolve to a mapping, got {type(raw).__name__}."
        )
    config = SyntheticFeederPlaceholderConfig.from_mapping(raw)
    package = generate_synthetic_feeder_placeholder(config, repo_root=REPO_ROOT)
    print(json.dumps(cli_summary(package, config), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
