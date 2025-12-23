from __future__ import annotations

import pytest

"""
conftest.py

Pytest configuration and fixtures for DutchBay EPC Model.

Provides:
- --fast-mode: Reduced-iteration test runs (for CI/dev)
- --full-iterations: Full production test runs
- fast_mode fixture: Boolean flag available to all tests
"""


def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register custom pytest command-line options.
    
    Options:
        --fast-mode: Run reduced-iteration/quick sanity variants of
                     stochastic & sensitivity tests
        --full-iterations: Run full-iteration variants (overrides --fast-mode)
    
    Example:
        pytest tests/sensitivity/ -v --fast-mode
        pytest tests/mc/ -v --full-iterations
    """
    group = parser.getgroup("dutchbay")
    group.addoption(
        "--fast-mode",
        action="store_true",
        default=False,
        help="Run reduced-iteration/quick sanity variants of stochastic & sensitivity tests.",
    )
    group.addoption(
        "--full-iterations",
        action="store_true",
        default=False,
        help="Run full-iteration variants (overrides --fast-mode).",
    )


@pytest.fixture(scope="session")
def fast_mode(pytestconfig: pytest.Config) -> bool:
    """
    Session-wide fixture indicating whether tests should run in fast mode.
    
    Returns True if --fast-mode is set, False if --full-iterations is set.
    If both are set, --full-iterations takes precedence.
    
    Usage in tests:
        def test_monte_carlo(fast_mode):
            n_iterations = 20 if fast_mode else 1000
            result = run_monte_carlo_analysis(..., n_iterations=n_iterations)
    
    Args:
        pytestconfig: Pytest configuration object
        
    Returns:
        Boolean indicating fast mode status
    """
    # Full iterations wins if both accidentally provided
    if pytestconfig.getoption("--full-iterations"):
        return False
    return bool(pytestconfig.getoption("--fast-mode"))
