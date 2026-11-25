"""Reproduce selective OCR text-coverage QC in private storage.

Uses --manifest (private selection of 98 pages), original and OCR PDFs.
NO PDF, OCR text or MarkItDown extraction is ever written inside public Git.
An optional MarkItDown markdown output is stored only under an explicit
out-of-repository path and never committed. Does not perform OCR itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf
from path_guard import require_external_path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]


def check_private_destination(path: Path, repo: Path) -> Path:
    return require_external_path(path, declared_repo=repo)


def verify(source: Path, ocr: Path, selected_pages: list[int]) -> dict:
    selection = [int(x) for x in selected_pages]
    if (
        len(selection) != 98
        or len(set(selection)) != 98
        or any(not 1 <= n <= 292 for n in selection)
    ):
        raise ValueError("Expected 98 unique PDF pages in range 1..292")
    selection_set = set(selection)
    substantial = 0
    genuinely_improved = 0
    weak_pages = []
    unchanged_untargeted = 0
    with pymupdf.open(source) as original, pymupdf.open(ocr) as search_pdf:
        if len(original) != len(search_pdf) or len(original) != 292:
            raise ValueError("Annex volume page count does not match 292-page source")
        for idx in range(len(original)):
            old = original[idx].get_text("text", sort=True)
            new = search_pdf[idx].get_text("text", sort=True)
            if idx + 1 in selection_set:
                if len(new.strip()) >= 100:
                    substantial += 1
                else:
                    weak_pages.append(idx + 1)
                if len(new.strip()) > len(old.strip()) + 20:
                    genuinely_improved += 1
            elif old == new:
                unchanged_untargeted += 1
    if (substantial, len(weak_pages), unchanged_untargeted) != (93, 5, 194):
        raise ValueError(
            "OCR quality-control results do not match frozen 93/5/194 reference"
        )
    if genuinely_improved < 1:
        raise ValueError(
            "No meaningful new text recovered; OCR source appears unchanged"
        )
    return {
        "status": "PRIVATE_SOURCE_QC_ONLY",
        "source_annex_pages": 292,
        "selected_pages": len(selection_set),
        "pages_with_substantial_text": substantial,
        "pages_with_more_than_20_new_characters": genuinely_improved,
        "weak_page_count": len(weak_pages),
        "untargeted_pages_retained": unchanged_untargeted,
        "reference_match_enforced": True,
        "expected_control": {
            "substantial_text": 93,
            "weak_pages": 5,
            "untargeted_pages": 194,
        },
        "holds": [
            "OCR cannot prove authenticity or regulatory approval",
            "No original pages/source text published",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-pdf", type=Path, required=True)
    ap.add_argument("--ocr-pdf", type=Path, required=True)
    ap.add_argument("--selection-manifest", type=Path, required=True)
    ap.add_argument("--qc-output", type=Path, required=True)
    ap.add_argument("--private-markitdown-output", type=Path)
    args = ap.parse_args()
    dest = check_private_destination(args.qc_output, REPO)
    for private_input in (args.source_pdf, args.ocr_pdf, args.selection_manifest):
        if private_input.resolve().is_relative_to(REPO.resolve()):
            raise SystemExit(
                "Refusing OCR of a private source inside the public checkout"
            )
    selection = json.loads(args.selection_manifest.read_text())["pages_1based"]
    result = verify(args.source_pdf, args.ocr_pdf, selection)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    if args.private_markitdown_output:
        md = check_private_destination(args.private_markitdown_output, REPO)
        from markitdown import MarkItDown

        md.parent.mkdir(parents=True, exist_ok=True)
        text = MarkItDown(enable_plugins=False).convert(str(args.ocr_pdf)).text_content
        md.write_text(text, encoding="utf-8")
        print("Private MarkItDown completed", len(text), "characters")


if __name__ == "__main__":
    main()
