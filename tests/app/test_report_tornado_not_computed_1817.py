"""#1817: a driver the model refused shows as "not computed: <reason>" in the report.

Before #1817 one refused driver removed the whole tornado. The sweep now marks that
driver's bar ``not_computed`` with the reason, and the report renders it last, with no
figures, named in a note, while every other bar renders as before. A not-computed bar is
not an undefined one: no rate failed to solve, so it adds nothing to the undefined count.
"""

from __future__ import annotations

import math
import re

from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context
from app.services.report_tornado import TornadoBlock, compute_report_tornado

_SCENARIO = {"project": {"name": "test"}}
_REASON = "PipelineValidationError: capex.breakdown does not sum to capex.usd_total"
_KPIS = {
    "project_irr": 0.0422,
    "equity_irr": 0.081,
    "project_npv": 1.0,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}


def _bar(
    label: str, impact: float, *, not_computed: str | None = None
) -> TornadoResult:
    low, high = (math.nan, math.nan) if not_computed else (0.04 - impact, 0.04)
    return TornadoResult(
        metric_name="project_irr",
        base_metric=0.04,
        impact_abs=math.nan if not_computed else impact,
        shock_results=[
            ShockResult(
                label=label,
                low_case=low,
                high_case=high,
                base_case=0.04,
                impact_abs=math.nan if not_computed else impact,
            )
        ],
        metadata={"not_computed": not_computed} if not_computed else {},
    )


def _suite() -> SensitivitySuite:
    return SensitivitySuite(
        tornado_results=[
            _bar("CAPEX", 0.0, not_computed=_REASON),
            _bar("OPEX", 0.002),
            _bar("Tariff", 0.03),
        ],
        metadata={
            "undefined_points": 0,
            "undefined_drivers": [],
            "not_computed_drivers": {"capex.usd_total": _REASON},
        },
    )


def _block() -> TornadoBlock:
    block = compute_report_tornado(_SCENARIO, runner=lambda _p, *, metric: _suite())
    assert block is not None
    return block


def test_the_refused_driver_keeps_its_row_last_and_the_rest_render() -> None:
    block = _block()
    assert [r.label for r in block.rows] == ["Tariff", "OPEX", "CAPEX"]
    capex = block.rows[-1]
    assert capex.not_computed == _REASON
    assert capex.low_case is None and capex.high_case is None
    assert capex.impact_abs is None
    assert [r.label for r in block.not_computed_rows] == ["CAPEX"]
    assert block.rows[0].impact_abs == 0.03


def test_a_not_computed_bar_is_not_counted_as_undefined() -> None:
    block = _block()
    assert block.undefined_points == 0
    assert block.undefined_drivers == []
    assert not block.has_undefined


def test_the_report_says_not_computed_with_the_reason() -> None:
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    html = render_report_html(
        build_report_context(
            case, generated_at="2026-11-21T00:00:00+00:00", tornado=_block()
        )
    )
    start = html.index("Sensitivity Tornado")
    section = html[start : html.index("</section>", start)]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", section))
    assert "then drivers not computed" in text
    assert "CAPEX not computed" in text
    assert f"CAPEX: not computed: {_REASON}." in text
    # The computed bars still show their figures, and no undefined note appears.
    assert "Tariff" in text and "OPEX" in text
    assert "tornado-undefined-note" not in section
    assert "tornado-not-computed-note" in section
