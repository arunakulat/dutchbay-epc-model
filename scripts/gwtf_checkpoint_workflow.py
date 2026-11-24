"""Coordinator-facing v2 receipt lifecycle; never stage, commit, push or merge.

All commands, check exits and logs are observations supplied by the coordinator.
Every journal mutation after start requires a separately retained prior tip.
The CLI does not authenticate execution or appoint or authorize any writer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING and __package__:
    from . import gwtf_checkpoint_readiness as ready
    from . import gwtf_checkpoint_receipt as receipt
else:
    import gwtf_checkpoint_readiness as ready
    import gwtf_checkpoint_receipt as receipt


def read_object(path: Path) -> dict[str, Any]:
    path = receipt.safe_external(path)
    if not path.is_file():
        raise ValueError("input must be a regular external file")
    value = json.loads(ready.read_regular(path))
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def execute_check(args: argparse.Namespace, journal: Path) -> dict[str, Any]:
    """Observe one planned test subprocess; no staging or commit authority.

    The independently retained subject and journal tips are inputs, not proof
    of custody. Tests themselves execute candidate code. This is not a sandbox,
    and ordinary caller-supplied observations remain unauthenticated.
    """
    root = args.worktree.resolve()
    lease = read_object(args.lease)
    start = receipt.start_data(lease)
    subject = start["subject"]
    receipt.require(
        receipt.command_contract_bound(subject)
        and start["subject_sha256"] == args.expected_subject,
        "externally retained bound subject required",
    )
    rows = receipt.parse_rows(ready.read_regular(journal).decode())
    receipt.require(
        bool(rows)
        and rows[0]["data"] == start
        and receipt.validate_chain(rows, journal.parent) == args.expected_tip,
        "journal subject or tip mismatch",
    )
    receipt.require(
        all(row["event"] in {"STARTED", "CHECK_OBSERVED"} for row in rows),
        "execution already completed",
    )
    checks = [row["data"] for row in rows[1:]]
    order = receipt.ordered_checks(subject)
    cid = args.check_id
    receipt.require(
        len(checks) < len(order)
        and cid == order[len(checks)]
        and all(row["exit_code"] == 0 for row in checks),
        "not next planned check or prior failure",
    )
    receipt.require(
        cid.startswith("types:") or cid == "regression",
        "only type and regression checks may execute",
    )
    planned = subject["command_contract"]["checks"][len(checks)]
    cmd = planned["command"]
    env = ready.hook_environment(root)
    receipt.verify_contract_runtime(root, subject)
    before = ready.verify_candidate(root, lease)
    plan = None
    if cid.startswith("types:"):
        plan = next(item for item in subject["type_plan"] if item["check_id"] == cid)
        receipt.require(
            sys.version == plan["python_version"]
            and ready.digest(root / "mypy.ini") == plan["config_sha256"]
            and subprocess.check_output(
                [sys.executable, "-I", "-m", "mypy", "--version"],
                cwd=root,
                env=env,
                text=True,
            ).strip()
            == plan["mypy_version"],
            "type runtime or configuration drift",
        )
    else:
        # Independently approved pytest arguments may execute candidate code.
        # The exact Git diff command is retained for synthetic fixture checks.
        receipt.require(
            cmd[:3] == [sys.executable, "-m", "pytest"]
            or cmd == ready.git_command("diff", "--check"),
            "unsupported regression command family",
        )
        if cmd[:3] == [sys.executable, "-m", "pytest"]:
            # Explicit governed candidate imports for project tests, not for
            # the externally pinned verifier or ordinary hooks.
            env["PYTHONPATH"] = str(root)
    log = receipt.safe_external(journal.parent / planned["log_name"])
    sidecar = receipt.safe_external(log.with_name(log.name + ".execution.json"))
    receipt.require(
        not sidecar.exists() and not sidecar.is_symlink(),
        "execution evidence already exists",
    )
    started = datetime.now(timezone.utc).isoformat()
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        result = subprocess.run(
            cmd, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False
        )
        stream.flush()
        os.fsync(stream.fileno())
    finished = datetime.now(timezone.utc).isoformat()
    receipt.verify_contract_runtime(root, subject)
    receipt.require(
        ready.verify_candidate(root, lease) == before,
        "candidate drift during execution; preserve log",
    )
    if plan is not None:
        receipt.require(
            ready.digest(root / "mypy.ini") == plan["config_sha256"],
            "type configuration drift during execution",
        )
    observation = {
        **planned,
        "subject_sha256": start["subject_sha256"],
        "exit_code": result.returncode,
        "log_sha256": ready.digest(log),
    }
    if plan is not None:
        observation["type_evidence"] = plan
    evidence = {
        "schema": 1,
        "observation": observation,
        "worktree": str(root),
        "prior_tip": args.expected_tip,
        "started_utc": started,
        "finished_utc": finished,
        "candidate_state_unchanged": True,
        "execution_authenticated": False,
    }
    fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(receipt.canonical(evidence) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    if receipt.observed_execution_required(subject):
        observation["execution_observation_sha256"] = ready.digest(sidecar)
    tip = receipt._append_event(
        journal, "CHECK_OBSERVED", observation, args.expected_tip
    )
    return {
        "tip_sha256": tip,
        "check_id": cid,
        "observed_exit_code": result.returncode,
        "execution_observation_sha256": ready.digest(sidecar),
        "checkpoint_verified": False,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    journal = receipt.safe_external(args.journal)
    action = args.action
    if action == "inspect":
        return receipt.inspect_journal(journal, args.expected_tip)
    if action == "start":
        lease = read_object(args.lease)
        ready.verify_candidate(args.worktree.resolve(), lease)
        start = receipt.start_data(lease)
        receipt.verify_contract_runtime(args.worktree.resolve(), start["subject"])
        tip = receipt.append_event(journal, "STARTED", start)
        return {
            "tip_sha256": tip,
            "subject_sha256": start["subject_sha256"],
            "required_checks": start["required_checks"],
            "command_contract_bound": receipt.command_contract_bound(start["subject"]),
            "type_commands": {
                p["check_id"]: receipt.type_command(p)
                for p in start["subject"]["type_plan"]
            },
            "checkpoint_verified": False,
        }
    tip = args.expected_tip
    receipt.require(receipt.hex_value(tip), "externally retained prior tip required")
    if action == "execute":
        return execute_check(args, journal)
    if action in {"record", "verify"}:
        lease = read_object(args.lease)
        if action == "record":
            new_tip = receipt.record_checkpoint(args.worktree, lease, journal, tip)
            return {
                "tip_sha256": new_tip,
                "checkpoint_recorded": True,
                "checkpoint_verified": False,
            }
        proof = receipt.reconcile_checkpoint(args.worktree, lease, journal, tip)
        return {"tip_sha256": tip, "git_object_comparison_passed": True, "proof": proof}
    if action == "observe":
        data = read_object(args.observation)
        receipt.require(
            set(data)
            in (
                {
                    "check_id",
                    "subject_sha256",
                    "command",
                    "exit_code",
                    "log_name",
                    "log_sha256",
                },
                {
                    "check_id",
                    "subject_sha256",
                    "command",
                    "exit_code",
                    "log_name",
                    "log_sha256",
                    "type_evidence",
                },
            ),
            "invalid check observation fields",
        )
        event = "CHECK_OBSERVED"
    elif action == "complete":
        data = {"exit_code": args.exit_code}
        event = "EXECUTION_COMPLETED"
    else:
        data = {
            "channel": args.channel,
            "observation": args.observation,
            "delivery_confirmed": False,
        }
        event = "REPORT_OBSERVED"
    new_tip = receipt._append_event(journal, event, data, tip)
    return {
        "tip_sha256": new_tip,
        "event_recorded": event,
        "checkpoint_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("start", "record", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--worktree", type=Path, required=True)
        command.add_argument("--lease", type=Path, required=True)
        if name != "start":
            command.add_argument("--expected-tip", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--worktree", type=Path, required=True)
    execute.add_argument("--lease", type=Path, required=True)
    execute.add_argument("--expected-tip", required=True)
    execute.add_argument("--expected-subject", required=True)
    execute.add_argument("--check-id", required=True)
    for name in ("observe", "complete", "report", "inspect"):
        command = sub.add_parser(name)
        command.add_argument("--expected-tip", required=name != "inspect")
        if name == "observe":
            command.add_argument("--observation", type=Path, required=True)
        elif name == "complete":
            command.add_argument("--exit-code", type=int, required=True)
        elif name == "report":
            command.add_argument(
                "--channel", choices=["operator", "chat", "issue"], required=True
            )
            command.add_argument(
                "--observation", choices=["emitted", "observed"], required=True
            )
    try:
        result = run(parser.parse_args())
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ready.ReadinessError,
        subprocess.SubprocessError,
    ):
        print(
            "STOP: checkpoint workflow refused; preserve evidence and reconcile",
            file=sys.stderr,
        )
        return 1
    result.update(
        execution_authenticated=False,
        writer_authorized=False,
        independent_review_complete=False,
        merge_authorized=False,
        delivery_confirmed=False,
    )
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get("observed_exit_code", 0) != 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
