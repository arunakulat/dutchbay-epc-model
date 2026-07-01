"""LibCST guard: no Typer in the v14 CLI / engine paths (R4 / CST-01).

GWTF R4 / CST-01 ban ``typer`` imports in the v14-critical paths — the canonical
pipeline entrypoints ``run_*_v14.py``, the chat package ``dutchbay_v14chat/``, and
(per CST-01) the ``analytics/`` and ``finance/`` layers. New CLIs must be Hydra-based;
legacy Typer/Click tools elsewhere (e.g. ``scripts/go_with_the_flow_ci.py``) are
tolerated-but-frozen and are deliberately OUT of this guard's scope.

This is a pure regression guard: no in-scope module imports Typer today, so it PASSES.
It FAILS the moment a Typer import is reintroduced under a guarded path.

Run:
    pytest tests/lint/test_no_typer_v14.py -v

GWTF:
    - R4 / CST-01: Typer banned under run_*_v14.py, dutchbay_v14chat/, analytics/,
      finance/. New CLIs must be Hydra.
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
BANNED_MODULE = "typer"

# Directory trees in scope (scanned recursively when they exist). Per CST-01 the
# Typer ban covers analytics/ and finance/ in addition to the chat package.
GUARDED_DIRS = ["analytics", "finance", "dutchbay_v14chat"]

# Individual repo-root files in scope: the canonical run_*_v14.py entrypoints.
GUARDED_ROOT_FILES = [
    "run_full_pipeline_v14.py",
    "run_scenario_analytics_v14.py",
]


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
    """Repo-relative POSIX path for use in messages."""
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


def _imports_typer(path: Path) -> bool:
    """True if ``path`` imports ``typer`` at module level."""
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


def _scan_typer_users() -> Set[str]:
    """Repo-relative paths (in scope) that import typer at module level."""
    return {_rel_posix(p) for p in _guarded_py_files() if _imports_typer(p)}


# ═════════════════════════════════════════════════════════════════════════════
# Tests
# ═════════════════════════════════════════════════════════════════════════════


def test_no_typer_in_v14_paths() -> None:
    """No v14-critical module imports Typer (R4 / CST-01).

    PASSES today (no in-scope module imports typer). FAILS if a Typer import is
    reintroduced under run_*_v14.py / analytics/ / finance/ / dutchbay_v14chat/.
    """
    offenders = sorted(_scan_typer_users())
    assert not offenders, (
        "GWTF R4 / CST-01 violation: Typer imported in a v14-critical path. "
        "New CLIs must be Hydra-based (@hydra.main + conf/*.yaml):\n"
        + "\n".join(f"  {rel}" for rel in offenders)
    )


def test_guarded_scope_is_non_empty() -> None:
    """Sanity: the guard is actually scanning files (anti-vacuous-pass guard).

    ``run_*_v14.py`` + analytics/ + finance/ must resolve to real files so a broken
    REPO_ROOT anchor can never make this suite pass by scanning nothing.
    """
    files = _guarded_py_files()
    assert files, "Typer guard scanned zero files — REPO_ROOT anchor is wrong."
    rels = {_rel_posix(p) for p in files}
    assert "run_full_pipeline_v14.py" in rels
    assert any(r.startswith("finance/") for r in rels)
    assert any(r.startswith("analytics/") for r in rels)


def test_typer_collector_semantics() -> None:
    """Unit-level checks on the collector (no filesystem I/O)."""
    src = "import typer\nfrom typer import Option\nimport os\n"
    collector = _ModuleLevelImportCollector()
    cst.parse_module(src).visit(collector)
    assert "typer" in collector.imported_modules
    assert "os" in collector.imported_modules

    # A function-scoped typer import is intentionally NOT collected.
    nested = "def main():\n    import typer\n    return typer\n"
    collector2 = _ModuleLevelImportCollector()
    cst.parse_module(nested).visit(collector2)
    assert "typer" not in collector2.imported_modules


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
