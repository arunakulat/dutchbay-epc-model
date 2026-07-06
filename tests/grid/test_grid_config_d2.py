"""D2 (#873) — grid config DATA MODEL + strict CESSPIT validation + opt-in gate tests.

Grid-FREE (no pandapower/andes import). Proves the EXTENDED per-site ``grid`` block and the
per-tech ``generation.technologies.<name>.grid`` interface:

  * a well-formed structured grid block validates (present-only, default-off);
  * ``study_enabled: true`` (or any present grid block) missing the structured Thevenin /
    POC fields is strict-REJECTED with a field-naming message (no silent default);
  * an ESTIMATED Thevenin (``assumption_basis: screening_estimate``) WITHOUT
    ``allow_unvalidated_grid: true`` is refused, and ALLOWED once opted in;
  * Thevenin min > max is rejected (the IEC-60909 min case governs);
  * a per-tech grid interface enforces rated_mva / converter_type / converter-interfaced
    tech / enum-only-needs-opt-in;
  * grid-absent scenarios remain byte-identical (never touch the grid path);
  * the finance-layer ``grid_types`` discriminators + ``allow_unvalidated_grid`` gate.
"""

from __future__ import annotations

import copy

import pytest

from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.grid import grid_types

# --------------------------------------------------------------------------- #
# Fixtures — a fully well-formed structured grid config (utility_provided).     #
# --------------------------------------------------------------------------- #

_FX = {"start_lkr_per_usd": 333.79, "annual_depr": 0.059}

_VALID_GRID = {
    "study_enabled": True,
    # D1 flat core (still strict-required — the values the screen reads today)
    "poc_voltage_kv": 33.0,
    "source_fault_level_mva": 250.0,
    "source_rx": 0.1,
    "connection_r_ohm": 0.5,
    "connection_x_ohm": 4.0,
    "plant_rating_mva": 159.6,
    # D2 structured per-site block
    "poc": {"bus_name": "Puttalam 220kV", "nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "thevenin": {
        "short_circuit_mva_min": 800.0,
        "short_circuit_mva_max": 1200.0,
        "x_r": 12.0,
        "assumption_basis": "utility_provided",
    },
    "scr": {"gfl_min": 3.0, "gfl_comfortable": 5.0},
    "gridcode": {
        "pf_range": [-0.95, 0.95],
        "voltage_control_mode": "voltage_droop",
        "rc_k_factor": 2.0,
    },
}


def _cfg(**grid_overrides):
    cfg = {"fx": dict(_FX), "grid": copy.deepcopy(_VALID_GRID)}
    cfg["grid"].update(grid_overrides)
    return cfg


# --------------------------------------------------------------------------- #
# 1. Well-formed structured grid block validates.                             #
# --------------------------------------------------------------------------- #


def test_full_structured_grid_block_passes() -> None:
    validate_config_for_v14(_cfg(), "grid.yaml", [])  # must not raise


# --------------------------------------------------------------------------- #
# 2. study_enabled:true + missing structured thevenin/poc => strict REJECT.    #
# --------------------------------------------------------------------------- #


def test_missing_thevenin_block_rejected() -> None:
    cfg = _cfg()
    del cfg["grid"]["thevenin"]
    with pytest.raises(ConfigValidationError, match="thevenin"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


def test_missing_poc_nominal_kv_rejected() -> None:
    cfg = _cfg()
    del cfg["grid"]["poc"]["nominal_kv"]
    with pytest.raises(ConfigValidationError, match="poc.nominal_kv"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


def test_empty_bus_name_rejected() -> None:
    cfg = _cfg()
    cfg["grid"]["poc"]["bus_name"] = "   "
    with pytest.raises(ConfigValidationError, match="poc.bus_name"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


def test_bad_assumption_basis_rejected() -> None:
    cfg = _cfg()
    cfg["grid"]["thevenin"]["assumption_basis"] = "guessed"
    with pytest.raises(ConfigValidationError, match="assumption_basis"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


def test_thevenin_min_gt_max_rejected() -> None:
    cfg = _cfg()
    cfg["grid"]["thevenin"]["short_circuit_mva_min"] = 1500.0  # > max (1200)
    with pytest.raises(ConfigValidationError, match="min case governs"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


# --------------------------------------------------------------------------- #
# 3. Estimated-Thevenin opt-in gate (allow_unvalidated_grid).                  #
# --------------------------------------------------------------------------- #


def test_screening_estimate_without_optin_refused() -> None:
    cfg = _cfg()
    cfg["grid"]["thevenin"]["assumption_basis"] = "screening_estimate"
    with pytest.raises(ConfigValidationError, match="allow_unvalidated_grid"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


def test_screening_estimate_with_optin_allowed() -> None:
    cfg = _cfg()
    cfg["grid"]["thevenin"]["assumption_basis"] = "screening_estimate"
    cfg["grid"]["allow_unvalidated_grid"] = True
    validate_config_for_v14(cfg, "grid.yaml", ["grid"])  # opted-in => allowed


def test_optin_must_be_real_bool() -> None:
    cfg = _cfg()
    cfg["grid"]["thevenin"]["assumption_basis"] = "screening_estimate"
    cfg["grid"]["allow_unvalidated_grid"] = "true"  # truthy string is NOT opt-in
    with pytest.raises(ConfigValidationError, match="allow_unvalidated_grid"):
        validate_config_for_v14(cfg, "grid.yaml", ["grid"])


# --------------------------------------------------------------------------- #
# 4. Per-tech generation.technologies.<name>.grid interface.                   #
# --------------------------------------------------------------------------- #


def _tech_cfg(grid_block):
    return {
        "fx": dict(_FX),
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": 159.6,
                    "capacity_factor": 0.332,
                    "grid": grid_block,
                }
            }
        },
    }


_VALID_TECH_GRID = {
    "rated_mva": 168.0,
    "converter_type": "gfl",
    "reactive_capability": {"pf_range": [-0.95, 0.95]},
    "dynamic_model": {
        "family": "REGC_A/REEC_A/REPC_A",
        "params_ref": "tests/fixtures/grid/envision_enpcs01_gridcode.yaml",
        "source": "Envision ENPCS01 PSS/E UDM V2",
    },
}


def test_valid_per_tech_grid_passes() -> None:
    validate_config_for_v14(_tech_cfg(copy.deepcopy(_VALID_TECH_GRID)), "t.yaml", [])


def test_per_tech_bad_converter_type_rejected() -> None:
    block = copy.deepcopy(_VALID_TECH_GRID)
    block["converter_type"] = "synchronous"
    with pytest.raises(ConfigValidationError, match="converter_type"):
        validate_config_for_v14(_tech_cfg(block), "t.yaml", [])


def test_per_tech_missing_rated_mva_rejected() -> None:
    block = copy.deepcopy(_VALID_TECH_GRID)
    del block["rated_mva"]
    with pytest.raises(ConfigValidationError, match="rated_mva"):
        validate_config_for_v14(_tech_cfg(block), "t.yaml", [])


def test_per_tech_enum_only_without_optin_refused() -> None:
    block = copy.deepcopy(_VALID_TECH_GRID)
    del block["dynamic_model"]  # enum-only interface => needs opt-in
    with pytest.raises(ConfigValidationError, match="allow_unvalidated_grid"):
        validate_config_for_v14(_tech_cfg(block), "t.yaml", [])


def test_per_tech_enum_only_with_optin_allowed() -> None:
    block = copy.deepcopy(_VALID_TECH_GRID)
    del block["dynamic_model"]
    block["allow_unvalidated_grid"] = True
    validate_config_for_v14(_tech_cfg(block), "t.yaml", [])  # opted-in => allowed


def test_grid_interface_on_unsupported_tech_rejected() -> None:
    cfg = {
        "fx": dict(_FX),
        "generation": {
            "technologies": {
                "diesel": {
                    "capacity_factor": 0.5,
                    "grid": copy.deepcopy(_VALID_TECH_GRID),
                }
            }
        },
    }
    with pytest.raises(ConfigValidationError, match="not a converter-interfaced"):
        validate_config_for_v14(cfg, "t.yaml", [])


# --------------------------------------------------------------------------- #
# 5. Grid-absent scenarios are byte-identical (never touch the grid path).      #
# --------------------------------------------------------------------------- #


def test_grid_absent_config_untouched() -> None:
    cfg = {
        "fx": dict(_FX),
        "generation": {
            "technologies": {"wind": {"capacity_mw": 159.6, "capacity_factor": 0.332}}
        },
    }
    validate_config_for_v14(cfg, "nogrid.yaml", [])  # no grid anywhere => no error


# --------------------------------------------------------------------------- #
# 6. finance.grid.grid_types discriminators + opt-in gate.                      #
# --------------------------------------------------------------------------- #


def test_grid_types_converter_classification() -> None:
    assert grid_types.is_gfl_converter("GFL")
    assert grid_types.is_gfl_converter("grid_following")
    assert grid_types.is_gfm_capable_converter("gfm")
    assert grid_types.is_gfm_capable_converter("Grid_Forming")
    assert grid_types.is_known_converter_type("gfl")
    assert not grid_types.is_known_converter_type("synchronous")


def test_grid_types_modelled_tech_and_basis() -> None:
    assert grid_types.is_modelled_grid_tech("wind")
    assert grid_types.is_modelled_grid_tech("bess")
    assert not grid_types.is_modelled_grid_tech("diesel")
    assert grid_types.is_known_assumption_basis("utility_provided")
    assert grid_types.is_estimated_assumption_basis("screening_estimate")
    assert not grid_types.is_estimated_assumption_basis("utility_provided")


def test_allow_unvalidated_grid_strict_bool() -> None:
    assert grid_types.allow_unvalidated_grid({"allow_unvalidated_grid": True}) is True
    assert (
        grid_types.allow_unvalidated_grid({"allow_unvalidated_grid": "true"}) is False
    )
    assert grid_types.allow_unvalidated_grid({"allow_unvalidated_grid": 1}) is False
    assert grid_types.allow_unvalidated_grid({}) is False
    assert grid_types.allow_unvalidated_grid(None) is False
