"""Docstring-coverage ratchet: make GWTF R24's advertised enforcement real.

Issue #958 (register §4.3 DOC1).

Why this file exists
--------------------
GWTF rule **R24** ("Docstring-first development") advertises its enforcement as
a "lint test (``test_docstring_coverage.py``) [that] checks that all public
functions have non-empty docstrings". Until this file was added, **no such test
existed anywhere in the tree** — the rule advertised enforcement that was never
wired. This module reconciles that contradiction by making the advertised file
real, and by pinning what it actually enforces.

What it enforces (and what it deliberately does not)
----------------------------------------------------
Public-API docstring coverage is **not** at 100% today (measured below), so a
strict "every public symbol must have a docstring" gate would fail on existing
code and could not be committed green. Instead this is a **ratchet floor**, in
the same spirit as ``tests/lint/test_no_direct_finance_pipeline_imports.py``:

  * ``test_docstring_coverage_meets_floor`` fails the moment a package's public
    docstring coverage drops **below** its pinned per-package floor, i.e. the
    moment new public code lands without a docstring (or a documented symbol is
    replaced by an undocumented one). This is the regression guard R24 promised.
  * ``test_floor_is_not_left_slack`` is the ratchet's other jaw: once a package
    climbs well above its floor, the floor must be raised to lock the gain in.
    This keeps the floors from rotting into meaningless low-water marks.

R24's enforcement text was amended in the same change (issue #958) to describe
this ratchet-floor behaviour rather than the never-true "all public functions"
claim, and ``test_r24_text_matches_reality`` pins that reconciliation so the doc
and the code cannot drift apart again.

Definition of "public API" (deterministic, static)
---------------------------------------------------
Measured by static ``ast`` parsing — the target modules are **never imported**,
so this guard has no optional-dependency (CASPER) exposure and does not perturb
the coverage denominator of the packages it measures. A symbol counts iff:

  * it lives in a **public module** — no path component (directory or the file
    stem) starts with ``_`` (so ``__init__.py`` and ``_private.py`` are skipped);
  * it is a **public** module-level ``def``/``async def``/``class`` (name does
    not start with ``_``), **or** a public method of such a public class.

A symbol is "documented" iff ``ast.get_docstring`` returns a non-empty (after
``strip``) string.

Run:
    pytest tests/lint/test_docstring_coverage.py -v

GWTF:
    - R24  : Docstring-first development — this IS its wired enforcement.
    - CST/TEST series: static inspection, no runtime import of the target.
"""

from __future__ import annotations

import ast
import csv
from pathlib import Path
from typing import Dict, List, NamedTuple, Tuple, Union

import pytest

# A public API definition node: a function, async function, or class.
Definition = Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]

# ═════════════════════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════════════════════

# Repository root (tests/lint/ -> tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Top-level first-party packages whose public API R24 governs.
PACKAGES: Tuple[str, ...] = ("api", "analytics", "finance")

# ─────────────────────────────────────────────────────────────────────────────
# Per-package ratchet FLOORS (minimum acceptable public-API docstring %).
#
# These are pinned a hair below the coverage measured at the time this guard was
# wired (issue #958), so they lock in today's state without tripping on float
# noise:
#
#     package     measured %   floor
#     ---------   ----------   -----
#     api             63.16    63.0
#     analytics       85.92    85.5
#     finance         91.27    91.0
#
# RATCHET DISCIPLINE: only ever move a floor UP. When you add docstrings and a
# package climbs past ``floor + RATCHET_SLACK_PP``, raise its floor here in the
# same PR (``test_floor_is_not_left_slack`` will remind you). Never lower a floor
# to make a regression pass — add the missing docstring instead.
# ─────────────────────────────────────────────────────────────────────────────
MIN_COVERAGE_PCT: Dict[str, float] = {
    "api": 63.0,
    "analytics": 85.5,
    "finance": 91.0,
}

# How far above its floor a package may drift before the floor must be ratcheted
# up. Generous enough that ordinary small improvements do not trip it, tight
# enough that a real jump in coverage must be locked in.
RATCHET_SLACK_PP = 5.0

# The GWTF rule this test is the enforcement for, and the CSV that holds it.
GWTF_CSV = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
RULE_ID = "R24"

# The stale overclaim that R24 used to make (issue #958). Pinned here so the
# reconciliation cannot silently regress back into the CSV.
STALE_R24_CLAIM = "checks that all public functions have non-empty docstrings"


# ═════════════════════════════════════════════════════════════════════════════
# Static docstring-coverage measurement (pure ast, no import of the target)
# ═════════════════════════════════════════════════════════════════════════════


class Coverage(NamedTuple):
    """Docstring-coverage result for one package.

    Attributes:
        total: Count of public API symbols considered.
        documented: How many of those have a non-empty docstring.
        missing: ``"path:lineno:name"`` for each undocumented public symbol.
    """

    total: int
    documented: int
    missing: List[str]

    @property
    def pct(self) -> float:
        """Documented fraction as a percentage (100.0 for an empty package)."""
        return 100.0 * self.documented / self.total if self.total else 100.0


def _is_public_module(rel_path: Path) -> bool:
    """True if no component of ``rel_path`` (dirs or file stem) starts with ``_``.

    Args:
        rel_path: Repo-relative path to a ``.py`` file.

    Returns:
        Whether the module is part of the public surface (``__init__.py`` and
        ``_private.py`` style modules are excluded).
    """
    for part in rel_path.parts[:-1]:
        if part.startswith("_"):
            return False
    stem = (
        rel_path.parts[-1][:-3]
        if rel_path.parts[-1].endswith(".py")
        else rel_path.parts[-1]
    )
    return not stem.startswith("_")


def _public_api_nodes(tree: ast.Module) -> List[Definition]:
    """Return the public API definition nodes of a parsed module.

    Public module-level functions and classes, plus the public methods of those
    public classes. Names starting with ``_`` are private and excluded.

    Args:
        tree: A parsed module AST.

    Returns:
        The list of function/class/method nodes that count toward coverage.
    """
    nodes: List[Definition] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                nodes.append(node)
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            nodes.append(node)
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not sub.name.startswith("_"):
                        nodes.append(sub)
    return nodes


def _measure_package(pkg: str) -> Coverage:
    """Measure public-API docstring coverage for one top-level package.

    Args:
        pkg: Package directory name under the repo root (e.g. ``"analytics"``).

    Returns:
        A :class:`Coverage` for the package.
    """
    total = 0
    documented = 0
    missing: List[str] = []
    root = REPO_ROOT / pkg
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(REPO_ROOT)
        if not _is_public_module(rel):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _public_api_nodes(tree):
            total += 1
            doc = ast.get_docstring(node)
            if doc and doc.strip():
                documented += 1
            else:
                missing.append(f"{rel.as_posix()}:{node.lineno}:{node.name}")
    return Coverage(total=total, documented=documented, missing=missing)


# Measure once at collection time so every test reads the same source of truth.
_COVERAGE: Dict[str, Coverage] = {pkg: _measure_package(pkg) for pkg in PACKAGES}


def _read_r24_enforcement() -> str:
    """Return the enforcement-column text of GWTF rule R24 from the CSV.

    Returns:
        The R24 ``enforcement`` field.

    Raises:
        AssertionError: If the CSV or the R24 row cannot be found.
    """
    assert GWTF_CSV.exists(), f"GWTF CSV not found at {GWTF_CSV}"
    with GWTF_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("rule_id") == RULE_ID:
                return row.get("enforcement", "")
    raise AssertionError(f"Rule {RULE_ID} not found in {GWTF_CSV}")


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("pkg", PACKAGES)
def test_docstring_coverage_meets_floor(pkg: str) -> None:
    """Public-API docstring coverage must not regress below the pinned floor.

    This is the regression guard R24 advertises: it fails the moment public code
    lands without a docstring and drives a package below its floor.
    """
    cov = _COVERAGE[pkg]
    floor = MIN_COVERAGE_PCT[pkg]
    # Show at most a handful of offenders so a failure is actionable, not a wall.
    sample = "\n".join(f"    {m}" for m in cov.missing[:15])
    more = (
        "" if len(cov.missing) <= 15 else f"\n    ... and {len(cov.missing) - 15} more"
    )
    assert cov.pct >= floor, (
        f"R24 docstring-coverage REGRESSION in '{pkg}/': "
        f"{cov.pct:.2f}% < floor {floor:.2f}% "
        f"({cov.documented}/{cov.total} public symbols documented).\n"
        f"Add a Google-style docstring to the undocumented public symbol(s) you "
        f"introduced. Undocumented public symbols in this package:\n"
        f"{sample}{more}\n"
        f"Do NOT lower the floor to make this pass."
    )


@pytest.mark.parametrize("pkg", PACKAGES)
def test_floor_is_not_left_slack(pkg: str) -> None:
    """Ratchet the floor up once a package climbs well above it.

    The other jaw of the ratchet: if coverage has improved past
    ``floor + RATCHET_SLACK_PP`` the floor is now stale and must be raised in
    this PR so the gain is locked in and cannot silently erode later.
    """
    cov = _COVERAGE[pkg]
    floor = MIN_COVERAGE_PCT[pkg]
    ceiling = floor + RATCHET_SLACK_PP
    assert cov.pct <= ceiling, (
        f"R24 docstring-coverage for '{pkg}/' has risen to {cov.pct:.2f}%, more "
        f"than {RATCHET_SLACK_PP:.1f}pp above its floor of {floor:.2f}%. "
        f"Raise MIN_COVERAGE_PCT['{pkg}'] in this file (e.g. to "
        f"{cov.pct - 0.5:.1f}) to lock in the improvement — that is the ratchet."
    )


@pytest.mark.parametrize("pkg", PACKAGES)
def test_package_surface_is_nonempty(pkg: str) -> None:
    """Guard against a vacuous pass: each package must expose public symbols.

    If the walker found zero symbols (e.g. a path bug), ``pct`` would be a
    meaningless 100% and the floor test would pass for the wrong reason.
    """
    assert _COVERAGE[pkg].total > 0, (
        f"No public API symbols discovered under '{pkg}/'. The measurement "
        f"walker is broken or the package moved — the coverage floor would pass "
        f"vacuously. Investigate before trusting this guard."
    )


def test_measurement_harness_detects_missing_docstrings() -> None:
    """Prove the detector distinguishes documented from undocumented symbols.

    Without this, the floor tests could pass because the harness silently counts
    everything as documented. Exercises every branch of the public-API rules on
    a synthetic module: documented/undocumented functions and classes, a public
    method, and the private/dunder exclusions.
    """
    source = '''
def documented_fn():
    """I have a docstring."""


def undocumented_fn():
    pass


def _private_fn():
    # excluded: name starts with underscore
    pass


class DocumentedClass:
    """I have a docstring."""

    def documented_method(self):
        """I have one too."""

    def undocumented_method(self):
        pass

    def _private_method(self):
        pass


class UndocumentedClass:
    pass


class _PrivateClass:
    """Excluded regardless of docstring."""
'''
    tree = ast.parse(source)
    nodes = _public_api_nodes(tree)
    names = {n.name for n in nodes}
    # Public functions, classes, and public methods of public classes are in.
    assert names == {
        "documented_fn",
        "undocumented_fn",
        "DocumentedClass",
        "documented_method",
        "undocumented_method",
        "UndocumentedClass",
    }, names
    # Private/dunder symbols are excluded.
    assert "_private_fn" not in names
    assert "_private_method" not in names
    assert "_PrivateClass" not in names

    documented = {n.name for n in nodes if (ast.get_docstring(n) or "").strip()}
    assert documented == {
        "documented_fn",
        "DocumentedClass",
        "documented_method",
    }, documented
    undocumented = names - documented
    assert undocumented == {
        "undocumented_fn",
        "undocumented_method",
        "UndocumentedClass",
    }


def test_measurement_excludes_private_and_dunder_modules() -> None:
    """The public-module filter must reject ``__init__``/private path parts."""
    assert _is_public_module(Path("analytics/core/metrics.py"))
    assert not _is_public_module(Path("analytics/__init__.py"))
    assert not _is_public_module(Path("analytics/_internal.py"))
    assert not _is_public_module(Path("analytics/_private/thing.py"))


def test_r24_text_matches_reality() -> None:
    """R24's enforcement text must describe THIS test and not overclaim (#958).

    Pins the doc<->code reconciliation: R24 must reference
    ``test_docstring_coverage.py`` (which now exists) and must NOT still claim
    the never-true strict "all public functions have non-empty docstrings" gate.
    If someone reverts the CSV wording or renames this file without updating
    R24, this fails.
    """
    enforcement = _read_r24_enforcement()
    assert "test_docstring_coverage.py" in enforcement, (
        "GWTF R24 no longer references test_docstring_coverage.py — the rule and "
        "its wired enforcement have drifted apart again (issue #958)."
    )
    assert STALE_R24_CLAIM not in enforcement, (
        "GWTF R24 still makes the stale overclaim "
        f"{STALE_R24_CLAIM!r}. Public-API docstring coverage is a RATCHET FLOOR, "
        "not a strict 100% gate; keep the R24 enforcement text honest (#958)."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
