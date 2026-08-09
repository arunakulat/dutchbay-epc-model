"""Tests for the wizard input model (app.models.inputs.WindFarmInputs).

Covers validation, the field→scenario-path mapping, base-variant resolution, and
an end-to-end flow (form → scenario dict → the canonical pipeline via the service
seam). Asserts structure/invariants, not hardcoded economic magic numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from app.models.inputs import WindFarmInputs
from app.services.pipeline_service import run_finance_case

REPO_ROOT = Path(__file__).resolve().parents[2]


def _valid_kwargs(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "site_name": "DutchBay",
        "capacity_mw": 150.0,
        "capacity_factor": 0.332,
        "project_life_years": 20,
        "ppa_price_lkr_per_kwh": 20.30,
        "ppa_term_years": 20,
        "capex_total_usd": 159_600_000.0,
        "opex_annual_usd": 5_000_000.0,
        "fx_start_lkr_per_usd": 333.79,
    }
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_valid_inputs_construct() -> None:
    m = WindFarmInputs(**_valid_kwargs())
    assert m.scenario_variant == "lendercase"  # default
    assert m.capacity_mw == pytest.approx(150.0)


def test_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        WindFarmInputs(**_valid_kwargs(surprise="x"))


@pytest.mark.parametrize(
    "bad",
    [
        {"capacity_mw": 0.0},
        {"capacity_factor": 1.5},
        {"capacity_factor": 0.0},
        {"project_life_years": 0},
        {"project_life_years": 99},
        {"ppa_price_lkr_per_kwh": -1.0},
        {"capex_total_usd": 0.0},
        {"debt_ratio": 1.5},
    ],
)
def test_rejects_out_of_range(bad: Dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        WindFarmInputs(**_valid_kwargs(**bad))


# --------------------------------------------------------------------------- #
# Mapping
# --------------------------------------------------------------------------- #
def test_to_overrides_maps_core_fields() -> None:
    ov = WindFarmInputs(**_valid_kwargs()).to_overrides()
    assert ov["project"]["capacity_mw"] == pytest.approx(150.0)
    assert ov["project"]["capacity_factor"] == pytest.approx(0.332)
    assert ov["project"]["life_years"] == 20
    assert ov["capex"]["usd_total"] == pytest.approx(159_600_000.0)
    assert ov["tariff"]["lkr_per_kwh"] == pytest.approx(20.30)
    assert ov["tariff"]["ppa_term_years"] == 20
    assert ov["opex"]["usd_per_year"] == pytest.approx(5_000_000.0)
    assert ov["fx"]["start_lkr_per_usd"] == pytest.approx(333.79)
    assert ov["turbine"]["total_capacity_mw"] == pytest.approx(150.0)


def test_to_overrides_omits_unset_optionals() -> None:
    ov = WindFarmInputs(**_valid_kwargs()).to_overrides()
    assert "location" not in ov["project"]
    assert "cod_year" not in ov["project"]
    assert "n_turbines" not in ov["turbine"]
    assert "Financing_Terms" not in ov  # no debt knobs set


def test_to_overrides_includes_set_optionals() -> None:
    ov = WindFarmInputs(
        **_valid_kwargs(
            location="Kalpitiya",
            cod_year=2027,
            num_turbines=15,
            hub_height_m=120.0,
            debt_ratio=0.65,
            target_dscr=1.30,
        )
    ).to_overrides()
    assert ov["project"]["location"] == "Kalpitiya"
    assert ov["project"]["cod_year"] == 2027
    assert ov["turbine"]["n_turbines"] == 15
    assert ov["turbine"]["hub_height_m"] == pytest.approx(120.0)
    assert ov["Financing_Terms"]["debt_ratio"] == pytest.approx(0.65)
    assert ov["Financing_Terms"]["target_dscr"] == pytest.approx(1.30)


# --------------------------------------------------------------------------- #
# #1023: capacity_mw / capacity_factor are OPTIONAL on the model so the async
# derive-authoritative wind path may omit them (they are derived + overwritten by
# the screening seam). The sync wizard still requires them (enforced at the route).
# --------------------------------------------------------------------------- #
def _valid_kwargs_no_capacity() -> Dict[str, Any]:
    kwargs = _valid_kwargs()
    del kwargs["capacity_mw"]
    del kwargs["capacity_factor"]
    return kwargs


def test_capacity_and_cf_optional_on_model() -> None:
    """The async path may omit capacity / capacity factor: the model validates with None."""
    m = WindFarmInputs(**_valid_kwargs_no_capacity())
    assert m.capacity_mw is None
    assert m.capacity_factor is None


def test_to_overrides_omits_capacity_keys_when_none() -> None:
    """With capacity / CF omitted, their keys are dropped so the base variant value survives
    the deep-merge and (async) the screening export overwrites it."""
    ov = WindFarmInputs(**_valid_kwargs_no_capacity(), num_turbines=15).to_overrides()
    assert "capacity_mw" not in ov["project"]
    assert "capacity_factor" not in ov["project"]
    assert "total_capacity_mw" not in ov["turbine"]
    # An unrelated turbine field still maps; project keeps name + life_years.
    assert ov["turbine"]["n_turbines"] == 15
    assert ov["project"]["name"] == "DutchBay"
    assert ov["project"]["life_years"] == 20


def test_to_overrides_byte_identical_when_both_present() -> None:
    """When BOTH capacity / CF are present the mapping is byte-identical to the pre-#1023
    output — same keys, same order (guards the finance/sync path from any drift)."""
    ov = WindFarmInputs(
        **_valid_kwargs(
            location="Kalpitiya", cod_year=2027, num_turbines=15, hub_height_m=120.0
        )
    ).to_overrides()
    expected = {
        "project": {
            "name": "DutchBay",
            "capacity_mw": 150.0,
            "capacity_factor": 0.332,
            "life_years": 20,
            "location": "Kalpitiya",
            "cod_year": 2027,
        },
        "turbine": {
            "total_capacity_mw": 150.0,
            "n_turbines": 15,
            "hub_height_m": 120.0,
        },
        "capex": {"usd_total": 159_600_000.0},
        "opex": {"usd_per_year": 5_000_000.0},
        "tariff": {"lkr_per_kwh": 20.30, "ppa_term_years": 20},
        "fx": {"start_lkr_per_usd": 333.79},
    }
    assert repr(ov) == repr(expected)  # key order + values, not just == equality


@pytest.mark.parametrize("variant", ["lendercase", "basecase", "equitycase"])
def test_base_scenario_path_exists(variant: str) -> None:
    path = WindFarmInputs(
        **_valid_kwargs(scenario_variant=variant)
    ).base_scenario_path()
    assert path.exists(), path


# --------------------------------------------------------------------------- #
# to_scenario_config + end-to-end
# --------------------------------------------------------------------------- #
def test_to_scenario_config_merges_over_base() -> None:
    cfg = WindFarmInputs(
        **_valid_kwargs(capacity_mw=160.0, site_name="WhatIf")
    ).to_scenario_config()
    # Overridden values win...
    assert cfg["project"]["capacity_mw"] == pytest.approx(160.0)
    assert cfg["project"]["name"] == "WhatIf"
    # ...and unrelated base blocks are preserved.
    assert "tax" in cfg and "wacc" in cfg


def test_form_to_pipeline_end_to_end() -> None:
    """A validated form submission runs through the canonical pipeline."""
    # Use the real 159.6 MW nameplate so capacity x CF reconciles with the lendercase
    # frozen AEP (464.3, post 2% over-prediction haircut) at the service-seam reconciliation
    # guard (the round 150.0 used elsewhere for structure checks would trip it: 150 x 0.332
    # x 8.760 = 436 vs 464.3).
    cfg = WindFarmInputs(**_valid_kwargs(capacity_mw=159.6)).to_scenario_config()
    result = run_finance_case(cfg)
    assert result["status"] == "success"
    assert {"project_irr", "equity_irr", "min_dscr"} <= set(result["kpis"])
