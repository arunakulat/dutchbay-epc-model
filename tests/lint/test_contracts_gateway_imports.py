"""CCCDIR guard: analytics modules must not import PRIVATE symbols from the gateway.

The existing boundary guard (``test_no_direct_finance_pipeline_imports.py``) records
imported MODULE names, so it is structurally blind to WHICH symbols are pulled from an
otherwise-allowed module. CCCDIR (FRAMEWORK-03 / ARCH-04) requires analytics consumers to
depend on the evaluation gateway's PUBLIC surface only — importing an underscore-prefixed
(implementation-detail) name from ``analytics.evaluation_v14`` couples the consumer to
internals that can change without notice.

This guard scans every module-level import under ``analytics/`` and fails if any imports a
private (single-``_``-prefixed) name FROM ``analytics.evaluation_v14``. It passes today: the
sole prior breach — ``evaluate_scenario.py`` importing the private
``_expand_dotted_overrides`` — was fixed by promoting that helper to the public
``expand_dotted_overrides``. So it is a pure regression guard.

GWTF / CCCDIR:
    - CCCDIR: import relationships explicit; analytics depends on the gateway's public API.
    - CST-01: LibCST static inspection (no runtime import of the target).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import libcst as cst
import pytest

# Repository root (tests/lint/ -> tests/ -> repo root).
REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_DIR = REPO_ROOT / "analytics"

# The gateway module whose PRIVATE (underscore-prefixed) symbols are off-limits to
# analytics consumers. The module itself is exempt — it defines them.
GATEWAY_MODULE = "analytics.evaluation_v14"
EXEMPT_FILES = {"analytics/evaluation_v14.py"}


class _PrivateGatewayImportCollector(cst.CSTVisitor):
    """Collect module-level ``from analytics.evaluation_v14 import _name`` symbols."""

    def __init__(self) -> None:
        self.private_names: List[Tuple[str, str]] = []

    # Do not descend into function/method bodies: keep scope to module level.
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        return False

    @staticmethod
    def _dotted_name(node: cst.BaseExpression) -> str:
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

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        if node.module is None or isinstance(node.names, cst.ImportStar):
            return
        if self._dotted_name(node.module) != GATEWAY_MODULE:
            return
        for alias in node.names:
            name = alias.name.value if isinstance(alias.name, cst.Name) else ""
            # Single-underscore = private; dunder (__all__ etc.) is not an internal API.
            if name.startswith("_") and not name.startswith("__"):
                self.private_names.append((GATEWAY_MODULE, name))


def _analytics_py_files() -> List[Path]:
    return sorted(
        p for p in ANALYTICS_DIR.rglob("*.py") if "__pycache__" not in p.parts
    )


def _scan_private_gateway_imports() -> dict[str, List[str]]:
    """Map repo-relative path -> list of private evaluation_v14 symbols it imports."""
    violations: dict[str, List[str]] = {}
    for path in _analytics_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in EXEMPT_FILES:
            continue
        source = path.read_text(encoding="utf-8")
        try:
            module = cst.parse_module(source)
        except Exception as exc:  # pragma: no cover - parse failure is a hard error
            pytest.fail(f"LibCST failed to parse {rel}: {exc}")
        collector = _PrivateGatewayImportCollector()
        module.visit(collector)
        if collector.private_names:
            violations[rel] = [name for _, name in collector.private_names]
    return violations


def test_no_private_gateway_imports_in_analytics() -> None:
    """No analytics module imports a private (_-prefixed) symbol from evaluation_v14."""
    violations = _scan_private_gateway_imports()
    assert not violations, (
        "CCCDIR breach — analytics modules must import only the PUBLIC surface of "
        f"{GATEWAY_MODULE}, not underscore-prefixed internals. Promote the symbol (as "
        "was done for expand_dotted_overrides) instead of importing the private name:\n"
        + "\n".join(f"  {rel}: {names}" for rel, names in sorted(violations.items()))
    )
