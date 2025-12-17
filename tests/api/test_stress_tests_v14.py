"""
Tests for Stress Testing Module (v14)

Coverage:
- TEST-01: Regression validation
- R7: Finance.irr compliance
- TYPE-01: Type hints
- CLI-03: JSON serialization
- FIN-01: Edge cases
"""

import json

import pytest

from analytics.stress_tests_v14 import (
    StressResult,
    StressScenario,
    StressTestEngine,
)


class TestStressTestsBasic:
    """Basic stress test functionality (TEST-01)."""

    @pytest.fixture
    def engine(self) -> StressTestEngine:
        """Create test engine (TEST-01 regression)."""
        base_cfs = [-100_000, 25_000, 25_000, 25_000, 25_000]
        return StressTestEngine(
            base_cash_flows=base_cfs,
            base_discount_rate=0.08,
            time_periods=30,
        )

    def test_stress_engine_init(self, engine: StressTestEngine) -> None:
        """Test engine initialization."""
        assert engine.base_discount_rate == 0.08
        assert len(engine.base_cash_flows) == 5
        assert engine.base_npv != 0
        assert engine.base_irr > 0

    def test_interest_rate_shock_up(self, engine: StressTestEngine) -> None:
        """Test upward rate shock."""
        shocked_rate = engine.apply_interest_rate_shock(200)  # +2%
        assert shocked_rate == 0.10
        assert shocked_rate > engine.base_discount_rate

    def test_interest_rate_shock_down(self, engine: StressTestEngine) -> None:
        """Test downward rate shock."""
        shocked_rate = engine.apply_interest_rate_shock(-200)  # -2%
        assert shocked_rate == 0.06
        assert shocked_rate < engine.base_discount_rate

    def test_market_downturn(self, engine: StressTestEngine) -> None:
        """Test market downturn application."""
        shocked_cfs = engine.apply_market_downturn(0.20)  # 20% decline
        assert len(shocked_cfs) == len(engine.base_cash_flows)
        assert shocked_cfs[1] == engine.base_cash_flows[1] * 0.80

    def test_inflation_stress(self, engine: StressTestEngine) -> None:
        """Test inflation stress."""
        cfs, rate = engine.apply_inflation_stress(0.04)
        assert len(cfs) == len(engine.base_cash_flows)
        assert rate > engine.base_discount_rate  # Rate increases with inflation

    def test_run_single_scenario(self, engine: StressTestEngine) -> None:
        """Test single scenario execution (TEST-01)."""
        result = engine.run_scenario(StressScenario.RATE_SHOCK_UP_2PCT)
        assert isinstance(result, StressResult)
        assert result.scenario == "rate_shock_up_2pct"
        assert result.base_npv_usd == engine.base_npv
        assert result.stressed_npv_usd <= result.base_npv_usd  # Should decrease


class TestStressTestsR7Compliance:
    """R7 compliance tests (finance.irr usage - CRITICAL)."""

    @pytest.mark.critical_error
    def test_r7_uses_finance_irr(self) -> None:
        """Verify finance.irr is used (R7 - CRITICAL)."""
        from finance.irr import irr, npv

        base_cfs = [-100_000, 30_000, 30_000, 30_000, 30_000]
        engine = StressTestEngine(base_cfs, 0.08)

        # Verify engine uses finance.irr
        assert engine.base_npv == npv(0.08, base_cfs)
        assert abs(engine.base_irr - irr(base_cfs) * 100) < 0.01


class TestStressTestsScenarios:
    """Test all 10 stress scenarios (TEST-01)."""

    @pytest.fixture
    def engine(self) -> StressTestEngine:
        """Create test engine."""
        base_cfs = [-100_000, 25_000, 25_000, 25_000, 25_000]
        return StressTestEngine(base_cfs, 0.08, 30)

    @pytest.mark.unit
    def test_scenario_rate_shock_up_2pct(self, engine: StressTestEngine) -> None:
        """Test rate shock +2%."""
        result = engine.run_scenario(StressScenario.RATE_SHOCK_UP_2PCT)
        assert result.stressed_npv_usd < result.base_npv_usd

    @pytest.mark.unit
    def test_scenario_rate_shock_up_5pct(self, engine: StressTestEngine) -> None:
        """Test rate shock +5%."""
        result = engine.run_scenario(StressScenario.RATE_SHOCK_UP_5PCT)
        assert result.stressed_npv_usd < result.base_npv_usd

    @pytest.mark.unit
    def test_scenario_market_downturn_20pct(self, engine: StressTestEngine) -> None:
        """Test 20% market downturn."""
        result = engine.run_scenario(StressScenario.MARKET_DOWNTURN_20PCT)
        # 20% decline in cash flows leads to ~20% NPV decline (TEST-01 regression)
        assert result.npv_change_pct < -5  # Conservative threshold

    @pytest.mark.unit
    def test_scenario_market_downturn_40pct(self, engine: StressTestEngine) -> None:
        """Test 40% market downturn."""
        result = engine.run_scenario(StressScenario.MARKET_DOWNTURN_40PCT)
        # 40% decline in cash flows leads to ~40% NPV decline (TEST-01 regression)
        assert result.npv_change_pct < -15  # Conservative threshold

    @pytest.mark.unit
    def test_scenario_inflation_6pct(self, engine: StressTestEngine) -> None:
        """Test 6% inflation."""
        result = engine.run_scenario(StressScenario.INFLATION_6PCT)
        # Inflation raises discount rate and reduces cash flows
        assert result.irr_change_bps != 0  # Should have some impact

    @pytest.mark.unit
    def test_scenario_combined_severe(self, engine: StressTestEngine) -> None:
        """Test combined severe scenario."""
        result = engine.run_scenario(StressScenario.COMBINED_SEVERE)
        # Combined: 30% downturn + 4% inflation + 3% rate shock = ~40%+ impact (TEST-01)
        assert result.npv_change_pct < -20  # Conservative threshold

    @pytest.mark.unit
    def test_run_all_scenarios(self, engine: StressTestEngine) -> None:
        """Test all scenarios at once (TEST-01)."""
        results = engine.run_all_scenarios()
        assert len(results) == len(StressScenario)
        assert all(isinstance(r, StressResult) for r in results)


class TestStressTestsSerialization:
    """CLI-03: JSON serialization tests."""

    @pytest.mark.unit
    def test_stress_result_to_dict(self) -> None:
        """Test StressResult to dict conversion."""
        result = StressResult(
            scenario="test",
            base_npv_usd=100_000,
            stressed_npv_usd=95_000,
            npv_change_usd=-5_000,
            npv_change_pct=-5.0,
            base_irr_pct=12.5,
            stressed_irr_pct=11.8,
            irr_change_bps=-70,
            var_95_usd=4_750,
            cvar_95_usd=5_937,
            break_even_point=None,
        )
        d = result.to_dict()
        assert d["scenario"] == "test"
        assert d["npv_change_pct"] == -5.0

    @pytest.mark.unit
    def test_export_to_json(self) -> None:
        """Test JSON export (CLI-03)."""
        base_cfs = [-100_000, 25_000, 25_000, 25_000, 25_000]
        engine = StressTestEngine(base_cfs, 0.08)
        results = [engine.run_scenario(StressScenario.RATE_SHOCK_UP_2PCT)]

        json_str = engine.export_to_json(results)
        data = json.loads(json_str)

        assert "base_metrics" in data
        assert "stress_results" in data
        assert len(data["stress_results"]) == 1


class TestStressTestsEdgeCases:
    """FIN-01: Edge cases and error handling."""

    @pytest.mark.unit
    def test_edge_case_zero_cf(self) -> None:
        """Test handling of zero cash flows (FIN-01)."""
        cfs = [0, 0, 0, 0, 0]
        engine = StressTestEngine(cfs, 0.08)
        assert engine.base_npv == 0

    @pytest.mark.unit
    def test_edge_case_negative_irr(self) -> None:
        """Test handling of negative IRR scenarios (FIN-01)."""
        cfs = [-100_000, 10_000, 10_000, 10_000]
        engine = StressTestEngine(cfs, 0.08)
        result = engine.run_scenario(StressScenario.MARKET_DOWNTURN_60PCT)
        # Should handle gracefully (no exceptions)
        assert isinstance(result, StressResult)

    @pytest.mark.unit
    def test_rate_capping(self) -> None:
        """Test rate shock capping (FIN-01)."""
        engine = StressTestEngine([-100_000, 25_000], 0.08)

        # Test upper cap (50%)
        high_rate = engine.apply_interest_rate_shock(5000)  # +50%
        assert high_rate <= 0.5

        # Test lower cap (0.1%)
        low_rate = engine.apply_interest_rate_shock(-1000)  # -10%
        assert low_rate >= 0.001


@pytest.mark.monte_carlo
class TestStressTestsTypeHints:
    """TYPE-01: Verify type hints."""

    @pytest.mark.unit
    def test_type_hints_engine(self) -> None:
        """Verify engine has type hints (TYPE-01)."""
        import inspect

        sig = inspect.signature(StressTestEngine.__init__)
        # Check return annotation
        assert sig.return_annotation is None

    @pytest.mark.unit
    def test_type_hints_methods(self) -> None:
        """Verify method type hints (TYPE-01)."""
        import inspect

        sig = inspect.signature(StressTestEngine.run_scenario)
        # Verify return type hint present
        assert "StressResult" in str(sig.return_annotation)
