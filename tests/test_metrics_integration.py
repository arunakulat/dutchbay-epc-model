from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.core.metrics import calculate_scenario_kpis
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer


ROOT = Path(__file__).resolve().parents[1]
LENDERCASE_CONFIG = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _extract_cfads_usd(annual_rows):
    """Helper to mirror the pipeline's CFADS extraction."""
    return [float(row.get("cfads_usd", 0.0) or 0.0) for row in annual_rows]


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

    # 4. Compute KPIs
    cfads_usd = _extract_cfads_usd(annual_rows)
    kpis = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=cfg,
        cfads_series_usd=cfads_usd,
    )

    # 5. Golden-value sanity: these come from the confirmed pipeline run
    #    for scenarios/dutchbay_lendercase_2025Q4.yaml.
    assert kpis["npv"] == pytest.approx(135297351.1553872, rel=1e-6)
    assert kpis["irr"] == pytest.approx(0.2003753638, rel=1e-6)
    assert kpis["dscr_min"] == pytest.approx(1.3, rel=1e-9)
    assert kpis["dscr_mean"] > 1.5
    assert kpis["dscr_max"] > kpis["dscr_mean"]
