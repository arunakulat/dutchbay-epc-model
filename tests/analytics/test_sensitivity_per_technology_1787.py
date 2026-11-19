"""#1787: the one-way sensitivity runs on a scenario that declares its generation per technology.

The capacity-factor driver shocked ``project.capacity_factor`` alone. A scenario with a
``generation.technologies`` block then failed the pipeline's year-1 reconciliation (the
technologies' capacity-weighted capacity factor must match the project's within 1%), so no
solar, hybrid or Blue Whale scenario got a tornado. The engine now scales every counted
technology's capacity factor by the same ratio as the project figure.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.core.sensitivity_runner import run_sensitivity_analysis_from_path
from analytics.sensitivity.engine import coherent_overrides

REPO = Path(__file__).resolve().parents[2]
CF = "project.capacity_factor"

#: The scenarios #1787 names, plus the Blue Whale wind and hybrid scenarios.
PER_TECHNOLOGY = (
    "scenarios/dutchbay_solar_only_2025Q4.yaml",
    "scenarios/dutchbay_hybrid_bess_2025Q4.yaml",
    "scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml",
    "scenarios/blue_whale_wind_lot5b_2026.yaml",
    "scenarios/blue_whale_hybrid_lot5b_2026.yaml",
)


def _hybrid() -> Dict[str, Any]:
    return {
        "project": {"capacity_mw": 20.0, "capacity_factor": 0.3},
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 10.0, "capacity_factor": 0.4},
                "solar": {"capacity_mw": 10.0, "capacity_factor": 0.2},
                "bess_1": {"type": "bess", "capacity_mw": 5.0, "capacity_factor": 0.9},
                "aux": {"capacity_mw": 1.0},
            }
        },
    }


def _weighted(cfg: Dict[str, Any], overrides: Dict[str, Any]) -> float:
    total = 0.0
    for name, block in cfg["generation"]["technologies"].items():
        key = f"generation.technologies.{name}.capacity_factor"
        if key in overrides:
            total += block["capacity_mw"] * overrides[key]
    return total


# ------------------------------------------------------------------ unit cases


def test_a_capacity_factor_shock_scales_each_counted_technology() -> None:
    cfg = _hybrid()
    out = coherent_overrides(cfg, {CF: 0.33})
    assert out[CF] == 0.33
    assert out["generation.technologies.wind.capacity_factor"] == pytest.approx(0.44)
    assert out["generation.technologies.solar.capacity_factor"] == pytest.approx(0.22)
    # Storage, and a block without a capacity factor, are not generation the
    # reconciliation counts, so they are left alone.
    assert set(out) == {
        CF,
        "generation.technologies.wind.capacity_factor",
        "generation.technologies.solar.capacity_factor",
    }
    # The shocked technologies reconcile with the shocked project figure exactly.
    assert _weighted(cfg, out) == pytest.approx(20.0 * 0.33, rel=1e-12)


@pytest.mark.parametrize(
    "overrides", [{"capex.usd_total": 1.0}, {"tariff.lkr_per_kwh": 20.0}, {}]
)
def test_any_other_shock_passes_unchanged(overrides: Dict[str, Any]) -> None:
    assert coherent_overrides(_hybrid(), overrides) == overrides


def test_a_scenario_without_counted_technologies_passes_unchanged() -> None:
    no_block = {"project": {"capacity_factor": 0.3}}
    assert coherent_overrides(no_block, {CF: 0.33}) == {CF: 0.33}
    storage_only = {
        "project": {"capacity_factor": 0.0},
        "generation": {"technologies": {"bess": {"type": "bess", "power_mw": 10}}},
    }
    assert coherent_overrides(storage_only, {CF: 0.0}) == {CF: 0.0}


def test_a_non_positive_base_refuses() -> None:
    cfg = _hybrid()
    cfg["project"]["capacity_factor"] = 0.0
    with pytest.raises(ValueError, match="positive base project.capacity_factor"):
        coherent_overrides(cfg, {CF: 0.1})


def test_a_technology_shocked_twice_refuses() -> None:
    key = "generation.technologies.wind.capacity_factor"
    with pytest.raises(ValueError, match="overridden directly and through"):
        coherent_overrides(_hybrid(), {CF: 0.33, key: 0.5})


def test_a_dotted_technology_name_refuses() -> None:
    cfg = _hybrid()
    techs = cfg["generation"]["technologies"]
    techs["wind.north"] = techs.pop("wind")
    with pytest.raises(ValueError, match="cannot be shocked by a dotted override"):
        coherent_overrides(cfg, {CF: 0.33})


# ------------------------------------------------------------ committed scenarios


@pytest.mark.parametrize("rel", PER_TECHNOLOGY)
def test_the_sensitivity_runs_on_a_per_technology_scenario(rel: str) -> None:
    logging.disable(logging.WARNING)
    try:
        suite = run_sensitivity_analysis_from_path(REPO / rel, metric="project_irr")
    finally:
        logging.disable(logging.NOTSET)
    by_label = {t.label: t for t in suite.tornado_results}
    shock = by_label["Capacity Factor"].shock_results[0]
    base = by_label["Capacity Factor"].base_metric
    assert math.isfinite(shock.low_case) and math.isfinite(shock.high_case)
    assert shock.low_case < base < shock.high_case


@pytest.mark.parametrize("rel", PER_TECHNOLOGY)
def test_each_shocked_point_reconciles(rel: str) -> None:
    """The shocked technologies match the shocked project figure, as the pipeline requires."""
    cfg = yaml.safe_load((REPO / rel).read_text(encoding="utf-8"))
    base = cfg["project"]["capacity_factor"]
    mw = cfg["project"]["capacity_mw"]
    for factor in (0.9, 1.1):
        out = coherent_overrides(cfg, {CF: base * factor})
        assert len(out) > 1
        assert _weighted(cfg, out) == pytest.approx(
            factor * _weighted(cfg, coherent_overrides(cfg, {CF: base})), rel=1e-12
        )
        assert (
            abs(_weighted(cfg, out) - mw * base * factor) / (mw * base * factor) < 0.01
        )


def test_a_single_technology_scenario_without_the_block_is_untouched() -> None:
    cfg = yaml.safe_load(
        (REPO / "scenarios/dutchbay_basecase_2025Q4.yaml").read_text(encoding="utf-8")
    )
    assert "technologies" not in (cfg.get("generation") or {})
    assert coherent_overrides(cfg, {CF: 0.3}) == {CF: 0.3}


def test_the_single_parameter_suite_is_coherent_too() -> None:
    """``build_one_way_sensitivity_suite`` takes the same route as the multi-driver run."""
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.scenario_loader import load_scenario_config
    from analytics.sensitivity.engine import build_one_way_sensitivity_suite

    cfg = load_scenario_config(REPO / PER_TECHNOLOGY[0])
    param = ParameterRangeConfig(
        variable_name=CF,
        base_value=float(cfg["project"]["capacity_factor"]),
        low_pct=-10.0,
        high_pct=10.0,
        label="Capacity Factor",
    )
    logging.disable(logging.WARNING)
    try:
        suite = build_one_way_sensitivity_suite(
            base_config=cfg, parameter=param, metric_key="project_irr"
        )
    finally:
        logging.disable(logging.NOTSET)
    shock = suite.tornado_results[0].shock_results[0]
    assert shock.low_case < suite.tornado_results[0].base_metric < shock.high_case
