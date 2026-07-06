"""Opt-in ANDES ride-through dynamics tests requiring the [grid] extra (D4a, #875).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED
in the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the heavy path the grid-free tests cannot:
the ANDES RMS LVRT solve, and assert the COMPLIANCE VERDICT (``rode_through``) that comes
from the PHYSICAL ENVELOPE — the post-fault recovered bus voltage and IBR-trip status —
NOT from the raw solver convergence flag. HVRT and frequency are NOT-RUN today (a shunt
fault cannot swell voltage; no frequency excursion is modeled yet), so they must report
``rode_through=None`` — a spurious pass here is exactly the bug this dolphin fixes.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

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


def test_hvrt_case_is_not_run() -> None:
    """HVRT: a shunt fault cannot swell voltage → explicit NOT-RUN, never a spurious pass."""
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("hvrt", run_dynamics=True)
    assert res.case == "hvrt"
    assert res.rode_through is None, res.detail  # NOT-RUN / UNSUPPORTED
    assert res.ran is False
    assert res.target_pu == pytest.approx(1.10)  # HVRT entry from the D0 fixture
    assert "NOT-RUN" in res.detail


def test_frequency_case_is_not_run() -> None:
    """Frequency: no excursion is modeled yet → explicit NOT-RUN, never a trivial pass."""
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("frequency", run_dynamics=True)
    assert res.case == "frequency"
    assert res.rode_through is None, res.detail  # NOT-RUN / UNSUPPORTED
    assert res.ran is False
    assert res.target_hz == pytest.approx(51.5)  # continuous over-freq edge
    assert "NOT-RUN" in res.detail


def test_suite_runs_lvrt_and_marks_others_not_run() -> None:
    """The suite runs LVRT physically and marks HVRT + frequency NOT-RUN."""
    pytest.importorskip("andes")
    suite = ride_through.run_ride_through_suite(run_dynamics=True)
    assert set(suite) == {"lvrt", "hvrt", "frequency"}
    assert suite["lvrt"].ran is True, suite["lvrt"].detail
    assert suite["lvrt"].rode_through in (True, False)
    assert suite["hvrt"].rode_through is None
    assert suite["frequency"].rode_through is None


def test_poc_shim_run_lvrt_case_still_runs() -> None:
    """The backward-compat SHIM still runs the LVRT dynamics via the shared core."""
    pytest.importorskip("andes")
    res = ride_through_poc.run_lvrt_case()
    assert res.ran is True, res.detail
    assert res.lvrt_enter_pu == pytest.approx(0.89)
    assert res.n_devices > 0
    # The shim now surfaces the compliance verdict too (not just "the solve ran").
    assert res.rode_through in (True, False, None)
