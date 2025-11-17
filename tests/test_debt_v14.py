import math

from src.debt_v14 import (
    DebtProfile,
    calculate_drawdown_schedule,
    calculate_idc,
    build_debt_schedule_with_grace,
)


def test_drawdown_schedule_default_three_years():
    profile = DebtProfile(
        total_debt=100_000_000,
        annual_interest_rate=0.08,
        tenor_years=15,
        grace_years=2,
        construction_years=3,
    )

    drawdowns = calculate_drawdown_schedule(profile)

    # Default 40/40/20 split
    assert len(drawdowns) == 3
    assert math.isclose(sum(drawdowns), 100_000_000, rel_tol=1e-9)
    assert drawdowns[0] > drawdowns[-1]
    assert math.isclose(drawdowns[0], drawdowns[1], rel_tol=1e-9)


def test_drawdown_schedule_equal_weights_other_years():
    profile = DebtProfile(
        total_debt=60_000_000,
        annual_interest_rate=0.07,
        tenor_years=10,
        grace_years=2,
        construction_years=2,
    )

    drawdowns = calculate_drawdown_schedule(profile)

    assert len(drawdowns) == 2
    assert math.isclose(sum(drawdowns), 60_000_000, rel_tol=1e-9)
    # Equal weights => equal drawdowns
    assert math.isclose(drawdowns[0], drawdowns[1], rel_tol=1e-12)


def test_calculate_idc_capitalized():
    drawdowns = [40_000_000, 40_000_000, 20_000_000]
    total_idc, period_interest = calculate_idc(drawdowns, annual_interest_rate=0.08)

    assert len(period_interest) == len(drawdowns)
    assert total_idc > 0
    # Capitalized IDC should grow over time as outstanding increases
    assert period_interest[1] >= period_interest[0]
    assert period_interest[2] >= period_interest[1]


def test_build_debt_schedule_with_grace_shapes_and_zero_residual():
    profile = DebtProfile(
        total_debt=100_000_000,
        annual_interest_rate=0.08,
        tenor_years=15,
        grace_years=2,
        construction_years=3,
    )

    # Simple CFADS profile: flat 20m/year, plenty to amortise the loan
    cfads_after_cod = [20_000_000] * profile.tenor_years

    schedule = build_debt_schedule_with_grace(
        profile=profile,
        cfads_after_cod=cfads_after_cod,
        target_dscr=1.3,
    )

    for key in [
        "opening_balance",
        "interest",
        "principal",
        "debt_service",
        "closing_balance",
    ]:
        assert key in schedule
        assert len(schedule[key]) == profile.tenor_years

    # Grace period: principal repayments should be zero in first `grace_years`
    assert all(
        math.isclose(p, 0.0, abs_tol=1e-6)
        for p in schedule["principal"][: profile.grace_years]
    )

    # Loan should be fully repaid (or extremely close) by end of tenor
    assert math.isclose(schedule["closing_balance"][-1], 0.0, abs_tol=1e-4)

    