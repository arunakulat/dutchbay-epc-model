"""Tests for M3 true per-tech generation in the cashflow.

Covers the production seam (resolve_tech_generation_specs +
calculate_net_production_for_year) and pins the canonical wind-only economics
as a byte-identical regression (the multi-tech path must never perturb them).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finance.cashflow_v14_production import (
    _calculate_net_production,
    calculate_net_production_for_year,
    resolve_tech_generation_specs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_HYBRID = {
    "generation": {
        "technologies": {
            "wind": {"capacity_mw": 150, "capacity_factor": 0.339, "degradation_pct": 0.006},
            "solar": {"capacity_mw": 50, "capacity_factor": 0.20, "degradation_pct": 0.004},
        }
    }
}
# project headline reconciles: (150*0.339 + 50*0.20)/200 = 0.304250
_PROJECT_PARAMS = {"capacity_mw": 200, "capacity_factor": 0.304250, "degradation": 0.005}


# --------------------------------------------------------------------------- #
# resolve_tech_generation_specs
# --------------------------------------------------------------------------- #
def test_resolve_none_without_block() -> None:
    assert resolve_tech_generation_specs({}, _PROJECT_PARAMS) is None
    assert resolve_tech_generation_specs({"generation": {}}, _PROJECT_PARAMS) is None


def test_resolve_specs_with_per_tech_degradation() -> None:
    specs = resolve_tech_generation_specs(_HYBRID, _PROJECT_PARAMS)
    assert specs is not None
    by = {s["technology"]: s for s in specs}
    assert by["wind"]["degradation"] == 0.006
    assert by["solar"]["degradation"] == 0.004


def test_degradation_falls_back_to_project() -> None:
    cfg = {"generation": {"technologies": {"wind": {"capacity_mw": 200, "capacity_factor": 0.304250}}}}
    specs = resolve_tech_generation_specs(cfg, _PROJECT_PARAMS)
    assert specs is not None and specs[0]["degradation"] == 0.005  # project fallback


def test_consistency_raises_on_mismatch() -> None:
    # per-tech sum 50.85 vs project 200*0.30 = 60 -> > 1% mismatch -> fail loud.
    cfg = {"generation": {"technologies": {"wind": {"capacity_mw": 150, "capacity_factor": 0.339}}}}
    with pytest.raises(ValueError, match="reconcile"):
        resolve_tech_generation_specs(cfg, {"capacity_mw": 200, "capacity_factor": 0.30, "degradation": 0.005})


def test_non_dict_block_and_all_skipped_return_none() -> None:
    # A malformed (non-dict) tech is skipped; a storage-only block has no
    # generation, so the whole resolution returns None (single-tech path).
    cfg = {"generation": {"technologies": {"bad": "not-a-dict", "bess": {"power_mw": 50}}}}
    assert resolve_tech_generation_specs(cfg, _PROJECT_PARAMS) is None


def test_storage_without_capacity_factor_skipped() -> None:
    cfg = {
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 200, "capacity_factor": 0.304250},
                "bess": {"capacity_mw": 50, "power_mw": 50},  # no capacity_factor/aep_gwh
            }
        }
    }
    specs = resolve_tech_generation_specs(cfg, _PROJECT_PARAMS)
    assert {s["technology"] for s in specs} == {"wind"}  # type: ignore[union-attr]


def test_generation_tech_missing_finance_keys_raises() -> None:
    # A tech declaring aep_gwh (a generation key) but no capacity_mw/capacity_factor
    # must FAIL LOUD — it cannot be silently dropped from the cashflow (audit #1/#2).
    cfg = {
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 200, "capacity_factor": 0.304250},
                "solar": {"aep_gwh": 87.6, "capex_usd": 40_000_000},  # reporting-only
            }
        }
    }
    with pytest.raises(ValueError, match="missing capacity_mw"):
        resolve_tech_generation_specs(cfg, _PROJECT_PARAMS)


def test_capacity_factor_without_capacity_mw_raises() -> None:
    cfg = {"generation": {"technologies": {"solar": {"capacity_factor": 0.20}}}}
    with pytest.raises(ValueError, match="missing capacity_mw"):
        resolve_tech_generation_specs(cfg, _PROJECT_PARAMS)


def test_non_positive_headline_raises() -> None:
    # The reconciliation must not silently skip on a non-positive headline (audit #3).
    cfg = {"generation": {"technologies": {"wind": {"capacity_mw": 200, "capacity_factor": 0.3}}}}
    with pytest.raises(ValueError, match="non-positive"):
        resolve_tech_generation_specs(cfg, {"capacity_mw": 0.0, "capacity_factor": 0.3, "degradation": 0.005})


# --------------------------------------------------------------------------- #
# calculate_net_production_for_year
# --------------------------------------------------------------------------- #
def test_single_tech_path_is_identical() -> None:
    params = {**_PROJECT_PARAMS, "grid_loss_pct": 0.02}  # no tech_generation_specs
    got = calculate_net_production_for_year(params, 5)
    expected = _calculate_net_production(200, 0.304250, 0.005, 0.02, 5, curtailment_pct=0.0)
    assert got == expected


def test_multitech_is_sum_of_per_tech() -> None:
    specs = resolve_tech_generation_specs(_HYBRID, _PROJECT_PARAMS)
    params = {"grid_loss_pct": 0.02, "tech_generation_specs": specs}
    gross, net = calculate_net_production_for_year(params, 5)
    gw, nw = _calculate_net_production(150, 0.339, 0.006, 0.02, 5, curtailment_pct=0.0)
    gs, ns = _calculate_net_production(50, 0.20, 0.004, 0.02, 5, curtailment_pct=0.0)
    assert gross == pytest.approx(gw + gs)
    assert net == pytest.approx(nw + ns)


def test_per_tech_degradation_diverges_from_single_blend() -> None:
    # THE proof: year 0 reconciles (no degradation yet), year 10 diverges because
    # wind (0.6%/yr) and solar (0.4%/yr) decay differently than a single 0.5% blend.
    specs = resolve_tech_generation_specs(_HYBRID, _PROJECT_PARAMS)
    multi = {"grid_loss_pct": 0.0, "tech_generation_specs": specs}
    single = {"grid_loss_pct": 0.0, "capacity_mw": 200, "capacity_factor": 0.304250, "degradation": 0.005}

    _, n0_multi = calculate_net_production_for_year(multi, 0)
    _, n0_single = calculate_net_production_for_year(single, 0)
    assert n0_multi == pytest.approx(n0_single)  # reconciles at year 0

    _, n10_multi = calculate_net_production_for_year(multi, 10)
    _, n10_single = calculate_net_production_for_year(single, 10)
    assert n10_multi != pytest.approx(n10_single)  # per-tech degradation genuinely matters


# --------------------------------------------------------------------------- #
# Byte-identical regression: the canonical wind-only economics must not move.
# --------------------------------------------------------------------------- #
def test_canonical_lendercase_economics_unchanged() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    lender = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
    kpis = run_v14_pipeline(config=lender, validation_mode="strict")["kpis"]
    assert kpis["project_irr"] == pytest.approx(0.05433752727321384, abs=1e-9)
    assert kpis["equity_irr"] == pytest.approx(0.00025995068190565185, abs=1e-9)
    assert kpis["project_npv"] == pytest.approx(-31926643.350233816, rel=1e-9)
    assert kpis["min_dscr"] == pytest.approx(1.2999999999999998, abs=1e-9)
    assert kpis["total_cfads_usd"] == pytest.approx(268070016.03115833, rel=1e-9)
