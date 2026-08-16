"""Unit tests for analytics.fx.fx_builder (FX Structured Block Builder, v14R6).

Covers the three public factory functions:
  - compute_fx_structured_block(): config + debt_result + annual_rows -> FXStructuredBlock
  - compute_fx_curve():            config + annual_rows               -> FXCurveOutput
  - compute_fx_risk_profile():     fx_block + fx_curve                -> FXRiskProfile

These functions are deterministic and offline: the only "default" they reach for is
the config-sourced reference rate from analytics.fx.fx_fetch.default_fx_lkr_per_usd()
(config/defaults.yaml), never a Python literal. We pin that here so the assertions
stay meaningful even if the vintage is re-baselined.

REGRESSION PIN (bug fixed in #305): a zero-debt volumetry path once made
compute_fx_risk_profile() return a "minimal" FXRiskProfile with
debt_lkr_pct = debt_usd_pct = debt_cny_pct = 0.0, crashing
FXRiskProfile.__post_init__ (debt percentages must sum to ~100%). The zero-debt
branch now sets debt_usd_pct = 100.0; the test below pins the corrected
behaviour (there is no xfail — the defect is closed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from analytics.fx.fx_builder import (
    compute_fx_curve,
    compute_fx_risk_profile,
    compute_fx_structured_block,
)
from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)
from analytics.fx.fx_fetch import default_fx_lkr_per_usd

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

DEFAULT_RATE = default_fx_lkr_per_usd()  # config-sourced (~333.79), never the stale 300


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _annual_rows() -> List[Dict[str, Any]]:
    """Two well-formed annual rows. Per-currency DEBT is no longer read from the rows
    (it comes from debt_result['principal_by_tranche']); the builder reads revenue_lkr,
    revenue_usd and interest_expense_lkr from the rows."""
    return [
        {
            "year": 2025,
            "revenue_lkr": 500.0,
            "revenue_usd": 0.0,
            "interest_expense_lkr": 80.0,
        },
        {
            "year": 2026,
            "revenue_lkr": 550.0,
            "revenue_usd": 0.0,
            "interest_expense_lkr": 72.0,
        },
    ]


def _debt_result() -> Dict[str, Any]:
    """Real v14 debt_result shape: per-currency committed principal (USD-equivalent).
    LKR=900, USD=1800, CNY=300 -> 30/60/10 currency split."""
    return {"principal_by_tranche": {"lkr": 900.0, "usd": 1800.0, "cny": 300.0}}


def _full_fx_config() -> Dict[str, Any]:
    """An explicit FX config section exercising every builder knob."""
    return {
        "FX": {
            "strategy": "hedged",
            "base_currency": "USD",
            "reporting_currency": "USD",
            "fx_match_ratio": 50.0,
            "hedging_coverage_pct": 30.0,
            "revenue_currencies": ["LKR"],
            "notes": "lender case",
            "curve": {
                "lkr_usd": [330.0, 335.0],
                "lkr_cny": [46.0, 47.0],
                "source": "stress",
                "notes": "two-year curve",
            },
        }
    }


# ---------------------------------------------------------------------------
# compute_fx_structured_block
# ---------------------------------------------------------------------------


def test_block_full_config_happy_path() -> None:
    """A fully-specified FX config maps straight through to the block fields."""
    block = compute_fx_structured_block(
        config=_full_fx_config(),
        debt_result={"principal_by_tranche": {"usd": 1000.0, "lkr": 2000.0}},
        annual_rows=_annual_rows(),
    )
    assert isinstance(block, FXStructuredBlock)
    assert block.strategy == "hedged"
    assert block.base_currency == "USD"
    assert block.reporting_currency == "USD"
    assert block.fx_match_ratio == pytest.approx(50.0)
    assert block.hedging_coverage_pct == pytest.approx(30.0)
    assert block.revenue_currencies == ["LKR"]
    assert block.notes == "lender case"
    # tranche names map to their reporting currency (usd->USD, lkr->LKR)
    assert block.debt_tranches == {"usd": "USD", "lkr": "LKR"}
    assert block.total_periods() == 2


def test_block_volumetry_is_built_per_row() -> None:
    """One FXVolumetry per annual row; committed debt (USD-equiv) is constant across
    periods (from principal_by_tranche), revenue/interest come from the rows."""
    rows = _annual_rows()
    block = compute_fx_structured_block(
        config={}, debt_result=_debt_result(), annual_rows=rows
    )
    assert len(block.volumetry) == len(rows)
    first, last = block.volumetry[0], block.volumetry[-1]
    assert first.period == 0
    assert last.period == 1
    # committed debt is the same every period: LKR=900, USD=1800, CNY=300
    assert first.total_debt_lkr == pytest.approx(900.0)
    assert first.total_debt_usd == pytest.approx(1800.0)
    assert last.total_debt_cny == pytest.approx(300.0)
    # revenue/interest are per-period from the cashflow rows
    assert last.revenue_lkr == pytest.approx(550.0)
    assert last.interest_lkr == pytest.approx(72.0)  # from interest_expense_lkr
    assert last.principal_lkr == pytest.approx(0.0)


def test_block_defaults_when_no_fx_section() -> None:
    """Empty config -> documented defaults (blended/USD/USD, ratios 0, LKR revenue)."""
    block = compute_fx_structured_block(config={}, debt_result={}, annual_rows=[])
    assert block.strategy == "blended"
    assert block.base_currency == "USD"
    assert block.reporting_currency == "USD"
    assert block.fx_match_ratio == pytest.approx(0.0)
    assert block.hedging_coverage_pct == pytest.approx(0.0)
    assert block.revenue_currencies == ["LKR"]
    assert block.debt_tranches == {}
    assert block.volumetry == []


def test_block_lowercase_fx_key_is_honored() -> None:
    """The FX section is read case-insensitively ('FX' OR 'fx')."""
    block = compute_fx_structured_block(
        config={"fx": {"strategy": "natural_hedge", "base_currency": "LKR"}},
        debt_result={},
        annual_rows=[],
    )
    assert block.strategy == "natural_hedge"
    assert block.base_currency == "LKR"


def test_block_unknown_strategy_falls_back_to_blended() -> None:
    """An out-of-enum strategy string is coerced to the safe default 'blended'."""
    block = compute_fx_structured_block(
        config={"FX": {"strategy": "WILD_GUESS"}},
        debt_result={},
        annual_rows=[],
    )
    assert block.strategy == "blended"


def test_block_revenue_currencies_string_is_wrapped() -> None:
    """A scalar string revenue_currencies is normalised into a single-element list."""
    block = compute_fx_structured_block(
        config={"FX": {"revenue_currencies": "USD"}},
        debt_result={},
        annual_rows=[],
    )
    assert block.revenue_currencies == ["USD"]


def test_block_unknown_tranche_name_defaults_to_usd() -> None:
    """A tranche whose name is not in the LKR/USD/DFI/CNY map defaults to USD."""
    block = compute_fx_structured_block(
        config={},
        debt_result={"principal_by_tranche": {"mezzanine": 100.0}},
        annual_rows=[],
    )
    assert block.debt_tranches == {"mezzanine": "USD"}


def test_block_non_mapping_fx_section_is_ignored() -> None:
    """A non-Mapping FX value degrades gracefully to defaults rather than crashing."""
    block = compute_fx_structured_block(
        config={"FX": ["not", "a", "mapping"]},
        debt_result={},
        annual_rows=[],
    )
    assert block.strategy == "blended"
    assert block.base_currency == "USD"


def test_block_malformed_row_raises_valueerror() -> None:
    """A non-numeric revenue value in a row fails fast with a ValueError naming the row."""
    bad_rows = [{"revenue_lkr": "not_a_number"}]
    with pytest.raises(ValueError, match="Row 0 malformed"):
        compute_fx_structured_block(
            config={}, debt_result=_debt_result(), annual_rows=bad_rows
        )


def test_block_from_lender_scenario_yaml() -> None:
    """The committed lender scenario loads offline and yields a coherent block.

    The scenario's fx: section uses a different shape than the builder's knobs
    (rates/start_lkr_per_usd, not strategy/curve), so the builder applies its
    documented defaults — which is itself the behaviour under test.
    """
    scenario = yaml.safe_load(LENDER_SCENARIO.read_text(encoding="utf-8"))
    assert "fx" in scenario  # sanity: the section we expect to drive defaults
    block = compute_fx_structured_block(
        config=scenario,
        debt_result={"principal_by_tranche": {"dfi": 11.0}},
        annual_rows=_annual_rows(),
    )
    assert isinstance(block, FXStructuredBlock)
    # base_currency 'USD' from the scenario fx: block is a valid currency.
    assert block.base_currency == "USD"
    # strategy not specified in this scenario shape -> safe default.
    assert block.strategy == "blended"
    # DFI is a USD-denominated development-finance tranche.
    assert block.debt_tranches == {"dfi": "USD"}
    assert block.total_periods() == 2


# ---------------------------------------------------------------------------
# compute_fx_curve
# ---------------------------------------------------------------------------


def test_curve_explicit_lkr_usd_and_optional_pairs() -> None:
    """Explicit curve arrays flow through, including the optional CNY pair."""
    curve = compute_fx_curve(config=_full_fx_config(), annual_rows=_annual_rows())
    assert isinstance(curve, FXCurveOutput)
    assert curve.years == [2025, 2026]
    assert curve.lkr_usd == [330.0, 335.0]
    assert curve.lkr_cny == [46.0, 47.0]
    assert curve.lkr_eur is None
    assert curve.lkr_gbp is None
    assert curve.source == "stress"
    # round-trip through the contract's accessor
    assert curve.get_rate(2026, "lkr_usd") == pytest.approx(335.0)
    assert curve.get_rate(2025, "lkr_cny") == pytest.approx(46.0)


def test_curve_uses_authoritative_annual_row_fx_rates() -> None:
    """Resolved cashflow rows outrank a synthetic parametric reporting rebuild."""
    rows = _annual_rows()
    rows[0]["fx_rate"] = 374.2684496059
    rows[1]["fx_rate"] = 396.31385823068697
    curve = compute_fx_curve(
        config={"fx": {"start_lkr_per_usd": 333.79, "annual_depr": 0.0589}},
        annual_rows=rows,
    )
    assert curve.lkr_usd == [374.2684496059, 396.31385823068697]


def test_explicit_reporting_curve_precedes_annual_row_rates() -> None:
    rows = _annual_rows()
    rows[0]["fx_rate"] = 374.0
    rows[1]["fx_rate"] = 396.0
    curve = compute_fx_curve(config=_full_fx_config(), annual_rows=rows)
    assert curve.lkr_usd == [330.0, 335.0]


@pytest.mark.parametrize("bad", [None, 0.0, -1.0, float("nan"), "bad"])
def test_invalid_annual_row_fx_falls_back_to_parametric_curve(bad: Any) -> None:
    rows = _annual_rows()
    rows[0]["fx_rate"] = bad
    rows[1]["fx_rate"] = 999.0
    curve = compute_fx_curve(
        config={"fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.10}},
        annual_rows=rows,
    )
    assert curve.lkr_usd == pytest.approx([300.0, 330.0])


def test_curve_default_flat_uses_config_reference_rate() -> None:
    """With no lkr_usd provided, a flat curve at the config reference rate is built."""
    curve = compute_fx_curve(config={}, annual_rows=_annual_rows())
    assert curve.lkr_usd == [DEFAULT_RATE, DEFAULT_RATE]
    assert all(r > 320.0 for r in curve.lkr_usd)  # never the stale 300
    assert curve.source == "base_case"
    assert curve.lkr_cny is None


def test_curve_explicit_spot_builds_flat_curve_at_that_rate() -> None:
    """A provided fx.curve.spot_lkr_usd builds a flat curve at exactly that rate."""
    cfg = {"fx": {"curve": {"spot_lkr_usd": 350.0}}}
    curve = compute_fx_curve(config=cfg, annual_rows=_annual_rows())
    assert curve.lkr_usd == [350.0, 350.0]


def test_curve_absent_spot_falls_back_to_reference_rate() -> None:
    """An absent spot_lkr_usd (key missing) still defaults to the config reference rate."""
    cfg = {"fx": {"curve": {"source": "no_spot_here"}}}
    curve = compute_fx_curve(config=cfg, annual_rows=_annual_rows())
    assert curve.lkr_usd == [DEFAULT_RATE, DEFAULT_RATE]


def test_curve_zero_or_negative_spot_fails_loud() -> None:
    """A supplied 0.0/negative spot is a config error and must RAISE, not be silently
    replaced by the default (the old `... or default()` falsy-or trap)."""
    for bad in (0.0, -5.0):
        cfg = {"fx": {"curve": {"spot_lkr_usd": bad}}}
        with pytest.raises(ValueError, match="spot rate must be > 0"):
            compute_fx_curve(config=cfg, annual_rows=_annual_rows())


def test_curve_default_flat_honors_explicit_spot() -> None:
    """spot_lkr_usd overrides the reference rate for the flat default curve."""
    curve = compute_fx_curve(
        config={"FX": {"curve": {"spot_lkr_usd": 350.0}}},
        annual_rows=_annual_rows(),
    )
    assert curve.lkr_usd == [350.0, 350.0]


def test_curve_years_fall_back_to_index_when_missing() -> None:
    """Rows without a 'year' key get sequential indices as the year labels."""
    curve = compute_fx_curve(config={}, annual_rows=[{}, {}, {}])
    assert curve.years == [0, 1, 2]
    assert len(curve.lkr_usd) == 3


def test_curve_empty_rows_yield_empty_curve() -> None:
    """No annual rows -> empty years and an empty (but valid) lkr_usd list."""
    curve = compute_fx_curve(config={}, annual_rows=[])
    assert curve.years == []
    assert curve.lkr_usd == []


def test_curve_length_mismatch_raises() -> None:
    """An explicit lkr_usd whose length != number of years fails fast."""
    with pytest.raises(ValueError, match="lkr_usd length"):
        compute_fx_curve(
            config={"FX": {"curve": {"lkr_usd": [330.0]}}},
            annual_rows=_annual_rows(),  # two years
        )


def test_curve_optional_pair_length_mismatch_raises() -> None:
    """An optional pair (lkr_cny) whose length != years fails fast too."""
    with pytest.raises(ValueError, match="lkr_cny length"):
        compute_fx_curve(
            config={
                "FX": {
                    "curve": {
                        "lkr_usd": [330.0, 335.0],
                        "lkr_cny": [46.0],  # wrong length
                    }
                }
            },
            annual_rows=_annual_rows(),
        )


def test_curve_eur_gbp_pairs_carried_through() -> None:
    """EUR and GBP optional curves are passed through when lengths match."""
    curve = compute_fx_curve(
        config={
            "FX": {
                "curve": {
                    "lkr_usd": [330.0, 335.0],
                    "lkr_eur": [360.0, 365.0],
                    "lkr_gbp": [420.0, 425.0],
                }
            }
        },
        annual_rows=_annual_rows(),
    )
    assert curve.lkr_eur == [360.0, 365.0]
    assert curve.lkr_gbp == [420.0, 425.0]
    assert curve.get_rate(2026, "lkr_gbp") == pytest.approx(425.0)


# ---------------------------------------------------------------------------
# compute_fx_risk_profile
# ---------------------------------------------------------------------------


def test_risk_profile_happy_path_percentages_and_var() -> None:
    """Debt mix drives currency percentages, HHI, and a positive simplified VaR."""
    block = compute_fx_structured_block(
        config=_full_fx_config(),
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )
    curve = compute_fx_curve(config=_full_fx_config(), annual_rows=_annual_rows())
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve)

    assert isinstance(profile, FXRiskProfile)
    # committed debt: LKR=900, USD=1800, CNY=300 -> total 3000 (USD-equiv)
    assert profile.debt_lkr_pct == pytest.approx(30.0)
    assert profile.debt_usd_pct == pytest.approx(60.0)
    assert profile.debt_cny_pct == pytest.approx(10.0)
    # percentages must sum to ~100 (the contract validator)
    total_pct = profile.debt_lkr_pct + profile.debt_usd_pct + profile.debt_cny_pct
    assert total_pct == pytest.approx(100.0)
    # HHI = 0.3^2 + 0.6^2 + 0.1^2 = 0.46
    assert profile.debt_concentration_hhi == pytest.approx(0.46)
    # VaR_95 = HARD-CURRENCY (USD + CNY) debt (the legs MISMATCHED vs LKR revenue), already
    # USD-equiv, * 5%, in USD millions. The LKR leg is a natural hedge and is EXCLUDED.
    # No spot division (the figure is already USD). CVaR = 1.5 * VaR.
    # _full_fx_config declares hedging_coverage_pct=30, so VaR is on the 70% residual.
    expected_var = ((1800.0 + 300.0) * 0.05 * 0.70) / 1e6  # USD 1800 + CNY 300
    assert profile.var_95_usd_million == pytest.approx(expected_var)
    assert profile.cvar_95_usd_million == pytest.approx(expected_var * 1.5)
    assert profile.cvar_95_usd_million >= profile.var_95_usd_million
    assert profile.revenues_lkr_pct == pytest.approx(100.0)


def test_risk_profile_var_is_independent_of_curve_spot() -> None:
    """VaR is computed on USD-equivalent debt, so it does NOT depend on the curve spot
    (the prior code wrongly divided an already-USD figure by spot). Two different curves
    must yield the same VaR for the same debt."""
    block = compute_fx_structured_block(
        config=_full_fx_config(),
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )
    p_a = compute_fx_risk_profile(
        fx_block=block,
        fx_curve=FXCurveOutput(years=[2025, 2026], lkr_usd=[330.0, 300.0]),
    )
    p_b = compute_fx_risk_profile(
        fx_block=block,
        fx_curve=FXCurveOutput(years=[2025, 2026], lkr_usd=[330.0, 400.0]),
    )
    # _full_fx_config declares hedging_coverage_pct=30 -> VaR on the 70% residual of the
    # hard-currency (USD + CNY) legs (the LKR leg is a natural hedge, excluded).
    expected_var = ((1800.0 + 300.0) * 0.05 * 0.70) / 1e6
    assert p_a.var_95_usd_million == pytest.approx(expected_var)
    assert p_b.var_95_usd_million == pytest.approx(expected_var)


def test_risk_profile_no_volumetry_returns_minimal_usd_profile() -> None:
    """No volumetry -> a minimal profile attributed 100% to USD (passes validation)."""
    block = FXStructuredBlock()  # empty volumetry
    curve = compute_fx_curve(config={}, annual_rows=[])
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve)
    assert profile.var_95_usd_million == pytest.approx(0.0)
    assert profile.cvar_95_usd_million == pytest.approx(0.0)
    assert profile.debt_usd_pct == pytest.approx(100.0)
    assert profile.debt_lkr_pct == pytest.approx(0.0)
    assert profile.debt_cny_pct == pytest.approx(0.0)


def test_risk_profile_revenue_not_lkr_sets_zero_pct() -> None:
    """If revenues are not in LKR, revenues_lkr_pct is 0.0."""
    block = compute_fx_structured_block(
        config={"FX": {"revenue_currencies": ["USD"]}},
        debt_result=_debt_result(),
        annual_rows=_annual_rows(),
    )
    curve = compute_fx_curve(config=_full_fx_config(), annual_rows=_annual_rows())
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve)
    assert profile.revenues_lkr_pct == pytest.approx(0.0)


def test_risk_profile_all_usd_debt_concentration() -> None:
    """Single-currency (all USD) debt -> HHI of 1.0 and 100% USD attribution."""
    rows = [{"year": 2025, "revenue_lkr": 100.0}]
    block = compute_fx_structured_block(
        config=_full_fx_config(),
        debt_result={"principal_by_tranche": {"usd": 5000.0}},
        annual_rows=rows,
    )
    curve = compute_fx_curve(
        config={"FX": {"curve": {"lkr_usd": [330.0]}}}, annual_rows=rows
    )
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve)
    assert profile.debt_usd_pct == pytest.approx(100.0)
    assert profile.debt_concentration_hhi == pytest.approx(1.0)
    # All-USD debt is 100% hard-currency exposure (mismatched vs LKR revenue) -> positive VaR
    # on the 70% residual (hedging_coverage_pct=30). (Previously this leg was wrongly excluded.)
    assert profile.var_95_usd_million == pytest.approx((5000.0 * 0.05 * 0.70) / 1e6)


def test_risk_profile_zero_debt_should_not_crash() -> None:
    """A zero-debt volumetry yields a valid profile, not a crashed validator.

    Regression: the zero-debt branch returned all debt percentages = 0.0, which
    violated FXRiskProfile.__post_init__ (must sum to ~100%). It now mirrors the
    no-volumetry branch (nominal 100% USD) so the minimal profile validates.
    """
    block = FXStructuredBlock(
        volumetry=[
            FXVolumetry(
                period=0,
                total_debt_lkr=0.0,
                total_debt_usd=0.0,
                total_debt_cny=0.0,
            )
        ]
    )
    curve = compute_fx_curve(config={}, annual_rows=[{"year": 0}])
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve)
    # If the bug is ever fixed, the returned profile must validate (sum ~100%).
    total_pct = profile.debt_lkr_pct + profile.debt_usd_pct + profile.debt_cny_pct
    assert 95.0 <= total_pct <= 105.0


# ---------------------------------------------------------------------------
# Wave-2: curve resolves the scenario's own rate; revenue_currencies [] preserved
# ---------------------------------------------------------------------------


def test_curve_resolves_scenario_rates_key() -> None:
    """No scenario ships an fx.curve block — the rate is under fx.rates.lkr_per_usd. The
    curve must use it, not silently fall back to the global default (Wave-2 fix)."""
    curve = compute_fx_curve(
        config={"fx": {"rates": {"lkr_per_usd": 350.0}}}, annual_rows=_annual_rows()
    )
    assert curve.lkr_usd == [350.0, 350.0]


def test_curve_resolves_start_lkr_per_usd_then_pinned_rate() -> None:
    """fx.start_lkr_per_usd and fx.source.pinned_rate are accepted fallbacks for the spot."""
    c1 = compute_fx_curve(
        config={"fx": {"start_lkr_per_usd": 310.0}}, annual_rows=_annual_rows()
    )
    assert c1.lkr_usd == [310.0, 310.0]
    c2 = compute_fx_curve(
        config={"fx": {"source": {"pinned_rate": 305.0}}}, annual_rows=_annual_rows()
    )
    assert c2.lkr_usd == [305.0, 305.0]


def test_curve_canonical_is_byte_identical_rate_equals_default() -> None:
    """The canonical lender case pins 333.79 (== the config default), so resolving from the
    scenario rate is byte-identical to the previous default-only behaviour."""
    curve = compute_fx_curve(
        config={"fx": {"rates": {"lkr_per_usd": float(DEFAULT_RATE)}}},
        annual_rows=_annual_rows(),
    )
    assert curve.lkr_usd == [DEFAULT_RATE, DEFAULT_RATE]


def test_block_revenue_currencies_empty_list_is_preserved() -> None:
    """An explicit empty revenue_currencies list is NOT silently replaced by ['LKR']
    (the falsy-or family, same as the fx spot trap)."""
    block = compute_fx_structured_block(
        config={"FX": {"revenue_currencies": []}}, debt_result={}, annual_rows=[]
    )
    assert block.revenue_currencies == []


def test_hedging_coverage_reduces_var() -> None:
    """A declared FX hedge (hedging_coverage_pct) reduces the VaR on the residual exposure;
    0% coverage is byte-identical to the unhedged VaR (round-3 fix — the field was read onto
    the block but never reduced risk)."""
    vol = [FXVolumetry(period=0, total_debt_lkr=1000.0, total_debt_usd=1000.0)]
    curve = compute_fx_curve(config={}, annual_rows=[{"year": 0}])
    v_unhedged = compute_fx_risk_profile(
        fx_block=FXStructuredBlock(volumetry=vol, hedging_coverage_pct=0.0),
        fx_curve=curve,
    ).var_95_usd_million
    v_hedged = compute_fx_risk_profile(
        fx_block=FXStructuredBlock(volumetry=vol, hedging_coverage_pct=40.0),
        fx_curve=curve,
    ).var_95_usd_million
    assert v_hedged == pytest.approx(v_unhedged * 0.60)  # 40% hedged -> 60% residual
