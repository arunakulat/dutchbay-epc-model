"""Path-traversal confinement for the HTTP API (api/path_safety).

Guards the /run-pipeline and /run-tornado endpoints against arbitrary file reads
via caller-supplied config_path / aep_summary_path.
"""

from __future__ import annotations

import pytest

from api.path_safety import REPO_ROOT, UnsafePathError, allowed_roots, confined_path


def test_allowed_roots_are_absolute_and_nonempty() -> None:
    roots = allowed_roots()
    assert roots, "allowed_path_roots must be configured"
    assert all(r.is_absolute() for r in roots)
    # scenarios + tests/mocks are required for the canonical lender scenario.
    rel = {str(r.relative_to(REPO_ROOT)) for r in roots}
    assert "scenarios" in rel
    assert "tests/mocks" in rel


def test_accepts_committed_scenario() -> None:
    p = confined_path("scenarios/dutchbay_lendercase_2025Q4.yaml", must_exist=True)
    assert p.is_file()
    assert p.is_relative_to(REPO_ROOT / "scenarios")


def test_accepts_canonical_aep_summary_mock() -> None:
    p = confined_path("tests/mocks/aep_summary_dutchbay_10mw.json", must_exist=True)
    assert p.is_file()


@pytest.mark.parametrize(
    "evil",
    [
        "../../etc/passwd",
        "scenarios/../../etc/passwd",
        "/etc/passwd",
        "scenarios/../../../../../../etc/hosts",
        "~/.ssh/id_rsa",
        "config/../../../../etc/passwd",
    ],
)
def test_rejects_traversal_and_absolute(evil: str) -> None:
    with pytest.raises(UnsafePathError):
        confined_path(evil)


def test_rejects_empty() -> None:
    with pytest.raises(UnsafePathError):
        confined_path("   ")


def test_must_exist_rejects_missing_inbounds_path() -> None:
    # Inside an allowed root but non-existent -> still rejected when must_exist.
    with pytest.raises(UnsafePathError):
        confined_path("scenarios/__does_not_exist__.yaml", must_exist=True)


def test_in_bounds_nonexistent_ok_without_must_exist() -> None:
    p = confined_path("exports/some_future_output.csv")
    assert p.is_relative_to(REPO_ROOT / "exports")


def test_endpoint_rejects_traversal_config_path() -> None:
    """End-to-end: /run-pipeline returns 400 for a traversal config_path."""
    httpx = pytest.importorskip("httpx")  # FastAPI TestClient transport
    assert httpx  # keep the import referenced
    from fastapi.testclient import TestClient

    from api.sensitivity_api import app

    client = TestClient(app)
    resp = client.post("/run-pipeline", json={"config_path": "../../etc/passwd"})
    assert resp.status_code == 400
    assert "config_path" in resp.json()["detail"]
