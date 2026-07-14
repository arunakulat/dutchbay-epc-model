"""Unified FastAPI application for the DutchBay EPC model.

Composes the existing surfaces under one app and adds the wizard-facing
``POST /v1/cases`` endpoint. The whole client-data surface is version-pinned under
``/v1`` (#841 contract freeze) so the public contract is stable and future changes
are additive (a breaking change lands as ``/v2``, never a mutation of ``/v1``):

* ``POST /v1/cases``        — run a lender case from a ``WindFarmInputs`` submission
                              (synchronous, frozen-AEP; returns ``CaseResult``).
* ``POST /v1/cases/surface`` — the same run, projected into the wizard result surface
                              (``CaseSurface``: KPI cards + tornado/global-SA charts +
                              capital-risk headline + artifact links) — #844.
* ``POST /v1/cases/report.html`` — the same run, rendered as an HTML report.
* ``POST /v1/cases/report.pdf``  — the same run, rendered as a PDF (optional WeasyPrint).
* ``POST /v1/cases/report.xlsx`` — the same run, emitted as the executive workbook (.xlsx) — #844.
* ``POST /v1/jobs`` + ``/v1/jobs/{id}`` + ``/v1/jobs/{id}/events`` — the async live-ERA5 path.
* ``POST /v1/run-pipeline`` — the lower-level inline-config route (``api.pipeline_api``).
* ``/v1/sensitivity/*``     — the tornado/sensitivity surface (``api.sensitivity_api``).
* ``POST /v1/token``        — exchange credentials for a bearer JWT.
* ``GET /health``           — liveness probe (deliberately UNVERSIONED infra endpoint;
                              self-reports the body-level ``API_CONTRACT_VERSION``).

The endpoint only orchestrates: it validates inputs (Pydantic), maps the form to
a scenario (``WindFarmInputs.to_scenario_config``), and delegates the compute to
the canonical engine via the service seam (``run_finance_case``). No finance
logic here (Dolphin).

Serve with: ``uvicorn app.api.main:app``.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from analytics.aep_provenance import AepProvenanceError
from analytics.aep_reconciliation import AepReconciliationError
from analytics.executive_workbook import emit_executive_workbook_from_pipeline
from analytics.schema_guard import ConfigValidationError
from api.pipeline_api import router as pipeline_router
from api.sensitivity_api import SensitivityInput, SensitivityTornadoRow, run_tornado
from app.api.auth import get_current_subject, login_for_access_token
from app.api.config import SYNC_ROUTE_MAX_CONCURRENCY, SYNC_ROUTE_TIMEOUT_SECONDS
from app.api.jobs_router import router as jobs_router
from app.api.responses import API_CONTRACT_VERSION, CaseResult
from app.api.security import SecurityHeadersMiddleware
from app.api.surface import CaseSurface
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

# Production hardening (#944): stamp security headers on every response and, in the #858
# production posture, take the interactive docs (/docs, /redoc, /openapi.json) offline.
# Added as the outermost middleware so its header injection covers every route — the
# versioned /v1 API, the HTMX wizard, /static, and /health alike — and its production
# docs gate short-circuits before routing. Pure-ASGI (see app.api.security) so it does
# not buffer the streaming SSE job-events response.
app.add_middleware(SecurityHeadersMiddleware)

#: The canonical public URL prefix (#841 contract freeze). Every client-data route is
#: mounted under ``/v1``, so the whole public surface is version-pinned at the URL: a
#: future breaking change lands additively as a ``/v2`` mount rather than mutating
#: ``/v1`` in place. ``/health`` is deliberately left UNVERSIONED (an infra liveness
#: probe, not a client-data contract; it self-reports :data:`API_CONTRACT_VERSION` in
#: its body). The URL prefix pins the *surface*; the body-level ``API_CONTRACT_VERSION``
#: and the pinned ``operation_id``s pin the response *shape* and the SDK method names.
API_V1_PREFIX = "/v1"

# ``public_router`` carries the versioned endpoints defined directly in this module
# (token + the /cases* case runs + the sensitivity tornado). It is mounted once, under
# /v1, alongside the pre-existing routers — one canonical surface, no forked copies to
# drift, and no duplicate OpenAPI operationIds (CASPER: one clear, predictable surface).
public_router = APIRouter()

# Unify the pre-existing surfaces under one app (Sprint 1 roadmap), all under /v1. Every
# compute surface is auth-gated via Depends(get_current_subject); only /health (infra,
# unversioned) and /v1/token are public. The /sensitivity surface is composed here as
# gated routes rather than a mounted sub-app: a mount is an opaque ASGI boundary that does
# NOT inherit the parent's auth dependency, which is how /sensitivity/* was reachable
# anonymously.
app.include_router(
    pipeline_router,
    prefix=API_V1_PREFIX,
    tags=["pipeline"],
    dependencies=[Depends(get_current_subject)],
)
app.include_router(
    jobs_router, prefix=API_V1_PREFIX
)  # async live-ERA5 job path (Sprint 2 PR E)
app.include_router(
    pipeline_router,
    prefix=f"{API_V1_PREFIX}/sensitivity",
    tags=["sensitivity"],
    dependencies=[Depends(get_current_subject)],
)

# Serve the HTMX wizard's static assets (CSS + vendored htmx.min.js) under /static. The
# directory is resolved from this file's location (``app/api/main.py`` → ``app/web/static``)
# so it is independent of the process working directory. This is the wizard UI (#843), a
# server-rendered surface layered on top of the versioned /v1 JSON API; the mount and the
# web router below are purely additive and do not touch any /v1 route or /health.
_WEB_STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_WEB_STATIC_DIR)), name="static")


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe + the public API contract version (#841)."""
    return {"status": "ok", "contract_version": API_CONTRACT_VERSION}


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


@public_router.post("/token", response_model=TokenResponse, tags=["auth"])
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
        run_result=result,
    )


def build_case_surface(inputs: WindFarmInputs) -> CaseSurface:
    """Project a completed run into the wizard result surface (#844, synchronous core).

    Reuses the SAME ``ReportContext`` the HTML/PDF report routes build, so the KPI cards,
    tornado, both global-SA charts, and the capital-risk headline the client shows are the
    identical numbers the PDF renders. Pure re-shaping (Dolphin) — no finance recompute — so
    it is KPI-neutral. Kept as a plain synchronous core so it is directly unit-testable; the
    HTTP endpoint wraps it with auth + a wall-clock timeout.
    """
    context = _build_report_context(inputs)
    return CaseSurface.from_report_context(context)


def run_case_workbook(inputs: WindFarmInputs) -> Response:
    """Build the executive workbook (.xlsx) for a lender case (synchronous core).

    Runs the case (mapping an engine-rejected scenario to a graceful 400, mirroring
    ``run_case``) and emits the existing single-scenario Executive Workbook via the canonical
    ``emit_executive_workbook_from_pipeline`` — no workbook logic is added here (Dolphin). The
    emitter is path-based, so the bytes are read from a private temp file that is always
    unlinked. The download filename is sanitised before it is interpolated into the
    ``Content-Disposition`` header. Kept as a plain synchronous core; the HTTP endpoint wraps
    it with auth + a wall-clock timeout.
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
    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="dutchbay_workbook_")
    os.close(fd)
    try:
        emit_executive_workbook_from_pipeline(result, path)
        with open(path, "rb") as fh:
            xlsx_bytes = fh.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)
    safe_variant = _sanitise_filename_component(inputs.scenario_variant)
    filename = f"dutchbay_{safe_variant}_workbook.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
@public_router.post(
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


@public_router.post(
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


@public_router.post(
    "/cases/report.pdf",
    tags=["cases"],
    operation_id="run_case_report_pdf",
)
async def run_case_report_pdf_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> Response:
    """Run a lender case and return a PDF report (auth-gated; timeout-bounded)."""
    return await _run_with_timeout(run_case_report_pdf, inputs)


@public_router.post(
    "/cases/surface",
    response_model=CaseSurface,
    tags=["cases"],
    operation_id="run_case_surface",
)
async def run_case_surface_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> CaseSurface:
    """Run a lender case and return the wizard result surface (#844; auth-gated, bounded).

    The typed, chart-ready contract a future frontend (#843) consumes: KPI cards, the
    tornado + both global-SA charts, the #657 capital-risk headline, and the artifact
    download links — projected from the same report context the PDF renders.
    """
    return await _run_with_timeout(build_case_surface, inputs)


@public_router.post(
    "/cases/report.xlsx",
    tags=["cases"],
    operation_id="run_case_workbook",
)
async def run_case_workbook_endpoint(
    inputs: WindFarmInputs, subject: str = Depends(get_current_subject)
) -> Response:
    """Run a lender case and return the executive workbook (.xlsx; auth-gated, bounded)."""
    return await _run_with_timeout(run_case_workbook, inputs)


@public_router.post(
    "/sensitivity/run-tornado/",
    response_model=list[SensitivityTornadoRow],
    tags=["sensitivity"],
    operation_id="run_sensitivity_tornado",
)
async def run_sensitivity_tornado_endpoint(
    payload: SensitivityInput, subject: str = Depends(get_current_subject)
) -> list[SensitivityTornadoRow]:
    """Single-metric tornado sensitivity (auth-gated; sync-route timeout-bounded).

    Delegates to the thin ``api.sensitivity_api.run_tornado`` adapter, wrapped in
    the same wall-clock timeout + concurrency limiter as ``/cases`` so a heavy
    multi-evaluation sweep cannot run unbounded. Previously this route lived on a
    mounted sub-app that bypassed BOTH auth and that limiter.
    """
    return await _run_with_timeout(run_tornado, payload)


# Mount the module-defined public endpoints under the canonical /v1 prefix (#841).
# Registered AFTER the handlers are defined so every route above is on public_router
# before it is attached to the app.
app.include_router(public_router, prefix=API_V1_PREFIX)

# Mount the HTMX wizard UI (#843) at the application root (no /v1 prefix — the versioned
# data API owns /v1; this is the human-facing surface). The import is deliberately placed
# HERE, at the bottom of the module: ``app.web.routes`` reuses the case-run functions defined
# above (``build_case_surface`` / ``run_case_report_*`` / ``run_case_workbook``), so importing
# it only once those names are bound avoids a circular import. Purely additive — it registers
# new root routes and changes no existing /v1 route or /health.
from app.web.routes import router as web_router  # noqa: E402 — see the comment above.

app.include_router(web_router)
