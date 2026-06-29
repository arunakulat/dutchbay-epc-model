"""Unit tests for ``finance.bess_lcos`` — the read-only Levelised Cost of Storage view.

LCOS = PV(lifetime costs) / PV(lifetime discharged energy) at the project WACC. The view
is strictly off the cashflow path (it must never feed CFADS/IRR/DSCR), so these tests pin
the present-value build-up, the cost sourcing (standalone vs hybrid), the degradation
coupling, and the CESSPIT fail-loud guards — but never assert anything about committed
KPIs.
"""

from __future__ import annotations

import pytest

from finance.bess_lcos import (
    LcosResult,
    LcosSpec,
    compute_lcos,
    compute_lcos_suite,
    resolve_lcos_specs,
)
from finance.bess_revenue import resolve_bess_specs


def _capacity_cfg(
    *,
    revenue_overrides: dict | None = None,
    block_capex_usd: float | None = 1_000.0,
    project_opex: float | None = 100.0,
    project_capex_total: float | None = 5_000.0,
    extra_techs: dict | None = None,
    tariff_lkr_per_kwh: float = 0.0,
) -> dict:
    """A standalone capacity-charge BESS config (overridable for hybrid/fallback tests)."""
    revenue = {
        "model": "capacity_charge",
        "capacity_charge_lkr_per_mw_month": 2_000_000,
        "cycles_per_year": 1.0,
        "round_trip_efficiency": 1.0,
    }
    if revenue_overrides:
        revenue.update(revenue_overrides)
    bess_block: dict = {
        "type": "bess",
        "power_mw": 10.0,
        "energy_mwh": 40.0,
        "duration_h": 4.0,
        "revenue": revenue,
    }
    if block_capex_usd is not None:
        bess_block["capex_usd"] = block_capex_usd
    techs: dict = {"bess_unit": bess_block}
    if extra_techs:
        techs.update(extra_techs)
    cfg: dict = {
        "generation": {"technologies": techs},
        "tariff": {"lkr_per_kwh": tariff_lkr_per_kwh},
    }
    if project_opex is not None:
        cfg["opex"] = {"usd_per_year": project_opex, "escalation_pct": 0.0}
    if project_capex_total is not None:
        cfg.setdefault("capex", {})["usd_total"] = project_capex_total
    return cfg


def _energy_cfg(**revenue_overrides) -> dict:
    """A standalone energy-tariff BESS config."""
    revenue = {
        "model": "energy_tariff",
        "tariff_lkr_per_kwh": 45.80,
        "cycles_per_year": 1.0,
        "round_trip_efficiency": 1.0,
    }
    revenue.update(revenue_overrides)
    return {
        "generation": {
            "technologies": {
                "bess_unit": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "duration_h": 4.0,
                    "capex_usd": 1_000.0,
                    "revenue": revenue,
                }
            }
        },
        "tariff": {"lkr_per_kwh": 0.0},
        "opex": {"usd_per_year": 100.0, "escalation_pct": 0.0},
    }


# ── resolution: absence ─────────────────────────────────────────────────────────


def test_no_bess_resolves_to_none_and_empty_suite():
    wind_only = {"generation": {"technologies": {"wind": {"capacity_factor": 0.34}}}}
    assert resolve_lcos_specs(wind_only) is None
    assert compute_lcos_suite(wind_only, wacc=0.10, project_years=20) == []


def test_resolution_does_not_disturb_the_revenue_spec():
    # The LCOS view must be purely additive: resolving it leaves the revenue spec intact.
    cfg = _capacity_cfg()
    before = resolve_bess_specs(cfg)
    resolve_lcos_specs(cfg)
    after = resolve_bess_specs(cfg)
    assert before == after


# ── resolution: cost sourcing & defaults ────────────────────────────────────────


def test_standalone_capacity_charge_defaults():
    specs = resolve_lcos_specs(_capacity_cfg())
    assert specs is not None and len(specs) == 1
    s = specs[0]
    assert isinstance(s, LcosSpec)
    assert s.revenue_model == "capacity_charge"
    assert s.energy_per_cycle_mwh == 40.0  # power_mw * duration_h
    assert s.depth_of_discharge == 0.80  # capacity-charge default
    assert s.capex_usd == 1_000.0  # block capex_usd
    assert s.opex_usd_per_year == 100.0  # standalone -> project opex
    assert any("CEB" in n for n in s.notes)  # dispatch-assumption note


def test_standalone_capex_falls_back_to_project_total_when_block_absent():
    specs = resolve_lcos_specs(_capacity_cfg(block_capex_usd=None))
    assert specs is not None
    assert specs[0].capex_usd == 5_000.0  # capex.usd_total fallback


def test_energy_tariff_defaults():
    specs = resolve_lcos_specs(_energy_cfg())
    assert specs is not None
    s = specs[0]
    assert s.revenue_model == "energy_tariff"
    assert s.depth_of_discharge == 0.40  # energy-tariff default
    assert s.energy_per_cycle_mwh == 40.0


# ── hybrid attribution ──────────────────────────────────────────────────────────


def test_hybrid_excludes_shared_project_opex_with_a_note():
    cfg = _capacity_cfg(
        extra_techs={"wind": {"type": "wind", "capacity_factor": 0.34}},
        tariff_lkr_per_kwh=18.0,
    )
    specs = resolve_lcos_specs(cfg)
    assert specs is not None
    s = specs[0]
    assert s.opex_usd_per_year == 0.0  # not attributed on a hybrid
    assert s.capex_usd == 1_000.0  # block capex still used
    assert any("opex not attributed" in n for n in s.notes)


def test_hybrid_uses_block_level_opex_override():
    cfg = _capacity_cfg(
        revenue_overrides={"opex_usd_per_year": 250.0},
        extra_techs={"wind": {"type": "wind", "capacity_factor": 0.34}},
        tariff_lkr_per_kwh=18.0,
    )
    s = resolve_lcos_specs(cfg)[0]
    assert s.opex_usd_per_year == 250.0
    assert all("opex not attributed" not in n for n in s.notes)


def test_hybrid_without_block_capex_excludes_capex_with_a_note():
    cfg = _capacity_cfg(
        block_capex_usd=None,
        extra_techs={"wind": {"type": "wind", "capacity_factor": 0.34}},
        tariff_lkr_per_kwh=18.0,
    )
    s = resolve_lcos_specs(cfg)[0]
    assert s.capex_usd == 0.0
    assert any("capex excluded" in n for n in s.notes)


# ── compute: hand-checked present values ────────────────────────────────────────


def test_lcos_undiscounted_hand_calc():
    # wacc=0 -> npv is a plain sum. energy/yr = 40 * 1 cycle * 0.80 dod * 1.0 rte = 32 MWh.
    # horizon 2: PV(costs) = 1000 capex + 2*100 opex = 1200; PV(energy) = 64 MWh.
    spec = resolve_lcos_specs(_capacity_cfg(revenue_overrides={"contract_years": 2}))[0]
    r = compute_lcos(spec, wacc=0.0, project_years=2)
    assert r.pv_capex_usd == pytest.approx(1_000.0)
    assert r.pv_opex_usd == pytest.approx(200.0)
    assert r.pv_costs_usd == pytest.approx(1_200.0)
    assert r.pv_discharged_mwh == pytest.approx(64.0)
    assert r.lcos_usd_per_mwh == pytest.approx(1_200.0 / 64.0)  # 18.75


def test_lcos_discounted_one_year_hand_calc():
    # horizon 1, wacc 10%: PV(costs) = 1000 + 100/1.1 ; PV(energy) = 32/1.1 ; ratio = 37.5.
    spec = resolve_lcos_specs(_capacity_cfg(revenue_overrides={"contract_years": 1}))[0]
    r = compute_lcos(spec, wacc=0.10, project_years=5)
    assert r.horizon_years == 1  # contract caps the horizon
    assert r.pv_costs_usd == pytest.approx(1_000.0 + 100.0 / 1.1)
    assert r.pv_discharged_mwh == pytest.approx(32.0 / 1.1)
    assert r.lcos_usd_per_mwh == pytest.approx(37.5)


def test_horizon_caps_at_project_years():
    spec = resolve_lcos_specs(_capacity_cfg(revenue_overrides={"contract_years": 30}))[
        0
    ]
    assert compute_lcos(spec, wacc=0.08, project_years=15).horizon_years == 15


def test_horizon_defaults_to_project_years_without_contract():
    spec = resolve_lcos_specs(_capacity_cfg())[0]  # no contract_years
    assert compute_lcos(spec, wacc=0.08, project_years=12).horizon_years == 12


# ── compute: degradation / augmentation / salvage couplings ─────────────────────


def test_fade_lowers_discharged_energy_and_raises_lcos():
    base = resolve_lcos_specs(_capacity_cfg())[0]
    faded = resolve_lcos_specs(
        _capacity_cfg(revenue_overrides={"mdsc_fade_pct_annual": 0.02})
    )[0]
    rb = compute_lcos(base, wacc=0.08, project_years=15)
    rf = compute_lcos(faded, wacc=0.08, project_years=15)
    assert rf.pv_discharged_mwh < rb.pv_discharged_mwh
    assert rf.lcos_usd_per_mwh > rb.lcos_usd_per_mwh


def test_augmentation_adds_capex_present_value():
    spec = resolve_lcos_specs(
        _capacity_cfg(
            revenue_overrides={
                "augmentation_schedule": [{"year": 8, "capex_usd": 500.0}],
            }
        )
    )[0]
    r = compute_lcos(spec, wacc=0.08, project_years=15)
    assert r.pv_augmentation_usd > 0.0
    assert r.pv_augmentation_usd == pytest.approx(500.0 / 1.08**8)


def test_salvage_reduces_costs():
    no_salvage = compute_lcos(
        resolve_lcos_specs(_capacity_cfg())[0], wacc=0.08, project_years=15
    )
    with_salvage = compute_lcos(
        resolve_lcos_specs(_capacity_cfg(revenue_overrides={"salvage_usd": 400.0}))[0],
        wacc=0.08,
        project_years=15,
    )
    assert with_salvage.pv_salvage_usd > 0.0
    assert with_salvage.pv_costs_usd < no_salvage.pv_costs_usd


# ── compute: undefined / guards ─────────────────────────────────────────────────


def test_zero_depth_of_discharge_yields_undefined_lcos():
    spec = resolve_lcos_specs(
        _capacity_cfg(revenue_overrides={"depth_of_discharge": 0.0})
    )[0]
    r = compute_lcos(spec, wacc=0.08, project_years=15)
    assert r.pv_discharged_mwh == 0.0
    assert r.lcos_usd_per_mwh is None
    assert any("undefined" in n for n in r.notes)


@pytest.mark.parametrize("bad_wacc", [-1.0, -2.0, float("nan"), float("inf")])
def test_compute_rejects_invalid_wacc(bad_wacc):
    spec = resolve_lcos_specs(_capacity_cfg())[0]
    with pytest.raises(ValueError):
        compute_lcos(spec, wacc=bad_wacc, project_years=15)


def test_compute_rejects_non_positive_project_years():
    spec = resolve_lcos_specs(_capacity_cfg())[0]
    with pytest.raises(ValueError):
        compute_lcos(spec, wacc=0.08, project_years=0)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("depth_of_discharge", 80.0),  # ratio mis-entered as a percent
        ("round_trip_efficiency", 1.5),
        ("cycles_per_year", 0.0),
        ("salvage_usd", -5.0),
    ],
)
def test_resolution_fails_loud_on_bad_lcos_fields(field, bad):
    with pytest.raises(ValueError):
        resolve_lcos_specs(_capacity_cfg(revenue_overrides={field: bad}))


# ── energy-basis resolution edge cases ──────────────────────────────────────────


def _bare_capacity_block(**block_extra) -> dict:
    """A standalone capacity-charge BESS with only the fields the test sets."""
    block = {
        "type": "bess",
        "power_mw": 10.0,
        "revenue": {
            "model": "capacity_charge",
            "capacity_charge_lkr_per_mw_month": 2_000_000,
        },
    }
    block.update(block_extra)
    return {
        "generation": {"technologies": {"bess_unit": block}},
        "tariff": {"lkr_per_kwh": 0.0},
        "opex": {"usd_per_year": 100.0},
        "capex": {"usd_total": 1_000.0},
    }


def test_energy_basis_falls_back_to_power_times_duration():
    # No energy_mwh, but duration_h is given -> energy_per_cycle = power_mw * duration_h.
    s = resolve_lcos_specs(_bare_capacity_block(duration_h=4.0))[0]
    assert s.energy_per_cycle_mwh == 40.0


def test_no_energy_rating_yields_undefined_lcos_with_note():
    s = resolve_lcos_specs(_bare_capacity_block())[0]  # no energy_mwh, no duration_h
    assert s.energy_per_cycle_mwh == 0.0
    assert any("no energy rating" in n for n in s.notes)
    r = compute_lcos(s, wacc=0.08, project_years=15)
    assert r.lcos_usd_per_mwh is None


def test_cycles_defaults_when_not_overridden():
    # Omitting revenue.cycles_per_year exercises the positive-default path (365/day).
    s = resolve_lcos_specs(_bare_capacity_block(energy_mwh=40.0, duration_h=4.0))[0]
    assert s.cycles_per_year == 365.0


# ── standalone detection edge cases ─────────────────────────────────────────────


def test_untyped_generation_block_marks_scenario_hybrid():
    # A pre-enum generation block (capacity_factor, no type) is key-sniffed as generation,
    # so the BESS is NOT standalone and project opex is not attributed.
    cfg = _capacity_cfg(
        extra_techs={"legacy_wind": {"capacity_factor": 0.34}},
        tariff_lkr_per_kwh=18.0,
    )
    s = resolve_lcos_specs(cfg)[0]
    assert s.opex_usd_per_year == 0.0
    assert any("opex not attributed" in n for n in s.notes)


def test_non_mapping_tech_block_is_ignored():
    cfg = _capacity_cfg(extra_techs={"junk": "not-a-mapping"})
    s = resolve_lcos_specs(cfg)[0]
    assert s.opex_usd_per_year == 100.0  # still standalone (junk ignored)


def test_resolution_fails_loud_on_non_numeric_ratio():
    with pytest.raises(ValueError):
        resolve_lcos_specs(
            _capacity_cfg(revenue_overrides={"depth_of_discharge": "deep"})
        )


# ── suite & serialisation ───────────────────────────────────────────────────────


def test_suite_returns_one_result_per_bess():
    results = compute_lcos_suite(_capacity_cfg(), wacc=0.0983, project_years=15)
    assert len(results) == 1
    assert isinstance(results[0], LcosResult)
    assert results[0].technology == "bess_unit"


def test_as_dict_is_json_shaped():
    r = compute_lcos_suite(_capacity_cfg(), wacc=0.0983, project_years=15)[0]
    d = r.as_dict()
    assert d["technology"] == "bess_unit"
    assert d["lcos_usd_per_mwh"] == r.lcos_usd_per_mwh
    assert isinstance(d["notes"], list)
