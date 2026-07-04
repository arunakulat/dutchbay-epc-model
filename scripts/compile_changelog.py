#!/usr/bin/env python3
"""Compile ``changelog.d/`` fragments into ``CHANGELOG.md`` ``[Unreleased]``.

Per-PR changelog entries live as small fragment files under ``changelog.d/`` instead
of being written straight into ``CHANGELOG.md``. Editing the single shared
``[Unreleased]`` block in every PR guarantees a merge conflict between any two
concurrent dolphins, which forces a rebase and a second full CI run; a fragment file
has a unique name, so fragments never collide. This is the towncrier/scriv pattern.

Fragment naming: ``changelog.d/<id>.<category>.md`` where ``<id>`` is any slug or issue
number and ``<category>`` is one of add/change/deprecate/remove/fix/security (the
Keep-a-Changelog sections). Each file contains one or more markdown bullet lines, e.g.::

    changelog.d/752.changed.md
    -----------------------------------------------------------------
    - **flake8-bugbear B905 resolved...** every ``zip()`` declares ``strict=``.
      A second continuation line is fine (keep it indented two spaces).

Usage (on-demand flush — run when you want to batch pending entries in)::

    python scripts/compile_changelog.py            # fold fragments into CHANGELOG.md, delete them
    python scripts/compile_changelog.py --check     # list pending fragments; exit 1 if any (CI-friendly)
    python scripts/compile_changelog.py --dry-run   # print the would-be CHANGELOG.md, change nothing

No argparse (kept out of the R3 banned-API surface): flags are read from ``sys.argv``.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FRAG_DIR = REPO / "changelog.d"
CHANGELOG = REPO / "CHANGELOG.md"

# Keep-a-Changelog subsection order. Fragment category is matched case-insensitively
# and accepts both the section noun and its verb form (e.g. "change" or "changed").
CATEGORIES: list[str] = [
    "added",
    "changed",
    "deprecated",
    "removed",
    "fixed",
    "security",
]
_ALIASES: dict[str, str] = {
    "add": "added",
    "change": "changed",
    "deprecate": "deprecated",
    "remove": "removed",
    "fix": "fixed",
}
UNRELEASED = "## [Unreleased]"


def category_of(name: str) -> str:
    """Return the canonical category for a fragment filename ``<id>.<category>.md``."""
    parts = name.split(".")
    if len(parts) < 3 or parts[-1].lower() != "md":
        raise ValueError(f"fragment {name!r} must be named <id>.<category>.md")
    raw = parts[-2].lower()
    cat = _ALIASES.get(raw, raw)
    if cat not in CATEGORIES:
        raise ValueError(
            f"fragment {name!r}: category {raw!r} not one of "
            f"{CATEGORIES} (or aliases {sorted(_ALIASES)})"
        )
    return cat


def fragments() -> list[Path]:
    """Return the fragment files under ``changelog.d/`` (README/dotfiles excluded), sorted."""
    if not FRAG_DIR.exists():
        return []
    return [
        p
        for p in sorted(FRAG_DIR.glob("*.md"))
        if p.name.lower() != "readme.md" and not p.name.startswith(".")
    ]


def _find_unreleased(lines: list[str]) -> int:
    for i, line in enumerate(lines):
        if line.strip() == UNRELEASED:
            return i
    raise ValueError(f"{UNRELEASED!r} heading not found in CHANGELOG.md")


def _section_end(lines: list[str], start: int) -> int:
    """Index of the first ``## `` heading after ``start`` (the end of [Unreleased]), or len."""
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            return i
    return len(lines)


def _insert_one(lines: list[str], category: str, bullets: list[str]) -> list[str]:
    """Insert ``bullets`` under the ``### <Category>`` subsection of [Unreleased].

    Appends to an existing subsection (newest-first, right below its heading) or creates
    the subsection at its Keep-a-Changelog-ordered position. Recomputes the [Unreleased]
    window on every call, so processing categories in order stays index-safe.
    """
    title = f"### {category.capitalize()}"
    unrel = _find_unreleased(lines)
    end = _section_end(lines, unrel)

    heading_idx: int | None = None
    existing: list[tuple[int, str]] = []
    for i in range(unrel + 1, end):
        stripped = lines[i].strip()
        if stripped.startswith("### "):
            name = stripped[4:].strip().lower()
            canon = _ALIASES.get(name, name)
            if canon in CATEGORIES:
                existing.append((i, canon))
            if canon == category:
                heading_idx = i

    if heading_idx is not None:
        # Newest-first: insert directly below the existing heading.
        return lines[: heading_idx + 1] + bullets + lines[heading_idx + 1 :]

    # Create the subsection at its Keep-a-Changelog position.
    order = CATEGORIES.index(category)
    insert_at = end
    for idx, canon in existing:
        if CATEGORIES.index(canon) > order:
            insert_at = idx
            break

    block = [title, *bullets, ""]
    if insert_at > 0 and lines[insert_at - 1].strip() != "":
        block = ["", *block]
    return lines[:insert_at] + block + lines[insert_at:]


def fold(changelog_text: str, bullets_by_category: dict[str, list[str]]) -> str:
    """Pure core: fold ``{category: [bullet lines]}`` into ``[Unreleased]`` of the text.

    Returns the new CHANGELOG text. Categories are applied in Keep-a-Changelog order.
    """
    lines = changelog_text.split("\n")
    for category in CATEGORIES:
        bullets = bullets_by_category.get(category)
        if bullets:
            lines = _insert_one(lines, category, bullets)
    return "\n".join(lines)


def _collect() -> dict[str, list[str]]:
    """Read all fragments into ``{category: [bullet lines]}`` (fragment order preserved)."""
    by_cat: dict[str, list[str]] = {}
    for frag in fragments():
        cat = category_of(frag.name)
        body = frag.read_text(encoding="utf-8").strip("\n")
        frag_lines = [ln for ln in body.split("\n") if ln.strip() != ""]
        if frag_lines:
            by_cat.setdefault(cat, []).extend(frag_lines)
    return by_cat


def main(argv: list[str]) -> int:
    flags = set(argv[1:])
    frags = fragments()

    if "--check" in flags:
        if frags:
            print(f"{len(frags)} pending changelog fragment(s):")
            for f in frags:
                print(f"  {f.relative_to(REPO)}")
            return 1
        print("no pending changelog fragments")
        return 0

    if not frags:
        print("no pending changelog fragments — CHANGELOG.md unchanged")
        return 0

    by_cat = _collect()
    new_text = fold(CHANGELOG.read_text(encoding="utf-8"), by_cat)

    if "--dry-run" in flags:
        sys.stdout.write(new_text)
        return 0

    CHANGELOG.write_text(new_text, encoding="utf-8")
    for frag in frags:
        frag.unlink()
    n = sum(len(v) for v in by_cat.values())
    print(
        f"folded {len(frags)} fragment(s) ({n} bullet line(s)) into "
        f"{CHANGELOG.name} [Unreleased] and removed them"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
