"""#841 — public API contract freeze: pin the versioned surface + the response schema.

The wizard (and a later iOS client) code against this contract, so a breaking change to a
public URL, response model, or its OpenAPI schema must fail LOUDLY here rather than silently
ship. The surface is version-pinned under ``/v1`` (a future breaking change lands as ``/v2``,
never a mutation of ``/v1`` in place); the body-level ``API_CONTRACT_VERSION`` pins the
response *shape*. Bump ``API_CONTRACT_VERSION`` (and the relevant assertion) deliberately when
the contract changes: MINOR for additive, MAJOR for breaking.

These tests assert the actual response-model FIELD SETS and TYPES and the OpenAPI schema — not
merely a 200 — so an accidental field rename/retype/removal is caught.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi.testclient import TestClient

from api.pipeline_api import RunPipelineResponse
from api.sensitivity_api import SensitivityTornadoRow
from app.api.jobs_router import JobAccepted
from app.api.main import API_V1_PREFIX, TokenResponse, app
from app.api.responses import API_CONTRACT_VERSION, AnalysisResult, CaseResult
from app.jobs.models import JobRecord

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Response-model field sets are the frozen contract (types pinned, not just 200).
# --------------------------------------------------------------------------- #
def test_case_result_public_field_set_is_frozen() -> None:
    """The client-facing CaseResult fields are the frozen contract. Changing this set is a
    contract change — update API_CONTRACT_VERSION and this assertion together."""
    assert set(CaseResult.model_fields) == {
        "status",
        "scenario_variant",
        "kpis",
        "run_manifest",
        "contract_version",
        "wind_assessment",  # #993: additive, optional (contract 1.1)
    }


def test_case_result_field_types_are_pinned() -> None:
    """Pin the client-facing TYPES, not only the field names — a silent retype (e.g.
    kpis -> list) is a breaking contract change and must be caught here."""
    ann = {k: str(f.annotation) for k, f in CaseResult.model_fields.items()}
    assert ann["status"] == "<class 'str'>"
    assert ann["scenario_variant"] == "<class 'str'>"
    assert "Dict[str, float]" in ann["kpis"] or "dict[str, float]" in ann["kpis"]
    assert ann["contract_version"] == "<class 'str'>"
    assert "WindAssessment" in ann["wind_assessment"]  # Optional[WindAssessment] (#993)


def test_tornado_row_public_field_set_and_types_are_frozen() -> None:
    """The sensitivity tornado response was an untyped list[dict[str, Any]] before #841;
    it is now a pinned list[SensitivityTornadoRow]. Freeze its field set + optionality.
    """
    assert set(SensitivityTornadoRow.model_fields) == {
        "parameter",
        "metric",
        "base_metric",
        "low_case",
        "high_case",
        "impact_abs",
    }
    ann = {k: str(f.annotation) for k, f in SensitivityTornadoRow.model_fields.items()}
    assert ann["parameter"] == "<class 'str'>"
    assert ann["metric"] == "<class 'str'>"
    # The numeric fields are Optional (the engine can yield None for an unevaluable shock).
    for numeric in ("base_metric", "low_case", "high_case", "impact_abs"):
        assert "Optional" in ann[numeric] or "None" in ann[numeric]


def test_job_accepted_public_field_set_is_frozen() -> None:
    assert set(JobAccepted.model_fields) == {
        "job_id",
        "state",
        "status_url",
        "events_url",
    }


def test_analysis_result_public_field_set_is_frozen() -> None:
    """The async-analysis envelope (#993 PR-B) is a client-facing shape delivered inside
    JobRecord.result. Freeze its field set + types — a rename/retype is a contract change
    (bump API_CONTRACT_VERSION and this assertion together)."""
    assert set(AnalysisResult.model_fields) == {
        "analysis_type",
        "metric",
        "scenario_variant",
        "engine_result",
        "contract_version",
    }
    ann = {k: str(f.annotation) for k, f in AnalysisResult.model_fields.items()}
    assert ann["analysis_type"] == "<class 'str'>"
    assert ann["metric"] == "<class 'str'>"
    assert ann["scenario_variant"] == "<class 'str'>"
    assert "Dict[str, " in ann["engine_result"] and "Any" in ann["engine_result"]
    assert ann["contract_version"] == "<class 'str'>"


def test_analysis_result_stamps_the_contract_version() -> None:
    envelope = AnalysisResult(
        analysis_type="mc", metric="project_irr", scenario_variant="lendercase"
    )
    assert envelope.contract_version == API_CONTRACT_VERSION


def test_job_record_public_field_set_is_frozen() -> None:
    assert set(JobRecord.model_fields) == {
        "job_id",
        "owner",
        "state",
        "progress",
        "result",
        "error",
        "created_at",
        "updated_at",
    }


def test_token_response_public_field_set_is_frozen() -> None:
    assert set(TokenResponse.model_fields) == {"access_token", "token_type"}


def test_run_pipeline_response_top_level_field_set_is_frozen() -> None:
    assert set(RunPipelineResponse.model_fields) == {
        "scenario_name",
        "config_path",
        "validation_mode",
        "cost_basis_year",
        "kpis",
        "aep",
        "debt",
        "cost",
        "funding",
        "manifest",
    }


# --------------------------------------------------------------------------- #
# Version stamping.
# --------------------------------------------------------------------------- #
def test_case_result_stamps_the_contract_version() -> None:
    result = CaseResult(status="success", scenario_variant="lendercase")
    assert result.contract_version == API_CONTRACT_VERSION


def test_health_reports_contract_version() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["contract_version"] == API_CONTRACT_VERSION


def test_contract_version_is_semver() -> None:
    parts = API_CONTRACT_VERSION.split(".")
    assert len(parts) >= 2 and all(p.isdigit() for p in parts)


def test_contract_version_value_is_pinned() -> None:
    """Pin the literal so a reverted/fat-fingered constant is caught — the stamping
    tests above are self-referential (== API_CONTRACT_VERSION) and would stay green.
    Bump this together with API_CONTRACT_VERSION on any deliberate contract change."""
    assert API_CONTRACT_VERSION == "1.2"


# --------------------------------------------------------------------------- #
# The URL surface is version-pinned under /v1 (freeze), /health stays unversioned.
# --------------------------------------------------------------------------- #
def test_public_endpoints_are_routed_under_v1() -> None:
    """The public HTTP surface the client depends on is ROUTED under /v1 (not 404):
    auth, run a case, fetch the report, sensitivity, and the async job path. Verified
    behaviourally (an auth-gated route answers 401/422 without a token, never 404).
    Removing an endpoint (making it 404) is a breaking change."""
    assert client.get("/health").status_code == 200
    for method, path in (
        ("POST", f"{API_V1_PREFIX}/token"),
        ("POST", f"{API_V1_PREFIX}/cases"),
        ("POST", f"{API_V1_PREFIX}/cases/report.html"),
        ("POST", f"{API_V1_PREFIX}/cases/report.pdf"),
        ("POST", f"{API_V1_PREFIX}/run-pipeline"),
        ("POST", f"{API_V1_PREFIX}/sensitivity/run-tornado/"),
        ("POST", f"{API_V1_PREFIX}/jobs"),
        ("GET", f"{API_V1_PREFIX}/jobs/some-id"),
    ):
        resp = client.request(method, path, json={} if method == "POST" else None)
        assert (
            resp.status_code != 404
        ), f"public endpoint not routed: {method} {path} -> {resp.status_code}"


def test_pre_freeze_unprefixed_paths_are_gone() -> None:
    """/v1 is the single public surface: the pre-freeze unprefixed client-data paths must
    now 404 (only /health remains unversioned). Re-introducing an unversioned public path
    would fork the surface and is a contract regression."""
    for method, path in (
        ("POST", "/cases"),
        ("POST", "/jobs"),
        ("POST", "/run-pipeline"),
        ("POST", "/sensitivity/run-tornado/"),
    ):
        resp = client.request(method, path, json={})
        assert (
            resp.status_code == 404
        ), f"unversioned path still routed: {method} {path}"


# --------------------------------------------------------------------------- #
# The auto-generated OpenAPI schema reflects the versioned, typed contract.
# --------------------------------------------------------------------------- #
def _schema() -> Dict[str, Any]:
    return app.openapi()


def test_openapi_paths_are_all_versioned_except_health() -> None:
    paths = set(_schema()["paths"])
    non_health = {p for p in paths if p != "/health"}
    assert non_health, "expected client-data paths in the schema"
    assert all(
        p.startswith(f"{API_V1_PREFIX}/") for p in non_health
    ), f"unversioned client-data path in schema: {sorted(non_health)}"


def test_openapi_operation_ids_are_pinned() -> None:
    """The SDK-facing operationIds stay pinned (decoupled from handler renames)."""
    paths = _schema()["paths"]
    assert paths[f"{API_V1_PREFIX}/cases"]["post"]["operationId"] == "run_case"
    assert (
        paths[f"{API_V1_PREFIX}/sensitivity/run-tornado/"]["post"]["operationId"]
        == "run_sensitivity_tornado"
    )


def test_openapi_tornado_response_is_typed_array_not_bare_object() -> None:
    """#841 core: the sensitivity tornado response schema is an ARRAY of the typed
    SensitivityTornadoRow (with named properties), not a free-form object. This is the
    schema that used to be list[dict[str, Any]] (an untyped array of objects)."""
    schema = _schema()
    op = schema["paths"][f"{API_V1_PREFIX}/sensitivity/run-tornado/"]["post"]
    body_schema = op["responses"]["200"]["content"]["application/json"]["schema"]
    assert body_schema["type"] == "array"
    ref = body_schema["items"].get("$ref", "")
    assert ref.endswith("/SensitivityTornadoRow"), ref
    # The referenced component actually pins the field names (not additionalProperties).
    row = schema["components"]["schemas"]["SensitivityTornadoRow"]
    assert set(row["properties"]) == {
        "parameter",
        "metric",
        "base_metric",
        "low_case",
        "high_case",
        "impact_abs",
    }


def test_openapi_case_response_is_typed_caseresult() -> None:
    schema = _schema()
    op = schema["paths"][f"{API_V1_PREFIX}/cases"]["post"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/CaseResult"), ref
    props = schema["components"]["schemas"]["CaseResult"]["properties"]
    assert {"status", "scenario_variant", "kpis", "contract_version"} <= set(props)
