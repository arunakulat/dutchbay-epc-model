"""Adversarial controls for the P03 primary-source review-plan candidate."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "docs" / "audit" / "2026-08-controlled-successor"
BUILDER = PACK_ROOT / "scripts" / "build_primary_source_review_plan.py"
CLI = REPO_ROOT / "scripts" / "verify_p03_primary_sources.py"


def _load_builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("p03_primary_source_builder", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source_inputs(
    builder: ModuleType,
) -> tuple[dict[str, object], dict[str, dict[str, object]], list[object]]:
    register = builder._load_object(
        builder.REGISTER_PATH,
        builder.REGISTER_SHA256,
        "primary-source register",
    )
    findings = builder._load_findings()
    manifest = builder._load_manifest()
    return register, findings, manifest


def _assert_control_error(
    builder: ModuleType, exc_info: pytest.ExceptionInfo[BaseException], code: str
) -> None:
    assert isinstance(exc_info.value, builder.PrimarySourceControlError)
    assert exc_info.value.code == code
    assert "/Users/" not in builder.failure_receipt(exc_info.value)["detail"]


def test_review_plan_is_population_exact_additive_and_hold_side() -> None:
    """All source rows and retained objects remain pending, covered and HOLD-blocking."""
    builder = _load_builder()
    payload = builder.build_review_plan()
    rendered = builder.render_json(payload)

    assert payload["schema_version"] == "dutchbay.primary_source_review_plan.v1"
    assert payload["gate_id"] == "P03"
    assert payload["release_status"] == "HOLD"
    assert payload["completion_authorized"] is False
    assert payload["independent_review"] == {
        "status": "pending_independent_review",
        "reviewer_identity": None,
        "decision": None,
        "decision_artifact_sha256": None,
        "review_policy": (
            "Verify all 42 claim rows and all 74 retained source objects; this is a "
            "population-exact review, not statistical sampling."
        ),
    }

    coverage = payload["coverage"]
    assert coverage["claim_records"] == 42
    assert coverage["claim_records_requiring_independent_semantic_review"] == 42
    assert coverage["claim_records_independently_reviewed"] == 0
    assert coverage["manifest_objects"] == 74
    assert coverage["manifest_objects_requiring_full_hash_verification"] == 74
    assert coverage["manifest_objects_independently_verified"] == 0
    assert coverage["artifact_references"] == 92
    assert coverage["unique_artifact_paths"] == 64
    assert coverage["claim_referenced_manifest_objects"] == 62
    assert coverage["retained_unreferenced_manifest_objects"] == 12
    assert coverage["governed_artifacts_outside_source_manifest"] == 2
    assert coverage["publication_rights_reviews_required"] == 42
    assert coverage["publication_rights_reviews_completed"] == 0
    assert coverage["hold_blocking_claim_records"] == 42
    assert coverage["evidence_status_counts"] == {
        "context_only": 3,
        "contradicts": 3,
        "supports": 36,
    }

    review_rows = payload["review_rows"]
    assert [row["record_id"] for row in review_rows] == [
        f"PSR-{number:04d}" for number in range(1, 43)
    ]
    assert all(
        row["review_result"]["status"] == "pending_independent_review"
        and row["review_result"]["reviewer_identity"] is None
        and row["review_result"]["result_artifact_sha256"] is None
        and row["publication_rights_status"]
        == "not_assessed_no_republication_authorized"
        and row["hold_effect"] == "blocks_board_lender_release"
        for row in review_rows
    )
    by_record = {row["record_id"]: row for row in review_rows}
    assert by_record["PSR-0005"]["transaction_evidence_status"] == "unavailable"
    assert by_record["PSR-0012"]["transaction_evidence_status"] == "not_applicable"
    assert by_record["PSR-0009"]["source_class"] == "analyst_judgment"
    assert by_record["PSR-0009"]["artifact_ref_count"] == 0

    manifest_rows = payload["manifest_objects"]
    assert len(manifest_rows) == 74
    assert Counter(row["reference_status"] for row in manifest_rows) == Counter(
        {"claim_referenced": 62, "retained_unreferenced": 12}
    )
    assert {
        row["relative_path"]
        for row in manifest_rows
        if row["reference_status"] == "retained_unreferenced"
    } == builder.EXPECTED_UNREFERENCED_MANIFEST_PATHS
    assert all(
        row["full_hash_verification_required"] is True
        and row["verification_status"] == "pending_independent_verification"
        for row in manifest_rows
    )

    assert payload["boundaries"] == {
        "source_register_modified": False,
        "source_manifest_modified": False,
        "evidence_status_upgrades_authorized": False,
        "publication_or_redistribution_rights_claimed": False,
        "synthetic_or_analyst_material_promoted_to_primary": False,
        "structural_or_hash_pass_is_semantic_acceptance": False,
        "f5_01_f5_02_netting_permitted": False,
    }
    assert "/Users/" not in rendered


def test_committed_plan_rebuilds_exactly_and_rejects_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The committed plan must be a byte-exact deterministic descendant."""
    builder = _load_builder()
    receipt = builder.validate_committed_plan()
    assert receipt == {
        "status": "PASS",
        "release_status": "HOLD",
        "gate_status": "pending_independent_review",
        "claim_records": 42,
        "manifest_objects": 74,
        "independently_reviewed": 0,
        "completion_authorized": False,
    }

    tampered = tmp_path / "primary_source_review_plan.v1.json"
    tampered.write_text(builder.PLAN_PATH.read_text(encoding="utf-8") + " ")
    monkeypatch.setattr(builder, "PLAN_PATH", tampered)
    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder.validate_committed_plan()
    _assert_control_error(builder, raised, "PLAN_DRIFT")


def test_evidence_boundary_escalation_is_rejected() -> None:
    """A valid-vocabulary status promotion cannot bypass the exact claim boundary."""
    builder = _load_builder()
    register, findings, manifest = _source_inputs(builder)
    mutated = copy.deepcopy(register)
    mutated["records"][4]["evidence_status"] = "supports"

    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder._validate_records(mutated, findings, manifest)
    _assert_control_error(builder, raised, "EVIDENCE_BOUNDARY_ESCALATION")


def test_analyst_judgment_cannot_be_laundered_as_publisher_evidence() -> None:
    """PSR-0009 must remain an artifact-free inference over six supporting rows."""
    builder = _load_builder()
    register, findings, manifest = _source_inputs(builder)
    mutated = copy.deepcopy(register)
    mutated["records"][8]["evidence_artifacts"] = copy.deepcopy(
        mutated["records"][5]["evidence_artifacts"]
    )

    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder._validate_records(mutated, findings, manifest)
    _assert_control_error(builder, raised, "ANALYST_EXCEPTION")


def test_csv_json_semantic_parity_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-consistently rehashed CSV still fails when one source field drifts."""
    builder = _load_builder()
    register, findings, manifest = _source_inputs(builder)
    records, _, _ = builder._validate_records(register, findings, manifest)
    altered = tmp_path / "primary_source_register.v2.csv"
    text = builder.CSV_PATH.read_text(encoding="utf-8")
    altered.write_text(text.replace("WIND-MEAS-12M", "WIND-MEAS-12X", 1))
    monkeypatch.setattr(builder, "CSV_PATH", altered)
    monkeypatch.setattr(builder, "CSV_SHA256", builder._sha256_file(altered))

    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder._validate_csv_parity(records)
    _assert_control_error(builder, raised, "CSV_PARITY")


@pytest.mark.parametrize(
    ("line", "expected_code"),
    [
        ("original/../escape.pdf", "PATH_INVALID"),
        ("original/a.pdf\\alias", "PATH_INVALID"),
        ("/absolute/a.pdf", "PATH_INVALID"),
    ],
)
def test_manifest_paths_cannot_escape_or_alias(line: str, expected_code: str) -> None:
    """Manifest parsing rejects traversal, platform separators and absolute paths."""
    builder = _load_builder()
    payload = f"{'0' * 64}  {line}\n".encode()
    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder.parse_source_manifest(payload)
    _assert_control_error(builder, raised, expected_code)


def test_manifest_parser_rejects_case_collisions_before_population_check() -> None:
    """Case-insensitive filesystems cannot collapse two retained source identities."""
    builder = _load_builder()
    payload = (f"{'0' * 64}  original/A.pdf\n{'1' * 64}  original/a.pdf\n").encode()
    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder.parse_source_manifest(payload)
    _assert_control_error(builder, raised, "MANIFEST_COLLISION")


def test_retained_tree_rejects_symlinks_and_special_root_forms(
    tmp_path: Path,
) -> None:
    """External evidence selection remains absolute, narrow and symlink-free."""
    builder = _load_builder()
    with pytest.raises(builder.PrimarySourceControlError) as relative:
        builder._safe_external_root(Path("relative/sources"))
    _assert_control_error(builder, relative, "ENVIRONMENT_PATH")

    real_parent = tmp_path / "one" / "two"
    real_root = real_parent / "sources"
    real_root.mkdir(parents=True)
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(builder.PrimarySourceControlError) as symlinked:
        builder._safe_external_root(alias_parent / "sources")
    _assert_control_error(builder, symlinked, "PATH_SYMLINK")


def test_retained_population_helper_rejects_inner_symlink(tmp_path: Path) -> None:
    """A symlink anywhere below original/converted cannot join the evidence set."""
    builder = _load_builder()
    root = tmp_path / "a" / "b" / "sources"
    (root / "original").mkdir(parents=True)
    (root / "converted").mkdir()
    target = tmp_path / "target.txt"
    target.write_text("not governed evidence\n")
    (root / "original" / "alias.txt").symlink_to(target)

    with pytest.raises(builder.PrimarySourceControlError) as raised:
        builder._collect_retained_paths(root)
    _assert_control_error(builder, raised, "SOURCE_SYMLINK")


@pytest.mark.parametrize(
    ("arguments", "expected_code"),
    [([], "ENVIRONMENT_PATH"), (["mode=unapproved"], "CLI_ARGUMENTS")],
)
def test_hydra_cli_fails_closed_without_logs_or_path_leak(
    tmp_path: Path, arguments: list[str], expected_code: str
) -> None:
    """The canonical CLI emits only one path-free JSON error and writes no logs."""
    environment = os.environ.copy()
    environment.pop("DUTCHBAY_P03_SOURCE_ROOT", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, str(CLI), *arguments],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    receipt = json.loads(completed.stderr)
    assert receipt["status"] == "FAIL"
    assert receipt["code"] == expected_code
    assert receipt["release_status"] == "HOLD"
    assert receipt["completion_authorized"] is False
    assert "/Users/" not in completed.stderr
    assert list(tmp_path.iterdir()) == []


def test_cli_and_config_preserve_hydra_json_only_policy() -> None:
    """The new operational entrypoint remains Hydra-based, JSON-only and argparse-free."""
    cli = CLI.read_text(encoding="utf-8")
    config = (REPO_ROOT / "conf" / "p03_primary_sources.yaml").read_text(
        encoding="utf-8"
    )
    assert "@hydra.main" in cli
    assert "import argparse" not in cli
    assert "json.dumps" in cli
    assert "output_subdir: null" in config
    assert "hydra/job_logging: disabled" in config
    assert "hydra/hydra_logging: disabled" in config
