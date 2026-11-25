"""G8 v2 receipts: real Git/check evidence and hostile candidate/anchor tests."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_checkpoint_receipt as receipt


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def observe(
    tmp_path: Path,
    *,
    typed: bool = False,
    omit: str | None = None,
    mode_drift: bool = False,
) -> tuple[Path, Path, dict, str]:
    root = tmp_path / "synthetic repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / ready.CONFIG).write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: fixture-check\n    name: fixture check\n    entry: "
        + json.dumps(shlex.quote(sys.executable) + " fixture_hook.py")
        + "\n    language: system\n    pass_filenames: false\n"
    )
    (root / "fixture_hook.py").write_text("pass\n")
    (root / "mypy.ini").write_text("[mypy]\n")
    name = "a.py" if typed else "a.txt"
    (root / name).write_text("x = 1\n" if typed else "base\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "switch", "-c", "feat/fixture")
    subprocess.run(
        [sys.executable, "-I", "-m", "pre_commit", "install"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    lease: dict[str, Any] = {
        **ready.identity(root),
        "lease_id": "fixture",
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "holder": "fixture",
        "coordinator": "fixture",
        "allowlist": [name],
    }
    (root / name).write_text("x: int = 2\n" if typed else "candidate\n")
    lease["candidate_sha256"] = {name: ready.digest(root / name)}
    lease["candidate_modes"] = {name: ready.git_mode(root / name)}
    if typed:
        lease["type_plan"] = [
            {
                "check_id": "types:strict",
                "profile": "strict",
                "scope": [name],
                "interpreter": sys.executable,
                "python_version": sys.version,
                "mypy_version": subprocess.check_output(
                    [sys.executable, "-I", "-m", "mypy", "--version"], text=True
                ).strip(),
                "config_sha256": ready.digest(root / "mypy.ini"),
            }
        ]
    else:
        lease["type_not_applicable_reason"] = (
            "fixture changes only plain text, no import contract"
        )
    journal = tmp_path / "events.jsonl"
    start = receipt.start_data(lease)
    receipt.append_event(journal, "STARTED", start)

    def record(
        cid: str, command: list[str], log: Path, code: int, plan: dict | None = None
    ) -> None:
        if omit == cid:
            return
        data = {
            "check_id": cid,
            "subject_sha256": start["subject_sha256"],
            "command": command,
            "exit_code": code,
            "log_name": log.name,
            "log_sha256": ready.digest(log),
        }
        if plan is not None:
            data["type_evidence"] = plan
        receipt.append_event(journal, "CHECK_OBSERVED", data)

    log = tmp_path / "readiness.jsonl"
    ready.run_readiness(root, lease, log)
    record("readiness", [sys.executable, "-B", "readiness"], log, 0)
    if typed:
        plan = lease["type_plan"][0]
        cmd = receipt.type_command(plan)
        result = subprocess.run(cmd, cwd=root, capture_output=True, check=False)
        log = tmp_path / "types.log"
        log.write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, log.read_text()
        record(plan["check_id"], cmd, log, result.returncode, plan)
    cmd = ["git", "diff", "--check"]
    result = subprocess.run(cmd, cwd=root, capture_output=True, check=False)
    log = tmp_path / "check.log"
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    record("regression", cmd, log, result.returncode)
    git(root, "add", name)
    proof = ready.verify_staged(root, lease)
    log = tmp_path / "staged.json"
    log.write_text(json.dumps(proof))
    record("staged", [sys.executable, "-B", "verify_staged"], log, 0)
    if mode_drift:
        (root / name).chmod(0o755)
        git(root, "add", name)
    cmd = ["git", "commit", "-m", "candidate"]
    result = subprocess.run(cmd, cwd=root, capture_output=True, check=False)
    log = tmp_path / "commit.log"
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, log.read_text()
    record("commit", cmd, log, result.returncode)
    tip = receipt.append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0})
    return root, journal, lease, tip


@pytest.fixture
def observed(tmp_path: Path) -> tuple[Path, Path, dict, str]:
    return observe(tmp_path)


def test_exact_object_and_reporting_states(observed: tuple) -> None:
    root, journal, lease, pretip = observed
    data = receipt.inspect_journal(journal)
    assert data["execution_completed"] is True
    assert data["report_observed"] is False
    assert data["checkpoint_recorded"] is False
    with pytest.raises(ValueError, match="checkpoint event required"):
        receipt.reconcile_checkpoint(root, lease, journal, pretip)
    tip = receipt.record_checkpoint(root, lease, journal, pretip)
    verified = receipt.reconcile_checkpoint(root, lease, journal, tip)
    assert verified["head"] == ready.git_text(root, "rev-parse", "HEAD")
    data = receipt.inspect_journal(journal, tip)
    assert data["checkpoint_recorded"] is True
    assert data["checkpoint_verified"] is False
    assert verified["execution_authenticated"] is False
    tip = receipt.append_event(
        journal,
        "REPORT_OBSERVED",
        {
            "channel": "operator transcript",
            "observation": "status emitted",
            "delivery_confirmed": False,
        },
    )
    assert receipt.reconcile_checkpoint(root, lease, journal, tip) == verified
    data = receipt.inspect_journal(journal, tip)
    assert data["report_observed"] is True
    assert data["delivery_confirmed"] is False
    assert data["independent_review_complete"] is False


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_parent",
        "wrong_blob",
        "wrong_scope",
        "dirty",
        "wrong_base",
        "wrong_lease",
        "wrong_mode",
    ],
)
def test_git_reconciliation_rejects(observed: tuple, defect: str) -> None:
    root, journal, lease, pretip = observed
    tip = receipt.record_checkpoint(root, lease, journal, pretip)
    if defect == "wrong_parent":
        lease["head"] = ready.git_text(root, "rev-parse", "HEAD")
    elif defect == "wrong_blob":
        lease["candidate_sha256"]["a.txt"] = "0" * 64
    elif defect == "wrong_scope":
        lease["allowlist"].append("b.txt")
        lease["candidate_sha256"]["b.txt"] = "0" * 64
        lease["candidate_modes"]["b.txt"] = "100644"
    elif defect == "dirty":
        (root / "a.txt").write_text("drift\n")
    elif defect == "wrong_base":
        lease["base"] = "0" * 40
    elif defect == "wrong_mode":
        lease["candidate_modes"]["a.txt"] = "100755"
    else:
        lease["lease_id"] = "another"
    with pytest.raises(ValueError):
        receipt.reconcile_checkpoint(root, lease, journal, tip)


@pytest.mark.parametrize(
    "defect", ["log", "chain", "partial", "tip", "delivery", "duplicate", "approval"]
)
def test_receipt_rejects_unsupported_evidence(observed: tuple, defect: str) -> None:
    root, journal, lease, pretip = observed
    if defect == "log":
        (journal.parent / "check.log").write_text("altered")
    elif defect == "chain":
        rows = receipt.parse_rows(journal.read_text())
        rows[1]["data"]["exit_code"] = 1
        journal.write_text("".join(json.dumps(x) + "\n" for x in rows))
    elif defect == "partial":
        journal.write_text(journal.read_text() + "{")
    elif defect == "tip":
        with pytest.raises(ValueError, match="tip mismatch"):
            receipt.inspect_journal(journal, "0" * 64)
        with pytest.raises(ValueError, match="tip mismatch"):
            receipt.record_checkpoint(root, lease, journal, "0" * 64)
        return
    elif defect == "delivery":
        with pytest.raises(ValueError, match="delivery claim"):
            receipt.append_event(
                journal,
                "REPORT_OBSERVED",
                {"channel": "chat", "observation": "sent", "delivery_confirmed": True},
            )
        return
    elif defect == "duplicate":
        with pytest.raises(ValueError, match="completion"):
            receipt.append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0})
        return
    else:
        tip = receipt.record_checkpoint(root, lease, journal, pretip)
        verified = receipt.reconcile_checkpoint(root, lease, journal, tip)
        verified["merge_authorized_by_receipt"] = True
        with pytest.raises(ValueError, match="approval"):
            receipt.append_event(journal, "CHECKPOINT_VERIFIED", verified)
        return
    with pytest.raises(ValueError):
        receipt.inspect_journal(journal)


def test_missing_required_check_blocks_checkpoint(tmp_path: Path) -> None:
    root, journal, lease, tip = observe(tmp_path, omit="regression")
    with pytest.raises(ValueError, match="required check evidence missing"):
        receipt.record_checkpoint(root, lease, journal, tip)


def test_incomplete_checkpoint_payload_rejected(observed: tuple) -> None:
    _, journal, _, tip = observed
    minimal = {
        "independent_review_complete": False,
        "merge_authorized_by_receipt": False,
    }
    with pytest.raises(ValueError, match="checkpoint requires anchored"):
        receipt.append_event(journal, "CHECKPOINT_VERIFIED", minimal)
    # Also reject a fully rehashed but structurally incomplete journal on read.
    rows = receipt.parse_rows(journal.read_text())
    forged = {
        "schema": receipt.SCHEMA,
        "sequence": len(rows),
        "previous_sha256": tip,
        "timestamp_utc": "synthetic",
        "event": "CHECKPOINT_VERIFIED",
        "data": minimal,
    }
    forged["event_sha256"] = receipt.digest(receipt.canonical(forged))
    with journal.open("a") as out:
        out.write(json.dumps(forged) + "\n")
    with pytest.raises(ValueError, match="object fields missing"):
        receipt.inspect_journal(journal, forged["event_sha256"])


def test_post_staging_mode_drift_blocks_checkpoint(tmp_path: Path) -> None:
    root, journal, lease, tip = observe(tmp_path, mode_drift=True)
    with pytest.raises(ValueError, match="index differs|mode mismatch"):
        receipt.record_checkpoint(root, lease, journal, tip)


def test_typed_scope_and_real_mypy_evidence(tmp_path: Path) -> None:
    root, journal, lease, pretip = observe(tmp_path, typed=True)
    tip = receipt.record_checkpoint(root, lease, journal, pretip)
    assert (
        receipt.reconcile_checkpoint(root, lease, journal, tip)[
            "execution_authenticated"
        ]
        is False
    )
    invalid = dict(lease, type_plan=[], type_not_applicable_reason="no types claimed")
    with pytest.raises(ValueError, match="typed scope missing"):
        receipt.start_data(invalid)
    # A candidate-bound journal refuses stale evidence or a fabricated command.
    original = receipt.parse_rows(journal.read_text())
    typed = next(
        x["data"]
        for x in original
        if x["event"] == "CHECK_OBSERVED" and x["data"]["check_id"] == "types:strict"
    )
    fresh = journal.with_name("negative.jsonl")
    receipt.append_event(fresh, "STARTED", receipt.start_data(lease))
    with pytest.raises(ValueError, match="stale or different candidate"):
        receipt.append_event(
            fresh, "CHECK_OBSERVED", dict(typed, subject_sha256="0" * 64)
        )
    with pytest.raises(ValueError, match="type command differs"):
        receipt.append_event(fresh, "CHECK_OBSERVED", dict(typed, command=["true"]))
    with pytest.raises(ValueError, match="metadata mismatch"):
        receipt.append_event(fresh, "CHECK_OBSERVED", dict(typed, type_evidence={}))
    (root / "mypy.ini").write_text("[mypy]\nwarn_return_any = True\n")
    with pytest.raises(ValueError, match="configuration drift"):
        receipt.reconcile_checkpoint(root, lease, journal, tip)


def test_typed_check_omitted_blocks_checkpoint(tmp_path: Path) -> None:
    root, journal, lease, tip = observe(tmp_path, typed=True, omit="types:strict")
    with pytest.raises(ValueError, match="required check evidence missing"):
        receipt.record_checkpoint(root, lease, journal, tip)


def test_legacy_journal_is_historical_only(observed: tuple) -> None:
    root, journal, lease, _ = observed
    old = journal.with_name("legacy.jsonl")
    log = journal.parent / "check.log"
    events = [
        ("STARTED", {"lease_id": "fixture", "required_checks": ["diff"]}),
        (
            "CHECK_OBSERVED",
            {
                "check_id": "diff",
                "command": ["git", "diff", "--check"],
                "exit_code": 0,
                "log_name": log.name,
                "log_sha256": ready.digest(log),
            },
        ),
        ("EXECUTION_COMPLETED", {"exit_code": 0}),
        (
            "CHECKPOINT_VERIFIED",
            {
                "independent_review_complete": False,
                "merge_authorized_by_receipt": False,
            },
        ),
    ]
    prev = receipt.ZERO
    with old.open("x") as out:
        for i, (event, data) in enumerate(events):
            row = {
                "schema": 1,
                "sequence": i,
                "previous_sha256": prev,
                "timestamp_utc": "historical fixture",
                "event": event,
                "data": data,
            }
            prev = receipt.digest(receipt.canonical(row))
            row["event_sha256"] = prev
            out.write(json.dumps(row) + "\n")
    result = receipt.inspect_journal(old, prev)
    assert result["legacy_historical_only"] is True
    assert result["checkpoint_recorded"] is True
    assert result["checkpoint_verified"] is False
    with pytest.raises(ValueError, match="legacy"):
        receipt.reconcile_checkpoint(root, lease, old, prev)
    with pytest.raises(ValueError, match="schema"):
        receipt.append_event(
            old,
            "REPORT_OBSERVED",
            {"channel": "chat", "observation": "seen", "delivery_confirmed": False},
        )
