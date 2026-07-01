#!/usr/bin/env python
"""The build-up WACC drives the discount rate (no longer a hardcoded 0.10).

Previously the project NPV was discounted at a hardcoded 10% and the computed WACC
was decorative. ``wacc.mode: build_up`` + ``wacc.drives_discount_rate`` now derive the
project discount rate from the after-tax WACC (computed from the ACTUAL sized debt)
and the equity discount rate from the cost of equity. The flag is opt-in, so configs
without it keep the legacy default — these tests lock both paths in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.wacc_sensitivity import ke_band_npv
from finance.wacc_v14 import build_wacc_build_up, resolve_cost_of_equity

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _kpis(overrides: dict) -> dict:
    return evaluate_with_overrides(LENDER_CONFIG, overrides=overrides)


def test_build_up_wacc_formula() -> None:
    """after-tax WACC = (1-g)*ke + g*(kd_pretax + fee)*(1-tax)."""
    w = build_wacc_build_up(
        debt_to_value=0.625,
        cost_of_debt_pretax=0.07628,
        cost_of_equity=0.12,
        tax_rate=0.30,
        debt_fee_rate=0.0082,
    )
    expected = 0.375 * 0.12 + 0.625 * (0.07628 + 0.0082) * (1 - 0.30)
    assert w.wacc_nominal == pytest.approx(expected, abs=1e-6)
    assert w.mode == "build_up"
    assert w.cost_of_equity == pytest.approx(0.12)


def test_cost_of_equity_resolves_direct_and_build_up() -> None:
    assert resolve_cost_of_equity({"cost_of_equity": 0.155}) == pytest.approx(0.155)
    built = resolve_cost_of_equity(
        {
            "build_up": {
                "risk_free": 4.5,
                "country_risk_premium": 7.0,
                "equity_risk_premium": 4.0,
            }
        }
    )
    assert built == pytest.approx(0.155, abs=1e-9)


def test_wacc_drives_project_discount_rate() -> None:
    """The lender case (build_up + drives_discount_rate) discounts at the WACC, not 0.10."""
    kpis = _kpis({})
    used = kpis["discount_rate_used"]
    assert used != pytest.approx(0.10)
    assert used == pytest.approx(
        0.09827, abs=0.002
    )  # ke=12%, gearing ~45%, kd up (PR-B UIP LKR rate 13.39%)
    # The project IRR (2.75%) is BELOW the WACC (~8.10% after the 5.9% FX-drift re-baseline),
    # so the project NPV is NEGATIVE (-$53.3M). The prior "+$5.9M / IRR 8.85%" was the
    # operating-year-1 off-by-one (year 1 undiscounted + the 2-yr lag ignored).
    assert kpis["project_npv"] < 0


def test_drives_discount_rate_flag_is_opt_in() -> None:
    """With the flag off, the project discount falls back to the legacy default (0.10)."""
    kpis = _kpis({"wacc.drives_discount_rate": False})
    assert kpis["discount_rate_used"] == pytest.approx(0.10)
    # The project IRR is 2.75% (5.9% FX-drift re-baseline), BELOW a flat 10% hurdle,
    # so the project NPV is NEGATIVE (~-$66.0M) at 0.10. The stale 300 FX had flattered
    # this to ~+$8M — an honest knife-edge the FX correction surfaced.
    assert kpis["project_npv"] < 0


def test_higher_ke_raises_wacc_and_lowers_project_npv() -> None:
    """The ke-band sweep is monotonic: higher cost of equity → higher WACC, lower NPV."""
    rows = ke_band_npv(LENDER_CONFIG, [0.12, 0.15, 0.20])
    waccs = [r["wacc"] for r in rows]
    npvs = [r["project_npv"] for r in rows]
    assert waccs[0] < waccs[1] < waccs[2]
    assert npvs[0] > npvs[1] > npvs[2]
    # The project IRR (2.75%, 5.9% FX-drift re-baseline) is below the WACC at EVERY ke in the
    # band, so project NPV is negative throughout (no sign flip) — it just gets more negative
    # as ke rises. (Pre-fix the off-by-one showed IRR 8.85% with a knife-edge crossover near
    # ke 0.13.) The monotonic ordering is the invariant under test.
    assert rows[0]["project_npv"] < 0
    assert rows[-1]["project_npv"] < 0


def test_equity_npv_discounts_at_cost_of_equity() -> None:
    """Raising ke makes equity NPV more negative (equity discounted at cost of equity)."""
    lo = _kpis({"wacc.cost_of_equity": 0.12})["equity_npv"]
    hi = _kpis({"wacc.cost_of_equity": 0.18})["equity_npv"]
    assert hi < lo
