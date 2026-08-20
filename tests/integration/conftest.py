"""Shared fixtures for integration tests.

Provides realistic test configurations for:
- DutchBay 150MW wind farm project
- Lender-grade analysis parameters
- Wind resource assessment data
- Degradation and DSCR targets

Framework Compliance:
- CESSPIT: All parameters explicit (no hardcoding)
- CASPER: Conservative lender assumptions
- TEST-01: Regression pins for integration behavior
"""

from typing import Any, Dict

import pytest
from omegaconf import OmegaConf


@pytest.fixture
def dutchbay_base_config() -> Dict[str, Any]:
    """Base configuration for DutchBay 150MW wind farm.

    Based on 2025Q4 lender case with:
    - 50 x Vestas V150-3.0MW turbines
    - Mannar region, Sri Lanka
    - 20-year PPA at $50/MWh
    - 0.6%/year degradation
    - Dual DSCR: 1.30x (P50) / 1.00x (P99)

    Returns:
        Dictionary with complete project configuration
    """
    return {
        "project": {
            "name": "DutchBay Wind Farm",
            "location": "Mannar, Sri Lanka",
            "capacity_mw": 150.0,
            "capex_usd": 200_000_000,  # $200M
            "degradation": 0.006,  # 0.6%/year
            "life_years": 20,
            "commissioning_date": "2026-01-01",
        },
        "turbine": {
            "model": "Vestas V150-3.0MW",
            "n_turbines": 50,
            "rated_power_mw": 3.0,
            "hub_height_m": 105.0,
            "rotor_diameter_m": 150.0,
        },
        "wind_resource": {
            "aep_p50_mwh": 400_000,  # 400 GWh/year P50
            "aep_p75_mwh": 380_000,  # 380 GWh/year P75 (conservative)
            "aep_p90_mwh": 360_000,  # 360 GWh/year P90
            "aep_p99_mwh": 340_000,  # 340 GWh/year P99 (lender downside)
            "capacity_factor_p50": 0.30,  # 30% CF
            "weibull_k": 2.0,
            "weibull_c": 7.5,  # m/s
            "data_years": 11,  # 2014-2025
        },
        "revenue": {
            "tariff_usd_mwh": 50.0,  # $50/MWh
            "escalation_rate": 0.02,  # 2%/year
            "ppa_term_years": 20,
        },
        "operations": {
            "opex_usd_year": 7_200_000,  # $7.2M/year
            "opex_escalation_rate": 0.025,  # 2.5%/year
            "availability_target": 0.97,  # 97%
            "grid_loss_factor": 0.03,  # 3%
        },
        "financing": {
            "debt_ratio_target": 0.70,  # 70% debt
            "debt_rate": 0.08,  # 8%
            "debt_tenor_years": 15,
            "dscr_target_p50": 1.30,  # P50 DSCR
            "dscr_target_p99": 1.00,  # P99 DSCR (downside)
            "debt_ratio_max": 0.75,  # Hard cap
        },
        "tax": {
            "corporate_rate": 0.28,  # 28%
            "depreciation_method": "straight_line",
            "depreciation_years": 10,
        },
        "monte_carlo": {
            "enabled": True,
            "n_iterations": 200,  # TEST-03 ordinary-suite hard maximum
            "discount_rate_pct": 8.0,
            "sampler": "lhs",
            "seed": 42,  # Reproducible
            "revenue_std_pct": 10.0,
            "cost_std_pct": 5.0,
            "fx_std_pct": 15.0,
            "degradation_mean_pct": 0.6,
            "degradation_std_pct": 0.1,
            "correlation_enabled": True,
            "correlation_matrix": [
                [1.0, 0.4, -0.3, -0.2],  # revenue, cost, fx, degradation
                [0.4, 1.0, -0.2, 0.1],
                [-0.3, -0.2, 1.0, 0.0],
                [-0.2, 0.1, 0.0, 1.0],
            ],
        },
        "sensitivity": {
            "enabled": True,
            "perturbation_range_pct": 20.0,
            "n_steps": 9,
            "variables": ["degradation", "aep", "tariff", "opex", "capex"],
        },
    }


@pytest.fixture
def dutchbay_omegaconf_config(dutchbay_base_config: Dict[str, Any]) -> OmegaConf:
    """OmegaConf version of DutchBay configuration.

    Args:
        dutchbay_base_config: Base configuration dictionary

    Returns:
        OmegaConf configuration object
    """
    return OmegaConf.create(dutchbay_base_config)


@pytest.fixture
def mc_sampling_config(dutchbay_base_config: Dict[str, Any]) -> OmegaConf:
    """Config for the canonical Monte Carlo engine (``analytics.mc.engine``).

    The current engine consumes ``monte_carlo.parameters`` — a list of Latin
    Hypercube stochastic variables (``name`` / ``distribution`` / ``low`` /
    ``high``) — and returns a :class:`analytics.contracts_v14.MonteCarloResult`
    dataclass (not a dict). This fixture augments the lender-case config with
    that block so the integration tests exercise the real engine API.

    The bespoke test config is intentionally *not* the full v14 finance schema,
    so per-trial evaluation falls back to the engine's deterministic toy-metric
    path. That exercises the sampler -> aggregator -> result-contract flow end
    to end *without* weakening production schema validation — the documented
    fallback behaviour in ``analytics/mc/engine.py``. The parameter names use
    the engine's recognised override keys so sampling produces non-degenerate
    (std > 0) distributions for every aggregated KPI (``project_npv``,
    ``project_irr``, ``dscr_min``, ``llcr``, ``plcr``).

    Args:
        dutchbay_base_config: Base configuration dictionary.

    Returns:
        OmegaConf configuration object with a ``monte_carlo.parameters`` block.
    """
    cfg = OmegaConf.create(dutchbay_base_config)
    cfg.monte_carlo.parameters = [
        {"name": "capex", "distribution": "uniform", "low": 90.0, "high": 110.0},
        {"name": "tariff", "distribution": "uniform", "low": 0.09, "high": 0.11},
        {
            "name": "capacity_factor",
            "distribution": "uniform",
            "low": 0.28,
            "high": 0.32,
        },
        {"name": "opex_annual", "distribution": "uniform", "low": 2.0, "high": 3.0},
    ]
    return cfg


@pytest.fixture
def wind_assessment_mock_results() -> Dict[str, Any]:
    """Mock wind assessment results for testing.

    Simulates output from wind_resource/wind_pipeline.py
    without requiring actual ERA5 data download.

    Returns:
        Dictionary mimicking WindPipeline.run_complete_assessment() output
    """
    return {
        "location": {
            "latitude": 8.98,
            "longitude": 79.90,
            "name": "Mannar",
        },
        "wind_statistics": {
            "mean_wind_speed_ms": 7.2,
            "weibull_k": 2.0,
            "weibull_c": 7.5,
            "data_years": 11,
            "data_completeness": 0.98,
        },
        "energy_production": {
            "gross_aep": {
                "gross_aep_p50_mwh": 420_000,
                "gross_aep_p75_mwh": 400_000,
                "gross_aep_p90_mwh": 380_000,
                "gross_aep_p99_mwh": 355_000,
            },
            "net_aep": {
                "net_aep_p50_mwh": 400_000,  # After losses
                "net_aep_p75_mwh": 380_000,
                "net_aep_p90_mwh": 360_000,
                "net_aep_p99_mwh": 340_000,
            },
            "capacity_factor_p50": 0.305,
            "loss_factors": {
                "availability": 0.97,
                "grid_loss": 0.03,
                "turbine_performance": 0.98,
                "combined_loss": 0.05,
            },
        },
        "uncertainty": {
            "p50_p75_ratio": 0.95,
            "p50_p90_ratio": 0.90,
            "p50_p99_ratio": 0.85,
            "inter_annual_variability_pct": 8.0,
        },
        "validation": {
            "data_quality_score": 0.95,
            "uncertainty_acceptable": True,
            "lender_grade": True,
        },
    }


@pytest.fixture
def degradation_test_params() -> Dict[str, Any]:
    """Degradation parameters for testing.

    Returns:
        Dictionary with degradation test scenarios
    """
    return {
        "base_case": {
            "annual_rate": 0.006,  # 0.6%/year
            "year_10_factor": 0.9418,  # (1-0.006)^10
            "year_20_factor": 0.8869,  # (1-0.006)^20
        },
        "conservative_case": {
            "annual_rate": 0.008,  # 0.8%/year
            "year_10_factor": 0.9230,
            "year_20_factor": 0.8521,
        },
        "optimistic_case": {
            "annual_rate": 0.004,  # 0.4%/year
            "year_10_factor": 0.9608,
            "year_20_factor": 0.9231,
        },
    }


@pytest.fixture
def dscr_test_targets() -> Dict[str, float]:
    """DSCR targets for dual constraint testing.

    Returns:
        Dictionary with DSCR parameters
    """
    return {
        "dscr_p50_target": 1.30,  # Investment grade
        "dscr_p99_target": 1.00,  # Downside protection
        "dscr_p50_min": 1.20,  # Minimum acceptable
        "dscr_p99_min": 0.95,  # Stress case floor
    }


@pytest.fixture
def performance_benchmarks() -> Dict[str, float]:
    """Performance benchmarks for integration tests.

    Returns:
        Dictionary with time limits (seconds)
    """
    return {
        "wind_assessment_max_seconds": 5.0,
        "cashflow_model_max_seconds": 2.0,
        "monte_carlo_1k_max_seconds": 10.0,
        "monte_carlo_10k_max_seconds": 60.0,
        "sensitivity_analysis_max_seconds": 30.0,
        "full_pipeline_max_seconds": 60.0,
    }
