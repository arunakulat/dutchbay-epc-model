#!/usr/bin/env python
"""Integration tests for the canonical Monte Carlo engine.

Exercises ``analytics.mc.engine`` (``run_monte_carlo_analysis`` /
``MonteCarloEngine``) end to end and verifies the ``MonteCarloResult`` contract:

1. The engine runs via the current API and returns a ``MonteCarloResult``
   dataclass (not a dict).
2. Aggregated KPI distributions (``project_npv`` / ``project_irr`` / ``dscr_min``
   / ``llcr`` / ``plcr``) are populated with summary statistics and raw trials.
3. Percentiles are correctly ordered (P10 <= P50 <= P90).
4. Runs are reproducible for a fixed seed (CASPER determinism / TEST-01).
5. Performance benchmarks are met.

Framework Compliance:
- TEST-01: Regression pins for MC behaviour (contract shape + determinism)
- CASPER: Deterministic, reproducible tail-risk distributions
- Performance: < 10s for 1K trials

Note on scope:
    The integration config (``mc_sampling_config``) is intentionally not the
    full v14 finance schema, so the engine exercises its deterministic
    toy-metric fallback. These tests therefore pin the engine *machinery* and
    *result contract* — sampling, aggregation, percentiles, determinism — not
    specific financial magnitudes (which belong to evaluation/golden tests).

Author: DutchBay Integration Team
Date: December 2025 (migrated to analytics.mc.engine API)
"""

import math
import time

import pytest

# Import modules to test
try:
    from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis
    from analytics.contracts_v14 import MonteCarloResult
    from omegaconf import OmegaConf  # noqa: F401  (used implicitly via fixtures)
except ImportError as e:
    pytest.skip(f"Required modules not available: {e}", allow_module_level=True)


# Canonical KPI keys the aggregator produces. The toy fallback now emits the SAME 7-key
# set a real trial returns (incl. equity_irr / equity_npv) so mixed real+toy runs build
# uniform-length arrays and never trip the equal-length guard (Wave-2 MC robustness fix).
EXPECTED_KPIS = {
    "project_npv",
    "project_irr",
    "equity_irr",
    "equity_npv",
    "dscr_min",
    "llcr",
    "plcr",
}
EXPECTED_PERCENTILE_LEVELS = {5, 10, 50, 90, 95}


class TestMonteCarloConfiguration:
    """Validate the *legacy config shape* of the lender-case fixture.

    These pin that ``dutchbay_omegaconf_config.monte_carlo`` still carries the
    historical fields (``degradation_mean_pct``, ``correlation_matrix`` ...).
    Note: the canonical engine (``analytics.mc.engine``) does not consume these
    fields — it reads ``monte_carlo.parameters`` and nested
    ``monte_carlo.degradation.enabled`` — so these are config-shape checks, not
    engine-behaviour coverage (which the other classes in this module provide).
    """

    def test_mc_config_includes_degradation(self, dutchbay_omegaconf_config) -> None:
        """Monte Carlo config should include degradation parameters."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        assert mc_config.enabled is True
        assert "degradation_mean_pct" in mc_config
        assert "degradation_std_pct" in mc_config

        # Values should be reasonable
        assert 0.4 <= mc_config.degradation_mean_pct <= 0.8
        assert 0.05 <= mc_config.degradation_std_pct <= 0.2

    def test_mc_config_has_correlation_matrix(self, dutchbay_omegaconf_config) -> None:
        """Monte Carlo should have 4x4 correlation matrix."""
        mc_config = dutchbay_omegaconf_config.monte_carlo

        if mc_config.correlation_enabled:
            corr_matrix = mc_config.correlation_matrix

            # Should be 4x4 (revenue, cost, FX, degradation)
            assert len(corr_matrix) == 4
            assert all(len(row) == 4 for row in corr_matrix)

            # Diagonal should be 1.0
            for i in range(4):
                assert corr_matrix[i][i] == 1.0

            # Should be symmetric
            for i in range(4):
                for j in range(4):
                    assert abs(corr_matrix[i][j] - corr_matrix[j][i]) < 1e-10


class TestMonteCarloExecution:
    """Test Monte Carlo execution and the MonteCarloResult contract."""

    @pytest.mark.slow
    def test_monte_carlo_runs_successfully(self, mc_sampling_config) -> None:
        """Engine should run via the current API and return a MonteCarloResult.

        Exercises the class API directly: ``MonteCarloEngine(cfg, seed=...)``
        followed by ``.run(n_trials=...)`` (n_trials is a run() argument, not a
        constructor argument).
        """
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)

        engine = MonteCarloEngine(cfg, seed=seed)
        result = engine.run(n_trials=100)

        assert isinstance(result, MonteCarloResult)
        assert result.metadata["n_trials"] == 100
        assert result.metadata["seed"] == seed
        assert result.summary, "summary should be populated"
        assert EXPECTED_KPIS.issubset(set(result.summary))

    @pytest.mark.slow
    def test_monte_carlo_produces_npv_distribution(self, mc_sampling_config) -> None:
        """Monte Carlo should produce a project NPV distribution."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=200, seed=int(cfg.monte_carlo.seed)
        )

        assert "project_npv" in result.summary
        npv = result.summary["project_npv"]
        for key in ("mean", "std", "min", "max", "percentiles"):
            assert key in npv, f"summary['project_npv'] missing '{key}'"

        assert math.isfinite(npv["mean"])
        assert math.isfinite(npv["std"])
        # Parameters are varied across trials, so the distribution is non-degenerate
        assert npv["std"] > 0, "NPV std should be positive when inputs vary"

        # Raw per-trial array is captured for lender analytics
        assert len(result.trials["project_npv"]) == 200

    @pytest.mark.slow
    def test_monte_carlo_produces_irr_distribution(self, mc_sampling_config) -> None:
        """Monte Carlo should produce a project IRR distribution."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=200, seed=int(cfg.monte_carlo.seed)
        )

        assert "project_irr" in result.summary
        irr = result.summary["project_irr"]
        for key in ("mean", "std", "percentiles"):
            assert key in irr, f"summary['project_irr'] missing '{key}'"

        assert math.isfinite(irr["mean"])
        assert irr["std"] > 0
        assert len(result.trials["project_irr"]) == 200


class TestMonteCarloStatistics:
    """Test Monte Carlo statistical outputs."""

    @pytest.mark.slow
    def test_percentiles_ordered_correctly(self, mc_sampling_config) -> None:
        """P10 <= P50 <= P90 ordering should hold for every KPI."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=500, seed=int(cfg.monte_carlo.seed)
        )

        for metric in ("project_npv", "project_irr", "dscr_min"):
            pct = result.summary[metric]["percentiles"]
            assert pct[10] <= pct[50] <= pct[90], (
                f"{metric} percentiles out of order: "
                f"P10={pct[10]:.4g}, P50={pct[50]:.4g}, P90={pct[90]:.4g}"
            )

        # The result-level percentile lookup table exposes the same levels
        assert EXPECTED_PERCENTILE_LEVELS.issubset(set(result.percentiles))
        for level in EXPECTED_PERCENTILE_LEVELS:
            assert "project_npv" in result.percentiles[level]

    @pytest.mark.slow
    def test_reproducible_with_fixed_seed(self, mc_sampling_config) -> None:
        """Same seed + config must produce identical results (CASPER / TEST-01).

        This replaces the old "median close to mean" heuristic with the
        engine's real determinism guarantee, which is the meaningful
        regression pin for a seeded Latin Hypercube sampler.
        """
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)

        first = run_monte_carlo_analysis(base_config=cfg, n_trials=300, seed=seed)
        second = run_monte_carlo_analysis(base_config=cfg, n_trials=300, seed=seed)

        assert first.trials == second.trials, "trials must be identical for a fixed seed"
        assert first.summary == second.summary, "summary must be identical for a fixed seed"

        # A different seed must change the draws
        other = run_monte_carlo_analysis(base_config=cfg, n_trials=300, seed=seed + 1)
        assert first.trials != other.trials, "different seed should change the draws"


class TestMonteCarloPerformance:
    """Test Monte Carlo performance benchmarks."""

    @pytest.mark.slow
    def test_1k_trials_performance(self, mc_sampling_config, performance_benchmarks) -> None:
        """1,000 trials should complete within the performance target."""
        cfg = mc_sampling_config

        start_time = time.perf_counter()
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=1000, seed=int(cfg.monte_carlo.seed)
        )
        execution_time = time.perf_counter() - start_time

        max_time = performance_benchmarks["monte_carlo_1k_max_seconds"]
        assert execution_time < max_time, (
            f"1K trials should complete in < {max_time}s, took {execution_time:.2f}s"
        )
        assert result.metadata["n_trials"] == 1000

    @pytest.mark.slow
    @pytest.mark.performance
    def test_10k_trials_performance(self, mc_sampling_config, performance_benchmarks) -> None:
        """10,000 trials should complete within the performance target."""
        cfg = mc_sampling_config

        start_time = time.perf_counter()
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=10000, seed=int(cfg.monte_carlo.seed)
        )
        execution_time = time.perf_counter() - start_time

        max_time = performance_benchmarks["monte_carlo_10k_max_seconds"]
        assert execution_time < max_time, (
            f"10K trials should complete in < {max_time}s, took {execution_time:.2f}s"
        )
        assert len(result.trials["project_npv"]) == 10000

    @pytest.mark.slow
    def test_trials_per_second_rate(self, mc_sampling_config) -> None:
        """Should achieve a minimum trials-per-second rate."""
        cfg = mc_sampling_config

        n_trials = 500
        start_time = time.perf_counter()
        run_monte_carlo_analysis(
            base_config=cfg, n_trials=n_trials, seed=int(cfg.monte_carlo.seed)
        )
        execution_time = time.perf_counter() - start_time

        trials_per_second = n_trials / execution_time
        assert trials_per_second > 100, (
            f"Should achieve > 100 trials/s, got {trials_per_second:.0f} trials/s"
        )


class TestMonteCarloDegradationIntegration:
    """Test the degradation hook in the current Monte Carlo engine."""

    @pytest.mark.slow
    def test_degradation_hook_is_documented_noop_on_toy_path(self, mc_sampling_config) -> None:
        """Pin the current degradation-hook behaviour (TEST-01).

        The current engine wires degradation through
        ``analytics.mc.degradation.apply_degradation_if_enabled``, which keys
        off ``monte_carlo.degradation.enabled`` (a nested block) and injects a
        ``wind.degradation_rate`` override. The legacy "degradation_std_pct
        widens the NPV distribution" behaviour belonged to the removed engine
        and no longer applies. On the toy-fallback path the injected override is
        not consumed, so enabling degradation is a *documented no-op* on the
        KPIs. We pin exactly that: the hook runs cleanly and yields KPI trials
        byte-identical to a run with degradation disabled, so a future
        behavioural change here is caught.
        """
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)

        # Baseline: degradation hook disabled (no monte_carlo.degradation block)
        baseline = run_monte_carlo_analysis(base_config=cfg, n_trials=200, seed=seed)

        # Enable the nested degradation hook and re-run with the same seed
        cfg.monte_carlo.degradation = {"enabled": True, "default_rate": 0.006}
        with_degradation = run_monte_carlo_analysis(base_config=cfg, n_trials=200, seed=seed)

        assert isinstance(with_degradation, MonteCarloResult)
        assert EXPECTED_KPIS.issubset(set(with_degradation.summary))
        assert len(with_degradation.trials["project_npv"]) == 200
        # Documented no-op on the toy path: identical KPI trials with/without
        assert with_degradation.trials == baseline.trials


class TestMonteCarloRegressionPins:
    """Regression pins for the MonteCarloResult contract (TEST-01)."""

    @pytest.mark.slow
    def test_canonical_kpis_present(self, mc_sampling_config) -> None:
        """The aggregator should expose exactly the canonical toy-fallback KPIs."""
        cfg = mc_sampling_config
        result = run_monte_carlo_analysis(
            base_config=cfg, n_trials=200, seed=int(cfg.monte_carlo.seed)
        )

        assert set(result.summary) == EXPECTED_KPIS
        assert set(result.trials) == EXPECTED_KPIS
        # All trial arrays share the same length
        lengths = {len(v) for v in result.trials.values()}
        assert lengths == {200}

    @pytest.mark.slow
    def test_metadata_records_run_parameters(self, mc_sampling_config) -> None:
        """Run metadata should faithfully record the seed/trials/sampler/params."""
        cfg = mc_sampling_config
        seed = int(cfg.monte_carlo.seed)
        result = run_monte_carlo_analysis(base_config=cfg, n_trials=250, seed=seed)

        meta = result.metadata
        assert meta["n_trials"] == 250
        assert meta["seed"] == seed
        assert meta["sampler"] == "lhs"
        assert meta["param_names"] == ["capex", "tariff", "capacity_factor", "opex_annual"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_degradation_hook_drives_live_project_degradation_key() -> None:
    """The MC degradation hook now writes the LIVE engine key project.degradation (was the
    dead wind.degradation_rate, silently ignored). Default-off returns overrides unchanged."""
    from analytics.mc.degradation import apply_degradation_if_enabled

    off = apply_degradation_if_enabled(
        base_cfg={"monte_carlo": {"degradation": {"enabled": False}}}, overrides={}
    )
    assert off == {}  # disabled -> no-op
    on = apply_degradation_if_enabled(
        base_cfg={"monte_carlo": {"degradation": {"enabled": True, "default_rate": 0.6}}},
        overrides={},
    )
    assert on == {"project.degradation": 0.6}  # live key, not wind.degradation_rate
    assert "wind.degradation_rate" not in on


def test_degradation_hook_does_not_clobber_a_sampled_value() -> None:
    """An MC SAMPLED degradation draw (flat OR nested) must NOT be overwritten by the static
    default_rate — the round-2 clobber bug collapsed the degradation distribution to a
    constant. Only inject the default when no sampled value is present."""
    from analytics.mc.degradation import apply_degradation_if_enabled

    base = {"monte_carlo": {"degradation": {"enabled": True, "default_rate": 0.6}}}
    # nested form (as MC overrides arrive): the 0.9 draw survives, no flat clobber key
    nested = apply_degradation_if_enabled(base_cfg=base, overrides={"project": {"degradation": 0.9}})
    assert nested == {"project": {"degradation": 0.9}}
    # flat form: the sampled flat key survives
    flat = apply_degradation_if_enabled(base_cfg=base, overrides={"project.degradation": 0.9})
    assert flat["project.degradation"] == 0.9
    # absent: the default is injected on the live key
    absent = apply_degradation_if_enabled(base_cfg=base, overrides={})
    assert absent == {"project.degradation": 0.6}
