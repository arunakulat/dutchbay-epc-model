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

import sys
from importlib import import_module

import pytest

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
    """Test importing contracts_v14 followed by fx integration.

    This specifically tests the P0-1 fix for circular imports.
    """
    try:
        # Clear any cached imports to test fresh
        for key in list(sys.modules.keys()):
            if "analytics.fx" in key or "analytics.contracts" in key:
                del sys.modules[key]

        # Import in order that would trigger circular dep
        from analytics import contracts_v14
        from analytics.fx import integrate_fx_into_scenario_result

        assert contracts_v14 is not None
        assert integrate_fx_into_scenario_result is not None
    except ImportError as e:
        pytest.fail(f"Circular import detected (contracts_v14 ↔ fx): {e}")


def test_import_monte_carlo_aep_before_analytics_wind():
    """Regression: monte_carlo_aep must import standalone (before analytics.wind).

    analytics.wind.__init__ -> pipeline_aep_v14 -> analytics.simulation.monte_carlo_aep
    forms a cycle; a module-level `from analytics.wind.losses_model import ...` in
    monte_carlo_aep broke when monte_carlo_aep was imported FIRST (the test suite masked
    it by importing analytics.wind earlier). The DEFAULT_WIND_LOSSES import is now lazy.
    """
    for key in list(sys.modules.keys()):
        if key.startswith("analytics.wind") or key.startswith("analytics.simulation"):
            del sys.modules[key]
    try:
        from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep

        assert run_monte_carlo_aep is not None
    except ImportError as e:
        pytest.fail(f"Circular import (analytics.wind ↔ monte_carlo_aep): {e}")


# =============================================================================
# Performance Guardrails (imports should be fast)
# =============================================================================


def test_import_speed_baseline():
    """Verify that basic imports complete quickly.

    Import times should be < 1 second for analytics package.
    Slow imports indicate:
      - Heavy computation at module level (anti-pattern)
      - Eager loading of large dependencies (use lazy imports)
      - Circular import resolution overhead
    """
    import time

    # Clear cache for clean test
    for key in list(sys.modules.keys()):
        if key.startswith("analytics"):
            del sys.modules[key]

    start = time.time()
    import analytics

    elapsed = time.time() - start

    # Allow up to 2 seconds (generous, but catches egregious issues)
    assert elapsed < 2.0, f"Import took {elapsed:.2f}s (expected <2.0s)"


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
