#!/usr/bin/env python
"""Tests for the capital_risk_layer_v14 facade (#33).

Covers the source-agnostic aggregator (VaR/CVaR, DSCR breach probability, AEP
exceedance) with synthetic distributions, and a small driver-MC smoke test that
wires evaluate_with_overrides → aggregation.

Context:
    Sprint 11 - Issue #33 (capital_risk_layer_v14 facade).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from analytics.capital_risk_layer_v14 import (
    CapitalRiskLayer,
    compute_capital_risk_layer,
    run_capital_risk_layer,
    run_driver_mc,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


@pytest.fixture
def synthetic() -> dict:
    rng = np.random.RandomState(0)
    return {
        "irr": rng.normal(0.08, 0.02, 2000),
        "npv": rng.normal(-3e6, 5e6, 2000),
        "dscr": rng.normal(1.30, 0.08, 2000),
        "aep": rng.normal(402.0, 30.0, 2000),
    }


def test_aggregator_returns_layer(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        equity_npv_samples=synthetic["npv"],
        aep_gwh_samples=synthetic["aep"],
        dscr_covenant=1.20,
    )
    assert isinstance(layer, CapitalRiskLayer)
    assert layer.n_samples == 2000
    assert layer.confidence == 0.95


def test_cvar_not_better_than_var(synthetic: dict) -> None:
    """CVaR (mean of the worst tail) must be <= VaR for returns."""
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"], min_dscr_samples=synthetic["dscr"]
    )
    vc = layer.equity_irr_var_cvar
    assert vc.cvar <= vc.var


def test_dscr_breach_probability(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        dscr_covenant=1.20,
    )
    # N(1.30, 0.08): P(DSCR < 1.20) ~ 0.106.
    assert 0.0 <= layer.dscr["prob_breach"] <= 1.0
    assert layer.dscr["prob_breach"] == pytest.approx(0.106, abs=0.04)
    assert layer.dscr["min"] < layer.dscr["p50"]


def test_aep_exceedance_ordering(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        aep_gwh_samples=synthetic["aep"],
    )
    assert layer.aep is not None
    assert layer.aep["p99"] < layer.aep["p90"] < layer.aep["p50"]


def test_npv_optional(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"], min_dscr_samples=synthetic["dscr"]
    )
    assert layer.equity_npv_var_cvar is None
    assert layer.aep is None


def test_too_few_samples_raises() -> None:
    with pytest.raises(ValueError, match="Need >="):
        compute_capital_risk_layer(
            equity_irr_samples=[0.08] * 5, min_dscr_samples=[1.3] * 5
        )


def test_driver_mc_shapes() -> None:
    mc = run_driver_mc(
        LENDER_CONFIG,
        drivers={"Financing_Terms.debt_ratio": {"mean": 0.625, "std": 0.02}},
        n_samples=25,
        seed=1,
    )
    assert set(mc) == {"equity_irr", "equity_npv", "min_dscr"}
    assert all(arr.shape == (25,) for arr in mc.values())


def test_run_capital_risk_layer_smoke() -> None:
    layer = run_capital_risk_layer(
        LENDER_CONFIG,
        drivers={"Financing_Terms.debt_ratio": {"mean": 0.625, "std": 0.02}},
        n_samples=25,
        seed=1,
    )
    assert layer.n_samples == 25
    assert 0.0 <= layer.dscr["prob_breach"] <= 1.0
    assert layer.equity_irr_var_cvar.var_label == "VaR(95%)"
