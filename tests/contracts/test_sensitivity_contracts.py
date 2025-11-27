"""
tests/contracts/test_sensitivity_contracts.py
Smoke tests for contracts_v14.py — Sensitivity/analytics dataclasses

Purpose: Ensure basic constructibility, default values, property logic,
         required fields, and type annotations for all new sensitivity/analytics types.
"""

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    ParetoFrontierResult,
    SensitivitySuite,
    TailRiskMetrics,
    TornadoResult,
)


def test_parameter_range_config_minimal():
    cfg = ParameterRangeConfig(
        variable_name="project.capex_usd_per_kw",
        base_value=1000,
        low_pct=-20,
        high_pct=20,
        steps=5,
    )
    assert cfg.low_value == 800
    assert cfg.high_value == 1200


def test_tornado_result_properties():
    res = TornadoResult(
        variable="project.capex_usd_per_kw",
        base_irr=0.10,
        low_irr=0.08,
        high_irr=0.12,
    )
    assert abs(res.impact_abs - 0.04) < 1e-9


def test_sensitivity_suite_instantiation():
    # Minimal suite with a single result
    result = TornadoResult(variable="foo", base_irr=0.1, low_irr=0.08, high_irr=0.12)
    suite = SensitivitySuite(
        tornado_results=[result],
        base_metric=0.10,
        base_config_path="config/test.yaml",
        metric="project_irr",
    )
    assert suite.tornado_results[0].variable == "foo"


def test_breakeven_result():
    br = BreakevenResult(
        variable="project.capex_usd_per_kw",
        breakeven_value=950.0,
        bracket=(800.0, 1200.0),
        status="success",
    )
    assert isinstance(br.breakeven_value, float) or br.breakeven_value is None


def test_multimetric_tornado_and_suite():
    mres = MultiMetricTornadoResult(
        variable="project.capex_usd_per_kw",
        label="Capex",
        base_values={"project_irr": 0.1, "npv": 1e6},
        low_values={"project_irr": 0.08, "npv": 0.7e6},
        high_values={"project_irr": 0.12, "npv": 1.2e6},
        impacts={"project_irr": 0.04, "npv": 0.5e6},
        impact_dirs={"project_irr": 1, "npv": 1},
    )
    suite = MultiMetricSensitivitySuite(
        tornado_results=[mres],
        base_metrics={"project_irr": 0.10, "npv": 1e6},
        base_config_path="test.yaml",
        metrics=["project_irr", "npv"],
    )
    assert mres.variable == "project.capex_usd_per_kw"
    assert isinstance(suite.metrics, list)


def test_pareto_frontier_result():
    pf = ParetoFrontierResult(
        frontier_points=[{"project_irr": 0.12, "dscr_min": 1.32}],
        objectives=["project_irr", "dscr_min"],
    )
    assert pf.objectives == ["project_irr", "dscr_min"]


def test_tail_risk_metrics():
    tr = TailRiskMetrics(
        var=0.08, cvar=0.07, p10=0.09, p50=0.12, p90=0.15, breach_prob=0.02
    )
    assert tr.var == 0.08


# Add/expand for additional contracts as needed.
