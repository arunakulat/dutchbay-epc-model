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

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from analytics.schema_guard import ConfigValidationError
from api.pipeline_api import router as pipeline_router
from api.sensitivity_api import app as sensitivity_app
from app.api.jobs_router import router as jobs_router
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_model import ReportContext, build_report_context
from app.reports.renderer import (
    ReportDependencyError,
    render_report_html,
    render_report_pdf,
)
from app.services.pipeline_service import run_finance_case

app = FastAPI(
    title="DutchBay EPC Model API",
    version="1.0.0",
    description="Lender-grade wind-farm project-finance, served as a web API.",
)

# Unify the pre-existing surfaces under one app (Sprint 1 roadmap).
app.include_router(pipeline_router, tags=["pipeline"])
app.include_router(jobs_router)  # async live-ERA5 job path (Sprint 2 PR E)
app.mount("/sensitivity", sensitivity_app)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/cases", response_model=CaseResult, tags=["cases"])
def run_case(inputs: WindFarmInputs) -> CaseResult:
    """Run a lender case from a wizard submission (synchronous, frozen-AEP).

    The request body is validated as ``WindFarmInputs`` by FastAPI (a 422 is
    returned automatically on malformed input). A scenario that the engine
    rejects in strict validation surfaces as a 400 (fail-loud, but graceful).
    """
    try:
        scenario = inputs.to_scenario_config()
        result = run_finance_case(scenario)
    except ConfigValidationError as exc:
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
    except ConfigValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid scenario: {exc}") from exc
    case_result = CaseResult.from_pipeline_result(
        result, scenario_variant=inputs.scenario_variant
    )
    return build_report_context(
        case_result,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        inputs=inputs,
    )


@app.post("/cases/report.html", response_class=HTMLResponse, tags=["cases"])
def run_case_report_html(inputs: WindFarmInputs) -> HTMLResponse:
    """Run a lender case and return it rendered as an HTML report."""
    context = _build_report_context(inputs)
    return HTMLResponse(content=render_report_html(context))


@app.post("/cases/report.pdf", tags=["cases"])
def run_case_report_pdf(inputs: WindFarmInputs) -> Response:
    """Run a lender case and return it rendered as a PDF.

    Returns a 503 when the optional WeasyPrint backend is not installed
    (``pip install -e '.[report]'``); the HTML route is unaffected.
    """
    context = _build_report_context(inputs)
    try:
        pdf_bytes = render_report_pdf(context)
    except ReportDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = f"dutchbay_{context.scenario_variant}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
