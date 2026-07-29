"""The async job orchestration: ERA5 assessment → finance, with progress.

``run_wind_job`` drives the slow chain and records every transition on the
:class:`~app.jobs.store.JobStore`. It is framework-agnostic and fully testable: the
slow, credential-bound ERA5 step is injected as ``assessment_fn`` so tests pass a
fake. The production default (:func:`default_assessment`) reuses the canonical
``WindPipeline`` and the ``run_integrated_case`` service seam — no duplicate
finance or wind logic (Dolphin).
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, Mapping

from app.api.responses import CaseResult
from app.jobs.models import JobProgress, JobState, WindJobRequest
from app.jobs.store import JobStore
from app.services.pipeline_service import run_integrated_case

if TYPE_CHECKING:  # pragma: no cover - typing only; pandas is a heavy, lazy import
    import pandas as pd

logger = logging.getLogger(__name__)

#: Coarse step budget for progress reporting (assessment 1–3, finance 4).
TOTAL_STEPS = 4


@contextmanager
def _ephemeral_workspace() -> Iterator[Path]:
    """Yield a per-job scratch dir writable by the runtime user, deleted on exit.

    ``WindPipeline``'s ``cache_dir`` / ``output_dir`` default to the RELATIVE paths
    ``inputs/wind_data`` / ``outputs/wind_assessment``. Under the non-root container
    user (uid 10001) those resolve to a location the process cannot create, so the
    pipeline's ``mkdir`` raises ``PermissionError`` before any ERA5 fetch (#952).
    Both dirs hold only scratch — the finance-relevant result is the returned
    mapping, and the report/xlsx downloads re-run statelessly — so each job gets its
    own ephemeral workspace under the system temp dir (always writable) and it is
    removed when the job finishes, whether it succeeds or raises.
    """
    workspace = Path(tempfile.mkdtemp(prefix="dutchbay-windjob-"))
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


#: ``(step, message) -> None`` progress sink handed to the assessment function.
ProgressFn = Callable[[int, str], None]

#: ``(request, progress) -> wind_export_dict`` — the slow ERA5 step, injectable.
AssessmentFn = Callable[[WindJobRequest, ProgressFn], Mapping[str, Any]]


def _weibull_screening_series(
    a: float, k: float, hub_height: float, n: int = 8760
) -> "pd.DataFrame":
    """Deterministic hub-height wind series whose empirical distribution IS Weibull(A,k).

    The ``resource_mode='weibull'`` screening path (#993): instead of fetching ERA5, we
    synthesise a series that *is* Weibull(A,k) and feed it through the SAME
    ``WindPipeline.run_complete_assessment(hub_height_series=...)`` seam (Dolphin — no
    duplicated AEP/exceedance math), so the result-dict shape and the whole downstream
    path stay identical to the live ERA5 path.

    Construction is an inverse-CDF quantile LATTICE — NOT random sampling: evaluate the
    Weibull ppf at evenly-spaced midpoint plotting positions ``p_i = (i-0.5)/n`` so
    ``p_i`` stays strictly in ``(0, 1)`` (avoiding ``ppf(0)=0`` and ``ppf(1)=+inf``).
    scipy's ``ppf`` and the downstream MLE fit (``weibull_min.fit(floc=0)``) are both
    deterministic, so the whole path is RNG-free and reproducible; at ``n=8760`` the
    lattice carries no sampling noise and the pipeline's fit recovers ``(A, k)`` to ~4
    significant figures. ``A``/``k`` are the HUB-HEIGHT Weibull (the injected-series
    contract assumes the series is already at hub height). ``scipy.stats.weibull_min``
    is a core dependency (not the optional ``[wind]`` extra).

    Returns exactly the frame the pipeline requires: a ``DatetimeIndex`` named
    ``timestamp`` plus one column ``ws_<hub>m`` of positive floats.
    """
    import numpy as np
    import pandas as pd
    from scipy.stats import weibull_min

    p = (np.arange(1, n + 1) - 0.5) / n  # (0,1) strictly; midpoint plotting positions
    ws = weibull_min.ppf(p, k, loc=0.0, scale=a)  # deterministic Weibull(A,k) lattice
    # 2001 = a non-leap reference year (8760 h). Order is irrelevant to both the MLE fit
    # and the AEP (both are order-independent), so the ascending lattice is fine.
    idx = pd.date_range("2001-01-01", periods=n, freq="h", name="timestamp")
    return pd.DataFrame({f"ws_{int(hub_height)}m": ws}, index=idx)


def default_assessment(
    request: WindJobRequest, progress: ProgressFn
) -> Mapping[str, Any]:  # pragma: no cover - needs Copernicus creds + network
    """Run the real ERA5 wind assessment and export the cashflow contract.

    Fetches the CDS ARCO **single-point TIMESERIES** product
    (``reanalysis-era5-single-levels-timeseries`` via
    ``wind_resource.era5_retrieval``) rather than the legacy gridded fetcher, whose
    hardcoded full-year hourly AREA request CDS rejects as "Your request is too
    large" (#965). The finished hub-height series is injected into the canonical
    ``WindPipeline`` (Dolphin — no duplicate wind/finance logic; Steps 3-5 and the
    ``export_for_cashflow_model`` contract are unchanged). All ``[wind]``-toolchain
    imports are lazy so importing this module never requires the optional extra.
    Not exercised in CI (needs Copernicus credentials and network).

    SCREENING-grade (#961): single-cell ERA5, no on-site mast, MCP unwired — the
    resulting AEP is NOT bankable and must not re-pin any frozen KPI.
    """
    from wind_resource.wind_pipeline import WindPipeline

    with _ephemeral_workspace() as workspace:
        if request.resource_mode == "weibull":
            # Deterministic screening from a supplied hub-height Weibull A/k — NO ERA5
            # fetch, no network (#993). The synthetic series feeds the SAME pipeline as
            # the live path below, so everything downstream is identical.
            # The model_validator guarantees A and k are present for this mode; the
            # assert narrows Optional[float] -> float for the type checker and fails loud
            # if that request-level invariant ever regresses.
            assert request.weibull_a is not None and request.weibull_k is not None
            progress(
                1, "Building deterministic Weibull screening series (no ERA5 fetch)"
            )
            series = _weibull_screening_series(
                request.weibull_a, request.weibull_k, request.hub_height_m
            )
        else:
            from wind_resource.era5_retrieval import (
                ERA5RequestConfig,
                build_hub_height_series,
                retrieve_era5_timeseries,
                validate_coverage,
            )

            cfg = ERA5RequestConfig(
                project_name=request.inputs.site_name,
                latitude=request.site_lat,
                longitude=request.site_lon,
                start_year=int(request.start_date.split("-")[0]),
                end_year=int(request.end_date.split("-")[0]),
                hub_height_m=request.hub_height_m,
                turbine_model=request.turbine_model,
                num_turbines=request.num_turbines,
                output_dir=str(workspace / "era5"),
                # Screening path: the default window (e.g. 2014-12 .. 2025-12) is a partial
                # 2014 plus a latency-truncated recent edge, so a strict leap-aware coverage
                # check would spuriously raise. Warn-only here; do NOT flip the module default.
                strict_coverage=False,
                # #994: a request-supplied shear REPLACES the ERA5-derived per-hour alpha
                # for every hour (None => keep the data-derived alpha, byte-identical).
                shear_exponent_override=request.shear_exponent,
            )

            progress(1, "Fetching ERA5 single-point timeseries from Copernicus CDS")
            nc_path = retrieve_era5_timeseries(cfg)
            series = build_hub_height_series(nc_path, cfg)
            # Observability only (warn-only, non-gating): surface any latency shortfall.
            coverage = validate_coverage(series, cfg)
            logger.info("ERA5 timeseries coverage for job: %s", coverage)

        pipeline = WindPipeline(
            location=request.site_location(),
            hub_height=request.hub_height_m,
            turbine_model=request.turbine_model,
            num_turbines=request.num_turbines,
            cache_dir=str(workspace / "cache"),
            output_dir=str(workspace / "output"),
        )
        progress(2, "Running Weibull → AEP assessment on the hub-height series")
        pipeline.run_complete_assessment(
            start_date=request.start_date,
            end_date=request.end_date,
            hub_height_series=series,
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
        # The async ERA5 location assessment is SCREENING-grade (#961/#996): a fresh
        # single-cell AEP, NOT the frozen bankable P50 of the lender-case base the
        # scenario is seeded from. Declaring run.mode=screening drives the service
        # seam to adopt this assessment's own capacity factor (physical-only, so the
        # form's tariff/FX are untouched) and skip the frozen-bankable reconciliation,
        # so a freshly computed P75 never collides with the unrelated committed P50.
        run_block = dict(scenario.get("run") or {})
        run_block["mode"] = "screening"
        scenario["run"] = run_block
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
        # Log the full exception server-side; expose only the exception class +
        # a generic message to the client (the raw message can leak internal
        # paths/config). The job id ties the two together for support.
        logger.exception("Async job %s failed", job_id)
        store.update(
            job_id,
            state=JobState.FAILED,
            error=(
                f"{type(exc).__name__}: the wind-assessment job failed; "
                "see the server logs for this job id."
            ),
        )


def new_queued_record(job_id: str, *, now: str, owner: str) -> Dict[str, Any]:
    """Build the kwargs for a freshly-queued :class:`JobRecord` (CCCDIR helper).

    Args:
        job_id: The id for the new record.
        now: The ISO timestamp to stamp ``created_at``/``updated_at`` with.
        owner: The authenticated subject the job is bound to (per-client isolation).
    """
    return {
        "job_id": job_id,
        "owner": owner,
        "state": JobState.QUEUED,
        "progress": JobProgress(step=0, total_steps=TOTAL_STEPS, message="Queued"),
        "created_at": now,
        "updated_at": now,
    }
