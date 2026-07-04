"""AACE estimate class + accuracy band + LandBOSSE BoP split — gap #7.

Lifts the AACE estimate class out of the QRA-only path into a first-class, config-first
attribute with an expected-accuracy band, and uses the band as a sanity-floor for the
probabilistic-CAPEX 1-sigma. The canonical CAPEX is unchanged (the BoP split sums to the
prior total), so economics are unaffected.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from analytics.cost.estimate_class import (
    accuracy_band,
    default_estimate_class,
    resolve_accuracy_band,
    resolve_estimate_class,
)

warnings.filterwarnings("ignore")
REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_default_class_is_config_sourced() -> None:
    assert (
        default_estimate_class() == 3
    )  # config/defaults.yaml cost_reference.estimate_class


def test_scenario_override_then_default() -> None:
    assert resolve_estimate_class({"capex": {"estimate_class": 2}}) == 2
    assert resolve_estimate_class({"capex": {}}) == 3  # falls back to default


def test_accuracy_band_and_implied_sigma() -> None:
    b = accuracy_band(3)
    assert (b.low_pct, b.high_pct) == (-15.0, 22.0)
    # implied 1-sigma = (|low| + high) / 2 / 2  (band ~= +/-2 sigma)
    assert b.implied_sigma_pct == pytest.approx((15.0 + 22.0) / 2.0 / 2.0)  # 9.25
    # tighter class -> tighter band
    assert accuracy_band(1).implied_sigma_pct < accuracy_band(5).implied_sigma_pct


def test_canonical_is_class_3() -> None:
    from analytics.scenario_loader import load_scenario_config

    assert resolve_estimate_class(load_scenario_config(LENDER)) == 3
    assert resolve_accuracy_band(load_scenario_config(LENDER)).estimate_class == 3


def test_mc_sigma_floored_to_class_band() -> None:
    from analytics.cost.mc_capex import run_capex_mc

    # 5% is tighter than Class 3 implies (9.25%) -> floored
    floored = run_capex_mc(LENDER, n_samples=8, sigma_pct=5.0, seed=1)
    assert floored.sigma_pct == pytest.approx(9.25, abs=0.01)
    # 12% (the QRA value) exceeds the class floor -> unchanged
    free = run_capex_mc(LENDER, n_samples=8, sigma_pct=12.0, seed=1)
    assert free.sigma_pct == pytest.approx(12.0)


def test_cost_block_surfaces_estimate_class() -> None:
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert resp.cost.estimate_class == 3
    assert resp.cost.accuracy_low_pct == -15.0
    assert resp.cost.accuracy_high_pct == 22.0
    # canonical economics unchanged by the WBS split (projIRR ~2.75% after the
    # 5.9% FX-drift re-baseline; the WBS split itself does not move it)
    assert resp.cost.capex_total_usd == pytest.approx(159_600_000, rel=1e-4)
    assert resp.kpis.project_irr == pytest.approx(0.0203, abs=0.003)
