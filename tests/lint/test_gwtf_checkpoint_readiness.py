"""Behavioral controls for the G2 readiness helper in disposable Git repositories."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import gwtf_checkpoint_readiness as ready


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def candidate(tmp_path: Path) -> tuple[Path, dict, Path]:
    root = tmp_path / "fixture repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / ready.CONFIG).write_text(
        f'repos:\n- repo: local\n  hooks:\n  - id: fixture-check\n    name: fixture check\n    entry: {json.dumps(shlex.quote(sys.executable) + " fixture_hook.py")}\n    language: system\n    pass_filenames: false\n'
    )
    (root / "fixture_hook.py").write_text(
        "from pathlib import Path\nassert Path('candidate.txt').exists()\n"
    )
    (root / "candidate.txt").write_text("base\n")
    (root / "unrelated.txt").write_text("base\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "fixture baseline")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "switch", "-c", "feat/fixture")
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    (root / "candidate.txt").write_text("candidate\n")
    lease = {
        **ready.identity(root),
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "lease_id": "fixture",
        "holder": "fixture writer",
        "coordinator": "fixture coordinator",
        "allowlist": ["candidate.txt"],
        "candidate_sha256": {"candidate.txt": ready.digest(root / "candidate.txt")},
    }
    return root, lease, tmp_path / "receipt.jsonl"


def events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_real_pinned_hook_two_pass_readiness(candidate: tuple) -> None:
    root, lease, receipt = candidate
    before = ready.identity(root)
    ready.run_readiness(root, lease, receipt)
    data = events(receipt)
    assert [x["state"] for x in data] == [
        "STARTED",
        "PREFLIGHTED",
        "HOOK_PASS_OBSERVED",
        "HOOK_PASS_OBSERVED",
        "READY_FOR_FINAL_BYTE_TESTS",
    ]
    assert ready.identity(root) == before
    assert all(x["exit_code"] == 0 for x in data if x["state"] == "HOOK_PASS_OBSERVED")
    assert data[-1]["checkpoint_verified"] is False
    assert data[-1]["tests_verified"] is False
    assert ready.changed(root) == {"candidate.txt"}


@pytest.mark.parametrize(
    "defect",
    [
        "protected",
        "head",
        "expired",
        "scope",
        "bytes",
        "missing_hook",
        "skip",
        "config",
        "untracked",
    ],
)
def test_preflight_rejects_before_hook(
    candidate: tuple, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    root, lease, receipt = candidate
    if defect == "protected":
        git(root, "switch", "main")
        lease["branch"] = "main"
    elif defect == "head":
        lease["head"] = "0" * 40
    elif defect == "expired":
        lease["state"] = "REVOKED"
    elif defect == "scope":
        lease["allowlist"].append("unrelated.txt")
    elif defect == "bytes":
        (root / "candidate.txt").write_text("changed\n")
    elif defect == "missing_hook":
        (root / ".git/hooks/pre-commit").unlink()
    elif defect == "skip":
        monkeypatch.setenv("SKIP", "fixture-check")
    elif defect == "config":
        (root / ready.CONFIG).write_text("repos: []\n")
    else:
        (root / "extra.txt").write_text("unexpected\n")
    with pytest.raises(ready.ReadinessError):
        ready.run_readiness(root, lease, receipt)
    assert events(receipt)[-1]["state"] == "STOPPED_RECONCILIATION_REQUIRED"
    assert not any(x["state"] == "HOOK_PASS_OBSERVED" for x in events(receipt))


@pytest.mark.parametrize("effect", ["candidate", "unrelated", "failure", "index"])
def test_hook_effect_stops_and_preserves_state(candidate: tuple, effect: str) -> None:
    root, lease, receipt = candidate
    # Change the synthetic baseline hook as a new committed fixture, not the candidate.
    code = {
        "candidate": "from pathlib import Path\nPath('candidate.txt').write_text('formatted\\n')\n",
        "unrelated": "from pathlib import Path\nPath('unrelated.txt').write_text('drift\\n')\n",
        "failure": "raise SystemExit(2)\n",
        "index": "import subprocess\nsubprocess.run(['git','add','candidate.txt'],check=True)\n",
    }[effect]
    (root / "fixture_hook.py").write_text(code)
    git(root, "add", "fixture_hook.py")
    # The fixture hook would mutate the candidate at commit time, so this test
    # models the hook result directly using the real pre-commit invocation below.
    # Keep the fixture's changed hook in the allowlist, no baseline commit needed.
    lease["allowlist"].append("fixture_hook.py")
    lease["candidate_sha256"]["fixture_hook.py"] = ready.digest(
        root / "fixture_hook.py"
    )
    with pytest.raises(ready.ReadinessError):
        ready.run_readiness(root, lease, receipt)
    data = events(receipt)
    assert data[-1]["state"] == "STOPPED_RECONCILIATION_REQUIRED"
    assert sum(x["state"] == "HOOK_PASS_OBSERVED" for x in data) == 1
    if effect == "candidate":
        assert (root / "candidate.txt").read_text() == "formatted\n"
    elif effect == "unrelated":
        assert (root / "unrelated.txt").read_text() == "drift\n"
    elif effect == "index":
        assert ready.identity(root)["index_sha256"] != lease["index_sha256"]


def test_receipt_is_exclusive_and_external(candidate: tuple) -> None:
    root, lease, receipt = candidate
    receipt.write_text("prior evidence\n")
    with pytest.raises(FileExistsError):
        ready.run_readiness(root, lease, receipt)
    assert receipt.read_text() == "prior evidence\n"
    with pytest.raises(ready.ReadinessError):
        ready.run_readiness(root, lease, root / "receipt.jsonl")
