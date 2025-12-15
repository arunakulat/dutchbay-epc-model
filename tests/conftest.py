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
5. TEST PERFORMANCE - Configurable iteration counts for Monte Carlo/sensitivity
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
# TEST PERFORMANCE CONFIGURATION
# =============================================================================


@pytest.fixture(scope="session")
def fast_test_mode(request) -> bool:
    """
    Session-scoped fixture: determine if tests should run in fast mode.

    Fast mode reduces Monte Carlo and sensitivity test iterations for rapid
    development feedback. Full iterations run in CI/CD or with --full-iterations.

    Returns
    -------
    bool
        True if fast mode enabled (default), False for full iterations.

    Usage
    -----
    Command line:
        pytest                        # Fast mode (default)
        pytest --fast-test-mode       # Explicit fast mode
        pytest --full-iterations      # Full iterations

    In test code:
        def test_monte_carlo(fast_test_mode):
            n_iter = 20 if fast_test_mode else 100000
            result = run_monte_carlo(n_iterations=n_iter)
    """
    # Check if --full-iterations flag is set
    return not request.config.getoption("--full-iterations", default=False)


@pytest.fixture(scope="session")
def test_iteration_config(fast_test_mode: bool) -> dict[str, int]:
    """
    Session-scoped fixture: iteration counts for different test types.

    Provides centralized configuration for test performance tuning.

    Parameters
    ----------
    fast_test_mode : bool
        Whether tests are running in fast mode.

    Returns
    -------
    dict[str, int]
        Configuration with keys:
        - monte_carlo_iterations: Number of MC simulations
        - sensitivity_parameters: Max parameters for sensitivity analysis
        - sensitivity_steps: Steps per parameter in tornado charts
        - timeout_seconds: Test timeout multiplier

    Examples
    --------
    >>> def test_monte_carlo(test_iteration_config):
    ...     n = test_iteration_config["monte_carlo_iterations"]
    ...     result = run_monte_carlo(n_iterations=n)
    """
    if fast_test_mode:
        return {
            "monte_carlo_iterations": 20,  # 500x faster (was 10,000+)
            "sensitivity_parameters": 3,  # Limit to 3 params (was 8+)
            "sensitivity_steps": 3,  # 3-point sensitivity (was 5)
            "timeout_seconds": 30,  # Short timeout for dev
            "mode": "fast",
        }
    else:
        return {
            "monte_carlo_iterations": 100000,  # Full production runs
            "sensitivity_parameters": 12,  # All parameters
            "sensitivity_steps": 5,  # Full 5-point tornado
            "timeout_seconds": 300,  # 5 min timeout
            "mode": "full",
        }


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


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add custom command-line options for test configuration.

    Options:
    --------
    --fast-test-mode
        Run tests with reduced iterations (20 MC, 3 params).
        This is the DEFAULT mode.

    --full-iterations
        Run tests with full production iterations (100k MC, all params).
        Use for pre-commit validation and CI/CD.

    Examples:
    ---------
    # Fast development mode (default)
    pytest
    pytest --fast-test-mode

    # Full validation mode
    pytest --full-iterations

    # Fast mode with verbose output
    pytest -v --fast-test-mode
    """
    parser.addoption(
        "--fast-test-mode",
        action="store_true",
        default=False,
        help="Run tests with reduced iterations for faster development (DEFAULT)",
    )
    parser.addoption(
        "--full-iterations",
        action="store_true",
        default=False,
        help="Run tests with full production iterations (100k+ MC simulations)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for test categorization.

    Markers:
    - edge_case: Edge case and boundary condition stress tests
    - stress: Stress tests, failure scenarios, and load/performance edge cases
    - critical_error: Critical error handling and recovery tests
    - integration: Integration tests spanning multiple modules
    - unit: Unit tests for individual functions and classes
    - slow: Tests taking >5 seconds (skip with -m "not slow")
    - regression: Regression tests with frozen/expected output
    - monte_carlo: Monte Carlo simulation tests
    - sensitivity: Sensitivity analysis tests
    - lint: Static analysis and linting tests
    - analytics_layer: Functional/integration tests for analytics layer
    """
    config.addinivalue_line(
        "markers",
        "edge_case: Edge case and boundary condition stress tests",
    )
    config.addinivalue_line(
        "markers",
        "stress: Stress/failure/load scenario tests",
    )
    config.addinivalue_line(
        "markers",
        "critical_error: Critical error handling and recovery tests",
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests spanning multiple modules",
    )
    config.addinivalue_line(
        "markers",
        "unit: Unit tests for individual functions and classes",
    )
    config.addinivalue_line(
        "markers",
        "slow: Tests with long runtime (>5s, use -m 'not slow' to skip)",
    )
    config.addinivalue_line(
        "markers",
        "regression: Regression tests with frozen/expected output",
    )
    config.addinivalue_line(
        "markers",
        "monte_carlo: Monte Carlo simulation tests",
    )
    config.addinivalue_line(
        "markers",
        "sensitivity: Sensitivity analysis tests",
    )
    config.addinivalue_line("markers", "lint: Static analysis and linting tests")
    config.addinivalue_line(
        "markers",
        "analytics_layer: Functional/integration tests for analytics layer",
    )

    # Print test mode banner
    if config.getoption("--full-iterations"):
        print("\n" + "=" * 78)
        print("TEST MODE: FULL ITERATIONS (100k+ MC simulations)")
        print("Expected runtime: 5-10 minutes for full suite")
        print("=" * 78 + "\n")
    else:
        print("\n" + "=" * 78)
        print("TEST MODE: FAST (20 iterations, 3 params)")
        print("Expected runtime: ~30 seconds for full suite")
        print("Use --full-iterations for production validation")
        print("=" * 78 + "\n")


# =============================================================================
# Test Collection Hooks
# =============================================================================


def pytest_collection_modifyitems(
    config: pytest.Config, items: List[pytest.Item]
) -> None:
    """
    Automatically apply markers based on test file location and characteristics.

    Tests in:
    - tests/lint/ → lint marker
    - tests/analytics_layer/ → analytics_layer marker
    - Any test with 'sensitivity' in name → sensitivity marker
    - Tests with 'monte_carlo' in name → slow marker (can be skipped)
    - Tests with 'edge_case' or 'stress' in name → edge_case/stress markers
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
        if "monte_carlo" in item.nodeid.lower():
            item.add_marker(pytest.mark.slow)
        if "edge_case" in item.nodeid.lower():
            item.add_marker(pytest.mark.edge_case)
        if "stress" in item.nodeid.lower():
            item.add_marker(pytest.mark.stress)


__all__ = [
    # Path setup
    "REPO_ROOT",
    "analytics",
    # Performance fixtures
    "fast_test_mode",
    "test_iteration_config",
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
