"""G3: durable, hash-linked local receipts; no write authority or delivery claim.

A hash chain detects accidental alteration against a trusted anchor. It is not a
signature and cannot authenticate an author or prove a supplied command ran.
The coordinator retains independent evidence and the final chain digest.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING and __package__:
    from . import gwtf_checkpoint_readiness as ready
else:
    import gwtf_checkpoint_readiness as ready

SCHEMA = 1
ZERO = "0" * 64
HEX = re.compile(r"[0-9a-f]{64}\Z")
EVENTS = {
    "STARTED",
    "CHECK_OBSERVED",
    "EXECUTION_COMPLETED",
    "CHECKPOINT_VERIFIED",
    "REPORT_OBSERVED",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def canonical(data: Any) -> bytes:
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_external(path: Path) -> Path:
    path = path.absolute()
    require(path.parent.is_dir(), "receipt parent missing")
    require(
        not any(p.is_symlink() for p in (path, *path.parents)), "symlink receipt path"
    )
    require(
        not any((p / ".git").exists() for p in path.parents),
        "receipt must be outside Git worktrees",
    )
    return path


def evidence_file(directory: Path, name: str) -> Path:
    require(
        isinstance(name, str)
        and Path(name).name == name
        and name not in {"", ".", ".."},
        "unsafe evidence name",
    )
    p = directory / name
    require(
        p.is_file() and not p.is_symlink(),
        "evidence must be a regular non-symlink file",
    )
    return p


def check_record(record: dict, directory: Path) -> None:
    require(
        isinstance(record.get("check_id"), str) and bool(record["check_id"]),
        "missing check identity",
    )
    command = record.get("command")
    require(
        isinstance(command, list)
        and bool(command)
        and all(isinstance(x, str) and x for x in command),
        "missing command evidence",
    )
    require(type(record.get("exit_code")) is int, "missing observed exit code")
    require(
        isinstance(record.get("log_sha256"), str)
        and bool(HEX.fullmatch(record["log_sha256"])),
        "invalid log digest",
    )
    require(
        ready.digest(evidence_file(directory, record["log_name"]))
        == record["log_sha256"],
        "check log digest mismatch",
    )


def validate_chain(rows: list[dict], directory: Path) -> str:
    prev = ZERO
    seen: set[str] = set()
    completed = False
    checkpoint = False
    reported = False
    for index, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k != "event_sha256"}
        require(
            row.get("schema") == SCHEMA
            and row.get("sequence") == index
            and row.get("previous_sha256") == prev,
            "journal sequence or previous hash mismatch",
        )
        require(
            row.get("event_sha256") == digest(canonical(body)),
            "journal event hash mismatch",
        )
        state = row.get("event")
        data = row.get("data")
        if (
            not isinstance(state, str)
            or state not in EVENTS
            or not isinstance(data, dict)
        ):
            raise ValueError("invalid journal event")
        if state == "STARTED":
            require(
                index == 0
                and bool(data.get("lease_id"))
                and isinstance(data.get("required_checks"), list),
                "invalid journal start",
            )
            required = data["required_checks"]
            require(
                bool(required)
                and all(isinstance(x, str) and x for x in required)
                and len(set(required)) == len(required),
                "invalid required checks",
            )
        else:
            require(
                index > 0 and rows[0]["event"] == "STARTED", "journal start missing"
            )
            if state == "CHECK_OBSERVED":
                require(
                    not completed and data.get("check_id") not in seen,
                    "duplicate or late check",
                )
                require(
                    data.get("check_id") in rows[0]["data"]["required_checks"],
                    "unplanned check",
                )
                check_record(data, directory)
                seen.add(data["check_id"])
            elif state == "EXECUTION_COMPLETED":
                require(
                    not completed and type(data.get("exit_code")) is int,
                    "invalid execution completion",
                )
                completed = True
            elif state == "CHECKPOINT_VERIFIED":
                require(
                    completed and not checkpoint and rows[-1].get("event") != "STARTED",
                    "checkpoint ordering invalid",
                )
                require(
                    any(
                        x["event"] == "EXECUTION_COMPLETED"
                        and x["data"]["exit_code"] == 0
                        for x in rows[:index]
                    ),
                    "execution did not succeed",
                )
                require(
                    seen == set(rows[0]["data"]["required_checks"]),
                    "required check evidence missing",
                )
                require(
                    all(
                        x["data"]["exit_code"] == 0
                        for x in rows[:index]
                        if x["event"] == "CHECK_OBSERVED"
                    ),
                    "check failed",
                )
                require(
                    data.get("independent_review_complete") is False
                    and data.get("merge_authorized_by_receipt") is False,
                    "receipt cannot grant approval",
                )
                checkpoint = True
            elif state == "REPORT_OBSERVED":
                require(
                    completed
                    and not reported
                    and data.get("delivery_confirmed") is False,
                    "invalid reporting event or unsupported delivery claim",
                )
                require(
                    bool(data.get("channel")) and bool(data.get("observation")),
                    "missing reporting observation",
                )
                reported = True
        prev = row["event_sha256"]
    return prev


def parse_rows(raw: str) -> list[dict]:
    require(not raw or raw.endswith("\n"), "partial journal record")
    return [json.loads(line) for line in raw.splitlines()]


def append_event(path: Path, event: str, data: dict) -> str:
    path = safe_external(path)
    flags = os.O_RDWR | os.O_NOFOLLOW
    if event == "STARTED":
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "r+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        require(
            stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "invalid journal object"
        )
        rows = parse_rows(stream.read())
        prev = validate_chain(rows, path.parent)
        row = {
            "schema": SCHEMA,
            "sequence": len(rows),
            "previous_sha256": prev,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        event_digest = digest(canonical(row))
        row["event_sha256"] = event_digest
        validate_chain([*rows, row], path.parent)
        stream.seek(0, os.SEEK_END)
        stream.write(canonical(row).decode() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        return event_digest


def inspect_journal(path: Path, expected_tip: str | None = None) -> dict:
    path = safe_external(path)
    rows = parse_rows(path.read_text())
    require(bool(rows), "empty journal")
    tip = validate_chain(rows, path.parent)
    if expected_tip is not None:
        require(tip == expected_tip, "trusted journal tip mismatch")
    return {
        "tip_sha256": tip,
        "events": len(rows),
        "execution_completed": any(x["event"] == "EXECUTION_COMPLETED" for x in rows),
        "checkpoint_recorded": any(x["event"] == "CHECKPOINT_VERIFIED" for x in rows),
        "report_observed": any(x["event"] == "REPORT_OBSERVED" for x in rows),
        "delivery_confirmed": False,
        "independent_review_complete": False,
        "anchor_supplied": expected_tip is not None,
    }


def reconcile_checkpoint(root: Path, lease: dict, journal: Path) -> dict:
    """Independently check Git objects and bind the supplied check-log evidence.

    The journal must be externally preserved; the check receipts are observed
    claims and not independently executed by this function.
    """
    root = root.resolve()
    journal = safe_external(journal)
    rows = parse_rows(journal.read_text())
    validate_chain(rows, journal.parent)
    require(
        bool(rows) and rows[0]["data"]["lease_id"] == lease["lease_id"],
        "journal lease mismatch",
    )
    require(lease["state"] == "PATCH_APPLIED", "applied-patch lease required")
    require(Path(lease["worktree"]).resolve() == root, "lease worktree mismatch")
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "environment override present",
    )
    require(
        Path(ready.git_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "incorrect worktree",
    )
    ident = ready.identity(root)
    require(
        ident["branch"] == lease["branch"]
        and ident["branch"] not in {"", "main", "master"},
        "protected or wrong branch",
    )
    require(ident["base"] == lease["base"], "base mismatch")
    require(
        ready.git_text(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
        == [ident["head"], lease["head"]],
        "unexpected commit parent",
    )
    require(
        ready.git_text(root, "rev-parse", lease["head"] + "^{tree}") == lease["tree"],
        "parent tree mismatch",
    )
    require(not ready.git(root, "status", "--porcelain", "-z"), "worktree not clean")
    scope = lease["allowlist"]
    hashes = lease["candidate_sha256"]
    require(
        bool(scope) and len(set(scope)) == len(scope) and set(scope) == set(hashes),
        "invalid candidate scope",
    )
    require(
        ready.names(
            ready.git(
                root,
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "--no-renames",
                "-r",
                "-z",
                "HEAD",
            )
        )
        == set(scope),
        "committed scope mismatch",
    )
    for name in scope:
        path = ready.path_at(root, name)
        require(path.is_file() and not path.is_symlink(), "non-regular candidate")
        blob = ready.git(root, "show", "HEAD:" + name)
        require(
            digest(blob) == hashes[name] == ready.digest(path),
            "committed blob mismatch",
        )
    return {
        "lease_id": lease["lease_id"],
        "head": ident["head"],
        "tree": ident["tree"],
        "base": ident["base"],
        "candidate_sha256": hashes,
        "worktree_clean": True,
        "independent_review_complete": False,
        "merge_authorized_by_receipt": False,
        "limitations": "Object and evidence integrity only; no execution, signer, remote-state or notification authentication",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("--expected-tip")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect_journal(args.journal, args.expected_tip), indent=2))
    except (OSError, ValueError, KeyError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
