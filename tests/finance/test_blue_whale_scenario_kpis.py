"""Regression pins for the Blue Whale Lot 5B scenario (v0.4, model 15.10.0).

The scenario is a screening skeleton on placeholder inputs, so these pins prove only that
the committed KPIs have not moved unnoticed. ``TEST-01`` pairs each pin with a
responsiveness guard: the year-1 generation revenue must equal the closed form
``(sum of capacity x CF x 8760) x tariff`` the engine is meant to compute, and the
project IRR must move with the wind capacity factor and the tariff. A pipeline that
returned the pinned numbers without deriving them would fail those guards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides

SCENARIO = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "blue_whale_hybrid_lot5b_2026.yaml"
)

# Pinned at 15.10.0 (v0.4: EN-206/10.5 de-rated to 9.5 MW). Before, at 15.9.0 (v0.3):
# project IRR 0.027674815875491747, equity IRR 0.0006314091936767685,
# min DSCR 0.8688229918413363.
PINS = {
    "project_irr": 0.03150801785651182,
    "equity_irr": 0.005060003909760136,
    "min_dscr": 0.8685883776324956,
}


def _kpis(overrides: Dict[str, Any] | None = None) -> Dict[str, float]:
    out = evaluate_with_overrides(str(SCENARIO), overrides=overrides or {})
    return {k: float(v) for k, v in out.items() if isinstance(v, (int, float))}


@pytest.fixture(scope="module")
def base() -> Dict[str, float]:
    return _kpis()


def test_blue_whale_kpi_pins(base: Dict[str, float]) -> None:
    for key, pinned in PINS.items():
        assert base[key] == pytest.approx(pinned, rel=1e-9, abs=1e-12), key


def test_year_one_generation_revenue_is_derived_from_the_wind_block() -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    techs = scen["generation"]["technologies"]
    full = evaluate_with_overrides(str(SCENARIO), overrides={}, return_full_result=True)
    assert isinstance(full, dict)
    row = full["annual_rows"][0]
    mwh = sum(
        t["capacity_mw"] * t["capacity_factor"] * 8760.0
        for name, t in techs.items()
        if name in ("wind", "solar")
    )
    assert row["generation_revenue_lkr"] == pytest.approx(
        mwh * 1000.0 * scen["tariff"]["lkr_per_kwh"], rel=1e-6
    )


def test_project_irr_moves_with_wind_cf_and_tariff(base: Dict[str, float]) -> None:
    scen = yaml.safe_load(SCENARIO.read_text())
    wind = scen["generation"]["technologies"]["wind"]
    solar = scen["generation"]["technologies"]["solar"]
    cf = wind["capacity_factor"] * 1.05
    project_cf = (
        wind["capacity_mw"] * cf + solar["capacity_mw"] * solar["capacity_factor"]
    ) / scen["project"]["capacity_mw"]
    higher_cf = _kpis(
        {
            "generation.technologies.wind.capacity_factor": cf,
            "project.capacity_factor": project_cf,
        }
    )
    assert higher_cf["project_irr"] > base["project_irr"]
    lower_tariff = _kpis({"tariff.lkr_per_kwh": scen["tariff"]["lkr_per_kwh"] * 0.9})
    assert lower_tariff["project_irr"] < base["project_irr"]
