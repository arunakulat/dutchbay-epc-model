"""Regression tests for the audit-R1 correctness fixes.

Covers: the degenerate LHS sampler (all dimensions perfectly correlated), the MC
toy-fallback crashing on nested overrides, MC success_rate counting toy-fallback trials
as successes, and VaR/CVaR returning NaN on small samples.
"""

from __future__ import annotations

import math

import numpy as np

# --- LHS sampler: dimensions must be independent ---------------------------------------


def test_lhs_dimensions_are_not_degenerate() -> None:
    """Each LHS dimension must use its own stratified column, not column 0 for all."""
    from analytics.mc.samplers import generate_lhs_samples

    samples = generate_lhs_samples(n_trials=64, bounds=[(0.0, 1.0)] * 4, seed=7)
    # Before the fix, every column was a permutation of column 0 -> identical sorted values.
    sorted_cols = [np.sort(samples[:, j]) for j in range(samples.shape[1])]
    assert not np.allclose(
        sorted_cols[0], sorted_cols[1]
    ), "dims 0 and 1 are degenerate"
    corr = np.corrcoef(samples[:, 0], samples[:, 1])[0, 1]
    assert abs(corr) < 0.6, f"LHS dims should be near-independent, got corr={corr:.2f}"


# --- MC toy-fallback must not crash on nested / dotted overrides ------------------------


def test_toy_fallback_survives_nested_overrides() -> None:
    """A nested override dict (from dotted-key expansion) must not crash float(dict)."""
    from analytics.mc.engine import _toy_metric_fallback

    nested = {"capex": {"usd_total": 150_000_000}, "project": {"capacity_factor": 0.30}}
    out = _toy_metric_fallback(nested)  # must NOT raise
    assert math.isfinite(out["project_irr"])
    assert math.isfinite(out["project_npv"])


def test_toy_fallback_reads_flat_and_dotted_keys() -> None:
    from analytics.mc.engine import _num_override

    assert _num_override({"capex": 5.0}, "capex", "capex.usd_total", default=1.0) == 5.0
    assert (
        _num_override({"capex.usd_total": 9.0}, "capex", "capex.usd_total", default=1.0)
        == 9.0
    )
    assert (
        _num_override({"capex": {"x": 1}}, "capex", default=1.0) == 1.0
    )  # dict -> default
    assert (
        _num_override({"capex": True}, "capex", default=1.0) == 1.0
    )  # bool -> default


# --- MC success_rate must not count toy-fallback (fabricated) trials as successes -------


def test_success_rate_treats_toy_fallback_as_failed() -> None:
    from analytics.mc.aggregate import aggregate_trials

    trials = [
        {"project_irr": 0.10, "project_npv": 1.0, "dscr_min": 1.3},
        {"project_irr": 0.11, "project_npv": 2.0, "dscr_min": 1.3},
        {
            "project_irr": 0.09,
            "project_npv": 0.5,
            "dscr_min": 1.3,
            "_toy_fallback": True,
        },
    ]
    result = aggregate_trials(
        trial_metrics=trials,
        base_config={},
        param_names=["x"],
        samples=np.zeros((3, 1)),
        meta={},
    )
    # 1 of 3 trials is a toy fallback -> it must count as failed, not a successful run.
    assert result.failed_iterations >= 1
    assert result.success_rate() < 100.0


# --- VaR/CVaR must not return NaN on a small sample -------------------------------------


def test_var_cvar_no_nan_on_small_sample() -> None:
    from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer

    analyzer = TailRiskAnalyzer(
        RiskConfig(
            confidence_level=0.95,
            target_return=0.10,
            min_dscr=1.2,
            min_llcr=1.2,
            min_plcr=1.4,
        )
    )
    returns = np.array(
        [1.0, 2.0, 3.0, 4.0, 5.0]
    )  # n=5: (1-0.95)*5 = 0.25 -> rounds to 0
    result = analyzer.calculate_var_cvar(returns=returns)
    assert math.isfinite(result.var)
    assert math.isfinite(result.cvar), "CVaR must not be NaN on a small sample"
