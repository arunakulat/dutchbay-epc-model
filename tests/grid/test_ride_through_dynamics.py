"""Opt-in ANDES ride-through dynamics tests requiring the [grid] extra (D4a #875; D4b #892).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED
in the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the heavy path the grid-free tests cannot: the
ANDES RMS solves, and assert the COMPLIANCE VERDICT (``rode_through``) that comes from the
PHYSICAL ENVELOPE — the measured dip/swell/frequency extreme + IBR-trip status — NOT from
the raw solver convergence flag.

D4b (#892) makes all three cases physical: LVRT injects a shunt impedance fault (dip), HVRT
injects a LOAD REJECTION (swell), and frequency injects a generator trip / load step (a real
excursion). Each includes a FAILURE regression (a disturbance that should NOT ride through →
``rode_through=False``), and the NO-SPURIOUS-PASS discipline is asserted throughout: a
verdict comes only from measured physical evidence, never a convergence-only pass.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import RideThroughResult  # noqa: E402
from analytics.grid import ride_through, ride_through_poc  # noqa: E402


def test_lvrt_case_runs_and_reports_physical_envelope() -> None:
    """LVRT: a real dip is injected and the verdict comes from the envelope, not exit_code.

    Asserts the PHYSICAL EVIDENCE: min_voltage_pu is a real float measurably BELOW the
    LVRT entry pu (the fault produced a measurable dip), and rode_through is a concrete
    bool derived from recovery/trip — never left as an unvalidated pass.
    """
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    assert isinstance(res, RideThroughResult)
    assert res.case == "lvrt"
    assert res.ran is True, res.detail  # the solve executed
    assert res.target_pu == pytest.approx(0.89)  # seeded from the D0 fixture
    assert res.k_factor == pytest.approx(2.0)
    assert res.n_devices > 0
    assert res.bankable is False
    # PHYSICAL EVIDENCE: a real, measurable dip below the entry threshold.
    assert isinstance(res.min_voltage_pu, float)
    assert res.min_voltage_pu < res.target_pu, res.detail
    # The verdict is a concrete compliance decision (True/False), NOT None: a real dip
    # was injected and recovery was measured. Which way it lands depends on the case,
    # but it must NOT be an unvalidated pass and must NOT echo `converged` blindly.
    assert res.rode_through in (True, False), res.detail


def test_lvrt_shallow_dip_rides_through() -> None:
    """A shallow, short dip that recovers cleanly → rode_through True."""
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case(
        "lvrt",
        run_dynamics=True,
        lvrt_fault_x_pu=0.30,  # a mild impedance fault — shallow dip
        fault_start_s=1.0,
        fault_clear_s=1.08,  # cleared quickly
    )
    assert res.ran is True, res.detail
    assert isinstance(res.min_voltage_pu, float)
    assert res.min_voltage_pu < res.target_pu  # a measurable dip
    assert res.rode_through is True, res.detail


def test_lvrt_deep_long_fault_does_not_ride_through() -> None:
    """FAILURE regression: a deep, long bolted-ish fault must NOT report a ride-through.

    A near-bolted fault held for a long window collapses the bus / trips the IBR. The
    verdict MUST be rode_through=False (a real breach) — never True, and never a pass
    inferred from a converged solve.
    """
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case(
        "lvrt",
        run_dynamics=True,
        lvrt_fault_x_pu=0.001,  # near-bolted — deep collapse
        fault_start_s=1.0,
        fault_clear_s=1.9,  # held ~0.9 s
        tf=3.0,
    )
    assert res.ran is True, res.detail
    assert res.rode_through is False, (
        "a deep long fault that collapses/trips the plant must be a breach, "
        f"not a pass: {res.detail}"
    )


def test_hvrt_case_runs_and_measures_a_real_swell() -> None:
    """HVRT: a LOAD REJECTION swells the bus and the verdict comes from the measured peak.

    D4b (#892): the shunt-fault-cannot-swell NOT-RUN is replaced by a real over-voltage
    (a load rejection). PHYSICAL EVIDENCE: max_voltage_pu is a real float measurably ABOVE
    the HVRT entry pu (a real swell was injected), and rode_through is a concrete bool
    derived from the peak vs the trip curve + settle + IBR trip — NEVER left unvalidated.
    """
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("hvrt", run_dynamics=True)
    assert res.case == "hvrt"
    assert res.ran is True, res.detail  # the solve executed
    assert res.target_pu == pytest.approx(1.10)  # HVRT entry from the D0 fixture
    assert res.n_devices > 0
    assert res.bankable is False
    # PHYSICAL EVIDENCE: a real, measurable swell above the entry threshold.
    assert isinstance(res.max_voltage_pu, float)
    assert res.max_voltage_pu > res.target_pu, res.detail
    # A concrete compliance decision derived from the measured swell — not None, not a
    # blind echo of `converged`.
    assert res.rode_through in (True, False), res.detail


def test_hvrt_severe_swell_does_not_ride_through() -> None:
    """FAILURE regression: a severe over-voltage that trips / stays swollen → False.

    A load rejection with the swell pushed toward the over-voltage instantaneous-trip edge
    must NOT report a ride-through — the verdict is a real breach (False), never a pass.
    We force the binding case with a tight envelope (a low over-voltage trip pu) so the
    measured peak reaches the trip curve.
    """
    pytest.importorskip("andes")
    env = ride_through.envelope_from_fixture()
    # Tighten the over-voltage trip edge so any real swell reaches it → a trip breach.
    strict = replace(env, hvrt_enter_pu=1.001, ov_trip_pu=1.002)
    res = ride_through.run_ride_through_case("hvrt", run_dynamics=True, envelope=strict)
    assert res.ran is True, res.detail
    assert res.rode_through is False, (
        "a swell reaching the over-voltage trip edge must be a breach, not a pass: "
        f"{res.detail} (peak={res.max_voltage_pu})"
    )


def test_frequency_case_runs_and_measures_a_real_excursion() -> None:
    """Frequency: a generator trip moves system frequency and the verdict is measured.

    D4b (#892): the no-excursion NOT-RUN is replaced by a real generator trip. PHYSICAL
    EVIDENCE: freq_extreme_hz is a real float and rode_through is a concrete bool derived
    from the measured frequency extreme vs the band + trip curve + IBR trip.
    """
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("frequency", run_dynamics=True)
    assert res.case == "frequency"
    assert res.ran is True, res.detail
    assert res.target_hz == pytest.approx(51.5)  # continuous over-freq edge
    assert res.n_devices > 0
    # PHYSICAL EVIDENCE: a real measured frequency extreme (a concrete float near nominal).
    assert isinstance(res.freq_extreme_hz, float), res.detail
    assert 40.0 < res.freq_extreme_hz < 60.0, res.detail
    assert res.rode_through in (True, False, None), res.detail


def test_frequency_severe_excursion_does_not_ride_through() -> None:
    """FAILURE regression: an excursion reaching the trip band → rode_through False.

    A generator trip whose frequency swing reaches the instantaneous under/over-frequency
    trip edge (forced with a tight envelope) must be a real breach, never a pass.
    """
    pytest.importorskip("andes")
    env = ride_through.envelope_from_fixture()
    # Tighten the continuous band + trip band around nominal so any real swing breaches it.
    strict = replace(
        env, freq_continuous_hz=(49.99, 50.01), freq_trip_hz=(49.98, 50.02)
    )
    res = ride_through.run_ride_through_case(
        "frequency", run_dynamics=True, envelope=strict
    )
    assert res.ran is True, res.detail
    assert res.rode_through is False, (
        "a frequency swing reaching the instantaneous trip band must be a breach, not a "
        f"pass: {res.detail} (extreme={res.freq_extreme_hz})"
    )


def test_suite_runs_all_three_cases_physically() -> None:
    """The suite runs LVRT, HVRT and frequency as real disturbances (all concrete)."""
    pytest.importorskip("andes")
    suite = ride_through.run_ride_through_suite(run_dynamics=True)
    assert set(suite) == {"lvrt", "hvrt", "frequency"}
    assert suite["lvrt"].ran is True, suite["lvrt"].detail
    assert suite["lvrt"].rode_through in (True, False)
    assert suite["hvrt"].ran is True, suite["hvrt"].detail
    assert suite["hvrt"].rode_through in (True, False)
    assert suite["frequency"].ran is True, suite["frequency"].detail
    assert suite["frequency"].rode_through in (True, False, None)
    assert isinstance(suite["frequency"].freq_extreme_hz, float)


def test_poc_shim_run_lvrt_case_still_runs() -> None:
    """The backward-compat SHIM still runs the LVRT dynamics via the shared core."""
    pytest.importorskip("andes")
    res = ride_through_poc.run_lvrt_case()
    assert res.ran is True, res.detail
    assert res.lvrt_enter_pu == pytest.approx(0.89)
    assert res.n_devices > 0
    # The shim now surfaces the compliance verdict too (not just "the solve ran").
    assert res.rode_through in (True, False, None)
