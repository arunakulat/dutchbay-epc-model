"""Grid-FREE coverage for the D4a RMS ride-through dynamics core (#875).

These tests import NO grid library (``andes`` is ABSENT in the default venv) and are
NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and
carry the real coverage for :mod:`analytics.grid.ride_through`. They exercise:

  * the envelope parser (``envelope_from_fixture``) against the real D0 fixture, a
    missing file, a fixture with no ``pcs`` block, and the frequency-trip-table reducer
    (longest-clearing-time setpoint) incl. its malformed-row branch;
  * the case-spec builder (``build_case_spec``) for LVRT / HVRT / frequency incl. the
    unknown-kind ValueError and the frequency-excursion override;
  * ``run_ride_through_case`` on the DYNAMIC-STUDY-GATE-OFF path (``run_dynamics=False``)
    — envelope parse + case set-up, NO andes import — for all three kinds, and the
    ``envelope=`` fast-path;
  * ``run_ride_through_suite`` (all three cases from one envelope, gate off);
  * ``RideThroughResult.from_case`` (frozen, dumps, disclaimer stamped, bankable False);
  * the CASPER ``_require_andes`` guard failing loud when the extra is absent.

The genuinely andes-only code (``_solve_case`` + the helpers it calls + the
``run_dynamics=True`` branch) is ``# pragma: no cover - requires [grid] extra`` and is
exercised instead by the ``grid``-marked ``test_ride_through_dynamics.py`` under
``pip install -e '.[grid]'``.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from analytics.contracts_v14 import RideThroughResult
from analytics.grid import ride_through as rt
from analytics.grid import ride_through_poc
from analytics.grid.ride_through import (
    RIDE_THROUGH_CASES,
    FreqEvidence,
    HvrtEvidence,
    LvrtEvidence,
    RideThroughEnvelope,
    build_case_spec,
    envelope_from_fixture,
    freq_extreme_hz,
    frequency_rode_through,
    hvrt_rode_through,
    lvrt_rode_through,
    run_ride_through_case,
    run_ride_through_suite,
)

_D0_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "grid"
    / "envision_enpcs01_gridcode.yaml"
)


# --------------------------------------------------------------------------- CASPER


def test_module_imports_without_andes() -> None:
    """Importing the core must not require andes (grid-free env)."""
    assert hasattr(rt, "run_ride_through_case")
    assert hasattr(rt, "envelope_from_fixture")


def test_require_andes_fails_loud_when_absent() -> None:
    try:
        import andes  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"\[grid\] extra"):
            rt._require_andes()
    else:  # pragma: no cover - only when the [grid] extra is installed
        assert rt._require_andes() is not None


# --------------------------------------------------------------- envelope parsing


def test_envelope_from_d0_fixture() -> None:
    """The envelope is seeded from the D0 grid-code fixture (not magic constants)."""
    env = envelope_from_fixture()
    assert env.lvrt_enter_pu == 0.89
    assert env.hvrt_enter_pu == 1.10
    assert env.lvrt_k_factor == 2.0
    assert env.hvrt_k_factor == 1.9
    # Widest continuous band = the longest-clearing setpoint each direction:
    # under 47.5 Hz @ 1800s (vs 47.0 @ 0.1s); over 51.5 Hz @ 1800s (vs 52.0 @ 0.1s).
    assert env.freq_continuous_hz == (47.5, 51.5)
    # D4b (#892) trip-curve edges: the SHORTEST-clearing setpoints (instantaneous trip).
    # over-voltage: 1.3 pu @ 0.1s (vs 1.2 @ 1.0s, 1.1 @ 20.0s) → 1.3.
    assert env.ov_trip_pu == 1.3
    # freq trip: under 47.0 Hz @ 0.1s (vs 47.5 @ 1800s); over 52.0 Hz @ 0.1s.
    assert env.freq_trip_hz == (47.0, 52.0)
    assert env.source == "envision_enpcs01_gridcode.yaml"


def test_envelope_explicit_fixture_path() -> None:
    env = envelope_from_fixture(_D0_FIXTURE)
    assert env.lvrt_enter_pu == 0.89


def test_envelope_missing_file_falls_back_to_defaults() -> None:
    env = envelope_from_fixture(Path("/nonexistent/gridcode.yaml"))
    assert env.lvrt_enter_pu == rt._DEFAULT_LVRT_ENTER_PU
    assert env.hvrt_enter_pu == rt._DEFAULT_HVRT_ENTER_PU
    assert env.lvrt_k_factor == rt._DEFAULT_LVRT_K
    assert env.hvrt_k_factor == rt._DEFAULT_HVRT_K
    assert env.freq_continuous_hz == rt._DEFAULT_FREQ_HZ
    assert env.ov_trip_pu == rt._DEFAULT_OV_TRIP_PU
    assert env.freq_trip_hz == rt._DEFAULT_FREQ_TRIP_HZ
    assert "defaults" in env.source


def test_envelope_fixture_without_pcs_block(tmp_path: Path) -> None:
    """A YAML file with no ``pcs`` mapping falls back to defaults (named source)."""
    p = tmp_path / "nopcs.yaml"
    p.write_text("provenance: x\npcs: 3\n")  # pcs present but not a mapping
    env = envelope_from_fixture(p)
    assert env.lvrt_enter_pu == rt._DEFAULT_LVRT_ENTER_PU
    assert "no pcs block" in env.source


def test_envelope_empty_yaml_file(tmp_path: Path) -> None:
    p = tmp_path / "empty.yaml"
    p.write_text("")  # safe_load -> None -> {} ; pcs absent
    env = envelope_from_fixture(p)
    assert env.lvrt_enter_pu == rt._DEFAULT_LVRT_ENTER_PU
    assert env.source == "empty.yaml"


def test_envelope_partial_freq_table(tmp_path: Path) -> None:
    """Only one direction present + a malformed row → other direction keeps its default."""
    p = tmp_path / "partial.yaml"
    p.write_text(
        "pcs:\n"
        "  freq_trip_hz:\n"
        "    underfrequency:\n"
        "      - [47.0, 5.0]\n"
        "      - [48.0]\n"  # malformed (len != 2) — skipped
        "      - ['x', 2.0]\n"  # malformed (non-numeric) — skipped
    )
    env = envelope_from_fixture(p)
    assert env.freq_continuous_hz[0] == 47.0  # only valid under row
    assert env.freq_continuous_hz[1] == rt._DEFAULT_FREQ_HZ[1]  # over default kept


def test_envelope_non_numeric_scalars_fall_back(tmp_path: Path) -> None:
    """A non-numeric / bool scalar in the fixture coerces to the default (not crash)."""
    p = tmp_path / "bad.yaml"
    p.write_text("pcs:\n  lvrt_enter_pu: notanumber\n  hvrt_enter_pu: true\n")
    env = envelope_from_fixture(p)
    assert env.lvrt_enter_pu == rt._DEFAULT_LVRT_ENTER_PU
    assert env.hvrt_enter_pu == rt._DEFAULT_HVRT_ENTER_PU


def test_longest_clearing_setpoint_empty_and_bad() -> None:
    assert rt._longest_clearing_setpoint(None) is None
    assert rt._longest_clearing_setpoint([]) is None
    assert rt._longest_clearing_setpoint("nope") is None
    assert rt._longest_clearing_setpoint([[50.0, 1.0], [49.0, 9.0]]) == 49.0


def test_shortest_clearing_setpoint_empty_and_bad() -> None:
    """The instantaneous-trip edge is the MIN-clearing-time setpoint; bad tables → None."""
    assert rt._shortest_clearing_setpoint(None) is None
    assert rt._shortest_clearing_setpoint([]) is None
    assert rt._shortest_clearing_setpoint("nope") is None
    # 50 @ 1.0s vs 49 @ 9.0s → shortest clearing is the 50 @ 1.0s row.
    assert rt._shortest_clearing_setpoint([[50.0, 1.0], [49.0, 9.0]]) == 50.0
    # Malformed rows (wrong arity / non-numeric / bool) are skipped.
    assert rt._shortest_clearing_setpoint([[52.0, 0.1], [51.0], ["x", 2.0]]) == 52.0


def test_ov_trip_from_volt_table_and_fallback() -> None:
    """Over-voltage trip = shortest-clearing overvoltage setpoint; absent → default."""
    pcs = {
        "volt_trip_pu": {
            "overvoltage": [[1.1, 20.0], [1.2, 1.0], [1.3, 0.1]],
        }
    }
    assert rt._ov_trip_from_volt_table(pcs) == 1.3
    assert rt._ov_trip_from_volt_table({}) == rt._DEFAULT_OV_TRIP_PU
    # A non-mapping table falls back to the default.
    assert rt._ov_trip_from_volt_table({"volt_trip_pu": 5}) == rt._DEFAULT_OV_TRIP_PU


def test_freq_trip_from_trip_table_and_partial() -> None:
    """Instantaneous freq trip band = shortest-clearing setpoints; partial keeps defaults."""
    pcs = {
        "freq_trip_hz": {
            "underfrequency": [[47.5, 1800.0], [47.0, 0.1]],
            "overfrequency": [[51.5, 1800.0], [52.0, 0.1]],
        }
    }
    assert rt._freq_trip_from_trip_table(pcs) == (47.0, 52.0)
    # Only under present → over keeps its default.
    partial = {"freq_trip_hz": {"underfrequency": [[46.5, 0.2]]}}
    lo, hi = rt._freq_trip_from_trip_table(partial)
    assert lo == 46.5
    assert hi == rt._DEFAULT_FREQ_TRIP_HZ[1]
    # Absent table → both defaults.
    assert rt._freq_trip_from_trip_table({}) == rt._DEFAULT_FREQ_TRIP_HZ


# ------------------------------------------------------------------- case specs


def test_build_case_spec_lvrt() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("lvrt", env)
    assert spec.kind == "lvrt"
    assert spec.target_pu == 0.89
    assert spec.target_hz is None
    assert spec.fault_x_pu == 0.05
    assert spec.k_factor == 2.0
    assert "LVRT" in spec.detail


def test_build_case_spec_hvrt() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("hvrt", env)
    assert spec.kind == "hvrt"
    assert spec.disturbance == "load_rejection"  # D4b: a real swell mechanism
    assert spec.target_pu == 1.10
    assert spec.fault_x_pu is None  # HVRT is a load rejection, not an impedance fault
    assert (
        spec.ov_trip_pu == 1.3
    )  # over-voltage instantaneous-trip edge from the fixture
    assert spec.k_factor == 1.9
    assert "HVRT" in spec.detail
    assert "LOAD REJECTION" in spec.detail


def test_build_case_spec_frequency_defaults_to_over_edge() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("frequency", env)
    assert spec.kind == "frequency"
    assert spec.disturbance == "generator_trip"  # D4b default frequency mechanism
    assert spec.target_pu is None
    assert spec.fault_x_pu is None
    assert spec.target_hz == 51.5  # over-frequency continuous edge
    assert spec.freq_trip_hz == (47.0, 52.0)  # instantaneous trip band from the fixture
    assert spec.k_factor == 0.0
    assert "Frequency" in spec.detail


def test_build_case_spec_frequency_excursion_override() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("frequency", env, freq_excursion_hz=47.5)
    assert spec.target_hz == 47.5


def test_build_case_spec_frequency_load_step_mechanism() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("frequency", env, freq_mechanism="load_step")
    assert spec.disturbance == "load_step"


def test_build_case_spec_frequency_unknown_mechanism_raises() -> None:
    env = envelope_from_fixture()
    with pytest.raises(ValueError, match="unknown freq_mechanism"):
        build_case_spec("frequency", env, freq_mechanism="asteroid")


def test_build_case_spec_unknown_kind_raises() -> None:
    env = envelope_from_fixture()
    with pytest.raises(ValueError, match="unknown ride-through case"):
        build_case_spec("islanding", env)


# ------------------------------------- run (dynamic-study gate OFF, no andes) -


@pytest.mark.parametrize("kind", RIDE_THROUGH_CASES)
def test_run_case_gate_off_is_static(kind: str) -> None:
    """run_dynamics=False parses + sets up but never runs andes → NOT-RUN result.

    Nothing is physically validated, so ran/converged are False and the compliance
    verdict ``rode_through`` is an honest None — NEVER a spurious pass.
    """
    res = run_ride_through_case(kind, run_dynamics=False)
    assert isinstance(res, RideThroughResult)
    assert res.case == kind
    assert res.ran is False
    assert res.converged is False
    assert res.rode_through is None  # NOT-RUN — no spurious pass
    assert res.n_devices == 0
    assert res.min_voltage_pu is None
    assert res.max_voltage_pu is None
    assert res.bankable is False
    assert "run_dynamics=False" in res.detail
    assert "NOT the OEM-certified" in res.disclaimer


def test_run_case_gate_off_lvrt_carries_envelope_targets() -> None:
    res = run_ride_through_case("lvrt", run_dynamics=False)
    assert res.target_pu == 0.89
    assert res.k_factor == 2.0
    assert res.target_hz is None


def test_run_case_gate_off_frequency_carries_hz() -> None:
    res = run_ride_through_case("frequency", run_dynamics=False)
    assert res.target_hz == 51.5
    assert res.target_pu is None


def test_run_case_accepts_prebuilt_envelope() -> None:
    """The ``envelope=`` fast-path skips the fixture read and uses the supplied envelope."""
    env = RideThroughEnvelope(
        lvrt_enter_pu=0.8,
        hvrt_enter_pu=1.2,
        lvrt_k_factor=3.0,
        hvrt_k_factor=1.5,
        freq_continuous_hz=(48.0, 51.0),
        source="unit-test",
    )
    res = run_ride_through_case("lvrt", run_dynamics=False, envelope=env)
    assert res.target_pu == 0.8
    assert res.k_factor == 3.0
    assert "unit-test" in res.detail


def test_run_suite_gate_off_covers_all_three() -> None:
    suite = run_ride_through_suite(run_dynamics=False)
    assert set(suite) == set(RIDE_THROUGH_CASES)
    assert all(r.ran is False for r in suite.values())
    assert suite["lvrt"].target_pu == 0.89
    assert suite["hvrt"].target_pu == 1.10
    assert suite["frequency"].target_hz == 51.5


# --------------------------------- rode_through verdict (PURE, no ANDES) ------


def _env(
    enter: float = 0.89,
    *,
    hvrt_enter_pu: float = 1.10,
    ov_trip_pu: float = 1.3,
    freq_continuous_hz: tuple[float, float] = (47.5, 51.5),
    freq_trip_hz: tuple[float, float] = (47.0, 52.0),
) -> RideThroughEnvelope:
    return RideThroughEnvelope(
        lvrt_enter_pu=enter,
        hvrt_enter_pu=hvrt_enter_pu,
        lvrt_k_factor=2.0,
        hvrt_k_factor=1.9,
        freq_continuous_hz=freq_continuous_hz,
        source="unit-test",
        ov_trip_pu=ov_trip_pu,
        freq_trip_hz=freq_trip_hz,
    )


def test_lvrt_verdict_true_when_dip_and_recovery() -> None:
    """A real dip that recovers above the entry pu with no trip → rode through."""
    ev = LvrtEvidence(min_voltage_pu=0.30, recovered_voltage_pu=0.99, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env()) is True


def test_lvrt_verdict_false_when_ibr_tripped() -> None:
    """Deep dip, IBR trips → breach even if the bus later 'recovers'."""
    ev = LvrtEvidence(min_voltage_pu=0.20, recovered_voltage_pu=0.99, ibr_tripped=True)
    assert lvrt_rode_through(ev, _env()) is False


def test_lvrt_verdict_false_when_voltage_does_not_recover() -> None:
    """Converged-but-collapsed: dip injected but recovered voltage stays below entry."""
    ev = LvrtEvidence(min_voltage_pu=0.20, recovered_voltage_pu=0.60, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env()) is False


def test_lvrt_verdict_none_when_no_measurable_dip() -> None:
    """No dip below the entry pu → the ride-through path was never exercised → None."""
    ev = LvrtEvidence(min_voltage_pu=0.95, recovered_voltage_pu=1.0, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env()) is None


def test_lvrt_verdict_none_when_vmin_missing() -> None:
    ev = LvrtEvidence(min_voltage_pu=None, recovered_voltage_pu=1.0, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env()) is None


def test_lvrt_verdict_none_when_recovery_unknown() -> None:
    """Dip injected but recovered voltage unreadable → honest None, not a pass."""
    ev = LvrtEvidence(min_voltage_pu=0.30, recovered_voltage_pu=None, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env()) is None


def test_lvrt_verdict_none_when_trip_status_unknown_but_recovered() -> None:
    """Trip-status unknown (None) with a good recovery is still a pass (no trip seen)."""
    ev = LvrtEvidence(min_voltage_pu=0.30, recovered_voltage_pu=0.99, ibr_tripped=None)
    assert lvrt_rode_through(ev, _env()) is True


def test_lvrt_verdict_respects_recovery_margin() -> None:
    """A recovery that just touches the entry pu fails once a margin is demanded."""
    ev = LvrtEvidence(min_voltage_pu=0.30, recovered_voltage_pu=0.89, ibr_tripped=False)
    assert lvrt_rode_through(ev, _env(), recovery_margin_pu=0.0) is True
    assert lvrt_rode_through(ev, _env(), recovery_margin_pu=0.02) is False


# ---- dynamic-run reducer (_lvrt_dynamic_verdict): PURE, grid-free, no ANDES ---
# This reducer is what the andes LVRT path delegates to; grading its collapse→False /
# setup-failure→None mapping here keeps the fix's decision logic covered without [grid].


def test_dynamic_verdict_collapse_when_applied_fault_diverges() -> None:
    """THE FIX: an applied LVRT fault whose TDS terminated early (not converged) → False.

    A deep/long fault drives ANDES to terminate on a stability-criteria violation
    (exit_code != 0). That is a COLLAPSE — the plant did NOT ride through — so the verdict
    must be a real breach (False), NOT an honest NOT-RUN (None).
    """
    # Evidence from a diverged solve is present but garbled; the verdict must not depend on
    # it — a non-converged solve under an applied fault is False regardless.
    ev = LvrtEvidence(min_voltage_pu=0.05, recovered_voltage_pu=0.10, ibr_tripped=None)
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True,
            solved=True,
            converged=False,
            evidence=ev,
            envelope=_env(),
        )
        is False
    )


def test_dynamic_verdict_setup_failure_is_not_run() -> None:
    """No candidate case could be built (solved False / evidence None) → NOT-RUN (None)."""
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True,
            solved=False,
            converged=False,
            evidence=None,
            envelope=_env(),
        )
        is None
    )


def test_dynamic_verdict_solved_but_no_evidence_is_not_run() -> None:
    """Defensive: solved flag True but evidence missing still returns NOT-RUN, not a crash."""
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True,
            solved=True,
            converged=True,
            evidence=None,
            envelope=_env(),
        )
        is None
    )


def test_dynamic_verdict_no_fault_applied_is_not_run() -> None:
    """A solved run that injected no fault exercised no envelope → NOT-RUN (None)."""
    ev = LvrtEvidence(min_voltage_pu=0.30, recovered_voltage_pu=0.99, ibr_tripped=False)
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=False,
            solved=True,
            converged=True,
            evidence=ev,
            envelope=_env(),
        )
        is None
    )


def test_dynamic_verdict_converged_delegates_to_envelope() -> None:
    """A cleanly converged applied-fault solve is graded on the physical envelope."""
    env = _env()
    # Recovers cleanly → True (matches lvrt_rode_through).
    good = LvrtEvidence(
        min_voltage_pu=0.30, recovered_voltage_pu=0.99, ibr_tripped=False
    )
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True, solved=True, converged=True, evidence=good, envelope=env
        )
        is True
    )
    # Converged but collapsed → False (envelope breach, not a crash).
    collapsed = LvrtEvidence(
        min_voltage_pu=0.20, recovered_voltage_pu=0.60, ibr_tripped=False
    )
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True,
            solved=True,
            converged=True,
            evidence=collapsed,
            envelope=env,
        )
        is False
    )
    # Converged, dip too shallow to certify → None (envelope NOT-RUN).
    shallow = LvrtEvidence(
        min_voltage_pu=0.95, recovered_voltage_pu=1.0, ibr_tripped=False
    )
    assert (
        rt._lvrt_dynamic_verdict(
            fault_applied=True,
            solved=True,
            converged=True,
            evidence=shallow,
            envelope=env,
        )
        is None
    )


# ---- HVRT verdict (hvrt_rode_through): PURE, grid-free, no ANDES (#892) ------


def test_hvrt_verdict_true_when_swell_settles_back() -> None:
    """A real swell above the entry pu that settles back with no trip → rode through."""
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.02, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env()) is True


def test_hvrt_verdict_false_when_ibr_tripped() -> None:
    ev = HvrtEvidence(max_voltage_pu=1.15, settled_voltage_pu=1.0, ibr_tripped=True)
    assert hvrt_rode_through(ev, _env()) is False


def test_hvrt_verdict_false_when_peak_reaches_ov_trip() -> None:
    """A peak at/above the over-voltage instantaneous-trip edge is a hard breach."""
    ev = HvrtEvidence(max_voltage_pu=1.31, settled_voltage_pu=1.0, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env(ov_trip_pu=1.3)) is False


def test_hvrt_verdict_false_when_stays_swollen() -> None:
    """Converged-but-swollen: peak swelled but the bus never settles back under entry."""
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.15, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env()) is False


def test_hvrt_verdict_none_when_no_measurable_swell() -> None:
    """No swell above the entry pu → the over-voltage path was never exercised → None."""
    ev = HvrtEvidence(max_voltage_pu=1.05, settled_voltage_pu=1.0, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env()) is None


def test_hvrt_verdict_none_when_vmax_missing() -> None:
    ev = HvrtEvidence(max_voltage_pu=None, settled_voltage_pu=1.0, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env()) is None


def test_hvrt_verdict_none_when_settle_unknown() -> None:
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=None, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env()) is None


def test_hvrt_verdict_respects_settle_margin() -> None:
    """A settle that just touches the entry pu fails once a below-entry margin is demanded."""
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.10, ibr_tripped=False)
    assert hvrt_rode_through(ev, _env(), settle_margin_pu=0.0) is True
    assert hvrt_rode_through(ev, _env(), settle_margin_pu=0.02) is False


def test_hvrt_verdict_none_when_trip_unknown_but_settled() -> None:
    """Trip-status unknown (None) with a good settle is still a pass (no trip seen)."""
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.02, ibr_tripped=None)
    assert hvrt_rode_through(ev, _env()) is True


# ---- HVRT dynamic reducer (_hvrt_dynamic_verdict): PURE, grid-free -----------


def test_hvrt_dynamic_verdict_collapse_when_diverged() -> None:
    """A runaway over-voltage that diverges under an APPLIED swell → False (collapse)."""
    ev = HvrtEvidence(max_voltage_pu=1.5, settled_voltage_pu=1.4, ibr_tripped=None)
    assert (
        rt._hvrt_dynamic_verdict(
            swell_applied=True,
            solved=True,
            converged=False,
            evidence=ev,
            envelope=_env(),
        )
        is False
    )


def test_hvrt_dynamic_verdict_setup_failure_is_none() -> None:
    assert (
        rt._hvrt_dynamic_verdict(
            swell_applied=True,
            solved=False,
            converged=False,
            evidence=None,
            envelope=_env(),
        )
        is None
    )


def test_hvrt_dynamic_verdict_no_swell_is_none() -> None:
    ev = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.0, ibr_tripped=False)
    assert (
        rt._hvrt_dynamic_verdict(
            swell_applied=False,
            solved=True,
            converged=True,
            evidence=ev,
            envelope=_env(),
        )
        is None
    )


def test_hvrt_dynamic_verdict_converged_delegates_to_envelope() -> None:
    good = HvrtEvidence(max_voltage_pu=1.18, settled_voltage_pu=1.02, ibr_tripped=False)
    assert (
        rt._hvrt_dynamic_verdict(
            swell_applied=True,
            solved=True,
            converged=True,
            evidence=good,
            envelope=_env(),
        )
        is True
    )


# ---- frequency extreme + verdict (frequency_rode_through): PURE, grid-free ----


def test_freq_extreme_picks_furthest_from_nominal() -> None:
    """The binding extreme is whichever of nadir/zenith deviates MORE from nominal."""
    # Zenith 51.0 (dev 1.0) vs nadir 49.4 (dev 0.6) → zenith binds.
    ev = FreqEvidence(nadir_hz=49.4, zenith_hz=51.0, settled_hz=50.0, ibr_tripped=False)
    assert freq_extreme_hz(ev, nominal_hz=50.0) == 51.0
    # Nadir 48.0 (dev 2.0) vs zenith 50.5 (dev 0.5) → nadir binds.
    ev2 = FreqEvidence(
        nadir_hz=48.0, zenith_hz=50.5, settled_hz=50.0, ibr_tripped=False
    )
    assert freq_extreme_hz(ev2, nominal_hz=50.0) == 48.0


def test_freq_extreme_none_when_unmeasured() -> None:
    ev = FreqEvidence(nadir_hz=None, zenith_hz=None, settled_hz=None, ibr_tripped=False)
    assert freq_extreme_hz(ev, nominal_hz=50.0) is None


def test_freq_verdict_true_when_excursion_settles_back() -> None:
    """A real excursion past the band that settles back inside, no trip → rode through."""
    ev = FreqEvidence(nadir_hz=47.3, zenith_hz=50.0, settled_hz=49.9, ibr_tripped=False)
    assert frequency_rode_through(ev, _env()) is True


def test_freq_verdict_false_when_ibr_tripped() -> None:
    ev = FreqEvidence(nadir_hz=47.3, zenith_hz=50.0, settled_hz=49.9, ibr_tripped=True)
    assert frequency_rode_through(ev, _env()) is False


def test_freq_verdict_false_when_extreme_reaches_trip_band() -> None:
    """A nadir at/below the under-frequency instantaneous-trip edge is a hard breach."""
    ev = FreqEvidence(nadir_hz=46.9, zenith_hz=50.0, settled_hz=49.9, ibr_tripped=False)
    assert frequency_rode_through(ev, _env(freq_trip_hz=(47.0, 52.0))) is False


def test_freq_verdict_false_when_does_not_settle_back() -> None:
    """Excursion past the band that never settles back inside the continuous band → False."""
    ev = FreqEvidence(nadir_hz=47.2, zenith_hz=50.0, settled_hz=47.0, ibr_tripped=False)
    assert frequency_rode_through(ev, _env()) is False


def test_freq_verdict_none_when_stays_in_band() -> None:
    """The frequency never left the continuous band → path not exercised → None."""
    ev = FreqEvidence(nadir_hz=49.9, zenith_hz=50.1, settled_hz=50.0, ibr_tripped=False)
    assert frequency_rode_through(ev, _env()) is None


def test_freq_verdict_none_when_extreme_unmeasured() -> None:
    ev = FreqEvidence(nadir_hz=None, zenith_hz=None, settled_hz=None, ibr_tripped=False)
    assert frequency_rode_through(ev, _env()) is None


def test_freq_verdict_none_when_settle_unknown() -> None:
    ev = FreqEvidence(nadir_hz=47.3, zenith_hz=50.0, settled_hz=None, ibr_tripped=False)
    assert frequency_rode_through(ev, _env()) is None


# ---- frequency dynamic reducer (_frequency_dynamic_verdict): PURE, grid-free -


def test_freq_dynamic_verdict_collapse_when_diverged() -> None:
    """A runaway frequency that diverges under an APPLIED excursion → False (collapse)."""
    ev = FreqEvidence(nadir_hz=45.0, zenith_hz=50.0, settled_hz=44.0, ibr_tripped=None)
    assert (
        rt._frequency_dynamic_verdict(
            excursion_applied=True,
            solved=True,
            converged=False,
            evidence=ev,
            envelope=_env(),
        )
        is False
    )


def test_freq_dynamic_verdict_setup_failure_is_none() -> None:
    assert (
        rt._frequency_dynamic_verdict(
            excursion_applied=True,
            solved=False,
            converged=False,
            evidence=None,
            envelope=_env(),
        )
        is None
    )


def test_freq_dynamic_verdict_no_excursion_is_none() -> None:
    ev = FreqEvidence(nadir_hz=47.3, zenith_hz=50.0, settled_hz=49.9, ibr_tripped=False)
    assert (
        rt._frequency_dynamic_verdict(
            excursion_applied=False,
            solved=True,
            converged=True,
            evidence=ev,
            envelope=_env(),
        )
        is None
    )


def test_freq_dynamic_verdict_converged_delegates_to_envelope() -> None:
    good = FreqEvidence(
        nadir_hz=47.3, zenith_hz=50.0, settled_hz=49.9, ibr_tripped=False
    )
    assert (
        rt._frequency_dynamic_verdict(
            excursion_applied=True,
            solved=True,
            converged=True,
            evidence=good,
            envelope=_env(),
        )
        is True
    )


# --- ALL cases with the gate ON require the [grid] extra (CASPER, no silent pass) --
# D4b (#892): HVRT and frequency are now physically modeled — a gate-ON call therefore
# reaches the CASPER _require_andes guard (no more grid-free NOT-RUN short-circuit). Without
# andes it raises loud; it NEVER returns a fabricated pass.


@pytest.mark.parametrize("kind", ["lvrt", "hvrt", "frequency"])
def test_run_dynamics_gate_on_requires_grid_extra(kind: str) -> None:
    """Gate-ON reaches _require_andes for EVERY case; absent [grid] it raises, never passes."""
    try:
        import andes  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match=r"\[grid\] extra"):
            run_ride_through_case(kind, run_dynamics=True)
    else:  # pragma: no cover - only when the [grid] extra is installed
        res = run_ride_through_case(kind, run_dynamics=True)
        assert res.rode_through in (True, False, None)


# ---------------------------------------------- RideThroughResult contract ----


def test_from_case_stamps_disclaimer_and_bankable_false() -> None:
    res = RideThroughResult.from_case(
        case="lvrt",
        ran=True,
        converged=True,
        rode_through=True,
        target_pu=0.89,
        k_factor=2.0,
        min_voltage_pu=0.42,
        n_devices=3,
        detail="unit",
    )
    assert res.bankable is False
    assert "NOT the OEM-certified" in res.disclaimer
    assert "generic wecc" in res.provenance.lower()
    assert res.ran is True and res.converged is True
    assert res.rode_through is True


def test_from_case_rode_through_defaults_to_none_not_converged() -> None:
    """rode_through is NOT defaulted from converged — a converged case is not a pass."""
    res = RideThroughResult.from_case(case="lvrt", ran=True, converged=True)
    assert res.converged is True
    assert res.rode_through is None  # must be passed explicitly, never inferred


def test_ride_through_result_is_frozen_and_dumps() -> None:
    res = RideThroughResult.from_case(case="hvrt", ran=False, converged=False)
    with pytest.raises(FrozenInstanceError):
        res.ran = True  # type: ignore[misc]  # frozen dataclass
    dumped = res.model_dump()
    assert dumped["case"] == "hvrt"
    assert dumped["bankable"] is False
    assert "disclaimer" in dumped


# ------------------------------------------------- SHIM (ride_through_poc) -----


def test_poc_shim_lvrt_enter_delegates() -> None:
    """The legacy ``lvrt_enter_from_fixture`` re-exports the core's envelope value."""
    assert ride_through_poc.lvrt_enter_from_fixture() == 0.89
    assert (
        ride_through_poc.lvrt_enter_from_fixture(Path("/nonexistent.yaml"))
        == rt._DEFAULT_LVRT_ENTER_PU
    )


def test_poc_shim_require_andes_is_core_guard() -> None:
    """The shim re-exports the core's _require_andes (single source of truth)."""
    assert ride_through_poc._require_andes is rt._require_andes


def test_poc_shim_result_shape_preserved() -> None:
    """LvrtScaffoldResult retains the legacy fields (backward compatibility)."""
    fields = ride_through_poc.LvrtScaffoldResult.__dataclass_fields__
    assert set(fields) >= {
        "ran",
        "lvrt_enter_pu",
        "detail",
        "n_devices",
        "min_bus_voltage_pu",
    }
