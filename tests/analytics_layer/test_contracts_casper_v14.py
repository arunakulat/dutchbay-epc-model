from analytics.contracts_v14 import CasperResult


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
