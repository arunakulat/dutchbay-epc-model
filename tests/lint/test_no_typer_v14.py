from __future__ import annotations

from pathlib import Path
from typing import List

import libcst as cst
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#!/usr/bin/env python3
"""
LibCST guardrail: forbid Typer in v14 CLI land.

Rationale:
- v14 CLIs should be Hydra-based.
- Typer is fine in some other repo, but not here.
"""

CLI_SCRIPTS = [
    REPO_ROOT / "run_full_pipeline_v14.py",
    REPO_ROOT / "run_scenario_analytics_v14.py",
]

MODULE_ROOTS = [
    REPO_ROOT / "dutchbay_v14chat",
]


def _iter_target_files() -> List[Path]:
    files: List[Path] = []
    for script in CLI_SCRIPTS:
        if script.exists():
            files.append(script)
    for root in MODULE_ROOTS:
        if root.exists() and root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
    return files


class TyperImportVisitor(cst.CSTVisitor):
    def __init__(self) -> None:
        self.violations: List[str] = []

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = alias.name.value
            if name == "typer":
                self.violations.append(f"import {name}")

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = node.module.value if node.module is not None else ""
        if module == "typer":
            self.violations.append(f"from {module} import ...")


def test_no_typer_in_v14_clis() -> None:
    """Ensure Typer is not imported in v14 CLI scripts or dutchbay_v14chat/."""
    target_files = _iter_target_files()
    if not target_files:
        pytest.skip("No v14 CLI scripts or dutchbay_v14chat modules found.")

    violations: List[str] = []
    for path in target_files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            pytest.fail(f"Failed to read {path}: {exc}")
        module = cst.parse_module(source)
        visitor = TyperImportVisitor()
        module.visit(visitor)
        for v in visitor.violations:
            violations.append(f"{path}: {v}")

    if violations:
        msg_lines = [
            "Typer is banned in v14 CLIs (Hydra only).",
            "Found the following illegal imports:",
            *violations,
        ]
        pytest.fail("\n".join(msg_lines))
