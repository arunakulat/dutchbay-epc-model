"""Bind exact D3A/D3B/D3C facts into non-authoritative D3C-1b candidates.

The binding is deliberately narrower than report-package assembly.  It performs no
evaluation, finance, filesystem, environment, network, persistence, rendering, or
clock work.  It accepts the original immutable D3B success, proves its complete
content identity, reconciles a fresh D3C-1a projection and one code-selected D3C-0
authority, verifies three supplied in-memory artifact payloads, and only then emits
candidate D2 records.  Completeness, evidence, review, professional acts, grade,
reliance, publication and release remain explicitly unresolved or held.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Final, Literal, Mapping, Self, TypeAlias, cast

from pydantic import Field, Strict, model_validator
from typing_extensions import Annotated

from analytics.contracts_v14 import (
    D3BAuthoredNumericValue,
    D3BExecutionSuccess,
    D3BNumericProjectionReceipt,
)
from analytics.feasibility_result_projection import (
    ResultProjectionError,
    project_d3b_result,
)

from . import assembly_authority
from .assembly_authority import (
    AcceptedAssemblyAuthority,
    AssemblyAuthorityResolution,
    AuthorizedRegistryIds,
    BlockedAssemblyAuthority,
    EvaluationRequestIdentity,
    GovernedByteArtifactBinding,
    GovernedByteArtifactRole,
    GovernedRuntimeReceipt,
    resolve_assembly_authority,
)
from .assessment_scope import EvaluationRequest, resolved_config_sha256
from .project_case import (
    AssumptionReference,
    CurrencyConversion,
    GenerationAsset,
    ProjectCase,
    ResolvedCount,
    ResolvedValue,
    SourceReference,
    UnitizedGenerationCapacity,
    ValueBinding,
)
from .records import (
    ActorRecord,
    ArtifactRecord,
    CanonicalValue,
    Digest,
    DistributionControl,
    InputRecord,
    OutputReference,
    PackBinding,
    ReportIdentity,
    SourceRecord,
)
from .result_facade import (
    D3C_RESULT_FIELD_ROUTES,
    D3C_SECTION_IDS,
    CarriedResultObservation,
    D3CResultProjection,
    ResultScalarKind,
)
from .vocabulary import (
    InputKind,
    InputResolutionStatus,
    OutputClass,
    StrictFrozenModel,
    ValueType,
)

D3C_CONTEXT_BINDING_SCHEMA_ID: Literal["dutchbay.d3c_context_binding.v1"] = (
    "dutchbay.d3c_context_binding.v1"
)
D3C_CONTEXT_BINDING_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
D3B_SUCCESS_CONTENT_IDENTITY_VERSION: Literal[
    "dutchbay.d3b_execution_success_content_identity.v1"
] = "dutchbay.d3b_execution_success_content_identity.v1"

_MAX_ARTIFACT_BYTES: Final = 16 * 1024 * 1024
_MAX_IDENTITY_DEPTH: Final = 132
_MAX_IDENTITY_CONTAINERS: Final = 25_000
_MAX_IDENTITY_SCALARS: Final = 250_000
_MAX_IDENTITY_TEXT_CODEPOINTS: Final = 3_000_000
_MAX_IDENTITY_CANONICAL_BYTES: Final = 64 * 1024 * 1024
_MAX_ERROR_TEXT: Final = 1_024
_STABLE_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")

ExactStableId: TypeAlias = Annotated[
    str,
    Strict(),
    Field(min_length=1, max_length=160, pattern=_STABLE_ID_RE.pattern),
]
ExactSha256: TypeAlias = Annotated[
    str,
    Strict(),
    Field(min_length=64, max_length=64, pattern=_SHA256_RE.pattern),
]


class D3CContextBindingError(ValueError):
    """Bounded deterministic fail-closed D3C-1b error."""

    def __init__(self, code: str, pointer: str, detail: str) -> None:
        if (
            type(code) is not str
            or not code
            or len(code) > 80
            or re.fullmatch(r"[a-z][a-z0-9_]*", code) is None
        ):
            raise ValueError("D3C-1b error code is invalid")
        if type(pointer) is not str or not pointer or len(pointer) > 512:
            raise ValueError("D3C-1b error pointer is invalid")
        if type(detail) is not str or not detail or len(detail) > _MAX_ERROR_TEXT:
            raise ValueError("D3C-1b error detail is invalid")
        self.code = code
        self.pointer = pointer
        self.detail = detail
        super().__init__(f"{code} at {pointer}: {detail}")


class D3CContextBindingBlockCode(str, Enum):
    """Closed reasons that prevent selection of a D3C-0 authority."""

    INVALID_AUTHORITY_ID = "invalid_authority_id"
    AUTHORITY_NOT_FOUND = "authority_not_found"
    SELECTED_AUTHORITY_INVALID = "selected_authority_invalid"


class _StrictJsonIngressModel(StrictFrozenModel):
    """Root model that rejects duplicate JSON object keys before Pydantic parsing."""

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        **kwargs: Any,
    ) -> Self:
        _scan_json_ingress(json_data)
        return super().model_validate_json(json_data, **kwargs)

    def canonical_json_bytes(self) -> bytes:
        """Return one stable JSON representation for equality and receipt checks."""

        try:
            rendered = json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        except (TypeError, ValueError) as exc:  # pragma: no cover - model invariant
            raise D3CContextBindingError(
                "canonical_json_failure",
                "/",
                "validated D3C-1b candidate could not be rendered canonically",
            ) from exc
        return rendered.encode("utf-8")


def _scan_json_ingress(json_data: str | bytes | bytearray) -> None:
    """Reject duplicate keys, non-finite constants and invalid Unicode scalars."""

    if type(json_data) is str:
        text = json_data
    elif type(json_data) is bytes:
        try:
            text = json_data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise D3CContextBindingError(
                "invalid_json_encoding", "/", "JSON ingress must be exact UTF-8"
            ) from exc
    elif type(json_data) is bytearray:
        try:
            text = bytes(json_data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise D3CContextBindingError(
                "invalid_json_encoding", "/", "JSON ingress must be exact UTF-8"
            ) from exc
    else:
        raise D3CContextBindingError(
            "invalid_json_type", "/", "JSON ingress must be str, bytes or bytearray"
        )

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise D3CContextBindingError(
                    "duplicate_json_key",
                    "/",
                    f"duplicate JSON object key {key!r} is forbidden",
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise D3CContextBindingError(
            "non_finite_json_number",
            "/",
            f"non-finite JSON token {value!r} is forbidden",
        )

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=pairs_hook,
            parse_constant=reject_constant,
        )
    except D3CContextBindingError:
        raise
    except (RecursionError, json.JSONDecodeError) as exc:
        raise D3CContextBindingError(
            "invalid_json", "/", "JSON ingress is malformed or exceeds parser depth"
        ) from exc
    _reject_surrogates(parsed)


def _reject_surrogates(value: Any) -> None:
    """Iteratively enforce Unicode, depth and occurrence bounds on parsed JSON."""

    stack: list[tuple[Any, int]] = [(value, 0)]
    containers = 0
    scalars = 0
    text_codepoints = 0
    while stack:
        item, depth = stack.pop()
        if depth > _MAX_IDENTITY_DEPTH:
            raise D3CContextBindingError(
                "json_ingress_depth_exceeded",
                "/",
                "JSON ingress exceeds the bounded maximum depth",
            )
        if type(item) is str:
            scalars += 1
            text_codepoints += len(item)
            if any(0xD800 <= ord(character) <= 0xDFFF for character in item):
                raise D3CContextBindingError(
                    "invalid_unicode_scalar",
                    "/",
                    "JSON strings must contain Unicode scalar values",
                )
        elif type(item) is list:
            containers += 1
            stack.extend((child, depth + 1) for child in reversed(item))
        elif type(item) is dict:
            containers += 1
            for key, child in reversed(tuple(item.items())):
                stack.append((child, depth + 1))
                stack.append((key, depth + 1))
        elif item is None or type(item) in {bool, int, float}:
            scalars += 1
        else:  # pragma: no cover - stdlib JSON parser has a closed result domain
            raise D3CContextBindingError(
                "invalid_json_value_type",
                "/",
                "JSON ingress contains a value outside the JSON data model",
            )
        if (
            containers > _MAX_IDENTITY_CONTAINERS
            or scalars > _MAX_IDENTITY_SCALARS
            or text_codepoints > _MAX_IDENTITY_TEXT_CODEPOINTS
        ):
            raise D3CContextBindingError(
                "json_ingress_out_of_bounds",
                "/",
                "JSON ingress exceeds bounded volume",
            )


@dataclass(frozen=True, slots=True)
class GovernedArtifactPayload:
    """One bounded exact in-memory payload selected by governed artifact role."""

    role: GovernedByteArtifactRole
    content: bytes

    def __post_init__(self) -> None:
        if type(self.role) is not GovernedByteArtifactRole:
            raise D3CContextBindingError(
                "invalid_artifact_role",
                "/artifact_payloads",
                "artifact role must be the exact governed role enum",
            )
        if type(self.content) is not bytes:
            raise D3CContextBindingError(
                "invalid_artifact_payload",
                f"/artifact_payloads/{self.role.value}",
                "artifact payload must be exact immutable bytes",
            )
        if not 1 <= len(self.content) <= _MAX_ARTIFACT_BYTES:
            raise D3CContextBindingError(
                "artifact_payload_out_of_bounds",
                f"/artifact_payloads/{self.role.value}",
                f"artifact payload must contain 1..{_MAX_ARTIFACT_BYTES} bytes",
            )


class VerifiedArtifactPayload(_StrictJsonIngressModel):
    """Receipt proving actual supplied bytes matched both D3C-0 artifact graphs."""

    role: GovernedByteArtifactRole
    artifact_id: ExactStableId
    byte_length: Annotated[int, Strict(), Field(gt=0, le=_MAX_ARTIFACT_BYTES)]
    content_digest: Digest


class CandidateInputOrigin(_StrictJsonIngressModel):
    """Exact D3A source or assumption edge retained beside a D2 input candidate."""

    input_id: ExactStableId
    kind: Literal["source", "assumption"]
    reference_id: ExactStableId


class D3CSectionCandidate(_StrictJsonIngressModel):
    """One taxonomy-ordered candidate, never a completed D2 SectionRecord."""

    section_id: ExactStableId
    candidate_input_ids: tuple[ExactStableId, ...]
    candidate_output_ids: tuple[ExactStableId, ...]
    candidate_artifact_ids: tuple[ExactStableId, ...]
    unresolved_dependency_ids: tuple[ExactStableId, ...]
    completeness_status: Literal["unresolved"]
    evidence_status: Literal["unresolved"]
    review_status: Literal["not_performed"]
    professional_act_status: Literal["not_performed"]
    achieved_grade: Literal["ungraded"]
    release_status: Literal["hold"]

    @model_validator(mode="after")
    def _references_are_unique(self) -> D3CSectionCandidate:
        for field_name in (
            "candidate_input_ids",
            "candidate_output_ids",
            "candidate_artifact_ids",
            "unresolved_dependency_ids",
        ):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate identities")
        return self


class BlockedD3CContextBinding(_StrictJsonIngressModel):
    """Serializable production-safe refusal before any candidate is emitted."""

    outcome: Literal["blocked"]
    schema_id: Literal["dutchbay.d3c_context_binding.v1"]
    contract_version: Literal["1.0.0"]
    code: D3CContextBindingBlockCode
    pointer: Literal["/authority_id"]
    authority_id: str
    detail: Annotated[str, Strict(), Field(min_length=1, max_length=_MAX_ERROR_TEXT)]
    candidate_emitted: Literal[False]


class D3CContextBindingCandidate(_StrictJsonIngressModel):
    """Exact non-authoritative D3C-1b candidate record graph."""

    outcome: Literal["candidate"]
    schema_id: Literal["dutchbay.d3c_context_binding.v1"]
    contract_version: Literal["1.0.0"]
    authority_status: Literal["candidate_non_authoritative"]
    authority_id: ExactStableId
    report_identity: ReportIdentity
    evaluation_request_identity: EvaluationRequestIdentity
    project_case_content_digest: Digest
    evaluation_request_content_digest: Digest
    d3b_execution_success_content_digest: Digest
    runtime_receipt: GovernedRuntimeReceipt
    projection: D3CResultProjection
    actor_records: tuple[ActorRecord, ...]
    source_records: tuple[SourceRecord, ...]
    pack_bindings: tuple[PackBinding, ...]
    jurisdiction_pack_ids: tuple[ExactStableId, ...]
    technology_pack_ids: tuple[ExactStableId, ...]
    authorized_registry_ids: AuthorizedRegistryIds
    input_records: tuple[InputRecord, ...]
    input_origins: tuple[CandidateInputOrigin, ...]
    output_references: tuple[OutputReference, ...]
    artifact_records: Annotated[
        tuple[ArtifactRecord, ...], Field(min_length=3, max_length=3)
    ]
    byte_artifact_bindings: Annotated[
        tuple[GovernedByteArtifactBinding, ...], Field(min_length=3, max_length=3)
    ]
    verified_artifact_payloads: Annotated[
        tuple[VerifiedArtifactPayload, ...], Field(min_length=3, max_length=3)
    ]
    distribution_control: DistributionControl
    sections: Annotated[
        tuple[D3CSectionCandidate, ...], Field(min_length=20, max_length=20)
    ]
    completeness_status: Literal["unresolved"]
    evidence_status: Literal["unresolved"]
    review_status: Literal["not_performed"]
    professional_act_status: Literal["not_performed"]
    achieved_grade: Literal["ungraded"]
    release_status: Literal["hold"]
    reliance_status: Literal["not_permitted"]
    publication_status: Literal["not_authorized"]

    @model_validator(mode="after")
    def _candidate_graph_is_exact(self) -> D3CContextBindingCandidate:
        report = self.report_identity
        request = self.evaluation_request_identity
        projection = self.projection
        if self.authority_id == report.report_id or self.authority_id == report.run_id:
            raise ValueError("authority identity cannot alias report or run identity")
        if (report.project_id, report.case_id) != (
            projection.project_id,
            projection.case_id,
        ):
            raise ValueError("candidate report identity differs from its projection")
        if (
            request.request_id != projection.request_id
            or request.project_id != projection.project_id
            or request.case_id != projection.case_id
            or request.project_case_revision != projection.project_case_revision
        ):
            raise ValueError("candidate request identity differs from its projection")
        if (
            self.project_case_content_digest.value != projection.project_case_sha256
            or self.evaluation_request_content_digest.value
            != projection.evaluation_request_sha256
        ):
            raise ValueError("candidate content digests differ from the projection")
        generated_at = datetime.fromisoformat(
            projection.engine_manifest.generated_at.replace("Z", "+00:00")
        )
        if (
            self.runtime_receipt.engine_version
            != projection.engine_manifest.engine_version
            or self.runtime_receipt.code_commit != projection.engine_manifest.git_sha
            or self.runtime_receipt.engine_run_created_at != generated_at
        ):
            raise ValueError(
                "candidate runtime receipt differs from the engine manifest"
            )

        for records, field_name in (
            (self.actor_records, "actor_id"),
            (self.source_records, "source_id"),
            (self.pack_bindings, "pack_id"),
            (self.input_records, "input_id"),
            (self.output_references, "output_id"),
            (self.artifact_records, "artifact_id"),
        ):
            identities = tuple(getattr(record, field_name) for record in records)
            if len(identities) != len(set(identities)):
                raise ValueError(f"candidate contains duplicate {field_name} values")

        artifact_ids = {record.artifact_id for record in self.artifact_records}
        binding_ids = {record.artifact_id for record in self.byte_artifact_bindings}
        verified_ids = {
            record.artifact_id for record in self.verified_artifact_payloads
        }
        if artifact_ids != binding_ids or artifact_ids != verified_ids:
            raise ValueError("candidate artifact identities are not reciprocal")
        artifact_by_id = {
            record.artifact_id: record for record in self.artifact_records
        }
        binding_by_id = {
            record.artifact_id: record for record in self.byte_artifact_bindings
        }
        for verified in self.verified_artifact_payloads:
            artifact = artifact_by_id[verified.artifact_id]
            binding = binding_by_id[verified.artifact_id]
            if (
                verified.role is not binding.role
                or verified.byte_length != binding.byte_length
                or verified.content_digest != binding.content_digest
                or verified.content_digest != artifact.content_digest
            ):
                raise ValueError("candidate artifact byte receipt is not reciprocal")

        input_ids = {record.input_id for record in self.input_records}
        output_ids = {record.output_id for record in self.output_references}
        source_ids = {record.source_id for record in self.source_records}
        if any(
            not set(record.source_ids) <= source_ids for record in self.input_records
        ):
            raise ValueError("candidate input contains a dangling source reference")
        if any(origin.input_id not in input_ids for origin in self.input_origins):
            raise ValueError("candidate input origin is dangling")
        origin_keys = tuple(
            (origin.input_id, origin.kind, origin.reference_id)
            for origin in self.input_origins
        )
        if len(origin_keys) != len(set(origin_keys)):
            raise ValueError("candidate contains duplicate input origins")
        if any(
            output.report_id != report.report_id or output.run_id != report.run_id
            for output in self.output_references
        ):
            raise ValueError("candidate output has foreign report/run identity")

        if tuple(section.section_id for section in self.sections) != D3C_SECTION_IDS:
            raise ValueError("candidate sections differ from taxonomy SSOT order")
        for section in self.sections:
            if (
                not set(section.candidate_input_ids) <= input_ids
                or not set(section.candidate_output_ids) <= output_ids
                or not set(section.candidate_artifact_ids) <= artifact_ids
            ):
                raise ValueError("candidate section contains a dangling reference")
        return self


D3CContextBindingOutcome: TypeAlias = (
    D3CContextBindingCandidate | BlockedD3CContextBinding
)


@dataclass(slots=True)
class _IdentityBounds:
    containers: int = 0
    scalars: int = 0
    text_codepoints: int = 0


def _bounded_text_node(value: str, bounds: _IdentityBounds) -> list[str]:
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise D3CContextBindingError(
            "invalid_success_unicode",
            "/d3b_execution_success",
            "accepted success contains a Unicode surrogate",
        )
    bounds.scalars += 1
    bounds.text_codepoints += len(value)
    _check_identity_bounds(bounds)
    return ["text", value]


def _check_identity_bounds(bounds: _IdentityBounds) -> None:
    if (
        bounds.containers > _MAX_IDENTITY_CONTAINERS
        or bounds.scalars > _MAX_IDENTITY_SCALARS
        or bounds.text_codepoints > _MAX_IDENTITY_TEXT_CODEPOINTS
    ):
        raise D3CContextBindingError(
            "success_identity_out_of_bounds",
            "/d3b_execution_success",
            "accepted-success content identity exceeds bounded volume",
        )


def _identity_node(
    value: Any,
    *,
    bounds: _IdentityBounds,
    active: set[int],
    depth: int,
) -> Any:
    """Encode an exact, type-tagged, alias-occurrence-expanded content node."""

    if depth > _MAX_IDENTITY_DEPTH:
        raise D3CContextBindingError(
            "success_identity_depth_exceeded",
            "/d3b_execution_success",
            "accepted-success content identity exceeds maximum depth",
        )
    if value is None:
        bounds.scalars += 1
        _check_identity_bounds(bounds)
        return ["none"]
    if type(value) is bool:
        bounds.scalars += 1
        _check_identity_bounds(bounds)
        return ["bool", value]
    if type(value) is int:
        if value.bit_length() > 4096:
            raise D3CContextBindingError(
                "success_identity_integer_out_of_bounds",
                "/d3b_execution_success",
                "accepted-success integer exceeds 4096 bits",
            )
        bounds.scalars += 1
        _check_identity_bounds(bounds)
        return ["integer", str(value)]
    if type(value) is float:
        if not math.isfinite(value):
            raise D3CContextBindingError(
                "success_identity_non_finite",
                "/d3b_execution_success",
                "accepted-success binary64 value must be finite",
            )
        bounds.scalars += 1
        _check_identity_bounds(bounds)
        return ["binary64", struct.pack(">d", value).hex()]
    if type(value) is str:
        return _bounded_text_node(value, bounds)
    if type(value) is date:
        bounds.scalars += 1
        _check_identity_bounds(bounds)
        return ["date", value.isoformat()]
    if type(value) is MappingProxyType:
        marker = id(value)
        if marker in active:
            raise D3CContextBindingError(
                "success_identity_cycle",
                "/d3b_execution_success",
                "accepted-success mapping cycle is forbidden",
            )
        bounds.containers += 1
        _check_identity_bounds(bounds)
        active.add(marker)
        try:
            entries: list[tuple[bytes, Any, Any]] = []
            for key, item in value.items():
                if type(key) not in {str, int, float}:
                    raise D3CContextBindingError(
                        "success_identity_key_type",
                        "/d3b_execution_success",
                        "accepted-success mapping key type is unsupported",
                    )
                key_node = _identity_node(
                    key,
                    bounds=bounds,
                    active=active,
                    depth=depth + 1,
                )
                key_bytes = json.dumps(
                    key_node,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                item_node = _identity_node(
                    item,
                    bounds=bounds,
                    active=active,
                    depth=depth + 1,
                )
                entries.append((key_bytes, key_node, item_node))
        finally:
            active.remove(marker)
        entries.sort(key=lambda entry: entry[0])
        if any(
            left[0] == right[0]
            for left, right in zip(entries, entries[1:], strict=False)
        ):  # pragma: no cover - exact key types make this unreachable
            raise D3CContextBindingError(
                "success_identity_key_collision",
                "/d3b_execution_success",
                "accepted-success mapping keys collide canonically",
            )
        return ["mapping", [[key, item] for _, key, item in entries]]
    if type(value) is tuple:
        marker = id(value)
        if marker in active:
            raise D3CContextBindingError(
                "success_identity_cycle",
                "/d3b_execution_success",
                "accepted-success tuple cycle is forbidden",
            )
        bounds.containers += 1
        _check_identity_bounds(bounds)
        active.add(marker)
        try:
            items = [
                _identity_node(
                    item,
                    bounds=bounds,
                    active=active,
                    depth=depth + 1,
                )
                for item in value
            ]
        finally:
            active.remove(marker)
        return ["tuple", items]
    if type(value) is D3BAuthoredNumericValue:
        return [
            "d3b_authored_numeric_value",
            _identity_node(
                value.json_type,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
            _identity_node(
                value.authored_value,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
            _identity_node(
                value.binary64_hex,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
        ]
    if type(value) is D3BNumericProjectionReceipt:
        return [
            "d3b_numeric_projection_receipt",
            _identity_node(
                value.assertion_id,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
            _identity_node(
                value.project_decimal,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
            _identity_node(
                value.projected_binary64_hex,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
            _identity_node(
                value.authored_values,
                bounds=bounds,
                active=active,
                depth=depth + 1,
            ),
        ]
    raise D3CContextBindingError(
        "success_identity_type",
        "/d3b_execution_success",
        f"accepted-success value type {type(value).__name__!r} is unsupported",
    )


def d3b_execution_success_content_digest(result: D3BExecutionSuccess) -> Digest:
    """Return the bounded deterministic content identity of one exact D3B success.

    Mapping order and safe alias topology are intentionally not identities.  Mapping
    entries are sorted by exact type-tagged key bytes, and shared aliases are expanded
    and counted on every occurrence.  Every public field of ``D3BExecutionSuccess`` is
    included, including opaque full-result metadata, annual-row values and the run
    manifest.  This is solely the D3C ledger's upstream-object identity; it is not D4
    package serialization.
    """

    if type(result) is not D3BExecutionSuccess:
        raise D3CContextBindingError(
            "invalid_success_type",
            "/d3b_execution_success",
            "content identity accepts exactly D3BExecutionSuccess",
        )
    bounds = _IdentityBounds()
    active: set[int] = set()
    fields = (
        ("request_id", result.request_id),
        ("project_id", result.project_id),
        ("case_id", result.case_id),
        ("project_case_revision", result.project_case_revision),
        ("project_case_sha256", result.project_case_sha256),
        ("evaluation_request_sha256", result.evaluation_request_sha256),
        ("authority_id", result.authority_id),
        ("config_id", result.config_id),
        ("source_file_sha256", result.source_file_sha256),
        ("resolved_config_sha256", result.resolved_config_sha256),
        ("evaluated_config_sha256", result.evaluated_config_sha256),
        ("evidence_cutoff", result.evidence_cutoff),
        ("valuation_date", result.valuation_date),
        ("validation_modules", result.validation_modules),
        ("numeric_projection_receipts", result.numeric_projection_receipts),
        ("gateway_call_count", result.gateway_call_count),
        ("full_result", result.full_result),
        ("run_manifest", result.run_manifest),
        ("warnings", result.warnings),
        ("fx_degraded", result.fx_degraded),
        ("outcome", result.outcome),
    )
    root = [
        D3B_SUCCESS_CONTENT_IDENTITY_VERSION,
        [
            [
                name,
                _identity_node(
                    value,
                    bounds=bounds,
                    active=active,
                    depth=0,
                ),
            ]
            for name, value in fields
        ],
    ]
    canonical = json.dumps(
        root,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(canonical) > _MAX_IDENTITY_CANONICAL_BYTES:
        raise D3CContextBindingError(
            "success_identity_bytes_exceeded",
            "/d3b_execution_success",
            "accepted-success canonical content exceeds the byte bound",
        )
    return Digest(value=hashlib.sha256(canonical).hexdigest())


def _blocked_from_authority(
    authority_id: object,
    resolution: BlockedAssemblyAuthority,
) -> BlockedD3CContextBinding:
    code = {
        "invalid_authority_id": D3CContextBindingBlockCode.INVALID_AUTHORITY_ID,
        "authority_not_found": D3CContextBindingBlockCode.AUTHORITY_NOT_FOUND,
    }.get(
        resolution.code.value,
        D3CContextBindingBlockCode.SELECTED_AUTHORITY_INVALID,
    )
    rendered_id = authority_id if type(authority_id) is str else repr(authority_id)
    return BlockedD3CContextBinding(
        outcome="blocked",
        schema_id=D3C_CONTEXT_BINDING_SCHEMA_ID,
        contract_version=D3C_CONTEXT_BINDING_CONTRACT_VERSION,
        code=code,
        pointer="/authority_id",
        authority_id=rendered_id[:160],
        detail=(
            "No code-owned accepted D3C-0 authority was selected; no D3C-1b "
            "candidate was emitted."
        ),
        candidate_emitted=False,
    )


def _require(condition: bool, code: str, pointer: str, detail: str) -> None:
    if not condition:
        raise D3CContextBindingError(code, pointer, detail)


def _ordered_scope_jurisdictions(request: EvaluationRequest) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            item.jurisdiction_code for item in request.scope.jurisdiction_scope
        )
    )


def _ordered_scope_technologies(request: EvaluationRequest) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(item.technology_id for item in request.scope.technology_scope)
    )


def _reconcile_identity_graph(
    project_case: ProjectCase,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    projection: D3CResultProjection,
    authority: AcceptedAssemblyAuthority,
) -> tuple[Digest, Digest, Digest]:
    project_digest = Digest(
        value=resolved_config_sha256(project_case.model_dump(mode="json"))
    )
    request_digest = Digest(
        value=resolved_config_sha256(request.model_dump(mode="json"))
    )
    success_digest = d3b_execution_success_content_digest(success)

    case_ref = request.project_case
    _require(
        (
            project_case.identity.project_id,
            project_case.identity.case_id,
            project_case.identity.revision,
        )
        == (case_ref.project_id, case_ref.case_id, case_ref.revision),
        "project_request_identity_mismatch",
        "/evaluation_request/project_case",
        "EvaluationRequest does not reference the exact ProjectCase identity",
    )
    _require(
        (
            success.project_id,
            success.case_id,
            success.project_case_revision,
            success.request_id,
        )
        == (
            case_ref.project_id,
            case_ref.case_id,
            case_ref.revision,
            request.request_id,
        ),
        "success_request_identity_mismatch",
        "/d3b_execution_success",
        "D3B success does not reciprocally identify the exact request and case",
    )
    _require(
        success.project_case_sha256 == project_digest.value
        and success.evaluation_request_sha256 == request_digest.value,
        "success_embedded_digest_mismatch",
        "/d3b_execution_success",
        "D3B success embedded ProjectCase/request digests differ from recomputation",
    )
    upstream = authority.upstream_digests
    _require(
        upstream.project_case == project_digest
        and upstream.evaluation_request == request_digest
        and upstream.d3b_execution_success == success_digest,
        "authority_upstream_digest_mismatch",
        "/authority/upstream_digests",
        "D3C-0 authority does not bind the exact three upstream contents",
    )

    authority_request = authority.evaluation_request_identity
    expected_request_identity = (
        request.request_id,
        case_ref.project_id,
        case_ref.case_id,
        case_ref.revision,
        success.authority_id,
        request.base_scenario.config_id,
        request.scope.scope_id,
        request.scope.project_boundary,
        _ordered_scope_jurisdictions(request),
        _ordered_scope_technologies(request),
        request.scope.project_stage,
        request.scope.intended_audiences,
        request.scope.intended_uses,
        request.scope.evidence_cutoff,
        request.scope.valuation_date,
    )
    actual_request_identity = (
        authority_request.request_id,
        authority_request.project_id,
        authority_request.case_id,
        authority_request.project_case_revision,
        authority_request.d3b_scenario_authority_id,
        authority_request.config_id,
        authority_request.scope_id,
        authority_request.project_boundary,
        authority_request.jurisdiction_codes,
        authority_request.technology_ids,
        authority_request.project_stage,
        authority_request.intended_audiences,
        authority_request.intended_uses,
        authority_request.evidence_cutoff,
        authority_request.valuation_date,
    )
    _require(
        actual_request_identity == expected_request_identity,
        "authority_request_identity_mismatch",
        "/authority/evaluation_request_identity",
        "D3C-0 request identity differs from the exact EvaluationRequest",
    )
    _require(
        (
            success.authority_id,
            success.config_id,
            success.source_file_sha256,
            success.resolved_config_sha256,
            success.evidence_cutoff,
            success.valuation_date,
            success.validation_modules,
        )
        == (
            authority_request.d3b_scenario_authority_id,
            request.base_scenario.config_id,
            request.base_scenario.source_file_sha256,
            request.base_scenario.resolved_config_sha256,
            request.scope.evidence_cutoff,
            request.scope.valuation_date,
            tuple(module.value for module in request.validation_modules),
        ),
        "success_origin_mismatch",
        "/d3b_execution_success",
        "D3B success origin fields differ from request and authority facts",
    )

    report = authority.report_identity
    _require(
        (report.project_id, report.case_id)
        == (project_case.identity.project_id, project_case.identity.case_id),
        "report_case_identity_mismatch",
        "/authority/report_identity",
        "D3C-0 report identity differs from the exact ProjectCase",
    )
    manifest = projection.engine_manifest
    generated_at = datetime.fromisoformat(manifest.generated_at.replace("Z", "+00:00"))
    runtime = authority.runtime_receipt
    _require(
        runtime.engine_version == manifest.engine_version
        and runtime.code_commit == manifest.git_sha
        and runtime.engine_run_created_at == generated_at,
        "runtime_manifest_mismatch",
        "/authority/runtime_receipt",
        "D3C-0 runtime receipt differs from the exact engine manifest",
    )
    return project_digest, request_digest, success_digest


def _verify_artifact_payloads(
    payloads: tuple[GovernedArtifactPayload, ...],
    authority: AcceptedAssemblyAuthority,
) -> tuple[VerifiedArtifactPayload, ...]:
    _require(
        type(payloads) is tuple
        and len(payloads) == 3
        and all(type(item) is GovernedArtifactPayload for item in payloads),
        "invalid_artifact_payload_set",
        "/artifact_payloads",
        "exactly three immutable governed artifact payloads are required",
    )
    roles = tuple(payload.role for payload in payloads)
    _require(
        len(set(roles)) == 3 and set(roles) == set(GovernedByteArtifactRole),
        "artifact_role_set_mismatch",
        "/artifact_payloads",
        "artifact payloads must cover every governed role exactly once",
    )
    bindings = {binding.role: binding for binding in authority.byte_artifact_bindings}
    artifacts = {
        artifact.artifact_id: artifact for artifact in authority.artifact_records
    }
    verified: list[VerifiedArtifactPayload] = []
    for role in GovernedByteArtifactRole:
        payload = next(item for item in payloads if item.role is role)
        binding = bindings[role]
        artifact = artifacts[binding.artifact_id]
        digest = Digest(value=hashlib.sha256(payload.content).hexdigest())
        _require(
            artifact.report_id == authority.report_identity.report_id
            and artifact.run_id == authority.report_identity.run_id,
            "artifact_report_run_mismatch",
            f"/authority/artifact_records/{artifact.artifact_id}",
            "D2 artifact does not reciprocally identify the selected report and run",
        )
        _require(
            len(payload.content) == binding.byte_length,
            "artifact_byte_length_mismatch",
            f"/artifact_payloads/{role.value}",
            "supplied bytes differ from the governed byte length",
        )
        _require(
            digest == binding.content_digest == artifact.content_digest,
            "artifact_digest_mismatch",
            f"/artifact_payloads/{role.value}",
            "supplied bytes differ from D3C-0 and D2 artifact digests",
        )
        _require(
            (
                binding.format,
                binding.mime_type,
                binding.producer,
                binding.producer_version,
                binding.created_at,
                binding.source_ids,
                binding.confidentiality,
            )
            == (
                artifact.format,
                artifact.mime_type,
                artifact.producer,
                artifact.producer_version,
                artifact.created_at,
                artifact.source_ids,
                artifact.confidentiality,
            ),
            "artifact_metadata_mismatch",
            f"/authority/byte_artifact_bindings/{role.value}",
            "D3C-0 byte binding differs from its exact D2 artifact record",
        )
        verified.append(
            VerifiedArtifactPayload(
                role=role,
                artifact_id=binding.artifact_id,
                byte_length=len(payload.content),
                content_digest=digest,
            )
        )
    return tuple(verified)


def _canonical_decimal(value: ResolvedValue, precision: int) -> CanonicalValue:
    return CanonicalValue(
        value_type=ValueType.DECIMAL,
        value=format(value.value, "f"),
        unit=value.unit,
        precision=precision,
    )


def _origin_edges(
    input_id: str,
    bindings: tuple[ValueBinding, ...],
    *,
    case_source_ids: set[str],
    case_assumption_ids: set[str],
    authority_source_ids: set[str],
) -> tuple[tuple[str, ...], tuple[CandidateInputOrigin, ...]]:
    source_ids: list[str] = []
    origins: list[CandidateInputOrigin] = []
    for binding in bindings:
        if type(binding) is SourceReference:
            _require(
                binding.reference_id in case_source_ids
                and binding.reference_id in authority_source_ids,
                "input_source_not_authorized",
                f"/project_case/{input_id}",
                "candidate input source is absent from ProjectCase or D3C-0 sources",
            )
            source_ids.append(binding.reference_id)
            kind: Literal["source", "assumption"] = "source"
        elif type(binding) is AssumptionReference:
            _require(
                binding.reference_id in case_assumption_ids,
                "input_assumption_not_found",
                f"/project_case/{input_id}",
                "candidate input assumption is absent from ProjectCase assumptions",
            )
            kind = "assumption"
        else:  # pragma: no cover - closed ProjectCase union
            raise D3CContextBindingError(
                "input_origin_type",
                f"/project_case/{input_id}",
                "candidate input contains an unsupported origin type",
            )
        origins.append(
            CandidateInputOrigin(
                input_id=input_id,
                kind=kind,
                reference_id=binding.reference_id,
            )
        )
    return tuple(source_ids), tuple(origins)


def _candidate_inputs(
    project_case: ProjectCase,
    authority: AcceptedAssemblyAuthority,
) -> tuple[tuple[InputRecord, ...], tuple[CandidateInputOrigin, ...]]:
    case_source_ids = {source.source_id for source in project_case.sources}
    case_assumption_ids = {
        assumption.assumption_id for assumption in project_case.assumptions
    }
    authority_source_ids = {source.source_id for source in authority.source_records}
    records: list[InputRecord] = []
    origins: list[CandidateInputOrigin] = []

    def add(
        *,
        input_id: str,
        name: str,
        value: CanonicalValue,
        bindings: tuple[ValueBinding, ...],
        section_ids: tuple[str, ...],
    ) -> None:
        source_ids, input_origins = _origin_edges(
            input_id,
            bindings,
            case_source_ids=case_source_ids,
            case_assumption_ids=case_assumption_ids,
            authority_source_ids=authority_source_ids,
        )
        records.append(
            InputRecord(
                input_id=input_id,
                kind=InputKind.RESOLVED,
                resolution_status=InputResolutionStatus.RESOLVED,
                name=name,
                resolved_value=value,
                source_ids=source_ids,
                affected_section_ids=section_ids,
            )
        )
        origins.extend(input_origins)

    for asset in project_case.assets:
        if (
            type(asset) is GenerationAsset
            and type(asset.capacity) is UnitizedGenerationCapacity
            and type(asset.capacity.unit_count) is ResolvedCount
        ):
            count = asset.capacity.unit_count
            add(
                input_id=f"input:project_case.asset.{asset.asset_id}.unit_count",
                name=f"ProjectCase unit count for {asset.asset_id}",
                value=CanonicalValue(
                    value_type=ValueType.INTEGER,
                    value=str(count.value),
                    unit="count",
                    precision=0,
                ),
                bindings=count.bindings,
                section_ids=(
                    "project_description_and_structure",
                    "technology_selection_design_basis",
                ),
            )

    for line in project_case.costs.lines:
        native = line.amount.native_amount
        if type(native) is ResolvedValue:
            add(
                input_id=f"input:project_case.cost.{line.line_id}.native_amount",
                name=f"ProjectCase native amount for {line.line_id}",
                value=_canonical_decimal(native, line.amount.native_minor_unit_places),
                bindings=native.bindings,
                section_ids=("capex_opex_contingency_procurement",),
            )
        reporting = line.amount.reporting_amount
        if type(reporting) is ResolvedValue:
            add(
                input_id=f"input:project_case.cost.{line.line_id}.reporting_amount",
                name=f"ProjectCase reporting amount for {line.line_id}",
                value=_canonical_decimal(
                    reporting, line.amount.reporting_minor_unit_places
                ),
                bindings=reporting.bindings,
                section_ids=("capex_opex_contingency_procurement",),
            )

    for conversion in project_case.costs.currency_conversions:
        if type(conversion.rate) is ResolvedValue:
            add(
                input_id=(
                    "input:project_case.currency_conversion."
                    f"{conversion.conversion_id}.rate"
                ),
                name=(
                    f"Directed {conversion.from_currency} to "
                    f"{conversion.to_currency} conversion rate"
                ),
                value=_canonical_decimal(conversion.rate, conversion.quote_precision),
                bindings=conversion.rate.bindings,
                section_ids=("tax_fx_inflation_accounting",),
            )
    return tuple(records), tuple(origins)


def _json_pointer(path: tuple[str, ...]) -> str:
    return "/" + "/".join(
        component.replace("~", "~0").replace("/", "~1") for component in path[1:]
    )


def _route_output_id(route_id: str) -> str:
    return "output:" + route_id.removeprefix("route:")


def _carried_route_outputs(
    projection: D3CResultProjection,
    report: ReportIdentity,
) -> list[OutputReference]:
    outputs: list[OutputReference] = []
    for observation in projection.route_observations:
        if type(observation) is not CarriedResultObservation:
            continue
        value_type = (
            ValueType.INTEGER
            if observation.source_scalar_kind is ResultScalarKind.INTEGER
            else ValueType.DECIMAL
        )
        outputs.append(
            OutputReference(
                output_id=_route_output_id(observation.route_id),
                report_id=report.report_id,
                run_id=report.run_id,
                section_ids=observation.section_ids,
                producing_contract=projection.schema_id,
                producing_version=projection.contract_version,
                output_class=OutputClass.CANONICAL,
                locator=_json_pointer(observation.source_path),
                value=CanonicalValue(
                    value_type=value_type,
                    value=observation.value_text,
                    unit=observation.unit,
                    precision=observation.meaningful_precision,
                ),
            )
        )
    return outputs


def _fx_conversion_context(
    project_case: ProjectCase,
    request: EvaluationRequest,
    authority: AcceptedAssemblyAuthority,
) -> CurrencyConversion:
    matches = tuple(
        conversion
        for conversion in project_case.costs.currency_conversions
        if conversion.from_currency == "USD" and conversion.to_currency == "LKR"
    )
    _require(
        len(matches) == 1,
        "fx_directional_conversion_missing",
        "/project_case/costs/currency_conversions",
        "FX result statistics require exactly one directed USD-to-LKR conversion",
    )
    conversion = matches[0]
    _require(
        type(conversion.rate) is ResolvedValue and conversion.rate.unit == "LKR/USD",
        "fx_quote_direction_mismatch",
        f"/project_case/costs/currency_conversions/{conversion.conversion_id}",
        "FX conversion must preserve the exact LKR/USD target/source quote",
    )
    _require(
        conversion.valuation_date == request.scope.valuation_date
        and conversion.price_basis_id == request.scope.price_basis_id,
        "fx_basis_mismatch",
        f"/project_case/costs/currency_conversions/{conversion.conversion_id}",
        "FX conversion date and price basis must match the EvaluationRequest",
    )
    rate = cast(ResolvedValue, conversion.rate)
    _require(
        len(rate.bindings) == 1 and type(rate.bindings[0]) is SourceReference,
        "fx_source_binding_missing",
        f"/project_case/costs/currency_conversions/{conversion.conversion_id}/rate",
        "FX conversion requires one exact governed source reference",
    )
    source_id = cast(SourceReference, rate.bindings[0]).reference_id
    _require(
        source_id in {source.source_id for source in authority.source_records},
        "fx_source_not_authorized",
        f"/project_case/costs/currency_conversions/{conversion.conversion_id}/rate",
        "FX conversion source is absent from the selected D3C-0 authority",
    )
    return conversion


def _contextual_fx_outputs(
    project_case: ProjectCase,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    projection: D3CResultProjection,
    authority: AcceptedAssemblyAuthority,
    report: ReportIdentity,
) -> list[OutputReference]:
    debt = success.full_result.get("debt_result")
    if type(debt) is not MappingProxyType:
        return []
    field_names = ("fx_min", "fx_max", "fx_avg")
    present = tuple(field in debt for field in field_names)
    if not any(present):
        return []
    _require(
        all(present),
        "fx_statistics_incomplete",
        "/d3b_execution_success/full_result/debt_result",
        "FX statistics must be present as the complete min/max/average set",
    )
    _require(
        projection.fx_integration.succeeded
        and not projection.fx_integration.degraded
        and not success.fx_degraded,
        "fx_integration_not_clean",
        "/d3b_execution_success/full_result/fx_integration",
        "FX statistics require a clean successful FX integration receipt",
    )
    annual_rows = success.full_result.get("annual_rows")
    _require(
        type(annual_rows) is tuple
        and bool(annual_rows)
        and all(
            type(row) is MappingProxyType
            and type(row.get("fx_rate")) is float
            and math.isfinite(row["fx_rate"])
            for row in annual_rows
        ),
        "annual_fx_predicate_unmet",
        "/d3b_execution_success/full_result/annual_rows",
        "every annual row must preserve one exact finite binary64 fx_rate",
    )
    _fx_conversion_context(project_case, request, authority)
    route_index = {route.route_id: route for route in D3C_RESULT_FIELD_ROUTES}
    outputs: list[OutputReference] = []
    for field_name in field_names:
        value = debt[field_name]
        _require(
            type(value) is float and math.isfinite(value),
            "fx_statistic_not_binary64",
            f"/d3b_execution_success/full_result/debt_result/{field_name}",
            "FX statistic must be an exact finite binary64 value",
        )
        route = route_index[f"route:debt_result.{field_name}"]
        outputs.append(
            OutputReference(
                output_id=_route_output_id(route.route_id),
                report_id=report.report_id,
                run_id=report.run_id,
                section_ids=route.section_ids,
                producing_contract=D3C_CONTEXT_BINDING_SCHEMA_ID,
                producing_version=D3C_CONTEXT_BINDING_CONTRACT_VERSION,
                output_class=OutputClass.CANONICAL,
                locator=_json_pointer(route.source_path),
                value=CanonicalValue(
                    value_type=ValueType.DECIMAL,
                    value=str(Decimal.from_float(value)),
                    unit=route.unit,
                    precision=route.meaningful_precision,
                ),
            )
        )
    return outputs


_ARTIFACT_SECTION_IDS: Final[Mapping[GovernedByteArtifactRole, tuple[str, ...]]] = (
    MappingProxyType(
        {
            GovernedByteArtifactRole.ANNUAL_ROWS: (
                "capex_opex_contingency_procurement",
                "financing_plan_debt_sizing",
                "tax_fx_inflation_accounting",
                "base_case_financial_outputs",
                "appendices_provenance_audit_trail",
            ),
            GovernedByteArtifactRole.DEBT_RESULT: (
                "financing_plan_debt_sizing",
                "base_case_financial_outputs",
                "appendices_provenance_audit_trail",
            ),
            GovernedByteArtifactRole.FX_CURVE: (
                "tax_fx_inflation_accounting",
                "appendices_provenance_audit_trail",
            ),
        }
    )
)


def _artifact_outputs(
    authority: AcceptedAssemblyAuthority,
) -> list[OutputReference]:
    report = authority.report_identity
    bindings = {
        binding.artifact_id: binding for binding in authority.byte_artifact_bindings
    }
    outputs: list[OutputReference] = []
    for artifact in authority.artifact_records:
        binding = bindings[artifact.artifact_id]
        outputs.append(
            OutputReference(
                output_id=f"output:artifact.{binding.role.value}",
                report_id=report.report_id,
                run_id=report.run_id,
                section_ids=_ARTIFACT_SECTION_IDS[binding.role],
                producing_contract=D3C_CONTEXT_BINDING_SCHEMA_ID,
                producing_version=D3C_CONTEXT_BINDING_CONTRACT_VERSION,
                output_class=OutputClass.CANONICAL,
                locator=binding.locator,
                digest=artifact.content_digest,
            )
        )
    return outputs


def _section_candidates(
    projection: D3CResultProjection,
    inputs: tuple[InputRecord, ...],
    outputs: tuple[OutputReference, ...],
    artifacts: tuple[ArtifactRecord, ...],
    bindings: tuple[GovernedByteArtifactBinding, ...],
) -> tuple[D3CSectionCandidate, ...]:
    role_by_artifact = {binding.artifact_id: binding.role for binding in bindings}
    projection_sections = {
        section.section_id: section for section in projection.sections
    }
    sections: list[D3CSectionCandidate] = []
    for section_id in D3C_SECTION_IDS:
        sections.append(
            D3CSectionCandidate(
                section_id=section_id,
                candidate_input_ids=tuple(
                    record.input_id
                    for record in inputs
                    if section_id in record.affected_section_ids
                ),
                candidate_output_ids=tuple(
                    record.output_id
                    for record in outputs
                    if section_id in record.section_ids
                ),
                candidate_artifact_ids=tuple(
                    record.artifact_id
                    for record in artifacts
                    if section_id
                    in _ARTIFACT_SECTION_IDS[role_by_artifact[record.artifact_id]]
                ),
                unresolved_dependency_ids=projection_sections[
                    section_id
                ].unresolved_dependency_ids,
                completeness_status="unresolved",
                evidence_status="unresolved",
                review_status="not_performed",
                professional_act_status="not_performed",
                achieved_grade="ungraded",
                release_status="hold",
            )
        )
    return tuple(sections)


def _bind_selected_authority(
    *,
    project_case: ProjectCase,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    projection: D3CResultProjection | None,
    authority: AcceptedAssemblyAuthority,
    artifact_payloads: tuple[GovernedArtifactPayload, ...],
) -> D3CContextBindingCandidate:
    _require(
        type(project_case) is ProjectCase,
        "invalid_project_case_type",
        "/project_case",
        "D3C-1b accepts exactly ProjectCase",
    )
    _require(
        type(request) is EvaluationRequest,
        "invalid_evaluation_request_type",
        "/evaluation_request",
        "D3C-1b accepts exactly EvaluationRequest",
    )
    _require(
        type(success) is D3BExecutionSuccess,
        "invalid_success_type",
        "/d3b_execution_success",
        "D3C-1b accepts exactly D3BExecutionSuccess",
    )
    _require(
        type(authority) is AcceptedAssemblyAuthority,
        "invalid_selected_authority_type",
        "/authority_id",
        "code-owned selection did not return an exact accepted D3C-0 authority",
    )
    try:
        fresh_projection = project_d3b_result(success)
    except ResultProjectionError as exc:
        raise D3CContextBindingError(
            "fresh_projection_failed",
            "/d3b_execution_success",
            f"fresh D3C-1a projection failed with {exc.code}",
        ) from exc
    if projection is None:
        selected_projection = fresh_projection
    else:
        _require(
            type(projection) is D3CResultProjection,
            "invalid_projection_type",
            "/projection",
            "supplied projection must be exactly D3CResultProjection",
        )
        _require(
            projection.model_dump_json() == fresh_projection.model_dump_json(),
            "projection_graph_mismatch",
            "/projection",
            "supplied D3C-1a projection is not graph-identical to a fresh projection",
        )
        selected_projection = projection

    project_digest, request_digest, success_digest = _reconcile_identity_graph(
        project_case, request, success, selected_projection, authority
    )
    verified = _verify_artifact_payloads(artifact_payloads, authority)
    inputs, origins = _candidate_inputs(project_case, authority)
    output_list = _carried_route_outputs(selected_projection, authority.report_identity)
    output_list.extend(
        _contextual_fx_outputs(
            project_case,
            request,
            success,
            selected_projection,
            authority,
            authority.report_identity,
        )
    )
    output_list.extend(_artifact_outputs(authority))
    outputs = tuple(output_list)
    sections = _section_candidates(
        selected_projection,
        inputs,
        outputs,
        authority.artifact_records,
        authority.byte_artifact_bindings,
    )
    return D3CContextBindingCandidate(
        outcome="candidate",
        schema_id=D3C_CONTEXT_BINDING_SCHEMA_ID,
        contract_version=D3C_CONTEXT_BINDING_CONTRACT_VERSION,
        authority_status="candidate_non_authoritative",
        authority_id=authority.authority_id,
        report_identity=authority.report_identity,
        evaluation_request_identity=authority.evaluation_request_identity,
        project_case_content_digest=project_digest,
        evaluation_request_content_digest=request_digest,
        d3b_execution_success_content_digest=success_digest,
        runtime_receipt=authority.runtime_receipt,
        projection=selected_projection,
        actor_records=authority.actor_records,
        source_records=authority.source_records,
        pack_bindings=authority.pack_bindings,
        jurisdiction_pack_ids=authority.jurisdiction_pack_ids,
        technology_pack_ids=authority.technology_pack_ids,
        authorized_registry_ids=authority.authorized_registry_ids,
        input_records=inputs,
        input_origins=origins,
        output_references=outputs,
        artifact_records=authority.artifact_records,
        byte_artifact_bindings=authority.byte_artifact_bindings,
        verified_artifact_payloads=verified,
        distribution_control=authority.distribution.control,
        sections=sections,
        completeness_status="unresolved",
        evidence_status="unresolved",
        review_status="not_performed",
        professional_act_status="not_performed",
        achieved_grade="ungraded",
        release_status="hold",
        reliance_status="not_permitted",
        publication_status="not_authorized",
    )


def bind_d3c_context(
    *,
    project_case: ProjectCase,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    projection: D3CResultProjection | None,
    authority_id: str,
    artifact_payloads: tuple[GovernedArtifactPayload, ...],
) -> D3CContextBindingOutcome:
    """Bind D3C-1b using only the code-owned production D3C-0 catalogue."""

    resolution = resolve_assembly_authority(authority_id)
    if type(resolution) is BlockedAssemblyAuthority:
        return _blocked_from_authority(authority_id, resolution)
    return _bind_selected_authority(
        project_case=project_case,
        request=request,
        success=success,
        projection=projection,
        authority=cast(AcceptedAssemblyAuthority, resolution),
        artifact_payloads=artifact_payloads,
    )


def _bind_d3c_context_from_catalogue_for_test(
    *,
    project_case: ProjectCase,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    projection: D3CResultProjection | None,
    authority_id: str,
    artifact_payloads: tuple[GovernedArtifactPayload, ...],
    authority_catalogue: Mapping[str, AcceptedAssemblyAuthority],
) -> D3CContextBindingOutcome:
    """Exercise code-owned selection in tests without opening caller injection publicly."""

    _require(
        type(authority_catalogue) is MappingProxyType,
        "test_catalogue_not_immutable",
        "/authority_id",
        "test authority catalogue must be an immutable code-owned mapping proxy",
    )
    resolution: AssemblyAuthorityResolution = (
        assembly_authority._resolve_from_catalogue(authority_id, authority_catalogue)
    )
    if type(resolution) is BlockedAssemblyAuthority:
        return _blocked_from_authority(authority_id, resolution)
    return _bind_selected_authority(
        project_case=project_case,
        request=request,
        success=success,
        projection=projection,
        authority=cast(AcceptedAssemblyAuthority, resolution),
        artifact_payloads=artifact_payloads,
    )


__all__ = (
    "D3B_SUCCESS_CONTENT_IDENTITY_VERSION",
    "D3C_CONTEXT_BINDING_CONTRACT_VERSION",
    "D3C_CONTEXT_BINDING_SCHEMA_ID",
    "BlockedD3CContextBinding",
    "CandidateInputOrigin",
    "D3CContextBindingBlockCode",
    "D3CContextBindingCandidate",
    "D3CContextBindingError",
    "D3CContextBindingOutcome",
    "D3CSectionCandidate",
    "GovernedArtifactPayload",
    "VerifiedArtifactPayload",
    "bind_d3c_context",
    "d3b_execution_success_content_digest",
)
