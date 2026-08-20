"""End-to-end: wizard inputs → full pipeline → rendered lender report (#481, RPT-7/8).

The existing ``tests/integration/test_assessment_report.py`` exercises the SOLAR script, not the
lender report. This is the missing real one: it drives a ``WindFarmInputs`` submission through the
exact production report path (scenario → ``run_finance_case`` → ``build_report_context`` →
``render_report_html``) and asserts that the live pipeline KPIs reach the report and that every
major section — including the cash-flow waterfall (#481 RPT-2) and the three statements (#479) —
renders and stays internally consistent.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Tuple

import pytest

import app.api.main as api_main
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.renderer import render_report_html, render_report_pdf
from app.reports.report_model import ReportContext, build_report_context
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)
from app.services.pipeline_service import run_finance_case

GENERATED_AT = "2026-07-01T00:00:00+00:00"


# The real 15 x 10.64 MW nameplate (159.6 MW x 0.332) reconciles with the frozen lender-case AEP,
# so the service-seam AEP-reconciliation guard passes — the same inputs the API smoke uses. Typed
# Dict[str, Any] so the ``**`` unpacking does not trip the WindFarmInputs default-arg check (the
# pattern test_api.py uses).
_VALID_KW: Dict[str, Any] = {
    "site_name": "DutchBay E2E",
    "location": "Kalpitiya",
    "capacity_mw": 159.6,
    "capacity_factor": 0.332,
    "project_life_years": 20,
    "ppa_price_lkr_per_kwh": 20.30,
    "ppa_term_years": 20,
    "capex_total_usd": 159_600_000.0,
    "opex_annual_usd": 5_000_000.0,
    "fx_start_lkr_per_usd": 333.79,
}


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(**_VALID_KW)


def _empty_bounded_sensitivity(
    scenario: Dict[str, Any],
) -> ReportSensitivityBundle:
    """Build metadata-complete bounded sensitivity with no live sweeps."""
    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: None,
        morris_computer=lambda _scenario, **_kwargs: None,
        pawn_computer=lambda _scenario, **_kwargs: None,
    )


def _render_deterministic() -> Tuple[CaseResult, Dict[str, Any], ReportContext, str]:
    """Run the production report path once (tornado/global-SA omitted to stay fast + deterministic).

    Returns the case result, the raw pipeline result, the report context and the rendered HTML.
    """
    inputs = _inputs()
    scenario = inputs.to_scenario_config()
    result = run_finance_case(scenario)
    case = CaseResult.from_pipeline_result(
        result, scenario_variant=inputs.scenario_variant
    )
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        inputs=inputs,
        scenario_config=scenario,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        tornado=None,
        global_sa=None,
    )
    return case, result, ctx, render_report_html(ctx)


def test_lender_report_renders_every_section_with_live_kpis() -> None:
    case, result, ctx, html = _render_deterministic()

    assert case.status == "success"
    # The quantitative + narrative blocks are all populated for a real run.
    assert ctx.finance is not None
    assert ctx.cashflow_waterfall is not None
    assert len(ctx.cashflow_waterfall.rows) == _VALID_KW["project_life_years"]
    assert ctx.three_statement is not None and ctx.three_statement.tie_outs_pass
    assert any(
        a.impact for a in ctx.assumptions
    )  # the deepened assumptions register (RPT-2)
    assert ctx.risk_register  # config-authored risk register
    fx_mitigation = next(
        row.mitigation for row in ctx.risk_register if row.category == "Revenue / FX"
    )
    assert "Manifest-bound resolved inputs use a deterministic FX path" in fx_mitigation
    assert "333.79 LKR per USD" in fx_mitigation
    assert "5.89% annual LKR depreciation" in fx_mitigation
    assert "source mode fixed" in fx_mitigation
    assert "IMF projections" not in html

    # The live pipeline KPIs reach the rendered report (not placeholders). Assert the minimum DSCR
    # AND a uniquely-identifying value (project NPV) so the proof cannot be satisfied by a template
    # constant — the covenant floor also renders as "1.30x", whereas the NPV dollar figure is the
    # live run's alone.
    for key in ("min_dscr", "project_npv"):
        row = next(r for r in ctx.kpi_rows if r.key == key)
        if row.display not in html:
            raise AssertionError(
                f"live KPI {key} ({row.display}) not in rendered report"
            )

    # Every major section header renders.
    for section in (
        "Executive Summary",
        "Key Financial Indicators",
        "Energy Production",
        "Uses of Funds",
        "Debt Structure",
        "Cash-Flow Waterfall by Payment Priority",  # RPT-2 (#481)
        "Financial Statements",  # three-statement (#479)
        "Covenant Assessment",
        "Risk Register",
        "Assumptions Register",
        "Audit Manifest",
    ):
        assert section in html, f"missing report section: {section!r}"

    # The RPT-2 / RPT-4 specifics introduced for #481 are present in the rendered output.
    assert "Scheduled debt service" in html and "Impact" in html


def test_feasibility_sections_render_through_the_production_path() -> None:
    """A scenario that declares the CP checklist + feasibility section schema (#708 slices)
    renders those sections through the EXACT production report path (run_finance_case →
    build_report_context → render_report_html), alongside the live KPIs — no new dependency.
    """
    inputs = _inputs()
    scenario = inputs.to_scenario_config()
    scenario["conditions_precedent"] = {
        "items": {
            "ppa_executed": {"status": "satisfied"},
            "esia_approved": {"status": "pending"},
        }
    }
    scenario["feasibility_sections"] = {
        "sections": {
            "executive_investment_thesis": {"status": "complete"},
            "base_case_financial_outputs": {"status": "draft"},
        }
    }
    result = run_finance_case(scenario)
    case = CaseResult.from_pipeline_result(
        result, scenario_variant=inputs.scenario_variant
    )
    ctx = build_report_context(
        case,
        generated_at=GENERATED_AT,
        inputs=inputs,
        scenario_config=scenario,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
    )
    html = render_report_html(ctx)

    assert case.status == "success"
    assert ctx.cp_checklist is not None and ctx.cp_checklist.n_outstanding == 1
    assert ctx.feasibility_sections is not None
    assert ctx.feasibility_sections.total == 20
    for section in ("Conditions Precedent", "Feasibility Report Structure"):
        assert section in html, f"missing feasibility section: {section!r}"
    # the live KPIs still reach the same report (the new sections are additive)
    npv_row = next(r for r in ctx.kpi_rows if r.key == "project_npv")
    assert npv_row.display in html


def test_rendered_waterfall_ties_to_the_headline_cfads() -> None:
    """The cash-flow waterfall in the rendered report is one source of truth with the engine:
    its total CFADS equals the run's headline ``total_cfads_usd`` KPI (haircut included).
    """
    _case, result, ctx, _html = _render_deterministic()
    assert ctx.cashflow_waterfall is not None
    wf = ctx.cashflow_waterfall
    assert wf.total_cfads == pytest.approx(result["kpis"]["total_cfads_usd"], rel=1e-9)
    # Cascade identity holds through the report-facing block, too.
    assert wf.total_cash_to_equity == pytest.approx(
        wf.total_cfads - wf.total_scheduled_debt_service - wf.total_balloon_sweep,
        rel=1e-9,
    )


@pytest.mark.slow
@pytest.mark.report_qualification
def test_complete_production_report_matrix_renders_html_and_pdf() -> None:
    """Qualify one complete production context through both real renderers.

    Finance, tornado, Morris, and PAWN are computed once. Both HTML and PDF then
    consume that same complete context, so the second renderer cannot hide a
    duplicate production computation.
    """
    report_case = run_report_case(
        _inputs(), generated_at=GENERATED_AT, finance_runner=run_finance_case
    )
    bundle = compute_report_sensitivity(
        report_case.scenario_config,
        profile=PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    )
    ctx = build_report_context_from_case(report_case, bundle)
    html = render_report_html(ctx)
    pdf = render_report_pdf(ctx)

    metadata = {row.method: row for row in bundle.methods}
    assert bundle.profile == "production_full"
    assert bundle.tornado is not None
    assert bundle.morris is not None
    assert bundle.pawn is not None
    assert metadata["tornado"].requested_evaluations == 15
    assert metadata["tornado"].effective_evaluations == 15
    assert metadata["tornado"].outcome == "completed"
    assert metadata["morris"].requested_evaluations == 112
    assert metadata["morris"].effective_evaluations == 112
    assert metadata["morris"].outcome == "completed"
    assert metadata["pawn"].requested_evaluations == 256
    assert metadata["pawn"].effective_evaluations == 256
    assert metadata["pawn"].outcome == "completed"
    assert bundle.requested_evaluations == 383
    assert bundle.effective_evaluations == 383
    assert ctx.tornado is bundle.tornado
    assert ctx.global_sa is bundle.morris
    assert ctx.global_sa_pawn is bundle.pawn
    assert ctx.manifest
    assert ctx.manifest.get("config_sha256")
    for section in (
        "Sensitivity Tornado",
        "Morris Screening",
        "PAWN (Distribution-Based)",
    ):
        assert section in html
    assert pdf[:5] == b"%PDF-"


@pytest.mark.slow
def test_lender_report_renders_through_the_auth_gated_http_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Representative e2e: the authenticated HTML route runs finance and renders over HTTP.

    Supplemental tornado/Morris/PAWN services are replaced at their orchestration
    seams because this test verifies auth, timeout, live finance, report-context and
    HTTP assembly. Their real integrated path is retained above as
    ``report_qualification``. The timeout shell's 504 behaviour has separate tests.
    """
    pytest.importorskip("httpx")
    import functools

    from fastapi.testclient import TestClient

    from app.api.auth import hash_password

    generous = float(os.environ.get("DUTCHBAY_SYNC_ROUTE_TIMEOUT_E2E", "600"))
    monkeypatch.setattr(
        api_main,
        "_run_with_timeout",
        functools.partial(api_main._run_with_timeout, timeout=generous),
    )
    monkeypatch.setattr(
        api_main, "compute_report_sensitivity", _empty_bounded_sensitivity
    )

    secret = "test04-real-auth-token-secret"
    monkeypatch.delenv("DUTCHBAY_ENV", raising=False)
    monkeypatch.delenv("DUTCHBAY_JWT_ISSUER", raising=False)
    monkeypatch.delenv("DUTCHBAY_JWT_AUDIENCE", raising=False)
    monkeypatch.setenv("DUTCHBAY_JWT_SECRET", secret)
    monkeypatch.setenv(
        "DUTCHBAY_API_USERS", f"e2e-user:{hash_password('test04-password')}"
    )

    client = TestClient(api_main.app)
    login = client.post(
        "/v1/token",
        json={"username": "e2e-user", "password": "test04-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = client.post(
        "/v1/cases/report.html",
        json=_VALID_KW,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "Cash-Flow Waterfall by Payment Priority" in body
    assert "Assumptions Register" in body
