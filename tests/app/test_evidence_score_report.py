"""Report wiring for the bankability evidence-completeness score (#707, slice 4/5 of #616).

Pins that build_report_context surfaces the score as an EvidenceScoreBlock and the template
renders it (render-when-present), and that a legacy caller (no scenario config) omits the
section. KPI-neutral: the block is a read-only projection of analytics.evidence_score.
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


def _scenario(entries: dict) -> dict:
    return {"evidence_register": {"entries": entries}}


def test_context_carries_score_and_template_renders_it() -> None:
    scenario = _scenario(
        {
            "tariff": {"source": "signed PPA", "as_of": "2026", "tier": "contracted"},
            "capex": {
                "source": "SINOHYDRO quote",
                "as_of": "2026",
                "tier": "vendor_quote",
            },
        }
    )
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.evidence_score is not None
    # two of the material assumptions are covered; the rest missing -> a partial score/band
    assert ctx.evidence_score.covered == 2
    assert (
        ctx.evidence_score.total > ctx.evidence_score.covered
    )  # more assumptions exist
    assert 0.0 < ctx.evidence_score.score < 100.0
    assert ctx.evidence_score.band  # a non-empty band label
    html = render_report_html(ctx)
    assert "Bankability Evidence-Completeness Score" in html
    assert ctx.evidence_score.band in html


def test_legacy_caller_without_scenario_omits_the_score_section() -> None:
    ctx = build_report_context(_case(), generated_at=GENERATED_AT)
    assert ctx.evidence_score is None
    html = render_report_html(ctx)
    assert "Bankability Evidence-Completeness Score" not in html


def test_malformed_register_degrades_to_no_score_section() -> None:
    # a structurally malformed entries container raises in the register builder; the
    # score block degrades to None (section omitted) rather than break the report.
    scenario = {"evidence_register": {"entries": 7}}
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.evidence_score is None


def test_score_block_rows_cover_every_material_assumption() -> None:
    scenario = _scenario(
        {"tariff": {"source": "s", "as_of": "2026", "tier": "measured"}}
    )
    ctx = build_report_context(
        _case(), generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert ctx.evidence_score is not None
    assert len(ctx.evidence_score.rows) == ctx.evidence_score.total
    tariff = next(r for r in ctx.evidence_score.rows if r.assumption == "tariff")
    assert tariff.covered is True and tariff.tier == "measured"
