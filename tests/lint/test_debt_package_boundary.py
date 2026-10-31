"""LibCST guard: ``finance.debt_v14`` stays the debt engine's only import surface.

The debt engine's code lives in the ``finance.debt`` package, moved there verbatim from
``finance/debt_v14.py`` by ``scripts/refactor/split_debt_v14.py``. The façade
re-exports every name the module defined before the move, so every consumer keeps one
documented entry point (CCCDIR, FRAMEWORK-03) and the package layout stays free to
change behind it.

Boundary rule
-------------
No production module may import ``finance.debt`` or any ``finance.debt.*`` submodule, at
any scope. Only the package itself and the façade may. Tests may import a submodule, but
only for state that a function rebinds with ``global``, which a façade copy cannot follow
(``_warned_decorative_tranches`` in ``finance.debt.terms``).

Run:
    pytest tests/lint/test_debt_package_boundary.py -v

GWTF:
    - FRAMEWORK-03 (CCCDIR): one documented import relationship for the debt engine.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import libcst as cst

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "finance.debt"

# Repo-relative POSIX paths allowed to import the package: the façade and the package.
ALLOWED_FILES = {"finance/debt_v14.py"}
ALLOWED_PREFIXES = ("finance/debt/", "tests/")

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


def _dotted(node: cst.BaseExpression | None) -> str:
    """Return the dotted name of an import target, or an empty string."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr.value}" if head else ""
    return ""


class _PackageImportCollector(cst.CSTVisitor):
    """Collect every import, at any scope, that reaches ``finance.debt``."""

    def __init__(self) -> None:
        self.hits: List[str] = []

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = _dotted(alias.name)
            if name == PACKAGE or name.startswith(PACKAGE + "."):
                self.hits.append(f"import {name}")

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if node.relative:
            return
        module = _dotted(node.module)
        if module == PACKAGE or module.startswith(PACKAGE + "."):
            self.hits.append(f"from {module} import ...")
        elif module == "finance" and not isinstance(node.names, cst.ImportStar):
            for alias in node.names:
                if _dotted(alias.name) == "debt":
                    self.hits.append("from finance import debt")


def _imports_of(source: str) -> List[str]:
    collector = _PackageImportCollector()
    cst.parse_module(source).visit(collector)
    return collector.hits


def _scan() -> Tuple[int, List[Tuple[str, List[str]]]]:
    scanned = 0
    violations: List[Tuple[str, List[str]]] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        rel = "/".join(rel_parts)
        if rel in ALLOWED_FILES or rel.startswith(ALLOWED_PREFIXES):
            continue
        try:
            hits = _imports_of(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, cst.ParserSyntaxError):
            continue
        scanned += 1
        if hits:
            violations.append((rel, hits))
    return scanned, violations


def test_collector_flags_every_import_form() -> None:
    """Negative control: each spelling that reaches the package is caught."""
    source = (
        "import finance.debt.plan\n"
        "from finance.debt.terms import _extract_financing_terms\n"
        "from finance.debt import plan\n"
        "from finance import debt\n"
        "def f():\n"
        "    from finance.debt.layer import apply_debt_layer\n"
        "from finance.debt_v14 import plan_debt\n"
        "import finance.debt_v14\n"
    )
    assert _imports_of(source) == [
        "import finance.debt.plan",
        "from finance.debt.terms import ...",
        "from finance.debt import ...",
        "from finance import debt",
        "from finance.debt.layer import ...",
    ]


def test_production_code_imports_the_debt_engine_only_through_the_facade() -> None:
    """Every module outside the package, the façade and tests uses ``finance.debt_v14``."""
    scanned, violations = _scan()
    # The scan must have read the production tree, not an empty or mis-rooted one.
    assert scanned > 200, f"scanned only {scanned} modules; is REPO_ROOT right?"
    assert not violations, (
        "Import the debt engine from finance.debt_v14, not from the finance.debt "
        "package behind it:\n"
        + "\n".join(f"  {rel}: {', '.join(hits)}" for rel, hits in violations)
    )
