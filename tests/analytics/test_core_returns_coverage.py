#!/usr/bin/env python3
"""Coverage tests for analytics.core.returns — project & equity returns.

This module wraps the finance.irr singleton to produce Pydantic V2 returns
contracts (ProjectReturns / EquityReturns / AllReturns) plus the thin NPV /
IRR / MIRR helpers and the ReturnsConfig.from_yaml schema adapter.

The tests here drive the helper edge branches (empty / too-short / non-finite
series, negative discount rates, MIRR sign guards, the safe-float fallbacks)
and the schema adapter's Financing_Terms-vs-financing fallback (#36). Every
economic assertion is made against the LIVE finance.irr engine and documented
invariants — signs, bounds, monotonicity, conservation, recomputed NPV/IRR —
never against a hardcoded IRR / NPV / DSCR magic number.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from analytics.core.returns import (
    AllReturns,
    EquityReturns,
    ProjectReturns,
    ReturnsConfig,
    calculate_equity_returns,
    calculate_irr,
    calculate_mirr,
    calculate_npv,
    calculate_project_returns,
    summarize_all_returns,
)
from analytics.core.returns import (
    _safe_float,  # type: ignore[attr-defined]
)
from finance.irr import irr as _live_irr
from finance.irr import npv as _live_npv

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
def _base_config(**overrides: Any) -> ReturnsConfig:
    """A small, deterministic ReturnsConfig with sane lender-like defaults."""
    params: Dict[str, Any] = {
        "capex_usd": 100.0,
        "capex_fx_rate": 300.0,
        "debt_ratio": 0.6,
        "project_discount_rate": 0.10,
        "equity_discount_rate": 0.12,
    }
    params.update(overrides)
    return ReturnsConfig(**params)


def _profitable_cfads(years: int = 6, level: float = 8000.0) -> List[float]:
    """A flat, comfortably-profitable operating CFADS stream (LKR)."""
    return [level] * years


# ---------------------------------------------------------------------------
# _safe_float — lines 222, 227-228, 230-232
# ---------------------------------------------------------------------------
def test_safe_float_none_returns_none() -> None:
    assert _safe_float(None, context="x") is None


def test_safe_float_passes_through_finite() -> None:
    assert _safe_float("1.5", context="x") == 1.5
    assert _safe_float(3, context="x") == 3.0


def test_safe_float_nan_and_inf_return_none() -> None:
    assert _safe_float(float("nan"), context="nan") is None
    assert _safe_float(float("inf"), context="inf") is None
    assert _safe_float(float("-inf"), context="ninf") is None


def test_safe_float_bad_type_returns_none() -> None:
    # A non-convertible object triggers the TypeError/ValueError branch.
    assert _safe_float(object(), context="obj") is None
    assert _safe_float("not-a-number", context="str") is None


# ---------------------------------------------------------------------------
# calculate_npv — lines 265, 268-269, 275, 279-281
# ---------------------------------------------------------------------------
def test_calculate_npv_empty_series_is_zero() -> None:
    assert calculate_npv([], 0.10) == 0.0


def test_calculate_npv_negative_rate_returns_zero() -> None:
    # Negative discount rate is rejected (returns 0.0), distinct from a valid
    # zero rate which sums the cashflows.
    assert calculate_npv([100.0, 100.0], -0.01) == 0.0


def test_calculate_npv_zero_start_matches_live_engine() -> None:
    # start_period == 0 hits the else branch (no zero-padding); must equal the
    # live finance.irr.npv on the identical vector.
    cashflows = [-1000.0, 400.0, 400.0, 400.0]
    got = calculate_npv(cashflows, 0.10, start_period=0)
    assert got == pytest.approx(_live_npv(0.10, cashflows))


def test_calculate_npv_start_period_shifts_by_zeros() -> None:
    # start_period > 0 prepends zeros; equivalent to discounting the same flows
    # one period later. Compare against the explicitly zero-padded live engine.
    cashflows = [500.0, 500.0]
    shifted = calculate_npv(cashflows, 0.10, start_period=2)
    expected = _live_npv(0.10, [0.0, 0.0] + cashflows)
    assert shifted == pytest.approx(expected)
    # Pushing the same positive flows later strictly reduces present value.
    assert shifted < calculate_npv(cashflows, 0.10, start_period=0)


def test_calculate_npv_exception_path_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the delegated npv to raise so the except branch (logger + 0.0) runs.
    import analytics.core.returns as returns_mod

    def _boom(_rate: float, _cfs: List[float]) -> float:
        raise RuntimeError("npv exploded")

    monkeypatch.setattr(returns_mod, "_npv", _boom)
    assert returns_mod.calculate_npv([100.0, 100.0], 0.10) == 0.0


# ---------------------------------------------------------------------------
# calculate_irr — lines 301-302, 307-309
# ---------------------------------------------------------------------------
def test_calculate_irr_too_few_cashflows_returns_none() -> None:
    assert calculate_irr([]) is None
    assert calculate_irr([100.0]) is None


def test_calculate_irr_matches_live_engine() -> None:
    cashflows = [-1000.0, 600.0, 600.0]
    got = calculate_irr(cashflows)
    live = _live_irr(cashflows)
    assert got is not None
    assert live is not None
    assert got == pytest.approx(live)
    # Sanity: a real, positive IRR root for an investment with net gain.
    assert got > 0.0


def test_calculate_irr_exception_path_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    import analytics.core.returns as returns_mod

    def _boom(_cfs: List[float]) -> float:
        raise ValueError("irr exploded")

    monkeypatch.setattr(returns_mod, "_irr", _boom)
    assert returns_mod.calculate_irr([-1000.0, 600.0, 600.0]) is None


# ---------------------------------------------------------------------------
# calculate_mirr — lines 337, 355-358, 363-365
# ---------------------------------------------------------------------------
def test_calculate_mirr_too_few_cashflows_returns_none() -> None:
    assert calculate_mirr([], 0.1, 0.1) is None
    assert calculate_mirr([-100.0], 0.1, 0.1) is None


def test_calculate_mirr_all_positive_returns_none() -> None:
    # No negative cashflow => pv_negative == 0 (>= 0 guard) => None.
    assert calculate_mirr([100.0, 100.0, 100.0], 0.1, 0.1) is None


def test_calculate_mirr_all_negative_returns_none() -> None:
    # No positive cashflow => fv_positive == 0 (<= 0 guard) => None.
    assert calculate_mirr([-100.0, -100.0], 0.1, 0.1) is None


def test_calculate_mirr_valid_is_bounded_by_irr() -> None:
    # For a standard investment, MIRR sits between the reinvest rate and IRR.
    cashflows = [-1000.0, 600.0, 600.0]
    mirr = calculate_mirr(cashflows, 0.10, 0.10)
    irr = calculate_irr(cashflows)
    assert mirr is not None
    assert irr is not None
    # MIRR with reinvest_rate < IRR must be below IRR but above the reinvest rate.
    assert 0.10 < mirr < irr


def test_calculate_mirr_exception_path_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Drive the inner try/except (lines 363-365): make the final MIRR _safe_float
    # raise an OverflowError so the handler returns None.
    import analytics.core.returns as returns_mod

    real_safe_float = returns_mod._safe_float

    def _raising_safe_float(value: Any, context: str = "value") -> Any:
        if context == "MIRR":
            raise OverflowError("forced overflow in mirr final step")
        return real_safe_float(value, context)

    monkeypatch.setattr(returns_mod, "_safe_float", _raising_safe_float)
    assert returns_mod.calculate_mirr([-1000.0, 600.0, 600.0], 0.1, 0.1) is None


# ---------------------------------------------------------------------------
# ReturnsConfig.from_yaml — line 101 (lowercase financing fallback) + raises
# ---------------------------------------------------------------------------
def test_from_yaml_financing_terms_branch() -> None:
    # Canonical scenario carries 'Financing_Terms' (the primary branch, 99-100).
    cfg = yaml.safe_load(CANONICAL_SCENARIO.read_text())
    parsed = ReturnsConfig.from_yaml(cfg)
    assert 0.0 <= parsed.debt_ratio <= 1.0
    assert parsed.debt_ratio == pytest.approx(float(cfg["Financing_Terms"]["debt_ratio"]))
    assert parsed.capex_usd == pytest.approx(float(cfg["capex"]["usd_total"]))
    assert parsed.capex_fx_rate == pytest.approx(float(cfg["fx"]["start_lkr_per_usd"]))


def test_from_yaml_lowercase_financing_fallback() -> None:
    # When 'Financing_Terms' is absent (or not a dict), the lowercase
    # 'financing' adapter wins — covers line 101 (#36).
    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 1000.0},
        "fx": {"start_lkr_per_usd": 320.0},
        "financing": {"debt_ratio": 0.55},
        "returns": {"project_discount_rate": 0.09, "equity_discount_rate": 0.11},
    }
    parsed = ReturnsConfig.from_yaml(cfg)
    assert parsed.debt_ratio == pytest.approx(0.55)
    assert parsed.capex_usd == pytest.approx(1000.0)


def test_from_yaml_financing_terms_non_dict_falls_back() -> None:
    # 'Financing_Terms' present but not a dict => the isinstance guard sends us
    # to the lowercase fallback (also exercises line 100->101).
    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 500.0},
        "fx": {"start_lkr_per_usd": 300.0},
        "Financing_Terms": "not-a-dict",
        "financing": {"debt_ratio": 0.4},
        "returns": {"project_discount_rate": 0.08, "equity_discount_rate": 0.10},
    }
    parsed = ReturnsConfig.from_yaml(cfg)
    assert parsed.debt_ratio == pytest.approx(0.4)


def test_from_yaml_optional_mirr_rates_carried() -> None:
    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        "fx": {"start_lkr_per_usd": 300.0},
        "financing": {"debt_ratio": 0.5},
        "returns": {
            "project_discount_rate": 0.10,
            "equity_discount_rate": 0.12,
            "finance_rate": 0.07,
            "reinvest_rate": 0.09,
        },
    }
    parsed = ReturnsConfig.from_yaml(cfg)
    assert parsed.finance_rate == pytest.approx(0.07)
    assert parsed.reinvest_rate == pytest.approx(0.09)


def test_from_yaml_missing_key_raises_value_error() -> None:
    # Missing 'returns' block => KeyError re-raised as a descriptive ValueError.
    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 100.0},
        "fx": {"start_lkr_per_usd": 300.0},
        "financing": {"debt_ratio": 0.5},
    }
    with pytest.raises(ValueError, match="Required config key missing"):
        ReturnsConfig.from_yaml(cfg)


# ---------------------------------------------------------------------------
# calculate_project_returns — invariants vs live engine
# ---------------------------------------------------------------------------
def test_project_returns_invariants_against_live_engine() -> None:
    cfg = _base_config()
    cfads = _profitable_cfads()
    pr = calculate_project_returns(cfads, cfg)
    assert isinstance(pr, ProjectReturns)

    capex_lkr = cfg.capex_usd * cfg.capex_fx_rate
    # The audited full series convention: [-capex] + cfads.
    assert pr.cashflows_with_capex == [-capex_lkr] + cfads
    # IRR matches the live engine on the identical full series.
    assert pr.project_irr == pytest.approx(_live_irr(pr.cashflows_with_capex))
    # NPV matches the live engine with the operation-start zero-padding.
    expected_npv = _live_npv(
        cfg.project_discount_rate,
        [0.0] * cfg.operation_start_year + cfads,
    )
    assert pr.project_npv == pytest.approx(expected_npv)
    # Profitability index is NPV / CAPEX by construction.
    assert pr.profitability_index == pytest.approx(pr.project_npv / capex_lkr)
    # Profitable stream pays back within the operating horizon.
    assert pr.payback_period is not None and 1 <= pr.payback_period <= len(cfads)


def test_project_returns_payback_none_when_never_recovered() -> None:
    # Tiny CFADS never reaches CAPEX => payback stays None.
    cfg = _base_config(capex_usd=1_000_000.0, capex_fx_rate=300.0)
    pr = calculate_project_returns([1.0, 1.0, 1.0], cfg)
    assert pr.payback_period is None


# ---------------------------------------------------------------------------
# calculate_equity_returns — line 477 raise + invariants
# ---------------------------------------------------------------------------
def test_equity_returns_length_mismatch_raises() -> None:
    cfg = _base_config()
    with pytest.raises(ValueError, match="length mismatch"):
        calculate_equity_returns([1.0, 2.0, 3.0], [1.0, 2.0], cfg)


def test_equity_returns_invariants_against_live_engine() -> None:
    cfg = _base_config()
    cfads = _profitable_cfads()
    debt_service = [3000.0] * len(cfads)
    er = calculate_equity_returns(cfads, debt_service, cfg)
    assert isinstance(er, EquityReturns)

    total_investment = cfg.capex_usd * cfg.capex_fx_rate
    equity_investment = total_investment * (1.0 - cfg.debt_ratio)
    expected_ecf = [c - d for c, d in zip(cfads, debt_service)]
    # Equity CF conservation: CFADS - debt service, element-wise.
    assert er.equity_cashflows == pytest.approx(expected_ecf)
    assert er.equity_cashflows_with_investment == [-equity_investment] + expected_ecf
    # IRR / NPV must match the live engine on the equity vectors.
    assert er.equity_irr == pytest.approx(_live_irr(er.equity_cashflows_with_investment))
    expected_npv = _live_npv(
        cfg.equity_discount_rate,
        [0.0] * cfg.equity_start_year + expected_ecf,
    )
    assert er.equity_npv == pytest.approx(expected_npv)
    assert er.equity_pi == pytest.approx(er.equity_npv / equity_investment)


def test_equity_returns_payback_none_when_never_recovered() -> None:
    cfg = _base_config()
    cfads = [100.0, 100.0, 100.0]
    # Debt service nearly equals CFADS => equity cumulative never reaches the
    # equity investment => payback None.
    debt_service = [99.0, 99.0, 99.0]
    er = calculate_equity_returns(cfads, debt_service, cfg)
    assert er.equity_payback_period is None


# ---------------------------------------------------------------------------
# summarize_all_returns — conservation & leverage invariants
# ---------------------------------------------------------------------------
def test_summarize_all_returns_conservation_and_uplift() -> None:
    cfg = _base_config()
    cfads = _profitable_cfads()
    debt_service = [3000.0] * len(cfads)
    summary = summarize_all_returns(cfads, debt_service, cfg)
    assert isinstance(summary, AllReturns)

    # Capital conservation: debt + equity == total CAPEX (LKR).
    assert summary.debt_investment_lkr + summary.equity_investment_lkr == pytest.approx(
        summary.total_capex_lkr
    )
    # Ratios conserve to 1.0.
    assert summary.debt_ratio + summary.equity_ratio == pytest.approx(1.0)
    # Sub-contracts are consistent with the standalone calculators.
    standalone_project = calculate_project_returns(cfads, cfg)
    assert summary.project_returns.project_irr == pytest.approx(
        standalone_project.project_irr
    )
    # IRR uplift is exactly equity IRR minus project IRR (with None->0.0 guard).
    pj = summary.project_returns.project_irr or 0.0
    eq = summary.equity_returns.equity_irr or 0.0
    assert summary.irr_uplift == pytest.approx(eq - pj)


def test_summarize_all_returns_leverage_raises_equity_irr() -> None:
    # With cheap debt and a profitable project, leverage should lift equity IRR
    # above project IRR (positive uplift) — a documented economic invariant.
    cfg = _base_config(debt_ratio=0.6)
    cfads = _profitable_cfads(years=8, level=9000.0)
    # Modest debt service well below CFADS so equity keeps the residual.
    debt_service = [2500.0] * len(cfads)
    summary = summarize_all_returns(cfads, debt_service, cfg)
    assert summary.project_returns.project_irr is not None
    assert summary.equity_returns.equity_irr is not None
    assert summary.irr_uplift > 0.0


# ---------------------------------------------------------------------------
# End-to-end on the canonical scenario (real schema, not magic numbers)
# ---------------------------------------------------------------------------
def test_canonical_scenario_roundtrip_is_finite_and_consistent() -> None:
    cfg_dict = yaml.safe_load(CANONICAL_SCENARIO.read_text())
    cfg = ReturnsConfig.from_yaml(cfg_dict)
    # Synthetic but realistically-scaled operating CFADS (LKR) over project life.
    years = int(cfg_dict["returns"].get("project_life_years", 20))
    capex_lkr = cfg.capex_usd * cfg.capex_fx_rate
    # ~14% of CAPEX per year — comfortably above debt service, deterministic.
    cfads = [capex_lkr * 0.14] * years
    debt_service = [capex_lkr * cfg.debt_ratio * 0.10] * years

    summary = summarize_all_returns(cfads, debt_service, cfg)
    assert math.isfinite(summary.total_capex_lkr)
    assert summary.total_capex_lkr == pytest.approx(capex_lkr)
    # NPV finite; PI finite; IRR (if found) within engine bounds.
    assert math.isfinite(summary.project_returns.project_npv)
    if summary.project_returns.project_irr is not None:
        assert -0.9999 <= summary.project_returns.project_irr <= 5.0
