"""Coverage-hardening tests for finance.wacc_v14.

These exercise the helper utilities, the pure builders, the build-up path,
and the CAPM / fixed / error branches of ``compute_wacc_from_config`` that the
existing suite leaves uncovered. Every expectation is derived from first
principles (the documented formulae) or asserts a documented ``raise`` /
structural invariant — no economic magic numbers are hardcoded.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

import pytest

from finance import wacc_v14

# =============================================================================
# Helper utilities
# =============================================================================


def test_as_float_or_none_handles_none_and_uncastable() -> None:
    assert wacc_v14._as_float_or_none(None) is None
    # A non-castable object triggers the (TypeError, ValueError) branch.
    assert wacc_v14._as_float_or_none(object()) is None
    assert wacc_v14._as_float_or_none("not-a-number") is None
    # A well-formed numeric string casts cleanly.
    assert wacc_v14._as_float_or_none("3.5") == pytest.approx(3.5)


def test_pct_to_decimal_none_and_threshold() -> None:
    assert wacc_v14._pct_to_decimal(None) is None
    # > 1.0 is treated as a percentage; <= 1.0 stays a decimal.
    assert wacc_v14._pct_to_decimal(24.0) == pytest.approx(0.24)
    assert wacc_v14._pct_to_decimal(0.24) == pytest.approx(0.24)
    assert wacc_v14._pct_to_decimal(1.0) == pytest.approx(1.0)


def test_get_nested_returns_default_on_non_dict_chain() -> None:
    # Walking into a non-dict mid-chain returns the default (line 154).
    d: Dict[str, Any] = {"tax": 5}
    assert wacc_v14.get_nested(d, ["tax", "corporate_tax_rate_pct"], default="x") == "x"
    # Missing key also returns the default.
    assert wacc_v14.get_nested({}, ["a"], default=None) is None
    # Happy path resolves the nested value.
    assert wacc_v14.get_nested({"a": {"b": 7}}, ["a", "b"]) == 7


def test_parse_prudential_spread_bps_variants() -> None:
    # None -> default.
    assert wacc_v14._parse_prudential_spread_bps(None, default_bps=42) == 42
    # Numeric passthrough.
    assert wacc_v14._parse_prudential_spread_bps(125) == 125
    assert wacc_v14._parse_prudential_spread_bps(75.9) == 75
    # "bps" suffix.
    assert wacc_v14._parse_prudential_spread_bps("100bps") == 100
    # "bp" suffix (line 194-195).
    assert wacc_v14._parse_prudential_spread_bps("50bp") == 50
    # Signed string.
    assert wacc_v14._parse_prudential_spread_bps("+25") == 25


def test_parse_prudential_spread_bps_bad_string_raises() -> None:
    # Non-numeric string body hits the ValueError re-raise (lines 201-202).
    with pytest.raises(ValueError, match="Invalid prudential_spread_bps"):
        wacc_v14._parse_prudential_spread_bps("abc")


def test_parse_prudential_spread_bps_bad_type_raises() -> None:
    # Unsupported type hits the trailing raise (line 205).
    with pytest.raises(ValueError, match="Invalid prudential_spread_bps type"):
        wacc_v14._parse_prudential_spread_bps([100])


# =============================================================================
# Pure builders — bounds / raises
# =============================================================================


def test_build_wacc_rejects_out_of_range_debt_to_value() -> None:
    with pytest.raises(ValueError, match="Invalid debt_to_value"):
        wacc_v14.build_wacc(
            risk_free_rate=0.05,
            asset_beta=0.8,
            market_risk_premium=0.06,
            debt_to_value=1.0,  # not < 1.0
            cost_of_debt=0.08,
            tax_rate=0.24,
        )


def test_build_wacc_build_up_rejects_out_of_range_debt_to_value() -> None:
    with pytest.raises(ValueError, match="Invalid debt_to_value"):
        wacc_v14.build_wacc_build_up(
            debt_to_value=-0.1,  # negative
            cost_of_debt_pretax=0.07,
            cost_of_equity=0.12,
            tax_rate=0.24,
        )


def test_build_wacc_build_up_real_wacc_and_fee_inclusive_kd() -> None:
    """Build-up WACC: derive every component from the documented formulae."""
    dv = 0.6
    kd_pre = 0.07
    fee = 0.005
    ke = 0.12
    tax = 0.25
    infl = 0.02
    bps = 150

    comp = wacc_v14.build_wacc_build_up(
        debt_to_value=dv,
        cost_of_debt_pretax=kd_pre,
        cost_of_equity=ke,
        tax_rate=tax,
        debt_fee_rate=fee,
        inflation_rate=infl,
        prudential_spread_bps=bps,
    )

    ev = 1.0 - dv
    kd_pre_total = kd_pre + fee
    kd_at = kd_pre_total * (1.0 - tax)
    expected_nominal = ev * ke + dv * kd_at

    assert comp.mode == "build_up"
    assert comp.cost_of_debt_pretax == pytest.approx(kd_pre_total)
    assert comp.cost_of_debt_aftertax == pytest.approx(kd_at)
    assert comp.wacc_nominal == pytest.approx(expected_nominal)
    # Fisher real WACC (line 395 path).
    expected_real = ((1.0 + expected_nominal) / (1.0 + infl)) - 1.0
    assert comp.wacc_real == pytest.approx(expected_real)
    assert comp.wacc_real < comp.wacc_nominal
    assert comp.wacc_prudential == pytest.approx(expected_nominal + bps / 10000.0)
    assert comp.target_debt_to_equity == pytest.approx(dv / ev)


# =============================================================================
# resolve_cost_of_equity branches
# =============================================================================


def test_resolve_cost_of_equity_direct_percent() -> None:
    # Percent form de-percentised to decimal.
    assert wacc_v14.resolve_cost_of_equity({"cost_of_equity": 12.0}) == pytest.approx(
        0.12
    )
    # target_equity_return alias.
    assert wacc_v14.resolve_cost_of_equity(
        {"target_equity_return": 0.15}
    ) == pytest.approx(0.15)


def test_resolve_cost_of_equity_direct_nonpositive_raises() -> None:
    with pytest.raises(ValueError, match="Invalid wacc.cost_of_equity"):
        wacc_v14.resolve_cost_of_equity({"cost_of_equity": 0.0})


def test_resolve_cost_of_equity_build_up_block_sums_components() -> None:
    cfg = {
        "build_up": {
            "risk_free": 4.5,
            "country_risk_premium": 3.5,
            "equity_risk_premium": 4.0,
            "size_premium": 1.5,
        }
    }
    ke = wacc_v14.resolve_cost_of_equity(cfg)
    # Each component is _pct_to_decimal'd (>1.0 => /100) then summed.
    assert ke == pytest.approx((4.5 + 3.5 + 4.0 + 1.5) / 100.0)


def test_resolve_cost_of_equity_build_up_negative_component_raises() -> None:
    # A negative premium component triggers the per-key raise (line 446).
    with pytest.raises(ValueError, match="Invalid wacc.build_up.country_risk_premium"):
        wacc_v14.resolve_cost_of_equity(
            {"build_up": {"risk_free": 4.5, "country_risk_premium": -1.0}}
        )


def test_resolve_cost_of_equity_build_up_empty_raises() -> None:
    # All-None components -> not seen / non-positive total (line 449-450).
    with pytest.raises(ValueError, match="positive risk_free/premia"):
        wacc_v14.resolve_cost_of_equity({"build_up": {"risk_free": None}})


def test_resolve_cost_of_equity_missing_block_raises() -> None:
    # Neither direct nor build_up present (line 453).
    with pytest.raises(ValueError, match="build_up WACC requires"):
        wacc_v14.resolve_cost_of_equity({})


# =============================================================================
# compute_build_up_wacc
# =============================================================================


def test_compute_build_up_wacc_uses_passed_gearing_and_tax_fallback() -> None:
    """End-to-end build-up WACC from config, with tax pulled from the tax block."""
    config: Dict[str, Any] = {
        "wacc": {"cost_of_equity": 0.12, "inflation_rate": 0.02},
        "tax": {"corporate_tax_rate_pct": 25.0},
    }
    dv = 0.625
    kd_pre = 0.0763
    fee = 0.0

    out = wacc_v14.compute_build_up_wacc(
        config,
        debt_to_value=dv,
        cost_of_debt_pretax=kd_pre,
        debt_fee_rate=fee,
    )
    assert out["mode"] == "build_up"
    # Reconstruct the expected nominal from the same documented formula.
    ev = 1.0 - dv
    kd_at = (kd_pre + fee) * (1.0 - 0.25)
    assert out["wacc_nominal"] == pytest.approx(ev * 0.12 + dv * kd_at)
    assert out["tax_rate"] == pytest.approx(0.25)
    # Gearing passed through, not from config.
    assert out["target_debt_to_value"] == pytest.approx(dv)


def test_compute_build_up_wacc_invalid_tax_raises() -> None:
    # An impossible >100 tax now fail-louds in the CANONICAL pct_to_decimal
    # (the #573 out-of-range gate) before wacc's own range check.
    config: Dict[str, Any] = {
        "wacc": {"cost_of_equity": 0.12, "tax_rate": 150.0},
    }
    with pytest.raises(ValueError, match="out of range"):
        wacc_v14.compute_build_up_wacc(
            config, debt_to_value=0.5, cost_of_debt_pretax=0.07
        )
    # wacc's OWN [0,1] range check stays reachable: a negative rate passes the
    # canonical conversion unchanged and is rejected here.
    config_neg: Dict[str, Any] = {
        "wacc": {"cost_of_equity": 0.12, "tax_rate": -0.3},
    }
    with pytest.raises(ValueError, match="Invalid tax_rate for build_up WACC"):
        wacc_v14.compute_build_up_wacc(
            config_neg, debt_to_value=0.5, cost_of_debt_pretax=0.07
        )


# =============================================================================
# compute_wacc_from_config — fixed / build_up / unknown-mode branches
# =============================================================================


def test_compute_wacc_no_block_warns_and_returns_empty() -> None:
    assert wacc_v14.compute_wacc_from_config({}) == {}
    # extract_wacc_rates surfaces all-None on an empty block.
    rates = wacc_v14.extract_wacc_rates({})
    assert rates == {
        "wacc_nominal": None,
        "wacc_real": None,
        "wacc_prudential": None,
    }


def test_compute_wacc_fixed_mode_invalid_discount_rate_raises() -> None:
    # discount_rate present, simple mode, but non-positive (line 540).
    with pytest.raises(ValueError, match="Invalid wacc.discount_rate"):
        wacc_v14.compute_wacc_from_config({"wacc": {"discount_rate": 0.0}})


def test_compute_wacc_build_up_mode_returns_empty() -> None:
    # build_up mode is resolved in-pipeline; here it returns {} (lines 573-578).
    out = wacc_v14.compute_wacc_from_config(
        {"wacc": {"mode": "build_up", "cost_of_equity": 0.12}}
    )
    assert out == {}


def test_compute_wacc_unknown_mode_raises() -> None:
    # An unrecognised mode (not simple/fixed/build_up/capm) raises (line 585).
    with pytest.raises(ValueError, match="Unknown wacc.mode"):
        wacc_v14.compute_wacc_from_config({"wacc": {"mode": "wibble"}})


# =============================================================================
# compute_wacc_from_config — CAPM required-input raises
# =============================================================================


def _capm_cfg(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "mode": "capm",
        "risk_free": 5.0,
        "market_premium": 6.0,
        "beta": 0.8,
        "gearing": 60.0,
        "cost_of_debt": 8.0,
        "tax_rate": 24.0,
    }
    base.update(overrides)
    return {"wacc": base}


def test_compute_wacc_capm_missing_risk_free_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("risk_free")
    with pytest.raises(ValueError, match="risk_free"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_missing_market_premium_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("market_premium")
    with pytest.raises(ValueError, match="market_premium"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_missing_beta_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("beta")
    with pytest.raises(ValueError, match="beta or wacc.asset_beta"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_negative_risk_free_raises() -> None:
    with pytest.raises(ValueError, match="Invalid risk_free"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(risk_free=-1.0))


def test_compute_wacc_capm_negative_market_premium_raises() -> None:
    with pytest.raises(ValueError, match="Invalid market_premium"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(market_premium=-1.0))


def test_compute_wacc_capm_negative_beta_raises() -> None:
    with pytest.raises(ValueError, match="Invalid beta"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(beta=-0.1))


# =============================================================================
# compute_wacc_from_config — CAPM capital-structure branches
# =============================================================================


def test_compute_wacc_capm_debt_to_equity_path() -> None:
    """D/E provided instead of gearing; derive D/V = DE / (1 + DE)."""
    cfg = _capm_cfg()
    cfg["wacc"].pop("gearing")
    cfg["wacc"]["target_debt_to_equity"] = 1.5
    out = wacc_v14.compute_wacc_from_config(cfg)
    expected_dv = 1.5 / (1.0 + 1.5)
    assert out["target_debt_to_value"] == pytest.approx(expected_dv)
    assert out["target_debt_to_equity"] == pytest.approx(1.5)


def test_compute_wacc_capm_negative_debt_to_equity_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("gearing")
    cfg["wacc"]["target_debt_to_equity"] = -0.5
    with pytest.raises(ValueError, match="Invalid target_debt_to_equity"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_invalid_gearing_raises() -> None:
    # An impossible >100 gearing fail-louds in the CANONICAL pct_to_decimal (#573).
    with pytest.raises(ValueError, match="out of range"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(gearing=120.0))
    # wacc's OWN check stays reachable: 100 converts to exactly 1.0 (D/V == 1),
    # which the gearing >= 1 gate rejects.
    with pytest.raises(ValueError, match=r"Invalid gearing"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(gearing=100.0))


def test_compute_wacc_capm_missing_capital_structure_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("gearing")
    with pytest.raises(ValueError, match="target_debt_to_equity or gearing"):
        wacc_v14.compute_wacc_from_config(cfg)


# =============================================================================
# compute_wacc_from_config — CAPM cost-of-debt branches
# =============================================================================


def test_compute_wacc_capm_negative_cost_of_debt_raises() -> None:
    with pytest.raises(ValueError, match="Invalid cost_of_debt"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(cost_of_debt=-1.0))


def test_compute_wacc_capm_base_rate_plus_margin_path() -> None:
    """No cost_of_debt: kd built from base_rate + margin (lines 650-666)."""
    cfg = _capm_cfg()
    cfg["wacc"].pop("cost_of_debt")
    cfg["wacc"]["base_rate"] = 5.0
    cfg["wacc"]["margin"] = 3.0
    out = wacc_v14.compute_wacc_from_config(cfg)
    # Pre-tax kd is the sum of the two decimal components.
    assert out["cost_of_debt_pretax"] == pytest.approx(0.05 + 0.03)


def test_compute_wacc_capm_missing_base_rate_and_margin_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("cost_of_debt")
    with pytest.raises(ValueError, match="cost_of_debt or"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_negative_base_rate_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("cost_of_debt")
    cfg["wacc"]["base_rate"] = -1.0
    cfg["wacc"]["margin"] = 3.0
    with pytest.raises(ValueError, match="Invalid base_rate"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_negative_margin_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("cost_of_debt")
    cfg["wacc"]["base_rate"] = 5.0
    cfg["wacc"]["margin"] = -3.0
    with pytest.raises(ValueError, match="Invalid margin"):
        wacc_v14.compute_wacc_from_config(cfg)


# =============================================================================
# compute_wacc_from_config — CAPM tax branches
# =============================================================================


def test_compute_wacc_capm_tax_fallback_to_corporate_tax_rate() -> None:
    """No wacc.tax_rate / no _pct key: falls back to tax.corporate_tax_rate."""
    cfg = _capm_cfg()
    cfg["wacc"].pop("tax_rate")
    cfg["tax"] = {"corporate_tax_rate": 0.24}
    out = wacc_v14.compute_wacc_from_config(cfg)
    assert out["tax_rate"] == pytest.approx(0.24)


def test_compute_wacc_capm_missing_tax_raises() -> None:
    cfg = _capm_cfg()
    cfg["wacc"].pop("tax_rate")
    with pytest.raises(ValueError, match="tax_rate or tax.corporate_tax_rate"):
        wacc_v14.compute_wacc_from_config(cfg)


def test_compute_wacc_capm_invalid_tax_raises() -> None:
    # An impossible >100 tax fail-louds in the CANONICAL pct_to_decimal (#573).
    with pytest.raises(ValueError, match="out of range"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(tax_rate=150.0))
    # wacc's OWN [0,1] range check stays reachable via a negative rate.
    with pytest.raises(ValueError, match="Invalid tax_rate"):
        wacc_v14.compute_wacc_from_config(_capm_cfg(tax_rate=-0.3))


# =============================================================================
# compute_wacc_from_config — CAPM full happy path (derive from formula)
# =============================================================================


def test_compute_wacc_capm_full_surface_matches_first_principles() -> None:
    """A full CAPM config must reproduce the documented WACC build."""
    rf, mrp, beta, tax = 0.05, 0.06, 0.8, 0.24
    dv = 0.6
    kd = 0.08
    infl = 0.02
    cfg = _capm_cfg(
        risk_free=rf,
        market_premium=mrp,
        beta=beta,
        gearing=dv,
        cost_of_debt=kd,
        tax_rate=tax,
        inflation_rate=infl,
        prudential_spread_bps=150,
    )
    out = wacc_v14.compute_wacc_from_config(cfg)

    # Cross-check against the pure builder using identical decimals.
    expected = asdict(
        wacc_v14.build_wacc(
            risk_free_rate=rf,
            asset_beta=beta,
            market_risk_premium=mrp,
            debt_to_value=dv,
            cost_of_debt=kd,
            tax_rate=tax,
            inflation_rate=infl,
            prudential_spread_bps=150,
        )
    )
    assert out["mode"] == "capm"
    assert out["wacc_nominal"] == pytest.approx(expected["wacc_nominal"])
    assert out["wacc_real"] == pytest.approx(expected["wacc_real"])
    assert out["wacc_prudential"] == pytest.approx(expected["wacc_prudential"])
    # Real < nominal; prudential > nominal — sign/ordering invariants.
    assert out["wacc_real"] < out["wacc_nominal"] < out["wacc_prudential"]
    # extract_wacc_rates surfaces the same three headline numbers.
    headline = wacc_v14.extract_wacc_rates(cfg)
    assert headline["wacc_nominal"] == pytest.approx(out["wacc_nominal"])
    assert headline["wacc_real"] == pytest.approx(out["wacc_real"])
    assert headline["wacc_prudential"] == pytest.approx(out["wacc_prudential"])
