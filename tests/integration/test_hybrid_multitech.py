"""End-to-end: a combined wind+solar plant runs through the finance engine and the
multi-tech layer reports the per-technology generation/CFADS split.

The plant is configured as one combined-output asset (combined nameplate × blended
P50 capacity factor), so the run's CFADS is the combined plant's; a
``generation.technologies`` block declares the wind/solar split, and the aggregator
allocates the run's CFADS across technologies in proportion to declared AEP.

This proves the multi-tech *reporting* capability runs end-to-end. True per-tech
project finance — separate solar CAPEX/OPEX/degradation flowing through the
cashflow — is a later step (the per-tech CFADS here is an indicative allocation).
"""

from __future__ import annotations

import pytest

from analytics.portfolio.generation_aggregator import build_multi_tech_from_run
from app.models.inputs import WindFarmInputs
from app.services.pipeline_service import run_finance_case

WIND_AEP_GWH = 473.8
SOLAR_AEP_GWH = 87.6
COMBINED_MW = 200.0
HOURS_PER_YEAR = 8760
COMBINED_CF = (WIND_AEP_GWH + SOLAR_AEP_GWH) * 1e6 / (COMBINED_MW * 1000 * HOURS_PER_YEAR)


def _hybrid_scenario() -> dict:
    inputs = WindFarmInputs(
        site_name="DutchBay Hybrid",
        capacity_mw=COMBINED_MW,
        capacity_factor=COMBINED_CF,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=230_000_000,  # wind 195M + solar 35M (illustrative)
        opex_annual_usd=6_500_000,
        fx_start_lkr_per_usd=333.79,
    )
    scenario = inputs.to_scenario_config()
    scenario["generation"] = {
        "technologies": {
            "wind": {"aep_gwh": WIND_AEP_GWH, "capex_usd": 195_000_000},
            "solar": {"aep_gwh": SOLAR_AEP_GWH, "capex_usd": 35_000_000},
        }
    }
    return scenario


def test_hybrid_runs_through_engine_and_reports_per_tech() -> None:
    scenario = _hybrid_scenario()

    # 1. It RUNS: the combined plant flows through the real finance engine.
    result = run_finance_case(scenario)
    assert result["status"] == "success"
    kpis = result["kpis"]
    assert "project_irr" in kpis and "min_dscr" in kpis

    # 2. It REPORTS: the multi-tech layer surfaces a wind + solar split.
    gen, breakdown = build_multi_tech_from_run(kpis, scenario)
    assert gen is not None and breakdown is not None
    assert set(gen.technologies) == {"wind", "solar"}

    # The CFADS allocation conserves the run's combined operational CFADS.
    run_cfads = kpis.get("mean_operational_cfads_usd") or kpis["final_cfads_usd"]
    assert gen.total_cfads_usd == pytest.approx(run_cfads)
    per_tech_sum = sum(p.annual_cfads_usd for p in gen.technologies.values())
    assert per_tech_sum == pytest.approx(run_cfads)

    # Shares follow the declared per-tech AEP proportions.
    total_aep = WIND_AEP_GWH + SOLAR_AEP_GWH
    rows = {r.technology: r for r in breakdown}
    assert rows["wind"].share_of_aep_pct == pytest.approx(100.0 * WIND_AEP_GWH / total_aep)
    assert rows["solar"].share_of_aep_pct == pytest.approx(100.0 * SOLAR_AEP_GWH / total_aep)
    assert rows["wind"].share_of_capex_pct == pytest.approx(100.0 * 195 / 230)

    # Serializes through the contract's JSON helper (what casper_payload emits).
    payload = gen.to_dict()
    assert set(payload["technologies"]) == {"wind", "solar"}


def test_per_tech_degradation_flows_through_the_real_cashflow() -> None:
    """M3: a generation.technologies block carrying per-tech capacity/CF/degradation
    drives the finance engine — the hybrid run differs from the single-tech run
    because wind and solar degrade at different rates."""
    base = WindFarmInputs(
        site_name="DutchBay Hybrid",
        capacity_mw=200.0,
        capacity_factor=0.304250,  # (150*0.339 + 50*0.20) / 200 — reconciles per-tech
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=230_000_000,
        opex_annual_usd=6_500_000,
        fx_start_lkr_per_usd=333.79,
    ).to_scenario_config()

    single = run_finance_case(dict(base))

    hybrid = dict(base)
    hybrid["generation"] = {
        "technologies": {
            "wind": {"capacity_mw": 150, "capacity_factor": 0.339, "degradation_pct": 0.006},
            "solar": {"capacity_mw": 50, "capacity_factor": 0.20, "degradation_pct": 0.004},
        }
    }
    multi = run_finance_case(hybrid)

    assert single["status"] == "success" and multi["status"] == "success"
    # Per-tech degradation genuinely changes lifetime CFADS / returns (not a no-op).
    assert multi["kpis"]["total_cfads_usd"] != pytest.approx(
        single["kpis"]["total_cfads_usd"]
    )
    assert multi["kpis"]["project_irr"] != pytest.approx(single["kpis"]["project_irr"])
