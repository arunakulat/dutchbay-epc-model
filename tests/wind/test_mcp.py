"""Tests for wind_resource.mcp (WIND-1 measure-correlate-predict, #477).

Synthetic mast <-> reanalysis pair: the long-term reference (ERA5 proxy) is a Weibull wind
series; the true on-site is ``1.2 * ref + small noise`` (a site ~20% windier than the
reanalysis cell). MCP must recover that relationship from a short concurrent window and
predict the long-term on-site distribution. Deterministic (fixed RNG seed; MRM-01).
"""

from __future__ import annotations

import numpy as np
import pytest

from wind_resource.mcp import (
    MCP_METHODS,
    MCPResult,
    linear_regression_transfer,
    mcp_settings,
    pearson_r,
    predict_long_term,
    run_mcp,
    variance_ratio_transfer,
)

_TRUE_SLOPE = 1.2
_N_LONG = 8760 * 5  # 5 years of long-term reference
_N_CONCURRENT = 8760  # 1 year of concurrent mast


def _synthetic_pair() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(mast_concurrent, ref_concurrent, ref_long_term)."""
    rng = np.random.default_rng(477)
    ref_long_term = 8.0 * rng.weibull(2.1, _N_LONG)
    ref_concurrent = ref_long_term[:_N_CONCURRENT]
    noise = rng.normal(0.0, 0.4, _N_CONCURRENT)
    mast_concurrent = np.clip(_TRUE_SLOPE * ref_concurrent + noise, 0.0, None)
    return mast_concurrent, ref_concurrent, ref_long_term


# --------------------------------------------------------------------------- #
# Transfer fitting recovers the synthetic relationship
# --------------------------------------------------------------------------- #
def test_ols_recovers_true_slope() -> None:
    mast, ref_c, _ = _synthetic_pair()
    slope, _intercept = linear_regression_transfer(mast, ref_c)
    assert slope == pytest.approx(_TRUE_SLOPE, abs=0.02)


def test_variance_ratio_preserves_on_site_variance() -> None:
    """Variance-ratio reproduces the measured on-site std; OLS deflates it (IEC rationale)."""
    mast, ref_c, ref_lt = _synthetic_pair()
    vr = run_mcp(mast, ref_c, ref_lt, method="variance_ratio")
    ols = run_mcp(mast, ref_c, ref_lt, method="linear_regression")

    vr_slope, _ = variance_ratio_transfer(mast, ref_c)
    vr_pred_std = vr_slope * float(ref_lt.std())
    ols_pred_std = linear_regression_transfer(mast, ref_c)[0] * float(ref_lt.std())
    measured_std = float(mast.std())
    # Variance-ratio prediction std tracks the measured on-site std; OLS sits below it.
    assert vr_pred_std == pytest.approx(measured_std, rel=0.05)
    assert ols_pred_std < vr_pred_std
    assert isinstance(vr, MCPResult) and isinstance(ols, MCPResult)


def test_predicted_long_term_mean_matches_true_on_site() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    res = run_mcp(mast, ref_c, ref_lt, method="variance_ratio")
    # The site is ~20% windier than the reanalysis cell.
    assert res.uplift_pct == pytest.approx(20.0, abs=2.0)
    assert res.predicted_long_term_mean_ms == pytest.approx(
        _TRUE_SLOPE * float(ref_lt.mean()), rel=0.03
    )
    assert res.pearson_r > 0.9
    assert res.n_concurrent == _N_CONCURRENT
    # A plausible Weibull falls out of the predicted distribution.
    assert 1.5 < res.weibull_k < 3.0
    assert res.weibull_a > 0.0


def test_result_serializable() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    payload = run_mcp(mast, ref_c, ref_lt).as_dict()
    assert payload["method"] == "variance_ratio"
    assert payload["n_concurrent"] == _N_CONCURRENT


# --------------------------------------------------------------------------- #
# Fail-loud guards (CESSPIT)
# --------------------------------------------------------------------------- #
def test_unknown_method_raises() -> None:
    with pytest.raises(ValueError, match="Unknown MCP method"):
        run_mcp([1.0] * 30, [1.0] * 30, [1.0] * 30, method="kriging")


def test_misaligned_concurrent_series_raises() -> None:
    with pytest.raises(ValueError, match="must align"):
        run_mcp([1.0] * 30, [1.0] * 29, [1.0] * 100)


def test_too_few_concurrent_samples_raises() -> None:
    with pytest.raises(ValueError, match="concurrent samples"):
        run_mcp([8.0] * 10, [7.0] * 10, [7.0] * 100, min_concurrent=24)


def test_zero_variance_reference_raises_for_both_methods() -> None:
    # Both methods must fail loud identically on a degenerate (constant) reference.
    for method in MCP_METHODS:
        with pytest.raises(ValueError, match="zero variance"):
            run_mcp(
                list(np.linspace(6.0, 9.0, 30)),
                [7.0] * 30,
                [7.0] * 100,
                method=method,
            )


def test_non_finite_input_raises() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    ref_lt_nan = ref_lt.copy()
    ref_lt_nan[10] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        run_mcp(mast, ref_c, ref_lt_nan)
    mast_inf = mast.copy()
    mast_inf[0] = np.inf
    with pytest.raises(ValueError, match="non-finite"):
        run_mcp(mast_inf, ref_c, ref_lt)


def test_fraction_clipped_disclosed_when_transfer_predicts_negative() -> None:
    # A strongly negative intercept (low-wind site offset) clips some long-term steps;
    # the result must DISCLOSE the clipped fraction rather than hide the mean/variance bias.
    mast = list(np.linspace(0.0, 4.0, 200))  # low-wind mast
    ref_c = list(np.linspace(6.0, 14.0, 200))  # windier reference -> negative intercept
    # Long-term reference reaches BELOW the concurrent window, where the transfer
    # (slope 0.5, intercept -3) predicts negative speeds that must be clipped.
    ref_lt = list(np.linspace(2.0, 14.0, 500))
    res = run_mcp(mast, ref_c, ref_lt, method="linear_regression")
    assert res.fraction_clipped > 0.0
    assert res.as_dict()["fraction_clipped"] == pytest.approx(
        res.fraction_clipped, abs=1e-5
    )


def test_no_clipping_for_well_behaved_pair() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    assert run_mcp(mast, ref_c, ref_lt).fraction_clipped == 0.0


def test_empty_long_term_reference_raises() -> None:
    with pytest.raises(ValueError, match="ref_long_term is empty"):
        run_mcp([7.0] * 30, list(np.linspace(5.0, 9.0, 30)), [])


# --------------------------------------------------------------------------- #
# Helper-level units
# --------------------------------------------------------------------------- #
def test_pearson_r_zero_for_constant_series() -> None:
    assert pearson_r(np.array([3.0, 3.0, 3.0]), np.array([1.0, 2.0, 3.0])) == 0.0


def test_predict_long_term_clips_negative_speeds() -> None:
    # slope 0.5, intercept -3 -> ref 2 -> -2 (clipped to 0); ref 14 -> 4.
    out = predict_long_term(0.5, -3.0, np.array([2.0, 14.0]))
    assert list(out) == [0.0, 4.0]


def test_variance_ratio_transfer_zero_variance_raises_directly() -> None:
    with pytest.raises(ValueError, match="zero variance"):
        variance_ratio_transfer(np.array([1.0, 2.0, 3.0]), np.array([5.0, 5.0, 5.0]))


def test_mcp_settings_rejects_non_integer_min_concurrent() -> None:
    cfg = {"resource": {"wind": {"mcp": {"enabled": True, "min_concurrent": "lots"}}}}
    with pytest.raises(ValueError, match="min_concurrent must be an integer"):
        mcp_settings(cfg)


# --------------------------------------------------------------------------- #
# Config gate (opt-in)
# --------------------------------------------------------------------------- #
def test_mcp_settings_none_when_disabled_or_absent() -> None:
    assert mcp_settings({}) is None
    assert mcp_settings({"resource": {"wind": {}}}) is None
    assert mcp_settings({"resource": {"wind": {"mcp": {"enabled": False}}}}) is None


def test_mcp_settings_resolves_when_enabled() -> None:
    cfg = {
        "resource": {
            "wind": {
                "mcp": {
                    "enabled": True,
                    "method": "variance_ratio",
                    "min_concurrent": 8760,
                }
            }
        }
    }
    assert mcp_settings(cfg) == {"method": "variance_ratio", "min_concurrent": 8760}


def test_mcp_settings_rejects_bad_method() -> None:
    cfg = {"resource": {"wind": {"mcp": {"enabled": True, "method": "bogus"}}}}
    with pytest.raises(ValueError, match="invalid"):
        mcp_settings(cfg)


def test_all_methods_are_runnable() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    for method in MCP_METHODS:
        assert run_mcp(mast, ref_c, ref_lt, method=method).method == method
