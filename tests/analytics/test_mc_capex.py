"""Probabilistic CAPEX — Monte Carlo over the cost distribution -> P-level economics.

Samples total CAPEX ~ Normal(base, sigma) and runs the v14 pipeline per draw, so the
dual-DSCR sizer re-solves at each cost. sigma comes from the QRA / uncertainty_pct / an
override. Straight percentiles (p10/p50/p90); for CAPEX p90 = high cost, for IRR/NPV/DSCR
p10 = downside.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.cost.mc_capex import resolve_capex_sigma_pct, run_capex_mc

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_sigma_resolution_order() -> None:
    # explicit override wins
    assert resolve_capex_sigma_pct({}, override=15.0) == 15.0
    # QRA uncertainty next
    assert (
        resolve_capex_sigma_pct(
            {"capex": {"contingency": {"base_cost_uncertainty_pct": 12.0}}}
        )
        == 12.0
    )
    # then capex.uncertainty_pct
    assert resolve_capex_sigma_pct({"capex": {"uncertainty_pct": 8.0}}) == 8.0


def test_sigma_resolution_raises_when_absent() -> None:
    with pytest.raises(ValueError, match="CAPEX uncertainty"):
        resolve_capex_sigma_pct({"capex": {"usd_total": 1.0}})


def test_capex_mc_distribution_is_monotonic_and_sound() -> None:
    res = run_capex_mc(LENDER, n_samples=48, sigma_pct=12.0, seed=7)

    assert res.sigma_pct == 12.0
    assert res.base_capex_usd == pytest.approx(159_600_000, rel=0.001)

    # CAPEX percentiles ordered; base sits inside the p10-p90 band
    assert res.capex_usd["p10"] < res.capex_usd["p50"] < res.capex_usd["p90"]
    assert res.capex_usd["p10"] < res.base_capex_usd < res.capex_usd["p90"]

    # KPIs anti-correlate with cost -> p10 (downside) below p50 below p90
    for kpi in (res.project_irr, res.equity_irr, res.project_npv_usd):
        assert kpi["p10"] < kpi["p50"] < kpi["p90"]

    # the median is near the deterministic base-case project IRR (~3.0% after the
    # 5.9% FX-drift re-baseline; was ~5.7% before the data-derived BIS depreciation)
    assert res.project_irr["p50"] == pytest.approx(0.0301, abs=0.02)

    # debt is DSCR-sculpted, so min DSCR holds at the covenant floor across the cost range
    for level in ("p10", "p50", "p90"):
        assert res.min_dscr[level] == pytest.approx(1.30, abs=0.02)


def test_capex_mc_is_reproducible() -> None:
    a = run_capex_mc(LENDER, n_samples=24, sigma_pct=10.0, seed=42)
    b = run_capex_mc(LENDER, n_samples=24, sigma_pct=10.0, seed=42)
    assert a.capex_usd == b.capex_usd  # same seed -> identical draws
    assert a.project_irr == b.project_irr
