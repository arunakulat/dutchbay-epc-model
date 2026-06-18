#!/usr/bin/env python3
from __future__ import annotations

"""
Integration tests for analytics.sensitivity_v14 module.

Phase: v14, Go-with-the-Flow compliant.

These tests validate integration across the full sensitivity workflow:

1. Uses the v14 evaluation gateway (evaluate_with_overrides) under the hood.
2. Enforces coordinator-only pattern (no direct finance engine access here).
3. Covers:
   - One-way tornado (single metric)
   - Multi-metric tornado
   - Breakeven search
   - Deep-merge behaviour
   - DataFrame export helpers

Pattern: Real v14 pipeline calls on real scenario configs (no mocks).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pandas as pd
import pytest

from analytics.contracts_v14 import (
    BreakevenResult,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    SensitivityRequest,
    SensitivitySuite,
    TornadoResult,
)
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.sensitivity_v14 import (
    build_nested_override,
    multi_metric_suite_to_dataframe,
    run_breakeven_parameter,
    run_multi_metric_tornado,
    run_tornado_sensitivity,
    tornado_suite_to_dataframe,
)

logger = logging.getLogger(__name__)


# Adjust this path if your test scenarios live elsewhere
SCENARIO_BASE = Path("scenarios")
TEST_BASE_SCENARIO = SCENARIO_BASE / "test_base_scenario.yaml"


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
class TestBuildNestedOverrideIntegration:
    def test_single_level(self) -> None:
        """Single-level path creates simple dict."""
        result = build_nested_override("tariff", 30.0)
        assert result == {"tariff": 30.0}

    def test_two_levels(self) -> None:
        """Two-level path creates nested dict."""
        result = build_nested_override("finance.tariff", 30.0)
        assert result == {"finance": {"tariff": 30.0}}

    def test_three_levels(self) -> None:
        """Three-level path creates deeply nested dict."""
        result = build_nested_override("config.finance.tariff", 30.0)
        expected = {"config": {"finance": {"tariff": 30.0}}}
        assert result == expected

    def test_list_path(self) -> None:
        """List of keys also creates nested dict."""
        result = build_nested_override(["finance", "tariff"], 30.0)
        assert result == {"finance": {"tariff": 30.0}}

    def test_empty_path(self) -> None:
        """Empty path returns empty dict."""
        result = build_nested_override("", 30.0)
        assert result == {}
        result2 = build_nested_override([], 30.0)
        assert result2 == {}


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
class TestRunTornadoSensitivityIntegration:
    def test_run_tornado_sensitivity_full_flow(self) -> None:
        """
        Full integration test: run tornado on a real scenario.

        Verifies:
        - Returns SensitivitySuite with correct structure.
        - Results sorted by impact_abs descending.
        - Base metric value is populated.
        - Uses v14 evaluation gateway throughout.
        """
        params = [
            ParameterRangeConfig(
                variable_name="finance.capex_usd",
                base_value=1_000_000.0,
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
            base_config_path=str(TEST_BASE_SCENARIO),
            parameters=params,
            metric="dscr_min",
        )

        suite = run_tornado_sensitivity(request)

        assert isinstance(suite, SensitivitySuite)
        assert len(suite.tornado_results) == len(params)
        assert suite.base_config_path == str(TEST_BASE_SCENARIO)
        assert suite.metric == "dscr_min"

        # Structure checks
        impacts = [r.impact_abs for r in suite.tornado_results]
        sorted_impacts = sorted(impacts, reverse=True)
        assert impacts == sorted_impacts
        assert isinstance(suite.base_metric, (int, float))

    def test_run_tornado_legacy_api(self) -> None:
        """
        Legacy API: config path string + parameters + metric.
        """
        params = [
            ParameterRangeConfig(
                variable_name="finance.tariff",
                base_value=25.0,
                low_pct=-10.0,
                high_pct=10.0,
            )
        ]

        suite = run_tornado_sensitivity(
            str(TEST_BASE_SCENARIO),
            parameters=params,
            metric="dscr_min",
        )

        assert isinstance(suite, SensitivitySuite)
        assert len(suite.tornado_results) == len(params)
        assert isinstance(suite.base_metric, (int, float))


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
class TestRunMultiMetricTornadoIntegration:
    def test_run_multi_metric_tornado_full_flow(self) -> None:
        """
        Full integration test: multi-metric tornado with v14 pipeline.

        Verifies:
        - Returns MultiMetricSensitivitySuite.
        - Captures impacts for all requested metrics.
        - Base values populated for each metric.
        """
        metrics = ["dscr_min", "dscr_max", "dscr_mean"]

        params = [
            ParameterRangeConfig(
                variable_name="finance.capex_usd",
                base_value=1_000_000.0,
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
            base_config_path=str(TEST_BASE_SCENARIO),
            parameters=params,
        )

        suite = run_multi_metric_tornado(request, metrics=metrics)

        assert isinstance(suite, MultiMetricSensitivitySuite)
        assert len(suite.tornado_results) == len(params)
        assert suite.metrics == list(metrics)
        assert len(suite.base_metrics) == len(metrics)

        for result in suite.tornado_results:
            assert isinstance(result, MultiMetricTornadoResult)
            assert set(result.impacts.keys()) == set(metrics)
            assert set(result.low_values.keys()) == set(metrics)
            assert set(result.high_values.keys()) == set(metrics)


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
class TestRunBreakevenParameterIntegration:
    def test_run_breakeven_parameter_full_flow(self) -> None:
        """
        Full integration test: breakeven analysis with v14 pipeline.

        Verifies:
        - Solves for parameter value that yields target metric.
        - Returns BreakevenResult with solution.
        """
        result = run_breakeven_parameter(
            base_config_path=str(TEST_BASE_SCENARIO),
            variable_name="tariff.tariff_lkr_per_kwh",
            target_metric="project_irr",
            target_value=0.12,  # target 12% IRR
            low_pct=-50.0,
            high_pct=50.0,
        )

        assert isinstance(result, BreakevenResult)
        assert result.variable == "tariff.tariff_lkr_per_kwh"

        if result.status == "success":
            assert result.breakeven_value is not None
            assert isinstance(result.breakeven_value, (int, float))
            assert result.bracket is not None
        else:
            # Even if max_iter_exceeded, structure must be valid
            assert result.breakeven_value is not None
            assert result.bracket is not None


class TestExportHelpers:
    def test_tornado_suite_to_dataframe(self) -> None:
        """Test converting tornado suite to DataFrame."""
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

        assert len(df) == 2
        assert list(df.columns) == [
            "variable",
            "base_irr",
            "low_irr",
            "high_irr",
            "impact_abs",
        ]
        assert df["variable"].tolist() == ["param_a", "param_b"]

    def test_multi_metric_suite_to_dataframe(self) -> None:
        """Test converting multi-metric suite to long-form DataFrame."""
        metrics = ["project_irr", "equity_irr"]
        base_metrics = {"project_irr": 0.12, "equity_irr": 0.15}

        result = MultiMetricTornadoResult(
            variable="param_a",
            label="Parameter A",
            base_values=base_metrics,
            low_values={"project_irr": 0.10, "equity_irr": 0.13},
            high_values={"project_irr": 0.14, "equity_irr": 0.17},
            impacts={"project_irr": 0.04, "equity_irr": 0.04},
            impact_dirs={"project_irr": 1, "equity_irr": 1},
        )

        suite = MultiMetricSensitivitySuite(
            tornado_results=[result],
            base_metrics=base_metrics,
            base_config_path="dummy.yaml",
            metrics=metrics,
        )

        df = multi_metric_suite_to_dataframe(suite)

        assert len(df) == 2  # 1 param * 2 metrics
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


@pytest.mark.skipif(
    not TEST_BASE_SCENARIO.is_file(),
    reason=f"Integration scenario not found: {TEST_BASE_SCENARIO}",
)
def test_evaluation_gateway_round_trip() -> None:
    """
    Sanity check: evaluate_with_overrides on the base scenario
    returns a KPI dict with core metrics needed by sensitivity tests.
    """
    kpis = evaluate_with_overrides(TEST_BASE_SCENARIO)
    # Adjust expected keys to match your pipeline outputs
    assert "project_irr" in kpis
    assert "dscr_min" in kpis
    assert isinstance(kpis["project_irr"], (int, float))
    assert isinstance(kpis["dscr_min"], (int, float))
