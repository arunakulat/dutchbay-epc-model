from __future__ import annotations

from typing import Dict

import pytest

from analytics.contracts_v14 import (  # noqa: F401  (kept for future use)
    CasperResult,
    MonteCarloResult,
    ScenarioResult,
    SensitivitySuite,
    TailRiskSnapshot,
    TornadoResult,
    build_casper_payload,
)


def _toy_scenario() -> ScenarioResult:
    return ScenarioResult(
        scenario_name="ToyScenario",
        config_path="conf/toy.yaml",
        project_npv=1_000_000.0,
        project_irr=0.12,
        dscr_series=[1.4, 1.5, 1.6],
        min_dscr=1.4,
        max_debt_usd=50_000_000.0,
    )


def _toy_mc() -> MonteCarloResult:
    # Values are not used by the summary test directly; we just need a
    # structurally valid object in case callers choose to inspect it.
    return MonteCarloResult(
        iterations=10,
        project_irr_mean=0.12,
        project_irr_std=0.01,
        project_irr_p10=0.11,
        project_irr_p50=0.12,
        project_irr_p90=0.13,
        project_npv_mean=1_000_000.0,
        project_npv_p10=900_000.0,
        project_npv_p50=1_000_000.0,
        project_npv_p90=1_100_000.0,
        dscr_min_p10=1.30,
        dscr_min_p50=1.40,
        failed_iterations=0,
        raw_results=None,
        scenario_name="ToyScenario",
    )


def test_build_casper_payload_includes_tail_risk_summary() -> None:
    scenario = _toy_scenario()
    mc = _toy_mc()

    baseline_kpis: Dict[str, float] = {
        "project_irr": 0.12,
        "project_npv": 1_000_000.0,
        "min_dscr": 1.40,
    }

    snapshots = {
        "project_irr": TailRiskSnapshot(
            metric="project_irr",
            confidence=0.9,
            var=0.105,
            cvar=0.100,
            p10=0.11,
            p50=0.12,
            p90=0.13,
            breach_probability=0.08,
        ),
        "dscr_min": TailRiskSnapshot(
            metric="dscr_min",
            confidence=0.9,
            var=1.25,
            cvar=1.20,
            p10=1.30,
            p50=1.40,
            p90=1.50,
            breach_probability=0.10,
        ),
    }

    payload = build_casper_payload(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=None,
        monte_carlo=mc,
        multi_tech_generation_breakdown=None,
        technology_breakdown=None,
        metadata={"tail_risk": {"rows": []}},  # full table lives here
        tail_risk_snapshots=snapshots,
    )

    assert "tail_risk" in payload
    tail = payload["tail_risk"]

    assert "project_irr" in tail
    assert "dscr_min" in tail

    irr_summary = tail["project_irr"]
    assert irr_summary["metric"] == "project_irr"
    assert irr_summary["confidence"] == pytest.approx(0.9)
    assert irr_summary["var"] == pytest.approx(0.105)
    assert irr_summary["cvar"] == pytest.approx(0.100)
    assert irr_summary["p10"] == pytest.approx(0.11)
    assert irr_summary["p50"] == pytest.approx(0.12)
    assert irr_summary["p90"] == pytest.approx(0.13)
    assert irr_summary["breach_probability"] == pytest.approx(0.08)
