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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING and __package__:
    from . import gwtf_checkpoint_readiness as ready
else:
    import gwtf_checkpoint_readiness as ready

SCHEMA = 2
BOUND_SCHEMA = 3
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


def _validate_legacy_chain(rows: list[dict], directory: Path) -> str:
    prev = ZERO
    seen: set[str] = set()
    completed = False
    checkpoint = False
    reported = False
    for index, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k != "event_sha256"}
        require(
            row.get("schema") == 1
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


BASE_CHECKS = {"readiness", "regression", "staged", "commit"}
SUBJECT_FIELDS = {
    "lease_id",
    "branch",
    "parent_head",
    "parent_tree",
    "base",
    "initial_index_sha256",
    "candidate_sha256",
    "candidate_modes",
    "type_plan",
    "type_not_applicable_reason",
}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
TYPE_PROFILES = {
    "scripts": [
        "--ignore-missing-imports",
        "--allow-untyped-defs",
        "--allow-untyped-calls",
        "--allow-any-generics",
    ],
    "strict": [],
    # Test modules import operational scripts via their runtime namespace.
    # Use the already established operational-script profile for these fixtures;
    # the basename-based production scripts/ gate remains separately mandatory.
    "tests": [
        "--ignore-missing-imports",
        "--allow-untyped-defs",
        "--allow-untyped-calls",
        "--allow-any-generics",
    ],
}


def hex_value(value: Any, pattern: re.Pattern[str] = HEX) -> bool:
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def safe_relative(name: Any) -> bool:
    return (
        isinstance(name, str)
        and bool(name)
        and not name.startswith("-")
        and not Path(name).is_absolute()
        and ".." not in Path(name).parts
        and ".git" not in Path(name).parts
        and name.rstrip("/") == Path(name).as_posix()
        and name != "."
    )


def covers(target: str, name: str) -> bool:
    return name == target.rstrip("/") or (
        target.endswith("/") and name.startswith(target)
    )


def type_command(plan: dict) -> list[str]:
    return [
        plan["interpreter"],
        "-I",
        "-m",
        "mypy",
        "--config-file",
        "mypy.ini",
        "--no-incremental",
        "--cache-dir",
        os.devnull,
        *TYPE_PROFILES[plan["profile"]],
        *plan["scope"],
    ]


def validate_subject(subject: dict) -> None:
    require(
        isinstance(subject, dict)
        and set(subject) in (SUBJECT_FIELDS, SUBJECT_FIELDS | {"command_contract"}),
        "invalid subject schema",
    )
    require(
        isinstance(subject["lease_id"], str) and bool(subject["lease_id"]),
        "missing lease identity",
    )
    require(
        isinstance(subject["branch"], str)
        and subject["branch"] not in {"", "main", "master"},
        "invalid subject branch",
    )
    require(
        all(
            hex_value(subject[k], HEX40) for k in ("parent_head", "parent_tree", "base")
        ),
        "invalid subject Git identity",
    )
    require(
        hex_value(subject["initial_index_sha256"]), "initial index evidence missing"
    )
    hashes, modes = subject["candidate_sha256"], subject["candidate_modes"]
    require(
        isinstance(hashes, dict)
        and bool(hashes)
        and isinstance(modes, dict)
        and set(hashes) == set(modes),
        "candidate mode/hash scope mismatch",
    )
    require(
        all(
            safe_relative(n)
            and not n.endswith("/")
            and hex_value(h)
            and modes[n] in {"100644", "100755"}
            for n, h in hashes.items()
        ),
        "invalid candidate file evidence",
    )
    # Type configuration changes require a separate governed contract rather than
    # allowing a candidate to change the configuration that qualifies itself.
    require(
        not (
            {"mypy.ini", "pyproject.toml", "setup.cfg", ".pre-commit-config.yaml"}
            & set(hashes)
        ),
        "type/hook configuration changes require separate qualification",
    )
    typed = {n for n in hashes if Path(n).suffix in {".py", ".pyi"}}
    plan = subject["type_plan"]
    require(isinstance(plan, list), "missing type plan")
    ids: set[str] = set()
    targets: list[str] = []
    for item in plan:
        require(
            isinstance(item, dict)
            and set(item)
            == {
                "check_id",
                "profile",
                "scope",
                "interpreter",
                "python_version",
                "mypy_version",
                "config_sha256",
            },
            "invalid type plan record",
        )
        cid, profile, scope = item["check_id"], item["profile"], item["scope"]
        require(
            isinstance(cid, str) and cid.startswith("types:") and cid not in ids,
            "duplicate or invalid type check ID",
        )
        require(
            isinstance(profile, str) and profile in TYPE_PROFILES,
            "invalid type gate profile",
        )
        require(
            isinstance(scope, list)
            and bool(scope)
            and all(safe_relative(n) for n in scope),
            "invalid type scope",
        )
        require(
            all(
                isinstance(item[k], str) and bool(item[k])
                for k in ("interpreter", "python_version", "mypy_version")
            ),
            "missing interpreter/version evidence",
        )
        require(
            Path(item["interpreter"]).is_absolute()
            and hex_value(item["config_sha256"]),
            "invalid type configuration evidence",
        )
        require(
            profile != "scripts" or all(n.startswith("scripts/") for n in scope),
            "scripts profile outside scripts",
        )
        require(
            profile != "tests" or all(n.startswith("tests/") for n in scope),
            "tests profile outside tests",
        )
        ids.add(cid)
        targets.extend(scope)
    require(
        all(any(covers(t, n) for t in targets) for n in typed),
        "required typed scope missing",
    )
    # A script/test path may not evade its applicable profile by a broader
    # arbitrary strict or relaxed target. Strict is always allowed as stronger.
    for name in typed:
        require(
            any(
                any(covers(t, name) for t in x["scope"])
                and (
                    x["profile"] == "strict"
                    or (name.startswith("scripts/") and x["profile"] == "scripts")
                    or (name.startswith("tests/") and x["profile"] == "tests")
                )
                for x in plan
            ),
            "applicable type profile missing",
        )
    if plan:
        require(
            subject["type_not_applicable_reason"] is None, "contradictory type plan"
        )
    else:
        require(
            not typed
            and isinstance(subject["type_not_applicable_reason"], str)
            and bool(subject["type_not_applicable_reason"].strip()),
            "type not-applicable rationale required",
        )


def ordered_checks(subject: dict) -> list[str]:
    return [
        "readiness",
        *(item["check_id"] for item in subject["type_plan"]),
        "regression",
        "staged",
        "commit",
    ]


def validate_command_contract(subject: dict) -> None:
    """Validate a coordinator-approved argv/log contract; not command adequacy.

    The plan must be retained independently and approved before execution.
    A caller's plan and observations do not authenticate execution.
    """
    contract = subject["command_contract"]
    require(
        isinstance(contract, dict)
        and set(contract)
        in (
            {"interpreter", "hook_config_sha256", "checks"},
            {
                "interpreter",
                "hook_config_sha256",
                "checks",
                "observed_execution_worktree",
            },
        )
        and isinstance(contract["interpreter"], str)
        and Path(contract["interpreter"]).is_absolute()
        and hex_value(contract["hook_config_sha256"])
        and isinstance(contract["checks"], list),
        "invalid command contract",
    )
    if "observed_execution_worktree" in contract:
        worktree = contract["observed_execution_worktree"]
        require(
            isinstance(worktree, str)
            and Path(worktree).is_absolute()
            and Path(worktree).as_posix() == worktree
            and ".." not in Path(worktree).parts,
            "invalid observed execution worktree",
        )
    checks = contract["checks"]
    require(
        len(checks) == len(ordered_checks(subject)),
        "command contract check count mismatch",
    )
    log_names: set[str] = set()
    type_plans = {item["check_id"]: item for item in subject["type_plan"]}
    for cid, item in zip(ordered_checks(subject), checks, strict=True):
        require(
            isinstance(item, dict)
            and set(item) == {"check_id", "command", "log_name"}
            and item["check_id"] == cid,
            "command contract check order mismatch",
        )
        command, name = item["command"], item["log_name"]
        require(
            isinstance(command, list)
            and bool(command)
            and all(isinstance(arg, str) and arg and "\0" not in arg for arg in command)
            and Path(command[0]).is_absolute(),
            "invalid planned argv",
        )
        require(
            isinstance(name, str)
            and safe_relative(name)
            and Path(name).name == name
            and name not in log_names,
            "unsafe or duplicate planned log name",
        )
        log_names.add(name)
        if cid in type_plans:
            plan = type_plans[cid]
            require(
                plan["interpreter"] == contract["interpreter"]
                and command == type_command(plan),
                "planned type command mismatch",
            )
    readiness_log = checks[0]["log_name"]
    require(
        not log_names.intersection(
            {readiness_log + ".pass1.log", readiness_log + ".pass2.log"}
        ),
        "planned log collides with hook pass evidence",
    )
    if "observed_execution_worktree" in contract:
        require(
            not log_names.intersection(
                {
                    item["log_name"] + ".execution.json"
                    for item in checks
                    if execution_check(item["check_id"])
                }
            ),
            "planned log collides with execution sidecar",
        )


def execution_check(cid: str) -> bool:
    return cid.startswith("types:") or cid == "regression"


def observed_execution_required(subject: dict) -> bool:
    return "observed_execution_worktree" in subject.get("command_contract", {})


def command_contract_bound(subject: dict) -> bool:
    return "command_contract" in subject


def journal_schema(subject: dict) -> int:
    return BOUND_SCHEMA if command_contract_bound(subject) else SCHEMA


def verify_contract_runtime(root: Path, subject: dict) -> None:
    if not command_contract_bound(subject):
        return
    contract = subject["command_contract"]
    config = root / ready.CONFIG
    if observed_execution_required(subject):
        require(
            str(root.resolve()) == contract["observed_execution_worktree"],
            "observed execution worktree drift",
        )
    require(
        contract["interpreter"] == sys.executable
        and config.is_file()
        and not config.is_symlink()
        and ready.digest(config) == contract["hook_config_sha256"]
        and digest(ready.git(root, "show", subject["parent_head"] + ":" + ready.CONFIG))
        == contract["hook_config_sha256"],
        "command contract interpreter or hook configuration drift",
    )


def build_subject(lease: dict) -> dict:
    require(
        isinstance(lease, dict) and lease.get("state") == "PATCH_APPLIED",
        "applied-patch lease required",
    )
    subject = {
        "lease_id": lease["lease_id"],
        "branch": lease["branch"],
        "parent_head": lease["head"],
        "parent_tree": lease["tree"],
        "base": lease["base"],
        "initial_index_sha256": lease["index_sha256"],
        "candidate_sha256": lease["candidate_sha256"],
        "candidate_modes": lease["candidate_modes"],
        "type_plan": lease.get("type_plan", []),
        "type_not_applicable_reason": lease.get("type_not_applicable_reason"),
    }
    if "command_contract" in lease:
        subject["command_contract"] = lease["command_contract"]
    validate_subject(subject)
    if command_contract_bound(subject):
        validate_command_contract(subject)
    require(
        isinstance(lease["allowlist"], list)
        and len(lease["allowlist"]) == len(set(lease["allowlist"]))
        and set(lease["allowlist"]) == set(subject["candidate_sha256"]),
        "subject allowlist mismatch",
    )
    return subject


def required_checks(subject: dict) -> set[str]:
    return BASE_CHECKS | {x["check_id"] for x in subject["type_plan"]}


def start_data(lease: dict) -> dict:
    subject = build_subject(lease)
    return {
        "subject": subject,
        "subject_sha256": digest(canonical(subject)),
        "required_checks": sorted(required_checks(subject)),
    }


def check_bound_record(data: dict, start: dict, directory: Path) -> None:
    check_record(data, directory)
    require(
        data.get("subject_sha256") == start["subject_sha256"],
        "stale or different candidate check",
    )
    cid = data["check_id"]
    subject = start["subject"]
    if command_contract_bound(subject):
        expected = next(
            (
                item
                for item in subject["command_contract"]["checks"]
                if item["check_id"] == cid
            ),
            None,
        )
        require(
            expected is not None
            and data["command"] == expected["command"]
            and data["log_name"] == expected["log_name"],
            "observation differs from planned command or log",
        )
        fields = {
            "check_id",
            "subject_sha256",
            "command",
            "exit_code",
            "log_name",
            "log_sha256",
        }
        if cid.startswith("types:"):
            fields.add("type_evidence")
        if observed_execution_required(subject) and execution_check(cid):
            fields.add("execution_observation_sha256")
        require(set(data) == fields, "invalid bound observation fields")
    if cid.startswith("types:"):
        plan = next(
            (x for x in start["subject"]["type_plan"] if x["check_id"] == cid), None
        )
        require(
            plan is not None and data.get("type_evidence") == plan,
            "type evidence metadata mismatch",
        )
        if plan is None:
            raise ValueError("unknown type plan")
        require(
            data["command"] == type_command(plan),
            "type command differs from governed plan",
        )


def verify_execution_evidence(
    record: dict, subject: dict, directory: Path, prior_tip: str
) -> None:
    """Reconcile captured bytes against the anchored event; not authentication."""
    pin = record.get("execution_observation_sha256")
    require(hex_value(pin), "execution sidecar digest required")
    raw = ready.read_regular(
        evidence_file(directory, record["log_name"] + ".execution.json")
    )
    require(digest(raw) == pin, "execution sidecar digest mismatch")
    evidence = json.loads(raw)
    require(
        isinstance(evidence, dict)
        and set(evidence)
        == {
            "schema",
            "observation",
            "worktree",
            "prior_tip",
            "started_utc",
            "finished_utc",
            "candidate_state_unchanged",
            "execution_authenticated",
        }
        and type(evidence["schema"]) is int
        and evidence["schema"] == 1
        and evidence["observation"]
        == {k: v for k, v in record.items() if k != "execution_observation_sha256"}
        and evidence["worktree"]
        == subject["command_contract"]["observed_execution_worktree"]
        and evidence["prior_tip"] == prior_tip
        and evidence["candidate_state_unchanged"] is True
        and evidence["execution_authenticated"] is False,
        "execution sidecar binding mismatch",
    )
    started = datetime.fromisoformat(evidence["started_utc"])
    finished = datetime.fromisoformat(evidence["finished_utc"])
    require(
        started.tzinfo is not None
        and finished.tzinfo is not None
        and started <= finished,
        "invalid execution time evidence",
    )


def verify_readiness_evidence(record: dict, subject: dict, directory: Path) -> None:
    rows = parse_rows(evidence_file(directory, record["log_name"]).read_text())
    require(
        [x.get("state") for x in rows]
        == [
            "STARTED",
            "PREFLIGHTED",
            "HOOK_PASS_OBSERVED",
            "HOOK_PASS_OBSERVED",
            "READY_FOR_FINAL_BYTE_TESTS",
        ],
        "readiness evidence incomplete",
    )
    final = rows[-1]
    require(
        all(x.get("lease_id") == subject["lease_id"] for x in rows),
        "readiness lease mismatch",
    )
    require(
        final.get("candidate_sha256") == subject["candidate_sha256"]
        and final.get("candidate_modes") == subject["candidate_modes"],
        "readiness candidate mismatch",
    )
    ident = final.get("identity", {})
    require(
        ident
        == {
            "branch": subject["branch"],
            "head": subject["parent_head"],
            "tree": subject["parent_tree"],
            "base": subject["base"],
            "index_sha256": subject["initial_index_sha256"],
        },
        "readiness index/identity mismatch",
    )
    if command_contract_bound(subject):
        contract = subject["command_contract"]
        preflight = rows[1]
        require(
            preflight.get("identity") == ident
            and preflight.get("candidate_sha256") == subject["candidate_sha256"]
            and preflight.get("candidate_modes") == subject["candidate_modes"]
            and preflight.get("config_sha256") == contract["hook_config_sha256"],
            "readiness preflight contract mismatch",
        )
        expected_hook = [
            contract["interpreter"],
            "-I",
            "-m",
            "pre_commit",
            "run",
            "--config",
            ready.CONFIG,
            "--hook-stage",
            "pre-commit",
            "--files",
            *sorted(subject["candidate_sha256"]),
        ]
        require(
            all(row.get("command") == expected_hook for row in rows[2:4]),
            "readiness hook command mismatch",
        )
    for attempt, row in enumerate(rows[2:4], 1):
        require(
            row.get("pass_number") == attempt
            and row.get("exit_code") == 0
            and row.get("drift") == []
            and row.get("index_and_identity_unchanged") is True,
            "readiness hook failure or drift",
        )
        path = evidence_file(directory, record["log_name"] + f".pass{attempt}.log")
        require(
            ready.digest(path) == row.get("log_sha256"),
            "readiness hook log digest mismatch",
        )


def staged_proof(record: dict, subject: dict, directory: Path) -> dict:
    proof = json.loads(evidence_file(directory, record["log_name"]).read_text())
    if not isinstance(proof, dict):
        raise ValueError("invalid staged evidence")
    require(
        proof.get("staged_matches_candidate") is True
        and proof.get("checkpoint_verified") is False
        and proof.get("independent_review_complete") is False,
        "invalid staged evidence",
    )
    require(
        proof.get("candidate_sha256") == subject["candidate_sha256"]
        and proof.get("candidate_modes") == subject["candidate_modes"],
        "staged candidate mismatch",
    )
    ident = proof.get("identity", {})
    require(
        all(
            ident.get(k) == subject[v]
            for k, v in (
                ("branch", "branch"),
                ("head", "parent_head"),
                ("tree", "parent_tree"),
                ("base", "base"),
            )
        )
        and hex_value(ident.get("index_sha256")),
        "staged identity mismatch",
    )
    objects = proof.get("index_objects")
    if not isinstance(objects, dict):
        raise ValueError("staged object scope mismatch")
    require(
        set(objects) == set(subject["candidate_sha256"]), "staged object scope mismatch"
    )
    require(
        all(
            isinstance(o, dict)
            and set(o) == {"mode", "oid"}
            and o["mode"] == subject["candidate_modes"][n]
            and hex_value(o["oid"], HEX40)
            for n, o in objects.items()
        ),
        "invalid staged object evidence",
    )
    return proof


def validate_checkpoint_payload(
    data: dict, start: dict, checks: dict, prev: str, directory: Path
) -> None:
    s = start["subject"]
    require(
        set(data)
        == {
            "subject_sha256",
            "lease_id",
            "head",
            "tree",
            "base",
            "parent_head",
            "parent_tree",
            "candidate_sha256",
            "candidate_modes",
            "index_objects",
            "staged_index_sha256",
            "precheckpoint_tip",
            "worktree_clean",
            "independent_review_complete",
            "merge_authorized_by_receipt",
            "execution_authenticated",
        },
        "checkpoint object fields missing",
    )
    require(
        data["subject_sha256"] == start["subject_sha256"]
        and all(
            data[k] == s[k]
            for k in (
                "lease_id",
                "base",
                "parent_head",
                "parent_tree",
                "candidate_sha256",
                "candidate_modes",
            )
        ),
        "checkpoint candidate mismatch",
    )
    require(
        hex_value(data["head"], HEX40)
        and hex_value(data["tree"], HEX40)
        and data["precheckpoint_tip"] == prev,
        "checkpoint Git identity or anchor mismatch",
    )
    proof = staged_proof(checks["staged"], s, directory)
    require(
        data["index_objects"] == proof["index_objects"]
        and data["staged_index_sha256"] == proof["identity"]["index_sha256"],
        "checkpoint staged object mismatch",
    )
    require(
        data["worktree_clean"] is True
        and all(
            data[k] is False
            for k in (
                "independent_review_complete",
                "merge_authorized_by_receipt",
                "execution_authenticated",
            )
        ),
        "receipt cannot grant approval or authenticate execution",
    )


def validate_chain(rows: list[dict], directory: Path) -> str:
    prev = ZERO
    checks: dict[str, dict] = {}
    completed = False
    successful = False
    checkpoint = False
    reported = False
    start: dict = {}
    schema = rows[0].get("schema") if rows and isinstance(rows[0], dict) else SCHEMA
    for index, row in enumerate(rows):
        require(
            isinstance(row, dict)
            and schema in {SCHEMA, BOUND_SCHEMA}
            and row.get("schema") == schema
            and row.get("sequence") == index
            and row.get("previous_sha256") == prev,
            "journal sequence/schema mismatch",
        )
        require(
            row.get("event_sha256")
            == digest(canonical({k: v for k, v in row.items() if k != "event_sha256"})),
            "journal event hash mismatch",
        )
        event, data = row.get("event"), row.get("data")
        if (
            not isinstance(event, str)
            or event not in EVENTS
            or not isinstance(data, dict)
        ):
            raise ValueError("invalid journal event")
        if event == "STARTED":
            require(
                index == 0
                and set(data) == {"subject", "subject_sha256", "required_checks"},
                "invalid journal start",
            )
            validate_subject(data["subject"])
            require(
                schema == journal_schema(data["subject"]),
                "journal command contract schema mismatch",
            )
            if schema == BOUND_SCHEMA:
                validate_command_contract(data["subject"])
            require(
                data["subject_sha256"] == digest(canonical(data["subject"]))
                and data["required_checks"] == sorted(required_checks(data["subject"])),
                "required check plan or subject mismatch",
            )
            start = data
        else:
            require(bool(start), "journal start missing")
            if event == "CHECK_OBSERVED":
                cid = data.get("check_id")
                if not isinstance(cid, str):
                    raise ValueError("invalid check identity")
                require(
                    isinstance(cid, str)
                    and cid in start["required_checks"]
                    and cid not in checks
                    and not completed,
                    "duplicate, late or unplanned check",
                )
                if schema == BOUND_SCHEMA:
                    order = ordered_checks(start["subject"])
                    require(
                        len(checks) < len(order)
                        and cid == order[len(checks)]
                        and all(x["exit_code"] == 0 for x in checks.values()),
                        "bound check order or prior failure",
                    )
                check_bound_record(data, start, directory)
                if observed_execution_required(start["subject"]) and execution_check(
                    cid
                ):
                    verify_execution_evidence(data, start["subject"], directory, prev)
                if (
                    schema == BOUND_SCHEMA
                    and cid == "readiness"
                    and data["exit_code"] == 0
                ):
                    verify_readiness_evidence(data, start["subject"], directory)
                checks[data["check_id"]] = data
            elif event == "EXECUTION_COMPLETED":
                require(
                    not completed and type(data.get("exit_code")) is int,
                    "invalid execution completion",
                )
                if schema == BOUND_SCHEMA and data["exit_code"] == 0:
                    require(
                        list(checks) == ordered_checks(start["subject"])
                        and all(x["exit_code"] == 0 for x in checks.values()),
                        "bound execution success requires all ordered checks passing",
                    )
                completed = True
                successful = data["exit_code"] == 0
            elif event == "CHECKPOINT_VERIFIED":
                require(
                    completed and successful and not checkpoint and not reported,
                    "checkpoint ordering or execution failure",
                )
                require(
                    set(checks) == set(start["required_checks"]),
                    "required check evidence missing",
                )
                require(
                    all(x["exit_code"] == 0 for x in checks.values()),
                    "required check failed",
                )
                verify_readiness_evidence(
                    checks["readiness"], start["subject"], directory
                )
                validate_checkpoint_payload(data, start, checks, prev, directory)
                checkpoint = True
            elif event == "REPORT_OBSERVED":
                require(
                    completed
                    and not reported
                    and data.get("delivery_confirmed") is False
                    and bool(data.get("channel"))
                    and bool(data.get("observation")),
                    "invalid reporting event or unsupported delivery claim",
                )
                reported = True
        prev = row["event_sha256"]
    return prev


def parse_rows(raw: str) -> list[dict]:
    require(not raw or raw.endswith("\n"), "partial journal record")
    rows = [json.loads(line) for line in raw.splitlines()]
    require(all(isinstance(row, dict) for row in rows), "invalid journal row")
    return rows


def _append_event(
    path: Path, event: str, data: dict, expected_tip: str | None = None
) -> str:
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
        if expected_tip is not None:
            require(prev == expected_tip, "trusted journal tip mismatch")
        schema = (
            rows[0]["schema"]
            if rows
            else journal_schema(data["subject"]) if event == "STARTED" else SCHEMA
        )
        row = {
            "schema": schema,
            "sequence": len(rows),
            "previous_sha256": prev,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data,
        }
        tip = digest(canonical(row))
        row["event_sha256"] = tip
        validate_chain([*rows, row], path.parent)
        stream.seek(0, os.SEEK_END)
        stream.write(canonical(row).decode() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        return tip


def append_event(path: Path, event: str, data: dict) -> str:
    require(
        event != "CHECKPOINT_VERIFIED",
        "checkpoint requires anchored Git reconciliation; no direct approval or checkpoint append",
    )
    return _append_event(path, event, data)


def inspect_journal(path: Path, expected_tip: str | None = None) -> dict:
    path = safe_external(path)
    rows = parse_rows(ready.read_regular(path).decode())
    require(bool(rows), "empty journal")
    legacy = rows[0].get("schema") == 1
    tip = (
        _validate_legacy_chain(rows, path.parent)
        if legacy
        else validate_chain(rows, path.parent)
    )
    if expected_tip is not None:
        require(tip == expected_tip, "trusted journal tip mismatch")
    return {
        "tip_sha256": tip,
        "events": len(rows),
        "execution_completed": any(x["event"] == "EXECUTION_COMPLETED" for x in rows),
        "checkpoint_recorded": any(x["event"] == "CHECKPOINT_VERIFIED" for x in rows),
        "checkpoint_verified": False,
        "legacy_historical_only": legacy,
        "command_contract_bound": rows[0].get("schema") == BOUND_SCHEMA,
        "observed_execution_required": (
            not legacy and observed_execution_required(rows[0]["data"]["subject"])
        ),
        "report_observed": any(x["event"] == "REPORT_OBSERVED" for x in rows),
        "delivery_confirmed": False,
        "independent_review_complete": False,
        "anchor_supplied": expected_tip is not None,
        "execution_authenticated": False,
    }


def qualification_rows(
    root: Path, lease: dict, journal: Path, expected_tip: str
) -> tuple[list[dict], dict, dict]:
    require(hex_value(expected_tip), "trusted journal tip required")
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "environment override present",
    )
    require(
        Path(lease["worktree"]).resolve() == root
        and Path(ready.git_text(root, "rev-parse", "--show-toplevel")).resolve()
        == root,
        "incorrect worktree",
    )
    rows = parse_rows(ready.read_regular(journal).decode())
    require(
        bool(rows) and rows[0].get("schema") in {SCHEMA, BOUND_SCHEMA},
        "legacy or empty journal cannot qualify",
    )
    require(
        validate_chain(rows, journal.parent) == expected_tip,
        "trusted journal tip mismatch",
    )
    start = rows[0]["data"]
    require(start == start_data(lease), "journal subject or lease mismatch")
    checks = {
        x["data"]["check_id"]: x["data"] for x in rows if x["event"] == "CHECK_OBSERVED"
    }
    require(
        set(checks) == set(start["required_checks"]), "required check evidence missing"
    )
    require(
        all(x["exit_code"] == 0 for x in checks.values())
        and any(
            x["event"] == "EXECUTION_COMPLETED" and x["data"]["exit_code"] == 0
            for x in rows
        ),
        "required check or execution failed",
    )
    subject = start["subject"]
    verify_contract_runtime(root, subject)
    verify_readiness_evidence(checks["readiness"], subject, journal.parent)
    for plan in subject["type_plan"]:
        require(
            plan["interpreter"] == sys.executable
            and plan["python_version"] == sys.version,
            "governed interpreter/version mismatch",
        )
        version = subprocess.check_output(
            [sys.executable, "-I", "-m", "mypy", "--version"], cwd=root, text=True
        ).strip()
        require(version == plan["mypy_version"], "governed mypy version mismatch")
        config = root / "mypy.ini"
        require(
            config.is_file()
            and not config.is_symlink()
            and ready.digest(config) == plan["config_sha256"],
            "type configuration drift",
        )
        require(
            all((root / x).exists() for x in plan["scope"]), "type target unavailable"
        )
    return rows, start, checks


def object_proof(
    root: Path, lease: dict, start: dict, checks: dict, journal: Path, pretip: str
) -> dict:
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "environment override present",
    )
    require(
        Path(lease["worktree"]).resolve() == root
        and Path(ready.git_text(root, "rev-parse", "--show-toplevel")).resolve()
        == root,
        "incorrect worktree",
    )
    s = start["subject"]
    ident = ready.identity(root)
    require(
        ident["branch"] == s["branch"] and ident["base"] == s["base"],
        "branch or base mismatch",
    )
    require(
        ready.git_text(root, "rev-list", "--parents", "-n", "1", "HEAD").split()
        == [ident["head"], s["parent_head"]],
        "unexpected commit parent",
    )
    require(
        ready.git_text(root, "rev-parse", s["parent_head"] + "^{tree}")
        == s["parent_tree"],
        "parent tree mismatch",
    )
    require(not ready.git(root, "status", "--porcelain", "-z"), "worktree not clean")
    ready.snapshot(root)
    scope = set(s["candidate_sha256"])
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
        == scope,
        "committed scope mismatch",
    )
    staged = staged_proof(checks["staged"], s, journal.parent)
    require(
        ident["index_sha256"] == staged["identity"]["index_sha256"],
        "postcommit index differs from staged proof",
    )
    entries = {}
    for raw in ready.git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if raw:
            meta, name = raw.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            entries[os.fsdecode(name)] = (mode, kind, oid)
    for name in scope:
        p = ready.path_at(root, name)
        require(
            name in entries and p.is_file() and not p.is_symlink(),
            "missing or nonregular committed object",
        )
        mode, kind, oid = entries[name]
        require(
            kind == "blob" and mode == s["candidate_modes"][name] == ready.git_mode(p),
            "committed Git mode mismatch",
        )
        require(
            staged["index_objects"][name] == {"mode": mode, "oid": oid},
            "committed object differs from staged evidence",
        )
        require(
            digest(ready.git(root, "cat-file", "blob", oid))
            == s["candidate_sha256"][name]
            == ready.digest(p),
            "committed blob mismatch",
        )
    return {
        "subject_sha256": start["subject_sha256"],
        "lease_id": s["lease_id"],
        "head": ident["head"],
        "tree": ident["tree"],
        "base": s["base"],
        "parent_head": s["parent_head"],
        "parent_tree": s["parent_tree"],
        "candidate_sha256": s["candidate_sha256"],
        "candidate_modes": s["candidate_modes"],
        "index_objects": staged["index_objects"],
        "staged_index_sha256": staged["identity"]["index_sha256"],
        "precheckpoint_tip": pretip,
        "worktree_clean": True,
        "independent_review_complete": False,
        "merge_authorized_by_receipt": False,
        "execution_authenticated": False,
    }


def record_checkpoint(root: Path, lease: dict, journal: Path, expected_tip: str) -> str:
    """Bind observations to actual committed objects and an externally retained tip."""
    root = root.resolve()
    journal = safe_external(journal)
    rows, start, checks = qualification_rows(root, lease, journal, expected_tip)
    require(
        rows[-1]["event"] == "EXECUTION_COMPLETED",
        "checkpoint requires completed unrecorded execution",
    )
    proof = object_proof(root, lease, start, checks, journal, expected_tip)
    return _append_event(journal, "CHECKPOINT_VERIFIED", proof, expected_tip)


def reconcile_checkpoint(
    root: Path, lease: dict, journal: Path, expected_tip: str
) -> dict:
    """Recheck a recorded checkpoint against actual Git objects; not execution authentication."""
    root = root.resolve()
    journal = safe_external(journal)
    rows, start, checks = qualification_rows(root, lease, journal, expected_tip)
    recorded = [x for x in rows if x["event"] == "CHECKPOINT_VERIFIED"]
    require(len(recorded) == 1, "checkpoint event required")
    proof = object_proof(
        root, lease, start, checks, journal, recorded[0]["previous_sha256"]
    )
    require(recorded[0]["data"] == proof, "checkpoint event differs from Git proof")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("journal", type=Path)
    parser.add_argument("--expected-tip")
    args = parser.parse_args()
    try:
        print(json.dumps(inspect_journal(args.journal, args.expected_tip), indent=2))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ready.ReadinessError,
    ):
        print(
            "STOP: checkpoint receipt refused; preserve evidence and reconcile",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
