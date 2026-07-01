"""Coverage top-up for ``wind_resource.power_curve_sourcing`` (issue #181).

The existing ``test_power_curve_sourcing.py`` covers the happy paths; this file
drives the remaining error/edge branches that those tests do not reach:

* the oedb "no power curve" raise (windpowerlib is faked -- no network),
* the three under-exercised ``validate_power_curve`` flags,
* the ``add_curve_to_store(overwrite=True)`` in-place-update branch,
* the ``turbine-models`` substring-match / no-match / bad-column raises
  (the package itself is monkeypatched to a tmp data dir -- no real package),
* the WAsP ``.wtg`` "no PerformanceTable" and bad-AirDensity branches,
* the tabular-import "no columns" raise and the ``certificate`` provenance path.

No network, no live CDS/ERA5, no real optional packages: ``windpowerlib`` and
``turbine_models`` are stubbed via ``sys.modules`` / monkeypatch, and all file
I/O goes through ``tmp_path``.
"""

from __future__ import annotations

import sys
import types

import pytest
import yaml

from wind_resource.power_curve_sourcing import (
    PowerCurve,
    add_curve_to_store,
    fetch_oedb_power_curve,
    fetch_turbine_models_curve,
    from_tabular_file,
    from_wasp_wtg,
    manual_power_curve,
    validate_power_curve,
)

# ── fetch_oedb_power_curve: turbine present but no power curve (line 127) ──────


def test_fetch_oedb_raises_when_no_power_curve(monkeypatch: pytest.MonkeyPatch) -> None:
    """A turbine that exists in the library but ships no curve -> ValueError."""

    class _FakeTurbine:
        def __init__(self, *, turbine_type: str, hub_height: float) -> None:
            self.turbine_type = turbine_type
            self.hub_height = hub_height
            self.power_curve = None  # the branch under test
            self.nominal_power = 0.0

    fake_module = types.ModuleType("windpowerlib")
    fake_module.WindTurbine = _FakeTurbine  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "windpowerlib", fake_module)

    with pytest.raises(ValueError, match="No power curve in the oedb library"):
        fetch_oedb_power_curve("NoCurve/9999", manufacturer="Ghost")


# ── validate_power_curve: the three remaining flag branches (190, 194, 196) ───


def test_validate_flags_too_few_points() -> None:
    pc = manual_power_curve("k", "M", "m", 1000, [3.0, 4.0], [0.0, 500.0])
    assert any("at least 3 curve points" in i for i in validate_power_curve(pc))


def test_validate_flags_negative_power() -> None:
    pc = PowerCurve(
        key="k",
        manufacturer="M",
        model="m",
        rated_capacity_kw=1000,
        wind_speeds_ms=[3.0, 4.0, 5.0],
        power_kw=[0.0, -10.0, 1000.0],
    )
    assert any("power must be non-negative" in i for i in validate_power_curve(pc))


def test_validate_flags_non_positive_rated() -> None:
    pc = PowerCurve(
        key="k",
        manufacturer="M",
        model="m",
        rated_capacity_kw=0.0,
        wind_speeds_ms=[3.0, 4.0, 5.0],
        power_kw=[0.0, 500.0, 1000.0],
    )
    issues = validate_power_curve(pc)
    assert any("rated_capacity_kw must be positive" in i for i in issues)
    # rated <= 0 takes the `if` branch, so no peak-vs-rated message is added.
    assert not any("exceeds rated" in i or "never reaches" in i for i in issues)


# ── add_curve_to_store: overwrite=True in-place update branch (241-242) ────────


def _good_curve() -> PowerCurve:
    return manual_power_curve(
        key="ovr_8mw",
        manufacturer="TestCo",
        model="TC-180/8.0",
        rated_capacity_kw=8000,
        wind_speeds_ms=[0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 20, 25],
        power_kw=[
            0,
            0,
            300,
            700,
            1300,
            2100,
            3200,
            4500,
            6000,
            7300,
            8000,
            8000,
            8000,
            8000,
            0,
        ],
        hub_heights_m=[120, 140],
    )


def test_add_curve_overwrite_updates_in_place(tmp_path) -> None:
    store = tmp_path / "pc.yaml"
    add_curve_to_store(_good_curve(), store_path=store)
    first = yaml.safe_load(store.read_text())
    assert first["ovr_8mw"]["rated_capacity_kw"] == 8000

    # Re-add with a different rated value and overwrite=True -> dict.update path.
    updated = manual_power_curve(
        key="ovr_8mw",
        manufacturer="TestCo",
        model="TC-180/8.0",
        rated_capacity_kw=7800,
        wind_speeds_ms=[0, 3, 4, 12, 25],
        power_kw=[0, 0, 300, 7800, 0],
    )
    add_curve_to_store(updated, store_path=store, overwrite=True)

    reread = yaml.safe_load(store.read_text())
    assert reread["ovr_8mw"]["rated_capacity_kw"] == 7800
    # safe_dump (not append) -> exactly one block, no duplicate key text.
    assert store.read_text().count("ovr_8mw:") == 1


# ── turbine-models: substring match / no match / missing columns ──────────────


def _stub_turbine_models(monkeypatch: pytest.MonkeyPatch, data_dir) -> None:
    """Point ``_turbine_models_data_dir`` at a tmp dir (no real package)."""
    monkeypatch.setattr(
        "wind_resource.power_curve_sourcing._turbine_models_data_dir",
        lambda: data_dir,
    )


def test_fetch_turbine_models_substring_match(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv = data_dir / "IEA_Reference_15MW_240.csv"
    csv.write_text(
        "Wind Speed [m/s],Power [kW]\n3.0,0\n10.0,7500\n12.0,15000\n25.0,0\n"
    )
    _stub_turbine_models(monkeypatch, data_dir)

    # No exact stem "15MW" -> falls through to the case-insensitive substring path.
    pc = fetch_turbine_models_curve("15mw", key="iea15", manufacturer="IEA")
    assert pc.rated_capacity_kw == 15000.0
    assert pc.source == "nrel_turbine_models"
    assert pc.thrust_coeffs is None  # no Ct column shipped


def test_fetch_turbine_models_no_match_raises(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "SomeTurbine.csv").write_text("Wind Speed [m/s],Power [kW]\n3.0,0\n")
    _stub_turbine_models(monkeypatch, data_dir)

    with pytest.raises(ValueError, match="No turbine-models curve named"):
        fetch_turbine_models_curve("does_not_exist")


def test_fetch_turbine_models_missing_columns_raises(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Columns the keyword matcher cannot map to ws/power.
    (data_dir / "Bad.csv").write_text("alpha,beta\n1,2\n3,4\n")
    _stub_turbine_models(monkeypatch, data_dir)

    with pytest.raises(ValueError, match="missing wind-speed/power columns"):
        fetch_turbine_models_curve("Bad")


# ── from_wasp_wtg: no PerformanceTable + bad AirDensity (354, 359-360) ─────────


def test_from_wasp_wtg_no_performance_table_raises(tmp_path) -> None:
    path = tmp_path / "empty.wtg"
    path.write_text(
        '<WindTurbineGenerator Description="X" RotorDiameter="200"></WindTurbineGenerator>'
    )
    with pytest.raises(ValueError, match="No <PerformanceTable>"):
        from_wasp_wtg(path)


def test_from_wasp_wtg_bad_air_density_defaults(tmp_path) -> None:
    """A non-numeric AirDensity falls back to 1.225 via the _density except-path."""
    path = tmp_path / "baddensity.wtg"
    path.write_text(
        '<WindTurbineGenerator Description="TC/10" RotorDiameter="180">'
        '<PerformanceTable AirDensity="not-a-number">'
        "<DataTable>"
        '<DataPoint WindSpeed="3.0" PowerOutput="0"/>'
        '<DataPoint WindSpeed="10.0" PowerOutput="5000000"/>'
        '<DataPoint WindSpeed="12.0" PowerOutput="10000000"/>'
        '<DataPoint WindSpeed="25.0" PowerOutput="0"/>'
        "</DataTable></PerformanceTable></WindTurbineGenerator>"
    )
    pc = from_wasp_wtg(path, air_density_kgm3=1.225, manufacturer="TestCo", key="tc10")
    # _density() swallowed the ValueError and reported the 1.225 default.
    assert pc.provenance["air_density_kgm3"] == 1.225
    assert pc.rated_capacity_kw == 10000.0
    # cut-in/out fall back to defaults (no StartStopStrategy present).
    assert pc.cut_in_ms == 3.0
    assert pc.cut_out_ms == 25.0


# ── from_tabular_file: no ws/power columns + certificate provenance ───────────


def test_from_tabular_file_missing_columns_raises(tmp_path) -> None:
    path = tmp_path / "nocols.csv"
    path.write_text("alpha,beta\n1,2\n3,4\n")
    with pytest.raises(ValueError, match="Could not find ws/power columns"):
        from_tabular_file(path, key="x", manufacturer="M", model="m")


def test_from_tabular_file_records_certificate(tmp_path) -> None:
    path = tmp_path / "curve.csv"
    path.write_text("wind speed (m/s),power (kW)\n3.0,0\n12.0,5000\n25.0,0\n")
    pc = from_tabular_file(
        path,
        key="cert_curve",
        manufacturer="M",
        model="m",
        rated_capacity_kw=5000,
        certificate="OEM-CERT-42",
    )
    assert pc.provenance["certificate"] == "OEM-CERT-42"
    assert pc.provenance["power_unit"] == "kW"
    assert pc.rated_capacity_kw == 5000.0
