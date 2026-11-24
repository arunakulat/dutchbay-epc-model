"""G5 incident classifications must never promote supplied claims to authority."""

from __future__ import annotations

import json
import os
import subprocess
import sys
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
        "baseline_sha256": "b" * 64,
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


@pytest.mark.parametrize(
    "overrides,kind,report",
    [
        ({"reporting": "UNKNOWN"}, "EXECUTION_SUCCEEDED", "REPORTING_UNKNOWN"),
        (
            {"reporting": "NOT_OBSERVED", "evidence_sha256": None},
            "MISSING_EXECUTION_EVIDENCE",
            "COMPLETION_NOT_ESTABLISHED",
        ),
        (
            {"baseline_sha256": None},
            "UNKNOWN_OUTCOME",
            "REPORT_OBSERVED_DELIVERY_UNCONFIRMED",
        ),
        (
            {
                "execution": "RUNNING",
                "exit_code": None,
                "reporting": "UNKNOWN",
                "drift": "ALLOWLIST_ONLY",
            },
            "RECONCILIATION_REQUIRED",
            "COMPLETION_NOT_ESTABLISHED",
        ),
        (
            {"platform_restriction": True, "baseline_sha256": None},
            "PLATFORM_EXECUTION_RESTRICTION",
            "REPORT_OBSERVED_DELIVERY_UNCONFIRMED",
        ),
    ],
)
def test_uncertainty_requires_reconciliation(
    overrides: dict, kind: str, report: str
) -> None:
    result = incident.classify(observation(**overrides))
    assert result["execution_disposition"] == kind
    assert result["reporting_disposition"] == report
    assert result["reconciliation_required"] is True


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({}, 0),
        ({"platform_restriction": True}, 2),
        ({"reporting": "UNKNOWN"}, 2),
        ({"evidence_sha256": None}, 2),
        ({"baseline_sha256": None}, 2),
        ({"execution": "RUNNING", "exit_code": None, "reporting": "UNKNOWN"}, 2),
        ({"exit_code": 1, "failure": "TEST_FAILURE"}, 2),
    ],
)
def test_incident_shell_gate(tmp_path: Path, overrides: dict, code: int) -> None:
    source = tmp_path / "input.json"
    target = tmp_path / "receipt.json"
    source.write_text(json.dumps(observation(**overrides)))
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "scripts/gwtf_incident.py"),
            "--observation",
            str(source),
            "--receipt",
            str(target),
        ],
        capture_output=True,
    )
    assert result.returncode == code, result.stderr
    assert target.is_file()
    assert json.loads(result.stdout)["retry_authorized"] is False


@pytest.mark.parametrize(
    "script",
    [
        "gwtf_checkpoint_readiness",
        "gwtf_checkpoint_receipt",
        "gwtf_checkpoint_workflow",
        "gwtf_incident",
        "gwtf_interruption_recovery",
    ],
)
@pytest.mark.parametrize("malformed", ["array", "fifo"])
def test_cli_refuses_malformed_or_special_input(
    tmp_path: Path, script: str, malformed: str
) -> None:
    source = tmp_path / "input.json"
    if malformed == "fifo":
        os.mkfifo(source)
    else:
        source.write_text('["PRIVATE_FIXTURE"]\n')
    target = tmp_path / "output.json"
    root = tmp_path / "repo"
    root.mkdir()
    if script == "gwtf_checkpoint_receipt":
        args = [str(source)]
    elif script == "gwtf_checkpoint_workflow":
        args = [
            "--journal",
            str(target),
            "start",
            "--worktree",
            str(root),
            "--lease",
            str(source),
        ]
    elif script == "gwtf_incident":
        args = ["--observation", str(source), "--receipt", str(target)]
    elif script == "gwtf_interruption_recovery":
        args = [
            "--worktree",
            str(root),
            "--lease",
            str(source),
            "--output",
            str(target),
        ]
    else:
        args = [
            "--worktree",
            str(root),
            "--lease",
            str(source),
            "--receipt",
            str(target),
        ]
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / (script + ".py")), *args],
        capture_output=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert b"STOP:" in result.stderr
    assert b"Traceback" not in result.stderr
    assert b"PRIVATE_FIXTURE" not in result.stderr
    assert not target.exists()
