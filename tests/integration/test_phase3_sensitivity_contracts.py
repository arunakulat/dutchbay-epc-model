"""Integration tests for Phase 3 Sensitivity Contracts.

Tests
-----
1. ShockSpec validation (CESSPIT compliance)
2. StandardShockLibrary templates (7 DFI-standard shocks)
3. TaxShockLibrary templates (5 tax-aware shocks)
4. SensitivitySuite export methods (to_dict, to_tornado_dict)
5. Integration with sensitivity_v14.py tornado engine
6. Integration with sensitivity_runner.py lightweight runner

Architecture Compliance
-----------------------
CESSPIT: Tests validate fail-fast contract violations
CCCDIR:  Comprehensive docstrings explain test intent
GWTF:    Type-annotated with expected outcomes
CASPER:  Contract-first testing approach
"""

from __future__ import annotations

import pytest
from datetime import datetime
from typing import Dict, Any

from analytics.contracts import (
    ShockSpec,
    ShockResult,
    SensitivitySuite,
    StandardShockLibrary,
    TaxShockLibrary,
)


# ═════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: ShockSpec Contract Validation (CESSPIT)
# ═════════════════════════════════════════════════════════════════════════════


def test_shock_spec_valid_construction():
    """Test ShockSpec accepts valid inputs."""
    shock = ShockSpec(
        variable_name="capex",
        low_value=180e6,
        high_value=220e6,
        label="CAPEX ±10%",
    )
    
    assert shock.variable_name == "capex"
    assert shock.low_value == 180e6
    assert shock.high_value == 220e6
    assert shock.label == "CAPEX ±10%"


def test_shock_spec_empty_variable_name_fails():
    """Test ShockSpec rejects empty variable_name (CESSPIT)."""
    with pytest.raises(ValueError, match="non-empty string"):
        ShockSpec(
            variable_name="",
            low_value=180e6,
            high_value=220e6,
        )


def test_shock_spec_inverted_range_fails():
    """Test ShockSpec rejects low > high (CESSPIT)."""
    with pytest.raises(ValueError, match="cannot exceed"):
        ShockSpec(
            variable_name="capex",
            low_value=220e6,
            high_value=180e6,
        )


def test_shock_spec_non_numeric_low_value_fails():
    """Test ShockSpec rejects non-numeric low_value (CESSPIT)."""
    with pytest.raises(TypeError, match="must be numeric"):
        ShockSpec(
            variable_name="capex",
            low_value="not_a_number",  # type: ignore
            high_value=220e6,
        )


def test_shock_spec_non_numeric_high_value_fails():
    """Test ShockSpec rejects non-numeric high_value (CESSPIT)."""
    with pytest.raises(TypeError, match="must be numeric"):
        ShockSpec(
            variable_name="capex",
            low_value=180e6,
            high_value="not_a_number",  # type: ignore
        )


def test_shock_spec_immutability():
    """Test ShockSpec is immutable (frozen=True)."""
    shock = ShockSpec("capex", 180e6, 220e6)
    
    with pytest.raises(Exception):  # FrozenInstanceError
        shock.low_value = 200e6  # type: ignore


# ═════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: StandardShockLibrary Templates
# ═════════════════════════════════════════════════════════════════════════════


def test_standard_shock_library_capex_overrun():
    """Test CAPEX overrun shock (±10%)."""
    shock = StandardShockLibrary.capex_overrun(200e6)
    
    assert shock.variable_name == "capex_total"
    assert shock.low_value == pytest.approx(180e6)
    assert shock.high_value == pytest.approx(220e6)
    assert shock.label == "CAPEX ±10%"


def test_standard_shock_library_opex_overrun():
    """Test OPEX overrun shock (±10%)."""
    shock = StandardShockLibrary.opex_overrun(5e6)
    
    assert shock.variable_name == "opex_annual"
    assert shock.low_value == pytest.approx(4.5e6)
    assert shock.high_value == pytest.approx(5.5e6)
    assert shock.label == "OPEX ±10%"


def test_standard_shock_library_interest_rate_rise():
    """Test interest rate shock (±100bps)."""
    shock = StandardShockLibrary.interest_rate_rise(0.08)
    
    assert shock.variable_name == "interest_rate"
    assert shock.low_value == pytest.approx(0.07)
    assert shock.high_value == pytest.approx(0.09)
    assert shock.label == "Interest Rate ±1%"


def test_standard_shock_library_production_shortfall():
    """Test production shortfall shock (±10%)."""
    shock = StandardShockLibrary.production_shortfall(450_000)
    
    assert shock.variable_name == "annual_output"
    assert shock.low_value == pytest.approx(405_000)
    assert shock.high_value == pytest.approx(495_000)
    assert shock.label == "Production ±10%"


def test_standard_shock_library_all_seven_shocks():
    """Test all 7 DFI-standard shocks can be instantiated."""
    shocks = [
        StandardShockLibrary.capex_overrun(200e6),
        StandardShockLibrary.opex_overrun(5e6),
        StandardShockLibrary.interest_rate_rise(0.08),
        StandardShockLibrary.inflation_rate_rise(0.03),
        StandardShockLibrary.production_shortfall(450_000),
        StandardShockLibrary.tariff_reduction(0.08),
        StandardShockLibrary.construction_delay(6),
    ]
    
    assert len(shocks) == 7
    assert all(isinstance(s, ShockSpec) for s in shocks)


# ═════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: TaxShockLibrary Templates
# ═════════════════════════════════════════════════════════════════════════════


def test_tax_shock_library_corporate_tax_rate():
    """Test corporate tax rate shock (±5%)."""
    shock = TaxShockLibrary.corporate_tax_rate(0.28)
    
    assert shock.variable_name == "tax.corporate_rate"
    assert shock.low_value == pytest.approx(0.23)
    assert shock.high_value == pytest.approx(0.33)
    assert "Tax Rate" in shock.label


def test_tax_shock_library_depreciation_method():
    """Test depreciation method categorical shock (0=SL, 1=MACRS)."""
    shock = TaxShockLibrary.depreciation_method()
    
    assert shock.variable_name == "tax.depreciation_method"
    assert shock.low_value == 0.0  # Straight-line
    assert shock.high_value == 1.0  # MACRS
    assert "Depreciation" in shock.label


def test_tax_shock_library_distribution_delay():
    """Test distribution delay shock (±2 years)."""
    shock = TaxShockLibrary.distribution_delay(4)
    
    assert shock.variable_name == "tax.distribution_delay_years"
    assert shock.low_value == 2.0
    assert shock.high_value == 6.0
    assert "Distribution Delay" in shock.label


def test_tax_shock_library_tlcf_carryforward_limit():
    """Test TLCF carryforward limit shock (±5 years)."""
    shock = TaxShockLibrary.tlcf_carryforward_limit(20)
    
    assert shock.variable_name == "tax.tlcf_carryforward_years"
    assert shock.low_value == 15.0
    assert shock.high_value == 25.0
    assert "TLCF Limit" in shock.label


def test_tax_shock_library_salvage_value():
    """Test salvage value shock (±20%)."""
    shock = TaxShockLibrary.salvage_value(10e6)
    
    assert shock.variable_name == "tax.salvage_value"
    assert shock.low_value == pytest.approx(8e6)
    assert shock.high_value == pytest.approx(12e6)
    assert "Salvage Value" in shock.label


def test_tax_shock_library_all_five_shocks():
    """Test all 5 tax-specific shocks can be instantiated."""
    shocks = [
        TaxShockLibrary.corporate_tax_rate(0.28),
        TaxShockLibrary.depreciation_method(),
        TaxShockLibrary.distribution_delay(4),
        TaxShockLibrary.tlcf_carryforward_limit(20),
        TaxShockLibrary.salvage_value(10e6),
    ]
    
    assert len(shocks) == 5
    assert all(isinstance(s, ShockSpec) for s in shocks)


def test_tax_shock_library_inherits_standard_shocks():
    """Test TaxShockLibrary can access StandardShockLibrary methods."""
    # TaxShockLibrary extends StandardShockLibrary
    capex_shock = TaxShockLibrary.capex_overrun(200e6)
    tax_shock = TaxShockLibrary.corporate_tax_rate(0.28)
    
    assert capex_shock.variable_name == "capex_total"
    assert tax_shock.variable_name == "tax.corporate_rate"


# ═════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: SensitivitySuite Export Methods
# ═════════════════════════════════════════════════════════════════════════════


def test_sensitivity_suite_to_dict():
    """Test SensitivitySuite.to_dict() exports complete data."""
    shock_result = ShockResult(
        variable_name="capex",
        label="CAPEX ±10%",
        base_metric=0.15,
        low_metric=0.18,
        high_metric=0.12,
        impact=0.03,
        direction="negative",
        sensitivity=0.20,
    )
    
    suite = SensitivitySuite(
        scenario_name="dutchbay_base",
        metric_name="project_irr",
        base_metric_value=0.15,
        shock_results=[shock_result],
        tornado_ranking=[shock_result],
        analysis_timestamp="2025-12-21T12:00:00",
    )
    
    data = suite.to_dict()
    
    assert data["scenario"] == "dutchbay_base"
    assert data["metric"] == "project_irr"
    assert data["base_value"] == 0.15
    assert len(data["shocks"]) == 1
    assert len(data["tornado"]) == 1
    assert data["tornado"][0]["rank"] == 1


def test_sensitivity_suite_to_tornado_dict():
    """Test SensitivitySuite.to_tornado_dict() exports ranking only."""
    shock_result = ShockResult(
        variable_name="capex",
        label="CAPEX ±10%",
        base_metric=0.15,
        low_metric=0.18,
        high_metric=0.12,
        impact=0.03,
        direction="negative",
        sensitivity=0.20,
    )
    
    suite = SensitivitySuite(
        scenario_name="dutchbay_base",
        metric_name="project_irr",
        base_metric_value=0.15,
        shock_results=[shock_result],
        tornado_ranking=[shock_result],
        analysis_timestamp="2025-12-21T12:00:00",
    )
    
    tornado = suite.to_tornado_dict()
    
    assert tornado["scenario"] == "dutchbay_base"
    assert tornado["metric"] == "project_irr"
    assert tornado["baseline"] == 0.15
    assert len(tornado["ranking"]) == 1
    assert tornado["ranking"][0]["rank"] == 1
    assert tornado["ranking"][0]["variable"] == "capex"


# ═════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Phase 3 Contracts with Ecosystem
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
def test_standard_shock_library_imports_from_contracts_package():
    """Test Phase 3 contracts available via analytics.contracts."""
    # This tests __init__.py export correctness
    from analytics.contracts import (
        ShockSpec,
        StandardShockLibrary,
        TaxShockLibrary,
    )
    
    shock1 = StandardShockLibrary.capex_overrun(200e6)
    shock2 = TaxShockLibrary.corporate_tax_rate(0.28)
    
    assert isinstance(shock1, ShockSpec)
    assert isinstance(shock2, ShockSpec)


@pytest.mark.integration
@pytest.mark.skip(reason="Requires sensitivity_runner.py integration - enable when runner available")
def test_phase3_contracts_work_with_sensitivity_runner():
    """Test Phase 3 contracts integrate with sensitivity_runner.py.
    
    This test validates that ShockSpec contracts can be passed to
    the lightweight sensitivity_runner.py module.
    """
    from analytics.sensitivity_runner import run_sensitivity_analysis
    
    shocks = [
        StandardShockLibrary.capex_overrun(200e6),
        StandardShockLibrary.opex_overrun(5e6),
    ]
    
    suite = run_sensitivity_analysis(
        base_config_path="scenarios/dutchbay_base.yaml",
        shock_specs=shocks,
        metric="project_irr",
    )
    
    assert suite.metric_name == "project_irr"
    assert len(suite.shock_results) >= 2


@pytest.mark.integration
@pytest.mark.skip(reason="Requires sensitivity_v14.py integration - enable when v14 available")
def test_phase3_contracts_work_with_sensitivity_v14():
    """Test Phase 3 contracts integrate with sensitivity_v14.py.
    
    This test validates that StandardShockLibrary templates can seed
    the v14 tornado engine via ParameterRangeConfig conversion.
    """
    from analytics.sensitivity_v14 import run_tornado_sensitivity, SensitivityRequest
    from analytics.contracts_v14 import ParameterRangeConfig
    
    # Convert Phase 3 ShockSpec to v14 ParameterRangeConfig
    capex_shock = StandardShockLibrary.capex_overrun(200e6)
    
    param_config = ParameterRangeConfig(
        variable_name=capex_shock.variable_name,
        base_value=200e6,
        low_pct=-10.0,
        high_pct=10.0,
    )
    
    request = SensitivityRequest(
        base_config_path="scenarios/dutchbay_base.yaml",
        parameters=[param_config],
        metric="project_irr",
    )
    
    suite = run_tornado_sensitivity(request)
    
    assert suite.metric == "project_irr"
    assert len(suite.tornado_results) >= 1


@pytest.mark.integration
@pytest.mark.skip(reason="Requires tax_sensitivity_v14.py - enable when tax module available")
def test_tax_shock_library_works_with_tax_sensitivity_v14():
    """Test TaxShockLibrary integrates with tax_sensitivity_v14.py.
    
    This test validates that tax-specific shocks work with the
    TLCF-aware tax sensitivity analysis module.
    """
    from analytics.tax_sensitivity_v14 import run_tax_sensitivity_analysis
    
    tax_shocks = [
        TaxShockLibrary.corporate_tax_rate(0.28),
        TaxShockLibrary.distribution_delay(4),
        TaxShockLibrary.tlcf_carryforward_limit(20),
    ]
    
    suite = run_tax_sensitivity_analysis(
        base_config_path="scenarios/dutchbay_base.yaml",
        shock_specs=tax_shocks,
        metric="equity_irr",
    )
    
    assert suite.metric_name == "equity_irr"
    assert len(suite.shock_results) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
