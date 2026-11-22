"""The lender report says when its tornado was not computed, and carries F-5 (#1818).

Follow-ups F-B and F-C of the #1803 domain review: a degraded tornado used to vanish
silently from the app/api lender report, and that route set no F-5 notice.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

import pytest

from analytics.executive_workbook import EXECUTIVE_WORKBOOK_F5_CAVEAT
from app.models.inputs import WindFarmInputs
from app.reports.renderer import render_report_html
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
    tornado_not_computed_reason,
)
from app.services.report_global_sa import GlobalSABlock
from app.services.report_tornado import TornadoBlock, TornadoRow

GENERATED_AT = "2026-11-21T00:00:00+00:00"


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="Tornado notice",
        capacity_mw=148.9,  # 14 x 10.638 MW, reconciles with the frozen AEP
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )


def _tornado(rows: int) -> TornadoBlock:
    return TornadoBlock(
        metric="project_irr",
        rows=[TornadoRow(label=f"driver-{i}", impact_abs=0.01) for i in range(rows)],
    )


def _bundle(
    scenario: Mapping[str, Any], tornado: Optional[TornadoBlock]
) -> ReportSensitivityBundle:
    def _none(*_args: Any, **_kwargs: Any) -> Optional[GlobalSABlock]:
        return None

    return compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: tornado,
        morris_computer=_none,
        pawn_computer=_none,
    )


@pytest.fixture(scope="module")
def case() -> Any:
    return run_report_case(_inputs(), generated_at=GENERATED_AT)


def _section(html: str) -> str:
    return html.split("<h2>Sensitivity Tornado", 1)[1].split("</section>", 1)[0]


def test_reason_is_none_exactly_when_the_tornado_renders(case: Any) -> None:
    assert (
        tornado_not_computed_reason(_bundle(case.scenario_config, _tornado(3))) is None
    )
    reason = tornado_not_computed_reason(_bundle(case.scenario_config, None))
    assert reason == (
        "not computed: the one-at-a-time sweep returned no usable driver rows "
        "(outcome: degraded)"
    )


def test_a_degraded_tornado_is_said_not_computed(case: Any) -> None:
    ctx = build_report_context_from_case(case, _bundle(case.scenario_config, None))
    html = render_report_html(ctx)
    section = _section(html)
    assert (
        "<strong>Not computed.</strong> not computed: the one-at-a-time sweep"
        in section
    )
    assert "(outcome: degraded)" in section
    assert "<table" not in section
    assert '<p class="muted f5-caption"><strong>F-5:</strong>' in section


def test_an_empty_tornado_block_is_said_not_computed(case: Any) -> None:
    ctx = build_report_context_from_case(
        case, _bundle(case.scenario_config, _tornado(0))
    )
    assert ctx.tornado_not_computed is not None
    assert "Not computed." in _section(render_report_html(ctx))


def test_a_computed_tornado_carries_the_f5_caption_and_no_notice(case: Any) -> None:
    ctx = build_report_context_from_case(
        case, _bundle(case.scenario_config, _tornado(3))
    )
    assert ctx.tornado_not_computed is None
    section = _section(render_report_html(ctx))
    assert "<table" in section
    assert "Not computed." not in section
    assert f"<strong>F-5:</strong> {EXECUTIVE_WORKBOOK_F5_CAVEAT}" in section


def test_the_api_route_report_carries_the_f5_cover_notice(case: Any) -> None:
    ctx = build_report_context_from_case(
        case, _bundle(case.scenario_config, _tornado(3))
    )
    assert ctx.f5_notice == EXECUTIVE_WORKBOOK_F5_CAVEAT
    cover = render_report_html(ctx).split("<h2>Important Notice</h2>", 1)[0]
    assert "<strong>F-5 non-reliance notice:</strong>" in cover
    assert "no quarterly CFADS or intra-year DSCR figure" in cover


def test_a_context_built_without_the_seam_is_unchanged(case: Any) -> None:
    """Other callers (the capital-risk emitter, direct builders) set F-5 themselves."""
    from app.reports.report_model import build_report_context

    ctx = build_report_context(case.case_result, generated_at=GENERATED_AT)
    assert ctx.tornado_not_computed is None
    html = render_report_html(ctx)
    assert "Sensitivity Tornado" not in html
    assert "f5-caption" not in html
