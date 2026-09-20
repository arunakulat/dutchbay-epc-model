"""Guard the changelog-fragment compiler (``scripts/compile_changelog.py``).

The compiler folds ``changelog.d/<id>.<category>.md`` fragments into
``CHANGELOG.md [Unreleased]``. These tests pin the pure ``fold`` core and the
``category_of`` filename parser so the dev workflow can't silently rot.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compile_changelog.py"


def _load():
    spec = importlib.util.spec_from_file_location("compile_changelog", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CL = _load()

_BASE = "\n".join(
    [
        "# Changelog",
        "",
        "## [Unreleased]",
        "",
        "### Added",
        "- existing added entry",
        "",
        "### Fixed",
        "- existing fixed entry",
        "",
        "## v1.0.0 - 2026-01-01",
        "",
        "### Added",
        "- shipped thing",
        "",
    ]
)


def test_category_of_accepts_nouns_verbs_and_slugs() -> None:
    assert CL.category_of("752.changed.md") == "changed"
    assert CL.category_of("b905-strict.change.md") == "changed"  # verb alias
    assert CL.category_of("997.security.md") == "security"
    assert CL.category_of("x.fix.md") == "fixed"


@pytest.mark.parametrize(
    "bad", ["notes.md", "752.md", "752.bogus.md", "752.changed.txt"]
)
def test_category_of_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        CL.category_of(bad)


def test_fold_creates_changed_subsection_between_added_and_fixed() -> None:
    out = CL.fold(_BASE, {"changed": ["- brand new changed"]})
    # A '### Changed' subsection is created (none existed) BETWEEN Added and Fixed.
    unrel = out.split("## v1.0.0")[0]
    assert "### Changed\n- brand new changed" in unrel
    assert (
        unrel.index("### Added") < unrel.index("### Changed") < unrel.index("### Fixed")
    )


def test_fold_prepends_within_existing_subsection() -> None:
    out = CL.fold(_BASE, {"added": ["- newest added"]})
    unrel = out.split("## v1.0.0")[0]
    # Newest-first: the new bullet sits directly below the heading, above the old one.
    assert "### Added\n- newest added\n- existing added entry" in unrel


def test_fold_only_touches_unreleased_not_released_sections() -> None:
    out = CL.fold(_BASE, {"added": ["- newest added"]})
    released = "## v1.0.0" + out.split("## v1.0.0")[1]
    assert released.count("- newest added") == 0
    assert "- shipped thing" in released


def test_fold_creates_new_subsection_in_keepachangelog_order() -> None:
    out = CL.fold(_BASE, {"security": ["- a CVE fix"]})
    unrel = out.split("## v1.0.0")[0]
    # Security is last in KaC order → after Fixed, still inside [Unreleased].
    assert unrel.index("### Fixed") < unrel.index("### Security")
    assert "### Security\n- a CVE fix" in unrel


def test_fold_is_noop_without_bullets() -> None:
    assert CL.fold(_BASE, {}) == _BASE


def test_repo_changelog_has_unreleased_anchor() -> None:
    # The real file must keep the anchor the compiler targets.
    text = (Path(__file__).resolve().parents[2] / "CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    assert CL.UNRELEASED in text


def test_validate_body_accepts_bullets_and_continuations() -> None:
    # The shape the README documents: bullets, with two-space continuation lines, and
    # flush-left prose paragraphs as many existing fragments already carry.
    CL.validate_body(
        "ok.fixed.md",
        [
            "- a bullet with **bold** and `code`",
            "  a two-space continuation line",
            "- a second bullet mentioning a C# library and a col#umn",
            "Flush-left prose, which the corpus uses and the compiler folds as-is.",
        ],
    )


@pytest.mark.parametrize("hashes", ["#", "##", "###", "####", "#####", "######"])
def test_validate_body_rejects_every_heading_level(hashes: str) -> None:
    # Negative control (VERIFY-01): the guard is observed to fire at every heading
    # depth, not only the '##' that truncates the [Unreleased] window.
    with pytest.raises(ValueError, match="bullets only"):
        CL.validate_body("bad.fixed.md", ["- fine", f"{hashes} Added"])


def test_collect_fails_closed_on_a_heading_fragment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Guard-the-guard: prove the validator is actually WIRED into the fold path, so a
    # real compile refuses the fragment instead of corrupting CHANGELOG.md.
    (tmp_path / "900-good.added.md").write_text("- a clean bullet\n", encoding="utf-8")
    monkeypatch.setattr(CL, "FRAG_DIR", tmp_path)
    assert CL._collect() == {"added": ["- a clean bullet"]}

    (tmp_path / "901-bad.fixed.md").write_text(
        "## Fixed\n\n- a bullet under a stray heading\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="901-bad.fixed.md"):
        CL._collect()


def test_every_repo_fragment_body_is_heading_free() -> None:
    # The live gate: no pending fragment may carry a heading. A fragment that does
    # folds it into [Unreleased] verbatim, where '##' truncates the window that every
    # later compile inserts into (observed on main before #1275).
    checked = 0
    for frag in CL.fragments():
        body = frag.read_text(encoding="utf-8").strip("\n")
        CL.validate_body(frag.name, [ln for ln in body.split("\n") if ln.strip()])
        checked += 1
    # Guard-the-guard: an empty or mis-globbed changelog.d must not pass vacuously.
    assert checked > 0, "no fragments were scanned - the shape check is inert"
