"""Regression tests for the strict-validation branch of analytics.pipeline_v14.

The base pipeline's `validation_mode="strict"` branch used to do
`from schema import schema_guard` (no such module) and call
`schema_guard.validate_config(...)` (no such function) — so it raised
ModuleNotFoundError on every strict-mode invocation, which the only caller
(scripts/legacy_runners/run_complete_analysis_fixed.py) swallowed. It is now wired
to the canonical `analytics.schema_guard.validate_config_for_v14`. These tests pin
that wiring via the early validation-failure path (which returns before the heavier
wind/ERA5 stages run, so no network or credentials are needed).
"""
from __future__ import annotations

from pathlib import Path

import yaml

from analytics.pipeline_v14 import run_v14_pipeline


def _write(tmp_path: Path, cfg: dict) -> str:
    p = tmp_path / "scenario.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return str(p)


def test_strict_validation_no_longer_raises_import_error(tmp_path: Path):
    """A config that fails validation must return a clean error dict, NOT raise
    ModuleNotFoundError('schema') / AttributeError (the old breakage)."""
    # Missing the required `fx` section -> validate_config_for_v14 raises
    # ConfigValidationError, which the pipeline catches and surfaces as an error dict.
    cfg = {"project": {"name": "unit-test", "capacity_mw": 10.0}}
    result = run_v14_pipeline(
        config=_write(tmp_path, cfg),
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )
    assert isinstance(result, dict)
    assert result.get("status") == "error"
    assert "Schema validation failed" in result.get("error", "")


def test_strict_validation_error_is_caught_not_propagated(tmp_path: Path):
    """The ConfigValidationError must be caught (returned), never propagated as an
    uncaught exception to the caller."""
    cfg = {"project": {"name": "unit-test", "capacity_mw": 10.0}}  # no fx
    # Should not raise — the function returns the error dict.
    result = run_v14_pipeline(
        config=_write(tmp_path, cfg),
        validation_mode="strict",
        validation_modules=["cashflow"],
    )
    assert result["status"] == "error"
