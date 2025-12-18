"""Tests for FX integration with pipeline_v14 (ACTION 4 - Sprint 15).

Comprehensive test suite for FX + pipeline integration:
- Pipeline with valid FX config
- Pipeline without FX config (graceful degradation)
- Pipeline with invalid FX config (error handling)
- FX field population in ScenarioResult
- Logging and error messages

All tests follow Go with the Flow standards:
- 88-char lines
- Full docstrings
- Parametrized edge cases
- Black/isort/mypy compliant
"""

import pytest
from analytics.pipeline_v14 import run_v14_pipeline
from analytics.contracts_v14 import ScenarioResult


class TestFXPipelineIntegrationWithConfig:
    """Test FX integration when FX config is present."""

    def test_pipeline_with_minimal_fx_config(self) -> None:
        """Pipeline populates FX fields when minimal FX config present."""
        # Minimal inline config with FX section
        config = {
            "scenario_name": "test_with_minimal_fx",
            "Project": {
                "name": "TestProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 15,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 10,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": "blended",
                "fx_match_ratio": 50,
                "hedging_coverage_pct": 25,
                "curve": {
                    "lkr_usd": [300, 302, 305, 310, 315, 320, 325, 330, 335, 340]
                    + [345, 350, 355, 360, 365],  # 15 years
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")

        # Verify result structure
        assert "scenario_result" in result
        scenario_result_dict = result["scenario_result"]

        # Verify FX fields populated
        assert scenario_result_dict.get("fx_block") is not None, \
            "fx_block should be populated when FX config present"
        assert scenario_result_dict.get("fx_curve") is not None, \
            "fx_curve should be populated"
        assert scenario_result_dict.get("fx_risk_profile") is not None, \
            "fx_risk_profile should be populated"

        # Verify FX block properties
        fx_block = scenario_result_dict["fx_block"]
        assert fx_block["strategy"] == "blended"
        assert fx_block["fx_match_ratio"] == 50.0
        assert fx_block["hedging_coverage_pct"] == 25.0

        # Verify FX curve
        fx_curve = scenario_result_dict["fx_curve"]
        assert fx_curve["source"] == "base_case"
        assert len(fx_curve["lkr_usd"]) == 15
        assert fx_curve["lkr_usd"][0] == 300.0
        assert fx_curve["lkr_usd"][-1] == 365.0

        # Verify FX risk profile
        fx_risk = scenario_result_dict["fx_risk_profile"]
        assert fx_risk["var_95_usd_million"] >= 0.0
        assert fx_risk["cvar_95_usd_million"] >= fx_risk["var_95_usd_million"]

    def test_pipeline_with_multicurrency_fx_config(self) -> None:
        """Pipeline handles multi-currency FX config (CNY + USD)."""
        config = {
            "scenario_name": "test_multicurrency_fx",
            "Project": {
                "name": "MultiCurrencyProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": "natural_hedge",
                "curve": {
                    "lkr_usd": [300] * 10,  # Flat LKR/USD
                    "lkr_cny": [42, 42.5, 43, 43.5, 44, 44.5, 45, 45.5, 46, 46.5],
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        scenario_result_dict = result["scenario_result"]

        # Verify both currencies in curve
        fx_curve = scenario_result_dict["fx_curve"]
        assert fx_curve["lkr_cny"] is not None
        assert len(fx_curve["lkr_cny"]) == 10

    def test_pipeline_with_eur_gbp_curves(self) -> None:
        """Pipeline supports EUR and GBP curves alongside USD."""
        config = {
            "scenario_name": "test_eur_gbp_fx",
            "Project": {
                "name": "EURGBPProject",
                "capex_usd": 50_000_000,
                "opex_usd_yr": 2_000_000,
                "project_life_years": 8,
                "construction_years": 1,
            },
            "Financing_Terms": {
                "total_debt_usd": 30_000_000,
                "debt_tenor_years": 7,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "curve": {
                    "lkr_usd": [300] * 8,
                    "lkr_eur": [350] * 8,
                    "lkr_gbp": [380] * 8,
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        fx_curve = result["scenario_result"]["fx_curve"]

        assert fx_curve["lkr_eur"] is not None
        assert fx_curve["lkr_gbp"] is not None


class TestFXPipelineIntegrationWithoutConfig:
    """Test pipeline gracefully degrades when FX config absent."""

    def test_pipeline_without_fx_config(self) -> None:
        """Pipeline works without FX config; FX fields are None."""
        config = {
            "scenario_name": "test_without_fx",
            "Project": {
                "name": "NoFXProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            # No FX section
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        scenario_result_dict = result["scenario_result"]

        # Verify FX fields are None (or absent)
        assert scenario_result_dict.get("fx_block") is None, \
            "fx_block should be None when FX config absent"
        assert scenario_result_dict.get("fx_curve") is None, \
            "fx_curve should be None"
        assert scenario_result_dict.get("fx_risk_profile") is None, \
            "fx_risk_profile should be None"

        # Verify rest of pipeline still works
        assert "kpis" in result
        assert "debt_result" in result
        assert len(result["annual_rows"]) > 0

    def test_pipeline_with_empty_fx_section(self) -> None:
        """Pipeline treats empty FX section as no FX (graceful fallback)."""
        config = {
            "scenario_name": "test_empty_fx",
            "Project": {
                "name": "EmptyFXProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {},  # Empty FX section
        }

        # Should not crash; will fail silently or populate with defaults
        result = run_v14_pipeline(config=config, validation_mode="off")
        assert result is not None


class TestFXPipelineIntegrationErrors:
    """Test pipeline error handling for invalid FX configs."""

    def test_pipeline_with_curve_length_mismatch(self) -> None:
        """Pipeline raises ValueError if curve length != years."""
        config = {
            "scenario_name": "test_curve_mismatch",
            "Project": {
                "name": "CurveMismatchProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "curve": {
                    "lkr_usd": [300, 302, 305],  # Only 3 rates, but 10 years
                },
            },
        }

        with pytest.raises(ValueError, match="lkr_usd length"):
            run_v14_pipeline(config=config, validation_mode="off")

    def test_pipeline_with_optional_curve_length_mismatch(self) -> None:
        """Pipeline raises ValueError if optional curve has wrong length."""
        config = {
            "scenario_name": "test_optional_curve_mismatch",
            "Project": {
                "name": "OptionalCurveMismatchProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "curve": {
                    "lkr_usd": [300] * 10,  # Correct length
                    "lkr_cny": [42, 42.5],  # Wrong length (only 2)
                },
            },
        }

        with pytest.raises(ValueError, match="lkr_cny length"):
            run_v14_pipeline(config=config, validation_mode="off")

    def test_pipeline_with_malformed_config_structure(self) -> None:
        """Pipeline handles malformed config gracefully (defaults used)."""
        config = {
            "scenario_name": "test_malformed_config",
            "Project": {
                "name": "MalformedProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 10,
                "construction_years": 2,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 8,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": "invalid_strategy",  # Invalid strategy
                "curve": {
                    "lkr_usd": [300] * 10,
                },
            },
        }

        # Should not crash; invalid strategy defaults to 'blended'
        result = run_v14_pipeline(config=config, validation_mode="off")
        fx_block = result["scenario_result"]["fx_block"]
        assert fx_block["strategy"] == "blended"  # Default fallback


class TestFXPipelineScenarioResultIntegration:
    """Test FX fields in ScenarioResult serialization."""

    def test_scenario_result_dict_has_fx_fields(self) -> None:
        """ScenarioResult.fx_* fields appear in asdict() output."""
        config = {
            "scenario_name": "test_fx_result_dict",
            "Project": {
                "name": "FXResultProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 5,
                "construction_years": 1,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 4,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": "hedged",
                "curve": {
                    "lkr_usd": [300, 302, 305, 310, 315],
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        scenario_result_dict = result["scenario_result"]

        # Check keys present
        assert "fx_block" in scenario_result_dict
        assert "fx_curve" in scenario_result_dict
        assert "fx_risk_profile" in scenario_result_dict

        # Verify nested structure is JSON-serializable (dict)
        assert isinstance(scenario_result_dict["fx_block"], dict)
        assert isinstance(scenario_result_dict["fx_curve"], dict)
        assert isinstance(scenario_result_dict["fx_risk_profile"], dict)

        # Verify nested keys
        fx_block = scenario_result_dict["fx_block"]
        assert "strategy" in fx_block
        assert "volumetry" in fx_block
        assert "debt_tranches" in fx_block
        assert "fx_match_ratio" in fx_block

        fx_curve = scenario_result_dict["fx_curve"]
        assert "years" in fx_curve
        assert "lkr_usd" in fx_curve
        assert "source" in fx_curve

        fx_risk = scenario_result_dict["fx_risk_profile"]
        assert "var_95_usd_million" in fx_risk
        assert "cvar_95_usd_million" in fx_risk
        assert "debt_lkr_pct" in fx_risk

    def test_fx_fields_roundtrip_through_asdict(self) -> None:
        """FX fields survive ScenarioResult.asdict() conversion."""
        config = {
            "scenario_name": "test_roundtrip",
            "Project": {
                "name": "RoundtripProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 5,
                "construction_years": 1,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 4,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "fx_match_ratio": 75,
                "curve": {
                    "lkr_usd": [300] * 5,
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        sr_dict = result["scenario_result"]

        # Verify FX config made it through
        assert sr_dict["fx_block"]["fx_match_ratio"] == 75.0
        assert sr_dict["fx_curve"]["lkr_usd"] == [300.0] * 5


class TestFXPipelineLogging:
    """Test logging output during FX pipeline integration."""

    def test_pipeline_logs_fx_integration(self, caplog: pytest.LogCaptureFixture) -> None:
        """Pipeline logs FX integration completion."""
        import logging
        caplog.set_level(logging.INFO)

        config = {
            "scenario_name": "test_logging",
            "Project": {
                "name": "LoggingProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 5,
                "construction_years": 1,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 4,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": "natural_hedge",
                "curve": {
                    "lkr_usd": [300] * 5,
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")

        # Check for FX integration log messages
        log_text = caplog.text
        assert "FX" in log_text or "fx" in log_text or "integration" in log_text


# Parametrized edge cases
class TestFXPipelineParametrized:
    """Parametrized tests for FX configurations."""

    @pytest.mark.parametrize(
        "strategy,fx_match,hedging",
        [
            ("natural_hedge", 0.0, 0.0),
            ("fixed_ccy", 50.0, 100.0),
            ("hedged", 75.0, 50.0),
            ("blended", 25.0, 25.0),
        ],
    )
    def test_fx_strategies(
        self,
        strategy: str,
        fx_match: float,
        hedging: float,
    ) -> None:
        """Pipeline handles all FX strategies correctly."""
        config = {
            "scenario_name": f"test_{strategy}",
            "Project": {
                "name": "StrategyTestProject",
                "capex_usd": 100_000_000,
                "opex_usd_yr": 5_000_000,
                "project_life_years": 5,
                "construction_years": 1,
            },
            "Financing_Terms": {
                "total_debt_usd": 70_000_000,
                "debt_tenor_years": 4,
                "rates": {
                    "usd_commercial_min": 0.08,
                },
            },
            "FX": {
                "strategy": strategy,
                "fx_match_ratio": fx_match,
                "hedging_coverage_pct": hedging,
                "curve": {
                    "lkr_usd": [300] * 5,
                },
            },
        }

        result = run_v14_pipeline(config=config, validation_mode="off")
        fx_block = result["scenario_result"]["fx_block"]

        assert fx_block["strategy"] == strategy
        assert fx_block["fx_match_ratio"] == fx_match
        assert fx_block["hedging_coverage_pct"] == hedging


__all__ = [
    "TestFXPipelineIntegrationWithConfig",
    "TestFXPipelineIntegrationWithoutConfig",
    "TestFXPipelineIntegrationErrors",
    "TestFXPipelineScenarioResultIntegration",
    "TestFXPipelineLogging",
    "TestFXPipelineParametrized",
]

# EOF - tests/test_fx_pipeline_integration.py
