"""LibCST guard: no argparse in the canonical v14 CLI / engine paths (R3 / ADD-02).

GWTF R3 / ADD-02 / CST-01 mandate that argument parsing for the model's canonical
paths goes through Hydra, never ``argparse``. The enforcement is scoped to where the
policy actually bites — the same principled split that ``test_entrypoints_hydra_only.py``
documents:

    * the canonical pipeline entrypoints ``run_*_v14.py`` at the repo root,
    * the finance engine (``finance/``),
    * the analytics layer (``analytics/``),
    * the chat package (``dutchbay_v14chat/``) when present.

Thin ``scripts/`` utilities and ``examples/`` that wrap a single library call are
DELIBERATELY out of scope (argparse is permitted there by design — see the
``test_entrypoints_hydra_only.py`` module docstring; a blanket repo-wide argparse ban
was evaluated and rejected as high-blast-radius ceremony against the Unix
small-composable-tools grain).

One legacy carve-out is allowlisted: ``analytics/cli/cli_sensitivity.py`` is the
DEPRECATED argparse sensitivity CLI, frozen and superseded by
``analytics/cli/cli_sensitivity_hydra.py`` (its own docstring marks it LEGACY / R3
VIOLATION and slates removal). It is allowlisted here — not exempted silently — so the
guard PASSES today while still failing the moment a NEW argparse import lands in a
canonical path.

Run:
    pytest tests/lint/test_no_argparse_anywhere.py -v

GWTF:
    - R3 / ADD-02: argparse banned in canonical v14 paths; new CLIs must be Hydra.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Set

import libcst as cst
import pytest

# ═════════════════════════════════════════════════════════════════════════════
# Scope configuration
# ═════════════════════════════════════════════════════════════════════════════

# Repository root (tests/lint/ -> tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]

# The banned top-level module.
BANNED_MODULE = "argparse"

# Directory trees that are in scope (scanned recursively when they exist).
GUARDED_DIRS = ["finance", "analytics", "dutchbay_v14chat"]

# Individual repo-root files that are in scope (the canonical pipeline entrypoints).
GUARDED_ROOT_FILES = [
    "run_full_pipeline_v14.py",
    "run_scenario_analytics_v14.py",
]

# Legacy carve-outs: files that pre-date the rule and are explicitly frozen/deprecated.
# Stored as repo-relative POSIX paths. Documented, not silent.
ALLOWLIST: dict[str, str] = {
    "analytics/cli/cli_sensitivity.py": (
        "[LEGACY] DEPRECATED argparse sensitivity CLI (its docstring marks it R3 "
        "VIOLATION / removal planned); superseded by "
        "analytics/cli/cli_sensitivity_hydra.py. Frozen, not extended."
    ),
}


# ═════════════════════════════════════════════════════════════════════════════
# LibCST module-level import collector (mirrors
# test_no_direct_finance_pipeline_imports._ModuleLevelImportCollector)
# ═════════════════════════════════════════════════════════════════════════════


class _ModuleLevelImportCollector(cst.CSTVisitor):
    """Collect imported module names from MODULE-LEVEL statements only.

    Both ``import a.b.c`` and ``from a.b import name`` forms are captured. Imports
    nested inside functions/methods are ignored: we never descend into
    ``FunctionDef`` bodies, so only top-level (and class-body) imports are recorded.
    """

    def __init__(self) -> None:
        self.imported_modules: List[str] = []

    # Do not descend into function/method bodies: keep scope to module level.
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        return False

    @staticmethod
    def _dotted_name(node: cst.BaseExpression) -> str:
        """Flatten a Name/Attribute node into a dotted module string."""
        parts: List[str] = []
        current: cst.BaseExpression | None = node
        while current is not None:
            if isinstance(current, cst.Name):
                parts.insert(0, current.value)
                break
            if isinstance(current, cst.Attribute):
                parts.insert(0, current.attr.value)
                current = current.value
            else:
                break
        return ".".join(parts)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = self._dotted_name(alias.name)
            if name:
                self.imported_modules.append(name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        # Skip relative imports (from . import x) — node.module is None there.
        if node.module is None:
            return
        name = self._dotted_name(node.module)
        if name:
            self.imported_modules.append(name)


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════


def _rel_posix(path: Path) -> str:
    """Repo-relative POSIX path for use as an allowlist key / message."""
    return path.relative_to(REPO_ROOT).as_posix()


def _guarded_py_files() -> List[Path]:
    """All in-scope Python files (guarded dirs + canonical root entrypoints)."""
    files: List[Path] = []
    for name in GUARDED_ROOT_FILES:
        path = REPO_ROOT / name
        if path.exists():
            files.append(path)
    for dirname in GUARDED_DIRS:
        base = REPO_ROOT / dirname
        if not base.exists():
            continue
        files.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(set(files))


def _imports_argparse(path: Path) -> bool:
    """True if ``path`` imports ``argparse`` at module level."""
    source = path.read_text(encoding="utf-8")
    try:
        module = cst.parse_module(source)
    except Exception as exc:  # pragma: no cover - parse failure is a hard error
        pytest.fail(f"LibCST failed to parse {_rel_posix(path)}: {exc}")
    collector = _ModuleLevelImportCollector()
    module.visit(collector)
    return any(
        m == BANNED_MODULE or m.startswith(BANNED_MODULE + ".")
        for m in collector.imported_modules
    )


def _scan_argparse_users() -> Set[str]:
    """Repo-relative paths (in scope) that import argparse at module level."""
    return {_rel_posix(p) for p in _guarded_py_files() if _imports_argparse(p)}


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


def test_no_unlisted_argparse_in_canonical_paths() -> None:
    """No canonical v14 path imports argparse unless legacy-allowlisted (R3/ADD-02).

    PASSES today: the sole argparse user in scope is the DEPRECATED
    ``analytics/cli/cli_sensitivity.py``, which is on ALLOWLIST. FAILS the moment a
    NEW ``import argparse`` lands in ``run_*_v14.py`` / ``finance/`` / ``analytics/`` /
    ``dutchbay_v14chat/``.
    """
    unlisted = sorted(_scan_argparse_users() - set(ALLOWLIST))
    assert not unlisted, (
        "GWTF R3 / ADD-02 violation: argparse imported in canonical v14 path(s). "
        "Use Hydra (@hydra.main + conf/*.yaml overrides) instead:\n"
        + "\n".join(f"  {rel}" for rel in unlisted)
    )


def test_argparse_allowlist_has_no_stale_entries() -> None:
    """Every ALLOWLIST entry must still exist AND still import argparse.

    Keeps the carve-out honest: once ``cli_sensitivity.py`` is removed (or migrated to
    Hydra), its allowlist entry must go too, or this test fails.
    """
    users = _scan_argparse_users()
    stale: List[str] = []
    for rel in sorted(ALLOWLIST):
        path = REPO_ROOT / rel
        if not path.exists():
            stale.append(f"{rel} (file no longer exists)")
        elif rel not in users:
            stale.append(f"{rel} (no longer imports argparse)")
    assert not stale, (
        "Stale argparse ALLOWLIST entries (remove them — the debt is paid off):\n"
        + "\n".join(f"  {s}" for s in stale)
    )


def test_argparse_collector_semantics() -> None:
    """Unit-level checks on the collector (no filesystem I/O)."""
    src = "import argparse\nimport os\nfrom pathlib import Path\n"
    collector = _ModuleLevelImportCollector()
    cst.parse_module(src).visit(collector)
    assert "argparse" in collector.imported_modules
    assert "os" in collector.imported_modules
    assert "pathlib" in collector.imported_modules

    # A function-scoped argparse import is intentionally NOT collected.
    nested = "def main():\n    import argparse\n    return argparse\n"
    collector2 = _ModuleLevelImportCollector()
    cst.parse_module(nested).visit(collector2)
    assert "argparse" not in collector2.imported_modules


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
