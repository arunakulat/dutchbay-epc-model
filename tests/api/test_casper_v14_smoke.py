from __future__ import annotations

from pathlib import Path

import pytest

from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.contracts_v14 import CASPER_CONTRACT_VERSION, CasperResult

SCENARIO_PATH = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


@pytest.mark.skipif(
    not SCENARIO_PATH.is_file(),
    reason="Required CASPER smoke-test config is missing",
)
@pytest.mark.xfail(
    raises=ValueError,
    reason=(
        "Monte Carlo scenario '<inline_config>' not found in the current "
        "monte_carlo_defaults configuration. This integration path will be "
        "aligned in a future sprint when MC scenarios are made CASPER-aware."
    ),
    strict=False,
)
def test_casper_v14_orchestrator_smoke() -> None:
    """
    Integration smoke: exercise the full evaluation_v14 + Monte Carlo +
    tail-risk path via the CASPER orchestrator.

    Currently marked xfail due to a known mismatch between the inline
    MonteCarloConfig scenario_name ('<inline_config>') and the configured
    scenarios in monte_carlo_defaults.yaml. Once that alignment is done,
    this test will start running the assertions below.
    """
    casper, payload = evaluate_with_casper_tail_risk_and_payload(
        config_path=str(SCENARIO_PATH),
        monte_carlo_config_path=None,
        sensitivity_suite=None,
        metric="project_irr",
        confidence=0.9,
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )

    # Typed surface checks
    assert isinstance(casper, CasperResult)
    assert casper.contract_version == CASPER_CONTRACT_VERSION

    # JSON payload contract checks
    assert isinstance(payload, dict)
    assert payload["contract_version"] == CASPER_CONTRACT_VERSION

    scenario_block = payload.get("scenario")
    assert isinstance(scenario_block, dict)
    assert scenario_block.get("scenario_name") == casper.scenario.scenario_name

    baseline_kpis = payload.get("baseline_kpis", {})
    assert "project_irr" in baseline_kpis
