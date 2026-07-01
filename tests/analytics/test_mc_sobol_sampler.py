"""Optional Sobol' QMC sampler (#589) — analytics/mc/samplers.generate_sobol_samples.

Sobol is an OPT-IN alternative to the canonical LHS path (monte_carlo.sampler: "sobol").
Default stays "lhs" -> byte-identical to every existing run (guarded here and in the oracle).
Sobol keeps its low-discrepancy balance only at n = 2**m, so a requested trial count is
rounded UP to the next power of two and all 2**m points are used.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine
from analytics.mc.samplers import generate_lhs_samples, generate_sobol_samples

_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _load() -> dict:
    return yaml.safe_load(_SCENARIO.read_text())


BOUNDS = [(0.0, 1.0), (10.0, 20.0), (-5.0, 5.0)]


class TestSobolSampler:
    def test_rounds_up_to_power_of_two_and_stays_in_bounds(self) -> None:
        x = generate_sobol_samples(n_trials=300, bounds=BOUNDS, seed=123)
        # 2**9 = 512 is the smallest power of two >= 300.
        assert x.shape == (512, 3)
        assert math.log2(x.shape[0]).is_integer()
        for j, (lo, hi) in enumerate(BOUNDS):
            assert x[:, j].min() >= lo
            assert x[:, j].max() <= hi

    def test_exact_power_of_two_is_not_inflated(self) -> None:
        assert (
            generate_sobol_samples(n_trials=256, bounds=BOUNDS, seed=7).shape[0] == 256
        )

    def test_deterministic_given_seed(self) -> None:
        a = generate_sobol_samples(n_trials=128, bounds=BOUNDS, seed=42)
        b = generate_sobol_samples(n_trials=128, bounds=BOUNDS, seed=42)
        c = generate_sobol_samples(n_trials=128, bounds=BOUNDS, seed=43)
        assert np.array_equal(a, b)
        assert not np.array_equal(a, c)

    def test_rejects_bad_inputs(self) -> None:
        with pytest.raises(ValueError, match="n_trials must be > 0"):
            generate_sobol_samples(n_trials=0, bounds=BOUNDS)
        with pytest.raises(ValueError, match="bounds must be non-empty"):
            generate_sobol_samples(n_trials=16, bounds=[])

    def test_lower_discrepancy_than_lhs(self) -> None:
        """The whole point of QMC: a Sobol net is more uniform (lower discrepancy) than an
        equal-size random-permutation LHS draw."""
        qmc = pytest.importorskip("scipy.stats.qmc")
        n = 256
        sob = generate_sobol_samples(n_trials=n, bounds=[(0.0, 1.0)] * 3, seed=1)
        lhs = generate_lhs_samples(n_trials=n, bounds=[(0.0, 1.0)] * 3, seed=1)
        assert qmc.discrepancy(sob) < qmc.discrepancy(lhs)

    def test_pinned_dimension_yields_constant_column(self) -> None:
        """A pinned driver (lo == hi) is an engine-accepted config shape (bounds validator only
        rejects lo > hi). It must NOT crash Sobol — scipy.qmc.scale requires strict lo < hi, so
        the affine map is used instead, giving a constant column exactly like LHS (Fable #589).
        """
        x = generate_sobol_samples(
            n_trials=64, bounds=[(0.0, 1.0), (2.5, 2.5), (-5.0, 5.0)]
        )
        assert x.shape == (64, 3)
        assert np.all(x[:, 1] == 2.5)  # pinned column is exactly constant
        assert x[:, 0].min() >= 0.0 and x[:, 0].max() <= 1.0  # other dims still swept


class TestEngineSamplerSwitch:
    def test_default_sampler_is_lhs(self) -> None:
        # Byte-identical guard: the shipped canonical never opts in, so the sampler stays lhs.
        assert MonteCarloEngine(_load(), seed=1)._sampler == "lhs"

    def test_invalid_sampler_raises(self) -> None:
        cfg = copy.deepcopy(_load())
        cfg["monte_carlo"]["sampler"] = "halton"
        with pytest.raises(MonteCarloConfigError, match="must be 'lhs' or 'sobol'"):
            MonteCarloEngine(cfg, seed=1)

    def test_sampler_value_is_case_and_whitespace_normalized(self) -> None:
        # A YAML value like "  SOBOL  " must normalize to "sobol" (guards against a future
        # refactor silently dropping the .strip().lower() and mis-routing opted-in configs).
        cfg = copy.deepcopy(_load())
        cfg["monte_carlo"]["sampler"] = "  SOBOL  "
        assert MonteCarloEngine(cfg, seed=1)._sampler == "sobol"

    def test_sobol_run_records_rounding_in_metadata(self) -> None:
        cfg = copy.deepcopy(_load())
        cfg["monte_carlo"]["sampler"] = "sobol"
        eng = MonteCarloEngine(cfg, seed=123)
        assert eng._sampler == "sobol"
        res = eng.run(n_trials=48)  # -> 64 = 2**6
        meta = res.metadata
        assert meta["sampler"] == "sobol"
        assert meta["n_trials"] == 64
        assert meta["sobol_n_requested"] == 48
        assert meta["sobol_n_used"] == 64
        assert res.failed_iterations == 0

    def test_sobol_exact_power_of_two_omits_rounding_keys(self) -> None:
        cfg = copy.deepcopy(_load())
        cfg["monte_carlo"]["sampler"] = "sobol"
        res = MonteCarloEngine(cfg, seed=123).run(n_trials=64)
        assert res.metadata["n_trials"] == 64
        assert "sobol_n_requested" not in res.metadata  # no rounding -> no noise keys
