"""Governed D3C-0 assembly-authority selection contract.

This module authorizes facts that a later D3C package assembler may consume. It
does not assemble sections or a FeasibilityReportPackage, import or run the
evaluator, recompute finance, infer grade or evidence sufficiency, or grant
release. Production selection is deliberately closed and code-owned: callers
can supply only one stable authority identifier, and the production catalogue
is empty until a separately reviewed ledger change adds an exact receipt.

The SHA-256 records below bind identity only. They do not assert source truth,
evidence sufficiency, review, professional authority, or fitness for reliance.
"""

from __future__ import annotations

import json
import re
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Annotated, Any, Final, Literal, Mapping, TypeAlias, cast

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    TypeAdapter,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

from analytics.feasibility_sections import load_feasibility_taxonomy

from .records import (
    ActorRecord,
    ArtifactRecord,
    Digest,
    DistributionControl,
    PackBinding,
    ReportIdentity,
    SourceRecord,
    StrictFrozenModel,
    UtcDateTime,
)
from .vocabulary import ActorKind, ArtifactFormat, ConfidentialityClass, PackKind

ASSEMBLY_AUTHORITY_SCHEMA_ID: Final = "dutchbay.feasibility_assembly_authority.v1"
ASSEMBLY_AUTHORITY_CONTRACT_VERSION: Final = "1.0.0"
NON_RELIANCE_STATEMENT: Final = (
    "No reliance is permitted; package release remains on HOLD."
)
NO_PUBLICATION_STATEMENT: Final = "No publication is authorized."

_MAX_RECORDS: Final = 256
_MAX_TEXT_CODEPOINTS: Final = 4_096
_STABLE_ID_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*\Z")
_MISSING: Final = object()


def _exact_stable_id(value: object) -> object:
    """Reject, rather than normalize, identity-critical text."""

    if type(value) is not str:
        raise ValueError("stable identifier must be an exact string")
    if not 1 <= len(value) <= 200 or _STABLE_ID_RE.fullmatch(value) is None:
        raise ValueError("stable identifier has invalid exact lexical form")
    return value


def _exact_nonempty_text(value: object) -> object:
    """Keep evidential whitespace visible while bounding text."""

    if type(value) is not str:
        raise ValueError("bounded text must be an exact string")
    if not value or len(value) > _MAX_TEXT_CODEPOINTS:
        raise ValueError("bounded text must contain 1..4096 code points")
    if value != value.strip():
        raise ValueError("bounded text must not rely on whitespace normalization")
    if any(
        ord(character) < 32 and character not in {"\t", "\n"} for character in value
    ):
        raise ValueError("bounded text contains a prohibited control character")
    return value


ExactStableId = Annotated[str, BeforeValidator(_exact_stable_id)]
ExactBoundedText = Annotated[str, BeforeValidator(_exact_nonempty_text)]


def _validate_nonempty_unique_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError("identity tuple contains duplicate identities")
    return value


ExactIdTuple = Annotated[
    tuple[ExactStableId, ...],
    Field(min_length=1, max_length=_MAX_RECORDS),
    AfterValidator(_validate_nonempty_unique_tuple),
]


def _raw_field(record: object, field_name: str) -> object:
    if type(record) is dict:
        return cast(dict[str, object], record).get(field_name, _MISSING)
    if isinstance(record, StrictFrozenModel):
        return getattr(record, field_name, _MISSING)
    raise ValueError(
        "nested D2 records must be exact dictionaries or frozen contract objects"
    )


def _raw_records(container: dict[str, object], field_name: str) -> tuple[object, ...]:
    value = container.get(field_name, _MISSING)
    if value is _MISSING:
        return ()
    if type(value) not in {list, tuple}:
        raise ValueError(f"{field_name} must be an exact list or tuple")
    return tuple(cast(list[object] | tuple[object, ...], value))


def _require_raw_exact_id(value: object, label: str) -> None:
    if value is _MISSING or value is None:
        return
    try:
        _exact_stable_id(value)
    except ValueError as exc:
        raise ValueError(f"{label} is not an exact stable identifier") from exc


def _require_raw_exact_id_tuple(value: object, label: str) -> None:
    if value is _MISSING:
        return
    if type(value) not in {list, tuple}:
        raise ValueError(f"{label} must be an exact identifier list or tuple")
    identities = tuple(cast(list[object] | tuple[object, ...], value))
    if len(identities) > _MAX_RECORDS:
        raise ValueError(f"{label} exceeds the bounded record count")
    for identity in identities:
        _require_raw_exact_id(identity, label)
    if len(identities) != len(set(cast(tuple[str, ...], identities))):
        raise ValueError(f"{label} contains duplicate identities")


def _require_raw_exact_text(value: object, label: str) -> None:
    if value is _MISSING or value is None:
        return
    try:
        _exact_nonempty_text(value)
    except ValueError as exc:
        raise ValueError(f"{label} is not exact bounded text") from exc


def _require_raw_exact_text_tuple(value: object, label: str) -> None:
    if value is _MISSING:
        return
    if type(value) not in {list, tuple}:
        raise ValueError(f"{label} must be an exact text list or tuple")
    entries = tuple(cast(list[object] | tuple[object, ...], value))
    if len(entries) > _MAX_RECORDS:
        raise ValueError(f"{label} exceeds the bounded record count")
    for entry in entries:
        _require_raw_exact_text(entry, label)
    if len(entries) != len(set(cast(tuple[str, ...], entries))):
        raise ValueError(f"{label} contains duplicate entries")


def _validate_raw_record_fields(
    record: object,
    label: str,
    *,
    id_fields: tuple[str, ...] = (),
    id_tuple_fields: tuple[str, ...] = (),
    text_fields: tuple[str, ...] = (),
    text_tuple_fields: tuple[str, ...] = (),
) -> None:
    for field_name in id_fields:
        _require_raw_exact_id(_raw_field(record, field_name), f"{label}.{field_name}")
    for field_name in id_tuple_fields:
        _require_raw_exact_id_tuple(
            _raw_field(record, field_name), f"{label}.{field_name}"
        )
    for field_name in text_fields:
        _require_raw_exact_text(_raw_field(record, field_name), f"{label}.{field_name}")
    for field_name in text_tuple_fields:
        _require_raw_exact_text_tuple(
            _raw_field(record, field_name), f"{label}.{field_name}"
        )


def _validate_raw_nested_d2_records(data: dict[str, object]) -> None:
    """Refuse wire aliases before the D2 models can normalize their strings."""

    payload = data

    report = payload.get("report_identity", _MISSING)
    if report is not _MISSING:
        _validate_raw_record_fields(
            report,
            "report_identity",
            id_fields=(
                "report_id",
                "project_id",
                "case_id",
                "run_id",
                "supersedes_report_id",
            ),
        )

    for index, actor in enumerate(_raw_records(payload, "actor_records")):
        _validate_raw_record_fields(
            actor,
            f"actor_records[{index}]",
            id_fields=("actor_id",),
            id_tuple_fields=("input_ids", "review_ids"),
            text_fields=(
                "name",
                "organization",
                "version",
                "operation",
                "authority_basis",
            ),
        )

    for index, source in enumerate(_raw_records(payload, "source_records")):
        label = f"source_records[{index}]"
        _validate_raw_record_fields(
            source,
            label,
            id_fields=("source_id", "extracting_actor_id", "supersedes_source_id"),
            id_tuple_fields=(
                "jurisdictions",
                "technology_ids",
                "section_ids",
                "limitation_ids",
                "review_ids",
            ),
            text_fields=(
                "title",
                "issuer_or_author",
                "document_or_dataset_id",
                "revision",
                "authority",
                "project_boundary",
                "period",
                "licence_or_publication_rights",
                "access_restrictions",
                "extraction_method",
            ),
            text_tuple_fields=("quality_checks",),
        )
        locator = _raw_field(source, "locator")
        if locator is not _MISSING:
            _validate_raw_record_fields(
                locator,
                f"{label}.locator",
                text_fields=("url", "evidence_path", "pinpoint"),
            )

    for index, pack in enumerate(_raw_records(payload, "pack_bindings")):
        label = f"pack_bindings[{index}]"
        _validate_raw_record_fields(
            pack,
            label,
            id_fields=("pack_id", "owner_actor_id"),
            id_tuple_fields=(
                "compatible_pack_ids",
                "jurisdiction_codes",
                "technology_ids",
                "section_ids",
                "capability_ids",
                "required_input_ids",
                "optional_input_ids",
                "output_ids",
                "validation_ids",
                "source_ids",
                "review_ids",
                "decision_ids",
                "limitation_ids",
            ),
            text_tuple_fields=(
                "project_stages",
                "cross_field_rules",
                "permitted_degradations",
                "prohibited_substitutions",
            ),
        )
        default_input_ids: list[object] = []
        for default_index, default in enumerate(
            _raw_sequence_field(pack, "input_defaults", label)
        ):
            default_label = f"{label}.input_defaults[{default_index}]"
            _validate_raw_record_fields(
                default,
                default_label,
                id_fields=("input_id",),
                id_tuple_fields=("source_ids",),
                text_fields=("applicability_predicate",),
            )
            default_input_ids.append(_raw_field(default, "input_id"))
            canonical_value = _raw_field(default, "value")
            if canonical_value is not _MISSING:
                _validate_raw_record_fields(
                    canonical_value,
                    f"{default_label}.value",
                    text_fields=("value", "unit"),
                )
        if len(default_input_ids) != len(set(default_input_ids)):
            raise ValueError(f"{label}.input_defaults contains duplicate input_ids")
        evidence_section_ids: list[object] = []
        for minimum_index, minimum in enumerate(
            _raw_sequence_field(pack, "evidence_minima", label)
        ):
            minimum_label = f"{label}.evidence_minima[{minimum_index}]"
            _validate_raw_record_fields(
                minimum,
                minimum_label,
                id_fields=("section_id",),
                text_fields=("requirement",),
            )
            section_id = _raw_field(minimum, "section_id")
            evidence_section_ids.append(section_id)
        if len(evidence_section_ids) != len(set(evidence_section_ids)):
            raise ValueError(f"{label}.evidence_minima contains duplicate section_ids")

    for index, artifact in enumerate(_raw_records(payload, "artifact_records")):
        _validate_raw_record_fields(
            artifact,
            f"artifact_records[{index}]",
            id_fields=(
                "artifact_id",
                "report_id",
                "run_id",
                "supersedes_artifact_id",
            ),
            id_tuple_fields=("source_ids",),
            text_fields=(
                "mime_type",
                "producer",
                "producer_version",
                "completeness_profile",
            ),
            text_tuple_fields=("disclosure_exceptions",),
        )

    distribution = payload.get("distribution", _MISSING)
    if distribution is not _MISSING:
        control = _raw_field(distribution, "control")
        if control is not _MISSING:
            _validate_raw_record_fields(
                control,
                "distribution.control",
                id_fields=("distribution_id",),
                id_tuple_fields=("artifact_ids",),
                text_fields=(
                    "permitted_reliance",
                    "confidentiality",
                    "publication_rights",
                    "redaction_policy",
                ),
                text_tuple_fields=(
                    "intended_audiences",
                    "permitted_uses",
                    "reliance_exclusions",
                ),
            )
            disclosure_pairs: list[tuple[object, object]] = []
            for index, disclosure in enumerate(
                _raw_sequence_field(
                    control, "disclosure_bindings", "distribution.control"
                )
            ):
                label = f"distribution.control.disclosure_bindings[{index}]"
                _validate_raw_record_fields(
                    disclosure,
                    label,
                    id_fields=("artifact_id", "source_id", "validation_id"),
                    text_fields=("reason",),
                )
                artifact_id = _raw_field(disclosure, "artifact_id")
                source_id = _raw_field(disclosure, "source_id")
                disclosure_pairs.append((artifact_id, source_id))
            if len(disclosure_pairs) != len(set(disclosure_pairs)):
                raise ValueError("distribution disclosures contain duplicate bindings")


def _raw_sequence_field(
    record: object, field_name: str, label: str
) -> tuple[object, ...]:
    value = _raw_field(record, field_name)
    if value is _MISSING:
        return ()
    if type(value) not in {list, tuple}:
        raise ValueError(f"{label}.{field_name} must be an exact list or tuple")
    records = tuple(cast(list[object] | tuple[object, ...], value))
    if len(records) > _MAX_RECORDS:
        raise ValueError(f"{label}.{field_name} exceeds the bounded record count")
    return records


class AssemblyAuthorityOutcome(str, Enum):
    """Closed public resolution outcomes."""

    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class AssemblyAuthorityBlockCode(str, Enum):
    """Closed reasons for withholding assembly authority."""

    INVALID_AUTHORITY_ID = "invalid_authority_id"
    AUTHORITY_NOT_FOUND = "authority_not_found"
    IDENTITY_FACT_UNAVAILABLE = "identity_fact_unavailable"
    PACK_FACT_UNAVAILABLE = "pack_fact_unavailable"
    ARTIFACT_FACT_UNAVAILABLE = "artifact_fact_unavailable"
    RUNTIME_FACT_UNAVAILABLE = "runtime_fact_unavailable"
    DISTRIBUTION_FACT_UNAVAILABLE = "distribution_fact_unavailable"
    ACTOR_OR_SOURCE_FACT_UNAVAILABLE = "actor_or_source_fact_unavailable"


class GovernedByteArtifactRole(str, Enum):
    """The three full-result byte artifacts required before D3C assembly."""

    ANNUAL_ROWS = "annual_rows"
    DEBT_RESULT = "debt_result"
    FX_CURVE = "fx_curve"


class EvaluationRequestIdentity(StrictFrozenModel):
    """Exact D3B request/case identity; it is never a D2 report or run ID."""

    request_id: ExactStableId
    project_id: ExactStableId
    case_id: ExactStableId
    project_case_revision: Annotated[int, Field(gt=0)]
    d3b_scenario_authority_id: ExactStableId
    config_id: ExactStableId
    evidence_cutoff: date
    valuation_date: date


class UpstreamObjectDigestBindings(StrictFrozenModel):
    """Identity digests for the exact three upstream objects."""

    project_case: Digest
    evaluation_request: Digest
    d3b_execution_success: Digest
    d3b_embedded_project_case: Digest
    d3b_embedded_evaluation_request: Digest

    @model_validator(mode="after")
    def _embedded_digests_match(self) -> "UpstreamObjectDigestBindings":
        if self.project_case != self.d3b_embedded_project_case:
            raise ValueError(
                "D3B ProjectCase digest differs from the exact ProjectCase"
            )
        if self.evaluation_request != self.d3b_embedded_evaluation_request:
            raise ValueError(
                "D3B EvaluationRequest digest differs from the exact request"
            )
        return self


class AllocationAuthorityBinding(StrictFrozenModel):
    """Source and actor that allocated report/run identity."""

    allocation_id: ExactStableId
    source_id: ExactStableId
    actor_id: ExactStableId
    allocated_at: UtcDateTime


class GovernedRuntimeReceipt(StrictFrozenModel):
    """Exact engine-run environment facts needed by the later D2 RunManifest."""

    runtime_receipt_id: ExactStableId
    source_id: ExactStableId
    source_digest: Digest
    engine_version: ExactBoundedText
    code_commit: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{7,64}$", min_length=7, max_length=64),
    ]
    dirty_worktree: bool
    dirty_diff_digest: Digest | None = None
    environment: Annotated[
        tuple[ExactBoundedText, ...], Field(min_length=1, max_length=64)
    ]
    dependency_versions: Annotated[
        tuple[ExactBoundedText, ...], Field(min_length=1, max_length=256)
    ]
    engine_run_created_at: UtcDateTime
    captured_at: UtcDateTime

    @model_validator(mode="after")
    def _runtime_is_complete(self) -> "GovernedRuntimeReceipt":
        if len(self.environment) != len(set(self.environment)):
            raise ValueError("runtime environment facts must be unique")
        if len(self.dependency_versions) != len(set(self.dependency_versions)):
            raise ValueError("runtime dependency facts must be unique")
        if self.dirty_worktree != (self.dirty_diff_digest is not None):
            raise ValueError(
                "dirty_worktree and dirty_diff_digest must describe the same state"
            )
        if self.engine_run_created_at > self.captured_at:
            raise ValueError("runtime capture cannot predate the engine run")
        return self


class AuthorizedRegistryIds(StrictFrozenModel):
    """Exact future D2 registry IDs referenced by selected pack objects."""

    capability_ids: ExactIdTuple
    input_ids: tuple[ExactStableId, ...] = ()
    output_ids: tuple[ExactStableId, ...] = ()
    validation_ids: tuple[ExactStableId, ...] = ()
    limitation_ids: tuple[ExactStableId, ...] = ()
    review_ids: tuple[ExactStableId, ...] = ()
    decision_ids: tuple[ExactStableId, ...] = ()

    @model_validator(mode="after")
    def _registry_ids_are_unique(self) -> "AuthorizedRegistryIds":
        for field_name in (
            "input_ids",
            "output_ids",
            "validation_ids",
            "limitation_ids",
            "review_ids",
            "decision_ids",
        ):
            values = getattr(self, field_name)
            if len(values) > _MAX_RECORDS:
                raise ValueError(f"{field_name} exceeds the bounded record count")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} contains duplicate identities")
        return self


class GovernedByteArtifactBinding(StrictFrozenModel):
    """Exact byte binding for one selected D2 artifact record."""

    artifact_id: ExactStableId
    role: GovernedByteArtifactRole
    byte_length: Annotated[int, Field(gt=0, le=2**63 - 1)]
    locator: ExactBoundedText
    format: ArtifactFormat
    mime_type: ExactBoundedText
    producer: ExactBoundedText
    producer_version: ExactBoundedText
    created_at: UtcDateTime
    source_ids: ExactIdTuple
    confidentiality: ConfidentialityClass
    content_digest: Digest


class HeldNonRelianceDistributionBinding(StrictFrozenModel):
    """One D2 distribution control under an inexpressibly held boundary."""

    release_status: Literal["hold"]
    non_reliance: Literal[True]
    permitted_reliance_statement: Literal[
        "No reliance is permitted; package release remains on HOLD."
    ]
    scope_intended_audiences: Annotated[
        tuple[ExactBoundedText, ...], Field(min_length=1, max_length=64)
    ]
    scope_intended_uses: Annotated[
        tuple[ExactBoundedText, ...], Field(min_length=1, max_length=64)
    ]
    control: DistributionControl

    @model_validator(mode="after")
    def _scope_is_covered(self) -> "HeldNonRelianceDistributionBinding":
        if len(self.scope_intended_audiences) != len(
            set(self.scope_intended_audiences)
        ):
            raise ValueError("scope intended audiences contain duplicates")
        if len(self.scope_intended_uses) != len(set(self.scope_intended_uses)):
            raise ValueError("scope intended uses contain duplicates")
        if self.scope_intended_audiences != self.control.intended_audiences:
            raise ValueError("distribution audiences do not equal the held scope")
        if self.scope_intended_uses != self.control.permitted_uses:
            raise ValueError("distribution uses do not equal the held scope")
        if self.control.permitted_reliance != self.permitted_reliance_statement:
            raise ValueError("distribution control contradicts the non-reliance hold")
        if self.control.distribution_class is ConfidentialityClass.PUBLIC:
            raise ValueError("held assembly facts cannot authorize public distribution")
        if self.control.publication_rights != NO_PUBLICATION_STATEMENT:
            raise ValueError("distribution control contradicts the publication hold")
        return self


class AcceptedAssemblyAuthority(StrictFrozenModel):
    """Immutable, ledger-owned authorization of D3C assembly facts.

    There is deliberately no D3A support-status field. A D2 pack fact can enter
    only as the exact PackBinding selected by this code-owned receipt; D3A's
    neutral declared state has no promotion route here.
    """

    outcome: Literal[AssemblyAuthorityOutcome.ACCEPTED]
    schema_id: Literal["dutchbay.feasibility_assembly_authority.v1"]
    contract_version: Literal["1.0.0"]
    authority_id: ExactStableId
    authority_created_at: UtcDateTime
    report_identity: ReportIdentity
    evaluation_request_identity: EvaluationRequestIdentity
    upstream_digests: UpstreamObjectDigestBindings
    allocation_authority: AllocationAuthorityBinding
    orchestration_actor_id: ExactStableId
    runtime_receipt: GovernedRuntimeReceipt
    actor_records: Annotated[
        tuple[ActorRecord, ...], Field(min_length=1, max_length=_MAX_RECORDS)
    ]
    source_records: Annotated[
        tuple[SourceRecord, ...], Field(min_length=1, max_length=_MAX_RECORDS)
    ]
    pack_bindings: Annotated[
        tuple[PackBinding, ...], Field(min_length=2, max_length=_MAX_RECORDS)
    ]
    jurisdiction_pack_ids: ExactIdTuple
    technology_pack_ids: ExactIdTuple
    authorized_registry_ids: AuthorizedRegistryIds
    artifact_records: Annotated[
        tuple[ArtifactRecord, ...], Field(min_length=3, max_length=3)
    ]
    byte_artifact_bindings: Annotated[
        tuple[GovernedByteArtifactBinding, ...], Field(min_length=3, max_length=3)
    ]
    distribution: HeldNonRelianceDistributionBinding

    @field_validator(
        "report_identity",
        "actor_records",
        "source_records",
        "pack_bindings",
        "artifact_records",
        "distribution",
        mode="wrap",
    )
    @classmethod
    def _nested_d2_ingress_is_exact(
        cls,
        data: object,
        handler: ValidatorFunctionWrapHandler,
        info: ValidationInfo,
    ) -> object:
        field_name = cast(str, info.field_name)
        _validate_raw_nested_d2_records({field_name: data})
        if info.mode == "json":
            adapter: TypeAdapter[Any] = TypeAdapter(
                cls.model_fields[field_name].annotation
            )
            converted = adapter.validate_json(
                json.dumps(data),
                context=info.context,
            )
            return handler(converted)
        return handler(data)

    @model_validator(mode="after")
    def _authority_graph_is_exact(self) -> "AcceptedAssemblyAuthority":
        request = self.evaluation_request_identity
        report = self.report_identity

        if request.request_id in {report.report_id, report.run_id}:
            raise ValueError("request_id cannot be aliased to report_id or run_id")
        if report.report_id == report.run_id:
            raise ValueError("report_id and run_id must be distinct")
        if (report.project_id, report.case_id) != (
            request.project_id,
            request.case_id,
        ):
            raise ValueError("report identity does not match the evaluation case")

        if self.allocation_authority.allocated_at > report.created_at:
            raise ValueError("report identity cannot predate its allocation")
        if report.created_at > self.runtime_receipt.engine_run_created_at:
            raise ValueError("engine run cannot predate the allocated report identity")
        if self.runtime_receipt.captured_at > self.authority_created_at:
            raise ValueError("assembly authority cannot predate its runtime receipt")

        actors = _index_records(self.actor_records, "actor_id", "actor")
        sources = _index_records(self.source_records, "source_id", "source")
        packs = _index_records(self.pack_bindings, "pack_id", "pack")
        artifacts = _index_records(self.artifact_records, "artifact_id", "artifact")
        evidence_cutoff = request.evidence_cutoff

        if self.allocation_authority.actor_id not in actors:
            raise ValueError("allocation actor_id is dangling")
        if self.allocation_authority.source_id not in sources:
            raise ValueError("allocation source_id is dangling")
        if self.orchestration_actor_id not in actors:
            raise ValueError("orchestration actor_id is dangling")
        orchestration_actor = cast(ActorRecord, actors[self.orchestration_actor_id])
        if orchestration_actor.kind not in {ActorKind.SOFTWARE, ActorKind.AI_AGENT}:
            raise ValueError(
                "package orchestration actor must be software or AI provenance"
            )
        if self.runtime_receipt.source_id not in sources:
            raise ValueError("runtime receipt source_id is dangling")
        runtime_source = cast(SourceRecord, sources[self.runtime_receipt.source_id])
        if runtime_source.content_digest != self.runtime_receipt.source_digest:
            raise ValueError("runtime receipt digest differs from its source record")

        for source in self.source_records:
            if source.extracting_actor_id not in actors:
                raise ValueError(
                    f"source {source.source_id} has a dangling extracting actor"
                )
            if (
                source.supersedes_source_id is not None
                and source.supersedes_source_id not in sources
            ):
                raise ValueError(
                    f"source {source.source_id} has a dangling supersession"
                )
            if not set(source.section_ids) <= set(
                load_feasibility_taxonomy().section_names
            ):
                raise ValueError(
                    f"source {source.source_id} references an unknown taxonomy section"
                )
            dated_events = {
                "publication": source.publication_date,
                "observation": source.observation_date,
                "retrieval": source.retrieval_date,
            }
            future_events = sorted(
                name
                for name, value in dated_events.items()
                if value is not None and value > evidence_cutoff
            )
            if future_events:
                raise ValueError(
                    f"source {source.source_id} is after evidence cutoff: "
                    f"{future_events}"
                )
            if (
                source.effective_date is not None
                and source.effective_date > evidence_cutoff
            ):
                raise ValueError(
                    f"source {source.source_id} is not effective at evidence cutoff"
                )
            if source.expiry_date is not None and source.expiry_date < evidence_cutoff:
                raise ValueError(
                    f"source {source.source_id} expired before evidence cutoff"
                )
        self._validate_source_supersession_graph(sources)

        for artifact in self.artifact_records:
            if (
                artifact.report_id != report.report_id
                or artifact.run_id != report.run_id
            ):
                raise ValueError(
                    f"artifact {artifact.artifact_id} has foreign report/run identity"
                )
            if not artifact.source_ids:
                raise ValueError(f"artifact {artifact.artifact_id} requires source_ids")
            if not set(artifact.source_ids) <= set(sources):
                raise ValueError(
                    f"artifact {artifact.artifact_id} has dangling source_ids"
                )
            if not (
                self.runtime_receipt.engine_run_created_at
                <= artifact.created_at
                <= self.authority_created_at
            ):
                raise ValueError(
                    f"artifact {artifact.artifact_id} falls outside engine/authority chronology"
                )
            if artifact.supersedes_artifact_id is not None:
                raise ValueError(
                    f"artifact {artifact.artifact_id} supersession is unsupported "
                    "without a governed predecessor-artifact authority"
                )

        for disclosure in self.distribution.control.disclosure_bindings:
            if disclosure.artifact_id not in artifacts:
                raise ValueError("distribution disclosure has a dangling artifact")
            if disclosure.source_id not in sources:
                raise ValueError("distribution disclosure has a dangling source")
            disclosure_artifact = cast(
                ArtifactRecord, artifacts[disclosure.artifact_id]
            )
            if disclosure.source_id not in disclosure_artifact.source_ids:
                raise ValueError(
                    "distribution disclosure source is absent from its artifact"
                )
            if (
                disclosure.validation_id is not None
                and disclosure.validation_id
                not in self.authorized_registry_ids.validation_ids
            ):
                raise ValueError("distribution disclosure has a dangling validation")

        expected_jurisdiction_packs = {
            pack_id
            for pack_id, pack_record in packs.items()
            if cast(PackBinding, pack_record).kind is PackKind.JURISDICTION
        }
        expected_technology_packs = {
            pack_id
            for pack_id, pack_record in packs.items()
            if cast(PackBinding, pack_record).kind is PackKind.TECHNOLOGY
        }
        if set(self.jurisdiction_pack_ids) != expected_jurisdiction_packs:
            raise ValueError(
                "jurisdiction_pack_ids do not equal selected jurisdiction packs"
            )
        if set(self.technology_pack_ids) != expected_technology_packs:
            raise ValueError(
                "technology_pack_ids do not equal selected technology packs"
            )
        selected_technology_axes = tuple(
            cast(PackBinding, packs[pack_id]).technology_ids[0]
            for pack_id in self.technology_pack_ids
        )
        if len(selected_technology_axes) != len(set(selected_technology_axes)):
            raise ValueError(
                "each selected technology type requires exactly one D2 pack"
            )
        for pack in self.pack_bindings:
            if pack.owner_actor_id not in actors:
                raise ValueError(f"pack {pack.pack_id} has a dangling owner actor")
            if not set(pack.source_ids) <= set(sources):
                raise ValueError(f"pack {pack.pack_id} has dangling source_ids")
            if not set(pack.compatible_pack_ids) <= set(packs):
                raise ValueError(
                    f"pack {pack.pack_id} has dangling compatible_pack_ids"
                )
            if not set(pack.section_ids) <= set(
                load_feasibility_taxonomy().section_names
            ):
                raise ValueError(
                    f"pack {pack.pack_id} references an unknown taxonomy section"
                )
            if (
                pack.effective_date > evidence_cutoff
                or pack.review_date > evidence_cutoff
            ):
                raise ValueError(
                    f"pack {pack.pack_id} is not current at evidence cutoff"
                )
        self._validate_pack_registry_ids()
        self._validate_actor_source_reciprocity(actors, sources)

        _index_artifact_roles(self.byte_artifact_bindings)
        for binding in self.byte_artifact_bindings:
            selected_artifact = cast(
                ArtifactRecord | None, artifacts.get(binding.artifact_id)
            )
            if selected_artifact is None:
                raise ValueError(
                    f"byte binding {binding.role.value} has a dangling artifact"
                )
            if binding.content_digest != selected_artifact.content_digest:
                raise ValueError(
                    f"byte binding {binding.role.value} differs from artifact digest"
                )
            for field_name in (
                "format",
                "mime_type",
                "producer",
                "producer_version",
                "created_at",
                "source_ids",
                "confidentiality",
            ):
                if getattr(binding, field_name) != getattr(
                    selected_artifact, field_name
                ):
                    raise ValueError(
                        f"byte binding {binding.role.value} differs from artifact "
                        f"{field_name}"
                    )

        control = self.distribution.control
        if set(control.artifact_ids) != set(artifacts):
            raise ValueError("distribution must cover every and only selected artifact")
        if control.expiry_or_review_date < self.authority_created_at.date():
            raise ValueError("distribution control is expired at authority creation")
        return self

    @staticmethod
    def _validate_source_supersession_graph(sources: dict[str, object]) -> None:
        for source_id, source_record in sources.items():
            seen = {source_id}
            predecessor_id = cast(SourceRecord, source_record).supersedes_source_id
            while predecessor_id is not None:
                if predecessor_id in seen:
                    raise ValueError("source supersession graph contains a cycle")
                seen.add(predecessor_id)
                predecessor_id = cast(
                    SourceRecord, sources[predecessor_id]
                ).supersedes_source_id

    def _validate_pack_registry_ids(self) -> None:
        registry = self.authorized_registry_ids
        expected: dict[str, set[str]] = {
            "capability_ids": set(),
            "input_ids": set(),
            "output_ids": set(),
            "validation_ids": set(),
            "limitation_ids": set(),
            "review_ids": set(),
            "decision_ids": set(),
        }
        for pack in self.pack_bindings:
            expected["capability_ids"].update(pack.capability_ids)
            expected["input_ids"].update(pack.required_input_ids)
            expected["input_ids"].update(pack.optional_input_ids)
            expected["output_ids"].update(pack.output_ids)
            expected["validation_ids"].update(pack.validation_ids)
            expected["limitation_ids"].update(pack.limitation_ids)
            expected["review_ids"].update(pack.review_ids)
            expected["decision_ids"].update(pack.decision_ids)
        for field_name, expected_ids in expected.items():
            if set(getattr(registry, field_name)) != expected_ids:
                raise ValueError(
                    f"authorized {field_name} do not equal the exact pack references"
                )

    def _validate_actor_source_reciprocity(
        self,
        actors: dict[str, object],
        sources: dict[str, object],
    ) -> None:
        registry = self.authorized_registry_ids
        referenced_actors = {
            self.allocation_authority.actor_id,
            self.orchestration_actor_id,
            *(source.extracting_actor_id for source in self.source_records),
            *(pack.owner_actor_id for pack in self.pack_bindings),
        }
        if referenced_actors != set(actors):
            raise ValueError("actor_records must be exactly the referenced actors")
        referenced_sources = {
            self.allocation_authority.source_id,
            self.runtime_receipt.source_id,
            *(
                source.supersedes_source_id
                for source in self.source_records
                if source.supersedes_source_id is not None
            ),
            *(
                source_id
                for pack in self.pack_bindings
                for source_id in pack.source_ids
            ),
            *(
                source_id
                for pack in self.pack_bindings
                for default in pack.input_defaults
                for source_id in default.source_ids
            ),
            *(
                source_id
                for artifact in self.artifact_records
                for source_id in artifact.source_ids
            ),
            *(
                disclosure.source_id
                for disclosure in self.distribution.control.disclosure_bindings
            ),
        }
        if referenced_sources != set(sources):
            raise ValueError("source_records must be exactly the referenced sources")
        for actor in self.actor_records:
            if not set(actor.input_ids) <= set(registry.input_ids):
                raise ValueError(f"actor {actor.actor_id} has unauthorized input_ids")
            if not set(actor.review_ids) <= set(registry.review_ids):
                raise ValueError(f"actor {actor.actor_id} has unauthorized review_ids")
        for source in self.source_records:
            if not set(source.limitation_ids) <= set(registry.limitation_ids):
                raise ValueError(
                    f"source {source.source_id} has unauthorized limitation_ids"
                )
            if not set(source.review_ids) <= set(registry.review_ids):
                raise ValueError(
                    f"source {source.source_id} has unauthorized review_ids"
                )


class BlockedAssemblyAuthority(StrictFrozenModel):
    """Closed refusal; no partial receipt can be mistaken for authority."""

    outcome: Literal[AssemblyAuthorityOutcome.BLOCKED]
    schema_id: Literal["dutchbay.feasibility_assembly_authority.v1"]
    contract_version: Literal["1.0.0"]
    authority_id: ExactStableId
    code: AssemblyAuthorityBlockCode
    blocking_fact_ids: tuple[ExactStableId, ...] = ()
    message: ExactBoundedText

    @model_validator(mode="after")
    def _blocking_facts_are_unique(self) -> "BlockedAssemblyAuthority":
        if len(self.blocking_fact_ids) > _MAX_RECORDS:
            raise ValueError("blocking_fact_ids exceed the bounded record count")
        if len(self.blocking_fact_ids) != len(set(self.blocking_fact_ids)):
            raise ValueError("blocking_fact_ids contain duplicates")
        return self


AssemblyAuthorityResolution: TypeAlias = Annotated[
    AcceptedAssemblyAuthority | BlockedAssemblyAuthority,
    Field(discriminator="outcome"),
]


def _index_records(
    records: tuple[object, ...], attribute: str, label: str
) -> dict[str, object]:
    indexed: dict[str, object] = {}
    for record in records:
        record_id = getattr(record, attribute)
        if record_id in indexed:
            raise ValueError(f"duplicate {label} identity: {record_id}")
        indexed[record_id] = record
    return indexed


def _index_artifact_roles(
    bindings: tuple[GovernedByteArtifactBinding, ...],
) -> dict[GovernedByteArtifactRole, GovernedByteArtifactBinding]:
    indexed: dict[GovernedByteArtifactRole, GovernedByteArtifactBinding] = {}
    artifact_ids: set[str] = set()
    for binding in bindings:
        if binding.role in indexed:
            raise ValueError(f"duplicate byte artifact role: {binding.role.value}")
        if binding.artifact_id in artifact_ids:
            raise ValueError("one artifact cannot satisfy multiple byte artifact roles")
        indexed[binding.role] = binding
        artifact_ids.add(binding.artifact_id)
    return indexed


AssemblyAuthorityCatalogue: TypeAlias = Mapping[
    str, AcceptedAssemblyAuthority | BlockedAssemblyAuthority
]

# A real authority requires governed production identity, pack, runtime, artifact,
# source, actor and distribution facts. None currently exists. Adding one is a
# separately reviewed ledger/code change; callers cannot inject a replacement.
_PRODUCTION_ASSEMBLY_AUTHORITIES: Final[AssemblyAuthorityCatalogue] = MappingProxyType(
    {}
)


def _is_exact_stable_id(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 200
        and _STABLE_ID_RE.fullmatch(value) is not None
    )


def _blocked(
    authority_id: str,
    code: AssemblyAuthorityBlockCode,
    message: str,
) -> BlockedAssemblyAuthority:
    return BlockedAssemblyAuthority(
        outcome=AssemblyAuthorityOutcome.BLOCKED,
        schema_id=ASSEMBLY_AUTHORITY_SCHEMA_ID,
        contract_version=ASSEMBLY_AUTHORITY_CONTRACT_VERSION,
        authority_id=authority_id,
        code=code,
        message=message,
    )


def _resolve_from_catalogue(
    authority_id: str, catalogue: AssemblyAuthorityCatalogue
) -> AcceptedAssemblyAuthority | BlockedAssemblyAuthority:
    """Private seam used by the immutable production catalogue and hostile tests."""

    resolved = catalogue.get(authority_id)
    if resolved is None:
        return _blocked(
            authority_id,
            AssemblyAuthorityBlockCode.AUTHORITY_NOT_FOUND,
            "No governed production assembly authority exists for this stable ID.",
        )
    if resolved.authority_id != authority_id:
        return _blocked(
            authority_id,
            AssemblyAuthorityBlockCode.IDENTITY_FACT_UNAVAILABLE,
            "The selected ledger key does not match its authority receipt.",
        )
    return resolved


def resolve_assembly_authority(
    authority_id: object,
) -> AcceptedAssemblyAuthority | BlockedAssemblyAuthority:
    """Resolve one code-owned authority by ID; arbitrary receipts are impossible."""

    if not _is_exact_stable_id(authority_id):
        return _blocked(
            "invalid:assembly-authority-id",
            AssemblyAuthorityBlockCode.INVALID_AUTHORITY_ID,
            "Assembly authority ID is not a valid exact stable identifier.",
        )
    return _resolve_from_catalogue(
        cast(str, authority_id), _PRODUCTION_ASSEMBLY_AUTHORITIES
    )


__all__ = (
    "ASSEMBLY_AUTHORITY_CONTRACT_VERSION",
    "ASSEMBLY_AUTHORITY_SCHEMA_ID",
    "NO_PUBLICATION_STATEMENT",
    "NON_RELIANCE_STATEMENT",
    "AcceptedAssemblyAuthority",
    "AllocationAuthorityBinding",
    "AssemblyAuthorityBlockCode",
    "AssemblyAuthorityOutcome",
    "AssemblyAuthorityResolution",
    "AuthorizedRegistryIds",
    "BlockedAssemblyAuthority",
    "EvaluationRequestIdentity",
    "GovernedByteArtifactBinding",
    "GovernedByteArtifactRole",
    "GovernedRuntimeReceipt",
    "HeldNonRelianceDistributionBinding",
    "UpstreamObjectDigestBindings",
    "resolve_assembly_authority",
)
