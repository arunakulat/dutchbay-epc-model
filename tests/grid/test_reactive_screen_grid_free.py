"""Grid-FREE coverage for the D3 reactive/voltage screen (#874).

These tests import NO grid library (pandapower is ABSENT in the default venv) and are
NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and
carry the real coverage for :mod:`analytics.grid.reactive_screen`. They exercise:

  * every pure helper (``pf_to_qp_ratio``, ``_resource_q_limits_mvar``,
    ``_required_mvar_at_p``, ``_pf_from_pq``, ``_grid_voltage_window``,
    ``_required_pf_magnitude``, ``_iter_resources``) incl. their ValueError branches; and
  * the CLOSED-FORM fallback of ``screen_reactive_capability`` (``use_pandapower=False``)
    — the P-sweep, the else branch, and ``ReactiveCapabilityResult.from_screen`` — for
    both a reactive-tight config (non-zero shortfall) and an ample one (zero shortfall).

The genuinely pandapower-only code (``_build_network``, ``_poc_pf_and_voltage``, and the
``runpp`` branch inside ``screen_reactive_capability``) is ``# pragma: no cover -
requires [grid] extra`` and is exercised instead by the ``grid``-marked
``test_reactive_screen_d3.py`` under ``pip install -e '.[grid]'``.
"""

from __future__ import annotations

import math

import pytest

from analytics.contracts_v14 import ReactiveCapabilityResult
from analytics.grid import reactive_screen as rs
from analytics.grid.reactive_screen import (
    DEFAULT_GRID_VOLTAGE_WINDOW_PU,
    pf_to_qp_ratio,
    screen_reactive_capability,
)

# A DutchBay-shaped grid block (mirrors test_reactive_screen_d3.py) whose aggregate
# reactive headroom (40 Mvar) is BELOW the code demand at rated (~52.5 Mvar for 0.95 pf
# at 159.6 MW) → a guaranteed, sizeable shortfall in the closed-form screen too.
_TIGHT_GRID = {
    "study_enabled": True,
    "poc_voltage_kv": 33.0,
    "plant_rating_mva": 159.6,
    "poc": {"bus_name": "Puttalam 220kV", "nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "gridcode": {"pf_range": [-0.95, 0.95], "voltage_window_pu": [0.9, 1.1]},
    "poc_transformer": {"r_ohm": 0.05, "x_ohm": 1.2},
    "collector_equivalent": {"nominal_kv": 33.0, "r_ohm": 0.05, "x_ohm": 0.2},
    "resources": [
        {
            "name": "wind_aggregate",
            "rated_mva": 159.6,
            "reactive_capability": {"min_q_mvar": -40.0, "max_q_mvar": 40.0},
        }
    ],
}


# --------------------------------------------------------------------------- helpers


def test_pf_to_qp_ratio_valid() -> None:
    # 0.95 pf → tan(acos(0.95)) ≈ 0.3287 Mvar/MW; pf = 1 → 0 (unity, no reactive).
    assert pf_to_qp_ratio(0.95) == pytest.approx(math.tan(math.acos(0.95)))
    assert pf_to_qp_ratio(1.0) == pytest.approx(0.0)
    # A signed pf uses its magnitude only.
    assert pf_to_qp_ratio(-0.9) == pytest.approx(pf_to_qp_ratio(0.9))


@pytest.mark.parametrize("bad_pf", [0.0, -0.0, 1.5, -2.0])
def test_pf_to_qp_ratio_out_of_range_raises(bad_pf: float) -> None:
    with pytest.raises(ValueError, match="magnitude must be in"):
        pf_to_qp_ratio(bad_pf)


def test_resource_q_limits_from_explicit_capability() -> None:
    lo, hi = rs._resource_q_limits_mvar(
        {"reactive_capability": {"min_q_mvar": -40.0, "max_q_mvar": 40.0}}
    )
    assert (lo, hi) == (-40.0, 40.0)


def test_resource_q_limits_explicit_capability_inverted_raises() -> None:
    with pytest.raises(ValueError, match="min_q_mvar .* must be <="):
        rs._resource_q_limits_mvar(
            {"reactive_capability": {"min_q_mvar": 40.0, "max_q_mvar": -40.0}}
        )


def test_resource_q_limits_from_pf_range_and_rated_mva() -> None:
    # pf_range [-0.95, 0.95] + 159.6 MVA → ±(159.6 * tan(acos(0.95))) headroom.
    lo, hi = rs._resource_q_limits_mvar({"pf_range": [-0.95, 0.95], "rated_mva": 159.6})
    expected = 159.6 * pf_to_qp_ratio(0.95)
    assert lo == pytest.approx(-expected)
    assert hi == pytest.approx(expected)


@pytest.mark.parametrize(
    "resource",
    [
        {},  # neither form present
        {"pf_range": [-0.95, 0.95]},  # pf_range without rated_mva
        {"pf_range": [-0.95], "rated_mva": 159.6},  # wrong-length pf_range
        {"pf_range": "-0.95,0.95", "rated_mva": 159.6},  # string, not a sequence
        {"pf_range": [-0.95, 0.95], "rated_mva": 0.0},  # non-positive rating
        {"pf_range": [-0.95, 0.95], "rated_mva": True},  # bool is not a rating
    ],
)
def test_resource_q_limits_undetermined_raises(resource: dict) -> None:
    with pytest.raises(ValueError, match="reactive capability is undetermined"):
        rs._resource_q_limits_mvar(resource)


def test_required_mvar_at_p() -> None:
    # 159.6 MW at 0.95 pf → 159.6 * tan(acos(0.95)) Mvar.
    assert rs._required_mvar_at_p(159.6, 0.95) == pytest.approx(
        159.6 * pf_to_qp_ratio(0.95)
    )
    # Zero power → zero reactive demand.
    assert rs._required_mvar_at_p(0.0, 0.95) == pytest.approx(0.0)


def test_pf_from_pq_signed_and_edge_branches() -> None:
    # Positive Q → leading (+pf); the magnitude is P/|S|.
    p, q = 100.0, 50.0
    pf = rs._pf_from_pq(p, q)
    assert pf > 0.0
    assert pf == pytest.approx(p / math.hypot(p, q))
    # Negative Q → lagging (−pf).
    assert rs._pf_from_pq(100.0, -50.0) < 0.0
    # q == 0 branch → unity (1.0), not signed.
    assert rs._pf_from_pq(100.0, 0.0) == pytest.approx(1.0)
    # s <= 0 branch (P == Q == 0) → unity by convention.
    assert rs._pf_from_pq(0.0, 0.0) == pytest.approx(1.0)


def test_grid_voltage_window_from_config() -> None:
    lo, hi = rs._grid_voltage_window({"gridcode": {"voltage_window_pu": [0.92, 1.08]}})
    assert (lo, hi) == (0.92, 1.08)


@pytest.mark.parametrize(
    "grid",
    [
        {},  # no gridcode at all → default
        {"gridcode": {}},  # gridcode without a window → default
        {"gridcode": {"voltage_window_pu": [1.1, 0.9]}},  # lo >= hi → default
        {"gridcode": {"voltage_window_pu": [0.95]}},  # wrong length → default
        {"gridcode": {"voltage_window_pu": "0.9,1.1"}},  # string → default
    ],
)
def test_grid_voltage_window_defaults(grid: dict) -> None:
    assert rs._grid_voltage_window(grid) == DEFAULT_GRID_VOLTAGE_WINDOW_PU


def test_required_pf_magnitude_valid() -> None:
    pf_req, pf_min, pf_max = rs._required_pf_magnitude(
        {"gridcode": {"pf_range": [-0.90, 0.95]}}
    )
    # The binding magnitude is the tighter (smaller |pf|) endpoint.
    assert pf_req == pytest.approx(0.90)
    assert (pf_min, pf_max) == (-0.90, 0.95)


@pytest.mark.parametrize(
    "grid",
    [
        {},  # no gridcode → pf_range absent
        {"gridcode": {}},  # gridcode without pf_range
        {"gridcode": {"pf_range": [-0.95]}},  # wrong length
        {"gridcode": {"pf_range": "-0.95,0.95"}},  # string, not a sequence
    ],
)
def test_required_pf_magnitude_missing_range_raises(grid: dict) -> None:
    with pytest.raises(ValueError, match="pf_range .* is required"):
        rs._required_pf_magnitude(grid)


@pytest.mark.parametrize("pf_range", [[0.0, 0.95], [-1.5, -1.2]])
def test_required_pf_magnitude_out_of_range_raises(pf_range: list) -> None:
    # The binding (smaller-|pf|) endpoint is out of (0, 1]: 0.0 in the first, 1.2 in the
    # second (min(1.5, 1.2) = 1.2 > 1) — both must raise.
    with pytest.raises(ValueError, match="magnitude in"):
        rs._required_pf_magnitude({"gridcode": {"pf_range": pf_range}})


def test_iter_resources_explicit_list() -> None:
    out = rs._iter_resources(_TIGHT_GRID)
    assert len(out) == 1
    assert out[0]["name"] == "wind_aggregate"


def test_iter_resources_synthesizes_aggregate_from_poc() -> None:
    grid = {
        "poc": {"plant_rated_mva": 159.6},
        "gridcode": {"pf_range": [-0.95, 0.95]},
    }
    out = rs._iter_resources(grid)
    assert len(out) == 1
    assert out[0]["name"] == "aggregate_plant"
    assert out[0]["rated_mva"] == pytest.approx(159.6)
    assert out[0]["pf_range"] == [-0.95, 0.95]


def test_iter_resources_synthesizes_aggregate_from_flat_rating() -> None:
    # No poc.plant_rated_mva → falls back to the flat grid.plant_rating_mva.
    grid = {"plant_rating_mva": 100.0, "gridcode": {"pf_range": [-0.95, 0.95]}}
    out = rs._iter_resources(grid)
    assert out[0]["rated_mva"] == pytest.approx(100.0)


def test_iter_resources_empty_list_falls_through_to_aggregate() -> None:
    # An explicit-but-empty resources list must not short-circuit the synthesis path.
    grid = {
        "resources": [],
        "poc": {"plant_rated_mva": 50.0},
        "gridcode": {"pf_range": [-0.95, 0.95]},
    }
    out = rs._iter_resources(grid)
    assert out[0]["name"] == "aggregate_plant"


def test_iter_resources_no_resources_and_no_aggregate_raises() -> None:
    with pytest.raises(ValueError, match="no resources"):
        rs._iter_resources({"gridcode": {"pf_range": [-0.95, 0.95]}})


# ------------------------------------------------------------- closed-form screen path


def test_screen_closed_form_sizes_shortfall_for_tight_config() -> None:
    """use_pandapower=False → closed-form fallback; a reactive-tight plant is short."""
    reactive, power_flow = screen_reactive_capability(_TIGHT_GRID, use_pandapower=False)
    assert isinstance(reactive, ReactiveCapabilityResult)
    assert reactive.method == "closed_form"
    assert reactive.bankable is False
    # 40 Mvar available vs ~52.5 Mvar required at rated → non-zero shortfall.
    assert reactive.mvar_available == pytest.approx(40.0)
    assert reactive.mvar_required == pytest.approx(
        159.6 * pf_to_qp_ratio(0.95), abs=0.5
    )
    assert reactive.mvar_shortfall > 0.0
    assert reactive.mvar_shortfall == pytest.approx(
        reactive.mvar_required - reactive.mvar_available, abs=1e-6
    )
    assert reactive.inside_pq_box is False
    assert reactive.governing_p_mw == pytest.approx(159.6)
    # Closed-form fallback carries no load-flow snapshot and no grid-voltage corner.
    assert power_flow is None
    assert reactive.governing_grid_v_pu is None


def test_screen_closed_form_meets_pq_box_when_ample() -> None:
    """An ample plant clears the PQ box with zero shortfall in the closed-form screen."""
    ample = {
        **_TIGHT_GRID,
        "resources": [
            {
                "name": "wind_aggregate",
                "rated_mva": 159.6,
                "reactive_capability": {"min_q_mvar": -80.0, "max_q_mvar": 80.0},
            }
        ],
    }
    reactive, power_flow = screen_reactive_capability(ample, use_pandapower=False)
    # 80 Mvar available comfortably exceeds the ~52.5 Mvar code demand → no shortfall.
    assert reactive.mvar_shortfall == pytest.approx(0.0)
    assert reactive.inside_pq_box is True
    assert power_flow is None


def test_screen_closed_form_when_use_pandapower_true_but_absent() -> None:
    """use_pandapower=True with pandapower ABSENT falls back to the closed form.

    Covers the ``try: _require_pandapower() except ImportError: pp = None`` acquisition
    branch in the default (grid-free) venv without needing the [grid] extra.
    """
    reactive, power_flow = screen_reactive_capability(_TIGHT_GRID, use_pandapower=True)
    assert reactive.method == "closed_form"
    assert power_flow is None
    assert reactive.mvar_shortfall > 0.0


def test_screen_requires_poc_kv() -> None:
    grid = {k: v for k, v in _TIGHT_GRID.items() if k not in ("poc", "poc_voltage_kv")}
    with pytest.raises(ValueError, match="nominal_kv"):
        screen_reactive_capability(grid, use_pandapower=False)


def test_screen_requires_plant_rated_mva() -> None:
    grid = {
        **_TIGHT_GRID,
        "poc": {"bus_name": "X", "nominal_kv": 33.0},  # no plant_rated_mva
    }
    grid = {k: v for k, v in grid.items() if k != "plant_rating_mva"}
    with pytest.raises(ValueError, match="plant_rated_mva"):
        screen_reactive_capability(grid, use_pandapower=False)


def test_screen_reads_poc_kv_and_rating_from_flat_core() -> None:
    """poc-block absent → nominal_kv/rating read from the D1 flat core keys."""
    grid = {
        "gridcode": {"pf_range": [-0.95, 0.95]},
        "poc_voltage_kv": 33.0,
        "plant_rating_mva": 159.6,
        "resources": _TIGHT_GRID["resources"],
    }
    reactive, _pf = screen_reactive_capability(grid, use_pandapower=False)
    assert reactive.governing_p_mw == pytest.approx(159.6)


def test_screen_honours_p_steps_floor() -> None:
    """p_steps < 2 is floored to 2 (still solves; governing at rated)."""
    reactive, _pf = screen_reactive_capability(
        _TIGHT_GRID, use_pandapower=False, p_steps=1
    )
    assert reactive.governing_p_mw == pytest.approx(159.6)


# ------------------------------------------------- contract: non-converged governing


def test_from_screen_non_converged_is_binding_failure() -> None:
    """ReactiveCapabilityResult.from_screen with governing_converged=False (grid-free).

    Even with AMPLE headroom (headroom shortfall would be 0), a non-converged governing
    corner escalates the shortfall to the full demand and forces inside_pq_box False.
    """
    reactive = ReactiveCapabilityResult.from_screen(
        pf_required_min=-0.95,
        pf_required_max=0.95,
        mvar_required=52.5,
        mvar_available=80.0,  # ample → headroom shortfall = 0
        pf_at_poc=1.0,
        governing_p_mw=159.6,
        governing_grid_v_pu=1.0,
        governing_converged=False,
        method="pandapower_runpp",
    )
    assert reactive.inside_pq_box is False
    assert reactive.mvar_shortfall >= reactive.mvar_required > 0.0
    assert reactive.governing_converged is False


def test_from_screen_converged_ample_is_inside_box() -> None:
    reactive = ReactiveCapabilityResult.from_screen(
        pf_required_min=-0.95,
        pf_required_max=0.95,
        mvar_required=52.5,
        mvar_available=80.0,
        pf_at_poc=1.0,
        governing_converged=True,
    )
    assert reactive.inside_pq_box is True
    assert reactive.mvar_shortfall == pytest.approx(0.0)
