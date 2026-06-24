"""Integration tests for BESS capacity-charge revenue in the v14 cashflow.

Pins: (1) the standalone CEB BESS scenario runs and books a flat capacity charge with
zero generation revenue; (2) a BESS folded onto the hybrid is additive and lifts the
project IRR; (3) a scenario with no ``type: bess`` block carries exactly zero BESS
revenue (byte-identical wind/solar behaviour). RUN+SHAPE is pinned, not the illustrative
vintage economics (the capacity charge rate is a placeholder bid value).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.bess_revenue import resolve_bess_specs
from finance.cashflow_v14_production import resolve_tech_generation_specs

_REPO = Path(__file__).resolve().parents[2]
_CEB = _REPO / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"
_HYBRID = _REPO / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"
_LENDER = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.mark.skipif(not _CEB.exists(), reason="CEB BESS scenario not present")
def test_standalone_bess_books_flat_capacity_charge():
    out = evaluate_with_overrides(
        raw_config=load_scenario_config(_CEB), overrides={}, return_full_result=True
    )
    rows = out["annual_rows"]
    assert len(rows) == 15  # 15-year tender term
    expected = 2_500_000 * 10 * 12  # R x power_mw x 12 (from the scenario)
    for row in rows:
        assert row["bess_revenue_lkr"] == pytest.approx(expected)
        assert row["generation_revenue_lkr"] == pytest.approx(0.0)  # storage-only
        assert row["revenue_lkr"] == pytest.approx(expected)
    kpis = out["kpis"]
    assert kpis["min_dscr"] > 0
    assert isinstance(kpis["project_irr"], float)  # runs end-to-end (debt/IRR resolve)


@pytest.mark.skipif(not _LENDER.exists(), reason="lendercase scenario not present")
def test_no_bess_block_means_zero_bess_revenue():
    """A wind-only scenario carries exactly zero BESS revenue on every row — the BESS
    path is additive and inert when absent (byte-identical economics)."""
    out = evaluate_with_overrides(
        raw_config=load_scenario_config(_LENDER), overrides={}, return_full_result=True
    )
    for row in out["annual_rows"]:
        assert row["bess_revenue_lkr"] == 0.0
        assert row["revenue_lkr"] == pytest.approx(row["generation_revenue_lkr"])


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_bess_is_additive_on_the_hybrid():
    cfg = load_scenario_config(_HYBRID)
    base = evaluate_with_overrides(raw_config=cfg, overrides={})
    bess = {
        "type": "bess",
        "power_mw": 50.0,
        "energy_mwh": 200.0,
        "revenue": {
            "model": "capacity_charge",
            "capacity_charge_lkr_per_mw_month": 5_000_000,
            "contract_years": 15,
        },
    }
    out = evaluate_with_overrides(
        raw_config=cfg,
        overrides={"generation.technologies.bess_1": bess},
        return_full_result=True,
    )
    # the capacity charge is added on top of generation revenue and lifts project IRR
    assert out["annual_rows"][0]["bess_revenue_lkr"] == pytest.approx(5_000_000 * 50 * 12)
    assert out["annual_rows"][0]["generation_revenue_lkr"] > 0
    assert out["kpis"]["project_irr"] > base["project_irr"]


def test_type_bess_is_not_double_counted_as_generation():
    """`type` is authoritative: a (mis-keyed) BESS block carrying a stray capacity_factor
    is excluded from generation (no tariff revenue) and earns only its capacity charge —
    so it is never double-counted (generation tariff AND capacity charge)."""
    cfg = {
        "project": {"capacity_mw": 100.0, "capacity_factor": 0.34},
        "generation": {"technologies": {
            "wind": {"capacity_mw": 100.0, "capacity_factor": 0.34},
            "bess": {
                "type": "bess", "power_mw": 50.0,
                "capacity_mw": 50.0, "capacity_factor": 0.20,  # stray generation keys
                "revenue": {"model": "capacity_charge",
                            "capacity_charge_lkr_per_mw_month": 1_000_000},
            },
        }},
    }
    params = {"degradation": 0.0, "capacity_mw": 100.0, "capacity_factor": 0.34}
    gen_specs = resolve_tech_generation_specs(cfg, params)
    # only wind is a generation tech; the type: bess block is excluded (reconciles, and
    # had it been included the per-tech sum would breach the ±1% reconciliation).
    assert [s["technology"] for s in gen_specs] == ["wind"]
    # ...and the same block is resolved as a BESS earning the capacity charge.
    bess_specs = resolve_bess_specs(cfg)
    assert [s["technology"] for s in bess_specs] == ["bess"]
