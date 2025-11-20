#!/usr/bin/env python3
"""
FX config strictness tests for analytics.scenario_loader.

We enforce the v14 rules:

- fx must be a mapping (dict), not a scalar.
- fx.start_lkr_per_usd is required and must be > 0.
- load_scenario_config must fail loudly when these rules are violated.
"""

from pathlib import Path

import pytest
import yaml

from analytics.scenario_loader import load_scenario_config


def _write_cfg(tmp_path: Path, name: str, cfg: dict) -> Path:
    """Helper to write a YAML config under tmp_path and return its path."""
    path = tmp_path / name
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return path


def _minimal_core_sections() -> dict:
    """Return the minimal required non-FX sections for v14 validation."""
    return {
        "capex": {"usd_total": 100_000_000.0},
        "debt": {"dummy": True},
        "generation": {"dummy": True},
    }


def test_fx_mapping_with_start_rate_is_accepted(tmp_path):
    """
    A config with fx as a mapping, including start_lkr_per_usd > 0,
    must load successfully via load_scenario_config.
    """
    cfg = {
        **_minimal_core_sections(),
        "fx": {
            "start_lkr_per_usd": 350.0,
            "annual_depr": 0.03,
        },
    }

    path = _write_cfg(tmp_path, "valid_fx.yaml", cfg)

    loaded = load_scenario_config(str(path))

    assert "fx" in loaded
    assert loaded["fx"]["start_lkr_per_usd"] == 350.0
    # annual_depr should be preserved if present
    assert loaded["fx"].get("annual_depr") == 0.03


def test_scalar_fx_is_rejected_with_clear_error(tmp_path):
    """
    A config with fx as a bare scalar (e.g. fx: 300.0) must be rejected.

    This encodes the policy of disallowing scalar fx in v14 configs.
    """
    cfg = {
        **_minimal_core_sections(),
        "fx": 300.0,  # invalid in v14
    }

    path = _write_cfg(tmp_path, "scalar_fx.yaml", cfg)

    with pytest.raises(ValueError) as excinfo:
        load_scenario_config(str(path))

    msg = str(excinfo.value)
    # We don't assert the full message, but we require it to clearly point
    # to "mapping vs scalar" so users know what to fix.
    assert "Invalid FX configuration" in msg
    assert "expected mapping" in msg
