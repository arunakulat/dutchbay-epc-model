"""Tests for surfacing the refinanced-balloon coverage block (#1491)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from analytics.evaluation_v14 import evaluate_with_overrides
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

GENERATED_AT = "2026-11-13T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _sample_refinance_debt_result() -> Dict[str, Any]:
    return {
        "debt_total_usd": 110_662_500.0,
        "gearing": 0.5675,
        "annual_row_debt_period_map": [
            {
                "annual_row_index": 16,
                "year": 17,
                "debt_period": 19,
                "cfads_usd": 4_200_000.0,
            },
            {
                "annual_row_index": 17,
                "year": 18,
                "debt_period": 20,
                "cfads_usd": 3_800_000.0,
            },
            {
                "annual_row_index": 18,
                "year": 19,
                "debt_period": 21,
                "cfads_usd": 3_400_000.0,
            },
        ],
        "refinance": {
            "terms_basis": "assumption_no_term_sheet",
            "tenor_years": 3,
            "rate_premium": 0.02,
            "rate": 0.1218,
            "principal_usd": 30_000_000.0,
            "total_service_usd": 37_200_000.0,
            "total_interest_usd": 7_200_000.0,
            "coverage_by_period": [
                {
                    "period": 19,
                    "service_usd": 12_400_000.0,
                    "interest_usd": 3_654_000.0,
                    "principal_usd": 8_746_000.0,
                    "cash_available_usd": 4_200_000.0,
                    "coverage": 0.34,
                },
                {
                    "period": 20,
                    "service_usd": 12_400_000.0,
                    "interest_usd": 2_588_737.0,
                    "principal_usd": 9_811_263.0,
                    "cash_available_usd": 3_800_000.0,
                    "coverage": 0.31,
                },
                {
                    "period": 21,
                    "service_usd": 12_400_000.0,
                    "interest_usd": 1_393_665.0,
                    "principal_usd": 11_006_335.0,
                    "cash_available_usd": 3_400_000.0,
                    "coverage": 0.28,
                },
            ],
            "min_coverage": 0.28,
            "coverage_floor": 1.30,
            "coverage_breach": True,
        },
    }


def test_refinance_coverage_block_omitted_without_refinance() -> None:
    case = CaseResult(
        status="success", scenario_variant="basecase", kpis={"min_dscr": 1.30}
    )
    ctx = build_report_context(case, generated_at=GENERATED_AT, debt_result={})
    assert ctx.refinance_coverage is None
    html = render_report_html(ctx)
    assert "Refinanced Balloon Coverage" not in html


def test_refinance_coverage_block_renders_terms_breach_and_f5_caveat() -> None:
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis={"min_dscr": 1.30}
    )
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        debt_result=_sample_refinance_debt_result(),
    )
    block = ctx.refinance_coverage
    assert block is not None
    assert block.terms_basis == "assumption_no_term_sheet"
    assert block.coverage_breach is True
    assert [row.year for row in block.coverage_by_period] == [17, 18, 19]
    assert "assumption_no_term_sheet" in block.caveat
    assert "F-5" in block.caveat
    assert "#1395" in block.caveat

    html = render_report_html(ctx)
    assert "Refinanced Balloon Coverage" in html
    assert "COVERAGE BREACH" in html
    assert "assumption_no_term_sheet" in html
    assert "F-5" in html
    assert "0.34x" in html
    assert "0.28x" in html


def test_lender_case_engine_run_wires_refinance_block_without_dbpl_regression() -> None:
    full = evaluate_with_overrides(str(_LENDER_CFG), return_full_result=True)
    debt_result = full["debt_result"]
    assert isinstance(debt_result.get("refinance"), dict)
    case = CaseResult.from_pipeline_result(full, scenario_variant="lendercase")
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        debt_result=debt_result,
        run_result=full,
    )
    assert ctx.refinance_coverage is not None
    assert ctx.refinance_coverage.coverage_breach is True
    assert [row.year for row in ctx.refinance_coverage.coverage_by_period] == [
        15,
        16,
        17,
    ]
    assert [row.debt_period for row in ctx.refinance_coverage.coverage_by_period] == [
        17,
        18,
        19,
    ]
    html = render_report_html(ctx)
    assert "COVERAGE BREACH" in html
    assert "F-5 Non-Reliance Caveat" in html
