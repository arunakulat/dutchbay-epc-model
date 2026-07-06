"""Grid-FREE scaffold tests for analytics.grid (D1, #872).

These tests run in the DEFAULT (grid-free) suite — they import NO grid library. They
prove:
  * the grid modules import cleanly with pandapower/andes/opendssdirect ABSENT (CASPER:
    optional deps are never imported at module-import time);
  * the call-time ``_require_*`` guards fail loud with an actionable message;
  * the closed-form SCR fallback computes + bands + carries the bankability/EMT caveat;
  * the frozen ``GridStrengthResult`` contract centralizes the IEC-60909-min rule and
    the provenance→caveat mapping;
  * the strict ``grid`` config block validates (present-only), default-off.

The pandapower IEC 60909 path and the ANDES LVRT case are exercised separately in
``test_grid_study_deps.py`` behind ``pytest.importorskip`` (the opt-in [grid] lane).
"""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError

import pytest

from analytics.config_schema import get_required_fields
from analytics.contracts_v14 import (
    GRID_EMT_CONFIRMATION_SCR,
    GRID_SCR_STRONG_ABOVE,
    GRID_SCR_WEAK_BELOW,
    GridStrengthResult,
    grid_gfl_gfm_recommendation,
    grid_scr_band,
)
from analytics.grid import ride_through_poc, short_circuit
from analytics.grid.grid_interface_schema import GRID_INTERFACE_MODULE
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

# --------------------------------------------------------------------------- #
# CASPER — optional deps are NOT imported at import time; guards fail loud.     #
# --------------------------------------------------------------------------- #


def test_grid_modules_import_without_optional_deps() -> None:
    """Importing the grid modules must not require pandapower/andes (grid-free env)."""
    assert hasattr(short_circuit, "screen_grid_strength")
    assert hasattr(ride_through_poc, "run_lvrt_case")


def test_require_pandapower_fails_loud_when_absent() -> None:
    try:
        import pandapower  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"\[grid\] extra"):
            short_circuit._require_pandapower()
    else:  # pragma: no cover - only when the [grid] extra is installed
        assert short_circuit._require_pandapower() is not None


def test_require_andes_fails_loud_when_absent() -> None:
    try:
        import andes  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"\[grid\] extra"):
            ride_through_poc._require_andes()
    else:  # pragma: no cover - only when the [grid] extra is installed
        assert ride_through_poc._require_andes() is not None


# --------------------------------------------------------------------------- #
# Closed-form SCR fallback (no pandapower needed).                             #
# --------------------------------------------------------------------------- #


def test_closed_form_scr_strong_grid() -> None:
    """A stiff upstream grid + light plant => strong SCR, GFL viable, no EMT flag."""
    res = short_circuit.screen_grid_strength(
        poc_voltage_kv=33.0,
        source_fault_level_mva=250.0,
        source_rx=0.1,
        connection_r_ohm=0.5,
        connection_x_ohm=4.0,
        plant_rating_mva=11.0,
        use_pandapower=False,
    )
    assert res.method == "closed_form"
    assert res.fault_level_case == "iec60909_min"
    assert res.scr > GRID_SCR_STRONG_ABOVE
    assert res.scr_band == "strong"
    assert res.bankable is False  # in-house screen is never bankable (rule 2)
    assert res.emt_confirmation_required is False
    assert "PSS/E or PowerFactory" in res.provenance


def test_closed_form_scr_weak_grid_flags_emt() -> None:
    """A soft grid feeding a large plant => weak SCR: GFM likely + EMT confirmation."""
    res = short_circuit.screen_grid_strength(
        poc_voltage_kv=33.0,
        source_fault_level_mva=120.0,
        source_rx=0.1,
        connection_r_ohm=1.0,
        connection_x_ohm=9.0,
        plant_rating_mva=150.0,
        use_pandapower=False,
    )
    assert res.scr < GRID_SCR_WEAK_BELOW
    assert res.scr_band == "weak"
    assert res.emt_confirmation_required is True  # scr < GRID_EMT_CONFIRMATION_SCR
    assert "grid-forming" in res.gfl_gfm_recommendation.lower()


def test_screen_rejects_nonpositive_plant_rating() -> None:
    with pytest.raises(ValueError, match="plant_rating_mva"):
        short_circuit.screen_grid_strength(
            poc_voltage_kv=33.0,
            source_fault_level_mva=250.0,
            source_rx=0.1,
            connection_r_ohm=0.5,
            connection_x_ohm=4.0,
            plant_rating_mva=0.0,
            use_pandapower=False,
        )


# --------------------------------------------------------------------------- #
# Contract centralizes the banding + IEC-60909-min + caveat rules.            #
# --------------------------------------------------------------------------- #


def test_scr_banding_thresholds() -> None:
    assert grid_scr_band(1.0) == "weak"
    assert grid_scr_band(GRID_SCR_WEAK_BELOW) == "marginal"  # boundary: not < weak
    assert grid_scr_band(4.0) == "marginal"
    assert grid_scr_band(GRID_SCR_STRONG_ABOVE) == "marginal"  # boundary: not > strong
    assert grid_scr_band(9.0) == "strong"


def test_gfl_gfm_recommendation_maps_each_band() -> None:
    assert "GFM" in grid_gfl_gfm_recommendation("weak")
    assert "marginal" in grid_gfl_gfm_recommendation("marginal").lower()
    assert "viable" in grid_gfl_gfm_recommendation("strong").lower()


def test_from_screen_applies_min_case_and_caveats() -> None:
    res = GridStrengthResult.from_screen(
        scr_min=2.5,
        fault_level_poc_min_mva=275.0,
        plant_rating_mva=110.0,
        fault_level_poc_max_mva=320.0,
        method="pandapower_iec60909",
        provenance="test",
    )
    assert res.scr == 2.5
    assert res.fault_level_case == "iec60909_min"
    assert res.fault_level_poc_mva == 275.0
    assert res.fault_level_poc_max_mva == 320.0
    assert res.scr_band == "marginal"
    assert res.bankable is False
    # 2.5 < GRID_EMT_CONFIRMATION_SCR (3.0) => EMT confirmation mandated.
    assert res.emt_confirmation_required is (2.5 < GRID_EMT_CONFIRMATION_SCR)


def test_grid_strength_result_is_frozen_and_dumps() -> None:
    res = GridStrengthResult.from_screen(
        scr_min=6.0, fault_level_poc_min_mva=100.0, plant_rating_mva=16.5
    )
    with pytest.raises(FrozenInstanceError):
        res.scr = 1.0  # type: ignore[misc]  # frozen dataclass
    dumped = res.model_dump()
    assert dumped["scr_band"] == "strong"
    assert dumped["bankable"] is False


def test_lvrt_enter_from_d0_fixture() -> None:
    """The LVRT scaffold seeds its entry threshold from the D0 grid-code fixture."""
    assert ride_through_poc.lvrt_enter_from_fixture() == 0.89


# --------------------------------------------------------------------------- #
# Strict `grid` config block — CESSPIT, default-off, validate-when-present.    #
# --------------------------------------------------------------------------- #

_VALID_GRID_CFG = {
    "fx": {"start_lkr_per_usd": 333.79, "annual_depr": 0.059},
    "grid": {
        "study_enabled": False,
        # D1 flat core (screen inputs)
        "poc_voltage_kv": 33.0,
        "source_fault_level_mva": 250.0,
        "source_rx": 0.1,
        "connection_r_ohm": 0.5,
        "connection_x_ohm": 4.0,
        "plant_rating_mva": 11.0,
        # D2 structured per-site block (#873). A utility_provided basis needs no opt-in.
        "poc": {
            "bus_name": "Puttalam 220kV",
            "nominal_kv": 33.0,
            "plant_rated_mva": 11.0,
        },
        "thevenin": {
            "short_circuit_mva_min": 250.0,
            "short_circuit_mva_max": 320.0,
            "x_r": 10.0,
            "assumption_basis": "utility_provided",
        },
    },
}


def test_grid_specs_registered() -> None:
    names = {spec.name for spec in get_required_fields(GRID_INTERFACE_MODULE)}
    assert names == {
        # D1 flat core
        "study_enabled",
        "poc_voltage_kv",
        "source_fault_level_mva",
        "source_rx",
        "connection_r_ohm",
        "connection_x_ohm",
        "plant_rating_mva",
        # D2 structured per-site block (#873)
        "poc.bus_name",
        "poc.nominal_kv",
        "poc.plant_rated_mva",
        "thevenin.short_circuit_mva_min",
        "thevenin.short_circuit_mva_max",
        "thevenin.x_r",
        "thevenin.assumption_basis",
    }


def test_valid_grid_block_passes() -> None:
    # Only the FX + grid surfaces are exercised (no finance modules requested), so a
    # well-formed grid block validates without a full cashflow config.
    validate_config_for_v14(_VALID_GRID_CFG, "grid.yaml", [])  # must not raise


def test_grid_block_auto_enforced_when_present() -> None:
    """A malformed grid block is caught even when the caller requests NO module.

    The top-level `grid` block is auto-enforced whenever present, so an empty module
    list still validates it — proving the guard is not dormant.
    """
    broken = copy.deepcopy(_VALID_GRID_CFG)
    del broken["grid"]["study_enabled"]
    with pytest.raises(ConfigValidationError, match="study_enabled"):
        validate_config_for_v14(broken, "grid.yaml", [])


def test_grid_study_enabled_must_be_bool() -> None:
    broken = copy.deepcopy(_VALID_GRID_CFG)
    broken["grid"]["study_enabled"] = "true"  # truthy string is NOT a bool (strict)
    with pytest.raises(ConfigValidationError, match="study_enabled"):
        validate_config_for_v14(broken, "grid.yaml", ["grid"])


def test_grid_negative_fault_level_fails() -> None:
    broken = copy.deepcopy(_VALID_GRID_CFG)
    broken["grid"]["source_fault_level_mva"] = -5.0
    with pytest.raises(ConfigValidationError, match="source_fault_level_mva"):
        validate_config_for_v14(broken, "grid.yaml", ["grid"])


def test_no_grid_block_is_untouched() -> None:
    """A scenario without a grid block never triggers grid validation (byte-identical)."""
    cfg = {"fx": {"start_lkr_per_usd": 333.79, "annual_depr": 0.059}}
    # No grid block + no modules requested => only FX is validated; grid stays dormant.
    validate_config_for_v14(cfg, "nogrid.yaml", [])  # must not raise
