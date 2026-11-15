#!/usr/bin/env python3
"""Hydra CLI: Blue Whale dual-currency financing and FX screening analysis.

Reads ``conf/blue_whale_fx_tenor_screening.yaml`` and governed basecase inputs
from ``scenarios/dutchbay_basecase_2025Q4.yaml``, and prints one JSON object
(CLI-01, CLI-03) summarizing the FX CAGR metrics, 14-turbine screening indicators,
tenor-tail compliance, and fixed-debt FX stress test grid.

HOLD (F-5, #1110, v15.6.1): Standalone screening utility complementary to
``analytics.evaluation_v14`` and PR #1678. The core v14 engine carries an FX
override to the USD OPEX share's own FX path (BW-5 / L-12 D-2); this utility does
not call it. Does NOT modify any
scenario YAML or execute/represent lender commitments.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.finance.blue_whale_fx_tenor_screening import run_comprehensive_screening


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_fx_tenor_screening",
)
def main(cfg: DictConfig) -> None:
    """Run the dual-currency FX and debt screening analysis and emit JSON on stdout."""
    logging.disable(logging.WARNING)
    container = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(container, dict):
        raise TypeError("expected the Hydra config to resolve to a mapping")
    raw: Dict[str, Any] = {str(k): v for k, v in container.items()}
    if raw.get("schema_version") != "blue_whale_fx_tenor_screening_v1":
        raise ValueError("schema_version must be blue_whale_fx_tenor_screening_v1")

    result = run_comprehensive_screening(raw)
    sys.stdout.write(
        json.dumps(result, sort_keys=True, allow_nan=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
