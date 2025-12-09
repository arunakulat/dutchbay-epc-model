#!/usr/bin/env python3
"""
tests/conftest.py

Shared pytest configuration and utilities for DutchBay v14 test suite.

Go-with-the-Flow Compliance:
- CST-01: LibCST Banned APIs enforcement (shared visitor base)
- CST-02: Safe code inspection without touching runtime
- Automated integration with pytest tests/ directory

This module provides:
1. PATH SETUP - Ensures repository root is on sys.path (CRITICAL for imports)
2. BaseSensitivityVisitor - Shared LibCST visitor for import/call inspection
3. load_sensitivity_source() - Unified file loading from multiple locations
4. Shared fixtures and configuration for all test suites
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import List, Set

import libcst as cst
import pytest

# =============================================================================
# PATH SETUP (CRITICAL - Must be first)
# =============================================================================
# Resolve repository root (one level above tests/)
REPO_ROOT = Path(__file__).resolve().parents[1]
root_str = str(REPO_ROOT)

# 1) Make sure repo root is FIRST on sys.path
if not sys.path or sys.path[0] != root_str:
    # Remove any existing occurrences and re-insert at front
    sys.path = [p for p in sys.path if p != root_str]
    sys.path.insert(0, root_str)

# 2) Force `analytics` to be the repo package, not tests/analytics
if "analytics" in sys.modules:
    del sys.modules["analytics"]

analytics = importlib.import_module("analytics")

# Optional: Uncomment for debugging path resolution
# print("Pytest using analytics from:", analytics.__file__)
# print("Pytest sys.path[0]:", sys.path[0])


# =============================================================================
# Shared LibCST Visitor Base Class
# =============================================================================


class BaseSensitivityVisitor(cst.CSTVisitor):
    """
    Base visitor for sensitivity_v14.py structural analysis via LibCST.

    Provides unified utilities for:
    - Safe module name extraction from CST nodes
    - Import tracking
    - Function call inspection
    - Error-safe visiting patterns

    Subclasses should override policy enforcement in visit_ImportFrom()
    and visit_Call() while inheriting utility methods.
    """

    def __init__(self) -> None:
        """Initialize visitor tracking collections."""
        self.forbidden_imports: List[str] = []
        self.direct_pipeline_calls: List[str] = []
        self.seen_imports: Set[str] = set()

    def _get_module_name(self, node: cst.Attribute | cst.Name) -> str:
        """Extract full module name from cst.Attribute or cst.Name node.

        Safely handles both:
        - Simple names: cst.Name (e.g., '__future__', 'os')
        - Dotted paths: cst.Attribute (e.g., 'analytics.evaluation_v14')

        Parameters
        ----------
        node : cst.Attribute | cst.Name
            The module node from an ImportFrom statement.

        Returns
        -------
        str
            Full module name (e.g., 'analytics.evaluation_v14') or empty string
            if extraction fails.
        """
        parts: List[str] = []
        current: cst.BaseExpression | None = node

        while current is not None:
            if isinstance(current, cst.Name):
                parts.insert(0, current.value)
                break
            elif isinstance(current, cst.Attribute):
                parts.insert(0, current.attr.value)
                current = current.value
            else:
                break

        return ".".join(parts) if parts else ""

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Base implementation: just track imports seen.

        Subclasses override to enforce specific policies.

        Parameters
        ----------
        node : cst.ImportFrom
            The ImportFrom node from the CST.
        """
        if node.module is None:
            return

        module_name = self._get_module_name(node.module)
        self.seen_imports.add(module_name)

    def visit_Call(self, node: cst.Call) -> None:
        """Base implementation: track function calls.

        Subclasses override to enforce specific policies.

        Parameters
        ----------
        node : cst.Call
            The Call node from the CST.
        """
        # Base implementation does nothing; subclasses override as needed


# =============================================================================
# Shared File Loading Utilities
# =============================================================================


def load_sensitivity_source() -> str:
    """Load sensitivity_v14.py source code from standard locations.

    Searches for the file in the following order:
    1. Current working directory: analytics/sensitivity_v14.py
    2. Parent directory: ../analytics/sensitivity_v14.py
    3. Finance directory: finance/sensitivity_v14.py

    Returns
    -------
    str
        Source code of sensitivity_v14.py.

    Raises
    ------
    pytest.skip
        If file not found in any standard location.
    """
    repo_root = Path.cwd()

    # Try direct path first
    sensitivity_path = repo_root / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    # Try parent directory
    sensitivity_path = repo_root.parent / "analytics" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    # Try finance directory (alternate location)
    sensitivity_path = repo_root / "finance" / "sensitivity_v14.py"
    if sensitivity_path.exists():
        return sensitivity_path.read_text(encoding="utf-8")

    pytest.skip(
        "sensitivity_v14.py not found in expected locations "
        "(tried analytics/, finance/, and parent/analytics/)"
    )


def load_sensitivity_module() -> cst.Module:
    """Parse sensitivity_v14.py and return LibCST Module object.

    Returns
    -------
    cst.Module
        Parsed CST module.

    Raises
    ------
    pytest.fail
        If file cannot be parsed.
    """
    source = load_sensitivity_source()

    try:
        return cst.parse_module(source)
    except Exception as exc:
        pytest.fail(f"Failed to parse sensitivity_v14.py: {exc}")


# =============================================================================
# Shared Pytest Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def sensitivity_source() -> str:
    """Session-scoped fixture: load sensitivity_v14.py source once.

    Returns
    -------
    str
        Source code of sensitivity_v14.py.
    """
    return load_sensitivity_source()


@pytest.fixture(scope="session")
def sensitivity_module(sensitivity_source: str) -> cst.Module:
    """Session-scoped fixture: parse sensitivity_v14.py once.

    Parameters
    ----------
    sensitivity_source : str
        Source code from sensitivity_source fixture.

    Returns
    -------
    cst.Module
        Parsed CST module (reused across all tests in session).
    """
    try:
        return cst.parse_module(sensitivity_source)
    except Exception as exc:
        pytest.fail(f"Failed to parse sensitivity_v14.py: {exc}")


@pytest.fixture
def visitor(sensitivity_module: cst.Module) -> BaseSensitivityVisitor:
    """Module-scoped fixture: create and populate BaseSensitivityVisitor.

    Subclasses in specific test modules can override this fixture
    to use their custom visitor implementation.

    Parameters
    ----------
    sensitivity_module : cst.Module
        Parsed module from sensitivity_module fixture.

    Returns
    -------
    BaseSensitivityVisitor
        Visitor with import/call data populated from sensitivity_v14.py.
    """
    v = BaseSensitivityVisitor()

    try:
        sensitivity_module.visit(v)
    except AttributeError as exc:
        pytest.fail(f"LibCST visitor AttributeError (unsupported CST node): {exc}")
    except Exception as exc:
        pytest.fail(f"LibCST visitor error: {exc}")

    return v


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test categorization.

    Markers:
    - lint: Static analysis and linting tests
    - analytics_layer: Functional/integration tests
    - sensitivity: Tests related to sensitivity_v14 module
    """
    config.addinivalue_line("markers", "lint: Static analysis and linting tests")
    config.addinivalue_line(
        "markers",
        "analytics_layer: Functional/integration tests for analytics layer",
    )
    config.addinivalue_line(
        "markers", "sensitivity: Tests related to sensitivity_v14 module"
    )


# =============================================================================
# Test Collection Hooks
# =============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """Automatically apply markers based on test file location.

    Tests in:
    - tests/lint/ → lint marker
    - tests/analytics_layer/ → analytics_layer marker
    - Any test with 'sensitivity' in name → sensitivity marker
    """
    for item in items:
        # Mark by directory
        if "lint" in str(item.fspath):
            item.add_marker(pytest.mark.lint)
        if "analytics_layer" in str(item.fspath):
            item.add_marker(pytest.mark.analytics_layer)

        # Mark by name
        if "sensitivity" in item.nodeid:
            item.add_marker(pytest.mark.sensitivity)


__all__ = [
    # Path setup
    "REPO_ROOT",
    "analytics",
    # Visitors
    "BaseSensitivityVisitor",
    # Utilities
    "load_sensitivity_source",
    "load_sensitivity_module",
    # Fixtures
    "sensitivity_source",
    "sensitivity_module",
    "visitor",
]
