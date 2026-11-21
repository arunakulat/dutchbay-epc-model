"""#1487: the report tornado shows an undefined point as "undefined", with a note.

#1457 maps an undefined sweep point (``nan``) to ``None``. Before #1487 the tornado
printed it with the em-dash the report uses for an absent value, so a reader could not
tell "no rate solves this case" from "not computed". The KPI table has rendered a
present-but-``None`` value as "undefined" since #1436; the tornado now does the same and
adds a note naming the undefined points and drivers.
"""

from __future__ import annotations

import re

import pytest

from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    _ABSENT,
    build_report_context,
    fmt_ratio_pct,
    fmt_ratio_pct_or_undefined,
)
from app.services.report_tornado import TornadoBlock, TornadoRow

GENERATED_AT = "2026-06-22T12:00:00+00:00"
_KPIS = {
    "project_irr": 0.0422,
    "equity_irr": -0.0246,
    "project_npv": -57994285.93,
    "min_dscr": 1.30,
    "discount_rate_used": 0.0854,
    "balloon_pct": 0.3467,
}
_NOTE_CLASS = "tornado-undefined-note"


def _tornado_section(tornado: TornadoBlock) -> str:
    case = CaseResult(
        status="success", scenario_variant="lendercase", kpis=_KPIS, run_manifest=None
    )
    html = render_report_html(
        build_report_context(case, generated_at=GENERATED_AT, tornado=tornado)
    )
    start = html.index("Sensitivity Tornado")
    end = html.index("</section>", start)
    return html[start:end]


def _note_text(section: str) -> str:
    """The note's rendered text with HTML whitespace collapsed, as a reader sees it."""
    start = section.index(_NOTE_CLASS)
    note = section[section.index(">", start) + 1 : section.index("</p>", start)]
    return re.sub(r"\s+", " ", note).strip()


def _defined_row(label: str = "Tariff") -> TornadoRow:
    return TornadoRow(
        label=label, base=0.0116, low_case=-0.0031, high_case=0.0249, impact_abs=0.0280
    )


def test_formatter_marks_none_undefined_and_keeps_numbers() -> None:
    assert fmt_ratio_pct_or_undefined(None) == "undefined"
    assert fmt_ratio_pct_or_undefined(None) != _ABSENT
    # A zero is a number, not an undefined point.
    assert fmt_ratio_pct_or_undefined(0.0) == "0.00%"
    for value in (0.0280, -0.0031, 0.0116):
        assert fmt_ratio_pct_or_undefined(value) == fmt_ratio_pct(value)


def test_undefined_cells_render_as_undefined_with_a_note() -> None:
    undefined_row = TornadoRow(
        label="Debt Tenor",
        base=0.0116,
        low_case=None,
        high_case=0.0101,
        impact_abs=None,
    )
    section = _tornado_section(
        TornadoBlock(
            metric="project_irr",
            rows=[_defined_row(), undefined_row],
            undefined_points=1,
            undefined_drivers=["Debt Tenor"],
        )
    )
    row_html = section[
        section.index("Debt Tenor") : section.index(
            "</tr>", section.index("Debt Tenor")
        )
    ]
    assert row_html.count(">undefined<") == 2  # downside and swing
    assert "1.01%" in row_html  # the defined upside still prints
    # No cell prints the absent-value em-dash. Checked per cell, so a literal "—" in
    # the section heading cannot trip it (#1692 assurance AS-L2).
    assert f">{_ABSENT}<" not in section
    assert _NOTE_CLASS in section
    assert "Undefined points: 1." in section
    assert "Drivers with an undefined point:" in section
    note = _note_text(section)
    # The sentences are joined with a space: the report's Jinja environment trims
    # block whitespace, which once printed "1.Drivers" (#1692 domain D-1).
    assert note.endswith(
        "a value left out. Undefined points: 1. Drivers with an undefined point: "
        "Debt Tenor."
    )
    assert re.search(r"\.\S", note.replace("&rsquo;", "'")) is None
    # The wording claims no more than the solver shows, matching the #1494
    # Project IRR note (#1692 domain D-2).
    assert "resolved no single rate" in note
    assert "no rate solves" not in note


def test_undefined_base_reads_undefined_in_the_caption() -> None:
    row = TornadoRow(
        label="Tariff", base=None, low_case=None, high_case=None, impact_abs=None
    )
    section = _tornado_section(
        TornadoBlock(
            metric="project_irr",
            rows=[row],
            undefined_base=True,
            undefined_points=3,
            undefined_drivers=["Tariff"],
        )
    )
    assert "(base undefined)" in section
    assert "Undefined points: 3." in section
    assert f">{_ABSENT}<" not in section


def test_fully_defined_tornado_has_no_note() -> None:
    section = _tornado_section(
        TornadoBlock(metric="project_irr", rows=[_defined_row(), _defined_row("CAPEX")])
    )
    assert _NOTE_CLASS not in section
    assert "undefined" not in section
    assert "2.80%" in section


@pytest.mark.parametrize("points", [0, 2])
def test_note_count_shows_only_when_positive(points: int) -> None:
    """The note never prints "Undefined points: 0" when only drivers are recorded."""
    section = _tornado_section(
        TornadoBlock(
            metric="project_irr",
            rows=[_defined_row()],
            undefined_points=points,
            undefined_drivers=["Tariff"],
        )
    )
    assert _NOTE_CLASS in section
    assert ("Undefined points:" in section) is (points > 0)
    assert "Undefined points: 0" not in section
    note = _note_text(section)
    expected_tail = (
        "a value left out. Undefined points: 2. Drivers with an undefined point: Tariff."
        if points
        else "a value left out. Drivers with an undefined point: Tariff."
    )
    assert note.endswith(expected_tail)


# ------------------------------------------- the #1487 follow-ups (bundle A2)


def _caption(section: str) -> str:
    start = section.index('<p class="muted">')
    text = section[start : section.index("</p>", start)]
    return re.sub(r"\s+", " ", text)


def test_heading_names_the_swept_metric() -> None:
    """The heading said "Project IRR" whatever was swept."""
    for metric, label in (("project_irr", "Project IRR"), ("equity_irr", "Equity IRR")):
        section = _tornado_section(TornadoBlock(metric=metric, rows=[_defined_row()]))
        assert section.startswith(f"Sensitivity Tornado &mdash; {label}</h2>")
        assert f"sensitivity of the {label} to each" in _caption(section)


def test_caption_says_undefined_swings_are_listed_last_only_when_one_is() -> None:
    undefined = TornadoRow(
        label="OPEX", base=0.0116, low_case=None, high_case=0.02, impact_abs=None
    )
    rows = [_defined_row(), undefined]
    with_undefined = _caption(
        _tornado_section(TornadoBlock(metric="project_irr", rows=rows))
    )
    assert "widest first, and drivers whose swing is undefined last." in with_undefined
    defined_only = _caption(
        _tornado_section(TornadoBlock(metric="project_irr", rows=[_defined_row()]))
    )
    assert defined_only.endswith("widest first.")


def test_an_undefined_swing_sorts_after_a_defined_zero_swing() -> None:
    """Treating an undefined swing as 0.0 left its place among the zero swings to chance."""
    from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
    from app.services.report_tornado import compute_report_tornado

    def result(label: str, low: float, high: float, swing: float) -> TornadoResult:
        return TornadoResult(
            metric_name="project_irr",
            base_metric=0.01,
            impact_abs=swing,
            shock_results=[
                ShockResult(label=label, low_case=low, high_case=high, base_case=0.01)
            ],
        )

    nan = float("nan")
    suite = SensitivitySuite(
        tornado_results=[
            result("Undefined", nan, 0.02, nan),
            result("Flat", 0.01, 0.01, 0.0),
            result("Wide", 0.0, 0.03, 0.03),
            result("Narrow", 0.009, 0.011, 0.002),
        ]
    )
    block = compute_report_tornado(
        {"project": {"name": "t"}}, runner=lambda _path, *, metric: suite
    )
    assert block is not None
    assert [r.label for r in block.rows] == ["Wide", "Narrow", "Flat", "Undefined"]
