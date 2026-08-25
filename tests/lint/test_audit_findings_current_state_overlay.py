"""Fail-closed controls for the additive P02 findings current-state overlay."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "scripts"
    / "build_findings_current_state_overlay.py"
)


def _load_builder() -> ModuleType:
    """Load the P02 builder without making the audit scripts a package."""
    spec = importlib.util.spec_from_file_location("findings_overlay_builder", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs(builder: ModuleType) -> tuple[dict[str, object], dict[str, object]]:
    findings = json.loads(builder.FINDINGS_REGISTER.read_text(encoding="utf-8"))
    plan = json.loads(builder.PLAN.read_text(encoding="utf-8"))
    return findings, plan


def test_findings_overlay_is_deterministic_complete_and_additive() -> None:
    """All 111 audited rows remain hash-bound while current state stays additive."""
    builder = _load_builder()
    payload = builder.build_from_disk()
    committed = builder.OUTPUT.read_text(encoding="utf-8")
    findings = json.loads(builder.FINDINGS_REGISTER.read_text(encoding="utf-8"))

    assert committed == builder.render_json(payload)
    assert (
        builder._sha256_file(builder.FINDINGS_REGISTER)
        == builder.SOURCE_REGISTER_SHA256
    )
    assert payload["release_status"] == "HOLD"
    assert payload["p02_gate"] == {
        "status": "candidate_overlay_pending_independent_review",
        "completion_authorized": False,
        "independent_reviewer_identity": None,
    }
    assert payload["coverage"]["record_count"] == 111
    assert payload["coverage"]["independently_reviewed_count"] == 0
    assert payload["coverage"]["hold_blocking_count"] == 111
    assert payload["coverage"]["current_state_not_reassessed_or_examined_count"] == 105
    assert Counter(
        row["current_main"]["state"] for row in payload["records"]
    ) == Counter(builder.EXPECTED_CURRENT_STATE_COUNTS)
    assert [row["finding_id"] for row in payload["records"]] == [
        row["finding_id"] for row in findings["findings"]
    ]
    assert len({row["finding_id"] for row in payload["records"]}) == 111
    assert (
        len({row["audited_record"]["row_sha256"] for row in payload["records"]}) == 111
    )

    for source, overlay in zip(findings["findings"], payload["records"], strict=True):
        assert overlay["audited_record"]["repository_commit"] == builder.AUDITED_COMMIT
        assert overlay["audited_record"]["row_sha256"] == builder._canonical_sha256(
            source
        )
        assert overlay["period_boundary"] == {
            "audited_fields_modified": False,
            "current_state_additive_only": True,
        }
        assert overlay["hold_effect"] == "blocks_board_lender_release"

    assert "/Users/" not in committed
    assert "/Users/" not in builder.PLAN.read_text(encoding="utf-8")
    assert payload["repository_history_implementer_self_check"] == {
        "path": builder.HISTORY_SELF_CHECK_RELATIVE,
        "sha256": builder.HISTORY_SELF_CHECK_SHA256,
        "review_kind": "implementer_self_check",
        "independence_satisfied": False,
        "commit_objects": 13,
        "tag_object_verified_in_full_history_self_check": True,
        "portable_validation_boundary": (
            "Shallow consumers validate the hash-bound self-check; they do not claim "
            "to have reperformed full-history object or ancestry checks."
        ),
    }


def test_findings_overlay_maps_only_evidenced_deliveries_and_keeps_f5_separate() -> (
    None
):
    """Positive delivery evidence must stay narrow, review-pending and non-netted."""
    builder = _load_builder()
    payload = builder.build_from_disk()
    by_id = {row["finding_id"]: row for row in payload["records"]}
    evidence = {row["evidence_id"]: row for row in payload["evidence_catalog"]}

    delivered = {
        finding_id
        for finding_id, row in by_id.items()
        if row["current_main"]["state"] == "implementation_delivered_review_pending"
    }
    assert delivered == {
        "P2-F5-01",
        "P2-MC-SENS-01",
        "P2-MC-SENS-02",
        "P3-EQ-04",
        "P3-MCFX-03",
    }
    assert all(
        by_id[finding_id]["current_main"]["review_status"]
        == "pending_independent_review"
        for finding_id in delivered
    )
    assert by_id["P2-F5-02"]["current_main"]["state"] == "external_evidence_blocked"
    assert (
        by_id["P2-F5-02"]["current_main"]["review_status"]
        == "not_applicable_until_authenticated_evidence"
    )
    assert "Synthetic lender terms" in by_id["P2-F5-02"]["current_main"]["limitations"]
    assert payload["f5_separation"]["netting_permitted"] is False
    assert payload["f5_separation"]["shared_evidence_ids"] == []
    assert set(by_id["P2-F5-01"]["current_main"]["evidence_ids"]).isdisjoint(
        by_id["P2-F5-02"]["current_main"]["evidence_ids"]
    )

    assert evidence["EVD-F5-01-FULL-SEQUENCE"]["merge_commits"] == [
        "72f1bf1e9601c815c53333f09c8f73a546b2c109",
        "e458a78c3377595e49b8c69ceb1afc5c5ff9869e",
        "dac8c7a36c63f1dbb8dcf855b263e645b57ed676",
        "7e64d336759292d1fa1c3f1533f6ec20ea6c0250",
        "32f83d2708759912636efe34cb795db60e0d1fa5",
        "15d450ec5eef88718286b3251e4264493a26538d",
    ]
    assert (
        "D1 receipt alone does not prove full F5-01 completion"
        in evidence["EVD-F5-01-FULL-SEQUENCE"]["limitations"]
    )
    assert evidence["EVD-F5-02-INTAKE-CONTROL"]["status"] == (
        "intake_ready_external_evidence_absent"
    )
    assert (
        "not F5-02 transaction evidence"
        in evidence["EVD-F5-02-INTAKE-CONTROL"]["limitations"]
    )


def test_unsigned_v154_exception_is_exact_and_does_not_claim_a_signature() -> None:
    """The accepted tag exception must preserve object identity and honest wording."""
    builder = _load_builder()
    exception = builder.build_from_disk()["release_provenance_exception"]

    assert exception["tag_name"] == "v15.4.0"
    assert exception["tag_object_oid"] == "5bbfacc37e0f072d6ac59f96f648a9f14f364f83"
    assert exception["target_commit"] == "0379843b28c493a1957b6b24f2853dd92a9ace05"
    assert exception["signature_status"] == "unsigned_exception_accepted_by_user"
    assert (
        "not a claim that the tag is cryptographically signed"
        in exception["limitation"]
    )


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("audited_field_in_override", "audited fields cannot be overridden"),
        ("unknown_override", "unknown override finding"),
        ("duplicate_override", "duplicate override"),
        ("unknown_evidence", "evidence mapping drift"),
        ("f5_shared_evidence", "F5-01/F5-02 separation drift"),
        ("tag_claim_signed", "unsigned tag exception status drift"),
        ("history_self_check_hash", "history self-check reference drift"),
        ("artifact_hash", "artifact digest drift"),
        ("machine_path_seam", "absolute path prohibited"),
        (
            "current_anchor_in_baseline",
            "current remediation entered an audited code anchor",
        ),
    ],
)
def test_findings_overlay_rejects_period_provenance_and_evidence_bypasses(
    mutation: str, expected: str
) -> None:
    """Current claims, false evidence and path laundering must fail closed."""
    builder = _load_builder()
    findings, plan = _inputs(builder)
    overrides = plan["overrides"]
    evidence = plan["evidence_catalog"]

    if mutation == "audited_field_in_override":
        overrides[0]["severity"] = "low"
    elif mutation == "unknown_override":
        overrides[0]["finding_id"] = "P2-NOT-A-REAL-FINDING"
    elif mutation == "duplicate_override":
        overrides.append(copy.deepcopy(overrides[0]))
    elif mutation == "unknown_evidence":
        overrides[0]["evidence_ids"] = ["EVD-NOT-REAL"]
    elif mutation == "f5_shared_evidence":
        plan["f5_separation"]["shared_evidence_ids"] = ["EVD-F5-01-FULL-SEQUENCE"]
    elif mutation == "tag_claim_signed":
        plan["release_provenance_exception"]["signature_status"] = "signed"
    elif mutation == "history_self_check_hash":
        plan["repository_history_implementer_self_check"]["sha256"] = "0" * 64
    elif mutation == "artifact_hash":
        evidence[0]["artifact_refs"][0]["sha256"] = "0" * 64
    elif mutation == "machine_path_seam":
        overrides[0]["current_code_seams"] = ["/Users/example/laundered.py"]
    else:
        anchored = next(row for row in findings["findings"] if row["code_anchors"])
        anchored["code_anchors"][0]["repository_commit"] = builder.CURRENT_MAIN_CUTOFF

    with pytest.raises(builder.FindingsOverlayBuildError, match=expected):
        builder.build_controlled_overlay(findings, plan, builder.REPO_ROOT)


def test_portable_overlay_build_does_not_require_live_git_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Depth-1 consumers use the hash-bound receipt without silent Git fallback."""
    builder = _load_builder()

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("deterministic portable build attempted live Git history")

    monkeypatch.setattr(builder, "_run_git", forbidden)
    monkeypatch.setattr(builder, "_run_git_bytes", forbidden)
    monkeypatch.setattr(builder, "_is_ancestor", forbidden)
    payload = builder.build_from_disk()

    assert payload["coverage"]["record_count"] == 111
    assert (
        payload["repository_history_implementer_self_check"]["independence_satisfied"]
        is False
    )


def test_full_history_self_check_is_reperformed_or_refused_explicitly() -> None:
    """A full clone re-verifies objects; a shallow clone fails with a precise boundary."""
    builder = _load_builder()
    shallow = builder._run_git(
        builder.REPO_ROOT, "rev-parse", "--is-shallow-repository"
    )
    if shallow == "true":
        with pytest.raises(
            builder.FindingsOverlayBuildError,
            match="requires a non-shallow clone",
        ):
            builder.verify_full_repository_history()
    else:
        assert builder.verify_full_repository_history() == {
            "status": "PASS",
            "repository_was_shallow": False,
            "commit_objects": 13,
            "ancestry_checks": 13,
            "tag_object_verified": True,
            "independence_satisfied": False,
        }


def test_findings_overlay_rejects_a_current_claim_written_into_the_source_register(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A semantically improved historical row still violates the evidence period."""
    builder = _load_builder()
    mutated = tmp_path / "findings_register.v2.json"
    shutil.copy2(builder.FINDINGS_REGISTER, mutated)
    payload = json.loads(mutated.read_text(encoding="utf-8"))
    existing_claim = payload["findings"][0]["corrected_claim"]
    payload["findings"][0]["corrected_claim"] = (
        existing_claim + " Current main has now remediated this claim."
    )
    mutated.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(builder, "FINDINGS_REGISTER", mutated)

    with pytest.raises(
        builder.FindingsOverlayBuildError,
        match="historical findings register digest drift; audited fields cannot be rewritten",
    ):
        builder.build_from_disk()


def test_findings_overlay_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    """Governed plan JSON cannot exploit last-key-wins parsing."""
    builder = _load_builder()
    malformed = tmp_path / "duplicate.json"
    malformed.write_text('{"finding_id":"P2-F5-01","finding_id":"P2-F5-02"}\n')

    with pytest.raises(
        builder.FindingsOverlayBuildError, match="duplicate JSON key: finding_id"
    ):
        builder._load_object(malformed)


def test_findings_overlay_rejects_symlink_backed_repository_evidence(
    tmp_path: Path,
) -> None:
    """A display-relative path cannot redirect evidence outside its repository root."""
    builder = _load_builder()
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    alias = repository / "evidence.json"
    alias.symlink_to(outside)

    with pytest.raises(
        builder.FindingsOverlayBuildError, match="symlink-backed path prohibited"
    ):
        builder._validate_repo_file(repository, "P02", "evidence.json")
