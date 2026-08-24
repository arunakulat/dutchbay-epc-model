#!/usr/bin/env python3
"""Hydra CLI for fail-closed validation of a private F5-02 lender return."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import hydra
from hydra.utils import to_absolute_path
from omegaconf import DictConfig

from analysis_tools.f5_02_lender_return import (
    ValidationMode,
    validate_f5_02_lender_return,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "lender-input"
    / "DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml"
)


@hydra.main(version_base="1.3", config_path=None)
def main(cfg: DictConfig) -> None:
    """Validate a private return and print only a non-confidential JSON receipt."""

    if "input" not in cfg:
        raise ValueError(
            "Hydra override +input=/private/path/returned.yaml is required"
        )
    if "custodian_role" not in cfg or "receipt_timestamp" not in cfg:
        raise ValueError(
            "Hydra overrides +custodian_role=<role> and "
            "+receipt_timestamp=<RFC3339> are required"
        )
    mode = str(cfg.get("mode", "structural"))
    if mode not in {"template", "structural", "closure_candidate"}:
        raise ValueError("+mode must be template, structural, or closure_candidate")
    path = Path(to_absolute_path(str(cfg.input)))
    summary = validate_f5_02_lender_return(
        path,
        template_path=DEFAULT_TEMPLATE,
        mode=cast(ValidationMode, mode),
    )
    receipt = summary.to_public_receipt(
        custodian_role=str(cfg.custodian_role),
        receipt_timestamp=str(cfg.receipt_timestamp),
    )
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
