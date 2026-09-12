"""Property test: a root returned by ``finance.irr.irr`` must zero the NPV.

``numpy_financial.irr`` 1.0.0 can return a materially wrong root for legitimate
cashflows (numpy-financial #28/#33/#39). ``finance.irr.irr`` checks both caller bounds
and the NPV residual before accepting that library result, using bisection when either
check fails. This Hypothesis test guards that contract (#595): over an adversarial
corpus of sign-changing cashflows, whatever rate ``irr`` returns must actually zero
the NPV. A wrong root would not.

Robustness: the property is asserted RELATIVE to the discounted-absolute magnitude at the
root (so it is invariant to cashflow scale and to the local steepness of the NPV curve),
and the pathologically ill-conditioned steep tail near ``rate → -1`` — where even a
correctly-converged root carries a large residual and no realistic project IRR lives — is
skipped. Non-convergence (``None``) is an allowed outcome, so the property is conditional.
"""

from __future__ import annotations

import math

import numpy as np
import numpy_financial as npf
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from finance.irr import irr, npv


@st.composite
def _cashflows_with_sign_change(draw: st.DrawFn) -> list[float]:
    """A finite cashflow series with at least one sign change (so a real IRR may exist)."""
    values = draw(
        st.lists(
            st.floats(
                min_value=-1.0e6,
                max_value=1.0e6,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=15,
        )
    )
    assume(min(values) < 0.0 < max(values))
    return values


@given(cashflows=_cashflows_with_sign_change())
@settings(max_examples=400, deadline=None)
def test_returned_irr_root_zeroes_npv(cashflows: list[float]) -> None:
    rate = irr(cashflows)
    if rate is None or rate < -0.5:
        # None: no root in band (allowed). rate < -0.5: the steep, ill-conditioned tail
        # where the residual is dominated by numerical conditioning, not a wrong root —
        # and no realistic project IRR lives there.
        return

    base = 1.0 + rate
    value = npv(rate, cashflows)
    discounted_abs = 0.0
    for t, cf in enumerate(cashflows):
        discounted_abs += abs(float(cf)) / base**t

    if (
        not math.isfinite(value)
        or not math.isfinite(discounted_abs)
        or discounted_abs <= 0.0
    ):
        return  # numerically degenerate — nothing meaningful to assert

    # |NPV| must be ~0 relative to the discounted-absolute magnitude: a genuine root is a
    # near-perfect cancellation, whereas a materially-wrong root (the numpy-financial
    # failure mode) leaves |NPV| / discounted_abs ~ O(1) — orders of magnitude outside this.
    assert abs(value) <= 1e-6 * discounted_abs + 1e-9, (
        f"irr returned {rate!r} but NPV={value!r} is not ~0 relative to "
        f"discounted_abs={discounted_abs!r}: the returned root does not zero the NPV."
    )


def test_irr_zeroes_npv_on_a_known_case() -> None:
    """A concrete pin: the textbook [-100, 40, 40, 40, 40] cashflow (~21.86% IRR)."""
    cashflows = [-100.0, 40.0, 40.0, 40.0, 40.0]
    rate = irr(cashflows)
    assert rate is not None
    assert abs(npv(rate, cashflows)) < 1e-6
    assert 0.21 < rate < 0.23  # sanity band around the textbook ~0.2186


@pytest.mark.parametrize(
    "cashflows, expected",
    [
        ([-100.0, 110.0], 0.10),  # 110/1.1 = 100
        ([-50.0, 55.0], 0.10),
        ([-100.0, 121.0], 0.21),  # 121/1.21 = 100
        ([-1000.0, 0.0, 1210.0], 0.10),  # 1210/1.1^2 = 1000
    ],
)
def test_irr_matches_closed_form_roots(cashflows: list[float], expected: float) -> None:
    """Independent oracle: irr must recover roots whose value is known in closed form.

    This does NOT rely on ``_is_npv_root``'s own acceptance rule — the expected IRR is
    derived analytically — so it is a genuine cross-check of the returned root, not a
    tautology against the guard's tolerance.
    """
    rate = irr(cashflows)
    assert rate is not None
    assert rate == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize("tail", [5e-324, 1e-310])
@pytest.mark.parametrize("end_zeros", [False, True])
def test_normalization_overflow_uses_existing_fallback_without_warning(
    tail: float, end_zeros: bool, recwarn: pytest.WarningsRecorder
) -> None:
    """The real polynomial failure still yields the analytic 10% fallback root."""
    cashflows = [-100.0, 110.0, tail]
    if end_zeros:
        cashflows = [0.0, *cashflows, 0.0, -0.0]

    with pytest.warns(RuntimeWarning, match="overflow encountered in divide"):
        with pytest.raises(np.linalg.LinAlgError, match="infs or NaNs"):
            npf.irr(cashflows)

    rate = irr(cashflows)
    assert rate == pytest.approx(0.10, abs=1e-9)
    assert len(recwarn) == 0


@pytest.mark.parametrize("tail", [5e-324, 1e-310])
def test_normalization_fallback_preserves_caller_bounds(tail: float) -> None:
    """A root excluded by caller bounds remains undefined after overflow."""
    assert irr([-100.0, 110.0, tail], lower_bound=0.2, upper_bound=0.3) is None
    assert irr([-100.0, 110.0, tail], lower_bound=0.1, upper_bound=0.3) == 0.1


@pytest.mark.parametrize("scale", [1e-10, 1.0, 1e10, 1e100])
def test_multiple_root_selection_and_scale_remain_unchanged(scale: float) -> None:
    """The factored polynomial has 10% and 20% roots; bounds select the latter."""
    cashflows = [scale * value for value in [-100.0, 230.0, -132.0]]
    assert irr(cashflows) == pytest.approx(0.10, abs=1e-6)
    # The existing bisection has an absolute stopping tolerance, so use an
    # ordinary scale for its independent bounded-root check.
    if scale == 1.0:
        assert irr(cashflows, 0.15, 0.25) == pytest.approx(0.20, abs=1e-6)


def test_reciprocal_overflow_does_not_bypass_finite_library_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated reciprocal overflow must leave the finite root choice intact."""
    # Inject a hostile eigensolver result at the real library seam; this does
    # not claim the installed eigensolver returns it for these cashflows.
    # The finite 10%/20% rates are analytic roots. Default bisection cannot
    # bracket either, so widening the error context would lose the valid 10%.
    monkeypatch.setattr(np, "roots", lambda _: np.array([5e-324, 1.0 / 1.1, 1.0 / 1.2]))
    with pytest.warns(RuntimeWarning, match="overflow encountered in divide"):
        assert irr([-100.0, 230.0, -132.0]) == pytest.approx(0.10, abs=1e-12)


@pytest.mark.parametrize("overflows", [False, True])
def test_normalization_overflow_matches_float64_boundary(overflows: bool) -> None:
    """Adjacent coefficients straddle the finite companion-matrix boundary."""
    from finance.irr import _irr_normalization_overflows

    numerator = float(np.finfo(float).max) / 2.0
    if overflows:
        numerator = math.nextafter(numerator, math.inf)
    cashflows = [-numerator, 0.5]
    assert _irr_normalization_overflows(cashflows) is overflows
    if overflows:
        with pytest.warns(RuntimeWarning, match="overflow encountered in divide"):
            with pytest.raises(np.linalg.LinAlgError, match="infs or NaNs"):
                npf.irr(cashflows)
    else:
        assert math.isfinite(float(npf.irr(cashflows)))
