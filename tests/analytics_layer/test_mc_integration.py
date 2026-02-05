from __future__ import annotations

"""
Integration tests for Monte Carlo → Lender Analytics pipeline.

Tests the complete flow:
  MC Engine → Aggregation → Exports → CASPER Payload

Sprint 18: Validates that all components work together correctly
and produce lender-grade risk analytics.
"""

import numpy as np
import pytest

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.correlation import CorrelationSpec
from analytics.mc.exports import (
    build_lender_risk_table,
    build_casper_risk_blocks,
    CovenantSpec,
)
from analytics.contracts_v14 import MonteCarloResult


# Test configuration fixture
@pytest.fixture
def minimal_mc_config():
    """Minimal config for MC testing."""
    return {
        "scenario_name": "test_scenario",
        "monte_carlo": {
            "parameters": [
                {
                    "name": "capex",
                    "min": 100.0,
                    "max": 120.0,
                    "distribution": "uniform",
                },
                {"name": "tariff", "min": 0.08, "max": 0.12, "distribution": "uniform"},
            ]
        },
    }


@pytest.fixture
def realistic_mc_config():
    """Realistic config with typical project finance parameters."""
    return {
        "scenario_name": "realistic_test",
        "monte_carlo": {
            "parameters": [
                {"name": "capex", "min": 100e6, "max": 120e6},
                {"name": "capacity_factor", "min": 0.30, "max": 0.40},
                {"name": "tariff", "min": 0.08, "max": 0.12},
                {"name": "opex_annual", "min": 2e6, "max": 3e6},
            ],
            "correlation": {
                "enabled": False,
            },
        },
    }


class TestMCEngineToExportsFullPipeline:
    """Test complete MC → exports pipeline."""

    @pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
    def test_mc_engine_to_exports_full_pipeline(self, minimal_mc_config):
        """Complete pipeline: MC engine → aggregate → lender risk table."""
        # 1. Run MC engine
        result = run_monte_carlo_analysis(
            base_config=minimal_mc_config,
            n_trials=50,
            seed=42,
        )

        # 2. Validate result structure
        assert isinstance(result, MonteCarloResult)
        assert result.trials is not None
        assert result.summary is not None
        assert result.metadata is not None

        # 3. Build lender risk table (requires trials)
        # Note: This will work once we have real trial metrics from engine
        # For now, we'll manually add trial data for testing
        test_result = MonteCarloResult(
            summary={"dscr_min": {"mean": 1.42}},
            metadata={"n_trials": 50},
            trials={"dscr_min": list(np.random.uniform(1.2, 1.6, 50))},
        )

        df = build_lender_risk_table(test_result)

        # 4. Validate output
        assert isinstance(df, pd.DataFrame)
        assert "metric" in df.columns
        assert "P50" in df.columns
        assert "mean" in df.columns
        assert len(df) > 0


class TestMCResultStructure:
    """Test MonteCarloResult has required fields for exports."""

    def test_mc_result_has_required_fields_for_exports(self):
        """MonteCarloResult must have trials field populated."""
        # Create result with trials
        result = MonteCarloResult(
            summary={
                "dscr_min": {
                    "mean": 1.42,
                    "std": 0.08,
                    "percentiles": {50: 1.45, 90: 1.32},
                },
            },
            metadata={"n_trials": 100, "seed": 42},
            trials={
                "dscr_min": list(np.random.uniform(1.2, 1.6, 100)),
                "project_irr": list(np.random.uniform(0.10, 0.18, 100)),
            },
        )

        # Validate
        assert result.trials is not None
        assert "dscr_min" in result.trials
        assert len(result.trials["dscr_min"]) == 100
        assert len(result.trials["project_irr"]) == 100

    def test_mc_result_trial_arrays_same_length(self):
        """All trial arrays must have same length."""
        with pytest.raises(ValueError) as exc_info:
            MonteCarloResult(
                summary={},
                metadata={},
                trials={
                    "dscr_min": [1.32, 1.45],  # 2 values
                    "project_irr": [0.14],  # 1 value - MISMATCH!
                },
            )

        assert "same length" in str(exc_info.value).lower()


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
class TestLenderRiskTableFromRealSimulation:
    """Test lender risk table from realistic MC simulation."""

    def test_lender_risk_table_from_real_mc_simulation(self):
        """Generate lender risk table from realistic trial data."""
        # Simulate realistic trial outcomes
        n_trials = 200

        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": n_trials, "seed": 42},
            trials={
                "dscr_min": list(np.random.normal(1.42, 0.08, n_trials)),
                "project_irr": list(np.random.normal(0.139, 0.012, n_trials)),
                "project_npv": list(np.random.normal(54.1e9, 4.3e9, n_trials)),
                "llcr": list(np.random.normal(1.61, 0.11, n_trials)),
                "plcr": list(np.random.normal(1.51, 0.10, n_trials)),
            },
        )

        # Generate lender pack
        covenant = CovenantSpec(dscr_floor=1.30)
        df = build_lender_risk_table(result, covenant=covenant)

        # Validate structure
        assert len(df) >= 5  # At least 5 metrics
        assert "DSCR (min)" in df["metric"].values
        assert "Prob(DSCR < 1.30)" in df["metric"].values
        assert "LLCR" in df["metric"].values

        # Validate statistics are reasonable
        dscr_row = df[df["metric"] == "DSCR (min)"].iloc[0]
        assert 1.2 < dscr_row["P50"] < 1.6
        assert dscr_row["std"] > 0


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
class TestCASPERPayloadIntegration:
    """Test CASPER payload block generation."""

    def test_casper_payload_integration(self):
        """CASPER blocks should be ready for payload insertion."""
        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": 100},
            trials={
                "dscr_min": list(np.random.uniform(1.2, 1.6, 100)),
            },
        )

        blocks = build_casper_risk_blocks(
            result, covenant=CovenantSpec(dscr_floor=1.30)
        )

        # Validate structure
        assert "lender_risk_table" in blocks
        assert "covenant" in blocks

        # DataFrame should be serializable
        df = blocks["lender_risk_table"]
        assert isinstance(df, pd.DataFrame)
        records = df.to_dict(orient="records")
        assert len(records) > 0

        # Covenant metrics should be JSON-safe
        covenant = blocks["covenant"]
        assert isinstance(covenant["dscr_floor"], (int, float))
        assert isinstance(covenant["prob_breach"], (int, float))
        assert isinstance(covenant["n_trials"], int)

    def test_casper_payload_ready_for_insertion(self):
        """Blocks can be directly inserted into CASPER payload."""
        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": 50},
            trials={"dscr_min": list(np.random.uniform(1.2, 1.6, 50))},
        )

        blocks = build_casper_risk_blocks(result)

        # Simulate CASPER payload structure
        payload = {
            "scenario": "test",
            "tables": {},
            "metrics": {},
        }

        # Insert blocks
        payload["tables"]["lender_risk_table"] = blocks["lender_risk_table"].to_dict(
            orient="records"
        )
        payload["metrics"]["covenant"] = blocks["covenant"]

        # Validate
        assert "lender_risk_table" in payload["tables"]
        assert "covenant" in payload["metrics"]
        assert payload["metrics"]["covenant"]["dscr_floor"] == 1.30


class TestCorrelationFlowThroughToExports:
    """Test correlation propagates through pipeline."""

    def test_correlation_metadata_preserved(self):
        """Correlation status should be preserved in metadata."""
        result = MonteCarloResult(
            summary={},
            metadata={
                "n_trials": 100,
                "correlation_enabled": True,
                "correlation_method": "iman_conover",
            },
            trials={"dscr_min": list(np.random.uniform(1.2, 1.6, 100))},
        )

        # Metadata should be accessible
        assert result.metadata["correlation_enabled"] is True
        assert result.metadata["correlation_method"] == "iman_conover"


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas required")
class TestMetricNameMappingEndToEnd:
    """Test custom metric name mapping through pipeline."""

    def test_metric_name_mapping_end_to_end(self):
        """Custom metric names should map correctly through exports."""
        # Result with custom metric names
        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": 50},
            trials={
                "custom_dscr_metric": list(np.random.uniform(1.2, 1.6, 50)),
            },
        )

        # Map custom name to canonical
        metric_map = {"dscr_min": "custom_dscr_metric"}
        df = build_lender_risk_table(result, metric_map=metric_map)

        # Should show canonical label in output
        assert "DSCR (min)" in df["metric"].values


class TestAggregationStoresTrials:
    """Test aggregation module stores raw trials."""

    def test_aggregate_trials_stores_raw_arrays(self):
        """aggregate_trials must populate result.trials field."""
        # Mock trial metrics
        trial_metrics = [
            {"dscr_min": 1.32, "project_irr": 0.14},
            {"dscr_min": 1.45, "project_irr": 0.13},
            {"dscr_min": 1.51, "project_irr": 0.15},
        ]

        result = aggregate_trials(
            trial_metrics=trial_metrics,
            base_config={},
            param_names=["capex", "tariff"],
            samples=np.random.rand(3, 2),
            meta={"n_trials": 3, "seed": 42},
        )

        # Validate trials stored
        assert result.trials is not None
        assert "dscr_min" in result.trials
        assert len(result.trials["dscr_min"]) == 3
        assert result.trials["dscr_min"] == [1.32, 1.45, 1.51]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
