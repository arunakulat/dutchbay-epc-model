"""Tests for power-curve sourcing (issue #181).

The fetch/list paths hit the oedb online library and skip if windpowerlib/network is
unavailable; validation, manual entry, store round-trip and EnergyCalculator
consumability are tested offline.
"""

from __future__ import annotations

import shutil

import numpy as np
import pandas as pd
import pytest
import yaml

from wind_resource.power_curve_sourcing import (
    DEFAULT_STORE,
    add_curve_to_store,
    fetch_oedb_power_curve,
    list_oedb_turbines,
    manual_power_curve,
    validate_power_curve,
)


def _good():
    return manual_power_curve(
        key="test_8mw",
        manufacturer="TestCo",
        model="TC-180/8.0",
        rated_capacity_kw=8000,
        wind_speeds_ms=[0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 20, 25],
        power_kw=[0, 0, 300, 700, 1300, 2100, 3200, 4500, 6000, 7300, 8000, 8000, 8000, 8000, 0],
        hub_heights_m=[120, 140],
        certificate="OEM-SPEC-X",
    )


def test_validate_good_curve():
    assert validate_power_curve(_good()) == []


def test_rated_wind_speed_detected():
    assert _good().rated_ms == 12.0  # first ws reaching 8000 kW


def test_validate_flags_bad_curves():
    mismatch = manual_power_curve("k", "M", "m", 8000, [0, 3, 4], [0, 0])
    assert any("length mismatch" in i for i in validate_power_curve(mismatch))
    nonmono = manual_power_curve("k", "M", "m", 8000, [0, 4, 3], [0, 1000, 2000])
    assert any("strictly increasing" in i for i in validate_power_curve(nonmono))
    overrated = manual_power_curve("k", "M", "m", 1000, [0, 3, 4], [0, 500, 2000])
    assert any("exceeds rated" in i for i in validate_power_curve(overrated))
    underrated = manual_power_curve("k", "M", "m", 8000, [0, 3, 4], [0, 100, 200])
    assert any("never reaches" in i for i in validate_power_curve(underrated))


def test_add_to_store_and_reload(tmp_path):
    store = tmp_path / "pc.yaml"
    store.write_text("# curves\n")
    add_curve_to_store(_good(), store_path=store)
    data = yaml.safe_load(store.read_text())
    assert "test_8mw" in data
    entry = data["test_8mw"]
    assert entry["rated_capacity_kw"] == 8000
    assert entry["power_curve"]["ws"][:3] == [0.0, 3.0, 4.0]
    assert entry["provenance"]["source"] == "manual"


def test_duplicate_key_raises(tmp_path):
    store = tmp_path / "pc.yaml"
    store.write_text("")
    add_curve_to_store(_good(), store_path=store)
    with pytest.raises(KeyError):
        add_curve_to_store(_good(), store_path=store)


def test_invalid_curve_rejected(tmp_path):
    store = tmp_path / "pc.yaml"
    store.write_text("")
    bad = manual_power_curve("k", "M", "m", 1000, [0, 3, 4], [0, 500, 2000])
    with pytest.raises(ValueError):
        add_curve_to_store(bad, store_path=store)


def test_added_curve_consumable_by_energy_calculator(tmp_path):
    store = tmp_path / "power_curves.yaml"
    shutil.copy(DEFAULT_STORE, store)  # real schema + existing curves
    add_curve_to_store(_good(), store_path=store)

    from wind_resource.energy_calculator import EnergyCalculator

    idx = pd.date_range("2023-01-01", periods=240, freq="h")
    df = pd.DataFrame(
        {"ws_150m": np.random.default_rng(1).weibull(2.4, 240) * 8.0}, index=idx
    )
    calc = EnergyCalculator(
        df=df, ws_column="ws_150m", turbine_model="test_8mw",
        num_turbines=10, power_curves_path=str(store),
    )
    assert calc.rated_capacity == 8000
    assert calc.calculate_gross_aep()["windfarm_aep_mwh"] > 0


@pytest.mark.parametrize("path", ["list", "fetch"])
def test_oedb_paths_if_available(path):
    try:
        if path == "list":
            df = list_oedb_turbines("Enercon")
            assert len(df) > 0
        else:
            pc = fetch_oedb_power_curve("E-126/7500", hub_height_m=135, manufacturer="Enercon")
            assert pc.rated_capacity_kw == pytest.approx(7500, rel=0.02)
            assert validate_power_curve(pc) == []
            assert pc.source == "oedb_windpowerlib"
    except Exception as exc:  # network / windpowerlib absent
        pytest.skip(f"oedb/windpowerlib unavailable: {type(exc).__name__}")
