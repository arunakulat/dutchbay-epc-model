"""The async job orchestration: ERA5 assessment → finance, with progress.

``run_wind_job`` drives the slow chain and records every transition on the
:class:`~app.jobs.store.JobStore`. It is framework-agnostic and fully testable: the
slow, credential-bound ERA5 step is injected as ``assessment_fn`` so tests pass a
fake. The production default (:func:`default_assessment`) reuses the canonical
``WindPipeline`` and the ``run_integrated_case`` service seam — no duplicate
finance or wind logic (Dolphin).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from app.api.responses import CaseResult
from app.jobs.models import JobProgress, JobState, WindJobRequest
from app.jobs.store import JobStore
from app.services.pipeline_service import run_integrated_case

#: Coarse step budget for progress reporting (assessment 1–3, finance 4).
TOTAL_STEPS = 4

#: ``(step, message) -> None`` progress sink handed to the assessment function.
ProgressFn = Callable[[int, str], None]

#: ``(request, progress) -> wind_export_dict`` — the slow ERA5 step, injectable.
AssessmentFn = Callable[[WindJobRequest, ProgressFn], Mapping[str, Any]]


def default_assessment(
    request: WindJobRequest, progress: ProgressFn
) -> Mapping[str, Any]:  # pragma: no cover - needs Copernicus creds + network
    """Run the real ERA5 wind assessment and export the cashflow contract.

    Reuses the canonical ``WindPipeline`` (Dolphin). Imported lazily so importing
    this module never requires the optional ``[wind]`` toolchain. Not exercised in
    CI (needs Copernicus credentials and network).
    """
    from wind_resource.wind_pipeline import WindPipeline

    progress(1, "Initializing wind pipeline + ERA5 fetch")
    pipeline = WindPipeline(
        location=request.site_location(),
        hub_height=request.hub_height_m,
        turbine_model=request.turbine_model,
        num_turbines=request.num_turbines,
    )
    progress(2, "Running ERA5 → Weibull → AEP assessment")
    pipeline.run_complete_assessment(
        start_date=request.start_date, end_date=request.end_date
    )
    progress(3, "Exporting wind metrics for finance")
    return pipeline.export_for_cashflow_model(scenario=request.p_level)


def run_wind_job(
    job_id: str,
    request: WindJobRequest,
    store: JobStore,
    *,
    assessment_fn: AssessmentFn = default_assessment,
) -> None:
    """Execute one async job to completion, recording progress and outcome.

    Any exception is captured onto the job record as ``state=failed`` (the error
    is surfaced to the client via the job, never swallowed) rather than crashing
    the worker — the correct fail-loud behaviour at a task boundary.

    Args:
        job_id: The id of an already-created (queued) job record.
        request: The validated async submission.
        store: Where lifecycle transitions are recorded.
        assessment_fn: The slow ERA5 step; defaults to the real pipeline.
    """

    def progress(step: int, message: str) -> None:
        store.update(
            job_id,
            progress=JobProgress(step=step, total_steps=TOTAL_STEPS, message=message),
        )

    try:
        store.update(job_id, state=JobState.RUNNING)
        wind_export = assessment_fn(request, progress)
        progress(TOTAL_STEPS - 1, "Running finance pipeline on the wind export")
        scenario = request.to_finance_scenario()
        result = run_integrated_case(
            scenario, wind_export, scenario_name=request.p_level
        )
        case = CaseResult.from_pipeline_result(
            result, scenario_variant=request.inputs.scenario_variant
        )
        store.update(
            job_id,
            state=JobState.SUCCEEDED,
            result=case.model_dump(),
            progress=JobProgress(
                step=TOTAL_STEPS, total_steps=TOTAL_STEPS, message="Complete"
            ),
        )
    except Exception as exc:  # noqa: BLE001 - boundary: record, don't crash worker
        store.update(job_id, state=JobState.FAILED, error=f"{type(exc).__name__}: {exc}")


def new_queued_record(job_id: str, *, now: str) -> Dict[str, Any]:
    """Build the kwargs for a freshly-queued :class:`JobRecord` (CCCDIR helper)."""
    return {
        "job_id": job_id,
        "state": JobState.QUEUED,
        "progress": JobProgress(step=0, total_steps=TOTAL_STEPS, message="Queued"),
        "created_at": now,
        "updated_at": now,
    }
