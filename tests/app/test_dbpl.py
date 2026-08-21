"""Tests for the DutchBay Presentation Layer (GWTF DBPL-01).

Two properties carry the rule. First, the print core must FAIL LOUD on an incomplete `[report]`
stack rather than emitting a document that claims to be DBPL without the machinery that makes it
one. Second, the structural furniture — banner, footer, caveat bands — must be un-suppressible,
because a DBPL document without its banner is an unlabelled one.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
from jinja2 import Environment, FileSystemLoader

from app.ops.extras import ExtraStatus, PackageStatus
from app.reports.dbpl import print_core as pc
from app.reports.dbpl.print_core import (
    DBPL_EXTRA,
    DbplDependencyError,
    DbplRenderResult,
    FontResolution,
    dbpl_stylesheet,
    probe_fonts,
    render_dbpl_pdf,
    require_dbpl_stack,
)
from app.reports.dbpl.style import (
    DBPL_FONT_STACKS,
    DBPL_PALETTE,
    DBPL_REFERENCE_DOCUMENT,
    DBPL_RULES,
    DBPL_STRUCTURAL_FURNITURE,
    DBPL_TYPE_SCALE,
    as_css_variables,
)

_TEMPLATES = "app/reports/dbpl/templates"


def _doc(**over: object) -> dict:
    doc: dict = {
        "title": "Proof",
        "banner": "ANALYST-GENERATED SYNTHETIC | NOT LENDER EVIDENCE",
        "document_id": "DBAY-TEST-2026-08-21",
        "version": "v0.1",
        "issue_date": "21 August 2026",
        "headline_caveat": "NON-BINDING • NOT LENDER EVIDENCE",
        "disclaimer": "Demonstration only.",
        "section_caveat": "CONTROL NOTICE — NOT LENDER EVIDENCE",
        "first_section_number": 0,
        "sections": [
            {
                "heading": "Document control",
                "table": {"columns": ["Field", "Value"], "rows": [["ID", "DBAY-TEST"]]},
            },
            {"heading": "Points", "points": ["one", "two"], "intro": "intro text"},
            {
                "heading": "Prose",
                "body": "body text",
                "caveat": "SECTION-SPECIFIC CAVEAT",
            },
        ],
    }
    doc.update(over)
    return doc


def _render_html(doc: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template("dbpl_base.html.j2").render(doc=doc)


# ── Style tokens ─────────────────────────────────────────────────────────────


def test_css_variables_have_no_name_collisions() -> None:
    """Rule colours and rule weights must not share a variable name.

    They did: four names were defined twice and the later weight silently won, so every rule
    colour was lost. This is the regression guard.
    """
    names = re.findall(r"^\s*(--[a-z0-9-]+):", as_css_variables(), re.M)
    duplicates = {n: c for n, c in Counter(names).items() if c > 1}
    assert not duplicates, f"colliding CSS variables: {duplicates}"


def test_rule_colours_and_weights_are_separately_addressable() -> None:
    css = as_css_variables()
    for name in ("title", "section", "body", "footer"):
        assert f"--dbpl-rulecolour-{name}:" in css
        assert f"--dbpl-rule-{name}:" in css


def test_every_palette_entry_is_a_hex_colour() -> None:
    for name, value in DBPL_PALETTE.items():
        assert re.fullmatch(
            r"#[0-9A-F]{6}", value
        ), f"{name} is not a hex colour: {value}"


def test_every_rule_weight_is_in_points() -> None:
    for name, value in DBPL_RULES.items():
        assert value.endswith("pt"), f"{name} is not expressed in points: {value}"


def test_type_scale_is_ordered_from_title_down_to_footer() -> None:
    assert (
        DBPL_TYPE_SCALE["title"] > DBPL_TYPE_SCALE["section"] > DBPL_TYPE_SCALE["body"]
    )
    assert DBPL_TYPE_SCALE["body"] > DBPL_TYPE_SCALE["footer"]


def test_font_stacks_lead_with_liberation_and_fall_back_metric_compatibly() -> None:
    """Liberation is metric-compatible with Times/Arial, so those must be the FIRST fallbacks."""
    assert DBPL_FONT_STACKS["serif"].startswith("'Liberation Serif', 'Times New Roman'")
    assert DBPL_FONT_STACKS["sans"].startswith("'Liberation Sans', Arial")


def test_reference_document_is_recorded_so_tokens_are_traceable() -> None:
    assert "DBAY-SLTS-2026-08-18" in DBPL_REFERENCE_DOCUMENT


def test_stylesheet_is_tokens_followed_by_house_rules() -> None:
    sheet = dbpl_stylesheet()
    assert sheet.startswith(":root {")
    assert "@page" in sheet and ".dbpl-caveat" in sheet


def test_stylesheet_references_tokens_rather_than_hard_coded_colours() -> None:
    """A literal hex in the house rules means a token was bypassed."""
    _, _, rules = dbpl_stylesheet().partition("}")
    literals = set(re.findall(r"#[0-9A-Fa-f]{6}", rules)) - {
        "#FFFFFF",
        "#E2E6E9",
        "#F4F8FA",
        "#2C3E4C",
    }
    assert not literals, f"hard-coded colours bypassing the tokens: {literals}"


# ── Structural furniture ─────────────────────────────────────────────────────


def test_structural_furniture_is_declared() -> None:
    assert "running_header_banner" in DBPL_STRUCTURAL_FURNITURE
    assert "running_footer_page_n_of_m" in DBPL_STRUCTURAL_FURNITURE


def test_banner_and_docline_render_on_every_page_via_page_strings() -> None:
    html = _render_html(_doc())
    assert 'class="dbpl-banner"' in html and 'class="dbpl-docline"' in html
    sheet = dbpl_stylesheet()
    assert "string-set: dbpl-banner content()" in sheet
    assert (
        "string(dbpl-banner)" in sheet
    ), "the banner must be carried into the running header"
    assert 'counter(page) " of " counter(pages)' in sheet


def test_headline_caveat_and_per_section_caveats_render() -> None:
    html = _render_html(_doc())
    assert "NON-BINDING • NOT LENDER EVIDENCE" in html
    assert html.count("dbpl-caveat") >= 4, "headline caveat plus one band per section"


def test_a_section_may_override_the_default_caveat() -> None:
    assert "SECTION-SPECIFIC CAVEAT" in _render_html(_doc())


def test_sections_are_numbered_from_the_declared_start() -> None:
    html = _render_html(_doc(first_section_number=3))
    assert "3. Document control" in html
    assert "4. Points" in html


def test_points_key_is_used_not_items() -> None:
    """`section.items` resolves to the dict method in Jinja, so the key must be `points`."""
    html = _render_html(_doc())
    assert "<li>one</li>" in html and "<li>two</li>" in html


def test_template_escapes_a_hostile_title() -> None:
    html = _render_html(_doc(title="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ── The print contract: fail loud ────────────────────────────────────────────


def _status(**over: object) -> ExtraStatus:
    fields: dict[str, object] = {
        "distribution": "weasyprint",
        "declared_spec": "<70,>=69",
        "installed_version": "69.0",
        "installed": True,
    }
    fields.update(over)
    return ExtraStatus(DBPL_EXTRA, (PackageStatus(**fields),), deep=True)  # type: ignore[arg-type]


def test_require_stack_returns_status_when_complete() -> None:
    status = require_dbpl_stack()
    assert status.available is True
    names = {p.distribution for p in status.packages}
    assert {
        "weasyprint",
        "reportlab",
        "geopandas",
        "contextily",
    } <= names, "DBPL-01 requires the COMPLETE [report] extra, not just weasyprint"


def test_missing_package_raises_and_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    absent = PackageStatus("contextily", ">=1.6", None, installed=False)
    monkeypatch.setattr(
        pc, "probe_extra", lambda *a, **k: ExtraStatus(DBPL_EXTRA, (absent,), deep=True)
    )
    with pytest.raises(DbplDependencyError, match="contextily"):
        require_dbpl_stack()


def test_unimportable_package_raises_and_points_at_system_libraries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The WeasyPrint-without-pango/cairo case must name the real cause."""
    monkeypatch.setattr(
        pc,
        "probe_extra",
        lambda *a, **k: _status(
            importable=False,
            import_error="OSError: cannot load library 'libpango-1.0.so.0'",
        ),
    )
    with pytest.raises(DbplDependencyError) as excinfo:
        require_dbpl_stack()
    assert "libpango" in str(excinfo.value)
    assert "pango/cairo" in str(excinfo.value)


def test_pin_violation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pc,
        "probe_extra",
        lambda *a, **k: _status(installed_version="71.0", satisfies_spec=False),
    )
    with pytest.raises(DbplDependencyError, match="violates its declared pin"):
        require_dbpl_stack()


def test_uninstalled_project_raises_rather_than_rendering_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pc, "probe_extra", lambda *a, **k: ExtraStatus(DBPL_EXTRA, (), deep=True)
    )
    with pytest.raises(DbplDependencyError, match="declares no packages"):
        require_dbpl_stack()


# ── Font provenance ──────────────────────────────────────────────────────────


def test_probe_fonts_reports_a_resolution_per_family() -> None:
    fonts = probe_fonts()
    assert {f.family for f in fonts} == {"Liberation Serif", "Liberation Sans"}


def test_substitution_is_surfaced_not_hidden() -> None:
    sub = FontResolution("Liberation Serif", "Times New Roman", True)
    assert "SUBSTITUTED" in sub.note
    native = FontResolution("Liberation Serif", "Liberation Serif", False)
    assert native.note.endswith("native")
    unknown = FontResolution("Liberation Serif", None, False)
    assert "unknown" in unknown.note


def test_missing_fontconfig_degrades_to_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pc.shutil, "which", lambda _n: None)
    fonts = probe_fonts()
    assert all(f.resolved is None and f.substituted is False for f in fonts)


def test_fontconfig_failure_degrades_to_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pc.shutil, "which", lambda _n: "/usr/bin/fc-match")

    def boom(*_a: object, **_k: object) -> object:
        raise OSError("fc-match exploded")

    monkeypatch.setattr(pc.subprocess, "run", boom)
    assert all(f.resolved is None for f in probe_fonts())


# ── End-to-end render ────────────────────────────────────────────────────────


def test_render_produces_a_pdf_with_provenance() -> None:
    result = render_dbpl_pdf(_render_html(_doc()))
    assert isinstance(result, DbplRenderResult)
    assert result.pdf[:5] == b"%PDF-"
    lines = result.provenance_lines()
    assert any("[report] extra" in line for line in lines)
    assert any("DBAY-SLTS-2026-08-18" in line for line in lines)


def test_render_accepts_extra_css() -> None:
    result = render_dbpl_pdf(_render_html(_doc()), extra_css="body { color: #111111; }")
    assert result.pdf[:5] == b"%PDF-"


def test_substituted_fonts_are_reported_on_the_result() -> None:
    result = render_dbpl_pdf(_render_html(_doc()))
    assert set(result.substituted_fonts) <= {"Liberation Serif", "Liberation Sans"}


def test_render_refuses_when_the_stack_is_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No best-effort PDF: a document that cannot be DBPL must not claim to be one."""
    absent = PackageStatus("geopandas", ">=1.0", None, installed=False)
    monkeypatch.setattr(
        pc, "probe_extra", lambda *a, **k: ExtraStatus(DBPL_EXTRA, (absent,), deep=True)
    )
    with pytest.raises(DbplDependencyError):
        render_dbpl_pdf(_render_html(_doc()))


def test_provenance_lines_survive_a_second_render() -> None:
    """The two-pass pattern from the style guide: render, collect provenance, render again."""
    doc = _doc()
    first = render_dbpl_pdf(_render_html(doc))
    doc["provenance_lines"] = first.provenance_lines()
    html = _render_html(doc)
    assert "dbpl-provenance" in html
    assert render_dbpl_pdf(html).pdf[:5] == b"%PDF-"
