from __future__ import annotations

from typing import Sequence

import pytest

from finance.equity_v14 import (
    EquityCashflowSummary,
    calculate_cash_on_cash,
    calculate_equity_irr,
    calculate_equity_npv,
    calculate_equity_performance,
    calculate_moic,
    calculate_payback_period,
    calculate_pe_triad,
    summarise_equity_cashflows,
)
from finance.irr import irr as core_irr


def _approx(x: float, rel: float = 1e-6) -> float:
    """Tiny helper to keep approx tolerances readable."""
    return pytest.approx(x, rel=rel)


def test_summarise_equity_cashflows_basic() -> None:
    # -120 = contribution, +30 +40 +70 = distributions
    raw = [-120.0, 30.0, 40.0, 70.0]
    summary: EquityCashflowSummary = summarise_equity_cashflows(raw)

    assert summary.cashflows == raw
    # Total invested is absolute sum of negative legs
    assert summary.total_invested == _approx(120.0)
    # Cumulative distributions is sum of positive legs
    assert summary.cumulative_distributions == _approx(140.0)


def test_calculate_equity_irr_standard_case_matches_core_irr() -> None:
    # Simple two-period: invest 100, receive 120 next year.
    cashflows: Sequence[float] = [-100.0, 120.0]

    eq_irr = calculate_equity_irr(cashflows)
    core = core_irr(cashflows)

    assert eq_irr is not None
    assert eq_irr == _approx(core)  # should be ~0.20


def test_calculate_equity_irr_no_sign_change_returns_none() -> None:
    # All non-negative: no true IRR in the sense we want.
    assert calculate_equity_irr([10.0, 20.0, 30.0]) is None
    # All non-positive: also meaningless from an investor-IRR standpoint.
    assert calculate_equity_irr([-10.0, -20.0]) is None
    # Empty / degenerate
    assert calculate_equity_irr([]) is None


def test_calculate_equity_npv_respects_discount_rate() -> None:
    # Invest 100, receive 120 next year; at 10% discount rate:
    # NPV = -100 + 120 / 1.1 ≈ 9.0909
    cashflows = [-100.0, 120.0]
    npv = calculate_equity_npv(cashflows, discount_rate=0.10)

    assert npv is not None
    assert npv == _approx(-100.0 + 120.0 / 1.10)


def test_calculate_cash_on_cash_basic() -> None:
    annual_distributions = [10.0, 20.0, 30.0]
    total_invested = 100.0

    coc = calculate_cash_on_cash(annual_distributions, total_invested)

    assert coc == [_approx(0.10), _approx(0.20), _approx(0.30)]


def test_calculate_cash_on_cash_handles_zero_invested() -> None:
    assert calculate_cash_on_cash([10.0, 20.0], total_equity_invested=0.0) == []
    assert calculate_cash_on_cash([10.0], total_equity_invested=-50.0) == []


def test_calculate_moic_basic() -> None:
    # 150 returned so far, 50 NAV, 100 invested → MOIC = (150+50)/100 = 2.0
    moic = calculate_moic(150.0, 50.0, total_invested=100.0)
    assert moic == _approx(2.0)


def test_calculate_moic_invalid_invested() -> None:
    assert calculate_moic(100.0, 0.0, total_invested=0.0) is None
    assert calculate_moic(100.0, 0.0, total_invested=-10.0) is None


def test_calculate_payback_period_fractional_year() -> None:
    # Initial equity 100.
    # Distributions: 30, 40, 50 → cumulative 30, 70, 120.
    # Payback occurs in year 3.
    # Shortfall at end of year 2 = 100 - 70 = 30.
    # Fraction of year 3 needed = 30 / 50 = 0.6.
    # Payback ≈ 2.6 years.
    annual_dists = [30.0, 40.0, 50.0]
    payback = calculate_payback_period(annual_dists, initial_equity=100.0)

    assert payback is not None
    assert payback == _approx(2.6)


def test_calculate_payback_period_handles_never_payback() -> None:
    # Total distributions never reach initial equity.
    annual_dists = [10.0, 20.0, 30.0]
    payback = calculate_payback_period(annual_dists, initial_equity=200.0)
    assert payback is None


def test_calculate_pe_triad_basic() -> None:
    dpi, rvpi, tvpi = calculate_pe_triad(
        cumulative_distributions=150.0,
        current_nav=50.0,
        capital_called=100.0,
    )

    assert dpi == _approx(1.5)
    assert rvpi == _approx(0.5)
    assert tvpi == _approx(2.0)


def test_calculate_pe_triad_invalid_capital_called() -> None:
    dpi, rvpi, tvpi = calculate_pe_triad(
        cumulative_distributions=100.0,
        current_nav=50.0,
        capital_called=0.0,
    )
    assert dpi is None and rvpi is None and tvpi is None


def test_calculate_equity_performance_happy_path() -> None:
    # Simple toy equity profile:
    # Year 0: -100 (investment)
    # Year 1–3: +20, +30, +60  → total distributions = 110
    cashflows = [-100.0, 20.0, 30.0, 60.0]

    perf = calculate_equity_performance(
        cashflows,
        discount_rate=0.10,
        current_nav=0.0,
    )
    assert perf is not None

    # MOIC: (110 + 0) / 100 = 1.1
