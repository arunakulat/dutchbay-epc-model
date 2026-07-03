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


def test_non_bool_cp_flag_degrades_to_none_not_crash() -> None:
    # a non-bool enforce raises a plain ValueError in the register; the report must degrade
    # (broadened except), not crash (the #708 Fable review defense-in-depth finding).
    scenario = {
        "conditions_precedent": {
            "enforce": "true",
            "items": {"ppa_executed": {"status": "satisfied"}},
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist is None


def test_off_scale_cp_status_is_surfaced_not_silently_dropped() -> None:
    # The #708 Fable BLOCK: a declared condition with a typo'd/off-scale status must NOT
    # vanish, and must NOT let a green "no outstanding" badge render over it.
    scenario = {
        "conditions_precedent": {
            "items": {
                "ppa_executed": {"status": "satisfied"},
                "esia_approved": {"status": "in_review"},  # off-scale (not pending)
            }
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist is not None
    # the dropped item is surfaced as flagged (not vanished from every view)
    assert "esia_approved" in ctx.cp_checklist.flagged
    assert ctx.cp_checklist.is_clean is False
    html = render_report_html(ctx)
    assert "esia_approved" in html
    # the green "no outstanding conditions" badge must NOT render over an ungraded condition
    assert "No outstanding conditions" not in html
    assert "unresolved entries" in html


def test_only_invalid_cp_items_still_render_the_section() -> None:
    # a checklist whose ONLY declared item is off-scale still renders (surfacing the flag)
    # rather than silently omitting the whole section.
    scenario = {
        "conditions_precedent": {"items": {"ppa_executed": {"status": "bogus"}}}
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.cp_checklist is not None
    assert ctx.cp_checklist.rows == []
    assert "ppa_executed" in ctx.cp_checklist.flagged


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


def test_non_bool_feasibility_flag_degrades_to_none_not_crash() -> None:
    scenario = {
        "feasibility_sections": {
            "require_complete": 1,
            "sections": {"executive_investment_thesis": {"status": "complete"}},
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.feasibility_sections is None


def test_off_scale_feasibility_status_keeps_total_20_and_is_surfaced() -> None:
    # The #708 Fable BLOCK: a section with an off-scale status must not drop the "of N"
    # count below the fixed 20-section skeleton, nor vanish from every view.
    scenario = {
        "feasibility_sections": {
            "sections": {
                "executive_investment_thesis": {"status": "complete"},
                "resource_and_energy_yield": {"status": "in_progress"},  # off-scale
            }
        }
    }
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.feasibility_sections is not None
    assert ctx.feasibility_sections.total == 20  # NOT 19
    assert "resource_and_energy_yield" in ctx.feasibility_sections.flagged
    assert ctx.feasibility_sections.is_clean is False
    html = render_report_html(ctx)
    assert "of 20 canonical sections" in html
    assert "resource_and_energy_yield" in html


def test_off_scale_status_blocks_the_all_addressed_badge() -> None:
    # a full 20-section declaration with ONE typo'd status must not render the green
    # "All sections addressed" badge (all_complete would be True over the survivors).
    from analytics.feasibility_sections import load_feasibility_taxonomy

    names = list(load_feasibility_taxonomy().section_names)
    sections = {n: {"status": "complete"} for n in names}
    sections[names[5]] = {"status": "donezo"}  # off-scale typo on one section
    ctx = build_report_context(
        _case(),
        generated_at=GENERATED_AT,
        scenario_config={"feasibility_sections": {"sections": sections}},
    )
    assert ctx.feasibility_sections is not None
    assert ctx.feasibility_sections.is_clean is False
    html = render_report_html(ctx)
    assert "All sections addressed" not in html
    assert names[5] in ctx.feasibility_sections.flagged


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
