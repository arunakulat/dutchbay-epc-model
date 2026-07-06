"""Opt-in [grid]-gated feature tests for the D3 reactive/voltage screen + gateway (#874).

Marked ``grid`` and gated behind ``pytest.importorskip('pandapower')`` so they are
DESELECTED in the default (grid-free) suite and run only with ``pip install -e '.[grid]'``.
They exercise the heavy path the grid-free gateway tests cannot:

  * the steady-state reactive/voltage screen (pandapower ``runpp`` over the P × grid-V
    sweep) sizing a NON-ZERO Mvar shortfall against the grid-code PQ box; and
  * the CCCDIR gateway ``evaluate_grid`` composing the D1 SCR + D3 reactive screens into
    one advisory :class:`analytics.contracts_v14.GridStudyResult`.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import (  # noqa: E402
    GridStudyResult,
    PowerFlowResult,
    ReactiveCapabilityResult,
)
from analytics.grid.evaluate_grid import evaluate_grid  # noqa: E402
from analytics.grid.reactive_screen import (  # noqa: E402
    pf_to_qp_ratio,
    screen_reactive_capability,
)

# A DutchBay-shaped grid block: 159.6 MVA plant at a 33 kV POC, grid-code ±0.95 pf, with a
# deliberately reactive-tight aggregate (reactive_capability below the code demand at
# rated) so the screen reports a NON-ZERO Mvar shortfall — the STATCOM/MSC sizing figure.
_DUTCHBAY_GRID = {
    "study_enabled": True,
    # D1 flat core (SCR screen inputs)
    "poc_voltage_kv": 33.0,
    "source_fault_level_mva": 800.0,
    "source_rx": 0.083,
    "connection_r_ohm": 0.3,
    "connection_x_ohm": 3.5,
    "plant_rating_mva": 159.6,
    # D2 structured block (reactive screen inputs)
    "poc": {"bus_name": "Puttalam 220kV", "nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "thevenin": {
        "short_circuit_mva_min": 800.0,
        "short_circuit_mva_max": 1200.0,
        "x_r": 12.0,
        "assumption_basis": "utility_provided",
    },
    "gridcode": {"pf_range": [-0.95, 0.95], "voltage_window_pu": [0.9, 1.1]},
    "poc_transformer": {"r_ohm": 0.05, "x_ohm": 1.2},
    "collector_equivalent": {"nominal_kv": 33.0, "r_ohm": 0.05, "x_ohm": 0.2},
    # Aggregate resource whose reactive headroom (40 Mvar) is BELOW the code demand at
    # rated (~52.5 Mvar for 0.95 pf at 159.6 MW) → a guaranteed, sizeable shortfall.
    "resources": [
        {
            "name": "wind_aggregate",
            "rated_mva": 159.6,
            "reactive_capability": {"min_q_mvar": -40.0, "max_q_mvar": 40.0},
        }
    ],
}


def test_pf_to_qp_ratio_matches_tan_acos() -> None:
    # 0.95 pf → tan(acos(0.95)) ≈ 0.3287 Mvar per MW (grid-free helper, always available).
    assert pf_to_qp_ratio(0.95) == pytest.approx(0.328684, abs=1e-5)


def test_reactive_screen_sizes_mvar_shortfall() -> None:
    pytest.importorskip("pandapower")
    reactive, power_flow = screen_reactive_capability(
        _DUTCHBAY_GRID, use_pandapower=True
    )
    assert isinstance(reactive, ReactiveCapabilityResult)
    assert reactive.method == "pandapower_runpp"
    assert reactive.bankable is False
    # 40 Mvar available vs ~52.5 Mvar required at rated → ~12.5 Mvar short.
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
    # The governing power-flow snapshot is present and converged.
    assert isinstance(power_flow, PowerFlowResult)
    assert power_flow.converged is True
    assert "POC" in power_flow.bus_voltages_pu


def test_reactive_screen_meets_pq_box_when_capability_ample() -> None:
    pytest.importorskip("pandapower")
    ample = {
        **_DUTCHBAY_GRID,
        "resources": [
            {
                "name": "wind_aggregate",
                "rated_mva": 159.6,
                "reactive_capability": {"min_q_mvar": -80.0, "max_q_mvar": 80.0},
            }
        ],
    }
    reactive, _pf = screen_reactive_capability(ample, use_pandapower=True)
    # 80 Mvar available comfortably exceeds the ~52.5 Mvar code demand → no shortfall.
    assert reactive.mvar_shortfall == pytest.approx(0.0)
    assert reactive.inside_pq_box is True


def test_evaluate_grid_gateway_returns_bundled_study() -> None:
    pytest.importorskip("pandapower")
    study = evaluate_grid({"grid": _DUTCHBAY_GRID}, use_pandapower=True)
    assert isinstance(study, GridStudyResult)
    assert study.study_enabled is True
    assert study.bankable is False
    assert study.poc_bus_name == "Puttalam 220kV"
    # D1 SCR screen composed in.
    assert study.strength.method == "pandapower_iec60909"
    assert study.strength.scr > 0.0
    assert study.strength.bankable is False
    # D3 reactive screen composed in with a sized shortfall.
    assert study.reactive is not None
    assert study.reactive.mvar_shortfall > 0.0
    assert study.reactive.inside_pq_box is False
    assert study.power_flow is not None
    assert study.power_flow.converged is True
    # The whole bundle round-trips (advisory, serialisable).
    dumped = study.model_dump()
    assert dumped["reactive"]["mvar_shortfall"] > 0.0
    assert dumped["strength"]["bankable"] is False


def test_reactive_screen_non_converged_corner_is_binding_failure(monkeypatch) -> None:
    """A non-converged governing corner must NOT pass as PQ-box-compliant, even when the
    plant has ample reactive headroom (regression for the escalation being discarded).
    """
    pytest.importorskip("pandapower")
    import analytics.grid.reactive_screen as rs

    # Force EVERY runpp corner to report non-convergence. Use AMPLE capability so a
    # headroom-only shortfall would be 0 — the failure must come from non-convergence.
    monkeypatch.setattr(
        rs,
        "_poc_pf_and_voltage",
        lambda pp, net, poc_bus: (False, float("nan"), 0.0, 0.0),
    )
    ample = {
        **_DUTCHBAY_GRID,
        "resources": [
            {
                "name": "wind_aggregate",
                "rated_mva": 159.6,
                "reactive_capability": {"min_q_mvar": -80.0, "max_q_mvar": 80.0},
            }
        ],
    }
    reactive, power_flow = rs.screen_reactive_capability(ample, use_pandapower=True)
    # 80 Mvar headroom ≥ ~52.5 Mvar demand → headroom shortfall would be 0, but the
    # governing corner did NOT converge → binding failure: not inside the PQ box, and
    # the shortfall is escalated to at least the full reactive demand.
    assert reactive.governing_converged is False
    assert reactive.inside_pq_box is False
    assert reactive.mvar_shortfall >= reactive.mvar_required > 0.0
    assert power_flow is not None
    assert power_flow.converged is False
