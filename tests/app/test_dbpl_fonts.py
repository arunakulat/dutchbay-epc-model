"""Tests for DBPL font provisioning.

The property that matters: a substituted face must be REPORTED, never silently accepted.
WeasyPrint renders happily with the wrong font, so the resolution tier is the only evidence
that the house typography was actually used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# fontTools is safe to import here without declaring it: WeasyPrint declares
# `fonttools[woff] >=4.59.2` as a direct dependency, and WeasyPrint is in the [report] extra that
# GWTF DBPL-01 requires. So wherever the DBPL can run at all, fontTools is present. This is a real
# anchor, unlike `packaging` elsewhere, which is transitive with no such guarantee (#756).
from fontTools.ttLib import TTFont

from app.reports.dbpl import fonts as fmod
from app.reports.dbpl.fonts import (
    DBPL_FONTS,
    FONT_DIR,
    FontProvision,
    FontSpec,
    font_face_css,
    provision_fonts,
    resolution_summary,
)

# ── The superfamily contract ─────────────────────────────────────────────────


def test_three_optical_classes_are_declared() -> None:
    assert {s.role for s in DBPL_FONTS} == {"serif", "sans", "mono"}


def test_every_family_is_ofl_licensed() -> None:
    for spec in DBPL_FONTS:
        assert "Open Font License" in spec.licence


def test_licence_text_is_bundled_beside_the_fonts() -> None:
    """OFL redistribution requires the licence to travel with the fonts."""
    assert (FONT_DIR / "OFL.txt").is_file()


def test_every_bundled_font_file_exists() -> None:
    for spec in DBPL_FONTS:
        assert (FONT_DIR / spec.filename).is_file(), f"{spec.filename} not bundled"


def test_bundled_fonts_have_tabular_figures() -> None:
    """The single most important property for a financial table.

    Verified against the actual binary rather than trusted: every digit must have the same
    advance width, which is what aligns a column of DSCRs without decimal tabs.
    """
    for spec in DBPL_FONTS:
        font = TTFont(FONT_DIR / spec.filename)
        cmap = font.getBestCmap()
        widths = {font["hmtx"][cmap[ord(d)]][0] for d in "0123456789" if ord(d) in cmap}
        assert (
            len(widths) == 1
        ), f"{spec.family} digits are proportional: {sorted(widths)}"


def test_fallbacks_are_metric_compatible_faces() -> None:
    """A substitution must change glyph shapes but not pagination."""
    serif = next(s for s in DBPL_FONTS if s.role == "serif")
    assert (
        "Liberation Serif" in serif.fallbacks and "Times New Roman" in serif.fallbacks
    )
    sans = next(s for s in DBPL_FONTS if s.role == "sans")
    assert "Liberation Sans" in sans.fallbacks and "Arial" in sans.fallbacks


def test_css_stack_ends_in_a_generic_family() -> None:
    for spec in DBPL_FONTS:
        assert spec.css_stack.rstrip().endswith(("serif", "sans-serif", "monospace"))
        assert spec.css_stack.startswith(f"'{spec.family}'")


# ── Resolution tiers ─────────────────────────────────────────────────────────


def test_bundled_tier_wins_when_the_file_is_present() -> None:
    for prov in provision_fonts():
        assert prov.tier == "bundled"
        assert prov.is_house_font is True


def test_missing_bundle_degrades_to_fallback_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fmod, "FONT_DIR", tmp_path)
    monkeypatch.setattr(fmod, "_system_resolves", lambda _s: None)
    provs = provision_fonts()
    assert all(p.tier == "fallback" for p in provs)
    assert all(p.is_house_font is False for p in provs)
    assert "FALLBACK" in provs[0].note


def test_web_tier_is_opt_in_not_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A build that reaches the network to look right is not reproducible offline."""
    monkeypatch.setattr(fmod, "FONT_DIR", tmp_path)
    monkeypatch.setattr(fmod, "_system_resolves", lambda _s: None)
    assert all(p.tier == "fallback" for p in provision_fonts())
    assert all(p.tier == "web" for p in provision_fonts(allow_web=True))


def test_system_tier_used_when_fontconfig_names_the_family_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fmod, "FONT_DIR", tmp_path)
    monkeypatch.setattr(fmod, "_system_resolves", lambda s: s.family)
    assert all(p.tier == "system" for p in provision_fonts())


def test_fontconfig_substitution_is_not_counted_as_a_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fc-match ALWAYS returns something; only a reply naming the family counts."""
    monkeypatch.setattr(fmod.shutil, "which", lambda _n: "/usr/bin/fc-match")

    class _R:
        stdout = "Times New Roman"

    monkeypatch.setattr(fmod.subprocess, "run", lambda *a, **k: _R())
    spec = next(s for s in DBPL_FONTS if s.role == "serif")
    assert fmod._system_resolves(spec) is None


def test_absent_fontconfig_degrades_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmod.shutil, "which", lambda _n: None)
    assert fmod._system_resolves(DBPL_FONTS[0]) is None


def test_fontconfig_failure_degrades_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fmod.shutil, "which", lambda _n: "/usr/bin/fc-match")

    def boom(*_a: object, **_k: object) -> object:
        raise OSError("fc-match exploded")

    monkeypatch.setattr(fmod.subprocess, "run", boom)
    assert fmod._system_resolves(DBPL_FONTS[0]) is None


# ── CSS emission ─────────────────────────────────────────────────────────────


def test_bundled_tier_emits_font_face_rules_including_italics() -> None:
    css = font_face_css(provision_fonts())
    assert css.count("@font-face") == 5, "3 upright + 2 italic companions"
    assert "font-style: italic" in css
    assert "file://" in css, "bundled fonts embed by absolute path"


def test_web_tier_emits_an_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fmod, "FONT_DIR", tmp_path)
    monkeypatch.setattr(fmod, "_system_resolves", lambda _s: None)
    css = font_face_css(provision_fonts(allow_web=True))
    assert css.count("@import") == 3
    assert "fonts.googleapis.com" in css


def test_fallback_tier_emits_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The stylesheet's own stack already names the fallbacks."""
    monkeypatch.setattr(fmod, "FONT_DIR", tmp_path)
    monkeypatch.setattr(fmod, "_system_resolves", lambda _s: None)
    assert font_face_css(provision_fonts()) == ""


def test_resolution_summary_is_keyed_by_role() -> None:
    summary = resolution_summary(provision_fonts())
    assert set(summary) == {"serif", "sans", "mono"}
    assert all(isinstance(v, str) and v for v in summary.values())


def test_provision_note_distinguishes_fallback_from_a_real_hit() -> None:
    spec = DBPL_FONTS[0]
    assert "FALLBACK" in FontProvision(spec, "fallback", "x").note
    assert "FALLBACK" not in FontProvision(spec, "bundled", "x").note


def test_unknown_role_is_rejected_by_the_css_stack() -> None:
    bad = FontSpec(
        role="ornamental", family="X", filename="x", web_css="", fallbacks=()
    )
    with pytest.raises(KeyError):
        _ = bad.css_stack
