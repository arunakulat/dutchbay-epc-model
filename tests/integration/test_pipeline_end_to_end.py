#!/usr/bin/env python
"""End-to-end integration test for complete DutchBay pipeline.

Tests the full analytical pipeline:
1. Wind resource assessment (or mock data)
2. Cashflow model with degradation
3. Dual DSCR debt sizing
4. Monte Carlo simulation
5. Sensitivity analysis

Validates:
- Cross-module data flow
- Degradation propagation
- Performance benchmarks
- Output completeness
- NO REGRESSIONS

Framework Compliance:
- TEST-01: End-to-end regression pins
- CASPER: Complete tail-risk analysis
- Performance: < 60s for full pipeline

Author: DutchBay Integration Team
Date: December 2025 (Monte Carlo migrated to analytics.mc.engine API)
"""

import json
import math
import time

import pytest

# Import Monte Carlo pipeline modules (canonical engine: analytics.mc.engine).
# These are FIRST-PARTY analytics symbols (plus omegaconf, a hard Hydra dependency),
# not optional deps, so import them UNGUARDED: a rename or removal must fail loudly at
# collection, never be swallowed by a module-level skip that silently drops this
# module's end-to-end regression pins (round-2 audit). (The analytics.dscr_sensitivity
# import below stays guarded because it feeds a per-test @_REQUIRES_SENSITIVITY marker,
# not a whole-module skip.)
from omegaconf import OmegaConf  # noqa: F401  (configs come via fixtures)

from analytics.contracts_v14 import MonteCarloResult
from analytics.mc.engine import run_monte_carlo_analysis

# Import analytics.dscr_sensitivity behind an ImportError guard so a genuinely
# unavailable optional dependency skips the sensitivity-dependent tests (via the
# @_REQUIRES_SENSITIVITY marker) instead of erroring collection. Any OTHER
# exception is a real breakage and must fail loudly at import, not be masked.
try:
    from analytics.dscr_sensitivity import analyze_dscr_sensitivity

    _HAS_SENSITIVITY = True
    _SENSITIVITY_IMPORT_ERROR = ""
except ImportError as exc:  # pragma: no cover - environment-dependent
    analyze_dscr_sensitivity = None  # type: ignore[assignment]
    _HAS_SENSITIVITY = False
    _SENSITIVITY_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_REQUIRES_SENSITIVITY = pytest.mark.skipif(
    not _HAS_SENSITIVITY,
    reason=f"analytics.dscr_sensitivity unavailable ({_SENSITIVITY_IMPORT_ERROR})",
)


class TestPipelineDataFlow:
    """Test data flow across pipeline modules."""

    def test_wind_to_cashflow_data_flow(
        self, wind_assessment_mock_results, dutchbay_base_config
    ):
        """Wind assessment results should flow into cashflow model."""
        # Wind assessment outputs
        wind_aep_p50 = wind_assessment_mock_results["energy_production"]["net_aep"][
            "net_aep_p50_mwh"
        ]

        # These should match or update config
        config_aep_p50 = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]

        # Verify AEP values are in same ballpark
        assert abs(wind_aep_p50 - config_aep_p50) / config_aep_p50 < 0.1, (
            f"Wind AEP should be consistent: wind={wind_aep_p50/1e3:.0f}GWh, "
            f"config={config_aep_p50/1e3:.0f}GWh"
        )

    @_REQUIRES_SENSITIVITY
    def test_cashflow_to_dscr_data_flow(self, dutchbay_base_config):
        """Cashflow outputs should feed into dual DSCR sizing."""
        # Cashflow generates revenue projections
        aep = dutchbay_base_config["wind_resource"]["aep_p50_mwh"]
        tariff = dutchbay_base_config["revenue"]["tariff_usd_mwh"]
        opex = dutchbay_base_config["operations"]["opex_usd_year"]
        degradation = dutchbay_base_config["project"]["degradation"]

        # Build simple CFADS
        from analytics.dscr_sensitivity import _build_cfads_array

        cfads_p50 = _build_cfads_array(aep, tariff, opex, degradation, 20)

        # CFADS should be positive and reasonable
        assert all(cf > 0 for cf in cfads_p50), "CFADS should be positive"
        assert cfads_p50[0] > opex, "Year 1 CFADS should exceed OPEX"

    @_REQUIRES_SENSITIVITY
    def test_dscr_to_sensitivity_data_flow(self, dutchbay_omegaconf_config):
        """DSCR sizing results should feed into sensitivity analysis."""
        # @_REQUIRES_SENSITIVITY already skips if the module is unimportable; a
        # runtime error here is a real regression, not a skip.
        # Run sensitivity with degradation only (fast)
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation"]
        )

        # Should have base case debt sizing
        assert "sensitivity_config" in result
        assert "variables" in result

        # Base debt should be available
        base_result = result["variables"][0]
        assert "base_debt" in base_result
        assert base_result["base_debt"] > 0


class TestPipelineDegradationPropagation:
    """Test degradation propagates through entire pipeline."""

    def test_degradation_in_cashflow_layer(self, dutchbay_base_config):
        """Degradation should be applied in cashflow calculations."""
        degradation = dutchbay_base_config["project"]["degradation"]

        # Verify degradation is configured
        assert degradation > 0, "Degradation should be configured"
        assert degradation == 0.006, f"Expected 0.6%, got {degradation*100}%"

    def test_degradation_in_monte_carlo_layer(self, dutchbay_omegaconf_config):
        """Degradation should be sampled in Monte Carlo."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        assert "degradation_mean_pct" in mc_config
        assert mc_config.degradation_mean_pct == 0.6

    def test_degradation_in_sensitivity_layer(self, dutchbay_omegaconf_config):
        """Degradation should be a sensitivity variable."""
        sens_config = dutchbay_omegaconf_config.sensitivity

        assert "degradation" in sens_config.variables

    @pytest.mark.slow
    @_REQUIRES_SENSITIVITY
    def test_degradation_flows_to_outputs(self, dutchbay_omegaconf_config):
        """Degradation impact should be visible in final outputs."""
        # Run sensitivity analysis
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation"]
        )

        deg_result = result["variables"][0]

        # Should have degradation-specific outputs
        assert deg_result["variable"] == "degradation"
        assert "tornado_data" in deg_result

        # Impact should be measurable
        tornado = deg_result["tornado_data"]
        assert (
            tornado["range_pct"] > 2.0
        ), f"Degradation should have > 2% impact, got {tornado['range_pct']:.1f}%"


class TestPipelinePerformance:
    """Test pipeline performance benchmarks."""

    @pytest.mark.slow
    @pytest.mark.performance
    @_REQUIRES_SENSITIVITY
    def test_sensitivity_analysis_performance(
        self, dutchbay_omegaconf_config, performance_benchmarks
    ):
        """Sensitivity analysis should meet performance target."""
        # Use minimal variables for speed test
        start_time = time.time()

        analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation", "aep"]
        )

        execution_time = time.time() - start_time
        max_time = performance_benchmarks["sensitivity_analysis_max_seconds"]

        assert (
            execution_time < max_time
        ), f"Sensitivity should complete in < {max_time}s, took {execution_time:.1f}s"

    @pytest.mark.slow
    @pytest.mark.performance
    def test_monte_carlo_performance(self, mc_sampling_config, performance_benchmarks):
        """Monte Carlo should meet performance target."""
        cfg = mc_sampling_config

        start_time = time.perf_counter()
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=1000, seed=int(cfg.monte_carlo.seed)
        )
        execution_time = time.perf_counter() - start_time

        max_time = performance_benchmarks["monte_carlo_1k_max_seconds"]
        assert (
            execution_time < max_time
        ), f"MC 1K trials should complete in < {max_time}s, took {execution_time:.2f}s"
        assert result.metadata["n_trials"] == 1000

    @pytest.mark.slow
    @pytest.mark.performance
    @_REQUIRES_SENSITIVITY
    def test_full_pipeline_performance(
        self, dutchbay_omegaconf_config, mc_sampling_config, performance_benchmarks
    ):
        """Complete pipeline (sensitivity + Monte Carlo) should meet target."""
        start_time = time.perf_counter()

        # Run sensitivity (includes DSCR sizing)
        analyze_dscr_sensitivity(
            dutchbay_omegaconf_config,
            variables=["degradation", "aep"],
        )

        # Run Monte Carlo (small sample)
        run_monte_carlo_analysis(
            base_config=mc_sampling_config,
            n_trials=500,
            seed=int(mc_sampling_config.monte_carlo.seed),
        )

        execution_time = time.perf_counter() - start_time
        max_time = performance_benchmarks["full_pipeline_max_seconds"]

        assert (
            execution_time < max_time
        ), f"Full pipeline should complete in < {max_time}s, took {execution_time:.2f}s"


class TestPipelineOutputs:
    """Test pipeline output completeness and validity."""

    @pytest.mark.slow
    @_REQUIRES_SENSITIVITY
    def test_sensitivity_output_structure(self, dutchbay_omegaconf_config):
        """Sensitivity analysis should produce complete output."""
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config, variables=["degradation", "aep"]
        )

        # Required top-level keys
        assert "sensitivity_config" in result
        assert "variables" in result
        assert "tornado_chart" in result
        assert "summary" in result
        assert "binding_constraint_analysis" in result

        # Tornado chart should be sorted
        tornado = result["tornado_chart"]
        for i in range(1, len(tornado)):
            assert abs(tornado[i - 1]["impact_range"]) >= abs(
                tornado[i]["impact_range"]
            )

        # Summary should have key metrics
        summary = result["summary"]
        assert "most_sensitive_variable" in summary
        assert "base_debt" in summary
        assert summary["base_debt"] > 0

    @pytest.mark.slow
    def test_monte_carlo_output_structure(self, mc_sampling_config):
        """Monte Carlo should produce a complete MonteCarloResult."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=100, seed=int(cfg.monte_carlo.seed)
        )

        assert isinstance(result, MonteCarloResult)

        # Contract surfaces are populated
        assert result.summary, "summary should be populated"
        assert result.percentiles, "percentiles should be populated"
        assert result.trials, "raw trials should be populated"
        assert result.metadata["n_trials"] == 100

        # Each KPI summary block is complete and trial arrays are full length
        required_keys = {"mean", "std", "min", "max", "percentiles"}
        for metric, stats in result.summary.items():
            assert required_keys.issubset(stats), f"{metric} summary missing keys"
            assert len(result.trials[metric]) == 100

    @pytest.mark.slow
    def test_outputs_are_json_serializable(self, mc_sampling_config):
        """Monte Carlo outputs should be JSON-serializable."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=50, seed=int(cfg.monte_carlo.seed)
        )

        # MonteCarloResult is a dataclass; model_dump() (ContractMixin) yields a
        # plain, JSON-serializable mapping.
        try:
            dumped = json.dumps(result.model_dump(), indent=2)
        except TypeError as e:
            pytest.fail(f"MonteCarloResult not JSON-serializable: {e}")
        assert len(dumped) > 0

        # The curated attribute payload should also serialize cleanly
        payload = {
            "summary": result.summary,
            "percentiles": result.percentiles,
            "metadata": result.metadata,
            "trials": result.trials,
        }
        assert len(json.dumps(payload)) > 0


class TestPipelineRegressionPins:
    """Regression pins for end-to-end pipeline (TEST-01 compliance)."""

    @pytest.mark.slow
    def test_dutchbay_baseline_npv(self, mc_sampling_config):
        """Baseline project-NPV distribution: reproducible and well-formed.

        The integration config exercises the engine's deterministic toy-metric
        fallback, so this pins the distribution's reproducibility and shape
        (TEST-01) rather than a specific dollar NPV — financial magnitudes are
        covered by evaluation/golden tests, not this engine-machinery test.
        """
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)

        first = run_monte_carlo_analysis(base_config=cfg, n_trials=500, seed=seed)
        second = run_monte_carlo_analysis(base_config=cfg, n_trials=500, seed=seed)

        assert first.trials["project_npv"] == second.trials["project_npv"]
        npv = first.summary["project_npv"]
        assert math.isfinite(npv["mean"]) and math.isfinite(npv["std"])
        assert (
            npv["percentiles"][10] <= npv["percentiles"][50] <= npv["percentiles"][90]
        )

    @pytest.mark.slow
    def test_dutchbay_baseline_irr(self, mc_sampling_config):
        """Baseline project-IRR distribution: reproducible and well-formed (TEST-01)."""
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)

        first = run_monte_carlo_analysis(base_config=cfg, n_trials=500, seed=seed)
        second = run_monte_carlo_analysis(base_config=cfg, n_trials=500, seed=seed)

        assert first.trials["project_irr"] == second.trials["project_irr"]
        irr = first.summary["project_irr"]
        assert math.isfinite(irr["mean"]) and math.isfinite(irr["std"])
        assert (
            irr["percentiles"][10] <= irr["percentiles"][50] <= irr["percentiles"][90]
        )

    @pytest.mark.slow
    @_REQUIRES_SENSITIVITY
    def test_dutchbay_debt_capacity(self, dutchbay_omegaconf_config):
        """DutchBay sized debt should be a sensible fraction of CAPEX.

        Availability of analytics.dscr_sensitivity is handled by the
        ``@_REQUIRES_SENSITIVITY`` marker, so the analysis is invoked directly:
        a runtime error is a real failure, not a skip.
        """
        result = analyze_dscr_sensitivity(
            dutchbay_omegaconf_config,
            variables=["degradation"],
        )

        base_debt_m = result["summary"]["base_debt"] / 1e6
        capex_m = dutchbay_omegaconf_config.project.capex_usd / 1e6
        debt_ratio = base_debt_m / capex_m

        # Regression pin (TEST-01): the P99-downside dual-DSCR sizing is
        # conservative, so the DutchBay gearing lands near ~45% of CAPEX.
        assert (
            0.40 < debt_ratio < 0.75
        ), f"Debt ratio should be 40-75% of CAPEX, got {debt_ratio:.1%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
