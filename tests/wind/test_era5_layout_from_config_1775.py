"""The ERA5 processing script reads its turbine layout from configuration (#1775).

``scripts/process_era5_wind_data.py`` held the 15 DutchBay positions in code and treated all
15 as DutchBay turbines. Since #1577 the turbine at T2 is the Blue Whale turbine, and the
layout with each turbine's role lives in ``conf/dutchbay_wake_14_turbines.yaml``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "process_era5_wind_data.py"
CONF = REPO_ROOT / "conf" / "dutchbay_wake_14_turbines.yaml"


def _script() -> ModuleType:
    pytest.importorskip("xarray")
    spec = importlib.util.spec_from_file_location("process_era5_wind_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_holds_no_layout() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "TURBINE_LOCATIONS" not in text
    assert "79.75" not in text


def test_dutchbay_layout_counts_fourteen_and_skips_t2() -> None:
    counted, skipped = _script().load_turbine_layout(str(CONF))
    assert len(counted) == 14
    assert "T2" not in counted
    assert skipped == ["T2"]
    turbines = yaml.safe_load(CONF.read_text())["wake_rebaseline"]["layout"]["turbines"]
    t1 = next(t for t in turbines if t["id"] == "T1")
    assert counted["T1"] == (t1["lat_deg"], t1["lon_deg"])


def test_top_level_layout_without_roles_counts_every_turbine(tmp_path: Path) -> None:
    path = tmp_path / "layout.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "layout": {
                    "turbines": [
                        {"id": "A", "lat_deg": 1.0, "lon_deg": 2.0},
                        {"id": "B", "lat_deg": 1.5, "lon_deg": 2.5},
                    ]
                }
            }
        )
    )
    counted, skipped = _script().load_turbine_layout(str(path))
    assert counted == {"A": (1.0, 2.0), "B": (1.5, 2.5)}
    assert skipped == []


@pytest.mark.parametrize(
    ("doc", "message"),
    [
        ({"other": 1}, "exactly one layout.turbines"),
        ({"layout": {"turbines": []}}, "non-empty list"),
        ({"layout": {"turbines": [{"id": "A", "lat_deg": 1.0}]}}, "needs id"),
        (
            {
                "layout": {
                    "turbines": [
                        {"id": "A", "lat_deg": 1.0, "lon_deg": 2.0},
                        {"id": "A", "lat_deg": 1.0, "lon_deg": 2.0},
                    ]
                }
            },
            "repeats",
        ),
        (
            {
                "layout": {
                    "turbines": [{"id": "A", "lat_deg": 1, "lon_deg": 2, "role": "x"}]
                }
            },
            "unknown role",
        ),
        (
            {
                "layout": {
                    "turbines": [
                        {
                            "id": "A",
                            "lat_deg": 1,
                            "lon_deg": 2,
                            "role": "external_waker",
                        }
                    ]
                }
            },
            "no counted turbine",
        ),
    ],
)
def test_bad_layouts_are_refused(
    tmp_path: Path, doc: Dict[str, Any], message: str
) -> None:
    path = tmp_path / "layout.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match=message):
        _script().load_turbine_layout(str(path))


# ── hub height comes from configuration, never from the script ─────────────────


def _write(tmp_path: Path, doc: Dict[str, Any]) -> Path:
    path = tmp_path / "layout.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


_ONE_TURBINE = {"turbines": [{"id": "A", "lat_deg": 1.0, "lon_deg": 2.0}]}


def test_script_assumes_no_hub_height() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "HUB_HEIGHT" not in text
    assert "150" not in text


def test_dutchbay_hub_height_is_read_from_the_layout_block() -> None:
    declared = yaml.safe_load(CONF.read_text())["wake_rebaseline"]["turbine"][
        "hub_height_m"
    ]
    assert _script().load_hub_height(str(CONF)) == float(declared)


def test_hub_height_is_read_beside_a_top_level_layout(tmp_path: Path) -> None:
    path = _write(
        tmp_path, {"layout": _ONE_TURBINE, "turbine": {"hub_height_m": 112.5}}
    )
    assert _script().load_hub_height(str(path)) == 112.5


@pytest.mark.parametrize(
    "turbine",
    [None, {}, {"hub_height_m": 0}, {"hub_height_m": -5}, {"hub_height_m": True}],
)
def test_a_missing_or_bad_hub_height_is_refused(
    tmp_path: Path, turbine: object
) -> None:
    doc: Dict[str, Any] = {"layout": _ONE_TURBINE}
    if turbine is not None:
        doc["turbine"] = turbine
    with pytest.raises(ValueError, match="no hub height is assumed"):
        _script().load_hub_height(str(_write(tmp_path, doc)))


def test_two_layout_holders_are_refused(tmp_path: Path) -> None:
    path = _write(
        tmp_path, {"a": {"layout": _ONE_TURBINE}, "b": {"layout": _ONE_TURBINE}}
    )
    with pytest.raises(ValueError, match="found 2"):
        _script().load_turbine_layout(str(path))
    with pytest.raises(ValueError, match="found 2"):
        _script().load_hub_height(str(path))


def test_main_writes_hub_height_outputs_from_config(tmp_path: Path) -> None:
    """Run ``main()`` end to end on a small synthetic single-point ERA5 file."""
    xr = pytest.importorskip("xarray")
    np = pytest.importorskip("numpy")
    pytest.importorskip("netCDF4")
    import json

    hours = 48
    time = np.array("2020-01-01T00", dtype="datetime64[h]") + np.arange(hours)
    rng = np.random.default_rng(0)
    u10 = 4.0 + rng.random(hours)
    u100 = 6.0 + rng.random(hours)
    ds = xr.Dataset(
        {
            "u10": ("time", u10),
            "v10": ("time", np.zeros(hours)),
            "u100": ("time", u100),
            "v100": ("time", np.zeros(hours)),
        },
        coords={"time": time},
    )
    nc = tmp_path / "era5.nc"
    ds.to_netcdf(nc)
    layout = _write(
        tmp_path,
        {
            "block": {
                "turbine": {"hub_height_m": 120},
                "layout": {
                    "turbines": [
                        {"id": "A", "lat_deg": 1.0, "lon_deg": 2.0},
                        {"id": "B", "lat_deg": 1.1, "lon_deg": 2.1},
                        {
                            "id": "X",
                            "lat_deg": 1.2,
                            "lon_deg": 2.2,
                            "role": "external_waker",
                        },
                    ]
                },
            }
        },
    )
    out = tmp_path / "out"
    df, stats = _script().main(str(nc), str(layout), str(out))
    assert sorted(df["turbine_id"].unique()) == ["A", "B"]
    assert set(stats["hub_height_m"]) == {120.0}
    site = json.loads((out / "site_average.json").read_text())
    assert site["hub_height_m"] == 120.0
    assert site["turbines_counted"] == 2
    assert site["turbines_skipped"] == ["X"]
    # 120 m sits above the 100 m level, so the power-law speed exceeds the 100 m speed.
    assert site["mean_ws_hub"] > float(u100.mean())
    for name in ("wind_hub_hourly.csv", "wind_hub_summary.csv", "wind_hub_monthly.csv"):
        assert (out / name).exists(), name
