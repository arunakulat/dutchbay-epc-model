"""Grid-FREE coverage for the D5a shared BESS SoC + reserve-split model (#879).

These tests import NO grid library (``pandapower`` / ``andes`` are ABSENT in the default
venv) and are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage
lane and carry the real coverage for :mod:`analytics.grid.capabilities.bess_soc`. The SoC
model is PURE energy accounting (no load-flow / dynamics), so it has NO grid-only lines at
all; there is no ``grid``-marked companion needed.

They exercise:

  * ``bess_soc_state`` — usable-energy + DISCHARGE/CHARGE headroom at a SoC, the SoH
    resolver (explicit ``soh_fraction`` / ``soh_curve`` end-of-life / reference_year), and
    every STRICT ValueError branch (non-storage type, missing/ill-formed nameplate, bad
    SoH, bad SoC window, out-of-window SoC);
  * ``split_reserves`` — the FOUNDATIONAL no-double-count invariant: a feasible split
    grants every reserve in full; an over-subscribed direction is REJECTED (``feasible``
    False) with a reported shortfall and proportionally-clamped grants that never exceed
    the headroom; discharge and charge are distinct pools; the CESSPIT request validation.
"""

from __future__ import annotations

import pytest

from analytics.contracts_v14 import BessSocState, ReserveSplitResult
from analytics.grid.capabilities import bess_soc
from analytics.grid.capabilities.bess_soc import bess_soc_state, split_reserves

# A DutchBay-shaped BESS energy block: a 40 MWh Envision site, SoH curve BoL 100% →
# yr15 76.5%, operating window 10%–95% SoC.
_BESS = {
    "type": "bess",
    "energy_mwh": 40.0,
    "soh_curve": {1: 1.0, 15: 0.765},
    "min_soc": 0.10,
    "max_soc": 0.95,
}


# ─────────────────────────────────────────────────────────────── bess_soc_state


def test_soc_state_usable_energy_and_headroom() -> None:
    # At end-of-life SoH (0.765) usable = 40 * 0.765 = 30.6 MWh; at SoC 0.60 within
    # [0.10, 0.95]: stored 18.36, dischargeable (0.60-0.10)*30.6, chargeable (0.95-0.60)*30.6.
    state = bess_soc_state(_BESS, soc_fraction=0.60)
    assert isinstance(state, BessSocState)
    assert state.bankable is False
    assert state.method == "closed_form"
    assert state.soh_fraction == pytest.approx(0.765)
    assert state.usable_energy_mwh == pytest.approx(30.6)
    assert state.stored_energy_mwh == pytest.approx(30.6 * 0.60)
    assert state.dischargeable_mwh == pytest.approx((0.60 - 0.10) * 30.6)
    assert state.chargeable_mwh == pytest.approx((0.95 - 0.60) * 30.6)


def test_soc_state_reference_year_selects_bol() -> None:
    state = bess_soc_state(_BESS, soc_fraction=0.50, reference_year=1)
    assert state.soh_fraction == pytest.approx(1.0)
    assert state.usable_energy_mwh == pytest.approx(40.0)


def test_soc_state_explicit_soh_fraction() -> None:
    grid = {**_BESS, "soh_fraction": 0.90}
    del_curve = {k: v for k, v in grid.items() if k != "soh_curve"}
    state = bess_soc_state(del_curve, soc_fraction=0.50)
    assert state.soh_fraction == pytest.approx(0.90)
    assert state.usable_energy_mwh == pytest.approx(36.0)


def test_soc_state_nameplate_energy_alias() -> None:
    grid = {k: v for k, v in _BESS.items() if k != "energy_mwh"}
    grid["nameplate_energy_mwh"] = 40.0
    state = bess_soc_state(grid, soc_fraction=0.50)
    assert state.nameplate_energy_mwh == pytest.approx(40.0)


def test_soc_state_headroom_zero_at_window_edges() -> None:
    # At the floor there is nothing to discharge; at the ceiling nothing to charge.
    at_floor = bess_soc_state(_BESS, soc_fraction=0.10)
    assert at_floor.dischargeable_mwh == pytest.approx(0.0)
    assert at_floor.chargeable_mwh == pytest.approx((0.95 - 0.10) * 30.6)
    at_ceiling = bess_soc_state(_BESS, soc_fraction=0.95)
    assert at_ceiling.chargeable_mwh == pytest.approx(0.0)
    assert at_ceiling.dischargeable_mwh == pytest.approx((0.95 - 0.10) * 30.6)


def test_soc_state_rejects_non_storage_type() -> None:
    with pytest.raises(ValueError, match="STORAGE model"):
        bess_soc_state({**_BESS, "type": "wind"}, soc_fraction=0.50)


def test_soc_state_default_type_is_bess() -> None:
    grid = {k: v for k, v in _BESS.items() if k != "type"}
    state = bess_soc_state(grid, soc_fraction=0.50)
    assert state.usable_energy_mwh == pytest.approx(30.6)


@pytest.mark.parametrize("bad", [0.0, -5.0, "40", None])
def test_soc_state_missing_or_bad_nameplate_raises(bad: object) -> None:
    grid = {k: v for k, v in _BESS.items() if k != "energy_mwh"}
    if bad is not None:
        grid["energy_mwh"] = bad
    with pytest.raises(ValueError, match="energy_mwh"):
        bess_soc_state(grid, soc_fraction=0.50)


def test_soc_state_soh_missing_raises() -> None:
    grid = {k: v for k, v in _BESS.items() if k != "soh_curve"}
    with pytest.raises(ValueError, match="soh_fraction.*soh_curve"):
        bess_soc_state(grid, soc_fraction=0.50)


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.01])
def test_soc_state_explicit_soh_out_of_range_raises(bad: float) -> None:
    grid = {**{k: v for k, v in _BESS.items() if k != "soh_curve"}, "soh_fraction": bad}
    with pytest.raises(ValueError, match=r"soh_fraction must be in"):
        bess_soc_state(grid, soc_fraction=0.50)


def test_soc_state_soh_curve_non_integer_year_raises() -> None:
    grid = {**{k: v for k, v in _BESS.items() if k != "soh_curve"}}
    grid["soh_curve"] = {"yr15": 0.765}
    with pytest.raises(ValueError, match="non-integer year"):
        bess_soc_state(grid, soc_fraction=0.50)


def test_soc_state_soh_curve_non_numeric_value_raises() -> None:
    grid = {**{k: v for k, v in _BESS.items() if k != "soh_curve"}}
    grid["soh_curve"] = {15: "0.765"}
    with pytest.raises(ValueError, match="must be a number"):
        bess_soc_state(grid, soc_fraction=0.50)


@pytest.mark.parametrize("bad_soh", [0.0, -0.1, 1.5])
def test_soc_state_soh_curve_out_of_range_raises(bad_soh: float) -> None:
    grid = {**{k: v for k, v in _BESS.items() if k != "soh_curve"}}
    grid["soh_curve"] = {15: bad_soh}
    with pytest.raises(ValueError, match=r"SoH fraction must be in"):
        bess_soc_state(grid, soc_fraction=0.50)


def test_soc_state_soh_curve_missing_reference_year_raises() -> None:
    with pytest.raises(ValueError, match="no entry for reference_year=7"):
        bess_soc_state(_BESS, soc_fraction=0.50, reference_year=7)


def test_soc_state_string_year_keys_coerce() -> None:
    grid = {**{k: v for k, v in _BESS.items() if k != "soh_curve"}}
    grid["soh_curve"] = {"1": 1.0, "15": 0.765}
    state = bess_soc_state(grid, soc_fraction=0.50)
    assert state.soh_fraction == pytest.approx(0.765)


@pytest.mark.parametrize("bad_soc", [-0.1, 1.5, "0.5"])
def test_soc_state_bad_soc_fraction_raises(bad_soc: object) -> None:
    with pytest.raises(ValueError, match="soc_fraction"):
        bess_soc_state(_BESS, soc_fraction=bad_soc)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field,value",
    [("min_soc", -0.1), ("max_soc", 1.5), ("min_soc", "x"), ("max_soc", None)],
)
def test_soc_state_bad_window_bounds_raise(field: str, value: object) -> None:
    grid = {**_BESS}
    if value is None:
        del grid[field]
    else:
        grid[field] = value
    with pytest.raises(ValueError, match=field):
        bess_soc_state(grid, soc_fraction=0.50)


def test_soc_state_window_min_not_below_max_raises() -> None:
    grid = {**_BESS, "min_soc": 0.80, "max_soc": 0.50}
    with pytest.raises(ValueError, match="min_soc < grid.max_soc"):
        bess_soc_state(grid, soc_fraction=0.60)


@pytest.mark.parametrize("soc", [0.05, 0.99])
def test_soc_state_out_of_window_soc_rejected(soc: float) -> None:
    with pytest.raises(ValueError, match="outside the operating window"):
        bess_soc_state(_BESS, soc_fraction=soc)


# ─────────────────────────────────────────────────────────────── split_reserves


def _mid_state() -> BessSocState:
    # SoC 0.60, usable 30.6: dischargeable = 0.50*30.6 = 15.30, chargeable = 0.35*30.6 = 10.71.
    return bess_soc_state(_BESS, soc_fraction=0.60)


def test_split_feasible_grants_every_reserve_in_full() -> None:
    state = _mid_state()
    res = split_reserves(state, firming_mwh=8.0, frequency_mwh=4.0, curtailment_mwh=5.0)
    assert isinstance(res, ReserveSplitResult)
    assert res.bankable is False
    assert res.feasible is True
    assert res.firming_allocated_mwh == pytest.approx(8.0)
    assert res.frequency_allocated_mwh == pytest.approx(4.0)
    assert res.curtailment_allocated_mwh == pytest.approx(5.0)
    assert res.discharge_shortfall_mwh == pytest.approx(0.0)
    assert res.charge_shortfall_mwh == pytest.approx(0.0)
    assert res.soc is state


def test_split_no_double_count_discharge_over_subscription_rejected() -> None:
    """Firming + frequency together exceed the 15.30 MWh discharge headroom → REJECTED."""
    state = _mid_state()  # dischargeable = 15.30
    res = split_reserves(
        state, firming_mwh=10.0, frequency_mwh=10.0, curtailment_mwh=0.0
    )
    assert res.feasible is False
    assert res.discharge_requested_mwh == pytest.approx(20.0)
    assert res.discharge_available_mwh == pytest.approx(15.30)
    assert res.discharge_shortfall_mwh == pytest.approx(20.0 - 15.30)
    # Grants are clamped to the headroom, split PROPORTIONALLY (10:10 → 7.65 each), and
    # NEVER over-allocated: the same MWh is not claimed by both services.
    assert res.firming_allocated_mwh == pytest.approx(15.30 / 2)
    assert res.frequency_allocated_mwh == pytest.approx(15.30 / 2)
    assert res.firming_allocated_mwh + res.frequency_allocated_mwh == pytest.approx(
        state.dischargeable_mwh
    )


def test_split_proportional_clamp_respects_request_ratio() -> None:
    state = _mid_state()  # dischargeable = 15.30
    res = split_reserves(
        state, firming_mwh=15.0, frequency_mwh=5.0, curtailment_mwh=0.0
    )
    assert res.feasible is False
    # 15:5 ratio → 3/4 and 1/4 of 15.30.
    assert res.firming_allocated_mwh == pytest.approx(15.30 * 0.75)
    assert res.frequency_allocated_mwh == pytest.approx(15.30 * 0.25)


def test_split_charge_over_subscription_rejected() -> None:
    """Curtailment absorption exceeding the 10.71 MWh charge headroom → REJECTED."""
    state = _mid_state()  # chargeable = 10.71
    res = split_reserves(
        state, firming_mwh=0.0, frequency_mwh=0.0, curtailment_mwh=15.0
    )
    assert res.feasible is False
    assert res.charge_requested_mwh == pytest.approx(15.0)
    assert res.charge_available_mwh == pytest.approx(10.71)
    assert res.charge_shortfall_mwh == pytest.approx(15.0 - 10.71)
    assert res.curtailment_allocated_mwh == pytest.approx(10.71)


def test_split_directions_are_distinct_pools() -> None:
    """A full discharge draw does NOT consume the charge pool, and vice versa."""
    state = _mid_state()
    # Discharge fully subscribed (15.30) but charge (curtailment) still fully honoured.
    res = split_reserves(
        state, firming_mwh=15.30, frequency_mwh=0.0, curtailment_mwh=10.71
    )
    assert res.feasible is True
    assert res.firming_allocated_mwh == pytest.approx(15.30)
    assert res.curtailment_allocated_mwh == pytest.approx(10.71)


def test_split_both_directions_over_subscribed() -> None:
    state = _mid_state()
    res = split_reserves(
        state, firming_mwh=20.0, frequency_mwh=0.0, curtailment_mwh=20.0
    )
    assert res.feasible is False
    assert res.discharge_shortfall_mwh > 0.0
    assert res.charge_shortfall_mwh > 0.0


def test_split_exact_headroom_is_feasible() -> None:
    """A request equal to the headroom (to fp round-off) is NOT spuriously rejected."""
    state = _mid_state()
    res = split_reserves(
        state,
        firming_mwh=state.dischargeable_mwh,
        frequency_mwh=0.0,
        curtailment_mwh=state.chargeable_mwh,
    )
    assert res.feasible is True
    assert res.discharge_shortfall_mwh == pytest.approx(0.0)
    assert res.charge_shortfall_mwh == pytest.approx(0.0)


def test_split_zero_requests_feasible() -> None:
    state = _mid_state()
    res = split_reserves(state, firming_mwh=0.0, frequency_mwh=0.0, curtailment_mwh=0.0)
    assert res.feasible is True
    assert res.firming_allocated_mwh == pytest.approx(0.0)


@pytest.mark.parametrize(
    "kwargs,field",
    [
        (
            {"firming_mwh": -1.0, "frequency_mwh": 0.0, "curtailment_mwh": 0.0},
            "firming",
        ),
        (
            {"firming_mwh": 0.0, "frequency_mwh": "x", "curtailment_mwh": 0.0},
            "frequency",
        ),
        (
            {"firming_mwh": 0.0, "frequency_mwh": 0.0, "curtailment_mwh": None},
            "curtailment",
        ),
    ],
)
def test_split_bad_request_raises(kwargs: dict, field: str) -> None:
    state = _mid_state()
    with pytest.raises(ValueError, match=field):
        split_reserves(state, **kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_soc_state_rejects_non_finite_soc(bad: float) -> None:
    # NaN / ±inf must be REJECTED at the boundary, not silently passed: NaN slips through
    # every < / > comparison, which would yield a spurious feasible verdict downstream.
    with pytest.raises(ValueError):
        bess_soc_state(_BESS, soc_fraction=bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_split_reserves_rejects_non_finite_request(bad: float) -> None:
    state = bess_soc_state(_BESS, soc_fraction=0.60)
    with pytest.raises(ValueError):
        split_reserves(state, firming_mwh=bad, frequency_mwh=0.0, curtailment_mwh=0.0)


def test_module_all_surface() -> None:
    assert set(bess_soc.__all__) == {"bess_soc_state", "split_reserves"}
