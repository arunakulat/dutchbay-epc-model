"""Tests for RECRUIT-01 reviewer-session lifecycle, reconciliation, and retirement (#1954)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gwtf_reviewer_lifecycle as lifecycle  # noqa: E402

MODULE_3 = (
    REPO_ROOT
    / "docs"
    / "governance"
    / "recruit_01"
    / "03_independent_review_and_attestation.md"
)

COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
TREE_A = "c" * 40
BASE_A = "d" * 40
MANIFEST_A = "e" * 64
RECEIPT_A = "f" * 64
COORD_RECEIPT_A = "1" * 64

REQUIRED_SECTION_9_CONTROLS = (
    "prefer headless external review with structured outputs",
    "Never assert active execution from unread or activity UI indicators",
    "Historical acceptance never qualifies a new head",
    "missing or unmatched evidence, live writers or locks, ambiguous ownership, unresolved scope, stale exact-head review, unique unmerged commits, or dirty paths fail closed",
    "Preserve the shared governed environment at `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`",
    "database edits, forced lock removal, unsupported client mutation, and transcript deletion are forbidden",
)


def _valid_session(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "reviewer_identity": "domain-reviewer-1",
        "session_id": "rev-sess-001",
        "role": "domain",
        "execution_mode": "HEADLESS_STRUCTURED",
        "headless_supported": True,
        "execution_state": "COMPLETED",
        "candidate_commit": COMMIT_A,
        "candidate_tree": TREE_A,
        "base_sha": BASE_A,
        "subject_manifest_sha256": MANIFEST_A,
        "terminal_disposition": "ACCEPT",
        "receipt_sha256": RECEIPT_A,
        "evidence_matched": True,
        "coordinator_receipt_sha256": COORD_RECEIPT_A,
        "findings": [
            {
                "finding_id": "F-1",
                "state": "ACCEPTED_RESIDUAL_WITHIN_SCOPE",
                "summary": "Minor doc wording noted.",
            }
        ],
        "api_archive_state": "ACTIVE",
        "ui_activity_state": "NONE",
        "active_execution_claimed_from_ui": False,
    }
    record.update(overrides)
    return record


def _valid_retirement_plan(**overrides: Any) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "session_id": "rev-sess-001",
        "merge_ancestry_verified": True,
        "exact_branch_head_verified": True,
        "worktree_clean": True,
        "dirty_paths": [],
        "unique_commits": [],
        "active_processes": [],
        "unresolved_recovery_refs": [],
        "dedicated_env_path": None,
        "dedicated_env_owned": False,
        "original_evidence_preserved": True,
        "evidence_reconciled": True,
        "archival_action": "SUPPORTED_ARCHIVE",
        "archival_reversible": True,
        "api_archive_state": "ARCHIVED",
        "ui_activity_state": "RECENT_EVENTS_VISIBLE",
        "requested_mutations": [],
    }
    plan.update(overrides)
    return plan


def test_module_3_section_9_preserves_lifecycle_controls() -> None:
    """Module 3 §9 carries all required #1954 lifecycle and retirement controls."""
    text = " ".join(MODULE_3.read_text(encoding="utf-8").split())
    assert "## 9. Reviewer-session lifecycle" in text
    for control in REQUIRED_SECTION_9_CONTROLS:
        assert " ".join(control.split()) in text


@pytest.mark.parametrize("control", REQUIRED_SECTION_9_CONTROLS)
def test_module_3_section_9_negative_control_removal(control: str) -> None:
    """Removing any pinned control from §9 causes the guard check to fail."""
    text = " ".join(MODULE_3.read_text(encoding="utf-8").split())
    mutated = text.replace(" ".join(control.split()), "REMOVED")
    assert " ".join(control.split()) not in mutated


def test_reconcile_qualified_headless_session() -> None:
    """Exact-head headless session with matched evidence and no blockers qualifies."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
        writer_sessions={"writer-sess-999"},
    )
    assert result["qualified"] is True
    assert result["status"] == "QUALIFIED"
    assert result["blockers"] == []
    assert result["advisories"] == []


def test_reconcile_prefers_headless_when_supported() -> None:
    """Imported conversation emits an advisory when headless structured review is supported."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(execution_mode="IMPORTED_CONVERSATION", headless_supported=True),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
    )
    assert result["qualified"] is True
    assert "PREFER_HEADLESS_STRUCTURED_REVIEW" in result["advisories"]


def test_reconcile_blocks_stale_head_and_historical_acceptance() -> None:
    """Historical acceptance never qualifies a new head."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(candidate_commit=COMMIT_A),
        target_commit=COMMIT_B,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
    )
    assert result["qualified"] is False
    assert "STALE_OR_MISMATCHED_SUBJECT" in result["blockers"]


@pytest.mark.parametrize(
    "disposition",
    ["REJECT", "CHANGES_REQUESTED", "WITHHELD", "NO_EVIDENCE"],
)
def test_reconcile_blocks_vetoes_and_no_evidence(disposition: str) -> None:
    """Vetoes and NO_EVIDENCE remain blocking."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(terminal_disposition=disposition),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
    )
    assert result["qualified"] is False
    assert f"BLOCKING_DISPOSITION:{disposition}" in result["blockers"]


@pytest.mark.parametrize(
    ("kwargs", "expected_blocker"),
    [
        ({"live_locks": True}, "LIVE_WRITER_OR_LOCK"),
        ({"ambiguous_ownership": True}, "AMBIGUOUS_OWNERSHIP"),
        ({"unresolved_scope": True}, "UNRESOLVED_SCOPE"),
        ({"dirty_paths": ["scripts/foo.py"]}, "DIRTY_PATHS_PRESENT"),
        ({"unique_commits": [COMMIT_B]}, "UNIQUE_UNMERGED_COMMITS_PRESENT"),
        ({"writer_sessions": {"rev-sess-001"}}, "NON_INDEPENDENT_WRITER_SESSION"),
    ],
)
def test_reconcile_fails_closed_on_environment_and_independence_gates(
    kwargs: dict[str, Any], expected_blocker: str
) -> None:
    """Fail closed on live locks, ambiguous ownership, scope, dirty paths, or writer collision."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
        **kwargs,
    )
    assert result["qualified"] is False
    assert expected_blocker in result["blockers"]


def test_reconcile_blocks_missing_evidence_and_blocking_finding() -> None:
    """Missing/unmatched evidence and blocking findings fail closed."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(
            evidence_matched=False,
            receipt_sha256=None,
            findings=[
                {
                    "finding_id": "F-BLOCK",
                    "state": "BLOCKS_CURRENT_CANDIDATE",
                    "summary": "Must be fixed before merge.",
                }
            ],
        ),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
    )
    assert result["qualified"] is False
    assert "MISSING_OR_UNMATCHED_EVIDENCE" in result["blockers"]
    assert "BLOCKING_FINDING:F-BLOCK" in result["blockers"]


def test_validate_rejects_ui_activity_as_active_execution() -> None:
    """Never assert active execution from unread or activity UI indicators."""
    with pytest.raises(ValueError, match="unread or activity UI indicators"):
        lifecycle.validate_reviewer_session(
            _valid_session(active_execution_claimed_from_ui=True)
        )


def test_validate_requires_deferred_finding_metadata() -> None:
    """Deferred findings must name owner, destination, rationale, gate, and HOLD effect."""
    with pytest.raises(ValueError, match="acceptance_gate"):
        lifecycle.validate_reviewer_session(
            _valid_session(
                findings=[
                    {
                        "finding_id": "F-DEF",
                        "state": "DEFERRED_TO_NAMED_DOLPHIN",
                        "summary": "Defer follow-up.",
                        "owner": "dolphin-2",
                        "destination": "#1999",
                        "rationale": "Out of scope.",
                        "hold_effect": "NO_HOLD_LIFT",
                    }
                ]
            )
        )


def test_reconcile_reports_ui_limitation_distinctly() -> None:
    """API archived state and UI visible state are recorded distinctly without blocking."""
    result = lifecycle.reconcile_reviewer_evidence(
        _valid_session(
            api_archive_state="ARCHIVED",
            ui_activity_state="RECENT_EVENTS_VISIBLE",
        ),
        target_commit=COMMIT_A,
        target_tree=TREE_A,
        target_base=BASE_A,
        target_manifest_sha256=MANIFEST_A,
    )
    assert result["qualified"] is True
    assert result["api_archive_state"] == "ARCHIVED"
    assert result["ui_activity_state"] == "RECENT_EVENTS_VISIBLE"
    assert result["ui_limitation_note"] is not None


def test_verify_safe_retirement_passes_when_all_gates_satisfied() -> None:
    """Safe retirement passes when all six checks and archival guards pass."""
    result = lifecycle.verify_safe_retirement(_valid_retirement_plan())
    assert result["allowed"] is True
    assert result["status"] == "SAFE_TO_RETIRE"
    assert result["ui_limitation_reported"] is True


def test_verify_safe_retirement_protects_shared_governed_venv() -> None:
    """Shared governed venv must never be targeted as a dedicated removable env."""
    result = lifecycle.verify_safe_retirement(
        _valid_retirement_plan(
            dedicated_env_path=lifecycle.SHARED_GOVERNED_VENV,
            dedicated_env_owned=True,
        )
    )
    assert result["allowed"] is False
    assert "SHARED_GOVERNED_VENV_PROTECTED" in result["blockers"]
    assert result["checks"]["dedicated_env_ownership"] is False


@pytest.mark.parametrize(
    ("override", "expected_check"),
    [
        ({"merge_ancestry_verified": False}, "merge_ancestry"),
        ({"exact_branch_head_verified": False}, "exact_branch_head"),
        ({"dirty_paths": ["README.md"]}, "worktree_status"),
        ({"unique_commits": [COMMIT_B]}, "worktree_status"),
        ({"active_processes": ["pid:1234"]}, "process_usage"),
        ({"unresolved_recovery_refs": ["handover-1954"]}, "recovery_references"),
        ({"original_evidence_preserved": False}, "original_evidence_preserved"),
        ({"evidence_reconciled": False}, "archival_supported"),
        ({"archival_reversible": False}, "archival_supported"),
        ({"requested_mutations": ["DB_EDIT"]}, "no_forbidden_mutations"),
        (
            {"requested_mutations": ["TRANSCRIPT_DELETION"]},
            "no_forbidden_mutations",
        ),
    ],
)
def test_verify_safe_retirement_blocks_each_failed_gate(
    override: dict[str, Any], expected_check: str
) -> None:
    """Each retirement gate and forbidden mutation fails closed independently."""
    result = lifecycle.verify_safe_retirement(_valid_retirement_plan(**override))
    assert result["allowed"] is False
    assert result["checks"][expected_check] is False
    assert expected_check in result["blockers"]


def test_cli_reconcile_and_verify_retirement(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CLI emits JSON and returns 0 on pass, 2 on block, and 1 on malformed input."""
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps(_valid_session()), encoding="utf-8")

    rc_pass = lifecycle.main(
        [
            "reconcile",
            "--session",
            str(session_file),
            "--target-commit",
            COMMIT_A,
            "--target-tree",
            TREE_A,
            "--target-base",
            BASE_A,
            "--target-manifest-sha256",
            MANIFEST_A,
        ]
    )
    assert rc_pass == 0
    assert json.loads(capsys.readouterr().out)["status"] == "QUALIFIED"

    rc_block = lifecycle.main(
        [
            "reconcile",
            "--session",
            str(session_file),
            "--target-commit",
            COMMIT_B,
            "--target-tree",
            TREE_A,
            "--target-base",
            BASE_A,
            "--target-manifest-sha256",
            MANIFEST_A,
        ]
    )
    assert rc_block == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"

    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(_valid_retirement_plan()), encoding="utf-8")
    rc_retire = lifecycle.main(["verify-retirement", "--plan", str(plan_file)])
    assert rc_retire == 0
    assert json.loads(capsys.readouterr().out)["status"] == "SAFE_TO_RETIRE"

    rc_bad = lifecycle.main(
        ["verify-retirement", "--plan", str(tmp_path / "missing.json")]
    )
    assert rc_bad == 1
