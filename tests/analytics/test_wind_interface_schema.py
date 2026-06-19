#!/usr/bin/env python
"""Schema-guard tests for the GIS → EPC wind interface (#22).

Validates the normalized ``resource.wind`` block: the real lender config must
satisfy it (CI fails otherwise), and broken blocks must be rejected by
``validate_config_for_v14(cfg, path, ["wind"])``.

Context:
    Sprint 10 - Issue #22 (Standardize GIS → EPC wind interface schema).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from analytics.config_schema import get_required_fields
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from analytics.wind.wind_interface_schema import WIND_INTERFACE_MODULE

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

EXPECTED_FIELDS = {
    "ws150_mean_ms",
    "ws150_std_ms",
    "capacity_factor",
    "aep_gwh",
    "source_id",
    "source_type",
}


@pytest.fixture
def cfg() -> dict:
    return yaml.safe_load(LENDER_CONFIG.read_text())


def test_specs_registered() -> None:
    names = {spec.name for spec in get_required_fields(WIND_INTERFACE_MODULE)}
    assert names == EXPECTED_FIELDS


def test_lender_config_passes_wind_schema(cfg: dict) -> None:
    """The real lender config must satisfy the resource.wind schema."""
    validate_config_for_v14(cfg, str(LENDER_CONFIG), ["wind"])  # must not raise


def test_resource_wind_block_present(cfg: dict) -> None:
    wind = cfg["resource"]["wind"]
    assert set(EXPECTED_FIELDS).issubset(wind.keys())


def test_missing_field_fails(cfg: dict) -> None:
    broken = copy.deepcopy(cfg)
    del broken["resource"]["wind"]["ws150_mean_ms"]
    with pytest.raises(ConfigValidationError, match="ws150_mean_ms"):
        validate_config_for_v14(broken, str(LENDER_CONFIG), ["wind"])


def test_unknown_source_id_fails(cfg: dict) -> None:
    broken = copy.deepcopy(cfg)
    broken["resource"]["wind"]["source_id"] = "NOT_IN_MANIFEST"
    with pytest.raises(ConfigValidationError, match="source_id"):
        validate_config_for_v14(broken, str(LENDER_CONFIG), ["wind"])


def test_capacity_factor_out_of_range_fails(cfg: dict) -> None:
    broken = copy.deepcopy(cfg)
    broken["resource"]["wind"]["capacity_factor"] = 1.5
    with pytest.raises(ConfigValidationError, match="capacity_factor"):
        validate_config_for_v14(broken, str(LENDER_CONFIG), ["wind"])


def test_negative_wind_speed_fails(cfg: dict) -> None:
    broken = copy.deepcopy(cfg)
    broken["resource"]["wind"]["ws150_mean_ms"] = -1.0
    with pytest.raises(ConfigValidationError, match="ws150_mean_ms"):
        validate_config_for_v14(broken, str(LENDER_CONFIG), ["wind"])


def test_invalid_source_type_fails(cfg: dict) -> None:
    broken = copy.deepcopy(cfg)
    broken["resource"]["wind"]["source_type"] = "SATELLITE"
    with pytest.raises(ConfigValidationError, match="source_type"):
        validate_config_for_v14(broken, str(LENDER_CONFIG), ["wind"])
