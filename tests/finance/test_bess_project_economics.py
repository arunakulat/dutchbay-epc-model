"""Unit tests for ``finance.bess_project_economics`` — standalone BESS project economics.

This module turns the real 2025 Sri Lankan BESS commercial inputs (a Huawei-CIF-style capex
quote, the CEB capacity-charge tender, the CEB energy-cost methodology) into project
economics: landed capex, the CEB effective-cost curve (LKR/kWh, charging EXCLUDED), the
separate charging-cost lever, and a standalone cashflow -> IRR / NPV / LCOS.

The tests assert REAL, hand-checkable economics (a known capex + capacity charge -> a
hand-derived duty / effective-cost / IRR / NPV), the CESSPIT fail-loud guards, and — the
cardinal rule — that the whole analysis is opt-in / default-off and never runs for a scenario
that does not carry ``bess_economics.enabled: true``.
"""

from __future__ import annotations

import numpy_financial as npf
import pytest

from finance.bess_project_economics import (
    BessProjectEconomics,
    ChargingCostSpec,
    LandedCapex,
    bess_economics_requested,
    ceb_effective_cost_curve,
    charging_cost_lkr_for_year,
    compute_bess_project_economics,
    resolve_charging_cost_spec,
    resolve_landed_capex,
)
from finance.irr import npv


def _capacity_cfg(
    *,
    capacity_charge: float = 2_000_000.0,
    equipment_usd: float = 5_000_000.0,
    enabled: bool = True,
    revenue_overrides: dict | None = None,
    economics_overrides: dict | None = None,
    fx_start: float = 300.0,
    project_life: int = 15,
) -> dict:
    """A standalone, opt-in capacity-charge BESS economics config (10 MW / 40 MWh)."""
    revenue = {
        "model": "capacity_charge",
        "capacity_charge_lkr_per_mw_month": capacity_charge,
    }
    if revenue_overrides:
        revenue.update(revenue_overrides)
    economics: dict = {"enabled": enabled, "capex": {"equipment_usd": equipment_usd}}
    if economics_overrides:
        # Deep-merge the capex sub-block so callers can add capex fields cleanly.
        if "capex" in economics_overrides:
            economics["capex"].update(economics_overrides.pop("capex"))
        economics.update(economics_overrides)
    return {
        "generation": {
            "technologies": {
                "bess_unit": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "duration_h": 4.0,
                    "revenue": revenue,
                }
            }
        },
        "fx": {"start_lkr_per_usd": fx_start, "annual_depr_pct": 0.0},
        "returns": {"project_life_years": project_life},
        "bess_economics": economics,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Opt-in / default-off (the cardinal rule)
# ═════════════════════════════════════════════════════════════════════════════


def test_not_requested_without_block() -> None:
    """No ``bess_economics`` block => the analysis is not requested (default-off)."""
    assert bess_economics_requested({}) is False
    assert bess_economics_requested({"generation": {}}) is False


def test_not_requested_when_disabled() -> None:
    """An explicit ``enabled: false`` (or a missing flag) is not a request."""
    assert bess_economics_requested({"bess_economics": {}}) is False
    assert bess_economics_requested({"bess_economics": {"enabled": False}}) is False
    assert bess_economics_requested({"bess_economics": {"enabled": 0}}) is False


def test_requested_only_when_enabled_true() -> None:
    """Only ``enabled: true`` opts in."""
    assert bess_economics_requested({"bess_economics": {"enabled": True}}) is True


def test_compute_returns_none_when_not_opted_in() -> None:
    """The top-level compute refuses to run unless the scenario opts in."""
    cfg = _capacity_cfg(enabled=False)
    assert (
        compute_bess_project_economics(cfg, discount_rate=0.1, project_years=15) is None
    )


def test_compute_returns_none_without_capacity_charge_bess() -> None:
    """Opted in but no capacity-charge BESS => nothing to compute."""
    cfg = {
        "generation": {"technologies": {}},
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr_pct": 0.0},
        "bess_economics": {"enabled": True, "capex": {"equipment_usd": 1.0}},
    }
    assert (
        compute_bess_project_economics(cfg, discount_rate=0.1, project_years=15) is None
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. Landed capex — CIF structure + SL customs/duty + USD->LKR FX
# ═════════════════════════════════════════════════════════════════════════════


def test_landed_capex_hand_checked_duty_and_fx() -> None:
    """Huawei-basis capex: equipment $4,829,679.59 + 15% duty + $907,264.63 warranty.

    dutiable base = 4,829,679.59; duty = 0.15 x base = 724,451.94; warranty non-dutiable.
    landed USD = base + duty + warranty = 6,461,396.16; landed LKR = x 300.
    """
    cfg = {
        "bess_economics": {
            "enabled": True,
            "capex": {
                "equipment_usd": 4_829_679.59,
                "optional_warranty_usd": 907_264.63,
                "customs_duty_pct": 0.15,
            },
        }
    }
    lc = resolve_landed_capex(cfg, fx_rate_lkr_per_usd=300.0)
    assert isinstance(lc, LandedCapex)
    assert lc.dutiable_base_usd == pytest.approx(4_829_679.59)
    assert lc.customs_duty_usd == pytest.approx(724_451.9385)
    assert lc.landed_capex_usd == pytest.approx(6_461_396.1685)
    assert lc.landed_capex_lkr == pytest.approx(6_461_396.1685 * 300.0)
    assert lc.fx_rate_lkr_per_usd == 300.0


def test_landed_capex_freight_adds_to_dutiable_base() -> None:
    """Freight quoted separately joins the dutiable base and is dutied."""
    cfg = {
        "bess_economics": {
            "enabled": True,
            "capex": {
                "equipment_usd": 1_000_000.0,
                "freight_usd": 150_000.0,
                "customs_duty_pct": 0.10,
            },
        }
    }
    lc = resolve_landed_capex(cfg, fx_rate_lkr_per_usd=330.0)
    assert lc.dutiable_base_usd == pytest.approx(1_150_000.0)
    assert lc.customs_duty_usd == pytest.approx(115_000.0)
    assert lc.landed_capex_usd == pytest.approx(1_265_000.0)


def test_landed_capex_warranty_dutiable_toggle() -> None:
    """``warranty_is_dutiable`` folds the warranty into the duty base."""
    cfg = {
        "bess_economics": {
            "enabled": True,
            "capex": {
                "equipment_usd": 1_000_000.0,
                "optional_warranty_usd": 200_000.0,
                "customs_duty_pct": 0.10,
                "warranty_is_dutiable": True,
            },
        }
    }
    lc = resolve_landed_capex(cfg, fx_rate_lkr_per_usd=300.0)
    assert lc.dutiable_base_usd == pytest.approx(1_200_000.0)
    assert lc.customs_duty_usd == pytest.approx(120_000.0)
    # landed = base + duty + warranty = 1,200,000 + 120,000 + 200,000
    assert lc.landed_capex_usd == pytest.approx(1_520_000.0)


def test_landed_capex_explicit_duty_amount_overrides_pct() -> None:
    """An explicit ``customs_duty_usd`` is used verbatim (overrides the pct)."""
    cfg = {
        "bess_economics": {
            "enabled": True,
            "capex": {
                "equipment_usd": 1_000_000.0,
                "customs_duty_usd": 333_000.0,
                "customs_duty_pct": 0.10,  # ignored when the explicit amount is present
            },
        }
    }
    lc = resolve_landed_capex(cfg, fx_rate_lkr_per_usd=300.0)
    assert lc.customs_duty_usd == pytest.approx(333_000.0)


def test_landed_capex_zero_duty_default() -> None:
    """Absent duty => zero duty (declared, not silently a rate)."""
    cfg = {"bess_economics": {"enabled": True, "capex": {"equipment_usd": 1_000_000.0}}}
    lc = resolve_landed_capex(cfg, fx_rate_lkr_per_usd=300.0)
    assert lc.customs_duty_usd == 0.0
    assert lc.landed_capex_usd == pytest.approx(1_000_000.0)


def test_landed_capex_requires_equipment() -> None:
    """Missing equipment_usd is a config error (CESSPIT — no silent zero capex)."""
    with pytest.raises(ValueError, match="equipment_usd"):
        resolve_landed_capex(
            {"bess_economics": {"enabled": True, "capex": {}}},
            fx_rate_lkr_per_usd=300.0,
        )


def test_landed_capex_requires_capex_block() -> None:
    """Missing the capex block entirely raises."""
    with pytest.raises(ValueError, match="capex block is required"):
        resolve_landed_capex(
            {"bess_economics": {"enabled": True}}, fx_rate_lkr_per_usd=300.0
        )


@pytest.mark.parametrize("bad_fx", [0.0, -5.0, float("nan"), float("inf")])
def test_landed_capex_rejects_bad_fx(bad_fx: float) -> None:
    """A non-positive / non-finite FX rate raises (it multiplies the landed cost)."""
    cfg = {"bess_economics": {"enabled": True, "capex": {"equipment_usd": 1.0}}}
    with pytest.raises(ValueError, match="fx_rate_lkr_per_usd"):
        resolve_landed_capex(cfg, fx_rate_lkr_per_usd=bad_fx)


def test_landed_capex_rejects_out_of_range_duty_pct() -> None:
    """A duty pct outside [0, 1] (e.g. 15 for 15%) is a config error."""
    cfg = {
        "bess_economics": {
            "enabled": True,
            "capex": {"equipment_usd": 1.0, "customs_duty_pct": 15.0},
        }
    }
    with pytest.raises(ValueError, match="customs_duty_pct"):
        resolve_landed_capex(cfg, fx_rate_lkr_per_usd=300.0)


# ═════════════════════════════════════════════════════════════════════════════
# 2. CEB effective-cost curve (LKR/kWh) — charging cost EXCLUDED
# ═════════════════════════════════════════════════════════════════════════════


def test_ceb_effective_cost_year1_hand_checked() -> None:
    """CEB method, year 1, no fade:

    charge = 2,000,000 x 10 MW x 12 = 240,000,000 LKR/yr
    discharge = 40 MWh x 400 cycles x SoH 1.0 = 16,000 MWh = 16,000,000 kWh
    effective = 240,000,000 / 16,000,000 = 15.0 LKR/kWh — and charging is EXCLUDED.
    """
    cfg = _capacity_cfg()
    curve = ceb_effective_cost_curve(cfg, years=2)
    assert curve is not None
    row = curve[0]
    assert row["technology"] == "bess_unit"
    assert row["year"] == 1
    assert row["capacity_charge_lkr"] == pytest.approx(240_000_000.0)
    assert row["discharge_mwh"] == pytest.approx(16_000.0)
    assert row["lkr_per_kwh"] == pytest.approx(15.0)
    assert row["charging_excluded"] is True
    assert "CHARGING COST EXCLUDED" in row["note"]


def test_ceb_effective_cost_charge_and_discharge_share_soh() -> None:
    """When the modelled charge fades with SoH, numerator and denominator share the SAME SoH,
    so the per-year ratio is constant — documenting that the effective-cost curve is coupled
    to the single-source-of-truth SoH curve (finance.bess_revenue.mdsc_soh_for_year)."""
    cfg = _capacity_cfg(revenue_overrides={"mdsc_fade_pct_annual": 0.025})
    curve = ceb_effective_cost_curve(cfg, years=5)
    assert curve is not None
    ratios = [r["lkr_per_kwh"] for r in curve]
    assert all(v == pytest.approx(ratios[0]) for v in ratios)


def test_ceb_effective_cost_flat_charge_degrading_discharge_rises() -> None:
    """The genuine CEB result shape: a FLAT capacity charge over a DEGRADING discharge basis
    makes the effective LKR/kWh RISE over life (the CEB doc's ~15 -> 24 LKR/kWh curve). The
    tender pays a flat charge (independent of SoH); we reconstruct that flat-charge cost over
    the module's degradation-adjusted discharge and confirm it rises."""
    cfg = _capacity_cfg(revenue_overrides={"mdsc_fade_pct_annual": 0.025})
    curve = ceb_effective_cost_curve(cfg, years=3)
    assert curve is not None
    flat_charge = 240_000_000.0  # 2M x 10 MW x 12 (the tender's fixed charge)
    tender_costs = [flat_charge / (r["discharge_mwh"] * 1000.0) for r in curve]
    assert tender_costs[1] > tender_costs[0]  # rises as the discharge basis degrades
    assert tender_costs[2] > tender_costs[1]


def test_ceb_effective_cost_energy_from_power_times_duration() -> None:
    """Energy basis falls back to power_mw x duration_h when energy_mwh is absent.

    10 MW x 4 h = 40 MWh per cycle => same 15.0 LKR/kWh as the explicit-energy case.
    """
    cfg = _capacity_cfg()
    del cfg["generation"]["technologies"]["bess_unit"]["energy_mwh"]
    curve = ceb_effective_cost_curve(cfg, years=1)
    assert curve is not None
    assert curve[0]["discharge_mwh"] == pytest.approx(16_000.0)
    assert curve[0]["lkr_per_kwh"] == pytest.approx(15.0)


def test_ceb_effective_cost_none_for_energy_tariff_only() -> None:
    """An energy-tariff BESS is not part of the CEB capacity-charge method => None."""
    cfg = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "duration_h": 4.0,
                    "revenue": {
                        "model": "energy_tariff",
                        "tariff_lkr_per_kwh": 45.80,
                    },
                }
            }
        }
    }
    assert ceb_effective_cost_curve(cfg, years=5) is None


def test_ceb_effective_cost_none_without_bess() -> None:
    """No BESS => None."""
    assert (
        ceb_effective_cost_curve({"generation": {"technologies": {}}}, years=5) is None
    )


def test_ceb_effective_cost_respects_contract_years() -> None:
    """The curve stops at the BESS contract term."""
    cfg = _capacity_cfg(revenue_overrides={"contract_years": 3})
    curve = ceb_effective_cost_curve(cfg, years=10)
    assert curve is not None
    assert [r["year"] for r in curve] == [1, 2, 3]


# ═════════════════════════════════════════════════════════════════════════════
# 3. Charging-cost lever (the piece the CEB method omits)
# ═════════════════════════════════════════════════════════════════════════════


def test_charging_cost_hand_checked_with_rte_inflation() -> None:
    """discharge 16,000 MWh, RTE 0.80, tariff 20 LKR/kWh:

    charge energy = 16,000 / 0.80 = 20,000 MWh = 20,000,000 kWh
    charging cost = 20,000,000 x 20 = 400,000,000 LKR.
    """
    spec = ChargingCostSpec(
        charging_tariff_lkr_per_kwh=20.0,
        round_trip_efficiency=0.80,
        cycles_per_year=400,
    )
    assert charging_cost_lkr_for_year(spec, 16_000.0) == pytest.approx(400_000_000.0)


def test_charging_cost_zero_without_lever() -> None:
    """No charging lever (None) => zero charging cost (the CEB-style case)."""
    assert charging_cost_lkr_for_year(None, 16_000.0) == 0.0


def test_resolve_charging_none_without_block() -> None:
    """Absent ``bess_economics.charging`` => no charging lever."""
    assert resolve_charging_cost_spec(_capacity_cfg()) is None


def test_resolve_charging_reads_block() -> None:
    """The charging block resolves tariff / RTE / cycles."""
    cfg = _capacity_cfg(
        economics_overrides={
            "charging": {
                "tariff_lkr_per_kwh": 25.0,
                "round_trip_efficiency": 0.9,
                "cycles_per_year": 350.0,
            }
        }
    )
    spec = resolve_charging_cost_spec(cfg)
    assert spec is not None
    assert spec.charging_tariff_lkr_per_kwh == 25.0
    assert spec.round_trip_efficiency == 0.9
    assert spec.cycles_per_year == 350.0


def test_resolve_charging_requires_tariff() -> None:
    """A charging block without a tariff is a config error."""
    cfg = _capacity_cfg(
        economics_overrides={"charging": {"round_trip_efficiency": 0.9}}
    )
    with pytest.raises(ValueError, match="tariff_lkr_per_kwh"):
        resolve_charging_cost_spec(cfg)


def test_resolve_charging_defaults_rte() -> None:
    """RTE defaults to 0.85 (NREL ATB 2024, matching finance.bess_revenue)."""
    cfg = _capacity_cfg(economics_overrides={"charging": {"tariff_lkr_per_kwh": 20.0}})
    spec = resolve_charging_cost_spec(cfg)
    assert spec is not None
    assert spec.round_trip_efficiency == 0.85


# ═════════════════════════════════════════════════════════════════════════════
# 4. Standalone BESS economics — cashflow -> IRR / NPV / LCOS
# ═════════════════════════════════════════════════════════════════════════════


def test_economics_irr_npv_hand_checked_no_opex_no_charging() -> None:
    """Clean capex -> capacity-revenue economics, hand-checked against numpy_financial.

    landed capex = 5,000,000 USD x 300 = 1,500,000,000 LKR at t0.
    revenue = 240,000,000 LKR/yr, flat, 15 years, no fade, no opex, no charging.
    IRR and NPV must equal the independent numpy_financial / finance.irr computation.
    """
    cfg = _capacity_cfg()
    results = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)
    assert results is not None and len(results) == 1
    res = results[0]
    assert isinstance(res, BessProjectEconomics)
    assert res.horizon_years == 15
    assert res.landed_capex.landed_capex_lkr == pytest.approx(1_500_000_000.0)

    expected_cf = [-1_500_000_000.0] + [240_000_000.0] * 15
    assert list(res.cashflow_lkr) == pytest.approx(expected_cf)
    assert res.irr == pytest.approx(float(npf.irr(expected_cf)))
    assert res.npv_lkr == pytest.approx(npv(0.10, expected_cf))
    # No opex / no charging => those legs are zero and disclosed.
    assert all(v == 0.0 for v in res.opex_lkr)
    assert all(v == 0.0 for v in res.charging_cost_lkr)
    assert res.charging_modelled is False


def test_economics_charging_lever_lowers_cashflow_and_irr() -> None:
    """Opting into the charging lever subtracts a real cost => lower cashflow, lower IRR."""
    base = compute_bess_project_economics(
        _capacity_cfg(), discount_rate=0.10, project_years=15
    )[0]
    # A modest charging tariff (5 LKR/kWh, well below the ~15 LKR/kWh effective discharge
    # revenue) leaves the project IRR-defined but lowers it — the real effect of the lever.
    charged_cfg = _capacity_cfg(
        economics_overrides={
            "charging": {"tariff_lkr_per_kwh": 5.0, "round_trip_efficiency": 0.85}
        }
    )
    charged = compute_bess_project_economics(
        charged_cfg, discount_rate=0.10, project_years=15
    )[0]
    # charge energy yr1 = 16,000 / 0.85 MWh -> x1000 x 5 LKR/kWh
    expected_charge = (16_000.0 / 0.85) * 1000.0 * 5.0
    assert charged.charging_cost_lkr[0] == pytest.approx(expected_charge)
    assert charged.charging_modelled is True
    assert charged.cashflow_lkr[1] < base.cashflow_lkr[1]
    assert charged.npv_lkr < base.npv_lkr
    assert base.irr is not None and charged.irr is not None
    assert charged.irr < base.irr


def test_economics_opex_reduces_cashflow() -> None:
    """A flat opex leg is subtracted each year."""
    cfg = _capacity_cfg(economics_overrides={"opex_lkr_per_year": 10_000_000.0})
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)[0]
    assert all(v == pytest.approx(10_000_000.0) for v in res.opex_lkr)
    # cashflow yr1 = revenue - opex = 240,000,000 - 10,000,000
    assert res.cashflow_lkr[1] == pytest.approx(230_000_000.0)


def test_economics_warranty_schedule_draws_in_year() -> None:
    """A warranty/service draw is a cash outflow in its operating year."""
    cfg = _capacity_cfg(
        economics_overrides={"warranty_schedule": [{"year": 5, "lkr": 50_000_000.0}]}
    )
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)[0]
    # Year 5 (index 5 in the cashflow, since index 0 is capex) nets the draw.
    assert res.cashflow_lkr[5] == pytest.approx(240_000_000.0 - 50_000_000.0)
    assert res.cashflow_lkr[4] == pytest.approx(240_000_000.0)


def test_economics_augmentation_is_a_cash_outflow() -> None:
    """A mid-life augmentation (USD) is FX-converted and netted out in its year, and the
    revenue RECOVERS after the SoH restore (reusing finance.bess_revenue)."""
    cfg = _capacity_cfg(
        revenue_overrides={
            "mdsc_fade_pct_annual": 0.05,
            "augmentation_schedule": [
                {"year": 10, "capex_usd": 1_000_000.0, "restore_to_soh": 1.0}
            ],
        }
    )
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)[0]
    # Augmentation year 10 -> cashflow index 10 carries a 1,000,000 USD x 300 LKR outflow.
    assert res.augmentation_capex_lkr[9] == pytest.approx(1_000_000.0 * 300.0)
    # Revenue in year 10 (index 9) recovers to the full flat charge after the SoH restore.
    assert res.revenue_lkr[9] == pytest.approx(240_000_000.0)


def test_economics_attaches_lcos_and_effective_cost() -> None:
    """The result carries the read-only LCOS view and the CEB effective-cost curve."""
    res = compute_bess_project_economics(
        _capacity_cfg(), discount_rate=0.10, project_years=15
    )[0]
    assert res.lcos is not None
    assert res.lcos.lcos_usd_per_mwh is not None
    assert res.effective_cost_curve is not None
    assert res.effective_cost_curve[0]["lkr_per_kwh"] == pytest.approx(15.0)


def test_economics_respects_contract_years_horizon() -> None:
    """A contract shorter than the project life caps the cashflow horizon."""
    cfg = _capacity_cfg(revenue_overrides={"contract_years": 10})
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)[0]
    assert res.horizon_years == 10
    # capex + 10 operating years.
    assert len(res.cashflow_lkr) == 11


def test_economics_as_dict_is_serialisable() -> None:
    """as_dict() yields a plain JSON-serialisable structure for report packs."""
    res = compute_bess_project_economics(
        _capacity_cfg(), discount_rate=0.10, project_years=15
    )[0]
    d = res.as_dict()
    assert d["technology"] == "bess_unit"
    assert d["landed_capex"]["landed_capex_lkr"] == pytest.approx(1_500_000_000.0)
    assert isinstance(d["cashflow_lkr"], list)
    assert d["lcos"] is not None
    import json

    json.dumps(d)  # must not raise


def test_economics_energy_from_power_times_duration() -> None:
    """The economics energy basis also falls back to power_mw x duration_h."""
    cfg = _capacity_cfg(
        economics_overrides={
            "charging": {"tariff_lkr_per_kwh": 5.0, "round_trip_efficiency": 0.85}
        }
    )
    del cfg["generation"]["technologies"]["bess_unit"]["energy_mwh"]
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=1)[0]
    # charge energy = (10 x 4) x 400 / 0.85 MWh -> x1000 x 5 LKR/kWh
    assert res.charging_cost_lkr[0] == pytest.approx((16_000.0 / 0.85) * 1000.0 * 5.0)


def test_economics_skips_energy_tariff_bess_in_multi_bess() -> None:
    """A mixed scenario computes economics only for the capacity-charge BESS."""
    cfg = _capacity_cfg()
    cfg["generation"]["technologies"]["night_bess"] = {
        "type": "bess",
        "power_mw": 5.0,
        "energy_mwh": 20.0,
        "duration_h": 4.0,
        "revenue": {"model": "energy_tariff", "tariff_lkr_per_kwh": 45.80},
    }
    results = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)
    assert results is not None
    assert [r.technology for r in results] == ["bess_unit"]


def test_economics_uses_fx_routine_not_hardcoded() -> None:
    """The FX rate comes from the config's fx block (the shared routine), not a literal."""
    cfg = _capacity_cfg(fx_start=350.0)
    res = compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)[0]
    assert res.landed_capex.fx_rate_lkr_per_usd == 350.0
    assert res.landed_capex.landed_capex_lkr == pytest.approx(5_000_000.0 * 350.0)


def test_economics_requires_fx_block() -> None:
    """No FX block => the shared FX routine fails loud (CESSPIT, FIN-6)."""
    cfg = _capacity_cfg()
    del cfg["fx"]
    with pytest.raises(ValueError, match="FX configuration"):
        compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)


@pytest.mark.parametrize("bad_rate", [-1.0, -2.0, float("nan"), float("inf")])
def test_economics_rejects_bad_discount_rate(bad_rate: float) -> None:
    """A non-finite / <= -1 discount rate raises."""
    with pytest.raises(ValueError, match="discount_rate"):
        compute_bess_project_economics(
            _capacity_cfg(), discount_rate=bad_rate, project_years=15
        )


def test_economics_rejects_bad_project_years() -> None:
    """A non-positive project horizon raises."""
    with pytest.raises(ValueError, match="project_years"):
        compute_bess_project_economics(
            _capacity_cfg(), discount_rate=0.10, project_years=0
        )


def test_warranty_schedule_bad_year_raises() -> None:
    """A non-positive / fractional warranty year is a config error."""
    cfg = _capacity_cfg(
        economics_overrides={"warranty_schedule": [{"year": 0, "lkr": 1.0}]}
    )
    with pytest.raises(ValueError, match="warranty_schedule"):
        compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)


def test_warranty_schedule_negative_lkr_raises() -> None:
    """A negative warranty draw is a config error."""
    cfg = _capacity_cfg(
        economics_overrides={"warranty_schedule": [{"year": 3, "lkr": -1.0}]}
    )
    with pytest.raises(ValueError, match="lkr"):
        compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)


def test_warranty_schedule_non_list_raises() -> None:
    """A non-list warranty schedule is a config error."""
    cfg = _capacity_cfg(economics_overrides={"warranty_schedule": {"year": 3}})
    with pytest.raises(ValueError, match="warranty_schedule"):
        compute_bess_project_economics(cfg, discount_rate=0.10, project_years=15)
