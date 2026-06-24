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
    bess_capacity_charge_lkr_for_year,
    resolve_bess_specs,
)


def _cfg(**revenue_overrides) -> dict:
    """A one-BESS config; revenue kwargs override the capacity-charge defaults."""
    revenue = {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 2_000_000}
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
    ok = {"generation": {"technologies": {"b": {
        "type": "bess", "power_mw": 10.0, "energy_mwh": 40.0, "duration_h": 4.0,
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1}}}}}
    assert resolve_bess_specs(ok) is not None
    bad = {"generation": {"technologies": {"b": {
        "type": "bess", "power_mw": 10.0, "energy_mwh": 80.0, "duration_h": 4.0,  # 80 != 40
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1}}}}}
    with pytest.raises(ValueError, match="reconcile"):
        resolve_bess_specs(bad)


def test_bess_revenue_model_without_type_fails_loud():
    """A block declaring a BESS revenue model but not typed bess is a mis-key that would
    silently earn zero — it must raise."""
    cfg = {"generation": {"technologies": {"b": {
        "power_mw": 10.0,  # no type: bess
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1}}}}}
    with pytest.raises(ValueError, match="not type"):
        resolve_bess_specs(cfg)


@pytest.mark.parametrize(
    "block, match",
    [
        ({"type": "bess", "revenue": {"model": "capacity_charge",
          "capacity_charge_lkr_per_mw_month": 1}}, "power_mw"),
        ({"type": "bess", "power_mw": 10}, "revenue"),
        ({"type": "bess", "power_mw": 10, "revenue": {"model": "arbitrage"}}, "model"),
        ({"type": "bess", "power_mw": 10, "revenue": {"model": "capacity_charge"}},
         "capacity_charge_lkr_per_mw_month"),
    ],
)
def test_malformed_bess_fails_loud(block, match):
    cfg = {"generation": {"technologies": {"b": block}}}
    with pytest.raises(ValueError, match=match):
        resolve_bess_specs(cfg)


def test_capacity_charge_is_the_only_supported_model():
    assert SUPPORTED_BESS_REVENUE_MODELS == ("capacity_charge",)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_power_mw_is_rejected(bad):
    cfg = {"generation": {"technologies": {"b": {"type": "bess", "power_mw": bad,
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1}}}}}
    with pytest.raises(ValueError, match="power_mw"):
        resolve_bess_specs(cfg)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_non_finite_capacity_charge_rate_is_rejected(bad):
    cfg = {"generation": {"technologies": {"b": {"type": "bess", "power_mw": 10,
        "revenue": {"model": "capacity_charge", "capacity_charge_lkr_per_mw_month": bad}}}}}
    with pytest.raises(ValueError, match="capacity_charge_lkr_per_mw_month"):
        resolve_bess_specs(cfg)


# ── the annual charge ───────────────────────────────────────────────────────────


def test_charge_is_r_times_mw_times_12():
    specs = resolve_bess_specs(_cfg(contract_years=15))
    assert bess_capacity_charge_lkr_for_year(specs, 0) == pytest.approx(2_000_000 * 10 * 12)


def test_charge_is_flat_across_the_contract_then_zero():
    specs = resolve_bess_specs(_cfg(contract_years=15))
    full = 2_000_000 * 10 * 12
    assert bess_capacity_charge_lkr_for_year(specs, 0) == pytest.approx(full)
    assert bess_capacity_charge_lkr_for_year(specs, 14) == pytest.approx(full)  # last yr
    assert bess_capacity_charge_lkr_for_year(specs, 15) == 0.0  # contract expired


def test_charge_factors_derate():
    specs = resolve_bess_specs(_cfg(availability_factor=0.9, dispatchable_ratio=0.8))
    assert bess_capacity_charge_lkr_for_year(specs, 0) == pytest.approx(
        2_000_000 * 10 * 12 * 0.9 * 0.8
    )


def test_none_and_empty_are_zero():
    assert bess_capacity_charge_lkr_for_year(None, 0) == 0.0
    assert bess_capacity_charge_lkr_for_year([], 3) == 0.0


def test_multiple_bess_are_summed():
    cfg = {"generation": {"technologies": {
        "b1": {"type": "bess", "power_mw": 10, "revenue": {
            "model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 1_000_000}},
        "b2": {"type": "bess", "power_mw": 5, "revenue": {
            "model": "capacity_charge", "capacity_charge_lkr_per_mw_month": 2_000_000}},
    }}}
    specs = resolve_bess_specs(cfg)
    assert bess_capacity_charge_lkr_for_year(specs, 0) == pytest.approx(
        (10 * 1_000_000 + 5 * 2_000_000) * 12
    )
