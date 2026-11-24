"""Real subprocess coordinator workflow; no implicit Git mutation."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import gwtf_checkpoint_readiness as ready

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/gwtf_checkpoint_workflow.py"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_anchored_cli_lifecycle(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Synthetic")
    git(root, "config", "user.email", "fixture@example.invalid")
    (root / ready.CONFIG).write_text(
        "repos:\n- repo: local\n  hooks:\n  - id: fixture\n    name: fixture\n    entry: "
        + json.dumps(shlex.quote(sys.executable) + " hook.py")
        + "\n    language: system\n    pass_filenames: false\n"
    )
    (root / "hook.py").write_text("pass\n")
    (root / "mypy.ini").write_text("[mypy]\n")
    path = root / "candidate.py"
    path.write_text("x = 1\n")
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
    path.write_text("x: int = 2\n")
    lease: dict[str, Any] = {
        **ready.identity(root),
        "lease_id": "fixture",
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "holder": "fixture",
        "coordinator": "fixture",
        "allowlist": [path.name],
        "candidate_sha256": {path.name: ready.digest(path)},
        "candidate_modes": {path.name: ready.git_mode(path)},
        "type_plan": [
            {
                "check_id": "types:strict",
                "profile": "strict",
                "scope": [path.name],
                "interpreter": sys.executable,
                "python_version": sys.version,
                "mypy_version": subprocess.check_output(
                    [sys.executable, "-I", "-m", "mypy", "--version"], text=True
                ).strip(),
                "config_sha256": ready.digest(root / "mypy.ini"),
            }
        ],
    }
    lp = tmp_path / "lease.json"
    lp.write_text(json.dumps(lease))
    j = tmp_path / "journal.jsonl"
    common = ["--worktree", str(root), "--lease", str(lp)]

    def call(*args: str, ok: bool = True) -> dict[str, Any]:
        before = ready.identity(root), ready.snapshot(root)
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "--journal", str(j), *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert (ready.identity(root), ready.snapshot(root)) == before
        if not ok:
            assert result.returncode != 0
            assert not result.stdout
            return {}
        assert result.returncode == 0, result.stderr
        data: dict[str, Any] = json.loads(result.stdout)
        assert data["writer_authorized"] is False
        assert data["merge_authorized"] is False
        assert data["execution_authenticated"] is False
        return data

    start = call("start", *common)
    tip = start["tip_sha256"]
    subject = start["subject_sha256"]
    call("start", *common, ok=False)
    call("record", *common, "--expected-tip", tip, ok=False)

    def observe(cid: str, cmd: list[str], log: Path, code: int, **extra: Any) -> None:
        nonlocal tip
        obs = tmp_path / ("obs-" + cid.replace(":", "-") + ".json")
        obs.write_text(
            json.dumps(
                {
                    "check_id": cid,
                    "subject_sha256": subject,
                    "command": cmd,
                    "exit_code": code,
                    "log_name": log.name,
                    "log_sha256": ready.digest(log),
                    **extra,
                }
            )
        )
        before = j.read_bytes()
        call("observe", "--expected-tip", "0" * 64, "--observation", str(obs), ok=False)
        assert j.read_bytes() == before
        tip = call("observe", "--expected-tip", tip, "--observation", str(obs))[
            "tip_sha256"
        ]

    log = tmp_path / "readiness.jsonl"
    ready.run_readiness(root, lease, log)
    observe("readiness", [sys.executable, "-B", "readiness"], log, 0)
    cmd = start["type_commands"]["types:strict"]
    result = subprocess.run(cmd, cwd=root, capture_output=True)
    log = tmp_path / "types.log"
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    observe(
        "types:strict", cmd, log, result.returncode, type_evidence=lease["type_plan"][0]
    )
    cmd = ["git", "diff", "--check"]
    result = subprocess.run(cmd, cwd=root, capture_output=True)
    log = tmp_path / "regression.log"
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    observe("regression", cmd, log, result.returncode)
    git(root, "add", path.name)
    log = tmp_path / "staged.json"
    log.write_text(json.dumps(ready.verify_staged(root, lease)))
    observe("staged", [sys.executable, "-B", "verify_staged"], log, 0)
    cmd = ["git", "commit", "-m", "candidate"]
    result = subprocess.run(cmd, cwd=root, capture_output=True)
    log = tmp_path / "commit.log"
    log.write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    observe("commit", cmd, log, result.returncode)
    tip = call("complete", "--expected-tip", tip, "--exit-code", "0")["tip_sha256"]
    call("verify", *common, "--expected-tip", tip, ok=False)
    pretip = tip
    tip = call("record", *common, "--expected-tip", pretip)["tip_sha256"]
    call("record", *common, "--expected-tip", pretip, ok=False)
    assert (
        call("verify", *common, "--expected-tip", tip)["git_object_comparison_passed"]
        is True
    )
    assert call("inspect", "--expected-tip", tip)["checkpoint_verified"] is False
    tip = call(
        "report", "--expected-tip", tip, "--channel", "chat", "--observation", "emitted"
    )["tip_sha256"]
    assert call("verify", *common, "--expected-tip", tip)["delivery_confirmed"] is False


@pytest.mark.parametrize(
    "args",
    [["complete", "--exit-code", "0"], ["record"], ["verify"], ["observe"], ["report"]],
)
def test_missing_anchor_or_arguments_refused(tmp_path: Path, args: list[str]) -> None:
    j = tmp_path / "missing.jsonl"
    result = subprocess.run(
        [sys.executable, "-B", str(CLI), "--journal", str(j), *args],
        capture_output=True,
    )
    assert result.returncode != 0
    assert not j.exists()
