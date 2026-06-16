"""Golden test: evaluation_v14 MUST return lender-stack outputs.

This test prevents regression where evaluation gateway gets rewired
to wind-only pipeline. If this test fails, someone broke the canonical
evaluation surface.

Framework: TEST-01 (golden behavior pin)
CESSPIT: Fail-fast on missing lender KPIs
GWTF: Canonical evaluation contract validation

Author: Dutch Bay Wind Farm Team
Date: December 2025
Sprint: Sprint 9 (Phase 3 contracts integration)
"""

from __future__ import annotations

import pytest
from pathlib import Path

from analytics.evaluation_v14 import (
    evaluate_with_overrides,
    evaluate_scenario_from_dict,
)


# Lender-grade KPIs that MUST be present in evaluation output
REQUIRED_LENDER_KPIS = {
    "project_irr",      # Unleveraged internal rate of return
    "equity_irr",       # Leveraged return to equity
    "min_dscr",         # Minimum debt service coverage ratio
    "avg_dscr",         # Average DSCR over debt term
    "llcr",             # Loan life coverage ratio
    "plcr",             # Project life coverage ratio
}


def test_evaluate_with_overrides_returns_lender_kpis():
    """Evaluation gateway must return lender KPIs, not just wind metrics.
    
    This is the PRIMARY regression pin. If this test fails:
    1. Check analytics/evaluation_v14.py line 11:
       - Should be: `from analytics.pipeline_v14_enhanced import run_v14_pipeline`
       - NOT: `from analytics.pipeline_v14 import run_v14_pipeline`
    2. Check analytics/pipeline_v14_enhanced.py output contract
    3. Check finance/kpis.py calculations
    
    Failure here means:
    - Sensitivity analysis is broken (no debt covenant impacts)
    - CASPER orchestration is broken (no tail risk on DSCR)
    - Optimization is broken (optimizing wrong objective)
    """
    # Arrange: Use minimal test scenario
    scenario_path = Path("tests/data/minimal_lender_scenario.yaml")
    
    # Skip if test data not available (CI environment)
    if not scenario_path.exists():
        pytest.skip(f"Test scenario not found: {scenario_path}")
    
    # Act: Run evaluation through canonical gateway
    kpis = evaluate_with_overrides(
        config_path=scenario_path,
        overrides={},
        validation_modules=["cashflow", "debt"]
    )
    
    # Assert: Output structure
    assert isinstance(kpis, dict), (
        "evaluate_with_overrides() must return dict. "
        f"Got {type(kpis).__name__}"
    )
    assert len(kpis) > 0, "KPIs dict must not be empty"
    
    # Assert: ALL required lender KPIs present
    missing_keys = REQUIRED_LENDER_KPIS - set(kpis.keys())
    assert not missing_keys, (
        f"\n\n"
        f"🚨 GOLDEN TEST FAILED: Evaluation gateway missing lender KPIs 🚨\n"
        f"\n"
        f"Missing KPIs: {missing_keys}\n"
        f"\n"
        f"This means evaluation_v14.py is wired to wind-only pipeline.\n"
        f"\n"
        f"Root Cause:\n"
        f"  - analytics/evaluation_v14.py imports wrong pipeline\n"
        f"  - Should import from: analytics.pipeline_v14_enhanced\n"
        f"  - Currently imports from: analytics.pipeline_v14 (wind-only)\n"
        f"\n"
        f"Impact:\n"
        f"  - Sensitivity analysis broken (no debt covenant impacts)\n"
        f"  - CASPER broken (no tail risk on DSCR)\n"
        f"  - Optimization broken (wrong objective function)\n"
        f"\n"
        f"Fix: Change line 11 in analytics/evaluation_v14.py:\n"
        f"  from analytics.pipeline_v14_enhanced import run_v14_pipeline\n"
        f"\n"
    )
    
    # Assert: KPI values are numeric and sane
    for key in REQUIRED_LENDER_KPIS:
        value = kpis[key]
        assert isinstance(value, (int, float)), (
            f"KPI '{key}' must be numeric, got {type(value).__name__}"
        )
        
        # Sanity checks on specific metrics
        if "dscr" in key.lower():
            assert value > 0, (
                f"DSCR metric '{key}' must be positive, got {value}. "
                f"This indicates debt structuring failed."
            )
        
        if "irr" in key.lower():
            assert -1.0 <= value <= 2.0, (
                f"IRR metric '{key}' outside reasonable range [-100%, 200%], "
                f"got {value * 100:.1f}%. This indicates calculation error."
            )


def test_evaluate_scenario_from_dict_returns_lender_kpis():
    """In-memory config evaluation must also return lender KPIs.
    
    This validates the alternative evaluation entry point.
    """
    # Arrange: Complete v14-compliant config with all required fields
    config = {
        "project": {
            "name": "test_project",
            "capacity_mw": 100.0,
            "capacity_factor_pct": 35.0,  # Required for energy calculation
            "project_life_years": 25,      # Required for timeline
        },
        "wind": {
            "weibull_k": 2.0,
            "weibull_lambda": 8.5,
            "hub_height_m": 120.0,
        },
        "finance": {
            "capex_total_usd": 200e6,
            "discount_rate_pct": 8.0,
        },
        "tariff": {
            "lkr_per_kwh": 24.0,  # 300 LKR/USD * 0.08 USD/kWh = 24 LKR/kWh
        },
        "opex": {
            "usd_per_year": 5e6,  # Annual OPEX in USD
        },
        "tax": {
            "corporate_tax_rate": 0.28,  # Sri Lankan corporate tax rate
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 15,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_pct": 1.0,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0.0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
        },
        "fx": {
            "start_lkr_per_usd": 300.0,  # Initial LKR/USD exchange rate
            "annual_depr": 0.02,          # 2% annual LKR depreciation (scalar)
        },
        "debt": {
            "target_dscr": 1.4,
            "interest_rate_pct": 6.0,
            "term_years": 18,
        },
    }
    
    # Act: Evaluate from dict
    kpis = evaluate_scenario_from_dict(
        config=config,
        overrides={}
    )
    
    # Assert: Same lender KPI requirements
    assert isinstance(kpis, dict)
    assert len(kpis) > 0
    
    missing_keys = REQUIRED_LENDER_KPIS - set(kpis.keys())
    assert not missing_keys, (
        f"evaluate_scenario_from_dict() missing lender KPIs: {missing_keys}"
    )
    
    # Validate numeric KPIs
    for key in REQUIRED_LENDER_KPIS:
        assert isinstance(kpis[key], (int, float)), (
            f"KPI '{key}' must be numeric"
        )


def test_evaluation_can_apply_parameter_overrides():
    """Evaluation must correctly apply parameter shocks.
    
    This validates the shock mechanism works with lender pipeline.
    Parameter changes should propagate through:
    1. Wind assessment (if applicable)
    2. Cashflow model
    3. Debt structuring
    4. KPI calculation
    """
    # Arrange: Complete v14-compliant base config
    config = {
        "project": {
            "name": "test_shock",
            "capacity_mw": 100.0,
            "capacity_factor_pct": 35.0,
            "project_life_years": 25,
        },
        "wind": {
            "weibull_k": 2.0,
            "weibull_lambda": 8.5,
            "hub_height_m": 120.0,
        },
        "finance": {
            "capex_total_usd": 200e6,
            "discount_rate_pct": 8.0,
        },
        "tariff": {
            "lkr_per_kwh": 24.0,  # Base tariff
        },
        "opex": {
            "usd_per_year": 5e6,
        },
        "tax": {
            "corporate_tax_rate": 0.28,
            "depreciation_method": "straight_line",
            "depreciation_start_year": 1,
            "depreciation_years": 15,
            "enhanced_allowance_applies": False,
            "enhanced_capital_allowance_pct": 1.0,
            "loss_carryforward_years": 25,
            "tax_holiday_start_year": 1,
            "tax_holiday_years": 0,
            "wht_on_interest_to_nonresidents": 0.0,
            "wht_on_interest_enabled": False,
            "wht_gross_up": False,
        },
        "fx": {
            "start_lkr_per_usd": 300.0,
            "annual_depr": 0.02,  # 2% annual depreciation (scalar)
        },
        "debt": {
            "target_dscr": 1.4,
            "interest_rate_pct": 6.0,
            "term_years": 18,
        },
    }
    
    # Act: Run base case
    kpis_base = evaluate_scenario_from_dict(config=config, overrides={})
    
    # Act: Apply CAPEX shock (+25%)
    kpis_capex_shock = evaluate_scenario_from_dict(
        config=config,
        overrides={"finance": {"capex_total_usd": 250e6}}  # +$50M
    )
    
    # Act: Apply tariff shock (+10%)
    kpis_tariff_shock = evaluate_scenario_from_dict(
        config=config,
        overrides={"tariff": {"lkr_per_kwh": 26.4}}  # +10% from 24.0
    )
    
    # Assert: CAPEX increase should reduce project IRR
    assert kpis_capex_shock["project_irr"] < kpis_base["project_irr"], (
        f"Higher CAPEX should reduce IRR. "
        f"Base: {kpis_base['project_irr']:.3f}, "
        f"Shocked: {kpis_capex_shock['project_irr']:.3f}. "
        f"This means shocks are not propagating through lender pipeline."
    )
    
    # Assert: Tariff increase should increase project IRR
    assert kpis_tariff_shock["project_irr"] > kpis_base["project_irr"], (
        f"Higher tariff should increase IRR. "
        f"Base: {kpis_base['project_irr']:.3f}, "
        f"Shocked: {kpis_tariff_shock['project_irr']:.3f}. "
        f"This means shocks are not propagating through lender pipeline."
    )
    
    # Assert: CAPEX shock should affect DSCR
    assert kpis_capex_shock["min_dscr"] < kpis_base["min_dscr"], (
        f"Higher CAPEX should reduce min_dscr (more debt service). "
        f"Base: {kpis_base['min_dscr']:.2f}, "
        f"Shocked: {kpis_capex_shock['min_dscr']:.2f}. "
        f"This means CAPEX shock not propagating to debt structuring."
    )


def test_evaluation_validates_missing_config():
    """Evaluation must fail fast on invalid config paths.
    
    CESSPIT compliance: fail-fast validation.
    """
    with pytest.raises(FileNotFoundError, match="Scenario config not found"):
        evaluate_with_overrides(
            config_path="nonexistent/scenario.yaml",
            overrides={}
        )


if __name__ == "__main__":
    # Allow running directly for quick validation
    pytest.main([__file__, "-v", "-s"])
