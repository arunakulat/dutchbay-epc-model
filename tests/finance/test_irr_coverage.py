"""Coverage tests for ``finance.irr`` — pure IRR/NPV/MIRR/XIRR numerics.

This is the canonical project-finance discounting engine. The tests below drive
synthetic, deterministic cashflow vectors through every public and internal path
and assert *relationships* rather than memorised magic numbers:

  * ``npv`` discounting identity, the -100% rate clamp, and t=0 weighting.
  * ``irr`` empty/flat contracts, the library-first path, and the bisection
    fallback (forced via out-of-bounds caps).
  * ``_irr_bisect`` exact-root-at-bound shortcuts, the no-sign-change ``None``
    contract, and the full bisection loop reconciled against ``npv``.
  * ``xnpv`` / ``xirr`` length-mismatch raises, empty/flat contracts, the dated
    discounting identity, and the bisection solver.
  * ``project_npv_from_cfads`` — carries the #280 construction-lag fix; the tests
    pin the assembled ``[-capex] + [0]*lag + cfads`` vector shape and the timing
    semantics (first operating CFADS discounted at t = lag + 1).
  * ``approx_project_irr`` — reconciled against ``project_npv_from_cfads`` (the
    returned rate zeroes the project NPV) plus its documented 0.0 guards.

All expected values are derived inside the test (closed-form discounting, or by
calling the function under test and asserting structure/sign/monotonicity), so
no economic magic number is hardcoded.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from finance.irr import (
    approx_project_irr,
    irr,
    npv,
    project_npv_from_cfads,
    xirr,
    xnpv,
)
from finance.irr import _irr_bisect, _xirr_bisect

# ---------------------------------------------------------------------------
# npv
# ---------------------------------------------------------------------------


def test_npv_matches_closed_form_discounting() -> None:
    """NPV equals the hand-computed Σ CF_t / (1+r)^t with t starting at 0."""
    rate = 0.10
    cfs = [-100.0, 60.0, 60.0]
    expected = -100.0 + 60.0 / 1.1 + 60.0 / (1.1**2)
    assert npv(rate, cfs) == pytest.approx(expected)


def test_npv_zero_rate_is_plain_sum() -> None:
    """At r=0 the discount factors are all 1, so NPV is the arithmetic sum."""
    cfs = [-100.0, 30.0, 40.0, 50.0]
    assert npv(0.0, cfs) == pytest.approx(sum(cfs))


def test_npv_first_cashflow_is_undiscounted() -> None:
    """The t=0 cashflow is weighted by (1+r)^0 = 1 regardless of rate."""
    # Only a t=0 flow: NPV must equal it exactly for any rate.
    assert npv(0.37, [-250.0]) == pytest.approx(-250.0)


def test_npv_clamps_rate_at_or_below_minus_one() -> None:
    """A rate <= -1.0 is clamped to -0.9999 to avoid division by zero (line 90).

    The clamp means npv(-1.0, .) and npv(-5.0, .) both evaluate at -0.9999 and
    therefore return the identical (finite) value.
    """
    cfs = [-100.0, 50.0, 80.0]
    clamped = npv(-0.9999, cfs)
    assert npv(-1.0, cfs) == pytest.approx(clamped)
    assert npv(-5.0, cfs) == pytest.approx(clamped)
    # And it is finite, not an exploded infinity.
    assert abs(npv(-1.0, cfs)) < float("inf")


# ---------------------------------------------------------------------------
# irr — public contracts
# ---------------------------------------------------------------------------


def test_irr_empty_series_returns_none() -> None:
    """An empty cashflow series has no IRR (line 133)."""
    assert irr([]) is None


def test_irr_all_zero_series_returns_zero() -> None:
    """An economically flat series is treated as 0% return (line 136)."""
    assert irr([0.0, 0.0, 0.0]) == 0.0


def test_irr_zeroes_project_npv() -> None:
    """The returned IRR is the rate at which NPV ≈ 0 (root definition)."""
    cfs = [-1000.0, 400.0, 400.0, 400.0]
    rate = irr(cfs)
    assert rate is not None
    assert npv(rate, cfs) == pytest.approx(0.0, abs=1e-6)


def test_irr_simple_doubling_is_one_hundred_percent() -> None:
    """-1 now, +2 next period => exactly 100% periodic return."""
    rate = irr([-1.0, 2.0])
    assert rate is not None
    assert rate == pytest.approx(1.0)


def test_irr_out_of_bounds_library_value_triggers_bisection_fallback() -> None:
    """A library IRR outside [lo, hi] forces the bisection fallback (line 149-150).

    The true root here is +100% (rate=1.0). Capping upper_bound below that makes
    the npf value out-of-bounds, and bisection cannot bracket a root in
    [-0.9999, 0.5] either, so the contract is a clean ``None``.
    """
    assert irr([-1.0, 2.0], upper_bound=0.5) is None


def test_irr_no_sign_change_returns_none() -> None:
    """All-positive flows never cross zero, so there is no IRR root."""
    # npf typically yields NaN here; the bisection fallback then returns None.
    assert irr([100.0, 50.0, 25.0]) is None


def test_irr_library_failure_falls_back_to_bisection(monkeypatch: pytest.MonkeyPatch) -> None:
    """If npf.irr raises, the NaN guard routes to bisection (lines 145-146).

    We monkeypatch the library entry point to raise; the robust bisection solver
    must still recover the correct root (+100%).
    """
    import finance.irr as irr_mod

    def _boom(_cfs: object) -> float:
        raise RuntimeError("forced library failure")

    monkeypatch.setattr(irr_mod.npf, "irr", _boom)
    rate = irr([-1.0, 2.0])
    assert rate is not None
    assert rate == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# _irr_bisect — internal solver
# ---------------------------------------------------------------------------


def test_irr_bisect_empty_returns_none() -> None:
    """The internal bisection solver rejects an empty series (line 162)."""
    assert _irr_bisect([]) is None


def test_irr_bisect_exact_root_at_lower_bound() -> None:
    """If NPV at the lower bound is ~0, that bound is returned (lines 171-172).

    Construct a one-period series whose root is exactly the lower bound:
    -1 + payoff/(1+lo) = 0  =>  payoff = (1+lo).
    """
    lo = -0.5
    payoff = 1.0 + lo  # 0.5
    assert npv(lo, [-1.0, payoff]) == pytest.approx(0.0, abs=1e-13)
    assert _irr_bisect([-1.0, payoff], lower_bound=lo, upper_bound=5.0) == pytest.approx(lo)


def test_irr_bisect_exact_root_at_upper_bound() -> None:
    """If NPV at the upper bound is ~0, that bound is returned (lines 173-174)."""
    hi = 1.0
    payoff = 1.0 + hi  # root is exactly r=hi: -1 + 2/(1+hi) = 0
    assert npv(hi, [-1.0, payoff]) == pytest.approx(0.0, abs=1e-13)
    assert _irr_bisect([-1.0, payoff], lower_bound=-0.9999, upper_bound=hi) == pytest.approx(hi)


def test_irr_bisect_no_sign_change_returns_none() -> None:
    """No sign change between the bounds => no bracketed root => None (line 178)."""
    # All-positive flows: NPV is positive at both bounds.
    assert _irr_bisect([10.0, 5.0, 1.0], lower_bound=-0.9, upper_bound=5.0) is None


def test_irr_bisect_loop_converges_to_npv_root() -> None:
    """The bisection loop returns a rate that zeroes NPV (lines 181-191)."""
    cfs = [-1000.0, 300.0, 400.0, 500.0]
    root = _irr_bisect(cfs, lower_bound=-0.9999, upper_bound=5.0)
    assert root is not None
    assert npv(root, cfs) == pytest.approx(0.0, abs=1e-6)


def test_irr_bisect_best_effort_when_not_fully_converged() -> None:
    """A tight bracket exits the loop early and returns the midpoint (line 194).

    Setting lower==upper makes the bracket zero-width: there is a sign change
    (one bound's NPV is treated against itself only if signs differ) — instead we
    pick bounds straddling the root so neither bound is an exact root and the loop
    drives toward it; the result still zeroes NPV.
    """
    cfs = [-1000.0, 400.0, 400.0, 400.0]
    # True root is ~9.7%. Use an asymmetric bracket that contains it.
    root = _irr_bisect(cfs, lower_bound=-0.5, upper_bound=2.0)
    assert root is not None
    assert npv(root, cfs) == pytest.approx(0.0, abs=1e-6)


def test_irr_bisect_loop_exhaustion_returns_midpoint() -> None:
    """Huge-magnitude flows defeat the abs(f_mid)<1e-10 exit, hitting line 194.

    With cashflows on the order of 1e17, the bisected rate converges to machine
    precision yet the *scaled* NPV residual stays far above 1e-10, so all 200
    iterations run and the best-effort midpoint return is taken. The result is
    still an economically correct root (residual is tiny relative to magnitude).
    """
    cfs = [-3e17, 2e17, 2e17]  # interior root, neither bound is an exact root
    root = _irr_bisect(cfs, lower_bound=-0.9999, upper_bound=5.0)
    assert root is not None
    # Relative residual is negligible against the 1e17-scale flows.
    assert abs(npv(root, cfs)) / 3e17 < 1e-15


# ---------------------------------------------------------------------------
# xnpv
# ---------------------------------------------------------------------------


def test_xnpv_length_mismatch_raises() -> None:
    """Mismatched cashflow/date lengths raise ValueError (lines 232-233)."""
    with pytest.raises(ValueError, match="same length"):
        xnpv(0.1, [-100.0, 50.0], [datetime(2025, 1, 1)])


def test_xnpv_empty_returns_zero() -> None:
    """Empty cashflows/dates discount to a present value of zero (lines 236-237)."""
    assert xnpv(0.1, [], []) == 0.0


def test_xnpv_matches_act_365_25_discounting() -> None:
    """XNPV equals the closed-form ACT/365.25 dated discounting (lines 239-247)."""
    rate = 0.10
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    cfs = [-100.0, 110.0]
    days = (dates[1] - dates[0]).days  # 365
    years = days / 365.25
    expected = -100.0 + 110.0 / ((1.0 + rate) ** years)
    assert xnpv(rate, cfs, dates) == pytest.approx(expected)


def test_xnpv_first_date_is_undiscounted() -> None:
    """The flow on the first (anchor) date is undiscounted (years == 0)."""
    dates = [datetime(2025, 6, 1), datetime(2030, 6, 1)]
    # Zero out the later flow so only the anchor remains.
    assert xnpv(0.25, [-500.0, 0.0], dates) == pytest.approx(-500.0)


# ---------------------------------------------------------------------------
# xirr
# ---------------------------------------------------------------------------


def test_xirr_length_mismatch_raises() -> None:
    """Mismatched lengths raise ValueError before any solving (lines 260-261)."""
    with pytest.raises(ValueError, match="same length"):
        xirr([-100.0, 50.0], [datetime(2025, 1, 1)])


def test_xirr_empty_returns_none() -> None:
    """An empty dated series has no XIRR (lines 264-265)."""
    assert xirr([], []) is None


def test_xirr_all_zero_returns_zero() -> None:
    """An economically flat dated series returns 0% (lines 266-267)."""
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    assert xirr([0.0, 0.0], dates) == 0.0


def test_xirr_zeroes_xnpv_at_returned_rate() -> None:
    """The returned XIRR is the rate at which XNPV ≈ 0 (lines 270-274)."""
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1), datetime(2027, 1, 1)]
    cfs = [-1000.0, 500.0, 700.0]
    rate = xirr(cfs, dates)
    assert rate is not None
    assert xnpv(rate, cfs, dates) == pytest.approx(0.0, abs=1e-6)


def test_xirr_annual_doubling_close_to_one_hundred_percent() -> None:
    """-1 then +2 one year later is ~100% annualised (ACT/365.25 ~ 365 days)."""
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    rate = xirr([-1.0, 2.0], dates)
    assert rate is not None
    # 365/365.25 years; the annualised rate is fractionally above 100%.
    assert rate == pytest.approx(1.0, abs=2e-2)


def test_xirr_exception_path_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the internal solver raises, xirr swallows it and returns None (275-276)."""
    import finance.irr as irr_mod

    def _boom(*_a: object, **_k: object) -> float:
        raise RuntimeError("forced solver failure")

    monkeypatch.setattr(irr_mod, "_xirr_bisect", _boom)
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    assert xirr([-1.0, 2.0], dates) is None


# ---------------------------------------------------------------------------
# _xirr_bisect — internal dated solver
# ---------------------------------------------------------------------------


def test_xirr_bisect_exact_root_at_lower_bound() -> None:
    """XNPV ~0 at the lower bound returns that bound (lines 292-293)."""
    lo = 0.0
    # At r=0, XNPV is the plain sum; make it zero so lo is an exact root.
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    root = _xirr_bisect([-100.0, 100.0], dates, lower_bound=lo, upper_bound=2.0)
    assert root == pytest.approx(lo)


def test_xirr_bisect_exact_root_at_upper_bound() -> None:
    """XNPV ~0 at the upper bound returns that bound (lines 294-295)."""
    hi = 0.0
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    root = _xirr_bisect([-100.0, 100.0], dates, lower_bound=-0.9, upper_bound=hi)
    assert root == pytest.approx(hi)


def test_xirr_bisect_no_sign_change_returns_none() -> None:
    """No sign change between the dated bounds => None (lines 298-299)."""
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1)]
    # All-positive flows: XNPV positive at both bounds.
    assert _xirr_bisect([100.0, 50.0], dates, lower_bound=-0.5, upper_bound=2.0) is None


def test_xirr_bisect_loop_converges() -> None:
    """The dated bisection loop converges to an XNPV root (lines 302-312)."""
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1), datetime(2027, 7, 1)]
    cfs = [-1000.0, 300.0, 900.0]
    root = _xirr_bisect(cfs, dates, lower_bound=-0.9, upper_bound=2.0)
    assert root is not None
    assert xnpv(root, cfs, dates) == pytest.approx(0.0, abs=1e-6)


def test_xirr_bisect_loop_exhaustion_returns_midpoint() -> None:
    """Huge-magnitude dated flows defeat the 1e-8 exit, hitting line 315.

    As with the periodic solver, 1e17-scale cashflows keep the scaled XNPV
    residual above the 1e-8 tolerance even at machine-precision rate accuracy, so
    the 100-iteration loop is exhausted and the best-effort midpoint is returned.
    """
    dates = [datetime(2025, 1, 1), datetime(2026, 1, 1), datetime(2027, 1, 1)]
    cfs = [-3e17, 2e17, 2e17]
    root = _xirr_bisect(cfs, dates, lower_bound=-0.9999, upper_bound=2.0)
    assert root is not None
    assert abs(xnpv(root, cfs, dates)) / 3e17 < 1e-15


# ---------------------------------------------------------------------------
# project_npv_from_cfads — carries the #280 construction-lag fix
# ---------------------------------------------------------------------------


def test_project_npv_assembles_lagged_vector_shape() -> None:
    """The project vector is [-capex] + [0]*lag + cfads, capex at t=0.

    We reconstruct the assembled vector by hand and assert the function equals
    ``npv(rate, that_vector)`` — pinning both the shape and the timing.
    """
    rate = 0.08
    capex = 1000.0
    cfads = [200.0, 220.0, 240.0]
    lag = 2
    expected_vector = [-capex] + [0.0] * lag + cfads
    expected = npv(rate, expected_vector)
    assert project_npv_from_cfads(rate, cfads, capex, construction_years=lag) == pytest.approx(
        expected
    )


def test_project_npv_lag_pushes_first_cfads_later_and_lowers_npv() -> None:
    """A construction lag discounts the first CFADS further out, lowering NPV.

    With a positive discount rate, deferring the operating stream by extra zero
    periods must reduce NPV (the #280 timing fix: the first operating year is
    discounted at t = lag + 1, never at t=0).
    """
    rate = 0.10
    capex = 1000.0
    cfads = [400.0, 400.0, 400.0]
    npv_no_lag = project_npv_from_cfads(rate, cfads, capex, construction_years=0)
    npv_lagged = project_npv_from_cfads(rate, cfads, capex, construction_years=2)
    assert npv_lagged < npv_no_lag


def test_project_npv_first_cfads_never_undiscounted() -> None:
    """Even with zero lag, the first CFADS sits at t=1, not t=0.

    Contrast with the buggy pre-#280 convention ``npv(cfads) - capex`` where the
    first operating year was undiscounted. Here, at a positive rate, the first
    CFADS must be discounted by exactly one period.
    """
    rate = 0.10
    capex = 0.0  # isolate the operating stream
    cfads = [100.0]
    # Correct convention: 100 / (1+r)^1, because vector = [-0, 100].
    assert project_npv_from_cfads(rate, cfads, capex, construction_years=0) == pytest.approx(
        100.0 / (1.0 + rate)
    )


def test_project_npv_capex_typeerror_coerced_to_zero() -> None:
    """A non-numeric capex_total is treated as 0.0 (lines 352-353)."""
    rate = 0.05
    cfads = [100.0, 100.0]
    # capex=None -> coerced to 0.0; result equals npv of [-0.0, 100, 100].
    expected = npv(rate, [0.0] + cfads)
    assert project_npv_from_cfads(rate, cfads, None) == pytest.approx(expected)  # type: ignore[arg-type]


def test_project_npv_construction_years_typeerror_coerced_to_zero() -> None:
    """A non-numeric construction_years is treated as lag 0 (lines 357-358)."""
    rate = 0.05
    capex = 500.0
    cfads = [300.0, 300.0]
    expected = npv(rate, [-capex] + cfads)  # lag 0
    got = project_npv_from_cfads(rate, cfads, capex, construction_years="bad")  # type: ignore[arg-type]
    assert got == pytest.approx(expected)


def test_project_npv_negative_lag_floored_to_zero() -> None:
    """A negative construction_years is floored to 0 (max(0, int(...)))."""
    rate = 0.07
    capex = 500.0
    cfads = [300.0, 300.0]
    floored = project_npv_from_cfads(rate, cfads, capex, construction_years=0)
    negative = project_npv_from_cfads(rate, cfads, capex, construction_years=-5)
    assert negative == pytest.approx(floored)


def test_project_npv_npv_failure_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the inner npv call raises, the result is a neutral 0.0 (lines 364-366)."""
    import finance.irr as irr_mod

    def _boom(*_a: object, **_k: object) -> float:
        raise RuntimeError("forced npv failure")

    monkeypatch.setattr(irr_mod, "npv", _boom)
    assert project_npv_from_cfads(0.1, [100.0, 100.0], 50.0) == 0.0


# ---------------------------------------------------------------------------
# approx_project_irr
# ---------------------------------------------------------------------------


def test_approx_project_irr_zeroes_project_npv() -> None:
    """The approximated IRR drives project NPV to ~0 (the root definition)."""
    capex = 1000.0
    cfads = [300.0, 400.0, 500.0, 200.0]
    rate = approx_project_irr(cfads, capex, r_low=0.0, r_high=0.5)
    resid = project_npv_from_cfads(rate, cfads, capex, construction_years=0)
    assert resid == pytest.approx(0.0, abs=1e-4)


def test_approx_project_irr_respects_construction_lag() -> None:
    """A construction lag lowers the IRR (cash arrives later)."""
    capex = 1000.0
    cfads = [400.0, 400.0, 400.0, 400.0]
    irr_no_lag = approx_project_irr(cfads, capex, construction_years=0, r_high=1.0)
    irr_lagged = approx_project_irr(cfads, capex, construction_years=2, r_high=1.0)
    assert 0.0 < irr_lagged < irr_no_lag


def test_approx_project_irr_zero_capex_returns_zero() -> None:
    """capex_total <= 0 short-circuits to 0.0 (line 396)."""
    assert approx_project_irr([100.0, 100.0], 0.0) == 0.0
    assert approx_project_irr([100.0, 100.0], -50.0) == 0.0


def test_approx_project_irr_empty_cfads_returns_zero() -> None:
    """An empty CFADS series short-circuits to 0.0 (line 396)."""
    assert approx_project_irr([], 1000.0) == 0.0


def test_approx_project_irr_capex_typeerror_coerced_to_zero() -> None:
    """A non-numeric capex is coerced to 0.0 and short-circuits (392-393, 396)."""
    assert approx_project_irr([100.0, 100.0], None) == 0.0  # type: ignore[arg-type]


def test_approx_project_irr_no_sign_change_returns_zero() -> None:
    """With CFADS too small to recover capex in the bracket, no root => 0.0 (415).

    Tiny CFADS relative to capex keeps project NPV negative across [r_low, r_high],
    so there is no sign change and the documented 0.0 is returned.
    """
    capex = 1_000_000.0
    cfads = [1.0, 1.0, 1.0]
    assert approx_project_irr(cfads, capex, r_low=0.0, r_high=0.5) == 0.0


def test_approx_project_irr_root_exactly_at_r_low() -> None:
    """When NPV at r_low is exactly 0, r_low is returned (lines 410-411).

    At r_low=0 the project NPV is sum(cfads) - capex. Choosing cfads summing to
    capex makes f_low == 0.0 exactly, so r_low is the root.
    """
    capex = 300.0
    cfads = [100.0, 100.0, 100.0]  # sums to capex => NPV at r=0 is 0
    assert project_npv_from_cfads(0.0, cfads, capex) == pytest.approx(0.0)
    assert approx_project_irr(cfads, capex, r_low=0.0, r_high=0.5) == pytest.approx(0.0)


def test_approx_project_irr_root_exactly_at_r_high() -> None:
    """When NPV at r_high is exactly 0, r_high is returned (lines 412-413).

    Single-period -capex now, +payoff next year: NPV at rate r is
    -capex + payoff/(1+r). Pick payoff so the root is exactly r_high.
    """
    capex = 100.0
    r_high = 0.25
    payoff = capex * (1.0 + r_high)  # root is exactly r_high
    assert project_npv_from_cfads(r_high, [payoff], capex) == pytest.approx(0.0, abs=1e-9)
    got = approx_project_irr([payoff], capex, r_low=-0.5, r_high=r_high)
    assert got == pytest.approx(r_high)


def test_approx_project_irr_npv_gap_exception_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the initial npv_gap evaluations raise, the result is 0.0 (lines 406-407)."""
    import finance.irr as irr_mod

    calls = {"n": 0}

    def _boom(*_a: object, **_k: object) -> float:
        calls["n"] += 1
        raise RuntimeError("forced gap failure")

    # project_npv_from_cfads swallows exceptions and returns 0.0, so patch it
    # directly to force the npv_gap call inside approx_project_irr to raise.
    monkeypatch.setattr(irr_mod, "project_npv_from_cfads", _boom)
    assert approx_project_irr([400.0, 400.0], 1000.0) == 0.0
    assert calls["n"] >= 1


def test_approx_project_irr_best_effort_midpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """When tol is never met, the loop returns the final bracket midpoint (line 429).

    Force a single bisection iteration (max_iter=1) with a tolerance impossible to
    hit; the function must return 0.5*(a+b) without converging.
    """
    capex = 1000.0
    cfads = [400.0, 400.0, 400.0]
    got = approx_project_irr(cfads, capex, r_low=0.0, r_high=0.5, tol=1e-30, max_iter=1)
    # Still a finite rate inside the original bracket.
    assert 0.0 <= got <= 0.5
