"""The yield-reconciliation record on every run result (#1768).

``analytics.aep_reconciliation.build_yield_reconciliation_record`` describes the AEP <->
capacity-factor check that the fail-loud gate (``reconcile_capacity_factor_with_bankable_aep``)
makes. The independent oracle here is that pre-existing gate (TEST-01): on every committed
scenario, and on perturbed copies of them, the record's verdict must agree with whether the
gate raises. The arithmetic is also checked against a closed form, and a mutation of the
capacity factor shows the record responds to its input rather than restating a constant.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from analytics.aep_reconciliation import (
    YIELD_RECONCILIATION_SCHEMA_VERSION,
    AepReconciliationError,
    build_yield_reconciliation_record,
    default_tolerance_pct,
    reconcile_capacity_factor_with_bankable_aep,
)
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Committed scenarios that declare a bankable net AEP (P50 and P90), listed by
#: ``tests/analytics/test_aep_reconciliation.py`` or found by
#: ``git grep -l net_aep_p50_gwh scenarios/``.
BANKABLE_SCENARIOS = [
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    "scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml",
    "scenarios/dutchbay_capex_eia_prudent_2025Q4.yaml",
    "scenarios/dutchbay_capex_sinohydro_lean_2025Q4.yaml",
    "scenarios/dutchbay_hybrid_bess_2025Q4.yaml",
    "scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml",
    "scenarios/dutchbay_solar_only_2025Q4.yaml",
    "scenarios/kalpitiya_lendercase_160m_fitted.yaml",
    "scenarios/mullikulam_2x50mw_mannar.yaml",
]


def _gate_passes(cfg: dict[str, Any]) -> bool:
    try:
        reconcile_capacity_factor_with_bankable_aep(copy.deepcopy(cfg), "<test>")
    except AepReconciliationError:
        return False
    return True


def _synthetic(
    capacity_mw: float = 100.0, capacity_factor: float = 0.4, **extra: Any
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "project": {"capacity_mw": capacity_mw, "capacity_factor": capacity_factor}
    }
    cfg.update(extra)
    return cfg


# --- the committed scenarios: the gate is the oracle ----------------------------------


@pytest.fixture(scope="module", params=BANKABLE_SCENARIOS)
def loaded(request: pytest.FixtureRequest, monkeypatch_module: Any) -> dict[str, Any]:
    return load_scenario_config(str(REPO_ROOT / request.param))


@pytest.fixture(scope="module")
def monkeypatch_module() -> Any:
    # aep_summary_path values are repo-relative, as the gate reads them.
    mp = pytest.MonkeyPatch()
    mp.chdir(REPO_ROOT)
    yield mp
    mp.undo()


def test_committed_scenarios_reconcile_and_agree_with_the_gate(
    loaded: dict[str, Any],
) -> None:
    record = build_yield_reconciliation_record(loaded, gate_applied=True)
    assert record["schema_version"] == YIELD_RECONCILIATION_SCHEMA_VERSION
    assert record["gate_applied"] is True
    # The scenario loaded, so the gate passed: the record must not claim otherwise.
    assert _gate_passes(loaded)
    assert record["status"] == "reconciled"
    assert record["p50"]["status"] == "reconciled"
    assert record["p50"]["references"], "a bankable scenario compares at least one P50"
    for ref in record["p50"]["references"]:
        assert ref["within_tolerance"] is True
        assert abs(ref["deviation_pct"]) <= record["tolerance_pct"]
    json.dumps(record)  # JSON-serialisable, as summary.json needs


def test_record_flags_what_the_gate_refuses(loaded: dict[str, Any]) -> None:
    """Push the capacity factor 1.5x the tolerance off: the gate raises and the record says so."""
    record = build_yield_reconciliation_record(loaded, gate_applied=True)
    tolerance = record["tolerance_pct"] / 100.0
    perturbed = copy.deepcopy(loaded)
    # Write the shifted CF where the engine reads it first, in decimal form.
    perturbed.setdefault("project", {})["capacity_factor"] = record[
        "capacity_factor"
    ] * (1.0 + 1.5 * tolerance + 0.01)
    assert not _gate_passes(perturbed)
    moved = build_yield_reconciliation_record(perturbed, gate_applied=False)
    assert moved["status"] == "outside_tolerance"
    assert moved["p50"]["status"] == "outside_tolerance"
    # Responsiveness: the implied generation moved with the capacity factor.
    assert moved["implied_net_aep_gwh"] > record["implied_net_aep_gwh"]


# --- arithmetic against a closed form -------------------------------------------------


def test_deviation_matches_closed_form() -> None:
    # 100 MW x 0.40 x 8.76 = 350.4 GWh against a 351.0 GWh reference.
    cfg = _synthetic(expected_results={"net_aep_p50_gwh": 351.0})
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["implied_net_aep_gwh"] == pytest.approx(350.4)
    (ref,) = record["p50"]["references"]
    assert ref["source"] == "expected_results.net_aep_p50_gwh"
    assert ref["net_aep_gwh"] == 351.0
    assert ref["deviation_pct"] == pytest.approx((350.4 - 351.0) / 351.0 * 100.0)
    assert ref["within_tolerance"] is True
    assert record["status"] == "reconciled"
    assert record["tolerance_pct"] == default_tolerance_pct()
    assert record["tolerance_source"] == "default"
    assert record["tolerance_overridden"] is False


def test_boundary_matches_the_gate_on_both_sides() -> None:
    tol = default_tolerance_pct() / 100.0
    implied = 100.0 * 0.4 * 8.76
    inside = _synthetic(
        expected_results={"net_aep_p50_gwh": implied / (1.0 + tol * 0.999)}
    )
    outside = _synthetic(
        expected_results={"net_aep_p50_gwh": implied / (1.0 + tol * 1.001)}
    )
    assert _gate_passes(inside)
    assert build_yield_reconciliation_record(inside, gate_applied=False)["status"] == (
        "reconciled"
    )
    assert not _gate_passes(outside)
    assert build_yield_reconciliation_record(outside, gate_applied=False)["status"] == (
        "outside_tolerance"
    )


def test_tolerance_override_is_recorded() -> None:
    cfg = _synthetic(
        expected_results={"net_aep_p50_gwh": 351.0},
        aep_reconciliation={"tolerance_pct": 5.0},
    )
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["tolerance_pct"] == 5.0
    assert record["tolerance_source"] == "scenario"
    assert record["tolerance_overridden"] is True


def test_p90_comparison(tmp_path: Path) -> None:
    summary = tmp_path / "aep_summary.json"
    summary.write_text(
        json.dumps(
            {"net_site_aep_gwh": 350.4, "exceedance": {"net_aep_p90_1yr_gwh": 300.0}}
        )
    )
    cfg = _synthetic(
        expected_results={"net_aep_p90_gwh": 301.5},
        resource={"aep_summary_path": str(summary)},
    )
    assert _gate_passes(cfg)
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    p90 = record["p90"]
    assert p90["status"] == "reconciled"
    assert p90["frozen_net_aep_p90_gwh"] == 301.5
    assert p90["summary_net_aep_p90_gwh"] == 300.0
    assert p90["deviation_pct"] == pytest.approx(0.5)
    assert record["p50"]["references"][0]["source"] == f"{summary}:net_site_aep_gwh"

    cfg["expected_results"]["net_aep_p90_gwh"] = 330.0  # 10% off
    assert not _gate_passes(cfg)
    assert build_yield_reconciliation_record(cfg, gate_applied=False)["status"] == (
        "outside_tolerance"
    )


# --- nothing to compare, or an input that cannot be read ------------------------------


def test_no_reference_is_not_applicable() -> None:
    record = build_yield_reconciliation_record(_synthetic(), gate_applied=True)
    assert record["status"] == "not_applicable"
    assert record["p50"]["reason"] == "no bankable net-AEP reference declared"
    assert record["p90"]["status"] == "not_applicable"
    assert record["reason"]


def test_no_billed_basis_is_not_applicable() -> None:
    record = build_yield_reconciliation_record(
        {"expected_results": {"net_aep_p50_gwh": 351.0}}, gate_applied=True
    )
    assert record["status"] == "not_applicable"
    assert record["p50"]["reason"] == "no resolvable capacity_mw and capacity_factor"
    assert record["implied_net_aep_gwh"] is None


def test_unreadable_summary_is_not_checked_and_never_raises(tmp_path: Path) -> None:
    cfg = _synthetic(resource={"aep_summary_path": str(tmp_path / "missing.json")})
    with pytest.raises(AepReconciliationError):
        reconcile_capacity_factor_with_bankable_aep(copy.deepcopy(cfg))
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["status"] == "not_checked"
    assert "AepReconciliationError" in record["reason"]


def test_unreadable_summary_without_a_billed_basis_follows_the_gate(
    tmp_path: Path,
) -> None:
    """The gate reads P50 references only when there is a billed basis; so does the record."""
    cfg = {"resource": {"aep_summary_path": str(tmp_path / "missing.json")}}
    assert _gate_passes(cfg)
    record = build_yield_reconciliation_record(cfg, gate_applied=True)
    assert record["status"] == "not_applicable"


def test_non_numeric_tolerance_is_not_checked() -> None:
    cfg = _synthetic(aep_reconciliation={"tolerance_pct": "loose"})
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["status"] == "not_checked"


def test_builder_does_not_mutate_its_input() -> None:
    cfg = _synthetic(expected_results={"net_aep_p50_gwh": 351.0})
    before = copy.deepcopy(cfg)
    build_yield_reconciliation_record(cfg, gate_applied=False)
    assert cfg == before


# --- the pipeline result ---------------------------------------------------------------


@pytest.mark.slow
def test_pipeline_result_carries_the_record_bound_to_the_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    monkeypatch.chdir(REPO_ROOT)
    path = "scenarios/dutchbay_lendercase_2025Q4.yaml"
    from_file = run_v14_pipeline(path)
    record = from_file["yield_reconciliation"]
    assert record["gate_applied"] is True
    assert record["status"] == "reconciled"
    assert record["config_sha256"] == from_file["run_manifest"]["config_sha256"]
    # The manifest's own field set is unchanged by the record.
    assert "yield_reconciliation" not in from_file["run_manifest"]

    inline = run_v14_pipeline(load_scenario_config(path))
    assert inline["yield_reconciliation"]["gate_applied"] is False
    assert inline["yield_reconciliation"]["status"] == "reconciled"
    # Disclosure only: the same scenario gives the same KPIs either way.
    assert inline["kpis"] == from_file["kpis"]


# --- review follow-ups: exact boundary, non-positive references, seams ------------------


def test_exactly_at_tolerance_is_within_as_the_gate_says() -> None:
    """105 against 100 at 5%: relative == tolerance exactly; the gate passes, so does the record."""
    cfg = _synthetic(
        capacity_mw=105.0 / 8.76,
        capacity_factor=1.0,
        expected_results={"net_aep_p50_gwh": 100.0},
        aep_reconciliation={"tolerance_pct": 5.0},
    )
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["implied_net_aep_gwh"] == 105.0  # exact in binary64
    assert _gate_passes(cfg)
    (ref,) = record["p50"]["references"]
    assert ref["deviation_pct"] == 5.0
    assert ref["within_tolerance"] is True
    assert record["status"] == "reconciled"
    # One step tighter and both refuse.
    cfg["aep_reconciliation"]["tolerance_pct"] = 4.999999
    assert not _gate_passes(cfg)
    assert build_yield_reconciliation_record(cfg, gate_applied=False)["status"] == (
        "outside_tolerance"
    )


@pytest.mark.parametrize("reference", [0.0, -10.0])
def test_non_positive_p50_reference_is_never_within(reference: float) -> None:
    cfg = _synthetic(expected_results={"net_aep_p50_gwh": reference})
    assert not _gate_passes(cfg)
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    (ref,) = record["p50"]["references"]
    assert ref["within_tolerance"] is False
    assert ref["deviation_pct"] is None
    assert ref["note"] == "non-positive reference"
    assert record["status"] == "outside_tolerance"


@pytest.mark.parametrize(("frozen", "exported"), [(0.0, 300.0), (300.0, -1.0)])
def test_non_positive_p90_is_never_within(
    tmp_path: Path, frozen: float, exported: float
) -> None:
    summary = tmp_path / "aep_summary.json"
    summary.write_text(
        json.dumps(
            {"net_site_aep_gwh": 350.4, "exceedance": {"net_aep_p90_1yr_gwh": exported}}
        )
    )
    cfg = _synthetic(
        expected_results={"net_aep_p90_gwh": frozen},
        resource={"aep_summary_path": str(summary)},
    )
    assert not _gate_passes(cfg)
    record = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert record["p90"]["within_tolerance"] is False
    assert record["p90"]["deviation_pct"] is None
    assert record["p90"]["note"] == "non-positive P90"
    assert record["status"] == "outside_tolerance"


def test_engine_records_where_the_gate_ran() -> None:
    from analytics.aep_reconciliation import record_gate_applied_at_seam

    cfg = _synthetic(expected_results={"net_aep_p50_gwh": 351.0})
    assert build_yield_reconciliation_record(cfg, gate_applied=True)["gate_site"] == (
        "scenario_load"
    )
    inline = build_yield_reconciliation_record(cfg, gate_applied=False)
    assert inline["gate_site"] is None
    result = {"yield_reconciliation": inline}
    record_gate_applied_at_seam(result, "api_boundary")
    assert inline["gate_applied"] is True
    assert inline["gate_site"] == "api_boundary"
    record_gate_applied_at_seam({}, "api_boundary")  # no record: nothing to do
    record_gate_applied_at_seam(None, "api_boundary")


def _spy_on_seam(monkeypatch: pytest.MonkeyPatch, module: Any) -> list[dict[str, Any]]:
    """Wrap a module's record_gate_applied_at_seam to keep the result it marked."""
    seen: list[dict[str, Any]] = []
    real = module.record_gate_applied_at_seam

    def spy(result: Any, gate_site: str) -> None:
        real(result, gate_site)
        seen.append(result)

    monkeypatch.setattr(module, "record_gate_applied_at_seam", spy)
    return seen


@pytest.mark.slow
def test_service_seam_behind_the_cases_routes_records_the_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.pipeline_service import run_finance_case

    monkeypatch.chdir(REPO_ROOT)
    scenario = load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
    record = run_finance_case(scenario)["yield_reconciliation"]
    assert record["gate_applied"] is True
    assert record["gate_site"] == "service_seam"
    assert record["status"] == "reconciled"
    # A screening run skips the gate, and its record says so.
    screening = run_finance_case(scenario, skip_bankable_reconciliation=True)
    assert screening["yield_reconciliation"]["gate_applied"] is False
    assert screening["yield_reconciliation"]["gate_site"] is None


@pytest.mark.slow
@pytest.mark.parametrize(
    "payload",
    [
        {"config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml"},
        {
            "config_path": "scenarios/dutchbay_lendercase_2025Q4.yaml",
            "overrides": {"tariff.lkr_per_kwh": 30.0},
        },
        "inline",
    ],
    ids=["config_path", "config_path_with_overrides", "inline_config"],
)
def test_run_pipeline_api_records_the_gate(
    monkeypatch: pytest.MonkeyPatch, payload: Any
) -> None:
    import api.pipeline_api as pipeline_api
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    monkeypatch.chdir(REPO_ROOT)
    if payload == "inline":
        payload = {
            "config": load_scenario_config("scenarios/dutchbay_lendercase_2025Q4.yaml")
        }
    seen = _spy_on_seam(monkeypatch, pipeline_api)
    run_pipeline(RunPipelineRequest(**payload))
    (result,) = seen
    record = result["yield_reconciliation"]
    assert record["gate_applied"] is True
    assert record["gate_site"] == "api_boundary"
    assert record["status"] == "reconciled"
