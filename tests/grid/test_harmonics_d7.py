"""Opt-in [grid]-gated feature tests for the D7 harmonics frequency-domain scan (#883).

Marked ``grid`` and gated behind ``pytest.importorskip('pandapower')`` so they are
DESELECTED in the default (grid-free) suite and run only with ``pip install -e '.[grid]'``.
They exercise the heavy path the grid-free tests cannot: the pandapower frequency-domain
bus-impedance scan (``_pandapower_zbus_pu_by_order`` → the ``method="pandapower_zbus"``
branch of ``screen_harmonics``), including the collector-cable capacitance that can lift
``|Zbus(h)|`` above the inductive ``h`` estimate at a resonance.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

pytest.importorskip("pandapower")

from analytics.contracts_v14 import HarmonicComplianceResult  # noqa: E402
from analytics.grid.harmonics import screen_harmonics  # noqa: E402

_GRID = {
    "poc": {"nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "source_rx": 0.1,
    "connection_r_ohm": 0.3,
    "connection_x_ohm": 3.5,
    "harmonic_spectrum": [[1, 100.0], [5, 2.4], [7, 1.5], [11, 0.9], [13, 0.7]],
    "flicker_coefficient": 3.4,
    "collector_equivalent": {
        "nominal_kv": 33.0,
        "r_ohm": 0.05,
        "x_ohm": 0.2,
        "c_nf": 250.0,
    },
    "gridcode": {"freq_ride_through": {"continuous_hz": [47.5, 51.5], "droop": 0.04}},
}


def test_pandapower_scan_runs_and_labels_method() -> None:
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=0.354, use_pandapower=True)
    assert isinstance(r, HarmonicComplianceResult)
    assert r.method == "pandapower_zbus"
    assert r.bankable is False
    # A spectrum was supplied → the harmonic domain was evaluated (not NOT-RUN).
    assert r.harmonic_within_limits is not None
    assert r.worst_harmonic_order is not None
    assert r.worst_harmonic_order >= 5  # fundamental excluded
    assert r.thd_voltage_pct is not None and r.thd_voltage_pct > 0.0


def test_pandapower_scan_scr_coupled() -> None:
    # The SCR coupling holds through the frequency-domain scan too: a weaker grid produces
    # a larger harmonic voltage + flicker.
    stiff = screen_harmonics(_GRID, scr=8.0, capacity_factor=0.3, use_pandapower=True)
    weak = screen_harmonics(_GRID, scr=2.0, capacity_factor=0.3, use_pandapower=True)
    assert weak.worst_harmonic_voltage_pct > stiff.worst_harmonic_voltage_pct
    assert weak.flicker_pst > stiff.flicker_pst
    assert weak.poc_ssc_mva < stiff.poc_ssc_mva


def test_pandapower_scan_frequency_headroom_present() -> None:
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=0.354, use_pandapower=True)
    assert r.freq_response_headroom_mw is not None and r.freq_response_headroom_mw > 0.0
    assert r.energy_foregone_mwh_yr is not None and r.energy_foregone_mwh_yr > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "grid"])
