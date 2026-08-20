#!/usr/bin/env python3
"""Hydra CLI for the governed #1077 synthetic QSTS input-record handoff."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.grid.synthetic_input_records import (
    SyntheticInputRecordsConfig,
    cli_summary,
    generate_and_ingress_synthetic_input_records,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="synthetic_input_records",
)
def main(cfg: DictConfig) -> None:
    """Generate, ingress, and publish one authenticated input-only handoff."""

    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, dict):
        raise TypeError(
            f"Expected Hydra config to resolve to a mapping, got {type(raw).__name__}."
        )
    handoff_raw = raw.get("handoff")
    if not isinstance(handoff_raw, Mapping):
        raise TypeError("Resolved config requires a handoff mapping.")
    handoff_config = SyntheticInputRecordsConfig.from_mapping(
        cast(Mapping[str, Any], handoff_raw)
    )
    generator_config_path = REPO_ROOT.joinpath(
        *handoff_config.generator_config_source.split("/")
    )
    if generator_config_path.is_symlink() or not generator_config_path.is_file():
        raise FileNotFoundError(
            "The governed synthetic generator configuration is absent or a symlink."
        )
    package_raw = OmegaConf.to_container(
        OmegaConf.load(generator_config_path), resolve=True
    )
    if not isinstance(package_raw, Mapping):
        raise TypeError("Generator configuration must resolve to a mapping.")
    record, digest = generate_and_ingress_synthetic_input_records(
        generator_config_raw=cast(Mapping[str, Any], package_raw),
        handoff_config=handoff_config,
        repo_root=REPO_ROOT,
    )
    print(
        json.dumps(
            cli_summary(record, digest, handoff_config),
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
