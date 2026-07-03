"""Report wiring for the feasibility CP checklist + section coverage (#708, slice 5/5 of #616).

Pins that build_report_context surfaces the conditions-precedent checklist and the
20-section feasibility coverage as blocks, that the existing renderer renders them
(render-when-present), and that legacy / no-scenario / malformed inputs omit the sections.
KPI-neutral: both blocks are read-only projections of the analytics registers.
"""

from __future__ import annotations

from typing import Dict

from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

GENERATED_AT = "2026-07-03T12:00:00+00:00"

_KPIS: Dict[str, float] = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "equity_npv": -60926463.83,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.10,
}


def _case() -> CaseResult:
    return CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )


# ── conditions-precedent checklist ───────────────────────────────────────────────
def test_cp_checklist_renders_when_declared() -> None:
    scenario = {
        "conditions_precedent": {
            "items": {
                "ppa_executed": {"status": "satisfied"},
                "esia_approved": {"status": "pending"},
                "insurance_in_place": {
                    "status": "waived",
                    "waived_reason": "bridged by sponsor guarantee",
                },
            }
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist is not None
    assert ctx.cp_checklist.n_satisfied == 1
    assert ctx.cp_checklist.n_waived == 1
    assert ctx.cp_checklist.n_outstanding == 1
    assert ctx.cp_checklist.all_satisfied is False
    assert len(ctx.cp_checklist.rows) == 3
    html = render_report_html(ctx)
    assert "Conditions Precedent" in html
    assert "bridged by sponsor guarantee" in html
    assert "gate first drawdown" in html


def test_cp_checklist_omitted_without_declaration() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, scenario_config={})
    assert ctx.cp_checklist is None
    assert "Conditions Precedent" not in render_report_html(ctx)


def test_cp_checklist_omitted_for_legacy_caller() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT)
    assert ctx.cp_checklist is None


def test_cp_checklist_all_satisfied_badge() -> None:
    scenario = {
        "conditions_precedent": {"items": {"ppa_executed": {"status": "satisfied"}}}
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist.all_satisfied is True
    assert "No outstanding conditions" in render_report_html(ctx)


def test_malformed_cp_checklist_degrades_to_none() -> None:
    scenario = {"conditions_precedent": {"items": 7}}
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist is None


# ── feasibility section coverage ─────────────────────────────────────────────────
def test_feasibility_sections_render_when_declared() -> None:
    scenario = {
        "feasibility_sections": {
            "sections": {
                "executive_investment_thesis": {"status": "complete"},
                "resource_and_energy_yield": {"status": "draft"},
                "optimization_alternatives_analysis": {
                    "status": "not_applicable",
                    "na_reason": "single fixed configuration",
                },
            }
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.feasibility_sections is not None
    assert ctx.feasibility_sections.n_complete == 1
    assert ctx.feasibility_sections.n_draft == 1
    assert ctx.feasibility_sections.n_not_applicable == 1
    assert ctx.feasibility_sections.total == 20
    assert ctx.feasibility_sections.all_complete is False
    # rendered in report order: thesis (financial) before resource (technical)
    assert [r.name for r in ctx.feasibility_sections.rows] == [
        "executive_investment_thesis",
        "resource_and_energy_yield",
        "optimization_alternatives_analysis",
    ]
    html = render_report_html(ctx)
    assert "Feasibility Report Structure" in html
    assert "Executive investment thesis" in html


def test_feasibility_sections_omitted_without_declaration() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT, scenario_config={})
    assert ctx.feasibility_sections is None
    assert "Feasibility Report Structure" not in render_report_html(ctx)


def test_feasibility_sections_omitted_for_legacy_caller() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT)
    assert ctx.feasibility_sections is None


def test_malformed_feasibility_sections_degrades_to_none() -> None:
    scenario = {"feasibility_sections": {"sections": 7}}
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.feasibility_sections is None


# ── the full feasibility document assembles through the existing renderer ─────────
def test_all_feasibility_blocks_render_from_one_context() -> None:
    scenario = {
        "conditions_precedent": {"items": {"ppa_executed": {"status": "pending"}}},
        "feasibility_sections": {
            "sections": {"executive_investment_thesis": {"status": "complete"}}
        },
        "evidence_register": {
            "entries": {
                "tariff": {
                    "source": "signed PPA",
                    "as_of": "2026",
                    "tier": "contracted",
                }
            }
        },
        "development_readiness": {"items": {"financing": {"status": "red"}}},
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    # every feasibility slice's block is present on the one context
    assert ctx.cp_checklist is not None
    assert ctx.feasibility_sections is not None
    assert ctx.ic_summary is not None  # slice 3 (#706)
    html = render_report_html(ctx)
    # and the existing renderer emits every section from that single context
    for heading in (
        "Conditions Precedent",
        "Feasibility Report Structure",
        "Investment Committee — Red Flags",
        "Assumption Evidence Register",
    ):
        assert heading in html
