"""Yearly indexation of a tariff's escalable O&M component (audit residual L-9).

The oracles here do not come from ``finance.tariff_indexation``: the yearly rate is written
out in closed form from the PUCSL 2026 methodology's basis (s.3.1 item 2: CCPI and LKR/USD
variations) and the year's tariff as ``base + escalable x ((1 + g) ** t - 1)`` (TEST-01).
A scenario without the block must be byte-identical, which the pre-existing KPI pins of
every non-Blue-Whale scenario also guard.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.bess_revenue import bess_revenue_lkr_for_year, resolve_bess_specs
from finance.cashflow_v14 import build_annual_rows, build_annual_rows_efficient
from finance.tariff_indexation import (
    OmIndexation,
    resolve_non_escalable_adjustment,
    resolve_om_indexation,
    tariff_lkr_per_kwh_for_year,
)

_REPO = Path(__file__).resolve().parents[2]
_WIND = _REPO / "scenarios" / "blue_whale_wind_lot5b_2026.yaml"
_SOLAR_BESS = _REPO / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
_NIGHTPEAK = _REPO / "scenarios" / "ceb_solar_bess_nightpeak_10mw.yaml"

_BLOCK: Dict[str, Any] = {
    "escalable_om_lkr_per_kwh": 4.93,
    "basis": "ccpi_fx_weighted",
    "ccpi_weight": 0.30,
    "lkr_usd_weight": 0.70,
    "ccpi_inflation_pct": 5.0,
    "lkr_usd_depreciation_pct": "relative_ppp",
    "usd_inflation_pct": 2.5,
    "pre_operation_years": 0,
}
# 0.30 x 5% + 0.70 x (1.05 / 1.025 - 1), by hand.
_G = 0.30 * 0.05 + 0.70 * (1.05 / 1.025 - 1.0)


def _cfg(path: Path) -> Dict[str, Any]:
    return copy.deepcopy(load_scenario_config(path))


def _with_block(block: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = _cfg(_WIND)
    cfg["tariff"].pop("om_indexation", None)
    if block is not None:
        cfg["tariff"]["om_indexation"] = dict(block)
    return cfg


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
def test_no_block_or_a_none_block_resolves_to_none() -> None:
    assert resolve_om_indexation({"tariff": {"lkr_per_kwh": 25.73}}) is None
    assert resolve_om_indexation({}) is None
    assert resolve_om_indexation({"tariff": 25.73}) is None
    assert (
        resolve_om_indexation({"tariff": {"lkr_per_kwh": 1.0, "om_indexation": None}})
        is None
    )


def test_ccpi_fx_weighted_rate_matches_the_closed_form() -> None:
    ix = resolve_om_indexation({"tariff": {"om_indexation": _BLOCK}})
    assert ix is not None
    assert ix.annual_rate == pytest.approx(_G, rel=1e-15)
    assert _G == pytest.approx(0.032073170731707, rel=1e-12)
    numeric = {**_BLOCK, "lkr_usd_depreciation_pct": 3.0}
    numeric.pop("usd_inflation_pct")
    ix2 = resolve_om_indexation({"tariff": {"om_indexation": numeric}})
    assert ix2 is not None
    assert ix2.annual_rate == pytest.approx(0.30 * 0.05 + 0.70 * 0.03, rel=1e-15)


def test_fixed_rate_basis_and_pre_operation_years() -> None:
    block = {
        "escalable_om_lkr_per_kwh": 3.02,
        "basis": "fixed_rate",
        "annual_rate_pct": 3.85,
        "pre_operation_years": 2,
    }
    ix = resolve_om_indexation({"tariff": {"om_indexation": block}})
    assert ix is not None
    assert ix.index(0) == pytest.approx(1.0385**2, rel=1e-15)
    assert ix.index(4) == pytest.approx(1.0385**6, rel=1e-15)
    assert ix.uplift_lkr_per_kwh(0) == pytest.approx(3.02 * (1.0385**2 - 1.0))


def test_flat_tariff_without_indexation_is_the_base_exactly() -> None:
    for t in range(25):
        assert tariff_lkr_per_kwh_for_year(25.73, None, t) == 25.73
    ix = OmIndexation(4.93, _G, 0, "ccpi_fx_weighted")
    assert tariff_lkr_per_kwh_for_year(25.73, ix, 0) == 25.73
    assert tariff_lkr_per_kwh_for_year(25.73, ix, 9) == pytest.approx(
        25.73 + 4.93 * ((1.0 + _G) ** 9 - 1.0), rel=1e-15
    )
    with pytest.raises(ValueError, match="year_index"):
        ix.index(-1)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        ({"basis": "cpi_only"}, "basis"),
        ({"surprise": 1}, "not allowed"),
        ({"annual_rate_pct": 3.0}, "not allowed"),
        ({"ccpi_weight": 0.5}, "must equal 1"),
        ({"ccpi_weight": -0.3, "lkr_usd_weight": 1.3}, r"\[0, 1\]"),
        ({"ccpi_inflation_pct": 500.0}, "percent"),
        ({"ccpi_inflation_pct": "5"}, "number"),
        ({"ccpi_inflation_pct": True}, "number"),
        ({"escalable_om_lkr_per_kwh": -1.0}, ">= 0"),
        ({"escalable_om_lkr_per_kwh": 30.0}, "non-escalable"),
        ({"pre_operation_years": -1}, "pre_operation_years"),
        ({"pre_operation_years": 1.5}, "pre_operation_years"),
        ({"pre_operation_years": True}, "pre_operation_years"),
        ({"lkr_usd_depreciation_pct": 2.0}, "usd_inflation_pct is read only"),
    ],
)
def test_resolver_refuses_a_malformed_block(change: Dict[str, Any], match: str) -> None:
    block = {**_BLOCK, **change}
    with pytest.raises(ValueError, match=match):
        resolve_om_indexation(
            {"tariff": {"lkr_per_kwh": 25.73, "om_indexation": block}},
            base_tariff_lkr_per_kwh=25.73,
        )


def test_resolver_refuses_a_missing_input_and_a_non_mapping() -> None:
    block = {k: v for k, v in _BLOCK.items() if k != "ccpi_inflation_pct"}
    with pytest.raises(ValueError, match="ccpi_inflation_pct"):
        resolve_om_indexation({"tariff": {"om_indexation": block}})
    with pytest.raises(ValueError, match="mapping"):
        resolve_om_indexation({"tariff": {"om_indexation": [1, 2]}})


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
def test_engine_indexes_only_the_escalable_part_in_both_builders() -> None:
    cfg = _with_block(_BLOCK)
    base = float(cfg["tariff"]["lkr_per_kwh"])
    rows = build_annual_rows(cfg)
    eff = build_annual_rows_efficient(cfg)
    assert len(rows) == len(eff) == 20
    for t, (r, e) in enumerate(zip(rows, eff, strict=True)):
        want = r["net_kwh"] * (base + 4.93 * ((1.0 + _G) ** t - 1.0))
        assert r["generation_revenue_lkr"] == pytest.approx(want, rel=1e-12), t
        assert e["generation_revenue_lkr"] == r["generation_revenue_lkr"], t
        assert e["cfads_final_lkr"] == pytest.approx(r["cfads_final_lkr"], rel=1e-12)
    # Year 20 carries (1 + g) ** 19 - 1 = 82% more escalable O&M than year 1.
    assert (1.0 + _G) ** 19 - 1.0 == pytest.approx(0.8216, abs=5e-4)


def test_a_zero_escalable_part_is_byte_identical_to_no_block() -> None:
    flat = build_annual_rows(_with_block(None))
    zero = build_annual_rows(_with_block({**_BLOCK, "escalable_om_lkr_per_kwh": 0.0}))
    assert flat == zero


def test_kpis_respond_to_the_index_inputs() -> None:
    def kpis(block: Dict[str, Any] | None) -> Dict[str, Any]:
        return evaluate_with_overrides(raw_config=_with_block(block), overrides={})

    flat = kpis(None)
    indexed = kpis(_BLOCK)
    hotter = kpis({**_BLOCK, "ccpi_inflation_pct": 8.0})
    assert flat["project_irr"] < indexed["project_irr"] < hotter["project_irr"]
    assert flat["project_npv"] < indexed["project_npv"] < hotter["project_npv"]
    # Year-1 DSCR cannot move: the index is 1.0 in operating year 1.
    assert indexed["min_dscr"] >= flat["min_dscr"]


def test_tariff_override_moves_only_the_non_escalable_base() -> None:
    cfg = _with_block(_BLOCK)
    out = evaluate_with_overrides(
        raw_config=cfg, overrides={"tariff.lkr_per_kwh": 20.0}, return_full_result=True
    )
    rows = out["annual_rows"]
    assert isinstance(rows, list)
    for t in (0, 5, 19):
        want = rows[t]["net_kwh"] * (20.0 + 4.93 * ((1.0 + _G) ** t - 1.0))
        assert rows[t]["generation_revenue_lkr"] == pytest.approx(want, rel=1e-12)


# ---------------------------------------------------------------------------
# BESS energy-tariff premium
# ---------------------------------------------------------------------------
def test_bess_premium_indexes_its_escalable_part_and_stops_with_its_term() -> None:
    cfg = _cfg(_SOLAR_BESS)
    specs = resolve_bess_specs(cfg)
    assert specs is not None and len(specs) == 1
    spec = specs[0]
    assert spec["escalable_om_lkr_per_kwh"] == pytest.approx(0.30)
    ix = resolve_om_indexation(cfg)
    assert ix is not None
    # #1569: the index starts at the 2026 price date, three steps before the 2029 COD.
    pre = ix.pre_operation_years
    assert pre == 3
    for t in (0, 7, 14):
        flat = bess_revenue_lkr_for_year(specs, t)
        indexed = bess_revenue_lkr_for_year(specs, t, ix)
        tariff = spec["tariff_lkr_per_kwh"]
        assert indexed == pytest.approx(
            flat
            * (tariff + 0.30 * ((1.0 + ix.annual_rate) ** (t + pre) - 1.0))
            / tariff,
            rel=1e-12,
        ), t
    assert bess_revenue_lkr_for_year(specs, 15, ix) == 0.0
    # With the index at 1.0 in operating year 1 the premium starts flat.
    at_cod = replace(ix, pre_operation_years=0)
    assert bess_revenue_lkr_for_year(specs, 0, at_cod) == bess_revenue_lkr_for_year(
        specs, 0
    )


def test_bess_escalable_part_is_range_checked_and_needs_the_index() -> None:
    cfg = _cfg(_SOLAR_BESS)
    rev = cfg["generation"]["technologies"]["bess_1"]["revenue"]
    rev["escalable_om_lkr_per_kwh"] = rev["tariff_lkr_per_kwh"] + 1.0
    with pytest.raises(ValueError, match="escalable_om_lkr_per_kwh"):
        resolve_bess_specs(cfg)
    cfg = _cfg(_SOLAR_BESS)
    cfg["tariff"]["om_indexation"] = None
    with pytest.raises(ValueError, match="no tariff.om_indexation"):
        build_annual_rows(cfg)


def test_a_scenario_without_the_block_carries_no_bess_escalation() -> None:
    cfg = _cfg(_NIGHTPEAK)
    assert "om_indexation" not in (cfg.get("tariff") or {})
    specs = resolve_bess_specs(cfg)
    assert specs is not None
    assert all(s["escalable_om_lkr_per_kwh"] == 0.0 for s in specs)


# ---------------------------------------------------------------------------
# The Blue Whale scenarios cite the regulatory config (one fact, one home)
# ---------------------------------------------------------------------------
def test_blue_whale_escalable_parts_match_the_annex_2_components() -> None:
    import yaml

    reg = yaml.safe_load(
        (_REPO / "conf" / "blue_whale_pucsl_fit_2026.yaml").read_text()
    )["tariff_lkr_per_kwh"]["components"]
    wind = _cfg(_WIND)
    assert wind["tariff"]["om_indexation"]["escalable_om_lkr_per_kwh"] == reg["wind"][1]
    assert wind["tariff"]["lkr_per_kwh"] == pytest.approx(sum(reg["wind"]))
    sb = _cfg(_SOLAR_BESS)
    assert (
        sb["tariff"]["om_indexation"]["escalable_om_lkr_per_kwh"]
        == reg["solar_bess_other"][1]
    )
    premium = sb["generation"]["technologies"]["bess_1"]["revenue"]
    assert premium["escalable_om_lkr_per_kwh"] == pytest.approx(
        reg["solar_bess_priority"][1] - reg["solar_bess_other"][1]
    )
    # The priority rate's escalable part is the standalone one over the methodology's 0.90
    # RTE (s.5.1.2: R_charging / RTE), to Annex 2's two decimals.
    assert reg["solar_bess_priority"][1] == pytest.approx(
        reg["solar_bess_other"][1] / 0.90, abs=0.005
    )
    # The three scenarios share one index basis. The index start is each project's own
    # (#1569: cod_year - opex.price_year; tests/finance/test_price_dates_1569.py).
    hybrid = _cfg(_REPO / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml")
    keys = set(_BLOCK) - {"escalable_om_lkr_per_kwh", "pre_operation_years"}
    for cfg in (sb, hybrid):
        block = cfg["tariff"]["om_indexation"]
        assert {k: block[k] for k in keys} == {
            k: wind["tariff"]["om_indexation"][k] for k in keys
        }
    assert {k: wind["tariff"]["om_indexation"][k] for k in keys} == {
        k: _BLOCK[k] for k in keys
    }


_NON_ESC_BLOCK: Dict[str, Any] = {
    "adjusted_component_lkr_per_kwh": 20.80,
    "ccpi_weight": 0.30,
    "lkr_usd_weight": 0.70,
    "ccpi_inflation_pct": 5.0,
    "lkr_usd_depreciation_pct": "relative_ppp",
    "usd_inflation_pct": 2.5,
    "sppa_signing_offset_months": -12,
}


def test_non_escalable_adjustment_closed_form() -> None:
    """Check formula against closed form: 30% CCPI + 70% FX (relative PPP)."""
    cfg = {"tariff": {"non_escalable_adjustment": dict(_NON_ESC_BLOCK)}}
    adj = resolve_non_escalable_adjustment(cfg)
    assert adj is not None
    assert adj.adjusted_component_lkr_per_kwh == 20.80

    # Closed form: CCPI move = 5.0%, FX move = (1 + 0.05)/(1 + 0.025) - 1 = 2.439024%
    ccpi_move = 0.05
    fx_move = 1.05 / 1.025 - 1.0
    expected_mult = 0.30 * (1.0 + ccpi_move) + 0.70 * (1.0 + fx_move)
    assert adj.adjustment_multiplier == pytest.approx(expected_mult)
    assert adj.start_year_index == 0
    expected_uplift = 20.80 * (expected_mult - 1.0)
    assert adj.uplift_lkr_per_kwh(0) == pytest.approx(expected_uplift)

    # Offset 0 months (signed at COD) -> starts at operating year 2 (year_index 1)
    cfg_cod = {
        "tariff": {
            "non_escalable_adjustment": dict(
                _NON_ESC_BLOCK, sppa_signing_offset_months=0
            )
        }
    }
    adj_cod = resolve_non_escalable_adjustment(cfg_cod)
    assert adj_cod is not None
    assert adj_cod.start_year_index == 1
    assert adj_cod.uplift_lkr_per_kwh(0) == 0.0
    assert adj_cod.uplift_lkr_per_kwh(1) == pytest.approx(expected_uplift)


def test_non_escalable_adjustment_refuses_malformed_blocks() -> None:
    """Validation checks: unknown keys, weights, component bounds."""
    # Unknown key
    bad = dict(_NON_ESC_BLOCK, bogus_key=123)
    with pytest.raises(ValueError, match="unknown keys"):
        resolve_non_escalable_adjustment({"tariff": {"non_escalable_adjustment": bad}})

    # Component exceeds base tariff
    with pytest.raises(ValueError, match="exceeds tariff.lkr_per_kwh"):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": _NON_ESC_BLOCK}},
            base_tariff_lkr_per_kwh=15.0,
        )

    # Weights don't sum to 1
    bad_weights = dict(_NON_ESC_BLOCK, ccpi_weight=0.50, lkr_usd_weight=0.70)
    with pytest.raises(ValueError, match="must equal 1"):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": bad_weights}}
        )

    # Missing both start year indicators
    missing_timing = {
        k: v for k, v in _NON_ESC_BLOCK.items() if k != "sppa_signing_offset_months"
    }
    with pytest.raises(ValueError, match="requires either 'start_operating_year'"):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": missing_timing}}
        )


def test_engine_applies_non_escalable_step_in_both_builders() -> None:
    """Verify both build_annual_rows and build_annual_rows_efficient apply step."""
    cfg = _cfg(_WIND)
    cfg["tariff"]["non_escalable_adjustment"] = dict(
        _NON_ESC_BLOCK, sppa_signing_offset_months=0
    )
    rows_std = build_annual_rows(cfg)
    rows_eff = build_annual_rows_efficient(cfg)

    assert len(rows_std) == len(rows_eff) == 20
    for t, (r, e) in enumerate(zip(rows_std, rows_eff, strict=True)):
        assert e["generation_revenue_lkr"] == pytest.approx(
            r["generation_revenue_lkr"], rel=1e-12
        ), t
        assert e["cfads_final_lkr"] == pytest.approx(r["cfads_final_lkr"], rel=1e-12), t

    # Year 1 (year_index 0): no adjustment (signed at COD, offset 0 -> year 2 start)
    # Year 2 (year_index 1): generation revenue has the non-escalable step applied
    base_cfg = _cfg(_WIND)
    base_rows = build_annual_rows_efficient(base_cfg)
    assert rows_eff[0]["generation_revenue_lkr"] == pytest.approx(
        base_rows[0]["generation_revenue_lkr"], rel=1e-12
    )
    assert (
        rows_eff[1]["generation_revenue_lkr"] > base_rows[1]["generation_revenue_lkr"]
    )


def test_bess_revenue_applies_non_escalable_adjustment() -> None:
    """Check energy_tariff BESS revenue uplift with non_escalable_lkr_per_kwh."""
    cfg = _cfg(_SOLAR_BESS)
    # Add non_escalable_adjustment to tariff
    cfg["tariff"]["non_escalable_adjustment"] = dict(
        _NON_ESC_BLOCK,
        adjusted_component_lkr_per_kwh=18.00,
        sppa_signing_offset_months=-12,
    )
    # bess_1 priority premium has non_escalable_lkr_per_kwh = 29.08
    cfg["generation"]["technologies"]["bess_1"]["revenue"][
        "non_escalable_lkr_per_kwh"
    ] = 29.08

    rows = build_annual_rows_efficient(cfg)
    # Revenue is higher with non_escalable_adjustment
    cfg_base = _cfg(_SOLAR_BESS)
    rows_base = build_annual_rows_efficient(cfg_base)
    assert rows[0]["revenue_lkr"] > rows_base[0]["revenue_lkr"]


def test_non_escalable_adjustment_responsiveness() -> None:
    """Changing non-escalable adjustment inputs moves NPV monotonically."""
    cfg = _cfg(_WIND)
    cfg["tariff"]["non_escalable_adjustment"] = dict(_NON_ESC_BLOCK)

    r_base = evaluate_with_overrides(raw_config=cfg, overrides={})
    # Higher CCPI inflation -> higher multiplier -> higher NPV
    cfg_high = copy.deepcopy(cfg)
    cfg_high["tariff"]["non_escalable_adjustment"]["ccpi_inflation_pct"] = 10.0
    r_high = evaluate_with_overrides(raw_config=cfg_high, overrides={})
    assert r_high["project_npv"] > r_base["project_npv"]


@pytest.mark.parametrize(
    ("offset", "expected_start_year"),
    [
        (-24, 0),  # Signed 24 months before COD -> window elapsed before COD -> Year 1
        (-18, 0),  # Signed 18 months before COD -> window elapsed before COD -> Year 1
        (
            -12,
            0,
        ),  # Signed 12 months before COD -> window elapsed exactly at COD -> Year 1
        (-11, 1),  # Signed 11 months before COD -> elapses 1 month post-COD -> Year 2
        (-6, 1),  # Signed 6 months before COD -> elapses 6 months post-COD -> Year 2
        (-1, 1),  # Signed 1 month before COD -> elapses 11 months post-COD -> Year 2
        (0, 1),  # Signed at COD -> elapses 12 months post-COD -> Year 2
        (1, 2),  # Signed 1 month after COD -> elapses 13 months post-COD -> Year 3
        (6, 2),  # Signed 6 months after COD -> elapses 18 months post-COD -> Year 3
        (12, 2),  # Signed 12 months after COD -> elapses 24 months post-COD -> Year 3
        (13, 3),  # Signed 13 months after COD -> elapses 25 months post-COD -> Year 4
    ],
)
def test_start_year_index_derivation_edge_cases(
    offset: int, expected_start_year: int
) -> None:
    """Verify sppa_signing_offset_months arithmetic across regimes (PUCSL s.3.1 item 1)."""
    block = dict(_NON_ESC_BLOCK, sppa_signing_offset_months=offset)
    adj = resolve_non_escalable_adjustment(
        {"tariff": {"non_escalable_adjustment": block}}
    )
    assert adj is not None
    assert adj.start_year_index == expected_start_year


@pytest.mark.parametrize("invalid_offset", [-12.5, "minus_twelve", True, None])
def test_start_year_index_refuses_non_integer_offsets(invalid_offset: Any) -> None:
    """Float offsets, strings, and booleans fail loud."""
    block = dict(_NON_ESC_BLOCK, sppa_signing_offset_months=invalid_offset)
    with pytest.raises(
        ValueError, match="sppa_signing_offset_months must be an integer"
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": block}}
        )


@pytest.mark.parametrize("invalid_year", [0, -1, 1.5, True, "year_1"])
def test_start_year_index_refuses_invalid_explicit_years(invalid_year: Any) -> None:
    """Explicit start_operating_year must be an integer >= 1."""
    block = dict(_NON_ESC_BLOCK)
    block.pop("sppa_signing_offset_months", None)
    block["start_operating_year"] = invalid_year
    with pytest.raises(
        ValueError, match="start_operating_year must be an integer >= 1"
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": block}}
        )


def test_pruned_dead_keys_raise_unknown_key_error() -> None:
    """Dead keys (sppa_signing_date, cod_date, cod_year) are refused under FRAMEWORK-02."""
    for dead_key in ("sppa_signing_date", "cod_date", "cod_year"):
        block = dict(_NON_ESC_BLOCK, **{dead_key: "2026-01-01"})
        with pytest.raises(ValueError, match="unknown keys"):
            resolve_non_escalable_adjustment(
                {"tariff": {"non_escalable_adjustment": block}}
            )


def test_dynamic_error_prefix_in_non_escalable_adjustment() -> None:
    """Error messages report tariff.non_escalable_adjustment prefix instead of om_indexation."""
    # Invalid component type
    bad_comp = dict(_NON_ESC_BLOCK, adjusted_component_lkr_per_kwh="not_a_number")
    with pytest.raises(
        ValueError,
        match=r"^tariff\.non_escalable_adjustment\.adjusted_component_lkr_per_kwh must be a number",
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": bad_comp}}
        )

    # Invalid weight type
    bad_weight = dict(_NON_ESC_BLOCK, ccpi_weight=True)
    with pytest.raises(
        ValueError,
        match=r"^tariff\.non_escalable_adjustment\.ccpi_weight must be a number",
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": bad_weight}}
        )

    # Out of bounds weight
    oob_weight = dict(_NON_ESC_BLOCK, ccpi_weight=1.5, lkr_usd_weight=-0.5)
    with pytest.raises(
        ValueError,
        match=r"^tariff\.non_escalable_adjustment\.ccpi_weight=1\.5 must be in \[0, 1\]",
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": oob_weight}}
        )

    # Out of bounds rate
    oob_rate = dict(_NON_ESC_BLOCK, ccpi_inflation_pct=150.0)
    with pytest.raises(
        ValueError,
        match=r"^tariff\.non_escalable_adjustment\.ccpi_inflation_pct=150\.0 is outside",
    ):
        resolve_non_escalable_adjustment(
            {"tariff": {"non_escalable_adjustment": oob_rate}}
        )


def test_bess_revenue_multi_year_step_interaction() -> None:
    """Verify year-by-year BESS revenue step when offset=0 vs offset=-12."""
    cfg_base = _cfg(_SOLAR_BESS)
    base_rows = build_annual_rows_efficient(cfg_base)

    # Case A: Signed at COD (offset=0) -> Adjustment takes effect in Year 2 (index 1)
    cfg_offset0 = copy.deepcopy(cfg_base)
    cfg_offset0["tariff"]["non_escalable_adjustment"] = dict(
        _NON_ESC_BLOCK,
        adjusted_component_lkr_per_kwh=18.00,
        sppa_signing_offset_months=0,
    )
    cfg_offset0["generation"]["technologies"]["bess_1"]["revenue"][
        "non_escalable_lkr_per_kwh"
    ] = 29.08
    rows_offset0 = build_annual_rows_efficient(cfg_offset0)

    # Year 1 (index 0): identical to base
    assert rows_offset0[0]["revenue_lkr"] == pytest.approx(
        base_rows[0]["revenue_lkr"], rel=1e-12
    )
    # Year 2 (index 1) & Year 3 (index 2): elevated revenue
    assert rows_offset0[1]["revenue_lkr"] > base_rows[1]["revenue_lkr"]
    assert rows_offset0[2]["revenue_lkr"] > base_rows[2]["revenue_lkr"]

    # Case B: Signed 12 months before COD (offset=-12) -> Takes effect Year 1 (index 0)
    cfg_offset12 = copy.deepcopy(cfg_base)
    cfg_offset12["tariff"]["non_escalable_adjustment"] = dict(
        _NON_ESC_BLOCK,
        adjusted_component_lkr_per_kwh=18.00,
        sppa_signing_offset_months=-12,
    )
    cfg_offset12["generation"]["technologies"]["bess_1"]["revenue"][
        "non_escalable_lkr_per_kwh"
    ] = 29.08
    rows_offset12 = build_annual_rows_efficient(cfg_offset12)

    # Year 1 (index 0): already elevated
    assert rows_offset12[0]["revenue_lkr"] > base_rows[0]["revenue_lkr"]
    assert rows_offset12[1]["revenue_lkr"] > base_rows[1]["revenue_lkr"]
