#!/usr/bin/env python3
"""Build the additive 111-row P02 current-main findings overlay.

The historical findings register remains an audited-commit statement.  This
builder refuses to rewrite it and records later implementation evidence only in
an additive, hash-bound current-state layer.  A v1 positive delivery mapping is
still an implementer claim pending independent model-risk review.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, cast

PACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parents[2]
FINDINGS_REGISTER = PACK_ROOT / "registers" / "findings_register.v2.json"
PLAN = PACK_ROOT / "registers" / "findings_current_state_plan.v1.json"
OUTPUT = PACK_ROOT / "registers" / "findings_current_state_overlay.v1.json"
HISTORY_SELF_CHECK = (
    PACK_ROOT / "qa" / "P02_REPOSITORY_HISTORY_IMPLEMENTER_SELF_CHECK_2026-08-24.json"
)

SCHEMA_VERSION = "dutchbay.findings_current_state_overlay.v1"
PLAN_SCHEMA_VERSION = "dutchbay.findings_current_state_overlay_plan.v1"
DOCUMENT_ID = "DUTCHBAY-1110-P02-FINDINGS-CURRENT-STATE-OVERLAY-v1"
PLAN_DOCUMENT_ID = "DUTCHBAY-1110-P02-FINDINGS-CURRENT-STATE-PLAN-v1"
AUDITED_COMMIT = "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8"
SOURCE_REGISTER_RELATIVE = "registers/findings_register.v2.json"
SOURCE_REGISTER_SHA256 = (
    "71d16a15357a6073456b241d713ba775e2945990b22fa72045d5f312e183b4b8"
)
CURRENT_MAIN_CUTOFF = "63b67eb62789da9ad712e9d0569737ec79988c65"
CURRENT_MAIN_TREE_OID = "272e608c729a6b836d45df16f7903c142d90bd0a"
HISTORY_SELF_CHECK_RELATIVE = (
    "docs/audit/2026-08-controlled-successor/qa/"
    "P02_REPOSITORY_HISTORY_IMPLEMENTER_SELF_CHECK_2026-08-24.json"
)
HISTORY_SELF_CHECK_SHA256 = (
    "8a8c481a3beb60ed54ef0f865f134bb9c82766e66e5e820db398fd19b684dc0a"
)
HISTORY_SELF_CHECK_DOCUMENT_ID = (
    "DUTCHBAY-1110-P02-REPOSITORY-HISTORY-IMPLEMENTER-SELF-CHECK-2026-08-24"
)
EXPECTED_FINDING_COUNT = 111
EXPECTED_AUDITED_STATUS_COUNTS = Counter(
    {"closed": 4, "deferred": 16, "open": 70, "requires_correction": 21}
)
DEFAULT_STATE_BY_AUDITED_STATUS = {
    "closed": "baseline_closed_current_state_not_reassessed",
    "deferred": "deferred_current_state_not_examined",
    "open": "open_current_state_not_examined",
    "requires_correction": "requires_correction_current_state_not_examined",
}
DELIVERED_STATE = "implementation_delivered_review_pending"
EXTERNAL_BLOCKED_STATE = "external_evidence_blocked"
HOLD_EFFECT = "blocks_board_lender_release"
EXPECTED_CURRENT_STATE_COUNTS = Counter(
    {
        "baseline_closed_current_state_not_reassessed": 4,
        "deferred_current_state_not_examined": 16,
        EXTERNAL_BLOCKED_STATE: 1,
        DELIVERED_STATE: 5,
        "open_current_state_not_examined": 65,
        "requires_correction_current_state_not_examined": 20,
    }
)
EXPECTED_OVERRIDE_STATES = {
    "P2-F5-01": DELIVERED_STATE,
    "P2-F5-02": EXTERNAL_BLOCKED_STATE,
    "P2-MC-SENS-01": DELIVERED_STATE,
    "P2-MC-SENS-02": DELIVERED_STATE,
    "P3-EQ-04": DELIVERED_STATE,
    "P3-MCFX-03": DELIVERED_STATE,
}
EXPECTED_FINDING_EVIDENCE = {
    "P2-F5-01": {"EVD-F5-01-FULL-SEQUENCE"},
    "P2-F5-02": {"EVD-F5-02-INTAKE-CONTROL"},
    "P2-MC-SENS-01": {"EVD-PR1031-CASPER-TORNADO"},
    "P2-MC-SENS-02": {"EVD-PR1030-MC-BREACH"},
    "P3-EQ-04": {"EVD-PR1032-FX-DISCLOSURE"},
    "P3-MCFX-03": {"EVD-PR1030-MC-BREACH"},
}
EXPECTED_EVIDENCE_FINDINGS = {
    "EVD-F5-01-FULL-SEQUENCE": {"P2-F5-01"},
    "EVD-F5-02-INTAKE-CONTROL": {"P2-F5-02"},
    "EVD-PR1030-MC-BREACH": {"P2-MC-SENS-02", "P3-MCFX-03"},
    "EVD-PR1031-CASPER-TORNADO": {"P2-MC-SENS-01"},
    "EVD-PR1032-FX-DISCLOSURE": {"P3-EQ-04"},
}
EXPECTED_EVIDENCE_COMMITS = {
    "EVD-F5-01-FULL-SEQUENCE": [
        "72f1bf1e9601c815c53333f09c8f73a546b2c109",
        "e458a78c3377595e49b8c69ceb1afc5c5ff9869e",
        "dac8c7a36c63f1dbb8dcf855b263e645b57ed676",
        "7e64d336759292d1fa1c3f1533f6ec20ea6c0250",
        "32f83d2708759912636efe34cb795db60e0d1fa5",
        "15d450ec5eef88718286b3251e4264493a26538d",
    ],
    "EVD-F5-02-INTAKE-CONTROL": ["5503ff0e49683ddb8d8439d2460e2ebd08451985"],
    "EVD-PR1030-MC-BREACH": ["9faa6a23d1e655533e5231b6959c6ce3f66be5ad"],
    "EVD-PR1031-CASPER-TORNADO": ["50adfe7ee59f91660678c0ca32c2cd6513e1c611"],
    "EVD-PR1032-FX-DISCLOSURE": ["8a6b48f6573e4ac9074da8fbbcb1e48f4353ce9a"],
}
EXPECTED_EVIDENCE_PRS = {
    "EVD-F5-01-FULL-SEQUENCE": [1035, 1036, 1037, 1038, 1040, 1057],
    "EVD-F5-02-INTAKE-CONTROL": [1150],
    "EVD-PR1030-MC-BREACH": [1030],
    "EVD-PR1031-CASPER-TORNADO": [1031],
    "EVD-PR1032-FX-DISCLOSURE": [1032],
}
EXPECTED_EVIDENCE_CLASS = {
    "EVD-F5-01-FULL-SEQUENCE": "merged_delivery_chain",
    "EVD-F5-02-INTAKE-CONTROL": "external_evidence_intake_control",
    "EVD-PR1030-MC-BREACH": "merged_implementation",
    "EVD-PR1031-CASPER-TORNADO": "merged_implementation",
    "EVD-PR1032-FX-DISCLOSURE": "merged_implementation",
}
EXPECTED_EVIDENCE_STATUS = {
    "EVD-F5-01-FULL-SEQUENCE": "delivered_review_pending",
    "EVD-F5-02-INTAKE-CONTROL": "intake_ready_external_evidence_absent",
    "EVD-PR1030-MC-BREACH": "delivered_review_pending",
    "EVD-PR1031-CASPER-TORNADO": "delivered_review_pending",
    "EVD-PR1032-FX-DISCLOSURE": "delivered_review_pending",
}
EXPECTED_HISTORY_COMMITS = [
    AUDITED_COMMIT,
    *EXPECTED_EVIDENCE_COMMITS["EVD-F5-01-FULL-SEQUENCE"],
    *EXPECTED_EVIDENCE_COMMITS["EVD-PR1030-MC-BREACH"],
    *EXPECTED_EVIDENCE_COMMITS["EVD-PR1031-CASPER-TORNADO"],
    *EXPECTED_EVIDENCE_COMMITS["EVD-PR1032-FX-DISCLOSURE"],
    *EXPECTED_EVIDENCE_COMMITS["EVD-F5-02-INTAKE-CONTROL"],
    "0379843b28c493a1957b6b24f2853dd92a9ace05",
    CURRENT_MAIN_CUTOFF,
]
PLAN_KEYS = {
    "schema_version",
    "document_id",
    "authority_status",
    "created_at",
    "gate_id",
    "historical_audited_commit",
    "historical_findings_register_path",
    "historical_findings_register_sha256",
    "historical_finding_count",
    "current_main_cutoff_commit",
    "current_main_cutoff_tree_oid",
    "repository_history_implementer_self_check",
    "release_status",
    "independent_review_status",
    "default_state_by_audited_status",
    "evidence_catalog",
    "release_provenance_exception",
    "overrides",
    "f5_separation",
    "immutability_rule",
    "limitations",
}
EVIDENCE_KEYS = {
    "evidence_id",
    "evidence_class",
    "status",
    "finding_ids",
    "pull_request_urls",
    "merge_commits",
    "artifact_refs",
    "scope",
    "limitations",
}
ARTIFACT_KEYS = {"path", "sha256", "role"}
OVERRIDE_KEYS = {
    "finding_id",
    "current_state",
    "evidence_ids",
    "current_code_seams",
    "review_status",
    "remaining_gate",
    "limitations",
}
TAG_EXCEPTION_KEYS = {
    "tag_name",
    "tag_object_oid",
    "target_commit",
    "signature_status",
    "acceptance_control_ref",
    "limitation",
}
HISTORY_SELF_CHECK_KEYS = {
    "schema_version",
    "document_id",
    "created_at",
    "gate_id",
    "repository",
    "verification_environment",
    "commit_objects",
    "tag_object",
    "review",
    "release_status",
    "limitations",
}
HISTORY_COMMIT_KEYS = {
    "commit",
    "tree_oid",
    "subject",
    "role",
    "is_ancestor_of_current_main_cutoff",
}
F5_SEPARATION_RULE = (
    "F5-01 and F5-02 remain separate findings, evidence periods, decisions, "
    "implementations, tests, reconciliations, commits, pull requests and rollback "
    "surfaces; neither evidence set can close or offset the other."
)
HEX_40 = re.compile(r"[0-9a-f]{40}\Z")
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")


class FindingsOverlayBuildError(ValueError):
    """Raised when the P02 plan, source register or repository fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FindingsOverlayBuildError(message)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return _sha256_text(rendered)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        _require(key not in value, f"duplicate JSON key: {key}")
        value[key] = member
    return value


def _load_object(path: Path) -> dict[str, Any]:
    _require(path.is_file(), f"governed JSON is missing: {path.name}")
    _require(not path.is_symlink(), f"governed JSON cannot be a symlink: {path.name}")
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    _require(isinstance(value, dict), f"JSON root must be an object: {path.name}")
    return cast(dict[str, Any], value)


def _run_git(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr.strip() or completed.stdout.strip())[-800:]
        raise FindingsOverlayBuildError(
            f"Git verification failed: {' '.join(arguments)}: {detail}"
        )
    return completed.stdout.strip()


def _run_git_bytes(repo_root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout)[-800:].decode(
            "utf-8", errors="replace"
        )
        raise FindingsOverlayBuildError(
            f"Git verification failed: {' '.join(arguments)}: {detail}"
        )
    return completed.stdout


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        completed.returncode in {0, 1},
        f"Git ancestry verification failed for {ancestor}",
    )
    return completed.returncode == 0


def _validate_repo_file(repo_root: Path, label: str, raw_path: Any) -> str:
    _require(isinstance(raw_path, str) and bool(raw_path), f"{label}: path missing")
    relative = Path(raw_path)
    _require(not relative.is_absolute(), f"{label}: absolute path prohibited")
    _require(".." not in relative.parts, f"{label}: escaping path prohibited")
    current = repo_root
    for part in relative.parts:
        current = current / part
        _require(not current.is_symlink(), f"{label}: symlink-backed path prohibited")
    _require(current.is_file(), f"{label}: repository file missing: {raw_path}")
    resolved_root = repo_root.resolve(strict=True)
    resolved = current.resolve(strict=True)
    _require(
        resolved.is_relative_to(resolved_root),
        f"{label}: resolved path escaped repository",
    )
    return relative.as_posix()


def _validate_snapshot(
    plan: dict[str, Any], history_by_commit: dict[str, dict[str, Any]]
) -> None:
    """Validate the portable cutoff against the pinned full-history self-check."""
    _require(
        set(history_by_commit) == set(EXPECTED_HISTORY_COMMITS),
        "repository-history commit population drift",
    )
    _require(
        history_by_commit[AUDITED_COMMIT]["is_ancestor_of_current_main_cutoff"] is True,
        "audited commit ancestry attestation drift",
    )
    _require(
        history_by_commit[CURRENT_MAIN_CUTOFF]["tree_oid"] == CURRENT_MAIN_TREE_OID,
        "current-main tree attestation drift",
    )
    _require(
        plan["current_main_cutoff_tree_oid"] == CURRENT_MAIN_TREE_OID,
        "plan current-main tree OID drift",
    )


def _validate_plan_header(plan: dict[str, Any]) -> None:
    _require(set(plan) == PLAN_KEYS, "plan top-level keys are not exact")
    _require(plan["schema_version"] == PLAN_SCHEMA_VERSION, "plan schema drift")
    _require(plan["document_id"] == PLAN_DOCUMENT_ID, "plan document ID drift")
    _require(
        plan["authority_status"] == "active_pre_review_candidate_plan",
        "plan authority status drift",
    )
    _require(plan["gate_id"] == "P02", "plan gate identity drift")
    _require(
        plan["historical_audited_commit"] == AUDITED_COMMIT,
        "plan audited-commit drift",
    )
    _require(
        plan["historical_findings_register_path"] == SOURCE_REGISTER_RELATIVE,
        "plan findings-register path drift",
    )
    _require(
        plan["historical_findings_register_sha256"] == SOURCE_REGISTER_SHA256,
        "plan findings-register digest drift",
    )
    _require(
        type(plan["historical_finding_count"]) is int
        and plan["historical_finding_count"] == EXPECTED_FINDING_COUNT,
        "plan finding count drift",
    )
    _require(
        plan["current_main_cutoff_commit"] == CURRENT_MAIN_CUTOFF,
        "plan current-main commit drift",
    )
    _require(
        plan["current_main_cutoff_tree_oid"] == CURRENT_MAIN_TREE_OID,
        "plan current-main tree drift",
    )
    _require(plan["release_status"] == "HOLD", "plan release HOLD missing")
    _require(
        plan["independent_review_status"] == "pending_independent_review",
        "plan cannot claim independent review",
    )
    _require(
        plan["default_state_by_audited_status"] == DEFAULT_STATE_BY_AUDITED_STATUS,
        "plan default-state mapping drift",
    )
    created_at = plan["created_at"]
    _require(isinstance(created_at, str), "plan created_at must be a string")
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise FindingsOverlayBuildError("plan created_at is not ISO-8601") from exc
    _require(parsed.utcoffset() is not None, "plan created_at must include UTC offset")
    _require(
        plan["immutability_rule"]
        == (
            "Do not edit findings_register.v2.json or any audited-commit field to "
            "express current-main remediation; rebuild this additive overlay from the "
            "exact source hash and issue a new overlay version for later evidence."
        ),
        "plan immutability rule drift",
    )
    limitations = plan["limitations"]
    _require(
        isinstance(limitations, list)
        and len(limitations) >= 4
        and all(
            isinstance(item, str) and len(item.strip()) >= 30 for item in limitations
        ),
        "plan limitations are incomplete",
    )


def _validate_history_self_check(
    plan: dict[str, Any], repo_root: Path
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate the portable, explicitly non-independent full-history receipt."""
    reference = plan["repository_history_implementer_self_check"]
    _require(isinstance(reference, dict), "history self-check reference missing")
    _require(
        reference
        == {
            "path": HISTORY_SELF_CHECK_RELATIVE,
            "sha256": HISTORY_SELF_CHECK_SHA256,
            "review_kind": "implementer_self_check",
            "independence_satisfied": False,
        },
        "history self-check reference drift",
    )
    path = _validate_repo_file(repo_root, "history self-check", reference["path"])
    _require(
        _sha256_file(repo_root / path) == HISTORY_SELF_CHECK_SHA256,
        "history self-check digest drift",
    )
    raw_text = (repo_root / path).read_text(encoding="utf-8")
    _require("/Users/" not in raw_text, "history self-check contains local paths")
    self_check = _load_object(repo_root / path)
    _require(
        set(self_check) == HISTORY_SELF_CHECK_KEYS,
        "history self-check top-level keys are not exact",
    )
    _require(
        self_check["schema_version"]
        == "dutchbay.p02_repository_history_implementer_self_check.v1",
        "history self-check schema drift",
    )
    _require(
        self_check["document_id"] == HISTORY_SELF_CHECK_DOCUMENT_ID,
        "history self-check document ID drift",
    )
    _require(
        self_check["created_at"] == plan["created_at"],
        "history self-check timestamp drift",
    )
    _require(self_check["gate_id"] == "P02", "history self-check gate drift")
    _require(
        self_check["repository"] == "arunakulat/dutchbay-epc-model",
        "history self-check repository drift",
    )
    environment = self_check["verification_environment"]
    _require(isinstance(environment, dict), "history verification environment missing")
    _require(
        environment
        == {
            "repository_was_shallow": False,
            "object_database_scope": "full_local_history_and_tags",
            "current_main_cutoff_commit": CURRENT_MAIN_CUTOFF,
            "current_main_cutoff_tree_oid": CURRENT_MAIN_TREE_OID,
        },
        "history verification environment drift",
    )
    raw_commits = self_check["commit_objects"]
    _require(isinstance(raw_commits, list), "history commit objects must be a list")
    commit_records: list[dict[str, Any]] = []
    for raw in raw_commits:
        _require(isinstance(raw, dict), "history commit record must be an object")
        record = cast(dict[str, Any], raw)
        _require(
            set(record) == HISTORY_COMMIT_KEYS,
            "history commit record keys are not exact",
        )
        _require(
            isinstance(record["commit"], str)
            and bool(HEX_40.fullmatch(record["commit"])),
            "history commit OID invalid",
        )
        _require(
            isinstance(record["tree_oid"], str)
            and bool(HEX_40.fullmatch(record["tree_oid"])),
            f"{record['commit']}: history tree OID invalid",
        )
        _require(
            isinstance(record["subject"], str) and bool(record["subject"].strip()),
            f"{record['commit']}: history subject missing",
        )
        _require(
            isinstance(record["role"], str) and len(record["role"].strip()) >= 15,
            f"{record['commit']}: history role missing",
        )
        _require(
            record["is_ancestor_of_current_main_cutoff"] is True,
            f"{record['commit']}: history ancestry is not attested",
        )
        commit_records.append(record)
    _require(
        [record["commit"] for record in commit_records] == EXPECTED_HISTORY_COMMITS,
        "history commit sequence drift",
    )
    history_by_commit = {str(record["commit"]): record for record in commit_records}
    _require(
        len(history_by_commit) == len(commit_records),
        "history self-check contains duplicate commits",
    )
    tag_object = self_check["tag_object"]
    _require(isinstance(tag_object, dict), "history tag object missing")
    _require(
        tag_object
        == {
            "name": "v15.4.0",
            "object_type": "tag",
            "tag_object_oid": "5bbfacc37e0f072d6ac59f96f648a9f14f364f83",
            "peeled_target_commit": "0379843b28c493a1957b6b24f2853dd92a9ace05",
            "canonical_object_body_sha256": (
                "7cb6b682021a5c5bad1e464c43b281ba07690614047a2c9830cd56d8c77ac6f7"
            ),
            "embedded_signature_present": False,
            "disposition": "unsigned_exception_accepted_by_user",
        },
        "history tag-object attestation drift",
    )
    _require(
        self_check["review"]
        == {
            "kind": "implementer_self_check",
            "independence_satisfied": False,
            "independent_reviewer_identity": None,
            "independent_decision": "pending",
        },
        "history self-check must remain explicitly non-independent",
    )
    _require(
        self_check["release_status"] == "HOLD",
        "history self-check release HOLD missing",
    )
    limitations = self_check["limitations"]
    _require(
        isinstance(limitations, list)
        and len(limitations) == 3
        and all(
            isinstance(item, str) and len(item.strip()) >= 50 for item in limitations
        ),
        "history self-check limitations drift",
    )
    return self_check, history_by_commit


def _validate_artifact_ref(
    evidence_id: str, raw: Any, repo_root: Path
) -> dict[str, str]:
    _require(isinstance(raw, dict), f"{evidence_id}: artifact must be an object")
    artifact = cast(dict[str, Any], raw)
    _require(
        set(artifact) == ARTIFACT_KEYS,
        f"{evidence_id}: artifact keys are not exact",
    )
    path = _validate_repo_file(repo_root, evidence_id, artifact["path"])
    sha256 = artifact["sha256"]
    _require(
        isinstance(sha256, str) and bool(HEX_64.fullmatch(sha256)),
        f"{evidence_id}: artifact SHA-256 invalid",
    )
    _require(
        _sha256_file(repo_root / path) == sha256,
        f"{evidence_id}: artifact digest drift: {path}",
    )
    role = artifact["role"]
    _require(
        isinstance(role, str) and len(role.strip()) >= 15,
        f"{evidence_id}: artifact role is too short",
    )
    return {"path": path, "sha256": sha256, "role": role}


def _validate_evidence_catalog(
    plan: dict[str, Any],
    repo_root: Path,
    history_by_commit: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    raw_records = plan["evidence_catalog"]
    _require(isinstance(raw_records, list), "evidence catalog must be a list")
    catalog: dict[str, dict[str, Any]] = {}
    for raw in raw_records:
        _require(isinstance(raw, dict), "evidence record must be an object")
        record = cast(dict[str, Any], raw)
        evidence_id = str(record.get("evidence_id", ""))
        _require(bool(evidence_id), "evidence ID missing")
        _require(evidence_id not in catalog, f"duplicate evidence ID: {evidence_id}")
        _require(
            set(record) == EVIDENCE_KEYS,
            f"{evidence_id}: evidence keys are not exact",
        )
        _require(
            evidence_id in EXPECTED_EVIDENCE_FINDINGS,
            f"unexpected evidence ID: {evidence_id}",
        )
        finding_ids = record["finding_ids"]
        _require(
            isinstance(finding_ids, list)
            and all(isinstance(item, str) for item in finding_ids)
            and set(finding_ids) == EXPECTED_EVIDENCE_FINDINGS[evidence_id]
            and len(finding_ids) == len(set(finding_ids)),
            f"{evidence_id}: finding scope drift",
        )
        _require(
            record["evidence_class"] == EXPECTED_EVIDENCE_CLASS[evidence_id],
            f"{evidence_id}: evidence class drift",
        )
        _require(
            record["status"] == EXPECTED_EVIDENCE_STATUS[evidence_id],
            f"{evidence_id}: evidence status drift",
        )
        expected_pr_urls = [
            f"https://github.com/arunakulat/dutchbay-epc-model/pull/{number}"
            for number in EXPECTED_EVIDENCE_PRS[evidence_id]
        ]
        _require(
            record["pull_request_urls"] == expected_pr_urls,
            f"{evidence_id}: pull-request sequence drift",
        )
        commits = record["merge_commits"]
        _require(
            commits == EXPECTED_EVIDENCE_COMMITS[evidence_id],
            f"{evidence_id}: merge-commit sequence drift",
        )
        for commit in commits:
            _require(
                isinstance(commit, str) and bool(HEX_40.fullmatch(commit)),
                f"{evidence_id}: invalid merge commit",
            )
            _require(commit in history_by_commit, f"{evidence_id}: commit not attested")
            _require(
                history_by_commit[commit]["is_ancestor_of_current_main_cutoff"] is True,
                f"{evidence_id}: merge commit ancestry is not attested",
            )
        raw_artifacts = record["artifact_refs"]
        _require(
            isinstance(raw_artifacts, list) and len(raw_artifacts) > 0,
            f"{evidence_id}: artifact references missing",
        )
        artifacts = [
            _validate_artifact_ref(evidence_id, item, repo_root)
            for item in raw_artifacts
        ]
        paths = [artifact["path"] for artifact in artifacts]
        _require(len(paths) == len(set(paths)), f"{evidence_id}: duplicate artifact")
        for field in ("scope", "limitations"):
            _require(
                isinstance(record[field], str) and len(record[field].strip()) >= 50,
                f"{evidence_id}: {field} is too short",
            )
        normalized = copy.deepcopy(record)
        normalized["artifact_refs"] = artifacts
        catalog[evidence_id] = normalized
    _require(
        set(catalog) == set(EXPECTED_EVIDENCE_FINDINGS),
        "evidence catalog population mismatch",
    )
    return catalog


def _validate_tag_exception(
    plan: dict[str, Any], repo_root: Path, history_self_check: dict[str, Any]
) -> dict[str, Any]:
    raw = plan["release_provenance_exception"]
    _require(isinstance(raw, dict), "release provenance exception must be an object")
    exception = cast(dict[str, Any], raw)
    _require(set(exception) == TAG_EXCEPTION_KEYS, "tag exception keys are not exact")
    _require(exception["tag_name"] == "v15.4.0", "tag exception name drift")
    _require(
        exception["tag_object_oid"] == "5bbfacc37e0f072d6ac59f96f648a9f14f364f83",
        "tag object OID drift",
    )
    _require(
        exception["target_commit"] == "0379843b28c493a1957b6b24f2853dd92a9ace05",
        "tag target commit drift",
    )
    _require(
        exception["signature_status"] == "unsigned_exception_accepted_by_user",
        "unsigned tag exception status drift",
    )
    tag_attestation = history_self_check["tag_object"]
    _require(
        tag_attestation["object_type"] == "tag"
        and tag_attestation["tag_object_oid"] == exception["tag_object_oid"]
        and tag_attestation["peeled_target_commit"] == exception["target_commit"]
        and tag_attestation["embedded_signature_present"] is False
        and tag_attestation["disposition"] == "unsigned_exception_accepted_by_user",
        "v15.4.0 portable tag attestation drift",
    )
    control = exception["acceptance_control_ref"]
    _require(isinstance(control, dict), "tag acceptance control missing")
    control = cast(dict[str, Any], control)
    _require(set(control) == {"path", "sha256"}, "tag acceptance keys are not exact")
    path = _validate_repo_file(repo_root, "tag exception", control["path"])
    _require(
        control["sha256"]
        == "7e22468672ff52cd70b669fb85a2dd16087477785f432b8b14ff74940877e799",
        "tag acceptance-control digest declaration drift",
    )
    _require(
        _sha256_file(repo_root / path) == control["sha256"],
        "tag acceptance-control digest drift",
    )
    _require(
        isinstance(exception["limitation"], str)
        and "not a claim that the tag is cryptographically signed"
        in exception["limitation"],
        "tag exception limitation is incomplete",
    )
    return copy.deepcopy(exception)


def verify_full_repository_history(
    repo_root: Path = REPO_ROOT,
) -> dict[str, int | str | bool]:
    """Reperform the self-check when a non-shallow Git object database is available."""
    top_level = Path(_run_git(repo_root, "rev-parse", "--show-toplevel")).resolve()
    _require(top_level == repo_root.resolve(), "repository-root substitution detected")
    _require(
        _run_git(repo_root, "rev-parse", "--is-shallow-repository") == "false",
        "full repository-history verification requires a non-shallow clone",
    )
    _require(
        _sha256_file(HISTORY_SELF_CHECK) == HISTORY_SELF_CHECK_SHA256,
        "history self-check digest drift",
    )
    self_check = _load_object(HISTORY_SELF_CHECK)
    commit_records = cast(list[dict[str, Any]], self_check["commit_objects"])
    for record in commit_records:
        commit = str(record["commit"])
        _require(
            _run_git(repo_root, "cat-file", "-t", commit) == "commit",
            f"history object is not a commit: {commit}",
        )
        _require(
            _run_git(repo_root, "rev-parse", f"{commit}^{{tree}}")
            == record["tree_oid"],
            f"history tree OID drift: {commit}",
        )
        _require(
            _run_git(repo_root, "show", "-s", "--format=%s", commit)
            == record["subject"],
            f"history commit subject drift: {commit}",
        )
        _require(
            _is_ancestor(repo_root, commit, CURRENT_MAIN_CUTOFF)
            is record["is_ancestor_of_current_main_cutoff"],
            f"history ancestry drift: {commit}",
        )
    tag = cast(dict[str, Any], self_check["tag_object"])
    _require(
        _run_git(repo_root, "cat-file", "-t", "refs/tags/v15.4.0")
        == tag["object_type"],
        "v15.4.0 object type drift",
    )
    _require(
        _run_git(repo_root, "rev-parse", "refs/tags/v15.4.0") == tag["tag_object_oid"],
        "v15.4.0 tag object drift",
    )
    _require(
        _run_git(repo_root, "rev-parse", "refs/tags/v15.4.0^{}")
        == tag["peeled_target_commit"],
        "v15.4.0 peeled target drift",
    )
    tag_body = _run_git_bytes(repo_root, "cat-file", "-p", "refs/tags/v15.4.0")
    _require(
        hashlib.sha256(tag_body).hexdigest() == tag["canonical_object_body_sha256"],
        "v15.4.0 canonical object body drift",
    )
    embedded_signature = (
        b"-----BEGIN PGP SIGNATURE-----" in tag_body
        or b"-----BEGIN SSH SIGNATURE-----" in tag_body
    )
    _require(
        embedded_signature is tag["embedded_signature_present"],
        "v15.4.0 embedded-signature disposition drift",
    )
    return {
        "status": "PASS",
        "repository_was_shallow": False,
        "commit_objects": len(commit_records),
        "ancestry_checks": len(commit_records),
        "tag_object_verified": True,
        "independence_satisfied": False,
    }


def _validate_overrides(
    plan: dict[str, Any],
    finding_ids: set[str],
    evidence: dict[str, dict[str, Any]],
    repo_root: Path,
) -> dict[str, dict[str, Any]]:
    raw_records = plan["overrides"]
    _require(isinstance(raw_records, list), "overrides must be a list")
    overrides: dict[str, dict[str, Any]] = {}
    for raw in raw_records:
        _require(isinstance(raw, dict), "override must be an object")
        record = cast(dict[str, Any], raw)
        finding_id = str(record.get("finding_id", ""))
        _require(bool(finding_id), "override finding ID missing")
        _require(finding_id not in overrides, f"duplicate override: {finding_id}")
        _require(
            set(record) == OVERRIDE_KEYS,
            f"{finding_id}: override keys are not exact; audited fields cannot be overridden",
        )
        _require(finding_id in finding_ids, f"unknown override finding: {finding_id}")
        _require(
            record["current_state"] == EXPECTED_OVERRIDE_STATES.get(finding_id),
            f"{finding_id}: current state drift",
        )
        evidence_ids = record["evidence_ids"]
        _require(
            isinstance(evidence_ids, list)
            and set(evidence_ids) == EXPECTED_FINDING_EVIDENCE[finding_id]
            and len(evidence_ids) == len(set(evidence_ids)),
            f"{finding_id}: evidence mapping drift",
        )
        for evidence_id in evidence_ids:
            _require(evidence_id in evidence, f"{finding_id}: unknown evidence ID")
            _require(
                finding_id in evidence[evidence_id]["finding_ids"],
                f"{finding_id}: evidence scope mismatch",
            )
        seams = record["current_code_seams"]
        _require(
            isinstance(seams, list) and len(seams) > 0,
            f"{finding_id}: current code seams missing",
        )
        normalized_seams = [
            _validate_repo_file(repo_root, finding_id, seam) for seam in seams
        ]
        _require(
            len(normalized_seams) == len(set(normalized_seams)),
            f"{finding_id}: duplicate current code seam",
        )
        expected_review = (
            "not_applicable_until_authenticated_evidence"
            if finding_id == "P2-F5-02"
            else "pending_independent_review"
        )
        _require(
            record["review_status"] == expected_review,
            f"{finding_id}: review status drift",
        )
        for field in ("remaining_gate", "limitations"):
            _require(
                isinstance(record[field], str) and len(record[field].strip()) >= 80,
                f"{finding_id}: {field} is too short",
            )
        normalized = copy.deepcopy(record)
        normalized["current_code_seams"] = normalized_seams
        overrides[finding_id] = normalized
    _require(
        set(overrides) == set(EXPECTED_OVERRIDE_STATES),
        "override population mismatch",
    )
    _require(
        set(overrides["P2-F5-01"]["evidence_ids"]).isdisjoint(
            overrides["P2-F5-02"]["evidence_ids"]
        ),
        "F5-01/F5-02 evidence sets overlap",
    )
    return overrides


def _validate_f5_separation(plan: dict[str, Any]) -> dict[str, Any]:
    raw = plan["f5_separation"]
    expected = {
        "f5_01_finding_id": "P2-F5-01",
        "f5_02_finding_id": "P2-F5-02",
        "netting_permitted": False,
        "shared_evidence_ids": [],
        "rule": F5_SEPARATION_RULE,
    }
    _require(raw == expected, "F5-01/F5-02 separation drift")
    return copy.deepcopy(cast(dict[str, Any], raw))


def _validate_source_findings(findings: dict[str, Any]) -> list[dict[str, Any]]:
    _require(
        findings.get("repository_commit") == AUDITED_COMMIT,
        "findings audited-commit identity drift",
    )
    raw_records = findings.get("findings")
    _require(isinstance(raw_records, list), "findings source records must be a list")
    raw_record_values = cast(list[Any], raw_records)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_record_values:
        _require(isinstance(raw, dict), "finding source row must be an object")
        record = cast(dict[str, Any], raw)
        finding_id = record.get("finding_id")
        _require(
            isinstance(finding_id, str) and bool(finding_id),
            "finding source ID missing",
        )
        finding_id = cast(str, finding_id)
        _require(finding_id not in seen, f"duplicate source finding ID: {finding_id}")
        seen.add(finding_id)
        _require(
            record.get("status") in DEFAULT_STATE_BY_AUDITED_STATUS,
            f"{finding_id}: audited status invalid",
        )
        _require(
            isinstance(record.get("title"), str)
            and isinstance(record.get("corrected_claim"), str),
            f"{finding_id}: audited claim text missing",
        )
        anchors = record.get("code_anchors")
        _require(
            isinstance(anchors, list), f"{finding_id}: code anchors must be a list"
        )
        anchor_values = cast(list[Any], anchors)
        for anchor in anchor_values:
            _require(isinstance(anchor, dict), f"{finding_id}: code anchor invalid")
            _require(
                anchor.get("repository_commit") == AUDITED_COMMIT,
                f"{finding_id}: current remediation entered an audited code anchor",
            )
        records.append(record)
    _require(len(records) == EXPECTED_FINDING_COUNT, "finding population drift")
    _require(len(seen) == EXPECTED_FINDING_COUNT, "finding IDs are not unique")
    counts = Counter(str(record["status"]) for record in records)
    _require(counts == EXPECTED_AUDITED_STATUS_COUNTS, "audited status counts drift")
    return records


def _default_current_state(audited_status: str) -> dict[str, Any]:
    state = DEFAULT_STATE_BY_AUDITED_STATUS[audited_status]
    gates = {
        "baseline_closed_current_state_not_reassessed": (
            "Reassess the historical closure against the current-main cutoff and obtain "
            "independent model-risk confirmation before relying on it for release."
        ),
        "deferred_current_state_not_examined": (
            "Resolve or govern the historical deferral, examine the current-main code and "
            "evidence state, and obtain independent model-risk review."
        ),
        "open_current_state_not_examined": (
            "Examine the finding against the current-main cutoff, bind any implementation "
            "or evidence result, and obtain independent model-risk review."
        ),
        "requires_correction_current_state_not_examined": (
            "Determine whether the required correction is present at the current-main "
            "cutoff, bind the evidence, and obtain independent model-risk review."
        ),
    }
    return {
        "state": state,
        "state_basis": "audited_status_default_not_current_examination",
        "current_code_seams": [],
        "evidence_ids": [],
        "review_status": "not_started",
        "remaining_gate": gates[state],
        "limitations": (
            "No current-main code examination or positive implementation evidence was "
            "admitted for this row in P02 v1; the audited baseline state is preserved."
        ),
    }


def build_controlled_overlay(
    findings: dict[str, Any],
    plan: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return a validated, deterministic additive current-state overlay."""
    _validate_plan_header(plan)
    history_self_check, history_by_commit = _validate_history_self_check(
        plan, repo_root
    )
    _validate_snapshot(plan, history_by_commit)
    source_records = _validate_source_findings(findings)
    finding_ids = {str(record["finding_id"]) for record in source_records}
    evidence = _validate_evidence_catalog(plan, repo_root, history_by_commit)
    tag_exception = _validate_tag_exception(plan, repo_root, history_self_check)
    overrides = _validate_overrides(plan, finding_ids, evidence, repo_root)
    f5_separation = _validate_f5_separation(plan)

    output_records: list[dict[str, Any]] = []
    for row_number, source in enumerate(source_records, 1):
        finding_id = str(source["finding_id"])
        if finding_id in overrides:
            override = overrides[finding_id]
            current = {
                "state": override["current_state"],
                "state_basis": "explicit_current_main_evidence_override",
                "current_code_seams": override["current_code_seams"],
                "evidence_ids": override["evidence_ids"],
                "review_status": override["review_status"],
                "remaining_gate": override["remaining_gate"],
                "limitations": override["limitations"],
            }
        else:
            current = _default_current_state(str(source["status"]))
        output_records.append(
            {
                "overlay_row_number": row_number,
                "finding_id": finding_id,
                "audited_record": {
                    "repository_commit": AUDITED_COMMIT,
                    "row_sha256": _canonical_sha256(source),
                    "title_sha256": _sha256_text(str(source["title"])),
                    "corrected_claim_sha256": _sha256_text(
                        str(source["corrected_claim"])
                    ),
                    "source_phase": source["source_phase"],
                    "severity": source["severity"],
                    "disposition": source["disposition"],
                    "status": source["status"],
                    "code_anchor_count": len(source["code_anchors"]),
                },
                "current_main": {
                    "evaluated_commit": CURRENT_MAIN_CUTOFF,
                    "evaluated_tree_oid": CURRENT_MAIN_TREE_OID,
                    **current,
                },
                "period_boundary": {
                    "audited_fields_modified": False,
                    "current_state_additive_only": True,
                },
                "hold_effect": HOLD_EFFECT,
            }
        )

    state_counts = Counter(
        str(record["current_main"]["state"]) for record in output_records
    )
    _require(
        state_counts == EXPECTED_CURRENT_STATE_COUNTS, "current-state counts drift"
    )
    _require(
        all(
            not record["period_boundary"]["audited_fields_modified"]
            and record["period_boundary"]["current_state_additive_only"]
            for record in output_records
        ),
        "period boundary drift",
    )
    plan_semantic_sha256 = _canonical_sha256(plan)
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": DOCUMENT_ID,
        "authority_status": "active_additive_candidate_overlay",
        "created_at": plan["created_at"],
        "gate_id": "P02",
        "p02_gate": {
            "status": "candidate_overlay_pending_independent_review",
            "completion_authorized": False,
            "independent_reviewer_identity": None,
        },
        "release_status": "HOLD",
        "source_findings_register": {
            "path": SOURCE_REGISTER_RELATIVE,
            "sha256": SOURCE_REGISTER_SHA256,
            "repository_commit": AUDITED_COMMIT,
            "record_count": EXPECTED_FINDING_COUNT,
        },
        "current_main_snapshot": {
            "commit": CURRENT_MAIN_CUTOFF,
            "tree_oid": CURRENT_MAIN_TREE_OID,
            "evidence_period": "current_main_cutoff_not_overlay_merge_commit",
        },
        "repository_history_implementer_self_check": {
            "path": HISTORY_SELF_CHECK_RELATIVE,
            "sha256": HISTORY_SELF_CHECK_SHA256,
            "review_kind": "implementer_self_check",
            "independence_satisfied": False,
            "commit_objects": len(history_by_commit),
            "tag_object_verified_in_full_history_self_check": True,
            "portable_validation_boundary": (
                "Shallow consumers validate the hash-bound self-check; they do not "
                "claim to have reperformed full-history object or ancestry checks."
            ),
        },
        "plan_input": {
            "path": "registers/findings_current_state_plan.v1.json",
            "semantic_sha256": plan_semantic_sha256,
            "immutability_rule": plan["immutability_rule"],
        },
        "coverage": {
            "record_count": len(output_records),
            "explicit_evidence_override_count": len(overrides),
            "implementation_delivered_review_pending_count": state_counts[
                DELIVERED_STATE
            ],
            "external_evidence_blocked_count": state_counts[EXTERNAL_BLOCKED_STATE],
            "current_state_not_reassessed_or_examined_count": len(output_records)
            - len(overrides),
            "independently_reviewed_count": 0,
            "hold_blocking_count": len(output_records),
            "current_state_counts": dict(sorted(state_counts.items())),
        },
        "controlled_vocabularies": {
            "current_state": sorted(EXPECTED_CURRENT_STATE_COUNTS),
            "review_status": [
                "not_applicable_until_authenticated_evidence",
                "not_started",
                "pending_independent_review",
            ],
            "hold_effect": [HOLD_EFFECT],
        },
        "evidence_catalog": [evidence[key] for key in sorted(evidence)],
        "release_provenance_exception": tag_exception,
        "f5_separation": f5_separation,
        "required_circulation_wording": (
            "This 111-row overlay preserves the audited findings register and records "
            "only five positively evidenced current-main implementation deliveries. "
            "Those five remain pending independent review; F5-02 remains separately "
            "blocked on authenticated external evidence; the other 105 rows are not "
            "reassessed. P02 is not complete and Board/lender release remains HOLD."
        ),
        "limitations": copy.deepcopy(plan["limitations"]),
        "records": output_records,
    }


def render_json(payload: dict[str, Any]) -> str:
    """Render the controlled overlay deterministically."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_from_disk() -> dict[str, Any]:
    """Load the exact governed inputs and return the controlled overlay."""
    _require(
        _sha256_file(FINDINGS_REGISTER) == SOURCE_REGISTER_SHA256,
        "historical findings register digest drift; audited fields cannot be rewritten",
    )
    raw_plan = PLAN.read_text(encoding="utf-8")
    _require("/Users/" not in raw_plan, "plan contains a machine-local path")
    payload = build_controlled_overlay(
        _load_object(FINDINGS_REGISTER), _load_object(PLAN), REPO_ROOT
    )
    rendered = render_json(payload)
    _require("/Users/" not in rendered, "overlay contains a machine-local path")
    return payload


def main() -> None:
    """Write the deterministic overlay and emit one concise receipt."""
    payload = build_from_disk()
    OUTPUT.write_text(render_json(payload), encoding="utf-8")
    receipt = {
        "status": "PASS",
        "release_status": payload["release_status"],
        "gate_status": payload["p02_gate"]["status"],
        "records": payload["coverage"]["record_count"],
        "output": OUTPUT.relative_to(REPO_ROOT).as_posix(),
        "output_sha256": _sha256_file(OUTPUT),
    }
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
