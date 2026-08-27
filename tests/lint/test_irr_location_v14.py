"""LibCST guard: irr / xirr / npv are defined ONLY in finance/irr.py (R7 / CST-01).

GWTF R7 / CST-01 confine the IRR/NPV *definitions* to the single source of truth,
``finance/irr.py``. Every other module must import ``irr`` / ``xirr`` / ``npv`` from
``finance.irr`` and must not redefine them. Divergent local IRR/NPV solvers are exactly
how KPI-sensitive numerics (project/equity IRR, NPV, LLCR/PLCR) drift out of sync.

Matching rule
-------------
A module-level ``def`` is a violation if its name, with leading underscores stripped
and lower-cased, is EXACTLY one of ``{irr, xirr, npv}``. Stripping leading underscores
catches a private redefinition (``_npv``) while deliberately NOT catching adjacent
helpers whose stem is longer — ``_npv_wrapper`` / ``_irr_wrapper`` (thin pass-throughs
that delegate to ``finance.irr``) and ``npv_derivative`` / ``npv_gap`` are not bare
irr/xirr/npv redefinitions and are out of scope.

Allowlist
---------
``finance/debt_v14.py::_npv`` is a LOCAL discount-factor sum (``Σ cf / (1+r)**t``) used
for the LLCR/PLCR coverage ratios — it contains NO root-finding / IRR logic (its own
docstring: "no IRR logic here - IRR stays in finance.irr"). It is KPI-sensitive and must
NOT be refactored, so it is allowlisted here (not exempted silently). Without this entry
the guard would flag ``_npv`` — the entry is therefore genuinely load-bearing, and the
staleness test below proves it.

This is a pure regression guard: with the one allowlist entry it PASSES today. It FAILS
the moment a new ``irr`` / ``xirr`` / ``npv`` (or ``_irr`` / ``_npv`` …) is defined
outside ``finance/irr.py``.

Run:
    pytest tests/lint/test_irr_location_v14.py -v

GWTF:
    - R7 / CST-01: irr/xirr/npv definitions live only in finance/irr.py.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set, Tuple

import libcst as cst
import pytest

# ═════════════════════════════════════════════════════════════════════════════
# Scope configuration
# ═════════════════════════════════════════════════════════════════════════════

# Repository root (tests/lint/ -> tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]

# The one sanctioned home for irr/xirr/npv definitions.
IRR_HOME = "finance/irr.py"

# Bare function names (post-normalisation) that may only be defined in IRR_HOME.
BANNED_NAMES = {"irr", "xirr", "npv"}

# Directory names skipped entirely: caches, VCS, the quarantined legacy tree, and
# packaging artifacts. Legacy code is isolated by policy and not part of the live model.
# ".claude" covers agent worktrees: a Claude Code subagent running with worktree
# isolation leaves a full nested checkout under .claude/worktrees/, whose copy of
# finance/irr.py would otherwise be reported here as an out-of-home R7 violation.
SKIP_DIR_NAMES = {
    ".claude",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "legacy",
    "node_modules",
    "build",
    "dist",
}

# Allowlist: repo-relative POSIX path -> set of local def names that are permitted
# despite normalising to a banned stem. Each MUST be a non-IRR helper.
ALLOWLIST: dict[str, Set[str]] = {
    # Local discount-factor sum for LLCR/PLCR — NOT an IRR solver, KPI-sensitive,
    # do not refactor. (finance/debt_v14.py _npv docstring: "no IRR logic here".)
    "finance/debt_v14.py": {"_npv"},
}


# ═════════════════════════════════════════════════════════════════════════════
# LibCST module-level def collector (mirrors the visitor pattern in
# test_no_direct_finance_pipeline_imports; here it records def names, not imports)
# ═════════════════════════════════════════════════════════════════════════════


class _ModuleLevelDefCollector(cst.CSTVisitor):
    """Collect MODULE-LEVEL (and class-body) function-definition names only.

    We record the def name and then return ``False`` from ``visit_FunctionDef`` so we
    never descend into nested bodies — a helper defined *inside* a function (e.g.
    ``npv_derivative`` inside a solver) is an implementation detail, not a public
    redefinition, and is intentionally not collected.
    """

    def __init__(self) -> None:
        self.def_names: List[str] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.def_names.append(node.name.value)
        return False  # do not descend into the body


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


def _normalise(name: str) -> str:
    """Leading underscores stripped, lower-cased. ``_NPV`` -> ``npv``."""
    return name.lstrip("_").lower()


def _rel_posix(path: Path) -> str:
    """Repo-relative POSIX path for use as an allowlist key / message."""
    return path.relative_to(REPO_ROOT).as_posix()


def _iter_py_files() -> List[Path]:
    """All repo Python files, skipping caches / legacy / packaging trees."""
    files: List[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        parts = set(path.relative_to(REPO_ROOT).parts)
        if parts & SKIP_DIR_NAMES:
            continue
        if any(p.endswith(".egg-info") for p in path.relative_to(REPO_ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def _banned_defs_in(path: Path) -> List[str]:
    """Module-level def names in ``path`` whose stem is a banned irr/xirr/npv name."""
    source = path.read_text(encoding="utf-8")
    try:
        module = cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - parse failure is a hard error
        pytest.fail(f"LibCST failed to parse {_rel_posix(path)}: {exc}")
    collector = _ModuleLevelDefCollector()
    module.visit(collector)
    return [n for n in collector.def_names if _normalise(n) in BANNED_NAMES]


def _scan_violations() -> dict[str, List[str]]:
    """Map repo-relative path -> banned irr/xirr/npv def names (outside IRR_HOME)."""
    violations: dict[str, List[str]] = {}
    for path in _iter_py_files():
        rel = _rel_posix(path)
        if rel == IRR_HOME:
            continue
        banned = _banned_defs_in(path)
        if banned:
            violations[rel] = banned
    return violations


_VIOLATIONS: dict[str, List[str]] = _scan_violations()


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


def test_no_unlisted_irr_npv_definitions_outside_finance_irr() -> None:
    """irr/xirr/npv may only be defined in finance/irr.py (R7), except allowlisted.

    PASSES today: the sole out-of-home definition is ``finance/debt_v14.py::_npv``
    (a discount-factor helper, allowlisted). FAILS the moment a new irr/xirr/npv (or
    ``_irr``/``_npv`` …) is defined outside finance/irr.py without an allowlist entry.
    """
    unlisted: List[Tuple[str, List[str]]] = []
    for rel, names in sorted(_VIOLATIONS.items()):
        allowed = ALLOWLIST.get(rel, set())
        remaining = [n for n in names if n not in allowed]
        if remaining:
            unlisted.append((rel, remaining))

    assert not unlisted, (
        "GWTF R7 violation: irr/xirr/npv defined outside finance/irr.py.\n"
        "Import from finance.irr instead of redefining. If this is a genuine "
        "non-IRR helper (e.g. a discount-factor sum), add it to ALLOWLIST here with a "
        "rationale:\n"
        + "\n".join(f"  {rel}: {', '.join(names)}" for rel, names in unlisted)
    )


def test_irr_allowlist_has_no_stale_entries() -> None:
    """Every ALLOWLIST entry must still exist AND still define the named helper.

    Keeps the allowlist honest: if ``finance/debt_v14.py::_npv`` is renamed or removed,
    its entry must go too, or this test fails.
    """
    stale: List[str] = []
    for rel, names in sorted(ALLOWLIST.items()):
        path = REPO_ROOT / rel
        if not path.exists():
            stale.append(f"{rel} (file no longer exists)")
            continue
        present = set(_VIOLATIONS.get(rel, []))
        for name in sorted(names):
            if name not in present:
                stale.append(f"{rel}::{name} (no longer defined / no longer matches)")
    assert (
        not stale
    ), "Stale irr/xirr/npv ALLOWLIST entries (remove them):\n" + "\n".join(
        f"  {s}" for s in stale
    )


def test_finance_irr_defines_the_canonical_trio() -> None:
    """Sanity: finance/irr.py actually defines irr, xirr and npv (single source)."""
    home = REPO_ROOT / IRR_HOME
    assert home.exists(), f"{IRR_HOME} missing — IRR single source of truth is gone."
    collector = _ModuleLevelDefCollector()
    cst.parse_module(home.read_text(encoding="utf-8")).visit(collector)
    defined = {_normalise(n) for n in collector.def_names}
    assert BANNED_NAMES <= defined, (
        f"{IRR_HOME} must define all of {sorted(BANNED_NAMES)}; "
        f"found {sorted(defined & BANNED_NAMES)}."
    )


def test_normalise_and_matcher_semantics() -> None:
    """Unit-level checks on the name normaliser (no filesystem I/O)."""
    # Bare and private irr/xirr/npv normalise into the banned set.
    assert _normalise("npv") == "npv"
    assert _normalise("_npv") == "npv"
    assert _normalise("_IRR") == "irr"
    assert _normalise("xirr") in BANNED_NAMES
    # Longer-stem helpers do NOT collapse onto a banned name.
    assert _normalise("_npv_wrapper") not in BANNED_NAMES
    assert _normalise("_irr_wrapper") not in BANNED_NAMES
    assert _normalise("npv_derivative") not in BANNED_NAMES
    assert _normalise("npv_gap") not in BANNED_NAMES
    assert _normalise("calculate_npv") not in BANNED_NAMES


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
