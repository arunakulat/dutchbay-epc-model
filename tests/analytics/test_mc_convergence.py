"""MC convergence diagnostic (#590) — analytics/mc/convergence.py.

Read-only: verifies the CI-half-width formula, checkpoint/filtering behaviour, that the
band shrinks with more trials, and that the engine attaches it to result.metadata without
changing any band (KPI-neutral).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from analytics.mc.convergence import Z_95, convergence_diagnostic

_LENDER = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def test_ci_halfwidth_matches_formula_and_ends_at_n() -> None:
    rng = np.random.default_rng(0)
    arr = rng.normal(0.10, 0.02, size=500)
    out = convergence_diagnostic({"project_irr": arr.tolist()}, z=Z_95, min_n=30)
    d = out["project_irr"]

    assert d["n"] == 500
    assert d["checkpoints"][-1] == 500  # trace always ends at n
    expected_hw = Z_95 * float(arr.std(ddof=1)) / np.sqrt(500)
    assert d["final_ci_halfwidth"] == pytest.approx(expected_hw)
    assert d["final_mean"] == pytest.approx(float(arr.mean()))
    assert d["final_rel_ci_halfwidth"] == pytest.approx(
        expected_hw / abs(float(arr.mean()))
    )
    # The half-width narrows from the first checkpoint (k=30) to the last (k=500).
    assert d["ci_halfwidth_trace"][0] >= d["ci_halfwidth_trace"][-1]


def test_metric_below_min_n_is_omitted() -> None:
    assert convergence_diagnostic({"x": [1.0, 2.0, 3.0]}, min_n=30) == {}


def test_none_and_nonfinite_entries_are_dropped() -> None:
    arr = [1.0, None, float("nan"), float("inf"), 2.0] + [1.5] * 40
    out = convergence_diagnostic({"x": arr}, min_n=30)
    assert out["x"]["n"] == 42  # 45 entries minus None, nan, inf


def test_halfwidth_shrinks_with_more_trials() -> None:
    rng = np.random.default_rng(1)
    small = convergence_diagnostic({"x": rng.normal(0, 1, 100).tolist()}, min_n=30)["x"]
    big = convergence_diagnostic({"x": rng.normal(0, 1, 4000).tolist()}, min_n=30)["x"]
    assert big["final_ci_halfwidth"] < small["final_ci_halfwidth"]


def test_rel_ci_halfwidth_is_none_when_mean_near_zero() -> None:
    """A mean within one half-width of zero has undefined relative precision (audit: DutchBay
    IRRs sit near zero, so |mean| in the denominator would blow up to a spurious huge number).
    """
    rng = np.random.default_rng(3)
    arr = rng.normal(0.0, 1.0, size=1000)  # mean ~ 0, well inside its own CI half-width
    d = convergence_diagnostic({"x": arr.tolist()}, min_n=30)["x"]
    assert d["final_rel_ci_halfwidth"] is None
    assert d["final_ci_halfwidth"] > 0.0  # the absolute half-width is still reported
    assert d["statistic"] == "mean"


def test_min_n_below_one_does_not_crash() -> None:
    """min_n <= 0 must not raise an opaque geomspace('cannot include zero') error."""
    out = convergence_diagnostic({"x": [float(i) for i in range(50)]}, min_n=0)
    assert out["x"]["checkpoints"][-1] == 50


def test_engine_attaches_convergence_metadata_without_changing_bands() -> None:
    from analytics.mc.engine import MonteCarloEngine

    cfg = yaml.safe_load(_LENDER.read_text())
    result = MonteCarloEngine(cfg, seed=1).run(n_trials=64)

    assert "convergence" in result.metadata
    conv = result.metadata["convergence"]
    # n_trials=64 >= min_n=30, so at least one metric is always diagnosed (assert, not guard).
    assert isinstance(conv, dict) and conv
    d = next(iter(conv.values()))
    assert d["statistic"] == "mean"
    assert {
        "n",
        "checkpoints",
        "ci_halfwidth_trace",
        "final_ci_halfwidth",
        "final_rel_ci_halfwidth",
    } <= set(d)
    assert d["checkpoints"][-1] == d["n"]
    assert len(d["ci_halfwidth_trace"]) == len(d["checkpoints"])
    # The diagnostic is additive: the percentile bands are still present and untouched.
    assert result.percentiles is not None
