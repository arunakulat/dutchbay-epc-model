#!/usr/bin/env python3
"""
Core tests for dutchbay_v14chat.finance.irr

We verify:
- npv() matches the documented example.
- irr() returns a sensible root for the same cashflows.
- xnpv() and xirr() behave consistently with the current implementation
  for a simple dated two-cashflow case.
"""

from datetime import datetime

import pytest

from dutchbay_v14chat.finance.irr import npv, irr, xnpv, xirr


def test_npv_matches_doc_example():
    """
    Example from irr.py docstring:

        >>> npv(0.10, [-1000, 500, 500, 500])
        243.426...

    We assert it's close to that value.
    """
    cashflows = [-1000.0, 500.0, 500.0, 500.0]
    rate = 0.10

    value = npv(rate, cashflows)

    assert value == pytest.approx(243.425995, rel=1e-6, abs=1e-6)


def test_irr_matches_expected_range_for_example():
    """
    Example from irr.py docstring:

        >>> irr([-1000, 500, 500, 500])
        0.2343...

    We don't insist on exact 4dp, but it should be close.
    This should be stable whether numpy-financial is present or not.
    """
    cashflows = [-1000.0, 500.0, 500.0, 500.0]

    rate = irr(cashflows)

    assert rate is not None
    # Around 23.4%
    assert rate == pytest.approx(0.2343, abs=1e-3)


def test_xnpv_two_cashflows_one_year_apart_current_baseline():
    """
    Baseline XNPV behaviour for a simple dated case:

        -1000 on 2020-01-01
        +1100 on 2021-01-01
        discount rate = 10%

    With the current day-count convention / implementation,
    this yields approximately -0.1956896384.
    """
    cfs = [-1000.0, 1100.0]
    dates = [datetime(2020, 1, 1), datetime(2021, 1, 1)]

    value = xnpv(0.10, cfs, dates)

    # Lock in current baseline to avoid silent regressions.
    assert value == pytest.approx(-0.19568963838366926, abs=1e-9)


def test_xirr_recovers_current_baseline_rate_for_simple_case():
    """
    Baseline XIRR behaviour for the same two-cashflow case:

        -1000 on 2020-01-01
        +1100 on 2021-01-01

    Current implementation yields approximately 0.09978518245.
    """
    cfs = [-1000.0, 1100.0]
    dates = [datetime(2020, 1, 1), datetime(2021, 1, 1)]

    rate = xirr(cfs, dates)

    assert rate is not None
    # Lock in the current numerical solution as baseline.
    assert rate == pytest.approx(0.09978518245325468, abs=1e-9)


def test_xirr_raises_on_mismatched_lengths():
    """
    xirr() should raise ValueError if cashflows and dates differ in length.
    """
    cfs = [-1000.0, 1100.0]
    dates = [datetime(2020, 1, 1)]  # mismatched

    with pytest.raises(ValueError):
        xirr(cfs, dates)
