"""ARCH-02 fence: WACC formulas must live only in ``finance/wacc_v14.py``.

Boundary rule
-------------
The weighted-average-cost-of-capital formula is the single responsibility of
``finance/wacc_v14.py`` (GWTF ARCH-02: "WACC only from finance/wacc_v14.py").
Every other module under ``finance/``, ``analytics/`` and ``api/`` must *use*
the outputs of that module — it must never re-derive the WACC formula itself.

Without this fence a second WACC formula can drift into the codebase (it has
before: the now-retired ``finance/wacc_integration.py`` carried a parallel
``WACC = (E/V)*CoE + (D/V)*CoD*(1-T)`` derivation). Two formulas = two sources
of truth = silent disagreement.

What is flagged
---------------
A file "redefines" WACC if any line matches :data:`WACC_DEF_PATTERNS` — the
spelled-out term or a formula-shaped expression. Two carve-outs:

* ``finance/wacc_v14.py`` — the sanctioned home of the formula — is excluded.
* :data:`ALLOWLIST` — a small, documented set of files that legitimately
  *mention* WACC (e.g. a validation-bound constant + comment) without defining
  the formula. Allowlisted files are still forbidden from carrying a
  *formula-shaped* match; the allowlist only tolerates the bare term.

Run:
    pytest tests/lint/test_wacc_fence_v14.py -v

GWTF / ARCH-02:
    - ARCH-02: IRR/NPV only from finance/irr.py; WACC only from
      finance/wacc_v14.py.
    - CCCDIR: one canonical definition, imports/usages explicit.
"""

from __future__ import annotations

import re
from pathlib import Path

# Project root: tests/lint/ -> tests -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# We care about internal code, not venvs or tests.
SEARCH_ROOTS = (
    PROJECT_ROOT / "finance",
    PROJECT_ROOT / "analytics",
    PROJECT_ROOT / "api",
)

# Patterns that suggest someone is re-defining WACC formulas rather than
# just *using* the outputs from finance/wacc_v14.py.
WACC_DEF_PATTERNS: list[str] = [
    r"weighted\s+average\s+cost\s+of\s+capital",
    r"WACC\s*=\s*\(",
    r"WACC\s*=\s*(\(E\s*/\s*V|E\s*/\s*V)",  # WACC = (E/V ... style
    r"\(E\s*/\s*V\)\s*\*\s*Ke\s*\+\s*\(D\s*/\s*V\)\s*\*\s*Kd",  # (E/V)*Ke + (D/V)*Kd
]

# The sanctioned home of every WACC formula (ARCH-02). Excluded from the fence
# because this is exactly where the formula is *supposed* to live.
CANONICAL_WACC_MODULE = PROJECT_ROOT / "finance" / "wacc_v14.py"

# Narrow, documented allowlist: files that legitimately *mention* WACC without
# defining the formula. Keyed by repo-relative POSIX path -> reason. Allowlisted
# files may carry the spelled-out term but still must NOT contain a
# formula-shaped match (enforced below).
# Currently empty: the sole prior entry (analytics/contracts_v14_validators.py, a
# dead post-execution result-bounds validator) was deleted in #472 (PIPE-2).
ALLOWLIST: dict[str, str] = {}

# Compiled once. ``_FORMULA_PATTERNS`` is every pattern except the spelled-out
# term — the shapes an allowlisted file may never contain.
_COMPILED: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in WACC_DEF_PATTERNS
]
_FORMULA_PATTERNS: list[re.Pattern[str]] = _COMPILED[1:]


def _iter_python_files() -> list[Path]:
    """Return the Python files under the core code packages.

    We *exclude* tests and virtualenvs on purpose, plus the ``__pycache__``
    byte-code dirs, the canonical WACC module, and this test file itself.
    """
    files: list[Path] = []
    this_file = Path(__file__).resolve()
    canonical = CANONICAL_WACC_MODULE.resolve()
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            resolved = path.resolve()
            if "__pycache__" in resolved.parts:
                continue
            if resolved == canonical or resolved == this_file:
                continue
            files.append(path)
    return files


def _matches(text: str, patterns: list[re.Pattern[str]]) -> list[tuple[int, str]]:
    """Return ``(line_number, pattern)`` for every matching line."""
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rx in patterns:
            if rx.search(line):
                hits.append((lineno, rx.pattern))
    return hits


def test_no_wacc_redefinition() -> None:
    """ARCH-02: no WACC formula outside ``finance/wacc_v14.py``.

    Every module under finance/, analytics/ and api/ — except the canonical
    ``finance/wacc_v14.py`` and the narrow :data:`ALLOWLIST` — must be free of
    WACC formula definitions. Allowlisted files may mention the term but may
    not contain a formula-shaped match.
    """
    violations: list[str] = []
    for path in _iter_python_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        if rel in ALLOWLIST:
            # Tolerate the bare term; never an actual formula.
            for lineno, pat in _matches(text, _FORMULA_PATTERNS):
                violations.append(
                    f"{rel}:{lineno} — allowlisted file defines a WACC formula "
                    f"(pattern {pat!r}); allowlist tolerates the term only"
                )
            continue
        for lineno, pat in _matches(text, _COMPILED):
            violations.append(f"{rel}:{lineno} (pattern {pat!r})")

    assert not violations, (
        "WACC formula(s) found outside finance/wacc_v14.py (ARCH-02 fence). "
        "Use the outputs of finance/wacc_v14.py instead of re-deriving WACC:\n  "
        + "\n  ".join(violations)
    )


def test_canonical_wacc_module_exists_and_is_not_scanned() -> None:
    """Guard the fence's own premises.

    If the canonical module disappeared or were accidentally scanned, the fence
    would either miss real drift or fail trivially — so assert both.
    """
    assert (
        CANONICAL_WACC_MODULE.is_file()
    ), f"Canonical WACC module is missing: {CANONICAL_WACC_MODULE}"
    scanned = {p.resolve() for p in _iter_python_files()}
    assert CANONICAL_WACC_MODULE.resolve() not in scanned


def test_allowlist_entries_are_live() -> None:
    """Anti-rot: every ALLOWLIST entry must point at a real file.

    A carve-out for a moved/deleted file would silently weaken the fence; this
    forces the allowlist to be pruned when a file goes away.
    """
    for rel in ALLOWLIST:
        assert (
            PROJECT_ROOT / rel
        ).is_file(), f"Stale WACC-fence allowlist entry (file no longer exists): {rel}"
