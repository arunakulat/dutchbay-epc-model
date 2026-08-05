"""#923 — D6b enablement-READINESS evidence (the flag stays PARKED; nothing here moves canon).

Issue #923 gates turning ``grid.qsts.finance_wiring.enabled`` ON for a committed scenario.
Its trigger — a REAL CEB feeder model at the DutchBay POC — has NOT fired, so this suite
pins the two halves of enablement readiness WITHOUT enabling anything:

  1. **The refusal gate, through the REAL chain (no ``run_qsts_curtailment`` monkeypatch).**
     The #915 suite (``test_self_curtailment_finance.py``) covers the resolver units and
     monkeypatches the QSTS seam on every enabled path. Here the enabled flag is exercised
     against the PRODUCTION chain end-to-end: flag on but no real feeder → the QSTS returns
     an inert NOT-RUN result and the cashflow/KPIs stay byte-identical canon (flipping the
     flag TODAY is vacuous — the honest reason #923 stays open). A synthetic/demo feeder is
     likewise refused, and a real-looking feeder file WITHOUT the ``[grid]`` extra raises the
     actionable CASPER ImportError instead of silently returning canon.

  2. **DEMO-GRADE oracle evidence** that the wiring MOVES KPIs exactly as designed once a
     real feeder exists. ``DEMO`` means: the tmp feeder is a synthetic 3-bus radial written
     by the test — it satisfies the file-exists gate but is **NOT the Kalpitiya/CEB feeder
     and carries NO site physics**; and the OpenDSS solver binary is replaced by a recording
     stub because the base venv has no ``[grid]`` extra. Everything else — the file-exists
     gate, the explicit ``grid.qsts.generation_profile_mw`` resolution, the strict
     validation, :func:`split_curtailment`'s energy accounting, the resolver, the
     multiplicative compose, and the full finance pipeline — is the REAL production chain.
     The demo pair (canon unmoved + demo moved, in the same suite) IS the readiness proof.

None of these numbers is presentable as site physics. The real enablement sequence stays
user-gated: real feeder → QSTS run → kpi_oracle before/after diff → user sign-off → flag +
canon re-pin in the SAME PR (see docs/knowledge_base/grid_screening_scope.md §7).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14_params import _build_cashflow_params
from tests._canon import LENDER_EQUITY_IRR as CANON_EQ_IRR
from tests._canon import LENDER_MIN_DSCR as CANON_MIN_DSCR
from tests._canon import LENDER_PROJECT_IRR as CANON_PROJ_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Committed 5th-gen canon (single source of truth: tests/_canon.py, #955).

_HAS_GRID_EXTRA = importlib.util.find_spec("opendssdirect") is not None

# ── The DEMO generation design (labelled, NOT site physics) ─────────────────────────────
# 12 hourly steps against a 100 MW POC export cap: four hours at 120 MW (20 MW over-cap
# shed each) + eight hours at 65 MW (below cap). Gross 1000 MWh, self-shed 80 MWh, no BESS
# → self_curtailed_pct is EXACTLY 8.0% — chosen to mirror the #923 reference fraction.
DEMO_EXPORT_CAP_MW = 100.0
DEMO_PROFILE_MW: List[float] = [120.0] * 4 + [65.0] * 8
DEMO_SELF_CURTAILMENT_DECIMAL = 0.08

# A deemed-paid (grid-instructed) schedule for the neutrality leg: 10 MW instructed during
# each below-cap hour → 80 MWh deemed-paid (8% of gross), which must move NOTHING.
DEMO_INSTRUCTED_PROFILE_MW: List[float] = [0.0] * 4 + [10.0] * 8

_DEMO_FEEDER_DSS = """\
! DEMO-ONLY synthetic 3-bus radial feeder (#923 enablement-readiness evidence).
! NOT the Kalpitiya / Puttalam CEB 33 kV distribution feeder — carries NO site physics.
! Exists solely so grid.qsts.feeder_model_path resolves to a real file in the demo test.
Clear
New Circuit.demo923 basekv=33 pu=1.0 phases=3 bus1=sourcebus mvasc3=900
New Line.l1 bus1=sourcebus bus2=poc phases=3 r1=0.6 x1=6.0 length=1
New Generator.plant bus1=poc phases=3 kv=33 kw=1.0 pf=1.0
Set VoltageBases=[33]
CalcVoltageBases
"""


def _lender_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = load_scenario_config(LENDER)
    return cfg


def _qsts_block(cfg: Dict[str, Any]) -> Dict[str, Any]:
    grid = cfg.setdefault("grid", {})
    qsts = grid.setdefault("qsts", {})
    assert isinstance(qsts, dict)
    return qsts


def _run_kpis(cfg: Dict[str, Any]) -> Dict[str, float]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis: Dict[str, float] = run_v14_pipeline(config=cfg, validation_mode="strict")[
        "kpis"
    ]
    return kpis


def _assert_canon(kpis: Dict[str, float]) -> None:
    assert kpis["project_irr"] == pytest.approx(CANON_PROJ_IRR, abs=1e-9)
    assert kpis["equity_irr"] == pytest.approx(CANON_EQ_IRR, abs=1e-9)
    assert kpis["min_dscr"] == pytest.approx(CANON_MIN_DSCR, abs=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# 1. The refusal gate through the REAL chain — flag on, no real feeder ⇒ canon
#    (no run_qsts_curtailment monkeypatch anywhere in this section)
# ─────────────────────────────────────────────────────────────────────────────


def test_flag_alone_without_qsts_study_is_vacuous() -> None:
    """finance_wiring.enabled=true but grid.qsts.enabled absent ⇒ inert ⇒ canon params.

    This is the closest single knob to "just flip #923's flag today": the QSTS default-off
    gate refuses before any feeder is even looked for, and curtailment_pct is untouched.
    """
    cfg = _lender_config()
    _qsts_block(cfg)["finance_wiring"] = {"enabled": True}
    assert _build_cashflow_params(cfg).curtailment_pct == 0.0


def test_flag_with_missing_feeder_file_full_pipeline_stays_canon() -> None:
    """The exact present-day #923 state, end-to-end: flag + qsts enabled, but the feeder
    path does not exist on disk ⇒ the QSTS emits an inert NOT-RUN result (never a
    fabricated zero-loss pass), the resolver refuses, and the FULL pipeline reproduces the
    pinned canon bit-for-bit. Flipping the flag without the real feeder is vacuous.
    """
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["feeder_model_path"] = "/nonexistent/ceb_kalpitiya_33kv_feeder.dss"
    qsts["finance_wiring"] = {"enabled": True}
    assert _build_cashflow_params(cfg).curtailment_pct == 0.0
    _assert_canon(_run_kpis(cfg))


def test_flag_with_synthetic_demo_feeder_stays_canon() -> None:
    """use_synthetic_demo=true is a smoke-test marker: it must NEVER drive finance, so the
    composed curtailment stays untouched even with the finance wiring enabled."""
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["use_synthetic_demo"] = True
    qsts["finance_wiring"] = {"enabled": True}
    assert _build_cashflow_params(cfg).curtailment_pct == 0.0


@pytest.mark.skipif(
    _HAS_GRID_EXTRA,
    reason="[grid] extra installed — the CASPER absent-dependency guard is unreachable",
)
def test_flag_with_real_file_but_no_grid_extra_raises_actionable(
    tmp_path: Path,
) -> None:
    """A real-looking feeder file + the flag, WITHOUT opendssdirect ⇒ the CASPER call-time
    guard raises the actionable ``[grid]`` ImportError. It must NOT silently fall back to
    canon: the user explicitly requested a KPI-moving study, so a silent unchanged result
    would be a fabricated "no self-curtailment" pass (NO SPURIOUS PASS).
    """
    feeder = tmp_path / "demo923_feeder.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["feeder_model_path"] = str(feeder)
    qsts["export_cap_mw"] = DEMO_EXPORT_CAP_MW
    qsts["generation_profile_mw"] = list(DEMO_PROFILE_MW)
    qsts["finance_wiring"] = {"enabled": True}
    with pytest.raises(ImportError, match=r"\[grid\] extra"):
        _build_cashflow_params(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DEMO-GRADE oracle evidence — a stubbed OpenDSS engine over a tmp demo feeder
#    (labelled: NOT site physics; the accounting + finance chain is production code)
# ─────────────────────────────────────────────────────────────────────────────


class _RecordingStubDss:
    """A recording stand-in for the ``opendssdirect`` module (DEMO ONLY).

    The base venv has no ``[grid]`` extra, so the solver binary is stubbed; the REAL
    :func:`analytics.grid.curtailment_qsts._solve_qsts` still executes (Redirect, QSTS
    mode/stepsize, per-step injection + solve), which this stub records so the test can
    prove the production solve path ran rather than being bypassed.
    """

    def __init__(self) -> None:
        self.log: List[Tuple[str, Any]] = []
        stub = self

        class _Solution:
            @staticmethod
            def Mode(mode: int) -> None:
                stub.log.append(("mode", mode))

            @staticmethod
            def StepSize(seconds: float) -> None:
                stub.log.append(("stepsize", seconds))

            @staticmethod
            def Number(n: int) -> None:
                stub.log.append(("number", n))

            @staticmethod
            def Solve() -> None:
                stub.log.append(("solve", None))

        class _Generators:
            @staticmethod
            def kW(kw: float) -> None:
                stub.log.append(("kw", kw))

        self.Solution = _Solution
        self.Generators = _Generators

    def Command(self, command: str) -> None:
        self.log.append(("command", command))


def _demo_config(
    feeder: Path, *, instructed: List[float] | None = None
) -> Dict[str, Any]:
    """The DEMO scenario: committed lendercase + the demo QSTS block + the flag ON."""
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["feeder_model_path"] = str(feeder)
    qsts["export_cap_mw"] = DEMO_EXPORT_CAP_MW
    qsts["generation_profile_mw"] = list(DEMO_PROFILE_MW)
    if instructed is not None:
        qsts["grid_instructed_profile_mw"] = list(instructed)
    qsts["finance_wiring"] = {"enabled": True}
    return cfg


def _stub_opendss(monkeypatch: pytest.MonkeyPatch) -> _RecordingStubDss:
    stub = _RecordingStubDss()
    monkeypatch.setattr(
        "analytics.grid.curtailment_qsts._require_opendss", lambda: stub
    )
    return stub


def test_demo_oracle_pair_canon_unmoved_and_demo_moves_kpis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE #923 READINESS PAIR: the committed canon does NOT move, and the identically-built
    pipeline DOES move — correctly signed on every headline KPI — once a (demo) feeder file
    exists and the flag is on. Composed curtailment_pct is exactly the demo's 8% self share.

    DEMO evidence only: the tmp feeder is synthetic (no site physics) and the OpenDSS solver
    is a recording stub. The measured deltas quantify the WIRING, not Kalpitiya curtailment.
    """
    before = _run_kpis(_lender_config())  # untouched committed scenario, no flag
    _assert_canon(before)

    stub = _stub_opendss(monkeypatch)
    feeder = tmp_path / "demo923_feeder.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")
    cfg = _demo_config(feeder)

    # The composed loss key is exactly the demo self-curtailment (config curtailment 0.0).
    assert _build_cashflow_params(cfg).curtailment_pct == pytest.approx(
        DEMO_SELF_CURTAILMENT_DECIMAL
    )

    after = _run_kpis(cfg)

    # Correctly-signed, real moves on every headline KPI (the D6b design intent).
    assert after["project_irr"] < before["project_irr"] - 1e-6
    assert after["equity_irr"] < before["equity_irr"] - 1e-6
    assert after["min_dscr"] < before["min_dscr"] - 1e-6
    assert after["total_cfads_usd"] < before["total_cfads_usd"]
    assert after["project_npv"] < before["project_npv"]

    # Prove the PRODUCTION _solve_qsts ran against the demo feeder (not a bypass): the stub
    # saw the Redirect of OUR tmp file, and every QSTS batch solved one step per timestep
    # (the pipeline builds cashflow params more than once per run, so whole batches — a
    # positive multiple of the profile length — is the honest invariant).
    commands = [arg for op, arg in stub.log if op == "command"]
    assert any(str(feeder) in c for c in commands), commands
    n_solves = sum(1 for op, _ in stub.log if op == "solve")
    n_redirects = len(commands)
    assert n_redirects > 0
    assert n_solves == n_redirects * len(DEMO_PROFILE_MW)


def test_demo_deemed_paid_schedule_neutral_through_real_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adding an 8%-of-gross grid-instructed (deemed-paid) schedule to the SAME demo changes
    NOTHING in the KPIs: deemed energy is PAID under the CEB SPPA and must never haircut.
    Unlike the #915 leg, this drives the schedule through the REAL QSTS accounting
    (``grid.qsts.grid_instructed_profile_mw`` → split_curtailment), not a monkeypatched
    result object.
    """
    _stub_opendss(monkeypatch)
    feeder = tmp_path / "demo923_feeder.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")

    kpis_self_only = _run_kpis(_demo_config(feeder))
    kpis_with_deemed = _run_kpis(
        _demo_config(feeder, instructed=DEMO_INSTRUCTED_PROFILE_MW)
    )

    assert kpis_with_deemed["project_irr"] == pytest.approx(
        kpis_self_only["project_irr"], abs=1e-12
    )
    assert kpis_with_deemed["equity_irr"] == pytest.approx(
        kpis_self_only["equity_irr"], abs=1e-12
    )
    assert kpis_with_deemed["min_dscr"] == pytest.approx(
        kpis_self_only["min_dscr"], abs=1e-12
    )
    assert kpis_with_deemed["total_cfads_usd"] == pytest.approx(
        kpis_self_only["total_cfads_usd"], abs=1e-6
    )
