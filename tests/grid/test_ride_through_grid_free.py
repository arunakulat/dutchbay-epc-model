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
    RideThroughEnvelope,
    build_case_spec,
    envelope_from_fixture,
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
    spec = build_case_spec("hvrt", env, hvrt_fault_x_pu=7.0)
    assert spec.kind == "hvrt"
    assert spec.target_pu == 1.10
    assert spec.fault_x_pu == 7.0
    assert spec.k_factor == 1.9
    assert "HVRT" in spec.detail


def test_build_case_spec_frequency_defaults_to_over_edge() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("frequency", env)
    assert spec.kind == "frequency"
    assert spec.target_pu is None
    assert spec.fault_x_pu is None
    assert spec.target_hz == 51.5  # over-frequency continuous edge
    assert spec.k_factor == 0.0
    assert "Frequency" in spec.detail


def test_build_case_spec_frequency_excursion_override() -> None:
    env = envelope_from_fixture()
    spec = build_case_spec("frequency", env, freq_excursion_hz=47.5)
    assert spec.target_hz == 47.5


def test_build_case_spec_unknown_kind_raises() -> None:
    env = envelope_from_fixture()
    with pytest.raises(ValueError, match="unknown ride-through case"):
        build_case_spec("islanding", env)


# ------------------------------------- run (dynamic-study gate OFF, no andes) -


@pytest.mark.parametrize("kind", RIDE_THROUGH_CASES)
def test_run_case_gate_off_is_static(kind: str) -> None:
    """run_dynamics=False parses + sets up but never runs andes → ran/converged False."""
    res = run_ride_through_case(kind, run_dynamics=False)
    assert isinstance(res, RideThroughResult)
    assert res.case == kind
    assert res.ran is False
    assert res.converged is False
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


# ---------------------------------------------- RideThroughResult contract ----


def test_from_case_stamps_disclaimer_and_bankable_false() -> None:
    res = RideThroughResult.from_case(
        case="lvrt",
        ran=True,
        converged=True,
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
