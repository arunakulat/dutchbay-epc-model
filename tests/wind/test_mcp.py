"""Tests for wind_resource.mcp (WIND-1 measure-correlate-predict, #477).

Synthetic mast <-> reanalysis pair: the long-term reference (ERA5 proxy) is a Weibull wind
series; the true on-site is ``1.2 * ref + small noise`` (a site ~20% windier than the
reanalysis cell). MCP must recover that relationship from a short concurrent window and
predict the long-term on-site distribution. Deterministic (fixed RNG seed; MRM-01).
"""

from __future__ import annotations

import logging

import numpy as np
import pytest

from wind_resource.mcp import (
    BANKABLE_MIN_CONCURRENT,
    CAMPAIGN_BELOW_DISCLOSURE_FLOOR,
    CAMPAIGN_BELOW_IEC_BANKABLE,
    CAMPAIGN_IEC_BANKABLE,
    DEFAULT_MIN_CONCURRENT,
    IEC_BANKABLE_MIN_CONCURRENT,
    LENDER_DISCLOSURE_MIN_CONCURRENT,
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


def _pair_of_size(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A well-behaved (non-degenerate) pair with exactly ``n`` concurrent samples."""
    rng = np.random.default_rng(597)
    ref_long_term = 8.0 * rng.weibull(2.1, n * 2)
    ref_concurrent = ref_long_term[:n]
    noise = rng.normal(0.0, 0.4, n)
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


# --------------------------------------------------------------------------- #
# Tiered bankability guard (#597; Sheridan et al. WES 2025)
# --------------------------------------------------------------------------- #
def test_hard_floor_tier_not_bypassed_by_override() -> None:
    # n = 23 < DEFAULT_MIN_CONCURRENT: the statistical floor raises even when the caller
    # opts out of the bankability tier — the override covers ONLY the bankable band.
    mast, ref_c, ref_lt = _pair_of_size(DEFAULT_MIN_CONCURRENT - 1)
    with pytest.raises(ValueError, match=f"need >= {DEFAULT_MIN_CONCURRENT}"):
        run_mcp(mast, ref_c, ref_lt, allow_below_bankable=True)


def test_hard_floor_boundary_lands_in_bankability_tier() -> None:
    # n = 24 clears the hard statistical floor but is far below the lender-disclosure
    # floor -> that error, not the statistical-floor error, is what the caller sees.
    mast, ref_c, ref_lt = _pair_of_size(DEFAULT_MIN_CONCURRENT)
    with pytest.raises(ValueError, match="lender-disclosure floor"):
        run_mcp(mast, ref_c, ref_lt)


def test_sub_bankable_boundary_raises_without_override() -> None:
    # n = 2879: one sample short of the ~4-month bankability threshold.
    mast, ref_c, ref_lt = _pair_of_size(BANKABLE_MIN_CONCURRENT - 1)
    with pytest.raises(ValueError, match="allow_below_bankable"):
        run_mcp(mast, ref_c, ref_lt)


def test_disclosure_floor_boundary_clears_the_gate_but_is_not_bankable(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """n = 2880 exactly: passes without an opt-out, but is NOT clean.

    This test previously asserted the opposite - that the ~4-month boundary logged no
    disclosure at all - and was named ``test_bankable_boundary_runs_clean``. That encoded
    the overclaim #961 identifies: 2880 samples is a third of the >= 12 concurrent months
    MEASNET v3.1 / IEC 61400-15-1:2025 require, so silence there told the caller the
    estimate was bankable when it is only showable. The gate itself is unchanged - no
    opt-out is needed at this boundary - but the shortfall is now recorded and logged.
    """
    mast, ref_c, ref_lt = _pair_of_size(LENDER_DISCLOSURE_MIN_CONCURRENT)
    with caplog.at_level(logging.WARNING, logger="wind_resource.mcp"):
        res = run_mcp(mast, ref_c, ref_lt)  # still no allow_below_bankable required
    assert res.n_concurrent == LENDER_DISCLOSURE_MIN_CONCURRENT
    assert res.campaign_adequacy == CAMPAIGN_BELOW_IEC_BANKABLE
    assert res.concurrent_shortfall_to_iec_bankable == (
        IEC_BANKABLE_MIN_CONCURRENT - LENDER_DISCLOSURE_MIN_CONCURRENT
    )
    assert [r for r in caplog.records if "NOT bankable" in r.getMessage()]


def test_sub_bankable_override_runs_with_logged_disclosure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The explicit opt-out downgrades the failure to a warning that names the sample
    # count, the threshold, and the non-bankability of the estimate.
    mast, ref_c, ref_lt = _pair_of_size(BANKABLE_MIN_CONCURRENT - 1)
    with caplog.at_level(logging.WARNING, logger="wind_resource.mcp"):
        res = run_mcp(mast, ref_c, ref_lt, allow_below_bankable=True)
    assert res.n_concurrent == BANKABLE_MIN_CONCURRENT - 1
    disclosures = [
        r.getMessage() for r in caplog.records if "NOT bankable" in r.getMessage()
    ]
    assert len(disclosures) == 1
    assert str(BANKABLE_MIN_CONCURRENT) in disclosures[0]
    assert str(BANKABLE_MIN_CONCURRENT - 1) in disclosures[0]


def test_data_integrity_errors_precede_bankability_tier() -> None:
    # A degenerate reference in the sub-bankable band reports the actionable data error,
    # not the campaign-duration error.
    with pytest.raises(ValueError, match="zero variance"):
        run_mcp(list(np.linspace(6.0, 9.0, 30)), [7.0] * 30, [7.0] * 100)


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
    # 200 concurrent samples sit below the bankability tier -> explicit opt-out required.
    res = run_mcp(
        mast, ref_c, ref_lt, method="linear_regression", allow_below_bankable=True
    )
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
    # The bankability opt-out defaults OFF when the scenario does not declare it.
    assert mcp_settings(cfg) == {
        "method": "variance_ratio",
        "min_concurrent": 8760,
        "allow_below_bankable": False,
    }


def test_mcp_settings_resolves_explicit_allow_below_bankable() -> None:
    cfg = {
        "resource": {"wind": {"mcp": {"enabled": True, "allow_below_bankable": True}}}
    }
    resolved = mcp_settings(cfg)
    assert resolved is not None
    assert resolved["allow_below_bankable"] is True


def test_mcp_settings_rejects_non_boolean_allow_below_bankable() -> None:
    # Strict (CESSPIT): truthy-but-non-boolean values are configuration errors, not opt-outs.
    for bad in ("yes", 1, 0, "false", [True]):
        cfg = {
            "resource": {
                "wind": {"mcp": {"enabled": True, "allow_below_bankable": bad}}
            }
        }
        with pytest.raises(ValueError, match="allow_below_bankable must be a boolean"):
            mcp_settings(cfg)


def test_mcp_settings_rejects_bad_method() -> None:
    cfg = {"resource": {"wind": {"mcp": {"enabled": True, "method": "bogus"}}}}
    with pytest.raises(ValueError, match="invalid"):
        mcp_settings(cfg)


def test_all_methods_are_runnable() -> None:
    mast, ref_c, ref_lt = _synthetic_pair()
    for method in MCP_METHODS:
        assert run_mcp(mast, ref_c, ref_lt, method=method).method == method


# --- campaign adequacy against the standards (#961) -------------------------------------
#
# The ~4-month constant was named BANKABLE_MIN_CONCURRENT while its own docstring conceded
# a bankable campaign needs >= 12 months, so the name overclaimed by 3x. These pin the
# corrected naming and, more importantly, the band that used to be SILENT: a campaign that
# clears the disclosure floor but falls short of the standards now says so on the result.


def test_deprecated_alias_still_resolves_to_the_disclosure_floor() -> None:
    assert BANKABLE_MIN_CONCURRENT == LENDER_DISCLOSURE_MIN_CONCURRENT == 2880


def test_iec_bankable_threshold_is_twelve_months_of_hourly_data() -> None:
    assert IEC_BANKABLE_MIN_CONCURRENT == 8760
    # The whole point: the disclosure floor is NOT the bankability threshold.
    assert LENDER_DISCLOSURE_MIN_CONCURRENT < IEC_BANKABLE_MIN_CONCURRENT


def test_full_twelve_month_campaign_is_recorded_iec_bankable() -> None:
    mast, ref_c, ref_lt = _pair_of_size(IEC_BANKABLE_MIN_CONCURRENT)
    res = run_mcp(mast, ref_c, ref_lt)
    assert res.campaign_adequacy == CAMPAIGN_IEC_BANKABLE
    assert res.concurrent_shortfall_to_iec_bankable == 0
    assert res.as_dict()["campaign_adequacy"] == CAMPAIGN_IEC_BANKABLE


def test_above_floor_but_short_of_iec_is_recorded_not_silent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The regression this dolphin exists for.

    A campaign at the ~4-month floor previously emitted an estimate with NO record that it
    was a third of the span the standards require - it cleared the only gate there was and
    said nothing. It must now both warn and carry the shortfall on the result.
    """
    n = LENDER_DISCLOSURE_MIN_CONCURRENT + 120
    mast, ref_c, ref_lt = _pair_of_size(n)
    with caplog.at_level(logging.WARNING, logger="wind_resource.mcp"):
        res = run_mcp(mast, ref_c, ref_lt)  # no opt-out needed: it clears the floor
    assert res.campaign_adequacy == CAMPAIGN_BELOW_IEC_BANKABLE
    assert res.concurrent_shortfall_to_iec_bankable == IEC_BANKABLE_MIN_CONCURRENT - n
    disclosures = [r.getMessage() for r in caplog.records]
    assert any(str(IEC_BANKABLE_MIN_CONCURRENT) in d for d in disclosures)
    assert any("NOT bankable" in d for d in disclosures)


def test_below_floor_records_the_worst_tier_when_opted_out() -> None:
    n = LENDER_DISCLOSURE_MIN_CONCURRENT - 1
    mast, ref_c, ref_lt = _pair_of_size(n)
    res = run_mcp(mast, ref_c, ref_lt, allow_below_bankable=True)
    assert res.campaign_adequacy == CAMPAIGN_BELOW_DISCLOSURE_FLOOR
    assert res.concurrent_shortfall_to_iec_bankable == IEC_BANKABLE_MIN_CONCURRENT - n


def test_sub_floor_error_names_the_iec_requirement_too() -> None:
    """Fail-loud text must not leave the reader thinking the floor is bankability."""
    mast, ref_c, ref_lt = _pair_of_size(LENDER_DISCLOSURE_MIN_CONCURRENT - 1)
    with pytest.raises(ValueError) as excinfo:
        run_mcp(mast, ref_c, ref_lt)
    message = str(excinfo.value)
    assert str(LENDER_DISCLOSURE_MIN_CONCURRENT) in message
    assert str(IEC_BANKABLE_MIN_CONCURRENT) in message
    assert "would not make the estimate bankable" in message
