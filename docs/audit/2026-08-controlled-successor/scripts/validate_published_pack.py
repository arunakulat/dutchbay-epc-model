#!/usr/bin/env python3
"""Fail-closed validation for the repository-published audit successor pack."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
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
        "reproductions": dict(sorted(reproduction_counts.items())),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
