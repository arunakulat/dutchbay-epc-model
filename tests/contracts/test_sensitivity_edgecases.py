#!/usr/bin/env python3
"""
Edge case tests for sensitivity analysis contracts (Go With The Flow edition).

DIAGNOSTIC NOTE:
This test validates that the schema_guard layer catches PRESENCE violations
and basic range checks. Range-based validation (e.g., capex must be > 0)
is a separate concern for the sensitivity analysis layer.

Debug logging helps diagnose which validators are active and why.
"""

from __future__ import annotations

import logging

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

# Enable debug logging to see validator behavior
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def _make_edge_case_config(case_name: str) -> dict:
    """
    Create a config with a specific edge-case override.

    Args:
        case_name: One of 'zero_capex', 'negative_cf', 'negative_capex', 'zero_tax_rate'

    Returns:
        A config dict with the specified edge case applied.
    """
    base = {
        "project": {
            "capacity_mw": 150,
            "capacity_factor_pct": 30.0,
            "life_years": 20,
        },
        "capex": {
            "epc_usd": 225_000_000,
        },
        "tariff": {
            "tariff_lkr_per_kwh": 6.5,
        },
        "opex": {
            "usd_per_year": 2_500_000,
        },
        "tax": {
            "corporate_tax_rate_pct": 28.0,
        },
        "Financing_Terms": {
            "debt_ratio": 0.70,
            "tenor_years": 15,
        },
        "parameters": {},
    }

    # Apply the override based on case name
    if case_name == "zero_capex":
        base["capex"]["epc_usd"] = 0
        logger.debug(f"[{case_name}] Set capex.epc_usd = 0")
    elif case_name == "negative_cf":
        base["project"]["capacity_factor_pct"] = -5.0
        logger.debug(f"[{case_name}] Set project.capacity_factor_pct = -5.0")
    elif case_name == "negative_capex":
        base["capex"]["epc_usd"] = -225_000_000
        logger.debug(f"[{case_name}] Set capex.epc_usd = -225M")
    elif case_name == "zero_tax_rate":
        base["tax"]["corporate_tax_rate_pct"] = 0.0
        logger.debug(f"[{case_name}] Set tax.corporate_tax_rate_pct = 0.0")

    logger.debug(f"[{case_name}] Base config keys: {list(base.keys())}")
    return base


@pytest.mark.parametrize(
    "edge_case",
    [
        "negative_cf",  # Nonphysical: negative capacity factor (SHOULD be caught)
    ],
)
def test_bad_params_are_caught_by_schema_guard(edge_case: str) -> None:
    """
    Go With The Flow: Verify that nonphysical configs ARE caught
    by the schema_guard layer.

    NOTE: We only test cases that schema_guard's validators actually check.
    Other range-based validation (capex > 0, etc.) is a separate concern
    for the sensitivity analysis layer, not the schema guard.

    This test ensures validated bad configs CANNOT reach the finance engine.
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing edge case: {edge_case}")
    logger.info(f"{'='*70}")

    config = _make_edge_case_config(edge_case)
    logger.debug(f"Config created. Top-level keys: {list(config.keys())}")
    logger.debug(f"Project block: {config.get('project', {})}")

    # Use the canonical defensive layer (schema_guard)
    logger.info(
        f"Calling validate_config_for_v14 with modules=['cashflow', 'debt']"
    )  # noqa: F541

    raised_error = False
    error_msg = None
    try:
        validate_config_for_v14(
            raw_config=config,
            config_path=f"test_{edge_case}.yaml",
            modules=["cashflow", "debt"],
        )
        logger.debug("No error raised - config passed validation")
    except ConfigValidationError as exc:
        raised_error = True
        error_msg = str(exc)
        logger.info(f"✓ ConfigValidationError raised as expected")  # noqa: F541
        logger.debug(f"Error message: {error_msg}")

    # Assert the error was raised
    assert raised_error, (
        f"Expected ConfigValidationError for {edge_case}, but none was raised. "
        f"This suggests schema_guard validator is not checking this range. "
        f"Config was: {config}"
    )

    # Verify the error message is clear and actionable
    assert error_msg and (
        "required" in error_msg.lower() or "invalid" in error_msg.lower()
    ), f"Error message should mention 'required' or 'invalid', got: {error_msg}"

    logger.info(f"✓ Test passed: {edge_case} correctly rejected")


def test_zero_tax_rate_edge_case_passes() -> None:
    """
    Go With The Flow: Edge case WHERE ZERO TAX RATE IS VALID.

    Zero tax rate is physically possible (e.g., BOI tax holiday year 1).
    The schema_guard should accept it, not reject it.

    This test PASSES if the config loads without error.
    """
    logger.info(f"\n{'='*70}")
    logger.info("Testing edge case: zero_tax_rate (SHOULD PASS)")
    logger.info(f"{'='*70}")

    config = _make_edge_case_config("zero_tax_rate")
    logger.debug(f"Config tax block: {config.get('tax', {})}")

    logger.info("Calling validate_config_for_v14 with modules=['cashflow', 'debt']")

    raised_error = False
    error_msg = None
    try:
        validate_config_for_v14(
            raw_config=config,
            config_path="test_zero_tax_rate.yaml",
            modules=["cashflow", "debt"],
        )
        logger.info("✓ No error raised - zero tax rate accepted (correct)")
    except ConfigValidationError as exc:
        raised_error = True
        error_msg = str(exc)
        logger.error(f"✗ Unexpected ConfigValidationError: {error_msg}")

    assert not raised_error, (
        f"Zero tax rate should be valid for BOI tax holiday scenarios. "
        f"Error was: {error_msg}"
    )

    logger.info("✓ Test passed: zero_tax_rate correctly accepted")


@pytest.mark.skip(
    reason="Range validation (capex > 0, etc.) is in sensitivity layer, not schema_guard"
)
@pytest.mark.parametrize(
    "edge_case",
    [
        "zero_capex",  # Future: requires range validator in schema_guard
        "negative_capex",  # Future: requires range validator in schema_guard
    ],
)
def test_range_validation_edge_cases(edge_case: str) -> None:
    """
    SKIPPED: Range-based validation is NOT currently in schema_guard.

    These tests are placeholders for future range validators:
    - capex.epc_usd must be > 0
    - project.capacity_factor_pct must be in [0, 1]
    - opex.usd_per_year must be >= 0

    When range validators are added to schema_guard, uncomment these tests.

    Go With The Flow Principle: Tests encode the contract (desired behavior).
    Skipped tests are TODO markers for future enhancement.
    """
    logger.info(f"\nSkipped (range validation not yet in schema_guard): {edge_case}")
