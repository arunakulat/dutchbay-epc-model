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

#: Font stacks by role. Liberation is the reference document's own family and is metric-compatible
#: with Times New Roman / Arial, so those are the correct first fallbacks — a substitution changes
#: glyph shapes but not line breaks or pagination. DejaVu backs them because it is what the
#: deployed image ships (``Dockerfile``: ``fonts-dejavu-core``).
DBPL_FONT_STACKS: Mapping[str, str] = {
    "serif": "'Liberation Serif', 'Times New Roman', 'DejaVu Serif', Times, serif",
    "sans": "'Liberation Sans', Arial, 'DejaVu Sans', Helvetica, sans-serif",
    "mono": "'Liberation Mono', 'DejaVu Sans Mono', 'Courier New', monospace",
}

#: Families a DBPL render should resolve natively. Absence is NOT fatal — the fallbacks are
#: metric-compatible — but it must be SURFACED, never silently substituted. WeasyPrint renders
#: happily with a substituted face, so a successful render proves nothing about which font was
#: used; :func:`app.reports.dbpl.print_core.probe_fonts` resolves them explicitly.
DBPL_REQUIRED_FONT_FAMILIES: tuple[str, ...] = (
    "Liberation Serif",
    "Liberation Sans",
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

#: Rule weights in points, converted from the measured pixel runs at 110 dpi (1px = 0.6545pt).
DBPL_RULES: Mapping[str, str] = {
    "banner": "0.7pt",  # 1px under the running header
    "title": "2.6pt",  # 4px under the document title
    "section": "0.7pt",  # 1px under a section heading
    "body": "0.7pt",  # the grey separator between blocks
    "footer": "0.7pt",
    "table_band": "10.5pt",  # height of the solid header band
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
    lines.append("}")
    return "\n".join(lines)
