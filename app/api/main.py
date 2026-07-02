"""Unified FastAPI application for the DutchBay EPC model.

Composes the existing surfaces under one app and adds the wizard-facing
``POST /cases`` endpoint:

* ``POST /cases``        — run a lender case from a ``WindFarmInputs`` submission
                           (synchronous, frozen-AEP; returns ``CaseResult``).
* ``POST /cases/report.html`` — the same run, rendered as an HTML report.
* ``POST /cases/report.pdf``  — the same run, rendered as a PDF (optional WeasyPrint).
* ``POST /jobs`` + ``/jobs/{id}`` + ``/jobs/{id}/events`` — the async live-ERA5 path.
* ``POST /run-pipeline`` — the lower-level inline-config route (``api.pipeline_api``).
* ``/sensitivity/*``     — the tornado/sensitivity app (``api.sensitivity_api``).
* ``GET /health``        — liveness probe.

The endpoint only orchestrates: it validates inputs (Pydantic), maps the form to
a scenario (``WindFarmInputs.to_scenario_config``), and delegates the compute to
the canonical engine via the service seam (``run_finance_case``). No finance
logic here (Dolphin).

Serve with: ``uvicorn app.api.main:app``.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from fastapi import Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, ConfigDict

from analytics.aep_provenance import AepProvenanceError
from analytics.aep_reconciliation import AepReconciliationError
from analytics.schema_guard import ConfigValidationError
from api.pipeline_api import router as pipeline_router
from api.sensitivity_api import SensitivityInput, run_tornado
from app.api.auth import get_current_subject, login_for_access_token
from app.api.config import SYNC_ROUTE_MAX_CONCURRENCY, SYNC_ROUTE_TIMEOUT_SECONDS
from app.api.jobs_router import router as jobs_router
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.renderer import (
    ReportDependencyError,
    render_report_html,
    render_report_pdf,
)
from app.reports.report_model import ReportContext, build_report_context
from app.services.pipeline_service import run_finance_case
from app.services.report_global_sa import (
    compute_report_global_sa,
    compute_report_global_sa_pawn,
)
from app.services.report_tornado import compute_report_tornado

app = FastAPI(
    title="DutchBay EPC Model API",
    version="1.0.0",
    description="Lender-grade wind-farm project-finance, served as a web API.",
)

# Unify the pre-existing surfaces under one app (Sprint 1 roadmap). Every compute
# surface is auth-gated via Depends(get_current_subject); only /health and /token
# are public. The /sensitivity surface is composed here as gated routes rather than
# a mounted sub-app: a mount is an opaque ASGI boundary that does NOT inherit the
# parent's auth dependency, which is how /sensitivity/* was reachable anonymously.
app.include_router(
    pipeline_router, tags=["pipeline"], dependencies=[Depends(get_current_subject)]
)
app.include_router(jobs_router)  # async live-ERA5 job path (Sprint 2 PR E)
app.include_router(
    pipeline_router,
    prefix="/sensitivity",
    tags=["sensitivity"],
    dependencies=[Depends(get_current_subject)],
)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


class TokenRequest(BaseModel):
    """Credentials submitted to ``POST /token`` to obtain a bearer token.

    A JSON body (not an OAuth2 form) so the feature needs no ``python-multipart``
    dependency — keeping the strict requirements lock + security gate intact.
    """

    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class TokenResponse(BaseModel):
    """The bearer token issued by ``POST /token``."""

    access_token: str
    token_type: str = "bearer"


@app.post("/token", response_model=TokenResponse, tags=["auth"])
def issue_token(credentials: TokenRequest) -> TokenResponse:
    """Exchange a username + password for a short-lived bearer JWT.

    Returns a 401 on bad credentials and a 500 if the server's signing secret
    (``DUTCHBAY_JWT_SECRET``) is unconfigured (fail-closed).
    """
    token = login_for_access_token(credentials.username, credentials.password)
    return TokenResponse(access_token=token)


_T = TypeVar("_T")


def _sanitise_filename_component(value: str) -> str:
    """Reduce an arbitrary label to a safe ASCII filename component.

    Keeps only ``[A-Za-z0-9._-]`` (collapsing any run of other characters to a single
    underscore) so the value can be interpolated into a ``Content-Disposition`` header
    without breaking the quoted string or injecting header bytes (CR/LF). Defence in depth:
    the only current caller passes a constrained scenario-variant literal, but the report
    context's variant is a free string at the type level. Returns ``"report"`` when nothing
    printable survives.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "report"


#: Per-loop concurrency limiter for the synchronous ``/cases*`` computes. ``asyncio`` primitives
#: bind to the loop that first awaits them (3.10+), so rather than construct one at import (which
#: would fail a test suite that spins up several loops) it is created lazily and rebound if the
#: running loop changes. Under uvicorn there is one loop per worker, so it is created once and
#: shared across requests — exactly the bound we want.
_compute_semaphore: Optional[asyncio.Semaphore] = None
_compute_semaphore_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_compute_semaphore() -> Optional[asyncio.Semaphore]:
    """Return the concurrency limiter bound to the running loop (``None`` when disabled)."""
    global _compute_semaphore, _compute_semaphore_loop
    if SYNC_ROUTE_MAX_CONCURRENCY <= 0:
        return None
    loop = asyncio.get_running_loop()
    if _compute_semaphore is None or _compute_semaphore_loop is not loop:
        _compute_semaphore = asyncio.Semaphore(SYNC_ROUTE_MAX_CONCURRENCY)
        _compute_semaphore_loop = loop
    return _compute_semaphore


def _discard_task_result(task: "asyncio.Future[Any]") -> None:
    """Retrieve a (possibly orphaned) task's outcome so asyncio does not warn it was unread."""
    if not task.cancelled():
        task.exception()


async def _run_with_timeout(
    func: Callable[..., _T],
    *args: Any,
    timeout: float = SYNC_ROUTE_TIMEOUT_SECONDS,
) -> _T:
    """Run a blocking callable in the threadpool, concurrency-bounded and time-limited.

    Concurrency is capped by ``_compute_semaphore``: when every slot is occupied the call sheds
    load with ``HTTPException(503)`` rather than queueing. The slot is held by a *shielded* task
    for the worker thread's FULL lifetime, so a compute that exceeds ``timeout`` keeps its slot
    until the (uncancellable) thread actually finishes. That is the crucial property — a bare
    ``wait_for(run_in_threadpool(...))`` would release the threadpool's limiter token on the
    timeout cancellation while the thread ran on, letting slow clients accumulate unbounded
    background compute; holding the slot via ``shield`` preserves real backpressure.

    Returns the callable's result, or raises ``HTTPException(504)`` when it does not finish
    within ``timeout`` seconds. The worker thread cannot be force-cancelled (Python threads are
    not killable), so on timeout the computation runs to completion in the background — the
    ceiling bounds the *client* wait, not the work (honest: no silent over-promise). Exceptions
    raised by ``func`` (e.g. the fail-loud ``HTTPException(400)``) propagate unchanged.
    """
    sem = _get_compute_semaphore()
    if sem is not None and sem.locked():
        # Every slot taken (including timed-out computes still running) — shed, don't queue.
        raise HTTPException(
            status_code=503,
            detail="Server is at compute capacity; please retry shortly.",
        )

    async def _guarded() -> _T:
        if sem is None:
            return await run_in_threadpool(func, *args)
        async with sem:
            return await run_in_threadpool(func, *args)

    task: "asyncio.Task[_T]" = asyncio.ensure_future(_guarded())
    task.add_done_callback(_discard_task_result)
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Computation exceeded the {timeout:g}s server time limit.",
        ) from exc


def run_case(inputs: WindFarmInputs) -> CaseResult:
    """Run a lender case from a wizard submission (synchronous, frozen-AEP).

    The request body is validated as ``WindFarmInputs`` by FastAPI (a 422 is
    returned automatically on malformed input). A scenario that the engine
    rejects in strict validation surfaces as a 400 (fail-loud, but graceful).
    Kept as a plain synchronous core so it is directly unit-testable; the HTTP
    endpoint wraps it with auth + a wall-clock timeout.
    """
    try:
        scenario = inputs.to_scenario_config()
        result = run_finance_case(scenario)
    except (
        ConfigValidationError,
        AepReconciliationError,
        AepProvenanceError,
    ) as exc:
        # All three are engine integrity rejections (the AEP guards subclass ValueError
        # but NOT ConfigValidationError): a wizard capacity/CF edit beyond the AEP
        # reconciliation tolerance must surface as a graceful 400, not an uncaught 500.
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {exc}") from exc
    return CaseResult.from_pipeline_result(
        result, scenario_variant=inputs.scenario_variant
    )


def _build_report_context(inputs: WindFarmInputs) -> ReportContext:
    """Run the case and assemble the report context (shared by both report routes).

    Maps an engine-rejected scenario to a 400 (fail-loud, graceful), mirroring
    ``run_case``. The ``generated_at`` timestamp is stamped here (production edge)
    so the pure builder stays deterministic.
    """
    try:
        scenario = inputs.to_scenario_config()
        result = run_finance_case(scenario)
    except (
        ConfigValidationError,
        AepReconciliationError,
        AepProvenanceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {exc}") from exc
    case_result = CaseResult.from_pipeline_result(
        result, scenario_variant=inputs.scenario_variant
    )
    # Pass the resolved scenario + the run's debt_result so the report can render the
    # quantitative lender sections (production P50/P90, sources-and-uses, DSCR profile,
    # readiness/E&S) — not just the KPI summary (RPT-1). The sensitivity tornado (local,
    # RPT-1), the Morris global-SA screening (MC-1) and the PAWN median-KS block (#645,
    # the distribution-based complement) are computed here (each runs a multi-evaluation
    # sweep) and passed in pre-built; all are best-effort (None on failure) so none sinks
    # the core report.
    return build_report_context(
        case_result,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        inputs=inputs,
        scenario_config=scenario,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        tornado=compute_report_tornado(scenario),
        global_sa=compute_report_global_sa(scenario),
        global_sa_pawn=compute_report_global_sa_pawn(scenario),
    )


def run_case_report_html(inputs: WindFarmInputs) -> HTMLResponse:
    """Build the HTML report for a lender case (synchronous core).

    Kept as a plain synchronous core so it is directly unit-testable; the HTTP
    endpoint wraps it with auth + a wall-clock timeout.
    """
    context = _build_report_context(inputs)
    return HTMLResponse(content=render_report_html(context))


def run_case_report_pdf(inputs: WindFarmInputs) -> Response:
    """Build the PDF report for a lender case (synchronous core).

    Returns a 503 when the optional WeasyPrint backend is not installed
    (``pip install -e '.[report]'``); the HTML route is unaffected. The download
    filename is sanitised (``_sanitise_filename_component``) before it is
    interpolated into the ``Content-Disposition`` header. Kept as a plain
    synchronous core; the HTTP endpoint wraps it with auth + a wall-clock timeout.
    """
    context = _build_report_context(inputs)
    try:
        pdf_bytes = render_report_pdf(context)
    except ReportDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    safe_variant = _sanitise_filename_component(context.scenario_variant)
    filename = f"dutchbay_{safe_variant}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# The ``operation_id``s are pinned (not auto-derived from the function name) so the route's
# client-facing contract is decoupled from internal renames — a generated-SDK method name no
# longer churns when a handler is refactored (CASPER: stable, predictable surface).
@app.post(
    "/cases",
    response_model=CaseResult,
    tags=["cases"],
    operation_id="run_case",
)
async def run_case_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> CaseResult:
    """Run a lender case (auth-gated; bounded by the sync-route timeout)."""
    return await _run_with_timeout(run_case, inputs)


@app.post(
    "/cases/report.html",
    response_class=HTMLResponse,
    tags=["cases"],
    operation_id="run_case_report_html",
)
async def run_case_report_html_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> HTMLResponse:
    """Run a lender case and return an HTML report (auth-gated; timeout-bounded)."""
    return await _run_with_timeout(run_case_report_html, inputs)


@app.post(
    "/cases/report.pdf",
    tags=["cases"],
    operation_id="run_case_report_pdf",
)
async def run_case_report_pdf_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> Response:
    """Run a lender case and return a PDF report (auth-gated; timeout-bounded)."""
    return await _run_with_timeout(run_case_report_pdf, inputs)


@app.post(
    "/sensitivity/run-tornado/",
    response_model=list[dict[str, Any]],
    tags=["sensitivity"],
    operation_id="run_sensitivity_tornado",
)
async def run_sensitivity_tornado_endpoint(
    payload: SensitivityInput, subject: str = Depends(get_current_subject)
) -> list[dict[str, Any]]:
    """Single-metric tornado sensitivity (auth-gated; sync-route timeout-bounded).

    Delegates to the thin ``api.sensitivity_api.run_tornado`` adapter, wrapped in
    the same wall-clock timeout + concurrency limiter as ``/cases`` so a heavy
    multi-evaluation sweep cannot run unbounded. Previously this route lived on a
    mounted sub-app that bypassed BOTH auth and that limiter.
    """
    return await _run_with_timeout(run_tornado, payload)
