from analytics.contracts_v14 import CASPER_CONTRACT_VERSION, CasperResult


def test_casper_result_with_generation_fields() -> None:
    result = CasperResult(
        scenario=None,  # type: ignore[arg-type]
        baseline_kpis={"project_irr": 0.12},
        sensitivities=None,
        monte_carlo=None,
        multi_tech_generation_breakdown=None,
    )

    assert result.baseline_kpis["project_irr"] == 0.12

    # Contract-level guard: field must exist and be optional-ish
    annotations = CasperResult.__annotations__
    assert "multi_tech_generation_breakdown" in annotations


def test_casper_result_has_frozen_contract_version() -> None:
    result = CasperResult(
        scenario=None,  # type: ignore[arg-type]
        baseline_kpis={"project_irr": 0.12},
        sensitivities=None,
        monte_carlo=None,
        multi_tech_generation_breakdown=None,
    )

    assert result.contract_version == CASPER_CONTRACT_VERSION
    assert CASPER_CONTRACT_VERSION == "casper_result_v1"
