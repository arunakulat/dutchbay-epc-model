"""Coverage-focused tests for ``finance.cashflow_v14_params``.

These exercise the parameter resolvers and validators along their multi-path
precedence branches and documented ``ValueError`` raises. No economic magic
numbers are hardcoded: every expected value is either DERIVED from the engine's
own config-sourced FX fallback (queried in the test) or computed from first
principles, and structural assertions (signs, ranges, membership, raises) carry
the rest.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from analytics.fx.fx_fetch import default_fx_lkr_per_usd
from finance.cashflow_v14_params import (
    _build_cashflow_params,
    _extract_parameters,
    _extract_project_life_years,
    _resolve_fx_start,
    _resolve_project_life_components,
    _resolve_tariff_lkr_per_kwh,
    validate_parameters,
)

# A minimal v14-compliant cashflow config used as the clean baseline that each
# negative-path test perturbs in exactly one place.
BASE_CONFIG: Dict[str, Any] = {
    "project": {
        "capacity_mw": 100.0,
        "capacity_factor": 0.40,
        "project_life_years": 20,
    },
    "tariff": {"lkr_per_kwh": 20.0},
    "opex": {"usd_per_year": 3_000_000.0},
    "tax": {"corporate_tax_rate": 0.30, "depreciation_years": 15},
}


def _cfg() -> Dict[str, Any]:
    """Return a deep copy of the compliant baseline for safe mutation."""
    return copy.deepcopy(BASE_CONFIG)


def _validate_error(cfg: Dict[str, Any]) -> str:
    """Run strict validation expecting failure; return the raised message."""
    with pytest.raises(ValueError) as excinfo:
        validate_parameters(cfg)
    return str(excinfo.value)


# ---------------------------------------------------------------------------
# _resolve_project_life_components
# ---------------------------------------------------------------------------


def test_project_life_components_sums_construction_and_operating() -> None:
    """construction_years + operating_years is summed when in the 5..60 band."""
    life = _resolve_project_life_components(
        {"project": {"construction_years": 2, "operating_years": 23}},
        log=True,
    )
    assert life == 25


def test_project_life_components_none_when_no_operating() -> None:
    """Without a positive operating life there is no component-derived life."""
    assert (
        _resolve_project_life_components(
            {"project": {"construction_years": 2}}, log=False
        )
        is None
    )


def test_project_life_components_out_of_band_returns_none() -> None:
    """A summed life outside the plausible 5..60 band is rejected (line 60)."""
    assert (
        _resolve_project_life_components(
            {"project": {"construction_years": 5, "operating_years": 80}},
            log=False,
        )
        is None
    )


# ---------------------------------------------------------------------------
# _resolve_fx_start
# ---------------------------------------------------------------------------


def test_fx_start_prefers_explicit_positive_rate() -> None:
    """An explicit positive ``fx.start_lkr_per_usd`` is returned verbatim (line 84)."""
    explicit = 305.5
    assert _resolve_fx_start({"fx": {"start_lkr_per_usd": explicit}}) == explicit


def test_fx_start_falls_back_to_config_default() -> None:
    """With no fx block the config-sourced reference rate is used, not a literal."""
    assert _resolve_fx_start({}) == default_fx_lkr_per_usd()


def test_fx_start_ignores_non_positive_rate() -> None:
    """A non-positive explicit rate is discarded in favour of the config default."""
    assert _resolve_fx_start({"fx": {"start_lkr_per_usd": 0.0}}) == default_fx_lkr_per_usd()


# ---------------------------------------------------------------------------
# _resolve_tariff_lkr_per_kwh — precedence across LKR / USD-MWh / USD-kWh
# ---------------------------------------------------------------------------


def test_tariff_lkr_direct_passthrough() -> None:
    """A direct LKR/kWh tariff is returned unchanged."""
    assert _resolve_tariff_lkr_per_kwh({"tariff": {"lkr_per_kwh": 22.5}}) == 22.5


def test_tariff_usd_per_mwh_converted_via_fx() -> None:
    """USD/MWh converts to LKR/kWh via fx_start / 1000 (first-principles check)."""
    usd_mwh = 75.0
    fx = _resolve_fx_start({})
    got = _resolve_tariff_lkr_per_kwh({"tariff": {"usd_per_mwh": usd_mwh}})
    assert got == pytest.approx(usd_mwh * fx / 1000.0)


def test_tariff_usd_per_kwh_converted_via_fx() -> None:
    """USD/kWh converts to LKR/kWh by multiplying fx_start (line 134)."""
    usd_kwh = 0.06
    fx = _resolve_fx_start({})
    got = _resolve_tariff_lkr_per_kwh({"tariff": {"usd_per_kwh": usd_kwh}})
    assert got == pytest.approx(usd_kwh * fx)


def test_tariff_missing_returns_none() -> None:
    """No tariff in any supported unit resolves to None."""
    assert _resolve_tariff_lkr_per_kwh({"project": {}}) is None


# ---------------------------------------------------------------------------
# _extract_project_life_years — explicit / component / financing / heuristic
# ---------------------------------------------------------------------------


def test_life_from_explicit_field() -> None:
    """An explicit ``project.life_years`` wins over everything else."""
    assert _extract_project_life_years({"project": {"life_years": 27}}, log=False) == 27


def test_life_from_financing_tenor() -> None:
    """Falls back to Financing_Terms.tenor_years when no explicit/component life (165-170)."""
    # log=True also exercises the info-log branch on this path.
    assert (
        _extract_project_life_years({"Financing_Terms": {"tenor_years": 18}}, log=True)
        == 18
    )


def test_life_heuristic_walks_into_lists() -> None:
    """The heuristic recurses through list nodes to find a life-like field (179-180)."""
    cfg = {"schedule": [{"unrelated": 3}, {"operating_life_years": 25}]}
    assert _extract_project_life_years(cfg, log=False) == 25


def test_life_missing_raises() -> None:
    """No life anywhere raises the documented ValueError."""
    with pytest.raises(ValueError, match="project life"):
        _extract_project_life_years({"project": {}}, log=False)


# ---------------------------------------------------------------------------
# _build_cashflow_params — degradation handling + required-field guard
# ---------------------------------------------------------------------------


def test_build_negative_degradation_raises() -> None:
    """A negative degradation_pct raises before params are assembled (line 237)."""
    cfg = _cfg()
    cfg["project"]["degradation_pct"] = -5.0
    with pytest.raises(ValueError, match="degradation_pct"):
        _build_cashflow_params(cfg)


def test_build_high_degradation_warns_but_builds() -> None:
    """A high degradation_pct (>5%) still builds; per-year fraction > 0.05 (line 242)."""
    cfg = _cfg()
    cfg["project"]["degradation_pct"] = 6.0
    params = _build_cashflow_params(cfg)
    # 6% -> 0.06/yr, which exceeds the 0.05 warning threshold.
    assert params.degradation == pytest.approx(0.06)
    assert params.degradation > 0.05


def test_build_missing_required_field_raises() -> None:
    """A zero capacity trips the required-field guard (lines 452, 474)."""
    cfg = _cfg()
    cfg["project"]["capacity_mw"] = 0.0
    with pytest.raises(ValueError, match="capacity_mw"):
        _build_cashflow_params(cfg)


def test_build_clean_config_passes_required_guard() -> None:
    """The compliant baseline assembles without tripping the guard."""
    params = _build_cashflow_params(_cfg())
    assert params.project_life_years == 20
    assert params.capacity_mw == 100.0
    assert 0.0 < params.capacity_factor <= 1.0


# ---------------------------------------------------------------------------
# enhanced_capital_allowance_pct — Wave-1 unit-trap remediation
#
# Regression pins for the fix that removed the buggy `raw > 1 -> raw/100` percent
# heuristic. The lever is an explicit MULTIPLIER on the depreciable base; the old
# heuristic silently mangled the 1.5 (150%) multiplier that 9 of 10 scenarios use
# into 0.015 — a 100x-too-small depreciation base.
# ---------------------------------------------------------------------------


def test_enhanced_allowance_multiplier_taken_as_is() -> None:
    """A 1.5 (150% enhanced) multiplier resolves to 1.5, NOT the old buggy 0.015."""
    cfg = _cfg()
    cfg["tax"]["enhanced_capital_allowance_pct"] = 1.5
    params = _build_cashflow_params(cfg)
    assert params.enhanced_capital_allowance_pct == pytest.approx(1.5)


def test_enhanced_allowance_zero_is_preserved_not_defaulted() -> None:
    """A legitimate 0.0 is preserved (CESSPIT), not coerced to 1.0 by an `or`."""
    cfg = _cfg()
    cfg["tax"]["enhanced_capital_allowance_pct"] = 0.0
    params = _build_cashflow_params(cfg)
    assert params.enhanced_capital_allowance_pct == 0.0


def test_enhanced_allowance_absent_defaults_to_unity() -> None:
    """When the key is absent the multiplier defaults to 1.0 (standard allowance)."""
    cfg = _cfg()
    cfg["tax"].pop("enhanced_capital_allowance_pct", None)
    params = _build_cashflow_params(cfg)
    assert params.enhanced_capital_allowance_pct == pytest.approx(1.0)


def test_enhanced_allowance_negative_raises() -> None:
    """A negative multiplier fails loud rather than silently corrupting depreciation."""
    cfg = _cfg()
    cfg["tax"]["enhanced_capital_allowance_pct"] = -0.5
    with pytest.raises(ValueError, match="enhanced_capital_allowance_pct"):
        _build_cashflow_params(cfg)


# ---------------------------------------------------------------------------
# _extract_parameters
# ---------------------------------------------------------------------------


def test_extract_parameters_returns_plain_dict() -> None:
    """_extract_parameters returns the dataclass fields as a plain dict (484-485)."""
    out = _extract_parameters(_cfg())
    assert isinstance(out, dict)
    assert out["project_life_years"] == 20
    assert out["capacity_mw"] == 100.0
    assert out["corporate_tax_rate"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# validate_parameters — each negative branch
# ---------------------------------------------------------------------------


def test_validate_clean_config() -> None:
    """The compliant baseline validates with no errors."""
    assert validate_parameters(_cfg()) == []


def test_validate_tax_rate_out_of_range() -> None:
    """An out-of-range corporate tax rate is reported (line 508)."""
    cfg = _cfg()
    cfg["tax"]["corporate_tax_rate"] = 150.0  # 150% even after pct->decimal is >1.0
    assert "corporate_tax_rate" in _validate_error(cfg)


def test_validate_capacity_factor_out_of_range() -> None:
    """A capacity factor above 1.0 (and above 100%) is reported (line 547)."""
    cfg = _cfg()
    cfg["project"]["capacity_factor"] = 200.0
    assert "capacity_factor" in _validate_error(cfg)


def test_validate_negative_degradation() -> None:
    """A negative degradation_pct is reported (line 573)."""
    cfg = _cfg()
    cfg["project"]["degradation_pct"] = -1.0
    msg = _validate_error(cfg)
    assert "degradation_pct" in msg and "must be >= 0" in msg


def test_validate_implausible_degradation() -> None:
    """A degradation_pct above 30%/yr is flagged as a likely unit error (line 577)."""
    cfg = _cfg()
    cfg["project"]["degradation_pct"] = 50.0
    assert "implausibly high" in _validate_error(cfg)


def test_validate_grid_loss_out_of_range() -> None:
    """A grid_loss decimal at/above 1.0 is reported (line 587)."""
    cfg = _cfg()
    cfg["project"]["grid_loss_pct"] = 150.0  # -> 1.5 after pct->decimal
    msg = _validate_error(cfg)
    assert "grid_loss_pct" in msg and "out of range" in msg


def test_validate_risk_haircut_out_of_range() -> None:
    """A risk haircut decimal at/above 1.0 is reported (line 601)."""
    cfg = _cfg()
    cfg["risk_adjustment"] = {"cfads_haircut_pct": 150.0}
    msg = _validate_error(cfg)
    assert "risk_haircut_pct" in msg and "out of range" in msg


def test_validate_depreciation_years_too_small() -> None:
    """A depreciation horizon below 1 year is reported (line 607)."""
    cfg = _cfg()
    cfg["tax"]["depreciation_years"] = 0
    msg = _validate_error(cfg)
    assert "depreciation_years" in msg and "must be >= 1" in msg


def test_validate_fx_block_invalid() -> None:
    """An fx block lacking both a start rate and a curve list is reported (line 616)."""
    cfg = _cfg()
    cfg["fx"] = {"unrelated_key": 1}
    assert "fx: invalid" in _validate_error(cfg)


def test_validate_fx_block_with_curve_ok() -> None:
    """An fx block carrying an explicit curve list is accepted."""
    cfg = _cfg()
    cfg["fx"] = {"curve": [300.0, 310.0, 320.0]}
    assert validate_parameters(cfg) == []


def test_validate_missing_tax_rate_reported() -> None:
    """A missing corporate tax rate is reported as a required field."""
    cfg = _cfg()
    cfg["tax"].pop("corporate_tax_rate")
    assert "corporate_tax_rate" in _validate_error(cfg)
