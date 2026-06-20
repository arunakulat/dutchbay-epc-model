"""FastAPI adapter for v14 tornado sensitivity.

This module is intentionally thin:

- Accepts a JSON payload describing:
    * scenario config path
    * parameter ranges
    * target KPI metric (default: "project_irr")
- Delegates to the canonical engine
  ``analytics.core.sensitivity_runner.run_sensitivity_analysis``.
- Returns a JSON-serialisable list[dict[str, Any]] of tornado rows.

No IRR or cashflow logic lives here; all modelling stays in analytics/finance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.core.sensitivity_runner import run_sensitivity_analysis
from api.pipeline_api import router as pipeline_router

app = FastAPI(title="DutchBay v14 API", version="1.1.0")

# Full-pipeline report endpoint (POST /run-pipeline): KPIs + sculpted debt + AEP.
app.include_router(pipeline_router, tags=["pipeline"])


class SensitivityInput(BaseModel):
    """Request body for single-metric tornado sensitivity."""

    config_path: str
    parameters: List[Dict[str, Any]]
    metric: str = "project_irr"


@app.post("/run-tornado/", response_model=List[Dict[str, Any]])
def run_tornado(payload: SensitivityInput) -> List[Dict[str, Any]]:
    """Run a single-metric tornado sensitivity for a given scenario.

    Parameters
    ----------
    payload:
        Pydantic model wrapping the incoming JSON body.

    Returns
    -------
    list[dict[str, Any]]:
        One tornado row per parameter: ``parameter``, ``metric``,
        ``base_metric``, ``low_case``, ``high_case``, ``impact_abs``.
    """
    # Normalise raw dicts into strongly-typed ParameterRangeConfig objects.
    params: List[ParameterRangeConfig] = [
        ParameterRangeConfig(**p) for p in payload.parameters
    ]

    # Canonical engine: takes the config path, target metric, and explicit
    # parameter ranges, and returns a SensitivitySuite with tornado_results.
    suite = run_sensitivity_analysis(
        payload.config_path,
        metric=payload.metric,
        parameters=params,
    )

    rows: List[Dict[str, Any]] = []
    for tornado in suite.tornado_results:
        shocks = tornado.shock_results or []
        first: Optional[Any] = shocks[0] if shocks else None
        parameter = (
            getattr(first, "variable_name", None)
            or tornado.label
            or tornado.metric_name
        )
        rows.append(
            {
                "parameter": parameter,
                "metric": payload.metric,
                "base_metric": tornado.base_metric,
                "low_case": getattr(first, "low_case", None),
                "high_case": getattr(first, "high_case", None),
                "impact_abs": tornado.impact_abs,
            }
        )
    return rows
