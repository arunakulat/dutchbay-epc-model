"""Smoke test for run_v14_pipeline function."""

from pathlib import Path

from run_full_pipeline_v14 import run_v14_pipeline

LENDERCASE_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


def test_v14_pipeline_smoke_runs_and_returns_structure():
    assert LENDERCASE_CONFIG.exists(), f"Missing lendercase config: {LENDERCASE_CONFIG}"

    result = run_v14_pipeline(
        config=str(LENDERCASE_CONFIG),
        validation_mode="strict",
    )

    # Basic shape
    assert isinstance(result, dict)
    assert result["validation_mode"] == "strict"
    assert isinstance(result["config"], dict)
    assert isinstance(result["annual_rows"], list)
    assert isinstance(result["debt_result"], dict)
    assert isinstance(result["kpis"], dict)

    kpis = result["kpis"]
    # Key KPIs must be present (v14 naming)
    for key in ("project_npv", "project_irr", "min_dscr", "dscr_series"):
        assert key in kpis, f"Expected key '{key}' in kpis"

    # NPV should be a number
    project_npv = kpis["project_npv"]
    assert isinstance(project_npv, (int, float))

    # IRR should be a number (may be 0 if cashflows are problematic)
    project_irr = kpis["project_irr"]
    assert isinstance(project_irr, (int, float))

    # DSCR should be positive
    min_dscr = kpis["min_dscr"]
    assert isinstance(min_dscr, (int, float))
    assert min_dscr > 0 or min_dscr == float('inf'), "min_dscr should be positive or inf"
