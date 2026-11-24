"""Per-turbine wake losses and waked roses, as a labelled sensitivity (#1589).

The owner asked on 2026-11-16 whether PyWake and a wind rose can be applied to each of
DutchBay's 14 turbines, and chose "Build it, reopen #1589". ``model_wake_loss`` now returns
each turbine's share of a run beside the farm figures, which it computes as before. The
re-baseline runner records the per-turbine block next to the lender basis, and labels it a
resource sensitivity because the live farm loss is far above the frozen value (#1589).
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "run_dutchbay_wake_rebaseline_v14.py"
CONF = REPO_ROOT / "conf" / "dutchbay_wake_14_turbines.yaml"
SUMMARY = REPO_ROOT / "docs" / "wind" / "dutchbay_14_turbine_wake_summary.json"


def _cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rebaseline_1589", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fresh() -> Dict[str, Any]:
    pytest.importorskip("py_wake")
    pytest.importorskip("pyproj")
    cfg = yaml.safe_load(CONF.read_text())
    cfg.pop("defaults", None)
    result: Dict[str, Any] = _cli().run(cfg)
    return result


def _row_layout() -> Dict[str, Any]:
    pytest.importorskip("py_wake")
    from analytics.power_curves.oem_parser import (
        IEC_REFERENCE_AIR_DENSITY_KGM3,
        parse_power_curve,
    )

    c = parse_power_curve(
        "iea_reference_10mw", air_density_kgm3=IEC_REFERENCE_AIR_DENSITY_KGM3
    )
    return {
        "wind_speed_ms": c["wind_speed_ms"],
        "power_kw": c["power_kw"],
        "thrust_coefficient": c["thrust_coefficient"],
        "rotor_diameter_m": 198.0,
        "hub_height_m": 150.0,
        "layout_x_m": [0.0, 0.0, 0.0],
        "layout_y_m": [1200.0, 600.0, 0.0],
        "weibull_a": 8.0,
        "weibull_k": 2.0,
        "wind_rose_freq": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    }


def test_per_turbine_figures_add_up_to_the_farm() -> None:
    from wind_resource.bankable_aep import model_wake_loss

    kwargs = _row_layout()
    res = model_wake_loss(**kwargs, counted=[True, False, True])
    assert [t.index for t in res.per_turbine] == [0, 1, 2]
    assert [t.counted for t in res.per_turbine] == [True, False, True]
    counted = [t for t in res.per_turbine if t.counted]
    assert sum(t.aep_wake_gwh for t in counted) == pytest.approx(res.aep_wake_gwh)
    assert sum(t.aep_gross_gwh for t in counted) == pytest.approx(res.aep_gross_gwh)
    for t in res.per_turbine:
        assert len(t.sector_wake_loss_pct) == 8
        assert sum(t.sector_energy_share) == pytest.approx(1.0)


def test_the_rose_follows_the_wind_direction() -> None:
    """All wind from the south (sector 4 of 8): the north turbine sits in both wakes."""
    from wind_resource.bankable_aep import model_wake_loss

    kwargs = _row_layout()
    kwargs["wind_rose_freq"] = [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    res = model_wake_loss(**kwargs)
    north, middle, south = res.per_turbine
    assert south.wake_loss_pct == pytest.approx(0.0, abs=1e-6)
    assert north.wake_loss_pct > middle.wake_loss_pct > 0.0
    assert max(range(8), key=lambda i: north.sector_energy_share[i]) == 4


def test_the_farm_figures_do_not_move(fresh: Dict[str, Any]) -> None:
    committed = json.loads(SUMMARY.read_text())
    assert fresh["wake_loss_14_pct"] == committed["wake_loss_14_pct"] == 7.32
    _assert_same_model_values(fresh["real_layout"], committed["real_layout"])
    _assert_same_model_values(fresh["synthetic_row"], committed["synthetic_row"])


def _assert_same_model_values(actual: Any, expected: Any) -> None:
    """Permit only bounded float roundoff; preserve types, keys and provenance."""
    assert type(actual) is type(expected)
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            _assert_same_model_values(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, e in zip(actual, expected):
            _assert_same_model_values(a, e)
    elif isinstance(expected, float):
        assert math.isfinite(actual) and math.isfinite(expected)
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-10)
    else:
        assert actual == expected


def test_machine_precision_comparison_accepts_observed_roundoff() -> None:
    _assert_same_model_values(
        {"energy": 432.9616663079632}, {"energy": 432.961666307966}
    )


@pytest.mark.parametrize(
    "actual, expected",
    [
        ({"energy": 432.961667}, {"energy": 432.961666}),
        ({"loss": 19.435306}, {"loss": 19.435305}),
        ({"ratio": 1.000001}, {"ratio": 1.0}),
        ({"count": True}, {"count": 1}),
        ({"count": 14.0}, {"count": 14}),
        ({"energy": 1}, {"energy": 1.0}),
        ({"energy": float("nan")}, {"energy": 1.0}),
        ({"energy": float("inf")}, {"energy": float("inf")}),
        ({"model": "changed"}, {"model": "original"}),
        ({"energy": 1.0, "extra": 2}, {"energy": 1.0}),
        ([1, 2], [1]),
    ],
)
def test_machine_precision_comparison_rejects_regression(
    actual: Any, expected: Any
) -> None:
    with pytest.raises(AssertionError):
        _assert_same_model_values(actual, expected)


def test_the_committed_summary_carries_the_fresh_per_turbine_block(
    fresh: Dict[str, Any],
) -> None:
    committed = json.loads(SUMMARY.read_text())
    assert fresh["per_turbine_sensitivity"] == committed["per_turbine_sensitivity"]


def test_the_block_is_labelled_a_sensitivity_and_scales_to_the_basis(
    fresh: Dict[str, Any],
) -> None:
    block = fresh["per_turbine_sensitivity"]
    assert block["label"].startswith("Resource sensitivity, not the lender basis.")
    assert block["work_item"] == "#1589"
    assert block["basis_wake_loss_pct"] == fresh["wake_loss_14_pct"]
    live = fresh["real_layout"]["dutchbay_14_t2_waking"]["wake_loss_pct"]
    assert block["scale_to_basis"] == pytest.approx(
        fresh["wake_loss_14_pct"] / live, abs=1e-6
    )
    rows = {t["id"]: t for t in block["turbines"]}
    assert len(rows) == 15
    assert rows["T2"]["counted"] is False and rows["T2"]["scaled_to_basis_pct"] is None
    for t in block["turbines"]:
        if t["counted"]:
            assert t["scaled_to_basis_pct"] == pytest.approx(
                t["live_wake_loss_pct"] * block["scale_to_basis"], abs=0.011
            )


def test_the_roses_draw(tmp_path: Path, fresh: Dict[str, Any]) -> None:
    pytest.importorskip("matplotlib")
    from app.reports.wind_rose_plot import render_turbine_wake_roses_png

    block = fresh["per_turbine_sensitivity"]
    out = tmp_path / "roses.png"
    render_turbine_wake_roses_png(
        block["turbines"], block["sector_deg"], str(out), title=block["label"]
    )
    assert out.read_bytes().startswith(b"\x89PNG")


def test_the_conf_draws_no_roses_by_default() -> None:
    cfg = yaml.safe_load(CONF.read_text())
    assert cfg["wake_rebaseline"]["per_turbine_rose_png"] is None
