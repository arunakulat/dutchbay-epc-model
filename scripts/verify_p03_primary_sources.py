#!/usr/bin/env python3
"""Hydra CLI for the fail-closed P03 retained-source implementer preflight."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Never, cast

import hydra
from omegaconf import DictConfig

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "scripts"
    / "build_primary_source_review_plan.py"
)
SOURCE_ROOT_ENV = "DUTCHBAY_P03_SOURCE_ROOT"
ALLOWED_CLI_ARGUMENTS = {(), ("mode=verify_retained_sources",)}


class P03CliError(RuntimeError):
    """Controlled CLI/configuration failure without a local-path payload."""

    def __init__(self, code: str, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.stage = stage
        self.detail = detail


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "p03_primary_source_review_builder", BUILDER_PATH
    )
    if spec is None or spec.loader is None:
        raise P03CliError(
            "BUILDER_LOAD", "runtime", "P03 primary-source builder cannot be loaded"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_root_from_environment() -> Path:
    raw = os.environ.get(SOURCE_ROOT_ENV, "")
    path = Path(raw)
    if not raw or not path.is_absolute():
        raise P03CliError(
            "ENVIRONMENT_PATH",
            "configuration",
            f"{SOURCE_ROOT_ENV} must contain an absolute path",
        )
    return path


def _base_failure_receipt(code: str, stage: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "dutchbay.p03_primary_source_verification_receipt.v1",
        "status": "FAIL",
        "gate_id": "P03",
        "gate_status": "pending_independent_review",
        "release_status": "HOLD",
        "code": code,
        "stage": stage,
        "detail": detail,
        "completion_authorized": False,
    }


def _failure_receipt(builder: ModuleType | None, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, P03CliError):
        return _base_failure_receipt(exc.code, exc.stage, exc.detail)
    if builder is not None:
        error_type = getattr(builder, "PrimarySourceControlError", None)
        if isinstance(error_type, type) and isinstance(exc, error_type):
            receipt = builder.failure_receipt(exc)
            return cast(dict[str, Any], receipt)
    return _base_failure_receipt(
        "UNEXPECTED_VALIDATION_FAILURE",
        "runtime",
        f"unexpected P03 validation failure: {type(exc).__name__}",
    )


def _reject(receipt: dict[str, Any]) -> Never:
    print(json.dumps(receipt, sort_keys=True, allow_nan=False), file=sys.stderr)
    raise SystemExit(2)


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="p03_primary_sources",
)
def main(cfg: DictConfig) -> None:
    """Verify retained P03 sources and print one concise path-free JSON receipt."""

    builder: ModuleType | None = None
    try:
        builder = _load_builder()
        if set(cfg.keys()) != {"mode"}:
            raise P03CliError(
                "CONFIGURATION_KEYS",
                "configuration",
                "P03 primary-source config has unexpected fields",
            )
        if cfg.get("mode") != "verify_retained_sources":
            raise P03CliError(
                "CONFIGURATION_MODE",
                "configuration",
                "P03 primary-source mode must be verify_retained_sources",
            )
        receipt = builder.verify_retained_source_root(_source_root_from_environment())
    except Exception as exc:
        _reject(_failure_receipt(builder, exc))
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    if tuple(sys.argv[1:]) not in ALLOWED_CLI_ARGUMENTS:
        _reject(
            _base_failure_receipt(
                "CLI_ARGUMENTS",
                "configuration",
                "unsupported P03 primary-source CLI arguments",
            )
        )
    main()
