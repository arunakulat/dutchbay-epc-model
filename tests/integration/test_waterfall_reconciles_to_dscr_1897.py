"""The cash-flow waterfall states its CFADS basis and reconciles to the covenant DSCR (#1897).

The #924 study (O-2) found the lender report's waterfall netting debt service against the
project-basis (unlevered-tax) CFADS, so that in the years after the tax losses run out it showed
coverage under 1x and negative cash to equity, while the DSCR profile, on the levered-tax
coverage CFADS, showed the covenant met. These tests run the DutchBay lender case, where the two
bases differ, and tie the waterfall's reconciliation to the engine's annual covenant DSCR.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.three_statement import build_cashflow_waterfall

ROOT = Path(__file__).resolve().parents[2]
LENDER = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def lender_result() -> Mapping[str, Any]:
    return run_v14_pipeline(config=dict(load_scenario_config(str(LENDER))))


def _rows(result: Mapping[str, Any]) -> Any:
    return result["annual_rows"]


def test_the_lender_case_has_years_where_the_bases_disagree(
    lender_result: Mapping[str, Any],
) -> None:
    """Non-vacuity: the project-basis CFADS falls short of debt service in some year."""
    wf = build_cashflow_waterfall(
        _rows(lender_result), debt_result=lender_result["debt_result"]
    )
    short = [
        r
        for r in wf.rows
        if r.scheduled_debt_service > 0 and r.cfads < r.scheduled_debt_service
    ]
    assert short, "the lender case no longer has a year where the bases disagree"
    for r in short:
        assert r.cash_to_equity < 0
        assert r.covenant_dscr is not None and r.covenant_dscr >= 1.0


def test_every_waterfall_year_reconciles_to_the_engine_covenant_dscr(
    lender_result: Mapping[str, Any],
) -> None:
    debt = lender_result["debt_result"]
    wf = build_cashflow_waterfall(_rows(lender_result), debt_result=debt)
    assert wf.has_coverage_basis
    by_year = {float(k): v for k, v in debt["dscr_by_year"].items()}
    checked = 0
    for r in wf.rows:
        assert r.coverage_cfads is not None and r.tax_basis_difference is not None
        assert math.isclose(
            r.cfads + r.tax_basis_difference, r.coverage_cfads, abs_tol=1e-6
        )
        if r.scheduled_debt_service <= 0:
            assert r.covenant_dscr is None
            continue
        engine = by_year.get(float(r.year))
        assert engine is not None, r.year
        assert r.covenant_dscr == pytest.approx(engine, rel=1e-9), r.year
        checked += 1
    assert checked >= 10


def test_without_a_debt_result_no_dscr_is_claimed(
    lender_result: Mapping[str, Any],
) -> None:
    wf = build_cashflow_waterfall(_rows(lender_result))
    assert wf.has_coverage_basis
    assert all(r.covenant_dscr is None and r.senior_fee is None for r in wf.rows)


def test_rows_without_coverage_cfads_keep_the_old_waterfall() -> None:
    rows = [
        {
            "year": 1,
            "cf_pre_debt": 10.0,
            "debt_service_total": 8.0,
            "balloon_resolution": 0.0,
            "cf_after_debt": 2.0,
        }
    ]
    wf = build_cashflow_waterfall(rows)
    assert not wf.has_coverage_basis
    assert wf.total_coverage_cfads is None
    assert wf.rows[0].coverage_cfads is None


def test_the_report_states_the_basis_and_prints_the_reconciliation(
    lender_result: Mapping[str, Any],
) -> None:
    from app.reports.renderer import render_report_html
    from app.reports.report_orchestration import (
        ORDINARY_REPORT_SENSITIVITY_PROFILE,
        build_report_context_from_case,
        compute_report_sensitivity,
        report_case_from_pipeline_result,
    )

    scenario = dict(load_scenario_config(str(LENDER)))
    case = report_case_from_pipeline_result(
        lender_result,
        scenario_config=scenario,
        scenario_variant=LENDER.stem,
        generated_at="2026-11-22T00:00:00+00:00",
    )
    bundle = compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )
    ctx = build_report_context_from_case(case, bundle)
    assert ctx.cashflow_waterfall is not None
    assert ctx.cashflow_waterfall.has_coverage_basis
    html = render_report_html(ctx)
    section = html[html.index("Cash-Flow Waterfall by Payment Priority") :]
    assert "CFADS in this table is the project basis" in section
    assert "Reconciliation to the DSCR covenant" in section
    debt = lender_result["debt_result"]
    dscrs = [
        r.covenant_dscr
        for r in ctx.cashflow_waterfall.rows
        if r.covenant_dscr is not None
    ]
    assert min(dscrs) == pytest.approx(
        min(v for v in debt["dscr_by_year"].values() if v is not None), rel=1e-9
    )
