"""LibCST guard: ``finance.debt_v14`` stays the debt engine's only import surface.

The debt engine's code lives in the ``finance.debt`` package, moved there verbatim from
``finance/debt_v14.py`` by ``scripts/refactor/split_debt_v14.py``. The façade
re-exports every name the module defined before the move, so every consumer keeps one
documented entry point (CCCDIR, FRAMEWORK-03) and the package layout stays free to
change behind it.

Boundary rules
--------------
1. No production module may import ``finance.debt`` or any ``finance.debt.*`` submodule,
   at any scope, by an absolute or a relative path (``from .debt.plan import ...`` inside
   ``finance/`` is the same import). Only the package itself and the façade may.
2. Nothing, tests included, may assign, ``setattr`` or patch an attribute of the façade.
   The engine's functions read their globals from their own modules, so a value written
   onto ``finance.debt_v14`` changes nothing the engine does: the write is silently dead.
   Patch the owning ``finance.debt.<module>`` instead.

Tests are exempt from rule 1. They may import a submodule to reach state that a function
rebinds with ``global`` (``_warned_decorative_tranches`` in ``finance.debt.terms``) or to
scan every module of the engine. Imports built at run time (``importlib``,
``__import__``) are outside what a static lint can see.

Run:
    pytest tests/lint/test_debt_package_boundary.py -v

GWTF:
    - FRAMEWORK-03 (CCCDIR): one documented import relationship for the debt engine.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

import libcst as cst

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "finance.debt"
FACADE = "finance.debt_v14"

# Repo-relative POSIX paths allowed to import the package: the façade and the package.
ALLOWED_FILES = {"finance/debt_v14.py"}
ALLOWED_PREFIXES = ("finance/debt/",)
TEST_PREFIX = "tests/"

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

# Calls whose first argument is a target object or a dotted target string.
_PATCH_CALLS = {"setattr", "patch", "patch.object", "mock.patch", "mock.patch.object"}


def _dotted(node: Optional[cst.BaseExpression]) -> str:
    """Return the dotted name of an import target or attribute chain, or ''."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr.value}" if head else ""
    return ""


def _in_package(name: str) -> bool:
    return name == PACKAGE or name.startswith(PACKAGE + ".")


def _package_of(rel: str) -> List[str]:
    """The dotted package a repo-relative module path belongs to, as parts."""
    return rel.split("/")[:-1]


class _BoundaryCollector(cst.CSTVisitor):
    """Collect package imports (rule 1) and writes to the façade (rule 2)."""

    def __init__(self, package_parts: Sequence[str]) -> None:
        self.package_parts = list(package_parts)
        self.imports: List[str] = []
        self.facade_writes: List[str] = []
        # Local names bound to the façade module, e.g. ``debt_v14`` or ``finance.debt_v14``.
        self.facade_aliases: Set[str] = set()

    # -- imports ----------------------------------------------------------------------
    def _absolute(self, node: cst.ImportFrom) -> str:
        module = _dotted(node.module)
        level = len(node.relative)
        if not level:
            return module
        base = self.package_parts[: len(self.package_parts) - (level - 1)]
        return ".".join([*base, module] if module else base)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = _dotted(alias.name)
            if _in_package(name):
                self.imports.append(f"import {name}")
            if name == FACADE:
                asname = alias.asname
                if asname is not None and isinstance(asname.name, cst.Name):
                    self.facade_aliases.add(asname.name.value)
                else:
                    self.facade_aliases.add(FACADE)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = self._absolute(node)
        if _in_package(module):
            self.imports.append(f"from {module} import ...")
            return
        if isinstance(node.names, cst.ImportStar):
            return
        for alias in node.names:
            full = f"{module}.{_dotted(alias.name)}" if module else _dotted(alias.name)
            if _in_package(full):
                self.imports.append(
                    f"from {module or '.'} import {_dotted(alias.name)}"
                )
            if full == FACADE:
                asname = alias.asname
                if asname is not None and isinstance(asname.name, cst.Name):
                    self.facade_aliases.add(asname.name.value)
                else:
                    self.facade_aliases.add(_dotted(alias.name))

    # -- writes to the façade ---------------------------------------------------------
    def _is_facade(self, node: cst.BaseExpression) -> bool:
        return _dotted(node) in self.facade_aliases

    def _check_target(self, target: cst.BaseExpression) -> None:
        if isinstance(target, cst.Attribute) and self._is_facade(target.value):
            self.facade_writes.append(f"{_dotted(target)} = ...")
        elif isinstance(target, (cst.Tuple, cst.List)):
            for element in target.elements:
                self._check_target(element.value)

    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            self._check_target(target.target)

    def visit_AugAssign(self, node: cst.AugAssign) -> None:
        self._check_target(node.target)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> None:
        self._check_target(node.target)

    def visit_Call(self, node: cst.Call) -> None:
        func = _dotted(node.func)
        if not node.args or not (
            func in _PATCH_CALLS or func.split(".")[-1] in {"setattr", "patch"}
        ):
            return
        first = node.args[0].value
        if self._is_facade(first):
            self.facade_writes.append(f"{func}({_dotted(first)}, ...)")
        elif isinstance(first, cst.SimpleString):
            text = first.evaluated_value
            if isinstance(text, str) and text.startswith(FACADE + "."):
                self.facade_writes.append(f"{func}({text!r}, ...)")


def _collect(source: str, rel: str) -> _BoundaryCollector:
    collector = _BoundaryCollector(_package_of(rel))
    cst.parse_module(source).visit(collector)
    return collector


def _scan() -> Tuple[int, List[Tuple[str, List[str]]], List[Tuple[str, List[str]]]]:
    scanned = 0
    imports: List[Tuple[str, List[str]]] = []
    writes: List[Tuple[str, List[str]]] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts[:-1]):
            continue
        rel = "/".join(rel_parts)
        if rel in ALLOWED_FILES or rel.startswith(ALLOWED_PREFIXES):
            continue
        try:
            collector = _collect(path.read_text(encoding="utf-8"), rel)
        except (UnicodeDecodeError, cst.ParserSyntaxError):
            continue
        scanned += 1
        if collector.imports and not rel.startswith(TEST_PREFIX):
            imports.append((rel, collector.imports))
        if collector.facade_writes:
            writes.append((rel, collector.facade_writes))
    return scanned, imports, writes


def test_collector_flags_every_import_form() -> None:
    """Negative control: each spelling that reaches the package is caught."""
    source = (
        "import finance.debt.plan\n"
        "from finance.debt.terms import _extract_financing_terms\n"
        "from finance.debt import plan\n"
        "from finance import debt\n"
        "def f():\n"
        "    from finance.debt.layer import apply_debt_layer\n"
        "from .debt.plan import plan_debt\n"
        "from . import debt\n"
        "from .debt import sizing\n"
        "from finance.debt_v14 import plan_debt\n"
        "import finance.debt_v14\n"
        "from .debt_v14 import plan_debt\n"
        "from . import debt_v14\n"
    )
    assert _collect(source, "finance/cashflow_v14.py").imports == [
        "import finance.debt.plan",
        "from finance.debt.terms import ...",
        "from finance.debt import ...",
        "from finance import debt",
        "from finance.debt.layer import ...",
        "from finance.debt.plan import ...",
        "from finance import debt",
        "from finance.debt import ...",
    ]
    # A module one package deeper reaches the engine two levels up.
    nested = "from ..debt import balloon\nfrom ..debt_v14 import plan_debt\n"
    assert _collect(nested, "finance/reporting/view.py").imports == [
        "from finance.debt import ..."
    ]


def test_collector_flags_every_write_to_the_facade() -> None:
    """Negative control: assignments, setattr and patches on the façade are caught."""
    source = (
        "import finance.debt_v14 as dv\n"
        "from finance import debt_v14\n"
        "import finance.debt_v14\n"
        "import unittest.mock as mock\n"
        "dv._warned_decorative_tranches = False\n"
        "debt_v14._BALLOON_TOL += 1\n"
        "finance.debt_v14.logger: object = None\n"
        "def t(monkeypatch):\n"
        "    monkeypatch.setattr(dv, '_npv', None)\n"
        "    monkeypatch.setattr('finance.debt_v14._pmt', None)\n"
        "    setattr(debt_v14, 'x', 1)\n"
        "    mock.patch.object(dv, 'plan_debt')\n"
        "    mock.patch('finance.debt_v14.apply_debt_layer')\n"
        "import finance.debt.terms as terms\n"
        "terms._warned_decorative_tranches = False\n"
        "monkeypatch.setattr(terms, '_warned_decorative_tranches', False)\n"
    )
    assert _collect(source, "tests/finance/test_x.py").facade_writes == [
        "dv._warned_decorative_tranches = ...",
        "debt_v14._BALLOON_TOL = ...",
        "finance.debt_v14.logger = ...",
        "monkeypatch.setattr(dv, ...)",
        "monkeypatch.setattr('finance.debt_v14._pmt', ...)",
        "setattr(debt_v14, ...)",
        "mock.patch.object(dv, ...)",
        "mock.patch('finance.debt_v14.apply_debt_layer', ...)",
    ]


def test_production_code_imports_the_debt_engine_only_through_the_facade() -> None:
    """Every module outside the package, the façade and tests uses ``finance.debt_v14``."""
    scanned, imports, _ = _scan()
    # The scan must have read the production tree, not an empty or mis-rooted one.
    assert scanned > 200, f"scanned only {scanned} modules; is REPO_ROOT right?"
    assert not imports, (
        "Import the debt engine from finance.debt_v14, not from the finance.debt "
        "package behind it:\n"
        + "\n".join(f"  {rel}: {', '.join(hits)}" for rel, hits in imports)
    )


def test_nothing_writes_to_the_facade() -> None:
    """A write to ``finance.debt_v14`` is dead: the engine reads its own modules."""
    scanned, _, writes = _scan()
    assert scanned > 200, f"scanned only {scanned} modules; is REPO_ROOT right?"
    assert not writes, (
        "These write to the finance.debt_v14 façade, which the engine never reads; "
        "write to the owning finance.debt.<module> instead:\n"
        + "\n".join(f"  {rel}: {', '.join(hits)}" for rel, hits in writes)
    )
