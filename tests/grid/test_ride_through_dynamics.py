"""Opt-in ANDES ride-through dynamics tests requiring the [grid] extra (D4a, #875).

Marked ``grid`` and gated behind ``pytest.importorskip("andes")`` so they are DESELECTED
in the default (grid-free) suite and run only in the opt-in CI lane / a dev machine with
``pip install -e '.[grid]'``. They exercise the heavy path the grid-free tests cannot:
one ANDES RMS ride-through solve per case kind (LVRT dip, HVRT swell, frequency
excursion), each parameterised from the D0 grid-code envelope and run behind the
``run_dynamics=True`` dynamic-study gate.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import RideThroughResult  # noqa: E402
from analytics.grid import ride_through, ride_through_poc  # noqa: E402


def test_lvrt_case_runs_dynamics() -> None:
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    assert isinstance(res, RideThroughResult)
    assert res.case == "lvrt"
    assert res.ran is True, res.detail
    assert res.converged is True
    assert res.target_pu == pytest.approx(0.89)  # seeded from the D0 fixture
    assert res.k_factor == pytest.approx(2.0)
    assert res.n_devices > 0
    assert res.bankable is False


def test_hvrt_case_runs_dynamics() -> None:
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("hvrt", run_dynamics=True)
    assert res.case == "hvrt"
    assert res.ran is True, res.detail
    assert res.target_pu == pytest.approx(1.10)  # HVRT entry from the D0 fixture
    assert res.n_devices > 0


def test_frequency_case_runs_dynamics() -> None:
    pytest.importorskip("andes")
    res = ride_through.run_ride_through_case("frequency", run_dynamics=True)
    assert res.case == "frequency"
    assert res.ran is True, res.detail
    assert res.target_hz == pytest.approx(51.5)  # continuous over-freq edge
    assert res.n_devices > 0


def test_suite_runs_all_three_dynamics() -> None:
    pytest.importorskip("andes")
    suite = ride_through.run_ride_through_suite(run_dynamics=True)
    assert set(suite) == {"lvrt", "hvrt", "frequency"}
    assert all(r.ran is True for r in suite.values()), {
        k: r.detail for k, r in suite.items()
    }


def test_poc_shim_run_lvrt_case_still_runs() -> None:
    """The backward-compat SHIM still runs the LVRT dynamics via the shared core."""
    pytest.importorskip("andes")
    res = ride_through_poc.run_lvrt_case()
    assert res.ran is True, res.detail
    assert res.lvrt_enter_pu == pytest.approx(0.89)
    assert res.n_devices > 0
