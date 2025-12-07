#!/usr/bin/env python3
"""
Instrument all statutory-deduction-related code paths with debug statements.

- Searches for lines containing key tokens
    ["statutory", "success_fee", "env_surcharge", "social_levy"]
  in .py files under analytics/ and finance/.
- Prints all matches (with file and line number) in --dry-run mode.
- In write mode, inserts a debug logging call *after* each matching line,
  tagged with a removable marker:  # STATUTORY_DEBUG_MARKER

Usage:
  python scripts/instrument_statutory_debug.py --dry-run   # inspect only
  python scripts/instrument_statutory_debug.py             # modify files
  python scripts/instrument_statutory_debug.py --cleanup   # remove markers
"""

from __future__ import annotations

import argparse
import pathlib
from typing import List

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SEARCH_DIRS = ["analytics", "finance"]
TOKENS = ["statutory", "success_fee", "env_surcharge", "social_levy"]
MARKER = "STATUTORY_DEBUG_MARKER"


def should_scan(path: pathlib.Path) -> bool:
    if path.suffix != ".py":
        return False
    # Avoid legacy etc. if needed; adjust as the repo evolves.
    parts = path.relative_to(REPO_ROOT).parts
    if parts[0] not in SEARCH_DIRS:
        return False
    return True


def find_matches(path: pathlib.Path) -> List[int]:
    """Return 0-based line numbers that contain any of the TOKENS."""
    lines = path.read_text(encoding="utf-8").splitlines()
    hits: List[int] = []
    for i, line in enumerate(lines):
        lower = line.lower()
        if any(tok in lower for tok in TOKENS):
            hits.append(i)
    return hits


def compute_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" "))]


def ensure_logger_import(lines: List[str]) -> List[str]:
    """Ensure `import logging` and a module-level logger exist."""
    has_logging_import = any(
        line.strip().startswith("import logging")
        or line.strip().startswith("from logging import")
        for line in lines
    )
    has_logger_def = any(
        "getLogger(" in line or "logging.getLogger" in line for line in lines
    )

    new_lines = list(lines)
    insertion_index = 0

    if not has_logging_import:
        new_lines.insert(insertion_index, "import logging  # " + MARKER)
        insertion_index += 1

    if not has_logger_def:
        new_lines.insert(
            insertion_index,
            f"logger = logging.getLogger(__name__)  # {MARKER}",
        )

    return new_lines


def instrument_file(path: pathlib.Path, dry_run: bool = True) -> None:
    rel = path.relative_to(REPO_ROOT)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    match_indices = find_matches(path)
    if not match_indices:
        return

    print(f"\n=== {rel} ===")
    for idx in match_indices:
        print(f"  {idx+1:4d}: {lines[idx]}")

    if dry_run:
        return

    # First ensure logger exists
    lines = ensure_logger_import(lines)

    # Recompute matches, because indices may have shifted slightly
    match_indices = find_matches(path)

    # Insert debug lines after each match, from bottom to top to avoid reindexing issues
    for idx in sorted(match_indices, reverse=True):
        original_line = lines[idx]
        indent = compute_indent(original_line)

        debug_line = (
            f"{indent}logger.debug("
            f'"[STATUTORY_DEBUG] file={rel}, line={idx+1}, '
            f'locals=%s" % locals())  # {MARKER}'
        )
        lines.insert(idx + 1, debug_line)

    new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    path.write_text(new_text, encoding="utf-8")
    print(f"  -> instrumented {rel}")


def cleanup_file(path: pathlib.Path) -> None:
    rel = path.relative_to(REPO_ROOT)
    text = path.read_text(encoding="utf-8")
    if MARKER not in text:
        return
    new_lines = [line for line in text.splitlines() if MARKER not in line]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"  -> cleaned {rel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list matches; do not modify any files.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove all STATUTORY_DEBUG_MARKER lines from scanned files.",
    )
    args = parser.parse_args()

    for root_dir in SEARCH_DIRS:
        base = REPO_ROOT / root_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if not should_scan(path):
                continue
            if args.cleanup:
                cleanup_file(path)
            else:
                instrument_file(path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
