"""Coordinator-facing v2 receipt lifecycle; never stage, commit, push or merge.

All commands, check exits and logs are observations supplied by the coordinator.
Every journal mutation after start requires a separately retained prior tip.
The CLI does not authenticate execution or appoint or authorize any writer.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    journal = receipt.safe_external(args.journal)
    action = args.action
    if action == "inspect":
        return receipt.inspect_journal(journal, args.expected_tip)
    if action == "start":
        lease = read_object(args.lease)
        ready.verify_candidate(args.worktree.resolve(), lease)
        start = receipt.start_data(lease)
        tip = receipt.append_event(journal, "STARTED", start)
        return {
            "tip_sha256": tip,
            "subject_sha256": start["subject_sha256"],
            "required_checks": start["required_checks"],
            "type_commands": {
                p["check_id"]: receipt.type_command(p)
                for p in start["subject"]["type_plan"]
            },
            "checkpoint_verified": False,
        }
    tip = args.expected_tip
    receipt.require(receipt.hex_value(tip), "externally retained prior tip required")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
