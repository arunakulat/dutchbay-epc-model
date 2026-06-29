"""Tests for the report renderer (HTML always; PDF gated on optional WeasyPrint)."""

from __future__ import annotations

from typing import Dict

import pytest

from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.renderer import (
    ReportDependencyError,
    render_report_html,
    render_report_pdf,
)
from app.reports.report_model import build_report_context

GENERATED_AT = "2026-06-22T12:00:00+00:00"

_KPIS: Dict[str, float] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57994285.93,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}


def _context():
    inputs = WindFarmInputs(
        site_name="Dutch Bay",
        location="Kalpitiya",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    return build_report_context(case, generated_at=GENERATED_AT, inputs=inputs)


def test_html_contains_core_content() -> None:
    html = render_report_html(_context())
    assert html.startswith("<!DOCTYPE html>")
    assert "Dutch Bay" in html
    assert "4.22%" in html  # project IRR display
    assert "1.30x" in html  # min DSCR display
    assert "-$57,994,286" in html  # project NPV display
    assert "Value-destructive" in html  # verdict headline
    assert "Important Notice" in html  # disclaimer section
    assert "Covenant Assessment" in html


def test_html_contains_risk_register() -> None:
    html = render_report_html(_context())
    assert "Risk Register" in html
    assert "Mitigation" in html  # table header
    assert "Revenue / FX" in html  # a seeded risk category
    assert 'class="badge sev-high"' in html  # severity badge rendered
    assert ">High<" in html  # severity label capitalized


def test_html_contains_development_readiness_when_supplied() -> None:
    inputs = WindFarmInputs(
        site_name="Dutch Bay",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    scenario = {
        "development_readiness": {
            "items": {
                "environmental_social": {"status": "green", "note": "ESIA final"},
                "financing": {"status": "red", "note": "not committed"},
            }
        }
    }
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, inputs=inputs, scenario_config=scenario
    )
    html = render_report_html(ctx)
    assert "Development Readiness" in html
    assert "environmental_social" in html
    assert 'class="badge rag-red"' in html  # financing red badge
    assert 'class="badge rag-green"' in html  # ESIA green badge


def test_html_omits_readiness_section_body_when_absent() -> None:
    # Default context passes no scenario_config -> the section renders its empty-state note.
    html = render_report_html(_context())
    assert "No development-readiness register was supplied" in html


def test_html_contains_finance_sections_when_supplied() -> None:
    # With a scenario_config + debt_result the quantitative lender sections render (RPT-1).
    inputs = WindFarmInputs(
        site_name="Dutch Bay",
        capacity_mw=159.6,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000,
        opex_annual_usd=5_000_000,
        fx_start_lkr_per_usd=333.79,
    )
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    scenario = {
        "resource": {"wind": {"aep_gwh": 464.3, "capacity_factor": 0.332}},
        "project": {"capacity_mw": 159.6},
        "finance": {"capex_total_usd": 159_600_000.0},
    }
    debt = {
        "debt_total": 65_835_000.0,
        "tenor_years": 15,
        "min_dscr": 1.30,
        "dual_dscr": {"solved_gearing": 0.4125},
        "principal_by_tranche": {"senior": 65_835_000.0},
        "raw_dscr_series": [None, None, 1.308],
        "debt_outstanding": [65_835_000.0, 65_835_000.0, 60_000_000.0],
        "debt_service_total": [0.0, 0.0, 8_000_000.0],
        "funding": {
            "sources_and_uses": {
                "uses": {"capex_usd": 159_600_000.0, "idc_usd": 10_287_933.22},
                "sources": {
                    "senior_debt_usd": 76_122_933.22,
                    "equity_usd": 93_765_000.0,
                },
                "uses_total_usd": 169_887_933.22,
                "sources_total_usd": 169_887_933.22,
                "balanced": True,
            }
        },
    }
    html = render_report_html(
        build_report_context(
            case,
            generated_at=GENERATED_AT,
            inputs=inputs,
            scenario_config=scenario,
            debt_result=debt,
        )
    )
    assert "Energy Production (P50 / P90)" in html
    assert "464.3 GWh" in html  # P50 net AEP rendered via fmt_gwh
    assert "Sources &amp; Uses of Funds" in html
    assert ">Balanced<" in html  # sources-and-uses balance badge
    assert "Debt Structure &amp; DSCR Profile" in html
    assert "Annual DSCR profile" in html
    assert "1.31x" in html  # operating-year DSCR rounded
    assert "$159,600,000" in html  # CAPEX use rendered via fmt_usd


def test_html_contains_tornado_when_supplied() -> None:
    from app.services.report_tornado import TornadoBlock, TornadoRow

    tornado = TornadoBlock(
        metric="project_irr",
        rows=[
            TornadoRow(
                label="Tariff",
                base=0.0116,
                low_case=-0.0031,
                high_case=0.0249,
                impact_abs=0.0280,
            ),
            TornadoRow(
                label="CAPEX",
                base=0.0116,
                low_case=0.0222,
                high_case=0.0025,
                impact_abs=0.0197,
            ),
        ],
    )
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    html = render_report_html(
        build_report_context(case, generated_at=GENERATED_AT, tornado=tornado)
    )
    assert "Sensitivity Tornado" in html
    assert "Downside IRR" in html  # table header
    assert "Tariff" in html and "CAPEX" in html  # drivers rendered (widest first)
    assert "2.80%" in html  # swing rendered via fmt_ratio_pct(0.0280)


def test_html_omits_tornado_section_when_absent() -> None:
    # Default context passes no tornado -> the section is omitted entirely.
    assert "Sensitivity Tornado" not in render_report_html(_context())


def test_html_covenant_badges_reflect_verdict() -> None:
    html = render_report_html(_context())
    # IRR below hurdle and equity negative -> both fail badges present.
    assert "Below hurdle" in html
    assert "Negative" in html
    # DSCR at target and balloon within ceiling -> pass badges present.
    assert "Met" in html
    assert "Within" in html


def test_html_escapes_site_name() -> None:
    inputs = WindFarmInputs(
        site_name="A & B <Wind>",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    )
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    html = render_report_html(
        build_report_context(case, generated_at=GENERATED_AT, inputs=inputs)
    )
    assert "A &amp; B &lt;Wind&gt;" in html  # autoescape engaged
    assert "<Wind>" not in html


def test_pdf_without_weasyprint_raises_clear_error() -> None:
    # In CI/local the optional extra is absent, so this exercises the fail-loud
    # path. When WeasyPrint *is* installed, skip (the happy path is covered below).
    try:
        import weasyprint  # noqa: F401
    except ImportError:
        with pytest.raises(ReportDependencyError, match="WeasyPrint"):
            render_report_pdf(_context())
    else:  # pragma: no cover - only when the optional extra is installed
        pytest.skip("WeasyPrint installed; error path not applicable")


def test_pdf_render_when_weasyprint_available() -> None:
    pytest.importorskip("weasyprint")
    pdf = render_report_pdf(_context())
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"
