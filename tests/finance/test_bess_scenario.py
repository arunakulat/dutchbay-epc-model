"""Integration tests for BESS capacity-charge revenue in the v14 cashflow.

Pins: (1) the standalone CEB BESS scenario runs and books a flat capacity charge with
zero generation revenue; (2) a BESS folded onto the hybrid is additive and lifts the
project IRR; (3) a scenario with no ``type: bess`` block carries exactly zero BESS
revenue (byte-identical wind/solar behaviour). RUN+SHAPE is pinned, not the illustrative
vintage economics (the capacity charge rate is a placeholder bid value).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from finance.bess_revenue import resolve_bess_specs
from finance.cashflow_v14 import build_annual_rows, build_annual_rows_efficient
from finance.cashflow_v14_production import resolve_tech_generation_specs

_REPO = Path(__file__).resolve().parents[2]
_CEB = _REPO / "scenarios" / "ceb_bess_10mw_capacity_charge.yaml"
_NIGHTPEAK = _REPO / "scenarios" / "ceb_solar_bess_nightpeak_10mw.yaml"
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


@pytest.mark.skipif(not _NIGHTPEAK.exists(), reason="night-peak scenario not present")
def test_energy_tariff_scenario_books_night_peak_revenue():
    out = evaluate_with_overrides(
        raw_config=load_scenario_config(_NIGHTPEAK),
        overrides={},
        return_full_result=True,
    )
    rows = out["annual_rows"]
    assert len(rows) == 10  # 10-year night-peak contract term
    expected = (
        40 * 1000 * 365 * 0.90 * 1.0 * 45.80
    )  # energy_mwh×1000×cycles×RTE×avail×tariff
    for row in rows:
        assert row["bess_revenue_lkr"] == pytest.approx(expected)
        assert row["generation_revenue_lkr"] == pytest.approx(0.0)  # BESS-incremental
    assert (
        out["kpis"]["project_irr"] > 0
    )  # the 45.80 LKR/kWh night-peak tariff is lucrative


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
def test_bess_revenue_without_capex_is_rejected_on_the_hybrid():
    """BESS-3: a type:bess block booking revenue with NO capex_usd must FAIL LOUD.

    The prior test asserted that folding such a battery onto the hybrid *lifted* project
    IRR — i.e. a ~$25M asset booked as pure free revenue (the cost-side twin of the
    CF x tariff fallacy). The reconciliation guard now rejects it.
    """
    cfg = load_scenario_config(_HYBRID)
    bess_no_capex = {
        "type": "bess",
        "power_mw": 50.0,
        "energy_mwh": 200.0,
        "revenue": {
            "model": "capacity_charge",
            "capacity_charge_lkr_per_mw_month": 5_000_000,
            "contract_years": 15,
        },
    }
    # The finance guard raises ValueError; the pipeline wraps it in PipelineValidationError.
    with pytest.raises(Exception, match="capex"):
        evaluate_with_overrides(
            raw_config=cfg,
            overrides={"generation.technologies.bess_1": bess_no_capex},
            return_full_result=True,
        )


@pytest.mark.skipif(not _HYBRID.exists(), reason="hybrid scenario not present")
def test_bess_with_capex_is_additive_and_financed_on_the_hybrid():
    """A BESS folded onto the hybrid books its capacity charge AND finances its capex:
    revenue is additive, and per-tech capex_usd must roll up to capex.usd_total so the
    battery's cost is actually financed (BESS-3), not free."""
    cfg = load_scenario_config(_HYBRID)
    bess_capex = 25_000_000  # 200 MWh x ~$125/kWh turnkey
    out = evaluate_with_overrides(
        raw_config=cfg,
        overrides={
            "generation.technologies.bess_1": {
                "type": "bess",
                "power_mw": 50.0,
                "energy_mwh": 200.0,
                "capex_usd": bess_capex,
                "revenue": {
                    "model": "capacity_charge",
                    "capacity_charge_lkr_per_mw_month": 5_000_000,
                    "contract_years": 15,
                },
            },
            # The financed total MUST grow by the BESS capex: wind 159.6M + solar 40M
            # (== the hybrid's base usd_total 199.6M) + BESS 25M.
            "capex.usd_total": 199_600_000 + bess_capex,
        },
        return_full_result=True,
    )
    # Capacity charge is booked additively on top of generation revenue ...
    assert out["annual_rows"][0]["bess_revenue_lkr"] == pytest.approx(
        5_000_000 * 50 * 12
    )
    assert out["annual_rows"][0]["generation_revenue_lkr"] > 0
    # ... and the run reconciles with the BESS capex financed, so project IRR reflects
    # real economics (a finite number), not a free-revenue uplift.
    assert math.isfinite(out["kpis"]["project_irr"])


def test_type_bess_is_not_double_counted_as_generation():
    """`type` is authoritative: a (mis-keyed) BESS block carrying a stray capacity_factor
    is excluded from generation (no tariff revenue) and earns only its capacity charge —
    so it is never double-counted (generation tariff AND capacity charge)."""
    cfg = {
        "project": {"capacity_mw": 100.0, "capacity_factor": 0.34},
        "generation": {
            "technologies": {
                "wind": {"capacity_mw": 100.0, "capacity_factor": 0.34},
                "bess": {
                    "type": "bess",
                    "power_mw": 50.0,
                    "capacity_mw": 50.0,
                    "capacity_factor": 0.20,  # stray generation keys
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1_000_000,
                    },
                },
            }
        },
    }
    params = {"degradation": 0.0, "capacity_mw": 100.0, "capacity_factor": 0.34}
    gen_specs = resolve_tech_generation_specs(cfg, params)
    # only wind is a generation tech; the type: bess block is excluded (reconciles, and
    # had it been included the per-tech sum would breach the ±1% reconciliation).
    assert [s["technology"] for s in gen_specs] == ["wind"]
    # ...and the same block is resolved as a BESS earning the capacity charge.
    bess_specs = resolve_bess_specs(cfg)
    assert [s["technology"] for s in bess_specs] == ["bess"]


@pytest.mark.skipif(not _CEB.exists(), reason="CEB BESS scenario not present")
def test_both_cashflow_builders_agree_on_bess_revenue():
    """The BESS revenue is mirrored into BOTH builders (calculate_single_year_cfads and
    build_annual_rows_efficient). Pin that they stay identical on a scenario with a
    NON-ZERO capacity charge — a one-sided edit to either builder's BESS branch then
    fails the suite (the canonical equivalence test runs only on a BESS-free scenario).
    """
    cfg = load_scenario_config(_CEB)
    rows = build_annual_rows(cfg)
    eff = build_annual_rows_efficient(cfg)
    assert len(rows) == len(eff)
    for base_row, eff_row in zip(rows, eff):
        assert set(base_row.keys()) == set(eff_row.keys())
        for key in base_row:
            assert math.isclose(
                base_row[key], eff_row[key], rel_tol=1e-9, abs_tol=1e-6
            ), f"mismatch on {key}"
    # guard the guard: the BESS branch is actually exercised (non-zero capacity charge)
    assert rows[0]["bess_revenue_lkr"] > 0


# ── Augmentation + degradation through the cashflow (#470 BESS-1a/1b) ────────────


def _ceb_with_degradation():
    """The CEB capacity-charge scenario with MDSC fade + a year-10 augmentation injected.

    Mutates a freshly-loaded config (does NOT touch the committed scenario file — the
    KPI-moving opt-in re-pin of the committed scenarios is a separate, held dolphin).
    """
    cfg = load_scenario_config(_CEB)
    for block in cfg["generation"]["technologies"].values():
        if block.get("type") == "bess":
            block["revenue"]["mdsc_fade_pct_annual"] = 0.011
            block["revenue"]["augmentation_schedule"] = [
                {"year": 10, "capex_usd": 5_000_000}
            ]
    return cfg


def test_augmentation_drags_cfads_and_fade_curve_through_the_cashflow():
    out = evaluate_with_overrides(
        raw_config=_ceb_with_degradation(), overrides={}, return_full_result=True
    )
    rows = out["annual_rows"]
    # Fade BEFORE the augmentation: operating year 9 (index 8) revenue is below year 1.
    assert rows[8]["bess_revenue_lkr"] < rows[0]["bess_revenue_lkr"]
    # Augmentation capex lands in operating year 10 (index 9) and nowhere adjacent.
    assert rows[9]["bess_augmentation_capex_lkr"] > 0
    assert rows[8]["bess_augmentation_capex_lkr"] == 0
    assert rows[10]["bess_augmentation_capex_lkr"] == 0
    # The top-up RESTORES capacity: year-10 revenue jumps back above the faded year-9.
    assert rows[9]["bess_revenue_lkr"] > rows[8]["bess_revenue_lkr"]
    # ...and the capex DRAGS that year's CFADS below its post-tax level.
    assert rows[9]["cfads_final_lkr"] < rows[9]["posttax_cfads_lkr"]


def test_both_builders_agree_with_augmentation():
    cfg = _ceb_with_degradation()
    rows = build_annual_rows(cfg)
    eff = build_annual_rows_efficient(cfg)
    for base_row, eff_row in zip(rows, eff):
        assert base_row["cfads_final_lkr"] == pytest.approx(eff_row["cfads_final_lkr"])
        assert base_row["bess_augmentation_capex_lkr"] == pytest.approx(
            eff_row["bess_augmentation_capex_lkr"]
        )
