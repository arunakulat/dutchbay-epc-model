"""Portable, fail-closed recovery controls for the DutchBay audit checkpoint.

The historical checkpoint contains a complete remediation tar archive, a Git bundle,
and a manifest-governed external audit corpus.  Its convenience-expanded remediation
directory is incomplete and its original validator depended on retired absolute paths.
This module reconstructs a clean successor from the verified archive and validates the
entire retained dependency chain without publishing the private payload.

Successful execution establishes structural recoverability only.  It never establishes
semantic correctness, lender acceptability, bankability, or release approval.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, NoReturn, Sequence, cast

RECOVERY_DESCRIPTOR_SCHEMA = "dutchbay.audit_recovery_descriptor.v1"
RECOVERY_RECEIPT_SCHEMA = "dutchbay.audit_recovery_receipt.v1"
STRUCTURAL_PASS = "structural_pass"
RELEASE_HOLD = "HOLD"
PENDING_INDEPENDENT_REVIEW = "pending_independent_review"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_MANIFEST_LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")
_APPLEDOUBLE_MAGIC = b"\x00\x05\x16\x07"


class AuditRecoveryError(ValueError):
    """Predictable recovery-control failure safe for a concise CLI receipt."""

    def __init__(self, code: str, check: str, message: str) -> None:
        """Initialize one typed recovery failure.

        Args:
            code: Stable machine-readable error code.
            check: Stable recovery check identifier.
            message: Actionable message containing no machine-local absolute path.
        """

        super().__init__(message)
        self.code = code
        self.check = check


@dataclass(frozen=True)
class ManifestEntry:
    """One exact SHA-256 manifest entry."""

    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ManifestSummary:
    """Validated facts for one manifest-governed directory."""

    manifest_sha256: str
    entries: int
    manifest_scope_root_digest_sha256: str
    root_digest_sha256: str


def _fail(code: str, check: str, message: str) -> NoReturn:
    raise AuditRecoveryError(code, check, message)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        _fail("DESCRIPTOR_TYPE", "descriptor", f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], label: str
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        detail: list[str] = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"unexpected {extra}")
        _fail(
            "DESCRIPTOR_KEYS",
            "descriptor",
            f"{label} has wrong fields: {'; '.join(detail)}",
        )


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("DESCRIPTOR_TYPE", "descriptor", f"{label} must be a non-empty string")
    return value


def _require_sha256(value: object, label: str) -> str:
    text = _require_string(value, label)
    if not _SHA256_RE.fullmatch(text):
        _fail("DESCRIPTOR_SHA256", "descriptor", f"{label} must be lowercase SHA-256")
    return text


def _require_git_oid(value: object, label: str) -> str:
    text = _require_string(value, label)
    if not _GIT_OID_RE.fullmatch(text):
        _fail(
            "DESCRIPTOR_GIT_OID", "descriptor", f"{label} must be a full Git object ID"
        )
    return text


def _require_positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _fail("DESCRIPTOR_TYPE", "descriptor", f"{label} must be a positive integer")
    return value


def _require_nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("DESCRIPTOR_TYPE", "descriptor", f"{label} must be a nonnegative integer")
    return value


def _require_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail("DESCRIPTOR_TYPE", "descriptor", f"{label} must be a non-empty list")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_require_string(item, f"{label}[{index}]"))
    if len(result) != len(set(result)):
        _fail("DESCRIPTOR_DUPLICATE", "descriptor", f"{label} contains duplicates")
    return result


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "DESCRIPTOR_DUPLICATE",
                "descriptor",
                f"descriptor contains duplicate JSON key: {key}",
            )
        result[key] = value
    return result


def _load_descriptor(path: Path) -> tuple[dict[str, object], str]:
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("DESCRIPTOR_MISSING", "descriptor", "recovery descriptor is unavailable")
    try:
        loaded = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        _fail("DESCRIPTOR_JSON", "descriptor", f"recovery descriptor is invalid: {exc}")
    if not isinstance(loaded, dict):
        _fail("DESCRIPTOR_TYPE", "descriptor", "recovery descriptor must be an object")
    descriptor = cast(dict[str, object], loaded)
    _validate_descriptor(descriptor)
    return descriptor, _sha256_bytes(raw)


def _validate_descriptor(descriptor: Mapping[str, object]) -> None:
    _require_exact_keys(
        descriptor,
        {
            "schema_version",
            "document_id",
            "gate_id",
            "release_status",
            "independent_review_status",
            "checkpoint",
            "audit_corpus",
            "repository",
            "materialized_successor",
            "trust_boundary",
            "publication_boundary",
            "limitations",
        },
        "descriptor",
    )
    if descriptor["schema_version"] != RECOVERY_DESCRIPTOR_SCHEMA:
        _fail("DESCRIPTOR_SCHEMA", "descriptor", "recovery descriptor schema is wrong")
    if descriptor["document_id"] != "P01-RECOVERY-DESCRIPTOR-v1":
        _fail("DESCRIPTOR_ID", "descriptor", "recovery descriptor document_id is wrong")
    if descriptor["gate_id"] != "P01":
        _fail("DESCRIPTOR_GATE", "descriptor", "recovery descriptor gate_id is wrong")
    if descriptor["release_status"] != RELEASE_HOLD:
        _fail(
            "DESCRIPTOR_RELEASE", "descriptor", "recovery descriptor must retain HOLD"
        )
    if descriptor["independent_review_status"] != PENDING_INDEPENDENT_REVIEW:
        _fail(
            "DESCRIPTOR_REVIEW",
            "descriptor",
            "recovery descriptor must retain pending independent review",
        )

    checkpoint = _require_mapping(descriptor["checkpoint"], "checkpoint")
    _require_exact_keys(
        checkpoint,
        {
            "checkpoint_payload_manifest",
            "remediation_archive",
            "inner_manifest",
            "source_manifest",
            "repository_bundle",
        },
        "checkpoint",
    )
    _validate_manifest_contract(
        checkpoint["checkpoint_payload_manifest"], "checkpoint_payload_manifest"
    )
    archive = _require_mapping(checkpoint["remediation_archive"], "remediation_archive")
    _require_exact_keys(
        archive,
        {
            "filename",
            "sha256",
            "tar_root",
            "governed_file_members",
            "appledouble_metadata_members",
            "total_regular_file_members",
        },
        "remediation_archive",
    )
    _safe_relative_path(_require_string(archive["filename"], "archive filename"))
    _require_sha256(archive["sha256"], "archive sha256")
    _safe_relative_path(_require_string(archive["tar_root"], "archive tar_root"))
    governed_members = _require_positive_int(
        archive["governed_file_members"], "archive governed_file_members"
    )
    appledouble_members = _require_nonnegative_int(
        archive["appledouble_metadata_members"],
        "archive appledouble_metadata_members",
    )
    total_regular_members = _require_positive_int(
        archive["total_regular_file_members"],
        "archive total_regular_file_members",
    )
    if governed_members + appledouble_members != total_regular_members:
        _fail(
            "DESCRIPTOR_COUNT",
            "descriptor",
            "archive regular-file member counts do not reconcile",
        )
    _validate_manifest_contract(checkpoint["inner_manifest"], "inner_manifest")
    source_contract = _require_mapping(checkpoint["source_manifest"], "source_manifest")
    _validate_manifest_contract(
        source_contract,
        "source_manifest",
        additional_fields={"parent_governed_unlisted_paths"},
    )
    parent_governed_unlisted = _require_string_list(
        source_contract["parent_governed_unlisted_paths"],
        "source_manifest parent_governed_unlisted_paths",
    )
    for relative_path in parent_governed_unlisted:
        _safe_relative_path(relative_path)

    bundle = _require_mapping(checkpoint["repository_bundle"], "repository_bundle")
    _require_exact_keys(bundle, {"filename", "sha256", "refs"}, "repository_bundle")
    _safe_relative_path(_require_string(bundle["filename"], "bundle filename"))
    _require_sha256(bundle["sha256"], "bundle sha256")
    refs = _require_mapping(bundle["refs"], "repository_bundle refs")
    if not refs:
        _fail("DESCRIPTOR_TYPE", "descriptor", "repository_bundle refs cannot be empty")
    for ref, commit in refs.items():
        _safe_git_ref(ref)
        _require_git_oid(commit, f"repository_bundle ref {ref}")

    audit = _require_mapping(descriptor["audit_corpus"], "audit_corpus")
    _require_exact_keys(
        audit,
        {
            "manifest",
            "ingress_scope_root_digest_sha256",
            "excluded_post_ingress_files",
            "retained_directory_files",
            "root_digest_sha256",
            "publication_classification",
        },
        "audit_corpus",
    )
    audit_manifest = _require_mapping(audit["manifest"], "audit_corpus manifest")
    _validate_manifest_contract(audit_manifest, "audit_corpus manifest")
    _require_sha256(
        audit["ingress_scope_root_digest_sha256"],
        "audit_corpus ingress_scope_root_digest_sha256",
    )
    excluded = audit["excluded_post_ingress_files"]
    if not isinstance(excluded, list) or not excluded:
        _fail(
            "DESCRIPTOR_TYPE",
            "descriptor",
            "audit_corpus excluded_post_ingress_files must be a non-empty list",
        )
    excluded_paths: dict[str, str] = {}
    collision_paths: dict[str, str] = {}
    for index, item in enumerate(excluded):
        record = _require_mapping(item, f"excluded_post_ingress_files[{index}]")
        _require_exact_keys(
            record,
            {"relative_path", "sha256", "classification"},
            f"excluded_post_ingress_files[{index}]",
        )
        relative_path = _safe_relative_path(
            _require_string(
                record["relative_path"],
                f"excluded_post_ingress_files[{index}] relative_path",
            )
        )
        if relative_path in excluded_paths:
            _fail(
                "DESCRIPTOR_DUPLICATE",
                "descriptor",
                f"audit_corpus exclusion duplicates {relative_path}",
            )
        collision = _collision_key(relative_path)
        if collision in collision_paths:
            _fail(
                "DESCRIPTOR_DUPLICATE",
                "descriptor",
                "audit_corpus exclusions have a case/Unicode collision",
            )
        collision_paths[collision] = relative_path
        excluded_paths[relative_path] = _require_sha256(
            record["sha256"],
            f"excluded_post_ingress_files[{index}] sha256",
        )
        _require_string(
            record["classification"],
            f"excluded_post_ingress_files[{index}] classification",
        )
    retained_directory_files = _require_positive_int(
        audit["retained_directory_files"], "audit_corpus retained_directory_files"
    )
    ingress_entries = _require_positive_int(
        audit_manifest["entries"], "audit_corpus manifest entries"
    )
    if retained_directory_files != ingress_entries + 1 + len(excluded_paths):
        _fail(
            "DESCRIPTOR_COUNT",
            "descriptor",
            "audit_corpus retained file population does not reconcile",
        )
    _require_sha256(audit["root_digest_sha256"], "audit_corpus root_digest_sha256")
    if audit["publication_classification"] != "retained_private_external_dependency":
        _fail(
            "DESCRIPTOR_PUBLICATION",
            "descriptor",
            "audit corpus must remain a retained private external dependency",
        )

    repository = _require_mapping(descriptor["repository"], "repository")
    _require_exact_keys(
        repository,
        {
            "origin_repository",
            "audited_commit",
            "successor_validator_relative_path",
            "expected_successor_contract",
        },
        "repository",
    )
    _require_string(repository["origin_repository"], "repository origin_repository")
    _require_git_oid(repository["audited_commit"], "repository audited_commit")
    _safe_relative_path(
        _require_string(
            repository["successor_validator_relative_path"],
            "repository successor_validator_relative_path",
        )
    )
    successor_contract = _require_mapping(
        repository["expected_successor_contract"], "expected_successor_contract"
    )
    _require_exact_keys(
        successor_contract,
        {
            "status",
            "release_status",
            "programme_gate_records",
            "architecture_examination_records",
        },
        "expected_successor_contract",
    )
    if successor_contract["status"] != "PASS":
        _fail("DESCRIPTOR_CONTRACT", "descriptor", "successor status must be PASS")
    if successor_contract["release_status"] != RELEASE_HOLD:
        _fail(
            "DESCRIPTOR_CONTRACT", "descriptor", "successor release status must be HOLD"
        )
    _require_positive_int(
        successor_contract["programme_gate_records"], "programme_gate_records"
    )
    _require_positive_int(
        successor_contract["architecture_examination_records"],
        "architecture_examination_records",
    )

    materialized = _require_mapping(
        descriptor["materialized_successor"], "materialized_successor"
    )
    _require_exact_keys(
        materialized,
        {"files", "root_digest_sha256", "authoritative_remediation_source"},
        "materialized_successor",
    )
    _require_positive_int(materialized["files"], "materialized_successor files")
    _require_sha256(
        materialized["root_digest_sha256"], "materialized_successor root_digest_sha256"
    )
    if materialized["authoritative_remediation_source"] != "verified_tar_archive":
        _fail(
            "DESCRIPTOR_SOURCE",
            "descriptor",
            "materialized remediation source must be the verified tar archive",
        )

    _require_string_list(descriptor["trust_boundary"], "trust_boundary")
    publication = _require_mapping(
        descriptor["publication_boundary"], "publication_boundary"
    )
    _require_exact_keys(
        publication,
        {"committed_metadata_only", "excluded_payload_classes"},
        "publication_boundary",
    )
    _require_string_list(
        publication["committed_metadata_only"], "committed_metadata_only"
    )
    _require_string_list(
        publication["excluded_payload_classes"], "excluded_payload_classes"
    )
    _require_string_list(descriptor["limitations"], "limitations")


def _validate_manifest_contract(
    value: object,
    label: str,
    *,
    additional_fields: set[str] | None = None,
) -> None:
    contract = _require_mapping(value, label)
    expected = {"relative_path", "sha256", "entries"}
    if additional_fields:
        expected.update(additional_fields)
    _require_exact_keys(contract, expected, label)
    _safe_relative_path(_require_string(contract["relative_path"], f"{label} path"))
    _require_sha256(contract["sha256"], f"{label} sha256")
    _require_positive_int(contract["entries"], f"{label} entries")


def _safe_relative_path(value: str) -> str:
    if "\\" in value or "\x00" in value:
        _fail("UNSAFE_PATH", "path_safety", f"unsafe relative path: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.as_posix() != value
    ):
        _fail("UNSAFE_PATH", "path_safety", f"unsafe relative path: {value!r}")
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value:
        _fail("UNSAFE_PATH", "path_safety", f"non-canonical relative path: {value!r}")
    return value


def _safe_git_ref(value: str) -> str:
    if not value.startswith("refs/") or any(
        token in value for token in ("..", " ", "~", "^", ":")
    ):
        _fail("DESCRIPTOR_REF", "descriptor", f"unsafe Git ref: {value!r}")
    return value


def _collision_key(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def _parse_manifest_bytes(raw: bytes, label: str) -> list[ManifestEntry]:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        _fail("MANIFEST_ENCODING", label, f"{label} is not UTF-8")
    if "\r" in text:
        _fail("MANIFEST_FORMAT", label, f"{label} contains non-canonical line endings")
    entries: list[ManifestEntry] = []
    exact_paths: set[str] = set()
    collision_paths: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _MANIFEST_LINE_RE.fullmatch(line)
        if match is None:
            _fail(
                "MANIFEST_FORMAT",
                label,
                f"{label} has invalid line {line_number}",
            )
        digest, relative_path = match.groups()
        _safe_relative_path(relative_path)
        if relative_path in exact_paths:
            _fail(
                "MANIFEST_DUPLICATE",
                label,
                f"{label} duplicates {relative_path}",
            )
        collision = _collision_key(relative_path)
        if collision in collision_paths:
            _fail(
                "MANIFEST_COLLISION",
                label,
                f"{label} has colliding paths {collision_paths[collision]} and {relative_path}",
            )
        exact_paths.add(relative_path)
        collision_paths[collision] = relative_path
        entries.append(ManifestEntry(relative_path=relative_path, sha256=digest))
    if not entries:
        _fail("MANIFEST_EMPTY", label, f"{label} is empty")
    return entries


def _assert_no_symlink_components(
    path: Path, label: str, *, allow_missing: bool
) -> None:
    if not path.is_absolute():
        _fail("PATH_NOT_ABSOLUTE", "path_safety", f"{label} must be an absolute path")
    if ".." in path.parts:
        _fail(
            "PATH_NON_CANONICAL",
            "path_safety",
            f"{label} must not contain parent traversal",
        )
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            if allow_missing:
                return
            _fail("PATH_MISSING", "path_safety", f"{label} is unavailable")
        if current.is_symlink():
            _fail(
                "PATH_SYMLINK", "path_safety", f"{label} contains a symlink component"
            )


def _require_directory(path: Path, label: str) -> None:
    _assert_no_symlink_components(path, label, allow_missing=False)
    if not path.is_dir():
        _fail("PATH_NOT_DIRECTORY", "path_safety", f"{label} must be a directory")


def _require_regular_file(path: Path, label: str) -> None:
    _assert_no_symlink_components(path, label, allow_missing=False)
    if not path.is_file():
        _fail("PATH_NOT_FILE", "path_safety", f"{label} must be a regular file")


def _assert_distinct_roots(inputs: Sequence[tuple[Path, str]]) -> None:
    canonical: list[tuple[str, str]] = []
    for path, label in inputs:
        key = _collision_key(str(path.resolve(strict=False)))
        for existing_key, existing_label in canonical:
            if (
                key == existing_key
                or key.startswith(existing_key + os.sep)
                or existing_key.startswith(key + os.sep)
            ):
                _fail(
                    "PATH_OVERLAP",
                    "path_safety",
                    f"{label} overlaps {existing_label}",
                )
        canonical.append((key, label))


def _actual_regular_files(root: Path) -> set[str]:
    result: set[str] = set()
    collisions: dict[str, str] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            _fail(
                "FILESYSTEM_SYMLINK",
                "manifest",
                f"manifest root contains symlink {relative}",
            )
        if path.is_dir():
            continue
        if not path.is_file():
            _fail(
                "FILESYSTEM_SPECIAL",
                "manifest",
                f"manifest root contains special entry {relative}",
            )
        collision = _collision_key(relative)
        if collision in collisions:
            _fail(
                "FILESYSTEM_COLLISION",
                "manifest",
                f"manifest root has colliding paths {collisions[collision]} and {relative}",
            )
        collisions[collision] = relative
        result.add(relative)
    return result


def _canonical_root_digest(entries: Sequence[ManifestEntry]) -> str:
    lines = "".join(
        f"{entry.sha256}  {entry.relative_path}\n"
        for entry in sorted(entries, key=lambda item: item.relative_path)
    )
    return _sha256_bytes(lines.encode("utf-8"))


def _validate_manifest_directory(
    root: Path,
    contract: Mapping[str, object],
    *,
    label: str,
    manifest_relative_to_root: str,
    parent_governed_unlisted_paths: Sequence[str] = (),
    additional_attested_entries: Sequence[ManifestEntry] = (),
) -> ManifestSummary:
    manifest_path = root / manifest_relative_to_root
    _require_regular_file(manifest_path, label)
    raw = manifest_path.read_bytes()
    actual_manifest_sha = _sha256_bytes(raw)
    expected_manifest_sha = _require_sha256(contract["sha256"], f"{label} sha256")
    if actual_manifest_sha != expected_manifest_sha:
        _fail("MANIFEST_DIGEST", label, f"{label} digest mismatch")
    entries = _parse_manifest_bytes(raw, label)
    expected_count = _require_positive_int(contract["entries"], f"{label} entries")
    if len(entries) != expected_count:
        _fail(
            "MANIFEST_COUNT",
            label,
            f"{label} expected {expected_count} entries but found {len(entries)}",
        )
    expected_paths = {entry.relative_path for entry in entries}
    permitted_unlisted = set(parent_governed_unlisted_paths)
    attested_unlisted = {
        entry.relative_path: entry.sha256 for entry in additional_attested_entries
    }
    if len(attested_unlisted) != len(additional_attested_entries):
        _fail(
            "MANIFEST_SCOPE",
            label,
            f"{label} duplicates an additional attested path",
        )
    if expected_paths & permitted_unlisted:
        _fail(
            "MANIFEST_SCOPE",
            label,
            f"{label} parent-governed exception duplicates a manifest entry",
        )
    if expected_paths & set(attested_unlisted):
        _fail(
            "MANIFEST_SCOPE",
            label,
            f"{label} additional attestation duplicates a manifest entry",
        )
    if permitted_unlisted & set(attested_unlisted):
        _fail(
            "MANIFEST_SCOPE",
            label,
            f"{label} additional attestation duplicates a parent-governed path",
        )
    for relative_path in permitted_unlisted:
        _safe_relative_path(relative_path)
    for relative_path, expected_sha in attested_unlisted.items():
        _safe_relative_path(relative_path)
        if not _SHA256_RE.fullmatch(expected_sha):
            _fail(
                "MANIFEST_SCOPE",
                label,
                f"{label} additional attestation has an invalid SHA-256",
            )
    actual_paths = _actual_regular_files(root)
    actual_paths.discard(manifest_relative_to_root)
    missing = sorted(expected_paths - actual_paths)
    missing_parent_governed = sorted(permitted_unlisted - actual_paths)
    missing_attested = sorted(set(attested_unlisted) - actual_paths)
    unexpected = sorted(
        actual_paths - expected_paths - permitted_unlisted - set(attested_unlisted)
    )
    if missing:
        _fail("MANIFEST_MISSING", label, f"{label} is missing {missing[0]}")
    if missing_parent_governed:
        _fail(
            "PARENT_MANIFEST_MISSING",
            label,
            f"{label} is missing parent-governed {missing_parent_governed[0]}",
        )
    if missing_attested:
        _fail(
            "ATTESTED_FILE_MISSING",
            label,
            f"{label} is missing attested {missing_attested[0]}",
        )
    if unexpected:
        _fail("MANIFEST_UNEXPECTED", label, f"{label} has unexpected {unexpected[0]}")
    for entry in entries:
        actual = _sha256_file(root / entry.relative_path)
        if actual != entry.sha256:
            _fail(
                "MANIFEST_HASH_MISMATCH",
                label,
                f"{label} hash mismatch for {entry.relative_path}",
            )
    for relative_path, expected_sha in attested_unlisted.items():
        if _sha256_file(root / relative_path) != expected_sha:
            _fail(
                "ATTESTED_FILE_HASH_MISMATCH",
                label,
                f"{label} attested hash mismatch for {relative_path}",
            )
    manifest_scope_entries = [
        *entries,
        ManifestEntry(
            relative_path=manifest_relative_to_root,
            sha256=actual_manifest_sha,
        ),
    ]
    all_entries = [*manifest_scope_entries, *additional_attested_entries]
    return ManifestSummary(
        manifest_sha256=actual_manifest_sha,
        entries=len(entries),
        manifest_scope_root_digest_sha256=_canonical_root_digest(
            manifest_scope_entries
        ),
        root_digest_sha256=_canonical_root_digest(all_entries),
    )


def _appledouble_target(name: str) -> str | None:
    path = PurePosixPath(name)
    basename = path.name
    if not basename.startswith("._"):
        return None
    target_basename = basename[2:]
    if not target_basename:
        _fail(
            "ARCHIVE_APPLEDOUBLE_NAME",
            "remediation_archive",
            "archive contains an invalid AppleDouble member name",
        )
    return (path.parent / target_basename).as_posix()


def _validate_archive(
    archive_path: Path,
    archive_contract: Mapping[str, object],
    outer_entries: Sequence[ManifestEntry],
) -> dict[str, bytes]:
    label = "remediation_archive"
    _require_regular_file(archive_path, label)
    expected_sha = _require_sha256(archive_contract["sha256"], "archive sha256")
    if _sha256_file(archive_path) != expected_sha:
        _fail("ARCHIVE_DIGEST", label, "remediation archive digest mismatch")
    tar_root = _require_string(archive_contract["tar_root"], "archive tar_root")
    expected_files = {
        entry.relative_path: entry.sha256
        for entry in outer_entries
        if entry.relative_path.startswith("remediation_workspace/")
    }
    payloads: dict[str, bytes] = {}
    exact_names: set[str] = set()
    collision_names: dict[str, str] = {}
    ordinary_member_names: set[str] = set()
    appledouble_targets: dict[str, str] = {}
    governed_file_members = 0
    total_regular_file_members = 0
    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (tarfile.TarError, OSError):
        _fail("ARCHIVE_OPEN", label, "remediation archive cannot be opened")
    with archive:
        for member in archive.getmembers():
            name = member.name.rstrip("/")
            _safe_relative_path(name)
            if name in exact_names:
                _fail("ARCHIVE_DUPLICATE", label, f"archive duplicates {name}")
            collision = _collision_key(name)
            if collision in collision_names:
                _fail(
                    "ARCHIVE_COLLISION",
                    label,
                    f"archive has colliding members {collision_names[collision]} and {name}",
                )
            exact_names.add(name)
            collision_names[collision] = name
            if member.issym() or member.islnk():
                _fail("ARCHIVE_LINK", label, f"archive contains link {name}")
            appledouble_target = _appledouble_target(name)
            if appledouble_target is not None:
                if not member.isfile():
                    _fail(
                        "ARCHIVE_APPLEDOUBLE_TYPE",
                        label,
                        "AppleDouble archive members must be regular files",
                    )
                if not (
                    appledouble_target == tar_root
                    or appledouble_target.startswith(tar_root + "/")
                ):
                    _fail(
                        "ARCHIVE_APPLEDOUBLE_ROOT",
                        label,
                        "AppleDouble archive member targets outside the tar root",
                    )
                extracted = archive.extractfile(member)
                if extracted is None:
                    _fail(
                        "ARCHIVE_APPLEDOUBLE_READ",
                        label,
                        "AppleDouble archive member cannot be read",
                    )
                metadata = extracted.read()
                if len(metadata) != 163 or not metadata.startswith(_APPLEDOUBLE_MAGIC):
                    _fail(
                        "ARCHIVE_APPLEDOUBLE_FORMAT",
                        label,
                        "AppleDouble archive member has an invalid format",
                    )
                appledouble_targets[name] = appledouble_target
                total_regular_file_members += 1
                continue
            if member.isdir():
                if not (name == tar_root or name.startswith(tar_root + "/")):
                    _fail(
                        "ARCHIVE_ROOT",
                        label,
                        f"archive directory is outside {tar_root}",
                    )
                ordinary_member_names.add(name)
                continue
            if not member.isfile():
                _fail(
                    "ARCHIVE_SPECIAL", label, f"archive contains special member {name}"
                )
            prefix = tar_root + "/"
            if not name.startswith(prefix):
                _fail("ARCHIVE_ROOT", label, f"archive member is outside {tar_root}")
            suffix = name[len(prefix) :]
            destination = "remediation_workspace/" + suffix
            if destination not in expected_files:
                _fail(
                    "ARCHIVE_UNEXPECTED", label, f"archive has unexpected {destination}"
                )
            extracted = archive.extractfile(member)
            if extracted is None:
                _fail(
                    "ARCHIVE_READ",
                    label,
                    f"archive member cannot be read: {destination}",
                )
            payload = extracted.read()
            if _sha256_bytes(payload) != expected_files[destination]:
                _fail(
                    "ARCHIVE_HASH_MISMATCH",
                    label,
                    f"archive hash mismatch for {destination}",
                )
            payloads[destination] = payload
            ordinary_member_names.add(name)
            governed_file_members += 1
            total_regular_file_members += 1
    appledouble_target_names = set(appledouble_targets.values())
    if len(appledouble_target_names) != len(appledouble_targets):
        _fail(
            "ARCHIVE_APPLEDOUBLE_DUPLICATE",
            label,
            "multiple AppleDouble members target one archive member",
        )
    if appledouble_target_names != ordinary_member_names:
        missing_metadata = sorted(ordinary_member_names - appledouble_target_names)
        missing_target = sorted(appledouble_target_names - ordinary_member_names)
        detail = missing_metadata[0] if missing_metadata else missing_target[0]
        _fail(
            "ARCHIVE_APPLEDOUBLE_PAIRING",
            label,
            f"AppleDouble pairing mismatch for {detail}",
        )
    expected_governed_count = _require_positive_int(
        archive_contract["governed_file_members"],
        "archive governed_file_members",
    )
    if governed_file_members != expected_governed_count:
        _fail(
            "ARCHIVE_COUNT",
            label,
            "archive expected "
            f"{expected_governed_count} governed files but found "
            f"{governed_file_members}",
        )
    expected_appledouble_count = _require_nonnegative_int(
        archive_contract["appledouble_metadata_members"],
        "archive appledouble_metadata_members",
    )
    if len(appledouble_targets) != expected_appledouble_count:
        _fail(
            "ARCHIVE_APPLEDOUBLE_COUNT",
            label,
            "archive expected "
            f"{expected_appledouble_count} AppleDouble members but found "
            f"{len(appledouble_targets)}",
        )
    expected_total_count = _require_positive_int(
        archive_contract["total_regular_file_members"],
        "archive total_regular_file_members",
    )
    if total_regular_file_members != expected_total_count:
        _fail(
            "ARCHIVE_TOTAL_COUNT",
            label,
            "archive expected "
            f"{expected_total_count} regular files but found "
            f"{total_regular_file_members}",
        )
    missing = sorted(set(expected_files) - set(payloads))
    if missing:
        _fail("ARCHIVE_MISSING", label, f"archive is missing {missing[0]}")
    return payloads


def _run_git(
    repository_root: Path,
    args: Sequence[str],
    check: str,
    *,
    failure_code: str = "GIT_COMMAND",
    failure_message: str | None = None,
) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if completed.returncode != 0:
        _fail(
            failure_code,
            check,
            failure_message or f"Git check failed: {' '.join(args[:2])}",
        )
    return completed.stdout.strip()


def _normalized_repository_identity(remote: str) -> str:
    value = remote.strip()
    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    if value.endswith(".git"):
        value = value[:-4]
    return value.strip("/")


def _validate_repository(
    repository_root: Path,
    repository_contract: Mapping[str, object],
) -> tuple[str, str]:
    _require_directory(repository_root, "repository root")
    top_level = Path(
        _run_git(repository_root, ["rev-parse", "--show-toplevel"], "repository")
    )
    try:
        same_root = top_level.samefile(repository_root)
    except OSError:
        same_root = False
    if not same_root:
        _fail(
            "REPOSITORY_ROOT", "repository", "repository root is not the Git top level"
        )
    remote = _run_git(repository_root, ["remote", "get-url", "origin"], "repository")
    expected_identity = _require_string(
        repository_contract["origin_repository"], "repository origin_repository"
    )
    if _normalized_repository_identity(remote) != expected_identity:
        _fail(
            "REPOSITORY_IDENTITY", "repository", "repository origin identity mismatch"
        )
    status = _run_git(
        repository_root,
        ["status", "--porcelain=v1", "--untracked-files=all"],
        "repository",
    )
    if status:
        _fail("REPOSITORY_DIRTY", "repository", "repository worktree must be clean")
    audited_commit = _require_git_oid(
        repository_contract["audited_commit"], "repository audited_commit"
    )
    _run_git(
        repository_root,
        ["cat-file", "-e", f"{audited_commit}^{{commit}}"],
        "repository",
        failure_code="AUDITED_COMMIT_MISSING",
        failure_message="audited commit is unavailable in the repository",
    )
    head = _run_git(repository_root, ["rev-parse", "HEAD"], "repository")
    if not _GIT_OID_RE.fullmatch(head):
        _fail(
            "REPOSITORY_HEAD",
            "repository",
            "repository HEAD is not a full Git object ID",
        )
    return expected_identity, head


def _validate_bundle(
    repository_root: Path,
    bundle_path: Path,
    bundle_contract: Mapping[str, object],
) -> dict[str, str]:
    label = "repository_bundle"
    _require_regular_file(bundle_path, label)
    expected_sha = _require_sha256(bundle_contract["sha256"], "bundle sha256")
    if _sha256_file(bundle_path) != expected_sha:
        _fail("BUNDLE_DIGEST", label, "repository bundle digest mismatch")
    _run_git(repository_root, ["bundle", "verify", str(bundle_path)], label)
    output = _run_git(
        repository_root, ["bundle", "list-heads", str(bundle_path)], label
    )
    actual: dict[str, str] = {}
    for line in output.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or not _GIT_OID_RE.fullmatch(parts[0]):
            _fail("BUNDLE_FORMAT", label, "repository bundle head listing is invalid")
        commit, ref = parts
        _safe_git_ref(ref)
        if ref in actual:
            _fail("BUNDLE_DUPLICATE", label, f"repository bundle duplicates {ref}")
        actual[ref] = commit
    expected_mapping = _require_mapping(bundle_contract["refs"], "bundle refs")
    expected = {str(key): str(value) for key, value in expected_mapping.items()}
    if actual != expected:
        _fail(
            "BUNDLE_REFS", label, "repository bundle refs do not match the descriptor"
        )
    return actual


def _validate_successor_pack(
    repository_root: Path,
    repository_contract: Mapping[str, object],
) -> Mapping[str, object]:
    relative = _require_string(
        repository_contract["successor_validator_relative_path"],
        "successor validator path",
    )
    validator = repository_root / relative
    _require_regular_file(validator, "successor validator")
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(repository_root)
    completed = subprocess.run(
        [sys.executable, str(validator)],
        cwd=repository_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
        env=environment,
    )
    if completed.returncode != 0:
        _fail(
            "SUCCESSOR_VALIDATOR",
            "successor_pack",
            "controlled successor validator failed",
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        _fail(
            "SUCCESSOR_RECEIPT",
            "successor_pack",
            "controlled successor receipt is invalid",
        )
    receipt = _require_mapping(result, "controlled successor receipt")
    expected = _require_mapping(
        repository_contract["expected_successor_contract"],
        "expected_successor_contract",
    )
    if receipt.get("status") != expected["status"]:
        _fail("SUCCESSOR_STATUS", "successor_pack", "controlled successor is not PASS")
    if receipt.get("release_status") != expected["release_status"]:
        _fail(
            "SUCCESSOR_RELEASE",
            "successor_pack",
            "controlled successor HOLD is missing",
        )
    programme = _require_mapping(receipt.get("programme_gates"), "programme_gates")
    architecture = _require_mapping(
        receipt.get("architecture_examinations"), "architecture_examinations"
    )
    if programme.get("records") != expected["programme_gate_records"]:
        _fail("SUCCESSOR_GATES", "successor_pack", "programme gate population drift")
    if programme.get("pending") != expected["programme_gate_records"]:
        _fail(
            "SUCCESSOR_GATES", "successor_pack", "programme gates are not all pending"
        )
    if architecture.get("records") != expected["architecture_examination_records"]:
        _fail(
            "SUCCESSOR_ARCHITECTURE", "successor_pack", "architecture population drift"
        )
    if (
        architecture.get("pending_examination")
        != expected["architecture_examination_records"]
    ):
        _fail(
            "SUCCESSOR_ARCHITECTURE",
            "successor_pack",
            "architecture examinations are not all pending",
        )
    return receipt


def _write_materialized_file(stage: Path, relative_path: str, payload: bytes) -> None:
    destination = stage / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as handle:
        handle.write(payload)


def _materialize_successor(
    checkpoint_root: Path,
    output_root: Path,
    outer_manifest_path: Path,
    outer_entries: Sequence[ManifestEntry],
    archived_payloads: Mapping[str, bytes],
) -> Path:
    output_parent = output_root.parent
    _require_directory(output_parent, "output parent")
    _assert_no_symlink_components(output_root, "output root", allow_missing=True)
    if output_root.exists():
        _fail("OUTPUT_EXISTS", "materialization", "output root must not already exist")
    stage = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.stage-", dir=output_parent)
    )
    try:
        for entry in outer_entries:
            if entry.relative_path.startswith("remediation_workspace/"):
                payload = archived_payloads.get(entry.relative_path)
                if payload is None:
                    _fail(
                        "ARCHIVE_MISSING",
                        "materialization",
                        f"archive is missing {entry.relative_path}",
                    )
            else:
                source = checkpoint_root / entry.relative_path
                if not source.exists() and not source.is_symlink():
                    _fail(
                        "MANIFEST_MISSING",
                        "checkpoint_payload_manifest",
                        "checkpoint_payload_manifest is missing "
                        f"{entry.relative_path}",
                    )
                _require_regular_file(
                    source, f"checkpoint payload {entry.relative_path}"
                )
                payload = source.read_bytes()
                if _sha256_bytes(payload) != entry.sha256:
                    _fail(
                        "CHECKPOINT_HASH_MISMATCH",
                        "materialization",
                        f"checkpoint hash mismatch for {entry.relative_path}",
                    )
            _write_materialized_file(stage, entry.relative_path, payload)
        _write_materialized_file(
            stage,
            outer_manifest_path.name,
            outer_manifest_path.read_bytes(),
        )
        os.replace(stage, output_root)
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return output_root


def validate_and_materialize_recovery(
    *,
    checkpoint_root: Path,
    audit_corpus_root: Path,
    repository_root: Path,
    output_root: Path,
    descriptor_path: Path,
) -> dict[str, object]:
    """Materialize and validate one complete portable recovery successor.

    Args:
        checkpoint_root: Historical checkpoint package containing the archive,
            bundle, and outer manifest.
        audit_corpus_root: Retained audit directory containing the immutable 73-file
            ingress population, its manifest, and explicitly classified later output.
        repository_root: Clean DutchBay repository worktree containing the audited
            commit and controlled successor.
        output_root: Nonexistent destination for the recovered checkpoint successor.
        descriptor_path: Repository-controlled hash-only recovery descriptor.

    Returns:
        A concise, JSON-safe structural receipt.  It deliberately records HOLD and
        pending independent review.

    Raises:
        AuditRecoveryError: If any path, manifest, archive, repository, bundle,
            controlled-pack, or publication-boundary invariant fails.
    """

    _require_directory(checkpoint_root, "checkpoint root")
    _require_directory(audit_corpus_root, "audit corpus root")
    _require_directory(repository_root, "repository root")
    _require_regular_file(descriptor_path, "recovery descriptor")
    _assert_no_symlink_components(output_root, "output root", allow_missing=True)
    _require_directory(output_root.parent, "output parent")
    _assert_distinct_roots(
        (
            (checkpoint_root, "checkpoint root"),
            (audit_corpus_root, "audit corpus root"),
            (repository_root, "repository root"),
            (output_root, "output root"),
        )
    )
    try:
        descriptor_inside_repo = descriptor_path.resolve().is_relative_to(
            repository_root.resolve()
        )
    except OSError:
        descriptor_inside_repo = False
    if not descriptor_inside_repo:
        _fail(
            "DESCRIPTOR_LOCATION",
            "descriptor",
            "recovery descriptor must be controlled by the repository",
        )
    descriptor, descriptor_sha = _load_descriptor(descriptor_path)
    checkpoint = _require_mapping(descriptor["checkpoint"], "checkpoint")

    outer_contract = _require_mapping(
        checkpoint["checkpoint_payload_manifest"], "checkpoint_payload_manifest"
    )
    outer_manifest_relative = _require_string(
        outer_contract["relative_path"], "checkpoint payload manifest path"
    )
    outer_manifest_path = checkpoint_root / outer_manifest_relative
    _require_regular_file(outer_manifest_path, "checkpoint payload manifest")
    outer_raw = outer_manifest_path.read_bytes()
    if _sha256_bytes(outer_raw) != outer_contract["sha256"]:
        _fail(
            "MANIFEST_DIGEST",
            "checkpoint_payload_manifest",
            "checkpoint payload manifest digest mismatch",
        )
    outer_entries = _parse_manifest_bytes(outer_raw, "checkpoint_payload_manifest")
    if len(outer_entries) != outer_contract["entries"]:
        _fail(
            "MANIFEST_COUNT",
            "checkpoint_payload_manifest",
            "checkpoint payload manifest population drift",
        )

    archive_contract = _require_mapping(
        checkpoint["remediation_archive"], "remediation_archive"
    )
    archive_path = checkpoint_root / _require_string(
        archive_contract["filename"], "archive filename"
    )
    archived_payloads = _validate_archive(archive_path, archive_contract, outer_entries)

    repository_contract = _require_mapping(descriptor["repository"], "repository")
    repository_identity, repository_head = _validate_repository(
        repository_root, repository_contract
    )
    bundle_contract = _require_mapping(
        checkpoint["repository_bundle"], "repository_bundle"
    )
    bundle_path = checkpoint_root / _require_string(
        bundle_contract["filename"], "bundle filename"
    )
    bundle_refs = _validate_bundle(repository_root, bundle_path, bundle_contract)
    _validate_successor_pack(repository_root, repository_contract)

    materialized_root = _materialize_successor(
        checkpoint_root,
        output_root,
        outer_manifest_path,
        outer_entries,
        archived_payloads,
    )
    try:
        outer_summary = _validate_manifest_directory(
            materialized_root,
            outer_contract,
            label="checkpoint_payload_manifest",
            manifest_relative_to_root=outer_manifest_relative,
        )
        inner_contract = _require_mapping(
            checkpoint["inner_manifest"], "inner_manifest"
        )
        inner_relative = _require_string(
            inner_contract["relative_path"], "inner manifest path"
        )
        workspace = materialized_root / "remediation_workspace"
        try:
            inner_within_workspace = (
                PurePosixPath(inner_relative)
                .relative_to(PurePosixPath("remediation_workspace"))
                .as_posix()
            )
        except ValueError:
            _fail(
                "DESCRIPTOR_PATH_SCOPE",
                "descriptor",
                "inner manifest must be below remediation_workspace",
            )
        inner_summary = _validate_manifest_directory(
            workspace,
            inner_contract,
            label="inner_manifest",
            manifest_relative_to_root=inner_within_workspace,
        )
        source_contract = _require_mapping(
            checkpoint["source_manifest"], "source_manifest"
        )
        source_relative = _require_string(
            source_contract["relative_path"], "source manifest path"
        )
        sources = workspace / "sources"
        try:
            source_within_sources = (
                PurePosixPath(source_relative)
                .relative_to(PurePosixPath("remediation_workspace/sources"))
                .as_posix()
            )
        except ValueError:
            _fail(
                "DESCRIPTOR_PATH_SCOPE",
                "descriptor",
                "source manifest must be below remediation_workspace/sources",
            )
        parent_governed_unlisted = _require_string_list(
            source_contract["parent_governed_unlisted_paths"],
            "source_manifest parent_governed_unlisted_paths",
        )
        source_summary = _validate_manifest_directory(
            sources,
            source_contract,
            label="source_manifest",
            manifest_relative_to_root=source_within_sources,
            parent_governed_unlisted_paths=parent_governed_unlisted,
        )
        audit = _require_mapping(descriptor["audit_corpus"], "audit_corpus")
        audit_contract = _require_mapping(audit["manifest"], "audit_corpus manifest")
        audit_manifest_relative = _require_string(
            audit_contract["relative_path"], "audit corpus manifest path"
        )
        excluded_records = audit["excluded_post_ingress_files"]
        if not isinstance(excluded_records, list):
            _fail(
                "DESCRIPTOR_TYPE",
                "descriptor",
                "audit_corpus excluded_post_ingress_files must be a list",
            )
        excluded_entries: list[ManifestEntry] = []
        for index, item in enumerate(excluded_records):
            record = _require_mapping(item, f"excluded_post_ingress_files[{index}]")
            excluded_entries.append(
                ManifestEntry(
                    relative_path=_require_string(
                        record["relative_path"],
                        f"excluded_post_ingress_files[{index}] relative_path",
                    ),
                    sha256=_require_sha256(
                        record["sha256"],
                        f"excluded_post_ingress_files[{index}] sha256",
                    ),
                )
            )
        audit_summary = _validate_manifest_directory(
            audit_corpus_root,
            audit_contract,
            label="audit_corpus_manifest",
            manifest_relative_to_root=audit_manifest_relative,
            additional_attested_entries=excluded_entries,
        )
        if (
            audit_summary.manifest_scope_root_digest_sha256
            != audit["ingress_scope_root_digest_sha256"]
        ):
            _fail(
                "AUDIT_INGRESS_ROOT_DIGEST",
                "audit_corpus_manifest",
                "audit corpus ingress-scope root digest mismatch",
            )
        if audit_summary.root_digest_sha256 != audit["root_digest_sha256"]:
            _fail(
                "AUDIT_ROOT_DIGEST",
                "audit_corpus_manifest",
                "audit corpus root digest mismatch",
            )
        retained_directory_files = _require_positive_int(
            audit["retained_directory_files"],
            "audit_corpus retained_directory_files",
        )
        if len(_actual_regular_files(audit_corpus_root)) != retained_directory_files:
            _fail(
                "AUDIT_RETAINED_COUNT",
                "audit_corpus_manifest",
                "audit corpus retained file population drift",
            )
        materialized_contract = _require_mapping(
            descriptor["materialized_successor"], "materialized_successor"
        )
        expected_files = _require_positive_int(
            materialized_contract["files"], "materialized_successor files"
        )
        if len(_actual_regular_files(materialized_root)) != expected_files:
            _fail(
                "MATERIALIZED_COUNT",
                "materialization",
                "materialized successor file population drift",
            )
        if (
            outer_summary.root_digest_sha256
            != materialized_contract["root_digest_sha256"]
        ):
            _fail(
                "MATERIALIZED_ROOT_DIGEST",
                "materialization",
                "materialized successor root digest mismatch",
            )
    except BaseException:
        # The destination is a newly-created controlled output of this call.  A failed
        # validation must not leave a plausible-looking partial recovery successor.
        shutil.rmtree(materialized_root, ignore_errors=True)
        raise

    audited_commit = _require_git_oid(
        repository_contract["audited_commit"], "audited commit"
    )
    return {
        "schema_version": RECOVERY_RECEIPT_SCHEMA,
        "gate_id": "P01",
        "status": "PASS",
        "structural_status": STRUCTURAL_PASS,
        "gate_status": PENDING_INDEPENDENT_REVIEW,
        "release_status": RELEASE_HOLD,
        "descriptor_sha256": descriptor_sha,
        "checkpoint": {
            "outer_manifest_sha256": outer_summary.manifest_sha256,
            "outer_entries": outer_summary.entries,
            "archive_sha256": archive_contract["sha256"],
            "archive_governed_file_members": archive_contract["governed_file_members"],
            "archive_appledouble_metadata_members": archive_contract[
                "appledouble_metadata_members"
            ],
            "archive_total_regular_file_members": archive_contract[
                "total_regular_file_members"
            ],
            "inner_manifest_sha256": inner_summary.manifest_sha256,
            "inner_entries": inner_summary.entries,
            "source_manifest_sha256": source_summary.manifest_sha256,
            "source_entries": source_summary.entries,
        },
        "audit_corpus": {
            "manifest_sha256": audit_summary.manifest_sha256,
            "entries": audit_summary.entries,
            "ingress_scope_root_digest_sha256": (
                audit_summary.manifest_scope_root_digest_sha256
            ),
            "excluded_post_ingress_files": len(excluded_entries),
            "retained_directory_files": audit["retained_directory_files"],
            "root_digest_sha256": audit_summary.root_digest_sha256,
            "publication_classification": audit["publication_classification"],
        },
        "repository": {
            "origin_repository": repository_identity,
            "head_commit": repository_head,
            "audited_commit": audited_commit,
            "audited_commit_present": True,
            "bundle_sha256": bundle_contract["sha256"],
            "bundle_refs": dict(sorted(bundle_refs.items())),
        },
        "materialized_successor": {
            "files": len(_actual_regular_files(materialized_root)),
            "root_digest_sha256": outer_summary.root_digest_sha256,
            "authoritative_remediation_source": "verified_tar_archive",
        },
        "trust_boundary": {
            "internal_hash_consistency": "verified",
            "repository_attestation": "descriptor tracked by Git; merge identity external to payload",
            "third_party_authorship": "not established by hashes",
            "semantic_approval": "not established",
            "independent_review": "required",
        },
    }


def failure_receipt(error: AuditRecoveryError) -> dict[str, object]:
    """Return the one concise public failure shape used by the Hydra CLI."""

    return {
        "schema_version": RECOVERY_RECEIPT_SCHEMA,
        "gate_id": "P01",
        "status": "FAIL",
        "structural_status": "failed",
        "gate_status": PENDING_INDEPENDENT_REVIEW,
        "release_status": RELEASE_HOLD,
        "error": {
            "code": error.code,
            "check": error.check,
            "message": str(error),
        },
    }


__all__ = [
    "AuditRecoveryError",
    "PENDING_INDEPENDENT_REVIEW",
    "RECOVERY_DESCRIPTOR_SCHEMA",
    "RECOVERY_RECEIPT_SCHEMA",
    "RELEASE_HOLD",
    "STRUCTURAL_PASS",
    "failure_receipt",
    "validate_and_materialize_recovery",
]
