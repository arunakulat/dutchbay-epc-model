"""Hybrid project.capacity_factor MC coupling (capability/provenance audit HIGH #2).

In a multi-tech scenario the cashflow drives production from per-tech capacity factors and
enforces a ±1% reconciliation (per-tech Σ cap·cf == project cap·cf). So sweeping the headline
project.capacity_factor ALONE raised that guard on every shocked trial -> toy fallback -> a
fictitious combined-plant CF risk band. The MC engine now COUPLES the sweep: it scales every
per-tech CF by the same shock ratio, keeping reconciliation valid so the driver actually moves
combined production. Wind-only scenarios (no generation.technologies) are unaffected.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from analytics.mc.engine import MonteCarloEngine

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HYBRID = _REPO_ROOT / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"
_WIND_ONLY = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text())


def test_coupling_inactive_for_wind_only() -> None:
    # Canonical lender case has no generation.technologies -> project.capacity_factor drives
    # production directly; no coupling, byte-identical behaviour.
    eng = MonteCarloEngine(_load(_WIND_ONLY), seed=1)
    assert eng._cf_coupling is None


def test_coupling_active_for_hybrid() -> None:
    eng = MonteCarloEngine(_load(_HYBRID), seed=1)
    assert eng._cf_coupling is not None
    base_proj_cf, base_tech_cfs = eng._cf_coupling
    assert base_proj_cf > 0
    assert "wind" in base_tech_cfs and "solar" in base_tech_cfs


def test_apply_cf_coupling_scales_per_tech_by_ratio() -> None:
    eng = MonteCarloEngine(_load(_HYBRID), seed=1)
    base_proj_cf, base_tech_cfs = eng._cf_coupling  # type: ignore[misc]
    shocked = round(base_proj_cf * 0.90, 6)
    overrides = {"project": {"capacity_factor": shocked}}
    out = eng._apply_cf_coupling(overrides)
    techs = out["generation"]["technologies"]
    ratio = shocked / base_proj_cf
    for tech, base_cf in base_tech_cfs.items():
        assert techs[tech]["capacity_factor"] == pytest.approx(base_cf * ratio)


def test_hybrid_mc_runs_without_toy_fallback_and_cf_moves_irr() -> None:
    logging.disable(logging.WARNING)
    try:
        res = MonteCarloEngine(_load(_HYBRID), seed=123).run(n_trials=48)
        # Before the coupling, CF-shocked trials raised the reconciliation guard -> toy
        # fallback. Now every trial evaluates for real.
        assert res.failed_iterations == 0
        assert res.metadata.get("degenerate_sweep") is False
        irr = [float(x) for x in (res.trials or {}).get("project_irr", []) if x is not None]
        assert len(irr) == 48
        assert max(irr) - min(irr) > 1e-3  # CF (+ the other drivers) genuinely move the IRR
    finally:
        logging.disable(logging.NOTSET)
