"""Tax-loss carry-forward vintage behaviour (Wave-1 remediation).

Pins the two corrected behaviours of the loss-carry-forward engine:
  * losses EXPIRE after ``loss_carryforward_years`` (Sri Lanka: 6) — they no longer
    shield profit indefinitely;
  * losses are PRESERVED through tax-holiday years instead of being silently consumed
    against income that bears no tax anyway.
Also pins that the two cashflow builders thread the vintage ledger identically (no
two-sources-of-truth) and that the legacy scalar path is unchanged.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from finance.cashflow_v14 import build_annual_rows, build_annual_rows_efficient
from finance.cashflow_v14_tax import TaxProfile, build_tax_series, calculate_tax

_REPO = Path(__file__).resolve().parents[2]
_LENDER = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _profile(cap: int, holidays=None) -> TaxProfile:
    return TaxProfile(
        tax_rate=0.30,
        interest_deductibility=True,
        depreciation_method="straight_line",
        depreciation_schedule=[],
        allowable_losses_carryforward=cap > 0,
        withholding_tax_rate=0.0,
        tax_holidays_by_year=holidays or {},
        loss_carryforward_years=cap,
    )


def _tax(year, ebit, profile, vintages):
    return calculate_tax(
        year=year, ebit=ebit, interest_expense=0.0, depreciation=0.0,
        tax_profile=profile, prior_loss_vintages=vintages,
    )


# ── expiry ──────────────────────────────────────────────────────────────────────


def test_loss_expires_after_the_carryforward_window():
    p = _profile(cap=6)
    r1 = _tax(1, -100.0, p, ())  # year-1 loss of 100
    assert r1.carried_forward_vintages == ((1, 100.0),)
    v = r1.carried_forward_vintages
    for y in range(2, 8):  # years 2..7: no income, the loss just ages
        v = _tax(y, 0.0, p, v).carried_forward_vintages
    # year 8: the year-1 loss is 7 years old (> cap 6) -> expired, full tax on profit
    r8 = _tax(8, 200.0, p, v)
    assert r8.taxable_income == pytest.approx(200.0)
    assert r8.tax_liability == pytest.approx(60.0)


def test_loss_used_within_window_offsets_normally():
    p = _profile(cap=6)
    r1 = _tax(1, -100.0, p, ())
    r2 = _tax(2, 100.0, p, r1.carried_forward_vintages)  # within window
    assert r2.taxable_income == pytest.approx(0.0)
    assert r2.tax_liability == pytest.approx(0.0)
    assert r2.carried_forward_vintages == ()  # fully consumed


def test_fifo_oldest_first():
    p = _profile(cap=10)
    v = (_tax(1, -100.0, p, ()).carried_forward_vintages)
    v = _tax(2, -50.0, p, v).carried_forward_vintages  # (1,100),(2,50)
    r = _tax(3, 120.0, p, v)  # 120 offsets the year-1 100 then 20 of year-2 50
    assert r.taxable_income == pytest.approx(0.0)
    assert r.carried_forward_vintages == ((2, 30.0),)  # 20 of year-2 consumed, 30 left


# ── holiday preservation ──────────────────────────────────────────────────────


def test_losses_preserved_through_holiday():
    p = _profile(cap=6, holidays={2: True})
    r1 = _tax(1, -100.0, p, ())
    r2 = _tax(2, 100.0, p, r1.carried_forward_vintages)  # holiday + profit
    assert r2.tax_liability == 0.0  # holiday: no tax
    assert r2.carried_forward_vintages == ((1, 100.0),)  # loss NOT consumed
    r3 = _tax(3, 100.0, p, r2.carried_forward_vintages)  # non-holiday
    assert r3.taxable_income == pytest.approx(0.0)  # now the preserved loss offsets


# ── legacy scalar path unchanged ──────────────────────────────────────────────


def test_scalar_path_has_no_expiry():
    p = _profile(cap=6)
    # prior_loss_vintages omitted -> legacy scalar path: an "old" loss still offsets
    r = calculate_tax(year=8, ebit=200.0, interest_expense=0.0, depreciation=0.0,
                      tax_profile=p, prior_year_losses=100.0)
    assert r.taxable_income == pytest.approx(100.0)  # offset applied (no expiry)
    assert r.carried_forward_vintages == ()


# ── builders agree on the vintage path (holiday scenario) ─────────────────────


def test_build_tax_series_threads_vintages():
    p = _profile(cap=6, holidays={2: True, 3: True})
    res = build_tax_series(
        years=[1, 2, 3, 4],
        ebit_series=[-100.0, 100.0, 100.0, 100.0],
        interest_series=[0.0, 0.0, 0.0, 0.0],
        depreciation_schedule=type("D", (), {"annual_amounts": [0.0, 0.0, 0.0, 0.0]})(),
        tax_profile=p,
    )
    # year 1 loss preserved through holidays 2-3, then offsets profit in year 4
    assert res[1].tax_liability == 0.0 and res[2].tax_liability == 0.0  # holidays
    assert res[3].taxable_income == pytest.approx(0.0)  # year-4 profit offset by the loss


@pytest.mark.skipif(not _LENDER.exists(), reason="lendercase scenario not present")
def test_both_builders_agree_with_a_tax_holiday():
    """The vintage ledger must thread identically through both builders even with a
    holiday (the path the canonical lendercase does not exercise)."""
    import yaml

    cfg = yaml.safe_load(_LENDER.read_text())
    cfg["tax"]["tax_holiday_years"] = 3  # induce holiday years -> exercise preservation
    rows = build_annual_rows(cfg)
    eff = build_annual_rows_efficient(cfg)
    assert len(rows) == len(eff)
    for base_row, eff_row in zip(rows, eff):
        assert set(base_row.keys()) == set(eff_row.keys())
        for key in base_row:
            assert math.isclose(base_row[key], eff_row[key], rel_tol=1e-9, abs_tol=1e-6), key
