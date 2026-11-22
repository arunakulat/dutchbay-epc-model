"""The cash-flow waterfall states its CFADS basis and reconciles to the covenant DSCR (#1897).

The #924 study (O-2) found the lender report's waterfall netting debt service against the
project-basis (unlevered-tax) CFADS, so that in the years after the tax losses run out it showed
coverage under 1x and negative cash to equity, while the DSCR profile, on the levered-tax
coverage CFADS, showed the covenant met. These tests run the DutchBay lender case, where the two
bases differ, and tie the waterfall's reconciliation to the engine's annual covenant DSCR.
"""

from __future__ import annotations

import copy
import math
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.three_statement import build_cashflow_waterfall

ROOT = Path(__file__).resolve().parents[2]
LENDER = ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
BW_WIND = ROOT / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
TREATMENTS = ("historical_fold", "equity_cfads_match", "construction_capitalized")


def _run(path: Path, treatment: Optional[str] = None) -> Mapping[str, Any]:
    cfg: Dict[str, Any] = copy.deepcopy(dict(load_scenario_config(str(path))))
    if treatment is not None:
        cfg.setdefault("Financing_Terms", {})["bridge_period_treatment"] = treatment
    return run_v14_pipeline(config=cfg)


@pytest.fixture(scope="module")
def lender_result() -> Mapping[str, Any]:
    return _run(LENDER)


@pytest.fixture(scope="module")
def runs() -> Dict[str, Mapping[str, Any]]:
    out = {f"lender:{t}": _run(LENDER, t) for t in TREATMENTS}
    out["bw_wind"] = _run(BW_WIND)
    return out


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


@pytest.mark.parametrize("key", [f"lender:{t}" for t in TREATMENTS] + ["bw_wind"])
def test_every_waterfall_year_reconciles_to_the_engine_covenant_dscr(
    runs: Dict[str, Mapping[str, Any]], key: str
) -> None:
    """Under every bridge treatment, each year ties to the engine's ``dscr_by_year``."""
    result = runs[key]
    debt = result["debt_result"]
    wf = build_cashflow_waterfall(_rows(result), debt_result=debt)
    assert wf.has_coverage_basis
    by_year = {float(k): v for k, v in debt["dscr_by_year"].items()}
    checked = 0
    for r in wf.rows:
        assert r.coverage_cfads is not None
        assert r.fee_in_project_basis is not None and r.tax_basis_difference is not None
        assert r.senior_fee is not None and r.covenant_cfads is not None
        assert math.isclose(
            r.cfads + r.fee_in_project_basis + r.tax_basis_difference,
            r.coverage_cfads,
            abs_tol=1e-6,
        )
        assert r.covenant_cfads == pytest.approx(r.coverage_cfads - r.senior_fee)
        if not r.covenant_debt_service:
            assert r.covenant_dscr is None
            continue
        engine = by_year.get(float(r.year))
        assert engine is not None, r.year
        assert r.covenant_dscr == pytest.approx(engine, rel=1e-9), r.year
        checked += 1
    assert checked >= 5


def test_the_senior_fee_is_not_counted_as_tax(
    runs: Dict[str, Mapping[str, Any]],
) -> None:
    """In a year with no tax, the levered and unlevered tax agree: no tax-basis difference.

    Non-vacuity: those years carry a senior fee, which the old single "difference" column
    reported as tax.
    """
    checked = 0
    for key in ("lender:historical_fold", "bw_wind"):
        result = runs[key]
        wf = build_cashflow_waterfall(_rows(result), debt_result=result["debt_result"])
        for r, row in zip(wf.rows, _rows(result), strict=True):
            if float(row.get("tax_lkr") or 0.0) == 0.0:
                assert r.tax_basis_difference == pytest.approx(0.0, abs=1e-6), r.year
                assert r.senior_fee and r.senior_fee > 0.0
                checked += 1
    assert checked >= 3


def test_a_capitalised_bridge_is_still_covered_by_year_one(
    runs: Dict[str, Mapping[str, Any]],
) -> None:
    capitalised = runs["lender:construction_capitalized"]
    debt = capitalised["debt_result"]
    wf = build_cashflow_waterfall(_rows(capitalised), debt_result=debt)
    first = wf.rows[0]
    assert first.covenant_debt_service is not None
    # Non-vacuity: the waterfall leaves the bridge out, the covenant does not.
    assert first.covenant_debt_service > first.scheduled_debt_service + 1.0
    folded = build_cashflow_waterfall(
        _rows(runs["lender:historical_fold"]),
        debt_result=runs["lender:historical_fold"]["debt_result"],
    ).rows[0]
    assert first.covenant_debt_service == pytest.approx(folded.scheduled_debt_service)


def test_without_a_debt_result_no_dscr_is_claimed(
    lender_result: Mapping[str, Any],
) -> None:
    wf = build_cashflow_waterfall(_rows(lender_result))
    assert wf.has_coverage_basis
    assert all(
        r.covenant_dscr is None
        and r.senior_fee is None
        and r.tax_basis_difference is None
        and r.covenant_debt_service is None
        for r in wf.rows
    )


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


def _report_html(result: Mapping[str, Any], path: Path) -> Any:
    from app.reports.renderer import render_report_html
    from app.reports.report_orchestration import (
        ORDINARY_REPORT_SENSITIVITY_PROFILE,
        build_report_context_from_case,
        compute_report_sensitivity,
        report_case_from_pipeline_result,
    )

    scenario = dict(load_scenario_config(str(path)))
    case = report_case_from_pipeline_result(
        result,
        scenario_config=scenario,
        scenario_variant=path.stem,
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
    html = render_report_html(ctx)
    start = html.index("Cash-Flow Waterfall by Payment Priority")
    return ctx, re.sub(r"\s+", " ", html[start : html.index("</section>", start)])


def test_the_report_states_the_basis_and_prints_the_reconciliation(
    lender_result: Mapping[str, Any],
) -> None:
    ctx, section = _report_html(lender_result, LENDER)
    assert ctx.cashflow_waterfall is not None
    wf = ctx.cashflow_waterfall
    assert wf.has_coverage_basis
    assert "CFADS in this table is the project basis" in section
    assert "Reconciliation to the DSCR covenant" in section
    assert "Senior fee in project basis" in section
    assert "still met" not in section
    assert wf.shortfall_years
    assert f"({', '.join(str(y) for y in wf.shortfall_years)})" in section
    assert wf.below_one_years == []
    assert "below 1.00x" not in section
    debt = lender_result["debt_result"]
    dscrs = [r.covenant_dscr for r in wf.rows if r.covenant_dscr is not None]
    assert min(dscrs) == pytest.approx(
        min(v for v in debt["dscr_by_year"].values() if v is not None), rel=1e-9
    )


def test_the_basis_note_states_a_covenant_shortfall_where_there_is_one(
    runs: Dict[str, Mapping[str, Any]],
) -> None:
    """Blue Whale wind's year-1 covenant DSCR is under 1.00x: the note says so."""
    ctx, section = _report_html(runs["bw_wind"], BW_WIND)
    wf = ctx.cashflow_waterfall
    assert wf is not None and wf.below_one_years
    years = ", ".join(str(y) for y in wf.below_one_years)
    assert "The covenant DSCR is below 1.00x in year" in section
    assert f"{years}." in section
    assert "still met" not in section


def test_the_report_names_a_year_whose_covenant_service_differs(
    runs: Dict[str, Mapping[str, Any]],
) -> None:
    ctx, section = _report_html(runs["lender:construction_capitalized"], LENDER)
    wf = ctx.cashflow_waterfall
    assert wf is not None and wf.service_differs_years == [1]
    assert "it differs from the waterfall's scheduled debt service" in section
    _, folded = _report_html(runs["lender:historical_fold"], LENDER)
    assert "it differs from the waterfall's scheduled debt service" not in folded
