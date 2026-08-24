#!/usr/bin/env python3
"""Build the immutable 23-row issue #1110 remediation/release gate ledger.

The frozen GitHub issue body is the source population. The plan adds execution
order, ownership, dependencies, required evidence, completion criteria and
negative controls, but it is intentionally incapable of recording completion.
Results belong in a later additive overlay; this v1 plan and its descendants
must remain pre-execution, unchecked and HOLD-blocking.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, cast

PACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parents[2]
ISSUE_SNAPSHOT = (
    PACK_ROOT
    / "registers"
    / "history"
    / "github_issue_1110.remediation_and_release_gates.20260824.9f7348f7.md"
)
PLAN = PACK_ROOT / "registers" / "programme_gate_plan.v1.json"
JSON_OUTPUT = PACK_ROOT / "registers" / "programme_gate_ledger.v1.json"
CSV_OUTPUT = PACK_ROOT / "registers" / "programme_gate_ledger.v1.csv"

SCHEMA_VERSION = "1.0.0"
DOCUMENT_ID = "DUTCHBAY-1110-PROGRAMME-GATE-PLAN-v1"
CURRENT_MAIN_CUTOFF = "e788fe3b40bf0ffd3bcc3d40043bb94cfa6de5f4"
ISSUE_NUMBER = 1110
ISSUE_URL = "https://github.com/arunakulat/dutchbay-epc-model/issues/1110"
ISSUE_UPDATED_AT = "2026-08-24T11:29:43Z"
ISSUE_SNAPSHOT_RELATIVE = (
    "registers/history/"
    "github_issue_1110.remediation_and_release_gates.20260824.9f7348f7.md"
)
ISSUE_SNAPSHOT_SHA256 = (
    "cf8d4709e4939589284a57dbda8cc0e6249da0abb28b5a10f9eda8e4d735bd02"
)
ISSUE_BODY_SHA256 = "9f7348f7a5c56f8aff45a5074e323d96abda418567f8cfd0eefb16f43855e0b9"
BODY_BEGIN = "<!-- BEGIN EXACT GITHUB ISSUE BODY -->\n"
BODY_END = "<!-- END EXACT GITHUB ISSUE BODY -->"

EXPECTED_GATE_BY_ORDINAL = {
    1: "P01",
    2: "P02",
    3: "P03",
    4: "P04",
    5: "P05",
    6: "P06",
    7: "P07",
    8: "P08",
    9: "P09",
    10: "L01",
    11: "L02",
    12: "L03",
    13: "L04",
    14: "L05",
    15: "L06",
    16: "R01",
    17: "R02",
    18: "R03",
    19: "R04",
    20: "R05",
    21: "R06",
    22: "R07",
    23: "R08",
}
EXPECTED_SECTION_BY_ORDINAL = {
    **{ordinal: "reconciled_predecessor_queue" for ordinal in range(1, 10)},
    **{ordinal: "additional_live_remediation_gates" for ordinal in range(10, 16)},
    **{ordinal: "release_gates" for ordinal in range(16, 24)},
}
EXPECTED_SECTION_COUNTS = Counter(
    {
        "reconciled_predecessor_queue": 9,
        "additional_live_remediation_gates": 6,
        "release_gates": 8,
    }
)
EXPECTED_STAGES: dict[str, set[str]] = {
    "S01_CONTROL_BASELINE": {"P01", "P02", "P03"},
    "S02_EVIDENCE_EXECUTION": {"P04", "P05", "P06", "P07"},
    "S03_LINEAGE_RECONCILIATION": {"P08"},
    "S04_IMPLEMENTATION_REMEDIATION": {"L01", "L02", "L03", "L04", "L05"},
    "S05_PROTECTED_DELIVERY": {"L06"},
    "S06_RELEASE_QUALIFICATION": {"R01", "R02", "R03", "R04"},
    "S07_SYNTHESIS_GENERATION": {"R05"},
    "S08_RENDERED_OUTPUT_REVIEW": {"R06"},
    "S09_INDEPENDENT_DISPOSITION": {"R07"},
    "S10_PROGRAMME_CONSOLIDATION": {"P09"},
    "S11_AUTHORISED_CLOSURE": {"R08"},
}
STAGE_INDEX = {stage: index for index, stage in enumerate(EXPECTED_STAGES, 1)}

EXPECTED_PLAN_KEYS = {
    "gate_id",
    "source_checkbox_ordinal",
    "source_section",
    "execution_stage",
    "owner_role",
    "independent_reviewer_role",
    "initial_evidence_state",
    "known_artifact_refs",
    "dependencies",
    "evidence_requirements",
    "completion_criteria",
    "planned_negative_control",
    "limitations",
}
ALLOWED_INITIAL_EVIDENCE_STATES = {
    "blocked_external",
    "control_surface_published_execution_pending",
    "evidence_gap_must_remain_disclosed",
    "independent_review_required",
    "not_started",
    "partial_evidence_present",
    "requires_current_main_reconciliation",
    "requires_dolphin_inventory",
}
INITIAL_GATE_STATUS = "pending"
HOLD_EFFECT = "blocks_board_lender_release"
CLOSURE_RULE = (
    "Issue #1110 must remain OPEN unless R07 records RELEASED and every other "
    "gate is complete in an independently validated additive overlay; R08 is "
    "the only closure-action gate."
)


class GateLedgerBuildError(ValueError):
    """Raised when a programme-gate input or descendant fails closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GateLedgerBuildError(message)


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
    _require(path.is_file(), f"governed JSON is missing: {path.name}")
    _require(not path.is_symlink(), f"governed JSON cannot be a symlink: {path.name}")
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys
    )
    _require(isinstance(value, dict), f"JSON root must be an object: {path.name}")
    return cast(dict[str, Any], value)


def _extract_issue_body(snapshot_text: str) -> str:
    _require(isinstance(snapshot_text, str), "issue snapshot must be text")
    _require(snapshot_text.count(BODY_BEGIN) == 1, "issue-body start marker drift")
    _require(snapshot_text.count(BODY_END) == 1, "issue-body end marker drift")
    prefix, remainder = snapshot_text.split(BODY_BEGIN, 1)
    body, suffix = remainder.split(BODY_END, 1)
    _require(suffix == "\n", "unexpected content after issue-body end marker")
    expected_metadata = {
        "- Repository: `arunakulat/dutchbay-epc-model`",
        "- Issue: `1110`",
        f"- URL: `{ISSUE_URL}`",
        "- Title: `audit(programme): controlled successor, remediation queue, and Board/lender release gate`",
        "- State at retrieval: `OPEN`",
        f"- GitHub `updated_at`: `{ISSUE_UPDATED_AT}`",
        "- Retrieved at: `2026-08-24T11:34:04Z`",
        "- UTF-8 issue-body bytes: `5371`",
        f"- SHA-256 of the exact issue-body string: `{ISSUE_BODY_SHA256}`",
    }
    for line in expected_metadata:
        _require(line in prefix, f"issue snapshot metadata drift: {line}")
    _require(len(body.encode("utf-8")) == 5371, "issue-body byte-length drift")
    _require(_sha256_text(body) == ISSUE_BODY_SHA256, "issue-body digest drift")
    return body


def _parse_issue_checkboxes(body: str) -> list[dict[str, Any]]:
    heading_to_section = {
        "## Reconciled predecessor queue": "reconciled_predecessor_queue",
        "## Additional live remediation gates": "additional_live_remediation_gates",
        "## Release gates": "release_gates",
    }
    current_section: str | None = None
    records: list[dict[str, Any]] = []
    checkbox_pattern = re.compile(r"^- \[([ xX])\] (.+)$")
    for line in body.splitlines():
        if line.startswith("## "):
            current_section = heading_to_section.get(line)
            continue
        match = checkbox_pattern.fullmatch(line)
        if match is None:
            continue
        _require(
            current_section is not None, "checkbox outside governed source section"
        )
        ordinal = len(records) + 1
        records.append(
            {
                "ordinal": ordinal,
                "section": current_section,
                "checked": match.group(1).lower() == "x",
                "text": match.group(2),
            }
        )

    _require(len(records) == 23, f"issue checkbox population drift: {len(records)}")
    _require(
        Counter(str(record["section"]) for record in records)
        == EXPECTED_SECTION_COUNTS,
        "issue checkbox section-population drift",
    )
    _require(
        all(record["checked"] is False for record in records),
        "frozen source contains a checked gate",
    )
    for record in records:
        ordinal = cast(int, record["ordinal"])
        _require(
            record["section"] == EXPECTED_SECTION_BY_ORDINAL[ordinal],
            f"source section drift at checkbox {ordinal}",
        )
    return records


def _validate_plan_header(plan: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "document_id",
        "authority_status",
        "created_at",
        "source_issue_number",
        "source_issue_url",
        "source_issue_state_at_cutoff",
        "source_issue_updated_at",
        "source_issue_snapshot_path",
        "source_issue_snapshot_sha256",
        "source_issue_body_sha256",
        "current_main_cutoff_commit",
        "release_status",
        "immutability_rule",
        "closure_rule",
        "records",
    }
    _require(set(plan) == expected_keys, "plan top-level keys are not exact")
    _require(plan["schema_version"] == SCHEMA_VERSION, "plan schema_version drift")
    _require(plan["document_id"] == DOCUMENT_ID, "plan document_id drift")
    _require(
        plan["authority_status"] == "active_pre_execution_plan",
        "plan authority_status drift",
    )
    created_at = plan["created_at"]
    _require(isinstance(created_at, str), "plan created_at must be a string")
    try:
        parsed_created_at = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise GateLedgerBuildError("plan created_at is not ISO-8601") from exc
    _require(
        parsed_created_at.utcoffset() is not None,
        "plan created_at must include a UTC offset",
    )
    _require(plan["source_issue_number"] == ISSUE_NUMBER, "issue number drift")
    _require(plan["source_issue_url"] == ISSUE_URL, "issue URL drift")
    _require(
        plan["source_issue_state_at_cutoff"] == "OPEN",
        "issue cutoff state must be OPEN",
    )
    _require(
        plan["source_issue_updated_at"] == ISSUE_UPDATED_AT,
        "issue updated_at drift",
    )
    _require(
        plan["source_issue_snapshot_path"] == ISSUE_SNAPSHOT_RELATIVE,
        "issue snapshot path drift",
    )
    _require(
        plan["source_issue_snapshot_sha256"] == ISSUE_SNAPSHOT_SHA256,
        "issue snapshot digest drift",
    )
    _require(
        plan["source_issue_body_sha256"] == ISSUE_BODY_SHA256,
        "issue body digest drift",
    )
    _require(
        plan["current_main_cutoff_commit"] == CURRENT_MAIN_CUTOFF,
        "current-main cutoff drift",
    )
    _require(plan["release_status"] == "HOLD", "plan release HOLD is missing")
    _require(
        plan["immutability_rule"]
        == "Do not edit this v1 plan after execution begins; issue an additive completion overlay or a new version.",
        "plan immutability rule drift",
    )
    _require(plan["closure_rule"] == CLOSURE_RULE, "plan closure rule drift")
    _require(isinstance(plan["records"], list), "plan records must be a list")


def _validate_string_list(
    gate_id: str,
    field: str,
    value: Any,
    *,
    allow_empty: bool = False,
) -> list[str]:
    _require(isinstance(value, list), f"{gate_id}: {field} must be a list")
    values = cast(list[Any], value)
    _require(allow_empty or bool(values), f"{gate_id}: {field} must not be empty")
    _require(
        all(isinstance(item, str) and len(item.strip()) >= 20 for item in values),
        f"{gate_id}: {field} entries are too short",
    )
    result = cast(list[str], values)
    _require(len(result) == len(set(result)), f"{gate_id}: duplicate {field} entry")
    return result


def _validate_artifact_refs(gate_id: str, value: Any, repo_root: Path) -> list[str]:
    _require(isinstance(value, list), f"{gate_id}: known_artifact_refs must be a list")
    values = cast(list[Any], value)
    validated: list[str] = []
    for item in values:
        _require(
            isinstance(item, str) and bool(item),
            f"{gate_id}: artifact reference must be a non-empty string",
        )
        path = Path(cast(str, item))
        _require(not path.is_absolute(), f"{gate_id}: absolute artifact reference")
        _require(".." not in path.parts, f"{gate_id}: escaping artifact reference")
        candidate = repo_root / path
        root_resolved = repo_root.resolve()
        current = candidate
        while current != repo_root:
            _require(
                not current.is_symlink(),
                f"{gate_id}: symlink-backed artifact reference: {item}",
            )
            _require(
                current.parent != current,
                f"{gate_id}: artifact ancestry does not reach repository root",
            )
            current = current.parent
        _require(
            candidate.is_file(),
            f"{gate_id}: artifact reference is not a file: {item}",
        )
        _require(
            candidate.resolve(strict=True).is_relative_to(root_resolved),
            f"{gate_id}: artifact reference resolves outside repository: {item}",
        )
        validated.append(path.as_posix())
    _require(
        len(validated) == len(set(validated)),
        f"{gate_id}: duplicate artifact reference",
    )
    return validated


def _validate_plan_records(
    plan: dict[str, Any], repo_root: Path
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for raw in plan["records"]:
        _require(isinstance(raw, dict), "plan record must be an object")
        record = cast(dict[str, Any], raw)
        gate_id = str(record.get("gate_id", ""))
        _require(bool(gate_id), "plan record gate_id missing")
        _require(gate_id not in records, f"duplicate plan gate: {gate_id}")
        _require(
            set(record) == EXPECTED_PLAN_KEYS,
            f"{gate_id}: plan record keys are not exact",
        )
        ordinal = record["source_checkbox_ordinal"]
        _require(type(ordinal) is int, f"{gate_id}: source ordinal must be an integer")
        _require(
            EXPECTED_GATE_BY_ORDINAL.get(ordinal) == gate_id,
            f"{gate_id}: source ordinal mapping drift",
        )
        _require(
            record["source_section"] == EXPECTED_SECTION_BY_ORDINAL[ordinal],
            f"{gate_id}: source section mapping drift",
        )
        stage = record["execution_stage"]
        _require(
            isinstance(stage, str) and stage in EXPECTED_STAGES,
            f"{gate_id}: execution stage invalid",
        )
        _require(gate_id in EXPECTED_STAGES[stage], f"{gate_id}: stage mapping drift")
        for field in ("owner_role", "independent_reviewer_role"):
            _require(
                isinstance(record[field], str) and len(record[field].strip()) >= 10,
                f"{gate_id}: {field} missing",
            )
        _require(
            record["owner_role"] != record["independent_reviewer_role"],
            f"{gate_id}: owner and independent reviewer roles conflict",
        )
        _require(
            isinstance(record["initial_evidence_state"], str)
            and record["initial_evidence_state"] in ALLOWED_INITIAL_EVIDENCE_STATES,
            f"{gate_id}: initial evidence state invalid",
        )
        record["known_artifact_refs"] = _validate_artifact_refs(
            gate_id, record["known_artifact_refs"], repo_root
        )
        dependencies = record["dependencies"]
        _require(
            isinstance(dependencies, list), f"{gate_id}: dependencies must be a list"
        )
        dependency_values = cast(list[Any], dependencies)
        _require(
            all(isinstance(item, str) and bool(item) for item in dependency_values),
            f"{gate_id}: dependency IDs must be non-empty strings",
        )
        dependency_ids = cast(list[str], dependency_values)
        _require(gate_id not in dependency_ids, f"{gate_id}: self dependency")
        _require(
            len(dependency_ids) == len(set(dependency_ids)),
            f"{gate_id}: duplicate dependency",
        )
        record["dependencies"] = dependency_ids
        record["evidence_requirements"] = _validate_string_list(
            gate_id, "evidence_requirements", record["evidence_requirements"]
        )
        record["completion_criteria"] = _validate_string_list(
            gate_id, "completion_criteria", record["completion_criteria"]
        )
        negative_control = record["planned_negative_control"]
        _require(
            isinstance(negative_control, str) and len(negative_control.strip()) >= 50,
            f"{gate_id}: planned negative control is too short",
        )
        record["limitations"] = _validate_string_list(
            gate_id, "limitations", record["limitations"]
        )
        records[gate_id] = record

    expected_ids = set(EXPECTED_GATE_BY_ORDINAL.values())
    actual_ids = set(records)
    _require(
        actual_ids == expected_ids,
        "plan gate population mismatch: "
        f"missing={sorted(expected_ids - actual_ids)}, "
        f"extra={sorted(actual_ids - expected_ids)}",
    )
    for stage, expected_ids_for_stage in EXPECTED_STAGES.items():
        actual = {
            gate_id
            for gate_id, record in records.items()
            if record["execution_stage"] == stage
        }
        _require(
            actual == expected_ids_for_stage, f"{stage}: stage population mismatch"
        )

    for gate_id, record in records.items():
        for dependency_id in record["dependencies"]:
            _require(
                dependency_id in records,
                f"{gate_id}: unknown dependency {dependency_id}",
            )
            _require(
                STAGE_INDEX[records[dependency_id]["execution_stage"]]
                < STAGE_INDEX[record["execution_stage"]],
                f"{gate_id}: dependency is not in an earlier execution stage",
            )

    _require(
        records["L03"]["dependencies"] == ["P06"],
        "L03 must depend only on the separate F5-02 evidence gate P06",
    )
    _require(
        "R07" in records["P09"]["dependencies"],
        "P09 must wait for the independent release disposition",
    )
    _require(
        records["R08"]["dependencies"] == ["R07", "P09"],
        "R08 closure dependencies drift",
    )
    return records


def build_controlled_ledger(
    snapshot_text: str,
    plan: dict[str, Any],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Return a validated, deterministic pre-execution gate ledger."""
    _validate_plan_header(plan)
    issue_body = _extract_issue_body(snapshot_text)
    source_records = _parse_issue_checkboxes(issue_body)
    plan_by_id = _validate_plan_records(plan, repo_root)

    output_records: list[dict[str, Any]] = []
    for source in source_records:
        ordinal = cast(int, source["ordinal"])
        gate_id = EXPECTED_GATE_BY_ORDINAL[ordinal]
        planned = plan_by_id[gate_id]
        output_records.append(
            {
                "ledger_row_number": ordinal,
                "gate_id": gate_id,
                "source_checkbox_ordinal": ordinal,
                "source_section": source["section"],
                "source_checkbox_state": "unchecked",
                "source_checkbox_text": source["text"],
                "source_checkbox_text_sha256": _sha256_text(cast(str, source["text"])),
                "execution_stage": planned["execution_stage"],
                "owner_role": planned["owner_role"],
                "independent_reviewer": {
                    "required_role": planned["independent_reviewer_role"],
                    "identity": None,
                    "independence_statement": None,
                    "reviewed_at": None,
                },
                "initial_evidence_state": planned["initial_evidence_state"],
                "known_artifact_refs": planned["known_artifact_refs"],
                "dependencies": planned["dependencies"],
                "evidence_requirements": planned["evidence_requirements"],
                "completion_criteria": planned["completion_criteria"],
                "planned_negative_control": planned["planned_negative_control"],
                "limitations": [
                    "The live issue checkbox was unchecked at the frozen source cutoff.",
                    "No completion result or independent reviewer is recorded in v1.",
                    *planned["limitations"],
                ],
                "completion_record": {
                    "artifact_path": None,
                    "sha256": None,
                    "evidence_refs": [],
                    "reproduction_refs": [],
                    "completed_at": None,
                },
                "gate_status": INITIAL_GATE_STATUS,
                "closure_authorized": False,
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
        "current_main_cutoff_commit": CURRENT_MAIN_CUTOFF,
        "source_issue": {
            "number": ISSUE_NUMBER,
            "url": ISSUE_URL,
            "state_at_cutoff": "OPEN",
            "updated_at": ISSUE_UPDATED_AT,
            "snapshot_path": ISSUE_SNAPSHOT_RELATIVE,
            "snapshot_sha256": ISSUE_SNAPSHOT_SHA256,
            "body_sha256": ISSUE_BODY_SHA256,
            "checkbox_count": 23,
            "checked_count": 0,
            "unchecked_count": 23,
        },
        "plan_input": {
            "path": "registers/programme_gate_plan.v1.json",
            "semantic_sha256": plan_semantic_sha256,
            "immutability_rule": plan["immutability_rule"],
        },
        "coverage": {
            "record_count": 23,
            "section_counts": dict(sorted(EXPECTED_SECTION_COUNTS.items())),
            "stage_count": len(EXPECTED_STAGES),
            "pending_count": 23,
            "completion_hash_count": 0,
            "independently_reviewed_count": 0,
            "closure_authorized_count": 0,
            "hold_blocking_count": 23,
        },
        "controlled_vocabularies": {
            "initial_evidence_state": sorted(ALLOWED_INITIAL_EVIDENCE_STATES),
            "initial_gate_status": [INITIAL_GATE_STATUS],
            "future_completion_status": ["blocked", "completed", "deferred"],
            "hold_effect": [HOLD_EFFECT],
        },
        "f5_separation": {
            "f5_01_gate": "L01",
            "f5_02_evidence_gate": "P06",
            "f5_02_decision_gate": "L03",
            "rule": (
                "F5-01 and F5-02 remain separate rollback surfaces; P06 and L03 "
                "remain distinct, and synthetic material cannot satisfy either F5-02 gate."
            ),
        },
        "closure_control": {
            "release_decision_gate": "R07",
            "programme_consolidation_gate": "P09",
            "only_closure_action_gate": "R08",
            "rule": CLOSURE_RULE,
        },
        "required_circulation_wording": (
            "This 23-row ledger is a pre-execution control plan sourced from the "
            "unchecked issue #1110 queue. All 23 gates remain pending, have no "
            "completion hash or independent reviewer, authorize no closure, and "
            "block Board/lender release."
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
        "gate_id",
        "source_checkbox_ordinal",
        "source_section",
        "source_checkbox_state",
        "source_checkbox_text",
        "source_checkbox_text_sha256",
        "execution_stage",
        "owner_role",
        "independent_reviewer",
        "initial_evidence_state",
        "known_artifact_refs",
        "dependencies",
        "evidence_requirements",
        "completion_criteria",
        "planned_negative_control",
        "limitations",
        "completion_record",
        "gate_status",
        "closure_authorized",
        "hold_effect",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for record in payload["records"]:
        serialised = dict(record)
        for field in (
            "independent_reviewer",
            "known_artifact_refs",
            "dependencies",
            "evidence_requirements",
            "completion_criteria",
            "limitations",
            "completion_record",
        ):
            serialised[field] = json.dumps(
                serialised[field], ensure_ascii=False, separators=(",", ":")
            )
        serialised["closure_authorized"] = json.dumps(serialised["closure_authorized"])
        writer.writerow(serialised)
    return stream.getvalue()


def build_from_disk() -> dict[str, Any]:
    """Load the governed inputs and return the controlled ledger."""
    _require(ISSUE_SNAPSHOT.is_file(), "frozen issue snapshot is missing")
    _require(
        not ISSUE_SNAPSHOT.is_symlink(),
        "frozen issue snapshot cannot be a symlink",
    )
    _require(
        ISSUE_SNAPSHOT.resolve(strict=True).is_relative_to(PACK_ROOT.resolve()),
        "frozen issue snapshot resolves outside the pack",
    )
    _require(
        _sha256_file(ISSUE_SNAPSHOT) == ISSUE_SNAPSHOT_SHA256,
        "frozen issue snapshot digest drift",
    )
    return build_controlled_ledger(
        ISSUE_SNAPSHOT.read_text(encoding="utf-8"),
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
                "pending": payload["coverage"]["pending_count"],
                "completion_hashes": payload["coverage"]["completion_hash_count"],
                "closure_authorized": payload["coverage"]["closure_authorized_count"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
