"""Fail-closed real/site QSTS evidence-package verification (#1072).

An enabled utility/site QSTS path is not evidence merely because a ``.dss`` file exists or
because YAML labels it "real". This module accepts it only when an externally pinned JSON
manifest binds the classification, feeder graph, generation profile, grid-instruction
schedule, export cap, timestep, and every payload byte. The accepted bytes are retained in
memory for private snapshot execution, closing the verify-then-reopen (TOCTOU) gap.

The v1 manifest has these exact top-level keys::

    {
      "schema": "dutchbay_qsts_evidence_manifest_v1",
      "package_id": "...",
      "input_kind": "utility_observed_model | engineer_prepared_site_model",
      "classification": {
        "generated_input": false,
        "observed_network_data": true | false,
        "site_representative": true,
        "bankable": false
      },
      "provenance": {
        "source_authority": "...",
        "source_reference": "...",
        "issued_at_utc": "RFC-3339 timestamp with timezone"
      },
      "feeder_model_path": "feeder/Master.dss",
      "runtime_inputs": {
        "generation_profile_mw_path": "profiles/generation.json",
        "grid_instructed_profile_mw_path": "profiles/instructions.json",
        "export_cap_mw": 150.0,
        "timestep_hours": 1.0
      },
      "payload_sha256": {"relative/path": "lowercase sha256", "...": "..."}
    }

Each profile payload is strict JSON with exact keys
``{"schema":"dutchbay_qsts_profile_v1","unit":"MW","values":[...]}``.
External manifest pinning authenticates package identity; it does *not* make the study
bankable. Bankability stays false until separate real-data, utility, and sign-off gates close.
"""

from __future__ import annotations

import hashlib
import json
import math
import posixpath
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, TypeGuard

from analytics.contracts_v14 import CANONICAL_FEEDER_INPUT_KINDS

QSTS_EVIDENCE_MANIFEST_SCHEMA = "dutchbay_qsts_evidence_manifest_v1"
QSTS_PROFILE_SCHEMA = "dutchbay_qsts_profile_v1"

_MANIFEST_KEYS = {
    "schema",
    "package_id",
    "input_kind",
    "classification",
    "provenance",
    "feeder_model_path",
    "runtime_inputs",
    "payload_sha256",
}
_CLASSIFICATION_KEYS = {
    "generated_input",
    "observed_network_data",
    "site_representative",
    "bankable",
}
_PROVENANCE_KEYS = {"source_authority", "source_reference", "issued_at_utc"}
_RUNTIME_KEYS = {
    "generation_profile_mw_path",
    "grid_instructed_profile_mw_path",
    "export_cap_mw",
    "timestep_hours",
}
_PROFILE_KEYS = {"schema", "unit", "values"}
_PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DSS_REDIRECT_RE = re.compile(
    r"^\s*(?:redirect|compile)\s+(?:\"([^\"]+)\"|'([^']+)'|([^\s!]+))",
    re.IGNORECASE,
)
_DSS_FILE_RE = re.compile(
    r"(?:csvfile|dblfile|sngfile|file)\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s,)!]+))",
    re.IGNORECASE,
)
_MAX_PAYLOAD_COUNT = 512
_MAX_PAYLOAD_BYTES = 256 * 1024 * 1024


class QSTSEvidenceError(ValueError):
    """A fail-closed QSTS identity, classification, or payload-binding failure."""


@dataclass(frozen=True)
class VerifiedQSTSPayload:
    """One payload accepted by digest and retained for immutable runtime execution."""

    relative_path: str
    sha256: str
    content: bytes


@dataclass(frozen=True)
class VerifiedQSTSEvidencePackage:
    """Externally pinned real/site package accepted for QSTS runtime use."""

    package_id: str
    input_kind: str
    manifest_sha256: str
    source_root: Path
    master_relative_path: str
    generation_profile_mw: tuple[float, ...]
    grid_instructed_profile_mw: tuple[float, ...]
    export_cap_mw: float
    timestep_hours: float
    payloads: tuple[VerifiedQSTSPayload, ...]
    observed_network_data: bool
    site_representative: bool


def _is_mapping(value: Any) -> TypeGuard[Mapping[str, Any]]:
    return isinstance(value, Mapping)


def _require_exact_keys(
    value: Mapping[str, Any], expected: set[str], field: str
) -> None:
    actual = set(value)
    if actual != expected:
        raise QSTSEvidenceError(
            f"{field} keys must be exactly {sorted(expected)}; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}."
        )


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise QSTSEvidenceError(
            f"{field} must be exactly 64 lowercase hexadecimal characters, got "
            f"{value!r}."
        )
    return value


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QSTSEvidenceError(f"{field} must be a non-empty string.")
    return value.strip()


def _require_positive(value: Any, field: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or float(value) <= 0.0
    ):
        raise QSTSEvidenceError(f"{field} must be a finite number > 0, got {value!r}.")
    return float(value)


def _safe_relative_path(value: Any, field: str) -> str:
    raw = _require_nonempty_string(value, field)
    if "\\" in raw:
        raise QSTSEvidenceError(
            f"{field} must use portable POSIX separators and may not contain backslashes."
        )
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or raw.startswith("~")
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise QSTSEvidenceError(
            f"{field} must be a normalized package-relative path without traversal, got "
            f"{value!r}."
        )
    normalized = posixpath.normpath(raw)
    if normalized != raw:
        raise QSTSEvidenceError(
            f"{field} must already be normalized; got {raw!r}, expected {normalized!r}."
        )
    return raw


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise QSTSEvidenceError(f"Evidence JSON repeats key {key!r}.")
        out[key] = value
    return out


def _load_json_bytes(payload: bytes, field: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise QSTSEvidenceError(f"{field} must be UTF-8 JSON.") from exc
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except QSTSEvidenceError:
        raise
    except json.JSONDecodeError as exc:
        raise QSTSEvidenceError(
            f"{field} is malformed JSON at line {exc.lineno}, column {exc.colno}."
        ) from exc


def _reject_symlink_path(path: Path, root: Path, field: str) -> None:
    """Reject a payload or any existing package-relative ancestor that is a symlink."""

    try:
        relative_parts = path.relative_to(root).parts
    except ValueError as exc:
        raise QSTSEvidenceError(
            f"{field} must resolve inside evidence package root {root}, got {path}."
        ) from exc
    current = root
    for part in relative_parts:
        current = current / part
        if current.is_symlink():
            raise QSTSEvidenceError(
                f"{field} resolves through symlink {current}; evidence payloads must be "
                "ordinary package files."
            )


def _read_bound_payload(
    *, root: Path, relative_path: str, expected_sha256: str, total_bytes: int
) -> tuple[VerifiedQSTSPayload, int]:
    path = root.joinpath(*PurePosixPath(relative_path).parts)
    _reject_symlink_path(path, root, f"payload {relative_path!r}")
    if not path.is_file():
        raise QSTSEvidenceError(
            f"Evidence manifest payload {relative_path!r} is missing or not a file."
        )
    content = path.read_bytes()
    new_total = total_bytes + len(content)
    if new_total > _MAX_PAYLOAD_BYTES:
        raise QSTSEvidenceError(
            f"Evidence package exceeds the {_MAX_PAYLOAD_BYTES}-byte verification limit."
        )
    actual_sha256 = _sha256_bytes(content)
    if actual_sha256 != expected_sha256:
        raise QSTSEvidenceError(
            f"Evidence payload digest mismatch for {relative_path!r}: "
            f"expected {expected_sha256}, got {actual_sha256}."
        )
    return (
        VerifiedQSTSPayload(relative_path, actual_sha256, content),
        new_total,
    )


def _require_profile(payload: bytes, field: str) -> tuple[float, ...]:
    raw = _load_json_bytes(payload, field)
    if not _is_mapping(raw):
        raise QSTSEvidenceError(f"{field} must be a JSON object.")
    _require_exact_keys(raw, _PROFILE_KEYS, field)
    if raw.get("schema") != QSTS_PROFILE_SCHEMA or raw.get("unit") != "MW":
        raise QSTSEvidenceError(
            f"{field} must declare schema={QSTS_PROFILE_SCHEMA!r} and unit='MW'."
        )
    values = raw.get("values")
    if not isinstance(values, list) or not values:
        raise QSTSEvidenceError(f"{field}.values must be a non-empty JSON array.")
    converted: list[float] = []
    for index, value in enumerate(values):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or float(value) < 0.0
        ):
            raise QSTSEvidenceError(
                f"{field}.values[{index}] must be a finite MW value >= 0, got {value!r}."
            )
        converted.append(float(value))
    return tuple(converted)


def _resolve_dss_reference(current_path: str, reference: str) -> str:
    cleaned = reference.strip()
    if (
        not cleaned
        or "\\" in cleaned
        or cleaned.startswith(("/", "~"))
        or re.match(r"^[A-Za-z]:", cleaned)
        or any(token in cleaned for token in ("$", "%", "{", "}"))
    ):
        raise QSTSEvidenceError(
            f"DSS payload {current_path!r} contains unsafe or dynamic file reference "
            f"{reference!r}."
        )
    combined = posixpath.normpath(
        posixpath.join(posixpath.dirname(current_path), cleaned)
    )
    if combined == ".." or combined.startswith("../"):
        raise QSTSEvidenceError(
            f"DSS payload {current_path!r} reference {reference!r} escapes the package."
        )
    return _safe_relative_path(combined, f"DSS reference from {current_path!r}")


def _validate_dss_references(
    payloads: tuple[VerifiedQSTSPayload, ...], payload_paths: set[str]
) -> None:
    """Require every static DSS file reference to resolve to a pinned payload."""

    for payload in payloads:
        if not payload.relative_path.lower().endswith(".dss"):
            continue
        try:
            text = payload.content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise QSTSEvidenceError(
                f"DSS payload {payload.relative_path!r} must be UTF-8 text."
            ) from exc
        for raw_line in text.splitlines():
            line = raw_line.split("!", 1)[0]
            redirect = _DSS_REDIRECT_RE.search(line)
            references: list[str] = []
            if redirect is not None:
                references.append(next(group for group in redirect.groups() if group))
            for match in _DSS_FILE_RE.finditer(line):
                references.append(next(group for group in match.groups() if group))
            for reference in references:
                resolved = _resolve_dss_reference(payload.relative_path, reference)
                if resolved not in payload_paths:
                    raise QSTSEvidenceError(
                        f"DSS payload {payload.relative_path!r} references {reference!r} "
                        f"({resolved!r}), which is not pinned in payload_sha256."
                    )


def verify_qsts_evidence_package(
    *,
    manifest_path: str | Path,
    expected_manifest_sha256: str,
    expected_input_kind: str,
    configured_master_path: str | Path,
) -> VerifiedQSTSEvidencePackage:
    """Verify and retain an externally pinned utility/site QSTS evidence package.

    The verifier reads each accepted file exactly once into the returned immutable payload
    tuple. Downstream code must execute those retained bytes from a private snapshot rather
    than reopening the mutable source paths.
    """

    expected_digest = _require_sha256(
        expected_manifest_sha256, "grid.qsts.evidence_manifest_sha256"
    )
    if expected_input_kind not in CANONICAL_FEEDER_INPUT_KINDS:
        raise QSTSEvidenceError(
            "Real/site evidence verification requires input_kind "
            "utility_observed_model or engineer_prepared_site_model, got "
            f"{expected_input_kind!r}."
        )

    manifest = Path(manifest_path)
    if manifest.is_symlink() or not manifest.is_file():
        raise QSTSEvidenceError(
            f"QSTS evidence manifest is missing, not a file, or a symlink: {manifest}."
        )
    manifest_bytes = manifest.read_bytes()
    actual_manifest_sha256 = _sha256_bytes(manifest_bytes)
    if actual_manifest_sha256 != expected_digest:
        raise QSTSEvidenceError(
            "QSTS evidence manifest digest mismatch: expected externally pinned "
            f"{expected_digest}, got {actual_manifest_sha256}. Refusing a resealed or "
            "substituted package."
        )

    raw_manifest = _load_json_bytes(manifest_bytes, "QSTS evidence manifest")
    if not _is_mapping(raw_manifest):
        raise QSTSEvidenceError("QSTS evidence manifest root must be a JSON object.")
    document = raw_manifest
    _require_exact_keys(document, _MANIFEST_KEYS, "QSTS evidence manifest")
    if document.get("schema") != QSTS_EVIDENCE_MANIFEST_SCHEMA:
        raise QSTSEvidenceError(
            "QSTS evidence manifest schema must be "
            f"{QSTS_EVIDENCE_MANIFEST_SCHEMA!r}, got {document.get('schema')!r}."
        )
    package_id = _require_nonempty_string(document.get("package_id"), "package_id")
    if _PACKAGE_ID_RE.fullmatch(package_id) is None:
        raise QSTSEvidenceError(
            "package_id must be 1-128 portable identifier characters "
            "[A-Za-z0-9._:-] and start alphanumeric."
        )
    input_kind = document.get("input_kind")
    if input_kind != expected_input_kind:
        raise QSTSEvidenceError(
            "QSTS evidence input_kind does not match the YAML mode: "
            f"manifest={input_kind!r}, configured={expected_input_kind!r}. Refusing "
            "cross-mode reclassification."
        )

    classification = document.get("classification")
    if not _is_mapping(classification):
        raise QSTSEvidenceError("classification must be a JSON object.")
    _require_exact_keys(classification, _CLASSIFICATION_KEYS, "classification")
    expected_observed = input_kind == "utility_observed_model"
    expected_classification = {
        "generated_input": False,
        "observed_network_data": expected_observed,
        "site_representative": True,
        "bankable": False,
    }
    if dict(classification) != expected_classification:
        raise QSTSEvidenceError(
            "QSTS evidence classification contradicts its input_kind or attempts to "
            f"claim bankability: expected {expected_classification}, got "
            f"{dict(classification)}."
        )

    provenance = document.get("provenance")
    if not _is_mapping(provenance):
        raise QSTSEvidenceError("provenance must be a JSON object.")
    _require_exact_keys(provenance, _PROVENANCE_KEYS, "provenance")
    _require_nonempty_string(provenance.get("source_authority"), "source_authority")
    _require_nonempty_string(provenance.get("source_reference"), "source_reference")
    issued_at = _require_nonempty_string(
        provenance.get("issued_at_utc"), "issued_at_utc"
    )
    try:
        parsed_issued_at = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QSTSEvidenceError(
            "provenance.issued_at_utc must be an RFC-3339 timestamp."
        ) from exc
    if parsed_issued_at.tzinfo is None:
        raise QSTSEvidenceError(
            "provenance.issued_at_utc must include an explicit timezone."
        )

    master_relative_path = _safe_relative_path(
        document.get("feeder_model_path"), "feeder_model_path"
    )
    runtime = document.get("runtime_inputs")
    if not _is_mapping(runtime):
        raise QSTSEvidenceError("runtime_inputs must be a JSON object.")
    _require_exact_keys(runtime, _RUNTIME_KEYS, "runtime_inputs")
    generation_relative_path = _safe_relative_path(
        runtime.get("generation_profile_mw_path"),
        "runtime_inputs.generation_profile_mw_path",
    )
    instructed_relative_path = _safe_relative_path(
        runtime.get("grid_instructed_profile_mw_path"),
        "runtime_inputs.grid_instructed_profile_mw_path",
    )
    export_cap_mw = _require_positive(
        runtime.get("export_cap_mw"), "runtime_inputs.export_cap_mw"
    )
    timestep_hours = _require_positive(
        runtime.get("timestep_hours"), "runtime_inputs.timestep_hours"
    )

    raw_payload_sha256 = document.get("payload_sha256")
    if not _is_mapping(raw_payload_sha256) or not raw_payload_sha256:
        raise QSTSEvidenceError("payload_sha256 must be a non-empty JSON object.")
    if len(raw_payload_sha256) > _MAX_PAYLOAD_COUNT:
        raise QSTSEvidenceError(
            f"payload_sha256 exceeds the {_MAX_PAYLOAD_COUNT}-file verification limit."
        )
    payload_sha256: dict[str, str] = {}
    for raw_path, raw_digest in raw_payload_sha256.items():
        relative_path = _safe_relative_path(raw_path, "payload_sha256 path")
        if relative_path in payload_sha256:
            raise QSTSEvidenceError(
                f"payload_sha256 repeats normalized path {relative_path!r}."
            )
        payload_sha256[relative_path] = _require_sha256(
            raw_digest, f"payload_sha256[{relative_path!r}]"
        )

    for required_path in (
        master_relative_path,
        generation_relative_path,
        instructed_relative_path,
    ):
        if required_path not in payload_sha256:
            raise QSTSEvidenceError(
                f"Required QSTS runtime payload {required_path!r} is not pinned in "
                "payload_sha256."
            )

    root = manifest.parent.resolve()
    configured_master = Path(configured_master_path)
    configured_master_absolute = (
        configured_master
        if configured_master.is_absolute()
        else (Path.cwd() / configured_master)
    ).absolute()
    _reject_symlink_path(
        configured_master_absolute,
        root,
        "grid.qsts.feeder_model_path",
    )
    expected_master = root.joinpath(*PurePosixPath(master_relative_path).parts)
    if configured_master_absolute.resolve(strict=False) != expected_master.resolve(
        strict=False
    ):
        raise QSTSEvidenceError(
            "grid.qsts.feeder_model_path does not match the externally pinned evidence "
            f"manifest: configured={configured_master}, expected={expected_master}."
        )

    accepted_payloads: list[VerifiedQSTSPayload] = []
    total_bytes = 0
    for relative_path in sorted(payload_sha256):
        accepted, total_bytes = _read_bound_payload(
            root=root,
            relative_path=relative_path,
            expected_sha256=payload_sha256[relative_path],
            total_bytes=total_bytes,
        )
        accepted_payloads.append(accepted)
    payloads = tuple(accepted_payloads)
    by_path = {payload.relative_path: payload for payload in payloads}
    _validate_dss_references(payloads, set(by_path))

    generation_profile_mw = _require_profile(
        by_path[generation_relative_path].content,
        f"payload {generation_relative_path!r}",
    )
    grid_instructed_profile_mw = _require_profile(
        by_path[instructed_relative_path].content,
        f"payload {instructed_relative_path!r}",
    )
    if len(grid_instructed_profile_mw) != len(generation_profile_mw):
        raise QSTSEvidenceError(
            "The manifest-bound grid instruction schedule must have the same number of "
            "timesteps as the generation profile: "
            f"{len(grid_instructed_profile_mw)} != {len(generation_profile_mw)}."
        )

    return VerifiedQSTSEvidencePackage(
        package_id=package_id,
        input_kind=expected_input_kind,
        manifest_sha256=actual_manifest_sha256,
        source_root=root,
        master_relative_path=master_relative_path,
        generation_profile_mw=generation_profile_mw,
        grid_instructed_profile_mw=grid_instructed_profile_mw,
        export_cap_mw=export_cap_mw,
        timestep_hours=timestep_hours,
        payloads=payloads,
        observed_network_data=expected_observed,
        site_representative=True,
    )


__all__ = [
    "QSTS_EVIDENCE_MANIFEST_SCHEMA",
    "QSTS_PROFILE_SCHEMA",
    "QSTSEvidenceError",
    "VerifiedQSTSPayload",
    "VerifiedQSTSEvidencePackage",
    "verify_qsts_evidence_package",
]
