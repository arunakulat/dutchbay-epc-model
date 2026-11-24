"""Exercise interruption preservation and reconciliation with real Git state."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_interruption_recovery as recovery


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def interrupted(tmp_path: Path) -> tuple[Path, dict, Path]:
    root = tmp_path / "synthetic repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / "a.txt").write_text("base\n")
    (root / "other.txt").write_text("untouched\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "switch", "-c", "feat/fixture")
    lease = {
        **ready.identity(root),
        "lease_id": "fixture",
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "allowlist": ["a.txt", "new.txt"],
    }
    (root / "a.txt").write_text("staged\n")
    git(root, "add", "a.txt")
    (root / "a.txt").write_text("working\n")
    (root / "new.txt").write_text("untracked\n")
    return root, lease, tmp_path / "observation"


def evidence() -> dict:
    return {
        "coordinator": "fixture coordinator",
        "ownership_reference": "fixture lease review",
        "stop_request_reference": "fixture stop",
        "prior_worker_disposition": "ACKNOWLEDGED_STOP",
        "stop_proof_reference": "fixture acknowledgement",
        "platform_restriction_pending": False,
    }


def test_preserves_mixed_index_working_and_untracked_bytes(interrupted: tuple) -> None:
    root, lease, output = interrupted
    before = recovery.state(root)
    data = recovery.capture(root, lease, output, preserve_bytes=True)
    assert data["stable_observation"] is True
    assert recovery.state(root) == before
    assert (
        output / data["preserved"]["a.txt"]["index"]["file"]
    ).read_text() == "staged\n"
    assert (
        output / data["preserved"]["a.txt"]["working"]["file"]
    ).read_text() == "working\n"
    assert (
        output / data["preserved"]["new.txt"]["working"]["file"]
    ).read_text() == "untracked\n"
    assert data["writer_authorized"] is False
    obs = output / "observation.json"
    result = recovery.assess(
        root, dict(lease, state="REVOKED"), obs, ready.digest(obs), evidence()
    )
    assert result["fresh_lease_required"] is True
    assert result["writer_authorized"] is False
    assert result["evidence_authenticated"] is False


def test_default_hash_only_and_unexpected_path_not_copied(interrupted: tuple) -> None:
    root, lease, output = interrupted
    assert recovery.capture(root, lease, output)["preserved"] == {}
    (root / "other.txt").write_text("out of scope\n")
    data = recovery.capture(root, lease, output.with_name("other"), preserve_bytes=True)
    assert data["unexpected_paths"] == ["other.txt"]
    assert data["preserved"] == {}
    assert (root / "other.txt").read_text() == "out of scope\n"


@pytest.mark.parametrize(
    "defect",
    [
        "not_revoked",
        "changed_state",
        "missing_stop",
        "restriction",
        "bad_digest",
        "bad_blob",
        "wrong_worktree",
    ],
)
def test_recovery_rejects_unsafe_resume(interrupted: tuple, defect: str) -> None:
    root, lease, output = interrupted
    data = recovery.capture(root, lease, output, preserve_bytes=True)
    obs = output / "observation.json"
    tip = ready.digest(obs)
    prior = dict(lease, state="REVOKED")
    proof = evidence()
    if defect == "not_revoked":
        prior["state"] = "PATCH_APPLIED"
    elif defect == "changed_state":
        (root / "a.txt").write_text("drift\n")
    elif defect == "missing_stop":
        proof["stop_proof_reference"] = ""
    elif defect == "restriction":
        proof["platform_restriction_pending"] = True
    elif defect == "bad_digest":
        tip = "0" * 64
    elif defect == "bad_blob":
        (output / data["preserved"]["a.txt"]["working"]["file"]).write_text("altered\n")
    else:
        prior["worktree"] = str(root.parent)
    with pytest.raises(ValueError):
        recovery.assess(root, prior, obs, tip, proof)


def test_output_inside_checkout_or_existing_refused(interrupted: tuple) -> None:
    root, lease, output = interrupted
    with pytest.raises(ValueError):
        recovery.capture(root, lease, root / "evidence")
    recovery.capture(root, lease, output)
    with pytest.raises(FileExistsError):
        recovery.capture(root, lease, output)
