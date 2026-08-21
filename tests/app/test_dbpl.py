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


def _rule_block(sheet: str, selector: str) -> str:
    """The declarations of one CSS rule, parsed rather than sliced.

    A fixed character window breaks the moment a comment is added above a declaration, which is a
    brittle test, not a real signal.
    """
    start = sheet.index(selector + " {") + len(selector) + 2
    return sheet[start : sheet.index("}", start)]


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


def test_stylesheet_is_font_faces_then_tokens_then_house_rules() -> None:
    """Order is load-bearing: @font-face must precede any rule using the families, and the
    token block must precede the house rules that reference its custom properties."""
    sheet = dbpl_stylesheet()
    face_at = sheet.index("@font-face")
    root_at = sheet.index(":root {")
    rules_at = sheet.index(".dbpl-caveat")
    assert face_at < root_at < rules_at
    assert "@page" in sheet


def test_house_rules_contain_no_hard_coded_colours_at_all() -> None:
    """Every colour must come from a token. v2 tightened this to ZERO literals.

    The house rules are everything after the generated :root block; a literal hex there means a
    surface bypassed style.py, which is how a house style forks.
    """
    sheet = dbpl_stylesheet()
    rules = sheet[sheet.index(":root {") :].split("}", 1)[1]
    literals = set(re.findall(r"#[0-9A-Fa-f]{3,8}\b", rules))
    assert not literals, f"hard-coded colours bypassing the tokens: {sorted(literals)}"


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
    from app.reports.dbpl.style import DBPL_REQUIRED_FONT_FAMILIES

    fonts = probe_fonts()
    assert {f.family for f in fonts} == set(DBPL_REQUIRED_FONT_FAMILIES)


def test_render_reports_the_provisioning_tier_not_fontconfig() -> None:
    """Regression guard for directly contradictory provenance.

    fontconfig is blind to an @font-face-embedded file, so it reported "SUBSTITUTED" for the very
    families the provisioner had just supplied from the bundled tier. The provisioning tier is
    authoritative; fc-match is consulted only for families it did not supply.
    """
    result = render_dbpl_pdf(_render_html(_doc()))
    assert set(result.font_tiers) == {"serif", "sans", "mono"}
    assert all("bundled" in note for note in result.font_tiers.values())
    assert (
        result.fonts == ()
    ), "no fc-match verdict for a family the provisioner supplied"
    joined = " ".join(result.provenance_lines())
    assert "SUBSTITUTED" not in joined


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


# ── v2: the symbiotic decisions, asserted as rules ───────────────────────────


def test_vignelli_rule_hierarchy_is_three_graded_weights() -> None:
    """Vignelli over Tufte: rules are load-bearing structure, in a graded hierarchy."""
    from app.reports.dbpl.style import DBPL_RULES

    assert DBPL_RULES["table_major"] == "2pt"
    assert DBPL_RULES["table_item"] == "1pt"
    assert DBPL_RULES["table_minor"] == "0.5pt"


def test_header_band_is_closed_by_the_major_rule() -> None:
    sheet = dbpl_stylesheet()
    assert "border-bottom: var(--dbpl-rule-table-major)" in sheet


def test_type_hangs_from_the_rule_above() -> None:
    """Vignelli, verbatim: 'Type should always hang from the ruler.'

    Implemented as asymmetric cell padding — tighter above than below.
    """
    sheet = dbpl_stylesheet()
    assert (
        "padding: 4pt 8pt 6pt 8pt" in sheet
    ), "cells must sit closer to the rule above them"


def test_no_interior_vertical_rules_anywhere() -> None:
    """Urban, ADB and Lazard all agree: no verticals inside a table."""
    sheet = dbpl_stylesheet()
    for banned in (
        "border-left: 1pt",
        "border-right: 1pt",
        "border-collapse: separate",
    ):
        assert banned not in sheet


def test_urban_zebra_shading_is_applied() -> None:
    """Adopted over Tufte deliberately: row-tracking beats data-ink ratio here."""
    sheet = dbpl_stylesheet()
    assert "nth-child(even)" in sheet
    assert "var(--dbpl-shade-zebra)" in sheet


def test_last_row_is_closed_by_the_item_rule() -> None:
    sheet = dbpl_stylesheet()
    assert "tbody tr:last-child" in sheet
    assert "var(--dbpl-rule-table-item)" in sheet


def test_adb_note_order_is_declared_verbatim() -> None:
    from app.reports.dbpl.style import DBPL_NOTE_ORDER

    assert DBPL_NOTE_ORDER == ("abbreviations", "notes", "footnotes", "sources")


def test_adb_footnote_indicators_are_superscript_and_not_bold() -> None:
    sheet = dbpl_stylesheet()
    block = _rule_block(sheet, ".dbpl-fn")
    assert "vertical-align: super" in block
    assert "font-weight: 400" in block, "ADB: superscript lowercase letters, NOT bold"


def test_key_symbols_distinguish_unavailable_from_zero() -> None:
    """A data-integrity control. Rendering these identically misstates the data."""
    from app.reports.dbpl.style import DBPL_KEY_SYMBOLS

    assert DBPL_KEY_SYMBOLS["..."] == "data not available"
    assert DBPL_KEY_SYMBOLS["–"] == "magnitude equals zero"
    assert DBPL_KEY_SYMBOLS["..."] != DBPL_KEY_SYMBOLS["–"]


def test_tabular_figures_are_asserted_regardless_of_font_tier() -> None:
    sheet = dbpl_stylesheet()
    assert sheet.count("font-variant-numeric: tabular-nums") >= 3


def test_measure_is_capped_for_prose_but_not_for_tables() -> None:
    """66-character measure governs prose; a table would be crippled by it."""
    sheet = dbpl_stylesheet()
    assert "max-width: var(--dbpl-measure-max-characters)" in sheet
    assert "max-width: none" in _rule_block(sheet, "table.dbpl")


def test_landscape_is_a_page_size_not_a_different_design() -> None:
    """Lazard landscape inherits every other rule; only the page box changes."""
    sheet = dbpl_stylesheet()
    assert "@page dbpl-landscape" in sheet
    assert "size: A4 landscape" in sheet
    assert ".dbpl-landscape" in sheet and "page: dbpl-landscape" in sheet
    # no duplicated table/typography rules scoped to landscape
    assert ".dbpl-landscape table.dbpl" not in sheet


def test_running_furniture_is_present_on_every_page() -> None:
    sheet = dbpl_stylesheet()
    assert "string(dbpl-banner)" in sheet
    assert "string(dbpl-docline)" in sheet
    assert 'counter(page) " of " counter(pages)' in sheet


# ── v2: document control, landscape sections, PDF/UA ─────────────────────────


def _controlled_doc(**over: object) -> dict:
    doc = _doc(
        control=[("Document ID", "DBAY-TEST-01"), ("Version", "v1.0")],
        revisions=[
            {
                "rev": "1.0",
                "date": "21 Aug 2026",
                "status": "Responding to client comments",
                "prepared": "A. Analyst",
                "checked": "B. Checker",
                "reviewed": "C. Reviewer",
                "approved": "D. Approver",
            }
        ],
        status="Final Report",
    )
    doc.update(over)
    return doc


def test_document_control_block_renders_with_four_eyes_signoff() -> None:
    html = _render_html(_controlled_doc())
    assert "Document control" in html
    assert "Revision history" in html
    for column in ("Prepared", "Checked", "Reviewed", "Approved"):
        assert (
            f">{column}<" in html
        ), f"{column} column missing from the four-eyes chain"


def test_draft_versus_final_is_a_status_field_not_a_watermark() -> None:
    """The sector convention: `Status / Reason for issue`, never a watermark overlay."""
    html = _render_html(_controlled_doc())
    assert "Status / Reason for issue" in html
    assert "Responding to client comments" in html
    # The word appears once, in the caption that EXPLAINS the convention. What must not exist is
    # a watermark overlay — a rotated/absolutely-positioned draft stamp over the page.
    assert "dbpl-watermark" not in html
    from app.reports.dbpl.print_core import dbpl_stylesheet

    assert "watermark" not in dbpl_stylesheet().lower()


def test_status_token_rides_the_running_footer() -> None:
    """Outer Dowsing's rule: a loose page must identify itself."""
    html = _render_html(_controlled_doc())
    docline = html.split('class="dbpl-docline">')[1].split("</div>")[0]
    assert "DBAY-TEST" in docline and "Final Report" in docline


def test_document_control_is_omitted_when_no_fields_supplied() -> None:
    assert "Revision history" not in _render_html(_doc())


def test_a_section_can_be_marked_landscape() -> None:
    html = _render_html(
        _doc(sections=[{"heading": "Wide", "landscape": True, "body": "x"}])
    )
    assert 'class="dbpl-landscape"' in html


def test_table_notes_render_in_the_adb_order() -> None:
    html = _render_html(
        _doc(
            sections=[
                {
                    "heading": "T",
                    "table": {
                        "columns": ["A", "B"],
                        "rows": [{"cells": ["1", "2"]}],
                        "abbreviations": "ABC = a b c.",
                        "notes": ["rounding"],
                        "footnotes": [{"mark": "a", "text": "a note"}],
                        "source": "DutchBay model.",
                    },
                }
            ]
        )
    )
    order = [
        html.index("dbpl-abbrev"),
        html.index("dbpl-note"),
        html.index("dbpl-footnote"),
        html.index("dbpl-source"),
    ]
    assert order == sorted(
        order
    ), "ADB order is abbreviations, notes, footnotes, sources"


def test_table_headers_carry_scope_for_pdf_ua() -> None:
    """WCAG PDF6 / PDF-UA: a table must be real structure, not positioned text."""
    html = _render_html(
        _doc(
            sections=[
                {
                    "heading": "T",
                    "table": {"columns": ["A"], "rows": [{"cells": ["1"]}]},
                }
            ]
        )
    )
    assert 'scope="col"' in html


def test_lang_is_on_the_html_element_not_the_body() -> None:
    """PDF/UA requires /Lang at the root; WeasyPrint rejects it on <body> alone."""
    html = _render_html(_doc())
    assert re.search(r"^\s*<html lang=", html.split(">", 1)[1], re.M)
    assert "<body lang=" not in html, "lang on <body> alone does not satisfy PDF/UA"


def test_group_and_emphasis_rows_render_with_their_classes() -> None:
    html = _render_html(
        _doc(
            sections=[
                {
                    "heading": "T",
                    "table": {
                        "columns": ["A", "B"],
                        "rows": [
                            {"group": "Debt service"},
                            {"cells": ["DSCR", "1.286"], "emphasis": True},
                        ],
                    },
                }
            ]
        )
    )
    assert 'class="dbpl-group"' in html and 'class="dbpl-emphasis"' in html


def test_output_is_tagged_pdf_ua() -> None:
    """The DBPL's own former defect: untagged output, shared with most of the sector."""
    from app.reports.dbpl.print_core import DBPL_PDF_VARIANT

    assert DBPL_PDF_VARIANT == "pdf/ua-1"
    result = render_dbpl_pdf(_render_html(_doc()))
    assert result.pdf[:5] == b"%PDF-"
    assert result.pdf_variant == "pdf/ua-1"
    assert any("pdf/ua-1" in line for line in result.provenance_lines())


def test_tables_never_hyphenate() -> None:
    """Cells carry names, labels and codes — not prose.

    Proof-rendering the revision table produced "A. Ana-lyst" and "D. Ap-prover": a hyphenated
    signatory is a defect. Body prose keeps `hyphens: auto`.
    """
    sheet = dbpl_stylesheet()
    assert "hyphens: none" in _rule_block(sheet, "table.dbpl")
    assert "hyphens: auto" in _rule_block(sheet, "body")
