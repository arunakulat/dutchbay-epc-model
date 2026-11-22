"""Blue Whale's wake loss from the DutchBay turbines (#1887): pinned, reproducible, labelled.

``scripts/run_neighbour_wake_sensitivity_v14.py`` (``conf/neighbour_wake_sensitivity.yaml``) runs the Blue Whale turbine (at T2)
as the only counted turbine with every DutchBay turbine waking it, on Blue Whale's own
long-term resource at 130 m, and writes
``docs/blue_whale/wake_from_dutchbay_1887_summary.json``.

Oracles do not come from the code under test (TEST-01):

* the SHA-256 of each input file, recomputed here;
* a fresh Hydra run, compared with the committed summary;
* geometry from the configured WGS84 positions by an independent equirectangular
  projection: the nearest neighbours are T3 and T1 at the distances
  ``docs/blue_whale/STATUS.md`` quotes, and the two most-waked sectors are the ones that
  contain the bearings to them;
* a control: the same turbine with no neighbour has no wake loss;
* the sensitivity is not applied: Blue Whale's committed ``wake_model_pct`` stays 0.0.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_neighbour_wake_sensitivity_v14.py"
SUMMARY = REPO_ROOT / "docs" / "blue_whale" / "wake_from_dutchbay_1887_summary.json"
STATUS = REPO_ROOT / "docs" / "blue_whale" / "STATUS.md"
MAST = REPO_ROOT / "docs" / "blue_whale" / "met_mast_transfer_summary.json"
CONF_DIR = REPO_ROOT / "conf"


def _summary() -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return data


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bw_wake_1887", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _layout() -> Dict[str, Any]:
    conf = yaml.safe_load((CONF_DIR / "dutchbay_wake_14_turbines.yaml").read_text())
    return {t["id"]: t for t in conf["wake_rebaseline"]["layout"]["turbines"]}


def test_the_summary_pins_its_inputs() -> None:
    s = _summary()
    for block in (s["resource"], s["scaled_to_dutchbay_basis"]):
        rel = block["source"]
        digest = hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        assert (
            block["source_sha256"] == digest
        ), f"{rel} changed: regenerate the summary"


def test_a_fresh_run_reproduces_the_summary() -> None:
    pytest.importorskip("py_wake")
    pytest.importorskip("pyproj")
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf

    with initialize_config_dir(version_base="1.3", config_dir=str(CONF_DIR)):
        cfg = compose(config_name="neighbour_wake_sensitivity")
    raw = OmegaConf.to_container(cfg, resolve=True)
    assert isinstance(raw, dict)
    fresh = json.loads(json.dumps(_cli().run(raw), sort_keys=True))
    assert fresh == _summary()


def _east_north_m(a: Dict[str, Any], b: Dict[str, Any]) -> tuple[float, float]:
    """b relative to a, metres, by an equirectangular projection."""
    r = 6_371_008.8
    lat0 = math.radians((a["lat_deg"] + b["lat_deg"]) / 2)
    east = math.radians(b["lon_deg"] - a["lon_deg"]) * r * math.cos(lat0)
    north = math.radians(b["lat_deg"] - a["lat_deg"]) * r
    return east, north


def test_nearest_neighbours_and_waked_sectors_follow_the_geometry() -> None:
    s, layout = _summary(), _layout()
    me = layout[s["waked_id"]]
    near = {n["id"]: n["distance_m"] for n in s["nearest_neighbours_m"][:2]}
    assert set(near) == {"T1", "T3"}
    for tid, quoted in (("T1", 624.0), ("T3", 529.0)):  # docs/blue_whale/STATUS.md
        e, n = _east_north_m(me, layout[tid])
        assert math.hypot(e, n) == pytest.approx(near[tid], rel=0.01)
        assert near[tid] == pytest.approx(quoted, rel=0.01)
    centres = s["resource"]["sector_centre_deg"]
    width = 360.0 / len(centres)
    expected = set()
    for tid in ("T1", "T3"):
        e, n = _east_north_m(me, layout[tid])
        bearing = math.degrees(math.atan2(e, n)) % 360.0
        expected.add(int(((bearing + width / 2) % 360.0) // width))
    sector = s["primary"]["sector_wake_loss_pct"]
    top_two = set(sorted(range(len(sector)), key=lambda i: -sector[i])[:2])
    assert top_two == expected


def test_a_lone_turbine_has_no_wake_loss() -> None:
    pytest.importorskip("py_wake")
    from analytics.power_curves.oem_parser import (
        IEC_REFERENCE_AIR_DENSITY_KGM3,
        parse_power_curve,
    )
    from wind_resource.bankable_aep import model_wake_loss

    c = parse_power_curve(
        "iea_reference_10mw", air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    res = _summary()["resource"]
    rose = json.loads(MAST.read_text())["long_term_130m"]["rose"]
    out = model_wake_loss(
        wind_speed_ms=c["wind_speed_ms"],
        power_kw=c["power_kw"],
        thrust_coefficient=c["thrust_coefficient"],
        rotor_diameter_m=198.0,
        hub_height_m=150.0,
        layout_x_m=[0.0],
        layout_y_m=[0.0],
        weibull_a=res["weibull_a_ms"],
        weibull_k=res["weibull_k"],
        wind_rose_freq=[float(r["frequency"]) for r in rose],
    )
    assert out.wake_loss_pct == pytest.approx(0.0, abs=1e-9)
    assert _summary()["primary"]["wake_loss_pct"] > 0.0


def test_derived_lines_follow_from_the_primary_loss() -> None:
    s = _summary()
    loss = s["primary"]["wake_loss_pct"]
    assert s["net_energy_relative_change_if_applied_pct"] == pytest.approx(-loss)
    scaled = s["scaled_to_dutchbay_basis"]
    basis = json.loads((REPO_ROOT / scaled["source"]).read_text())
    assert (
        scaled["scale_to_basis"] == basis["per_turbine_sensitivity"]["scale_to_basis"]
    )
    assert scaled["wake_loss_pct"] == pytest.approx(
        loss * scaled["scale_to_basis"], abs=0.01
    )
    unc = s["implied_wake_model_uncertainty_pct"]
    assert unc["value"] == pytest.approx(loss * unc["fraction_of_loss"], abs=0.01)
    # The primary case is one of each sensitivity's cases.
    for cases in s["sensitivities"].values():
        assert s["primary"] in cases


def test_the_sensitivity_is_not_applied_and_the_status_note_cites_it() -> None:
    budget = json.loads(MAST.read_text())["uncertainty"]["energy_pct"]["budget"]
    assert budget["wake_model_pct"] == 0.0
    assert (
        _summary()["implied_wake_model_uncertainty_pct"]["committed_wake_model_pct"]
        == 0.0
    )
    note = STATUS.read_text(encoding="utf-8")
    assert "docs/blue_whale/wake_from_dutchbay_1887_summary.json" in note
    s = _summary()
    for figure in (
        s["primary"]["wake_loss_pct"],
        s["scaled_to_dutchbay_basis"]["wake_loss_pct"],
    ):
        assert f"{figure:.2f}%" in note
