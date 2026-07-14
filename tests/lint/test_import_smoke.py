"""Import smoke tests - permanent guardrail against circular imports.

These tests must pass before ANY code changes are committed.
They catch circular import issues that would otherwise break production.

Test Philosophy:
  - FAST: No heavy computation, just import statements
  - EXHAUSTIVE: Cover all critical module combinations
  - EARLY: Run in CI before unit/integration tests
  - ACTIONABLE: Clear error messages point to exact import cycle

Coverage:
  - Core analytics package
  - Contract system (contracts_v14)
  - FX integration (analytics.fx)
  - Monte Carlo engine (analytics.mc)
  - Sensitivity analysis (analytics.sensitivity)
  - Legacy shims (backward compatibility)

If these tests fail:
  1. Check for circular imports (A imports B imports A)
  2. Use TYPE_CHECKING for type-only imports
  3. Use lazy imports (__getattr__) for heavy modules
  4. Never import at module level if it creates a cycle

Example CI failure diagnosis:
  FAILED test_import_analytics - ImportError: cannot import name 'ScenarioResult'
  → Likely circular import between contracts_v14 and fx package
  → Fix: Use TYPE_CHECKING in fx/fx_integration.py
"""

import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cold_probe(code: str) -> "subprocess.CompletedProcess[str]":
    """Run *code* in a FRESH interpreter — a true cold-import probe.

    Never "simulate" a cold import by purging sys.modules in-process and
    re-importing: that creates a SECOND generation of module/class objects
    while already-collected test modules keep first-generation references,
    splitting class identity (isinstance checks fail) and mock.patch targets
    (patches land on the new module, code runs the old one) for every test
    that runs later in the same process (#937). A subprocess is also the
    stronger test for the stated purpose: parent-package attributes and C
    extensions survive an in-process purge, so only a fresh interpreter
    exercises the real cold-import order (same pattern as
    tests/lint/test_cold_import_order.py).
    """
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True,
        text=True,
        # A pathologically hung cold import must fail the probe, not hang the
        # suite (no global pytest-timeout is configured); 120 s is ~300× the
        # measured ~0.4 s cold import.
        timeout=120,
    )


# =============================================================================
# P0 Critical Imports (must always work)
# =============================================================================


def test_import_analytics():
    """Test that 'import analytics' succeeds without errors.

    This is the most basic smoke test. If this fails, the entire
    analytics package is broken (likely circular import).
    """
    try:
        import analytics

        assert analytics is not None
    except ImportError as e:
        pytest.fail(f"Failed to import analytics: {e}")


def test_import_contracts_v14():
    """Test that contracts_v14 can be imported from analytics.

    contracts_v14.py is the foundation of all type contracts.
    If this fails, check for:
      - Circular imports with fx package
      - Missing Pydantic dependency
      - Syntax errors in contracts_v14.py
    """
    try:
        from analytics import contracts_v14

        assert contracts_v14 is not None
        # Verify key contracts exist
        assert hasattr(contracts_v14, "ScenarioResult")
        assert hasattr(contracts_v14, "SensitivitySuite")
        assert hasattr(contracts_v14, "MonteCarloResult")
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.contracts_v14: {e}")


def test_import_fx_integration():
    """Test that FX integration can be imported without circular issues.

    This was the source of P0 circular import bug:
      contracts_v14 → fx_contracts → fx/__init__ → fx_integration → contracts_v14

    Fix applied:
      - analytics/fx/__init__.py uses lazy __getattr__
      - fx_integration.py uses TYPE_CHECKING for ScenarioResult

    If this fails:
      - Check analytics/fx/__init__.py for eager imports
      - Check fx_integration.py for runtime import of contracts_v14
    """
    try:
        from analytics.fx import integrate_fx_into_scenario_result

        assert integrate_fx_into_scenario_result is not None
    except ImportError as e:
        pytest.fail(
            f"Failed to import analytics.fx.integrate_fx_into_scenario_result: {e}"
        )


def test_import_sensitivity_optimizer():
    """Test that sensitivity.optimizer can be imported.

    This is the canonical Pareto optimization module.
    """
    try:
        from analytics.sensitivity.optimizer import run_pareto_search

        assert run_pareto_search is not None
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.sensitivity.optimizer: {e}")


def test_import_sensitivity_pareto_shim():
    """Test that legacy sensitivity_pareto.py shim works.

    This was converted from broken implementation to shim in P0-2.

    If this fails:
      - Check that analytics.sensitivity.optimizer exists
      - Check that sensitivity_pareto.py doesn't have import-time pandas
    """
    try:
        import analytics.sensitivity_pareto

        assert analytics.sensitivity_pareto is not None
        # Verify shim exports canonical functions
        assert hasattr(analytics.sensitivity_pareto, "run_pareto_search")
        assert hasattr(
            analytics.sensitivity_pareto, "optimize_from_sensitivity_insights"
        )
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.sensitivity_pareto: {e}")


def test_import_mc_engine():
    """Test that Monte Carlo engine can be imported."""
    try:
        from analytics.mc import engine

        assert engine is not None
        assert hasattr(engine, "run_monte_carlo_analysis")
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.mc.engine: {e}")


def test_import_sensitivity_engine():
    """Test that sensitivity engine can be imported."""
    try:
        from analytics.sensitivity import engine

        assert engine is not None
        assert hasattr(engine, "run_sensitivity_analysis")
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.sensitivity.engine: {e}")


def test_import_scenario_analytics():
    """Test that the blessed scenario-analytics entrypoint imports.

    analytics.scenario_analytics backs the run_scenario_analytics_v14 CLI.
    It silently broke (ImportError) when a call to an unimplemented
    normalise_kpis_for_export was added in #135 — nothing imported it, so
    nothing caught it. This guard keeps the entrypoint importable.
    """
    try:
        from analytics.scenario_analytics import ScenarioAnalytics

        assert ScenarioAnalytics is not None
    except ImportError as e:
        pytest.fail(f"Failed to import analytics.scenario_analytics: {e}")


# =============================================================================
# Cross-Module Import Tests (detect subtle circular deps)
# =============================================================================


def test_import_all_analytics_submodules():
    """Test that all major analytics submodules can be imported together.

    This catches subtle circular dependencies that only appear when
    multiple modules are imported in the same process.
    """
    modules_to_test = [
        "analytics.contracts_v14",
        "analytics.fx.fx_integration",
        "analytics.mc.engine",
        "analytics.sensitivity.engine",
        "analytics.evaluation_v14",
        "analytics.pipeline_v14_enhanced",
    ]

    failed_imports = []
    for module_name in modules_to_test:
        try:
            mod = import_module(module_name)
            assert mod is not None
        except ImportError as e:
            failed_imports.append((module_name, str(e)))

    if failed_imports:
        error_msg = "Failed to import the following modules:\n"
        for mod, err in failed_imports:
            error_msg += f"  - {mod}: {err}\n"
        pytest.fail(error_msg)


def test_import_contracts_then_fx():
    """Test importing contracts_v14 followed by fx integration, cold.

    This specifically tests the P0-1 fix for circular imports. Runs in a
    fresh interpreter so the import order is genuinely contracts-then-fx
    (in-process, both are already cached by earlier tests — and purging
    the cache to fake freshness is exactly the #937 leak; see _cold_probe).
    """
    probe = (
        "from analytics import contracts_v14; "
        "from analytics.fx import integrate_fx_into_scenario_result; "
        "assert contracts_v14 is not None; "
        "assert integrate_fx_into_scenario_result is not None"
    )
    result = _cold_probe(probe)
    if result.returncode != 0:
        pytest.fail(f"Circular import detected (contracts_v14 ↔ fx):\n{result.stderr}")


def test_import_monte_carlo_aep_before_analytics_wind():
    """Regression: monte_carlo_aep must import standalone (before analytics.wind).

    analytics.wind.__init__ -> pipeline_aep_v14 -> analytics.simulation.monte_carlo_aep
    forms a cycle; a module-level `from analytics.wind.losses_model import ...` in
    monte_carlo_aep broke when monte_carlo_aep was imported FIRST (the test suite masked
    it by importing analytics.wind earlier). The DEFAULT_WIND_LOSSES import is now lazy.

    Runs in a fresh interpreter: only there is monte_carlo_aep truly imported
    first (an in-process sys.modules purge is approximate AND leaks split
    module generations into later tests, #937; see _cold_probe).
    """
    probe = (
        "from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep; "
        "assert run_monte_carlo_aep is not None"
    )
    result = _cold_probe(probe)
    if result.returncode != 0:
        pytest.fail(
            f"Circular import (analytics.wind ↔ monte_carlo_aep):\n{result.stderr}"
        )


# =============================================================================
# Performance Guardrails (imports should be fast)
# =============================================================================


def test_import_speed_baseline():
    """Verify that basic imports complete quickly.

    Slow imports indicate:
      - Heavy computation at module level (anti-pattern)
      - Eager loading of large dependencies (use lazy imports)
      - Circular import resolution overhead

    Times `import analytics` inside a fresh interpreter — an honest cold
    timing (the old in-process purge timed a warm re-import over cached
    third-party modules, and the purge itself was the #937 leak; see
    _cold_probe). Cold baseline measured ~0.4s (2026-07-11); the 2.0s bound
    still catches egregious regressions.
    """
    probe = (
        "import time; "
        "t0 = time.perf_counter(); "
        "import analytics; "
        "elapsed = time.perf_counter() - t0; "
        "assert elapsed < 2.0, f'Import took {elapsed:.2f}s (expected <2.0s)'"
    )
    result = _cold_probe(probe)
    assert result.returncode == 0, f"import-speed probe failed:\n{result.stderr}"


# =============================================================================
# Metadata (for CI reporting)
# =============================================================================


def test_smoke_test_coverage():
    """Document what this test suite covers.

    This is a meta-test that just prints coverage info.
    Useful for CI logs and documentation.
    """
    coverage_report = """
    Import Smoke Test Coverage:
      ✅ analytics (root package)
      ✅ analytics.contracts_v14 (type system)
      ✅ analytics.fx.integrate_fx_into_scenario_result (P0 circular import fix)
      ✅ analytics.mc.engine (Monte Carlo)
      ✅ analytics.sensitivity.engine (sensitivity analysis)
      ✅ analytics.sensitivity.optimizer (Pareto)
      ✅ analytics.sensitivity_pareto (legacy shim, P0-2 fix)
      ✅ Cross-module imports (circular dep detection)
      ✅ Import performance baseline (<2s)
    
    Total modules tested: 8+
    P0 fixes validated: 2 (FX circular import, pareto shim)
    """
    print(coverage_report)
    assert True  # Always passes, just for documentation


if __name__ == "__main__":
    # Allow running directly for quick local validation
    pytest.main([__file__, "-v", "--tb=short"])
