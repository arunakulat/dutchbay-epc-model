"""Second iteration smoke test for CASPER orchestrator.

This test exercises the CASPER v14 orchestrator on the DutchBay lender
case.  It verifies that the orchestrator returns a valid ``CasperResult``
object and that the corresponding JSON payload contains the expected
contract version and baseline KPIs.  Unlike the first iteration, this
version supplies a Monte Carlo configuration path to avoid the
``NoneType`` error encountered in the initial test.

Run instructions:

    # Make sure this file is executable (optional on most systems)
    chmod +x tests/api/test_casper_v14_smoke_iteration2.py

    # Execute just this test using pytest without coverage enforcement:
    python -m pytest tests/api/test_casper_v14_smoke_iteration2.py --no-cov -q

If coverage is required, you may omit ``--no-cov`` but note that the
project's coverage threshold (55%) will cause failures when only a
single test runs.  To run all tests together, simply invoke
``pytest`` from the repository root.
"""

import pytest

from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
from analytics.contracts_v14 import CASPER_CONTRACT_VERSION, CasperResult


def test_casper_smoke_iteration2() -> None:
    """Run CASPER orchestrator with explicit Monte Carlo config path."""
    # Path to the sample scenario configuration.  Adjust the path as needed
    # when running in different environments.
    config_path = "scenarios/dutchbay_lendercase_2025Q4.yaml"

    # Provide a Monte Carlo configuration file to avoid NoneType errors.  The
    # file name must exist in the ``monte_carlo`` directory of the project.
    mc_config_path = "monte_carlo/dutchbay_lendercase_mc_2025Q4.yaml"

    # Run the CASPER orchestrator without a SensitivitySuite.  The Monte
    # Carlo configuration will still be parsed to satisfy the evaluation
    # logic in ``evaluation_v14.py``.
    casper_result, payload = evaluate_with_casper_tail_risk_and_payload(
        config_path=config_path,
        monte_carlo_config_path=mc_config_path,
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
