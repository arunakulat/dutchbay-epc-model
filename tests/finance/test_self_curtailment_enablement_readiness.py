"""#923 — D6b enablement-READINESS evidence (the flag stays PARKED; nothing here moves canon).

Issue #923 gates turning ``grid.qsts.finance_wiring.enabled`` ON for a committed scenario.
Its trigger — a REAL CEB feeder model at the DutchBay POC — has NOT fired, so this suite
pins the two halves of enablement readiness WITHOUT enabling anything:

  1. **The refusal gate, through the REAL chain (no ``run_qsts_curtailment`` monkeypatch).**
     The #915 suite (``test_self_curtailment_finance.py``) covers the resolver units and
     monkeypatches the QSTS seam on every canonical path. Here the enabled flag is exercised
     against the PRODUCTION chain end-to-end: a lone or synthetic finance flag fails the
     canonical configuration gate, and a site-labelled path without an externally pinned
     #1072 evidence package now fails before solver import. The untouched default-off case
     remains canon-identical; an enabled missing identity can no longer masquerade as an
     innocent inert result.

  2. **DEMO-GRADE diagnostic and refusal evidence.** The temporary feeder is explicitly
     ``test_fixture`` and carries no site physics. A recording solver proves the production
     QSTS path executes and calculates the expected 8% diagnostic split; the finance seam
     then fails loudly at the configuration and result boundaries. File existence can no
     longer launder the fixture into a project KPI.

None of these numbers is presentable as site physics. The real enablement sequence stays
user-gated: real feeder → QSTS run → kpi_oracle before/after diff → user sign-off → flag +
canon re-pin in the SAME PR (see docs/knowledge_base/grid_screening_scope.md §7).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from analytics.grid.curtailment_qsts import run_qsts_curtailment
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14_params import _build_cashflow_params
from tests._canon import LENDER_EQUITY_IRR as CANON_EQ_IRR
from tests._canon import LENDER_MIN_DSCR as CANON_MIN_DSCR
from tests._canon import LENDER_PROJECT_IRR as CANON_PROJ_IRR

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Committed 5th-gen canon (single source of truth: tests/_canon.py, #955).

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


def test_flag_alone_without_qsts_study_fails_strictly() -> None:
    """A lone KPI-moving flag cannot bypass the QSTS pre-flight contract."""
    cfg = _lender_config()
    _qsts_block(cfg)["finance_wiring"] = {"enabled": True}
    with pytest.raises(ValueError, match="canonical finance configuration refused"):
        _build_cashflow_params(cfg)


def test_flag_with_unpinned_site_label_fails_before_finance() -> None:
    """A site label/path without externally pinned evidence is no longer an inert pass."""
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["input_kind"] = "engineer_prepared_site_model"
    qsts["feeder_model_path"] = "/nonexistent/ceb_kalpitiya_33kv_feeder.dss"
    qsts["finance_wiring"] = {
        "enabled": True,
        "mode": "canonical",
        "canonical_eligible": True,
    }
    with pytest.raises(ValueError, match="evidence_manifest"):
        _build_cashflow_params(cfg)
    # The untouched, default-off scenario remains byte-identical to canon.
    _assert_canon(_run_kpis(_lender_config()))


def test_flag_with_synthetic_demo_feeder_fails_strictly() -> None:
    """A pathless demo cannot be enabled at the KPI-moving canonical seam."""
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["input_kind"] = "test_fixture"
    qsts["use_synthetic_demo"] = True
    qsts["finance_wiring"] = {
        "enabled": True,
        "mode": "synthetic_counterfactual",
        "canonical_eligible": False,
    }
    with pytest.raises(ValueError, match="canonical finance configuration refused"):
        _build_cashflow_params(cfg)


def test_flag_with_real_file_but_no_evidence_manifest_fails_before_solver(
    tmp_path: Path,
) -> None:
    """An existing DSS file cannot outrank the #1072 evidence pre-flight boundary."""
    feeder = tmp_path / "canonical_contract_shape_only.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["input_kind"] = "engineer_prepared_site_model"
    qsts["feeder_model_path"] = str(feeder)
    qsts["export_cap_mw"] = DEMO_EXPORT_CAP_MW
    qsts["generation_profile_mw"] = list(DEMO_PROFILE_MW)
    qsts["finance_wiring"] = {
        "enabled": True,
        "mode": "canonical",
        "canonical_eligible": True,
    }
    with pytest.raises(ValueError, match="evidence_manifest"):
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
    """The DEMO scenario: path-backed fixture with canonical finance explicitly parked."""
    cfg = _lender_config()
    qsts = _qsts_block(cfg)
    qsts["enabled"] = True
    qsts["input_kind"] = "test_fixture"
    qsts["feeder_model_path"] = str(feeder)
    qsts["export_cap_mw"] = DEMO_EXPORT_CAP_MW
    qsts["generation_profile_mw"] = list(DEMO_PROFILE_MW)
    if instructed is not None:
        qsts["grid_instructed_profile_mw"] = list(instructed)
    qsts["finance_wiring"] = {
        "enabled": False,
        "mode": "synthetic_counterfactual",
        "canonical_eligible": False,
    }
    return cfg


def _stub_opendss(monkeypatch: pytest.MonkeyPatch) -> _RecordingStubDss:
    stub = _RecordingStubDss()
    monkeypatch.setattr(
        "analytics.grid.curtailment_qsts._require_opendss", lambda: stub
    )
    return stub


def test_demo_oracle_pair_canon_unmoved_and_fixture_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fixture can exercise QSTS, but its typed provenance blocks canonical finance."""
    before = _run_kpis(_lender_config())  # untouched committed scenario, no flag
    _assert_canon(before)

    stub = _stub_opendss(monkeypatch)
    feeder = tmp_path / "demo923_feeder.dss"
    feeder.write_text(_DEMO_FEEDER_DSS, encoding="utf-8")
    cfg = _demo_config(feeder)

    result = run_qsts_curtailment(cfg)
    assert result.self_curtailed_pct == pytest.approx(
        DEMO_SELF_CURTAILMENT_DECIMAL * 100.0
    )
    assert result.feeder_input_kind == "test_fixture"
    assert result.generated_input is True
    assert result.canonical_finance_eligible is False
    assert _build_cashflow_params(cfg).curtailment_pct == pytest.approx(
        _build_cashflow_params(_lender_config()).curtailment_pct
    )
    cfg["grid"]["qsts"]["finance_wiring"]["enabled"] = True
    with pytest.raises(ValueError, match="canonical finance configuration refused"):
        _build_cashflow_params(cfg)
    _assert_canon(_run_kpis(_lender_config()))

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

    self_only = run_qsts_curtailment(_demo_config(feeder))
    with_deemed = run_qsts_curtailment(
        _demo_config(feeder, instructed=DEMO_INSTRUCTED_PROFILE_MW)
    )

    assert with_deemed.self_curtailed_pct == pytest.approx(self_only.self_curtailed_pct)
    assert with_deemed.deemed_paid_pct == pytest.approx(8.0)
    cfg = _demo_config(feeder)
    assert _build_cashflow_params(cfg).curtailment_pct == pytest.approx(
        _build_cashflow_params(_lender_config()).curtailment_pct
    )
    cfg["grid"]["qsts"]["finance_wiring"]["enabled"] = True
    with pytest.raises(ValueError, match="canonical finance configuration refused"):
        _build_cashflow_params(cfg)
