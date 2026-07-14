"""FastAPI adapter for v14 tornado sensitivity.

This module is intentionally thin:

- Accepts a JSON payload describing:
    * scenario config path
    * parameter ranges
    * target KPI metric (default: "project_irr")
- Delegates to the canonical engine
  ``analytics.core.sensitivity_runner.run_sensitivity_analysis``.
- Returns a typed ``list[SensitivityTornadoRow]`` (the public tornado contract, #841).

No IRR or cashflow logic lives here; all modelling stays in analytics/finance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.core.sensitivity_runner import run_sensitivity_analysis
from api.path_safety import UnsafePathError, confined_path
from api.pipeline_api import router as pipeline_router

app = FastAPI(title="DutchBay v14 API", version="1.1.0")

# Full-pipeline report endpoint (POST /run-pipeline): KPIs + sculpted debt + AEP.
app.include_router(pipeline_router, tags=["pipeline"])


class SensitivityInput(BaseModel):
    """Request body for single-metric tornado sensitivity."""

    config_path: str
    parameters: List[Dict[str, Any]]
    metric: str = "project_irr"


class SensitivityTornadoRow(BaseModel):
    """One tornado row of the public sensitivity response (#841 contract freeze).

    Firms up the client-facing shape from an untyped ``dict[str, Any]`` to a pinned
    Pydantic model: the wizard (and a later iOS client) codes against these exact
    field names/types. ``base_metric``/``low_case``/``high_case`` are ``Optional`` —
    the engine can legitimately yield ``None`` for a shock it could not evaluate — so
    the optionality is part of the contract, not papered over.
    """

    parameter: str = Field(..., description="Perturbed variable name.")
    metric: str = Field(..., description="Target KPI (e.g. 'project_irr').")
    base_metric: Optional[float] = Field(
        default=None, description="KPI value at the base case."
    )
    low_case: Optional[float] = Field(
        default=None, description="KPI value at the low shock."
    )
    high_case: Optional[float] = Field(
        default=None, description="KPI value at the high shock."
    )
    impact_abs: Optional[float] = Field(
        default=None, description="Absolute KPI swing across the shock range."
    )


@app.post("/run-tornado/", response_model=List[SensitivityTornadoRow])
def run_tornado(payload: SensitivityInput) -> List[SensitivityTornadoRow]:
    """Run a single-metric tornado sensitivity for a given scenario.

    Parameters
    ----------
    payload:
        Pydantic model wrapping the incoming JSON body.

    Returns
    -------
    list[SensitivityTornadoRow]:
        One typed tornado row per parameter: ``parameter``, ``metric``,
        ``base_metric``, ``low_case``, ``high_case``, ``impact_abs`` (#841 contract).
    """
    # Confine the caller-supplied scenario path to the allowed roots before the
    # engine opens it (path-traversal guard); reject out-of-bounds paths loudly.
    try:
        safe_path = confined_path(payload.config_path, must_exist=True)
    except UnsafePathError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid config_path: {exc}"
        ) from exc

    # Normalise raw dicts into strongly-typed ParameterRangeConfig objects.
    params: List[ParameterRangeConfig] = [
        ParameterRangeConfig(**p) for p in payload.parameters
    ]

    # Canonical engine: takes the config path, target metric, and explicit
    # parameter ranges, and returns a SensitivitySuite with tornado_results.
    suite = run_sensitivity_analysis(
        str(safe_path),
        metric=payload.metric,
        parameters=params,
    )

    rows: List[SensitivityTornadoRow] = []
    for tornado in suite.tornado_results:
        shocks = tornado.shock_results or []
        first: Optional[Any] = shocks[0] if shocks else None
        parameter = (
            getattr(first, "variable_name", None)
            or tornado.label
            or tornado.metric_name
        )
        rows.append(
            SensitivityTornadoRow(
                parameter=parameter,
                metric=payload.metric,
                base_metric=tornado.base_metric,
                low_case=getattr(first, "low_case", None),
                high_case=getattr(first, "high_case", None),
                impact_abs=tornado.impact_abs,
            )
        )
    return rows
