"""DutchBay Presentation Layer (DBPL) — the canonical house style.

Provenance of these tokens
--------------------------
Every value here was measured from the reference document, not invented:

    DUTCHBAY_ANALYST_GENERATED_SYNTHETIC_LENDER_TERM_SHEET_2026-08-18.pdf
    A4, 29pp, tagged, document ID DBAY-SLTS-2026-08-18

Colours were sampled from a 110 dpi raster of pages 1 and 4; rule weights were measured by
scanning for horizontal runs and converting pixels to points at that raster density. The font
stack is the set the reference PDF actually embeds.

The DBPL is the single source of truth for how a DutchBay document looks. A surface that renders
its own colours or margins has forked the house style, and two documents that disagree about
what a caveat looks like teach a reader to stop noticing caveats.

Structural, un-suppressible furniture
-------------------------------------
The reference document carries provenance on EVERY page, not just the cover: a running header
banner, a running footer with document ID, version, date and ``Page n of m``, and a caveat band
under each section heading. :data:`DBPL_STRUCTURAL_FURNITURE` records that this is a contract,
not a default — a DBPL document without its banner is not a styled document, it is an unlabelled
one, which for analyst-generated material is the failure mode that matters.

GWTF:
    - DBPL-01: any DBPL PDF must be produced through the full ``[report]`` extra and this style.
    - CCCDIR: pure data. No rendering, no I/O, no finance.
"""

from __future__ import annotations

from typing import Mapping

__all__ = [
    "DBPL_PALETTE",
    "DBPL_FONT_STACKS",
    "DBPL_REQUIRED_FONT_FAMILIES",
    "DBPL_TYPE_SCALE",
    "DBPL_PAGE",
    "DBPL_RULES",
    "DBPL_SHADING",
    "DBPL_MEASURE",
    "DBPL_NOTE_ORDER",
    "DBPL_KEY_SYMBOLS",
    "DBPL_PAGE_LANDSCAPE",
    "DBPL_STRUCTURAL_FURNITURE",
    "DBPL_REFERENCE_DOCUMENT",
    "as_css_variables",
]

#: The reference document these tokens were measured from.
DBPL_REFERENCE_DOCUMENT = (
    "DUTCHBAY_ANALYST_GENERATED_SYNTHETIC_LENDER_TERM_SHEET_2026-08-18.pdf "
    "(DBAY-SLTS-2026-08-18, v0.1, A4, 29pp)"
)

#: Sampled palette. Names describe ROLE, not colour, so a re-skin changes values not call sites.
DBPL_PALETTE: Mapping[str, str] = {
    # Primary identity — titles, section headings, emphasis inside caveat bands.
    "ink": "#123B5D",
    # Heavy rule under the document title.
    "rule_title": "#1D698D",
    # Table header band, and the thin rule under a section heading's baseline.
    "band": "#1D5877",
    "rule_section": "#8CB6CA",
    # Warning register — the running banner and the caveat band's left bar.
    "warn_text": "#AB5044",
    "warn_rule": "#9E3426",
    "warn_bar": "#C1533D",
    "warn_bg": "#FFF1ED",
    # Controlled-value accent: document IDs, file paths, SHA-256 digests, version strings.
    # A reader must be able to see at a glance which values are identifiers rather than prose.
    "accent_id": "#5B245F",
    # Body and furniture.
    "body": "#000000",
    "meta": "#767F88",
    "rule_body": "#808080",
    "rule_footer": "#31546B",
    "paper": "#FFFFFF",
}


def _house_font_stacks() -> Mapping[str, str]:
    """Font stacks by role, derived from the single font declaration in :mod:`.fonts`.

    These MUST come from the same place the ``@font-face`` rules come from. They previously did
    not: the ``@font-face`` rules loaded the bundled Source superfamily while these stacks still
    named Liberation, so every document embedded Times New Roman and Arial instead — and the
    provenance reported "substituted: none", because it checked that the fonts had been
    *provisioned*, not that the stylesheet actually *asked* for them.

    Imported lazily to keep this module free of a circular import at load time.
    """
    from app.reports.dbpl.fonts import DBPL_FONTS

    return {spec.role: spec.css_stack for spec in DBPL_FONTS}


#: Font stacks by role. House family first, then metric-compatible fallbacks — a substitution
#: changes glyph shapes but not line breaks or pagination. Generated, never hand-written, so the
#: stack and the @font-face rules cannot diverge.
DBPL_FONT_STACKS: Mapping[str, str] = _house_font_stacks()

#: Families a DBPL render should resolve natively. Absence is NOT fatal — the fallbacks are
#: metric-compatible — but it must be SURFACED, never silently substituted. WeasyPrint renders
#: happily with a substituted face, so a successful render proves nothing about which font was
#: used; :func:`app.reports.dbpl.print_core.probe_fonts` resolves them explicitly.
DBPL_REQUIRED_FONT_FAMILIES: tuple[str, ...] = (
    "Source Serif 4",
    "Source Sans 3",
    "Source Code Pro",
)

#: Type scale in points, measured from the reference document.
DBPL_TYPE_SCALE: Mapping[str, float] = {
    "title": 26.0,
    "section": 15.5,
    "subsection": 12.0,
    "body": 10.0,
    "table": 9.5,
    "caveat": 9.5,
    "banner": 7.5,
    "footer": 7.5,
}

#: Page geometry (A4, matching the reference document's 595.304 x 841.89 pt).
DBPL_PAGE: Mapping[str, str] = {
    "size": "A4",
    "margin_top": "18mm",
    "margin_bottom": "18mm",
    "margin_left": "18mm",
    "margin_right": "18mm",
}

#: Rule weights. Two systems reconciled.
#:
#: The document furniture weights were measured from the reference PDF at 110 dpi
#: (1 px = 0.6545 pt). The TABLE weights follow **Vignelli over Tufte** — a deliberate choice.
#: Tufte would erase rules as non-data-ink; Vignelli treats them as load-bearing structure and
#: deploys them as a graded hierarchy. For a covenant or cash-flow table read by a credit officer
#: who must find one row among forty, structure beats minimalism.
#:
#: Vignelli, verbatim: *"bolder rulers (2 pt) will separate major parts of the text, light rulers
#: (1/2 pt or 1 pt) will separate items within each part of the form. In that situation the type
#: between the rulers will be 8 pt, always set closer to the ruler above. Type should always hang
#: from the ruler, regardless of the size."*
DBPL_RULES: Mapping[str, str] = {
    # Document furniture (measured from the reference document).
    "banner": "0.7pt",
    "title": "2.6pt",
    "section": "0.7pt",
    "body": "0.7pt",
    "footer": "0.7pt",
    # Vignelli's three-step table hierarchy.
    "table_major": "2pt",  # separates major parts — header band, table foot
    "table_item": "1pt",  # separates items within a part — Urban's under-header/last-row rule
    "table_minor": "0.5pt",  # finest division — optional interior row rules
}

#: Row shading. **Urban Institute over Tufte**, where the two conflict.
#:
#: Zebra shading is strictly anti-Tufte — it is ink that encodes nothing. It is adopted anyway
#: because the reading task here is row-tracking across a wide table, not pattern-perception, and
#: a mis-tracked row in a covenant schedule is a costlier error than a slightly lower data-ink
#: ratio. The tint is deliberately near-threshold: enough to guide the eye, not enough to compete
#: with the numbers.
#:
#: Urban's concrete rule set is adopted with it: a rule beneath the column headers and beneath the
#: last row; interior verticals omitted entirely.
DBPL_SHADING: Mapping[str, str] = {
    "zebra": "#F4F6F8",  # alternate body rows
    "group": "#E8EDF1",  # in-table group-header rows
    "emphasis": "#FFF8E6",  # a row needing attention without alarm
    "table_ground": "#FFFFFF",
}

#: Measure and vertical rhythm.
#:
#: Bringhurst caps single-column measure at 75 characters; Butterick allows 90; USWDS targets 66.
#: 66 is adopted as the anchor — the safer end of a genuine 15-character disagreement, and the
#: value that survives at the 10 pt body size the reference document uses.
#:
#: Leading is expressed as a RATIO, because leading and measure must be chosen together: Vignelli's
#: 8-on-9 (1.125) works only because he pairs it with a 70 mm column, and USWDS's 1.62 exceeds
#: Butterick's 145 % ceiling. Every vertical interval is a multiple of the body leading, which is
#: Bringhurst's "add and delete vertical space in measured intervals".
DBPL_MEASURE: Mapping[str, str] = {
    "target_characters": "66ch",
    "max_characters": "78ch",
    "body_leading": "1.42",  # within Butterick's 120-145%
    "table_leading": "1.30",  # tighter: table cells are short, not continuous prose
    "heading_leading": "1.18",
    "rhythm_unit": "14.2pt",  # 10pt x 1.42 — the interval every vertical space is a multiple of
}

#: ADB conventions, adopted verbatim as the fallback authority.
#:
#: ADB HSU 2024: *"Place all explanatory material immediately below the table, not at the bottom of
#: the page, in this order (listed vertically): abbreviation(s), general explanatory note(s),
#: footnote(s), and source(s). Use font size 9 points."* Footnote indicators are superscript
#: lowercase letters, NOT bold. A source is required for every table, and should be documentary
#: rather than an organisation name.
DBPL_NOTE_ORDER: tuple[str, ...] = ("abbreviations", "notes", "footnotes", "sources")

#: ADB Key Symbols (Key Indicators 2025, p.28), adopted verbatim.
#:
#: This is a DATA-INTEGRITY control, not a typographic nicety. A lender table that renders "not
#: available" and "zero" identically has misstated the data, and no amount of good typography
#: repairs that.
DBPL_KEY_SYMBOLS: Mapping[str, str] = {
    "...": "data not available",
    "\u2013": "magnitude equals zero",
    "0 or 0.0": "magnitude is less than half of unit employed",
    "*": "provisional/preliminary/estimate/budget figure",
    "|": "marks break in series",
    "n.a.": "not applicable",
}

#: Page geometry for the LANDSCAPE variant (Lazard).
#:
#: Used only where a table's width cannot be carried by a portrait A4 column. The landscape page
#: obeys every other rule here — same palette, same rule hierarchy, same note order, same
#: furniture. It is a different page size, not a different design.
DBPL_PAGE_LANDSCAPE: Mapping[str, str] = {
    "size": "A4 landscape",
    "margin_top": "15mm",
    "margin_bottom": "15mm",
    "margin_left": "18mm",
    "margin_right": "18mm",
}

#: The furniture that must appear on every page of a DBPL document. Recorded as data so a
#: template can be tested against it rather than trusted.
DBPL_STRUCTURAL_FURNITURE: tuple[str, ...] = (
    "running_header_banner",
    "running_footer_document_id",
    "running_footer_page_n_of_m",
    "caveat_band_per_section",
)


def as_css_variables() -> str:
    """Render the tokens as a CSS custom-property block for the DBPL stylesheet.

    Emitted rather than hand-copied into the template so the stylesheet and the Python tokens
    cannot drift — the same class of bug as a hand-kept dependency-pin table.
    """
    lines = [":root {"]
    for name, value in DBPL_PALETTE.items():
        # Rule COLOURS are namespaced `--dbpl-rulecolour-*` so they cannot collide with the rule
        # WEIGHTS emitted below as `--dbpl-rule-*`. They did collide: four names were defined
        # twice and the later weight silently won, so every rule colour was being lost and the
        # stylesheet was quietly falling back to hard-coded literals.
        css_name = (
            f"rulecolour-{name[len('rule_'):]}" if name.startswith("rule_") else name
        ).replace("_", "-")
        lines.append(f"  --dbpl-{css_name}: {value};")
    for name, stack in DBPL_FONT_STACKS.items():
        lines.append(f"  --dbpl-font-{name}: {stack};")
    for name, size in DBPL_TYPE_SCALE.items():
        lines.append(f"  --dbpl-size-{name.replace('_', '-')}: {size}pt;")
    for name, weight in DBPL_RULES.items():
        lines.append(f"  --dbpl-rule-{name.replace('_', '-')}: {weight};")
    for name, value in DBPL_PAGE.items():
        lines.append(f"  --dbpl-page-{name.replace('_', '-')}: {value};")
    for name, value in DBPL_PAGE_LANDSCAPE.items():
        lines.append(f"  --dbpl-land-{name.replace('_', '-')}: {value};")
    for name, value in DBPL_SHADING.items():
        lines.append(f"  --dbpl-shade-{name.replace('_', '-')}: {value};")
    for name, value in DBPL_MEASURE.items():
        lines.append(f"  --dbpl-measure-{name.replace('_', '-')}: {value};")
    lines.append("}")
    return "\n".join(lines)
