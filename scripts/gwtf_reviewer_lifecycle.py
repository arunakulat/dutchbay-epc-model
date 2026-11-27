"""RECRUIT-01 reviewer-session lifecycle, evidence reconciliation, and safe retirement (#1954).

This module provides fail-closed validation and verification helpers for:
1. Reviewer-session lifecycle records (distinguishing provider execution,
   terminal disposition, evidence custody, coordinator receipt, per-finding
   reconciliation, supersession, resource retirement, supported transcript
   archival, and API vs. displayed UI activity state).
2. Exact-head evidence reconciliation (blocking on missing/unmatched evidence,
   live writers/locks, ambiguous ownership, unresolved scope, stale exact-head
   reviews, vetoes, and NO_EVIDENCE).
3. Safe-retirement verification (separately checking merge/ancestry, exact branch
   head, clean worktree status, process usage, recovery references, dedicated
   environment ownership, preserved original evidence, supported reversible
   archival, and forbidding DB edits, forced lock removal, unsupported client
   mutation, transcript deletion, or touching the shared governed venv).

This module is pure/read-only verification logic; it performs no Git, process,
database, or filesystem mutations.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SHARED_GOVERNED_VENV = "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"

EXECUTION_MODES = frozenset(
    {"HEADLESS_STRUCTURED", "IMPORTED_CONVERSATION", "LOCAL_SUBAGENT"}
)
EXECUTION_STATES = frozenset(
    {"PLANNED", "RUNNING", "COMPLETED", "FAILED", "INTERRUPTED", "UNKNOWN"}
)
TERMINAL_DISPOSITIONS = frozenset(
    {
        "ACCEPT",
        "APPROVE",
        "PASS",
        "REJECT",
        "CHANGES_REQUESTED",
        "WITHHELD",
        "NO_EVIDENCE",
        "SUPERSEDED",
    }
)
ACCEPTING_DISPOSITIONS = frozenset({"ACCEPT", "APPROVE", "PASS"})
BLOCKING_DISPOSITIONS = frozenset(
    {"REJECT", "CHANGES_REQUESTED", "WITHHELD", "NO_EVIDENCE"}
)
FINDING_STATES = frozenset(
    {
        "BLOCKS_CURRENT_CANDIDATE",
        "ACCEPTED_RESIDUAL_WITHIN_SCOPE",
        "DEFERRED_TO_NAMED_DOLPHIN",
        "TRACKED_IN_NAMED_ISSUE",
        "NOT_APPLICABLE_WITH_REASON",
        "SUPERSEDED_BY_SUCCESSOR_FINDING",
    }
)
DEFERRED_FINDING_STATES = frozenset(
    {"DEFERRED_TO_NAMED_DOLPHIN", "TRACKED_IN_NAMED_ISSUE"}
)
API_ARCHIVE_STATES = frozenset({"ACTIVE", "ARCHIVED", "UNKNOWN"})
UI_ACTIVITY_STATES = frozenset(
    {"NONE", "UNREAD_BADGE", "RECENT_EVENTS_VISIBLE", "UNKNOWN"}
)
ARCHIVAL_ACTIONS = frozenset(
    {"SUPPORTED_ARCHIVE", "RETAIN_PENDING_RECONCILIATION", "NO_ACTION"}
)
FORBIDDEN_MUTATIONS = frozenset(
    {
        "DB_EDIT",
        "FORCED_LOCK_REMOVAL",
        "UNSUPPORTED_CLIENT_MUTATION",
        "TRANSCRIPT_DELETION",
        "SHARED_VENV_MODIFICATION",
    }
)
ROLES = frozenset({"domain", "assurance", "security", "advisory"})

SESSION_FIELDS = frozenset(
    {
        "reviewer_identity",
        "session_id",
        "role",
        "execution_mode",
        "headless_supported",
        "execution_state",
        "candidate_commit",
        "candidate_tree",
        "base_sha",
        "subject_manifest_sha256",
        "terminal_disposition",
        "receipt_sha256",
        "evidence_matched",
        "coordinator_receipt_sha256",
        "findings",
        "api_archive_state",
        "ui_activity_state",
        "active_execution_claimed_from_ui",
    }
)

RETIREMENT_FIELDS = frozenset(
    {
        "session_id",
        "merge_ancestry_verified",
        "exact_branch_head_verified",
        "worktree_clean",
        "dirty_paths",
        "unique_commits",
        "active_processes",
        "unresolved_recovery_refs",
        "dedicated_env_path",
        "dedicated_env_owned",
        "original_evidence_preserved",
        "evidence_reconciled",
        "archival_action",
        "archival_reversible",
        "api_archive_state",
        "ui_activity_state",
        "requested_mutations",
    }
)

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def _require(condition: bool, message: str) -> None:
    """Raise ValueError when an invariant is violated."""
    if not condition:
        raise ValueError(message)


def _require_non_empty_str(value: Any, field: str) -> str:
    """Validate that a field is a non-empty string."""
    _require(
        isinstance(value, str) and bool(value.strip()),
        f"{field} must be a non-empty string",
    )
    return str(value)


def _require_hex40(value: Any, field: str) -> str:
    """Validate a 40-character lowercase Git SHA."""
    _require(
        isinstance(value, str) and bool(HEX40.fullmatch(value)),
        f"{field} must be a 40-hex SHA",
    )
    return str(value)


def _require_hex64(value: Any, field: str, *, allow_none: bool = False) -> str | None:
    """Validate a 64-character lowercase SHA-256 hex digest."""
    if value is None and allow_none:
        return None
    _require(
        isinstance(value, str) and bool(HEX64.fullmatch(value)),
        f"{field} must be a 64-hex SHA-256 digest",
    )
    return str(value)


def _require_choice(value: Any, allowed: frozenset[str], field: str) -> str:
    """Validate that a string field belongs to an allowed vocabulary."""
    _require(
        isinstance(value, str) and value in allowed,
        f"invalid {field}: {value!r}",
    )
    return str(value)


def _validate_finding(finding: Any, index: int) -> None:
    """Validate one per-finding reconciliation entry against RECRUIT-01 module 3 §5."""
    _require(isinstance(finding, dict), f"findings[{index}] must be an object")
    _require_non_empty_str(finding.get("finding_id"), f"findings[{index}].finding_id")
    state = _require_choice(
        finding.get("state"), FINDING_STATES, f"findings[{index}].state"
    )
    _require_non_empty_str(finding.get("summary"), f"findings[{index}].summary")

    if state in DEFERRED_FINDING_STATES:
        for req_key in (
            "owner",
            "destination",
            "rationale",
            "acceptance_gate",
            "hold_effect",
        ):
            _require_non_empty_str(finding.get(req_key), f"findings[{index}].{req_key}")
    if state == "NOT_APPLICABLE_WITH_REASON":
        _require_non_empty_str(finding.get("rationale"), f"findings[{index}].rationale")
    if state == "SUPERSEDED_BY_SUCCESSOR_FINDING":
        _require_non_empty_str(
            finding.get("superseded_by"), f"findings[{index}].superseded_by"
        )


def validate_reviewer_session(record: dict[str, Any]) -> None:
    """Strictly validate a reviewer-session lifecycle record.

    Fails closed on missing/extra fields, invalid SHAs or digests, invalid
    dispositions, incomplete deferred findings, or asserting active execution
    from unread/activity UI indicators.
    """
    _require(
        isinstance(record, dict) and set(record) == SESSION_FIELDS,
        "invalid reviewer session schema",
    )
    _require_non_empty_str(record["reviewer_identity"], "reviewer_identity")
    _require_non_empty_str(record["session_id"], "session_id")
    _require_choice(record["role"], ROLES, "role")
    _require_choice(record["execution_mode"], EXECUTION_MODES, "execution_mode")
    _require(
        type(record["headless_supported"]) is bool,
        "headless_supported must be boolean",
    )
    _require_choice(record["execution_state"], EXECUTION_STATES, "execution_state")
    _require_hex40(record["candidate_commit"], "candidate_commit")
    _require_hex40(record["candidate_tree"], "candidate_tree")
    _require_hex40(record["base_sha"], "base_sha")
    _require_hex64(record["subject_manifest_sha256"], "subject_manifest_sha256")
    _require_choice(
        record["terminal_disposition"], TERMINAL_DISPOSITIONS, "terminal_disposition"
    )
    _require_hex64(record["receipt_sha256"], "receipt_sha256", allow_none=True)
    _require(
        type(record["evidence_matched"]) is bool,
        "evidence_matched must be boolean",
    )
    _require_hex64(
        record["coordinator_receipt_sha256"],
        "coordinator_receipt_sha256",
        allow_none=True,
    )
    _require_choice(
        record["api_archive_state"], API_ARCHIVE_STATES, "api_archive_state"
    )
    _require_choice(
        record["ui_activity_state"], UI_ACTIVITY_STATES, "ui_activity_state"
    )
    _require(
        type(record["active_execution_claimed_from_ui"]) is bool,
        "active_execution_claimed_from_ui must be boolean",
    )
    _require(
        not record["active_execution_claimed_from_ui"],
        "cannot assert active execution from unread or activity UI indicators",
    )

    findings = record["findings"]
    _require(isinstance(findings, list), "findings must be a list")
    for idx, finding in enumerate(findings):
        _validate_finding(finding, idx)


def reconcile_reviewer_evidence(
    record: dict[str, Any],
    *,
    target_commit: str,
    target_tree: str,
    target_base: str,
    target_manifest_sha256: str,
    writer_sessions: set[str] | None = None,
    live_locks: bool = False,
    ambiguous_ownership: bool = False,
    unresolved_scope: bool = False,
    dirty_paths: list[str] | None = None,
    unique_commits: list[str] | None = None,
) -> dict[str, Any]:
    """Reconcile a reviewer session against exact target Git objects and gates.

    Historical acceptance never qualifies a new head; vetoes, NO_EVIDENCE,
    missing/unmatched evidence, live writers/locks, ambiguous ownership,
    unresolved scope, dirty paths, and unique commits all fail closed.
    """
    validate_reviewer_session(record)
    _require_hex40(target_commit, "target_commit")
    _require_hex40(target_tree, "target_tree")
    _require_hex40(target_base, "target_base")
    _require_hex64(target_manifest_sha256, "target_manifest_sha256")

    blockers: list[str] = []
    advisories: list[str] = []

    if live_locks:
        blockers.append("LIVE_WRITER_OR_LOCK")
    if ambiguous_ownership:
        blockers.append("AMBIGUOUS_OWNERSHIP")
    if unresolved_scope:
        blockers.append("UNRESOLVED_SCOPE")
    if dirty_paths:
        blockers.append("DIRTY_PATHS_PRESENT")
    if unique_commits:
        blockers.append("UNIQUE_UNMERGED_COMMITS_PRESENT")
    if writer_sessions and record["session_id"] in writer_sessions:
        blockers.append("NON_INDEPENDENT_WRITER_SESSION")

    exact_head_match = (
        record["candidate_commit"] == target_commit
        and record["candidate_tree"] == target_tree
        and record["base_sha"] == target_base
        and record["subject_manifest_sha256"] == target_manifest_sha256
    )
    if not exact_head_match:
        blockers.append("STALE_OR_MISMATCHED_SUBJECT")

    if (
        not record["evidence_matched"]
        or record["receipt_sha256"] is None
        or record["coordinator_receipt_sha256"] is None
    ):
        blockers.append("MISSING_OR_UNMATCHED_EVIDENCE")

    disp = record["terminal_disposition"]
    if disp in BLOCKING_DISPOSITIONS:
        blockers.append(f"BLOCKING_DISPOSITION:{disp}")
    elif disp == "SUPERSEDED":
        blockers.append("SUPERSEDED_RECORD")
    elif disp not in ACCEPTING_DISPOSITIONS:
        blockers.append(f"NON_ACCEPTING_DISPOSITION:{disp}")

    if record["execution_state"] != "COMPLETED":
        blockers.append(f"INCOMPLETE_EXECUTION:{record['execution_state']}")

    finding_counts: dict[str, int] = {}
    for finding in record["findings"]:
        state = finding["state"]
        finding_counts[state] = finding_counts.get(state, 0) + 1
        if state == "BLOCKS_CURRENT_CANDIDATE":
            blockers.append(f"BLOCKING_FINDING:{finding['finding_id']}")

    if (
        record["headless_supported"]
        and record["execution_mode"] != "HEADLESS_STRUCTURED"
    ):
        advisories.append("PREFER_HEADLESS_STRUCTURED_REVIEW")

    ui_limitation_note: str | None = None
    if record["api_archive_state"] == "ARCHIVED" and record["ui_activity_state"] in {
        "UNREAD_BADGE",
        "RECENT_EVENTS_VISIBLE",
    }:
        ui_limitation_note = (
            "Archived thread remains visible in UI activity/Recent Events; "
            "no supported activity-dismissal operation exists and UI state "
            "does not indicate active execution."
        )

    qualified = len(blockers) == 0
    return {
        "schema": "gwtf.reviewer_reconciliation.v1",
        "session_id": record["session_id"],
        "reviewer_identity": record["reviewer_identity"],
        "role": record["role"],
        "status": "QUALIFIED" if qualified else "BLOCKED",
        "qualified": qualified,
        "exact_head_match": exact_head_match,
        "terminal_disposition": disp,
        "api_archive_state": record["api_archive_state"],
        "ui_activity_state": record["ui_activity_state"],
        "ui_limitation_note": ui_limitation_note,
        "finding_counts": finding_counts,
        "blockers": blockers,
        "advisories": advisories,
    }


def _is_shared_governed_venv(path_str: str) -> bool:
    """Return True if path_str names or resolves inside the shared governed venv."""
    norm_shared = os.path.normpath(os.path.realpath(SHARED_GOVERNED_VENV))
    norm_candidate = os.path.normpath(os.path.realpath(path_str))
    if norm_candidate == norm_shared:
        return True
    if norm_candidate.startswith(norm_shared + os.sep):
        return True
    # Also check lexical normalization in case symlink/mount doesn't exist in test env.
    lex_shared = os.path.normpath(SHARED_GOVERNED_VENV)
    lex_candidate = os.path.normpath(path_str)
    return lex_candidate == lex_shared or lex_candidate.startswith(lex_shared + os.sep)


def verify_safe_retirement(plan: dict[str, Any]) -> dict[str, Any]:
    """Separately verify all CLEANUP-01, THREAD-01, and RECRUIT-01 retirement gates.

    Verifies merge/ancestry, exact branch head, worktree cleanliness, process usage,
    recovery references, dedicated environment ownership (protecting the shared
    governed venv), original evidence preservation, supported/reversible archival,
    and absence of forbidden mutations.
    """
    _require(
        isinstance(plan, dict) and set(plan) == RETIREMENT_FIELDS,
        "invalid retirement plan schema",
    )
    _require_non_empty_str(plan["session_id"], "session_id")
    for bool_field in (
        "merge_ancestry_verified",
        "exact_branch_head_verified",
        "worktree_clean",
        "dedicated_env_owned",
        "original_evidence_preserved",
        "evidence_reconciled",
        "archival_reversible",
    ):
        _require(type(plan[bool_field]) is bool, f"{bool_field} must be boolean")

    for list_field in (
        "dirty_paths",
        "unique_commits",
        "active_processes",
        "unresolved_recovery_refs",
        "requested_mutations",
    ):
        val = plan[list_field]
        _require(
            isinstance(val, list) and all(isinstance(x, str) for x in val),
            f"{list_field} must be a list of strings",
        )

    env_path = plan["dedicated_env_path"]
    _require(
        env_path is None or (isinstance(env_path, str) and bool(env_path.strip())),
        "dedicated_env_path must be None or a non-empty string",
    )
    _require_choice(plan["archival_action"], ARCHIVAL_ACTIONS, "archival_action")
    _require_choice(plan["api_archive_state"], API_ARCHIVE_STATES, "api_archive_state")
    _require_choice(plan["ui_activity_state"], UI_ACTIVITY_STATES, "ui_activity_state")

    checks: dict[str, bool] = {
        "merge_ancestry": bool(plan["merge_ancestry_verified"]),
        "exact_branch_head": bool(plan["exact_branch_head_verified"]),
        "worktree_status": (
            bool(plan["worktree_clean"])
            and len(plan["dirty_paths"]) == 0
            and len(plan["unique_commits"]) == 0
        ),
        "process_usage": len(plan["active_processes"]) == 0,
        "recovery_references": len(plan["unresolved_recovery_refs"]) == 0,
        "dedicated_env_ownership": (
            env_path is None
            or (
                bool(plan["dedicated_env_owned"])
                and not _is_shared_governed_venv(env_path)
            )
        ),
        "original_evidence_preserved": bool(plan["original_evidence_preserved"]),
        "archival_supported": (
            plan["archival_action"] != "SUPPORTED_ARCHIVE"
            or (bool(plan["archival_reversible"]) and bool(plan["evidence_reconciled"]))
        ),
        "no_forbidden_mutations": not any(
            m in FORBIDDEN_MUTATIONS for m in plan["requested_mutations"]
        ),
    }

    blockers = [name for name, ok in checks.items() if not ok]
    if env_path is not None and _is_shared_governed_venv(env_path):
        blockers.append("SHARED_GOVERNED_VENV_PROTECTED")

    ui_limitation_reported = plan["api_archive_state"] == "ARCHIVED" and plan[
        "ui_activity_state"
    ] in {"UNREAD_BADGE", "RECENT_EVENTS_VISIBLE"}

    allowed = len(blockers) == 0
    return {
        "schema": "gwtf.reviewer_retirement.v1",
        "session_id": plan["session_id"],
        "status": "SAFE_TO_RETIRE" if allowed else "BLOCKED",
        "allowed": allowed,
        "checks": checks,
        "blockers": blockers,
        "api_archive_state": plan["api_archive_state"],
        "ui_activity_state": plan["ui_activity_state"],
        "ui_limitation_reported": ui_limitation_reported,
    }


def _load_json_regular_file(path_str: str) -> Any:
    """Load JSON from a regular file (not a directory or symlink to non-regular)."""
    path = Path(path_str)
    if not path.is_file():
        raise ValueError(f"input is not a regular file: {path_str}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for reviewer lifecycle reconciliation and safe retirement."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser(
        "reconcile", help="Reconcile a reviewer session record against target SHAs."
    )
    rec.add_argument("--session", required=True, help="Path to session JSON file.")
    rec.add_argument("--target-commit", required=True)
    rec.add_argument("--target-tree", required=True)
    rec.add_argument("--target-base", required=True)
    rec.add_argument("--target-manifest-sha256", required=True)
    rec.add_argument(
        "--writer-session",
        action="append",
        default=[],
        help="Writer session ID to check independence against.",
    )
    rec.add_argument("--live-locks", action="store_true")
    rec.add_argument("--ambiguous-ownership", action="store_true")
    rec.add_argument("--unresolved-scope", action="store_true")

    ret = sub.add_parser(
        "verify-retirement", help="Verify safe retirement preconditions."
    )
    ret.add_argument("--plan", required=True, help="Path to retirement plan JSON file.")

    args = parser.parse_args(argv)
    try:
        if args.command == "reconcile":
            record = _load_json_regular_file(args.session)
            result = reconcile_reviewer_evidence(
                record,
                target_commit=args.target_commit,
                target_tree=args.target_tree,
                target_base=args.target_base,
                target_manifest_sha256=args.target_manifest_sha256,
                writer_sessions=set(args.writer_session),
                live_locks=bool(args.live_locks),
                ambiguous_ownership=bool(args.ambiguous_ownership),
                unresolved_scope=bool(args.unresolved_scope),
            )
            print(json.dumps(result, sort_keys=True))
            return 0 if result["qualified"] else 2

        plan = _load_json_regular_file(args.plan)
        result = verify_safe_retirement(plan)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["allowed"] else 2
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
