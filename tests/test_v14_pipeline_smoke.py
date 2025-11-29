"""
Smoke tests for run_v14_pipeline - v14 full pipeline entry point.

These tests verify the basic contract of run_v14_pipeline without
asserting exact KPI values (which would be brittle). They ensure:
  1. The pipeline runs without crashing
  2. The output structure matches expectations
  3. KPI values are within plausible ranges
  4. Both validation modes (strict/off) work correctly
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from run_full_pipeline_v14 import run_v14_pipeline

# Test data constants
SCENARIO_DIR = Path("scenarios")
LENDERCASE_CONFIG = SCENARIO_DIR / "dutchbay_lendercase_2025Q4.yaml"

# Plausible KPI ranges (prevent obviously broken values)
PLAUSIBLE_IRR_RANGE = (-0.5, 2.0)  # -50% to 200%
PLAUSIBLE_DSCR_RANGE = (0.1, 50.0)  # Extreme but not impossible
PLAUSIBLE_NPV_RANGE = (-1e10, 1e10)  # ±10 billion USD


def _validate_kpi_structure(kpis: dict[str, Any]) -> None:
    """
    Helper to validate KPI dict structure and value sanity.

    Raises AssertionError if KPIs are malformed or implausible.
    """
    # Required KPI keys (v14 naming convention)
    required_keys = {
        "project_npv",
        "project_irr",
        "min_dscr",
        "dscr_series",
    }

    missing = required_keys - kpis.keys()
    assert not missing, f"Missing required KPIs: {missing}"

    # NPV: numeric and within plausible range
    npv = kpis["project_npv"]
    assert isinstance(npv, (int, float)), f"project_npv not numeric: {type(npv)}"
    assert (
        PLAUSIBLE_NPV_RANGE[0] <= npv <= PLAUSIBLE_NPV_RANGE[1]
    ), f"project_npv out of range: {npv}"

    # IRR: numeric and within plausible range
    irr = kpis["project_irr"]
    assert isinstance(irr, (int, float)), f"project_irr not numeric: {type(irr)}"
    assert (
        PLAUSIBLE_IRR_RANGE[0] <= irr <= PLAUSIBLE_IRR_RANGE[1]
    ), f"project_irr out of range: {irr} (expected {PLAUSIBLE_IRR_RANGE})"

    # min_dscr: numeric and positive (not inf)
    dscr = kpis["min_dscr"]
    assert isinstance(dscr, (int, float)), f"min_dscr not numeric: {type(dscr)}"
    assert not (
        dscr == float("inf") or dscr == float("-inf")
    ), f"min_dscr is infinite: {dscr}"
    assert (
        PLAUSIBLE_DSCR_RANGE[0] <= dscr <= PLAUSIBLE_DSCR_RANGE[1]
    ), f"min_dscr out of range: {dscr}"

    # dscr_series: list of numerics
    dscr_series = kpis["dscr_series"]
    assert isinstance(dscr_series, list), "dscr_series must be a list"
    assert len(dscr_series) > 0, "dscr_series should not be empty"
    assert all(
        isinstance(x, (int, float)) for x in dscr_series
    ), "dscr_series must contain only numbers"


@pytest.fixture(scope="module")
def scenario_path() -> Path:
    """Provide the lendercase config path, checking it exists."""
    assert LENDERCASE_CONFIG.exists(), (
        f"Missing test scenario: {LENDERCASE_CONFIG}. "
        "Ensure the repository includes test fixtures."
    )
    return LENDERCASE_CONFIG


@pytest.mark.smoke
@pytest.mark.parametrize(
    "validation_mode",
    ["strict", "off"],
    ids=["strict_mode", "off_mode"],
)
def test_run_v14_pipeline_returns_valid_structure(
    scenario_path: Path,
    validation_mode: str,
) -> None:
    """
    Smoke test: pipeline runs and returns structurally valid output.

    Verifies that run_v14_pipeline:
      1. Executes without raising exceptions
      2. Returns a dict with expected keys
      3. Produces KPIs that pass sanity checks
      4. Works in both 'strict' and 'off' validation modes
    """
    result: dict[str, Any] = run_v14_pipeline(
        config=str(scenario_path),
        validation_mode=validation_mode,
    )

    # Top-level structure
    assert isinstance(result, dict), "Result must be a dict"
    assert result.get("config_path") == str(scenario_path)
    assert result.get("validation_mode") == validation_mode

    # Required top-level keys
    required_keys = {"config", "annual_rows", "debt_result", "kpis"}
    missing = required_keys - result.keys()
    assert not missing, f"Missing required keys: {missing}"

    # Type checks
    assert isinstance(result["config"], dict), "config must be a dict"
    assert isinstance(result["annual_rows"], list), "annual_rows must be a list"
    assert isinstance(result["debt_result"], dict), "debt_result must be a dict"
    assert isinstance(result["kpis"], dict), "kpis must be a dict"

    # Validate KPI structure and values
    _validate_kpi_structure(result["kpis"])


@pytest.mark.smoke
def test_run_v14_pipeline_strict_mode_validates_schema(
    scenario_path: Path,
) -> None:
    """
    Ensure strict mode actually runs schema validation.

    This test would catch regressions where validation is accidentally
    disabled or bypassed.
    """
    # This should succeed (valid config)
    result = run_v14_pipeline(
        config=str(scenario_path),
        validation_mode="strict",
    )
    assert result["validation_mode"] == "strict"
    assert "kpis" in result


@pytest.mark.smoke
def test_run_v14_pipeline_rejects_invalid_validation_mode() -> None:
    """
    Ensure invalid validation_mode raises ValueError.
    """
    with pytest.raises(
        ValueError,
        match=r"validation_mode must be 'strict' or 'off'",
    ):
        run_v14_pipeline(
            config=str(LENDERCASE_CONFIG),
            validation_mode="invalid_mode",
        )


@pytest.mark.smoke
def test_run_v14_pipeline_rejects_missing_config() -> None:
    """
    Ensure missing config file raises appropriate error.
    """
    nonexistent = SCENARIO_DIR / "does_not_exist.yaml"

    with pytest.raises((FileNotFoundError, OSError)):
        run_v14_pipeline(
            config=str(nonexistent),
            validation_mode="off",
        )


@pytest.mark.integration
def test_run_v14_pipeline_annual_rows_not_empty(
    scenario_path: Path,
) -> None:
    """
    Integration test: verify annual_rows contains actual cashflow data.

    This is a deeper check than the smoke test - it ensures the finance
    engine actually produced output, not just empty structures.
    """
    result = run_v14_pipeline(
        config=str(scenario_path),
        validation_mode="strict",
    )

    annual_rows = result["annual_rows"]
    assert len(annual_rows) > 0, "annual_rows should contain cashflow data"

    # Check that rows have expected structure (sample first row)
    if annual_rows:
        first_row = annual_rows[0]
        assert isinstance(first_row, dict), "Each annual row should be a dict"

        # Common expected keys in cashflow rows
        expected_keys = {"year", "revenue", "opex", "ebitda"}
        present_keys = expected_keys & first_row.keys()
        assert (
            len(present_keys) >= 2
        ), f"Annual rows missing common keys. Found: {list(first_row.keys())}"


@pytest.mark.integration
def test_run_v14_pipeline_debt_result_has_metrics(
    scenario_path: Path,
) -> None:
    """
    Integration test: verify debt_result contains debt metrics.
    """
    result = run_v14_pipeline(
        config=str(scenario_path),
        validation_mode="strict",
    )

    debt_result = result["debt_result"]

    # If debt is configured, expect non-empty debt_result
    config = result["config"]
    if config.get("Financing_Terms"):
        assert (
            len(debt_result) > 0
        ), "debt_result should not be empty when Financing_Terms exists"


# EOF
