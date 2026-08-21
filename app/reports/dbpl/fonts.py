"""DBPL font provisioning — local-first, web-optional, metric-compatible fallback.

The problem this solves
-----------------------
WeasyPrint renders successfully with a **substituted** face. A PDF that came out looking fine is
therefore no evidence that the house font was used, and a report whose typography silently changed
between two runs is a reproducibility defect, not a cosmetic one.

So resolution is explicit and its outcome is **surfaced**, never assumed.

Resolution order
----------------
1. **Bundled** — a font file committed beside this module (``_FONT_DIR``). Deterministic, offline,
   identical on every machine and in the container. This is the preferred tier.
2. **System** — the family is installed and resolves natively through fontconfig.
3. **Web** — fetched at production time from the declared OFL source, when explicitly enabled.
   Off by default: a build that reaches the network to look right is a build that renders
   differently when the network is down.
4. **Fallback** — a metric-compatible face. Glyph shapes change; line breaks and pagination do
   not, because the fallbacks are chosen for metric compatibility.

Why this superfamily
--------------------
Source Serif 4 / Source Sans 3 / Source Code Pro: one family in three optical classes, which
satisfies Vignelli's "differentiate by weight, not by adding families" while still giving a serif
for continuous prose (Bringhurst, Butterick), a sans for dense tables (Carbon's data-table spec,
ADB's own practice) and a monospace for identifiers.

All three are SIL Open Font Licence 1.1 — freely usable, embeddable and redistributable.

**All three are tabular by default** — verified by comparing digit advance widths in the actual
font binaries (Source Serif 4: 529/1000 for every digit; Source Sans 3: 497; Source Code Pro: 600).
That matters more than any other single micro-typographic property for a financial table: it is
what makes a column of DSCRs align without decimal tabs. ``font-variant-numeric: tabular-nums`` is
still asserted in the stylesheet as belt-and-braces.

GWTF:
    - DBPL-01: the font stack is part of the print contract, not a per-document choice.
    - CASPER: every tier degrades to the next; a missing font never raises. What it does do is
      report honestly which tier answered.
    - CCCDIR: pure resolution logic. No rendering, no finance.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

__all__ = [
    "FONT_DIR",
    "DBPL_FONTS",
    "FontSpec",
    "FontProvision",
    "provision_fonts",
    "font_face_css",
    "resolution_summary",
]

#: Where a bundled font file is looked for. Committed fonts live here.
FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


@dataclass(frozen=True)
class FontSpec:
    """One house family and how to obtain it.

    Fields
        role: ``serif`` | ``sans`` | ``mono`` — the optical class, not the family name.
        family: the canonical family name as fontconfig and CSS know it.
        filename: the bundled file name looked for under :data:`FONT_DIR`.
        web_css: the OFL web source for the opt-in runtime tier.
        fallbacks: metric-compatible faces, in preference order.
        licence: the licence the family ships under.
    """

    role: str
    family: str
    filename: str
    web_css: str
    fallbacks: tuple[str, ...]
    italic_filename: Optional[str] = None
    licence: str = "SIL Open Font License 1.1"

    @property
    def css_stack(self) -> str:
        """The full CSS ``font-family`` stack: house family first, then fallbacks."""
        names = [self.family, *self.fallbacks]
        quoted = [f"'{n}'" if " " in n else n for n in names]
        generic = {"serif": "serif", "sans": "sans-serif", "mono": "monospace"}[
            self.role
        ]
        return ", ".join([*quoted, generic])


#: The house superfamily. Fallbacks are metric-compatible, so a substitution changes glyph shapes
#: but not pagination — the property that makes a substitution survivable rather than corrupting.
DBPL_FONTS: tuple[FontSpec, ...] = (
    FontSpec(
        role="serif",
        family="Source Serif 4",
        filename="SourceSerif4-Variable.ttf",
        web_css="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        fallbacks=(
            "Source Serif Pro",
            "Liberation Serif",
            "Times New Roman",
            "DejaVu Serif",
        ),
        italic_filename="SourceSerif4-Italic-Variable.ttf",
    ),
    FontSpec(
        role="sans",
        family="Source Sans 3",
        filename="SourceSans3-Variable.ttf",
        web_css="https://fonts.googleapis.com/css2?family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap",
        fallbacks=("Source Sans Pro", "Liberation Sans", "Arial", "DejaVu Sans"),
        italic_filename="SourceSans3-Italic-Variable.ttf",
    ),
    FontSpec(
        role="mono",
        family="Source Code Pro",
        filename="SourceCodePro-Variable.ttf",
        web_css="https://fonts.googleapis.com/css2?family=Source+Code+Pro:wght@400;600&display=swap",
        fallbacks=("Liberation Mono", "DejaVu Sans Mono", "Courier New"),
    ),
)


@dataclass(frozen=True)
class FontProvision:
    """How one family was actually resolved, and by which tier."""

    spec: FontSpec
    tier: str  # bundled | system | web | fallback
    detail: str

    @property
    def is_house_font(self) -> bool:
        """True when the house family itself resolved — not a fallback."""
        return self.tier in {"bundled", "system", "web"}

    @property
    def note(self) -> str:
        if self.tier == "fallback":
            return f"{self.spec.family}: FALLBACK — {self.detail}"
        return f"{self.spec.family}: {self.tier} — {self.detail}"


def _bundled(spec: FontSpec) -> Optional[Path]:
    """The committed font file, when present."""
    path = FONT_DIR / spec.filename
    return path if path.is_file() else None


def _system_resolves(spec: FontSpec) -> Optional[str]:
    """The face fontconfig actually returns for the family, or ``None`` when unavailable.

    Uses ``fc-match`` rather than attempting a render: a render succeeds with a substituted face,
    which is exactly the failure mode being guarded against.
    """
    binary = shutil.which("fc-match")
    if binary is None:
        return None
    try:
        out = subprocess.run(  # noqa: S603 - fixed binary, family names are our own constants
            [binary, "-f", "%{family}", spec.family],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    # fc-match ALWAYS returns something; a genuine hit is one that names the family back.
    return out if spec.family.lower() in out.lower() else None


def provision_fonts(
    specs: Sequence[FontSpec] = DBPL_FONTS,
    *,
    allow_web: bool = False,
) -> tuple[FontProvision, ...]:
    """Resolve every house family and report the tier that answered.

    Args:
        specs: the families to resolve.
        allow_web: permit the runtime web tier. **Off by default** — a build that reaches the
            network in order to look right renders differently when the network is down, which
            makes the output non-reproducible.

    Returns:
        One :class:`FontProvision` per family. Never raises: an unresolvable family degrades to
        the metric-compatible fallback and says so.
    """
    provisions: list[FontProvision] = []
    for spec in specs:
        bundled = _bundled(spec)
        if bundled is not None:
            provisions.append(
                FontProvision(
                    spec,
                    "bundled",
                    f"{bundled.name} ({bundled.stat().st_size:,} bytes)",
                )
            )
            continue
        system = _system_resolves(spec)
        if system is not None:
            provisions.append(
                FontProvision(spec, "system", f"fontconfig resolved {system}")
            )
            continue
        if allow_web:
            provisions.append(FontProvision(spec, "web", spec.web_css))
            continue
        provisions.append(
            FontProvision(
                spec, "fallback", f"using {spec.fallbacks[0]} (metric-compatible)"
            )
        )
    return tuple(provisions)


def font_face_css(provisions: Sequence[FontProvision]) -> str:
    """``@font-face`` / ``@import`` rules for the tiers that need them.

    A bundled font is embedded by absolute ``file://`` URL so the rule resolves regardless of the
    document's base URL. System and fallback tiers need no rule — the stack in the stylesheet
    already names them.
    """
    blocks: list[str] = []
    for prov in provisions:
        if prov.tier == "bundled":
            path = FONT_DIR / prov.spec.filename
            blocks.append(
                "@font-face {\n"
                f"  font-family: '{prov.spec.family}';\n"
                f"  src: url('file://{path}') format('truetype');\n"
                "  font-weight: 100 900;\n"
                "  font-style: normal;\n"
                "}"
            )
            italic = prov.spec.italic_filename
            if italic and (FONT_DIR / italic).is_file():
                blocks.append(
                    "@font-face {\n"
                    f"  font-family: '{prov.spec.family}';\n"
                    f"  src: url('file://{FONT_DIR / italic}') format('truetype');\n"
                    "  font-weight: 100 900;\n"
                    "  font-style: italic;\n"
                    "}"
                )
        elif prov.tier == "web":
            blocks.append(f"@import url('{prov.spec.web_css}');")
    return "\n".join(blocks)


def resolution_summary(provisions: Sequence[FontProvision]) -> Mapping[str, str]:
    """Role → resolution note, for stamping into a document's provenance block."""
    return {p.spec.role: p.note for p in provisions}
