"""Property tests for the two battery dispatch paths (#1838).

Both paths read correctly, but before this file nothing pinned their energy accounting
against later edits. These tests run Hypothesis over generated wind profiles, sizes,
efficiencies, reserves and instructions. They change no code, output or KPI.

Oracles do not come from the code under test (TEST-01):

* ``analytics.wind.wind_bess_options.dispatch`` returns only totals per size. Per-hour flows
  come from differencing runs over every prefix of the profile, which uses nothing but the
  public totals. The stored energy implied by those flows is ``RTE x charged - delivered``,
  because the whole round trip is booked on charge.
* Exact conservation is proved by a drain: zero-wind window hours appended after the
  profile, long enough to empty the battery to its reserve. After the drain, delivered
  energy must equal ``RTE x charged - reserve`` (or zero when the reserve was never filled).
  That identity holds only if the RTE enters exactly once.
* ``analytics.storage_dispatch.simulate_dispatch`` returns a step ledger. Its balances are
  recomputed here from the rows and the authored inputs, independently of the ledger's own
  ``__post_init__`` checks.

Property 8 pins a stated simplification: standby and auxiliary load (BMS, HVAC) is excluded
(``scenario_with_battery`` docstring). An idle hour therefore leaves stored energy unchanged.
If standby losses are modelled later (an R3 change, since Blue Whale KPIs would move), that
test is the one to revise, on purpose.

Deterministic by design (``derandomize=True`` and no deadline), as in
``tests/finance/test_finance_invariants_property.py``, so CI is reproducible (MRM-01).
A failing property is reported, not weakened or skipped.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from analytics.contracts_v14 import ChronologicalDispatchInput
from analytics.storage_dispatch import simulate_dispatch
from analytics.wind import wind_bess_options as wbo

_SETTINGS = settings(max_examples=60, deadline=None, derandomize=True)
TOL = 1e-7


# ---------------------------------------------------------------------------
# Wind battery options: dispatch()
# ---------------------------------------------------------------------------
def _stamps(hours: int) -> List[str]:
    """Hourly stamps in one year, so the per-year mean is the total."""
    return [f"202601{1 + h // 24:02d}{h % 24:02d}" for h in range(hours)]


def _finite(lo: float, hi: float) -> st.SearchStrategy[float]:
    return st.floats(min_value=lo, max_value=hi, allow_nan=False, allow_infinity=False)


@st.composite
def _case(draw: Any, *, cap_floor: float = 0.0) -> Dict[str, Any]:
    hours = draw(st.integers(min_value=1, max_value=48))
    wind = draw(st.lists(_finite(0.0, 12.0), min_size=hours, max_size=hours))
    window = draw(
        st.lists(st.integers(0, 23), min_size=1, max_size=8, unique=True).map(sorted)
    )
    n = draw(st.integers(min_value=1, max_value=3))
    power = draw(
        st.lists(st.one_of(st.just(0.0), _finite(0.25, 5.0)), min_size=n, max_size=n)
    )
    energy = draw(st.lists(_finite(0.0, 20.0), min_size=n, max_size=n))
    share = draw(st.lists(_finite(0.0, 1.0), min_size=n, max_size=n))
    rte = draw(st.lists(_finite(0.5, 1.0), min_size=n, max_size=n))
    cap = draw(st.one_of(st.none(), _finite(max(cap_floor, 0.0), 15.0)))
    return {
        "wind": np.asarray(wind, dtype=np.float64),
        "stamps": _stamps(hours),
        "power_mw": power,
        "energy_mwh": energy,
        "reserve_mwh": [s * e for s, e in zip(share, energy, strict=True)],
        "round_trip_efficiency": rte,
        "window_utc_hours": window,
        "export_cap_mw": cap,
    }


def _run(case: Dict[str, Any], **change: Any) -> wbo.DispatchResult:
    args = {**case, **change}
    return wbo.dispatch(
        args["wind"],
        args["stamps"],
        power_mw=args["power_mw"],
        energy_mwh=args["energy_mwh"],
        round_trip_efficiency=args["round_trip_efficiency"],
        window_utc_hours=args["window_utc_hours"],
        export_cap_mw=args["export_cap_mw"],
        reserve_mwh=args["reserve_mwh"],
    )


def _hourly(case: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray]:
    """Per-hour delivered and charged energy, shape (hours, sizes), from prefix totals."""
    n = len(case["stamps"])
    cum_d = [np.zeros(len(case["power_mw"]))]
    cum_c = [np.zeros(len(case["power_mw"]))]
    for k in range(1, n + 1):
        res = _run(case, wind=case["wind"][:k], stamps=case["stamps"][:k])
        cum_d.append(res.delivered_mwh)
        cum_c.append(res.charged_mwh)
    return np.diff(np.asarray(cum_d), axis=0), np.diff(np.asarray(cum_c), axis=0)


@_SETTINGS
@given(case=_case())
def test_hourly_flows_respect_window_power_cap_and_stored_energy(
    case: Dict[str, Any],
) -> None:
    """Properties 2, 3, 4 and 5 on the per-hour flows."""
    delivered, charged = _hourly(case)
    rte = np.asarray(case["round_trip_efficiency"])
    power = np.asarray(case["power_mw"])
    energy = np.asarray(case["energy_mwh"])
    floor = np.asarray(case["reserve_mwh"])
    hours = np.array([int(s[8:10]) for s in case["stamps"]])
    in_window = np.isin(hours, case["window_utc_hours"])
    cap = case["export_cap_mw"]
    stored = np.zeros_like(power)
    for i, w in enumerate(case["wind"]):
        d, c = delivered[i], charged[i]
        assert (d >= -TOL).all() and (c >= -TOL).all()
        # 4. Window rules: no charge inside the window, no discharge outside it.
        if in_window[i]:
            assert (np.abs(c) <= TOL).all()
        else:
            assert (np.abs(d) <= TOL).all()
        # Power limits, and charge comes from the turbine only.
        assert (d <= power + TOL).all()
        assert (c <= np.minimum(power, w) + TOL).all()
        # 3. Export cap: wind plus discharge never exceeds the cap in any hour.
        if cap is not None:
            assert (d <= max(cap - w, 0.0) + TOL).all()
        # 5. Reserve floor: discharge never draws stored energy below the reserve.
        assert (d <= np.maximum(stored - floor, 0.0) + TOL).all()
        stored = stored + rte * c - d
        # 2. SOC bounds: stored energy stays within [0, capacity] ...
        assert (stored >= -TOL).all() and (stored <= energy + TOL).all()
        # ... and after any revenue discharge it is still at or above the reserve.
        assert (stored[d > TOL] >= floor[d > TOL] - TOL).all()


def _drained(case: Dict[str, Any]) -> Dict[str, Any]:
    """Append zero-wind window hours that empty every battery down to its reserve."""
    power = np.asarray(case["power_mw"])
    cap = case["export_cap_mw"]
    rate = power if cap is None else np.minimum(power, cap)
    active = rate > 0
    need = 1 + int(
        math.ceil(
            max(
                (np.asarray(case["energy_mwh"])[active] / rate[active]).tolist()
                or [0.0]
            )
        )
    )
    hour = case["window_utc_hours"][0]
    tail = [f"20260131{hour:02d}"] * need
    return {
        **case,
        "wind": np.concatenate([case["wind"], np.zeros(need)]),
        "stamps": case["stamps"] + tail,
    }


@_SETTINGS
@given(case=_case(cap_floor=0.25))
def test_drain_conserves_energy_with_the_rte_booked_once(case: Dict[str, Any]) -> None:
    """Properties 1 and 7: after a drain, delivered = RTE x charged - reserve held."""
    res = _run(_drained(case))
    rte = np.asarray(case["round_trip_efficiency"])
    floor = np.asarray(case["reserve_mwh"])
    stored_in = rte * res.charged_mwh
    held = np.minimum(floor, stored_in)
    assert np.allclose(res.delivered_mwh, stored_in - held, rtol=0, atol=1e-6)
    # Without the drain, what is still stored is bounded by the capacity.
    plain = _run(case)
    left = rte * plain.charged_mwh - plain.delivered_mwh
    assert (left >= -TOL).all()
    assert (left <= np.asarray(case["energy_mwh"]) + TOL).all()


@_SETTINGS
@given(case=_case(cap_floor=0.25), rte=_finite(0.5, 0.99))
def test_rte_is_not_applied_twice_or_dropped(case: Dict[str, Any], rte: float) -> None:
    """Property 7: a drained battery returns exactly RTE x charged, not RTE^2 or 1 x."""
    case = {**case, "round_trip_efficiency": rte, "reserve_mwh": 0.0}
    res = _run(_drained(case))
    assume((res.charged_mwh > 1e-3).any())
    sel = res.charged_mwh > 1e-3
    ratio = res.delivered_mwh[sel] / res.charged_mwh[sel]
    assert np.allclose(ratio, rte, rtol=0, atol=1e-6)


@_SETTINGS
@given(case=_case())
def test_zero_wind_gives_zero_energy(case: Dict[str, Any]) -> None:
    """Property 6a: no wind, no charge and no delivery, for every size."""
    res = _run(case, wind=np.zeros_like(case["wind"]))
    assert (res.delivered_mwh == 0.0).all()
    assert (res.charged_mwh == 0.0).all()


@_SETTINGS
@given(case=_case(), extra=_finite(0.0, 20.0))
def test_more_energy_capacity_never_reduces_delivery(
    case: Dict[str, Any], extra: float
) -> None:
    """Property 6b: more energy capacity, all else fixed, never reduces delivered energy."""
    bigger = [e + extra for e in case["energy_mwh"]]
    small = _run(case)
    large = _run(case, energy_mwh=bigger)
    assert (large.delivered_mwh >= small.delivered_mwh - 1e-6).all()


@_SETTINGS
@given(case=_case(), at=st.integers(min_value=0, max_value=48), day=st.booleans())
def test_an_idle_hour_leaves_stored_energy_unchanged(
    case: Dict[str, Any], at: int, day: bool
) -> None:
    """Property 8 (standby exclusion): an hour with no flow changes nothing after it.

    An idle hour is either outside the window with no wind, or inside the window with no
    export headroom. Inserting one anywhere must leave every total unchanged, which holds
    only while standby and auxiliary load is excluded.
    """
    window = case["window_utc_hours"]
    cap = case["export_cap_mw"]
    if day or cap is None:
        free = [h for h in range(24) if h not in window]
        assume(free)
        hour, wind = free[0], 0.0
    else:
        hour, wind = window[0], cap + 1.0
    at = min(at, len(case["stamps"]))
    stamps = case["stamps"][:at] + [f"20260131{hour:02d}"] + case["stamps"][at:]
    winds = np.insert(case["wind"], at, wind)
    base = _run(case)
    idle = _run(case, wind=winds, stamps=stamps)
    assert np.allclose(idle.delivered_mwh, base.delivered_mwh, rtol=0, atol=1e-9)
    assert np.allclose(idle.charged_mwh, base.charged_mwh, rtol=0, atol=1e-9)


def test_the_prefix_oracle_detects_a_double_counted_rte() -> None:
    """Non-vacuity control: the drain identity rejects an RTE booked twice."""
    case = {
        "wind": np.full(24, 4.0),
        "stamps": _stamps(24),
        "power_mw": [2.0],
        "energy_mwh": [6.0],
        "reserve_mwh": [0.0],
        "round_trip_efficiency": [0.8],
        "window_utc_hours": [18, 19, 20, 21],
        "export_cap_mw": None,
    }
    res = _run(_drained(case))
    assert math.isclose(res.delivered_mwh[0], 0.8 * res.charged_mwh[0], abs_tol=1e-9)
    assert not math.isclose(
        res.delivered_mwh[0], 0.8 * 0.8 * res.charged_mwh[0], abs_tol=1e-6
    )


# ---------------------------------------------------------------------------
# Chronological storage dispatch: simulate_dispatch()
# ---------------------------------------------------------------------------
_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


@st.composite
def _envelope(draw: Any) -> Dict[str, Any]:
    n = draw(st.integers(min_value=1, max_value=24))
    lo = draw(_finite(0.0, 0.4))
    hi = draw(_finite(lo + 0.1, 1.0))
    init = draw(_finite(lo, hi))

    def series(strategy: st.SearchStrategy[Any]) -> List[Any]:
        values: List[Any] = draw(st.lists(strategy, min_size=n, max_size=n))
        return values

    # The contract requires charge_source "none" exactly when the hour does not charge.
    instructions = series(st.one_of(st.just(0.0), _finite(-25.0, 25.0)))
    sources = series(st.sampled_from(["renewable", "grid"]))
    return {
        "sizing": {
            "power_mw": draw(_finite(0.5, 20.0)),
            "duration_h": draw(_finite(0.5, 6.0)),
        },
        "timestamps_utc": [
            (_START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(n)
        ],
        "step_h": 1.0,
        "wind_generation_mwh": series(_finite(0.0, 30.0)),
        "solar_generation_mwh": series(_finite(0.0, 30.0)),
        "dispatch_instruction_mw": instructions,
        "poc_limit_mw": series(_finite(0.0, 60.0)),
        "wind_outage": series(st.booleans()),
        "solar_outage": series(st.booleans()),
        "bess_outage": series(st.booleans()),
        "poc_outage": series(st.booleans()),
        "charge_source": [
            source if mw < 0 else "none"
            for mw, source in zip(instructions, sources, strict=True)
        ],
        "charge_efficiency": draw(_finite(0.5, 1.0)),
        "discharge_efficiency": draw(_finite(0.5, 1.0)),
        "soh_fraction": draw(_finite(0.5, 1.0)),
        "minimum_soc_fraction": lo,
        "maximum_soc_fraction": hi,
        "initial_soc_fraction": init,
        "final_soc_fraction": init,
        "poc_flow_basis": "gross_sum",
        "allocation_policy": "charge_then_generation_then_discharge",
        "tariff_terms": "Synthetic property test only; no tariff valuation.",
        "ld_terms": "Synthetic property test only; no LD valuation.",
        "provenance": "Generated synthetic input (#1838); not Dutch Bay evidence.",
    }


def _ledger(raw: Dict[str, Any]) -> Tuple[Any, Sequence[Any]]:
    inputs = ChronologicalDispatchInput.from_mapping(raw)
    return inputs, simulate_dispatch(inputs).steps


@_SETTINGS
@given(raw=_envelope())
def test_storage_ledger_conserves_energy_and_respects_bounds(
    raw: Dict[str, Any],
) -> None:
    """Properties 1, 2, 3 and 7 recomputed from the ledger rows."""
    cfg, steps = _ledger(raw)
    usable = cfg.sizing.energy_mwh * cfg.soh_fraction
    lo = usable * cfg.minimum_soc_fraction
    hi = usable * cfg.maximum_soc_fraction
    previous = usable * cfg.initial_soc_fraction
    total_in = total_out = total_loss = 0.0
    for i, row in enumerate(steps):
        charge = row.wind_to_bess_mwh + row.solar_to_bess_mwh + row.grid_to_bess_mwh
        out = row.bess_to_poc_mwh
        # 7. Each efficiency enters once: the loss is the gap between flow and storage.
        assert math.isclose(
            row.soc_end_mwh - row.soc_start_mwh,
            charge - row.charge_loss_mwh - out - row.discharge_loss_mwh,
            abs_tol=TOL,
        )
        assert math.isclose(
            row.charge_loss_mwh, charge * (1 - cfg.charge_efficiency), abs_tol=TOL
        )
        assert math.isclose(
            row.discharge_loss_mwh,
            out * (1 / cfg.discharge_efficiency - 1),
            abs_tol=TOL,
        )
        assert math.isclose(row.soc_start_mwh, previous, abs_tol=TOL)
        # 2. SOC stays in the authored window.
        assert lo - TOL <= row.soc_end_mwh <= hi + TOL
        # 3. The gross POC flow (exports plus grid charging) stays within the limit.
        cap = 0.0 if cfg.poc_outage[i] else cfg.poc_limit_mw[i]
        exports = row.wind_to_poc_mwh + row.solar_to_poc_mwh + out
        assert exports + row.grid_to_bess_mwh <= cap + TOL
        # Power, no simultaneous charge and discharge, and an outage blocks the battery.
        assert max(charge, out) <= cfg.sizing.power_mw + TOL
        assert charge <= TOL or out <= TOL
        if cfg.bess_outage[i]:
            assert charge <= TOL and out <= TOL
        # Renewable charge never exceeds the generation available in the hour.
        wind = 0.0 if cfg.wind_outage[i] else cfg.wind_generation_mwh[i]
        solar = 0.0 if cfg.solar_outage[i] else cfg.solar_generation_mwh[i]
        assert row.wind_to_bess_mwh <= wind + TOL
        assert row.solar_to_bess_mwh <= solar + TOL
        previous = row.soc_end_mwh
        total_in += charge
        total_out += out
        total_loss += row.charge_loss_mwh + row.discharge_loss_mwh
    # 1. Whole-horizon conservation: in - out - losses = change in stored energy.
    start = usable * cfg.initial_soc_fraction
    assert math.isclose(
        total_in - total_out - total_loss, previous - start, abs_tol=1e-6
    )


@_SETTINGS
@given(raw=_envelope(), at=st.integers(min_value=0, max_value=23))
def test_storage_idle_step_leaves_stored_energy_unchanged(
    raw: Dict[str, Any], at: int
) -> None:
    """Property 8 (standby exclusion): a zero instruction moves no energy in or out."""
    at = min(at, len(raw["timestamps_utc"]) - 1)
    raw["dispatch_instruction_mw"][at] = 0.0
    raw["charge_source"][at] = "none"
    _, steps = _ledger(raw)
    row = steps[at]
    assert row.soc_end_mwh == row.soc_start_mwh
    assert row.charge_loss_mwh == 0.0 and row.discharge_loss_mwh == 0.0
    assert row.bess_to_poc_mwh == 0.0
    assert row.wind_to_bess_mwh + row.solar_to_bess_mwh + row.grid_to_bess_mwh == 0.0


@_SETTINGS
@given(raw=_envelope())
def test_storage_renewable_charging_needs_generation(raw: Dict[str, Any]) -> None:
    """Property 6a: with no wind or solar, renewable-sourced charging moves nothing."""
    n = len(raw["timestamps_utc"])
    raw["wind_generation_mwh"] = [0.0] * n
    raw["solar_generation_mwh"] = [0.0] * n
    raw["charge_source"] = [
        "renewable" if mw < 0 else "none" for mw in raw["dispatch_instruction_mw"]
    ]
    _, steps = _ledger(raw)
    for row in steps:
        assert row.wind_to_bess_mwh == 0.0 and row.solar_to_bess_mwh == 0.0
        assert row.grid_to_bess_mwh == 0.0
        assert row.wind_to_poc_mwh == 0.0 and row.solar_to_poc_mwh == 0.0
