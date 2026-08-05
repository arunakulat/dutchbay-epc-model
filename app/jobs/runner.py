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
from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    Mapping,
    Optional,
    Union,
)

from analytics.resource_contracts import ResourceAssessment
from app.api.responses import CaseResult, WindAssessment
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


@dataclass(frozen=True)
class AssessmentResult:
    """What the production assessment step returns: the frozen cashflow ``export`` the
    finance seam consumes, plus the OPTIONAL full ``wind_assessment`` (all P50/P75/P90 +
    provenance + site + data period + wind stats) surfaced on the API result (#993). A
    fake or legacy step may still return a bare export mapping; ``run_wind_job`` accepts
    either shape.
    """

    export: Mapping[str, Any]
    wind_assessment: Optional[WindAssessment] = None
    #: The frozen, VALIDATED resource basis (#996 D4-wire): P50/P75/P90 AEP + CF with the
    #: AEP=capacity*8760*CF identity and P90<=P75<=P50 monotonicity checked on construction.
    #: The construction (in default_assessment) IS the guard; the object is carried here as
    #: forward-wiring for the downside-debt slice (D5), which will read its P90/P50 ratio
    #: from it — no consumer reads it yet.
    resource_assessment: Optional[ResourceAssessment] = None


#: ``(request, progress) -> AssessmentResult | export_mapping`` — the slow resource step,
#: injectable. The production step returns an :class:`AssessmentResult`; a bare export
#: mapping (the pre-#993 shape) is still accepted for the export-only path.
AssessmentFn = Callable[
    [WindJobRequest, ProgressFn], Union[Mapping[str, Any], AssessmentResult]
]


#: Below this drift (percent) the submitted and derived physical values are effectively
#: equal, so the reconciliation note marks the field NOT superseded. Mirrors the wind
#: cashflow adapter's 0.5% drift tolerance — the very guard the async path used to trip
#: (#974); a difference the adapter would have rejected is one worth surfacing.
_RECON_TOLERANCE_PCT = 0.5


def _input_reconciliation(
    submitted_capacity_mw: float,
    submitted_capacity_factor: float,
    export: Mapping[str, Any],
    *,
    tolerance_pct: float = _RECON_TOLERANCE_PCT,
) -> Optional[Dict[str, Any]]:
    """Reconcile the client's submitted capacity / capacity factor against the values
    the screening assessment actually used (#974).

    On the async wind path the finance inputs are DERIVED — capacity from
    ``num_turbines × turbine nameplate`` and the capacity factor from the selected
    ``p_level`` export — and the screening seam (#997) overwrites whatever the client
    submitted. This builds a structured note (submitted vs used, per-field drift, and a
    ``superseded`` flag when the drift exceeds ``tolerance_pct``) so the overwrite is
    SURFACED in the assessment provenance rather than applied silently.

    Args:
        submitted_capacity_mw: The client-supplied nameplate capacity (MW).
        submitted_capacity_factor: The client-supplied capacity factor (decimal).
        export: The wind cashflow export; must carry ``project_capacity_mw`` and
            ``capacity_factor_percent`` (the derived physical basis) for a note to be
            built.
        tolerance_pct: Drift below which a field is considered unchanged (not
            superseded). Defaults to the adapter's 0.5% guard.

    Returns:
        The reconciliation note, or ``None`` when the export lacks the derived physical
        keys (a bare / legacy export) so nothing can be reconciled.
    """
    used_capacity = export.get("project_capacity_mw")
    used_cf_pct = export.get("capacity_factor_percent")
    if not isinstance(used_capacity, (int, float)) or not isinstance(
        used_cf_pct, (int, float)
    ):
        return None
    used_cf = float(used_cf_pct) / 100.0

    def _field(submitted: float, used: float) -> Dict[str, Any]:
        drift_pct = (
            abs(used - submitted) / abs(submitted) * 100.0 if submitted else None
        )
        return {
            "submitted": float(submitted),
            "used": float(used),
            "drift_pct": drift_pct,
            "superseded": drift_pct is not None and drift_pct > tolerance_pct,
        }

    return {
        "capacity_mw": _field(float(submitted_capacity_mw), float(used_capacity)),
        "capacity_factor": _field(float(submitted_capacity_factor), used_cf),
        "basis": (
            "screening-grade physical assessment: capacity_mw = num_turbines × turbine "
            "nameplate, capacity_factor from the selected p_level export. The submitted "
            "capacity / capacity_factor are advisory on the async wind path and were "
            "overwritten by the live assessment (#974/#997)."
        ),
    }


def _build_wind_assessment(
    full_results: Mapping[str, Any], selected_scenario: str
) -> WindAssessment:
    """Project a ``WindPipeline.run_complete_assessment`` result into a
    :class:`~app.api.responses.WindAssessment` (#993).

    Reads the documented result paths (``metadata`` / ``wind_data`` /
    ``statistical_analysis`` / ``energy_production.net_aep``) and marks the resource
    SCREENING-grade — a live single-cell / analytic-Weibull run is never bankable (#961).
    Missing keys degrade to omitted/empty rather than raising, so a partial assessment
    still yields a usable block.
    """
    fr: Mapping[str, Any] = full_results if isinstance(full_results, Mapping) else {}
    meta = fr.get("metadata") or {}
    net = (fr.get("energy_production") or {}).get("net_aep") or {}
    stats = fr.get("statistical_analysis") or {}
    wind_data = fr.get("wind_data") or {}
    weibull = stats.get("weibull") or {}

    def _gwh(mwh: Any) -> Optional[float]:
        return float(mwh) / 1000.0 if isinstance(mwh, (int, float)) else None

    p_levels_gwh = {
        lvl.upper(): g
        for lvl in ("p50", "p75", "p90")
        if (g := _gwh(net.get(f"net_aep_{lvl}_mwh"))) is not None
    }
    net_cf = {
        lvl.upper(): float(cf)
        for lvl in ("p50", "p75", "p90")
        if isinstance((cf := net.get(f"capacity_factor_net_{lvl}")), (int, float))
    }
    provenance = {
        "engine_version": meta.get("version"),
        # a live single-cell ERA5 / analytic-Weibull run is NOT bankable (#961)
        "grade": "screening",
        "pvalue_method": net.get("pvalue_method"),
        "uncertainty_sigma_1yr_pct": net.get("uncertainty_sigma_1yr_pct"),
        "selected_p_level": selected_scenario,
    }
    wind_stats = {
        k: float(v)
        for k, v in (
            ("mean_ws", wind_data.get("mean_ws")),
            ("weibull_a", weibull.get("scale_c")),
            ("weibull_k", weibull.get("shape_k")),
        )
        if isinstance(v, (int, float))
    }
    return WindAssessment(
        p_levels_gwh=p_levels_gwh,
        net_capacity_factor=net_cf,
        provenance={k: v for k, v in provenance.items() if v is not None},
        site=dict(meta.get("location") or {}),
        data_period=dict(meta.get("data_period") or {}),
        wind_stats=wind_stats,
    )


#: Result keys a strict ResourceAssessment needs; absence => degrade to None.
_RESOURCE_NET_KEYS = (
    "net_aep_p50_mwh",
    "net_aep_p75_mwh",
    "net_aep_p90_mwh",
    "capacity_factor_net_p50",
    "capacity_factor_net_p75",
    "capacity_factor_net_p90",
)


def _build_resource_assessment(
    full_results: Mapping[str, Any], selected_scenario: str
) -> Optional[ResourceAssessment]:
    """Project + VALIDATE a ``run_complete_assessment`` result into a frozen
    :class:`~analytics.resource_contracts.ResourceAssessment` (#996 D4-wire).

    Lenient on ABSENCE, strict on INCONSISTENCY. Like :func:`_build_wind_assessment` it
    returns ``None`` when the assessment block is missing/partial (a bare export or a
    fake step), so it never crashes a job over a shape it cannot project. But when the
    P50/P75/P90 net-AEP + capacity-factor block and the turbine configuration ARE present
    — which every real ``run_complete_assessment`` produces — construction fails loud
    (``ResourceAssessmentError``) if the ``AEP = capacity x 8760 x CF`` identity or the
    ``P90 <= P75 <= P50`` monotonicity is violated: the #996 "AEP validated for the active
    selected P-level" / monotonicity guard. Screening-grade (#961): a live single-cell /
    analytic-Weibull run is never bankable.
    """
    fr: Mapping[str, Any] = full_results if isinstance(full_results, Mapping) else {}
    net = (fr.get("energy_production") or {}).get("net_aep") or {}
    config = (fr.get("metadata") or {}).get("configuration") or {}
    if not all(k in net for k in _RESOURCE_NET_KEYS):
        return None
    if "total_capacity_mw" not in config or "num_turbines" not in config:
        return None
    return ResourceAssessment.from_assessment(
        full_results, selected_scenario, report_grade="screening"
    )


def apply_active_resource_basis(
    scenario: Dict[str, Any],
    resource_assessment: Optional[ResourceAssessment],
) -> Dict[str, Any]:
    """Inject the freshly-ASSESSED P50/P90 net AEP into a screening scenario (#996 D5).

    On the async location-assessment path the finance scenario is seeded from a lender-case
    base whose ``expected_results.net_aep_p50/p90_gwh`` are the FROZEN bankable numbers, not
    this run's assessment. When the scenario binds the downside case
    (``Financing_Terms.bind_downside``), ``finance.debt_v14._resolve_downside_ratio`` sizes
    the P90 gearing off that frozen P90/P50 ratio — so a location assessment would be sized
    against an unrelated committed resource. This replaces just those two keys with the
    ACTIVE assessment's values so downside debt uses the live P90/P50 ratio.

    Injection, not deletion: every other ``expected_results`` key is preserved (the known
    regression is stripping the block wholesale). Returns ``scenario`` unchanged when there
    is no assessment. Byte-neutral for scenarios that do NOT bind downside — on the screening
    path the ONLY runtime reader of these keys is ``_resolve_downside_ratio`` under
    ``bind_downside`` (the bankable reconciliation is skipped for screening runs), so a
    non-binding case (e.g. the canonical wind-only lender base) is unaffected.

    Scope note: no async-runnable variant currently sets ``Financing_Terms.bind_downside``
    (the canonical lender base is bind_downside-absent by design), so today this is
    forward-correct wiring — it changes debt sizing ONLY for a location assessment of a
    downside-binding case, which the API does not yet expose. The effect on the actual
    gearing solve (not just the ratio helper) is proven by
    ``test_injected_active_basis_changes_solved_downside_gearing``.
    """
    if resource_assessment is None:
        return scenario
    updated = dict(scenario)
    expected = dict(updated.get("expected_results") or {})
    expected["net_aep_p50_gwh"] = resource_assessment.net_aep_p50_gwh
    expected["net_aep_p90_gwh"] = resource_assessment.net_aep_p90_gwh
    updated["expected_results"] = expected
    return updated


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
) -> AssessmentResult:  # pragma: no cover - needs Copernicus creds + network
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
        full_results = pipeline.run_complete_assessment(
            start_date=request.start_date,
            end_date=request.end_date,
            hub_height_series=series,
        )
        progress(3, "Exporting wind metrics for finance")
        return AssessmentResult(
            export=pipeline.export_for_cashflow_model(scenario=request.p_level),
            wind_assessment=_build_wind_assessment(full_results, request.p_level),
            resource_assessment=_build_resource_assessment(
                full_results, request.p_level
            ),
        )


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
        assessment = assessment_fn(request, progress)
        # The production step returns an AssessmentResult (export + full wind assessment);
        # a fake / pre-#993 step may return a bare export mapping — accept either.
        resource_assessment = None
        if isinstance(assessment, AssessmentResult):
            wind_export: Mapping[str, Any] = assessment.export
            wind_assessment = assessment.wind_assessment
            resource_assessment = assessment.resource_assessment
        else:
            wind_export = assessment
            wind_assessment = None
        # #974: the async path DERIVES the finance capacity / capacity factor from the
        # turbine layout + selected p_level, and the screening seam (#997) overwrites the
        # client's submitted values. Record that supersession in the assessment
        # provenance so the overwrite is SURFACED to the client, never silent. (No-op for
        # a bare/legacy export with no wind_assessment or no physical keys.)
        if wind_assessment is not None:
            reconciliation = _input_reconciliation(
                request.inputs.capacity_mw, request.inputs.capacity_factor, wind_export
            )
            if reconciliation is not None:
                wind_assessment = wind_assessment.model_copy(
                    update={
                        "provenance": {
                            **wind_assessment.provenance,
                            "input_reconciliation": reconciliation,
                        }
                    }
                )
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
        # #996 D5: downside debt sizing must use THIS assessment's P90/P50, not the frozen
        # lender-case base — inject the active net AEP (no-op unless the case binds downside).
        scenario = apply_active_resource_basis(scenario, resource_assessment)
        result = run_integrated_case(
            scenario, wind_export, scenario_name=request.p_level
        )
        case = CaseResult.from_pipeline_result(
            result,
            scenario_variant=request.inputs.scenario_variant,
            wind_assessment=wind_assessment,
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


def new_queued_record(
    job_id: str, *, now: str, owner: str, total_steps: int = TOTAL_STEPS
) -> Dict[str, Any]:
    """Build the kwargs for a freshly-queued :class:`JobRecord` (CCCDIR helper).

    Args:
        job_id: The id for the new record.
        now: The ISO timestamp to stamp ``created_at``/``updated_at`` with.
        owner: The authenticated subject the job is bound to (per-client isolation).
        total_steps: The step budget advertised on the queued progress marker.
            Defaults to the wind-job budget (:data:`TOTAL_STEPS`); the analysis job
            passes its own so the queued record reflects the right budget before the
            runner's first ``progress()`` call overwrites it.
    """
    return {
        "job_id": job_id,
        "owner": owner,
        "state": JobState.QUEUED,
        "progress": JobProgress(step=0, total_steps=total_steps, message="Queued"),
        "created_at": now,
        "updated_at": now,
    }
