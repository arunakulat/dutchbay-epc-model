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
from tests._canon import (
    LENDER_EQUITY_IRR,
    LENDER_MIN_DSCR,
    LENDER_MIN_DSCR_PERIOD,
    LENDER_PROJECT_IRR,
    LENDER_PROJECT_NPV,
    LENDER_PROJECT_NPV_PRUDENTIAL,
    LENDER_PRUDENTIAL_RATE_USED,
    LENDER_TOTAL_CFADS_USD,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_HYBRID = {
    "generation": {
        "technologies": {
            # degradation_pct is a PERCENT (0.6 -> 0.6%/yr), matching the single-tech
            # convention (_build_cashflow_params divides by 100). Resolved to 0.006 dec.
            "wind": {
                "capacity_mw": 150,
                "capacity_factor": 0.339,
                "degradation_pct": 0.6,
            },
            "solar": {
                "capacity_mw": 50,
                "capacity_factor": 0.20,
                "degradation_pct": 0.4,
            },
        }
    }
}
# project headline reconciles: (150*0.339 + 50*0.20)/200 = 0.304250
_PROJECT_PARAMS = {
    "capacity_mw": 200,
    "capacity_factor": 0.304250,
    "degradation": 0.005,
}


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
    cfg = {
        "generation": {
            "technologies": {"wind": {"capacity_mw": 200, "capacity_factor": 0.304250}}
        }
    }
    specs = resolve_tech_generation_specs(cfg, _PROJECT_PARAMS)
    assert specs is not None and specs[0]["degradation"] == 0.005  # project fallback


def test_consistency_raises_on_mismatch() -> None:
    # per-tech sum 50.85 vs project 200*0.30 = 60 -> > 1% mismatch -> fail loud.
    cfg = {
        "generation": {
            "technologies": {"wind": {"capacity_mw": 150, "capacity_factor": 0.339}}
        }
    }
    with pytest.raises(ValueError, match="reconcile"):
        resolve_tech_generation_specs(
            cfg, {"capacity_mw": 200, "capacity_factor": 0.30, "degradation": 0.005}
        )


def test_non_dict_block_and_all_skipped_return_none() -> None:
    # A malformed (non-dict) tech is skipped; a storage-only block has no
    # generation, so the whole resolution returns None (single-tech path).
    cfg = {
        "generation": {"technologies": {"bad": "not-a-dict", "bess": {"power_mw": 50}}}
    }
    assert resolve_tech_generation_specs(cfg, _PROJECT_PARAMS) is None


def test_storage_without_capacity_factor_skipped() -> None:
    cfg = {
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 200, "capacity_factor": 0.304250},
                "bess": {
                    "capacity_mw": 50,
                    "power_mw": 50,
                },  # no capacity_factor/aep_gwh
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
    cfg = {
        "generation": {
            "technologies": {"wind": {"capacity_mw": 200, "capacity_factor": 0.3}}
        }
    }
    with pytest.raises(ValueError, match="non-positive"):
        resolve_tech_generation_specs(
            cfg, {"capacity_mw": 0.0, "capacity_factor": 0.3, "degradation": 0.005}
        )


# --------------------------------------------------------------------------- #
# calculate_net_production_for_year
# --------------------------------------------------------------------------- #
def test_single_tech_path_is_identical() -> None:
    params = {**_PROJECT_PARAMS, "grid_loss_pct": 0.02}  # no tech_generation_specs
    got = calculate_net_production_for_year(params, 5)
    expected = _calculate_net_production(
        200, 0.304250, 0.005, 0.02, 5, curtailment_pct=0.0
    )
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
    single = {
        "grid_loss_pct": 0.0,
        "capacity_mw": 200,
        "capacity_factor": 0.304250,
        "degradation": 0.005,
    }

    _, n0_multi = calculate_net_production_for_year(multi, 0)
    _, n0_single = calculate_net_production_for_year(single, 0)
    assert n0_multi == pytest.approx(n0_single)  # reconciles at year 0

    _, n10_multi = calculate_net_production_for_year(multi, 10)
    _, n10_single = calculate_net_production_for_year(single, 10)
    assert n10_multi != pytest.approx(
        n10_single
    )  # per-tech degradation genuinely matters


# --------------------------------------------------------------------------- #
# Unit consistency (degradation): the two paths must be interchangeable.
# --------------------------------------------------------------------------- #
_LIFE_PROJECT = {
    "capacity_mw": 200.0,
    "capacity_factor": 0.304250,
    "degradation": 0.005,  # decimal, as _build_cashflow_params would emit (0.5%/yr)
    "grid_loss_pct": 0.02,
    "curtailment_pct": 0.0,
}


def test_wind_only_block_percent_degradation_matches_single_tech_full_life() -> None:
    # A single wind tech equal to the project headline, with degradation_pct as a
    # PERCENT (0.5 == the 0.005 decimal the single-tech path uses), must reproduce
    # the legacy single-tech generation EVERY year — not just year 1.
    config = {
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": 200.0,
                    "capacity_factor": 0.304250,
                    "degradation_pct": 0.5,
                }
            }
        }
    }
    specs = resolve_tech_generation_specs(config, _LIFE_PROJECT)
    assert specs is not None and specs[0]["degradation"] == pytest.approx(0.005)
    multi = {**_LIFE_PROJECT, "tech_generation_specs": specs}
    single = {**_LIFE_PROJECT, "tech_generation_specs": None}
    for year in range(20):
        assert calculate_net_production_for_year(
            multi, year
        ) == calculate_net_production_for_year(single, year)


def test_wind_only_block_no_degradation_falls_back_full_life() -> None:
    # No per-tech degradation -> falls back to the (already-decimal) project value;
    # byte-identical to single-tech across the full project life.
    config = {
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 200.0, "capacity_factor": 0.304250}
            }
        }
    }
    specs = resolve_tech_generation_specs(config, _LIFE_PROJECT)
    multi = {**_LIFE_PROJECT, "tech_generation_specs": specs}
    single = {**_LIFE_PROJECT, "tech_generation_specs": None}
    for year in range(20):
        assert calculate_net_production_for_year(
            multi, year
        ) == calculate_net_production_for_year(single, year)


def test_negative_per_tech_degradation_raises() -> None:
    config = {
        "generation": {
            "technologies": {
                "wind": {
                    "capacity_mw": 200,
                    "capacity_factor": 0.30,
                    "degradation_pct": -0.5,
                }
            }
        }
    }
    with pytest.raises(ValueError, match="degradation_pct"):
        resolve_tech_generation_specs(
            config, {"capacity_mw": 200, "capacity_factor": 0.30, "degradation": 0.005}
        )


# --------------------------------------------------------------------------- #
# Byte-identical regression: the canonical wind-only economics must not move.
# Re-baselined 2026-06-28 for the 2.0% pre-construction P50 over-prediction haircut
# on the DutchBay wind resource (net AEP 473.8 -> 464.3 GWh, builder emits 464.36;
# CF 0.339 -> 0.332): the smaller energy yield drops USD revenue across the 20yr
# life. Project IRR 2.75% -> 2.50%, equity IRR -0.46% -> -1.00%, NPV -$53.29M ->
# -$56.10M, CFADS $203.46M -> $199.10M. minDSCR unchanged (the dual-DSCR sculpt
# re-pins it at the 1.30 covenant target). Prior history: re-baselined 2026-06-28
# for the 5.9% FX-drift re-baseline (fx.annual_depr 0.03 -> 0.0589, data-derived BIS
# 2005-2026 LKR depreciation: 5.05% -> 2.75%); 2026-06-23 (M3e) for the degradation
# correction (5.43% -> 5.05%, CFADS $268.07M -> $257.10M).
# --------------------------------------------------------------------------- #
def test_canonical_lendercase_economics_unchanged() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    lender = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
    kpis = run_v14_pipeline(config=lender, validation_mode="strict")["kpis"]
    # Re-baselined by #738 (2026-07-05): import levies + indirect taxes ON at the
    # PRUDENT posture (taxes_indirect: PAL 5% + import-SSCL 2.5% PAID on the 0.69
    # imported share = $8.2593M duties capitalized into financed capex + the
    # depreciable base; capex VAT relieved via BOI s.17/bonded; 18% unrecoverable
    # VAT on O&M PAID) AND the revenue-SSCL statutory-exemption REVERSAL
    # (statutory.social_services_levy_pct 0.025 -> 0.0 — IPP-to-CEB supply is
    # SSCL-exempt; on its own that RAISES the canon, the levies dominate). Net:
    # projIRR 2.03% -> 1.46%, eqIRR -4.99% -> -5.84%, NPV -70.95M -> -79.27M,
    # CFADS 191.22M -> 191.11M, gross capex 159.6M -> 167.86M, gearing 0.4275 ->
    # 0.41 (debt 68.23M -> 68.82M on the grossed base). Prior: #737 credit-support
    # fees (2.68% -> 2.03%); PR B (group-C #3) UIP LKR debt rate re-baseline.
    assert kpis["project_irr"] == pytest.approx(LENDER_PROJECT_IRR, abs=1e-9)
    assert kpis["equity_irr"] == pytest.approx(LENDER_EQUITY_IRR, abs=1e-9)
    assert kpis["project_npv"] == pytest.approx(LENDER_PROJECT_NPV, rel=1e-9)
    # #790 (user decision 2026-07-05): the headline min_dscr is the CONSERVATIVE
    # fold-corrected covenant minimum (bridge-corrected per-year table, fee-netted
    # per #737, levy-inclusive per #738) — the annual number covenants are tested
    # on. The per-period sculpt floor stays pinned as min_dscr_period (the sculpt
    # re-solves to hold 1.30 under the levies; the year-1 fold eases 1.2884 ->
    # 1.2857, still exactly 1 equity-lockup year).
    assert kpis["min_dscr"] == pytest.approx(LENDER_MIN_DSCR, abs=1e-9)
    assert kpis["min_dscr_period"] == pytest.approx(LENDER_MIN_DSCR_PERIOD, abs=1e-9)
    assert kpis["total_cfads_usd"] == pytest.approx(LENDER_TOTAL_CFADS_USD, rel=1e-9)
    # Prudential (downside) NPV: CFADS discounted at the haircut WACC (prudential_rate =
    # WACC + spread), below the base NPV. -76.44M -> -84.72M (#738 levies + higher WACC:
    # the de-levered stack carries more 12% equity).
    assert kpis["project_npv_prudential"] == pytest.approx(
        LENDER_PROJECT_NPV_PRUDENTIAL, rel=1e-9
    )
    assert kpis["prudential_rate_used"] == pytest.approx(
        LENDER_PRUDENTIAL_RATE_USED, abs=1e-9
    )
    assert (
        kpis["project_npv_prudential"] < kpis["project_npv"]
    )  # haircut rate -> lower NPV
