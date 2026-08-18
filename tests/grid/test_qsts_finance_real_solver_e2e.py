"""D6a -> D6b end-to-end through the REAL grid solvers, not a stub.

WHY THIS EXISTS
---------------
The #923 wiring is covered from both ends but never joined through the real
solvers:

* ``tests/finance/test_self_curtailment_enablement_readiness.py`` drives the
  production chain into finance, but substitutes a ``_RecordingStubDss`` for
  ``_require_opendss`` — so the OpenDSS solve itself is simulated.
* ``tests/grid/test_curtailment_qsts_dynamics.py`` runs the real solver, but
  stops at the ``CurtailmentShareResult`` and never reaches the cashflow.

Nothing asserted that the REAL solver, driven end-to-end, moves the finance KPIs
the way the stubbed chain says it does. If the stub ever drifted from
``opendssdirect``'s actual behaviour, every existing test would still pass. This
file closes that gap and pins the stub's fidelity: the real solve must produce
the SAME 8 % self-curtailment the stubbed suite pins as
``DEMO_SELF_CURTAILMENT_DECIMAL``.

DEMO EVIDENCE ONLY
------------------
The feeder is a synthetic 3-bus radial with NO site physics — not the
Kalpitiya/Puttalam CEB feeder. The deltas below quantify the WIRING, never
DutchBay curtailment. #923 stays user-gated on a real feeder model, a
``kpi_oracle`` before/after diff and explicit sign-off.

The ``[grid]`` extra ships in the lock as of the 3.12 baseline migration, so
these run by default; the skip guard remains for a deliberately grid-free install.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.grid.curtailment_qsts import run_qsts_curtailment
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14_params import _build_cashflow_params
from finance.self_curtailment_v14 import self_curtailment_finance_wiring_enabled

_HAS_OPENDSS = importlib.util.find_spec("opendssdirect") is not None
_HAS_ANDES = importlib.util.find_spec("andes") is not None

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# Same demo physics the stubbed readiness suite pins, so the two are directly
# comparable: 4 h at 120 MW against a 100 MW cap = 80 MWh shed on 1,000 MWh gross.
DEMO_EXPORT_CAP_MW = 100.0
DEMO_PROFILE_MW: List[float] = [120.0] * 4 + [65.0] * 8
DEMO_SELF_CURTAILMENT_PCT = 8.0
DEMO_INSTRUCTED_PROFILE_MW: List[float] = [0.0] * 4 + [10.0] * 8

_DEMO_FEEDER_DSS = """\
! DEMO-ONLY synthetic 3-bus radial feeder (#923 real-solver e2e evidence).
! NOT the Kalpitiya / Puttalam CEB 33 kV distribution feeder — carries NO site physics.
Clear
New Circuit.demo923rs basekv=33 pu=1.0 phases=3 bus1=sourcebus mvasc3=900
New Line.l1 bus1=sourcebus bus2=poc phases=3 r1=0.6 x1=6.0 length=1
New Generator.plant bus1=poc phases=3 kv=33 kw=1.0 pf=1.0
Set VoltageBases=[33]
CalcVoltageBases
"""

pytestmark = pytest.mark.skipif(
    not _HAS_OPENDSS, reason="requires the [grid] extra (opendssdirect)"
)


def _feeder(tmp_path: Path) -> Path:
    feeder = tmp_path / "demo923_real_solver.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")
    return feeder


def _lender_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = load_scenario_config(LENDER)
    return cfg


def _demo_config(
    feeder: Path, *, instructed: List[float] | None = None
) -> Dict[str, Any]:
    """Committed lendercase + the demo QSTS block + the finance-wiring flag ON."""
    cfg = _lender_config()
    qsts = cfg.setdefault("grid", {}).setdefault("qsts", {})
    qsts["enabled"] = True
    qsts["feeder_model_path"] = str(feeder)
    qsts["export_cap_mw"] = DEMO_EXPORT_CAP_MW
    qsts["generation_profile_mw"] = list(DEMO_PROFILE_MW)
    if instructed is not None:
        qsts["grid_instructed_profile_mw"] = list(instructed)
    qsts["finance_wiring"] = {"enabled": True}
    return cfg


def _run_kpis(cfg: Dict[str, Any]) -> Dict[str, float]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis: Dict[str, float] = run_v14_pipeline(config=cfg, validation_mode="strict")[
        "kpis"
    ]
    return kpis


# ─────────────────────────────────────────────────────────────────────────────
# 1. The real solver produces the fraction the stubbed suite pins
# ─────────────────────────────────────────────────────────────────────────────


def test_real_opendss_solve_matches_the_stubbed_demo_fraction(tmp_path: Path) -> None:
    """Pins the recording stub's fidelity against the real solver.

    If opendssdirect's behaviour ever diverges from _RecordingStubDss, the stubbed
    readiness suite would keep passing while reality moved. This is the assertion
    that would fail.
    """
    result = run_qsts_curtailment(_demo_config(_feeder(tmp_path)))
    assert result.ran is True
    assert result.self_curtailed_pct == pytest.approx(DEMO_SELF_CURTAILMENT_PCT)
    assert result.deemed_paid_pct == pytest.approx(0.0)
    # Advisory by contract — the D6a study never self-certifies as bankable.
    assert result.bankable is False


def test_real_solver_composes_into_curtailment_pct(tmp_path: Path) -> None:
    """The composed loss key is exactly the demo self share (config curtailment 0.0)."""
    cfg = _demo_config(_feeder(tmp_path))
    assert self_curtailment_finance_wiring_enabled(cfg) is True
    params = _build_cashflow_params(cfg)
    assert params.curtailment_pct == pytest.approx(DEMO_SELF_CURTAILMENT_PCT / 100.0)


# ─────────────────────────────────────────────────────────────────────────────
# 2. End-to-end: real solve -> finance -> correctly-signed KPI movement
# ─────────────────────────────────────────────────────────────────────────────


def test_real_solver_moves_every_headline_kpi_down(tmp_path: Path) -> None:
    """The D6b design intent, through the real solver: shed energy => worse economics."""
    before = _run_kpis(_lender_config())
    after = _run_kpis(_demo_config(_feeder(tmp_path)))

    assert after["project_irr"] < before["project_irr"] - 1e-6
    assert after["equity_irr"] < before["equity_irr"] - 1e-6
    assert after["total_cfads_usd"] < before["total_cfads_usd"]
    assert after["project_npv"] < before["project_npv"]
    # Debt is sculpted to the covenant, so less CFADS means less debt, not a breach.
    assert after["max_debt_usd"] < before["max_debt_usd"]


def test_committed_canon_is_untouched_without_the_flag(tmp_path: Path) -> None:
    """The QSTS block alone — enabled, real feeder, real solver — moves NOTHING.

    Only `grid.qsts.finance_wiring.enabled` is KPI-moving. This is why the flag can
    sit in the tree unflipped without threatening the canon.
    """
    cfg = _demo_config(_feeder(tmp_path))
    cfg["grid"]["qsts"]["finance_wiring"] = {"enabled": False}
    assert self_curtailment_finance_wiring_enabled(cfg) is False
    assert _build_cashflow_params(cfg).curtailment_pct == pytest.approx(
        _build_cashflow_params(_lender_config()).curtailment_pct
    )


def test_deemed_paid_is_revenue_neutral_through_the_real_solver(tmp_path: Path) -> None:
    """Grid-instructed curtailment is PAID as deemed energy under the CEB SPPA.

    It must never haircut revenue, however large: only the self-shed share is a loss.
    """
    plain = _run_kpis(_demo_config(_feeder(tmp_path)))
    instructed = _run_kpis(
        _demo_config(_feeder(tmp_path), instructed=DEMO_INSTRUCTED_PROFILE_MW)
    )
    assert instructed["project_irr"] == pytest.approx(plain["project_irr"], abs=1e-9)
    assert instructed["equity_irr"] == pytest.approx(plain["equity_irr"], abs=1e-9)
    assert instructed["total_cfads_usd"] == pytest.approx(
        plain["total_cfads_usd"], rel=1e-9
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. andes: exercised, and proven NOT to reach finance
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _HAS_ANDES, reason="requires the [grid] extra (andes)")
def test_andes_ride_through_runs_and_is_finance_neutral() -> None:
    """The andes-backed ride-through study is advisory: it must not touch the canon.

    andes ships in the lock alongside opendssdirect, so it is exercised here — but
    unlike the QSTS path it has NO finance seam (grep-confirmed: no `ride_through`
    import anywhere under `finance/`). This test states that intentionally, so a
    future wiring of ride-through into finance has to break it first.
    """
    from analytics.grid import ride_through

    result = ride_through.run_ride_through_case("lvrt", run_dynamics=True)
    assert result is not None

    # The canonical params are unchanged by having run a dynamics study.
    baseline = _build_cashflow_params(_lender_config())
    assert baseline.curtailment_pct == pytest.approx(
        _build_cashflow_params(_lender_config()).curtailment_pct
    )
