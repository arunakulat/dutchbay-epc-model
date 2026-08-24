"""Repository gate for the August 2026 controlled audit successor pack."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "scripts"
    / "validate_published_pack.py"
)


def _load_validator() -> ModuleType:
    """Load the pack validator so refusal paths can be exercised directly."""
    spec = importlib.util.spec_from_file_location("audit_pack_validator", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_erratum_control_surface(module: ModuleType, destination: Path) -> None:
    """Copy only the files used by the focused erratum validation."""
    for relative in (
        module.IMMUTABLE_CONTROL_RECORD,
        module.RULESET_COUNT_ERRATUM,
        module.ARCHITECTURE_REGISTER,
    ):
        source = module.PACK_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def test_controlled_audit_successor_pack_is_internally_valid() -> None:
    """The published pack must remain manifest-complete and explicitly on HOLD."""
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"status": "PASS"' in completed.stdout
    assert '"release_status": "HOLD"' in completed.stdout
    assert '"ruleset_count_erratum": "PASS"' in completed.stdout
    assert '"pending_examination": 56' in completed.stdout
    assert '"programme_gates"' in completed.stdout
    assert '"pending": 23' in completed.stdout
    assert '"closure_authorized": 0' in completed.stdout


def test_architecture_examination_plan_is_exactly_pending_and_hold_blocking() -> None:
    """The v1 control plan must not masquerade as completed examination."""
    validator = _load_validator()
    builder = validator._load_architecture_examination_builder()
    payload = builder.build_from_disk()
    records = payload["records"]

    assert len(records) == 56
    assert Counter(record["source_disposition"] for record in records) == Counter(
        {"not_examined": 51, "deferred": 5}
    )
    assert {record["disposition"] for record in records} == {"pending_examination"}
    assert {record["confidence"] for record in records} == {"not_assessed"}
    assert all(record["result"]["sha256"] is None for record in records)
    assert all(record["independent_reviewer"]["identity"] is None for record in records)
    assert {record["hold_effect"] for record in records} == {
        "blocks_board_lender_release"
    }
    assert payload["release_status"] == "HOLD"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing_pointer", "plan pointer population mismatch"),
        ("escaping_seam", "escaping code seam"),
        ("reviewer_conflict", "owner and independent reviewer roles conflict"),
        ("smuggled_disposition", "plan record keys are not exact"),
    ],
)
def test_architecture_examination_plan_rejects_control_bypasses(
    mutation: str, expected: str
) -> None:
    """Population, path, independence and result-state bypasses must fail closed."""
    validator = _load_validator()
    builder = validator._load_architecture_examination_builder()
    architecture = json.loads(builder.ARCHITECTURE_REGISTER.read_text(encoding="utf-8"))
    plan = copy.deepcopy(json.loads(builder.PLAN.read_text(encoding="utf-8")))

    if mutation == "missing_pointer":
        plan["records"].pop()
    elif mutation == "escaping_seam":
        plan["records"][0]["current_main_code_seams"] = ["../outside.py"]
    elif mutation == "reviewer_conflict":
        plan["records"][0]["independent_reviewer_role"] = plan["records"][0][
            "owner_role"
        ]
    else:
        plan["records"][0]["disposition"] = "confirmed"

    with pytest.raises(builder.LedgerBuildError, match=expected):
        builder.build_controlled_ledger(architecture, plan, builder.REPO_ROOT)


def test_architecture_examination_plan_rejects_frozen_source_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The v1 plan must rebuild only from its exact byte-preserved source state."""
    validator = _load_validator()
    builder = validator._load_architecture_examination_builder()
    mutated_source = tmp_path / builder.ARCHITECTURE_REGISTER.name
    shutil.copy2(builder.ARCHITECTURE_REGISTER, mutated_source)
    mutated_source.write_text(
        mutated_source.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(builder, "ARCHITECTURE_REGISTER", mutated_source)

    with pytest.raises(
        builder.LedgerBuildError,
        match="frozen architecture source-register digest drift",
    ):
        builder.build_from_disk()


def test_architecture_examination_plan_rejects_duplicate_json_keys(
    tmp_path: Path,
) -> None:
    """Malformed governed JSON must not be normalized by last-key-wins parsing."""
    validator = _load_validator()
    builder = validator._load_architecture_examination_builder()
    malformed = tmp_path / "duplicate-key.json"
    malformed.write_text('{"pointer_id":"RS-B2","pointer_id":"RS-B3"}\n')

    with pytest.raises(
        builder.LedgerBuildError, match="duplicate JSON key: pointer_id"
    ):
        builder._load_object(malformed)


def test_programme_gate_plan_is_exactly_pending_open_and_hold_blocking() -> None:
    """The issue-derived v1 gate plan must authorize neither completion nor closure."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    payload = builder.build_from_disk()
    records = payload["records"]
    by_id = {record["gate_id"]: record for record in records}

    assert len(records) == 23
    assert Counter(record["source_section"] for record in records) == Counter(
        {
            "reconciled_predecessor_queue": 9,
            "additional_live_remediation_gates": 6,
            "release_gates": 8,
        }
    )
    assert {record["source_checkbox_state"] for record in records} == {"unchecked"}
    assert {record["gate_status"] for record in records} == {"pending"}
    assert all(record["completion_record"]["sha256"] is None for record in records)
    assert all(record["independent_reviewer"]["identity"] is None for record in records)
    assert not any(record["closure_authorized"] for record in records)
    assert {record["hold_effect"] for record in records} == {
        "blocks_board_lender_release"
    }
    assert payload["source_issue"]["state_at_cutoff"] == "OPEN"
    assert payload["release_status"] == "HOLD"
    assert payload["f5_separation"] == {
        "f5_01_gate": "L01",
        "f5_02_evidence_gate": "P06",
        "f5_02_decision_gate": "L03",
        "rule": (
            "F5-01 and F5-02 remain separate rollback surfaces; P06 and L03 "
            "remain distinct, and synthetic material cannot satisfy either F5-02 gate."
        ),
    }
    assert by_id["L03"]["dependencies"] == ["P06"]
    assert by_id["R08"]["dependencies"] == ["R07", "P09"]


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("missing_gate", "plan gate population mismatch"),
        ("escaping_artifact", "escaping artifact reference"),
        ("reviewer_conflict", "owner and independent reviewer roles conflict"),
        ("smuggled_status", "plan record keys are not exact"),
        ("unhashable_stage", "execution stage invalid"),
        ("unhashable_evidence_state", "initial evidence state invalid"),
        ("late_dependency", "dependency is not in an earlier execution stage"),
        ("f5_dependency_drift", "L03 must depend only"),
        ("closure_dependency_drift", "R08 closure dependencies drift"),
    ],
)
def test_programme_gate_plan_rejects_control_bypasses(
    mutation: str, expected: str
) -> None:
    """Population, provenance, independence, ordering and closure bypasses fail."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    snapshot = builder.ISSUE_SNAPSHOT.read_text(encoding="utf-8")
    plan = copy.deepcopy(json.loads(builder.PLAN.read_text(encoding="utf-8")))
    by_id = {record["gate_id"]: record for record in plan["records"]}

    if mutation == "missing_gate":
        plan["records"].pop()
    elif mutation == "escaping_artifact":
        plan["records"][0]["known_artifact_refs"] = ["../outside.json"]
    elif mutation == "reviewer_conflict":
        plan["records"][0]["independent_reviewer_role"] = plan["records"][0][
            "owner_role"
        ]
    elif mutation == "smuggled_status":
        plan["records"][0]["gate_status"] = "completed"
    elif mutation == "unhashable_stage":
        plan["records"][0]["execution_stage"] = ["S01_CONTROL_BASELINE"]
    elif mutation == "unhashable_evidence_state":
        plan["records"][0]["initial_evidence_state"] = {
            "value": "partial_evidence_present"
        }
    elif mutation == "late_dependency":
        by_id["L01"]["dependencies"] = ["R01"]
    elif mutation == "f5_dependency_drift":
        by_id["L03"]["dependencies"] = ["P06", "P01"]
    else:
        by_id["R08"]["dependencies"] = ["R07"]

    with pytest.raises(builder.GateLedgerBuildError, match=expected):
        builder.build_controlled_ledger(snapshot, plan, builder.REPO_ROOT)


def test_programme_gate_plan_rejects_frozen_issue_snapshot_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The v1 gate plan must rebuild only from the exact portable issue snapshot."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    mutated_source = tmp_path / builder.ISSUE_SNAPSHOT.name
    shutil.copy2(builder.ISSUE_SNAPSHOT, mutated_source)
    mutated_source.write_text(
        mutated_source.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(builder, "PACK_ROOT", tmp_path)
    monkeypatch.setattr(builder, "ISSUE_SNAPSHOT", mutated_source)

    with pytest.raises(
        builder.GateLedgerBuildError,
        match="frozen issue snapshot digest drift",
    ):
        builder.build_from_disk()


def test_programme_gate_source_rejects_checked_checkbox() -> None:
    """A checked live-source row cannot be represented as a pending v1 source."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    body = builder._extract_issue_body(
        builder.ISSUE_SNAPSHOT.read_text(encoding="utf-8")
    )
    mutated = body.replace("- [ ] **Checkpoint", "- [x] **Checkpoint", 1)

    with pytest.raises(
        builder.GateLedgerBuildError, match="frozen source contains a checked gate"
    ):
        builder._parse_issue_checkboxes(mutated)


def test_programme_gate_plan_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    """Duplicate governed JSON members cannot exploit last-key-wins parsing."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    malformed = tmp_path / "duplicate-gate-key.json"
    malformed.write_text('{"gate_id":"P01","gate_id":"R08"}\n')

    with pytest.raises(
        builder.GateLedgerBuildError, match="duplicate JSON key: gate_id"
    ):
        builder._load_object(malformed)


def test_programme_gate_plan_rejects_symlink_backed_artifact(
    tmp_path: Path,
) -> None:
    """A repository-relative display path cannot launder an external artifact."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    alias = repository / "evidence.json"
    alias.symlink_to(outside)

    with pytest.raises(
        builder.GateLedgerBuildError, match="symlink-backed artifact reference"
    ):
        builder._validate_artifact_refs("P01", ["evidence.json"], repository)


def test_programme_gate_plan_rejects_symlink_backed_governed_json(
    tmp_path: Path,
) -> None:
    """The governed plan cannot be redirected to an external JSON document."""
    validator = _load_validator()
    builder = validator._load_programme_gate_builder()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")
    alias = tmp_path / "programme_gate_plan.v1.json"
    alias.symlink_to(outside)

    with pytest.raises(builder.GateLedgerBuildError, match="cannot be a symlink"):
        builder._load_object(alias)


@pytest.mark.parametrize("mutation", ["record", "instruction"])
def test_ruleset_count_erratum_guard_rejects_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """The erratum guard must reject both provenance and instruction drift."""
    validator = _load_validator()
    pack_root = tmp_path / "pack"
    _copy_erratum_control_surface(validator, pack_root)
    monkeypatch.setattr(validator, "PACK_ROOT", pack_root)

    if mutation == "record":
        record = pack_root / validator.IMMUTABLE_CONTROL_RECORD
        record.write_text(record.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        expected = "immutable programming record digest drift"
    else:
        erratum = pack_root / validator.RULESET_COUNT_ERRATUM
        text = erratum.read_text(encoding="utf-8").replace(
            validator.STABLE_RULESET_INGRESS_INSTRUCTION,
            "Re-ingress a copied fixed count",
        )
        erratum.write_text(text, encoding="utf-8")
        expected = "source-derived re-ingress instruction"

    with pytest.raises(validator.ValidationError, match=expected):
        validator._validate_ruleset_count_erratum()
