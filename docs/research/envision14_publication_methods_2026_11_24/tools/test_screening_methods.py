"""Independent hand-calculable synthetic cases; no site inputs."""

import hashlib

import pytest
from path_guard import TRUSTED_CHECKOUT, require_external_path
from screening_methods import (
    paired_export_screen,
    validate_curve_snapshot,
    wind_accounting,
)


def test_wind_denominator_and_loss_stack():
    result = wind_accounting(
        owned_units=4,
        nameplate_mw=5,
        cap_mw=3,
        gross_mwh=1000,
        wake_loss=0.2,
        nonwake_retention=0.9,
        hours=100,
    )
    assert result["owned_nameplate_mw"] == 20
    assert result["owned_active_cap_mw"] == 12
    assert result["waked_mwh"] == 800
    assert result["net_mwh"] == 720
    assert result["net_capacity_factor_on_assumed_cap"] == pytest.approx(0.6)
    assert result["probability_quantiles"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"owned_units": True},
        {"cap_mw": 6},
        {"gross_mwh": 1201},
        {"wake_loss": -0.1},
        {"nonwake_retention": 1.1},
        {"hours": float("nan")},
        {"gross_mwh": float("inf")},
        {"nameplate_mw": 10**500},
        {"nameplate_mw": 1e308},
        {"hours": 1e308},
        {"owned_units": 10**500},
    ],
)
def test_wind_rejects_invalid_inputs(changes):
    base = dict(
        owned_units=4,
        nameplate_mw=5,
        cap_mw=3,
        gross_mwh=1000,
        wake_loss=0.2,
        nonwake_retention=0.9,
        hours=100,
    )
    base.update(changes)
    with pytest.raises(ValueError):
        wind_accounting(**base)


def grid_inputs():
    return dict(
        nominal_kv=33,
        source_fault_mva=200,
        line_r_ohm=3,
        line_x_ohm=4,
        own_mva=15,
        own_mw=12,
        external_mva=5,
        external_mw=4,
        transformer_mva=10,
        transformer_count=2,
        power_factor=0.9,
    )


def test_paired_export_and_static_limit():
    result = paired_export_screen(**grid_inputs())
    own, shared = result["cases"]
    # 3-4-5 impedance triangle and fixed source impedance 1089/200.
    equivalent = 1089 / (1089 / 200 + 5)
    assert own["scr_magnitude_only"] == pytest.approx(equivalent / 15)
    assert shared["scr_magnitude_only"] == pytest.approx(equivalent / 20)
    assert own["n_minus_one_static_shortfall_mw"] == 3
    assert shared["n_minus_one_static_shortfall_mw"] == 7
    assert not own["selected_design"] and not shared["selected_design"]
    assert result["physical_boundary"] == "UNKNOWN"
    assert result["annual_energy_curtailment"] is None
    assert result["shared_asset_allocation"] is None
    assert result["utility_approval"] is False


@pytest.mark.parametrize(
    "changes",
    [
        {"own_mw": 16},
        {"external_mw": 6},
        {"transformer_count": 1},
        {"power_factor": 0},
        {"source_fault_mva": float("nan")},
        {"nominal_kv": 1e308},
        {"nominal_kv": 1e-308},
        {"own_mva": 1e308, "external_mva": 1e308},
    ],
)
def test_grid_rejects_invalid_inputs(changes):
    base = grid_inputs()
    base.update(changes)
    with pytest.raises(ValueError):
        paired_export_screen(**base)


def curve():
    return b"wind_speed_ms,power_kw,thrust_coefficient\n1,0,0.2\n2,100,0.3\n"


def test_curve_single_snapshot_and_digest():
    data = curve()
    assert validate_curve_snapshot(data, hashlib.sha256(data).hexdigest(), 200) == (
        (1, 0, 0.2),
        (2, 100, 0.3),
    )
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_curve_snapshot(
            data + b"3,100,0.3\n", hashlib.sha256(data).hexdigest(), 200
        )


@pytest.mark.parametrize(
    "row",
    [
        b"2,nan,0.3\n",
        b"2,201,0.3\n",
        b"1,100,0.3\n",
        b"2,100,3\n",
        b"2,100,0.3,extra\n",
        b"2,100\n",
    ],
)
def test_curve_rejects_malformed_rows(row):
    data = curve().splitlines(keepends=True)[0] + b"1,0,0.2\n" + row
    with pytest.raises(ValueError):
        validate_curve_snapshot(data, hashlib.sha256(data).hexdigest(), 200)


def test_external_output_guard_no_caller_override(tmp_path):
    with pytest.raises(ValueError):
        require_external_path(
            TRUSTED_CHECKOUT / "restricted.csv", declared_repo=tmp_path
        )
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / ".git").write_text("synthetic gitdir marker")
    with pytest.raises(ValueError):
        require_external_path(foreign / "restricted.csv")
    link = tmp_path / "via_symlink"
    link.symlink_to(TRUSTED_CHECKOUT, target_is_directory=True)
    with pytest.raises(ValueError):
        require_external_path(link / "restricted.csv")
    assert require_external_path(tmp_path / "safe.csv") == tmp_path / "safe.csv"
