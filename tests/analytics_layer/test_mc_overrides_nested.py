"""
tests/analytics_layer/test_mc_overrides_nested.py

Regression tests for the fix to MonteCarloEngine._build_overrides_from_sample
(P0 Bug 1 — MC trials silently fell back to toy metrics because dot-notation
parameter names were not expanded into nested dicts before deep-merge).

GWTF compliance:
  - MRM-01 (Deterministic runs for stochastic components): fixed seed used
  - TEST-01 (Regression tests and pins for financial behaviour): pins added
  - FIN-01 (Numeric robustness): fallback path no longer activated silently
  - R23/R25 (branch + CI gate): this file ships on fix/p0-mc-overrides-not-nested
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import numpy as np
import pytest
import yaml

from analytics.mc.engine import MonteCarloEngine, run_monte_carlo_analysis

SCENARIO_PATH = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")


@pytest.fixture
def lendercase_config() -> Dict[str, Any]:
    cfg = yaml.safe_load(SCENARIO_PATH.read_text())
    cfg["monte_carlo"] = {
        "parameters": [
            {
                "name": "project.capacity_factor",
                "low": 0.38,
                "high": 0.47,
                "distribution": "uniform",
            },
            {
                "name": "Financing_Terms.rates.lkr_nominal",
                "low": 0.06,
                "high": 0.10,
                "distribution": "uniform",
            },
            {
                "name": "project.degradation",
                "low": 0.003,
                "high": 0.008,
                "distribution": "uniform",
            },
        ]
    }
    return cfg


@pytest.fixture
def minimal_flat_config() -> Dict[str, Any]:
    return {
        "scenario_name": "flat_param_test",
        "monte_carlo": {
            "parameters": [
                {
                    "name": "capex",
                    "low": 100.0,
                    "high": 120.0,
                    "distribution": "uniform",
                },
                {
                    "name": "tariff",
                    "low": 0.08,
                    "high": 0.12,
                    "distribution": "uniform",
                },
            ]
        },
    }


class TestBuildOverridesFromSample:
    """Unit tests for the fixed _build_overrides_from_sample static method."""

    def test_dotted_names_produce_nested_dict(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([0.42, 0.075, 0.005]),
            [
                "project.capacity_factor",
                "Financing_Terms.rates.lkr_nominal",
                "project.degradation",
            ],
        )
        assert result == {
            "project": {"capacity_factor": 0.42, "degradation": 0.005},
            "Financing_Terms": {"rates": {"lkr_nominal": 0.075}},
        }

    def test_flat_names_placed_at_top_level(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([110.0, 0.10]),
            ["capex", "tariff"],
        )
        assert result == {"capex": 110.0, "tariff": 0.10}

    def test_mixed_names(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([0.40, 115.0]),
            ["project.capacity_factor", "capex"],
        )
        assert result["project"]["capacity_factor"] == pytest.approx(0.40)
        assert result["capex"] == pytest.approx(115.0)

    def test_deep_three_level_nesting(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([0.08]),
            ["a.b.c"],
        )
        assert result == {"a": {"b": {"c": 0.08}}}

    def test_sibling_keys_merged_under_same_parent(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([0.40, 0.005]),
            ["project.capacity_factor", "project.degradation"],
        )
        assert result == {"project": {"capacity_factor": 0.40, "degradation": 0.005}}

    def test_empty_sample_returns_empty_dict(self):
        result = MonteCarloEngine._build_overrides_from_sample(np.array([]), [])
        assert result == {}

    def test_values_are_python_floats_not_numpy_scalars(self):
        result = MonteCarloEngine._build_overrides_from_sample(
            np.array([0.42]),
            ["project.capacity_factor"],
        )
        assert isinstance(result["project"]["capacity_factor"], float)


class TestMCEngineNoToyFallback:
    """Integration tests: with nested overrides, real pipeline runs must succeed."""

    def test_mc_run_produces_non_null_statistics(self, lendercase_config):
        """After fix: result.summary must contain project_irr and dscr_min stats.

        Pre-fix: all trials raised ValidationError (flat dot-notation keys never
        merged correctly) and fell to _toy_metric_fallback.  aggregate_trials saw
        only toy metrics, which do not include project_irr, so summary was empty.

        Post-fix: nested overrides pass schema guard -> real pipeline runs ->
        summary["project_irr"] and summary["dscr_min"] are both populated.
        """
        result = MonteCarloEngine(lendercase_config, seed=42).run(n_trials=50)

        assert (
            "project_irr" in result.summary
        ), "project_irr missing from summary — trials still falling to toy fallback"
        assert "dscr_min" in result.summary, "dscr_min missing from summary"
        assert result.summary["project_irr"]["mean"] > 0, "Mean IRR is zero or negative"
        assert (
            result.failed_iterations == 0
        ), f"{result.failed_iterations} trials failed — check override nesting"

    def test_mc_irr_in_plausible_range(self, lendercase_config):
        """IRR mean must fall within a plausible range given CF 0.38-0.47.

        #738 re-baseline: the committed lendercase now carries the PRUDENT import
        levies + 18% opex VAT (net of the revenue-SSCL exemption reversal), which
        pulls the sampled-CF mean project IRR from ~5.5% to the measured 4.736%
        (seed 42) — the lower plausibility bound moves 5% -> 3%, keeping >=1.3pp
        of margin BOTH ways (vs the 4.736% mean and vs the ~1.46% deterministic-
        canon / toy-fallback signature this test exists to catch).
        """
        result = MonteCarloEngine(lendercase_config, seed=42).run(n_trials=100)

        if "project_irr" not in result.summary:
            pytest.skip("project_irr not in summary — toy fallback still active")

        irr_stats = result.summary["project_irr"]
        assert (
            0.03 < irr_stats["mean"] < 0.35
        ), f"Mean IRR {irr_stats['mean']:.2%} outside plausible range [3%, 35%]"
        p10 = irr_stats["percentiles"][10]
        p90 = irr_stats["percentiles"][90]
        assert p10 < p90, f"P10 {p10:.2%} >= P90 {p90:.2%} — distribution inverted"

    def test_mc_deterministic_with_fixed_seed(self, lendercase_config):
        """Two runs with same seed must produce identical IRR mean (MRM-01)."""
        r1 = MonteCarloEngine(lendercase_config, seed=99).run(n_trials=30)
        r2 = MonteCarloEngine(lendercase_config, seed=99).run(n_trials=30)
        assert r1.summary.get("project_irr", {}).get("mean") == r2.summary.get(
            "project_irr", {}
        ).get("mean"), "Same seed produced different IRR means"

    def test_mc_different_seeds_differ(self, lendercase_config):
        """Different seeds must produce different mean IRR values."""
        r1 = MonteCarloEngine(lendercase_config, seed=1).run(n_trials=50)
        r2 = MonteCarloEngine(lendercase_config, seed=2).run(n_trials=50)
        irr1 = r1.summary.get("project_irr", {}).get("mean")
        irr2 = r2.summary.get("project_irr", {}).get("mean")
        if irr1 is None or irr2 is None:
            pytest.skip("project_irr not in summary")
        assert irr1 != irr2, "Different seeds produced identical IRR means"


class TestMCEngineBackwardCompatFlatParams:
    """Flat param names must still work — no regression."""

    def test_flat_params_engine_runs_without_error(self, minimal_flat_config):
        from omegaconf import OmegaConf

        cfg = OmegaConf.create(minimal_flat_config)
        engine = MonteCarloEngine(cfg, seed=42)
        result = engine.run(n_trials=10)
        assert result is not None

    def test_public_run_monte_carlo_analysis_api_unchanged(self, minimal_flat_config):
        result = run_monte_carlo_analysis(
            base_config=minimal_flat_config,
            n_trials=10,
            seed=42,
        )
        assert result is not None
