#!/usr/bin/env python3
"""Hydra CLI: Blue Whale equipment-cost parity benchmark and cost-buildup check.

Reads ``conf/blue_whale_equipment_parity.yaml`` and prints one JSON object
(CLI-01, CLI-03) summarizing the Mannar equipment-cost parity benchmark,
uncalibrated sensitivity cases, and the ``None``-safe road/marine cost-buildup
completeness checks. Does not modify any scenario file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.wind.blue_whale_equipment_parity import (
    compute_equipment_parity,
    evaluate_cost_buildup,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_equipment_parity",
)
def main(cfg: DictConfig) -> None:
    """Run the parity benchmark and cost-buildup checks and print JSON."""
    logging.disable(logging.WARNING)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    if raw.get("schema_version") != "blue_whale_equipment_parity_v1":
        raise ValueError("schema_version must be blue_whale_equipment_parity_v1")

    parity = compute_equipment_parity(raw, REPO_ROOT)
    packages = raw["cost_buildup_packages"]
    buildup = {
        "road": evaluate_cost_buildup(packages, "road"),
        "marine": evaluate_cost_buildup(packages, "marine"),
    }
    print(
        json.dumps(
            {"equipment_parity": parity, "cost_buildup": buildup},
            sort_keys=True,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
