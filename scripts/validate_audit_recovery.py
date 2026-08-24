#!/usr/bin/env python3
"""Hydra CLI for portable, fail-closed DutchBay audit checkpoint recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Never

import hydra
from omegaconf import DictConfig

from analysis_tools.audit_recovery import (
    AuditRecoveryError,
    failure_receipt,
    validate_and_materialize_recovery,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_PATH = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "recovery"
    / "P01_RECOVERY_DESCRIPTOR.v1.json"
)
CHECKPOINT_ROOT_ENV = "DUTCHBAY_AUDIT_CHECKPOINT_ROOT"
AUDIT_CORPUS_ROOT_ENV = "DUTCHBAY_AUDIT_CORPUS_ROOT"
REPOSITORY_ROOT_ENV = "DUTCHBAY_AUDIT_REPOSITORY_ROOT"
OUTPUT_ROOT_ENV = "DUTCHBAY_AUDIT_RECOVERY_OUTPUT_ROOT"
ALLOWED_CLI_ARGUMENTS = {(), ("mode=recover_and_validate",)}


def _absolute_environment_path(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_absolute():
        raise AuditRecoveryError(
            "ENVIRONMENT_PATH",
            "configuration",
            f"{name} must contain an absolute path",
        )
    return path


def _reject_cli(error: AuditRecoveryError) -> Never:
    print(
        json.dumps(failure_receipt(error), sort_keys=True, allow_nan=False),
        file=sys.stderr,
    )
    raise SystemExit(2)


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="audit_recovery",
)
def main(cfg: DictConfig) -> None:
    """Recover the checkpoint into a new root and print one concise JSON receipt."""

    try:
        if set(cfg.keys()) != {"mode"}:
            raise AuditRecoveryError(
                "CONFIGURATION_KEYS",
                "configuration",
                "audit recovery config has unexpected fields",
            )
        mode = cfg.get("mode")
        if mode != "recover_and_validate":
            raise AuditRecoveryError(
                "CONFIGURATION_MODE",
                "configuration",
                "audit recovery mode must be recover_and_validate",
            )
        receipt = validate_and_materialize_recovery(
            checkpoint_root=_absolute_environment_path(CHECKPOINT_ROOT_ENV),
            audit_corpus_root=_absolute_environment_path(AUDIT_CORPUS_ROOT_ENV),
            repository_root=_absolute_environment_path(REPOSITORY_ROOT_ENV),
            output_root=_absolute_environment_path(OUTPUT_ROOT_ENV),
            descriptor_path=DESCRIPTOR_PATH,
        )
    except AuditRecoveryError as exc:
        _reject_cli(exc)
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as exc:
        # This branch is intentionally generic and path-free.  All expected control
        # failures should already be typed as AuditRecoveryError.
        _reject_cli(
            AuditRecoveryError(
                "UNEXPECTED_VALIDATION_FAILURE",
                "runtime",
                f"unexpected recovery validation failure: {type(exc).__name__}",
            )
        )
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    if tuple(sys.argv[1:]) not in ALLOWED_CLI_ARGUMENTS:
        _reject_cli(
            AuditRecoveryError(
                "CLI_ARGUMENTS",
                "configuration",
                "unsupported audit recovery CLI arguments",
            )
        )
    main()
