"""Tests for surfacing the refinanced-balloon coverage block (#1491)."""

from __future__ import annotations

import html as html_lib
import re
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    build_report_context,
    fmt_ratio_pct,
    fmt_usd,
    fmt_x,
)

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


# The caveat is the protective part of this block under the F-5 HOLD, so it is pinned
# word for word here, in the test's own copy, not read back from the module (#1657 A-3).
EXPECTED_CAVEAT = (
    "Assumed refinance terms only (assumption_no_term_sheet — no executed term sheet). "
    "Under the F-5 bar, these coverage figures support no covenant, lender, or IC "
    "representation until the within-year event calendar (#1395) and real refinance "
    "terms land."
)


def _section(html: str) -> str:
    """The rendered refinance section, from its heading to the end of its page."""
    start = html.index("Refinanced Balloon Coverage")
    return html[start : html.index("</section>", start)]


def _cells(row_html: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
        for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)
    ]


def test_lender_case_block_projects_the_engine_field_for_field() -> None:
    """Every figure shown is the engine's own, in the cell that names it (#1657 A-3)."""
    full = evaluate_with_overrides(str(_LENDER_CFG), return_full_result=True)
    debt_result = full["debt_result"]
    refi = debt_result["refinance"]
    case = CaseResult.from_pipeline_result(full, scenario_variant="lendercase")
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, debt_result=debt_result, run_result=full
    )
    block = ctx.refinance_coverage
    assert block is not None
    assert block.caveat == EXPECTED_CAVEAT
    for field in (
        "terms_basis",
        "tenor_years",
        "rate_premium",
        "rate",
        "principal_usd",
        "total_service_usd",
        "total_interest_usd",
        "min_coverage",
        "coverage_floor",
        "coverage_breach",
    ):
        assert getattr(block, field) == refi[field], field
    assert block.rate != block.rate_premium
    years = {
        int(e["debt_period"]): int(e["year"])
        for e in debt_result["annual_row_debt_period_map"]
    }
    assert len(block.coverage_by_period) == len(refi["coverage_by_period"]) == 3
    for row, item in zip(
        block.coverage_by_period, refi["coverage_by_period"], strict=True
    ):
        assert row.debt_period == item["period"]
        assert row.year == years[item["period"]]
        for field in (
            "service_usd",
            "interest_usd",
            "principal_usd",
            "cash_available_usd",
        ):
            assert getattr(row, field) == item[field], field
        assert row.coverage == item["coverage"]
        assert row.service_usd == pytest.approx(row.interest_usd + row.principal_usd)
        assert row.interest_usd != pytest.approx(row.principal_usd)

    section = _section(render_report_html(ctx))
    assert html_lib.unescape(re.sub(r"\s+", " ", section)).count(EXPECTED_CAVEAT) == 1
    summary = {
        cells[0]: cells[1]
        for cells in (_cells(r) for r in re.findall(r"<tr>(.*?)</tr>", section, re.S))
        if len(cells) == 2
    }
    assert summary["Assumed refinance tenor"] == f"{refi['tenor_years']} years"
    assert summary["Rate premium / all-in rate"] == (
        f"{fmt_ratio_pct(refi['rate_premium'])} / {fmt_ratio_pct(refi['rate'])}"
    )
    assert summary["Refinanced principal"] == fmt_usd(refi["principal_usd"])
    assert summary["Total refinance service / interest"] == (
        f"{fmt_usd(refi['total_service_usd'])} / {fmt_usd(refi['total_interest_usd'])}"
    )
    assert summary["Minimum refinance coverage / floor"] == (
        f"{fmt_x(refi['min_coverage'])} / {fmt_x(refi['coverage_floor'])} COVERAGE BREACH"
    )
    body = section[section.index("<tbody>", section.index("Annual refinance")) :]
    shown = [_cells(r) for r in re.findall(r"<tr>(.*?)</tr>", body, re.S)]
    assert shown == [
        [
            str(years[item["period"]]),
            fmt_usd(item["service_usd"]),
            fmt_usd(item["interest_usd"]),
            fmt_usd(item["principal_usd"]),
            fmt_usd(item["cash_available_usd"]),
            fmt_x(item["coverage"]),
        ]
        for item in refi["coverage_by_period"]
    ]


def test_sample_block_renders_the_caveat_verbatim() -> None:
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis={"min_dscr": 1.30}
    )
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, debt_result=_sample_refinance_debt_result()
    )
    assert ctx.refinance_coverage is not None
    assert ctx.refinance_coverage.caveat == EXPECTED_CAVEAT
    section = html_lib.unescape(re.sub(r"\s+", " ", _section(render_report_html(ctx))))
    assert f"F-5 Non-Reliance Caveat: {EXPECTED_CAVEAT}" in re.sub(
        r"<[^>]+>", "", section
    )


@pytest.mark.parametrize("change", ["no_breach_flag", "unmapped_period"])
def test_incomplete_refinance_result_fails_closed(change: str) -> None:
    """An absent breach flag or unmapped period is refused, not shown as safe (A-5)."""
    debt = _sample_refinance_debt_result()
    if change == "no_breach_flag":
        del debt["refinance"]["coverage_breach"]
        match = "coverage_breach"
    else:
        debt["annual_row_debt_period_map"].pop()
        match = "refinance period 21"
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis={"min_dscr": 1.30}
    )
    with pytest.raises(ValueError, match=match):
        build_report_context(case, generated_at=GENERATED_AT, debt_result=debt)
