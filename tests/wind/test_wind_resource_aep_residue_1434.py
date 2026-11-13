"""Executable controls for #1434 wind_resource AEP-path residue (items 1 & 2)."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from wind_resource import layout_optimizer
from wind_resource.energy_calculator import EnergyCalculator

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_OPT_PATH = REPO_ROOT / "wind_resource" / "layout_optimizer.py"


def test_layout_optimizer_uses_shared_gaussian_k_star_ast() -> None:
    """AST guard (#1434 item 1): optimizer imports and calls gaussian_k_star with no inline closure."""
    source = LAYOUT_OPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_from_bankable = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "wind_resource.bankable_aep"
        and any(alias.name == "gaussian_k_star" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert imported_from_bankable, "layout_optimizer must import gaussian_k_star"

    called_k_star = any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "gaussian_k_star"
        for node in ast.walk(tree)
    )
    assert called_k_star, "layout_optimizer must call gaussian_k_star"

    inline_constants = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
    }
    assert 0.38 not in inline_constants
    assert 0.004 not in inline_constants


def test_build_wind_farm_model_propagates_gaussian_k_star(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Responsiveness guard: perturbing gaussian_k_star changes the wake k passed to PyWake."""
    pytest.importorskip("py_wake")
    captured: dict[str, Any] = {}
    import py_wake.literature.gaussian_models as gm

    def _fake_bpa(site: Any, wt: Any, *, k: float) -> dict[str, Any]:
        captured["k"] = k
        return {"k": k}

    monkeypatch.setattr(gm, "Bastankhah_PorteAgel_2014", _fake_bpa)
    monkeypatch.setattr(layout_optimizer, "gaussian_k_star", lambda ti: 0.12345)

    turbine = layout_optimizer.TurbineSpec(
        name="TestTurbine",
        rotor_diameter_m=171.0,
        hub_height_m=110.0,
        wind_speed_ms=np.array([0.0, 5.0, 10.0, 25.0]),
        power_kw=np.array([0.0, 1500.0, 6500.0, 6500.0]),
        thrust_coefficient=np.array([0.8, 0.8, 0.5, 0.2]),
    )
    res = layout_optimizer._build_wind_farm_model(
        turbine=turbine,
        wind_rose_freq=None,
        weibull_a=8.0,
        weibull_k=2.0,
        turbulence_intensity=0.08,
        default_sectors=12,
    )
    assert res["k"] == pytest.approx(0.12345, abs=1e-12)
    assert captured["k"] == pytest.approx(0.12345, abs=1e-12)


def test_energy_calculator_wind4_non_double_count_control(tmp_path: Path) -> None:
    """WIND-4 (#484, #1434 item 2): gross AEP is wake-free and net applies loss stack once."""
    idx = pd.date_range("2025-01-01", periods=8760, freq="h", tz="UTC")
    df = pd.DataFrame({"ws_150m": np.full(8760, 10.0)}, index=idx)
    power_curve = {"ws": [0.0, 10.0, 25.0], "power": [0.0, 2000.0, 2000.0]}

    cfg_zero_wake = tmp_path / "cfg_zero.yaml"
    cfg_wake = tmp_path / "cfg_wake.yaml"

    base_yaml = """
losses:
  availability: 0.97
  grid_curtailment: 0.98
  electrical: 0.99
  wake: {wake}
  environmental: 0.995
p_levels:
  p50: 1.0
revenue:
  default_tariff_lkr_kwh: 20.30
  default_exchange_rate_lkr_usd: 333.79
  ppa_years: 20
"""
    cfg_zero_wake.write_text(base_yaml.format(wake=1.0), encoding="utf-8")
    cfg_wake.write_text(base_yaml.format(wake=0.88), encoding="utf-8")

    calc_zero = EnergyCalculator(
        df=df,
        ws_column="ws_150m",
        power_curve=power_curve,
        num_turbines=10,
        config_path=str(cfg_zero_wake),
    )
    calc_wake = EnergyCalculator(
        df=df,
        ws_column="ws_150m",
        power_curve=power_curve,
        num_turbines=10,
        config_path=str(cfg_wake),
    )

    gross_zero = calc_zero.calculate_gross_aep()["windfarm_aep_mwh"]
    gross_wake = calc_wake.calculate_gross_aep()["windfarm_aep_mwh"]
    assert gross_zero == pytest.approx(gross_wake, abs=1e-9)

    net_wake = calc_wake.calculate_net_aep()
    expected_loss_factor = 0.97 * 0.98 * 0.99 * 0.88 * 0.995
    assert net_wake["total_loss_factor"] == pytest.approx(
        expected_loss_factor, abs=1e-12
    )
    assert net_wake["net_aep_p50_mwh"] == pytest.approx(
        gross_wake * expected_loss_factor, rel=1e-12
    )
