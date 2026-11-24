"""G3 behavioral receipts tests using real Git objects and hostile evidence."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_checkpoint_receipt as receipt


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def observed(tmp_path: Path) -> tuple[Path, Path, dict]:
    root = tmp_path / "synthetic repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / "a.txt").write_text("base\n")
    git(root, "add", "a.txt")
    git(root, "commit", "-m", "base")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "switch", "-c", "feat/fixture")
    lease = {
        **ready.identity(root),
        "lease_id": "fixture",
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "allowlist": ["a.txt"],
    }
    (root / "a.txt").write_text("candidate\n")
    lease["candidate_sha256"] = {"a.txt": ready.digest(root / "a.txt")}
    log = tmp_path / "check.log"
    result = subprocess.run(
        ["git", "diff", "--check"], cwd=root, capture_output=True, check=False
    )
    log.write_bytes(result.stdout + result.stderr)
    journal = tmp_path / "events.jsonl"
    receipt.append_event(
        journal, "STARTED", {"lease_id": "fixture", "required_checks": ["diff"]}
    )
    receipt.append_event(
        journal,
        "CHECK_OBSERVED",
        {
            "check_id": "diff",
            "command": ["git", "diff", "--check"],
            "exit_code": result.returncode,
            "log_name": log.name,
            "log_sha256": ready.digest(log),
        },
    )
    git(root, "add", "a.txt")
    git(root, "commit", "-m", "candidate")
    receipt.append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0})
    return root, journal, lease


def test_exact_object_and_reporting_states(observed: tuple) -> None:
    root, journal, lease = observed
    data = receipt.inspect_journal(journal)
    assert data["execution_completed"] is True
    assert data["report_observed"] is False
    assert data["checkpoint_recorded"] is False
    verified = receipt.reconcile_checkpoint(root, lease, journal)
    assert verified["head"] == ready.git_text(root, "rev-parse", "HEAD")
    tip = receipt.append_event(journal, "CHECKPOINT_VERIFIED", verified)
    assert receipt.inspect_journal(journal, tip)["checkpoint_recorded"] is True
    tip = receipt.append_event(
        journal,
        "REPORT_OBSERVED",
        {
            "channel": "operator transcript",
            "observation": "status emitted",
            "delivery_confirmed": False,
        },
    )
    data = receipt.inspect_journal(journal, tip)
    assert data["report_observed"] is True
    assert data["delivery_confirmed"] is False
    assert data["independent_review_complete"] is False


@pytest.mark.parametrize(
    "defect",
    ["wrong_parent", "wrong_blob", "wrong_scope", "dirty", "wrong_base", "wrong_lease"],
)
def test_git_reconciliation_rejects(observed: tuple, defect: str) -> None:
    root, journal, lease = observed
    if defect == "wrong_parent":
        lease["head"] = ready.git_text(root, "rev-parse", "HEAD")
    elif defect == "wrong_blob":
        lease["candidate_sha256"]["a.txt"] = "0" * 64
    elif defect == "wrong_scope":
        lease["allowlist"].append("b.txt")
        lease["candidate_sha256"]["b.txt"] = "0" * 64
    elif defect == "dirty":
        (root / "a.txt").write_text("drift\n")
    elif defect == "wrong_base":
        lease["base"] = "0" * 40
    else:
        lease["lease_id"] = "another"
    with pytest.raises(ValueError):
        receipt.reconcile_checkpoint(root, lease, journal)


@pytest.mark.parametrize(
    "defect", ["log", "chain", "partial", "tip", "delivery", "duplicate", "approval"]
)
def test_receipt_rejects_unsupported_evidence(observed: tuple, defect: str) -> None:
    root, journal, lease = observed
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
        verified = receipt.reconcile_checkpoint(root, lease, journal)
        verified["merge_authorized_by_receipt"] = True
        with pytest.raises(ValueError, match="approval"):
            receipt.append_event(journal, "CHECKPOINT_VERIFIED", verified)
        return
    with pytest.raises(ValueError):
        receipt.inspect_journal(journal)


def test_missing_required_check_blocks_checkpoint(tmp_path: Path) -> None:
    journal = tmp_path / "events.jsonl"
    receipt.append_event(
        journal, "STARTED", {"lease_id": "fixture", "required_checks": ["missing"]}
    )
    receipt.append_event(journal, "EXECUTION_COMPLETED", {"exit_code": 0})
    with pytest.raises(ValueError, match="required check evidence missing"):
        receipt.append_event(
            journal,
            "CHECKPOINT_VERIFIED",
            {
                "independent_review_complete": False,
                "merge_authorized_by_receipt": False,
            },
        )
