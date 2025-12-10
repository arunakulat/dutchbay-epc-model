from __future__ import annotations

import json
from typing import Dict

import pytest

from analytics.contracts_v14 import (
    MonteCarloResult,
    ScenarioResult,
    SensitivitySuite,
    TornadoResult,
    build_casper_payload,
)


def _build_toy_scenario_result() -> ScenarioResult:
    """
    Minimal, self-contained ScenarioResult for CASPER payload tests.
    """
    return ScenarioResult(
        scenario_name="toy_scenario",
        config_path="scenarios/toy.yaml",
        project_npv=123.0,
        project_irr=0.15,
        dscr_series=[1.30, 1.35, 1.40],
        min_dscr=1.30,
        max_debt_usd=100_000_000.0,
        kpis={"dscr_min": 1.30},
    )


def _build_toy_sensitivity_suite() -> SensitivitySuite:
    """
    Single-row tornado for a simple IRR sensitivity.
    """
    tornado_row = TornadoResult(
        variable="project.capex_usd_per_kw",
        base_irr=0.15,
        low_irr=0.13,
        high_irr=0.17,
    )

    return SensitivitySuite(
        tornado_results=[tornado_row],
        base_metric=0.15,
        base_config_path="scenarios/toy.yaml",
        metric="project_irr",
    )


def _build_toy_monte_carlo_result() -> MonteCarloResult:
    """
    Toy MonteCarloResult with simple, deterministic numbers.

    We keep the shape realistic enough to exercise success_rate()
    and the nested IRR/NPV/DSCR blocks in the payload.
    """
    iterations = 100
    failed_iterations = 10

    return MonteCarloResult(
        iterations=iterations,
        project_irr_mean=0.15,
        project_irr_std=0.02,
        project_irr_p10=0.12,
        project_irr_p50=0.15,
        project_irr_p90=0.18,
        project_npv_mean=120.0,
        project_npv_p10=80.0,
        project_npv_p50=120.0,
        project_npv_p90=160.0,
        dscr_min_p10=1.20,
        dscr_min_p50=1.30,
        failed_iterations=failed_iterations,
        raw_results=[
            {"project_irr": 0.15, "project_npv": 120.0, "dscr_min": 1.30},
            {"project_irr": 0.14, "project_npv": 110.0, "dscr_min": 1.25},
        ],
        scenario_name="toy_scenario",
        project_irr_se=0.001,
        project_npv_se=1.0,
        dscr_min_se=0.01,
    )


def test_build_casper_payload_basic_shape_and_numbers() -> None:
    scenario = _build_toy_scenario_result()
    sensitivities = _build_toy_sensitivity_suite()
    mc_result = _build_toy_monte_carlo_result()

    baseline_kpis: Dict[str, float] = {
        "project_irr": 0.15,
        "project_npv": 123.0,
        "dscr_min": 1.30,
    }

    payload = build_casper_payload(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=sensitivities,
        monte_carlo=mc_result,
    )

    # --- Top-level structure ----------------------------------------------------
    assert set(payload.keys()) >= {
        "scenario",
        "baseline_kpis",
        "sensitivity",
        "monte_carlo",
    }

    # Scenario block should echo ScenarioResult.as_dict()
    scenario_block = payload["scenario"]
    assert scenario_block["scenario_name"] == "toy_scenario"
    assert scenario_block["config_path"] == "scenarios/toy.yaml"
    assert scenario_block["project_irr"] == pytest.approx(0.15)
    assert scenario_block["project_npv"] == pytest.approx(123.0)
    assert scenario_block["min_dscr"] == pytest.approx(1.30)

    # Baseline KPIs preserved and numeric
    baseline = payload["baseline_kpis"]
    assert baseline["project_irr"] == pytest.approx(0.15)
    assert baseline["project_npv"] == pytest.approx(123.0)
    assert baseline["dscr_min"] == pytest.approx(1.30)

    # --- Monte Carlo block ------------------------------------------------------
    mc_block = payload["monte_carlo"]
    assert mc_block["iterations"] == 100
    assert mc_block["failed_iterations"] == 10
    assert mc_block["success_rate"] == pytest.approx(90.0)

    irr_block = mc_block["project_irr"]
    assert irr_block["mean"] == pytest.approx(0.15)
    assert irr_block["p10"] == pytest.approx(0.12)
    assert irr_block["p50"] == pytest.approx(0.15)
    assert irr_block["p90"] == pytest.approx(0.18)

    npv_block = mc_block["project_npv"]
    assert npv_block["mean"] == pytest.approx(120.0)
    assert npv_block["p10"] == pytest.approx(80.0)
    assert npv_block["p50"] == pytest.approx(120.0)
    assert npv_block["p90"] == pytest.approx(160.0)

    dscr_block = mc_block["dscr_min"]
    assert dscr_block["p10"] == pytest.approx(1.20)
    assert dscr_block["p50"] == pytest.approx(1.30)

    # --- Sensitivity / tornado block -------------------------------------------
    sens_block = payload["sensitivity"]
    assert sens_block["metric"] == "project_irr"
    assert sens_block["base_metric"] == pytest.approx(0.15)
    assert sens_block["base_config_path"] == "scenarios/toy.yaml"

    tornado_rows = sens_block["tornado"]
    assert isinstance(tornado_rows, list)
    assert len(tornado_rows) == 1

    row0 = tornado_rows[0]
    # Echo raw values
    assert row0["variable"] == "project.capex_usd_per_kw"
    assert row0["base_irr"] == pytest.approx(0.15)
    assert row0["low_irr"] == pytest.approx(0.13)
    assert row0["high_irr"] == pytest.approx(0.17)

    # impact_abs = |high - low| = 0.04
    assert row0["impact_abs"] == pytest.approx(0.04)

    # impact_pct = (high - low)/base * 100 = 26.666...%
    assert row0["impact_pct"] == pytest.approx((0.17 - 0.13) / 0.15 * 100.0)

    # --- JSON-safe check --------------------------------------------------------
    # If this fails, something non-serialisable leaked into the payload.
    json.dumps(payload)
