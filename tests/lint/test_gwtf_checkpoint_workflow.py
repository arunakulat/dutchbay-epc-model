"""Real subprocess coordinator workflow; no implicit Git mutation."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import gwtf_checkpoint_readiness as ready
from scripts import gwtf_checkpoint_receipt as receipt

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts/gwtf_checkpoint_workflow.py"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.mark.parametrize(
    "external", [False, True], ids=["direct-diagnostic", "external-fixture-pin"]
)
def test_anchored_cli_lifecycle(tmp_path: Path, external: bool) -> None:
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
    scope = [path.name]
    bundle = tmp_path.resolve() / "review-fixture-bundle"
    pin = ""
    marker = root / "shadow-ran"
    if external:
        # This test uses a self-issued synthetic fixture pin, not an independent
        # reviewer approval or operational custody claim.
        bundle.mkdir(mode=0o700)
        names = (
            "gwtf_trusted_verifier.py",
            "gwtf_checkpoint_readiness.py",
            "gwtf_checkpoint_receipt.py",
            "gwtf_checkpoint_workflow.py",
            "gwtf_interruption_recovery.py",
            "gwtf_incident.py",
        )
        for name in names:
            shutil.copyfile(ROOT / "scripts" / name, bundle / name)
            (bundle / name).chmod(0o600)
        manifest = bundle / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "reviewed_commit": "a" * 40,
                    "files": {name: ready.digest(bundle / name) for name in names},
                }
            )
        )
        manifest.chmod(0o600)
        pin = ready.digest(manifest)
        for name in ("gwtf_checkpoint_readiness.py", "pre_commit.py"):
            (root / name).write_text(
                "from pathlib import Path\nPath('shadow-ran').touch()\n"
                "raise RuntimeError('candidate shadow')\n"
            )
            scope.append(name)

    def verifier_command(entry: str, *args: str) -> list[str]:
        if external:
            return [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(bundle / "gwtf_trusted_verifier.py"),
                "--bundle",
                str(bundle),
                "--manifest-sha256",
                pin,
                entry,
                *args,
            ]
        return [sys.executable, "-B", str(ROOT / "scripts" / (entry + ".py")), *args]

    # The inherited path is deliberately hostile in the external fixture.
    # It must not replace any module in the pinned verifier closure.
    env = dict(os.environ, PYTHONPATH=str(root)) if external else None
    lease: dict[str, Any] = {
        **ready.identity(root),
        "lease_id": "fixture",
        "worktree": str(root),
        "state": "PATCH_APPLIED",
        "holder": "fixture",
        "coordinator": "fixture",
        "allowlist": scope,
        "candidate_sha256": {name: ready.digest(root / name) for name in scope},
        "candidate_modes": {name: ready.git_mode(root / name) for name in scope},
        "type_plan": [
            {
                "check_id": "types:strict",
                "profile": "strict",
                "scope": scope,
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
    j = tmp_path / "journal.jsonl"
    common = ["--worktree", str(root), "--lease", str(lp)]
    if external:
        planned = [
            (
                "readiness",
                verifier_command(
                    "gwtf_checkpoint_readiness",
                    *common,
                    "--receipt",
                    str(tmp_path / "readiness.jsonl"),
                ),
                "readiness.jsonl",
            ),
            ("types:strict", receipt.type_command(lease["type_plan"][0]), "types.log"),
            ("regression", ready.git_command("diff", "--check"), "regression.log"),
            (
                "staged",
                verifier_command(
                    "gwtf_checkpoint_readiness",
                    *common,
                    "--receipt",
                    str(tmp_path / "staged.json"),
                    "--verify-staged",
                ),
                "staged.json",
            ),
            ("commit", ready.git_command("commit", "-m", "candidate"), "commit.log"),
        ]
        lease["command_contract"] = {
            "interpreter": sys.executable,
            "hook_config_sha256": ready.digest(root / ready.CONFIG),
            "observed_execution_worktree": str(root.resolve()),
            "checks": [
                {"check_id": cid, "command": argv, "log_name": log}
                for cid, argv, log in planned
            ],
        }
    lp.write_text(json.dumps(lease))

    def call(*args: str, ok: bool = True) -> dict[str, Any]:
        before = ready.identity(root), ready.snapshot(root)
        result = subprocess.run(
            verifier_command("gwtf_checkpoint_workflow", "--journal", str(j), *args),
            cwd=root,
            env=env,
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
    assert start["command_contract_bound"] is external
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
    cmd = verifier_command("gwtf_checkpoint_readiness", *common, "--receipt", str(log))
    result = subprocess.run(cmd, cwd=root, env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert b"READY_FOR_FINAL_BYTE_TESTS" in result.stdout
    observe("readiness", cmd, log, result.returncode)
    if external:

        def execute(
            cid: str, *, pin_value: str = subject, ok: bool = True
        ) -> dict[str, Any]:
            return call(
                "execute",
                *common,
                "--expected-tip",
                tip,
                "--expected-subject",
                pin_value,
                "--check-id",
                cid,
                ok=ok,
            )

        original = j.read_bytes()
        execute("types:strict", pin_value="0" * 64, ok=False)
        execute("regression", ok=False)
        execute("commit", ok=False)
        assert j.read_bytes() == original
        log = tmp_path / "types.log"
        log.write_text("existing evidence")
        execute("types:strict", ok=False)
        assert log.read_text() == "existing evidence"
        log.unlink()
        for cid, name in (
            ("types:strict", "types.log"),
            ("regression", "regression.log"),
        ):
            observation = execute(cid)
            assert observation["observed_exit_code"] == 0
            sidecar = tmp_path / (name + ".execution.json")
            assert observation["execution_observation_sha256"] == ready.digest(sidecar)
            evidence = json.loads(sidecar.read_text())
            assert evidence["observation"]["log_sha256"] == ready.digest(
                tmp_path / name
            )
            assert evidence["prior_tip"] == tip
            assert evidence["candidate_state_unchanged"] is True
            assert evidence["execution_authenticated"] is False
            tip = observation["tip_sha256"]
            assert receipt.parse_rows(j.read_text())[-1]["data"][
                "execution_observation_sha256"
            ] == ready.digest(sidecar)
            assert (
                call("inspect", "--expected-tip", tip)["observed_execution_required"]
                is True
            )
            original_sidecar = sidecar.read_bytes()
            sidecar.write_bytes(original_sidecar + b" ")
            call("inspect", "--expected-tip", tip, ok=False)
            sidecar.write_bytes(original_sidecar)
            sidecar.unlink()
            call("inspect", "--expected-tip", tip, ok=False)
            sidecar.write_bytes(original_sidecar)
            execute(cid, ok=False)
    else:
        cmd = start["type_commands"]["types:strict"]
        result = subprocess.run(cmd, cwd=root, capture_output=True)
        log = tmp_path / "types.log"
        log.write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0
        observe(
            "types:strict",
            cmd,
            log,
            result.returncode,
            type_evidence=lease["type_plan"][0],
        )
        cmd = ready.git_command("diff", "--check")
        result = subprocess.run(cmd, cwd=root, capture_output=True)
        log = tmp_path / "regression.log"
        log.write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0
        observe("regression", cmd, log, result.returncode)
    git(root, "add", *scope)
    log = tmp_path / "staged.json"
    cmd = verifier_command(
        "gwtf_checkpoint_readiness", *common, "--receipt", str(log), "--verify-staged"
    )
    result = subprocess.run(cmd, cwd=root, env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    observe("staged", cmd, log, result.returncode)
    cmd = ready.git_command("commit", "-m", "candidate")
    result = subprocess.run(
        cmd, cwd=root, env=ready.hook_environment(root), capture_output=True
    )
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
    inspected = call("inspect", "--expected-tip", tip)
    assert inspected["checkpoint_verified"] is False
    assert inspected["command_contract_bound"] is external
    assert receipt.parse_rows(j.read_text())[0]["schema"] == (
        receipt.BOUND_SCHEMA if external else receipt.SCHEMA
    )
    tip = call(
        "report", "--expected-tip", tip, "--channel", "chat", "--observation", "emitted"
    )["tip_sha256"]
    assert call("verify", *common, "--expected-tip", tip)["delivery_confirmed"] is False
    assert not marker.exists()
    historical_commit = ready.git_text(root, "rev-parse", "HEAD")
    hist = [
        "--worktree",
        str(root),
        "--commit",
        historical_commit,
        "--expected-tip",
        tip,
    ]
    original_journal = j.read_bytes()
    assert call("verify-historical", *hist)["historical_git_object_comparison_passed"]
    call(
        "verify-historical",
        "--worktree",
        str(root),
        "--commit",
        "HEAD",
        "--expected-tip",
        tip,
        ok=False,
    )
    call(
        "verify-historical",
        "--worktree",
        str(root),
        "--commit",
        historical_commit,
        "--expected-tip",
        "0" * 64,
        ok=False,
    )
    # Advance the current branch and remote-tracking base, then dirty the
    # current configuration. Historical comparison must use recorded objects.
    subprocess.run(
        ready.git_command("commit", "--allow-empty", "-m", "later checkpoint"),
        cwd=root,
        env=ready.hook_environment(root),
        check=True,
        capture_output=True,
    )
    later = ready.git_text(root, "rev-parse", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", later)
    (root / "mypy.ini").write_text("[mypy]\n")
    call("verify", *common, "--expected-tip", tip, ok=False)
    historical = call("verify-historical", *hist)
    assert historical["historical_git_object_comparison_passed"] is True
    assert historical["live_qualification"] is False
    assert historical["checkpoint_verified"] is False
    assert historical["execution_authenticated"] is False
    assert historical["candidate_objects_verified"] == len(scope)
    assert j.read_bytes() == original_journal
    call(
        "verify-historical",
        "--worktree",
        str(root),
        "--commit",
        later,
        "--expected-tip",
        tip,
        ok=False,
    )
    if external:
        # Prove the actual record/verify path refuses a changed bundle even
        # when the journal and candidate remain unchanged.
        module = bundle / "gwtf_checkpoint_receipt.py"
        module.write_text("raise RuntimeError('substitute')\n")
        before = j.read_bytes()
        call("verify", *common, "--expected-tip", tip, ok=False)
        assert j.read_bytes() == before
        assert not marker.exists()


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
