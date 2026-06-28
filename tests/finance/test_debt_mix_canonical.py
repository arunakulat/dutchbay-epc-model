#!/usr/bin/env python
"""The debt mix/rates are canonical; Financing_Terms.debt_tranches is not an input.

The engine sizes total debt via dual_dscr and splits it by ``Financing_Terms.mix``
proportions at ``Financing_Terms.rates`` (proportions are required because debt is
auto-sized, so absolute per-tranche principals cannot apply). A hand-authored
``Financing_Terms.debt_tranches`` list used to sit in the lender config as a
DECORATIVE restatement of mix+rates — editing its rates changed nothing. These
tests lock in that mix+rates govern ``avg_debt_rate`` and that a stray
``debt_tranches`` block is ignored (and warned about), so the trap can't recur.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import finance.debt_v14 as debt_v14
from analytics.evaluation_v14 import evaluate_with_overrides

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
RATES = "Financing_Terms.rates."
MIX = "Financing_Terms.mix."


def _debt(overrides: dict) -> dict:
    res = evaluate_with_overrides(
        LENDER_CONFIG, overrides=overrides, return_full_result=True
    )
    return res["debt_result"]


def test_baseline_avg_rate_is_mix_weighted_rates() -> None:
    """avg_debt_rate tracks the mix-weighted tranche rates. PR B raised the LKR (45%) tranche
    to the UIP-implied 13.39%: mix-weighted 0.45*13.39 + 0.10*6.5 + 0.45*7.5 = 10.05%; the
    realised principal-after-IDC weighting (the high-rate LKR tranche accrues more IDC) lifts
    it slightly to ~10.18%."""
    assert _debt({})["avg_debt_rate"] == pytest.approx(0.10178143097234378, abs=1e-4)


def test_rates_drive_avg_debt_rate() -> None:
    """Raising the USD (45%) tranche rate +3pp lifts avg_debt_rate by ~0.45*3pp."""
    base = _debt({})["avg_debt_rate"]
    bumped = _debt({RATES + "usd_nominal": 0.105})["avg_debt_rate"]
    assert bumped - base == pytest.approx(0.45 * 0.03, abs=2e-3)


def test_mix_drives_tranche_split() -> None:
    """Tranche principals follow the mix proportions, not any tranche table."""
    dr = _debt({MIX + "dfi_max": 0.20, MIX + "lkr_max": 0.40, MIX + "usd_commercial_min": 0.40})
    principal = dr["principal_by_tranche"]
    total = sum(principal.values())
    assert principal["dfi"] / total == pytest.approx(0.20, abs=0.02)
    # PR B's 13.39% LKR rate accrues proportionally more IDC on the LKR tranche, so its
    # principal-after-IDC share drifts ~2pp above its 0.40 mix share (the split still FOLLOWS
    # the mix; the IDC distortion just widens at the higher rate -> loosened band).
    assert principal["lkr"] / total == pytest.approx(0.40, abs=0.03)


def test_decorative_debt_tranches_is_ignored() -> None:
    """A re-added debt_tranches with absurd rates does NOT move avg_debt_rate."""
    base = _debt({})["avg_debt_rate"]
    bogus_tranches = [
        {"name": "USD_DFI", "currency": "USD", "rate_pct": 99.0, "principal_usd": 1},
        {"name": "LKR_Local", "currency": "LKR", "rate_pct": 99.0, "principal_lkr": 1},
    ]
    with_block = _debt({"Financing_Terms.debt_tranches": bogus_tranches})["avg_debt_rate"]
    assert with_block == pytest.approx(base, abs=1e-9)


def test_decorative_debt_tranches_warns(caplog: pytest.LogCaptureFixture) -> None:
    """plan_debt warns (once) when a non-input debt_tranches block is present."""
    debt_v14._warned_decorative_tranches = False
    with caplog.at_level(logging.WARNING, logger="finance.debt_v14"):
        _debt({"Financing_Terms.debt_tranches": [{"name": "X", "rate_pct": 5.0}]})
    assert any(
        "debt_tranches is NOT an engine input" in rec.message for rec in caplog.records
    )
    debt_v14._warned_decorative_tranches = False
