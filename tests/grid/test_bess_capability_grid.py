"""Opt-in [grid]-gated feature tests for the D4d BESS capability plug-in (#878).

Marked ``grid`` and gated behind ``pytest.importorskip('pandapower')`` so they are
DESELECTED in the default (grid-free) suite and run only with ``pip install -e '.[grid]'``.
They exercise the heavy path the grid-free tests cannot: the BESS SCR screen running through
pandapower's IEC 60909 short-circuit solver (``method="pandapower_iec60909"``) with the
MANUAL PCS short-circuit contribution folded into the POC fault level, and confirm the
SoH-degraded reactive verdict still assembles alongside it.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import (  # noqa: E402
    GridStrengthResult,
    ReactiveCapabilityResult,
)
from analytics.grid.capabilities.bess import screen_bess_capability  # noqa: E402

_BESS_GRID = {
    "type": "bess",
    "poc_voltage_kv": 33.0,
    "source_fault_level_mva": 800.0,
    "source_rx": 0.083,
    "connection_r_ohm": 0.05,
    "connection_x_ohm": 1.2,
    "rated_mva": 10.64,
    "q_rated_mvar": 3.0,
    "sc_contribution_pu": 1.1,
    "pf_range": [-0.95, 0.95],
    "soh_curve": {1: 1.0, 15: 0.765},
}


def test_bess_scr_screen_runs_iec60909() -> None:
    """With pandapower present the SCR screen uses IEC 60909, not the closed form."""
    pytest.importorskip("pandapower")
    strength, reactive = screen_bess_capability(_BESS_GRID, use_pandapower=True)
    assert isinstance(strength, GridStrengthResult)
    assert isinstance(reactive, ReactiveCapabilityResult)
    assert strength.method == "pandapower_iec60909"
    assert strength.bankable is False
    # A finite, positive fault level + SCR at the POC.
    assert strength.fault_level_poc_mva > 0.0
    assert strength.scr > 0.0
    # The MAX-case fault level is reported for context under pandapower (None in closed form).
    assert strength.fault_level_poc_max_mva is not None


def test_bess_pcs_contribution_raises_iec60909_fault_level() -> None:
    """The manual PCS SC contribution raises the IEC 60909 POC fault level vs a zero BESS."""
    pytest.importorskip("pandapower")
    strength, _ = screen_bess_capability(_BESS_GRID, use_pandapower=True)
    strength_zero, _ = screen_bess_capability(
        {**_BESS_GRID, "sc_contribution_pu": 0.0}, use_pandapower=True
    )
    assert strength.fault_level_poc_mva > strength_zero.fault_level_poc_mva
    assert strength.scr > strength_zero.scr


def test_bess_reactive_degraded_alongside_iec60909() -> None:
    """The SoH-degraded reactive verdict assembles alongside the pandapower SCR screen."""
    pytest.importorskip("pandapower")
    _strength, reactive = screen_bess_capability(_BESS_GRID, use_pandapower=True)
    # Reactive available is the year-15 degraded headroom (3.0 * 0.765), regardless of the
    # SCR solver backend (the reactive screen is closed-form capability math).
    assert reactive.mvar_available == pytest.approx(3.0 * 0.765)
    assert reactive.method == "closed_form"
