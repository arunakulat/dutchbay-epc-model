from __future__ import annotations

from typing import Any, Dict

from analytics import casper_v14
from analytics.contracts_v14 import (
    CASPER_CONTRACT_VERSION,
    CasperResult,
    ScenarioResult,
)


def _dummy_scenario_result() -> ScenarioResult:
    # Minimal ScenarioResult that satisfies casper_payload._scenario_summary_to_dict
    return ScenarioResult(
        scenario_name="dummy_scenario",
        config_path="scenarios/dummy.yaml",
        project_npv=123.0,
        project_irr=0.123,
        dscr_series=[1.3, 1.4],
        min_dscr=1.3,
        max_debt_usd=100_000_000.0,
        wacc=None,
        discount_rate_used=None,
        wacc_label=None,
        wacc_is_real=None,
        validation_mode="strict",
        config={},
        annual_rows=[],
        debt_result={},
        kpis={},
        cashflow=None,
        equity_performance=None,
        debt_profile=None,
        debt_covenants=None,
    )


class _DummyCasper(CasperResult):
    """
    Lightweight CasperResult for unit tests that bypasses the full v14 stack.
    """

    def __init__(self) -> None:
        super().__init__(
            scenario=_dummy_scenario_result(),
            baseline_kpis={"project_irr": 0.123, "project_npv": 123.0},
            sensitivities=None,
            monte_carlo=None,
            generation=None,
            multi_tech_generation_breakdown=None,
            metadata={"tail_risk": {"rows": []}},
        )


def test_evaluate_with_casper_tail_risk_and_payload_unit(monkeypatch) -> None:
    """
    Unit-level test for the CASPER orchestrator.

    This does *not* hit the real Monte Carlo / pipeline stack; instead it
    monkeypatches evaluation_v14.evaluate_with_casper_tail_risk to return
    a dummy CasperResult and verifies that the orchestrator builds a
    JSON-safe payload with the correct contract version and basic shape.
    """

    captured_calls: Dict[str, Any] = {}

    def _fake_evaluate_with_casper_tail_risk(**kwargs: Any) -> CasperResult:
        captured_calls.update(kwargs)
        return _DummyCasper()

    monkeypatch.setattr(
        "analytics.evaluation_v14.evaluate_with_casper_tail_risk",
        _fake_evaluate_with_casper_tail_risk,
    )

    casper, payload = casper_v14.evaluate_with_casper_tail_risk_and_payload(
        config_path="scenarios/dummy.yaml",
        monte_carlo_config_path=None,
        sensitivity_suite=None,
        metric="project_irr",
        confidence=0.9,
        validation_mode="strict",
        validation_modules=["cashflow", "debt"],
    )

    # Ensure we invoked evaluation_v14 with the expected parameters
    assert captured_calls["config_path"] == "scenarios/dummy.yaml"
    assert captured_calls["metric"] == "project_irr"
    assert captured_calls["validation_mode"] == "strict"
    assert captured_calls["validation_modules"] == ["cashflow", "debt"]

    # Typed result checks
    assert isinstance(casper, CasperResult)
    assert casper.contract_version == CASPER_CONTRACT_VERSION
    assert casper.scenario is not None
    assert casper.scenario.scenario_name == "dummy_scenario"

    # Payload contract checks
    assert isinstance(payload, dict)
    assert payload["contract_version"] == CASPER_CONTRACT_VERSION

    scenario_block = payload.get("scenario")
    assert isinstance(scenario_block, dict)
    assert scenario_block.get("scenario_name") == "dummy_scenario"

    baseline_kpis = payload.get("baseline_kpis", {})
    assert baseline_kpis["project_irr"] == 0.123
    assert baseline_kpis["project_npv"] == 123.0

    metadata = payload.get("metadata", {})
    assert "tail_risk" in metadata
    assert isinstance(metadata["tail_risk"], dict)
