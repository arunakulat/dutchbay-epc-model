"""Async ANALYSIS-job orchestration: bounded MC / sensitivity / global-SA on the
freshly-assessed screening case, reusing the wind-job lifecycle (Dolphin).

``run_analysis_job`` mirrors :func:`app.jobs.runner.run_wind_job`'s shell — the same
store transitions and the same generic client-error boundary — but, instead of running
finance, it (1) recomputes the ACTIVE assessed case exactly as the finance path does
under ``RunMode.SCREENING`` (the live capacity factor, never the stale form input —
#993) and (2) runs a bounded analysis engine over that assessed scenario. Both slow
steps are injected (``assessment_fn`` / ``analysis_fn``) so the whole lifecycle is
testable without the ``[wind]`` toolchain, a network fetch, or the heavy engine.

PR-B1 wires the Monte-Carlo engine, PR-B2 the one-way ``tornado`` engine, and PR-B3
the Morris elementary-effects global-SA engine — all over the same spine and lifecycle.
No finance or engine logic is duplicated here (Dolphin): the assessment reuses
:func:`app.jobs.runner.default_assessment`, the screening seam reuses
``wind_export_to_scenario_patch``, and the analysis reuses the canonical engines.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Mapping

from analytics.core.sensitivity_runner import _default_parameters
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.engine import run_monte_carlo_analysis
from analytics.sensitivity.engine import run_sensitivity_analysis
from analytics.sensitivity.global_sa import build_problem, run_morris
from app.api.responses import AnalysisResult
from app.jobs.models import AnalysisJobRequest, JobProgress, JobState, WindJobRequest
from app.jobs.runner import (
    AssessmentFn,
    AssessmentResult,
    ProgressFn,
    default_assessment,
)
from app.jobs.store import JobStore
from wind_resource.cashflow_adapter import wind_export_to_scenario_patch

logger = logging.getLogger(__name__)

#: Step budget for progress reporting: the assessment reuses ``default_assessment``'s
#: steps 1-3, the analysis engine is step 4, and completion is step 5.
ANALYSIS_TOTAL_STEPS = 5

#: ``(request, assessed_scenario, progress) -> JSON-safe result dict`` — the analysis
#: engine step, injectable. The production step (:func:`default_analysis`) dispatches on
#: ``analysis_type`` and returns an :class:`AnalysisResult` envelope as a plain dict.
AnalysisFn = Callable[
    [AnalysisJobRequest, Mapping[str, Any], ProgressFn], Dict[str, Any]
]


def _build_assessed_scenario(
    wind_request: WindJobRequest, wind_export: Mapping[str, Any]
) -> Dict[str, Any]:
    """Build the ACTIVE assessed scenario the engines analyse (#993 crux).

    Replicates exactly what :func:`app.services.pipeline_service.run_integrated_case`
    does under ``RunMode.SCREENING``: seed the finance scenario from the form, declare
    ``run.mode=screening``, and OVERWRITE the physical resource slots with the
    freshly-assessed export (``physical_only`` — the scenario's own tariff/FX are never
    clobbered by a possibly-stale export, #996 P2). The returned scenario therefore
    carries the FRESH capacity factor as its deterministic base — not the stale
    ``WindFarmInputs.capacity_factor`` the form submitted (feeding that to an engine is
    the #993 defect). This stops before ``run_finance_case``: the analysis engines
    consume the patched scenario directly.
    """
    scenario = wind_request.to_finance_scenario()
    run_block = dict(scenario.get("run") or {})
    run_block["mode"] = "screening"
    scenario["run"] = run_block
    return wind_export_to_scenario_patch(
        wind_export,
        scenario,
        scenario_name=wind_request.p_level,
        adapter_mode="overwrite",
        physical_only=True,
    )


def default_analysis(
    request: AnalysisJobRequest,
    assessed_scenario: Mapping[str, Any],
    progress: ProgressFn,
) -> Dict[str, Any]:
    """Run the requested bounded analysis over the assessed scenario.

    Dispatches on ``request.analysis_type`` — ``mc`` (bounded Monte Carlo),
    ``tornado`` (one-way sensitivity over the canonical default driver library), or
    ``morris`` (Morris elementary-effects global sensitivity over the scenario's
    ``monte_carlo.parameters``). The engine is called with the assessed scenario
    (fresh-CF base) and its serialised result is wrapped in a typed
    :class:`~app.api.responses.AnalysisResult` envelope, returned as a plain JSON-safe
    dict for :attr:`JobRecord.result`.

    All three families run IN-MEMORY over the assessed dict so the sweep honours #993
    (the fresh capacity factor) and — crucially — bypasses ``load_scenario_config``'s
    frozen-bankable reconciliation, which a path-based Morris (``run_morris(config_path)``)
    would otherwise trip on the screening CF (#996). Morris therefore builds its SALib
    problem from the in-memory drivers (``build_problem(params=...)``) and supplies a
    ``raw_config`` evaluator rather than a config path.

    Band semantics (screening honesty, ``mc``): the MC driver BANDS come from the committed
    ``monte_carlo.parameters`` of the base variant (absolute, lender-authored). The
    fresh screening assessment sets the deterministic base; where the two diverge the
    engine surfaces it in ``metadata['base_outside_bounds']`` rather than silently
    re-centering the risk envelope on a screening P50 (that would be a separate
    modelling decision). The full engine ``metadata`` is preserved in the envelope.
    """
    if request.analysis_type == "mc":
        progress(
            ANALYSIS_TOTAL_STEPS - 1,
            f"Running Monte Carlo ({request.n_trials} trials) on the assessed case",
        )
        mc = run_monte_carlo_analysis(
            base_config=assessed_scenario,
            n_trials=request.n_trials,
            seed=request.seed,
        )
        engine_result = mc.model_dump()
    elif request.analysis_type == "tornado":
        progress(
            ANALYSIS_TOTAL_STEPS - 1,
            f"Running one-way tornado sensitivity on {request.metric}",
        )
        # In-memory over the ASSESSED dict (honours #993, and — unlike a path-based
        # sweep — bypasses load_scenario_config's frozen-bankable reconciliation, so the
        # fresh screening CF does not trip the #996 guard). Drivers come from the canonical
        # default library (skips keys absent from the config → no flat bars); strict=True
        # so an unresolvable driver fails loud rather than emitting a silent flat bar.
        parameters = _default_parameters(assessed_scenario)
        if not parameters:
            raise ValueError(
                "tornado analysis found no default sensitivity drivers in the "
                "assessed scenario; expected at least one live finance override path."
            )
        suite = run_sensitivity_analysis(
            base_config=assessed_scenario,
            parameters=parameters,
            metric_keys=[request.metric],
        )
        engine_result = suite.model_dump()
    elif request.analysis_type == "morris":
        progress(
            ANALYSIS_TOTAL_STEPS - 1,
            f"Running Morris global sensitivity ({request.n_trajectories} "
            f"trajectories) on {request.metric}",
        )
        # #996-safe IN-MEMORY drive: the path-based run_morris(config_path) would call
        # load_scenario_config on the screening scenario and trip the frozen-bankable
        # AepReconciliationError on the fresh CF. Instead build the SALib problem from the
        # assessed drivers (build_problem with params -> no config load) and pass a
        # raw_config evaluator (evaluate_with_overrides bypasses load_scenario_config).
        # build_problem fails loud on <2 sweepable drivers (CESSPIT); the request boundary
        # already guarantees a non-empty list-form monte_carlo.parameters for 'morris'.
        mc_block = assessed_scenario.get("monte_carlo") or {}
        problem = build_problem("<in-memory>", params=mc_block.get("parameters"))

        def _evaluate(overrides: Mapping[str, float]) -> Mapping[str, Any]:
            return evaluate_with_overrides(
                config_path=None,
                raw_config=assessed_scenario,
                overrides=dict(overrides),
            )

        engine_result = run_morris(
            metrics=[request.metric],
            n_trajectories=request.n_trajectories,
            seed=request.seed,
            problem=problem,
            evaluate_fn=_evaluate,
        )
    else:  # pragma: no cover - the Literal is exhaustive (mc | tornado | morris)
        raise ValueError(f"unsupported analysis_type: {request.analysis_type!r}")

    return AnalysisResult(
        analysis_type=request.analysis_type,
        metric=request.metric,
        scenario_variant=request.wind.inputs.scenario_variant,
        engine_result=engine_result,
    ).model_dump()


def run_analysis_job(
    job_id: str,
    request: AnalysisJobRequest,
    store: JobStore,
    *,
    assessment_fn: AssessmentFn = default_assessment,
    analysis_fn: AnalysisFn = default_analysis,
) -> None:
    """Execute one async analysis job to completion (mirrors ``run_wind_job``).

    Records every lifecycle transition on the store and captures any exception as
    ``state=failed`` with a GENERIC client message — the raw message can leak internal
    paths/config, so only the exception class is surfaced and the full traceback is
    logged server-side under ``job_id`` (the correct fail-loud behaviour at a task
    boundary; the worker is never crashed). Both slow steps are injected for testability.

    Args:
        job_id: The id of an already-created (queued) job record.
        request: The validated async analysis submission.
        store: Where lifecycle transitions are recorded.
        assessment_fn: The slow resource step; defaults to the real pipeline
            (:func:`app.jobs.runner.default_assessment`).
        analysis_fn: The analysis engine step; defaults to :func:`default_analysis`.
    """

    def progress(step: int, message: str) -> None:
        store.update(
            job_id,
            progress=JobProgress(
                step=step, total_steps=ANALYSIS_TOTAL_STEPS, message=message
            ),
        )

    try:
        store.update(job_id, state=JobState.RUNNING)
        # 1. Recompute the ACTIVE assessed case (#993) — never the stale form CF.
        assessment = assessment_fn(request.wind, progress)
        # The production step returns an AssessmentResult (export + full assessment); a
        # fake / pre-#993 step may return a bare export mapping — accept either.
        wind_export: Mapping[str, Any] = (
            assessment.export
            if isinstance(assessment, AssessmentResult)
            else assessment
        )
        assessed = _build_assessed_scenario(request.wind, wind_export)
        # 2. Run the bounded analysis engine over the assessed scenario.
        result_dict = analysis_fn(request, assessed, progress)
        store.update(
            job_id,
            state=JobState.SUCCEEDED,
            result=result_dict,
            progress=JobProgress(
                step=ANALYSIS_TOTAL_STEPS,
                total_steps=ANALYSIS_TOTAL_STEPS,
                message="Complete",
            ),
        )
    except Exception as exc:  # noqa: BLE001 - boundary: record, don't crash worker
        logger.exception("Async analysis job %s failed", job_id)
        store.update(
            job_id,
            state=JobState.FAILED,
            error=(
                f"{type(exc).__name__}: the analysis job failed; "
                "see the server logs for this job id."
            ),
        )
