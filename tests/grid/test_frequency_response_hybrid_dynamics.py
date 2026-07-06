"""Opt-in ANDES dynamics tests for the D5c hybrid frequency-response study (#881).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED in
the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the ONE ANDES-touching line the grid-free tests
cannot: :func:`analytics.grid.hybrid.frequency_response._attempt_dynamic_nadir`, which reaches
``andes`` through the SHARED D4a ride-through machinery at call-time.

The load-bearing assertion is the NO-SPURIOUS-PASS discipline: the D4a core does NOT model a
frequency excursion yet (a shunt fault cannot apply one), so even with ``run_dynamics=True``
the dynamic frequency nadir MUST be reported NOT-RUN (``dynamic_nadir_hz=None``) — never a
fabricated value derived from the closed-form settling estimate. A dynamic nadir here would be
exactly the bug this epic guards against.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import FreqResponseResult  # noqa: E402
from analytics.grid.hybrid.frequency_response import (  # noqa: E402
    run_hybrid_frequency_response,
)

_GRIDCODE = {"freq_ride_through": {"continuous_hz": [47.5, 51.5]}}
_PPC = {
    "groups": [
        {
            "name": "wg1",
            "tech": "wind",
            "rated_mw": 100.0,
            "freq_droop_pct": 4.0,
            "output_mw": 0.0,
        },
    ],
    "p_priority_order": ["wg1"],
}


def test_dynamic_gate_on_does_not_fabricate_a_nadir() -> None:
    """run_dynamics=True reaches ANDES but the frequency nadir stays NOT-RUN (None).

    The closed-form per-group split + band compliance are still physically produced; the
    dynamic nadir is NOT modelled by the D4a core, so it MUST be None (never fabricated from
    the settling estimate). This is the spurious-pass guard for the dynamic path.
    """
    pytest.importorskip("andes")
    cfg = {"grid": {"ppc": _PPC, "freq_event_hz": 49.6, "gridcode": _GRIDCODE}}
    res = run_hybrid_frequency_response(cfg, run_dynamics=True)
    assert isinstance(res, FreqResponseResult)
    # The closed-form deliverables are real regardless of the dynamic path.
    # Single 100 MW group at 4 % droop on a −0.4 Hz event commands
    # (0.4/50)/0.04 · 100 = 20 MW, delivered in full (100 MW spinning headroom).
    assert res.total_commanded_mw == pytest.approx(20.0)
    assert res.total_delivered_mw == pytest.approx(20.0)
    assert res.band_compliant is True
    # NO SPURIOUS PASS: the un-modelled dynamic nadir is an explicit NOT-RUN.
    assert res.dynamic_nadir_hz is None
    # The D4a frequency case is itself NOT-RUN, so the solve did not execute a real
    # frequency excursion → dynamic_ran is False.
    assert res.dynamic_ran is False
    assert res.bankable is False


def test_dynamic_gate_off_matches_no_andes_import() -> None:
    """With the gate OFF the study is byte-for-byte the pure-Python result (no ANDES)."""
    pytest.importorskip("andes")
    cfg = {"grid": {"ppc": _PPC, "freq_event_hz": 49.6, "gridcode": _GRIDCODE}}
    off = run_hybrid_frequency_response(cfg, run_dynamics=False)
    on = run_hybrid_frequency_response(cfg, run_dynamics=True)
    # The physical, closed-form deliverables are identical whether or not the (NOT-RUN)
    # dynamic path is attempted.
    assert off.total_delivered_mw == pytest.approx(on.total_delivered_mw)
    assert off.settling_frequency_hz == pytest.approx(on.settling_frequency_hz)
    assert off.band_compliant == on.band_compliant
    assert off.dynamic_nadir_hz is None and on.dynamic_nadir_hz is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "grid", "--tb=short"])
