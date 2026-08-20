"""Typed orchestration seams for lender-report construction.

The report request used to fuse one finance run, three supplemental sensitivity
sweeps, context assembly, and rendering in one API helper.  This module keeps
those responsibilities explicit without moving report-only fields into the
canonical analytics contracts:

* :func:`run_report_case` performs the one canonical finance run;
* :func:`compute_report_sensitivity` performs the optional tornado, Morris, and
  PAWN work and records its evaluation profile; and
* :func:`build_report_context_from_case` is pure assembly from already-computed
  inputs.

Production retains the historical Morris and PAWN settings.  The smaller
ordinary profile is an explicit test/contract option; no production route
selects it implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_model import ReportContext, build_report_context
from app.services.pipeline_service import run_finance_case
from app.services.report_global_sa import (
    GlobalSABlock,
    compute_report_global_sa,
    compute_report_global_sa_pawn,
)
from app.services.report_tornado import TornadoBlock, compute_report_tornado

ReportSensitivityMethod = Literal["tornado", "morris", "pawn"]
ReportSensitivityOutcome = Literal["completed", "degraded"]
FinanceRunner = Callable[[Mapping[str, Any]], Mapping[str, Any]]
TornadoComputer = Callable[..., Optional[TornadoBlock]]
GlobalSAComputer = Callable[..., Optional[GlobalSABlock]]


@dataclass(frozen=True)
class ReportCaseData:
    """Finance result and deterministic inputs needed to assemble a report.

    ``generated_at`` is supplied by the caller so this seam is deterministic in
    tests; the API stamps its production timestamp at the request boundary.
    """

    inputs: WindFarmInputs
    scenario_config: Mapping[str, Any]
    run_result: Mapping[str, Any]
    case_result: CaseResult
    generated_at: str


@dataclass(frozen=True)
class ReportSensitivityProfile:
    """Config-first evaluation controls for report sensitivity composition."""

    name: str
    tornado_evaluations: int
    morris_trajectories: int
    pawn_evaluations: int
    pawn_slices: int


# Historical production defaults from app.services.report_global_sa.  These are
# deliberately not reduced by TEST-04.
PRODUCTION_REPORT_SENSITIVITY_PROFILE = ReportSensitivityProfile(
    name="production_full",
    tornado_evaluations=15,
    morris_trajectories=16,
    pawn_evaluations=256,
    pawn_slices=10,
)

# Six canonical global-SA drivers produce 4 * (6 + 1) + 128 Morris/PAWN
# evaluations.  Together with the seven-driver OAT tornado (15 evaluations),
# the representative lender scenario remains at 171, below TEST-03's 200 cap.
ORDINARY_REPORT_SENSITIVITY_PROFILE = ReportSensitivityProfile(
    name="ordinary_bounded",
    tornado_evaluations=15,
    morris_trajectories=4,
    pawn_evaluations=128,
    pawn_slices=10,
)


class ReportSensitivityMethodMetadata(BaseModel):
    """Evaluation accounting for one report sensitivity method."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: ReportSensitivityMethod
    requested_evaluations: int = Field(ge=0)
    effective_evaluations: Optional[int] = Field(default=None, ge=0)
    outcome: ReportSensitivityOutcome


class ReportSensitivityBundle(BaseModel):
    """Report-local tornado, Morris, and PAWN outputs with execution metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: str
    methods: tuple[ReportSensitivityMethodMetadata, ...]
    requested_evaluations: int = Field(ge=0)
    effective_evaluations: Optional[int] = Field(default=None, ge=0)
    tornado: Optional[TornadoBlock] = None
    morris: Optional[GlobalSABlock] = None
    pawn: Optional[GlobalSABlock] = None

    @model_validator(mode="after")
    def _validate_evaluation_totals(self) -> "ReportSensitivityBundle":
        """Keep aggregate counts tied to their per-method evidence."""
        methods = [entry.method for entry in self.methods]
        if len(methods) != len(set(methods)):
            raise ValueError("report sensitivity methods must be unique")
        if set(methods) != {"tornado", "morris", "pawn"}:
            raise ValueError(
                "report sensitivity methods must contain exactly tornado, morris, and pawn"
            )
        requested = sum(entry.requested_evaluations for entry in self.methods)
        known_effective = [
            entry.effective_evaluations
            for entry in self.methods
            if entry.effective_evaluations is not None
        ]
        effective = (
            sum(known_effective) if len(known_effective) == len(self.methods) else None
        )
        if self.requested_evaluations != requested:
            raise ValueError(
                "requested_evaluations must equal the sum of method metadata"
            )
        if self.effective_evaluations != effective:
            raise ValueError(
                "effective_evaluations must equal the sum of method metadata"
            )
        return self


def run_report_case(
    inputs: WindFarmInputs,
    *,
    generated_at: str,
    finance_runner: FinanceRunner = run_finance_case,
) -> ReportCaseData:
    """Run one canonical finance case and return its typed report inputs.

    Engine validation and integrity exceptions intentionally propagate to the
    API boundary, where they retain the established deterministic HTTP 400 map.
    """
    scenario = inputs.to_scenario_config()
    run_result = finance_runner(scenario)
    case_result = CaseResult.from_pipeline_result(
        run_result, scenario_variant=inputs.scenario_variant
    )
    return ReportCaseData(
        inputs=inputs,
        scenario_config=scenario,
        run_result=run_result,
        case_result=case_result,
        generated_at=generated_at,
    )


def _global_sa_driver_count(scenario_config: Mapping[str, Any]) -> int:
    """Count sweepable authored global-SA drivers for evaluation accounting."""
    monte_carlo = scenario_config.get("monte_carlo") or scenario_config.get(
        "Monte_Carlo"
    )
    if not isinstance(monte_carlo, Mapping):
        return 0
    parameters = monte_carlo.get("parameters")
    if not isinstance(parameters, (list, tuple)):
        return 0
    return sum(
        1
        for parameter in parameters
        if isinstance(parameter, Mapping)
        and str(parameter.get("distribution", parameter.get("kind", "uniform")))
        != "fx_calibrated"
        and parameter.get("low", parameter.get("min")) is not None
        and parameter.get("high", parameter.get("max")) is not None
    )


def _method_metadata(
    *,
    method: ReportSensitivityMethod,
    requested: int,
    effective: Optional[int],
    outcome: ReportSensitivityOutcome,
) -> ReportSensitivityMethodMetadata:
    """Build one method-accounting row without inventing degraded-run counts."""
    return ReportSensitivityMethodMetadata(
        method=method,
        requested_evaluations=max(0, requested),
        effective_evaluations=(None if effective is None else max(0, effective)),
        outcome=outcome,
    )


def compute_report_sensitivity(
    scenario_config: Mapping[str, Any],
    *,
    profile: ReportSensitivityProfile = PRODUCTION_REPORT_SENSITIVITY_PROFILE,
    tornado_computer: TornadoComputer = compute_report_tornado,
    morris_computer: GlobalSAComputer = compute_report_global_sa,
    pawn_computer: GlobalSAComputer = compute_report_global_sa_pawn,
) -> ReportSensitivityBundle:
    """Compute typed supplemental report sensitivity under an explicit profile.

    The adapters retain their established best-effort behavior: a failed or
    unusable supplemental method returns ``None`` without sinking the core
    report.  Evaluation metadata remains explicit so ordinary and qualification
    tests can prove which profile they selected.
    """
    tornado = tornado_computer(scenario_config)
    morris = morris_computer(
        scenario_config, n_trajectories=profile.morris_trajectories
    )
    pawn = pawn_computer(
        scenario_config,
        n=profile.pawn_evaluations,
        s=profile.pawn_slices,
    )

    # Requested work is profile evidence and survives the adapter's CASPER degrade
    # path. Renderable output is not an execution counter: a runner can complete
    # evaluations and subsequently return None because its metric was flagged or its
    # rows were unusable. In that case the effective count is truthfully unknown.
    tornado_requested = profile.tornado_evaluations
    tornado_effective = 1 + 2 * len(tornado.rows) if tornado is not None else None

    driver_count = _global_sa_driver_count(scenario_config)
    morris_requested = profile.morris_trajectories * (driver_count + 1)
    morris_effective = (
        int(morris.n_runs) if morris is not None and morris.n_runs is not None else None
    )
    pawn_requested = profile.pawn_evaluations
    pawn_effective = (
        int(pawn.n_runs) if pawn is not None and pawn.n_runs is not None else None
    )

    methods = (
        _method_metadata(
            method="tornado",
            requested=tornado_requested,
            effective=tornado_effective,
            outcome="completed" if tornado is not None else "degraded",
        ),
        _method_metadata(
            method="morris",
            requested=morris_requested,
            effective=morris_effective,
            outcome="completed" if morris is not None else "degraded",
        ),
        _method_metadata(
            method="pawn",
            requested=pawn_requested,
            effective=pawn_effective,
            outcome="completed" if pawn is not None else "degraded",
        ),
    )
    return ReportSensitivityBundle(
        profile=profile.name,
        methods=methods,
        requested_evaluations=sum(row.requested_evaluations for row in methods),
        effective_evaluations=(
            sum(
                row.effective_evaluations
                for row in methods
                if row.effective_evaluations is not None
            )
            if all(row.effective_evaluations is not None for row in methods)
            else None
        ),
        tornado=tornado,
        morris=morris,
        pawn=pawn,
    )


def build_report_context_from_case(
    report_case: ReportCaseData,
    sensitivity: ReportSensitivityBundle,
) -> ReportContext:
    """Assemble a render-ready context from already-computed typed inputs."""
    result = report_case.run_result
    return build_report_context(
        report_case.case_result,
        generated_at=report_case.generated_at,
        inputs=report_case.inputs,
        scenario_config=report_case.scenario_config,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        tornado=sensitivity.tornado,
        global_sa=sensitivity.morris,
        global_sa_pawn=sensitivity.pawn,
        run_result=result,
    )
