#!/usr/bin/env python3
"""Fail-closed validation for the repository-published audit successor pack."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, cast

PACK_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PACK_ROOT / "PUBLICATION_MANIFEST.sha256"
AUDITED_COMMIT = "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8"
IMMUTABLE_CONTROL_RECORD = Path(
    "06_CURRENT_PROGRAMMING_REVIEW_AND_TODO_v3_2026-08-19.md"
)
IMMUTABLE_CONTROL_RECORD_SHA256 = (
    "7e22468672ff52cd70b669fb85a2dd16087477785f432b8b14ff74940877e799"
)
RULESET_COUNT_ERRATUM = Path("03_AUDIT_ERRATA_2026-08-24.md")
ARCHITECTURE_REGISTER = Path("registers/architecture_pointer_dispositions.json")
STABLE_RULESET_INGRESS_INSTRUCTION = (
    "Re-ingress every active rule from `go_with_the_flow_rules_v3_0_clean.csv`"
)
ARCHITECTURE_EXAMINATION_BUILDER = (
    PACK_ROOT / "scripts" / "build_architecture_examination_ledger.py"
)
ARCHITECTURE_EXAMINATION_JSON = (
    PACK_ROOT / "registers" / "architecture_examination_ledger.v1.json"
)
ARCHITECTURE_EXAMINATION_CSV = (
    PACK_ROOT / "registers" / "architecture_examination_ledger.v1.csv"
)
PROGRAMME_GATE_BUILDER = PACK_ROOT / "scripts" / "build_programme_gate_ledger.py"
PROGRAMME_GATE_JSON = PACK_ROOT / "registers" / "programme_gate_ledger.v1.json"
PROGRAMME_GATE_CSV = PACK_ROOT / "registers" / "programme_gate_ledger.v1.csv"


class ValidationError(RuntimeError):
    """Raised when a publication control fails."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(relative: str) -> dict[str, Any]:
    path = PACK_ROOT / relative
    _require(path.is_file(), f"missing JSON: {relative}")
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), f"JSON root must be an object: {relative}")
    return cast(dict[str, Any], value)


def _load_architecture_examination_builder() -> ModuleType:
    """Load the pure ledger builder without making the scripts dir a package."""
    spec = importlib.util.spec_from_file_location(
        "architecture_examination_builder", ARCHITECTURE_EXAMINATION_BUILDER
    )
    if spec is None or spec.loader is None:
        raise ValidationError("architecture examination builder cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_programme_gate_builder() -> ModuleType:
    """Load the pure programme-gate builder without packaging the scripts dir."""
    spec = importlib.util.spec_from_file_location(
        "programme_gate_builder", PROGRAMME_GATE_BUILDER
    )
    if spec is None or spec.loader is None:
        raise ValidationError("programme gate builder cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_architecture_examination_ledger() -> dict[str, int]:
    """Rebuild both descendants in memory and enforce the pre-execution boundary."""
    _require(
        ARCHITECTURE_EXAMINATION_BUILDER.is_file(),
        "architecture examination builder is missing",
    )
    _require(
        ARCHITECTURE_EXAMINATION_JSON.is_file(),
        "architecture examination JSON ledger is missing",
    )
    _require(
        ARCHITECTURE_EXAMINATION_CSV.is_file(),
        "architecture examination CSV ledger is missing",
    )
    builder = _load_architecture_examination_builder()
    payload = cast(dict[str, Any], builder.build_from_disk())
    _require(
        ARCHITECTURE_EXAMINATION_JSON.read_text(encoding="utf-8")
        == builder.render_json(payload),
        "architecture examination JSON descendant drift",
    )
    _require(
        ARCHITECTURE_EXAMINATION_CSV.read_text(encoding="utf-8")
        == builder.render_csv(payload),
        "architecture examination CSV descendant drift",
    )
    records = payload.get("records", [])
    _require(len(records) == 56, "architecture examination population drift")
    _require(
        Counter(str(record.get("source_disposition")) for record in records)
        == Counter({"not_examined": 51, "deferred": 5}),
        "architecture examination source-disposition drift",
    )
    _require(
        all(record.get("disposition") == "pending_examination" for record in records),
        "v1 architecture plan must remain pending examination",
    )
    _require(
        all(record.get("confidence") == "not_assessed" for record in records),
        "v1 architecture plan must remain not assessed",
    )
    _require(
        all(record.get("result", {}).get("sha256") is None for record in records),
        "v1 architecture plan cannot carry result hashes",
    )
    _require(
        all(
            record.get("independent_reviewer", {}).get("identity") is None
            for record in records
        ),
        "v1 architecture plan cannot claim completed independent review",
    )
    _require(
        all(
            record.get("hold_effect") == "blocks_board_lender_release"
            for record in records
        ),
        "architecture examination HOLD effect drift",
    )
    _require(
        payload.get("release_status") == "HOLD", "architecture ledger HOLD missing"
    )
    return {
        "records": len(records),
        "pending_examination": len(records),
        "hash_bound_results": 0,
    }


def _validate_programme_gate_ledger() -> dict[str, int]:
    """Rebuild the 23-gate descendants and enforce OPEN/HOLD pre-execution state."""
    _require(PROGRAMME_GATE_BUILDER.is_file(), "programme gate builder is missing")
    _require(PROGRAMME_GATE_JSON.is_file(), "programme gate JSON ledger is missing")
    _require(PROGRAMME_GATE_CSV.is_file(), "programme gate CSV ledger is missing")
    builder = _load_programme_gate_builder()
    payload = cast(dict[str, Any], builder.build_from_disk())
    _require(
        PROGRAMME_GATE_JSON.read_text(encoding="utf-8") == builder.render_json(payload),
        "programme gate JSON descendant drift",
    )
    _require(
        PROGRAMME_GATE_CSV.read_text(encoding="utf-8") == builder.render_csv(payload),
        "programme gate CSV descendant drift",
    )
    records = payload.get("records", [])
    _require(len(records) == 23, "programme gate population drift")
    _require(
        Counter(str(record.get("source_section")) for record in records)
        == Counter(
            {
                "reconciled_predecessor_queue": 9,
                "additional_live_remediation_gates": 6,
                "release_gates": 8,
            }
        ),
        "programme gate source-section drift",
    )
    _require(
        all(record.get("source_checkbox_state") == "unchecked" for record in records),
        "programme source must remain unchecked at the frozen cutoff",
    )
    _require(
        all(record.get("gate_status") == "pending" for record in records),
        "v1 programme gates must remain pending",
    )
    _require(
        all(
            record.get("completion_record", {}).get("sha256") is None
            for record in records
        ),
        "v1 programme gates cannot carry completion hashes",
    )
    _require(
        all(
            record.get("independent_reviewer", {}).get("identity") is None
            for record in records
        ),
        "v1 programme gates cannot claim completed independent review",
    )
    _require(
        all(record.get("closure_authorized") is False for record in records),
        "v1 programme gate ledger cannot authorize issue closure",
    )
    _require(
        all(
            record.get("hold_effect") == "blocks_board_lender_release"
            for record in records
        ),
        "programme gate HOLD effect drift",
    )
    _require(
        payload.get("source_issue", {}).get("state_at_cutoff") == "OPEN",
        "programme source issue cutoff state must remain OPEN",
    )
    _require(payload.get("release_status") == "HOLD", "programme ledger HOLD missing")
    _require(
        payload.get("f5_separation", {}).get("f5_01_gate") == "L01"
        and payload.get("f5_separation", {}).get("f5_02_evidence_gate") == "P06"
        and payload.get("f5_separation", {}).get("f5_02_decision_gate") == "L03",
        "programme ledger F5 separation drift",
    )
    _require(
        payload.get("closure_control", {}).get("release_decision_gate") == "R07"
        and payload.get("closure_control", {}).get("only_closure_action_gate") == "R08",
        "programme ledger closure-control drift",
    )
    return {
        "records": len(records),
        "pending": len(records),
        "completion_hashes": 0,
        "closure_authorized": 0,
    }


def _validate_manifest() -> int:
    _require(MANIFEST.is_file(), "PUBLICATION_MANIFEST.sha256 is missing")
    seen: set[str] = set()
    for line_number, line in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        parts = line.split("  ", 1)
        _require(len(parts) == 2, f"bad manifest line {line_number}")
        expected, relative = parts
        _require(len(expected) == 64, f"bad SHA-256 on manifest line {line_number}")
        _require(relative not in seen, f"duplicate manifest path: {relative}")
        _require(not relative.startswith("/"), f"absolute manifest path: {relative}")
        _require(
            ".." not in Path(relative).parts, f"escaping manifest path: {relative}"
        )
        _require(relative != MANIFEST.name, "manifest must not attest itself")
        target = PACK_ROOT / relative
        _require(target.is_file(), f"manifest target missing: {relative}")
        _require(_digest(target) == expected, f"manifest hash mismatch: {relative}")
        seen.add(relative)

    actual = {
        path.relative_to(PACK_ROOT).as_posix()
        for path in PACK_ROOT.rglob("*")
        if path.is_file() and path != MANIFEST and "__pycache__" not in path.parts
    }
    _require(
        seen == actual,
        f"manifest coverage mismatch: missing={sorted(actual - seen)}, extra={sorted(seen - actual)}",
    )
    return len(seen)


def _validate_ruleset_count_erratum() -> None:
    """Require an additive erratum while preserving the dated source records."""
    control_record = PACK_ROOT / IMMUTABLE_CONTROL_RECORD
    _require(control_record.is_file(), "immutable programming record is missing")
    _require(
        _digest(control_record) == IMMUTABLE_CONTROL_RECORD_SHA256,
        "immutable programming record digest drift",
    )

    erratum_path = PACK_ROOT / RULESET_COUNT_ERRATUM
    _require(erratum_path.is_file(), "GWTF rule-count erratum is missing")
    erratum = erratum_path.read_text(encoding="utf-8")
    _require(
        IMMUTABLE_CONTROL_RECORD.as_posix() in erratum,
        "GWTF erratum omits the immutable programming record",
    )
    _require(
        ARCHITECTURE_REGISTER.as_posix() in erratum,
        "GWTF erratum omits the architecture register",
    )
    _require(
        STABLE_RULESET_INGRESS_INSTRUCTION in erratum,
        "GWTF erratum omits the source-derived re-ingress instruction",
    )

    architecture = _load(ARCHITECTURE_REGISTER.as_posix())
    rs_f3 = [
        record
        for record in architecture.get("records", [])
        if record.get("pointer_id") == "RS-F3"
    ]
    _require(len(rs_f3) == 1, "architecture register must contain exactly one RS-F3")
    _require(
        rs_f3[0].get("area")
        == "**63 of 66 GWTF rules have unpinned enforcement text**",
        "RS-F3 historical pointer text drift",
    )
    _require(
        rs_f3[0].get("disposition") == "not_examined",
        "RS-F3 must remain not_examined until separately adjudicated",
    )


def main() -> None:
    """Validate manifest integrity and controlled register invariants."""
    manifest_entries = _validate_manifest()
    _validate_ruleset_count_erratum()
    architecture_examinations = _validate_architecture_examination_ledger()
    programme_gates = _validate_programme_gate_ledger()
    findings = _load("registers/findings_register.v2.json")
    sources = _load("registers/primary_source_register.v2.json")
    architecture = _load("registers/architecture_pointer_dispositions.json")
    reproductions = _load("reproductions/reproduction_register.json")
    validation = _load("qa/STRUCTURAL_VALIDATION_2026-08-16T145800+0530.json")

    _require(
        findings.get("repository_commit") == AUDITED_COMMIT, "findings commit drift"
    )
    _require(len(findings.get("findings", [])) == 111, "findings population drift")
    _require(len(sources.get("records", [])) == 42, "source population drift")
    _require(
        len(architecture.get("records", [])) == 72, "architecture population drift"
    )
    _require(
        len(reproductions.get("records", [])) == 34, "reproduction population drift"
    )

    reproduction_counts = Counter(
        str(record.get("status")) for record in reproductions.get("records", [])
    )
    _require(
        reproduction_counts
        == Counter({"completed": 18, "required_not_run": 11, "unavailable": 5}),
        f"reproduction status drift: {dict(reproduction_counts)}",
    )

    _require(
        validation.get("repository_commit") == AUDITED_COMMIT, "validation commit drift"
    )
    _require(validation.get("status") == "PASS", "structural validation is not PASS")
    _require(validation.get("release_status") == "HOLD", "release HOLD is missing")

    readme = (PACK_ROOT / "README.md").read_text(encoding="utf-8")
    corrigendum = (PACK_ROOT / "02_AUDIT_CORRIGENDUM_v1.0.1_2026-08-16.md").read_text(
        encoding="utf-8"
    )
    for text, label in ((readme, "README"), (corrigendum, "corrigendum")):
        _require("HOLD" in text, f"{label} omits HOLD")
        _require("F5-01" in text and "F5-02" in text, f"{label} omits F5 separation")

    result = {
        "status": "PASS",
        "release_status": "HOLD",
        "audited_commit": AUDITED_COMMIT,
        "manifest_entries": manifest_entries,
        "findings": 111,
        "primary_sources": 42,
        "ruleset_count_erratum": "PASS",
        "architecture_pointers": 72,
        "architecture_examinations": architecture_examinations,
        "programme_gates": programme_gates,
        "reproductions": dict(sorted(reproduction_counts.items())),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
