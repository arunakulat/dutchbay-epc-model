"""Non-uniform MC sampler shapes (capability/provenance audit #19/#59/#85).

The declared per-parameter `distribution` was decorative: the sampler produced uniform draws
regardless. The engine now honors triangular / normal / lognormal via a unit-LHS-draw +
inverse-CDF transform (so the shape stays inside the stratified-LHS / CRN / correlation
machinery), and FAILS LOUD on an unrecognised shape instead of silently sampling uniform.
All shipped scenarios use `uniform`, so this is additive / byte-identical.
"""

from __future__ import annotations

import copy
import logging
import statistics
from pathlib import Path

import pytest
import yaml

from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine, _inv_cdf_shaped

_SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _load() -> dict:
    return yaml.safe_load(_SCENARIO.read_text())


class TestInverseCdf:
    def test_triangular_peaks_at_mode_and_is_monotone(self) -> None:
        xs = [
            _inv_cdf_shaped(u / 1000, "triangular", 100.0, 200.0, 150.0)
            for u in range(1, 1000)
        ]
        assert all(xs[i] <= xs[i + 1] + 1e-9 for i in range(len(xs) - 1))
        assert statistics.median(xs) == pytest.approx(150.0, abs=2.0)
        assert min(xs) >= 100.0 and max(xs) <= 200.0

    def test_normal_low_high_is_95pct_ci(self) -> None:
        xs = [
            _inv_cdf_shaped(u / 1000, "normal", 100.0, 200.0, 150.0)
            for u in range(1, 1000)
        ]
        assert statistics.median(xs) == pytest.approx(150.0, abs=1.0)
        assert xs[24] == pytest.approx(100.0, abs=2.0)  # ~P2.5
        assert xs[974] == pytest.approx(200.0, abs=2.0)  # ~P97.5

    def test_lognormal_is_right_skewed(self) -> None:
        xs = [
            _inv_cdf_shaped(u / 1000, "lognormal", 100.0, 200.0, 150.0)
            for u in range(1, 1000)
        ]
        assert statistics.mean(xs) > statistics.median(xs)  # positive skew
        assert min(xs) > 0.0


class TestEngineShapes:
    def test_unknown_distribution_raises(self) -> None:
        cfg = _load()
        cfg["monte_carlo"]["parameters"][0]["distribution"] = "weibull"
        with pytest.raises(MonteCarloConfigError, match="unsupported distribution"):
            MonteCarloEngine(cfg, seed=1)

    def test_all_uniform_scenario_has_no_shaped_params(self) -> None:
        # Byte-identical: the shipped canonical uses uniform throughout -> nothing shaped.
        assert MonteCarloEngine(_load(), seed=1)._shaped_params == {}

    def test_triangular_param_registers_and_runs(self) -> None:
        logging.disable(logging.WARNING)
        try:
            cfg = copy.deepcopy(_load())
            for p in cfg["monte_carlo"]["parameters"]:
                if p["name"] == "capex.usd_total":
                    p["distribution"] = "triangular"
            eng = MonteCarloEngine(cfg, seed=123)
            assert any(k == "triangular" for k in eng._param_kinds)
            assert eng._shaped_params  # capex registered as shaped
            res = eng.run(n_trials=48)
            assert res.failed_iterations == 0
            assert res.metadata.get("degenerate_sweep") is False
        finally:
            logging.disable(logging.NOTSET)
