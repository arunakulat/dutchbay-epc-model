import pandas as pd

from src.equity_analysis_v14 import (
    generate_comprehensive_equity_table_v14,
    calculate_payback_period,
)


def test_generate_comprehensive_equity_table_shapes_and_columns():
    years = [-2, -1, 0, 1, 2, 3]
    cfads = [-20.0, -20.0, 0.0, 15.0, 15.0, 15.0]
    tax = [0.0] * len(years)
    debt_service = [0.0, 0.0, 0.0, 5.0, 5.0, 5.0]

    equity_commitment_lkr = 40.0
    usd_equity_pct = 0.6
    lkr_equity_pct = 0.4
    usd_fx_rates = [300.0] * len(years)

    df = generate_comprehensive_equity_table_v14(
        years=years,
        cfads=cfads,
        tax=tax,
        debt_service=debt_service,
        equity_commitment_lkr=equity_commitment_lkr,
        usd_equity_pct=usd_equity_pct,
        lkr_equity_pct=lkr_equity_pct,
        usd_fx_rates=usd_fx_rates,
        bank_equivalent_rate=0.08,
    )

    assert isinstance(df, pd.DataFrame)
    assert len(df) == len(years)

    expected_cols = {
        "year",
        "cfads",
        "tax",
        "debt_service",
        "equity_cashflow",
        "cum_equity_invested",
        "equity_balance",
        "usd_equity_balance",
        "lkr_equity_balance",
        "usd_equity_balance_usd",
        "bank_equivalent_yield",
    }
    assert expected_cols.issubset(set(df.columns))


def test_calculate_payback_period_simple_case():
    years = [-2, -1, 0, 1, 2, 3]
    equity_cashflow = [-20.0, -20.0, 0.0, 15.0, 15.0, 15.0]

    # Cumulative: -20, -40, -40, -25, -10, +5 -> payback at year=3
    payback = calculate_payback_period(years, equity_cashflow)

    assert payback == 3

    