"""Grid-FREE coverage for the D4b wind grid-capability plug-in (#876).

These tests import NO grid library (``andes`` / ``pandapower`` are ABSENT in the default
venv) and are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage
lane and carry the real coverage for :mod:`analytics.grid.capabilities.wind`. They
exercise ALL the pure logic:

  * the turbine converter-type discriminators added in :mod:`finance.grid.grid_types`
    (``is_type3_dfig`` / ``is_type4_full_converter`` / ``is_known_wind_converter_type``
    incl. their alias/normalisation branches);
  * ``resolve_wind_converter_spec`` (Type-3 / Type-4, explicit Q vs pf_range, and every
    strict ValueError branch: unknown converter, non-positive rating, undetermined Q);
  * the topology-aware PQ-envelope math (``q_capability_mvar_at_p`` — the RECTANGULAR
    Type-4 box vs the partial-load-NARROWING Type-3 DFIG box — and
    ``build_wind_pq_envelope`` incl. its pf-range ValueError);
  * ``assemble_reactive_result`` (governing-point selection, shortfall, PQ-box verdict,
    advisory ``bankable=False``) for an ample and a reactive-tight DFIG config;
  * ``screen_wind_capability`` on the DYNAMICS-GATE-OFF path (LVRT NOT-RUN, no ANDES),
    with the D0 fixture, a fixture override, and a pre-parsed ride-through envelope.

The LVRT dynamics (ANDES) path is delegated to the D4a core, whose andes-only code is
already ``# pragma: no cover - requires [grid] extra`` and is exercised by the
``grid``-marked ``test_wind_capability_dynamics.py`` under ``pip install -e '.[grid]'``.
"""

from __future__ import annotations

import math
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from analytics.contracts_v14 import ReactiveCapabilityResult, RideThroughResult
from analytics.grid.capabilities import wind
from analytics.grid.capabilities.wind import (
    WindCapabilityResult,
    WindConverterSpec,
    WindPQEnvelopePoint,
    assemble_reactive_result,
    build_wind_pq_envelope,
    q_capability_mvar_at_p,
    resolve_wind_converter_spec,
    screen_wind_capability,
)
from analytics.grid.ride_through import RideThroughEnvelope, envelope_from_fixture
from finance.grid.grid_types import (
    is_known_wind_converter_type,
    is_type3_dfig,
    is_type4_full_converter,
)

_D0_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "grid"
    / "envision_enpcs01_gridcode.yaml"
)

# A DutchBay-shaped wind grid block: 159.6 MVA, ±0.95 pf grid-code envelope, reactive
# rating derived from the same pf_range so the plant EXACTLY meets the demand at rated.
_WIND_T4 = {
    "rated_mva": 159.6,
    "turbine": {"converter_type": "type4_full_converter", "pf_range": [-0.95, 0.95]},
    "gridcode": {"pf_range": [-0.95, 0.95]},
}
_WIND_T3 = {
    "rated_mva": 159.6,
    "turbine": {"converter_type": "type3_dfig", "pf_range": [-0.95, 0.95]},
    "gridcode": {"pf_range": [-0.95, 0.95]},
}


# --------------------------------------------------------------- converter-type enum


@pytest.mark.parametrize(
    "token",
    [
        "type4_full_converter",
        "type4",
        "full_converter",
        "Full-Scale-Converter",
        " TYPE4 ",
    ],
)
def test_is_type4_full_converter_aliases(token: str) -> None:
    assert is_type4_full_converter(token) is True
    assert is_type3_dfig(token) is False
    assert is_known_wind_converter_type(token) is True


@pytest.mark.parametrize(
    "token", ["type3_dfig", "type3", "DFIG", "doubly_fed", " dfig "]
)
def test_is_type3_dfig_aliases(token: str) -> None:
    assert is_type3_dfig(token) is True
    assert is_type4_full_converter(token) is False
    assert is_known_wind_converter_type(token) is True


@pytest.mark.parametrize("token", [None, "", "type5", "gfl", "solar", 3])
def test_unknown_wind_converter_types(token: object) -> None:
    assert is_known_wind_converter_type(token) is False
    assert is_type3_dfig(token) is False
    assert is_type4_full_converter(token) is False


# --------------------------------------------------------------- spec resolution


def test_resolve_spec_type4_from_pf_range() -> None:
    spec = resolve_wind_converter_spec(_WIND_T4)
    assert spec.converter_type == "type4_full_converter"
    assert spec.is_full_converter is True
    assert spec.rated_mva == pytest.approx(159.6)
    # ±Q at rated = rated · tan(acos(0.95)).
    assert spec.q_max_mvar == pytest.approx(159.6 * math.tan(math.acos(0.95)))


def test_resolve_spec_type3_from_explicit_q() -> None:
    grid = {
        "rated_mva": 160.0,
        "turbine": {"converter_type": "type3_dfig"},
        "reactive_capability": {"max_q_mvar": -55.0},  # magnitude taken
    }
    spec = resolve_wind_converter_spec(grid)
    assert spec.converter_type == "type3_dfig"
    assert spec.is_full_converter is False
    assert spec.q_max_mvar == pytest.approx(55.0)


def test_resolve_spec_converter_type_top_level_fallback() -> None:
    # converter_type may sit directly on the grid block (no turbine sub-map).
    grid = {"rated_mva": 100.0, "converter_type": "type4", "pf_range": [-0.9, 0.9]}
    spec = resolve_wind_converter_spec(grid)
    assert spec.is_full_converter is True
    assert spec.q_max_mvar == pytest.approx(100.0 * math.tan(math.acos(0.9)))


def test_resolve_spec_unknown_converter_raises() -> None:
    with pytest.raises(ValueError, match="recognised wind turbine topology"):
        resolve_wind_converter_spec(
            {"rated_mva": 100.0, "turbine": {"converter_type": "gfm"}}
        )


@pytest.mark.parametrize("bad", [0.0, -5.0, "x", None, True])
def test_resolve_spec_bad_rating_raises(bad: object) -> None:
    with pytest.raises(ValueError, match="rated_mva"):
        resolve_wind_converter_spec(
            {"rated_mva": bad, "turbine": {"converter_type": "type4"}}
        )


def test_resolve_spec_undetermined_q_raises() -> None:
    with pytest.raises(ValueError, match="reactive rating undetermined"):
        resolve_wind_converter_spec(
            {"rated_mva": 100.0, "turbine": {"converter_type": "type4"}}
        )


def test_resolve_spec_nonpositive_explicit_q_raises() -> None:
    with pytest.raises(ValueError, match="max_q_mvar must be > 0"):
        resolve_wind_converter_spec(
            {
                "rated_mva": 100.0,
                "turbine": {"converter_type": "type4"},
                "reactive_capability": {"max_q_mvar": 0.0},
            }
        )


# The BINDING endpoint is the smaller |pf|; only a bad binding endpoint raises.
@pytest.mark.parametrize("pf", [[0.0, 0.9], [-1.5, 0.0], [0.0, 0.0]])
def test_resolve_spec_bad_pf_range_raises(pf: list[float]) -> None:
    with pytest.raises(ValueError, match="magnitude in"):
        resolve_wind_converter_spec(
            {"rated_mva": 100.0, "turbine": {"converter_type": "type3", "pf_range": pf}}
        )


def test_resolve_spec_wide_pf_endpoint_uses_binding() -> None:
    # A wide (|pf|>1) endpoint is fine as long as the BINDING (smaller |pf|) one is valid.
    spec = resolve_wind_converter_spec(
        {
            "rated_mva": 100.0,
            "turbine": {"converter_type": "type4", "pf_range": [-2.0, 0.9]},
        }
    )
    assert spec.q_max_mvar == pytest.approx(100.0 * math.tan(math.acos(0.9)))


# --------------------------------------------------------------- PQ envelope math


def test_type4_box_is_rectangular_constant_across_p() -> None:
    """Type-4 full converter: ±Q is CONSTANT across the whole active-power range."""
    spec = WindConverterSpec("type4_full_converter", True, 160.0, 50.0)
    for p in (0.0, 40.0, 80.0, 120.0, 160.0):
        assert q_capability_mvar_at_p(spec, p) == pytest.approx(50.0)


def test_type3_dfig_box_narrows_at_partial_load() -> None:
    """Type-3 DFIG: ±Q shrinks as active power drops, flooring at the zero-P reserve."""
    spec = WindConverterSpec("type3_dfig", False, 160.0, 50.0)
    q_rated = q_capability_mvar_at_p(spec, 160.0)
    q_half = q_capability_mvar_at_p(spec, 80.0)
    q_zero = q_capability_mvar_at_p(spec, 0.0)
    assert q_rated == pytest.approx(50.0)  # full at rated
    assert q_zero == pytest.approx(50.0 * 0.10)  # 10 % floor at zero P
    # Strictly monotone-increasing with P and strictly below the full box at partial load.
    assert q_zero < q_half < q_rated
    assert q_half < 50.0
    # Linear interpolation: floor + (1-floor)·frac.
    assert q_half == pytest.approx(50.0 * (0.10 + 0.90 * 0.5))


def test_q_capability_clamps_p_out_of_range() -> None:
    spec = WindConverterSpec("type3_dfig", False, 100.0, 40.0)
    # P above rated clamps to the full box; negative P uses |P| and clamps to floor.
    assert q_capability_mvar_at_p(spec, 250.0) == pytest.approx(40.0)
    assert q_capability_mvar_at_p(spec, -0.0) == pytest.approx(40.0 * 0.10)


def test_q_capability_zero_rating_is_safe() -> None:
    spec = WindConverterSpec("type4_full_converter", True, 0.0, 0.0)
    assert q_capability_mvar_at_p(spec, 10.0) == pytest.approx(0.0)


def test_build_pq_envelope_points_and_shortfall() -> None:
    spec = resolve_wind_converter_spec(_WIND_T3)
    pts = build_wind_pq_envelope(spec, 0.95, p_steps=5)
    assert len(pts) == 5
    assert pts[0].p_mw == pytest.approx(0.0)
    assert pts[-1].p_mw == pytest.approx(159.6)
    # At rated, demand == available (both derived from the same 0.95 pf) → no shortfall.
    assert pts[-1].shortfall_mvar == pytest.approx(0.0, abs=1e-9)
    assert all(isinstance(p, WindPQEnvelopePoint) for p in pts)


def test_build_pq_envelope_bad_pf_raises() -> None:
    spec = WindConverterSpec("type4_full_converter", True, 100.0, 40.0)
    with pytest.raises(ValueError, match="pf_required must be"):
        build_wind_pq_envelope(spec, 1.5)


def test_build_pq_envelope_clamps_steps() -> None:
    spec = WindConverterSpec("type4_full_converter", True, 100.0, 40.0)
    assert len(build_wind_pq_envelope(spec, 0.9, p_steps=1)) == 2  # clamped to >= 2


# --------------------------------------------------------------- reactive result


def test_assemble_reactive_result_ample_inside_box() -> None:
    spec = resolve_wind_converter_spec(_WIND_T4)
    res = assemble_reactive_result(spec, _WIND_T4)
    assert isinstance(res, ReactiveCapabilityResult)
    assert res.inside_pq_box is True
    assert res.mvar_shortfall == pytest.approx(0.0, abs=1e-9)
    assert res.method == "wind_pq_envelope"
    assert res.bankable is False
    assert res.pf_required_min == pytest.approx(-0.95)
    assert res.pf_required_max == pytest.approx(0.95)


def test_assemble_reactive_result_dfig_partial_load_shortfall() -> None:
    """A DFIG whose box narrows below the code demand surfaces a governing shortfall."""
    grid = {
        "rated_mva": 160.0,
        "turbine": {"converter_type": "type3_dfig"},
        "reactive_capability": {"max_q_mvar": 60.0},
        "gridcode": {"pf_range": [-0.90, 0.90]},
    }
    spec = resolve_wind_converter_spec(grid)
    res = assemble_reactive_result(spec, grid, p_steps=5)
    assert res.inside_pq_box is False
    assert res.mvar_shortfall > 0.0
    # The governing (worst) point is at rated (deepest demand), and available < required.
    assert res.governing_p_mw == pytest.approx(160.0)
    assert res.mvar_available < res.mvar_required


def test_assemble_reactive_result_requires_gridcode_pf_range() -> None:
    spec = resolve_wind_converter_spec(_WIND_T4)
    with pytest.raises(ValueError, match="gridcode.pf_range"):
        assemble_reactive_result(spec, {"rated_mva": 159.6})


@pytest.mark.parametrize("bad_pf", [[0.0, 0.9], [-2.0, 0.0]])
def test_assemble_reactive_result_bad_pf_range_raises(bad_pf: list[float]) -> None:
    spec = resolve_wind_converter_spec(_WIND_T4)
    with pytest.raises(ValueError, match="magnitude in"):
        assemble_reactive_result(spec, {"gridcode": {"pf_range": bad_pf}})


def test_pf_at_poc_zero_apparent_power_is_unity() -> None:
    # P=0, Q=0 → apparent power 0 → unity pf (the S<=0 guard branch).
    assert wind._pf_at_poc(0.0, 0.0) == pytest.approx(1.0)
    # Sign follows Q: leading (Q>0) → +pf, lagging (Q<0) → -pf; Q=0 → +1.
    assert wind._pf_at_poc(10.0, 5.0) > 0.0
    assert wind._pf_at_poc(10.0, -5.0) < 0.0
    assert wind._pf_at_poc(10.0, 0.0) == pytest.approx(1.0)


# --------------------------------------------------------------- full plug-in (gate off)


def test_screen_wind_capability_gate_off_lvrt_not_run() -> None:
    """Default (run_dynamics=False): reactive computed, LVRT NOT-RUN (no ANDES)."""
    res = screen_wind_capability(_WIND_T4)
    assert isinstance(res, WindCapabilityResult)
    assert res.converter_type == "type4_full_converter"
    assert isinstance(res.reactive, ReactiveCapabilityResult)
    assert res.reactive.inside_pq_box is True
    # LVRT delegated to the D4a core with the dynamics gate OFF → honest NOT-RUN.
    assert isinstance(res.lvrt, RideThroughResult)
    assert res.lvrt.case == "lvrt"
    assert res.lvrt.ran is False
    assert res.lvrt.rode_through is None  # NOT-RUN, never a spurious pass
    assert res.lvrt.target_pu == pytest.approx(0.89)  # seeded from the D0 fixture
    assert res.lvrt.k_factor == pytest.approx(2.0)
    assert res.lvrt.bankable is False
    # The swept PQ envelope is exposed for reporting.
    assert len(res.envelope_points) == 5
    assert all(isinstance(p, WindPQEnvelopePoint) for p in res.envelope_points)


def test_screen_wind_capability_type3_narrowing_envelope() -> None:
    res = screen_wind_capability(_WIND_T3)
    assert res.converter_type == "type3_dfig"
    q_at_zero = res.envelope_points[0].q_available_mvar
    q_at_rated = res.envelope_points[-1].q_available_mvar
    assert q_at_zero < q_at_rated  # narrows at partial load


def test_screen_wind_capability_fixture_override() -> None:
    """A fixture-path override flows through to the LVRT envelope seed."""
    res = screen_wind_capability(_WIND_T4, fixture_path=_D0_FIXTURE)
    assert res.lvrt.target_pu == pytest.approx(0.89)


def test_screen_wind_capability_preparsed_envelope_skips_fixture() -> None:
    env = RideThroughEnvelope(
        lvrt_enter_pu=0.85,
        hvrt_enter_pu=1.15,
        lvrt_k_factor=2.5,
        hvrt_k_factor=0.0,
        freq_continuous_hz=(47.5, 51.5),
        source="unit-test",
    )
    res = screen_wind_capability(_WIND_T4, ride_through_envelope=env)
    assert res.lvrt.target_pu == pytest.approx(0.85)
    assert res.lvrt.k_factor == pytest.approx(2.5)


def test_envelope_from_fixture_matches_lvrt_seed() -> None:
    """Sanity: the plug-in's LVRT seed equals the shared core's fixture parse."""
    env = envelope_from_fixture(_D0_FIXTURE)
    res = screen_wind_capability(_WIND_T4, ride_through_envelope=env)
    assert res.lvrt.target_pu == pytest.approx(env.lvrt_enter_pu)


# --------------------------------------------------------------- dataclass hygiene


def test_result_dataclasses_are_frozen() -> None:
    spec = WindConverterSpec("type4_full_converter", True, 100.0, 40.0)
    with pytest.raises(FrozenInstanceError):
        spec.rated_mva = 200.0  # type: ignore[misc]
    pt = WindPQEnvelopePoint(1.0, 2.0, 3.0, 1.0)
    with pytest.raises(FrozenInstanceError):
        pt.p_mw = 5.0  # type: ignore[misc]


def test_module_imports_without_grid_libs(monkeypatch: pytest.MonkeyPatch) -> None:
    """The plug-in must import (and stay usable) with no grid library importable.

    andes absence is SIMULATED (poisoned ``sys.modules`` entry) so the assertion is
    environment-independent — the already-imported plug-in keeps working even when
    ``import andes`` raises, with or without the [grid] extra installed.
    """
    monkeypatch.setitem(sys.modules, "andes", None)
    assert hasattr(wind, "screen_wind_capability")
    with pytest.raises(ImportError):
        __import__("andes")
