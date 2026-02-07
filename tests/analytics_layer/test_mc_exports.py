from __future__ import annotations

"""
Tests for analytics.mc.exports - Lender risk table generation.

Sprint 18: Comprehensive test coverage for lender-grade Monte Carlo analytics.
"""

import numpy as np
import pytest

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from analytics.contracts_v14 import MonteCarloResult
from analytics.mc.exports import (
    CovenantSpec,
    build_lender_risk_table,
    build_casper_risk_blocks,
    dscr_breach_probability,
    worst_year_dscr_p95,
    _get_trial_array,
)


class TestCovenantSpec:
    """Test CovenantSpec dataclass."""

    def test_covenant_spec_defaults(self):
        """CovenantSpec should have sensible defaults."""
        covenant = CovenantSpec()
        assert covenant.dscr_floor == 1.30

    def test_covenant_spec_custom(self):
        """CovenantSpec should accept custom floor."""
        covenant = CovenantSpec(dscr_floor=1.25)
        assert covenant.dscr_floor == 1.25

    def test_covenant_spec_frozen(self):
        """CovenantSpec should be immutable."""
        covenant = CovenantSpec()
        with pytest.raises(Exception):  # FrozenInstanceError or similar
            covenant.dscr_floor = 1.40  # type: ignore


class TestGetTrialArray:
    """Test _get_trial_array extraction."""

    def test_get_trial_array_from_trials_field(self):
        """Should extract array from result.trials field."""
        result = MonteCarloResult(
            summary={},
            metadata={},
            trials={"dscr_min": [1.32, 1.45, 1.51]},
        )

        arr = _get_trial_array(result, "dscr_min")
        assert isinstance(arr, np.ndarray)
        assert arr.shape == (3,)
        assert np.allclose(arr, [1.32, 1.45, 1.51])

    def test_get_trial_array_from_metadata(self):
        """Should fall back to metadata['trials'] if trials field is None."""
        result = MonteCarloResult(
            summary={},
            metadata={"trials": {"dscr_min": [1.32, 1.45]}},
            trials=None,
        )

        arr = _get_trial_array(result, "dscr_min")
        assert isinstance(arr, np.ndarray)
        assert arr.shape == (2,)

    def test_get_trial_array_missing_key_raises(self):
        """Should raise KeyError with helpful message if metric not found."""
        result = MonteCarloResult(
            summary={},
            metadata={},
            trials={"dscr_min": [1.32]},
        )

        with pytest.raises(KeyError) as exc_info:
            _get_trial_array(result, "missing_metric")

        assert "missing_metric" in str(exc_info.value)
        assert "raw trial array" in str(exc_info.value)


class TestBreachProbability:
    """Test DSCR breach probability calculation."""

    def test_dscr_breach_probability_simple(self):
        """Should compute fraction of trials below floor."""
        dscr = np.array([1.20, 1.25, 1.35, 1.40, 1.45])
        prob = dscr_breach_probability(dscr, floor=1.30)
        assert np.isclose(prob, 0.4)  # 2 out of 5

    def test_dscr_breach_probability_no_breaches(self):
        """Should return 0 if no breaches."""
        dscr = np.array([1.35, 1.40, 1.45])
        prob = dscr_breach_probability(dscr, floor=1.30)
        assert prob == 0.0

    def test_dscr_breach_probability_all_breaches(self):
        """Should return 1.0 if all trials breach."""
        dscr = np.array([1.20, 1.25, 1.28])
        prob = dscr_breach_probability(dscr, floor=1.30)
        assert prob == 1.0

    def test_dscr_breach_probability_empty_array(self):
        """Should return NaN for empty array."""
        dscr = np.array([])
        prob = dscr_breach_probability(dscr, floor=1.30)
        assert np.isnan(prob)


class TestWorstYearDSCR:
    """Test worst-year DSCR P95 downside calculation."""

    def test_worst_year_dscr_p95_simple(self):
        """Should compute 5th percentile (P95 downside)."""
        dscr_min = np.array([1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50])
        p95_downside = worst_year_dscr_p95(dscr_min)

        # 5th percentile should be near the low end
        expected = np.percentile(dscr_min, 5)
        assert np.isclose(p95_downside, expected)

    def test_worst_year_dscr_p95_empty_array(self):
        """Should return NaN for empty array."""
        dscr_min = np.array([])
        p95 = worst_year_dscr_p95(dscr_min)
        assert np.isnan(p95)


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
class TestBuildLenderRiskTable:
    """Test lender risk table generation."""

    def test_build_lender_risk_table_basic(self):
        """Should build complete DataFrame with all required columns."""
        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": 100},
            trials={
                "dscr_min": list(np.random.uniform(1.2, 1.6, 100)),
                "project_irr": list(np.random.uniform(0.10, 0.18, 100)),
                "llcr": list(np.random.uniform(1.3, 1.8, 100)),
            },
        )

        df = build_lender_risk_table(result, covenant=CovenantSpec(dscr_floor=1.30))

        # Check structure
        assert isinstance(df, pd.DataFrame)
        assert "metric" in df.columns
        assert "P50" in df.columns
        assert "P90" in df.columns
        assert "P95" in df.columns
        assert "mean" in df.columns
        assert "std" in df.columns

        # Check required metrics present
        metrics = df["metric"].tolist()
        assert "DSCR (min)" in metrics
        assert "Prob(DSCR < 1.30)" in metrics
        assert "Worst-year DSCR (P95 downside)" in metrics

    def test_build_lender_risk_table_metric_mapping(self):
        """Should support custom metric name mapping."""
        result = MonteCarloResult(
            summary={},
            metadata={},
            trials={
                "custom_dscr": list(np.random.uniform(1.2, 1.6, 50)),
            },
        )

        metric_map = {"dscr_min": "custom_dscr"}
        df = build_lender_risk_table(result, metric_map=metric_map)

        # Should find metric using custom name
        assert "DSCR (min)" in df["metric"].tolist()

    def test_build_lender_risk_table_ordering(self):
        """Metrics should be in lender-preferred order."""
        result = MonteCarloResult(
            summary={},
            metadata={},
            trials={
                "dscr_min": list(np.random.uniform(1.2, 1.6, 50)),
                "llcr": list(np.random.uniform(1.3, 1.8, 50)),
            },
        )

        df = build_lender_risk_table(result)
        metrics = df["metric"].tolist()

        # DSCR should come first
        assert metrics[0] == "DSCR (min)"
        # Covenant metrics should follow
        assert "Prob(DSCR < 1.30)" in metrics[:3]


@pytest.mark.skipif(not HAS_PANDAS, reason="pandas not installed")
class TestBuildCasperRiskBlocks:
    """Test CASPER payload generation."""

    def test_build_casper_risk_blocks_structure(self):
        """Should return complete CASPER-ready payload."""
        result = MonteCarloResult(
            summary={},
            metadata={"n_trials": 100},
            trials={
                "dscr_min": list(np.random.uniform(1.2, 1.6, 100)),
            },
        )

        blocks = build_casper_risk_blocks(result, covenant=CovenantSpec(dscr_floor=1.30))

        # Check structure
        assert "lender_risk_table" in blocks
        assert "covenant" in blocks

        # Check DataFrame
        df = blocks["lender_risk_table"]
        assert isinstance(df, pd.DataFrame)

        # Check covenant block
        covenant = blocks["covenant"]
        assert "dscr_floor" in covenant
        assert "prob_breach" in covenant
        assert "worst_year_dscr_p95_downside" in covenant
        assert "n_trials" in covenant

        assert covenant["dscr_floor"] == 1.30
        assert covenant["n_trials"] == 100
        assert 0.0 <= covenant["prob_breach"] <= 1.0


class TestPandasRequirement:
    """Test pandas dependency handling."""

    @pytest.mark.skipif(HAS_PANDAS, reason="Test requires pandas to be missing")
    def test_build_lender_risk_table_requires_pandas(self):
        """Should raise RuntimeError if pandas not installed."""
        result = MonteCarloResult(
            summary={},
            metadata={},
            trials={"dscr_min": [1.32]},
        )

        with pytest.raises(RuntimeError) as exc_info:
            build_lender_risk_table(result)

        assert "pandas" in str(exc_info.value).lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
