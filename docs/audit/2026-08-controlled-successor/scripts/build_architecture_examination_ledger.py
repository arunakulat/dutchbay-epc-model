#!/usr/bin/env python3
"""Build the pre-execution 56-row architecture examination ledger.

The input plan is intentionally incapable of recording a completed examination.
It freezes the claim, current-main scout seam, owner, dependencies and planned
negative control before evidence is run.  Completed results belong in a later,
additive result overlay; they must never be back-written into this v1 plan.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, cast

PACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parents[2]
ARCHITECTURE_REGISTER = (
    PACK_ROOT
    / "registers"
    / "history"
    / "architecture_pointer_dispositions.pre-architecture-examination-plan.20260824.0b9c6803.json"
)
PLAN = PACK_ROOT / "registers" / "architecture_examination_plan.v1.json"
JSON_OUTPUT = PACK_ROOT / "registers" / "architecture_examination_ledger.v1.json"
CSV_OUTPUT = PACK_ROOT / "registers" / "architecture_examination_ledger.v1.csv"

SCHEMA_VERSION = "1.0.0"
DOCUMENT_ID = "DUTCHBAY-1110-ARCHITECTURE-EXAMINATION-PLAN-v1"
AUDITED_COMMIT = "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8"
CURRENT_MAIN_CUTOFF = "5503ff0e49683ddb8d8439d2460e2ebd08451985"
SOURCE_REGISTER_RELATIVE = (
    "registers/history/"
    "architecture_pointer_dispositions.pre-architecture-examination-plan."
    "20260824.0b9c6803.json"
)
SOURCE_REGISTER_SHA256 = (
    "0b9c68039c24a4f23b2c6299b4189db6b6cabaffddf0cec628de5afc70ea96d8"
)
EXPECTED_SOURCE_COUNTS = Counter({"not_examined": 51, "deferred": 5})
EXPECTED_BATCHES: dict[str, set[str]] = {
    "B01": {"RS-F3"},
    "B02": {"RS-F1", "RS-F5", "RS-F6", "RS-F7", "RS-F11"},
    "B03": {"RS-F2", "RS-F10"},
    "B04": {"RS-F8"},
    "B05": {"RS-B1", "RS-B2", "RS-B3", "RS-E1", "RS-E2"},
    "B06": {"RS-A13", "RS-B4", "RS-B5", "RS-B6", "RS-B9", "RS-C12"},
    "B07": {"RS-A11", "RS-A12", "RS-B7", "RS-B8", "RS-D11"},
    "B08": {"RS-C3", "RS-C4", "RS-C5", "RS-C6", "RS-C7"},
    "B09": {"RS-C9", "RS-C10", "RS-C11"},
    "B10": {"RS-C1", "RS-C2", "RS-C8"},
    "B11": {"RS-D5", "RS-D6", "RS-D7", "RS-D8", "RS-D10"},
    "B12": {"RS-D2", "RS-D4", "RS-D12"},
    "B13": {"RS-E3", "RS-E4", "RS-E5", "RS-E6", "RS-E7", "RS-E8", "RS-E9"},
    "B14": {"RS-E10", "RS-E11", "RS-E12", "RS-E13"},
    "B15": {"RS-A14"},
}
EXPECTED_PLAN_KEYS = {
    "pointer_id",
    "batch_id",
    "owner_role",
    "independent_reviewer_role",
    "current_main_code_seams",
    "planned_negative_control",
    "dependencies",
    "additional_unresolved_gaps",
}
EXPECTED_DEPENDENCY_KEYS = {
    "dependency_id",
    "kind",
    "status",
    "blocking",
    "requirement",
}
ALLOWED_DEPENDENCY_KINDS = {
    "registered_reproduction",
    "external_evidence",
    "cross_pointer",
}
ALLOWED_DEPENDENCY_STATUS = {
    "planned",
    "required_not_run",
    "blocked_external",
}
INITIAL_DISPOSITION = "pending_examination"
INITIAL_CONFIDENCE = "not_assessed"
HOLD_EFFECT = "blocks_board_lender_release"


class LedgerBuildError(ValueError):
    """Raised when the immutable examination plan fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LedgerBuildError(message)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object while refusing duplicate member names."""
    value: dict[str, Any] = {}
    for key, member in pairs:
        _require(key not in value, f"duplicate JSON key: {key}")
        value[key] = member
    return value


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    _require(isinstance(value, dict), f"JSON root must be an object: {path.name}")
    return cast(dict[str, Any], value)


def _validate_relative_file(repo_root: Path, pointer_id: str, value: Any) -> str:
    _require(isinstance(value, str) and bool(value), f"{pointer_id}: empty code seam")
    path = Path(value)
    _require(not path.is_absolute(), f"{pointer_id}: absolute code seam")
    _require(".." not in path.parts, f"{pointer_id}: escaping code seam")
    _require(
        (repo_root / path).is_file(),
        f"{pointer_id}: current-main code seam is not a file: {value}",
    )
    return path.as_posix()


def _validate_plan_header(plan: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "document_id",
        "authority_status",
        "created_at",
        "historical_audited_commit",
        "historical_register_path",
        "historical_register_sha256",
        "current_main_cutoff_commit",
        "release_status",
        "immutability_rule",
        "records",
    }
    _require(set(plan) == expected_keys, "plan top-level keys are not exact")
    _require(plan["schema_version"] == SCHEMA_VERSION, "plan schema_version drift")
    _require(plan["document_id"] == DOCUMENT_ID, "plan document_id drift")
    _require(
        plan["authority_status"] == "active_pre_execution_plan",
        "plan authority_status drift",
    )
    _require(
        plan["historical_audited_commit"] == AUDITED_COMMIT,
        "plan audited-commit drift",
    )
    _require(
        plan["historical_register_path"] == SOURCE_REGISTER_RELATIVE,
        "plan historical-register path drift",
    )
    _require(
        plan["historical_register_sha256"] == SOURCE_REGISTER_SHA256,
        "plan historical-register digest drift",
    )
    _require(plan["release_status"] == "HOLD", "plan release HOLD is missing")
    created_at = plan["created_at"]
    _require(isinstance(created_at, str), "plan created_at must be a string")
    try:
        parsed_created_at = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise LedgerBuildError("plan created_at is not ISO-8601") from exc
    _require(
        parsed_created_at.utcoffset() is not None,
        "plan created_at must include a UTC offset",
    )
    _require(
        plan["current_main_cutoff_commit"] == CURRENT_MAIN_CUTOFF,
        "plan current-main cutoff drift",
    )
    _require(
        plan["immutability_rule"]
        == "Do not edit this v1 plan after execution begins; issue an additive result overlay or a new version.",
        "plan immutability rule drift",
    )
    _require(isinstance(plan["records"], list), "plan records must be a list")


def _validate_dependency(pointer_id: str, value: Any) -> dict[str, Any]:
    _require(isinstance(value, dict), f"{pointer_id}: dependency must be an object")
    dependency = cast(dict[str, Any], value)
    _require(
        set(dependency) == EXPECTED_DEPENDENCY_KEYS,
        f"{pointer_id}: dependency keys are not exact",
    )
    _require(
        isinstance(dependency["dependency_id"], str)
        and bool(dependency["dependency_id"]),
        f"{pointer_id}: dependency_id missing",
    )
    _require(
        dependency["kind"] in ALLOWED_DEPENDENCY_KINDS,
        f"{pointer_id}: dependency kind invalid",
    )
    _require(
        dependency["status"] in ALLOWED_DEPENDENCY_STATUS,
        f"{pointer_id}: dependency status invalid",
    )
    _require(
        type(dependency["blocking"]) is bool,
        f"{pointer_id}: dependency blocking must be Boolean",
    )
    _require(
        isinstance(dependency["requirement"], str)
        and len(dependency["requirement"].strip()) >= 20,
        f"{pointer_id}: dependency requirement is too short",
    )
    return dependency


def _validate_plan_records(
    plan: dict[str, Any],
    expected_pointer_ids: set[str],
    repo_root: Path,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in plan["records"]:
        _require(isinstance(raw, dict), "plan record must be an object")
        record = cast(dict[str, Any], raw)
        pointer_id = str(record.get("pointer_id", ""))
        _require(bool(pointer_id), "plan record pointer_id missing")
        _require(pointer_id not in records, f"duplicate plan pointer: {pointer_id}")
        _require(
            set(record) == EXPECTED_PLAN_KEYS,
            f"{pointer_id}: plan record keys are not exact",
        )
        _require(
            record["batch_id"] in EXPECTED_BATCHES,
            f"{pointer_id}: batch_id invalid",
        )
        _require(
            pointer_id in EXPECTED_BATCHES[record["batch_id"]],
            f"{pointer_id}: pointer is assigned to the wrong batch",
        )
        for field in ("owner_role", "independent_reviewer_role"):
            _require(
                isinstance(record[field], str) and bool(record[field]),
                f"{pointer_id}: {field} missing",
            )
        _require(
            record["owner_role"] != record["independent_reviewer_role"],
            f"{pointer_id}: owner and independent reviewer roles conflict",
        )
        seams = record["current_main_code_seams"]
        _require(
            isinstance(seams, list) and len(seams) > 0,
            f"{pointer_id}: current-main code seams missing",
        )
        seam_values = cast(list[Any], seams)
        record["current_main_code_seams"] = [
            _validate_relative_file(repo_root, pointer_id, seam) for seam in seam_values
        ]
        _require(
            len(set(record["current_main_code_seams"]))
            == len(record["current_main_code_seams"]),
            f"{pointer_id}: duplicate current-main code seam",
        )
        negative_control = record["planned_negative_control"]
        _require(
            isinstance(negative_control, str) and len(negative_control.strip()) >= 50,
            f"{pointer_id}: planned negative control is too short",
        )
        dependencies = record["dependencies"]
        _require(
            isinstance(dependencies, list),
            f"{pointer_id}: dependencies must be a list",
        )
        record["dependencies"] = [
            _validate_dependency(pointer_id, dependency) for dependency in dependencies
        ]
        dependency_ids = [item["dependency_id"] for item in record["dependencies"]]
        _require(
            len(dependency_ids) == len(set(dependency_ids)),
            f"{pointer_id}: duplicate dependency_id",
        )
        gaps = record["additional_unresolved_gaps"]
        _require(
            isinstance(gaps, list)
            and all(isinstance(gap, str) and gap.strip() for gap in gaps),
            f"{pointer_id}: unresolved gaps must be non-empty strings",
        )
        records[pointer_id] = record

    actual_ids = set(records)
    _require(
        actual_ids == expected_pointer_ids,
        "plan pointer population mismatch: "
        f"missing={sorted(expected_pointer_ids - actual_ids)}, "
        f"extra={sorted(actual_ids - expected_pointer_ids)}",
    )
    for batch_id, expected_ids in EXPECTED_BATCHES.items():
        actual = {
            pointer_id
            for pointer_id, record in records.items()
            if record["batch_id"] == batch_id
        }
        _require(actual == expected_ids, f"{batch_id}: batch population mismatch")
    return records


def build_controlled_ledger(
    architecture: dict[str, Any],
    plan: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return a validated, deterministic pre-execution ledger payload."""
    _validate_plan_header(plan)
    source_records = architecture.get("records")
    _require(isinstance(source_records, list), "architecture records must be a list")
    source_record_values = cast(list[Any], source_records)
    selected = [
        cast(dict[str, Any], row)
        for row in source_record_values
        if isinstance(row, dict) and row.get("disposition") in EXPECTED_SOURCE_COUNTS
    ]
    source_counts = Counter(str(row["disposition"]) for row in selected)
    _require(
        source_counts == EXPECTED_SOURCE_COUNTS,
        f"architecture source counts drift: {dict(source_counts)}",
    )
    source_by_id = {str(row["pointer_id"]): row for row in selected}
    _require(len(source_by_id) == 56, "architecture source pointer IDs are not unique")
    plan_by_id = _validate_plan_records(plan, set(source_by_id), repo_root)

    output_records: list[dict[str, Any]] = []
    ordered_ids = sorted(
        source_by_id,
        key=lambda pointer_id: (
            int(plan_by_id[pointer_id]["batch_id"][1:]),
            pointer_id,
        ),
    )
    for row_number, pointer_id in enumerate(ordered_ids, 1):
        source = source_by_id[pointer_id]
        planned = plan_by_id[pointer_id]
        gaps = [
            "Dedicated current-main examination has not been executed.",
            "Independent review and a hash-bound result are absent.",
            *planned["additional_unresolved_gaps"],
        ]
        output_records.append(
            {
                "ledger_row_number": row_number,
                "pointer_id": pointer_id,
                "batch_id": planned["batch_id"],
                "historical_audited_commit": AUDITED_COMMIT,
                "historical_source_anchor": source["source_anchor"],
                "historical_area": source["area"],
                "historical_code_location": source["code_location"],
                "historical_risk_claim": source["risk_claim"],
                "historical_assigned_phase": source["assigned_phase"],
                "source_disposition": source["disposition"],
                "source_confidence": source["confidence"],
                "fixed_claim": source["risk_claim"],
                "fixed_claim_sha256": _sha256_text(source["risk_claim"]),
                "current_main_cutoff_commit": plan["current_main_cutoff_commit"],
                "current_main_code_seams": planned["current_main_code_seams"],
                "seam_mapping_status": "file_level_scout_only_not_examination",
                "historical_wording_status": "not_assessed",
                "owner_role": planned["owner_role"],
                "dependencies": planned["dependencies"],
                "planned_negative_control": planned["planned_negative_control"],
                "independent_reviewer": {
                    "required_role": planned["independent_reviewer_role"],
                    "identity": None,
                    "independence_statement": None,
                    "reviewed_at": None,
                },
                "result": {
                    "artifact_path": None,
                    "sha256": None,
                    "evidence_refs": [],
                    "reproduction_refs": [],
                },
                "disposition": INITIAL_DISPOSITION,
                "confidence": INITIAL_CONFIDENCE,
                "unresolved_gaps": gaps,
                "hold_effect": HOLD_EFFECT,
            }
        )

    plan_semantic_sha256 = _sha256_text(
        json.dumps(plan, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": DOCUMENT_ID,
        "authority_status": "active_pre_execution_ledger",
        "created_at": plan["created_at"],
        "historical_audited_commit": AUDITED_COMMIT,
        "current_main_cutoff_commit": plan["current_main_cutoff_commit"],
        "source_register": {
            "path": SOURCE_REGISTER_RELATIVE,
            "sha256": SOURCE_REGISTER_SHA256,
            "record_count": 72,
            "selected_source_disposition_counts": dict(
                sorted(EXPECTED_SOURCE_COUNTS.items())
            ),
        },
        "plan_input": {
            "path": "registers/architecture_examination_plan.v1.json",
            "semantic_sha256": plan_semantic_sha256,
            "immutability_rule": plan["immutability_rule"],
        },
        "coverage": {
            "record_count": len(output_records),
            "batch_count": len(EXPECTED_BATCHES),
            "pending_examination_count": len(output_records),
            "hash_bound_result_count": 0,
            "independently_reviewed_count": 0,
            "hold_blocking_count": len(output_records),
        },
        "controlled_vocabularies": {
            "future_final_disposition": [
                "blocked_external",
                "confirmed",
                "not_a_defect",
                "partially_confirmed",
                "refuted",
                "remediated",
            ],
            "initial_disposition": [INITIAL_DISPOSITION],
            "initial_confidence": [INITIAL_CONFIDENCE],
            "hold_effect": [HOLD_EFFECT],
        },
        "required_circulation_wording": (
            "This 56-row ledger is a pre-execution control plan, not completed "
            "architecture examination. All 56 rows remain pending, have no "
            "independent reviewer or result hash, and block Board/lender release."
        ),
        "release_status": "HOLD",
        "records": output_records,
    }


def render_json(payload: dict[str, Any]) -> str:
    """Render the controlled JSON descendant deterministically."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render_csv(payload: dict[str, Any]) -> str:
    """Render the human-review CSV descendant deterministically."""
    fieldnames = [
        "ledger_row_number",
        "pointer_id",
        "batch_id",
        "historical_audited_commit",
        "historical_source_anchor",
        "historical_area",
        "historical_code_location",
        "historical_risk_claim",
        "historical_assigned_phase",
        "source_disposition",
        "source_confidence",
        "fixed_claim",
        "fixed_claim_sha256",
        "current_main_cutoff_commit",
        "current_main_code_seams",
        "seam_mapping_status",
        "historical_wording_status",
        "owner_role",
        "dependencies",
        "planned_negative_control",
        "independent_reviewer",
        "result",
        "disposition",
        "confidence",
        "unresolved_gaps",
        "hold_effect",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in payload["records"]:
        serialised = dict(record)
        for field in (
            "current_main_code_seams",
            "dependencies",
            "independent_reviewer",
            "result",
            "unresolved_gaps",
        ):
            serialised[field] = json.dumps(
                serialised[field], ensure_ascii=False, separators=(",", ":")
            )
        writer.writerow(serialised)
    return stream.getvalue()


def build_from_disk() -> dict[str, Any]:
    """Load the governed inputs and return the controlled ledger."""
    _require(
        _sha256_file(ARCHITECTURE_REGISTER) == SOURCE_REGISTER_SHA256,
        "frozen architecture source-register digest drift",
    )
    return build_controlled_ledger(
        _load_object(ARCHITECTURE_REGISTER),
        _load_object(PLAN),
        REPO_ROOT,
    )


def main() -> None:
    """Write both deterministic descendants and emit one concise receipt."""
    payload = build_from_disk()
    JSON_OUTPUT.write_text(render_json(payload), encoding="utf-8")
    CSV_OUTPUT.write_text(render_csv(payload), encoding="utf-8", newline="")
    print(
        json.dumps(
            {
                "status": "PASS",
                "release_status": "HOLD",
                "records": payload["coverage"]["record_count"],
                "pending_examination": payload["coverage"]["pending_examination_count"],
                "result_hashes": payload["coverage"]["hash_bound_result_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
