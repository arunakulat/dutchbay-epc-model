from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import libcst as cst
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#!/usr/bin/env python3
"""
LibCST guardrail: ban argparse anywhere in the repo.

Rationale:
- All new CLIs (especially v14) must use Hydra.
- argparse is considered deprecated for this codebase.

If you really, really need argparse for some legacy helper, put it in a
separate repo. This one is Hydra-only.
"""


# Directories we never want to scan
EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".mypy_cache",
    "__pycache__",
}
EXCLUDED_PREFIXES = {".venv", "venv", ".env"}


def _iter_target_files() -> List[Path]:
    """Yield all Python files under the repo, excluding venvs / caches."""
    files: List[Path] = []
    for path in REPO_ROOT.rglob("*.py"):
        parts = set(path.parts)
        # Skip known junk / env dirs
        if parts & EXCLUDED_DIRS:
            continue
        if any(part.startswith(tuple(EXCLUDED_PREFIXES)) for part in path.parts):
            continue
        files.append(path)
    return files


class ArgparseImportVisitor(cst.CSTVisitor):
    """Collect any imports of argparse."""

    def __init__(self) -> None:
        self.violations: List[Tuple[str, str]] = []

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            name = alias.name.value
            if name == "argparse":
                self.violations.append(("import", name))

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        module = node.module.value if node.module is not None else ""
        if module == "argparse":
            self.violations.append(("from", module))


def test_no_argparse_anywhere() -> None:
    """Ensure argparse is not imported anywhere in the repo."""
    target_files = _iter_target_files()
    if not target_files:
        pytest.skip("No Python files found to scan for argparse usage.")

    violations: List[str] = []

    for path in target_files:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            pytest.fail(f"Failed to read {path}: {exc}")

        module = cst.parse_module(source)
        visitor = ArgparseImportVisitor()
        module.visit(visitor)

        for kind, name in visitor.violations:
            violations.append(f"{path}: {kind} {name}")

    if violations:
        msg_lines = [
            "argparse is banned in this repo (Hydra-only CLIs).",
            "Found the following illegal imports:",
            *violations,
        ]
        pytest.fail("\n".join(msg_lines))
