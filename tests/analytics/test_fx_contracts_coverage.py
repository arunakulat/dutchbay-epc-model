"""Coverage tests for analytics.fx.fx_contracts (FX Structured Block Contracts).

Exercises the FX dataclasses (FXVolumetry, FXCurveOutput, FXRiskProfile,
FXStructuredBlock, FXRegimeConfig, FXRegimeScenario) and their CESSPIT
``__post_init__`` validators, accessors, and ``to_dict`` serializers.

These contracts are deterministic and offline. The only "default" they reach
for is the config-sourced reference rate from
``analytics.fx.fx_fetch.default_fx_lkr_per_usd()`` (config/defaults.yaml),
never a Python literal. We pin that here so the USD-equivalent assertions stay
meaningful even if the FX vintage is re-baselined.
"""

from __future__ import annotations

import pytest

from analytics.fx.fx_contracts import (
    FXCurveOutput,
    FXMonteCarloConfig,
    FXRegimeConfig,
    FXRegimeScenario,
    FXRiskProfile,
    FXStructuredBlock,
    FXVolumetry,
)
from analytics.fx.fx_fetch import default_fx_lkr_per_usd

DEFAULT_RATE = default_fx_lkr_per_usd()  # config-sourced (~333.79), never the stale 300


# ---------------------------------------------------------------------------
# FXVolumetry
# ---------------------------------------------------------------------------


def test_volumetry_usd_exposure_equivalent_sums_usd_equiv_fields() -> None:
    """total_usd_exposure_equivalent is a straight sum: all fields are already
    USD-equivalent (labelled by denomination currency), so there is no spot conversion."""
    vol = FXVolumetry(
        period=3,
        total_debt_lkr=1000.0,  # USD-equivalent value of LKR-denominated debt
        total_debt_usd=500.0,
        total_debt_cny=300.0,
        interest_lkr=200.0,
    )
    # 1000 + 500 + 300 + 200 = 2000 USD-equivalent
    assert vol.total_usd_exposure_equivalent == pytest.approx(2000.0)


def test_volumetry_defaults_are_zero() -> None:
    """Optional exposure fields default to 0.0."""
    vol = FXVolumetry(period=0, total_debt_lkr=0.0, total_debt_usd=0.0)
    assert vol.total_debt_cny == 0.0
    assert vol.revenue_lkr == 0.0
    assert vol.revenue_usd == 0.0
    assert vol.interest_lkr == 0.0
    assert vol.principal_lkr == 0.0
    assert vol.total_usd_exposure_equivalent == 0.0


# ---------------------------------------------------------------------------
# FXCurveOutput – construction & __post_init__ validators
# ---------------------------------------------------------------------------


def test_curve_valid_construction_with_all_pairs() -> None:
    """A fully-specified curve constructs and carries all optional pairs."""
    curve = FXCurveOutput(
        years=[0, 1, 2],
        lkr_usd=[300.0, 302.0, 305.0],
        lkr_cny=[42.0, 43.0, 44.0],
        lkr_eur=[330.0, 332.0, 335.0],
        lkr_gbp=[380.0, 382.0, 385.0],
        source="stress",
        notes="historical_avg_volatility_15pct",
    )
    assert curve.source == "stress"
    assert curve.lkr_cny == [42.0, 43.0, 44.0]


def test_curve_length_mismatch_years_vs_usd_raises() -> None:
    """years and lkr_usd must be the same length."""
    with pytest.raises(ValueError, match="years and lkr_usd must have same length"):
        FXCurveOutput(years=[0, 1, 2], lkr_usd=[300.0, 302.0])


def test_curve_optional_pair_length_mismatch_raises() -> None:
    """An optional pair shorter than years is rejected."""
    with pytest.raises(ValueError, match="lkr_cny must have same length as years"):
        FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 302.0], lkr_cny=[42.0])


def test_curve_non_positive_rate_raises() -> None:
    """A non-positive lkr_usd rate is rejected with its index."""
    with pytest.raises(ValueError, match=r"lkr_usd\[1\]=0.0 must be > 0"):
        FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 0.0])


# ---------------------------------------------------------------------------
# FXCurveOutput.get_rate – pair lookups & raises
# ---------------------------------------------------------------------------


def test_get_rate_all_available_pairs() -> None:
    """get_rate returns the right value for every available pair."""
    curve = FXCurveOutput(
        years=[0, 1],
        lkr_usd=[300.0, 302.0],
        lkr_cny=[42.0, 43.0],
        lkr_eur=[330.0, 332.0],
        lkr_gbp=[380.0, 382.0],
    )
    assert curve.get_rate(1, "lkr_usd") == 302.0
    assert curve.get_rate(0, "lkr_cny") == 42.0
    assert curve.get_rate(1, "lkr_eur") == 332.0
    assert curve.get_rate(0, "lkr_gbp") == 380.0


def test_get_rate_default_pair_is_lkr_usd() -> None:
    """The default pair is lkr_usd."""
    curve = FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 302.0])
    assert curve.get_rate(0) == 300.0


def test_get_rate_unknown_year_raises_index_error() -> None:
    """A year outside the curve raises IndexError."""
    curve = FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 302.0])
    with pytest.raises(IndexError, match="year 9 not in curve"):
        curve.get_rate(9)


@pytest.mark.parametrize("pair", ["lkr_cny", "lkr_eur", "lkr_gbp"])
def test_get_rate_missing_optional_pair_raises(pair: str) -> None:
    """Requesting an optional pair that was never supplied raises ValueError."""
    curve = FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 302.0])
    with pytest.raises(ValueError, match=f"pair '{pair}' not available in curve"):
        curve.get_rate(0, pair)


def test_get_rate_unknown_pair_raises() -> None:
    """An entirely unknown pair name raises ValueError."""
    curve = FXCurveOutput(years=[0, 1], lkr_usd=[300.0, 302.0])
    with pytest.raises(ValueError, match="unknown currency pair 'lkr_jpy'"):
        curve.get_rate(0, "lkr_jpy")


def test_curve_to_dict_round_trips_fields() -> None:
    """to_dict emits every field verbatim."""
    curve = FXCurveOutput(
        years=[0, 1],
        lkr_usd=[300.0, 302.0],
        lkr_cny=[42.0, 43.0],
        source="base_case",
        notes="n",
    )
    d = curve.to_dict()
    assert d["years"] == [0, 1]
    assert d["lkr_usd"] == [300.0, 302.0]
    assert d["lkr_cny"] == [42.0, 43.0]
    assert d["lkr_eur"] is None
    assert d["lkr_gbp"] is None
    assert d["source"] == "base_case"
    assert d["notes"] == "n"


# ---------------------------------------------------------------------------
# FXRiskProfile – construction, validators, helpers
# ---------------------------------------------------------------------------


def _valid_risk(**overrides: object) -> FXRiskProfile:
    base: dict[str, object] = {
        "var_95_usd_million": 2.0,
        "cvar_95_usd_million": 3.0,
        "debt_lkr_pct": 40.0,
        "debt_usd_pct": 40.0,
        "debt_cny_pct": 20.0,
    }
    base.update(overrides)
    return FXRiskProfile(**base)  # type: ignore[arg-type]


def test_risk_profile_valid_construction() -> None:
    """A coherent risk profile constructs cleanly."""
    risk = _valid_risk()
    assert risk.debt_concentration_hhi == 0.5
    assert risk.revenues_lkr_pct == 100.0


def test_risk_profile_debt_sum_out_of_band_raises() -> None:
    """Debt percentages that don't sum to ~100% are rejected."""
    with pytest.raises(ValueError, match="debt percentages must sum to ~100%"):
        _valid_risk(debt_lkr_pct=10.0, debt_usd_pct=10.0, debt_cny_pct=10.0)


def test_risk_profile_var_above_cvar_raises() -> None:
    """VaR must be <= CVaR (expected shortfall dominates)."""
    with pytest.raises(ValueError, match=r"VaR \(5.0\) must be <= CVaR"):
        _valid_risk(var_95_usd_million=5.0, cvar_95_usd_million=3.0)


def test_risk_profile_hhi_out_of_range_raises() -> None:
    """HHI must lie in [0, 1]."""
    with pytest.raises(ValueError, match=r"debt_concentration_hhi must be in \[0, 1\]"):
        _valid_risk(debt_concentration_hhi=1.5)


def test_risk_profile_is_high_risk_threshold() -> None:
    """is_high_risk compares VaR against the threshold (default 5.0)."""
    assert _valid_risk(var_95_usd_million=6.0, cvar_95_usd_million=7.0).is_high_risk()
    low = _valid_risk(var_95_usd_million=4.0, cvar_95_usd_million=5.0)
    assert not low.is_high_risk()
    assert low.is_high_risk(var_threshold_usd_million=3.0)


def test_risk_profile_to_dict_rounds_and_flags() -> None:
    """to_dict rounds numerics and embeds the is_high_risk flag."""
    risk = _valid_risk(
        var_95_usd_million=2.123456,
        cvar_95_usd_million=3.987654,
        debt_concentration_hhi=0.333333,
        correlation_shock_scenario="LKR -15% with rate shock",
        worst_case_year=7,
        recovery_years_to_1x_llcr=2,
    )
    d = risk.to_dict()
    assert d["var_95_usd_million"] == 2.123
    assert d["cvar_95_usd_million"] == 3.988
    assert d["debt_concentration_hhi"] == 0.333
    assert d["correlation_shock_scenario"] == "LKR -15% with rate shock"
    assert d["worst_case_year"] == 7
    assert d["recovery_years_to_1x_llcr"] == 2
    assert d["is_high_risk"] is False


# ---------------------------------------------------------------------------
# FXStructuredBlock – construction, validators, methods
# ---------------------------------------------------------------------------


def test_structured_block_defaults() -> None:
    """An empty block carries sensible defaults and zero periods."""
    block = FXStructuredBlock()
    assert block.strategy == "blended"
    assert block.base_currency == "USD"
    assert block.revenue_currencies == ["LKR"]
    assert block.total_periods() == 0
    assert block.total_debt_usd_equivalent() == 0.0


def test_structured_block_fx_match_ratio_out_of_range_raises() -> None:
    """fx_match_ratio must lie in [0, 100]."""
    with pytest.raises(ValueError, match=r"fx_match_ratio must be in \[0, 100\]"):
        FXStructuredBlock(fx_match_ratio=150.0)


def test_structured_block_hedging_coverage_out_of_range_raises() -> None:
    """hedging_coverage_pct must lie in [0, 100]."""
    with pytest.raises(ValueError, match=r"hedging_coverage_pct must be in \[0, 100\]"):
        FXStructuredBlock(hedging_coverage_pct=-1.0)


def test_structured_block_bad_base_currency_raises() -> None:
    """An unknown base currency is rejected."""
    with pytest.raises(ValueError, match="base_currency 'JPY' not in"):
        FXStructuredBlock(base_currency="JPY")


def test_structured_block_bad_reporting_currency_raises() -> None:
    """An unknown reporting currency is rejected."""
    with pytest.raises(ValueError, match="reporting_currency 'JPY' not in"):
        FXStructuredBlock(reporting_currency="JPY")


def test_structured_block_total_debt_usd_equivalent_is_straight_sum() -> None:
    """All debt fields are USD-equivalent, so the total is a straight final-period sum —
    NO spot conversion (the spot arg is accepted for back-compat but ignored)."""
    block = FXStructuredBlock(
        volumetry=[
            FXVolumetry(period=0, total_debt_lkr=1000.0, total_debt_usd=10.0),
            FXVolumetry(
                period=1,
                total_debt_lkr=2000.0,
                total_debt_usd=50.0,
                total_debt_cny=5.0,
            ),
        ]
    )
    # final period: 50 USD + 2000 (USD-equiv LKR) + 5 CNY = 2055
    assert block.total_debt_usd_equivalent() == pytest.approx(2055.0)
    # the back-compat spot arg is ignored — same result
    assert block.total_debt_usd_equivalent(spot_rate_lkr_usd=200.0) == pytest.approx(2055.0)
    assert block.total_periods() == 2


def test_structured_block_total_debt_usd_equivalent_empty_is_zero() -> None:
    """No volumetry -> 0.0."""
    assert FXStructuredBlock().total_debt_usd_equivalent() == 0.0


def test_structured_block_to_dict_serializes_volumetry() -> None:
    """to_dict rounds volumetry rows and carries config metadata."""
    block = FXStructuredBlock(
        strategy="natural_hedge",
        debt_tranches={"LKR_Tranche": "LKR"},
        fx_match_ratio=55.555,
        hedging_coverage_pct=10.111,
        notes="hedge note",
        volumetry=[
            FXVolumetry(
                period=0,
                total_debt_lkr=1000.123,
                total_debt_usd=2.567,
                total_debt_cny=3.0,
                revenue_lkr=4.0,
                revenue_usd=5.0,
                interest_lkr=6.0,
                principal_lkr=7.0,
            )
        ],
    )
    d = block.to_dict()
    assert d["strategy"] == "natural_hedge"
    assert d["debt_tranches"] == {"LKR_Tranche": "LKR"}
    assert d["fx_match_ratio"] == 55.6
    assert d["hedging_coverage_pct"] == 10.1
    assert d["notes"] == "hedge note"
    row = d["volumetry"][0]
    assert row["total_debt_lkr"] == 1000.12
    assert row["total_debt_usd"] == 2.57
    assert row["principal_lkr"] == 7.0


# ---------------------------------------------------------------------------
# FXRegimeConfig / FXRegimeScenario / FXMonteCarloConfig
# ---------------------------------------------------------------------------


def test_regime_config_defaults() -> None:
    """FXRegimeConfig carries its documented defaults."""
    cfg = FXRegimeConfig(
        base_currency="LKR",
        target_currency="USD",
        regime_type="managed",
        years=20,
    )
    assert cfg.annual_depr == 0.0
    assert cfg.start_rate == 1.0


def test_regime_scenario_exposes_regime_type() -> None:
    """FXRegimeScenario.regime_type delegates to its wrapped config."""
    cfg = FXRegimeConfig(
        base_currency="LKR",
        target_currency="USD",
        regime_type="floating",
        years=15,
        annual_depr=0.025,
        start_rate=333.79,
    )
    scenario = FXRegimeScenario(config=cfg)
    assert scenario.scenario_name == "base"
    assert scenario.regime_type == "floating"


def test_monte_carlo_config_allows_extra_fields() -> None:
    """The Pydantic stub accepts arbitrary extra fields (extra='allow')."""
    cfg = FXMonteCarloConfig(n_sims=1000, anything="ok")  # type: ignore[call-arg]
    assert cfg.n_sims == 1000  # type: ignore[attr-defined]
    assert cfg.anything == "ok"  # type: ignore[attr-defined]
