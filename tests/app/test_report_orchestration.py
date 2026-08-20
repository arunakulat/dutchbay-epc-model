"""Typed seam tests for TEST-04 report orchestration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

import pytest
from conftest import _load_report_test_policy, _load_stochastic_test_policy
from pydantic import ValidationError

from app.models.inputs import WindFarmInputs
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    ReportSensitivityBundle,
    ReportSensitivityMethodMetadata,
    build_report_context_from_case,
    compute_report_sensitivity,
    run_report_case,
)
from app.services.report_global_sa import GlobalSABlock
from app.services.report_tornado import TornadoBlock, TornadoRow

GENERATED_AT = "2026-08-20T00:00:00+00:00"


def _inputs() -> WindFarmInputs:
    return WindFarmInputs(
        site_name="Report seam",
        capacity_mw=159.6,
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )


def _tornado() -> TornadoBlock:
    return TornadoBlock(
        metric="project_irr",
        rows=[
            TornadoRow(label=f"driver-{index}", impact_abs=float(index))
            for index in range(7)
        ],
    )


def _global_sa(method: str, n_runs: int) -> GlobalSABlock:
    return GlobalSABlock(
        method=method,
        metric="project_irr",
        n_runs=n_runs,
        drivers=[],
    )


def test_run_report_case_is_a_deterministic_typed_finance_seam() -> None:
    observed: dict[str, Mapping[str, Any]] = {}

    def _finance(scenario: Mapping[str, Any]) -> Mapping[str, Any]:
        observed["scenario"] = scenario
        return {
            "status": "success",
            "kpis": {"project_irr": 0.0422, "min_dscr": 1.30},
            "run_manifest": {"config_sha256": "a" * 64},
        }

    report_case = run_report_case(
        _inputs(), generated_at=GENERATED_AT, finance_runner=_finance
    )

    assert report_case.generated_at == GENERATED_AT
    assert report_case.scenario_config is observed["scenario"]
    assert report_case.case_result.status == "success"
    assert report_case.case_result.kpis["project_irr"] == pytest.approx(0.0422)


def test_bounded_profile_records_all_methods_within_test03_budget() -> None:
    scenario = _inputs().to_scenario_config()
    calls: dict[str, dict[str, int]] = {}
    report_policy = _load_report_test_policy()
    stochastic_policy = _load_stochastic_test_policy()

    def _morris(_scenario: Mapping[str, Any], *, n_trajectories: int) -> GlobalSABlock:
        calls["morris"] = {"n_trajectories": n_trajectories}
        return _global_sa("morris", 28)

    def _pawn(_scenario: Mapping[str, Any], *, n: int, s: int) -> GlobalSABlock:
        calls["pawn"] = {"n": n, "s": s}
        return _global_sa("pawn", 128)

    bundle = compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: _tornado(),
        morris_computer=_morris,
        pawn_computer=_pawn,
    )

    assert bundle.profile == "ordinary_bounded"
    assert asdict(ORDINARY_REPORT_SENSITIVITY_PROFILE) == asdict(
        report_policy.ordinary_sensitivity_profile
    )
    assert calls == {
        "morris": {"n_trajectories": 4},
        "pawn": {"n": 128, "s": 10},
    }
    assert [entry.method for entry in bundle.methods] == [
        "tornado",
        "morris",
        "pawn",
    ]
    assert bundle.requested_evaluations == 171
    assert bundle.effective_evaluations == 171
    assert bundle.requested_evaluations <= stochastic_policy.hard_max_model_evaluations
    assert bundle.effective_evaluations <= stochastic_policy.hard_max_model_evaluations


def test_production_profile_preserves_historical_morris_and_pawn_counts() -> None:
    scenario = _inputs().to_scenario_config()
    calls: dict[str, int] = {}
    report_policy = _load_report_test_policy()

    def _morris(_scenario: Mapping[str, Any], *, n_trajectories: int) -> GlobalSABlock:
        calls["morris"] = n_trajectories
        return _global_sa("morris", 112)

    def _pawn(_scenario: Mapping[str, Any], *, n: int, s: int) -> GlobalSABlock:
        calls["pawn"] = n
        calls["pawn_slices"] = s
        return _global_sa("pawn", 256)

    bundle = compute_report_sensitivity(
        scenario,
        profile=PRODUCTION_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: _tornado(),
        morris_computer=_morris,
        pawn_computer=_pawn,
    )

    assert calls == {"morris": 16, "pawn": 256, "pawn_slices": 10}
    assert bundle.profile == "production_full"
    assert asdict(PRODUCTION_REPORT_SENSITIVITY_PROFILE) == asdict(
        report_policy.production_sensitivity_profile
    )
    assert bundle.requested_evaluations == 383
    assert bundle.effective_evaluations == 383


def test_context_assembly_consumes_precomputed_case_and_sensitivity() -> None:
    report_case = run_report_case(
        _inputs(),
        generated_at=GENERATED_AT,
        finance_runner=lambda _scenario: {
            "status": "success",
            "kpis": {
                "project_irr": 0.0422,
                "equity_irr": -0.0246,
                "project_npv": -57_994_285.93,
                "min_dscr": 1.30,
            },
        },
    )
    sensitivity = compute_report_sensitivity(
        report_case.scenario_config,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: _tornado(),
        morris_computer=lambda _scenario, **_kwargs: _global_sa("morris", 28),
        pawn_computer=lambda _scenario, **_kwargs: _global_sa("pawn", 128),
    )

    context = build_report_context_from_case(report_case, sensitivity)

    assert context.generated_at == GENERATED_AT
    assert context.scenario_variant == "lendercase"
    assert context.tornado is sensitivity.tornado
    assert context.global_sa is sensitivity.morris
    assert context.global_sa_pawn is sensitivity.pawn


def test_bundle_rejects_evaluation_totals_that_do_not_tie() -> None:
    methods = tuple(
        ReportSensitivityMethodMetadata(
            method=method,
            requested_evaluations=requested,
            effective_evaluations=requested,
            outcome="completed",
        )
        for method, requested in (("tornado", 15), ("morris", 28), ("pawn", 128))
    )
    with pytest.raises(ValidationError, match="requested_evaluations must equal"):
        ReportSensitivityBundle(
            profile="ordinary_bounded",
            methods=methods,
            requested_evaluations=170,
            effective_evaluations=171,
        )


def test_bundle_requires_all_methods_and_preserves_degraded_count_uncertainty() -> None:
    scenario = _inputs().to_scenario_config()
    called: list[str] = []

    def _degrade(method: str) -> None:
        called.append(method)
        return None

    bundle = compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _scenario: _degrade("tornado"),
        morris_computer=lambda _scenario, **_kwargs: _degrade("morris"),
        pawn_computer=lambda _scenario, **_kwargs: _degrade("pawn"),
    )

    assert called == ["tornado", "morris", "pawn"]
    assert bundle.requested_evaluations == 171
    assert bundle.effective_evaluations is None
    assert {row.method for row in bundle.methods} == {"tornado", "morris", "pawn"}
    assert all(row.outcome == "degraded" for row in bundle.methods)
    assert all(row.effective_evaluations is None for row in bundle.methods)

    with pytest.raises(ValidationError, match="exactly tornado, morris, and pawn"):
        ReportSensitivityBundle(
            profile="invalid",
            methods=(),
            requested_evaluations=0,
            effective_evaluations=0,
        )
