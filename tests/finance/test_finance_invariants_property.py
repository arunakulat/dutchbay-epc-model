"""Property-based (Hypothesis) invariants for the v14 finance numerics (#491, audit §4.10).

The pinned regression tests assert exact KPIs for specific scenarios; these complement
them by asserting *structural* invariants that must hold across whole input RANGES — the
kind of property a single pinned example can silently violate after a refactor. They cover
the load-bearing primitives: the NPV/IRR core (``finance.irr``) and the BESS
state-of-health curve (``finance.bess_revenue.mdsc_soh_for_year``).

Deterministic by design (``derandomize=True`` + no deadline) so CI is reproducible
(MRM-01) and never flakes on a slow runner.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from finance.bess_revenue import mdsc_soh_for_year
from finance.irr import irr, npv

# Reproducible + fast: a fixed-seed sweep, no per-example wall-clock deadline.
_SETTINGS = settings(max_examples=150, deadline=None, derandomize=True)

# Money-scale finite floats kept in a bounded range so float summation error stays small
# relative to the assertion tolerances (the invariants are exact in real arithmetic).
_money = st.floats(
    min_value=-1.0e6, max_value=1.0e6, allow_nan=False, allow_infinity=False
)
_nonneg = st.floats(
    min_value=0.0, max_value=1.0e6, allow_nan=False, allow_infinity=False
)
# Discount rates strictly above -1 (npv clamps <= -1 to -0.9999, which would break the
# pure-arithmetic invariants), capped at a sane upper bound.
_rate = st.floats(min_value=-0.95, max_value=2.0, allow_nan=False, allow_infinity=False)


@_SETTINGS
@given(cashflows=st.lists(_money, min_size=1, max_size=30))
def test_npv_at_zero_rate_equals_undiscounted_sum(cashflows: list[float]) -> None:
    """At a 0% discount rate, NPV is just the undiscounted sum of the cashflows."""
    scale = sum(abs(c) for c in cashflows) + 1.0
    assert math.isclose(
        npv(0.0, cashflows), sum(cashflows), rel_tol=1e-9, abs_tol=1e-6 * scale
    )


@_SETTINGS
@given(rate=_rate, data=st.data())
def test_npv_is_additive_in_cashflows(rate: float, data: st.DataObject) -> None:
    """NPV is linear: npv(r, a) + npv(r, b) == npv(r, a + b) for matching periods."""
    n = data.draw(st.integers(min_value=1, max_value=25))
    a = data.draw(st.lists(_money, min_size=n, max_size=n))
    b = data.draw(st.lists(_money, min_size=n, max_size=n))
    combined = [x + y for x, y in zip(a, b)]
    scale = sum(abs(x) for x in a + b) + 1.0
    assert math.isclose(
        npv(rate, a) + npv(rate, b),
        npv(rate, combined),
        rel_tol=1e-9,
        abs_tol=1e-6 * scale,
    )


@_SETTINGS
@given(
    outflow=st.floats(
        min_value=1.0, max_value=1.0e6, allow_nan=False, allow_infinity=False
    ),
    inflows=st.lists(_nonneg, min_size=1, max_size=25),
    r1=_rate,
    r2=_rate,
)
def test_npv_is_monotone_decreasing_in_rate_for_conventional_cashflows(
    outflow: float, inflows: list[float], r1: float, r2: float
) -> None:
    """For a conventional series (one upfront outflow, then non-negative inflows), NPV is
    non-increasing in the discount rate — a higher rate never raises the present value.
    """
    cashflows = [-outflow, *inflows]
    lo, hi = sorted((r1, r2))
    # A tiny tolerance absorbs float noise when the two rates are nearly equal.
    assert npv(lo, cashflows) >= npv(hi, cashflows) - 1e-6 * (outflow + 1.0)


@_SETTINGS
@given(
    outflow=st.floats(
        min_value=1.0e3, max_value=1.0e6, allow_nan=False, allow_infinity=False
    ),
    inflows=st.lists(
        st.floats(
            min_value=1.0, max_value=1.0e6, allow_nan=False, allow_infinity=False
        ),
        min_size=2,
        max_size=25,
    ),
)
def test_irr_is_a_root_of_npv(outflow: float, inflows: list[float]) -> None:
    """When IRR converges on a conventional series whose inflows exceed the outflow, the
    returned rate is (numerically) a root of NPV: npv(irr, cashflows) ~= 0."""
    # Ensure a positive IRR exists: total inflow strictly exceeds the upfront outflow.
    if sum(inflows) <= outflow:
        inflows = [*inflows, outflow + 1.0]
    cashflows = [-outflow, *inflows]
    rate = irr(cashflows)
    if rate is None:  # non-convergence is allowed (FIN-01); nothing to assert
        return
    scale = outflow + sum(inflows)
    assert abs(npv(rate, cashflows)) <= 1e-4 * scale


@_SETTINGS
@given(
    fade=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    floor=st.floats(
        min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
    ),
    t=st.integers(min_value=0, max_value=40),
)
def test_mdsc_soh_is_bounded_and_non_increasing_without_augmentation(
    fade: float, floor: float, t: int
) -> None:
    """Without augmentation the state-of-health curve stays within [floor, 1] and never
    rises from one operating year to the next (it only fades)."""
    spec = {
        "mdsc_fade_pct_annual": fade,
        "mdsc_floor_soh": floor,
        "augmentation_events": [],
    }
    soh_t = mdsc_soh_for_year(spec, t)
    soh_next = mdsc_soh_for_year(spec, t + 1)
    assert floor - 1e-12 <= soh_t <= 1.0 + 1e-12
    assert soh_next <= soh_t + 1e-12  # monotone non-increasing
