"""Integration test for metrics module with real YAML config."""

from pathlib import Path

from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer

LENDERCASE_CONFIG = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


def test_metrics_integration_lendercase_yaml():
    """End-to-end metrics integration on the canonical lender-case YAML.

    This checks that:
    - The YAML loads via the shared scenario loader.
    - v14 cashflow + debt stack runs.
    - Metrics module produces stable KPIs for the lender case.
    """
    assert LENDERCASE_CONFIG.exists(), f"Missing lendercase config: {LENDERCASE_CONFIG}"

    # 1. Load and normalise config
    cfg = load_scenario_config(str(LENDERCASE_CONFIG))

    # 2. Build v14 annual cashflows
    annual_rows = build_annual_rows(cfg)
    assert len(annual_rows) > 0

    # 3. Apply v14 debt layer
    debt_result = apply_debt_layer(cfg, annual_rows)
    dscr_series = debt_result.get("dscr_series") or []
    assert len(dscr_series) > 0
    assert all(d > 0 for d in dscr_series)

    # 4. Compute KPIs with v14 signature
    kpis = calculate_scenario_kpis(
        config=cfg,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,
    )

    # 5. Assert core KPIs present
    assert "project_npv" in kpis
    assert "project_irr" in kpis
    assert "min_dscr" in kpis
    assert "dscr_series" in kpis

    # 6. Sanity checks on values
    project_npv = kpis["project_npv"]
    assert isinstance(project_npv, (int, float))

    project_irr = kpis["project_irr"]
    assert isinstance(project_irr, (int, float))

    min_dscr = kpis["min_dscr"]
    assert min_dscr > 0, "DSCR should be positive for lender case"

    # DSCR series should have been passed through
    kpi_dscr_series = kpis["dscr_series"]
    assert len(kpi_dscr_series) > 0

