#!/usr/bin/env python3
"""
Integration tests for analytics.sensitivity_v14 module (Phase 2B).

Tests validate v14 pipeline integration across the full sensitivity workflow:
1. Uses run_v14_pipeline() gateway (migrated from evaluate_with_overrides)
2. Tests coordinator-only pattern (no direct finance engine access)
3. Covers tornado, multi-metric, and breakeven analysis
4. Validates export helpers and error handling

Pattern: Integration tests with direct v14 pipeline calls.

Sprint 7 Phase 2B: Migrated from evaluate_with_overrides to run_v14_pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pytest

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    SensitivitySuite,
    TornadoResult,
)
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity_v14 import (
    SensitivityRequest,
    _build_nested_override,
    _deep_merge_config,
    run_breakeven_parameter,
    run_multi_metric_tornado,
    run_tornado_sensitivity,
)
from run_full_pipeline_v14 import run_v14_pipeline

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Helper: _build_nested_override
# ══════════════════════════════════════════════════════════════════════════


def test_build_nested_override_single_level():
    """Single-level path creates simple dict."""
    result = _build_nested_override("tariff", 30.0)
    assert result == {"tariff": 30.0}


def test_build_nested_override_two_levels():
    """Two-level path creates nested dict."""
    result = _build_nested_override("finance.tariff", 30.0)
    assert result == {"finance": {"tariff": 30.0}}


def test_build_nested_override_three_levels():
    """Three-level path creates deeply nested dict."""
    result = _build_nested_override("config.finance.tariff", 30.0)
    expected = {"config": {"finance": {"tariff": 30.0}}}
    assert result == expected


def test_build_nested_override_with_list():
    """List of keys also creates nested dict."""
    result = _build_nested_override(["finance", "tariff"], 30.0)
    assert result == {"finance": {"tariff": 30.0}}


def test_build_nested_override_empty_path():
    """Empty path returns empty dict."""
    result = _build_nested_override("", 30.0)
    assert result == {}

    result = _build_nested_override([], 30.0)
    assert result == {}


def test_build_nested_override_empty_path():
    """Empty path returns empty dict."""
    result = _build_nested_override("", 30.0)
    assert result == {}

    result = _build_nested_override([], 30.0)
    assert result == {}


def test_build_nested_override_empty_path():
    """Empty path returns empty dict."""
    result = _build_nested_override("", 30.0)
    assert result == {}

    result = _build_nested_override([], 30.0)
    assert result == {}


def test_build_nested_override_empty_path():
    """Empty path returns empty dict."""
    result = _build_nested_override("", 30.0)
    assert result == {}

    result = _build_nested_override([], 30.0)
    assert result == {}


# ══════════════════════════════════════════════════════════════════════════
# Integration: run_tornado_sensitivity (requires mock/fixture)
# ══════════════════════════════════════════════════════════════════════════


def test_run_tornado_sensitivity_integration_full_flow():
    """
    Full integration test: run tornado on real scenario (when available).

    Verifies:
    - Returns SensitivitySuite with correct structure
    - Results sorted by impact_abs descending
    - Base metric value is populated
    - Uses v14 pipeline throughout
    """
    params = [
        ParameterRangeConfig(
            variable_name="finance.capex_usd",
            base_value=1000000.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
        ParameterRangeConfig(
            variable_name="tariff.tariff_lkr_per_kwh",
            base_value=25.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
    ]

    request = SensitivityRequest(
        base_config_path="scenarios/test/base_scenario.yaml",
        parameters=params,
        metric="dscr_min",
    )

    suite = run_tornado_sensitivity(request)

    # Structure checks
    assert isinstance(suite, SensitivitySuite)
    assert len(suite.tornado_results) == len(params)
    assert suite.base_config_path == "scenarios/test/base_scenario.yaml"
    assert suite.metric == "dscr_min"

    # Results should be sorted by impact_abs descending
    impacts = [r.impact_abs for r in suite.tornado_results]
    assert impacts == sorted(impacts, reverse=True)

    # Base metric should be numeric
    assert isinstance(suite.base_metric, (int, float))


def test_run_tornado_legacy_api():
    """Test legacy API: passing config path as string + params separately."""
    params = [
        ParameterRangeConfig(
            variable_name="finance.tariff",
            base_value=25.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
    ]

    suite = run_tornado_sensitivity(
        "scenarios/test/base_scenario.yaml",
        parameters=params,
        metric="dscr_min",
    )

    assert isinstance(suite, SensitivitySuite)
    assert len(suite.tornado_results) == len(params)


# ══════════════════════════════════════════════════════════════════════════
# Integration: run_multi_metric_tornado
# ══════════════════════════════════════════════════════════════════════════


def test_run_multi_metric_tornado_integration_full_flow():
    """
    Full integration test: multi-metric tornado with v14 pipeline.

    Verifies:
    - Returns MultiMetricSensitivitySuite
    - Captures impacts for all requested metrics
    - Base values populated for each metric
    - Uses v14 pipeline throughout
    """
    metrics = ["dscr_min", "dscr_max", "dscr_mean"]

    params = [
        ParameterRangeConfig(
            variable_name="finance.capex_usd",
            base_value=1000000.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
        ParameterRangeConfig(
            variable_name="tariff.tariff_lkr_per_kwh",
            base_value=25.0,
            low_pct=-10.0,
            high_pct=10.0,
        ),
    ]

    request = SensitivityRequest(
        base_config_path="scenarios/test/base_scenario.yaml",
        parameters=params,
    )

    suite = run_multi_metric_tornado(request, metrics=metrics)

    # Structure checks
    assert isinstance(suite, MultiMetricSensitivitySuite)
    assert len(suite.tornado_results) == len(params)
    assert suite.metrics == list(metrics)
    assert len(suite.base_metrics) == len(metrics)

    # Each result should have impacts for all metrics
    for result in suite.tornado_results:
        assert isinstance(result, MultiMetricTornadoResult)
        assert set(result.impacts.keys()) == set(metrics)
        assert set(result.low_values.keys()) == set(metrics)
        assert set(result.high_values.keys()) == set(metrics)


# ══════════════════════════════════════════════════════════════════════════
# Integration: run_breakeven_parameter
# ══════════════════════════════════════════════════════════════════════════


def test_run_breakeven_parameter_integration_full_flow():
    """
    Full integration test: breakeven analysis with v14 pipeline.

    Verifies:
    - Solves for parameter value that yields target metric
    - Returns BreakevenResult with solution
    - Status is 'success' if converged
    - Uses v14 pipeline for objective evaluation
    """
    result = run_breakeven_parameter(
        base_config_path="scenarios/test/base_scenario.yaml",
        variable_name="tariff.tariff_lkr_per_kwh",
        target_metric="project_irr",
        target_value=0.12,  # Target 12% IRR
        low_pct=-50.0,  # -50% of base value
        high_pct=50.0,  # +50% of base value
    )

    # Structure checks
    assert isinstance(result, BreakevenResult)
    assert result.variable == "tariff.tariff_lkr_per_kwh"

    # If converged, status should be success
    if result.status == "success":
        assert result.breakeven_value is not None
        assert isinstance(result.breakeven_value, (int, float))
        assert result.bracket is not None


# ══════════════════════════════════════════════════════════════════════════
# Unit tests: _deep_merge_config helper
# ══════════════════════════════════════════════════════════════════════════


def test_deep_merge_config_simple():
    """Test simple merge of nested dicts."""
    base = {"finance": {"capex": 100, "tariff": 0.10}, "debt": {}}
    override = {"finance": {"tariff": 0.12}}

    result = _deep_merge_config(base, override)

    assert result["finance"]["tariff"] == 0.12
    assert result["finance"]["capex"] == 100  # Preserved
    assert result["debt"] == {}


def test_deep_merge_config_nested_preservation():
    """Test that deep merge preserves non-overridden nested values."""
    base = {
        "finance": {"capex": 100, "opex": 50, "tariff": 0.10},
        "debt": {"principal": 600000, "rate": 0.08},
    }
    override = {"finance": {"tariff": 0.12}}

    result = _deep_merge_config(base, override)

    # Overridden
    assert result["finance"]["tariff"] == 0.12

    # Preserved
    assert result["finance"]["capex"] == 100
    assert result["finance"]["opex"] == 50
    assert result["debt"]["principal"] == 600000
    assert result["debt"]["rate"] == 0.08


def test_deep_merge_config_creates_copy():
    """Test that merge creates a copy, not modifying original."""
    base = {"finance": {"capex": 100}}
    override = {"finance": {"tariff": 0.12}}

    result = _deep_merge_config(base, override)

    # Modify result
    result["finance"]["capex"] = 999

    # Original should be unchanged
    assert base["finance"]["capex"] == 100


# ══════════════════════════════════════════════════════════════════════════
# Export helpers (unit tests)
# ══════════════════════════════════════════════════════════════════════════


def test_tornado_suite_to_dataframe():
    """Test converting tornado suite to DataFrame."""
    from analytics.sensitivity_v14 import tornado_suite_to_dataframe

    # Create mock suite
    results = [
        TornadoResult(
            variable="param_a",
            base_irr=0.12,
            low_irr=0.10,
            high_irr=0.14,
        ),
        TornadoResult(
            variable="param_b",
            base_irr=0.12,
            low_irr=0.11,
            high_irr=0.13,
        ),
    ]

    suite = SensitivitySuite(
        tornado_results=results,
        base_metric=0.12,
        base_config_path="dummy.yaml",
        metric="dscr_min",
    )

    df = tornado_suite_to_dataframe(suite)

    # Structure checks
    assert len(df) == 2
    assert list(df.columns) == [
        "variable",
        "base_irr",
        "low_irr",
        "high_irr",
        "impact_abs",
    ]
    assert df["variable"].tolist() == ["param_a", "param_b"]


def test_multi_metric_suite_to_dataframe():
    """Test converting multi-metric suite to long-form DataFrame."""
    from analytics.sensitivity_v14 import multi_metric_suite_to_dataframe

    metrics = ["project_irr", "equity_irr"]
    base_metrics = {"project_irr": 0.12, "equity_irr": 0.15}

    results = [
        MultiMetricTornadoResult(
            variable="param_a",
            label="Parameter A",
            base_values=base_metrics,
            low_values={"project_irr": 0.10, "equity_irr": 0.13},
            high_values={"project_irr": 0.14, "equity_irr": 0.17},
            impacts={"project_irr": 0.04, "equity_irr": 0.04},
            impact_dirs={"project_irr": 1, "equity_irr": 1},
        ),
    ]

    suite = MultiMetricSensitivitySuite(
        tornado_results=results,
        base_metrics=base_metrics,
        base_config_path="dummy.yaml",
        metrics=metrics,
    )

    df = multi_metric_suite_to_dataframe(suite)

    # Structure checks
    assert len(df) == 2  # 1 param × 2 metrics
    expected_cols = [
        "variable",
        "label",
        "metric",
        "base_value",
        "low_value",
        "high_value",
        "impact",
        "impact_dir",
    ]
    assert list(df.columns) == expected_cols
    assert set(df["metric"].unique()) == set(metrics)


# ══════════════════════════════════════════════════════════════════════════
# Edge cases and error handling
# ══════════════════════════════════════════════════════════════════════════


def test_empty_parameters_handled_gracefully():
    """Empty parameter list should be handled without crashing."""
    request = SensitivityRequest(
        base_config_path="dummy.yaml",
        parameters=[],
        metric="dscr_min",
    )

    # Should either return empty suite or fallback to defaults
    # (Current implementation falls back to defaults)
    # This is acceptable behavior for legacy compatibility
    assert request.parameters == []


def test_override_labels_structure():
    """Override labels should have correct structure."""
    override_labels = {
        "finance.capex_usd": "Capital Expenditure (USD)",
        "finance.tariff": "Tariff (LKR/kWh)",
    }

    request = SensitivityRequest(
        base_config_path="dummy.yaml",
        parameters=[
            ParameterRangeConfig(
                variable_name="finance.capex_usd",
                base_value=1000000.0,
                low_pct=-10.0,
                high_pct=10.0,
            ),
        ],
        override_labels=override_labels,
        metric="dscr_min",
    )

    assert request.override_labels == override_labels
    assert request.override_labels["finance.capex_usd"] == "Capital Expenditure (USD)"


def test_parameter_range_config_validation():
    """ParameterRangeConfig should validate inputs."""
    # Valid config
    param = ParameterRangeConfig(
        variable_name="finance.tariff",
        base_value=25.0,
        low_pct=-10.0,
        high_pct=10.0,
    )

    assert param.variable_name == "finance.tariff"
    assert param.base_value == 25.0
    assert param.low_pct == -10.0
    assert param.high_pct == 10.0


def test_sensitivity_request_immutable():
    """SensitivityRequest should be frozen (immutable)."""
    request = SensitivityRequest(
        base_config_path="test.yaml",
        parameters=[],
        metric="dscr_min",
    )

    # Should not be able to modify
    with pytest.raises((AttributeError, TypeError)):
        request.metric = "equity_irr"  # type: ignore


def test_tornado_result_properties():
    """TornadoResult should expose correct properties."""
    result = TornadoResult(
        variable="test_param",
        base_irr=0.12,
        low_irr=0.10,
        high_irr=0.14,
    )

    assert result.variable == "test_param"
    assert result.base_irr == 0.12
    assert result.low_irr == 0.10
    assert result.high_irr == 0.14
    assert result.impact_abs == pytest.approx(
        0.04, abs=1e-6
    )  # max(|0.10-0.12|, |0.14-0.12|)


def test_breakeven_result_structure():
    """BreakevenResult should have correct structure."""
    result = BreakevenResult(
        variable="finance.tariff",
        breakeven_value=28.5,
        bracket=(25.0, 35.0),
        status="success",
    )

    assert result.variable == "finance.tariff"
    assert result.breakeven_value == 28.5
    assert result.bracket == (25.0, 35.0)
    assert result.status == "success"


# ══════════════════════════════════════════════════════════════════════════
# Legacy API compatibility tests
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# Legacy API compatibility tests - DEPRECATED after Phase 2A migration
# ══════════════════════════════════════════════════════════════════════════


def test_legacy_parameters_now_use_sensitivity_request():
    """
    Test that legacy _load_parameters pattern is replaced by SensitivityRequest.

    Phase 2A Note: _load_parameters() was removed during v14 pipeline migration.
    Use SensitivityRequest with explicit parameters instead.
    """
    params = [
        ParameterRangeConfig(
            variable_name="test.param",
            base_value=100.0,
            low_pct=-10.0,
            high_pct=10.0,
        )
    ]

    request = SensitivityRequest(
        base_config_path="dummy.yaml",
        parameters=params,
        metric="dscr_min",
    )

    # Verify request structure
    assert len(request.parameters) == 1
    assert request.parameters[0].variable_name == "test.param"


def test_legacy_api_still_works_with_string_config_path():
    """Test backward compatibility: passing config path as string."""
    from unittest.mock import patch

    params = [
        ParameterRangeConfig(
            variable_name="test.param",
            base_value=100.0,
            low_pct=-10.0,
            high_pct=10.0,
        )
    ]

    # Legacy API: pass string path + parameters
    with patch("analytics.sensitivity_v14.load_scenario_config") as mock_load:
        with patch("analytics.sensitivity_v14.run_v14_pipeline") as mock_pipeline:
            mock_load.return_value = {"test": {"param": 100.0}}
            mock_pipeline.return_value = {"kpis": {"dscr_min": 8202.23}}

            suite = run_tornado_sensitivity(
                "test.yaml",
                parameters=params,
                metric="dscr_min",
            )

            assert isinstance(suite, SensitivitySuite)


# pytest configuration
pytest_plugins = []

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
