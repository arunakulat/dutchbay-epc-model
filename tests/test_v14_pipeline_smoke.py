from pathlib import Path

from run_full_pipeline import run_v14_pipeline


ROOT = Path(__file__).resolve().parents[1]
LENDERCASE_CONFIG = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


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
    # Key KPIs must be present
    for key in ("npv", "irr", "dscr_min", "dscr_mean", "dscr_max"):
        assert key in kpis

    # DSCR sanity: for lender case we expect > 1.0
    assert kpis["dscr_min"] is not None
    assert kpis["dscr_min"] > 1.0
