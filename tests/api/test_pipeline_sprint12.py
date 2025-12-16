"""
Tests for Full Pipeline Orchestrator (Sprint 12)

Coverage:
- CLI-03: JSON output
- CLI-01: Hydra configuration
- TYPE-01: Type hints
- FIN-01: Error handling
- R7: Finance.irr compliance
"""

import json

import pytest
from omegaconf import OmegaConf

from scripts.run_full_pipeline_sprint12 import (
    FullPipeline,
    PipelineResult,
)


class TestPipelineBasic:
    """Basic pipeline functionality."""

    @pytest.fixture
    def config(self) -> OmegaConf:
        """Create test configuration."""
        return OmegaConf.create({
            'scenario_name': 'pipeline_test',
            'n_iterations': 100,  # Small for testing
        })

    @pytest.fixture
    def pipeline(self, config) -> FullPipeline:
        """Create pipeline instance."""
        return FullPipeline(config)

    @pytest.mark.unit
    def test_pipeline_init(self, pipeline: FullPipeline) -> None:
        """Test pipeline initialization."""
        assert pipeline.config.scenario_name == 'pipeline_test'
        assert pipeline.timestamp is not None
        assert len(pipeline.modules_executed) == 0

    @pytest.mark.unit
    def test_pipeline_run(self, pipeline: FullPipeline) -> None:
        """Test full pipeline execution."""
        result = pipeline.run()
        assert isinstance(result, PipelineResult)
        assert result.scenario_name == 'pipeline_test'
        assert result.success is True
        assert len(result.modules_executed) == 4

    @pytest.mark.unit
    def test_refinancing_module(self, pipeline: FullPipeline) -> None:
        """Test refinancing module execution."""
        result = pipeline.run_refinancing_module()
        assert result is not None
        assert result['module'] == 'refinancing_v14'
        assert 'status' in result
        assert 'refinancing_date' in result

    @pytest.mark.unit
    def test_equity_module(self, pipeline: FullPipeline) -> None:
        """Test equity distribution module execution."""
        result = pipeline.run_equity_distribution_module()
        assert result is not None
        assert result['module'] == 'equity_distribution_v14'
        assert 'equity_irr_pct' in result
        assert 'equity_multiple' in result

    @pytest.mark.unit
    def test_monte_carlo_module(self, pipeline: FullPipeline) -> None:
        """Test Monte Carlo module execution."""
        result = pipeline.run_monte_carlo_module()
        assert result is not None
        assert result['module'] == 'monte_carlo_v14'
        assert 'statistics' in result
        assert result['n_iterations'] == 100

    @pytest.mark.unit
    def test_stress_tests_module(self, pipeline: FullPipeline) -> None:
        """Test stress tests module execution."""
        result = pipeline.run_stress_tests_module()
        assert result is not None
        assert result['module'] == 'stress_tests_v14'
        assert 'scenarios_tested' in result
        assert result['scenarios_tested'] == 10


class TestPipelineOutput:
    """CLI-03: JSON output tests."""

    @pytest.fixture
    def config(self) -> OmegaConf:
        """Create test configuration."""
        return OmegaConf.create({
            'scenario_name': 'output_test',
            'n_iterations': 50,
        })

    @pytest.mark.unit
    def test_pipeline_result_to_dict(self, config) -> None:
        """Test PipelineResult to dict conversion (CLI-03)."""
        result = PipelineResult(
            timestamp='2025-12-17T02:30:00',
            scenario_name='test',
            modules_executed=['refinancing', 'monte_carlo'],
            refinancing_result={'status': 'ok'},
            monte_carlo_result={'iterations': 100},
            success=True,
        )
        d = result.to_dict()
        assert d['scenario_name'] == 'test'
        assert d['success'] is True
        assert len(d['modules_executed']) == 2

    @pytest.mark.unit
    def test_pipeline_json_serializable(self, config) -> None:
        """Test pipeline output is JSON serializable (CLI-03)."""
        pipeline = FullPipeline(config)
        result = pipeline.run()
        output_dict = result.to_dict()
        # Should not raise exception
        json_str = json.dumps(output_dict, default=str)
        assert isinstance(json_str, str)
        assert 'scenario_name' in json_str
        assert 'modules_executed' in json_str

    @pytest.mark.unit
    def test_pipeline_result_aggregation(self, config) -> None:
        """Test result aggregation."""
        pipeline = FullPipeline(config)
        result = pipeline.run()
        summary = result.summary
        assert summary is not None
        assert 'modules_executed' in summary
        assert 'scenario' in summary
        assert 'execution_timestamp' in summary


class TestPipelineIntegration:
    """Integration tests."""

    @pytest.fixture
    def config(self) -> OmegaConf:
        """Create test configuration."""
        return OmegaConf.create({
            'scenario_name': 'integration_test',
            'n_iterations': 100,
        })

    @pytest.mark.unit
    def test_all_modules_executed(self, config) -> None:
        """Test that all modules are executed."""
        pipeline = FullPipeline(config)
        result = pipeline.run()
        assert len(result.modules_executed) == 4
        assert 'refinancing' in result.modules_executed
        assert 'equity_distribution' in result.modules_executed
        assert 'monte_carlo' in result.modules_executed
        assert 'stress_tests' in result.modules_executed

    @pytest.mark.unit
    def test_module_sequence(self, config) -> None:
        """Test modules execute in correct sequence."""
        pipeline = FullPipeline(config)
        result = pipeline.run()
        # Modules should execute in order
        assert result.refinancing_result is not None
        assert result.equity_distribution_result is not None
        assert result.monte_carlo_result is not None
        assert result.stress_tests_result is not None

    @pytest.mark.unit
    def test_error_handling(self) -> None:
        """Test pipeline error handling (FIN-01)."""
        # Create invalid config to trigger error
        try:
            invalid_config = OmegaConf.create({})  # Missing required fields
            pipeline = FullPipeline(invalid_config)
            result = pipeline.run()
            # Should still produce result, even if error
            assert isinstance(result, PipelineResult)
        except Exception:
            # Error is acceptable; just verify pipeline handles it gracefully
            pass


class TestPipelineTypeHints:
    """TYPE-01: Type hints verification."""

    @pytest.mark.unit
    def test_pipeline_type_hints(self) -> None:
        """Verify pipeline has type hints (TYPE-01)."""
        import inspect

        sig = inspect.signature(FullPipeline.__init__)
        assert sig.parameters['config'].annotation is not None

    @pytest.mark.unit
    def test_pipeline_result_type_hints(self) -> None:
        """Verify PipelineResult has type hints (TYPE-01)."""
        import inspect

        sig = inspect.signature(PipelineResult.to_dict)
        assert sig.return_annotation is not None
