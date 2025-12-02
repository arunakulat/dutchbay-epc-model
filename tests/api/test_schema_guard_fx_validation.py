#!/usr/bin/env python3
"""
Schema guard validation tests for FX configuration (Go With The Flow R5/R6).

These tests verify that the schema guard correctly enforces:
  - R5: Schema guard as pre-flight gatekeeper
  - R6: FX must be a mapping (not scalar)

Invalid configs are tested here explicitly, instead of weakening
production code or bypassing validation in functional tests.
"""

from __future__ import annotations

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14


def test_schema_guard_rejects_missing_fx() -> None:
    """
    R5/R6: Schema guard must reject configs without FX section.

    Ensures all v14 configs explicitly specify FX assumptions.
    """
    config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        # Missing "fx"
    }

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_for_v14(
            raw_config=config,
            config_path="test_config.yaml",
            modules=["cashflow"],
        )

    msg = str(exc_info.value)
    assert "Missing `fx` section" in msg
    assert "start_lkr_per_usd" in msg
    assert "annual_depr" in msg


def test_schema_guard_rejects_scalar_fx() -> None:
    """
    R6: Schema guard must reject scalar FX values (v13 legacy style).
    """
    config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        "fx": 375.0,  # legacy scalar style
    }

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_for_v14(
            raw_config=config,
            config_path="test_config.yaml",
            modules=["cashflow"],
        )

    msg = str(exc_info.value).lower()
    assert "scalar" in msg
    assert "fx" in msg
    assert "mapping" in msg


def test_schema_guard_rejects_fx_missing_start_rate() -> None:
    """
    R6: FX mapping must include start_lkr_per_usd.
    """
    config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        "fx": {
            "annual_depr": 0.03,
        },
    }

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config_for_v14(
            raw_config=config,
            config_path="test_config.yaml",
            modules=["cashflow"],
        )

    msg = str(exc_info.value)
    assert "start_lkr_per_usd" in msg


def test_schema_guard_accepts_valid_fx_mapping() -> None:
    """
    R6: Valid FX mapping with both required keys should pass.
    """
    config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 225_000_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tariff": {
            "tariff_lkr_per_kwh": 6.5,
        },
        "fx": {
            "start_lkr_per_usd": 300.0,
            "annual_depr": 0.03,
        },
    }

    # Should not raise
    validate_config_for_v14(
        raw_config=config,
        config_path="test_config.yaml",
        modules=["cashflow"],
    )


def test_schema_guard_accepts_fx_with_zero_depreciation() -> None:
    """
    R6: FX with zero annual_depr is valid (flat FX curve scenarios).
    """
    config = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 225_000_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28,
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tariff": {
            "tariff_lkr_per_kwh": 6.5,
        },
        "fx": {
            "start_lkr_per_usd": 300.0,
            "annual_depr": 0.0,
        },
    }

    # Should not raise
    validate_config_for_v14(
        raw_config=config,
        config_path="test_config.yaml",
        modules=["cashflow"],
    )
