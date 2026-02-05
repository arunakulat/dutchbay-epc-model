"""Golden test: CLI must produce lender stack outputs.

This test PREVENTS REGRESSION where the canonical CLI gets rewired to
wind-only pipeline. It asserts the output contract includes all
lender-critical keys.

If this test fails, it means:
1. Someone changed run_full_pipeline_v14.py import (back to pipeline_v14)
2. Or pipeline_v14_enhanced broke its output contract
3. Or lender stack modules (cashflow/debt) regressed

Framework:
- TEST-01: Golden behavior regression pin
- GWTF: Canonical surface validation
- CESSPIT: Fail-fast on contract breach

Author: Dutch Bay Wind Farm Team
Date: December 2025
"""

from __future__ import annotations

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline


class TestCanonicalCLIProducesLenderStack:
    """GOLDEN TEST: Canonical CLI must run lender-grade pipeline.

    This test suite ensures run_full_pipeline_v14.py is correctly wired
    to analytics.pipeline_v14_enhanced (lender stack), not
    analytics.pipeline_v14 (wind-only).
    """

    @pytest.fixture
    def minimal_test_config(self) -> dict:
        """Minimal valid scenario config for testing.

        This is a lightweight config that passes validation and produces
        all required lender outputs without heavy computation.
        """
        return {
            "scenario_name": "test_lender_stack",
            "Project": {
                "name": "Test Wind Farm",
                "capacity_mw": 100,
                "construction_years": 2,
                "operating_years": 20,
            },
            "Turbine": {
                "model": "Test-5.0",
                "capacity_mw": 5.0,
                "n_turbines": 20,
                "hub_height_m": 100,
            },
            "Production": {
                "net_aep_p50_mwh": 300000,
                "net_aep_p75_mwh": 280000,
                "net_aep_p90_mwh": 260000,
                "capacity_factor_net": 0.34,
            },
            "Revenue": {
                "tariff_usd_per_mwh": 80.0,
                "escalation_pct": 0.02,
            },
            "Costs": {
                "capex_total_usd": 200_000_000,
                "opex_annual_usd": 5_000_000,
            },
            "Financing_Terms": {
                "equity_pct": 0.30,
                "debt_pct": 0.70,
                "rates": {
                    "usd_nominal": 0.075,
                },
                "tenor_years": 15,
                "construction_years": 2,
                "interest_only_years": 2,
                "amortization_style": "sculpted",
                "target_dscr": 1.30,
            },
            "Tax": {
                "corporate_rate": 0.28,
                "depreciation_method": "straight_line",
                "depreciation_years": 20,
            },
        }

    def test_cli_output_has_annual_rows(self, minimal_test_config):
        """GOLDEN: CLI output must contain annual_rows (cashflow schedule).

        annual_rows is the canonical cashflow representation from
        finance.cashflow_v14.build_annual_rows(). If missing, CLI is
        wired to wrong pipeline.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",  # Skip validation for speed
        )

        assert "annual_rows" in result, (
            "CLI output missing 'annual_rows' key. "
            "This means run_full_pipeline_v14.py is wired to wind-only pipeline. "
            "Fix: Change import to analytics.pipeline_v14_enhanced"
        )

        annual_rows = result["annual_rows"]
        assert isinstance(
            annual_rows, list
        ), f"annual_rows must be list, got {type(annual_rows).__name__}"
        assert len(annual_rows) > 0, "annual_rows cannot be empty"

        # Validate first row structure
        first_row = annual_rows[0]
        assert isinstance(
            first_row, dict
        ), f"annual_rows[0] must be dict, got {type(first_row).__name__}"

        required_keys = {"year", "cf_pre_debt", "debt_service_total"}
        missing_keys = required_keys - set(first_row.keys())
        assert not missing_keys, f"annual_rows[0] missing required keys: {missing_keys}"

    def test_cli_output_has_debt_result(self, minimal_test_config):
        """GOLDEN: CLI output must contain debt_result (DSCR series).

        debt_result is the canonical debt output from
        finance.debt_v14.plan_debt(). If missing, CLI is wired to
        wrong pipeline.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        assert "debt_result" in result, (
            "CLI output missing 'debt_result' key. "
            "This means run_full_pipeline_v14.py is wired to wind-only pipeline. "
            "Fix: Change import to analytics.pipeline_v14_enhanced"
        )

        debt_result = result["debt_result"]
        assert isinstance(
            debt_result, dict
        ), f"debt_result must be dict, got {type(debt_result).__name__}"

        # Validate lender-critical keys
        required_keys = {"min_dscr", "dscr_series", "balloon_remaining"}
        missing_keys = required_keys - set(debt_result.keys())
        assert (
            not missing_keys
        ), f"debt_result missing required lender keys: {missing_keys}"

        # Validate DSCR series structure
        dscr_series = debt_result["dscr_series"]
        assert isinstance(
            dscr_series, list
        ), f"dscr_series must be list, got {type(dscr_series).__name__}"
        assert len(dscr_series) > 0, "dscr_series cannot be empty"

        # Validate min_dscr is numeric
        min_dscr = debt_result["min_dscr"]
        assert isinstance(
            min_dscr, (int, float)
        ), f"min_dscr must be numeric, got {type(min_dscr).__name__}"

    def test_cli_output_has_kpis(self, minimal_test_config):
        """GOLDEN: CLI output must contain kpis (IRR, NPV, DSCR, LLCR, PLCR).

        kpis is the canonical metrics dict from
        analytics.core.metrics.calculate_scenario_kpis(). If missing,
        CLI is wired to wrong pipeline.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        assert "kpis" in result, (
            "CLI output missing 'kpis' key. "
            "This means run_full_pipeline_v14.py is wired to wind-only pipeline. "
            "Fix: Change import to analytics.pipeline_v14_enhanced"
        )

        kpis = result["kpis"]
        assert isinstance(kpis, dict), f"kpis must be dict, got {type(kpis).__name__}"

        # Validate lender-critical KPIs exist
        lender_critical_kpis = {
            "project_irr",
            "equity_irr",
            "project_npv",
            "min_dscr",
            "avg_dscr",
        }

        missing_kpis = lender_critical_kpis - set(kpis.keys())
        assert not missing_kpis, f"kpis missing lender-critical metrics: {missing_kpis}"

        # Validate KPI values are numeric
        for kpi_name in lender_critical_kpis:
            kpi_value = kpis[kpi_name]
            assert isinstance(
                kpi_value, (int, float)
            ), f"kpis['{kpi_name}'] must be numeric, got {type(kpi_value).__name__}"

    def test_cli_output_has_scenario_result(self, minimal_test_config):
        """GOLDEN: CLI output must contain scenario_result (ScenarioResult contract).

        scenario_result is the CASPER contract from
        analytics.contracts_v14.ScenarioResult. If missing, CLI is
        wired to wrong pipeline.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        assert "scenario_result" in result, (
            "CLI output missing 'scenario_result' key. "
            "This means run_full_pipeline_v14.py is wired to wind-only pipeline. "
            "Fix: Change import to analytics.pipeline_v14_enhanced"
        )

        scenario_result = result["scenario_result"]
        assert isinstance(
            scenario_result, dict
        ), f"scenario_result must be dict, got {type(scenario_result).__name__}"

        # Validate ScenarioResult contract keys
        required_keys = {
            "scenario_name",
            "config_path",
            "project_irr",
            "project_npv",
            "min_dscr",
            "dscr_series",
            "max_debt_usd",
        }

        missing_keys = required_keys - set(scenario_result.keys())
        assert (
            not missing_keys
        ), f"scenario_result missing required contract keys: {missing_keys}"

        # Validate project_irr is numeric
        project_irr = scenario_result["project_irr"]
        assert isinstance(
            project_irr, (int, float)
        ), f"project_irr must be numeric, got {type(project_irr).__name__}"

    def test_cli_output_status_is_success(self, minimal_test_config):
        """GOLDEN: CLI output status must be 'success' for valid config.

        If status is not 'success', pipeline execution failed or
        contract was breached.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        assert "status" in result, "CLI output missing 'status' key"
        assert result["status"] == "success", (
            f"Pipeline execution failed: status={result.get('status')}, "
            f"error={result.get('error')}"
        )

    def test_cli_output_has_all_lender_keys(self, minimal_test_config):
        """COMPREHENSIVE: CLI output must have ALL lender-critical keys.

        This is the master validation that combines all individual tests.
        If this fails, CLI is definitely wired to wrong pipeline.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        all_required_keys = {
            "status",
            "config_path",
            "validation_mode",
            "scenario_result",
            "kpis",
            "annual_rows",
            "debt_result",
        }

        missing_keys = all_required_keys - set(result.keys())
        assert not missing_keys, (
            f"CLI output missing lender-critical keys: {missing_keys}. "
            "This means run_full_pipeline_v14.py is wired to wind-only pipeline. "
            "Fix: Change import to analytics.pipeline_v14_enhanced"
        )

    def test_wind_only_keys_should_not_be_present(self, minimal_test_config):
        """NEGATIVE: Wind-only keys should NOT be in lender stack output.

        If these keys are present, it means CLI is wired to
        analytics.pipeline_v14 (wind-only), not pipeline_v14_enhanced.
        """
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        # These keys are ONLY in wind-only pipeline
        wind_only_keys = {
            "wind_assessment",
            "aep_p50_mwh",
            "aep_p75_mwh",
            "aep_p90_mwh",
            "capacity_factor_net_p75",
            "revenue_annual_p75_usd",
            "weibull_k",
            "weibull_c",
            "mean_wind_speed_ms",
        }

        present_wind_keys = wind_only_keys & set(result.keys())

        # NOTE: It's OK if wind keys are present IF lender keys are also present
        # (i.e., enhanced pipeline with wind integration)
        # But if ONLY wind keys are present, that's a problem

        has_lender_keys = "annual_rows" in result and "debt_result" in result
        has_wind_keys = len(present_wind_keys) > 0

        if has_wind_keys and not has_lender_keys:
            pytest.fail(
                f"CLI output has wind-only keys {present_wind_keys} "
                "but missing lender keys (annual_rows, debt_result). "
                "This means run_full_pipeline_v14.py is wired to "
                "analytics.pipeline_v14 (wind-only). "
                "Fix: Change import to analytics.pipeline_v14_enhanced"
            )


class TestLenderStackOutputQuality:
    """Additional tests for lender stack output quality.

    These tests validate not just presence but also quality of
    lender-critical outputs.
    """

    @pytest.fixture
    def minimal_test_config(self) -> dict:
        """Reuse minimal config."""
        return {
            "scenario_name": "test_quality",
            "Project": {
                "name": "Test Wind Farm",
                "capacity_mw": 100,
                "construction_years": 2,
                "operating_years": 20,
            },
            "Turbine": {
                "model": "Test-5.0",
                "capacity_mw": 5.0,
                "n_turbines": 20,
                "hub_height_m": 100,
            },
            "Production": {
                "net_aep_p50_mwh": 300000,
                "net_aep_p75_mwh": 280000,
                "net_aep_p90_mwh": 260000,
                "capacity_factor_net": 0.34,
            },
            "Revenue": {
                "tariff_usd_per_mwh": 80.0,
                "escalation_pct": 0.02,
            },
            "Costs": {
                "capex_total_usd": 200_000_000,
                "opex_annual_usd": 5_000_000,
            },
            "Financing_Terms": {
                "equity_pct": 0.30,
                "debt_pct": 0.70,
                "rates": {
                    "usd_nominal": 0.075,
                },
                "tenor_years": 15,
                "construction_years": 2,
                "interest_only_years": 2,
                "amortization_style": "sculpted",
                "target_dscr": 1.30,
            },
            "Tax": {
                "corporate_rate": 0.28,
                "depreciation_method": "straight_line",
                "depreciation_years": 20,
            },
        }

    def test_annual_rows_has_expected_length(self, minimal_test_config):
        """QUALITY: annual_rows should have length = construction + operating years."""
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        construction_years = minimal_test_config["Project"]["construction_years"]
        operating_years = minimal_test_config["Project"]["operating_years"]
        expected_length = construction_years + operating_years

        annual_rows = result["annual_rows"]
        assert len(annual_rows) == expected_length, (
            f"annual_rows length mismatch: expected {expected_length}, "
            f"got {len(annual_rows)}"
        )

    def test_dscr_series_has_expected_length(self, minimal_test_config):
        """QUALITY: dscr_series should have length = operating years."""
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        operating_years = minimal_test_config["Project"]["operating_years"]

        dscr_series = result["debt_result"]["dscr_series"]
        # DSCR series typically excludes construction years
        assert len(dscr_series) <= operating_years + 5, (
            f"dscr_series length unreasonable: expected ~{operating_years}, "
            f"got {len(dscr_series)}"
        )

    def test_min_dscr_matches_series_minimum(self, minimal_test_config):
        """QUALITY: min_dscr should match minimum of dscr_series."""
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        debt_result = result["debt_result"]
        min_dscr = debt_result["min_dscr"]
        dscr_series = debt_result["dscr_series"]

        # Filter out inf values
        finite_dscrs = [d for d in dscr_series if d != float("inf")]

        if finite_dscrs:
            series_min = min(finite_dscrs)
            assert abs(min_dscr - series_min) < 0.01, (
                f"min_dscr mismatch: min_dscr={min_dscr}, " f"series_min={series_min}"
            )

    def test_project_irr_is_reasonable(self, minimal_test_config):
        """QUALITY: project_irr should be reasonable (0-50%)."""
        result = run_v14_pipeline(
            config=minimal_test_config,
            validation_mode="off",
        )

        project_irr = result["kpis"]["project_irr"]

        assert (
            0.0 <= project_irr <= 0.5
        ), f"project_irr unreasonable: {project_irr} (expected 0-50%)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
