"""The ERA5 processing script reads its turbine layout from configuration (#1775).

``scripts/process_era5_wind_data.py`` held the 15 DutchBay positions in code and treated all
15 as DutchBay turbines. Since #1577 the turbine at T2 is the Blue Whale turbine, and the
layout with each turbine's role lives in ``conf/dutchbay_wake_14_turbines.yaml``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

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
def test_bad_layouts_are_refused(tmp_path: Path, doc: dict, message: str) -> None:
    path = tmp_path / "layout.yaml"
    path.write_text(yaml.safe_dump(doc))
    with pytest.raises(ValueError, match=message):
        _script().load_turbine_layout(str(path))
