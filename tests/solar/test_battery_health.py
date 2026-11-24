"""Tests for the solar + BESS battery's fade and augmentation (#1578 L-11).

``TEST-01`` oracles that did not originate in this change:

* closed forms: a linear fade ``1 - f (y - 1)`` and the first year it falls below the
  threshold, ``floor(0.2 / f) + 2`` for an 80% threshold; the reserve's all-in share
  ``8.00 / (1 - 0.10)`` from the pricing config's own build-up lines;
* ``finance.bess_revenue.mdsc_soh_for_year`` (the engine's state of health) and
  ``finance.bess_revenue.bess_augmentation_capex_lkr_for_year`` (its augmentation cash):
  an event written by the sizing changes the engine's cash in its year only, and leaves the
  engine's BESS revenue unchanged in every year;
* the OEM curve itself, when ``DUTCHBAY_BLUE_WHALE_PRIVATE_SOH_CURVE`` names the private
  file (outside the repository; the curve is never committed): the committed rate is the
  rate it gives, and the rate and the curve cross 80% in the same year.

No test here runs the engine more than a handful of times (``TEST-03``).
"""

from __future__ import annotations

import dataclasses
import math
import os
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from finance.bess_revenue import (
    bess_augmentation_capex_lkr_for_year,
    mdsc_soh_for_year,
)
from solar_resource import pv_bess_dispatch as pbd
from solar_resource import pv_bess_sizing as sz

REPO_ROOT = Path(__file__).resolve().parents[2]
SOLAR_BESS_SCENARIO = REPO_ROOT / "scenarios" / "blue_whale_solar_bess_lot5b_2026.yaml"
PRICING_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_pricing.yaml"
PR3_CONF = REPO_ROOT / "conf" / "blue_whale_pv_bess_sizing.yaml"
PRIVATE_ENV = "DUTCHBAY_BLUE_WHALE_PRIVATE_SOH_CURVE"


def _yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _health_raw() -> Dict[str, Any]:
    return dict(_yaml(SOLAR_BESS_SCENARIO)["solar_storage_sizing"]["battery_health"])


def _health(**kw: Any) -> sz.BatteryHealth:
    return dataclasses.replace(sz.BatteryHealth.from_mapping(_health_raw()), **kw)


def test_committed_block_parses_and_bad_blocks_are_refused() -> None:
    h = sz.BatteryHealth.from_mapping(_health_raw())
    assert (h.augment_below_soh, h.restore_to_soh) == (0.80, 1.0)
    assert h.replaces_price_reserve is True
    assert 0.0 < h.fade_pct_per_year < 5.0
    for change, match in (
        ({"augment_below_soh": 1.0}, "augment_below_soh < restore_to_soh"),
        ({"augment_below_soh": 0.0}, "0 < augment_below_soh"),
        ({"restore_to_soh": 1.2}, "restore_to_soh <= 1"),
        ({"fade_pct_per_year": -0.1}, "out of range"),
        ({"augmentation_usd_per_kwh": float("nan")}, "out of range"),
        ({"replaces_price_reserve": "yes"}, "boolean"),
        ({"fade_basis": " "}, "non-empty"),
        ({"extra": 1}, "unknown keys"),
    ):
        with pytest.raises(ValueError, match=match):
            sz.BatteryHealth.from_mapping({**_health_raw(), **change})
    raw = _health_raw()
    del raw["augmentation_basis"]
    with pytest.raises(ValueError, match="missing keys"):
        sz.BatteryHealth.from_mapping(raw)


@pytest.mark.parametrize("fade_pct", [1.5533, 1.3, 2.4, 3.7])
def test_soh_path_is_linear_and_augments_before_the_first_year_below_80(
    fade_pct: float,
) -> None:
    h = _health()
    f = fade_pct / 100.0
    soh, events = h.soh_path(f, 20)
    assert len(soh) == 20 and soh[0] == 1.0
    # Closed form: year y (before any event) carries 1 - f (y - 1); it first falls below
    # 0.80 in year floor(0.2 / f) + 2, which is the first event.
    first = math.floor(0.2 / f) + 2
    assert events[0][0] == first
    for year in range(1, first):
        assert soh[year - 1] == pytest.approx(1.0 - f * (year - 1), abs=1e-12)
    assert events[0][1] == pytest.approx(1.0 - (1.0 - f * (first - 1)), abs=1e-12)
    assert soh[first - 1] == 1.0
    # The battery re-fades from the restored SoH; every event restores the nameplate and
    # no year runs below the threshold.
    assert all(s >= 0.80 for s in soh)
    for (year, added), nxt in zip(events, events[1:], strict=False):
        assert nxt[0] - year == first - 1
        assert added == pytest.approx(nxt[1], abs=1e-12)
    assert len(events) == len([y for y in range(1, 21) if soh[y - 1] == 1.0]) - 1


def test_soh_path_without_fade_never_augments_and_refuses_negative_fade() -> None:
    soh, events = _health().soh_path(0.0, 20)
    assert soh == [1.0] * 20 and events == []
    with pytest.raises(ValueError, match="non-negative"):
        _health().soh_path(-0.001, 20)


def test_augmentation_boundary_is_strictly_below_80() -> None:
    """The trigger is "below 80%": a year at or just above 0.80 is not augmented.

    Closed form: year 14 starts at ``1 - 13 f``. At 0.801 the battery runs year 14 unaugmented;
    at 0.799 the event falls in year 14. A year that starts at exactly 0.80 (``f = 0.1``,
    year 3; ``1 - 0.1 * 2`` is exactly 0.8 in binary floating point) is not augmented either,
    and the event falls in the next year.
    """
    h = _health()
    soh, events = h.soh_path(0.199 / 13.0, 14)
    assert soh[13] == pytest.approx(0.801, abs=1e-12)
    assert events == []
    soh, events = h.soh_path(0.201 / 13.0, 14)
    assert [year for year, _ in events] == [14]
    assert events[0][1] == pytest.approx(0.201, abs=1e-12)
    assert soh[13] == 1.0
    soh, events = h.soh_path(0.1, 5)
    assert soh[2] == 0.8
    assert events[0][0] == 4


def test_fade_rate_from_a_synthetic_curve() -> None:
    curve = [100.0, 97.0, 95.0, 92.0, 90.0, 88.0, 86.0, 84.0, 82.0, 80.5, 79.0]
    got = sz.fade_rate_from_soh_curve(curve)
    assert got["fade_pct_per_year"] == pytest.approx(2.1)
    assert got["curve_years"] == 10
    assert got["curve_first_end_of_year_below_80_pct"] == 10
    # 100 - 2.1 k < 80 first at k = 10.
    assert got["line_first_end_of_year_below_80_pct"] == 10
    with pytest.raises(ValueError, match="at least one year"):
        sz.fade_rate_from_soh_curve([100.0])


def test_reserve_share_is_the_build_up_reserve_grossed_up_by_land() -> None:
    raw = _yaml(PRICING_CONF)["bess"]
    p = sz.Pricing.from_mapping(_yaml(PRICING_CONF))
    expected = raw["augmentation_reserve_usd_per_kwh_base"] / (
        1.0 - raw["land_and_auxiliaries_share_base"]
    )
    assert expected == pytest.approx(8.00 / 0.90)
    assert p.bess_augmentation_reserve_usd_per_kwh == pytest.approx(expected)
    # Below the lowest price, so every draw stays positive after it is removed.
    assert p.bess_augmentation_reserve_usd_per_kwh < p.bess_usd_per_kwh.low


def test_pr3_sizing_config_carries_no_battery_health() -> None:
    # PR 3's run keeps its linear residual fade with the reserve left in the price.
    assert "battery_health" not in _yaml(PR3_CONF)
    assert "battery_health" not in sz.SIZING_KEYS
    assert "battery_health" in sz.PROJECT_SIZING_KEYS


def _rep(fade: float) -> pbd.EngineRepresentation:
    return pbd.EngineRepresentation(
        solar_capacity_mw=3.5,
        solar_capacity_factor=0.2,
        solar_aep_gwh=6.0,
        solar_degradation_pct=0.4,
        bess_tariff_lkr_per_kwh=29.38,
        bess_cycles_per_year=400.0,
        bess_round_trip_efficiency=0.85,
        bess_contract_years=15,
        bess_mdsc_fade_pct_annual=fade,
        tariff_lkr_per_kwh=20.0,
        project_capacity_mw=3.5,
        project_capacity_factor=0.2,
        dispatcher_revenue_lkr=[],
        engine_revenue_lkr=[],
        max_later_year_gap_pct=0.0,
    )


@pytest.mark.parametrize("fade", [0.011, 0.0, -0.002])
def test_engine_event_moves_cash_only_in_its_year_and_not_the_revenue(
    fade: float,
) -> None:
    from tests.solar.test_solar_bess_project_sizing import _context

    ctx = _context()

    class _Point:  # the fields engine_overrides reads
        bess_power_mw = 0.1
        bess_energy_mwh = 0.4
        dc_mwp = 4.01464

    rep = _rep(fade)
    common = dict(
        point=_Point(),
        pv_capex_usd=2.4e6,
        bess_capex_usd=52740.0,
        opex_usd_per_year=1.9e5,
    )
    plain = sz.engine_overrides(ctx, rep, **common)  # type: ignore[arg-type]
    key = "generation.technologies.bess_1.revenue.augmentation_schedule"
    assert key not in plain
    empty = sz.engine_overrides(ctx, rep, augmentation_capex_usd={}, **common)  # type: ignore[arg-type]
    assert empty[key] == []
    with_event = sz.engine_overrides(
        ctx,
        rep,
        augmentation_capex_usd={14: 8363.9},
        **common,  # type: ignore[arg-type]
    )
    (event,) = with_event[key]
    assert (event["year"], event["capex_usd"]) == (14, 8363.9)
    spec = {"mdsc_fade_pct_annual": fade, "soh_model": "geometric"}
    spec_event = {
        **spec,
        "augmentation_events": [{**event, "restore_to_soh": event["restore_to_soh"]}],
    }
    for y in range(20):
        assert mdsc_soh_for_year(spec_event, y) == pytest.approx(
            mdsc_soh_for_year(spec, y), rel=1e-12, abs=1e-15
        ), y
        cash = bess_augmentation_capex_lkr_for_year([spec_event], y, 300.0)
        assert cash == (pytest.approx(8363.9 * 300.0) if y == 13 else 0.0), y


def test_unit_cash_flow_pays_the_augmentation_in_its_operating_year() -> None:
    base = sz.unit_pretax_cashflows_usd(
        [3.0e7] * 20,
        capex_usd=1.0e6,
        opex_usd_year1=1.0e4,
        opex_escalation_pct=3.0,
        lkr_per_usd=300.0,
        construction_years=2,
    )
    aug = sz.unit_pretax_cashflows_usd(
        [3.0e7] * 20,
        capex_usd=1.0e6,
        opex_usd_year1=1.0e4,
        opex_escalation_pct=3.0,
        lkr_per_usd=300.0,
        construction_years=2,
        augmentation_capex_usd={14: 5000.0},
    )
    diff = [a - b for a, b in zip(aug, base, strict=True)]
    # t=0 capex, two build years, then operating year 14 at index 2 + 14.
    assert diff[2 + 14] == pytest.approx(-5000.0)
    assert sum(abs(d) for i, d in enumerate(diff) if i != 16) == 0.0


def test_shifted_case_moves_the_battery_health_inputs() -> None:
    from tests.solar.test_solar_bess_project_sizing import _base_trial, _context

    ctx = _context()
    assert ctx.battery_health is not None
    base = _base_trial(ctx)
    c, _ = sz.shifted_case(ctx, base, {"fade_pct_per_year": 2.0}, where="t")
    assert c.battery_health is not None and c.battery_health.fade_pct_per_year == 2.0
    assert c.battery_health.augmentation_usd_per_kwh == (
        ctx.battery_health.augmentation_usd_per_kwh
    )
    c, _ = sz.shifted_case(ctx, base, {"augmentation_usd_per_kwh": 50.0}, where="t")
    assert c.battery_health is not None
    assert c.battery_health.augmentation_usd_per_kwh == 50.0
    assert c.battery_health.fade_pct_per_year == ctx.battery_health.fade_pct_per_year
    with pytest.raises(ValueError, match="battery_health block"):
        sz.shifted_case(
            dataclasses.replace(ctx, battery_health=None),
            base,
            {"fade_pct_per_year": 2.0},
            where="t",
        )
    with pytest.raises(ValueError, match="out of range"):
        sz.shifted_case(ctx, base, {"augmentation_usd_per_kwh": -1.0}, where="t")


@pytest.mark.skipif(
    not os.environ.get(PRIVATE_ENV), reason="private SoH curve not supplied"
)
def test_committed_rate_is_the_private_curves_rate() -> None:
    path = Path(os.environ[PRIVATE_ENV]).resolve()
    assert REPO_ROOT.resolve() not in path.parents, "the curve must stay outside"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["schema_version"] == "blue_whale_private_soh_curve_v1"
    got = sz.fade_rate_from_soh_curve(raw["soh_pct"])
    committed = _health_raw()["fade_pct_per_year"]
    assert committed == pytest.approx(got["fade_pct_per_year"], abs=5e-5)
    assert (
        got["curve_first_end_of_year_below_80_pct"]
        == got["line_first_end_of_year_below_80_pct"]
    )
    # The sizing augments before the year after the crossing.
    _, events = _health().soh_path(committed / 100.0, 20)
    assert events[0][0] == got["curve_first_end_of_year_below_80_pct"] + 1
