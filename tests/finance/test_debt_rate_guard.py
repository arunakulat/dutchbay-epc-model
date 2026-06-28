"""A1/#65/#93: the debt engine must refuse to silently model COST-FREE debt.

When a scenario sizes a non-zero facility but omits an explicit tranche-rate
block, ``_solve_mix`` falls back to a 0.0 rate (and a 100%-USD residual),
servicing the whole facility at zero interest — which flatters CFADS-after-debt,
DSCR and equity IRR. ``apply_debt_layer`` now fails loud unless the
``allow_toy_fallback`` escape (the same opt-in already guarding toy CAPEX) is set.
"""

from __future__ import annotations

import pytest

from finance.debt_v14 import apply_debt_layer


def _rows(cfads: float, n: int = 5) -> list[dict[str, object]]:
    return [{"year": i + 1, "cfads_usd": cfads} for i in range(n)]


def _params(*, rates: dict | None = None, allow_toy: bool = False) -> dict:
    ft: dict = {
        "debt_ratio": 0.6,
        "tenor_years": 5,
        "construction_periods": 1,
        "mix": {"usd_commercial_min": 1.0},
    }
    if rates is not None:
        ft["rates"] = rates
    params: dict = {"Financing_Terms": ft, "capex": {"usd_total": 100.0}}
    if allow_toy:
        params["allow_toy_fallback"] = True
    return params


def test_sized_debt_with_no_rates_raises() -> None:
    """Debt sized > 0 with no rates block -> every tranche at 0.0 -> raise."""
    with pytest.raises(ValueError, match="cost-free debt"):
        apply_debt_layer(params=_params(rates=None), annual_rows=_rows(10.0))


def test_explicit_zero_rate_with_no_other_tranche_raises() -> None:
    """An explicit but all-zero rates block is still cost-free debt -> raise."""
    with pytest.raises(ValueError, match="0.0 interest rate"):
        apply_debt_layer(
            params=_params(rates={"usd_nominal": 0.0}), annual_rows=_rows(10.0)
        )


def test_allow_toy_fallback_bypasses_zero_rate_guard() -> None:
    """The explicit allow_toy_fallback escape permits cost-free toy debt."""
    core = apply_debt_layer(
        params=_params(rates=None, allow_toy=True), annual_rows=_rows(10.0)
    )
    assert core["debt_total"] == pytest.approx(60.0)
    assert core["avg_debt_rate"] == 0.0  # toy cost-free debt, explicitly opted in


def test_explicit_rates_do_not_trip_the_guard() -> None:
    """A real tranche rate sizes debt normally — the guard never fires."""
    core = apply_debt_layer(
        params=_params(rates={"usd_nominal": 0.08}), annual_rows=_rows(10.0)
    )
    assert core["debt_total"] == pytest.approx(60.0)
    assert core["avg_debt_rate"] > 0.0


def test_zero_debt_does_not_trip_the_guard() -> None:
    """debt_ratio 0 -> debt_total 0 -> the cost-free guard is irrelevant (no raise)."""
    params = _params(rates=None)
    params["Financing_Terms"]["debt_ratio"] = 0.0
    core = apply_debt_layer(params=params, annual_rows=_rows(10.0))
    assert core["debt_total"] == 0.0
