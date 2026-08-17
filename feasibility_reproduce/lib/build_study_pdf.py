#!/usr/bin/env python3
"""Render the Complete Feasibility Study Markdown to its deliverable PDF.

Thin wrapper over :mod:`build_md_pdf` so ``run_all.sh`` step 10 keeps its
argument-free call for the headline deliverable while the coverage and catalog
PDFs go through the general builder.
"""

from __future__ import annotations

from pathlib import Path

from build_md_pdf import build

KIT = Path(__file__).resolve().parent.parent
MD = KIT / "report" / "DutchBay_Complete_Feasibility_Study.md"
PDF = KIT / "report" / "DutchBay_Complete_Feasibility_Study.pdf"
TITLE = "DutchBay 150 MW Wind — Complete Feasibility & Recommendation Study"


def main() -> int:
    if not MD.is_file():
        raise SystemExit(f"missing study Markdown: {MD}")
    build(MD, PDF, "portrait", TITLE)
    print(f"  wrote {PDF} ({PDF.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
