"""Opt-in OpenDSS QSTS curtailment dynamics tests requiring the [grid] extra (D6a, #882).

Marked ``grid`` and gated behind ``pytest.importorskip("opendssdirect")`` so they are
DESELECTED in the default (grid-free) suite and run only in the opt-in CI lane / a dev
machine with ``pip install -e '.[grid]'``. They exercise the heavy path the grid-free tests
cannot: the OpenDSSDirect QSTS solve over a real feeder master, injecting the per-timestep
generation profile and establishing the plant's SELF-curtailment against the export cap.

The DISCIPLINE these tests protect (the whole point of the epic): SELF-curtailment comes
from the injected generation vs the export cap (the QSTS's real competency); DEEMED-PAID is
the committed operator schedule (``grid_instructed_profile_mw``), NOT inferred from a
monitor heuristic — the over-cap MWh must NOT be double-counted as both self and deemed. The
energy balance comes from PHYSICAL integrals (export-cap breaches + the committed
instruction schedule + SoC headroom), NEVER from solver convergence. A synthetic/demo feeder
must NOT overwrite the real loss placeholder — a fabricated curtailment number is exactly the
bug this dolphin refuses.

Run: ``pytest tests/ -m grid``  (or ``-m 'not grid'`` to skip).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.grid

from analytics.contracts_v14 import CurtailmentShareResult  # noqa: E402
from analytics.grid import curtailment_qsts as cq  # noqa: E402
from analytics.grid.curtailment_qsts import run_qsts_curtailment  # noqa: E402

# A tiny but REAL (loadable) OpenDSS feeder master: a source, a POC bus, a line, and a POC
# generator whose kW the QSTS driver overwrites per timestep. This is a self-contained
# feeder for the LIVE solve smoke test; the accounting split it produces is still derived
# from physical quantities, not from the solver exit flag.
_FEEDER_DSS = textwrap.dedent("""\
    Clear
    New Circuit.dutchbay basekv=33 pu=1.0 phases=3 bus1=source
    New Line.l1 bus1=source bus2=poc length=1 r1=0.1 x1=0.3 c1=0
    New Generator.plant bus1=poc phases=3 kv=33 kw=0 pf=1.0 model=1
    Set voltagebases=[33]
    CalcVoltageBases
    Solve
    """)


@pytest.fixture()
def real_feeder(tmp_path: Path) -> Path:
    feeder = tmp_path / "dutchbay_feeder.dss"
    feeder.write_text(_FEEDER_DSS)
    return feeder


def test_qsts_solve_over_real_feeder_produces_physical_split(real_feeder: Path) -> None:
    """The OpenDSS QSTS solve runs over a real feeder and yields a deemed-vs-self split.

    Injects a generation profile with a clear over-cap excursion and asserts the split is a
    real integral: gross > 0, a positive self-curtailment for the over-cap hour, and the
    energy-conservation identity (total == deemed + self_pre_bess) holds. ``ran`` is True
    because a REAL feeder solved — not because the solver merely converged.
    """
    pytest.importorskip("opendssdirect")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "feeder_model_path": str(real_feeder),
                "export_cap_mw": 15.0,
                # A committed per-timestep MW profile drives the injection; hour 3 exceeds
                # the 15 MW cap → a real self-curtailment.
                "generation_profile_mw": [10.0, 12.0, 20.0, 8.0],
            }
        }
    }
    res = run_qsts_curtailment(config)
    assert isinstance(res, CurtailmentShareResult)
    assert res.ran is True, res.reason
    assert res.feeder_source == str(real_feeder)
    assert res.bankable is False
    assert res.gross_energy_mwh is not None and res.gross_energy_mwh > 0.0
    # The over-cap hour (20 MWh over a 15 cap) is a real 5 MWh self-shed.
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(5.0)
    assert res.hours_self_curtailed == 1
    assert res.hours_total == 4
    # With NO committed grid-instruction schedule, deemed-paid is EXACTLY 0.0 — the QSTS
    # does NOT fabricate an operator instruction from a monitor heuristic (which would
    # double-count the above-cap MWh as both self and deemed). Assert the ACTUAL value.
    assert res.deemed_paid_energy_mwh == pytest.approx(0.0)
    assert res.deemed_paid_pct == pytest.approx(0.0)
    # Energy conservation — a real assertion, not a convergence echo.
    assert res.curtailed_total_mwh == pytest.approx(
        res.deemed_paid_energy_mwh + res.self_curtailed_pre_bess_mwh
    )


def test_qsts_solve_with_explicit_grid_instruction_no_overlap(
    real_feeder: Path,
) -> None:
    """A committed deemed schedule is honoured and does NOT overlap the self-shed.

    Hour 1 generates 10 MWh (below the 15 cap) and carries a 4 MWh operator INSTRUCTION →
    4 MWh deemed-paid. Hour 3 generates 20 MWh (over the cap) with NO instruction → 5 MWh
    self-shed. The deemed and self quantities come from DIFFERENT hours and DIFFERENT
    mechanisms, so they must NOT double-count: deemed == 4.0, self == 5.0, total == 9.0.
    """
    pytest.importorskip("opendssdirect")
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "feeder_model_path": str(real_feeder),
                "export_cap_mw": 15.0,
                "generation_profile_mw": [10.0, 12.0, 20.0, 8.0],
                # The committed utility feeder-limit / dispatch schedule (deemed-paid).
                "grid_instructed_profile_mw": [4.0, 0.0, 0.0, 0.0],
            }
        }
    }
    res = run_qsts_curtailment(config)
    assert res.ran is True, res.reason
    assert res.deemed_paid_energy_mwh == pytest.approx(4.0)
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(5.0)
    # No double-count: the two mechanisms sum without overlapping the above-cap MWh.
    assert res.curtailed_total_mwh == pytest.approx(9.0)


def test_qsts_solve_with_bess_recovers_surplus(real_feeder: Path) -> None:
    """The live QSTS + co-located BESS recovers surplus bounded by the D5a headroom."""
    pytest.importorskip("opendssdirect")
    bess = {
        "type": "bess",
        "energy_mwh": 40.0,
        "soh_curve": {1: 1.0, 15: 0.765},
        "min_soc": 0.10,
        "max_soc": 0.95,
        "soc_fraction": 0.90,
    }
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "feeder_model_path": str(real_feeder),
                "export_cap_mw": 15.0,
                "generation_profile_mw": [20.0, 20.0],
                "bess": bess,
            }
        }
    }
    res = run_qsts_curtailment(config)
    assert res.ran is True, res.reason
    assert res.self_curtailed_pre_bess_mwh == pytest.approx(10.0)
    # chargeable at SoC 0.90 = (0.95-0.90)*40*0.765 = 1.53 MWh.
    assert res.bess_absorbed_energy_mwh == pytest.approx(1.53)
    assert res.self_curtailed_energy_mwh == pytest.approx(10.0 - 1.53)
    assert (
        res.self_curtailed_energy_mwh + res.bess_absorbed_energy_mwh
        == pytest.approx(res.self_curtailed_pre_bess_mwh)
    )


def test_require_opendss_imports_when_extra_present() -> None:
    """With the [grid] extra installed, the guard returns the module (no error)."""
    pytest.importorskip("opendssdirect")
    mod = cq._require_opendss()
    assert mod is not None
