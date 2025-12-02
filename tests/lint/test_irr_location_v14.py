from __future__ import annotations

from pathlib import Path
from typing import List

import libcst as cst
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
IRR_MODULE = REPO_ROOT / "finance" / "irr.py"

#!/usr/bin/env python3
"""
LibCST guardrail: IRR/NPV functions must be defined only in finance/irr.py.

Rationale:
- Keep IRR/NPV logic centralized for auditability and contracts.
- Other modules may *import* from finance.irr but must not define their own
  irr/xirr/npv functions.
"""


def _iter_python_files() -> List[Path]:
    files: List[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        parts = set(path.parts)
        if ".git" in parts or ".tox" in parts or "__pycache__" in parts:
            continue
        if any(part.startswith(".venv") for part in path.parts):
            continue
        files.append(path)
    return files


class IrrLocationVisitor(cst.CSTVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.bad_defs: List[str] = []
        self.bad_imports: List[str] = []

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        if node.name.value in {"irr", "xirr", "npv"}:
            if self.path.resolve() != IRR_MODULE.resolve():
                self.bad_defs.append(node.name.value)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        # Build full module path from CST node
        if node.module is None:
            return

        # Get the full dotted module name
        module_parts = []
        current = node.module
        while current is not None:
            if isinstance(current, cst.Name):
                module_parts.insert(0, current.value)
                break
            elif isinstance(current, cst.Attribute):
                module_parts.insert(0, current.attr.value)
                current = current.value
            else:
                break

        module = ".".join(module_parts)

        names = {
            alias.name.value
            for alias in node.names
            if isinstance(alias, cst.ImportAlias)
        }
        bad_names = names & {"irr", "xirr", "npv"}
        if bad_names and module != "finance.irr":
            self.bad_imports.append(
                f"from {module} import {', '.join(sorted(bad_names))}"
            )


def test_irr_npz_only_in_finance_irr() -> None:
    """Enforce that irr/xirr/npv are only defined in finance/irr.py."""
    py_files = _iter_python_files()
    if not py_files:
        pytest.skip("No Python files found to scan for IRR/NPV definitions.")

    bad_messages: List[str] = []

    for path in py_files:
        source = path.read_text(encoding="utf-8")
        module = cst.parse_module(source)
        visitor = IrrLocationVisitor(path)
        module.visit(visitor)

        for name in visitor.bad_defs:
            bad_messages.append(
                f"{path}: illegal definition of '{name}' (must live only in finance/irr.py)"
            )

        for desc in visitor.bad_imports:
            bad_messages.append(
                f"{path}: illegal import – {desc} (must import from finance.irr instead)"
            )

    if bad_messages:
        msg = "IRR/NPV location violations detected:\n" + "\n".join(bad_messages)
        pytest.fail(msg)
