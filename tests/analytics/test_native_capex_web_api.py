"""Native CAPEX over the web API (#1629 follow-ups from the #1645 review).

The equivalent USD and LKR twins come from the native-CAPEX override tests, so both
files exercise the same committed public inputs. The checks go over HTTP, because the
contract is the JSON a client receives, not the Python response object.
"""

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

import api.path_safety as path_safety
from analytics.evaluation_v14 import evaluated_scenario_config
from api.pipeline_api import router
from finance.native_cost_inputs import normalize_native_capex
from tests.analytics.test_native_capex_overrides import cases

# The manifest keys a USD-authored run returned before native CAPEX reached the API.
USD_MANIFEST_KEYS = {
    "config_sha256",
    "engine_version",
    "generated_at",
    "git_sha",
    "manifest_schema_version",
    "seed",
    "validation_mode",
}
STALE_REFUSAL = "native CAPEX provenance is stale"
CONFLICT_REFUSAL = "conflicts with capex.input"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _fx_override(native: dict[str, Any]) -> dict[str, float]:
    rate = native["capex"]["input"]["conversion"]["rate_lkr_per_usd"]
    return {"fx.start_lkr_per_usd": rate + 1.0}


def test_web_api_manifest_carries_native_provenance() -> None:
    """/run-pipeline returns the native_capex block with schema 1.1 (DOM-1645-R4-01)."""
    usd, native = cases()
    client = _client()
    left = client.post("/run-pipeline", json={"config": copy.deepcopy(native)})
    right = client.post("/run-pipeline", json={"config": copy.deepcopy(usd)})
    assert left.status_code == 200, left.text
    assert right.status_code == 200, right.text
    applied = evaluated_scenario_config(native)["capex"]["native_input_applied"]
    native_manifest = left.json()["manifest"]
    usd_manifest = right.json()["manifest"]
    assert native_manifest["manifest_schema_version"] == "1.1"
    assert native_manifest["native_capex"] == jsonable_encoder(applied)
    assert set(native_manifest) == USD_MANIFEST_KEYS | {"native_capex"}
    # A USD run leaves the key out (not null), so its manifest keys are unchanged.
    assert usd_manifest["manifest_schema_version"] == "1.0"
    assert "native_capex" not in usd_manifest
    assert set(usd_manifest) == USD_MANIFEST_KEYS
    # The pre-check does not change what the engine evaluates.
    assert left.json()["kpis"] == right.json()["kpis"]
    assert left.json()["debt"] == right.json()["debt"]


def test_web_api_fx_override_on_authored_native_derives_conversion_and_matches_usd_twin() -> (
    None
):
    """DOM-1645-03: lone fx.start_lkr_per_usd override on authored native CAPEX succeeds
    and matches the equivalent USD twin, while resolved configs refuse stale FX."""
    usd, native = cases()
    client = _client()
    fx_override = _fx_override(native)
    new_rate = fx_override["fx.start_lkr_per_usd"]
    lkr_amount = float(native["capex"]["input"]["amount"])

    moved = client.post(
        "/run-pipeline", json={"config": native, "overrides": fx_override}
    )
    assert moved.status_code == 200, moved.text
    manifest = moved.json()["manifest"]
    assert manifest["manifest_schema_version"] == "1.1"
    assert (
        manifest["native_capex"]["input"]["conversion"]["rate_lkr_per_usd"] == new_rate
    )
    assert manifest["native_capex"]["usd_at_price_date"] == pytest.approx(
        lkr_amount / new_rate, rel=1e-12
    )

    usd_oracle = client.post(
        "/run-pipeline",
        json={
            "config": usd,
            "overrides": {
                "fx.start_lkr_per_usd": new_rate,
                "capex.usd_total": lkr_amount / new_rate,
            },
        },
    )
    assert usd_oracle.status_code == 200, usd_oracle.text
    assert moved.json()["kpis"] == usd_oracle.json()["kpis"]
    assert moved.json()["debt"] == usd_oracle.json()["debt"]

    # Already-resolved config still refuses an FX spot override as stale provenance.
    resolved = normalize_native_capex(native)
    refused = client.post(
        "/run-pipeline", json={"config": resolved, "overrides": fx_override}
    )
    assert refused.status_code == 422
    assert STALE_REFUSAL in refused.json()["detail"]
    assert "see the server logs" not in refused.json()["detail"]


def test_web_api_config_path_run_gets_the_same_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run started from config_path gets the native pre-check, FX derivation, and manifest."""
    _, native = cases()
    (tmp_path / "native.yaml").write_text(yaml.safe_dump(native))
    monkeypatch.setattr(path_safety, "allowed_roots", lambda: (tmp_path.resolve(),))
    path = str(tmp_path / "native.yaml")
    client = _client()
    refused = client.post(
        "/run-pipeline",
        json={"config_path": path, "overrides": {"capex.usd_total": 1.0}},
    )
    assert refused.status_code == 422
    assert CONFLICT_REFUSAL in refused.json()["detail"]
    assert "see the server logs" not in refused.json()["detail"]

    fx_moved = client.post(
        "/run-pipeline",
        json={"config_path": path, "overrides": _fx_override(native)},
    )
    assert fx_moved.status_code == 200, fx_moved.text
    assert (
        fx_moved.json()["manifest"]["native_capex"]["input"]["conversion"][
            "rate_lkr_per_usd"
        ]
        == _fx_override(native)["fx.start_lkr_per_usd"]
    )

    plain = client.post("/run-pipeline", json={"config_path": path})
    assert plain.status_code == 200, plain.text
    manifest = plain.json()["manifest"]
    assert manifest["manifest_schema_version"] == "1.1"
    assert manifest["native_capex"]["input"] == jsonable_encoder(
        native["capex"]["input"]
    )


def test_web_api_openapi_native_capex_schema_is_non_nullable_optional_object() -> None:
    """#1696 follow-up: ManifestBlock.native_capex is an optional object, not anyOf[object, null]."""
    schema = _client().get("/openapi.json").json()
    manifest_schema = schema["components"]["schemas"]["ManifestBlock"]
    prop = manifest_schema["properties"]["native_capex"]
    assert prop["type"] == "object"
    assert "anyOf" not in prop
    assert "default" not in prop
    assert "native_capex" not in manifest_schema.get("required", [])
