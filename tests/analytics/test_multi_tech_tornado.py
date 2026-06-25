"""Unit tests for ``analytics.portfolio.multi_tech_tornado`` (Epic 6.1).

Pins the per-technology tornado contract for the hybrid wind+solar scenario:

* the *coupled* overrides keep the scenario reconciled (no raise) and route each
  shock to the field finance actually reads — so no axis is a phantom (the failure
  mode a plain one-way ``generation.technologies.<tech>.capex_usd`` /
  ``capacity_factor`` sweep would hit: a zero-impact bar, or a reconciliation raise);
* the lender headline holds: **wind drives the IRR / balloon volatility**;
* ``min_dscr`` is correctly reported as structurally flat (dual-DSCR sculpting).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.portfolio.multi_tech_tornado import (
    DEFAULT_DRIVERS,
    DEFAULT_METRICS,
    MultiTechTornadoBar,
    applicable_drivers,
    applicable_storage_drivers,
    build_coupled_override,
    build_storage_override,
    discover_generation_technologies,
    discover_non_generation_technologies,
    discover_storage_technologies,
    flat_metrics,
    impact_by_technology,
    run_multi_tech_tornado,
)
from analytics.scenario_loader import load_scenario_config

_REPO = Path(__file__).resolve().parents[2]
_HYBRID = _REPO / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml"

pytestmark = pytest.mark.skipif(
    not _HYBRID.exists(), reason="hybrid wind+solar scenario not present"
)


@pytest.fixture(scope="module")
def hybrid_config() -> dict:
    return load_scenario_config(_HYBRID)


@pytest.fixture(scope="module")
def hybrid_bars(hybrid_config: dict) -> list[MultiTechTornadoBar]:
    # evaluate_with_overrides does not mutate raw_config (it deep-merges into a copy),
    # so a module-scoped config + bars is safe to share across tests.
    return run_multi_tech_tornado(hybrid_config)


# ── tech / driver discovery (pure, no evaluation) ──────────────────────────────

# A heterogeneous portfolio: two canonical gen techs, an arbitrary third gen tech
# (proving no wind/solar special-casing), and a BESS storage block.
_MIXED = {
    "generation": {
        "technologies": {
            "wind": {"capacity_mw": 100, "capacity_factor": 0.35},
            "solar": {"capacity_mw": 50, "capacity_factor": 0.20},
            "tidal": {"capacity_mw": 10, "capacity_factor": 0.40},  # 3rd gen tech
            "battery": {"power_mw": 20, "energy_mwh": 80},  # BESS: power/energy, no CF
        }
    }
}


def test_discover_generation_is_class_agnostic_and_skips_storage():
    # wind == solar == tidal (any block with a capacity_factor); battery excluded.
    assert discover_generation_technologies(_MIXED) == ["wind", "solar", "tidal"]


def test_discover_storage_finds_bess():
    assert discover_storage_technologies(_MIXED) == ["battery"]


def test_discover_non_generation_is_robust_superset():
    # catches storage AND any non-generation block, so nothing is silently dropped.
    weird = {"generation": {"technologies": {
        "battery": {"power_mw": 20, "energy_mwh": 80},
        "mystery": {"foo": 1},  # neither generation nor recognised storage
    }}}
    assert discover_non_generation_technologies(weird) == ["battery", "mystery"]
    assert discover_storage_technologies(weird) == ["battery"]


def test_type_bess_is_storage_not_generation_even_with_capacity_factor():
    # `type` is authoritative: a BESS mis-keyed with a capacity_factor must NOT be
    # classified as generation (it would be swept as a phantom driver) — it is storage,
    # consistent with the cashflow excluding it from generation revenue.
    cfg = {"generation": {"technologies": {
        "wind": {"capacity_mw": 100, "capacity_factor": 0.34},
        "bess": {"type": "bess", "power_mw": 50, "capacity_factor": 0.20},
    }}}
    assert discover_generation_technologies(cfg) == ["wind"]
    assert discover_storage_technologies(cfg) == ["bess"]
    assert discover_non_generation_technologies(cfg) == ["bess"]


def test_discover_generation_empty_without_block():
    assert discover_generation_technologies({"project": {"capacity_mw": 100}}) == []


def test_hybrid_discovers_wind_and_solar(hybrid_config: dict):
    assert discover_generation_technologies(hybrid_config) == ["wind", "solar"]
    assert discover_storage_technologies(hybrid_config) == []


def test_applicable_drivers_skips_absent_field():
    config = {
        "generation": {
            "technologies": {
                # solar declares capex + CF but NOT degradation_pct
                "solar": {"capacity_mw": 50, "capacity_factor": 0.20, "capex_usd": 4e7},
            }
        }
    }
    assert applicable_drivers(config, "solar") == ["capex_usd", "capacity_factor"]


# ── coupled-override construction ──────────────────────────────────────────────


def test_capex_override_couples_per_tech_to_financed_total(hybrid_config: dict):
    """A per-tech capex shock must also move ``capex.usd_total`` by the same delta —
    otherwise the financed CAPEX (which the cashflow reads) never changes."""
    ov = build_coupled_override(hybrid_config, "wind", "capex_usd", 1.10)
    base_tech = hybrid_config["generation"]["technologies"]["wind"]["capex_usd"]
    base_total = hybrid_config["capex"]["usd_total"]
    delta = base_tech * 0.10
    assert ov["generation.technologies.wind.capex_usd"] == pytest.approx(base_tech + delta)
    assert ov["capex.usd_total"] == pytest.approx(base_total + delta)


def test_capacity_factor_override_reconciles_exactly(hybrid_config: dict):
    """The blended ``project.capacity_factor`` in a CF override must make the per-tech
    year-1 capacity reconcile exactly (the ±1% in-cashflow guard)."""
    ov = build_coupled_override(hybrid_config, "wind", "capacity_factor", 1.10)
    techs = hybrid_config["generation"]["technologies"]
    new_wind_cf = ov["generation.technologies.wind.capacity_factor"]
    blended = ov["project.capacity_factor"]
    project_mw = hybrid_config["project"]["capacity_mw"]
    # sum(mw*cf) with shocked wind == project_mw * blended  (reconciliation == 0)
    actual = techs["wind"]["capacity_mw"] * new_wind_cf + techs["solar"]["capacity_mw"] * techs["solar"]["capacity_factor"]
    assert actual == pytest.approx(project_mw * blended)


def test_degradation_override_is_single_key(hybrid_config: dict):
    ov = build_coupled_override(hybrid_config, "solar", "degradation_pct", 0.90)
    assert set(ov) == {"generation.technologies.solar.degradation_pct"}


def test_build_coupled_override_rejects_unknown_driver(hybrid_config: dict):
    with pytest.raises(ValueError, match="unknown driver"):
        build_coupled_override(hybrid_config, "wind", "bogus", 1.1)


# ── the tornado itself ─────────────────────────────────────────────────────────


def test_runs_without_raising_and_has_expected_shape(hybrid_bars):
    # 2 techs x 3 drivers x 4 metrics = 24 bars (no reconciliation raise).
    assert len(hybrid_bars) == len(DEFAULT_METRICS) * 2 * len(DEFAULT_DRIVERS)
    assert {b.technology for b in hybrid_bars} == {"wind", "solar"}
    assert {b.driver for b in hybrid_bars} == set(DEFAULT_DRIVERS)


def test_no_phantom_axis_every_driver_moves_project_irr(hybrid_bars):
    """Each (tech, driver) genuinely moves project_irr — the coupling is what turns
    the otherwise-phantom capex bar and the otherwise-raising CF bar into real ones."""
    irr_bars = [b for b in hybrid_bars if b.metric == "project_irr"]
    assert len(irr_bars) == 2 * len(DEFAULT_DRIVERS)
    for bar in irr_bars:
        assert bar.impact_abs > 1e-9, f"{bar.label} is a phantom (zero-impact) bar"


def test_wind_dominates_volatility(hybrid_bars):
    """The lender headline: wind drives the IRR and balloon swing (it is ~88% of
    generation), comfortably above solar on every responsive metric."""
    for metric in ("project_irr", "equity_irr", "balloon_pct"):
        ranking = impact_by_technology(hybrid_bars, metric)
        assert list(ranking)[0] == "wind"
        assert ranking["wind"] > ranking["solar"]


def test_min_dscr_is_flagged_flat(hybrid_bars):
    """min_dscr is sculpted to target by dual-DSCR sizing -> structurally flat."""
    assert flat_metrics(hybrid_bars) == ["min_dscr"]
    # and it is genuinely flat, not merely under-tolerance by luck:
    for bar in hybrid_bars:
        if bar.metric == "min_dscr":
            assert bar.impact_abs < 1e-9


def test_bars_sorted_by_impact_within_each_metric(hybrid_bars):
    for metric in DEFAULT_METRICS:
        impacts = [b.impact_abs for b in hybrid_bars if b.metric == metric]
        assert impacts == sorted(impacts, reverse=True)


def test_base_case_constant_within_metric(hybrid_bars):
    for metric in DEFAULT_METRICS:
        bases = {b.base_case for b in hybrid_bars if b.metric == metric}
        assert len(bases) == 1


# ── validation / fail-loud ─────────────────────────────────────────────────────


@pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5])
def test_shock_pct_must_be_a_proper_fraction(hybrid_config: dict, bad: float):
    with pytest.raises(ValueError, match="shock_pct"):
        run_multi_tech_tornado(hybrid_config, shock_pct=bad)


def test_unknown_metric_fails_loud(hybrid_config: dict):
    with pytest.raises(ValueError, match="not in the evaluation KPIs"):
        run_multi_tech_tornado(hybrid_config, metrics=["not_a_real_kpi"])


def test_no_technologies_yields_no_bars():
    # No generation.technologies block -> empty result, without any evaluation.
    assert run_multi_tech_tornado({"project": {"capacity_mw": 100}}) == []


# ── tech-independence: storage / BESS handled, never silently dropped ───────────


def test_storage_only_scenario_yields_no_bars_and_warns(caplog):
    """A BESS-only scenario has no generation -> no bars (no evaluation), and the
    storage block is surfaced rather than silently dropped."""
    bess_only = {"generation": {"technologies": {
        "battery": {"power_mw": 50, "energy_mwh": 200},
    }}}
    with caplog.at_level("WARNING"):
        assert run_multi_tech_tornado(bess_only) == []
    assert "battery" in caplog.text
    assert discover_storage_technologies(bess_only) == ["battery"]


def test_storage_alongside_generation_is_reported_not_swept(hybrid_config: dict, caplog):
    """wind + solar + BESS: the generation techs are swept exactly as before, and the
    storage block is warned about (so the tornado can't be mistaken for complete)."""
    cfg = dict(hybrid_config)
    techs = dict(cfg["generation"]["technologies"])
    techs["battery"] = {"power_mw": 50, "energy_mwh": 200}  # add a BESS block
    cfg["generation"] = {"technologies": techs}

    with caplog.at_level("WARNING"):
        bars = run_multi_tech_tornado(cfg)

    # storage is skipped by the engine's reconciliation, so the run is unaffected:
    assert {b.technology for b in bars} == {"wind", "solar"}
    assert len(bars) == len(DEFAULT_METRICS) * 2 * len(DEFAULT_DRIVERS)
    # ...but the BESS block is loudly reported, not silently dropped.
    assert "battery" in caplog.text
    assert discover_storage_technologies(cfg) == ["battery"]


# ── storage (BESS) is now SWEPT on its capacity-charge driver ───────────────────


def test_applicable_storage_drivers_needs_a_revenue_lever():
    cfg = {"generation": {"technologies": {
        "bess": {"type": "bess", "power_mw": 10, "revenue": {
            "model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 2_000_000}},
        "bare": {"type": "bess", "power_mw": 5},  # no revenue -> not sweepable
    }}}
    assert applicable_storage_drivers(cfg, "bess") == ["capacity_charge_lkr_per_mw_month"]
    assert applicable_storage_drivers(cfg, "bare") == []


def test_build_storage_override_is_direct_single_key():
    cfg = {"generation": {"technologies": {"bess": {"type": "bess", "power_mw": 10,
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 2_000_000}}}}}
    ov = build_storage_override(cfg, "bess", "capacity_charge_lkr_per_mw_month", 1.1)
    assert ov == {
        "generation.technologies.bess.revenue.capacity_charge_lkr_per_mw_month":
        pytest.approx(2_200_000)
    }


def test_build_storage_override_rejects_unknown_driver():
    cfg = {"generation": {"technologies": {"bess": {"type": "bess", "power_mw": 10,
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1}}}}}
    with pytest.raises(ValueError, match="unknown storage driver"):
        build_storage_override(cfg, "bess", "bogus", 1.1)


def test_bess_with_revenue_lever_is_swept_alongside_generation(hybrid_config):
    cfg = dict(hybrid_config)
    techs = dict(cfg["generation"]["technologies"])
    techs["bess_1"] = {
        "type": "bess", "power_mw": 50.0, "energy_mwh": 200.0,
        "revenue": {"model": "capacity_charge",
                    "capacity_charge_lkr_per_mw_month": 5_000_000, "contract_years": 15},
    }
    cfg["generation"] = {"technologies": techs}
    bars = run_multi_tech_tornado(cfg, metrics=["project_irr"])
    bess_bars = [b for b in bars if b.technology == "bess_1"]
    assert len(bess_bars) == 1  # one storage driver
    assert bess_bars[0].driver == "capacity_charge_lkr_per_mw_month"
    assert bess_bars[0].impact_abs > 1e-9  # the bid rate is a live driver
    # wind/solar still swept too
    assert {"wind", "solar"} <= {b.technology for b in bars}


# ── why coupling exists: pin the uncoupled failure modes (regression guard) ─────


def test_uncoupled_per_tech_capex_is_a_phantom(hybrid_config: dict):
    """A bare per-tech ``capex_usd`` override does NOT move project_irr — the
    financed CAPEX is ``capex.usd_total``. This is exactly why the tornado couples
    the two; if this ever starts moving, the coupling can be simplified."""
    base = evaluate_with_overrides(raw_config=hybrid_config, overrides={})
    bumped = evaluate_with_overrides(
        raw_config=hybrid_config,
        overrides={"generation.technologies.wind.capex_usd": 159_600_000 * 1.10},
    )
    assert bumped["project_irr"] == pytest.approx(base["project_irr"])


def test_uncoupled_per_tech_capacity_factor_breaks_reconciliation(hybrid_config: dict):
    """A bare per-tech ``capacity_factor`` override breaks the ±1% year-1 capacity
    reconciliation and raises — which is why the tornado also re-blends
    ``project.capacity_factor``."""
    with pytest.raises(Exception, match="reconcile"):
        evaluate_with_overrides(
            raw_config=hybrid_config,
            overrides={"generation.technologies.wind.capacity_factor": 0.339 * 1.10},
        )


# ---------------------------------------------------------------------------
# Wave-2: energy_tariff BESS is now a swept storage driver (was only capacity_charge)
# ---------------------------------------------------------------------------
_NIGHTPEAK = str(
    Path(__file__).resolve().parents[2] / "scenarios" / "ceb_solar_bess_nightpeak_10mw.yaml"
)


def test_energy_tariff_bess_is_swept_with_real_impact() -> None:
    """An energy-tariff BESS (revenue.tariff_lkr_per_kwh) is now a live storage driver:
    the tornado produces a non-phantom bar for it (was only capacity_charge before)."""
    cfg = load_scenario_config(_NIGHTPEAK)
    # discovery picks the tariff lever (present), not capacity_charge (absent here)
    techs = [t for t in cfg["generation"]["technologies"] if cfg["generation"]["technologies"][t].get("type") == "bess"]
    assert techs, "expected a type:bess block in the night-peak scenario"
    drivers = applicable_storage_drivers(cfg, techs[0])
    assert "tariff_lkr_per_kwh" in drivers
    assert "capacity_charge_lkr_per_mw_month" not in drivers  # absent -> not a phantom

    bars = run_multi_tech_tornado(cfg, metrics=["project_irr"])
    tariff_bars = [b for b in bars if b.driver == "tariff_lkr_per_kwh"]
    assert tariff_bars, "energy-tariff BESS produced no tornado bar"
    assert any(abs(b.impact_abs) > 1e-6 for b in tariff_bars)  # real sensitivity, not ~0
