"""#841 — public API contract freeze: pin the client-facing response shape + version.

The wizard (and a later iOS client) code against this contract, so a breaking change to a
public response model must fail LOUDLY here rather than silently ship. Bump
``API_CONTRACT_VERSION`` (and this test's expected set) deliberately when the contract
changes: MINOR for additive, MAJOR for breaking.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.responses import API_CONTRACT_VERSION, CaseResult

client = TestClient(app)


def test_case_result_public_field_set_is_frozen() -> None:
    """The client-facing CaseResult fields are the frozen contract. Changing this set is a
    contract change — update API_CONTRACT_VERSION and this assertion together."""
    assert set(CaseResult.model_fields) == {
        "status",
        "scenario_variant",
        "kpis",
        "run_manifest",
        "contract_version",
    }


def test_case_result_stamps_the_contract_version() -> None:
    result = CaseResult(status="success", scenario_variant="lendercase")
    assert result.contract_version == API_CONTRACT_VERSION


def test_health_reports_contract_version() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["contract_version"] == API_CONTRACT_VERSION


def test_public_endpoints_are_routed() -> None:
    """The public HTTP surface the client depends on is ROUTED (not 404): auth, run a
    case, fetch the report, sensitivity, and the async job path. Verified behaviourally
    via the client (an auth-gated route answers 401/422 without a token, never 404;
    /health is open) — removing an endpoint (making it 404) is a breaking change."""
    assert client.get("/health").status_code == 200
    for method, path in (
        ("POST", "/token"),
        ("POST", "/cases"),
        ("POST", "/cases/report.html"),
        ("POST", "/cases/report.pdf"),
        ("POST", "/sensitivity/run-tornado/"),
        ("POST", "/jobs"),
        ("GET", "/jobs/some-id"),
    ):
        resp = client.request(method, path, json={} if method == "POST" else None)
        assert (
            resp.status_code != 404
        ), f"public endpoint not routed: {method} {path} -> {resp.status_code}"


def test_contract_version_is_semver() -> None:
    parts = API_CONTRACT_VERSION.split(".")
    assert len(parts) >= 2 and all(p.isdigit() for p in parts)
