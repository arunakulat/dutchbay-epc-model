"""DutchBay drops to 14 turbines when the Blue Whale turbine takes T2 (#1577).

Three groups of checks:

- the wake re-baseline reproduces from ``conf/dutchbay_wake_14_turbines.yaml``, and its
  layout is the recorded one: the 15 positions are pinned by digest (they lived in
  ``scripts/process_era5_wind_data.py`` until #1775 moved them to this config), and T2 is the
  Blue Whale siting reference point;
- every scenario built on the IEA 10 MW layout carries 14 turbines, the re-baselined wake,
  and capex and opex breakdowns that still sum to the totals the engine reads;
- the per-turbine cost rule holds against the 15-turbine lines frozen at
  ``legacy_scenarios/dutchbay_lendercase_2025Q4_15_turbines.yaml``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_dutchbay_wake_rebaseline_v14.py"
CONF = REPO_ROOT / "conf" / "dutchbay_wake_14_turbines.yaml"
SUMMARY = REPO_ROOT / "docs" / "wind" / "dutchbay_14_turbine_wake_summary.json"
FROZEN_15 = (
    REPO_ROOT / "legacy_scenarios" / "dutchbay_lendercase_2025Q4_15_turbines.yaml"
)

SCENARIOS = (
    "dutchbay_lendercase_2025Q4",
    "dutchbay_lendercase_5usc_fixed_lkr",
    "dutchbay_capex_eia_prudent_2025Q4",
    "dutchbay_capex_sinohydro_lean_2025Q4",
    "dutchbay_hybrid_windsolar_2025Q4",
    "dutchbay_hybrid_bess_2025Q4",
)
RATED_MW = 10.6383


def _load(name: str) -> Dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "scenarios" / f"{name}.yaml").read_text())


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dutchbay_wake_rebaseline_cli", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: SHA-256 of the 15 recorded positions (ENVISION_ROAD-DATA.pdf), one ``id,lat,lon`` line
#: per turbine at 6 dp, T1 to T15. Computed from ``TURBINE_LOCATIONS`` in
#: ``scripts/process_era5_wind_data.py`` at 1711fcf3, before #1775 moved the layout into
#: configuration, so the config cannot drift from the record unnoticed.
RECORDED_LAYOUT_SHA256 = (
    "54547d208ddd94ef505aba796e4c06b96468097a886b6ebd28b0fd48a16b232f"
)
SITING_CONF = REPO_ROOT / "conf" / "blue_whale_wind_siting.yaml"


def test_wake_layout_is_the_recorded_layout_with_t2_as_the_waker() -> None:
    conf = yaml.safe_load(CONF.read_text())["wake_rebaseline"]
    turbines = conf["layout"]["turbines"]
    assert [t["id"] for t in turbines] == [f"T{i}" for i in range(1, 16)]
    canon = "\n".join(
        f"{t['id']},{t['lat_deg']:.6f},{t['lon_deg']:.6f}" for t in turbines
    )
    assert hashlib.sha256(canon.encode()).hexdigest() == RECORDED_LAYOUT_SHA256
    # Independent record of T2: the Blue Whale siting reference point.
    site = yaml.safe_load(SITING_CONF.read_text())["site"]
    t2 = next(t for t in turbines if t["id"] == "T2")
    assert site["reference_point_name"] == "T2"
    assert round(t2["lat_deg"], 4) == site["reference_lat_deg"]
    assert round(t2["lon_deg"], 4) == site["reference_lon_deg"]
    wakers = [t["id"] for t in turbines if t["role"] == "external_waker"]
    assert wakers == ["T2"]
    assert sum(t["role"] == "counted" for t in turbines) == 14


def test_wake_rebaseline_reproduces_the_committed_summary() -> None:
    pytest.importorskip("py_wake")
    pytest.importorskip("pyproj")
    cfg = yaml.safe_load(CONF.read_text())
    cfg.pop("defaults", None)
    fresh = _cli().run(cfg)
    committed = json.loads(SUMMARY.read_text())
    assert fresh["wake_loss_14_pct"] == committed["wake_loss_14_pct"]
    assert fresh["sensitivities_pct"] == committed["sensitivities_pct"]
    for block in ("real_layout", "synthetic_row"):
        for key in ("ratio_t2_waking", "ratio_t2_removed"):
            assert fresh[block][key] == pytest.approx(committed[block][key], rel=1e-9)
    assert fresh["real_layout"]["dutchbay_14_t2_waking"]["n_turbines_counted"] == 14


def test_summary_states_the_frozen_value_it_scales() -> None:
    committed = json.loads(SUMMARY.read_text())
    frozen = yaml.safe_load(FROZEN_15.read_text())
    assert (
        committed["frozen_wake_15_pct"] == frozen["resource"]["losses"]["wake_loss_pct"]
    )
    assert committed["wake_loss_14_pct"] == round(
        committed["frozen_wake_15_pct"] * committed["real_layout"]["ratio_t2_waking"], 2
    )


@pytest.mark.parametrize("name", SCENARIOS)
def test_scenario_carries_fourteen_turbines(name: str) -> None:
    cfg = _load(name)
    wake = json.loads(SUMMARY.read_text())["wake_loss_14_pct"]
    assert cfg["turbine"]["n_turbines"] == 14
    assert cfg["resource"]["turbines"]["count"] == 14
    nameplate = round(14 * RATED_MW, 1)
    assert cfg["turbine"]["total_capacity_mw"] == nameplate
    assert cfg["resource"]["turbines"]["total_capacity_mw"] == nameplate
    assert cfg["resource"]["losses"]["wake_loss_pct"] == wake
    wind_mw = (
        cfg["generation"]["technologies"]["wind"]["capacity_mw"]
        if "generation" in cfg
        else cfg["project"]["capacity_mw"]
    )
    assert wind_mw == nameplate


@pytest.mark.parametrize("name", SCENARIOS)
def test_cost_breakdowns_sum_to_the_totals_the_engine_reads(name: str) -> None:
    cfg = _load(name)
    capex_lines = cfg["capex"].get("breakdown")
    if capex_lines:
        assert sum(capex_lines.values()) == cfg["capex"]["usd_total"]
    opex_lines = cfg["opex"]["breakdown"]
    land = opex_lines["land_lease_usd"]
    assert land == 280000  # 14 turbine sites at 20,000 each
    if "generation" not in cfg:
        assert sum(opex_lines.values()) == cfg["opex"]["usd_per_year"]


def test_lender_capex_scales_only_the_per_turbine_lines() -> None:
    old = yaml.safe_load(FROZEN_15.read_text())["capex"]["breakdown"]
    new = _load("dutchbay_lendercase_2025Q4")["capex"]["breakdown"]
    per_turbine = {"wtg_supply_usd", "foundation_usd", "erection_usd"}
    assert set(old) == set(new)
    for key in old:
        if key in per_turbine:
            assert new[key] == pytest.approx(old[key] * 14 / 15, abs=0.5)
        else:
            assert new[key] == old[key]


def test_lender_import_share_is_the_wtg_share_of_capex() -> None:
    cfg = _load("dutchbay_lendercase_2025Q4")
    share = cfg["capex"]["breakdown"]["wtg_supply_usd"] / cfg["capex"]["usd_total"]
    assert cfg["taxes_indirect"]["import_share_pct"] == round(share, 4)


def test_grid_screen_plant_rating_follows_the_nameplate() -> None:
    cfg = _load("dutchbay_lendercase_2025Q4")
    assert cfg["grid"]["plant_rating_mva"] == cfg["project"]["capacity_mw"]
    assert cfg["grid"]["poc"]["plant_rated_mva"] == cfg["project"]["capacity_mw"]
