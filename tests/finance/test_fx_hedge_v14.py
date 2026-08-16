"""Unit tests for the FX-forward hedge lever (finance.cashflow_v14_fx + cashflow_v14).

The v14 engine is USD-equivalent-numeraire: FX risk enters only where LKR CFADS is
converted to ``cfads_usd`` (the stream debt sizing / DSCR run on). ``fx.hedge_ratio`` lets
a scenario convert part of that flow at a locked CIP forward rate instead of the projected
spot. Every expected value here is DERIVED from first principles (CIP compounding, the blend
formula) — no opaque economic constants — and the byte-identity invariant at hedge_ratio == 0
is asserted directly against the pure-spot arithmetic.

Direction note: the tests assert direction SELF-CONSISTENTLY against the forward-vs-spot
relationship they compute from the same rates, never a hardcoded "hedging helps/hurts" — the
sign is a property of the rate configuration, verified, not assumed.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List

import pytest

from finance.cashflow_v14 import build_annual_rows, build_annual_rows_efficient
from finance.cashflow_v14_contracts import FxHedge
from finance.cashflow_v14_fx import (
    _cip_forward_rates,
    _forward_curve,
    _hedged_usd,
    _resolve_fx_hedge,
)
from finance.cashflow_v14_params import validate_parameters

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
BASE_CONFIG: Dict[str, Any] = {
    "project": {
        "project_life_years": 6,
        "capacity_mw": 150.0,
        "capacity_factor_pct": 40.0,
        "degradation_pct": 0.5,
        "grid_loss_pct": 2.0,
        "corporate_tax_rate_pct": 30.0,
    },
    "tariff": {"lkr_per_kwh": 20.30},
    "opex": {"usd_per_year": 500_000.0},
    "statutory": {
        "success_fee_pct": 0.01,
        "env_surcharge_pct": 0.0025,
        "social_levy_pct": 0.0025,
    },
    "tax": {
        "corporate_tax_rate": 0.30,
        "depreciation_method": "straight_line",
        "depreciation_start_year": 1,
        "depreciation_years": 20,
        "enhanced_allowance_applies": False,
        "enhanced_capital_allowance_multiple": 1.0,
        "loss_carryforward_years": 25,
        "tax_holiday_start_year": 1,
        "tax_holiday_years": 0,
        "wht_on_interest_to_nonresidents": 0.0,
        "wht_on_interest_enabled": False,
        "wht_gross_up": False,
    },
    "risk": {"haircut_pct": 10.0},
    "fx": {
        "start_lkr_per_usd": 333.79,
        "annual_depr": 0.0589,
    },
    "capex": {"usd_total": 120_000_000.0},
    # CIP forward inputs: mirror the canonical lender-case rate resolution.
    "Financing_Terms": {
        "rates": {
            "lkr_nominal": 0.1339,
            "usd_nominal": 0.075,
        },
    },
}


def _cfg(**fx_overrides: Any) -> Dict[str, Any]:
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["fx"].update(fx_overrides)
    return cfg


# ---------------------------------------------------------------------------
# _cip_forward_rates
# ---------------------------------------------------------------------------
def test_cip_rates_resolve_nominal_keys() -> None:
    r_lkr, r_usd = _cip_forward_rates(BASE_CONFIG)
    assert r_lkr == pytest.approx(0.1339)
    assert r_usd == pytest.approx(0.075)


def test_cip_rates_percent_form_normalized() -> None:
    """A rate authored in percent form (> 1.0) is divided by 100 (mirrors _solve_mix)."""
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["Financing_Terms"]["rates"] = {"lkr_nominal": 13.39, "usd_nominal": 7.5}
    r_lkr, r_usd = _cip_forward_rates(cfg)
    assert r_lkr == pytest.approx(0.1339)
    assert r_usd == pytest.approx(0.075)


def test_cip_rates_fallback_min_keys() -> None:
    cfg = copy.deepcopy(BASE_CONFIG)
    cfg["Financing_Terms"]["rates"] = {"lkr_min": 0.12, "usd_commercial_min": 0.06}
    r_lkr, r_usd = _cip_forward_rates(cfg)
    assert r_lkr == pytest.approx(0.12)
    assert r_usd == pytest.approx(0.06)


def test_cip_rates_missing_resolve_zero() -> None:
    r_lkr, r_usd = _cip_forward_rates({"project": {}})
    assert r_lkr == 0.0 and r_usd == 0.0


def test_cip_rates_parity_with_debt_engine_on_every_config_shape() -> None:
    """_cip_forward_rates must resolve the SAME rates block the debt engine services the
    facility at, on every config shape — it delegates to debt_v14._extract_financing_terms,
    so this pins the parity contract (Fable review of cfb3908: a local mirror silently
    used debt.rates when a config carried BOTH financing.rates and debt.rates)."""
    from finance.debt_v14 import _extract_financing_terms, _rate_decimal

    shapes: list[Dict[str, Any]] = [
        # canonical
        {"Financing_Terms": {"rates": {"lkr_nominal": 0.13, "usd_nominal": 0.07}}},
        # case-insensitive section name
        {"FINANCING_TERMS": {"rates": {"lkr_min": 0.12, "usd_commercial_min": 0.06}}},
        # financing-only shape
        {"financing": {"rates": {"lkr_nominal": 0.11, "usd_nominal": 0.05}}},
        # BOTH financing and debt: the debt engine prefers financing -> so must we
        {
            "financing": {"rates": {"lkr_nominal": 0.14, "usd_nominal": 0.08}},
            "debt": {"rates": {"lkr_nominal": 0.99, "usd_nominal": 0.01}},
        },
        # debt-only shape (rates synthesized from interest_rate by the debt engine)
        {"debt": {"interest_rate": 0.09}},
    ]
    for cfg in shapes:
        terms = _extract_financing_terms(cfg)
        rates = terms.get("rates", {}) if isinstance(terms, dict) else {}
        expected_lkr = _rate_decimal(
            rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0
        )
        expected_usd = _rate_decimal(
            rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0
        )
        got_lkr, got_usd = _cip_forward_rates(cfg)
        assert (got_lkr, got_usd) == (expected_lkr, expected_usd), cfg


# ---------------------------------------------------------------------------
# _forward_curve
# ---------------------------------------------------------------------------
def test_forward_curve_is_geometric_cip_and_anchors_on_spot0() -> None:
    r_lkr, r_usd = 0.1339, 0.075
    spot0 = 333.79
    curve = _forward_curve(BASE_CONFIG, 6, spot0)
    ratio = (1.0 + r_lkr) / (1.0 + r_usd)
    expected = [spot0 * ratio**t for t in range(6)]
    assert len(curve) == 6
    for got, exp in zip(curve, expected, strict=True):
        assert math.isclose(got, exp, rel_tol=1e-12, abs_tol=1e-9)
    # t == 0 is exactly spot (a same-day forward is spot).
    assert curve[0] == pytest.approx(spot0)


def test_forward_curve_two_period_offset_advances_maturity() -> None:
    """The offset changes maturity, not the financial-close spot anchor."""
    spot0 = 333.79
    r_lkr, r_usd = _cip_forward_rates(BASE_CONFIG)
    ratio = (1.0 + r_lkr) / (1.0 + r_usd)
    curve = _forward_curve(BASE_CONFIG, 3, spot0, period_offset=2)
    expected = [spot0 * ratio**t for t in range(2, 5)]
    assert curve == pytest.approx(expected)
    assert curve[0] == pytest.approx(371.36921839342347)


def test_forward_curve_negative_offset_fails_loud() -> None:
    """Negative hedge maturities are invalid rather than silently clamped."""
    with pytest.raises(ValueError, match="period_offset must be non-negative"):
        _forward_curve(BASE_CONFIG, 3, 333.79, period_offset=-1)


def test_forward_drift_below_spot_for_canonical_rates() -> None:
    """With r_lkr built as additive UIP (usd + drift), CIP forward drift < spot drift."""
    r_lkr, r_usd = _cip_forward_rates(BASE_CONFIG)
    forward_drift = (1.0 + r_lkr) / (1.0 + r_usd) - 1.0
    spot_drift = BASE_CONFIG["fx"]["annual_depr"]
    assert forward_drift < spot_drift
    # Forward is LESS depreciated than spot -> hedging yields MORE USD (helps).


def test_forward_curve_raises_without_rates() -> None:
    with pytest.raises(ValueError, match="CIP forward rates could not be resolved"):
        _forward_curve({"project": {}}, 5, 333.79)


# ---------------------------------------------------------------------------
# _hedged_usd — the blend
# ---------------------------------------------------------------------------
def test_hedged_usd_zero_ratio_is_pure_spot_identity() -> None:
    """hedge_ratio == 0 returns EXACTLY value / spot (no blend arithmetic evaluated)."""
    value, spot, forward = 1_000_000.0, 333.79, 400.0
    assert _hedged_usd(value, spot, forward, 0.0, 0.0) == value / spot
    # Even a populated forward + spread must not perturb the null-hedge path.
    assert _hedged_usd(value, spot, forward, 0.0, 0.0025) == value / spot


def test_hedged_usd_full_hedge_uses_forward() -> None:
    value, spot, forward, spread = 1_000_000.0, 333.79, 400.0, 0.0025
    got = _hedged_usd(value, spot, forward, 1.0, spread)
    assert got == pytest.approx(value / (forward * (1.0 + spread)))


def test_hedged_usd_blend_is_convex_combination() -> None:
    value, spot, forward, h, spread = 1_000_000.0, 333.79, 400.0, 0.5, 0.0025
    got = _hedged_usd(value, spot, forward, h, spread)
    expected = (1 - h) * (value / spot) + h * (value / (forward * (1 + spread)))
    assert got == pytest.approx(expected)


def test_hedged_usd_raises_on_bad_forward_when_hedged() -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        _hedged_usd(1.0, 333.79, 0.0, 0.5, 0.0)


# ---------------------------------------------------------------------------
# _resolve_fx_hedge
# ---------------------------------------------------------------------------
def test_resolve_hedge_null_when_ratio_absent_or_zero() -> None:
    assert _resolve_fx_hedge(_cfg(), [333.79] * 6) == FxHedge()
    assert _resolve_fx_hedge(_cfg(hedge_ratio=0.0), [333.79] * 6) == FxHedge()
    # Null hedge builds no forward curve, so no Financing_Terms.rates is needed.
    assert _resolve_fx_hedge({"fx": {}}, [333.79] * 6).forward_curve == ()


def test_resolve_hedge_builds_forward_and_spread() -> None:
    hedge = _resolve_fx_hedge(_cfg(hedge_ratio=0.5, spread_bps=25.0), [333.79] * 6)
    assert hedge.hedge_ratio == pytest.approx(0.5)
    assert hedge.spread == pytest.approx(0.0025)  # 25 bps
    assert len(hedge.forward_curve) == 6
    assert hedge.forward_curve[0] == pytest.approx(333.79)


def test_resolve_hedge_uses_close_anchor_and_period_offset() -> None:
    """An active hedge compounds once from close to the first operating maturity."""
    operating_spot = 333.79 * 1.0589**2
    hedge = _resolve_fx_hedge(
        _cfg(hedge_ratio=1.0),
        [operating_spot] * 3,
        financial_close_spot=333.79,
        period_offset=2,
    )
    expected = _forward_curve(BASE_CONFIG, 3, 333.79, period_offset=2)
    assert hedge.forward_curve == pytest.approx(expected)
    assert hedge.forward_curve[0] == pytest.approx(371.36921839342347)


def test_resolve_offset_hedge_requires_close_anchor() -> None:
    """An operating curve alone cannot price a close-origin forward maturity."""
    with pytest.raises(ValueError, match="requires financial_close_spot"):
        _resolve_fx_hedge(
            _cfg(hedge_ratio=0.5),
            [374.2684496059] * 3,
            period_offset=2,
        )


@pytest.mark.parametrize("bad_close", [0.0, -1.0, float("nan"), float("inf")])
def test_resolve_hedge_rejects_invalid_close_anchor(bad_close: float) -> None:
    """The active hedge rejects non-positive or non-finite close anchors."""
    with pytest.raises(ValueError, match="finite and positive"):
        _resolve_fx_hedge(
            _cfg(hedge_ratio=0.5),
            [374.2684496059] * 3,
            financial_close_spot=bad_close,
            period_offset=2,
        )


def test_null_hedge_does_not_require_close_anchor_for_offset() -> None:
    """The pure-spot branch stays independent of forward configuration."""
    assert (
        _resolve_fx_hedge(
            _cfg(hedge_ratio=0.0),
            [374.2684496059] * 3,
            period_offset=2,
        )
        == FxHedge()
    )


def test_resolve_hedge_raises_when_hedged_but_no_rates() -> None:
    cfg = _cfg(hedge_ratio=0.5)
    cfg.pop("Financing_Terms")
    with pytest.raises(ValueError, match="CIP forward rates could not be resolved"):
        _resolve_fx_hedge(cfg, [333.79] * 6)


# ---------------------------------------------------------------------------
# Engine-level: byte-identity, both-builders-agree, direction
# ---------------------------------------------------------------------------
def test_no_hedge_byte_identical_to_pure_spot() -> None:
    """A config with no hedge keys yields the exact pre-hedge cfads_usd (value / spot)."""
    rows = build_annual_rows(_cfg())
    for row in rows:
        fx = row["fx_rate"]
        assert row["cfads_usd"] == row["cfads_final_lkr"] / fx
        assert row["revenue_usd"] == row["revenue_lkr"] / fx


def test_explicit_zero_hedge_byte_identical() -> None:
    base = build_annual_rows(_cfg())
    zero = build_annual_rows(_cfg(hedge_ratio=0.0, spread_bps=25.0))
    for rb, rz in zip(base, zero, strict=True):
        assert rb["cfads_usd"] == rz["cfads_usd"]
        assert rb["revenue_usd"] == rz["revenue_usd"]


def test_both_builders_agree_under_hedge() -> None:
    cfg = _cfg(hedge_ratio=0.5, spread_bps=25.0)
    rows_a = build_annual_rows(cfg)
    rows_b = build_annual_rows_efficient(cfg)
    assert len(rows_a) == len(rows_b) > 0
    for ra, rb in zip(rows_a, rows_b, strict=True):
        assert ra["cfads_usd"] == pytest.approx(rb["cfads_usd"], rel=1e-12)
        assert ra["revenue_usd"] == pytest.approx(rb["revenue_usd"], rel=1e-12)


def test_full_hedge_matches_forward_conversion_year_by_year() -> None:
    cfg = _cfg(hedge_ratio=1.0, spread_bps=0.0)
    rows = build_annual_rows(cfg)
    hedge = _resolve_fx_hedge(cfg, [r["fx_rate"] for r in rows])
    for i, row in enumerate(rows):
        assert row["cfads_usd"] == pytest.approx(
            row["cfads_final_lkr"] / hedge.forward_curve[i], rel=1e-12
        )


def test_hedged_cfads_usd_direction_tracks_forward_vs_spot() -> None:
    """The hedged cfads_usd direction is DERIVED from the config's own forward-vs-spot
    relationship (never hardcoded): forward below spot => hedging raises cfads_usd."""
    cfg = _cfg()
    r_lkr, r_usd = _cip_forward_rates(cfg)
    forward_drift = (1.0 + r_lkr) / (1.0 + r_usd) - 1.0
    forward_below_spot = forward_drift < float(cfg["fx"]["annual_depr"])

    base = build_annual_rows(cfg)
    hedged = build_annual_rows(_cfg(hedge_ratio=1.0, spread_bps=0.0))
    # Year 1 (t=0) forward == spot, so cfads_usd is unchanged there; later years diverge.
    for i in range(1, len(base)):
        if base[i]["cfads_final_lkr"] > 0:
            if forward_below_spot:
                assert hedged[i]["cfads_usd"] > base[i]["cfads_usd"]
            else:
                assert hedged[i]["cfads_usd"] < base[i]["cfads_usd"]


# ---------------------------------------------------------------------------
# Validation (fail-loud)
# ---------------------------------------------------------------------------
def test_validate_rejects_hedge_ratio_above_one() -> None:
    with pytest.raises(ValueError, match="fx.hedge_ratio"):
        validate_parameters(_cfg(hedge_ratio=1.5))


def test_validate_rejects_negative_hedge_ratio() -> None:
    with pytest.raises(ValueError, match="fx.hedge_ratio"):
        validate_parameters(_cfg(hedge_ratio=-0.1))


def test_validate_rejects_negative_spread_bps() -> None:
    with pytest.raises(ValueError, match="fx.spread_bps"):
        validate_parameters(_cfg(spread_bps=-1.0))


def test_validate_rejects_bool_hedge_ratio() -> None:
    """YAML `hedge_ratio: true` must fail loud, not float() to a silent FULL hedge."""
    with pytest.raises(ValueError, match="fx.hedge_ratio"):
        validate_parameters(_cfg(hedge_ratio=True))


def test_validate_rejects_non_finite_spread_bps() -> None:
    """`.nan` passes a bare `< 0.0` check; it must be rejected before it can propagate
    NaN into the load-bearing cfads_usd stream (Fable review of cfb3908)."""
    with pytest.raises(ValueError, match="fx.spread_bps"):
        validate_parameters(_cfg(hedge_ratio=0.5, spread_bps=float("nan")))
    with pytest.raises(ValueError, match="fx.spread_bps"):
        validate_parameters(_cfg(hedge_ratio=0.5, spread_bps=float("inf")))


def test_validate_rejects_non_finite_hedge_ratio() -> None:
    with pytest.raises(ValueError, match="fx.hedge_ratio"):
        validate_parameters(_cfg(hedge_ratio=float("nan")))


def test_validate_rejects_bool_spread_bps() -> None:
    with pytest.raises(ValueError, match="fx.spread_bps"):
        validate_parameters(_cfg(hedge_ratio=0.5, spread_bps=True))


def test_validate_accepts_valid_hedge() -> None:
    assert validate_parameters(_cfg(hedge_ratio=0.5, spread_bps=25.0)) == []


def test_engine_gate_blocks_nan_spread_end_to_end() -> None:
    """The engine pre-flight (validate_parameters inside _prepare_cashflow_context)
    must refuse a NaN spread on EVERY engine call — no silent NaN cfads_usd."""
    with pytest.raises(ValueError, match="fx.spread_bps"):
        build_annual_rows(_cfg(hedge_ratio=0.5, spread_bps=float("nan")))


# ---------------------------------------------------------------------------
# Schema-guard mirror
# ---------------------------------------------------------------------------
def test_schema_guard_rejects_bad_hedge_ratio() -> None:
    from analytics.schema_guard import _validate_fx_section

    errors: List[str] = []
    _validate_fx_section(
        {
            "fx": {
                "start_lkr_per_usd": 333.79,
                "annual_depr": 0.0589,
                "hedge_ratio": 2.0,
            }
        },
        errors,
    )
    assert any("hedge_ratio" in e for e in errors)


def test_schema_guard_rejects_negative_spread_bps() -> None:
    from analytics.schema_guard import _validate_fx_section

    errors: List[str] = []
    _validate_fx_section(
        {
            "fx": {
                "start_lkr_per_usd": 333.79,
                "annual_depr": 0.0589,
                "spread_bps": -5.0,
            }
        },
        errors,
    )
    assert any("spread_bps" in e for e in errors)
