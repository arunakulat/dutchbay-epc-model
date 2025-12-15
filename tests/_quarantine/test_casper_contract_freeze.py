from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION,
    ScenarioResult,
    build_casper_payload,
)


def _minimal_scenario_result() -> ScenarioResult:
    """
    Build a minimal ScenarioResult instance for contract checks.

    Uses only the required fields from the ScenarioResult dataclass;
    all optional fields rely on their defaults as defined in
    analytics.contracts_v14.
    """
    return ScenarioResult(
        scenario_name="dummy_scenario",
        config_path="scenarios/dummy.yaml",
        project_npv=0.0,
        project_irr=0.0,
        dscr_series=[],
        min_dscr=1.0,
        max_debt_usd=0.0,
    )


def test_casper_payload_top_level_contract() -> None:
    scenario = _minimal_scenario_result()
    payload = build_casper_payload(
        scenario=scenario,
        baseline_kpis={"project_irr": 0.135},
        sensitivities=None,
        monte_carlo=None,
        multi_tech_generation_breakdown=None,
        technology_breakdown=None,
        metadata=None,
        tail_risk_snapshots=None,
    )

    # Version freeze: this is the CASPER / GWTF v1 contract identifier.
    assert CASPER_CONTRACT_VERSION == "casper_result_v1"
    assert payload["contract_version"] == CASPER_CONTRACT_VERSION

    # Required keys
    assert "scenario" in payload
    assert "baseline_kpis" in payload
    assert payload["baseline_kpis"]["project_irr"] == pytest.approx(0.135)

    # Optional keys: must be safely present or omittable without breaking JSON
    for optional_key in (
        "sensitivity",
        "monte_carlo",
        "generation",
        "technology_breakdown",
        "tail_risk",
        "metadata",
    ):
        payload.get(optional_key, None)

    # Payload MUST be JSON-serialisable for CASPER / lender dashboards
    json.dumps(payload)
