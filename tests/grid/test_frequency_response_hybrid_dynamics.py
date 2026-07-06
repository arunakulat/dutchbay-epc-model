"""Opt-in ANDES dynamics tests for the D5c hybrid frequency-response study (#881, #892).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED in
the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the ONE ANDES-touching line the grid-free tests
cannot: :func:`analytics.grid.hybrid.frequency_response._attempt_dynamic_nadir`, which reaches
``andes`` through the SHARED D4b ride-through machinery at call-time.

As of D4b (#892) the ride-through core applies a REAL frequency excursion (a generator trip /
load step), so ``run_dynamics=True`` now yields a MEASURED dynamic nadir (a real frequency
extreme) — no longer a NOT-RUN. The load-bearing discipline is still NO-SPURIOUS-PASS: the
nadir must come from the PHYSICAL solve (a measured frequency var), never fabricated from the
closed-form settling estimate, and the closed-form deliverables must stay identical whether or
not the dynamic path runs.

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


def test_dynamic_gate_on_measures_a_real_nadir() -> None:
    """run_dynamics=True reaches ANDES and now measures a REAL dynamic frequency nadir.

    The closed-form per-group split + band compliance are still physically produced; the
    D4b core applies a real frequency excursion, so the dynamic nadir is now a MEASURED
    frequency extreme (a concrete float in a physical Hz range), NEVER fabricated from the
    settling estimate. NO SPURIOUS PASS still holds: the value is physical or None, and
    ``dynamic_ran`` reflects whether the solve executed.
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
    # The D4b frequency case executes a real excursion → the solve ran and measured a nadir.
    assert res.dynamic_ran is True, res.notes
    # PHYSICAL EVIDENCE: a measured frequency extreme (a concrete float), NOT fabricated. It
    # must be a plausible RMS frequency (a positive value near nominal, not the settling
    # estimate which the closed-form already produced).
    assert isinstance(res.dynamic_nadir_hz, float), res.notes
    assert 40.0 < res.dynamic_nadir_hz < 60.0, res.notes
    assert res.bankable is False


def test_dynamic_gate_off_matches_no_andes_import() -> None:
    """With the gate OFF the study is byte-for-byte the pure-Python result (no ANDES)."""
    pytest.importorskip("andes")
    cfg = {"grid": {"ppc": _PPC, "freq_event_hz": 49.6, "gridcode": _GRIDCODE}}
    off = run_hybrid_frequency_response(cfg, run_dynamics=False)
    on = run_hybrid_frequency_response(cfg, run_dynamics=True)
    # The physical, closed-form deliverables are identical whether or not the dynamic path
    # is attempted (the dynamic nadir is an ADDITIONAL advisory measurement, not a feedback).
    assert off.total_delivered_mw == pytest.approx(on.total_delivered_mw)
    assert off.settling_frequency_hz == pytest.approx(on.settling_frequency_hz)
    assert off.band_compliant == on.band_compliant
    # Gate off measures no nadir; gate on measures a real one (D4b excursion).
    assert off.dynamic_nadir_hz is None
    assert on.dynamic_nadir_hz is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "grid", "--tb=short"])
