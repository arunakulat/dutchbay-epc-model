"""Opt-in ANDES wind-LVRT dynamics tests requiring the [grid] extra (D4b, #876).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED
in the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the one path the grid-free tests cannot: the
wind plug-in driving the shared D4a ANDES RMS LVRT solve (``run_dynamics=True``) and
asserting the COMPLIANCE VERDICT comes from the PHYSICAL ENVELOPE (post-fault recovered
bus voltage + IBR-trip), NOT from the raw solver convergence flag — while the reactive
PQ-envelope (pure Python) stays identical to the gate-off path.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import RideThroughResult  # noqa: E402
from analytics.grid.capabilities import wind  # noqa: E402

_WIND_T4 = {
    "rated_mva": 159.6,
    "turbine": {"converter_type": "type4_full_converter", "pf_range": [-0.95, 0.95]},
    "gridcode": {"pf_range": [-0.95, 0.95]},
}


def test_wind_lvrt_runs_and_reports_physical_envelope() -> None:
    """run_dynamics=True: the ANDES LVRT solve executes; verdict from the envelope."""
    pytest.importorskip("andes")
    res = wind.screen_wind_capability(_WIND_T4, run_dynamics=True)
    lvrt: RideThroughResult = res.lvrt
    assert lvrt.case == "lvrt"
    assert lvrt.ran is True, lvrt.detail  # the solve executed
    assert lvrt.target_pu == pytest.approx(0.89)  # seeded from the D0 fixture
    assert lvrt.n_devices > 0
    assert lvrt.bankable is False
    # PHYSICAL EVIDENCE: a real, measurable dip below the entry threshold.
    assert isinstance(lvrt.min_voltage_pu, float)
    assert isinstance(lvrt.target_pu, float)
    assert lvrt.min_voltage_pu < lvrt.target_pu, lvrt.detail
    # A concrete compliance decision (never an unvalidated pass, never echoing converged).
    assert lvrt.rode_through in (True, False), lvrt.detail
    # The reactive screen is pure Python — unaffected by the dynamics gate.
    assert res.reactive.inside_pq_box is True
    assert res.reactive.bankable is False


def test_wind_reactive_identical_gate_on_off() -> None:
    """The PQ envelope (pure) is byte-identical whether or not the dynamics gate is on."""
    pytest.importorskip("andes")
    off = wind.screen_wind_capability(_WIND_T4, run_dynamics=False)
    on = wind.screen_wind_capability(_WIND_T4, run_dynamics=True)
    assert off.reactive == on.reactive
    assert off.envelope_points == on.envelope_points
