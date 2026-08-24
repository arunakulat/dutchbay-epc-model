"""Tests for the vendor-neutral tender gap dossier emitter.

The emitter's job is to render a gap register faithfully and to refuse a malformed one. The
failure mode that matters most is a SILENTLY DROPPED gap, so the guards are tested as hard as the
rendering.
"""

from __future__ import annotations

import pytest
from markupsafe import escape as _escape

from app.reports.tender_gap_dossier_emit import (
    DEFAULT_BIDDER_LABEL,
    MANDATORY_DOSSIER_CAVEAT,
    SEVERITIES,
    SOURCE_GOVERNS_CAVEAT,
    VERIFICATION_DISCIPLINE,
    DossierRegisterError,
    EvidenceLine,
    GapItem,
    SourceDocument,
    as_dbpl_document,
    build_dossier,
    render_dossier_html,
    render_dossier_markdown,
)


def html_escape(s: str) -> str:
    """Match Jinja2 autoescaping so an escaped caveat still compares equal."""
    return str(_escape(s))


def _gap(gap_id: str = "A1", severity: str = "CRITICAL", **kw: object) -> GapItem:
    """A minimal valid gap, overridable per test."""
    base: dict[str, object] = {
        "gap_id": gap_id,
        "title": "Model supplied is the wrong variant",
        "severity": severity,
        "clause": "Volume I 3.1(c)",
        "requirement": "The BESS must have a full grid forming capable inverter.",
        "supplied": "A grid-following model.",
        "why_insufficient": "A current source cannot evidence voltage-source behaviour.",
        "question": "Please issue the grid-forming model.",
        "closure_test": "A GFM package with a validation report.",
    }
    base.update(kw)
    return GapItem(**base)  # type: ignore[arg-type]


def _dossier(**kw: object):
    base: dict[str, object] = {
        "tender_ref": "TR/TEST/2026/001",
        "tender_title": "Test tender",
        "oem_label": "Test OEM",
        "gaps": [_gap()],
        "generated_at": "2026-01-01 00:00:00Z",
    }
    base.update(kw)
    return build_dossier(**base)  # type: ignore[arg-type]


# ── Guards: a malformed register must fail loud (CESSPIT) ────────────────────


def test_empty_register_raises_rather_than_emitting_a_clean_bill() -> None:
    with pytest.raises(DossierRegisterError, match="empty"):
        build_dossier(tender_ref="T", tender_title="T", oem_label="O", gaps=[])


def test_duplicate_gap_id_raises() -> None:
    with pytest.raises(DossierRegisterError, match="duplicate"):
        build_dossier(
            tender_ref="T",
            tender_title="T",
            oem_label="O",
            gaps=[_gap("A1"), _gap("A1")],
        )


def test_unknown_severity_raises() -> None:
    with pytest.raises(DossierRegisterError, match="severity"):
        _gap(severity="SEVERE")


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_gap_without_a_controlling_clause_raises(blank: str) -> None:
    with pytest.raises(DossierRegisterError, match="clause"):
        _gap(clause=blank)


def test_unknown_extraction_route_raises() -> None:
    with pytest.raises(DossierRegisterError, match="extraction route"):
        SourceDocument("doc", "role", extraction="telepathy")


# ── Ordering, grouping and determinism ───────────────────────────────────────


def test_gaps_sort_most_severe_first_then_by_id() -> None:
    model = _dossier(
        gaps=[
            _gap("C1", "LOW"),
            _gap("B2", "CRITICAL"),
            _gap("A3", "HIGH"),
            _gap("B1", "CRITICAL"),
        ]
    )
    assert [g.gap_id for g in model.gaps_by_severity] == ["B1", "B2", "A3", "C1"]


def test_severity_counts_omit_empty_severities_and_keep_order() -> None:
    model = _dossier(
        gaps=[_gap("A1", "CRITICAL"), _gap("A2", "LOW"), _gap("A3", "CRITICAL")]
    )
    assert model.severity_counts == (("CRITICAL", 2), ("LOW", 1))


def test_critical_path_selects_by_tier_not_by_severity() -> None:
    model = _dossier(
        gaps=[
            _gap("A1", "CRITICAL", tier="critical path"),
            _gap("A2", "CRITICAL", tier="document"),
        ]
    )
    assert [g.gap_id for g in model.critical_path] == ["A1"]


def test_unverified_findings_are_surfaced_not_dropped() -> None:
    model = _dossier(gaps=[_gap("A1"), _gap("A2", verified=False)])
    assert [g.gap_id for g in model.unverified] == ["A2"]
    assert len(model.gaps) == 2, "an unverified gap must remain in the register"


def test_register_digest_is_stable_and_order_independent() -> None:
    a = _dossier(gaps=[_gap("A1"), _gap("A2", "HIGH")])
    b = _dossier(gaps=[_gap("A2", "HIGH"), _gap("A1")])
    assert a.register_digest == b.register_digest


def test_register_digest_changes_when_a_gap_changes() -> None:
    a = _dossier(gaps=[_gap("A1")])
    b = _dossier(gaps=[_gap("A1", closure_test="something else")])
    assert a.register_digest != b.register_digest


# ── Vendor neutrality ────────────────────────────────────────────────────────


def test_default_bidder_label_is_the_neutral_role_word() -> None:
    assert DEFAULT_BIDDER_LABEL == "Bidder"
    assert _dossier().bidder_label == "Bidder"


def test_bidder_label_is_overridable_without_touching_the_register() -> None:
    model = _dossier(bidder_label="Consortium X")
    assert "Consortium X" in render_dossier_markdown(model)


# ── Rendering: caveats are structural and cannot be suppressed ───────────────


@pytest.mark.parametrize("renderer", [render_dossier_html, render_dossier_markdown])
def test_un_suppressible_caveats_always_render(renderer) -> None:  # type: ignore[no-untyped-def]
    out = renderer(_dossier())
    # The HTML surface autoescapes, so compare against the escaped form there. Escaping is the
    # correct behaviour (it is what stops a hostile label injecting markup) — the caveat must
    # still be present, just entity-encoded.
    escape = html_escape if renderer is render_dossier_html else (lambda s: s)
    assert escape(MANDATORY_DOSSIER_CAVEAT) in out
    assert escape(SOURCE_GOVERNS_CAVEAT) in out
    assert escape(VERIFICATION_DISCIPLINE) in out


@pytest.mark.parametrize("renderer", [render_dossier_html, render_dossier_markdown])
def test_every_gap_renders(renderer) -> None:  # type: ignore[no-untyped-def]
    gaps = [_gap(f"A{i}", SEVERITIES[i % len(SEVERITIES)]) for i in range(1, 8)]
    out = renderer(_dossier(gaps=gaps))
    for gap in gaps:
        assert gap.gap_id in out
        assert gap.question in out
        assert gap.closure_test in out


def test_html_escapes_a_hostile_label() -> None:
    out = render_dossier_html(_dossier(oem_label="<script>alert(1)</script>"))
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_markdown_escapes_pipes_in_table_cells() -> None:
    model = _dossier(
        evidence=[EvidenceLine("a|b", "declared", "received", adequate=False)],
    )
    out = render_dossier_markdown(model)
    assert r"a\|b" in out


def test_source_provenance_surfaces_extraction_route_and_hash() -> None:
    model = _dossier(
        sources=[SourceDocument("Doc", "Controlling", "a" * 64, "ocr", "1 Jan 2026")]
    )
    out = render_dossier_markdown(model)
    assert "ocr" in out
    assert "aaaaaaaaaaaa" in out, "short hash must be surfaced"


def test_unhashed_source_says_so_rather_than_rendering_blank() -> None:
    assert SourceDocument("Doc", "role").short_hash == "not hashed"


def test_evidence_status_label_distinguishes_not_assessed_from_adequate() -> None:
    assert EvidenceLine("i", "d", "r", adequate=None).status_label == "not assessed"
    assert EvidenceLine("i", "d", "r", adequate=True).status_label == "adequate"
    assert EvidenceLine("i", "d", "r", adequate=False).status_label == "NOT adequate"


def test_deadline_and_working_days_render_when_supplied() -> None:
    out = render_dossier_markdown(
        _dossier(submission_deadline="2 September 2026", working_days_remaining=9)
    )
    assert "2 September 2026" in out
    assert "9 working days remaining" in out


def test_consequence_renders_only_when_present() -> None:
    without = render_dossier_markdown(_dossier())
    assert "Stated tender consequence" not in without
    with_it = render_dossier_markdown(_dossier(gaps=[_gap(consequence="Rejection.")]))
    assert "Stated tender consequence" in with_it


# ── Markdown renderer: the optional blocks ───────────────────────────────────


def _rich_dossier():
    """A dossier exercising every optional Markdown block."""
    return _dossier(
        gaps=[
            _gap("A1", "CRITICAL", tier="critical path"),
            _gap("A2", "HIGH", verified=False, title="Unconfirmed finding"),
            _gap("A3", "LOW", consequence="Technical rejection."),
        ],
        evidence=[
            EvidenceLine(
                "Model", "Received", "Wrong variant", adequate=False, note="see A2"
            ),
            EvidenceLine("Letter", "Received", "Signed", adequate=True),
            EvidenceLine("Plan", "not listed", "Absent", adequate=None),
        ],
        sources=[
            SourceDocument(
                "Vol I", "Controlling", "a" * 64, "markitdown", "3 Jul 2026"
            ),
            SourceDocument("Scan", "OEM evidence", None, "ocr", None, "handwritten"),
        ],
        sections={
            "How to use": "Send it as it stands.",
            "Obtain from NSO": "Annex A and D.",
        },
        submission_deadline="2 September 2026",
        working_days_remaining=9,
    )


def test_markdown_renders_the_critical_path_block() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "## Critical path — raise these first" in out
    assert "nothing downstream can start" in out
    assert "**A1**" in out


def test_markdown_renders_free_text_sections_in_order() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "## How to use" in out and "Send it as it stands." in out
    assert out.index("## How to use") < out.index("## Obtain from NSO")


def test_markdown_renders_the_unverified_block() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "## Unverified findings" in out
    assert "treated as a question, not a finding of fact" in out
    assert "**A2**" in out


def test_markdown_flags_unverified_gaps_inline_too() -> None:
    assert "UNVERIFIED" in render_dossier_markdown(_rich_dossier())


def test_markdown_renders_the_evidence_inventory_with_all_three_states() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "## Evidence inventory — declared against received" in out
    for state in ("NOT adequate", "adequate", "not assessed"):
        assert state in out


def test_markdown_renders_source_provenance_including_an_unhashed_source() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "## Source provenance" in out
    assert "markitdown" in out and "ocr" in out
    assert "not hashed" in out, "a source with no hash must say so"
    assert "not stated" in out, "a source with no date must say so"


def test_markdown_renders_the_deadline_and_consequence() -> None:
    out = render_dossier_markdown(_rich_dossier())
    assert "2 September 2026" in out and "9 working days remaining" in out
    assert "Technical rejection." in out


def test_html_renders_the_same_optional_blocks() -> None:
    out = render_dossier_html(_rich_dossier())
    for probe in (
        "Critical path",
        "How to use",
        "Unverified findings",
        "Evidence inventory",
    ):
        assert probe in out


# ── DBPL adapter (GWTF DBPL-01) ──────────────────────────────────────────────


def test_dbpl_document_carries_the_un_suppressible_furniture() -> None:
    doc = as_dbpl_document(_rich_dossier())
    assert doc["banner"], "the running banner is what puts the warning on every page"
    assert "NOT A COMPLIANCE DETERMINATION" in doc["banner"]
    assert doc["headline_caveat"] == MANDATORY_DOSSIER_CAVEAT
    assert doc["section_caveat"]
    assert doc["document_id"].startswith("DBAY-TGD-")
    assert doc["version"] and doc["issue_date"]


def test_dbpl_document_renders_one_section_per_gap_plus_front_and_back_matter() -> None:
    model = _rich_dossier()
    doc = as_dbpl_document(model)
    headings = [s["heading"] for s in doc["sections"]]
    for gap in model.gaps:
        assert any(h.startswith(f"{gap.gap_id} - ") for h in headings)
    assert "Document control" in headings
    assert "Critical path - raise these first" in headings
    assert "Evidence inventory - declared against received" in headings
    assert "Source provenance" in headings
    assert "Verification discipline" in headings


def test_dbpl_gap_section_carries_clause_question_and_closure_test() -> None:
    model = _rich_dossier()
    doc = as_dbpl_document(model)
    section = next(s for s in doc["sections"] if s["heading"].startswith("A1 - "))
    fields = {r["cells"][0]: r["cells"][1] for r in section["table"]["rows"]}
    assert fields["Severity"] == "CRITICAL"
    assert fields["Controlling clause"]
    assert fields[f"Question to {model.oem_label}"]
    assert fields["Closes when"]


def test_dbpl_marks_an_unverified_gap_rather_than_dropping_it() -> None:
    doc = as_dbpl_document(_rich_dossier())
    section = next(s for s in doc["sections"] if s["heading"].startswith("A2 - "))
    fields = {r["cells"][0]: r["cells"][1] for r in section["table"]["rows"]}
    assert "UNVERIFIED" in fields["Verification"]


def test_dbpl_sections_use_points_not_items() -> None:
    """`.items` on a dict resolves to the built-in method in Jinja — the key must be `points`."""
    doc = as_dbpl_document(_rich_dossier())
    for section in doc["sections"]:
        assert (
            "items" not in section
        ), "an `items` key would silently break the template"


def test_dbpl_document_accepts_print_core_provenance() -> None:
    doc = as_dbpl_document(_rich_dossier(), provenance_lines=("line one", "line two"))
    assert doc["provenance_lines"] == ("line one", "line two")


# ── row-shape contract with the DBPL template ────────────────────────────────


def test_every_adapter_table_row_is_a_mapping() -> None:
    """The v2 template reads `row.cells` / `row.group`.

    A bare list silently rendered NOTHING: the gap headings all appeared, so the document looked
    complete while ~85% of its body text was missing. This guards the adapter side of that
    contract.
    """
    doc = as_dbpl_document(_rich_dossier())
    for section in doc["sections"]:
        table = section.get("table")
        if not table:
            continue
        for row in table["rows"]:
            assert isinstance(
                row, dict
            ), f"{section['heading']}: row is {type(row).__name__}"
            assert "cells" in row or "group" in row


def test_adapter_output_renders_every_gap_field() -> None:
    """End-to-end: the fields must survive the adapter AND the template."""
    from jinja2 import Environment, FileSystemLoader

    model = _rich_dossier()
    env = Environment(
        loader=FileSystemLoader("app/reports/dbpl/templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    html = env.get_template("dbpl_base.html.j2").render(doc=as_dbpl_document(model))
    for gap in model.gaps:
        assert gap.requirement in html
        assert gap.supplied in html
        assert gap.why_insufficient in html
        assert gap.question in html
        assert gap.closure_test in html
