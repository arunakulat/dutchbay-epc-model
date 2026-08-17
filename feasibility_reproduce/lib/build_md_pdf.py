#!/usr/bin/env python3
"""Render one of the kit's Markdown reports to an Acrobat-safe PDF.

Usage:
    build_md_pdf.py <input.md> <output.pdf> [portrait|landscape] [running-title]

Acrobat-safe means: no colour-emoji font is ever selected. Acrobat rasterises or
drops glyphs from a CBDT/COLR emoji face, so the coverage legends (which use
🟢/🟡/⚪) are transliterated to text markers before rendering rather than being
left to the font stack.

This lives in ``feasibility_reproduce/lib/`` because ``run_all.sh`` step 10 calls
it from there. That directory was silently swallowed for a long time by the
unanchored ``lib/`` rule in ``.gitignore`` (now anchored to ``/lib/``), which is
why the kit shipped a ``run_all.sh`` referencing helpers that were never
committed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import mistune
from weasyprint import HTML

# Colour-emoji codepoints the reports use as coverage markers. Rendering these
# through a CBDT/COLR face is what makes a PDF misbehave in Acrobat, so they are
# replaced with plain-text equivalents that any serif face can draw.
EMOJI_MARKERS = {
    "\N{LARGE GREEN CIRCLE}": "[fired]",
    "\N{LARGE YELLOW CIRCLE}": "[not fired]",
    "\N{MEDIUM WHITE CIRCLE}": "[n/a]",
    "\N{WHITE CIRCLE}": "[n/a]",
    "\N{WARNING SIGN}": "(!)",
    "\N{VARIATION SELECTOR-16}": "",
}

CSS = """
@page {{ size: A4 {orientation}; margin: 16mm 14mm 18mm 14mm;
  @bottom-center {{ content: "{title} — page " counter(page) " / " counter(pages);
    font-family: "DejaVu Serif", Georgia, serif; font-size: 8pt; color: #555; }} }}
body {{ font-family: "DejaVu Serif", Georgia, serif; font-size: 9.2pt; line-height: 1.45; color: #111; }}
h1 {{ font-size: 18pt; border-bottom: 2px solid #234; padding-bottom: 4px; }}
h2 {{ font-size: 13pt; margin-top: 16px; border-bottom: 1px solid #bbb; padding-bottom: 2px; }}
h3 {{ font-size: 11pt; margin-top: 12px; }}
h4 {{ font-size: 9.8pt; margin-top: 10px; }}
table {{ border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 8.2pt; }}
th, td {{ border: 1px solid #99a; padding: 3px 5px; text-align: left; vertical-align: top; }}
th {{ background: #eef1f5; font-weight: bold; }}
tr {{ page-break-inside: avoid; }}
code, pre {{ font-family: "DejaVu Sans Mono", monospace; font-size: 7.8pt; }}
pre {{ background: #f5f6f8; border: 1px solid #ccd; padding: 6px; white-space: pre-wrap;
  word-wrap: break-word; page-break-inside: avoid; }}
blockquote {{ border-left: 3px solid #99a; margin-left: 0; padding-left: 10px; color: #333; }}
img {{ max-width: 100%; }}
h1, h2, h3, h4 {{ page-break-after: avoid; }}
"""


def transliterate_emoji(text: str) -> str:
    for glyph, replacement in EMOJI_MARKERS.items():
        text = text.replace(glyph, replacement)
    return text


def build(md_path: Path, pdf_path: Path, orientation: str, title: str) -> None:
    raw = transliterate_emoji(md_path.read_text(encoding="utf-8"))
    # `table` gives GFM pipe tables; `strikethrough`/`url` match the reports' usage.
    render = mistune.create_markdown(plugins=["table", "strikethrough", "url"])
    body = render(raw)
    css = CSS.format(orientation=orientation, title=title.replace('"', "'"))
    html = f"<!doctype html><meta charset='utf-8'><style>{css}</style>{body}"
    # base_url lets relative <img src="artifacts/…"> resolve next to the Markdown.
    HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(pdf_path))


def main(argv: list[str]) -> int:
    if not 3 <= len(argv) <= 5:
        print(__doc__, file=sys.stderr)
        return 2
    md_path = Path(argv[1])
    pdf_path = Path(argv[2])
    orientation = argv[3] if len(argv) > 3 else "portrait"
    if orientation not in {"portrait", "landscape"}:
        print(
            f"orientation must be portrait|landscape, got {orientation!r}",
            file=sys.stderr,
        )
        return 2
    title = argv[4] if len(argv) > 4 else md_path.stem.replace("_", " ")
    if not md_path.is_file():
        print(f"no such Markdown file: {md_path}", file=sys.stderr)
        return 1
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    build(md_path, pdf_path, orientation, title)
    print(f"  wrote {pdf_path} ({pdf_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
