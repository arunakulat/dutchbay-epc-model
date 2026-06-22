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
