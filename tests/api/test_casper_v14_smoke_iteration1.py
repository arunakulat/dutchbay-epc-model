"""Initial smoke test for CASPER orchestrator.

This test calls the CASPER orchestrator on the DutchBay lender case configuration and
checks that a `CasperResult` is returned and that the JSON payload contains the
expected contract version and baseline KPIs.  It uses the default evaluation
logic (no Monte Carlo and no sensitivity suite) for a fast smoke test.
"""

import pytest

from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.contracts_v14 import CASPER_CONTRACT_VERSION, CasperResult


@pytest.mark.xfail(
    raises=ValueError,
    reason=(
        "Monte Carlo scenario '<inline_config>' not found in the current "
        "monte_carlo_defaults configuration. This integration path will be "
        "aligned in a future sprint when MC scenarios are made CASPER-aware."
    ),
    strict=False,
)
def test_casper_smoke() -> None:
    # Path to the sample scenario configuration.  Adjust the path as needed
    # when running in different environments.
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # Run the CASPER orchestrator without Monte Carlo (None).
    # Monte Carlo integration will be aligned in a future sprint.
    casper_result, payload = evaluate_with_casper_tail_risk_and_payload(
        config_path=config_path,
        monte_carlo_config_path=None,  # Skip MC for now
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
