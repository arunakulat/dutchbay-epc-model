"""DutchBay Presentation Layer (DBPL) — the PDF print core.

GWTF DBPL-01
------------
When a document is described as a **DutchBay Presentation Layer / DBPL / dbpl** PDF, it MUST be
produced through this module. That carries three obligations, all enforced here rather than left
to a caller's discipline:

1. The **complete** ``[report]`` optional extra must be installed — ``weasyprint``, ``reportlab``,
   ``geopandas`` and ``contextily`` — not merely the one package a given page happens to touch.
   ``geopandas``/``contextily`` back the location and context maps that a lender report may carry,
   and a print core that renders text today and fails on the first map tomorrow is not a print
   core. Missing packages raise :class:`DbplDependencyError`.
2. The DBPL **house style** must be applied (:mod:`app.reports.dbpl.style`), so every DutchBay
   document looks like the same document.
3. The **font provenance** must be surfaced. This is the subtle one: WeasyPrint renders happily
   with a substituted face, so a successful render proves nothing about which font was used. A
   missing family is not fatal — the DBPL stack falls back to metric-compatible faces, which
   changes glyph shapes but not pagination — but the substitution is RECORDED and returned, never
   hidden.

Fail loud, not graceful
-----------------------
This is a deliberate departure from the CASPER default elsewhere in the reporting layer. The
generic renderer (:mod:`app.reports.renderer`) degrades when WeasyPrint is absent because the HTML
report is still useful without it. Here the PDF *is* the deliverable: degrading would emit a
document that claims to be a DBPL PDF while missing the machinery that makes it one. A caller who
wants a best-effort render should call the generic renderer and not describe the result as DBPL.

GWTF:
    - CESSPIT: incomplete extra raises; no silent partial render.
    - CCCDIR: presentation only. No finance, no scenario, no engine imports.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence

from app.ops.extras import ExtraStatus, probe_extra
from app.reports.dbpl.fonts import font_face_css, provision_fonts, resolution_summary
from app.reports.dbpl.style import (
    DBPL_REFERENCE_DOCUMENT,
    DBPL_REQUIRED_FONT_FAMILIES,
    as_css_variables,
)

__all__ = [
    "DBPL_EXTRA",
    "DbplDependencyError",
    "FontResolution",
    "DbplRenderResult",
    "require_dbpl_stack",
    "probe_fonts",
    "render_dbpl_pdf",
    "dbpl_stylesheet",
]

#: The optional extra a DBPL PDF requires, in full.
DBPL_EXTRA = "report"

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_STYLESHEET = _TEMPLATE_DIR / "dbpl.css"


class DbplDependencyError(RuntimeError):
    """Raised when the DBPL print stack is incomplete (CESSPIT — fail loud)."""


@dataclass(frozen=True)
class FontResolution:
    """What a requested font family actually resolved to on this machine.

    ``substituted`` is the field that matters: a True value means the document rendered with a
    different face than the house style asks for.
    """

    family: str
    resolved: Optional[str]
    substituted: bool

    @property
    def note(self) -> str:
        if self.resolved is None:
            return f"{self.family}: resolution unknown (fontconfig unavailable)"
        if self.substituted:
            return f"{self.family}: SUBSTITUTED by {self.resolved}"
        return f"{self.family}: native"


@dataclass(frozen=True)
class DbplRenderResult:
    """A rendered DBPL PDF plus the provenance of how it was produced."""

    pdf: bytes
    extra_status: ExtraStatus
    fonts: tuple[FontResolution, ...]
    stylesheet_applied: bool = True
    font_tiers: Mapping[str, str] = field(default_factory=dict)

    @property
    def substituted_fonts(self) -> tuple[str, ...]:
        return tuple(f.family for f in self.fonts if f.substituted)

    def provenance_lines(self) -> tuple[str, ...]:
        """Human-readable provenance, for logging or for stamping into a caller's report."""
        versions = ", ".join(
            f"{p.distribution}=={p.installed_version}"
            for p in self.extra_status.packages
            if p.installed_version
        )
        lines = [
            f"DBPL print core · [{DBPL_EXTRA}] extra: {versions}",
            f"House style measured from {DBPL_REFERENCE_DOCUMENT}",
        ]
        lines.extend(
            f"font {role}: {note}" for role, note in sorted(self.font_tiers.items())
        )
        lines.extend(f.note for f in self.fonts)
        return tuple(lines)


def require_dbpl_stack(*, deep: bool = True) -> ExtraStatus:
    """Assert the complete ``[report]`` extra is installed and usable.

    Args:
        deep: also import-check each package. On by default, because the failure this guards
            against — WeasyPrint installed without pango/cairo — is invisible to a metadata check
            and shows up as a broken PDF at the first request.

    Returns:
        The probed status, for surfacing as provenance.

    Raises:
        DbplDependencyError: any declared package is missing, violates its pin, or fails to
            import. The message names what is wrong and how to fix it.
    """
    status = probe_extra(DBPL_EXTRA, deep=deep)
    if not status.packages:
        raise DbplDependencyError(
            "the [report] extra declares no packages — the project is not installed as "
            "distribution metadata, so the DBPL stack cannot be verified. Install the project "
            "(pip install -e '.[report]') before rendering a DBPL PDF."
        )
    if status.available:
        return status

    problems: list[str] = []
    if status.missing:
        problems.append(f"not installed: {', '.join(status.missing)}")
    if status.broken:
        for pkg in status.packages:
            if pkg.import_error:
                problems.append(
                    f"{pkg.distribution} installed but not importable — "
                    f"{pkg.import_error}"
                )
            elif pkg.satisfies_spec is False:
                problems.append(
                    f"{pkg.distribution} {pkg.installed_version} violates its declared pin "
                    f"{pkg.declared_spec}"
                )
    raise DbplDependencyError(
        "the DBPL print core requires the COMPLETE [report] extra "
        "(weasyprint, reportlab, geopandas, contextily). "
        + "; ".join(problems)
        + ". Fix with: pip install -e '.[report]'"
        + (
            " — an installed-but-unimportable package usually means a missing system library "
            "(WeasyPrint needs pango/cairo; see docs/deploy/DEPLOY.md)."
            if status.broken
            else "."
        )
    )


def probe_fonts(
    families: Sequence[str] = DBPL_REQUIRED_FONT_FAMILIES,
) -> tuple[FontResolution, ...]:
    """Resolve each house family through fontconfig and report substitutions.

    Uses ``fc-match`` rather than attempting a render, because WeasyPrint renders successfully
    with a substituted face — a render proves the pipeline works, not that the requested font was
    used. When ``fc-match`` is unavailable the resolution is reported as unknown rather than
    guessed.

    **Scope limit, and it matters.** This answers only "is the family installed on this system".
    It is blind to a font embedded via ``@font-face``, which is how the bundled tier supplies the
    house superfamily — fontconfig has never heard of a file the stylesheet points at. Reporting
    its verdict alongside the provisioning tier therefore produced directly contradictory
    provenance ("bundled" and "SUBSTITUTED" for the same family in one block).
    :func:`render_dbpl_pdf` consequently reports the PROVISIONING tier, which is authoritative,
    and consults this only for families the provisioner did not supply.
    """
    binary = shutil.which("fc-match")
    if binary is None:
        return tuple(FontResolution(f, None, False) for f in families)

    resolutions: list[FontResolution] = []
    for family in families:
        try:
            out = subprocess.run(  # noqa: S603 - fixed binary, family names are our own constants
                [binary, "-f", "%{family}", family],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            resolutions.append(FontResolution(family, None, False))
            continue
        resolved = out or None
        # `resolved is not None` rather than `bool(resolved)`: mypy narrows the Optional on the
        # explicit identity check, and an empty string is already collapsed to None above.
        substituted = resolved is not None and family.lower() not in resolved.lower()
        resolutions.append(FontResolution(family, resolved, substituted))
    return tuple(resolutions)


def dbpl_stylesheet(*, allow_web_fonts: bool = False) -> str:
    """The DBPL stylesheet: @font-face rules, then design tokens, then the house rules.

    Order matters. ``@font-face`` and ``@import`` must precede any rule that uses the families,
    and the token block must precede the house rules that reference its custom properties.
    """
    base = _STYLESHEET.read_text(encoding="utf-8") if _STYLESHEET.exists() else ""
    faces = font_face_css(provision_fonts(allow_web=allow_web_fonts))
    return f"{faces}\n\n{as_css_variables()}\n\n{base}"


def render_dbpl_pdf(
    html: str,
    *,
    extra_css: Optional[str] = None,
    base_url: Optional[str] = None,
    deep_check: bool = True,
    allow_web_fonts: bool = False,
) -> DbplRenderResult:
    """Render DBPL HTML to PDF through the enforced ``[report]`` stack.

    Args:
        html: a complete HTML document, normally produced from the DBPL base template.
        extra_css: additional CSS appended after the house stylesheet.
        base_url: base for resolving relative assets (images, embedded maps).
        deep_check: import-check the extra as well as verifying it is installed.

    Returns:
        The PDF bytes plus the dependency and font provenance behind them.

    Raises:
        DbplDependencyError: the ``[report]`` stack is incomplete.
    """
    status = require_dbpl_stack(deep=deep_check)

    from weasyprint import (  # imported after the guard, so the error is ours not a stack
        CSS,
        HTML,
    )
    from weasyprint.text.fonts import FontConfiguration

    provisions = provision_fonts(allow_web=allow_web_fonts)
    # Only fc-match families the provisioner did NOT supply; for a bundled or web family the
    # provisioning tier is the authoritative answer and fontconfig's is simply out of scope.
    unprovisioned = tuple(p.spec.family for p in provisions if not p.is_house_font)
    font_config = FontConfiguration()
    sheets = [
        CSS(
            string=dbpl_stylesheet(allow_web_fonts=allow_web_fonts),
            font_config=font_config,
        )
    ]
    if extra_css:
        sheets.append(CSS(string=extra_css, font_config=font_config))

    pdf = HTML(string=html, base_url=base_url).write_pdf(
        stylesheets=sheets, font_config=font_config
    )
    return DbplRenderResult(
        pdf=pdf,
        extra_status=status,
        fonts=probe_fonts(unprovisioned) if unprovisioned else (),
        font_tiers=dict(resolution_summary(provisions)),
    )
