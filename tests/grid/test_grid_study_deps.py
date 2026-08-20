"""Opt-in grid-study tests requiring the [grid] extra (D1, #872).

Marked ``grid`` and gated behind ``pytest.importorskip`` so they are DESELECTED in the
default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the two heavy paths the grid-free scaffold
tests cannot:

  * pandapower IEC 60909 SCR@POC (min + max), banded into the GFL/GFM screen;
  * one ANDES RMS LVRT case parameterised from the D0 grid-code fixture.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.grid import ride_through_poc, short_circuit  # noqa: E402


def test_pandapower_iec60909_scr_computes_and_bands() -> None:
    pytest.importorskip("pandapower")
    res = short_circuit.screen_grid_strength(
        poc_voltage_kv=33.0,
        source_fault_level_mva=250.0,
        source_rx=0.1,
        connection_r_ohm=0.5,
        connection_x_ohm=4.0,
        plant_rating_mva=11.0,
        use_pandapower=True,
    )
    assert res.method == "pandapower_iec60909"
    assert res.fault_level_case == "iec60909_min"
    assert res.fault_level_poc_mva > 0.0
    # The MAX case is reported for context and is >= the MIN case fault level.
    assert res.fault_level_poc_max_mva is not None
    assert res.fault_level_poc_max_mva >= res.fault_level_poc_mva
    assert res.scr > 0.0
    assert res.scr_band in {"weak", "marginal", "strong"}
    assert res.bankable is False  # in-house screen is never bankable


def test_pandapower_scr_denominator_scales_with_plant() -> None:
    pytest.importorskip("pandapower")
    common = dict(
        poc_voltage_kv=33.0,
        source_fault_level_mva=250.0,
        source_rx=0.1,
        connection_r_ohm=0.5,
        connection_x_ohm=4.0,
        use_pandapower=True,
    )
    light = short_circuit.screen_grid_strength(plant_rating_mva=11.0, **common)
    heavy = short_circuit.screen_grid_strength(plant_rating_mva=150.0, **common)
    # Same grid, larger plant => lower SCR.
    assert heavy.scr < light.scr


def test_andes_lvrt_case_runs() -> None:
    pytest.importorskip("andes")
    res = ride_through_poc.run_lvrt_case()
    assert res.ran is True, res.detail
    assert res.lvrt_enter_pu == pytest.approx(0.89)  # seeded from the D0 fixture
    assert res.n_devices > 0


def test_issue_1107_controlled_failure_probe() -> None:
    """Temporary PR probe: prove an independent Grid Study failure blocks merge."""

    pytest.importorskip("opendssdirect")
    pytest.fail("controlled #1107 Grid Study failure probe")
