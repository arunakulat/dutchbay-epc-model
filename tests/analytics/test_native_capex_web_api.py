"""Native CAPEX over the web API (#1629 follow-ups from the #1645 review).

The equivalent USD and LKR twins come from the native-CAPEX override tests, so both
files exercise the same committed public inputs.
"""

import copy

import pytest

from analytics.evaluation_v14 import evaluated_scenario_config
from tests.analytics.test_native_capex_overrides import cases


def test_web_api_manifest_carries_native_provenance() -> None:
    """/run-pipeline returns the native_capex block with schema 1.1 (DOM-1645-R4-01)."""
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    usd, native = cases()
    left = run_pipeline(RunPipelineRequest(config=copy.deepcopy(native)))
    right = run_pipeline(RunPipelineRequest(config=copy.deepcopy(usd)))
    applied = evaluated_scenario_config(native)["capex"]["native_input_applied"]
    assert left.manifest.manifest_schema_version == "1.1"
    assert left.manifest.native_capex == applied
    assert right.manifest.manifest_schema_version == "1.0"
    assert right.manifest.native_capex is None
    # The pre-check does not change what the engine evaluates.
    assert left.kpis == right.kpis
    assert left.debt == right.debt


def test_web_api_fx_override_on_native_gives_the_actionable_422() -> None:
    """An FX spot override on native CAPEX names the conflict (ASSURANCE-1645-R11)."""
    from fastapi import HTTPException

    from api.pipeline_api import RunPipelineRequest, run_pipeline

    usd, native = cases()
    rate = native["capex"]["input"]["conversion"]["rate_lkr_per_usd"]
    request = RunPipelineRequest(
        config=native, overrides={"fx.start_lkr_per_usd": rate + 1.0}
    )
    with pytest.raises(HTTPException) as caught:
        run_pipeline(request)
    assert caught.value.status_code == 422
    assert "conversion rate must equal fx.start_lkr_per_usd" in str(caught.value.detail)
    assert "see the server logs" not in str(caught.value.detail)
    # The same override on the USD twin still runs.
    run_pipeline(
        RunPipelineRequest(config=usd, overrides={"fx.start_lkr_per_usd": rate + 1.0})
    )
