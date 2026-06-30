"""Tests for analytics.three_statement (#479 three-statement output + tie-outs)."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from analytics.three_statement import (
    build_three_statement,
    build_three_statement_from_run,
)


def _rows(n: int = 3) -> List[Dict[str, Any]]:
    """Internally-consistent enriched operating rows (LKR P&L + per-year USD debt; fx=100).

    Per-year USD debt: interest 10/8/6, service 30/28/26 -> principal 20 each -> retires a
    60 drawn debt to 0. No balloon.
    """
    interest = [10.0, 8.0, 6.0]
    service = [30.0, 28.0, 26.0]
    return [
        {
            "year": t + 1,
            "revenue_lkr": 1000.0,
            "opex_lkr": 200.0,
            "ebitda_lkr": 800.0,
            "total_depreciation_lkr": 500.0,
            "tax_lkr": 100.0,
            "fx_rate": 100.0,
            "interest_usd": interest[t],
            "debt_service_total": service[t],
            "balloon_resolution": 0.0,
        }
        for t in range(n)
    ]


def _build(rows, **kw):
    kw.setdefault("debt_drawn", 60.0)  # = sum of principals -> retires to 0
    kw.setdefault("balloon_residual", 0.0)
    kw.setdefault("gross_capitalised_cost", 60.0)
    return build_three_statement(rows, **kw)


# --------------------------------------------------------------------------- #
# Articulation invariants
# --------------------------------------------------------------------------- #
def test_balance_sheet_balances_and_all_tieouts_pass() -> None:
    res = _build(_rows(3), fx_rates=[100.0] * 3)
    assert res.tie_outs is not None
    assert res.tie_outs.all_pass
    assert res.tie_outs.max_abs_balance_residual <= res.tie_outs.tolerance
    assert all(abs(b.balance_residual) <= 1e-6 for b in res.balance_sheet)


def test_income_statement_subtracts_depreciation_and_uses_mapped_interest() -> None:
    res = _build(_rows(1), fx_rates=[100.0])
    i = res.income_statement[0]
    # USD via fx=100: ebitda 8, dep 5 -> EBIT 3. Interest is the per-row USD figure (10), NOT
    # the LKR placeholder; tax 1. NI = 3 - 10 - 1 = -8.
    assert i.ebitda == pytest.approx(8.0)
    assert i.ebit == pytest.approx(3.0)  # EBITDA − depreciation
    assert i.interest == pytest.approx(10.0)  # interest_usd (engine-mapped)
    assert i.net_income == pytest.approx(-8.0)


def test_retained_earnings_roll_forward() -> None:
    res = _build(_rows(3), fx_rates=[100.0] * 3)
    re_prev = 0.0
    for inc, bs, cf in zip(res.income_statement, res.balance_sheet, res.cash_flow):
        expected = re_prev + inc.net_income - (-cf.distributions)
        assert bs.retained_earnings == pytest.approx(expected)
        re_prev = bs.retained_earnings


def test_fx_conversion_scales_pl_only() -> None:
    usd = _build(_rows(1), fx_rates=[100.0], currency="USD")
    lkr = _build(_rows(1), fx_rates=None, currency="LKR")
    assert usd.currency == "USD" and lkr.currency == "LKR"
    # The LKR P&L scales 100x with fx; the per-row USD interest does NOT.
    assert usd.income_statement[0].revenue == pytest.approx(
        lkr.income_statement[0].revenue / 100.0
    )
    assert usd.income_statement[0].interest == lkr.income_statement[0].interest


# --------------------------------------------------------------------------- #
# The INDEPENDENT debt-retirement tie-out has teeth
# --------------------------------------------------------------------------- #
def test_debt_retires_to_residual_passes_when_consistent() -> None:
    res = _build(_rows(3), fx_rates=[100.0] * 3)
    assert res.tie_outs is not None
    assert res.tie_outs.debt_retires_to_residual is True
    assert res.tie_outs.debt_retirement_residual <= 1.0
    assert res.balance_sheet[-1].debt == pytest.approx(0.0, abs=1e-6)


def test_debt_retirement_tieout_catches_undersized_repayments() -> None:
    # Drawn debt 80 but the per-row principals only retire 60 -> debt does not reach residual.
    res = _build(_rows(3), fx_rates=[100.0] * 3, debt_drawn=80.0, balloon_residual=0.0)
    assert res.tie_outs is not None
    assert res.tie_outs.debt_retires_to_residual is False
    assert res.tie_outs.debt_retirement_residual == pytest.approx(20.0)


def test_balloon_residual_is_respected() -> None:
    # Drawn 70, principals retire 60 -> leaves a 10 balloon residual (consistent).
    res = _build(_rows(3), fx_rates=[100.0] * 3, debt_drawn=70.0, balloon_residual=10.0)
    assert res.tie_outs is not None
    assert res.tie_outs.debt_retires_to_residual is True
    assert res.balance_sheet[-1].debt == pytest.approx(10.0)


# --------------------------------------------------------------------------- #
# from_run wrapper
# --------------------------------------------------------------------------- #
def test_from_run_none_without_inputs() -> None:
    assert build_three_statement_from_run({"debt_result": {}}, {}) is None
    assert build_three_statement_from_run({"annual_rows": []}, {}) is None
    # No capex / no debt -> None.
    assert (
        build_three_statement_from_run(
            {"annual_rows": _rows(1), "debt_result": {"debt_total": 0.0}}, {}
        )
        is None
    )


def test_from_run_assembles_and_ties_out() -> None:
    pipeline_result = {
        "annual_rows": _rows(3),
        # debt_total 55 + IDC 5 = 60 drawn, retired by the 60 of principals -> residual 0.
        "debt_result": {"debt_total": 55.0, "total_idc": 5.0, "balloon_residual": 0.0},
    }
    config = {"capex": {"usd_total": 55.0}}  # gross capitalised = 55 + 5 IDC = 60
    res = build_three_statement_from_run(pipeline_result, config)
    assert res is not None
    assert res.currency == "USD"
    assert res.tie_outs is not None and res.tie_outs.all_pass
    assert res.to_dict()["tie_outs"]["debt_retires_to_residual"] is True
