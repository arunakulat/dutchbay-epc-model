#!/usr/bin/env python3
"""Build and verify the additive P03 primary-source review plan.

The 42-row source register and 74-object source manifest are historical control
inputs.  This module validates them without rewriting either, emits a deterministic
independent-review plan, and can hash-verify a separately retained source root.  A
successful implementer run is explicitly not an independent semantic source review.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, NamedTuple, cast

PACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACK_ROOT.parents[2]
REGISTER_PATH = PACK_ROOT / "registers" / "primary_source_register.v2.json"
CSV_PATH = PACK_ROOT / "registers" / "primary_source_register.v2.csv"
SOURCE_MANIFEST_PATH = (
    PACK_ROOT / "source-controls" / "SOURCE_ARCHIVE_MANIFEST.v2.sha256"
)
FINDINGS_PATH = PACK_ROOT / "registers" / "findings_register.v2.json"
PLAN_PATH = PACK_ROOT / "registers" / "primary_source_review_plan.v1.json"
TESTED_SNAPSHOT_RELATIVES = (
    "conf/p03_primary_sources.yaml",
    (
        "docs/audit/2026-08-controlled-successor/registers/"
        "primary_source_review_plan.v1.json"
    ),
    (
        "docs/audit/2026-08-controlled-successor/scripts/"
        "build_primary_source_review_plan.py"
    ),
    ("docs/audit/2026-08-controlled-successor/scripts/validate_published_pack.py"),
    "scripts/verify_p03_primary_sources.py",
    "tests/lint/test_audit_evidence_pack.py",
    "tests/lint/test_audit_primary_source_control.py",
)

SCHEMA_VERSION = "dutchbay.primary_source_review_plan.v1"
DOCUMENT_ID = "DUTCHBAY-1110-P03-PRIMARY-SOURCE-REVIEW-PLAN-v1"
GATE_ID = "P03"
CREATED_AT = "2026-08-24T20:43:04+05:30"
CURRENT_MAIN_CUTOFF = "594fbac4da33e1836481b482c962a7f5a9539b2d"
CURRENT_MAIN_TREE_OID = "b3fdb1692271f11e984c2bf5f332393126049e62"
REGISTER_RELATIVE = "registers/primary_source_register.v2.json"
REGISTER_SHA256 = "4c8cc05648abd31f5123c80de09a65b60f60bb57cb12e8ed6fad309498a6df96"
REGISTER_SEMANTIC_SHA256 = (
    "a0ca6e545ef0f254aee6dbd4a2533f1f9e337fa5a8f6d939ad8eaaebc17cc7c4"
)
CSV_RELATIVE = "registers/primary_source_register.v2.csv"
CSV_SHA256 = "eb40b182debefb45a0492d5eb0052f035b972204f99336a5302ba2d5d3e2ab8d"
SOURCE_MANIFEST_RELATIVE = "source-controls/SOURCE_ARCHIVE_MANIFEST.v2.sha256"
SOURCE_MANIFEST_SHA256 = (
    "d1f376941576cd000c3162009dc30a4c21ce64bd2cee18da4801fb7cabf491bb"
)
HISTORICAL_SOURCE_MANIFEST_SHA256 = (
    "568c54095213821a683fd385fe5f7dabfb8d026ddfa9b4d750c386ed145aed93"
)
FINDINGS_RELATIVE = "registers/findings_register.v2.json"
FINDINGS_SHA256 = "71d16a15357a6073456b241d713ba775e2945990b22fa72045d5f312e183b4b8"
EXPECTED_RECORD_COUNT = 42
EXPECTED_MANIFEST_COUNT = 74
EXPECTED_MANIFEST_UNIQUE_DIGESTS = 70
EXPECTED_ARTIFACT_REFS = 92
EXPECTED_UNIQUE_ARTIFACT_PATHS = 64
EXPECTED_MANIFEST_REFERENCED_PATHS = 62
EXPECTED_MANIFEST_UNREFERENCED_PATHS = 12
HOLD_EFFECT = "blocks_board_lender_release"
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")

CSV_HEADERS = [
    "record_id",
    "claim_id",
    "finding_ids",
    "claim_text",
    "source_id",
    "source_class",
    "publisher",
    "title",
    "version_or_date",
    "page_or_section",
    "url",
    "accessed_at",
    "archive_filename",
    "archive_sha256",
    "converted_filename",
    "converted_sha256",
    "evidence_status",
    "evidence_role",
    "transaction_evidence_status",
    "paraphrased_support",
    "limitations",
    "evidence_artifacts",
    "supporting_record_ids",
    "artifact_exception",
    "retrieval_command",
    "repository_commit",
    "retrieval_completed_at",
]

CONTROLLED_VOCABULARIES = {
    "source_class": [
        "standard",
        "official_guidance",
        "official_project_document",
        "academic_primary",
        "official_software_documentation",
        "official_source_code",
        "official_catalogue_record",
        "transaction_document",
        "repository_evidence",
        "analyst_judgment",
    ],
    "evidence_status": [
        "supports",
        "partially_supports",
        "contradicts",
        "context_only",
        "unavailable",
    ],
    "evidence_role": [
        "standard_text",
        "standard_scope",
        "financing_precedent",
        "analyst_judgment_boundary",
        "claim_boundary",
        "audit_arithmetic",
        "scope_accounting",
        "transaction_evidence_status",
        "catalogue_status",
        "ratio_definition",
        "risk_treatment_guidance",
        "method_definition",
        "software_contract",
        "methodology_boundary",
        "energy_yield_convention",
        "numerical_solver_contract",
        "source_gap",
    ],
    "transaction_evidence_status": ["available", "unavailable", "not_applicable"],
    "artifact_role": [
        "publisher_original",
        "controlled_conversion",
        "official_metadata",
        "official_source_code",
        "official_release_record",
        "official_catalogue_query_log",
        "official_catalogue_response",
        "positive_control",
        "repository_snapshot",
        "controlled_reproduction",
    ],
}

EXPECTED_RECORD_BOUNDARIES = {
    "PSR-0001": ("WIND-MEAS-12M", "standard", "supports", "standard_text"),
    "PSR-0002": ("WIND-MEAS-DEVIATION", "standard", "supports", "standard_text"),
    "PSR-0003": ("WIND-MEAS-BASIS", "standard", "supports", "standard_text"),
    "PSR-0004": ("WIND-IEC-SCOPE", "standard", "supports", "standard_scope"),
    "PSR-0005": (
        "WIND-BANKABILITY-CP",
        "standard",
        "context_only",
        "analyst_judgment_boundary",
    ),
    "PSR-0006": (
        "DFI-COV-ADB-EXAMPLE",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0007": (
        "DFI-COV-WB-VIETNAM",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0008": (
        "DFI-COV-WB-PERU",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0009": (
        "DFI-COV-UNIVERSAL",
        "analyst_judgment",
        "contradicts",
        "claim_boundary",
    ),
    "PSR-0010": (
        "AUDIT-POINTER-COUNT",
        "repository_evidence",
        "supports",
        "audit_arithmetic",
    ),
    "PSR-0011": (
        "AUDIT-SCENARIO-COUNT",
        "repository_evidence",
        "supports",
        "scope_accounting",
    ),
    "PSR-0012": (
        "DFI-DSRA-TERM-SHEET",
        "repository_evidence",
        "supports",
        "transaction_evidence_status",
    ),
    "PSR-0013": (
        "DFI-CEB-LEGACY-PAYMENT-SECURITY",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0014": (
        "DFI-CEB-IDA-SBLC",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0015": (
        "WIND-IEC-15-2-PUBLICATION-STATUS",
        "official_catalogue_record",
        "contradicts",
        "catalogue_status",
    ),
    "PSR-0016": (
        "DFI-DSRA-IFC-GENERIC",
        "official_guidance",
        "supports",
        "financing_precedent",
    ),
    "PSR-0017": (
        "DFI-DSCR-IFC-GENERIC",
        "official_guidance",
        "supports",
        "financing_precedent",
    ),
    "PSR-0018": (
        "DFI-DSRA-ADB-BURGOS",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0019": (
        "FIN-DSCR-DEFINITION",
        "official_guidance",
        "supports",
        "ratio_definition",
    ),
    "PSR-0020": (
        "FIN-LLCR-DEFINITION",
        "official_guidance",
        "supports",
        "ratio_definition",
    ),
    "PSR-0021": (
        "FIN-PLCR-DEFINITION",
        "official_guidance",
        "supports",
        "ratio_definition",
    ),
    "PSR-0022": (
        "AUDIT-P2-POPULATION",
        "repository_evidence",
        "contradicts",
        "audit_arithmetic",
    ),
    "PSR-0023": (
        "MC-RISK-IFC-SENSITIVITY",
        "official_guidance",
        "supports",
        "risk_treatment_guidance",
    ),
    "PSR-0024": (
        "MC-RISK-WBG-PPP-UNIVERSE",
        "official_guidance",
        "supports",
        "risk_treatment_guidance",
    ),
    "PSR-0025": (
        "MC-RISK-WB-SRI-LANKA",
        "official_project_document",
        "supports",
        "financing_precedent",
    ),
    "PSR-0026": (
        "MC-IMAN-CONOVER-SOURCE-GAP",
        "official_catalogue_record",
        "context_only",
        "source_gap",
    ),
    "PSR-0027": (
        "MC-LHS-DEFINITION",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0028": (
        "MC-SCIPY-SOBOL-CONTRACT",
        "official_source_code",
        "supports",
        "software_contract",
    ),
    "PSR-0029": (
        "MC-GAUSSIAN-COPULA-TAIL",
        "academic_primary",
        "supports",
        "methodology_boundary",
    ),
    "PSR-0030": (
        "SA-SALIB-SOBOL-CONTRACT",
        "official_source_code",
        "supports",
        "software_contract",
    ),
    "PSR-0031": (
        "SA-SALTELLI-SOBOL-ESTIMATORS",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0032": (
        "SA-MORRIS-METHOD",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0033": (
        "SA-ENHANCED-MORRIS",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0034": (
        "SA-SALIB-MORRIS-CONTRACT",
        "official_source_code",
        "supports",
        "software_contract",
    ),
    "PSR-0035": (
        "SA-PAWN-2015-METADATA",
        "academic_primary",
        "context_only",
        "method_definition",
    ),
    "PSR-0036": (
        "SA-PAWN-GENERIC-SAMPLE",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0037": (
        "SA-SALIB-PAWN-CONTRACT",
        "official_source_code",
        "supports",
        "software_contract",
    ),
    "PSR-0038": (
        "RISK-CVAR-DISCRETE-DEFINITION",
        "academic_primary",
        "supports",
        "method_definition",
    ),
    "PSR-0039": (
        "RISK-LENDER-PXX-IFC",
        "official_guidance",
        "supports",
        "energy_yield_convention",
    ),
    "PSR-0040": (
        "WIND-LEE-FIELDS-PROPOSED-FRAMEWORK",
        "academic_primary",
        "supports",
        "methodology_boundary",
    ),
    "PSR-0041": (
        "WIND-MEASNET-PXX-CONVENTION",
        "standard",
        "supports",
        "energy_yield_convention",
    ),
    "PSR-0042": (
        "FIN-SCIPY-BISECT-CONTRACT",
        "official_source_code",
        "supports",
        "numerical_solver_contract",
    ),
}

BASE_RECORD_KEYS = {
    "record_id",
    "claim_id",
    "claim_text",
    "source_id",
    "source_class",
    "publisher",
    "title",
    "version_or_date",
    "page_or_section",
    "url",
    "accessed_at",
    "archive_filename",
    "archive_sha256",
    "converted_filename",
    "converted_sha256",
    "evidence_status",
    "evidence_role",
    "paraphrased_support",
    "limitations",
    "finding_ids",
    "evidence_artifacts",
}
OPTIONAL_RECORD_KEYS = {
    "transaction_evidence_status",
    "supporting_record_ids",
    "artifact_exception",
    "retrieval_command",
    "repository_commit",
    "retrieval_completed_at",
}
ARTIFACT_KEYS = {"path", "sha256", "role", "label"}
OPTIONAL_ARTIFACT_KEYS = {"request_ref"}
JSON_ENCODED_CSV_FIELDS = {
    "finding_ids",
    "evidence_artifacts",
    "supporting_record_ids",
    "artifact_exception",
}
EXPECTED_GOVERNED_EXCEPTIONS: dict[str, dict[str, Any]] = {
    "sources/IEC_CATALOGUE_QUERY_LOG.json": {
        "repository_path": "source-controls/IEC_CATALOGUE_QUERY_LOG.json",
        "sha256": "6a7b24b58e952f684267ed21b46470951b11a28cdcf281850175ded70ab602dc",
        "record_ids": ["PSR-0015"],
        "role": "official_catalogue_query_log",
        "external_source_root_copy_required": True,
    },
    "reproductions/p2_population_reconciliation.v2.json": {
        "repository_path": "reproductions/p2_population_reconciliation.v2.json",
        "sha256": "e357fca869e3b14f97d66bb0a011f220fa161c8c39341d38e76017931aed7455",
        "record_ids": ["PSR-0022"],
        "role": "controlled_reproduction",
        "external_source_root_copy_required": False,
    },
}
EXPECTED_UNREFERENCED_MANIFEST_PATHS = {
    "converted/p5/rockafellar_uryasev_2000_cvar.md",
    "original/p5/Rockafellar_Uryasev_2000_CVaR.pdf",
    "original/p5/mckay_beckman_conover_1979_primary_scan.pdf",
    "original/p5/morris_1991_primary_scan.pdf",
    "original/p5/pianosi_wagener_2018_primary_aam.pdf",
    "original/p5/salib_official_citations.html",
    "original/p5/salib_v1.5.2_CITATION.cff",
    "original/p5/salib_v1.5.2_release_metadata.json",
    "original/p5/salib_v1.5.2_sample_saltelli.py",
    "original/p5/saltelli_et_al_2010_crossref_metadata.json",
    "original/p5/scipy_v1.17.0_sobol_docs.html",
    "original/p5/scipy_v1.17.1_qmc_source.py",
}
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}


class PrimarySourceControlError(RuntimeError):
    """Raised when a P03 source, plan or retained payload fails closed."""

    def __init__(self, code: str, stage: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.stage = stage
        self.detail = detail


class ManifestEntry(NamedTuple):
    """One exact retained-source manifest row."""

    relative_path: str
    sha256: str


def _require(condition: bool, code: str, stage: str, detail: str) -> None:
    if not condition:
        raise PrimarySourceControlError(code, stage, detail)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, member in pairs:
        _require(
            key not in value,
            "DUPLICATE_JSON_KEY",
            "repository_inputs",
            f"duplicate JSON key: {key}",
        )
        value[key] = member
    return value


def _load_object(path: Path, expected_sha256: str, label: str) -> dict[str, Any]:
    _require(path.is_file(), "INPUT_MISSING", "repository_inputs", f"{label} missing")
    _require(
        not path.is_symlink(),
        "INPUT_SYMLINK",
        "repository_inputs",
        f"{label} cannot be a symlink",
    )
    payload = path.read_bytes()
    _require(
        _sha256_bytes(payload) == expected_sha256,
        "INPUT_HASH_MISMATCH",
        "repository_inputs",
        f"{label} hash mismatch",
    )
    try:
        value = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrimarySourceControlError(
            "INPUT_JSON_INVALID", "repository_inputs", f"{label} is invalid JSON"
        ) from exc
    _require(
        isinstance(value, dict),
        "INPUT_ROOT_INVALID",
        "repository_inputs",
        f"{label} root must be an object",
    )
    return cast(dict[str, Any], value)


def _safe_relative_path(raw: str, *, stage: str) -> str:
    _require(
        isinstance(raw, str) and bool(raw),
        "PATH_INVALID",
        stage,
        "manifest path is empty",
    )
    _require(
        "\\" not in raw and "//" not in raw,
        "PATH_INVALID",
        stage,
        f"unsafe path syntax: {raw}",
    )
    path = PurePosixPath(raw)
    _require(
        not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts),
        "PATH_INVALID",
        stage,
        f"unsafe relative path: {raw}",
    )
    normalized = path.as_posix()
    _require(
        unicodedata.normalize("NFC", normalized) == normalized,
        "PATH_NORMALIZATION",
        stage,
        f"path is not NFC normalized: {raw}",
    )
    return normalized


def parse_source_manifest(payload: bytes) -> list[ManifestEntry]:
    """Parse the exact two-space SHA-256 manifest without path normalization."""

    _require(
        bool(payload) and not payload.startswith(b"\xef\xbb\xbf"),
        "MANIFEST_FORMAT",
        "source_manifest",
        "source manifest is empty or BOM-prefixed",
    )
    _require(
        b"\r" not in payload and payload.endswith(b"\n"),
        "MANIFEST_FORMAT",
        "source_manifest",
        "source manifest must use final LF and no CR bytes",
    )
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    seen_folded: set[str] = set()
    for line_number, raw_line in enumerate(payload.splitlines(), 1):
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PrimarySourceControlError(
                "MANIFEST_ENCODING",
                "source_manifest",
                f"manifest line {line_number} is not UTF-8",
            ) from exc
        _require(
            re.fullmatch(r"[0-9a-f]{64}  \S+", line) is not None,
            "MANIFEST_FORMAT",
            "source_manifest",
            f"manifest line {line_number} has invalid syntax",
        )
        digest, raw_path = line.split("  ", 1)
        relative = _safe_relative_path(raw_path, stage="source_manifest")
        _require(
            relative.startswith(("original/", "converted/")),
            "MANIFEST_SCOPE",
            "source_manifest",
            f"manifest path outside original/converted: {relative}",
        )
        _require(
            relative not in seen,
            "MANIFEST_DUPLICATE",
            "source_manifest",
            f"duplicate manifest path: {relative}",
        )
        folded = unicodedata.normalize("NFC", relative).casefold()
        _require(
            folded not in seen_folded,
            "MANIFEST_COLLISION",
            "source_manifest",
            f"case/Unicode-colliding manifest path: {relative}",
        )
        seen.add(relative)
        seen_folded.add(folded)
        entries.append(ManifestEntry(relative, digest))
    _require(
        len(entries) == EXPECTED_MANIFEST_COUNT,
        "MANIFEST_COUNT",
        "source_manifest",
        f"source manifest count is {len(entries)}, expected {EXPECTED_MANIFEST_COUNT}",
    )
    _require(
        len({entry.sha256 for entry in entries}) == EXPECTED_MANIFEST_UNIQUE_DIGESTS,
        "MANIFEST_DIGEST_POPULATION",
        "source_manifest",
        "source manifest unique-digest population drift",
    )
    return entries


def _load_manifest() -> list[ManifestEntry]:
    _require(
        SOURCE_MANIFEST_PATH.is_file() and not SOURCE_MANIFEST_PATH.is_symlink(),
        "MANIFEST_MISSING",
        "repository_inputs",
        "repository source manifest missing or symlinked",
    )
    payload = SOURCE_MANIFEST_PATH.read_bytes()
    _require(
        _sha256_bytes(payload) == SOURCE_MANIFEST_SHA256,
        "MANIFEST_HASH_MISMATCH",
        "repository_inputs",
        "repository source manifest hash mismatch",
    )
    return parse_source_manifest(payload)


def _load_findings() -> dict[str, dict[str, Any]]:
    findings = _load_object(FINDINGS_PATH, FINDINGS_SHA256, "findings register")
    records = findings.get("findings")
    _require(
        isinstance(records, list) and len(records) == 111,
        "FINDINGS_POPULATION",
        "repository_inputs",
        "findings register population drift",
    )
    by_id: dict[str, dict[str, Any]] = {}
    for raw in cast(list[Any], records):
        _require(
            isinstance(raw, dict),
            "FINDING_INVALID",
            "repository_inputs",
            "finding row is not an object",
        )
        record = cast(dict[str, Any], raw)
        raw_finding_id = record.get("finding_id")
        severity = record.get("severity")
        _require(
            isinstance(raw_finding_id, str)
            and raw_finding_id not in by_id
            and severity in SEVERITY_RANK,
            "FINDING_INVALID",
            "repository_inputs",
            "finding identity or severity drift",
        )
        finding_id = cast(str, raw_finding_id)
        by_id[finding_id] = record
    return by_id


def _validate_csv_parity(records: list[dict[str, Any]]) -> None:
    _require(
        CSV_PATH.is_file() and not CSV_PATH.is_symlink(),
        "CSV_MISSING",
        "csv_parity",
        "primary-source CSV is missing or symlinked",
    )
    payload = CSV_PATH.read_bytes()
    _require(
        _sha256_bytes(payload) == CSV_SHA256,
        "CSV_HASH_MISMATCH",
        "csv_parity",
        "primary-source CSV hash mismatch",
    )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PrimarySourceControlError(
            "CSV_ENCODING", "csv_parity", "primary-source CSV is not UTF-8"
        ) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fieldnames = reader.fieldnames or []
    rows = list(reader)
    _require(
        list(fieldnames) == CSV_HEADERS and len(set(fieldnames)) == len(CSV_HEADERS),
        "CSV_HEADERS",
        "csv_parity",
        "primary-source CSV headers drift",
    )
    _require(
        len(rows) == len(records) == EXPECTED_RECORD_COUNT,
        "CSV_POPULATION",
        "csv_parity",
        "primary-source CSV population drift",
    )
    for record, row in zip(records, rows, strict=True):
        for header in CSV_HEADERS:
            expected = record.get(header, "")
            if header in JSON_ENCODED_CSV_FIELDS and expected != "":
                expected = json.dumps(
                    expected, ensure_ascii=False, separators=(",", ":")
                )
            _require(
                row[header] == expected,
                "CSV_PARITY",
                "csv_parity",
                f"CSV/JSON drift for {record['record_id']} field {header}",
            )


def _validate_record_boundaries(records: list[dict[str, Any]]) -> None:
    actual: dict[str, tuple[str, str, str, str]] = {}
    for record in records:
        record_id = str(record.get("record_id", ""))
        actual[record_id] = (
            str(record.get("claim_id", "")),
            str(record.get("source_class", "")),
            str(record.get("evidence_status", "")),
            str(record.get("evidence_role", "")),
        )
    _require(
        actual == EXPECTED_RECORD_BOUNDARIES,
        "EVIDENCE_BOUNDARY_ESCALATION",
        "register_semantics",
        "record claim/source/evidence boundary drift",
    )


def _validate_register_header(register: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "as_of",
        "status",
        "record_count",
        "source_predecessors",
        "controlled_vocabularies",
        "manifest",
        "csv_companion",
        "records",
        "limitations",
    }
    _require(
        set(register) == expected_keys,
        "REGISTER_KEYS",
        "register_semantics",
        "primary-source register top-level keys drift",
    )
    _require(
        register["schema_version"] == "dutchbay.primary_source_register.v2.0.0"
        and register["status"] == "controlled_draft"
        and register["record_count"] == EXPECTED_RECORD_COUNT,
        "REGISTER_HEADER",
        "register_semantics",
        "primary-source register header drift",
    )
    _require(
        register["controlled_vocabularies"] == CONTROLLED_VOCABULARIES,
        "REGISTER_VOCABULARY",
        "register_semantics",
        "primary-source controlled vocabulary drift",
    )
    manifest = register["manifest"]
    _require(
        isinstance(manifest, dict)
        and Path(str(manifest.get("path"))).name == "SOURCE_ARCHIVE_MANIFEST.v2.sha256"
        and manifest.get("sha256") == SOURCE_MANIFEST_SHA256
        and manifest.get("file_count") == EXPECTED_MANIFEST_COUNT
        and manifest.get("scope")
        == "complete recursive file set under sources/original and sources/converted",
        "REGISTER_MANIFEST_DECLARATION",
        "register_semantics",
        "primary-source manifest declaration drift",
    )
    companion = register["csv_companion"]
    _require(
        isinstance(companion, dict)
        and Path(str(companion.get("path"))).name == CSV_PATH.name
        and companion.get("sha256") == CSV_SHA256
        and companion.get("headers") == CSV_HEADERS
        and companion.get("array_and_object_encoding") == "compact JSON",
        "REGISTER_CSV_DECLARATION",
        "register_semantics",
        "primary-source CSV declaration drift",
    )
    predecessors = register["source_predecessors"]
    expected_predecessors = [
        (
            "primary_source_register.json",
            "6302ce76aa7e8bcd1274a8031a951a273d6c13c2166dd869b4b8ad2f096b78f9",
            "unchanged predecessor",
        ),
        (
            "primary_source_register.csv",
            "3b3003a5dd263227594a380231d40d0ad87d1a5b9ba19fc34dd97e7726040f31",
            "unchanged predecessor",
        ),
        (
            "SOURCE_ARCHIVE_MANIFEST.sha256",
            HISTORICAL_SOURCE_MANIFEST_SHA256,
            "unchanged historical manifest",
        ),
    ]
    actual_predecessors = [
        (
            Path(str(item.get("path"))).name,
            item.get("sha256"),
            item.get("preservation"),
        )
        for item in predecessors
        if isinstance(item, dict)
    ]
    _require(
        actual_predecessors == expected_predecessors,
        "REGISTER_PREDECESSORS",
        "register_semantics",
        "primary-source predecessor identities drift",
    )
    limitations = register["limitations"]
    _require(
        isinstance(limitations, list)
        and len(limitations) == 5
        and all(isinstance(item, str) and len(item) >= 80 for item in limitations),
        "REGISTER_LIMITATIONS",
        "register_semantics",
        "primary-source limitations are incomplete",
    )


def _validate_string(
    record: dict[str, Any], field: str, *, allow_empty: bool = False
) -> str:
    value = record.get(field)
    _require(
        isinstance(value, str) and (allow_empty or bool(value.strip())),
        "RECORD_FIELD",
        "register_semantics",
        f"{record.get('record_id', '<unknown>')}: invalid {field}",
    )
    return cast(str, value)


def _route_artifact(
    record_id: str,
    artifact: dict[str, Any],
    manifest_by_path: dict[str, ManifestEntry],
) -> tuple[str, str]:
    raw_path = _validate_string(artifact, "path")
    path = _safe_relative_path(raw_path, stage="register_semantics")
    digest = _validate_string(artifact, "sha256")
    _require(
        HEX_64.fullmatch(digest) is not None,
        "ARTIFACT_HASH",
        "register_semantics",
        f"{record_id}: artifact digest invalid",
    )
    if path.startswith(("sources/original/", "sources/converted/")):
        manifest_path = path.removeprefix("sources/")
        expected = manifest_by_path.get(manifest_path)
        _require(
            expected is not None and expected.sha256 == digest,
            "ARTIFACT_MANIFEST_LINK",
            "register_semantics",
            f"{record_id}: artifact missing or mismatched in source manifest",
        )
        return "source_manifest", manifest_path
    exception = EXPECTED_GOVERNED_EXCEPTIONS.get(path)
    _require(
        exception is not None
        and record_id in exception["record_ids"]
        and digest == exception["sha256"]
        and artifact.get("role") == exception["role"],
        "ARTIFACT_ROUTE",
        "register_semantics",
        f"{record_id}: ungoverned artifact route",
    )
    return "repository_exception", path


def _validate_records(
    register: dict[str, Any],
    findings: dict[str, dict[str, Any]],
    manifest: list[ManifestEntry],
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    raw_records = register["records"]
    _require(
        isinstance(raw_records, list) and len(raw_records) == EXPECTED_RECORD_COUNT,
        "REGISTER_POPULATION",
        "register_semantics",
        "primary-source record population drift",
    )
    records: list[dict[str, Any]] = []
    manifest_by_path = {entry.relative_path: entry for entry in manifest}
    manifested_refs: dict[str, list[str]] = defaultdict(list)
    exception_refs: dict[str, list[str]] = defaultdict(list)
    for index, raw in enumerate(raw_records, 1):
        _require(
            isinstance(raw, dict),
            "RECORD_TYPE",
            "register_semantics",
            f"primary-source row {index} is not an object",
        )
        record = cast(dict[str, Any], raw)
        expected_id = f"PSR-{index:04d}"
        _require(
            record.get("record_id") == expected_id,
            "RECORD_ORDER",
            "register_semantics",
            f"primary-source row {index} identity drift",
        )
        _require(
            BASE_RECORD_KEYS <= set(record)
            and set(record) <= BASE_RECORD_KEYS | OPTIONAL_RECORD_KEYS,
            "RECORD_KEYS",
            "register_semantics",
            f"{expected_id}: record keys drift",
        )
        for field in (
            "claim_id",
            "claim_text",
            "source_id",
            "source_class",
            "publisher",
            "title",
            "version_or_date",
            "page_or_section",
            "accessed_at",
            "evidence_status",
            "evidence_role",
            "paraphrased_support",
            "limitations",
        ):
            _validate_string(record, field)
        url = _validate_string(record, "url", allow_empty=True)
        _require(
            not url or url.startswith("https://"),
            "RECORD_URL",
            "register_semantics",
            f"{expected_id}: source URL must be empty or HTTPS",
        )
        accessed = _validate_string(record, "accessed_at")
        try:
            accessed_at = datetime.fromisoformat(accessed)
        except ValueError as exc:
            raise PrimarySourceControlError(
                "RECORD_DATE",
                "register_semantics",
                f"{expected_id}: accessed_at is not ISO-8601",
            ) from exc
        _require(
            accessed_at.utcoffset() is not None,
            "RECORD_DATE",
            "register_semantics",
            f"{expected_id}: accessed_at lacks UTC offset",
        )
        finding_ids = record["finding_ids"]
        _require(
            isinstance(finding_ids, list)
            and bool(finding_ids)
            and len(finding_ids) == len(set(finding_ids))
            and all(isinstance(item, str) and item in findings for item in finding_ids),
            "FINDING_LINK",
            "register_semantics",
            f"{expected_id}: finding links invalid",
        )
        artifacts = record["evidence_artifacts"]
        _require(
            isinstance(artifacts, list),
            "ARTIFACT_LIST",
            "register_semantics",
            f"{expected_id}: evidence_artifacts must be a list",
        )
        if expected_id == "PSR-0009":
            _require(
                artifacts == []
                and record.get("supporting_record_ids")
                == [
                    "PSR-0006",
                    "PSR-0007",
                    "PSR-0008",
                    "PSR-0016",
                    "PSR-0017",
                    "PSR-0018",
                ]
                and record.get("artifact_exception")
                == {
                    "type": "analyst_judgment_synthesis",
                    "reason": (
                        "This row is an explicit claim-boundary inference over the six "
                        "hashed official records in supporting_record_ids; it has no "
                        "separate publisher original and must not be presented as primary "
                        "source text."
                    ),
                },
                "ANALYST_EXCEPTION",
                "register_semantics",
                "PSR-0009 analyst-judgment boundary drift",
            )
        else:
            _require(
                bool(artifacts)
                and "supporting_record_ids" not in record
                and "artifact_exception" not in record,
                "ARTIFACT_REQUIRED",
                "register_semantics",
                f"{expected_id}: evidence artifacts missing or exception smuggled",
            )
        for raw_artifact in artifacts:
            _require(
                isinstance(raw_artifact, dict),
                "ARTIFACT_TYPE",
                "register_semantics",
                f"{expected_id}: artifact is not an object",
            )
            artifact = cast(dict[str, Any], raw_artifact)
            _require(
                ARTIFACT_KEYS <= set(artifact)
                and set(artifact) <= ARTIFACT_KEYS | OPTIONAL_ARTIFACT_KEYS,
                "ARTIFACT_KEYS",
                "register_semantics",
                f"{expected_id}: artifact keys drift",
            )
            role = _validate_string(artifact, "role")
            _require(
                role in CONTROLLED_VOCABULARIES["artifact_role"],
                "ARTIFACT_ROLE",
                "register_semantics",
                f"{expected_id}: artifact role invalid",
            )
            _validate_string(artifact, "label")
            if "request_ref" in artifact:
                request_ref = _validate_string(artifact, "request_ref")
                _require(
                    expected_id == "PSR-0015"
                    and request_ref.startswith(
                        "sources/IEC_CATALOGUE_QUERY_LOG.json#requests["
                    )
                    and request_ref.endswith("]"),
                    "ARTIFACT_REQUEST_REF",
                    "register_semantics",
                    f"{expected_id}: request reference invalid",
                )
            route, routed_path = _route_artifact(
                expected_id, artifact, manifest_by_path
            )
            target = manifested_refs if route == "source_manifest" else exception_refs
            target[routed_path].append(expected_id)
        archive_name = _validate_string(record, "archive_filename", allow_empty=True)
        archive_sha = _validate_string(record, "archive_sha256", allow_empty=True)
        _require(
            bool(archive_name) == bool(archive_sha)
            and (not archive_sha or HEX_64.fullmatch(archive_sha) is not None),
            "ARCHIVE_FIELDS",
            "register_semantics",
            f"{expected_id}: archive name/hash pairing invalid",
        )
        converted_name = _validate_string(
            record, "converted_filename", allow_empty=True
        )
        converted_sha = _validate_string(record, "converted_sha256", allow_empty=True)
        _require(
            bool(converted_name) == bool(converted_sha)
            and (not converted_sha or HEX_64.fullmatch(converted_sha) is not None),
            "CONVERSION_FIELDS",
            "register_semantics",
            f"{expected_id}: conversion name/hash pairing invalid",
        )
        artifact_pairs = {
            (str(item["path"]), str(item["sha256"]))
            for item in artifacts
            if isinstance(item, dict)
        }
        if archive_name:
            _require(
                (f"sources/original/{archive_name}", archive_sha) in artifact_pairs,
                "ARCHIVE_ARTIFACT_LINK",
                "register_semantics",
                f"{expected_id}: archive fields do not resolve to an artifact",
            )
        if converted_name:
            _require(
                (f"sources/converted/{converted_name}", converted_sha)
                in artifact_pairs,
                "CONVERSION_ARTIFACT_LINK",
                "register_semantics",
                f"{expected_id}: conversion fields do not resolve to an artifact",
            )
        if expected_id == "PSR-0005":
            _require(
                record.get("transaction_evidence_status") == "unavailable",
                "TRANSACTION_EVIDENCE_BOUNDARY",
                "register_semantics",
                "PSR-0005 transaction-evidence boundary drift",
            )
        else:
            _require(
                "transaction_evidence_status" not in record,
                "TRANSACTION_EVIDENCE_BOUNDARY",
                "register_semantics",
                f"{expected_id}: transaction-evidence status smuggled",
            )
        if expected_id == "PSR-0011":
            _require(
                record.get("repository_commit")
                == "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8"
                and record.get("retrieval_command")
                == (
                    "git ls-tree -r --name-only "
                    "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8 -- scenarios"
                )
                and record.get("retrieval_completed_at") == "2026-08-12T09:28:49+05:30",
                "REPOSITORY_RETRIEVAL",
                "register_semantics",
                "PSR-0011 repository retrieval boundary drift",
            )
        else:
            _require(
                not (
                    {"repository_commit", "retrieval_command", "retrieval_completed_at"}
                    & set(record)
                ),
                "REPOSITORY_RETRIEVAL",
                "register_semantics",
                f"{expected_id}: repository retrieval fields smuggled",
            )
        records.append(record)
    _validate_record_boundaries(records)
    _require(
        len({record["claim_id"] for record in records}) == EXPECTED_RECORD_COUNT,
        "CLAIM_ID_POPULATION",
        "register_semantics",
        "claim IDs are not unique",
    )
    artifact_ref_count = sum(len(record["evidence_artifacts"]) for record in records)
    unique_paths = set(manifested_refs) | set(exception_refs)
    _require(
        artifact_ref_count == EXPECTED_ARTIFACT_REFS
        and len(unique_paths) == EXPECTED_UNIQUE_ARTIFACT_PATHS
        and len(manifested_refs) == EXPECTED_MANIFEST_REFERENCED_PATHS
        and set(manifest_by_path) - set(manifested_refs)
        == EXPECTED_UNREFERENCED_MANIFEST_PATHS
        and set(exception_refs) == set(EXPECTED_GOVERNED_EXCEPTIONS),
        "ARTIFACT_POPULATION",
        "register_semantics",
        "artifact reference or retained-object population drift",
    )
    for path, expected in EXPECTED_GOVERNED_EXCEPTIONS.items():
        _require(
            sorted(exception_refs[path]) == expected["record_ids"],
            "EXCEPTION_LINK",
            "register_semantics",
            f"governed exception link drift: {path}",
        )
    return records, dict(manifested_refs), dict(exception_refs)


def _source_location_status(record: dict[str, Any]) -> str:
    if record["url"]:
        return "url_and_locator_present"
    if record["record_id"] == "PSR-0009":
        return "analyst_judgment_boundary_no_publisher_source"
    return "repository_evidence_no_external_url"


def _review_priority(record: dict[str, Any], severities: Iterable[str]) -> str:
    highest = max((SEVERITY_RANK[item] for item in severities), default=-1)
    if (
        highest >= SEVERITY_RANK["high"]
        or record["evidence_status"] != "supports"
        or record["source_class"] in {"analyst_judgment", "repository_evidence"}
        or record.get("transaction_evidence_status") == "unavailable"
    ):
        return "full_semantic_priority"
    return "full_semantic_standard"


def build_review_plan() -> dict[str, Any]:
    """Return the deterministic population-exact P03 independent-review plan."""

    register = _load_object(REGISTER_PATH, REGISTER_SHA256, "primary-source register")
    _require(
        _canonical_sha256(register) == REGISTER_SEMANTIC_SHA256,
        "REGISTER_SEMANTIC_HASH",
        "register_semantics",
        "primary-source register semantic hash drift",
    )
    _validate_register_header(register)
    manifest = _load_manifest()
    findings = _load_findings()
    records, manifested_refs, _exception_refs = _validate_records(
        register, findings, manifest
    )
    _validate_csv_parity(records)

    review_rows: list[dict[str, Any]] = []
    for index, record in enumerate(records, 1):
        finding_links = [
            {
                "finding_id": finding_id,
                "severity": findings[finding_id]["severity"],
                "status": findings[finding_id]["status"],
            }
            for finding_id in record["finding_ids"]
        ]
        severities = [str(item["severity"]) for item in finding_links]
        highest_severity = max(severities, key=lambda item: SEVERITY_RANK[item])
        artifact_paths = [str(item["path"]) for item in record["evidence_artifacts"]]
        review_rows.append(
            {
                "review_row_number": index,
                "record_id": record["record_id"],
                "claim_id": record["claim_id"],
                "source_id": record["source_id"],
                "source_class": record["source_class"],
                "evidence_status": record["evidence_status"],
                "evidence_role": record["evidence_role"],
                "transaction_evidence_status": record.get(
                    "transaction_evidence_status", "not_applicable"
                ),
                "source_register_record_sha256": _canonical_sha256(record),
                "claim_text_sha256": _sha256_bytes(
                    record["claim_text"].encode("utf-8")
                ),
                "paraphrased_support_sha256": _sha256_bytes(
                    record["paraphrased_support"].encode("utf-8")
                ),
                "finding_links": finding_links,
                "highest_linked_severity": highest_severity,
                "source_location_status": _source_location_status(record),
                "artifact_ref_count": len(artifact_paths),
                "manifested_source_artifact_count": sum(
                    path.startswith(("sources/original/", "sources/converted/"))
                    for path in artifact_paths
                ),
                "governed_repository_artifact_count": sum(
                    path in EXPECTED_GOVERNED_EXCEPTIONS for path in artifact_paths
                ),
                "review_priority": _review_priority(record, severities),
                "review_requirements": {
                    "artifact_hash_review_required": True,
                    "source_location_review_required": True,
                    "semantic_support_review_required": True,
                    "limitation_review_required": True,
                    "publication_rights_review_required": True,
                },
                "publication_rights_status": (
                    "not_assessed_no_republication_authorized"
                ),
                "review_result": {
                    "status": "pending_independent_review",
                    "reviewer_identity": None,
                    "reviewed_at": None,
                    "semantic_support_decision": None,
                    "publication_rights_decision": None,
                    "result_artifact_sha256": None,
                },
                "hold_effect": HOLD_EFFECT,
            }
        )

    manifest_rows: list[dict[str, Any]] = []
    for index, entry in enumerate(manifest, 1):
        referenced_by = sorted(set(manifested_refs.get(entry.relative_path, [])))
        manifest_rows.append(
            {
                "object_number": index,
                "relative_path": entry.relative_path,
                "sha256": entry.sha256,
                "referenced_by_record_ids": referenced_by,
                "reference_count": len(manifested_refs.get(entry.relative_path, [])),
                "reference_status": (
                    "claim_referenced" if referenced_by else "retained_unreferenced"
                ),
                "full_hash_verification_required": True,
                "verification_status": "pending_independent_verification",
            }
        )

    exception_rows = []
    for source_path in sorted(EXPECTED_GOVERNED_EXCEPTIONS):
        expected = EXPECTED_GOVERNED_EXCEPTIONS[source_path]
        exception_rows.append(
            {
                "source_register_path": source_path,
                "repository_path": expected["repository_path"],
                "sha256": expected["sha256"],
                "record_ids": expected["record_ids"],
                "role": expected["role"],
                "external_source_root_copy_required": expected[
                    "external_source_root_copy_required"
                ],
                "verification_status": "pending_independent_verification",
            }
        )

    source_class_counts = Counter(str(record["source_class"]) for record in records)
    evidence_status_counts = Counter(
        str(record["evidence_status"]) for record in records
    )
    review_priority_counts = Counter(row["review_priority"] for row in review_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": DOCUMENT_ID,
        "authority_status": "active_pre_review_candidate_plan",
        "created_at": CREATED_AT,
        "gate_id": GATE_ID,
        "release_status": "HOLD",
        "completion_authorized": False,
        "independent_review": {
            "status": "pending_independent_review",
            "reviewer_identity": None,
            "decision": None,
            "decision_artifact_sha256": None,
            "review_policy": (
                "Verify all 42 claim rows and all 74 retained source objects; this is a "
                "population-exact review, not statistical sampling."
            ),
        },
        "source_inputs": {
            "primary_source_register": {
                "path": REGISTER_RELATIVE,
                "sha256": REGISTER_SHA256,
                "semantic_sha256": REGISTER_SEMANTIC_SHA256,
                "records": EXPECTED_RECORD_COUNT,
            },
            "csv_companion": {
                "path": CSV_RELATIVE,
                "sha256": CSV_SHA256,
                "records": EXPECTED_RECORD_COUNT,
                "parity_required": True,
            },
            "source_archive_manifest": {
                "path": SOURCE_MANIFEST_RELATIVE,
                "sha256": SOURCE_MANIFEST_SHA256,
                "objects": EXPECTED_MANIFEST_COUNT,
                "unique_digests": EXPECTED_MANIFEST_UNIQUE_DIGESTS,
                "scope": "sources/original and sources/converted only",
            },
            "findings_register": {
                "path": FINDINGS_RELATIVE,
                "sha256": FINDINGS_SHA256,
                "records": 111,
            },
            "current_main_cutoff": {
                "commit": CURRENT_MAIN_CUTOFF,
                "tree_oid": CURRENT_MAIN_TREE_OID,
            },
        },
        "coverage": {
            "claim_records": len(review_rows),
            "claim_records_requiring_independent_semantic_review": len(review_rows),
            "claim_records_independently_reviewed": 0,
            "manifest_objects": len(manifest_rows),
            "manifest_objects_requiring_full_hash_verification": len(manifest_rows),
            "manifest_objects_independently_verified": 0,
            "artifact_references": EXPECTED_ARTIFACT_REFS,
            "unique_artifact_paths": EXPECTED_UNIQUE_ARTIFACT_PATHS,
            "claim_referenced_manifest_objects": EXPECTED_MANIFEST_REFERENCED_PATHS,
            "retained_unreferenced_manifest_objects": (
                EXPECTED_MANIFEST_UNREFERENCED_PATHS
            ),
            "governed_artifacts_outside_source_manifest": len(exception_rows),
            "publication_rights_reviews_required": len(review_rows),
            "publication_rights_reviews_completed": 0,
            "source_class_counts": dict(sorted(source_class_counts.items())),
            "evidence_status_counts": dict(sorted(evidence_status_counts.items())),
            "review_priority_counts": dict(sorted(review_priority_counts.items())),
            "hold_blocking_claim_records": len(review_rows),
        },
        "governed_artifacts_outside_source_manifest": exception_rows,
        "manifest_objects": manifest_rows,
        "review_rows": review_rows,
        "negative_controls": [
            {
                "control_id": "P03-NC-01",
                "purpose": "reject unsupported promotion to verified primary evidence",
                "expected_result": "EVIDENCE_BOUNDARY_ESCALATION",
            },
            {
                "control_id": "P03-NC-02",
                "purpose": "reject missing, extra, escaping, colliding or hash-mismatched retained objects",
                "expected_result": "retained-source verification fails before PASS",
            },
            {
                "control_id": "P03-NC-03",
                "purpose": "reject CSV/JSON population or field drift",
                "expected_result": "CSV_PARITY",
            },
            {
                "control_id": "P03-NC-04",
                "purpose": "reject analyst judgment presented as publisher source text",
                "expected_result": "ANALYST_EXCEPTION",
            },
        ],
        "boundaries": {
            "source_register_modified": False,
            "source_manifest_modified": False,
            "evidence_status_upgrades_authorized": False,
            "publication_or_redistribution_rights_claimed": False,
            "synthetic_or_analyst_material_promoted_to_primary": False,
            "structural_or_hash_pass_is_semantic_acceptance": False,
            "f5_01_f5_02_netting_permitted": False,
        },
        "required_circulation_wording": (
            "P03 remains pending independent review. The register contains 42 claim "
            "records and the retained source manifest contains 74 objects; implementer "
            "hash verification does not establish semantic support, publication rights, "
            "transaction evidence, bankability or release approval."
        ),
        "limitations": [
            "The source register contains historical absolute predecessor paths; this additive plan binds only portable repository-relative successors and does not rewrite the register.",
            "No publication or redistribution right is inferred from public availability, an official URL, local retention or successful hash verification.",
            "PSR-0009 is analyst judgment over six supporting official records and has no separate publisher artifact; it cannot be presented as primary-source text.",
            "The IEC catalogue result establishes only public-catalogue status at the cutoff and does not prove that no unpublished committee draft exists.",
            "The P2 population reproduction and IEC query log are governed outside the 74-object original/converted source-manifest scope and remain separately hash-bound.",
            "A same-implementer preflight cannot satisfy the independent source-verification reviewer or final P03 decision requirements.",
            "Issue #1110 remains OPEN, all programme gates remain pending and Board/lender circulation remains HOLD.",
        ],
    }


def render_json(payload: dict[str, Any]) -> str:
    """Render a controlled JSON payload deterministically."""

    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def validate_committed_plan() -> dict[str, int | str | bool]:
    """Rebuild the committed plan and enforce its additive HOLD-side boundary."""

    _require(
        PLAN_PATH.is_file() and not PLAN_PATH.is_symlink(),
        "PLAN_MISSING",
        "review_plan",
        "committed P03 review plan missing or symlinked",
    )
    expected = render_json(build_review_plan())
    actual = PLAN_PATH.read_text(encoding="utf-8")
    _require(
        actual == expected,
        "PLAN_DRIFT",
        "review_plan",
        "committed P03 review plan does not rebuild exactly",
    )
    _require(
        "/Users/" not in actual,
        "PLAN_LOCAL_PATH",
        "review_plan",
        "committed P03 review plan contains a machine-local path",
    )
    return {
        "status": "PASS",
        "release_status": "HOLD",
        "gate_status": "pending_independent_review",
        "claim_records": EXPECTED_RECORD_COUNT,
        "manifest_objects": EXPECTED_MANIFEST_COUNT,
        "independently_reviewed": 0,
        "completion_authorized": False,
    }


def _reject_symlink_components(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        _require(
            not current.is_symlink(),
            "PATH_SYMLINK",
            "retained_sources",
            f"{label} contains a symlink component",
        )


def _safe_external_root(source_root: Path) -> Path:
    _require(
        source_root.is_absolute(),
        "ENVIRONMENT_PATH",
        "configuration",
        "DUTCHBAY_P03_SOURCE_ROOT must contain an absolute path",
    )
    _require(
        source_root.name == "sources" and len(source_root.parts) >= 5,
        "SOURCE_ROOT_SCOPE",
        "configuration",
        "source root must be a narrowly scoped directory named sources",
    )
    _reject_symlink_components(source_root, "source root")
    try:
        resolved = source_root.resolve(strict=True)
    except OSError as exc:
        raise PrimarySourceControlError(
            "SOURCE_ROOT_MISSING", "configuration", "source root is unavailable"
        ) from exc
    _require(
        source_root.absolute() == resolved and resolved.is_dir(),
        "SOURCE_ROOT_ALIAS",
        "configuration",
        "source root must be its real directory path",
    )
    return resolved


def _stable_file_digest(path: Path, label: str) -> tuple[str, int]:
    _require(
        path.is_file() and not path.is_symlink(),
        "SOURCE_FILE_TYPE",
        "retained_sources",
        f"{label} is missing, symlinked or not a regular file",
    )
    before = path.stat()
    digest = _sha256_file(path)
    after = path.stat()
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "SOURCE_FILE_CHANGED",
        "retained_sources",
        f"{label} changed during verification",
    )
    return digest, after.st_size


def _stable_file_payload(path: Path, label: str) -> bytes:
    _require(
        path.is_file() and not path.is_symlink(),
        "SOURCE_FILE_TYPE",
        "retained_sources",
        f"{label} is missing, symlinked or not a regular file",
    )
    before = path.stat()
    payload = path.read_bytes()
    after = path.stat()
    _require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "SOURCE_FILE_CHANGED",
        "retained_sources",
        f"{label} changed during verification",
    )
    return payload


def _collect_retained_paths(root: Path) -> set[str]:
    actual_paths: set[str] = set()
    for directory_name in ("original", "converted"):
        directory = root / directory_name
        _require(
            directory.is_dir() and not directory.is_symlink(),
            "SOURCE_DIRECTORY",
            "retained_sources",
            f"retained {directory_name} directory missing or symlinked",
        )
        for candidate in directory.rglob("*"):
            _require(
                not candidate.is_symlink(),
                "SOURCE_SYMLINK",
                "retained_sources",
                "retained source tree contains a symlink",
            )
            if candidate.is_file():
                actual_paths.add(candidate.relative_to(root).as_posix())
            else:
                _require(
                    candidate.is_dir(),
                    "SOURCE_FILE_TYPE",
                    "retained_sources",
                    "retained source tree contains a special filesystem object",
                )
    return actual_paths


def _tested_snapshot() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for relative in TESTED_SNAPSHOT_RELATIVES:
        path = REPO_ROOT / relative
        digest, _ = _stable_file_digest(path, relative)
        snapshot[relative] = digest
    return snapshot


def _verify_repository_exceptions() -> None:
    for source_path, expected in EXPECTED_GOVERNED_EXCEPTIONS.items():
        repo_path = PACK_ROOT / str(expected["repository_path"])
        digest, _ = _stable_file_digest(repo_path, source_path)
        _require(
            digest == expected["sha256"],
            "REPOSITORY_EXCEPTION_HASH",
            "retained_sources",
            f"governed repository artifact hash mismatch: {source_path}",
        )


def verify_retained_source_root(source_root: Path) -> dict[str, Any]:
    """Hash-verify all retained source objects and return a path-free receipt."""

    validate_committed_plan()
    root = _safe_external_root(source_root)
    manifest_file = root / "SOURCE_ARCHIVE_MANIFEST.v2.sha256"
    manifest_payload = _stable_file_payload(manifest_file, "source manifest")
    _require(
        not manifest_file.is_symlink()
        and _sha256_bytes(manifest_payload) == SOURCE_MANIFEST_SHA256
        and manifest_payload == SOURCE_MANIFEST_PATH.read_bytes(),
        "EXTERNAL_MANIFEST_MISMATCH",
        "retained_sources",
        "retained source manifest is absent or differs from the controlled copy",
    )
    entries = parse_source_manifest(manifest_payload)
    historical_manifest = root / "SOURCE_ARCHIVE_MANIFEST.sha256"
    historical_digest, _ = _stable_file_digest(
        historical_manifest, "historical source manifest"
    )
    _require(
        historical_digest == HISTORICAL_SOURCE_MANIFEST_SHA256,
        "HISTORICAL_MANIFEST_HASH",
        "retained_sources",
        "historical source manifest hash mismatch",
    )
    expected_paths = {entry.relative_path for entry in entries}
    actual_paths = _collect_retained_paths(root)
    _require(
        actual_paths == expected_paths,
        "SOURCE_POPULATION",
        "retained_sources",
        "retained source file population differs from the 74-object manifest",
    )
    bytes_verified = 0
    actual_entries: list[dict[str, str]] = []
    for entry in entries:
        candidate = root / PurePosixPath(entry.relative_path)
        digest, size = _stable_file_digest(candidate, entry.relative_path)
        _require(
            digest == entry.sha256,
            "SOURCE_HASH_MISMATCH",
            "retained_sources",
            f"retained source hash mismatch: {entry.relative_path}",
        )
        bytes_verified += size
        actual_entries.append(
            {"relative_path": entry.relative_path, "sha256": entry.sha256}
        )
    query_log = root / "IEC_CATALOGUE_QUERY_LOG.json"
    query_digest, query_bytes = _stable_file_digest(query_log, "IEC query log")
    _require(
        query_digest
        == EXPECTED_GOVERNED_EXCEPTIONS["sources/IEC_CATALOGUE_QUERY_LOG.json"][
            "sha256"
        ],
        "QUERY_LOG_HASH",
        "retained_sources",
        "retained IEC query-log hash mismatch",
    )
    _verify_repository_exceptions()
    _require(
        _collect_retained_paths(root) == expected_paths,
        "SOURCE_POPULATION_CHANGED",
        "retained_sources",
        "retained source file population changed during verification",
    )
    return {
        "schema_version": "dutchbay.p03_primary_source_verification_receipt.v1",
        "status": "PASS",
        "gate_id": GATE_ID,
        "gate_status": "pending_independent_review",
        "release_status": "HOLD",
        "review_kind": "implementer_self_check",
        "independence_satisfied": False,
        "source_root_recorded": False,
        "source_root_selection": "DUTCHBAY_P03_SOURCE_ROOT_environment_only",
        "source_register_sha256": REGISTER_SHA256,
        "csv_sha256": CSV_SHA256,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA256,
        "source_manifest_objects": len(entries),
        "source_manifest_objects_verified": len(entries),
        "source_manifest_unique_digests": len({entry.sha256 for entry in entries}),
        "source_payload_bytes_verified": bytes_verified,
        "verified_content_set_sha256": _canonical_sha256(actual_entries),
        "parent_governed_query_log_sha256": query_digest,
        "parent_governed_query_log_bytes": query_bytes,
        "governed_repository_exceptions_verified": len(EXPECTED_GOVERNED_EXCEPTIONS),
        "claim_records_structurally_verified": EXPECTED_RECORD_COUNT,
        "claim_records_semantically_reviewed": 0,
        "publication_rights_reviews_completed": 0,
        "tested_snapshot": _tested_snapshot(),
        "completion_authorized": False,
        "limitations": [
            "All source bytes and structural links passed implementer preflight; semantic support and publication rights remain unreviewed.",
            "No local source-root path is recorded in this receipt.",
            "This receipt cannot satisfy the independent P03 reviewer requirement or lift HOLD.",
        ],
    }


def failure_receipt(error: PrimarySourceControlError) -> dict[str, Any]:
    """Return a path-free fail-closed receipt for the P03 verification CLI."""

    return {
        "schema_version": "dutchbay.p03_primary_source_verification_receipt.v1",
        "status": "FAIL",
        "gate_id": GATE_ID,
        "gate_status": "pending_independent_review",
        "release_status": "HOLD",
        "code": error.code,
        "stage": error.stage,
        "detail": error.detail,
        "completion_authorized": False,
    }


def main() -> None:
    """Write the deterministic plan and emit one concise build receipt."""

    payload = build_review_plan()
    rendered = render_json(payload)
    _require(
        "/Users/" not in rendered,
        "PLAN_LOCAL_PATH",
        "review_plan",
        "generated P03 plan contains a machine-local path",
    )
    PLAN_PATH.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "release_status": "HOLD",
                "gate_status": "pending_independent_review",
                "records": EXPECTED_RECORD_COUNT,
                "manifest_objects": EXPECTED_MANIFEST_COUNT,
                "output": PLAN_PATH.relative_to(REPO_ROOT).as_posix(),
                "output_sha256": _sha256_file(PLAN_PATH),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
