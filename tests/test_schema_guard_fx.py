"""
Regression tests for v14 schema_guard FX validation.

The v14 engine requires a structured FX configuration with mandatory
keys (start_lkr_per_usd, annual_depr). These tests ensure the schema
guard properly validates FX configs before heavy finance logic runs.
"""

from __future__ import annotations

from typing import Any

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

# Test fixtures
MINIMAL_VALID_CONFIG: dict[str, Any] = {
    "project": {
        "name": "test_project",
        "capacity_factor": 0.40,
        "capacity_mw": 100,
        "life_years": 20,
        "corporate_tax_rate": 0.30,
    },
    "capex": {
        "usd_total": 100_000_000.0,
    },
    "opex": {
        "usd_per_year": 5_000_000.0,
    },
    "tax": {
        "corporate_tax_rate": 0.30,
    },
    "tariff": {
        "lkr_per_kwh": 20.30,
    },
    "fx": {
        "start_lkr_per_usd": 375.0,
        "annual_depr": 0.03,
    },
}


class TestFXValidationRejections:
    """Tests for configs that should be REJECTED."""

    def test_scalar_fx_is_rejected(self) -> None:
        """v14 must reject scalar `fx` configs (legacy v13 style)."""
        cfg: dict[str, Any] = {
            "project": {"name": "bad_fx"},
            "fx": 375.0,  # Scalar instead of mapping
        }

        with pytest.raises(
            ConfigValidationError,
            match="scalar `fx` is no longer supported",
        ):
            validate_config_for_v14(
                raw_config=cfg,
                config_path="bad_scalar_fx.yaml",
                modules=["cashflow"],
            )

    def test_missing_fx_section_is_rejected(self) -> None:
        """FX section is mandatory in v14."""
        cfg: dict[str, Any] = {
            "project": {"name": "no_fx"},
            # No 'fx' key at all
        }

        with pytest.raises(
            ConfigValidationError,
            match="Missing `fx` section",
        ):
            validate_config_for_v14(cfg, "no_fx.yaml", modules=["cashflow"])

    def test_fx_missing_start_rate_is_rejected(self) -> None:
        """FX mapping must include start_lkr_per_usd."""
        cfg: dict[str, Any] = {
            "project": {"name": "incomplete_fx"},
            "fx": {
                "annual_depr": 0.03,
                # Missing start_lkr_per_usd
            },
        }

        with pytest.raises(
            ConfigValidationError,
            match="start_lkr_per_usd",
        ):
            validate_config_for_v14(cfg, "incomplete.yaml", modules=["cashflow"])

    def test_fx_missing_annual_depr_is_rejected(self) -> None:
        """FX mapping must include annual_depr."""
        cfg: dict[str, Any] = {
            "project": {"name": "incomplete_fx"},
            "fx": {
                "start_lkr_per_usd": 375.0,
                # Missing annual_depr
            },
        }

        with pytest.raises(
            ConfigValidationError,
            match="annual_depr",
        ):
            validate_config_for_v14(cfg, "incomplete.yaml", modules=["cashflow"])

    @pytest.mark.parametrize(
        "bad_fx_value",
        [
            [375.0, 0.03],  # List
            "375 LKR/USD",  # String
            123,  # Integer
        ],
        ids=["list", "string", "int"],
    )
    def test_fx_wrong_type_is_rejected(self, bad_fx_value: Any) -> None:
        """FX must be a mapping/dict, not other types."""
        cfg: dict[str, Any] = {
            "project": {"name": "bad_type"},
            "fx": bad_fx_value,
        }

        with pytest.raises(
            ConfigValidationError,
            match="Invalid FX config",
        ):
            validate_config_for_v14(cfg, "bad_type.yaml", modules=["cashflow"])


class TestFXValidationAcceptance:
    """Tests for configs that should be ACCEPTED."""

    def test_structured_fx_is_accepted(self) -> None:
        """
        Standard v14 FX config with both required keys and minimal cashflow fields.

        This uses MINIMAL_VALID_CONFIG, which satisfies all required
        cashflow fields (capacity, capex, opex, tax, tariff, life_years)
        plus a structured FX block.
        """
        cfg: dict[str, Any] = dict(MINIMAL_VALID_CONFIG)

        # Should NOT raise
        validate_config_for_v14(
            raw_config=cfg,
            config_path="good_structured_fx.yaml",
            modules=["cashflow"],
        )

    def test_fx_with_zero_depr_is_accepted(self) -> None:
        """Zero depreciation (pegged currency regime)."""
        cfg: dict[str, Any] = dict(MINIMAL_VALID_CONFIG)
        cfg["fx"] = {
            "start_lkr_per_usd": 375.0,
            "annual_depr": 0.0,
        }

        # Should NOT raise
        validate_config_for_v14(cfg, "zero_depr.yaml", modules=["cashflow"])

    def test_fx_with_negative_depr_is_accepted(self) -> None:
        """Negative depreciation (currency appreciation)."""
        cfg: dict[str, Any] = dict(MINIMAL_VALID_CONFIG)
        cfg["fx"] = {
            "start_lkr_per_usd": 375.0,
            "annual_depr": -0.02,  # Appreciation scenario
        }

        # Should NOT raise
        validate_config_for_v14(cfg, "appreciation.yaml", modules=["cashflow"])

    def test_fx_with_extra_keys_is_accepted(self) -> None:
        """Extra keys in FX config should not cause rejection."""
        cfg: dict[str, Any] = dict(MINIMAL_VALID_CONFIG)
        cfg["fx"] = {
            "start_lkr_per_usd": 375.0,
            "annual_depr": 0.03,
            "historical_volatility": 0.12,  # Extra key
            "regime": "floating",  # Extra key
        }

        # Should NOT raise
        validate_config_for_v14(cfg, "extra_keys.yaml", modules=["cashflow"])


class TestFXValidationModuleIndependence:
    """Ensure FX validation runs regardless of which modules are validated."""

    @pytest.mark.parametrize(
        "modules",
        [
            ["cashflow"],
            ["debt"],
            ["cashflow", "debt"],
            None,  # If None is supported
        ],
        ids=["cashflow_only", "debt_only", "both", "none"],
    )
    def test_fx_validation_always_runs(self, modules: list[str] | None) -> None:
        """FX validation should run for any module list."""
        cfg: dict[str, Any] = {
            "project": {"name": "bad_fx"},
            "fx": 375.0,  # Invalid scalar
        }

        with pytest.raises(ConfigValidationError):
            validate_config_for_v14(cfg, "bad.yaml", modules=modules)


class TestErrorMessageQuality:
    """Ensure error messages are helpful for users."""

    def test_missing_fx_error_is_descriptive(self) -> None:
        """Missing FX error should guide user to solution."""
        cfg: dict[str, Any] = {"project": {"name": "test"}}

        try:
            validate_config_for_v14(cfg, "test.yaml", modules=["cashflow"])
            pytest.fail("Should have raised ConfigValidationError")
        except ConfigValidationError as e:
            error_msg = str(e).lower()
            # Should mention what's missing
            assert "fx" in error_msg
            # Should mention required keys
            assert "start_lkr_per_usd" in error_msg
            assert "annual_depr" in error_msg

    def test_incomplete_fx_error_lists_missing_keys(self) -> None:
        """Error for incomplete FX should list missing keys."""
        cfg: dict[str, Any] = {
            "project": {"name": "test"},
            "fx": {"start_lkr_per_usd": 375.0},  # Missing annual_depr
        }

        try:
            validate_config_for_v14(cfg, "test.yaml", modules=["cashflow"])
            pytest.fail("Should have raised ConfigValidationError")
        except ConfigValidationError as e:
            error_msg = str(e).lower()
            assert "annual_depr" in error_msg


# EOF
