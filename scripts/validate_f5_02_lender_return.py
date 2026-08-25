#!/usr/bin/env python3
"""Hydra CLI for fail-closed validation of a private F5-02 lender return."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Never, cast

import hydra
from omegaconf import DictConfig

from analysis_tools.f5_02_lender_return import (
    F502LenderReturnError,
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
RETURN_PATH_ENV = "DUTCHBAY_F5_02_RETURN_PATH"
INGRESS_MANIFEST_PATH_ENV = "DUTCHBAY_F5_02_INGRESS_MANIFEST_PATH"
CUSTODIAN_ROLE_ENV = "DUTCHBAY_F5_02_CUSTODIAN_ROLE"
RECEIPT_TIMESTAMP_ENV = "DUTCHBAY_F5_02_RECEIPT_TIMESTAMP"
REJECTED_RECEIPT = {"error": "F5_02_RETURN_REJECTED"}
ALLOWED_CLI_ARGUMENTS = {
    ("mode=template",),
    ("mode=structural",),
    ("mode=closure_candidate",),
}


def _reject_cli() -> Never:
    """Emit the one permitted rejection receipt without echoing private input."""

    print(json.dumps(REJECTED_RECEIPT, sort_keys=True), file=sys.stderr)
    raise SystemExit(2)


def _absolute_environment_path(value: str) -> Path:
    """Require environment-only absolute transport for private path values."""

    path = Path(value)
    if not path.is_absolute():
        raise F502LenderReturnError("private validator path must be absolute")
    return path


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="f5_02_lender_return",
)
def main(cfg: DictConfig) -> None:
    """Validate a private return and print only a non-confidential JSON receipt."""

    try:
        if set(cfg.keys()) != {"mode"}:
            raise F502LenderReturnError("validator config has unexpected fields")
        mode_value = cfg.get("mode")
        if not isinstance(mode_value, str):
            raise F502LenderReturnError("validation mode must be a string")
        mode = mode_value
        if mode not in {"template", "structural", "closure_candidate"}:
            raise F502LenderReturnError("unsupported validation mode")
        input_value = os.environ.get(RETURN_PATH_ENV, "")
        custodian_role = os.environ.get(CUSTODIAN_ROLE_ENV, "")
        receipt_timestamp = os.environ.get(RECEIPT_TIMESTAMP_ENV, "")
        if not input_value or not custodian_role or not receipt_timestamp:
            raise F502LenderReturnError("required private validator input is absent")
        ingress_manifest_value = os.environ.get(INGRESS_MANIFEST_PATH_ENV, "")
        ingress_manifest_path = (
            _absolute_environment_path(ingress_manifest_value)
            if ingress_manifest_value
            else None
        )
        summary = validate_f5_02_lender_return(
            _absolute_environment_path(input_value),
            template_path=DEFAULT_TEMPLATE,
            mode=cast(ValidationMode, mode),
            private_ingress_manifest_path=ingress_manifest_path,
        )
        receipt = summary.to_public_receipt(
            custodian_role=custodian_role,
            receipt_timestamp=receipt_timestamp,
        )
    except (F502LenderReturnError, OSError, UnicodeError, ValueError):
        _reject_cli()
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    if tuple(sys.argv[1:]) not in ALLOWED_CLI_ARGUMENTS:
        _reject_cli()
    main()
