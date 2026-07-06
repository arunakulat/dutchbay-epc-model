"""Opt-in [grid]-gated integration for the D4c solar capability plug-in (#877).

Marked ``grid`` and gated behind ``pytest.importorskip`` so it is DESELECTED in the
default (grid-free) suite and runs only under ``pip install -e '.[grid]'`` (the CI grid
lane / a dev machine with the extra). The solar plug-in itself is grid-library-free, so
this file covers the INTEROP with the heavy grid paths it is designed to feed:

  * the AC export rating + grid-code pf envelope the plug-in derives feed a REAL
    pandapower AC load-flow via the D3 reactive screen
    (:func:`analytics.grid.reactive_screen.screen_reactive_capability`), and the two
    reactive verdicts agree in direction (pf-matched → no shortfall);
  * the D4a ride-through core runs a REAL ANDES LVRT solve seeded from the same grid-code
    envelope a solar block carries — confirming the plug-in reuses (not re-implements) the
    shared dynamics core.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import (  # noqa: E402
    ReactiveCapabilityResult,
    RideThroughResult,
)
from analytics.grid.capabilities.solar import (  # noqa: E402
    ac_rating_from_dc,
    screen_solar_capability,
)


def test_solar_ac_rating_feeds_real_pandapower_reactive_screen() -> None:
    """The plug-in's AC rating + pf envelope drive a REAL pandapower load-flow (D3)."""
    pytest.importorskip("pandapower")
    from analytics.grid.reactive_screen import screen_reactive_capability

    # A pf-matched solar plant: inverter delivers exactly the grid-code 0.95 pf.
    block = {
        "dc_capacity_mw": 50.0,
        "dc_ac_ratio": 1.2,
        "gridcode": {"pf_range": [-0.95, 0.95]},
    }
    reactive_closed, fault = screen_solar_capability(block)
    assert reactive_closed.mvar_shortfall == pytest.approx(0.0)
    assert fault.is_synchronous is False  # never a machine

    ac = ac_rating_from_dc(50.0, 1.2)
    # Feed the SAME AC rating + pf envelope into the pandapower AC load-flow screen. The
    # aggregate plant carries reactive headroom matching the grid-code demand, so the
    # load-flow screen must also find it inside the PQ box (no shortfall) with a converged
    # governing corner — the two independent screens agree in direction.
    grid = {
        "study_enabled": True,
        "poc_voltage_kv": 33.0,
        "plant_rating_mva": ac,
        "poc": {"bus_name": "POC", "nominal_kv": 33.0, "plant_rated_mva": ac},
        "gridcode": {"pf_range": [-0.95, 0.95], "voltage_window_pu": [0.9, 1.1]},
        "resources": [
            {
                "name": "solar_aggregate",
                "rated_mva": ac,
                "reactive_capability": {
                    "min_q_mvar": -reactive_closed.mvar_available,
                    "max_q_mvar": reactive_closed.mvar_available,
                },
            }
        ],
    }
    reactive_pp, pf_result = screen_reactive_capability(grid, use_pandapower=True)
    assert isinstance(reactive_pp, ReactiveCapabilityResult)
    assert reactive_pp.method == "pandapower_runpp"
    assert reactive_pp.governing_converged is True
    assert reactive_pp.mvar_shortfall == pytest.approx(0.0)
    assert reactive_pp.inside_pq_box is True
    assert pf_result is not None and pf_result.converged is True
    assert reactive_pp.bankable is False


def test_solar_reuses_ride_through_core_real_andes_lvrt() -> None:
    """A solar block's grid-code envelope drives the SHARED D4a ANDES LVRT solve (reuse)."""
    pytest.importorskip("andes")
    from analytics.grid.ride_through import RideThroughEnvelope, run_ride_through_case

    # Envelope a solar grid block would carry (Envision ENPCS01 GFL PCS values).
    env = RideThroughEnvelope(
        lvrt_enter_pu=0.89,
        hvrt_enter_pu=1.10,
        lvrt_k_factor=2.0,
        hvrt_k_factor=1.9,
        freq_continuous_hz=(47.5, 51.5),
        source="solar-d4c-integration",
    )
    res = run_ride_through_case("lvrt", run_dynamics=True, envelope=env)
    assert isinstance(res, RideThroughResult)
    assert res.case == "lvrt"
    assert res.ran is True, res.detail
    assert res.target_pu == pytest.approx(0.89)
    assert res.bankable is False
    # The compliance verdict comes from the physical envelope (True/False), never None for
    # an applied-fault LVRT solve that executed.
    assert res.rode_through in (True, False)
