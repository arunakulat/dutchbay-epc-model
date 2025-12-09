from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

import libcst as cst
import pytest

# Repo root: tests/ or tests/lint/ -> repo
REPO_ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY_PATH = REPO_ROOT / "analytics" / "sensitivity_v14.py"

# Explicitly banned import targets for analytics.sensitivity_v14.
# These reflect the Go-with-the-Flow rules: sensitivity is a coordinator,
# not an engine. It must not import finance engines, legacy stacks, or
# the top-level v14 runner script directly.
FORBIDDEN_EXACT: Set[str] = {
    "finance",
    "run_full_pipeline_v14",
    "dutchbay_v13",
    "dutchbay_v14chat",
    "legacy",
}

FORBIDDEN_PREFIXES: Set[str] = {
    "finance.",
    "dutchbay_v13.",
    "dutchbay.v13.",
    "dutchbay_v14chat.",
    "legacy.",
}


def _qualname_from_expr(expr: cst.BaseExpression) -> str:
    """
    Turn a LibCST expression used as an import module into a dotted name.

    Examples:
        Name("os") -> "os"
        Attribute(value=Name("analytics"), attr=Name("contracts_v14"))
            -> "analytics.contracts_v14"
    """
    if isinstance(expr, cst.Name):
        return expr.value

    parts: List[str] = []
    node: cst.BaseExpression = expr

    while isinstance(node, cst.Attribute):
        parts.append(node.attr.value)
        node = node.value

    if isinstance(node, cst.Name):
        parts.append(node.value)

    if not parts:
        return ""

    return ".".join(reversed(parts))


@dataclass
class ImportCollector(cst.CSTVisitor):
    """Collect all imported module names in a module."""

    imported_modules: List[str] = field(default_factory=list)

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            module_name = _qualname_from_expr(alias.name)
            if module_name:
                self.imported_modules.append(module_name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        # Skip "from . import something" that has no explicit module target.
        if node.module is None:
            return

        module_name = _qualname_from_expr(node.module)
        if module_name:
            self.imported_modules.append(module_name)


def _load_sensitivity_module() -> cst.Module:
    if not SENSITIVITY_PATH.exists():
        pytest.skip(f"sensitivity_v14 not found at {SENSITIVITY_PATH}")

    try:
        source = SENSITIVITY_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - defensive
        pytest.fail(f"Failed to read {SENSITIVITY_PATH}: {exc}")

    try:
        return cst.parse_module(source)
    except cst.ParserSyntaxError as exc:  # pragma: no cover - defensive
        pytest.fail(f"Failed to parse {SENSITIVITY_PATH}: {exc}")


def _find_forbidden_imports(collected: List[str]) -> List[str]:
    violations: List[str] = []
    for raw in collected:
        if not raw:
            continue

        # Normalise away leading dots from any relative imports, just in case.
        module = raw.lstrip(".")

        if module in FORBIDDEN_EXACT:
            violations.append(module)
            continue

        for prefix in FORBIDDEN_PREFIXES:
            if module == prefix.rstrip(".") or module.startswith(prefix):
                violations.append(module)
                break

    # De-duplicate but keep deterministic ordering.
    seen: Set[str] = set()
    unique: List[str] = []
    for v in violations:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def test_sensitivity_v14_import_fence() -> None:
    """
    LibCST guardrail: analytics.sensitivity_v14 must not import
    finance engines, legacy stacks, or the top-level CLI runner.

    Sensitivity is a coordinator layer only:
      - Talks to v14 pipeline/evaluation/contract surfaces.
      - Must not reach into finance.cashflow_v14, finance.debt_v14, etc.
      - Must not import run_full_pipeline_v14 or any legacy v13/v14chat modules.
    """
    module = _load_sensitivity_module()
    visitor = ImportCollector()
    module.visit(visitor)

    violations = _find_forbidden_imports(visitor.imported_modules)

    if violations:
        msg_lines = [
            "analytics.sensitivity_v14 has forbidden imports.",
            "This module must not depend directly on finance engines,",
            "legacy stacks, or the top-level v14 runner.",
            "",
            "Forbidden modules found:",
            *violations,
        ]
        pytest.fail("\n".join(msg_lines))
