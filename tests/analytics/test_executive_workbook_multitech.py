"""Multi-technology guard for the Executive Workbook (#726, follow-up to #656 slice 3).

The five finance sheets of the single-scenario Executive Workbook (Summary / Cashflow /
DebtService / Ratios / ScenarioSummary) are assembled from the plain ``run_v14_pipeline``
result via ``frames_from_pipeline_result`` — so they are **technology-agnostic by
construction**: no per-technology wiring exists, and none should be needed. Only the optional
"ResourceTrend" sheet is resource-specific (wind long-term trend), and it is default-off.

This test locks that tech-agnostic behaviour against regression: for a hybrid (wind+solar), a
solar+BESS, and a BESS scenario, a real pipeline run + workbook emit must produce exactly the
five finance sheets (and NOT a spurious ResourceTrend sheet, since no wind_export is passed).
It runs the genuine engine on the committed scenarios — a golden pin, not a fabricated frame.

KPI-neutral / opt-in surface: the workbook is a read-only projection of the run result; this
test asserts sheet structure only and derives no financial value (CCCDIR one-source).
"""

from __future__ import annotations

import pytest

from analytics.executive_workbook import emit_executive_workbook_from_pipeline
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

openpyxl = pytest.importorskip("openpyxl")

#: The five technology-agnostic finance sheets every workbook must carry.
_FINANCE_SHEETS = ["Summary", "Cashflow", "DebtService", "Ratios", "ScenarioSummary"]

#: One scenario per non-wind-only technology mix, exercising the tech-agnostic finance path.
_MULTI_TECH_SCENARIOS = [
    "dutchbay_hybrid_windsolar_2025Q4",  # hybrid wind + solar
    "ceb_solar_bess_nightpeak_10mw",  # solar + BESS
    "ceb_bess_10mw_capacity_charge",  # BESS only
]


@pytest.mark.parametrize("scenario", _MULTI_TECH_SCENARIOS)
def test_executive_workbook_emits_five_finance_sheets_per_technology(
    scenario: str, tmp_path
) -> None:
    cfg = load_scenario_config(f"scenarios/{scenario}.yaml")
    result = run_v14_pipeline(config=cfg)

    out = emit_executive_workbook_from_pipeline(result, tmp_path / f"{scenario}.xlsx")

    assert out.exists()
    sheetnames = openpyxl.load_workbook(out).sheetnames
    # Exactly the five finance sheets: tech-agnostic, and no ResourceTrend when no
    # wind_export is supplied (a hybrid/solar/BESS run must not fabricate one).
    assert sheetnames == _FINANCE_SHEETS


@pytest.mark.parametrize("scenario", _MULTI_TECH_SCENARIOS)
def test_finance_sheets_are_non_empty_per_technology(scenario: str, tmp_path) -> None:
    cfg = load_scenario_config(f"scenarios/{scenario}.yaml")
    result = run_v14_pipeline(config=cfg)
    out = emit_executive_workbook_from_pipeline(result, tmp_path / f"{scenario}.xlsx")

    wb = openpyxl.load_workbook(out)
    for sheet in _FINANCE_SHEETS:
        ws = wb[sheet]
        # header row + at least one data row for every technology
        assert ws.max_row >= 2, (scenario, sheet, ws.max_row)
