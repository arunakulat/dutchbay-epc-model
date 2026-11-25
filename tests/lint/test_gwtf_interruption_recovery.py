"""Exercise interruption preservation and reconciliation with real Git state."""

from __future__ import annotations

import json
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
    assert data["unexpected_path_count"] == 1
    assert (
        "other.txt" not in (output.with_name("other") / "observation.json").read_text()
    )
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


@pytest.mark.parametrize(
    "field", ["head", "tree", "base", "branch", "index_sha256", "allowlist"]
)
def test_same_id_different_revoked_lease_refused(
    interrupted: tuple, field: str
) -> None:
    root, lease, output = interrupted
    recovery.capture(root, lease, output, preserve_bytes=True)
    prior = dict(lease, state="REVOKED")
    prior[field] = (
        ["a.txt"]
        if field == "allowlist"
        else (
            "feat/other"
            if field == "branch"
            else "0" * (64 if field == "index_sha256" else 40)
        )
    )
    obs = output / "observation.json"
    with pytest.raises(ValueError, match="lease binding mismatch"):
        recovery.assess(root, prior, obs, ready.digest(obs), evidence())


@pytest.mark.parametrize(
    "defect", ["forged_flags", "omitted_blob", "rehashed_blob", "old_schema"]
)
def test_rederive_observation_and_preserved_bytes(
    interrupted: tuple, defect: str
) -> None:
    root, lease, output = interrupted
    data = recovery.capture(root, lease, output, preserve_bytes=True)
    obs = output / "observation.json"
    if defect == "forged_flags":
        (root / "other.txt").write_text("changed outside scope")
    elif defect == "omitted_blob":
        del data["preserved"]["a.txt"]["working"]
    elif defect == "rehashed_blob":
        blob = data["preserved"]["a.txt"]["working"]
        (output / blob["file"]).write_text("changed")
        blob["sha256"] = ready.digest(output / blob["file"])
    else:
        data["schema"] = 1
    obs.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        recovery.assess(
            root, dict(lease, state="REVOKED"), obs, ready.digest(obs), evidence()
        )


def test_capture_minimizes_outside_scope_evidence(interrupted: tuple) -> None:
    root, lease, output = interrupted
    secret = root / "private-fixture.txt"
    secret.write_text("synthetic confidential material")
    data = recovery.capture(root, lease, output, preserve_bytes=True)
    raw = (output / "observation.json").read_text()
    assert data["unexpected_path_count"] == 1
    assert data["preserved"] == {}
    assert secret.name not in raw
    assert ready.digest(secret) not in raw
    assert "synthetic confidential material" not in raw
    assert "snapshot" not in data["before"]
    assert "status_hex" not in data["before"]


def test_regular_read_refuses_symlink_and_fifo(tmp_path: Path) -> None:
    import os

    target = tmp_path / "target"
    target.write_text("fixture")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        recovery.read_regular(link)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular evidence"):
        recovery.read_regular(fifo)
