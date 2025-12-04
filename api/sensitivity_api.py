"""FastAPI adapter for v14 tornado sensitivity.

This module is intentionally thin:

- Accepts a JSON payload describing:
    * scenario config path
    * parameter ranges
    * target KPI metric (default: "project_irr")
- Builds a `SensitivityRequest` from `analytics.sensitivity_v14`.
- Delegates the work to the v14 sensitivity coordinator.
- Returns a JSON-serialisable list[dict[str, Any]].

No IRR or cashflow logic lives here; all modelling stays in analytics/finance.
"""

from __future__ import annotations

from typing import Any, Dict, Hashable, List

from fastapi import FastAPI
from pydantic import BaseModel

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity_export import tornado_suite_to_dataframe
from analytics.sensitivity_v14 import (
    SensitivityRequest,
)
from analytics.sensitivity_v14 import (
    run as run_sensitivity,  # type: ignore[attr-defined]
)

app = FastAPI(title="DutchBay v14 Sensitivity API", version="1.0.0")


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
        Tornado rows as a list of plain dicts, ready for JSON encoding.
        Column names and semantics are defined by the analytics layer
        (see `tornado_suite_to_dataframe`).
    """
    # Normalise raw dicts into strongly-typed ParameterRangeConfig objects
    params: List[ParameterRangeConfig] = [
        ParameterRangeConfig(**p) for p in payload.parameters
    ]

    request = SensitivityRequest(
        base_config_path=payload.config_path,
        parameters=params,
        metric=payload.metric,
    )

    suite = run_sensitivity(request)
    df = tornado_suite_to_dataframe(suite)

    # Pandas returns list[dict[Hashable, Any]]; normalise keys to str for JSON contract.
    rows: List[Dict[Hashable, Any]] = df.to_dict(orient="records")
    return [{str(k): v for k, v in row.items()} for row in rows]
