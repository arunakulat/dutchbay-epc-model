"""Tests for scripts/run_blue_whale_wind_siting_v14.py (Blue Whale single-turbine yield).

The OEM power curve is confidential and never enters the repository, so every test here
uses a SYNTHETIC curve. The oracles do not come from the code under test:

* a closed-form Weibull integral for a flat-topped curve,
  ``AEP = P * 8760 * (exp(-(a/A)^k) - exp(-(b/A)^k))``;
* the independently written integrator ``wind_resource.bankable_aep.gross_aep_weibull``,
  which predates this change and is kept off the production path to serve as an oracle;
* the closed-form loss product ``1 - 0.97 * 0.98 * 0.98 * 0.99``;
* the power-law shear ratio ``(130/150)^0.14``.

The one test that touches the real curve runs only where ``BLUE_WHALE_POWER_CURVE_CSV``
points at it, and checks that the committed scenario still equals what the curve yields.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import numpy as np
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_blue_whale_wind_siting_v14.py"
CONF = REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml"
SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_hybrid_lot5b_2026.yaml"


def _load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("blue_whale_wind_siting_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()

WS = np.arange(3.0, 25.01, 0.5)


def _synthetic_curve() -> np.ndarray:
    """A smooth, generic 10 MW-class shape. Not derived from any OEM document."""
    rated, v_in, v_r = 10000.0, 3.0, 11.0
    p = rated * np.clip((WS**3 - v_in**3) / (v_r**3 - v_in**3), 0.0, 1.0)
    p[WS < v_in] = 0.0
    return np.asarray(p, dtype=np.float64)


def _write_curve(path: Path, ws: np.ndarray, pw: np.ndarray) -> Path:
    lines = ["# synthetic test curve", "wind_speed_ms,power_kw,thrust_coefficient"]
    lines += [f"{w},{p},0.5" for w, p in zip(ws, pw)]
    path.write_text("\n".join(lines) + "\n")
    return path


def _yield(pw: np.ndarray, **kw: Any) -> Dict[str, Any]:
    args: Dict[str, Any] = dict(
        derated_power_kw=9500.0,
        weibull_a_hub=8.0,
        weibull_k=2.665,
        rho_site_kgm3=1.15,
        rho_curve_kgm3=1.15,
        losses={"availability_pct": 100.0},
        integrator_tolerance_pct=0.1,
    )
    args.update(kw)
    return dict(cli.single_turbine_yield(WS, pw, **args))


# ---------------------------------------------------------------------------
# Closed forms and the independent integrator
# ---------------------------------------------------------------------------
def test_flat_topped_curve_matches_the_closed_form_weibull_integral() -> None:
    a_lo, b_hi, power = 5.0, 20.0, 4000.0
    ws = np.array([a_lo - 0.001, a_lo, b_hi])
    pw = np.array([0.0, power, power])
    A, k = 8.0, 2.0
    got = cli.single_turbine_yield(
        ws,
        pw,
        derated_power_kw=9500.0,
        weibull_a_hub=A,
        weibull_k=k,
        rho_site_kgm3=1.2,
        rho_curve_kgm3=1.2,
        losses={},
        integrator_tolerance_pct=1.0,
    )
    expected = (
        power
        * 8760.0
        * (math.exp(-((a_lo / A) ** k)) - math.exp(-((b_hi / A) ** k)))
        / 1e6
    )
    assert got["gross_aep_gwh"] == pytest.approx(expected, rel=5e-3)


def test_production_and_independent_integrators_agree() -> None:
    from wind_resource.bankable_aep import gross_aep_weibull

    pw = cli.derate_by_clipping(_synthetic_curve(), 9500.0)
    got = _yield(_synthetic_curve(), rho_site_kgm3=1.15, rho_curve_kgm3=1.148)
    oracle = gross_aep_weibull(
        wind_speed_ms=WS,
        power_kw=pw,
        weibull_a=8.0,
        weibull_k=2.665,
        rated_power_kw=9500.0,
        n_turbines=1,
        cut_in_ms=0.0,
        cut_out_ms=float(WS.max()) / got["density_velocity_factor"],
        rho_site_kgm3=1.15,
        rho_ref_kgm3=1.148,
    ).aep_gwh_farm
    assert got["gross_aep_gwh"] == pytest.approx(oracle, rel=1e-3)
    assert got["integrator_gap_pct"] < 0.1


def test_integrator_disagreement_fails_loud() -> None:
    with pytest.raises(ValueError, match="disagree"):
        _yield(_synthetic_curve(), integrator_tolerance_pct=0.0)


def test_loss_stack_matches_the_closed_form_product() -> None:
    losses = {
        "wake_loss_pct": 0.0,
        "availability_pct": 97.0,
        "electrical_loss_pct": 2.0,
        "curtailment_pct": 2.0,
        "other_pct": 1.0,
    }
    got = _yield(_synthetic_curve(), losses=losses)
    retention = 0.97 * 0.98 * 0.98 * 0.99
    assert got["net_aep_gwh"] == pytest.approx(
        got["gross_aep_gwh"] * retention, rel=1e-12
    )
    assert got["total_loss_pct"] == pytest.approx(100.0 * (1.0 - retention), rel=1e-12)
    assert got["net_capacity_factor"] == pytest.approx(
        got["net_aep_gwh"] * 1000.0 / (9.5 * 8760.0)
    )


def test_shear_and_operating_probability_closed_forms() -> None:
    a = cli.weibull_scale_at_height(8.199, 150.0, 130.0, 0.14)
    assert a == pytest.approx(8.199 * (130.0 / 150.0) ** 0.14, rel=1e-15)
    pw = _synthetic_curve()
    p = cli.operating_probability(WS, pw, 8.0, 2.0, 1.0)
    first = float(WS[pw > 0].min())
    assert p == pytest.approx(
        math.exp(-((first / 8.0) ** 2)) - math.exp(-((25.0 / 8.0) ** 2))
    )


# ---------------------------------------------------------------------------
# De-rate and responsiveness
# ---------------------------------------------------------------------------
def test_derate_invariants() -> None:
    pw = _synthetic_curve()
    full = _yield(pw, derated_power_kw=10000.0)["gross_aep_gwh"]
    above = _yield(pw, derated_power_kw=12000.0)["gross_aep_gwh"]
    clipped = _yield(pw, derated_power_kw=9500.0)["gross_aep_gwh"]
    lower = _yield(pw, derated_power_kw=8000.0)["gross_aep_gwh"]
    assert above == pytest.approx(
        full, rel=1e-12
    )  # a ceiling above the curve changes nothing
    assert lower < clipped < full
    assert float(cli.derate_by_clipping(pw, 9500.0).max()) == 9500.0
    with pytest.raises(ValueError):
        cli.derate_by_clipping(pw, 0.0)


def test_yield_responds_to_each_driver() -> None:
    pw = _synthetic_curve()
    base = _yield(pw)["gross_aep_gwh"]
    assert _yield(pw, weibull_a_hub=8.5)["gross_aep_gwh"] > base
    assert _yield(pw, rho_site_kgm3=1.10)["gross_aep_gwh"] < base  # thinner air
    lossy = _yield(pw, losses={"availability_pct": 90.0})
    assert lossy["net_aep_gwh"] == pytest.approx(0.9 * lossy["gross_aep_gwh"])


# ---------------------------------------------------------------------------
# Confidentiality guards on the curve loader
# ---------------------------------------------------------------------------
def test_loader_refuses_missing_and_in_repository_paths(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No power curve"):
        cli.load_private_power_curve(None)
    inside = REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml"
    with pytest.raises(ValueError, match="outside the repository"):
        cli.load_private_power_curve(str(inside))
    path = _write_curve(tmp_path / "c.csv", WS, _synthetic_curve())
    ws, pw = cli.load_private_power_curve(str(path))
    np.testing.assert_allclose(ws, WS)
    bad = _write_curve(tmp_path / "bad.csv", WS[::-1], _synthetic_curve())
    with pytest.raises(ValueError, match="increasing"):
        cli.load_private_power_curve(str(bad))


# ---------------------------------------------------------------------------
# The whole screen on a synthetic curve
# ---------------------------------------------------------------------------
def _config(curve: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(CONF.read_text())
    raw.pop("defaults")
    raw.pop("hydra")
    raw["turbine"]["power_curve_csv"] = str(curve)
    fl = raw["shadow_flicker"]
    fl.update(time_step_minutes=60, grid_half_width_m=200.0, grid_spacing_m=200.0)
    return dict(raw)


def test_run_on_a_synthetic_curve(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    curve = _write_curve(tmp_path / "curve.csv", WS, _synthetic_curve())
    out = cli.run(_config(curve))
    assert out["placeholder_site"] is True
    assert out["lot"]["site_geojson_matches_committed"] is True
    assert out["turbine"]["derated_power_mw"] == 9.5
    assert out["coastal_placement"]["tower_distance_to_coastline_m"] == pytest.approx(
        60.0, abs=0.05
    )
    assert out["tip_setback"]["setback_m"] == 233.0
    assert len(out["shadow_flicker"]["receptors"]) == 8
    text = json.dumps(out)
    for value in _synthetic_curve()[1:-1]:
        assert f"{value:.6f}" not in text  # no curve value leaks into the output


def test_hydra_entrypoint_prints_one_json_object(tmp_path: Path) -> None:
    pytest.importorskip("pvlib")
    pytest.importorskip("shapely")
    curve = _write_curve(tmp_path / "curve.csv", WS, _synthetic_curve())
    env = {
        **os.environ,
        "PYTHONPATH": str(REPO_ROOT),
        "BLUE_WHALE_POWER_CURVE_CSV": str(curve),
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "shadow_flicker.time_step_minutes=60",
            "shadow_flicker.grid_half_width_m=0",
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["config"] == "conf/blue_whale_wind_siting.yaml"
    assert not (tmp_path / "outputs").exists() and not (tmp_path / ".hydra").exists()


# ---------------------------------------------------------------------------
# The committed scenario against the curve it was derived from (private input)
# ---------------------------------------------------------------------------
def test_scenario_wind_block_is_internally_consistent() -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    wind = scen["generation"]["technologies"]["wind"]
    solar = scen["generation"]["technologies"]["solar"]
    assert wind["capacity_mw"] == 9.5
    assert wind["aep_gwh"] == pytest.approx(
        wind["capacity_mw"] * 8.76 * wind["capacity_factor"], abs=0.005
    )
    # Re-pinned for PR 6 capex: the blended single-turbine mode, USD 936.84/kW
    # (conf/blue_whale_capex_solar_resource.yaml). Before: 1300.0 (the B09 placeholder).
    assert wind["capex_usd"] == pytest.approx(936.84 * 1000.0 * wind["capacity_mw"])
    project = scen["project"]
    assert project["capacity_mw"] == wind["capacity_mw"] + solar["capacity_mw"]
    blend = (
        wind["capacity_mw"] * wind["capacity_factor"]
        + solar["capacity_mw"] * solar["capacity_factor"]
    ) / project["capacity_mw"]
    assert project["capacity_factor"] == pytest.approx(blend, abs=5e-7)
    e_w = wind["capacity_mw"] * wind["capacity_factor"]
    e_s = solar["capacity_mw"] * solar["capacity_factor"]
    tariff = (e_w * 25.73 + e_s * 20.72) / (e_w + e_s)
    assert scen["tariff"]["lkr_per_kwh"] == pytest.approx(tariff, abs=0.005)


@pytest.mark.skipif(
    not os.environ.get("BLUE_WHALE_POWER_CURVE_CSV"),
    reason="needs the confidential curve (BLUE_WHALE_POWER_CURVE_CSV); it is never in the repository",
)
def test_scenario_matches_the_private_curve_yield() -> None:
    raw = yaml.safe_load(CONF.read_text())
    basis = cli.resource_basis(raw["resource"])
    ws, pw = cli.load_private_power_curve(os.environ["BLUE_WHALE_POWER_CURVE_CSV"])
    a_hub = cli.weibull_scale_at_height(
        basis["weibull_a_ref_ms"],
        basis["reference_height_m"],
        130.0,
        basis["shear_exponent"],
    )
    got = cli.single_turbine_yield(
        ws,
        pw,
        derated_power_kw=raw["turbine"]["derated_power_kw"],
        weibull_a_hub=a_hub,
        weibull_k=basis["weibull_k"],
        rho_site_kgm3=basis["air_density_site_kgm3"],
        rho_curve_kgm3=raw["turbine"]["power_curve_air_density_kgm3"],
        losses=basis["losses"],
        integrator_tolerance_pct=raw["resource"]["integrator_tolerance_pct"],
    )
    # From PR 5 the scenario's wind CF rests on the met-mast transfer; this screen's ERA5
    # basis is recorded in that run's summary, which must still equal what the curve yields.
    era5 = json.loads(
        (
            REPO_ROOT / "docs" / "blue_whale" / "met_mast_transfer_summary.json"
        ).read_text()
    )["yield"]["era5_weibull_basis_1530"]
    assert era5["net_capacity_factor"] == pytest.approx(
        got["net_capacity_factor"], abs=5e-7
    )
    assert era5["net_aep_gwh"] == pytest.approx(got["net_aep_gwh"], abs=0.005)
