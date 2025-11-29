"""
api/sensitivity_api.py

Minimal FastAPI REST endpoint for analytics.sensitivity tornado analysis.
Accepts JSON POST with scenario and driver parameters, returns tornado DataFrame in JSON.
"""

from fastapi import FastAPI
from pydantic import BaseModel

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.sensitivity import (
    SensitivityRequest,
    run_tornado_sensitivity,
    tornado_suite_to_dataframe,
)

app = FastAPI()


class SensitivityInput(BaseModel):
    config_path: str
    parameters: list[dict]
    metric: str = "project_irr"


@app.post("/run-tornado/")
def run_tornado(input: SensitivityInput):
    params = [ParameterRangeConfig(**p) for p in input.parameters]
    req = SensitivityRequest(input.config_path, params, metric=input.metric)
    suite = run_tornado_sensitivity(req)
    df = tornado_suite_to_dataframe(suite)
    return df.to_dict(orient="records")
