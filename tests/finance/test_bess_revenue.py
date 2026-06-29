"""Unit tests for ``finance.bess_revenue`` — BESS capacity-charge revenue.

Pins the capacity-charge model for the CEB standalone-BESS tender: a ``type: bess``
technology earns ``R x power_mw x 12 x availability_factor x dispatchable_ratio``
(LKR), flat over its contract term — NOT generation revenue. Fail-loud on a mis-keyed
BESS block (CESSPIT), and ``None``/``0.0`` when no BESS is present so wind/solar runs
stay byte-identical.
"""

from __future__ import annotations

import pytest

from finance.bess_revenue import (
    SUPPORTED_BESS_REVENUE_MODELS,
    bess_augmentation_capex_lkr_for_year,
    bess_revenue_lkr_for_year,
    mdsc_soh_for_year,
    resolve_bess_specs,
)


def _cfg(**revenue_overrides) -> dict:
    """A one-BESS config; revenue kwargs override the capacity-charge defaults."""
    revenue = {
        "model": "capacity_charge",
        "capacity_charge_lkr_per_mw_month": 2_000_000,
    }
    revenue.update(revenue_overrides)
    return {
        "generation": {
            "technologies": {
                "bess_unit": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "revenue": revenue,
                }
            }
        }
    }


# ── resolution ────────────────────────────────────────────────────────────────


def test_none_without_generation_block():
    assert resolve_bess_specs({}) is None
    assert resolve_bess_specs({"project": {"capacity_mw": 10}}) is None


def test_none_when_only_generation_techs():
    cfg = {"generation": {"technologies": {"wind": {"capacity_factor": 0.34}}}}
    assert resolve_bess_specs(cfg) is None


def test_only_explicit_type_bess_is_picked_up():
    # a storage-shaped block WITHOUT an explicit type: bess is not a BESS here
    cfg = {"generation": {"technologies": {"b": {"power_mw": 10, "energy_mwh": 40}}}}
    assert resolve_bess_specs(cfg) is None


def test_resolves_spec_fields():
    specs = resolve_bess_specs(_cfg(contract_years=15))
    assert specs is not None and len(specs) == 1
    s = specs[0]
    assert s["technology"] == "bess_unit"
    assert s["power_mw"] == 10.0
    assert s["r_lkr_per_mw_month"] == 2_000_000
    assert s["contract_years"] == 15


def test_factor_and_contract_defaults():
    s = resolve_bess_specs(_cfg())[0]
    assert s["availability_factor"] == 1.0
    assert s["dispatchable_ratio"] == 1.0
    assert s["contract_years"] is None  # paid for full project life when unset


@pytest.mark.parametrize("field", ["availability_factor", "dispatchable_ratio"])
@pytest.mark.parametrize("bad", [1.5, -0.2, 97, "x"])
def test_derate_factors_out_of_range_fail_loud(field, bad):
    """Both downside levers must be in [0, 1] — a mis-keyed value (97 vs 0.97, or a
    stray sign) raises rather than silently inflating/negating the capacity charge."""
    with pytest.raises(ValueError, match=field):
        resolve_bess_specs(_cfg(**{field: bad}))


@pytest.mark.parametrize("field", ["availability_factor", "dispatchable_ratio"])
def test_derate_factors_accept_valid_range(field):
    spec = resolve_bess_specs(_cfg(**{field: 0.85}))[0]
    assert spec[field] == 0.85


@pytest.mark.parametrize("bad", [0, -5, 2.5, "ten"])
def test_contract_years_must_be_positive_whole_number(bad):
    with pytest.raises(ValueError, match="contract_years"):
        resolve_bess_specs(_cfg(contract_years=bad))


def test_energy_duration_cross_assert():
    # power 10 x duration 4 = 40 MWh -> ok; a mismatched energy_mwh raises
    ok = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "duration_h": 4.0,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1,
                    },
                }
            }
        }
    }
    assert resolve_bess_specs(ok) is not None
    bad = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 80.0,
                    "duration_h": 4.0,  # 80 != 40
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1,
                    },
                }
            }
        }
    }
    with pytest.raises(ValueError, match="reconcile"):
        resolve_bess_specs(bad)


def test_bess_revenue_model_without_type_fails_loud():
    """A block declaring a BESS revenue model but not typed bess is a mis-key that would
    silently earn zero — it must raise."""
    cfg = {
        "generation": {
            "technologies": {
                "b": {
                    "power_mw": 10.0,  # no type: bess
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1,
                    },
                }
            }
        }
    }
    with pytest.raises(ValueError, match="not type"):
        resolve_bess_specs(cfg)


@pytest.mark.parametrize(
    "block, match",
    [
        (
            {
                "type": "bess",
                "revenue": {
                    "model": "capacity_charge",
                    "capacity_charge_lkr_per_mw_month": 1,
                },
            },
            "power_mw",
        ),
        ({"type": "bess", "power_mw": 10}, "revenue"),
        ({"type": "bess", "power_mw": 10, "revenue": {"model": "arbitrage"}}, "model"),
        (
            {"type": "bess", "power_mw": 10, "revenue": {"model": "capacity_charge"}},
            "capacity_charge_lkr_per_mw_month",
        ),
    ],
)
def test_malformed_bess_fails_loud(block, match):
    cfg = {"generation": {"technologies": {"b": block}}}
    with pytest.raises(ValueError, match=match):
        resolve_bess_specs(cfg)


def test_supported_models():
    assert SUPPORTED_BESS_REVENUE_MODELS == ("capacity_charge", "energy_tariff")


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_power_mw_is_rejected(bad):
    cfg = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": bad,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1,
                    },
                }
            }
        }
    }
    with pytest.raises(ValueError, match="power_mw"):
        resolve_bess_specs(cfg)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_capacity_charge_rate_is_rejected(bad):
    cfg = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": 10,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": bad,
                    },
                }
            }
        }
    }
    with pytest.raises(ValueError, match="capacity_charge_lkr_per_mw_month"):
        resolve_bess_specs(cfg)


# ── the annual charge ───────────────────────────────────────────────────────────


def test_charge_is_r_times_mw_times_12():
    specs = resolve_bess_specs(_cfg(contract_years=15))
    assert bess_revenue_lkr_for_year(specs, 0) == pytest.approx(2_000_000 * 10 * 12)


def test_charge_is_flat_across_the_contract_then_zero():
    specs = resolve_bess_specs(_cfg(contract_years=15))
    full = 2_000_000 * 10 * 12
    assert bess_revenue_lkr_for_year(specs, 0) == pytest.approx(full)
    assert bess_revenue_lkr_for_year(specs, 14) == pytest.approx(full)  # last yr
    assert bess_revenue_lkr_for_year(specs, 15) == 0.0  # contract expired


def test_charge_factors_derate():
    specs = resolve_bess_specs(_cfg(availability_factor=0.9, dispatchable_ratio=0.8))
    assert bess_revenue_lkr_for_year(specs, 0) == pytest.approx(
        2_000_000 * 10 * 12 * 0.9 * 0.8
    )


def test_none_and_empty_are_zero():
    assert bess_revenue_lkr_for_year(None, 0) == 0.0
    assert bess_revenue_lkr_for_year([], 3) == 0.0


def test_multiple_bess_are_summed():
    cfg = {
        "generation": {
            "technologies": {
                "b1": {
                    "type": "bess",
                    "power_mw": 10,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 1_000_000,
                    },
                },
                "b2": {
                    "type": "bess",
                    "power_mw": 5,
                    "revenue": {
                        "model": "capacity_charge",
                        "capacity_charge_lkr_per_mw_month": 2_000_000,
                    },
                },
            }
        }
    }
    specs = resolve_bess_specs(cfg)
    assert bess_revenue_lkr_for_year(specs, 0) == pytest.approx(
        (10 * 1_000_000 + 5 * 2_000_000) * 12
    )


# ── energy_tariff model (night-peak Solar+BESS) ─────────────────────────────────


def _energy_cfg(**revenue_overrides) -> dict:
    revenue = {
        "model": "energy_tariff",
        "tariff_lkr_per_kwh": 45.80,
        "cycles_per_year": 365,
        "round_trip_efficiency": 0.90,
    }
    revenue.update(revenue_overrides)
    return {
        "generation": {
            "technologies": {
                "bess_pv": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "revenue": revenue,
                }
            }
        }
    }


def test_energy_tariff_revenue_formula():
    specs = resolve_bess_specs(_energy_cfg(contract_years=10))
    assert specs[0]["model"] == "energy_tariff"
    # energy_mwh × 1000 × cycles × RTE × availability × tariff
    expected = 40.0 * 1000 * 365 * 0.90 * 1.0 * 45.80
    assert bess_revenue_lkr_for_year(specs, 0) == pytest.approx(expected)
    assert bess_revenue_lkr_for_year(specs, 9) == pytest.approx(expected)  # last yr
    assert bess_revenue_lkr_for_year(specs, 10) == 0.0  # contract expired


def test_energy_tariff_defaults_cycles_and_rte():
    s = resolve_bess_specs(
        {
            "generation": {
                "technologies": {
                    "b": {
                        "type": "bess",
                        "power_mw": 10.0,
                        "energy_mwh": 40.0,
                        "revenue": {
                            "model": "energy_tariff",
                            "tariff_lkr_per_kwh": 45.80,
                        },
                    }
                }
            }
        }
    )[0]
    assert s["cycles_per_year"] == 365.0  # one cycle/day default
    assert s["round_trip_efficiency"] == 0.90  # default RTE


@pytest.mark.parametrize(
    "block, match",
    [
        (
            {"type": "bess", "power_mw": 10, "revenue": {"model": "energy_tariff"}},
            "energy_mwh",
        ),
        (
            {
                "type": "bess",
                "power_mw": 10,
                "energy_mwh": 40,
                "revenue": {"model": "energy_tariff"},
            },
            "tariff_lkr_per_kwh",
        ),
        (
            {
                "type": "bess",
                "power_mw": 10,
                "energy_mwh": 40,
                "revenue": {
                    "model": "energy_tariff",
                    "tariff_lkr_per_kwh": 45.8,
                    "cycles_per_year": 0,
                },
            },
            "cycles_per_year",
        ),
        (
            {
                "type": "bess",
                "power_mw": 10,
                "energy_mwh": 40,
                "revenue": {
                    "model": "energy_tariff",
                    "tariff_lkr_per_kwh": 45.8,
                    "round_trip_efficiency": 1.5,
                },
            },
            "round_trip_efficiency",
        ),
    ],
)
def test_energy_tariff_malformed_fails_loud(block, match):
    with pytest.raises(ValueError, match=match):
        resolve_bess_specs({"generation": {"technologies": {"b": block}}})


# ── MDSC degradation (#470 BESS-1a) ─────────────────────────────────────────────


def test_mdsc_defaults_are_no_fade():
    # Absent keys -> no fade (byte-identical) + the documented 0.70 floor default.
    spec = resolve_bess_specs(_cfg())[0]
    assert spec["mdsc_fade_pct_annual"] == 0.0
    assert spec["mdsc_floor_soh"] == pytest.approx(0.70)


def test_mdsc_soh_identity_when_no_fade():
    spec = resolve_bess_specs(_cfg())[0]
    assert all(mdsc_soh_for_year(spec, t) == 1.0 for t in (0, 1, 5, 10, 20))


def test_mdsc_soh_declines_with_fade():
    spec = resolve_bess_specs(_cfg(mdsc_fade_pct_annual=0.011))[0]
    assert mdsc_soh_for_year(spec, 0) == pytest.approx(1.0)  # year 1 undiminished
    assert mdsc_soh_for_year(spec, 1) == pytest.approx(0.989)
    assert mdsc_soh_for_year(spec, 10) == pytest.approx(0.989**10)
    assert mdsc_soh_for_year(spec, 5) < mdsc_soh_for_year(spec, 1)


def test_mdsc_soh_floored():
    # A steep fade hits the floor and stops there.
    spec = resolve_bess_specs(_cfg(mdsc_fade_pct_annual=0.10, mdsc_floor_soh=0.80))[0]
    assert mdsc_soh_for_year(spec, 50) == pytest.approx(0.80)


def test_revenue_flat_when_no_fade_byte_identical():
    specs = resolve_bess_specs(_cfg())
    y0 = bess_revenue_lkr_for_year(specs, 0)
    assert all(bess_revenue_lkr_for_year(specs, t) == y0 for t in (1, 5, 10))


def test_revenue_declines_with_fade():
    specs = resolve_bess_specs(_cfg(mdsc_fade_pct_annual=0.011))
    y0 = bess_revenue_lkr_for_year(specs, 0)
    y10 = bess_revenue_lkr_for_year(specs, 10)
    assert y10 < y0
    assert y10 == pytest.approx(y0 * (0.989**10))


@pytest.mark.parametrize("bad", [1.0, 1.1, -0.1])
def test_fade_rate_out_of_range_fails_loud(bad):
    with pytest.raises(ValueError, match="mdsc_fade_pct_annual"):
        resolve_bess_specs(_cfg(mdsc_fade_pct_annual=bad))


def test_floor_soh_out_of_range_fails_loud():
    with pytest.raises(ValueError, match="mdsc_floor_soh"):
        resolve_bess_specs(_cfg(mdsc_floor_soh=1.5))


def test_fade_applies_to_energy_tariff_model_too():
    cfg = {
        "generation": {
            "technologies": {
                "b": {
                    "type": "bess",
                    "power_mw": 10.0,
                    "energy_mwh": 40.0,
                    "revenue": {
                        "model": "energy_tariff",
                        "tariff_lkr_per_kwh": 45.8,
                        "mdsc_fade_pct_annual": 0.005,
                    },
                }
            }
        }
    }
    specs = resolve_bess_specs(cfg)
    assert bess_revenue_lkr_for_year(specs, 10) < bess_revenue_lkr_for_year(specs, 0)


# ── Augmentation (#470 BESS-1b) ─────────────────────────────────────────────────


def test_augmentation_default_is_empty_byte_identical():
    spec = resolve_bess_specs(_cfg())[0]
    assert spec["augmentation_events"] == []
    # No schedule -> no capex any year, soh unaffected by augmentation.
    assert bess_augmentation_capex_lkr_for_year([spec], 9, 300.0) == 0.0


def test_augmentation_schedule_parsed_and_sorted():
    spec = resolve_bess_specs(
        _cfg(
            augmentation_schedule=[
                {"year": 10, "capex_usd": 5_000_000},
                {"year": 5, "capex_usd": 1_000_000, "restore_to_soh": 0.95},
            ]
        )
    )[0]
    evs = spec["augmentation_events"]
    assert [e["year"] for e in evs] == [5, 10]  # sorted ascending
    assert evs[0]["restore_to_soh"] == 0.95
    assert evs[1]["restore_to_soh"] == 1.0  # default full restore


def test_augmentation_capex_lands_in_the_event_year_only():
    specs = resolve_bess_specs(
        _cfg(augmentation_schedule=[{"year": 10, "capex_usd": 5_000_000}])
    )
    # Year 10 is 0-based index 9; capex = 5e6 USD * fx.
    assert bess_augmentation_capex_lkr_for_year(specs, 9, 300.0) == pytest.approx(
        5_000_000 * 300.0
    )
    assert bess_augmentation_capex_lkr_for_year(specs, 8, 300.0) == 0.0
    assert bess_augmentation_capex_lkr_for_year(specs, 10, 300.0) == 0.0


def test_augmentation_restores_soh():
    spec = resolve_bess_specs(
        _cfg(
            mdsc_fade_pct_annual=0.05,
            augmentation_schedule=[{"year": 11, "capex_usd": 5_000_000}],
        )
    )[0]
    soh_y10 = mdsc_soh_for_year(spec, 9)  # operating year 10, pre-augmentation
    soh_y11 = mdsc_soh_for_year(spec, 10)  # operating year 11, the augmentation year
    assert soh_y11 == pytest.approx(1.0)  # restored to full at the event
    assert soh_y11 > soh_y10  # the curve jumps back up
    # ...then re-fades from the restore point.
    assert mdsc_soh_for_year(spec, 12) < soh_y11


@pytest.mark.parametrize(
    "bad, match",
    [
        ([{"year": 0, "capex_usd": 1}], "year"),
        ([{"year": 2.5, "capex_usd": 1}], "year"),
        ([{"year": 5, "capex_usd": -1}], "capex_usd"),
        ([{"year": 5, "capex_usd": 1, "restore_to_soh": 1.5}], "restore_to_soh"),
        ({"year": 5, "capex_usd": 1}, "must be a list"),
    ],
)
def test_augmentation_schedule_malformed_fails_loud(bad, match):
    with pytest.raises(ValueError, match=match):
        resolve_bess_specs(_cfg(augmentation_schedule=bad))
