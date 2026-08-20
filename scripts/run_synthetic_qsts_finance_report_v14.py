#!/usr/bin/env python3
"""Hydra CLI for the governed #1074 synthetic process-provenance report."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from app.reports.synthetic_qsts_finance_report import (
    SyntheticFinanceReportConfig,
    cli_summary,
    generate_synthetic_qsts_finance_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="synthetic_qsts_finance_report",
)
def main(cfg: DictConfig) -> None:
    """Authenticate #1077/#1073, evaluate, render, verify, and publish #1074."""

    logging.disable(logging.INFO)
    raw: Any = OmegaConf.to_container(cfg, resolve=True)
    if not isinstance(raw, Mapping):
        raise TypeError("Resolved #1074 Hydra config must be a mapping.")
    config = SyntheticFinanceReportConfig.from_mapping(cast(Mapping[str, Any], raw))
    record, digest = generate_synthetic_qsts_finance_report(
        config=config, repo_root=REPO_ROOT
    )
    print(
        json.dumps(cli_summary(record, digest, config), sort_keys=True, allow_nan=False)
    )


if __name__ == "__main__":
    main()
