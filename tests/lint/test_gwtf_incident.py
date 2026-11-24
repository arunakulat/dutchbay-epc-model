"""G5 incident classifications must never promote supplied claims to authority."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import gwtf_incident as incident


def observation(**overrides: object) -> dict:
    return {
        "execution": "EXITED",
        "phase": "TEST",
        "exit_code": 0,
        "failure": "NONE",
        "platform_restriction": False,
        "reporting": "OBSERVED",
        "drift": "UNCHANGED",
        "evidence_sha256": "a" * 64,
        **overrides,
    }


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "EXECUTION_SUCCEEDED"),
        (
            {
                "phase": "FORMATTER",
                "exit_code": 1,
                "failure": "FORMATTER_MUTATION",
                "drift": "ALLOWLIST_ONLY",
            },
            "FORMATTER_MUTATION",
        ),
        ({"exit_code": 1, "failure": "TEST_FAILURE"}, "TEST_FAILURE"),
        (
            {"phase": "COMMIT", "exit_code": 1, "failure": "GIT_REJECTION"},
            "GIT_REJECTION",
        ),
        ({"exit_code": 127, "failure": "ENVIRONMENT_FAILURE"}, "ENVIRONMENT_FAILURE"),
        (
            {
                "execution": "UNKNOWN",
                "exit_code": None,
                "failure": "UNKNOWN",
                "reporting": "UNKNOWN",
                "drift": "UNKNOWN",
                "platform_restriction": True,
            },
            "PLATFORM_EXECUTION_RESTRICTION",
        ),
        (
            {"platform_restriction": True, "exit_code": 0, "failure": "TEST_FAILURE"},
            "PLATFORM_EXECUTION_RESTRICTION",
        ),
        ({"platform_restriction": None}, "UNKNOWN_OUTCOME"),
        (
            {"execution": "UNKNOWN", "exit_code": None, "reporting": "UNKNOWN"},
            "UNKNOWN_OUTCOME",
        ),
        (
            {"execution": "RUNNING", "exit_code": None, "reporting": "UNKNOWN"},
            "EXECUTION_RUNNING",
        ),
        (
            {"execution": "NOT_STARTED", "exit_code": None, "reporting": "UNKNOWN"},
            "EXECUTION_NOT_STARTED",
        ),
        (
            {
                "execution": "RUNNING",
                "exit_code": None,
                "failure": "WRITER_COLLISION",
                "reporting": "UNKNOWN",
            },
            "WRITER_COLLISION",
        ),
        ({"drift": "OUTSIDE_ALLOWLIST"}, "UNEXPECTED_DRIFT"),
        ({"evidence_sha256": None}, "MISSING_EXECUTION_EVIDENCE"),
        ({"exit_code": 0, "failure": "TEST_FAILURE"}, "CONTRADICTORY_OBSERVATIONS"),
        ({"execution": "RUNNING", "exit_code": 0}, "CONTRADICTORY_OBSERVATIONS"),
        (
            {"phase": "TEST", "exit_code": 1, "failure": "GIT_REJECTION"},
            "CONTRADICTORY_OBSERVATIONS",
        ),
        (
            {"phase": "COMMIT", "exit_code": 1, "failure": "FORMATTER_MUTATION"},
            "CONTRADICTORY_OBSERVATIONS",
        ),
        ({"exit_code": 1, "failure": "UNKNOWN"}, "UNCLASSIFIED_EXECUTION_FAILURE"),
        ({"drift": "ALLOWLIST_ONLY"}, "RECONCILIATION_REQUIRED"),
    ],
)
def test_execution_classification_never_grants_authority(
    overrides: dict, expected: str
) -> None:
    result = incident.classify(observation(**overrides))
    assert result["execution_disposition"] == expected
    for key in (
        "checkpoint_verified",
        "independent_review_complete",
        "writer_authorized",
        "retry_authorized",
        "merge_authorized",
        "delivery_confirmed",
        "evidence_authenticated",
    ):
        assert result[key] is False


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"reporting": "NOT_OBSERVED"}, "COMPLETED_BUT_UNREPORTED"),
        (
            {"reporting": "NOT_OBSERVED", "exit_code": 1, "failure": "TEST_FAILURE"},
            "COMPLETED_BUT_UNREPORTED",
        ),
        ({"reporting": "OBSERVED"}, "REPORT_OBSERVED_DELIVERY_UNCONFIRMED"),
        ({"reporting": "UNKNOWN"}, "REPORTING_UNKNOWN"),
        (
            {"execution": "RUNNING", "exit_code": None, "reporting": "UNKNOWN"},
            "COMPLETION_NOT_ESTABLISHED",
        ),
        ({"execution": "EXITED", "exit_code": None}, "COMPLETION_NOT_ESTABLISHED"),
    ],
)
def test_reporting_is_distinct(overrides: dict, expected: str) -> None:
    result = incident.classify(observation(**overrides))
    assert result["reporting_disposition"] == expected
    assert result["delivery_confirmed"] is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"raw_log": "synthetic private text"},
        {"phase": "synthetic private text"},
        {"exit_code": True},
        {"platform_restriction": 1},
        {"evidence_sha256": "not a digest"},
        {"execution": []},
        {"reporting": None},
    ],
)
def test_rejects_invalid_or_free_text_fields(overrides: dict, tmp_path: Path) -> None:
    target = tmp_path / "incident.json"
    with pytest.raises(ValueError):
        incident.persist(observation(**overrides), target)
    assert not target.exists()


def test_external_receipt_exclusive_and_fixed_schema(tmp_path: Path) -> None:
    target = tmp_path / "incident.json"
    tip = incident.persist(observation(reporting="NOT_OBSERVED"), target)
    raw = target.read_bytes()
    assert incident.hashlib.sha256(raw).hexdigest() == tip
    record = json.loads(raw)
    assert set(record) == {"recorded_utc", "observation", "disposition"}
    assert record["disposition"]["reconciliation_required"] is True
    with pytest.raises(FileExistsError):
        incident.persist(observation(), target)
    assert target.read_bytes() == raw
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    with pytest.raises(ValueError):
        incident.persist(observation(), repo / "incident.json")
