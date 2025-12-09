#!/usr/bin/env python3

"""
tests/analytics_layer/test_sensitivity_v14_behavioral_imports.py

**BEHAVIORAL/INTEGRATION TESTS** for sensitivity_v14.py module structure.

Purpose: Verify functional allowances for sensitivity_v14 implementation
- Allows scenario_loader (internal helper usage)
- Requires evaluation_v14 gateway
- No direct pipeline calls

This tests the BEHAVIORAL CONTRACT of the module.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

import libcst as cst
import pytest


class SensitivityImportValidator(cst.CSTVisitor):
    """
    Validate sensitivity_v14.py imports and structure.

    Enforces:
    1. No direct imports from run_v14_pipeline (must go through evaluate_with_overrides)
    2. ALLOW analytics.scenario_loader (used by _get_base_param_value helper)
    3. ALLOW analytics.evaluation_v14 (required gateway)
    4. No direct calls to run_v14_pipeline()
    """

    def __init__(self) -> None:
        self.forbidden_imports: List[str] = []
        self.direct_pipeline_calls: List[str] = []
        self.seen_imports: set[str] = set()

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Check ImportFrom statements for banned modules."""
        if node.module is None:
            return

        # Build the full module path
        module_name = self._get_full_name(node.module)
        self.seen_imports.add(module_name)

        # ✅ ALLOW: analytics.scenario_loader (used by _get_base_param_value)
        if "scenario_loader" in module_name:
            return  # This is OK

        # ✅ ALLOW: analytics.evaluation_v14 (required gateway)
        if "evaluation_v14" in module_name:
            return  # This is OK

        # ❌ DENY: direct pipeline imports
        if "pipeline_v14" in module_name or "run_v14_pipeline" in module_name:
            names = [
                alias.name.value
                for alias in node.names
                if isinstance(alias, cst.ImportAlias)
            ]
            if "run_v14_pipeline" in names:
                self.forbidden_imports.append(
                    f"Forbidden: from {module_name} import run_v14_pipeline. "
                    f"Use analytics.evaluation_v14.evaluate_with_overrides instead."
                )

    def visit_Call(self, node: cst.Call) -> None:
        """Check for direct calls to run_v14_pipeline."""
        if isinstance(node.func, cst.Name):
            if node.func.value == "run_v14_pipeline":
                self.direct_pipeline_calls.append(
                    "Direct call to run_v14_pipeline() found. "
                    "Use evaluate_with_overrides(config, overrides) instead."
                )

    def _get_full_name(self, attr: Any) -> str:
        """Extract full module name from ImportFrom node."""
        if isinstance(attr, cst.Attribute):
            return f"{self._get_full_name(attr.value)}.{attr.attr.value}"
        elif isinstance(attr, cst.Name):
            return attr.value
        return str(attr)


def get_sensitivity_v14_path() -> Path:
    """Locate analytics/sensitivity_v14.py in the repo."""
    # Try current working directory
    repo_root = Path.cwd()
    sensitivity_path = repo_root / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path

    # Try one level up (common for pytest run from repo root)
    sensitivity_path = repo_root.parent / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path

    pytest.skip("analytics/sensitivity_v14.py not found in expected locations")


def test_sensitivity_v14_no_forbidden_imports() -> None:
    """LibCST check: sensitivity_v14.py must not import run_v14_pipeline directly."""
    path = get_sensitivity_v14_path()
    source = path.read_text(encoding="utf-8")

    try:
        module = cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Failed to parse {path}: {exc}")

    validator = SensitivityImportValidator()
    module.visit(validator)

    assert (
        not validator.forbidden_imports
    ), f"Found forbidden imports in {path}:\n" + "\n".join(
        f"  - {msg}" for msg in validator.forbidden_imports
    )


def test_sensitivity_v14_no_direct_pipeline_calls() -> None:
    """LibCST check: sensitivity_v14.py must not call run_v14_pipeline() directly."""
    path = get_sensitivity_v14_path()
    source = path.read_text(encoding="utf-8")

    try:
        module = cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Failed to parse {path}: {exc}")

    validator = SensitivityImportValidator()
    module.visit(validator)

    assert (
        not validator.direct_pipeline_calls
    ), f"Found direct pipeline calls in {path}:\n" + "\n".join(
        f"  - {msg}" for msg in validator.direct_pipeline_calls
    )


def test_sensitivity_v14_has_required_evaluate_scenario() -> None:
    """LibCST check: sensitivity_v14.py should import evaluate_with_overrides from analytics.evaluation_v14."""
    path = get_sensitivity_v14_path()
    source = path.read_text(encoding="utf-8")

    try:
        module = cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Failed to parse {path}: {exc}")

    validator = SensitivityImportValidator()
    module.visit(validator)

    # Check if analytics.evaluation_v14 is imported (required gateway)
    has_evaluation_v14 = "analytics.evaluation_v14" in validator.seen_imports

    assert has_evaluation_v14, (
        f"Missing required import from analytics.evaluation_v14 in {path}. "
        "sensitivity_v14 must use evaluate_with_overrides() as the gateway."
    )


def test_sensitivity_v14_syntax_valid() -> None:
    """LibCST check: sensitivity_v14.py must parse without syntax errors."""
    path = get_sensitivity_v14_path()
    source = path.read_text(encoding="utf-8")

    try:
        cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Syntax error in {path}: {exc}")
