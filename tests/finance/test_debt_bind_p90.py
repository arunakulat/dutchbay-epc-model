"""The bankable P90 (downside) case can BIND debt sizing — gap #5.

Best practice sizes to min(P50-DSCR, P90-DSCR). Previously the dual-DSCR P90/P99
capacity was computed into lender-pack metadata but never resized the gearing (only
the P50 solve drove it), and the report-only downside used a flat 0.80 CFADS proxy
instead of the real bankable P90 AEP. This adds an opt-in `Financing_Terms.bind_downside`
(default off) that solves a second gearing against P90 CFADS (rescaled by the real
P90/P50 AEP ratio) at `target_dscr_p90` and applies min(P50, P90). Default-off preserves
canonical economics exactly.
"""

from __future__ import annotations

import copy
import warnings
from pathlib import Path

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

warnings.filterwarnings("ignore")
REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _run(**fin_overrides):
    cfg = dict(load_scenario_config(LENDER))
    cfg["Financing_Terms"] = {**cfg["Financing_Terms"], **fin_overrides}
    r = run_v14_pipeline(config=cfg)
    return r["kpis"], (r.get("debt_result") or {}).get("dual_dscr") or {}


def test_default_off_preserves_canonical() -> None:
    kpis, d = _run()  # no bind_downside -> default off
    # Canonical after the M3e degradation re-baseline (0.005 -> 0.5, 0.5%/yr aging):
    # projIRR 5.05%, minDSCR 1.30. The round-5 interest-tax-shield fix lifts equity IRR
    # -0.82% -> +2.42% (the levered equity path now bears levered tax); project IRR unchanged.
    assert kpis["project_irr"] == pytest.approx(0.0505, abs=0.003)
    assert kpis["equity_irr"] == pytest.approx(0.0242, abs=0.003)
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
    # P50 is the sole driver; the detail uses the legacy flat-factor downside.
    assert d["binding_production_case"] == "P50"
    assert d["downside_source"] == "flat_factor"
    assert d["downside_ratio"] == pytest.approx(0.80, abs=1e-6)
    assert "solved_gearing_p90" not in d
    assert d["solved_gearing_p50"] == pytest.approx(0.628, abs=0.01)


def test_p90_binds_when_floor_is_high() -> None:
    kpis, d = _run(bind_downside=True, target_dscr_p90=1.20)
    assert d["binding_production_case"] == "P90"
    assert d["solved_gearing_p90"] < d["solved_gearing_p50"]  # downside deleverages
    assert d["solved_gearing"] == pytest.approx(d["solved_gearing_p90"], abs=1e-6)
    # the real bankable P90/P50 AEP ratio (412.7/473.8 = 0.871), NOT the flat 0.80
    assert d["downside_source"] == "p90_aep"
    assert d["downside_ratio"] == pytest.approx(412.7 / 473.8, abs=0.001)
    # the base-case DSCR floor still holds (the structure is only ever MORE conservative)
    assert kpis["min_dscr"] >= 1.30 - 0.02


def test_low_p90_floor_keeps_p50_binding() -> None:
    # At a 1.00 P90 floor the canonical clears the downside, so P50 still binds and
    # gearing is unchanged from the default solve.
    _, d_off = _run()
    _, d_on = _run(bind_downside=True, target_dscr_p90=1.00)
    assert d_on["binding_production_case"] == "P50"
    assert d_on["solved_gearing"] == pytest.approx(d_off["solved_gearing"], abs=1e-6)


def test_explicit_downside_factor_override() -> None:
    _, d = _run(bind_downside=True, target_dscr_p90=1.20, downside_cfads_factor=0.70)
    assert d["downside_source"] == "explicit_factor"
    assert d["downside_ratio"] == pytest.approx(0.70, abs=1e-6)
