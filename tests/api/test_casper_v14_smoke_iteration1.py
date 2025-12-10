"""Initial smoke test for CASPER orchestrator.

This test calls the CASPER orchestrator on the DutchBay lender case configuration and
checks that a `CasperResult` is returned and that the JSON payload contains the
expected contract version and baseline KPIs.  It uses the default evaluation
logic (no Monte Carlo and no sensitivity suite) for a fast smoke test.
"""

import pytest

from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.contracts_v14 import CASPER_CONTRACT_VERSION, CasperResult


def test_casper_smoke() -> None:
    # Path to the sample scenario configuration.  Adjust the path as needed
    # when running in different environments.
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    mc_config_path = "monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml"  # ← ADD THIS

    # Run the CASPER orchestrator with Monte Carlo analysis.
    casper_result, payload = evaluate_with_casper_tail_risk_and_payload(
        config_path=config_path,
        monte_carlo_config_path=mc_config_path,  # ← CHANGE None to mc_config_path
        sensitivity_suite=None,
        metric="project_irr",
        confidence=0.9,
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )

    # Verify that the typed result is a CasperResult and has the expected version.
    assert isinstance(casper_result, CasperResult)
    assert casper_result.contract_version == CASPER_CONTRACT_VERSION

    # Verify that the JSON payload mirrors the contract version and includes baseline KPIs.
    assert payload["contract_version"] == CASPER_CONTRACT_VERSION
    assert "baseline_kpis" in payload and payload["baseline_kpis"]
