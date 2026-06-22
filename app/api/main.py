"""Unified FastAPI application for the DutchBay EPC model.

Composes the existing surfaces under one app and adds the wizard-facing
``POST /cases`` endpoint:

* ``POST /cases``        — run a lender case from a ``WindFarmInputs`` submission
                           (synchronous, frozen-AEP; returns ``CaseResult``).
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

from fastapi import FastAPI, HTTPException

from analytics.schema_guard import ConfigValidationError
from api.pipeline_api import router as pipeline_router
from api.sensitivity_api import app as sensitivity_app
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.services.pipeline_service import run_finance_case

app = FastAPI(
    title="DutchBay EPC Model API",
    version="1.0.0",
    description="Lender-grade wind-farm project-finance, served as a web API.",
)

# Unify the pre-existing surfaces under one app (Sprint 1 roadmap).
app.include_router(pipeline_router, tags=["pipeline"])
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
