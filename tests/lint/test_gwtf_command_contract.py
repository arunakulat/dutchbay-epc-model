"""Schema-3 command contracts: synthetic hostile evidence and compatibility tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_checkpoint_receipt as receipt


def lease_fixture() -> dict[str, Any]:
    checks = [
        {
            "check_id": cid,
            "command": [sys.executable, "-B", cid],
            "log_name": cid + ".log",
        }
        for cid in ("readiness", "regression", "staged", "commit")
    ]
    return {
        "state": "PATCH_APPLIED",
        "lease_id": "fixture",
        "branch": "feat/fixture",
        "head": "a" * 40,
        "tree": "b" * 40,
        "base": "c" * 40,
        "index_sha256": "d" * 64,
        "allowlist": ["a.txt"],
        "candidate_sha256": {"a.txt": "e" * 64},
        "candidate_modes": {"a.txt": "100644"},
        "type_plan": [],
        "type_not_applicable_reason": "plain text fixture",
        "command_contract": {
            "interpreter": sys.executable,
            "hook_config_sha256": "f" * 64,
            "checks": checks,
        },
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "order",
        "missing",
        "relative",
        "duplicate_log",
        "hook_log_collision",
        "invalid_config",
        "extra_field",
    ],
)
def test_invalid_command_plan_refused(mutation: str) -> None:
    lease = lease_fixture()
    contract = lease["command_contract"]
    checks = contract["checks"]
    if mutation == "order":
        checks[0], checks[1] = checks[1], checks[0]
    elif mutation == "missing":
        checks.pop()
    elif mutation == "relative":
        checks[1]["command"] = ["true"]
    elif mutation == "duplicate_log":
        checks[1]["log_name"] = checks[0]["log_name"]
    elif mutation == "hook_log_collision":
        checks[1]["log_name"] = checks[0]["log_name"] + ".pass1.log"
    elif mutation == "invalid_config":
        contract["hook_config_sha256"] = "no digest"
    else:
        checks[1]["approval"] = True
    with pytest.raises(ValueError):
        receipt.start_data(lease)


def readiness_fixture(directory: Path, start: dict) -> dict:
    subject = start["subject"]
    contract = subject["command_contract"]
    planned = contract["checks"][0]
    log = directory / planned["log_name"]
    identity = {
        "branch": subject["branch"],
        "head": subject["parent_head"],
        "tree": subject["parent_tree"],
        "base": subject["base"],
        "index_sha256": subject["initial_index_sha256"],
    }
    candidate = {
        "identity": identity,
        "candidate_sha256": subject["candidate_sha256"],
        "candidate_modes": subject["candidate_modes"],
    }
    rows = [
        {"state": "STARTED"},
        {
            "state": "PREFLIGHTED",
            **candidate,
            "config_sha256": contract["hook_config_sha256"],
        },
    ]
    command = [
        sys.executable,
        "-I",
        "-m",
        "pre_commit",
        "run",
        "--config",
        ready.CONFIG,
        "--hook-stage",
        "pre-commit",
        "--files",
        "a.txt",
    ]
    for attempt in (1, 2):
        hook_log = log.with_name(log.name + f".pass{attempt}.log")
        hook_log.write_text("synthetic hook fixture, not actual execution\n")
        rows.append(
            {
                "state": "HOOK_PASS_OBSERVED",
                "pass_number": attempt,
                "exit_code": 0,
                "drift": [],
                "index_and_identity_unchanged": True,
                "command": command,
                "log_sha256": ready.digest(hook_log),
            }
        )
    rows.append({"state": "READY_FOR_FINAL_BYTE_TESTS", **candidate})
    log.write_text(
        "".join(
            json.dumps(dict(row, lease_id=subject["lease_id"])) + "\n" for row in rows
        )
    )
    return {
        **planned,
        "subject_sha256": start["subject_sha256"],
        "exit_code": 0,
        "log_sha256": ready.digest(log),
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "argv",
        "log_name",
        "wrong_order",
        "config",
        "hook_argv",
        "preflight_hash",
        "extra_field",
    ],
)
def test_bound_observation_mutations_refused(tmp_path: Path, mutation: str) -> None:
    start = receipt.start_data(lease_fixture())
    journal = tmp_path / "events.jsonl"
    tip = receipt.append_event(journal, "STARTED", start)
    original = journal.read_bytes()
    observation = readiness_fixture(tmp_path, start)
    if mutation == "argv":
        observation["command"] = [sys.executable, "-c", "pass"]
    elif mutation == "log_name":
        path = tmp_path / "other.log"
        path.write_bytes((tmp_path / observation["log_name"]).read_bytes())
        observation["log_name"] = path.name
    elif mutation == "wrong_order":
        observation.update(start["subject"]["command_contract"]["checks"][1])
        path = tmp_path / observation["log_name"]
        path.write_text("wrong order")
        observation["log_sha256"] = ready.digest(path)
    elif mutation in {"config", "hook_argv", "preflight_hash"}:
        path = tmp_path / observation["log_name"]
        rows = receipt.parse_rows(path.read_text())
        if mutation == "config":
            rows[1]["config_sha256"] = "0" * 64
        elif mutation == "hook_argv":
            rows[2]["command"] = [sys.executable, "-c", "pass"]
        else:
            rows[1]["candidate_sha256"] = {"a.txt": "0" * 64}
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        observation["log_sha256"] = ready.digest(path)
    else:
        observation["approval"] = True
    with pytest.raises(ValueError):
        receipt._append_event(journal, "CHECK_OBSERVED", observation, tip)
    assert journal.read_bytes() == original


def test_bound_completion_and_failure_stop(tmp_path: Path) -> None:
    start = receipt.start_data(lease_fixture())
    journal = tmp_path / "events.jsonl"
    tip = receipt.append_event(journal, "STARTED", start)
    before = journal.read_bytes()
    with pytest.raises(ValueError, match="requires all ordered checks"):
        receipt._append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0}, tip)
    assert journal.read_bytes() == before
    observation = readiness_fixture(tmp_path, start)
    tip = receipt._append_event(journal, "CHECK_OBSERVED", observation, tip)
    planned = start["subject"]["command_contract"]["checks"][1]
    log = tmp_path / planned["log_name"]
    log.write_text("synthetic failed regression")
    failure = {
        **planned,
        "subject_sha256": start["subject_sha256"],
        "exit_code": 1,
        "log_sha256": ready.digest(log),
    }
    tip = receipt._append_event(journal, "CHECK_OBSERVED", failure, tip)
    before = journal.read_bytes()
    planned = start["subject"]["command_contract"]["checks"][2]
    log = tmp_path / planned["log_name"]
    log.write_text("synthetic staged evidence")
    staged = {
        **planned,
        "subject_sha256": start["subject_sha256"],
        "exit_code": 0,
        "log_sha256": ready.digest(log),
    }
    with pytest.raises(ValueError, match="prior failure"):
        receipt._append_event(journal, "CHECK_OBSERVED", staged, tip)
    with pytest.raises(ValueError, match="requires all ordered checks"):
        receipt._append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0}, tip)
    assert journal.read_bytes() == before
    tip = receipt._append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 1}, tip)
    result = receipt.inspect_journal(journal, tip)
    assert result["command_contract_bound"] is True
    assert result["checkpoint_recorded"] is False
    assert result["execution_authenticated"] is False


def test_schema_downgrade_refused_and_v2_remains_diagnostic(tmp_path: Path) -> None:
    lease = lease_fixture()
    start = receipt.start_data(lease)
    journal = tmp_path / "events.jsonl"
    tip = receipt.append_event(journal, "STARTED", start)
    rows = receipt.parse_rows(journal.read_text())
    assert rows[0]["schema"] == receipt.BOUND_SCHEMA
    altered = copy.deepcopy(rows)
    altered[0]["schema"] = receipt.SCHEMA
    altered[0]["event_sha256"] = receipt.digest(
        receipt.canonical({k: v for k, v in altered[0].items() if k != "event_sha256"})
    )
    with pytest.raises(ValueError, match="contract schema mismatch"):
        receipt.validate_chain(altered, tmp_path)
    assert receipt.inspect_journal(journal, tip)["command_contract_bound"] is True
    del lease["command_contract"]
    prior = tmp_path / "v2.jsonl"
    old_tip = receipt.append_event(prior, "STARTED", receipt.start_data(lease))
    assert receipt.inspect_journal(prior, old_tip)["command_contract_bound"] is False


@pytest.mark.parametrize(
    "mutation", ["missing", "tip", "worktree", "exit", "auth", "time", "hash", "none"]
)
def test_execution_sidecar_binding(tmp_path: Path, mutation: str) -> None:
    lease = lease_fixture()
    lease["command_contract"]["observed_execution_worktree"] = str(
        tmp_path / "worktree"
    )
    start = receipt.start_data(lease)
    journal = tmp_path / "events.jsonl"
    tip = receipt.append_event(journal, "STARTED", start)
    tip = receipt._append_event(
        journal, "CHECK_OBSERVED", readiness_fixture(tmp_path, start), tip
    )
    planned = start["subject"]["command_contract"]["checks"][1]
    log = tmp_path / planned["log_name"]
    log.write_text("synthetic output, not attestation")
    observation = {
        **planned,
        "subject_sha256": start["subject_sha256"],
        "exit_code": 0,
        "log_sha256": ready.digest(log),
    }
    sidecar = log.with_name(log.name + ".execution.json")
    data: dict[str, Any] = {
        "schema": 1,
        "observation": copy.deepcopy(observation),
        "worktree": str(tmp_path / "worktree"),
        "prior_tip": tip,
        "started_utc": "2026-01-01T00:00:00+00:00",
        "finished_utc": "2026-01-01T00:00:01+00:00",
        "candidate_state_unchanged": True,
        "execution_authenticated": False,
    }
    if mutation == "tip":
        data["prior_tip"] = "0" * 64
    elif mutation == "worktree":
        data["worktree"] = "/other"
    elif mutation == "exit":
        data["observation"]["exit_code"] = 1
    elif mutation == "auth":
        data["execution_authenticated"] = True
    elif mutation == "time":
        data["finished_utc"] = "2025-01-01T00:00:00+00:00"
    sidecar.write_bytes(receipt.canonical(data))
    observation["execution_observation_sha256"] = ready.digest(sidecar)
    if mutation == "missing":
        del observation["execution_observation_sha256"]
    elif mutation == "hash":
        sidecar.write_bytes(sidecar.read_bytes() + b" ")
    before = journal.read_bytes()
    if mutation == "none":
        tip = receipt._append_event(journal, "CHECK_OBSERVED", observation, tip)
        assert receipt.inspect_journal(journal, tip)["observed_execution_required"]
        assert receipt.inspect_journal(journal, tip)["execution_authenticated"] is False
    else:
        with pytest.raises(ValueError):
            receipt._append_event(journal, "CHECK_OBSERVED", observation, tip)
        assert journal.read_bytes() == before


def test_execution_sidecar_log_collision_refused(tmp_path: Path) -> None:
    lease = lease_fixture()
    lease["command_contract"]["observed_execution_worktree"] = str(tmp_path)
    checks = lease["command_contract"]["checks"]
    checks[2]["log_name"] = checks[1]["log_name"] + ".execution.json"
    with pytest.raises(ValueError, match="execution sidecar"):
        receipt.start_data(lease)
