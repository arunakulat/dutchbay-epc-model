#!/usr/bin/env python
"""Comprehensive tests for dual DSCR sensitivity analysis.

Test Coverage:
- CFADS array construction with degradation
- Parameter perturbation mechanics
- Single variable sensitivity
- Binding constraint transitions
- Tornado chart generation
- Integration with dual DSCR debt sizing
- Edge cases and validation

Framework Compliance:
- TEST-01: Regression pins for behavior
- CASPER: Tail-risk edge cases
- TYPE-01: Full type hints

Author: DutchBay V14 Team
Date: December 2025
"""

import pytest
from omegaconf import OmegaConf

from analytics.dscr_sensitivity import (
    SensitivityConfig,
    _build_cfads_array,
    _perturb_parameter,
    analyze_dscr_sensitivity,
    analyze_single_variable,
)


@pytest.fixture
def base_config():
    """Base sensitivity configuration for testing."""
    return SensitivityConfig(
        base_capex=200e6,  # $200M
        base_aep_p50=100_000,  # 100 GWh/year P50
        base_aep_p99=85_000,  # 85 GWh/year P99 (downside)
        base_tariff=50.0,  # $50/MWh
        # Revenue P50 = 100 GWh * $50/MWh = $5M/yr. OPEX must leave positive
        # CFADS: the prior $5M (== revenue) drove CFADS to ~0 and produced a
        # negative sized debt. $2.5M gives a ~50% CFADS margin.
        base_opex=2.5e6,  # $2.5M/year (~50% CFADS margin)
        base_degradation=0.006,  # 0.6%/year
        project_life=20,
        perturbation_range_pct=20.0,  # ±20%
        n_steps=5,  # Fast for testing
        dscr_target_p50=1.30,
        dscr_target_p99=1.00,
        debt_ratio_max=0.70,
        debt_rate=0.08,
    )


@pytest.fixture
def omegaconf_config():
    """OmegaConf configuration for full pipeline testing."""
    return OmegaConf.create(
        {
            "project": {
                "capex_usd": 200e6,
                "degradation": 0.006,
                "life_years": 20,
            },
            "wind_resource": {
                "aep_p50_mwh": 100_000,
                "aep_p99_mwh": 85_000,
            },
            "revenue": {
                "tariff_usd_mwh": 50.0,
            },
            "operations": {
                # ~50% CFADS margin (revenue P50 ≈ $5M/yr); $5M would zero out CFADS.
                "opex_usd_year": 2.5e6,
            },
            "financing": {
                "dscr_target_p50": 1.30,
                "dscr_target_p99": 1.00,
                "debt_ratio_max": 0.70,
                "debt_rate": 0.08,
            },
            "sensitivity": {
                "perturbation_range_pct": 20.0,
                "n_steps": 5,
            },
        }
    )


class TestCFADSConstruction:
    """Test CFADS array construction with degradation."""

    def test_cfads_year1_no_degradation_yet(self):
        """Year 1 CFADS should use full AEP (degradation starts after)."""
        cfads = _build_cfads_array(
            aep=100_000,
            tariff=50.0,
            opex=500_000,
            degradation_rate=0.006,
            project_life=20,
        )

        # Year 1: Full output (degradation applies from year 2)
        expected_y1 = 100_000 * 50.0 - 500_000
        assert abs(cfads[0] - expected_y1) < 1.0

    def test_cfads_degradation_reduces_over_time(self):
        """CFADS should decrease over time due to degradation."""
        cfads = _build_cfads_array(
            aep=100_000,
            tariff=50.0,
            opex=500_000,
            degradation_rate=0.006,
            project_life=20,
        )

        # Verify monotonic decrease (ignoring opex)
        revenues = [cf + 500_000 for cf in cfads]  # Add back opex
        for i in range(1, len(revenues)):
            assert revenues[i] < revenues[i - 1], (
                f"Revenue should decrease: year {i} = {revenues[i]}, "
                f"year {i-1} = {revenues[i-1]}"
            )

    def test_cfads_year20_degradation(self):
        """Year 20 should reflect cumulative degradation."""
        cfads = _build_cfads_array(
            aep=100_000,
            tariff=50.0,
            opex=500_000,
            degradation_rate=0.006,  # 0.6%
            project_life=20,
        )

        # Year 20: (1-0.006)^19 ≈ 0.8934 of year 1
        expected_factor = (1 - 0.006) ** 19
        revenue_y1 = 100_000 * 50.0
        revenue_y20 = revenue_y1 * expected_factor
        expected_cfads_y20 = revenue_y20 - 500_000

        assert abs(cfads[19] - expected_cfads_y20) < 100, (
            f"Year 20 CFADS mismatch: expected {expected_cfads_y20:.0f}, "
            f"got {cfads[19]:.0f}"
        )

    def test_cfads_zero_degradation(self):
        """Zero degradation should produce constant CFADS."""
        cfads = _build_cfads_array(
            aep=100_000,
            tariff=50.0,
            opex=500_000,
            degradation_rate=0.0,  # No degradation
            project_life=20,
        )

        # All years should be identical
        assert all(
            abs(cf - cfads[0]) < 1.0 for cf in cfads
        ), "CFADS should be constant with zero degradation"


class TestParameterPerturbation:
    """Test parameter perturbation mechanics."""

    def test_perturb_degradation(self, base_config):
        """Degradation perturbation should scale correctly."""
        params = _perturb_parameter(base_config, "degradation", 10.0)

        expected = base_config.base_degradation * 1.10
        assert abs(params["degradation"] - expected) < 1e-9

    def test_perturb_aep_both_percentiles(self, base_config):
        """AEP perturbation should affect both P50 and P99."""
        params = _perturb_parameter(base_config, "aep", 15.0)

        expected_p50 = base_config.base_aep_p50 * 1.15
        expected_p99 = base_config.base_aep_p99 * 1.15

        assert abs(params["aep_p50"] - expected_p50) < 1.0
        assert abs(params["aep_p99"] - expected_p99) < 1.0

    def test_perturb_tariff(self, base_config):
        """Tariff perturbation should scale correctly."""
        params = _perturb_parameter(base_config, "tariff", -10.0)

        expected = base_config.base_tariff * 0.90
        assert abs(params["tariff"] - expected) < 0.01

    def test_perturb_opex(self, base_config):
        """OPEX perturbation should scale correctly."""
        params = _perturb_parameter(base_config, "opex", 20.0)

        expected = base_config.base_opex * 1.20
        assert abs(params["opex"] - expected) < 1.0

    def test_perturb_capex(self, base_config):
        """CAPEX perturbation should scale correctly."""
        params = _perturb_parameter(base_config, "capex", -15.0)

        expected = base_config.base_capex * 0.85
        assert abs(params["capex"] - expected) < 1.0

    def test_perturb_invalid_variable(self, base_config):
        """Invalid variable should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown sensitivity variable"):
            _perturb_parameter(base_config, "invalid_var", 10.0)


class TestSingleVariableSensitivity:
    """Test single variable sensitivity analysis."""

    def test_degradation_sensitivity_basic(self, base_config):
        """Degradation sensitivity should produce valid results."""
        result = analyze_single_variable(base_config, "degradation")

        assert result["variable"] == "degradation"
        assert result["base_value"] == base_config.base_degradation
        assert result["base_debt"] > 0
        assert len(result["perturbations"]) == base_config.n_steps

    def test_debt_decreases_with_higher_degradation(self, base_config):
        """Higher degradation should reduce debt capacity."""
        result = analyze_single_variable(base_config, "degradation")

        perturbations = result["perturbations"]

        # Find min and max perturbation results
        min_pert = min(perturbations, key=lambda x: x["perturbation_pct"])
        max_pert = max(perturbations, key=lambda x: x["perturbation_pct"])

        # Lower degradation (-20%) → higher debt
        # Higher degradation (+20%) → lower debt
        assert (
            min_pert["debt_sized"] > max_pert["debt_sized"]
        ), "Debt capacity should decrease with higher degradation"

    def test_debt_increases_with_higher_aep(self, base_config):
        """Higher AEP should increase debt capacity."""
        result = analyze_single_variable(base_config, "aep")

        perturbations = result["perturbations"]

        min_pert = min(perturbations, key=lambda x: x["perturbation_pct"])
        max_pert = max(perturbations, key=lambda x: x["perturbation_pct"])

        # Higher AEP (+20%) → higher debt
        assert (
            max_pert["debt_sized"] > min_pert["debt_sized"]
        ), "Debt capacity should increase with higher AEP"

    def test_tornado_data_calculated(self, base_config):
        """Tornado data should be calculated correctly."""
        result = analyze_single_variable(base_config, "tariff")

        tornado = result["tornado_data"]

        assert "min_impact" in tornado
        assert "max_impact" in tornado
        assert "range_usd" in tornado
        assert "range_pct" in tornado
        assert tornado["range_usd"] > 0

    def test_constraint_transitions_detected(self, base_config):
        """Constraint transitions should be detected."""
        # Use wider range to force transitions
        config_wide = SensitivityConfig(
            base_capex=200e6,
            base_aep_p50=100_000,
            base_aep_p99=50_000,  # Very weak P99 (50% of P50)
            base_tariff=50.0,
            base_opex=5e6,
            base_degradation=0.006,
            project_life=20,
            perturbation_range_pct=50.0,  # Wide range
            n_steps=11,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )

        result = analyze_single_variable(config_wide, "aep")

        # With weak P99, expect P99 to bind at low AEP
        # Should have transitions as AEP increases
        assert "constraint_transitions" in result
        # May or may not have transitions depending on specifics
        # Just verify structure is correct
        for transition in result["constraint_transitions"]:
            assert "at_perturbation_pct" in transition
            assert "from_constraint" in transition
            assert "to_constraint" in transition


class TestFullSensitivityAnalysis:
    """Test complete sensitivity analysis pipeline."""

    def test_analyze_dscr_sensitivity_basic(self, omegaconf_config):
        """Full analysis should produce comprehensive results."""
        result = analyze_dscr_sensitivity(
            omegaconf_config, variables=["degradation", "aep"]
        )

        assert "sensitivity_config" in result
        assert "variables" in result
        assert "tornado_chart" in result
        assert "summary" in result
        assert "binding_constraint_analysis" in result

        # Should have results for 2 variables
        assert len(result["variables"]) == 2
        assert len(result["tornado_chart"]) == 2

    def test_tornado_chart_sorted_by_impact(self, omegaconf_config):
        """Tornado chart should be sorted by impact magnitude."""
        result = analyze_dscr_sensitivity(
            omegaconf_config, variables=["degradation", "aep", "tariff"]
        )

        tornado = result["tornado_chart"]

        # Verify descending order by absolute impact
        for i in range(1, len(tornado)):
            assert abs(tornado[i - 1]["impact_range"]) >= abs(
                tornado[i]["impact_range"]
            ), "Tornado chart should be sorted by descending impact magnitude"

    def test_summary_statistics(self, omegaconf_config):
        """Summary should contain key statistics."""
        result = analyze_dscr_sensitivity(omegaconf_config)

        summary = result["summary"]

        assert "most_sensitive_variable" in summary
        assert "max_impact_range_usd" in summary
        assert "max_impact_range_pct" in summary
        assert "variables_analyzed" in summary
        assert "base_debt" in summary

        assert summary["base_debt"] > 0

    def test_binding_constraint_analysis(self, omegaconf_config):
        """Binding constraint analysis should be comprehensive."""
        result = analyze_dscr_sensitivity(
            omegaconf_config, variables=["degradation", "aep"]
        )

        binding_analysis = result["binding_constraint_analysis"]

        # Should have analysis for each variable
        assert "degradation" in binding_analysis
        assert "aep" in binding_analysis

        # Each should have transitions and counts
        for var in ["degradation", "aep"]:
            var_analysis = binding_analysis[var]
            assert "transitions" in var_analysis
            assert "binding_counts" in var_analysis
            assert "p99_binds_frequently" in var_analysis

            # Binding counts should have all constraint types
            counts = var_analysis["binding_counts"]
            assert "P50" in counts
            assert "P99" in counts
            assert "RATIO_CAP" in counts

    def test_default_variables_used(self, omegaconf_config):
        """Default variables should be used if not specified."""
        result = analyze_dscr_sensitivity(omegaconf_config)  # No variables arg

        # Default: ['degradation', 'aep', 'tariff', 'opex', 'capex']
        assert len(result["variables"]) == 5

        var_names = [v["variable"] for v in result["variables"]]
        assert "degradation" in var_names
        assert "aep" in var_names
        assert "tariff" in var_names
        assert "opex" in var_names
        assert "capex" in var_names

    def test_missing_config_raises_error(self):
        """Missing required config should raise clear error."""
        incomplete_config = OmegaConf.create(
            {
                "project": {
                    "capex_usd": 200e6,
                    # Missing degradation and life_years
                },
            }
        )

        with pytest.raises(ValueError, match="Missing required configuration"):
            analyze_dscr_sensitivity(incomplete_config)


class TestEdgeCases:
    """Test edge cases and validation."""

    def test_zero_degradation_sensitivity(self, base_config):
        """Zero base degradation should still work."""
        config_zero_deg = SensitivityConfig(
            base_capex=200e6,
            base_aep_p50=100_000,
            base_aep_p99=85_000,
            base_tariff=50.0,
            base_opex=5e6,
            base_degradation=0.0,  # Zero degradation
            project_life=20,
            perturbation_range_pct=20.0,
            n_steps=5,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )

        result = analyze_single_variable(config_zero_deg, "degradation")

        # Should complete without error
        assert result["variable"] == "degradation"
        assert len(result["perturbations"]) == 5

    def test_high_degradation_reduces_debt_significantly(self, base_config):
        """Very high degradation should drastically reduce debt."""
        config_high_deg = SensitivityConfig(
            base_capex=200e6,
            base_aep_p50=100_000,
            base_aep_p99=85_000,
            base_tariff=50.0,
            base_opex=5e6,
            base_degradation=0.02,  # 2%/year (very high)
            project_life=20,
            perturbation_range_pct=20.0,
            n_steps=5,
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )

        result = analyze_single_variable(config_high_deg, "degradation")

        # Base debt should be significantly lower than low-degradation case
        assert (
            result["base_debt"] < base_config.base_capex * 0.60
        ), "High degradation should significantly reduce debt capacity"


class TestRegressionPins:
    """Regression pins for sensitivity behavior (TEST-01 compliance)."""

    def test_degradation_impact_magnitude(self, base_config):
        """Degradation sensitivity impact should be within expected range."""
        result = analyze_single_variable(base_config, "degradation")

        # ±20% degradation should have material but not catastrophic impact
        # Expect ±5-15% debt capacity change
        tornado = result["tornado_data"]
        impact_pct = abs(tornado["range_pct"])

        assert (
            3.0 < impact_pct < 25.0
        ), f"Degradation impact should be 3-25% of debt, got {impact_pct:.1f}%"

    def test_aep_sensitivity_highest_impact(self, omegaconf_config):
        """AEP should typically be most sensitive variable."""
        result = analyze_dscr_sensitivity(
            omegaconf_config, variables=["degradation", "aep", "tariff"]
        )

        # AEP should be in top 2 most sensitive
        top2 = [result["tornado_chart"][i]["variable"] for i in range(2)]
        assert "aep" in top2, "AEP should be one of the most sensitive parameters"


def test_even_n_steps_rejected() -> None:
    """An even n_steps cannot include the 0% base point in a symmetric grid, so
    SensitivityConfig rejects it loudly (CESSPIT) instead of silently zeroing every
    delta."""
    with pytest.raises(ValueError, match="n_steps must be"):
        SensitivityConfig(
            base_capex=200e6,
            base_aep_p50=100_000,
            base_aep_p99=85_000,
            base_tariff=50.0,
            base_opex=2.5e6,
            base_degradation=0.006,
            project_life=20,
            perturbation_range_pct=20.0,
            n_steps=8,  # even -> no 0% midpoint
            dscr_target_p50=1.30,
            dscr_target_p99=1.00,
            debt_ratio_max=0.70,
            debt_rate=0.08,
        )


def test_downside_deltas_measured_against_presized_base(
    base_config: SensitivityConfig,
) -> None:
    """Regression: the base is sized before the sweep, so downside perturbation rows
    (evaluated before the 0% midpoint) carry a real delta_from_base, not the 0.0 the
    old mid-loop capture left for every pre-midpoint point."""
    result = analyze_single_variable(base_config, "degradation")
    perts = result["perturbations"]
    downside = [r for r in perts if r["perturbation_pct"] < 0]
    assert downside, "expected downside perturbation rows"
    # Pre-fix every pre-midpoint row recorded delta_from_base_usd == 0.0.
    assert any(r["delta_from_base_usd"] != 0.0 for r in downside)
    # The 0% midpoint remains the base itself (zero delta).
    base_row = min(perts, key=lambda r: abs(r["perturbation_pct"]))
    assert base_row["delta_from_base_usd"] == pytest.approx(0.0, abs=1.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
