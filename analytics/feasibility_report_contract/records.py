"""Typed records for DBAY-FRC-001 feasibility-report package v1.

This module is deliberately policy-light.  It validates the meaning local to each
record; package-wide identity, taxonomy and reference-integrity checks live in
``package.py``.  No record derives assessment grade or release authority.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal, Union

from pydantic import (
    AfterValidator,
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from analytics.feasibility_sections import load_feasibility_taxonomy
from analytics.run_modes import RunMode

from .vocabulary import (
    FEASIBILITY_REPORT_CONTRACT_VERSION,
    FEASIBILITY_REPORT_SCHEMA_ID,
    SECTION_CONTRACT_VERSION,
    AchievedGrade,
    ActorKind,
    Applicability,
    ArtifactFormat,
    AssessmentGrade,
    AuthenticityStatus,
    CapabilityOutcome,
    ConfidentialityClass,
    CurrencyCode,
    DecisionKind,
    DecisionOutcome,
    DisclosureAction,
    EvidenceStatus,
    FindingStatus,
    GitCommit,
    GovernedSubjectKind,
    Identifier,
    IndependenceStatus,
    InputKind,
    InputResolutionStatus,
    JurisdictionCode,
    Materiality,
    NonEmptyText,
    OutputClass,
    PackageReleaseStatus,
    PackKind,
    PackStatus,
    ProductionStatus,
    ReconciliationFamily,
    ReconciliationStatus,
    ResponsibilityRole,
    ResponsibilityStatus,
    ReviewStatus,
    SectionAchievedGrade,
    SectionReleaseStatus,
    SemanticVersion,
    Sha256Hex,
    SourceClass,
    StrictFrozenModel,
    SubjectKind,
    UnitToken,
    ValidationStatus,
    ValueType,
)


def _utc_only(value: datetime) -> datetime:
    """Reject naive and non-UTC timestamps as required by DBAY-FRC-001 section 10.3."""
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be timezone-aware RFC 3339 UTC")
    return value


UtcDateTime = Annotated[datetime, AfterValidator(_utc_only)]


class Digest(StrictFrozenModel):
    """A typed identity digest; it does not assert truth or authority."""

    algorithm: Literal["sha256"] = "sha256"
    value: Sha256Hex


class CanonicalValue(StrictFrozenModel):
    """Precision-preserving lexical value and optional unit."""

    value_type: ValueType
    value: NonEmptyText
    unit: UnitToken | None = None
    precision: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _lexical_value_matches_declared_type(self) -> CanonicalValue:
        if self.value_type is ValueType.INTEGER:
            if re.fullmatch(r"[+-]?\d+", self.value) is None:
                raise ValueError("integer CanonicalValue has invalid lexical value")
        elif self.value_type is ValueType.DECIMAL:
            try:
                decimal_value = Decimal(self.value)
            except InvalidOperation as exc:
                raise ValueError(
                    "decimal CanonicalValue has invalid lexical value"
                ) from exc
            if not decimal_value.is_finite():
                raise ValueError("decimal CanonicalValue must be finite")
        elif self.value_type is ValueType.BOOLEAN:
            if self.value not in {"true", "false"}:
                raise ValueError("boolean CanonicalValue must be 'true' or 'false'")
        elif self.value_type is ValueType.DATE:
            try:
                date.fromisoformat(self.value)
            except ValueError as exc:
                raise ValueError("date CanonicalValue must be ISO 8601") from exc
        elif self.value_type is ValueType.DATETIME:
            try:
                parsed = datetime.fromisoformat(self.value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("datetime CanonicalValue must be ISO 8601") from exc
            _utc_only(parsed)
        if self.precision is not None and self.value_type not in {
            ValueType.INTEGER,
            ValueType.DECIMAL,
        }:
            raise ValueError("precision is valid only for integer/decimal values")
        if (
            self.value_type in {ValueType.INTEGER, ValueType.DECIMAL}
            and self.unit is None
        ):
            raise ValueError(
                "numeric CanonicalValue requires an explicit unit; use controlled "
                "dimensionless tokens such as '1', 'fraction', 'pct', 'basis_point', "
                "'ratio' or 'count'"
            )
        return self


class ReportIdentity(StrictFrozenModel):
    """Stable identity and revision binding for one report package."""

    report_id: Identifier
    project_id: Identifier
    case_id: Identifier
    run_id: Identifier
    issue: PositiveInt
    revision: NonNegativeInt
    created_at: UtcDateTime
    supersedes_report_id: Identifier | None = None


class ScopeDeclaration(StrictFrozenModel):
    """Explicit project, decision, grade, jurisdiction and technology boundary."""

    project_boundary: NonEmptyText
    technology_ids: tuple[Identifier, ...]
    jurisdictions: tuple[JurisdictionCode, ...]
    project_stage: NonEmptyText
    intended_audiences: tuple[NonEmptyText, ...]
    intended_uses: tuple[NonEmptyText, ...]
    run_mode: RunMode
    target_grade: AssessmentGrade
    valuation_date: date
    evidence_cutoff: date
    reporting_currency: CurrencyCode
    price_basis: NonEmptyText
    exclusions: tuple[NonEmptyText, ...] = ()
    materiality_rule: NonEmptyText
    jurisdiction_pack_ids: tuple[Identifier, ...]
    technology_pack_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _scope_is_explicit(self) -> ScopeDeclaration:
        if not self.technology_ids:
            raise ValueError("scope requires at least one typed technology_id")
        if not self.jurisdictions:
            raise ValueError("scope requires at least one explicit jurisdiction")
        if not self.intended_audiences or not self.intended_uses:
            raise ValueError("scope requires intended audience and use")
        if not self.jurisdiction_pack_ids or not self.technology_pack_ids:
            raise ValueError(
                "scope requires explicit jurisdiction and technology pack bindings"
            )
        return self


class JurisdictionSubjectBinding(StrictFrozenModel):
    """Disposition one governed subject through one exact jurisdiction pack."""

    binding_id: Identifier
    jurisdiction: JurisdictionCode
    subject_id: Identifier
    subject_kind: GovernedSubjectKind
    disposition_pack_id: Identifier
    contribution_section_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _contribution_is_explicit(self) -> JurisdictionSubjectBinding:
        if not self.contribution_section_ids:
            raise ValueError(
                "jurisdiction subject binding requires contribution_section_ids"
            )
        return self


class ActorRecord(StrictFrozenModel):
    """A human, institution or automated provenance actor."""

    actor_id: Identifier
    kind: ActorKind
    name: NonEmptyText
    organization: NonEmptyText | None = None
    version: NonEmptyText | None = None
    operation: NonEmptyText | None = None
    input_ids: tuple[Identifier, ...] = ()
    review_ids: tuple[Identifier, ...] = ()
    identity_verified: bool = False
    authority_basis: NonEmptyText | None = None

    @model_validator(mode="after")
    def _version_automated_actors(self) -> ActorRecord:
        if self.kind in {ActorKind.SOFTWARE, ActorKind.AI_AGENT} and (
            self.version is None or self.operation is None
        ):
            raise ValueError("software and AI actors require version and operation")
        if (
            self.kind in {ActorKind.HUMAN, ActorKind.INSTITUTION}
            and self.organization is None
        ):
            raise ValueError("human and institution actors require organization")
        return self


class ReportSubjectBinding(StrictFrozenModel):
    """Exact report/run and optional section/artifact/review subject binding."""

    kind: Literal[SubjectKind.REPORT_SECTIONS] = SubjectKind.REPORT_SECTIONS
    report_id: Identifier
    run_id: Identifier
    section_ids: tuple[Identifier, ...] = ()
    claim_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()
    artifact_ids: tuple[Identifier, ...] = ()
    review_ids: tuple[Identifier, ...] = ()


class PackVersionSubjectBinding(StrictFrozenModel):
    """Exact pack/version/grade and effective-period subject binding."""

    kind: Literal[SubjectKind.PACK_VERSION] = SubjectKind.PACK_VERSION
    pack_id: Identifier
    pack_version: SemanticVersion
    grade: AssessmentGrade
    effective_from: date
    effective_until: date
    review_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _period_is_ordered(self) -> PackVersionSubjectBinding:
        if self.effective_until < self.effective_from:
            raise ValueError("pack subject effective_until precedes effective_from")
        return self


SubjectBinding = Annotated[
    Union[ReportSubjectBinding, PackVersionSubjectBinding],
    Field(discriminator="kind"),
]


class ResponsibilityAssignment(StrictFrozenModel):
    """A controlled responsibility statement; automation cannot fill human roles."""

    assignment_id: Identifier
    role: ResponsibilityRole
    status: ResponsibilityStatus
    scope: NonEmptyText
    subject_binding: SubjectBinding
    actor_id: Identifier | None = None
    performed_at: UtcDateTime | None = None
    decision_id: Identifier | None = None
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def _performed_assignment_is_attributed(self) -> ResponsibilityAssignment:
        if self.status is ResponsibilityStatus.PERFORMED:
            if (
                self.actor_id is None
                or self.performed_at is None
                or self.decision_id is None
            ):
                raise ValueError(
                    "performed responsibility requires actor_id, performed_at and decision_id"
                )
        elif self.reason is None:
            raise ValueError(
                "unperformed/not-required responsibility requires a reason"
            )
        return self


class PackInputDefault(StrictFrozenModel):
    """Explicit pack default and its provenance; never a hidden fallback."""

    input_id: Identifier
    value: CanonicalValue
    source_ids: tuple[Identifier, ...]
    applicability_predicate: NonEmptyText

    @model_validator(mode="after")
    def _default_has_provenance(self) -> PackInputDefault:
        if not self.source_ids:
            raise ValueError("pack input default requires source provenance")
        return self


class PackEvidenceMinimum(StrictFrozenModel):
    """Pack-declared evidence minimum for one section and target grade."""

    section_id: Identifier
    target_grade: AssessmentGrade
    requirement: NonEmptyText


class PackBinding(StrictFrozenModel):
    """Versioned jurisdiction or technology contribution boundary."""

    pack_id: Identifier
    kind: PackKind
    status: PackStatus
    version: SemanticVersion
    owner_actor_id: Identifier
    effective_date: date
    review_date: date
    compatible_contract_versions: tuple[SemanticVersion, ...]
    compatible_pack_ids: tuple[Identifier, ...] = ()
    jurisdiction_codes: tuple[JurisdictionCode, ...] = ()
    technology_ids: tuple[Identifier, ...] = ()
    project_stages: tuple[NonEmptyText, ...]
    section_ids: tuple[Identifier, ...]
    capability_ids: tuple[Identifier, ...]
    required_input_ids: tuple[Identifier, ...] = ()
    optional_input_ids: tuple[Identifier, ...] = ()
    input_defaults: tuple[PackInputDefault, ...] = ()
    output_ids: tuple[Identifier, ...] = ()
    validation_ids: tuple[Identifier, ...] = ()
    source_ids: tuple[Identifier, ...] = ()
    evidence_minima: tuple[PackEvidenceMinimum, ...]
    cross_field_rules: tuple[NonEmptyText, ...]
    permitted_degradations: tuple[NonEmptyText, ...]
    prohibited_substitutions: tuple[NonEmptyText, ...]
    review_ids: tuple[Identifier, ...] = ()
    decision_ids: tuple[Identifier, ...] = ()
    limitation_ids: tuple[Identifier, ...] = ()
    grade_ceiling: AchievedGrade | None = None

    @model_validator(mode="after")
    def _pack_has_one_explicit_axis(self) -> PackBinding:
        if self.kind is PackKind.JURISDICTION:
            if not self.jurisdiction_codes or self.technology_ids:
                raise ValueError(
                    "jurisdiction pack requires jurisdiction_codes and forbids technology_ids"
                )
            if len(self.jurisdiction_codes) != 1:
                raise ValueError(
                    "v1 jurisdiction pack must govern exactly one jurisdiction"
                )
        elif not self.technology_ids or self.jurisdiction_codes:
            raise ValueError(
                "technology pack requires technology_ids and forbids jurisdiction_codes"
            )
        elif len(self.technology_ids) != 1:
            raise ValueError(
                "v1 technology pack must represent exactly one technology type"
            )
        if FEASIBILITY_REPORT_CONTRACT_VERSION not in self.compatible_contract_versions:
            raise ValueError(
                "pack is not compatible with the feasibility-report contract"
            )
        if not self.project_stages or not self.section_ids or not self.capability_ids:
            raise ValueError(
                "pack requires project stages, constrained sections and capabilities"
            )
        if set(self.required_input_ids) & set(self.optional_input_ids):
            raise ValueError("pack required and optional inputs must be disjoint")
        declared_inputs = set(self.required_input_ids) | set(self.optional_input_ids)
        if any(
            default.input_id not in declared_inputs for default in self.input_defaults
        ):
            raise ValueError("pack default references an undeclared input")
        if any(
            not set(default.source_ids) <= set(self.source_ids)
            for default in self.input_defaults
        ):
            raise ValueError("pack default source must be declared by the pack")
        if any(
            minimum.section_id not in self.section_ids
            for minimum in self.evidence_minima
        ):
            raise ValueError(
                "pack evidence minimum references an unconstrained section"
            )
        if not self.cross_field_rules or not self.prohibited_substitutions:
            raise ValueError(
                "pack requires explicit cross-field rules and prohibited substitutions"
            )
        if self.status is PackStatus.UNSUPPORTED and self.grade_ceiling is not None:
            raise ValueError(
                "unsupported pack must not claim an achieved-grade ceiling"
            )
        if self.status is not PackStatus.UNSUPPORTED and (
            self.grade_ceiling is None or not self.evidence_minima
        ):
            raise ValueError(
                "supported/assured pack requires grade ceiling and evidence minima"
            )
        if (
            self.status is not PackStatus.UNSUPPORTED
            and self.grade_ceiling is AchievedGrade.UNGRADED
        ):
            raise ValueError(
                "supported/assured pack requires a non-sentinel grade ceiling"
            )
        if self.status is not PackStatus.UNSUPPORTED and {
            minimum.section_id for minimum in self.evidence_minima
        } != set(self.section_ids):
            raise ValueError(
                "supported/assured pack requires evidence minima for every section"
            )
        if self.status is not PackStatus.UNSUPPORTED and (
            not self.source_ids
            or not self.validation_ids
            or not self.limitation_ids
            or not self.permitted_degradations
        ):
            raise ValueError(
                "supported/assured pack requires sources, validations, limitations "
                "and declared degradations"
            )
        if self.status is PackStatus.ASSURED and (
            not self.review_ids or not self.decision_ids
        ):
            raise ValueError("assured pack requires review and decision records")
        return self


class InputRecord(StrictFrozenModel):
    """Supplied, enriched, resolved or derived input with explicit state."""

    input_id: Identifier
    kind: InputKind
    resolution_status: InputResolutionStatus
    name: NonEmptyText
    raw_value: CanonicalValue | None = None
    resolved_value: CanonicalValue | None = None
    source_ids: tuple[Identifier, ...] = ()
    derivation_ids: tuple[Identifier, ...] = ()
    validation_ids: tuple[Identifier, ...] = ()
    affected_claim_ids: tuple[Identifier, ...] = ()
    affected_section_ids: tuple[Identifier, ...]
    reason: NonEmptyText | None = None
    remedy: NonEmptyText | None = None

    @model_validator(mode="after")
    def _resolution_is_explicit(self) -> InputRecord:
        if not self.affected_section_ids:
            raise ValueError("input requires at least one affected section")
        if self.kind is InputKind.DERIVED and not self.derivation_ids:
            raise ValueError("derived input requires derivation_ids")
        if self.resolution_status is InputResolutionStatus.RESOLVED:
            if self.resolved_value is None:
                raise ValueError("resolved input requires resolved_value")
        elif self.reason is None or self.remedy is None:
            raise ValueError("missing/invalid input requires reason and remedy")
        return self


class SourceLocator(StrictFrozenModel):
    """Direct and pinpoint location of a controlled source."""

    url: NonEmptyText | None = None
    evidence_path: NonEmptyText | None = None
    pinpoint: NonEmptyText

    @model_validator(mode="after")
    def _has_location(self) -> SourceLocator:
        if self.url is None and self.evidence_path is None:
            raise ValueError("source locator requires url or evidence_path")
        return self


class SourceRecord(StrictFrozenModel):
    """Source identity, authority, temporal scope, rights and provenance."""

    source_id: Identifier
    title: NonEmptyText
    issuer_or_author: NonEmptyText
    document_or_dataset_id: NonEmptyText
    revision: NonEmptyText
    publication_date: date | None = None
    effective_date: date | None = None
    observation_date: date | None = None
    retrieval_date: date
    locator: SourceLocator
    source_class: SourceClass
    authenticity_status: AuthenticityStatus
    authority: NonEmptyText
    jurisdictions: tuple[JurisdictionCode, ...]
    technology_ids: tuple[Identifier, ...]
    project_boundary: NonEmptyText
    section_ids: tuple[Identifier, ...]
    period: NonEmptyText
    licence_or_publication_rights: NonEmptyText
    publication_permitted: bool
    access_restrictions: NonEmptyText
    confidentiality: ConfidentialityClass
    extraction_method: NonEmptyText
    extracting_actor_id: Identifier
    quality_checks: tuple[NonEmptyText, ...]
    content_digest: Digest | None = None
    supersedes_source_id: Identifier | None = None
    expiry_date: date | None = None
    limitation_ids: tuple[Identifier, ...] = ()
    review_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _source_has_scope_and_quality_control(self) -> SourceRecord:
        if not self.section_ids:
            raise ValueError("source requires explicit section_ids")
        if not self.quality_checks:
            raise ValueError("source requires at least one quality check")
        return self


class OutputReference(StrictFrozenModel):
    """A typed reference to output produced for this report run."""

    output_id: Identifier
    report_id: Identifier
    run_id: Identifier
    section_ids: tuple[Identifier, ...]
    producing_contract: NonEmptyText
    producing_version: NonEmptyText
    output_class: OutputClass
    locator: NonEmptyText
    value: CanonicalValue | None = None
    digest: Digest | None = None
    warning: NonEmptyText | None = None
    derivation_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _synthetic_is_labelled(self) -> OutputReference:
        if self.output_class is OutputClass.SYNTHETIC and self.warning is None:
            raise ValueError("synthetic output requires a persistent warning")
        return self


class ClaimRecord(StrictFrozenModel):
    """A precise report proposition linked to outputs and evidence."""

    claim_id: Identifier
    section_id: Identifier
    statement: NonEmptyText
    materiality: Materiality
    jurisdictions: tuple[JurisdictionCode, ...]
    technology_ids: tuple[Identifier, ...]
    project_boundary: NonEmptyText
    value: CanonicalValue | None = None
    output_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _claim_has_evidence_disposition(self) -> ClaimRecord:
        if not self.evidence_ids:
            raise ValueError("claim requires at least one evidence disposition")
        return self


class EvidenceRecord(StrictFrozenModel):
    """Claim-specific evidence sufficiency and review statement."""

    evidence_id: Identifier
    claim_id: Identifier
    source_id: Identifier | None = None
    locator: NonEmptyText
    authenticity_status: AuthenticityStatus
    relevance: NonEmptyText
    jurisdictions: tuple[JurisdictionCode, ...]
    technology_ids: tuple[Identifier, ...]
    project_boundary: NonEmptyText
    period: NonEmptyText
    independence_status: IndependenceStatus
    sufficiency: EvidenceStatus
    limitation_ids: tuple[Identifier, ...] = ()
    review_ids: tuple[Identifier, ...] = ()
    expiry_date: date | None = None
    required_external_item: NonEmptyText | None = None

    @model_validator(mode="after")
    def _source_or_missing_request(self) -> EvidenceRecord:
        missing_states = {
            EvidenceStatus.MISSING,
            EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
        }
        if self.source_id is None and self.sufficiency not in missing_states:
            raise ValueError("non-missing evidence requires source_id")
        if self.sufficiency in missing_states and self.required_external_item is None:
            raise ValueError(
                "missing/external-hold evidence requires required_external_item"
            )
        if (
            self.independence_status is IndependenceStatus.INDEPENDENT
            and not self.review_ids
        ):
            raise ValueError("independent evidence status requires a review record")
        return self


class AssumptionRecord(StrictFrozenModel):
    """Explicit assumption with owner, basis, sensitivity and replacement action."""

    assumption_id: Identifier
    statement: NonEmptyText
    owner_actor_id: Identifier
    basis: NonEmptyText
    materiality: Materiality
    sensitivity: NonEmptyText
    affected_claim_ids: tuple[Identifier, ...]
    affected_section_ids: tuple[Identifier, ...]
    approval_decision_id: Identifier | None = None
    review_date: date
    replacement_action: NonEmptyText


class JudgementRecord(StrictFrozenModel):
    """Professional/model judgement kept distinct from sourced fact and assumption."""

    judgement_id: Identifier
    statement: NonEmptyText
    actor_id: Identifier
    basis: NonEmptyText
    alternatives_considered: tuple[NonEmptyText, ...]
    affected_claim_ids: tuple[Identifier, ...]
    affected_section_ids: tuple[Identifier, ...]
    review_ids: tuple[Identifier, ...] = ()


class DerivationRecord(StrictFrozenModel):
    """Typed transformation chain from input/source to current-run output."""

    derivation_id: Identifier
    method_contract: NonEmptyText
    method_version: NonEmptyText
    input_ids: tuple[Identifier, ...]
    source_ids: tuple[Identifier, ...] = ()
    assumption_ids: tuple[Identifier, ...] = ()
    derived_input_ids: tuple[Identifier, ...] = ()
    output_ids: tuple[Identifier, ...]
    validation_ids: tuple[Identifier, ...]
    precision_policy: NonEmptyText

    @model_validator(mode="after")
    def _derivation_has_operands_and_result(self) -> DerivationRecord:
        if not self.input_ids and not self.source_ids:
            raise ValueError("derivation requires input_ids or source_ids")
        if not self.derived_input_ids and not self.output_ids:
            raise ValueError("derivation requires a derived input or output")
        return self


class LimitationRecord(StrictFrozenModel):
    """Known limitation, consequence, grade ceiling, owner and remedy."""

    limitation_id: Identifier
    statement: NonEmptyText
    materiality: Materiality
    affected_claim_ids: tuple[Identifier, ...]
    affected_section_ids: tuple[Identifier, ...]
    consequence: NonEmptyText
    grade_ceiling: AchievedGrade
    owner_actor_id: Identifier
    remedy: NonEmptyText
    target_date_or_gate: NonEmptyText | None = None


class ErrorRecord(StrictFrozenModel):
    """CASPER-compatible actionable error without leaking sensitive technical detail."""

    error_id: Identifier
    code: Identifier
    capability_id: Identifier
    section_ids: tuple[Identifier, ...]
    safe_user_message: NonEmptyText
    technical_cause_reference: NonEmptyText
    remedy: NonEmptyText
    partial_output_valid: bool
    consequence: NonEmptyText
    grade_ceiling: AchievedGrade
    release_blocking: bool


class ReviewFindingRecord(StrictFrozenModel):
    """A review finding and its controlled disposition."""

    finding_id: Identifier
    status: FindingStatus
    statement: NonEmptyText
    affected_claim_ids: tuple[Identifier, ...]
    affected_section_ids: tuple[Identifier, ...]
    response: NonEmptyText | None = None
    decision_id: Identifier | None = None

    @model_validator(mode="after")
    def _closed_finding_is_dispositioned(self) -> ReviewFindingRecord:
        if self.status is FindingStatus.CLOSED and (
            self.response is None or self.decision_id is None
        ):
            raise ValueError("closed finding requires response and decision_id")
        return self


class ReviewRecord(StrictFrozenModel):
    """Review scope, method, independence, findings and signed-decision reference."""

    review_id: Identifier
    reviewer_actor_id: Identifier
    independence_status: IndependenceStatus
    scope: NonEmptyText
    subject_binding: SubjectBinding
    method: NonEmptyText
    finding_ids: tuple[Identifier, ...]
    response: NonEmptyText
    signed_decision_id: Identifier | None = None
    completed_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _completed_review_is_signed(self) -> ReviewRecord:
        if self.completed_at is not None and self.signed_decision_id is None:
            raise ValueError("completed review requires signed_decision_id")
        if self.completed_at is None and self.signed_decision_id is not None:
            raise ValueError("incomplete review cannot carry a signed decision")
        return self


class DecisionRecord(StrictFrozenModel):
    """Named decision and authority; never inferred from a calculation or CI result."""

    decision_id: Identifier
    kind: DecisionKind
    outcome: DecisionOutcome
    authority_actor_id: Identifier
    authority_basis: NonEmptyText
    scope: NonEmptyText
    subject_binding: SubjectBinding
    decision: NonEmptyText
    grade: AssessmentGrade | None = None
    conditions: tuple[NonEmptyText, ...]
    evidence_ids: tuple[Identifier, ...]
    decided_at: UtcDateTime
    supersedes_decision_id: Identifier | None = None

    @model_validator(mode="after")
    def _grade_decision_is_typed(self) -> DecisionRecord:
        if self.kind in {DecisionKind.GRADE, DecisionKind.PACK_ASSURANCE}:
            if self.grade is None:
                raise ValueError("grade/pack-assurance decision requires a grade")
        elif self.grade is not None:
            raise ValueError("only grade/pack-assurance decisions may carry grade")
        if self.kind is DecisionKind.PACK_ASSURANCE and not isinstance(
            self.subject_binding, PackVersionSubjectBinding
        ):
            raise ValueError(
                "pack-assurance decision requires exact pack-version binding"
            )
        if self.kind not in {
            DecisionKind.PACK_ASSURANCE,
            DecisionKind.REVIEW,
        } and isinstance(self.subject_binding, PackVersionSubjectBinding):
            raise ValueError(
                "only pack-assurance/review decisions may use pack-version binding"
            )
        return self


class ReconciliationRecord(StrictFrozenModel):
    """Cross-section consistency result and exact compared values."""

    reconciliation_id: Identifier
    family: ReconciliationFamily
    name: NonEmptyText
    status: ReconciliationStatus
    section_ids: tuple[Identifier, ...]
    output_ids: tuple[Identifier, ...]
    tolerance: CanonicalValue | None = None
    detail: NonEmptyText
    limitation_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def _failed_reconciliation_has_limitation(self) -> ReconciliationRecord:
        if self.status is ReconciliationStatus.FAILED and not self.limitation_ids:
            raise ValueError("failed reconciliation requires a limitation record")
        if self.status in {
            ReconciliationStatus.PASSED,
            ReconciliationStatus.FAILED,
        } and (len(set(self.section_ids)) < 2 or len(set(self.output_ids)) < 2):
            raise ValueError(
                "passed/failed reconciliation requires at least two distinct sections and outputs"
            )
        if self.status is ReconciliationStatus.NOT_APPLICABLE and (
            self.section_ids or self.output_ids or self.limitation_ids
        ):
            raise ValueError(
                "not-applicable reconciliation forbids operands and limitations"
            )
        return self


class ValidationRecord(StrictFrozenModel):
    """Minimum structured receipt for a validation/pre-flight check."""

    validation_id: Identifier
    name: NonEmptyText
    status: ValidationStatus
    checked_at: UtcDateTime
    detail: NonEmptyText


class RunManifest(StrictFrozenModel):
    """Reproducibility identity for the material run basis (not canonical hashing)."""

    report_id: Identifier
    project_id: Identifier
    case_id: Identifier
    run_id: Identifier
    schema_id: Literal["dutchbay.feasibility_report_package.v1"] = (
        FEASIBILITY_REPORT_SCHEMA_ID
    )
    contract_version: Literal["1.0.0"] = FEASIBILITY_REPORT_CONTRACT_VERSION
    engine_version: NonEmptyText
    code_commit: GitCommit
    dirty_worktree: bool
    resolved_config_digest: Digest
    pack_ids: tuple[Identifier, ...]
    input_ids: tuple[Identifier, ...]
    source_ids: tuple[Identifier, ...]
    assumption_ids: tuple[Identifier, ...]
    capability_ids: tuple[Identifier, ...]
    environment: tuple[NonEmptyText, ...]
    dependency_versions: tuple[NonEmptyText, ...]
    deterministic_seeds: tuple[NonNegativeInt, ...] = ()
    external_snapshot_ids: tuple[Identifier, ...] = ()
    validation_ids: tuple[Identifier, ...]
    reconciliation_ids: tuple[Identifier, ...]
    created_at: UtcDateTime
    valuation_date: date
    evidence_cutoff: date
    report_issue: PositiveInt
    report_revision: NonNegativeInt
    payload_digest: Digest | None = None


class ArtifactDisclosureBinding(StrictFrozenModel):
    """Structured treatment of one source in one delivery artifact."""

    artifact_id: Identifier
    source_id: Identifier
    action: DisclosureAction
    reason: NonEmptyText
    validation_id: Identifier | None = None

    @model_validator(mode="after")
    def _controlled_transformation_is_validated(self) -> ArtifactDisclosureBinding:
        if (
            self.action
            in {
                DisclosureAction.REDACT,
                DisclosureAction.OMIT,
                DisclosureAction.REFERENCE_ONLY,
            }
            and self.validation_id is None
        ):
            raise ValueError(
                "redact/omit/reference-only disclosure requires validation_id"
            )
        return self


class ArtifactRecord(StrictFrozenModel):
    """Delivery artifact identity and disclosure profile."""

    artifact_id: Identifier
    report_id: Identifier
    run_id: Identifier
    format: ArtifactFormat
    mime_type: NonEmptyText
    producer: NonEmptyText
    producer_version: NonEmptyText
    created_at: UtcDateTime
    content_digest: Digest
    completeness_profile: NonEmptyText
    is_full_package: bool
    source_ids: tuple[Identifier, ...]
    disclosure_exceptions: tuple[NonEmptyText, ...]
    confidentiality: ConfidentialityClass
    supersedes_artifact_id: Identifier | None = None


class DistributionControl(StrictFrozenModel):
    """Audience, reliance, rights, expiry and redaction controls."""

    distribution_id: Identifier
    artifact_ids: tuple[Identifier, ...]
    intended_audiences: tuple[NonEmptyText, ...]
    permitted_uses: tuple[NonEmptyText, ...]
    permitted_reliance: NonEmptyText
    distribution_class: ConfidentialityClass
    confidentiality: NonEmptyText
    publication_rights: NonEmptyText
    reliance_exclusions: tuple[NonEmptyText, ...]
    expiry_or_review_date: date
    redaction_policy: NonEmptyText
    disclosure_bindings: tuple[ArtifactDisclosureBinding, ...] = ()

    @model_validator(mode="after")
    def _distribution_scope_is_explicit(self) -> DistributionControl:
        if not self.intended_audiences or not self.permitted_uses:
            raise ValueError(
                "distribution control requires intended audiences and permitted uses"
            )
        return self


class PackageRelease(StrictFrozenModel):
    """Final hold/authorization bound to exact report, artifacts and controls."""

    status: PackageReleaseStatus = PackageReleaseStatus.HOLD
    report_id: Identifier
    artifact_ids: tuple[Identifier, ...]
    distribution_ids: tuple[Identifier, ...] = ()
    scope: NonEmptyText
    conditions: tuple[NonEmptyText, ...]
    authority_actor_id: Identifier | None = None
    decision_id: Identifier | None = None
    decided_at: UtcDateTime | None = None
    reason: NonEmptyText

    @model_validator(mode="after")
    def _authorization_is_explicit(self) -> PackageRelease:
        if self.status is PackageReleaseStatus.AUTHORIZED and (
            self.authority_actor_id is None
            or self.decision_id is None
            or self.decided_at is None
            or not self.artifact_ids
            or not self.distribution_ids
        ):
            raise ValueError(
                "authorized package requires authority, decision, date, artifact and distribution binding"
            )
        if self.status is PackageReleaseStatus.HOLD:
            if any(
                item is not None
                for item in (self.authority_actor_id, self.decision_id, self.decided_at)
            ):
                raise ValueError(
                    "held package forbids release authority, decision and decided_at metadata"
                )
            if self.distribution_ids:
                raise ValueError("held package forbids release distribution bindings")
        if len(self.distribution_ids) != len(set(self.distribution_ids)):
            raise ValueError("package release contains duplicate distribution_ids")
        return self


class CapabilityBase(StrictFrozenModel):
    """Fields common to every discriminated capability disposition."""

    capability_id: Identifier
    section_ids: tuple[Identifier, ...]
    owning_contract: NonEmptyText
    implementation_version: NonEmptyText
    activation_predicate: NonEmptyText
    pack_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _has_pack_and_section_bindings(self) -> CapabilityBase:
        if not self.section_ids or not self.pack_ids:
            raise ValueError("capability requires section_ids and pack_ids")
        return self


class ExecutedCapability(CapabilityBase):
    """Capability executed on its canonical path for this run."""

    outcome: Literal[CapabilityOutcome.EXECUTED] = CapabilityOutcome.EXECUTED
    output_ids: tuple[Identifier, ...]

    @model_validator(mode="after")
    def _has_output(self) -> ExecutedCapability:
        if not self.output_ids:
            raise ValueError("executed capability requires output_ids")
        return self


class DegradedCapability(CapabilityBase):
    """Sanctioned substitute with persistent warning and grade ceiling."""

    outcome: Literal[CapabilityOutcome.DEGRADED] = CapabilityOutcome.DEGRADED
    failed_path: NonEmptyText
    sanctioned_substitute: NonEmptyText
    warning: NonEmptyText
    limitation_id: Identifier
    error_id: Identifier | None = None
    output_ids: tuple[Identifier, ...]
    grade_ceiling: AchievedGrade


class FailedCapability(CapabilityBase):
    """Capability failed without exposing stale output as current output."""

    outcome: Literal[CapabilityOutcome.FAILED] = CapabilityOutcome.FAILED
    error_id: Identifier


class MissingInputCapability(CapabilityBase):
    """Capability did not run because named inputs were absent or invalid."""

    outcome: Literal[CapabilityOutcome.NOT_RUN_MISSING_INPUT] = (
        CapabilityOutcome.NOT_RUN_MISSING_INPUT
    )
    missing_input_ids: tuple[Identifier, ...]
    consequence: NonEmptyText
    remedy: NonEmptyText

    @model_validator(mode="after")
    def _has_missing_input(self) -> MissingInputCapability:
        if not self.missing_input_ids:
            raise ValueError("missing-input disposition requires missing_input_ids")
        return self


class MissingDependencyCapability(CapabilityBase):
    """Capability did not run because a named dependency was unavailable."""

    outcome: Literal[CapabilityOutcome.NOT_RUN_MISSING_DEPENDENCY] = (
        CapabilityOutcome.NOT_RUN_MISSING_DEPENDENCY
    )
    dependency: NonEmptyText
    error_id: Identifier
    consequence: NonEmptyText
    remedy: NonEmptyText


class UnsupportedJurisdictionCapability(CapabilityBase):
    """Capability is unavailable for the explicit jurisdiction scope."""

    outcome: Literal[CapabilityOutcome.NOT_RUN_UNSUPPORTED_JURISDICTION] = (
        CapabilityOutcome.NOT_RUN_UNSUPPORTED_JURISDICTION
    )
    jurisdiction: JurisdictionCode
    pack_id: Identifier
    consequence: NonEmptyText
    remedy: NonEmptyText


class UnsupportedTechnologyCapability(CapabilityBase):
    """Capability is unavailable for the explicit technology scope."""

    outcome: Literal[CapabilityOutcome.NOT_RUN_UNSUPPORTED_TECHNOLOGY] = (
        CapabilityOutcome.NOT_RUN_UNSUPPORTED_TECHNOLOGY
    )
    technology_id: Identifier
    pack_id: Identifier
    consequence: NonEmptyText
    remedy: NonEmptyText


class DeferredCapability(CapabilityBase):
    """Intentional deferral authorized by a named decision and future gate."""

    outcome: Literal[CapabilityOutcome.INTENTIONALLY_DEFERRED] = (
        CapabilityOutcome.INTENTIONALLY_DEFERRED
    )
    decision_id: Identifier
    owner_actor_id: Identifier
    reason: NonEmptyText
    target_date_or_gate: NonEmptyText
    consequence: NonEmptyText


class NotApplicableCapability(CapabilityBase):
    """Capability outside the declared project scope, with an approval basis."""

    outcome: Literal[CapabilityOutcome.NOT_APPLICABLE] = (
        CapabilityOutcome.NOT_APPLICABLE
    )
    reason: NonEmptyText
    decision_id: Identifier


CapabilityDisposition = Annotated[
    Union[
        ExecutedCapability,
        DegradedCapability,
        FailedCapability,
        MissingInputCapability,
        MissingDependencyCapability,
        UnsupportedJurisdictionCapability,
        UnsupportedTechnologyCapability,
        DeferredCapability,
        NotApplicableCapability,
    ],
    Field(discriminator="outcome"),
]


class SectionRecord(StrictFrozenModel):
    """All seven orthogonal truths and traceability for one canonical section."""

    section_id: Identifier
    section_contract_version: Literal["1.0.0"] = SECTION_CONTRACT_VERSION
    applicability: Applicability
    applicability_reason: NonEmptyText
    production_status: ProductionStatus
    evidence_status: EvidenceStatus
    review_status: ReviewStatus
    release_status: SectionReleaseStatus
    target_grade: AssessmentGrade
    achieved_grade: SectionAchievedGrade = SectionAchievedGrade.UNGRADED
    materiality: Materiality
    summary: NonEmptyText
    output_references: tuple[Identifier, ...]
    required_inputs: tuple[Identifier, ...]
    resolved_inputs: tuple[Identifier, ...]
    derived_inputs: tuple[Identifier, ...]
    capability_dispositions: tuple[Identifier, ...]
    jurisdiction_pack_ids: tuple[Identifier, ...]
    technology_pack_ids: tuple[Identifier, ...]
    source_ids: tuple[Identifier, ...]
    claim_ids: tuple[Identifier, ...]
    evidence_ids: tuple[Identifier, ...]
    assumption_ids: tuple[Identifier, ...]
    judgement_ids: tuple[Identifier, ...]
    limitation_ids: tuple[Identifier, ...]
    error_ids: tuple[Identifier, ...]
    review_ids: tuple[Identifier, ...]
    decision_ids: tuple[Identifier, ...]
    started_at: UtcDateTime | None = None
    completed_at: UtcDateTime | None = None

    @field_validator("section_id")
    @classmethod
    def _known_section_id(cls, value: str) -> str:
        if value not in load_feasibility_taxonomy().section_names:
            raise ValueError(
                "section_id is not present in the feasibility taxonomy SSOT"
            )
        return value

    @model_validator(mode="after")
    def _validate_state_axes(self) -> SectionRecord:
        is_na = self.applicability is Applicability.NOT_APPLICABLE
        if is_na:
            if self.production_status is not ProductionStatus.NOT_REQUIRED_BY_SCOPE:
                raise ValueError("not-applicable section must be not_required_by_scope")
            if self.evidence_status is not EvidenceStatus.NOT_REQUIRED:
                raise ValueError("not-applicable section evidence must be not_required")
            if self.review_status is not ReviewStatus.NOT_REQUIRED:
                raise ValueError("not-applicable section review must be not_required")
            if self.release_status is not SectionReleaseStatus.NOT_APPLICABLE:
                raise ValueError(
                    "not-applicable section release must be not_applicable"
                )
            if self.achieved_grade is not SectionAchievedGrade.NOT_APPLICABLE:
                raise ValueError("not-applicable section grade must be not_applicable")
            if not self.decision_ids:
                raise ValueError(
                    "not-applicable section requires approval decision_ids"
                )
            incompatible_material = {
                "output_references": self.output_references,
                "required_inputs": self.required_inputs,
                "resolved_inputs": self.resolved_inputs,
                "derived_inputs": self.derived_inputs,
                "source_ids": self.source_ids,
                "claim_ids": self.claim_ids,
                "evidence_ids": self.evidence_ids,
                "assumption_ids": self.assumption_ids,
                "judgement_ids": self.judgement_ids,
                "limitation_ids": self.limitation_ids,
                "error_ids": self.error_ids,
                "review_ids": self.review_ids,
            }
            present = sorted(
                name for name, values in incompatible_material.items() if values
            )
            if present:
                raise ValueError(
                    "not-applicable section forbids current production material: "
                    f"{present}"
                )
            if self.started_at is not None or self.completed_at is not None:
                raise ValueError("not-applicable section forbids production timestamps")
        else:
            if self.production_status is ProductionStatus.NOT_REQUIRED_BY_SCOPE:
                raise ValueError("not_required_by_scope is exclusive to not_applicable")
            if self.achieved_grade is SectionAchievedGrade.NOT_APPLICABLE:
                raise ValueError(
                    "applicable/undetermined section cannot have N/A grade"
                )
            if self.release_status is SectionReleaseStatus.NOT_APPLICABLE:
                raise ValueError(
                    "applicable/undetermined section cannot have N/A release"
                )

        if self.production_status is ProductionStatus.COMPLETE:
            if (
                not self.output_references
                or not self.capability_dispositions
                or set(self.required_inputs) != set(self.resolved_inputs)
            ):
                raise ValueError(
                    "complete section requires outputs, capabilities and all required inputs resolved"
                )
        elif self.production_status is ProductionStatus.COMPLETE_WITH_LIMITATIONS:
            if not self.output_references or not self.limitation_ids:
                raise ValueError(
                    "complete_with_limitations requires output and explicit limitations"
                )
        elif self.production_status is ProductionStatus.NOT_RUN_MISSING_INPUT:
            if not self.required_inputs or set(self.required_inputs) <= set(
                self.resolved_inputs
            ):
                raise ValueError(
                    "missing-input state requires an unresolved required input"
                )
        elif self.production_status is ProductionStatus.FAILED:
            if not self.error_ids or self.output_references:
                raise ValueError(
                    "failed section requires errors and forbids current outputs"
                )
        elif self.production_status is ProductionStatus.DEGRADED:
            if not self.limitation_ids or not self.capability_dispositions:
                raise ValueError(
                    "degraded section requires limitation and capability disposition"
                )
        elif self.production_status is ProductionStatus.INTENTIONALLY_DEFERRED:
            if not self.decision_ids or not self.limitation_ids:
                raise ValueError(
                    "deferred section requires authority decision and limitation"
                )

        if (
            self.evidence_status
            in {
                EvidenceStatus.LIMITED,
                EvidenceStatus.MISSING,
                EvidenceStatus.SYNTHETIC_ONLY,
                EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
            }
            and not self.evidence_ids
        ):
            raise ValueError(
                "limited/missing/synthetic/held evidence requires evidence_ids"
            )
        if (
            self.review_status
            in {
                ReviewStatus.SELF_CHECKED,
                ReviewStatus.INDEPENDENT_REVIEW_PENDING,
                ReviewStatus.INDEPENDENT_REVIEW_COMPLETED_WITH_FINDINGS,
                ReviewStatus.INDEPENDENTLY_ACCEPTED,
            }
            and not self.review_ids
        ):
            raise ValueError(
                "self/pending/completed/accepted review requires review_ids"
            )
        if (
            self.release_status is SectionReleaseStatus.AUTHORIZED
            and not self.decision_ids
        ):
            raise ValueError("authorized section requires a decision record")
        if (self.started_at is None) != (self.completed_at is None):
            raise ValueError("section timestamps must be both present or both absent")
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at cannot precede started_at")
        return self


class ActorRegister(StrictFrozenModel):
    records: tuple[ActorRecord, ...]


class ResponsibilityRegister(StrictFrozenModel):
    records: tuple[ResponsibilityAssignment, ...]


class PackRegistry(StrictFrozenModel):
    records: tuple[PackBinding, ...]


class CapabilityRegistry(StrictFrozenModel):
    records: tuple[CapabilityDisposition, ...]


class InputRegister(StrictFrozenModel):
    records: tuple[InputRecord, ...]


class SourceRegister(StrictFrozenModel):
    records: tuple[SourceRecord, ...]


class OutputRegister(StrictFrozenModel):
    records: tuple[OutputReference, ...]


class ClaimRegister(StrictFrozenModel):
    records: tuple[ClaimRecord, ...]


class EvidenceRegister(StrictFrozenModel):
    records: tuple[EvidenceRecord, ...]


class AssumptionRegister(StrictFrozenModel):
    records: tuple[AssumptionRecord, ...]


class JudgementRegister(StrictFrozenModel):
    records: tuple[JudgementRecord, ...]


class DerivationRegister(StrictFrozenModel):
    records: tuple[DerivationRecord, ...]


class LimitationRegister(StrictFrozenModel):
    records: tuple[LimitationRecord, ...]


class ErrorRegister(StrictFrozenModel):
    records: tuple[ErrorRecord, ...]


class ReviewFindingRegister(StrictFrozenModel):
    records: tuple[ReviewFindingRecord, ...]


class ReviewRegister(StrictFrozenModel):
    records: tuple[ReviewRecord, ...]


class DecisionRegister(StrictFrozenModel):
    records: tuple[DecisionRecord, ...]


class ReconciliationRegister(StrictFrozenModel):
    records: tuple[ReconciliationRecord, ...]


class ValidationRegister(StrictFrozenModel):
    records: tuple[ValidationRecord, ...]


class ArtifactManifest(StrictFrozenModel):
    records: tuple[ArtifactRecord, ...]


class DistributionRegister(StrictFrozenModel):
    records: tuple[DistributionControl, ...]


__all__ = [
    "UtcDateTime",
    "Digest",
    "CanonicalValue",
    "ReportIdentity",
    "ScopeDeclaration",
    "JurisdictionSubjectBinding",
    "ActorRecord",
    "ReportSubjectBinding",
    "PackVersionSubjectBinding",
    "SubjectBinding",
    "ResponsibilityAssignment",
    "PackInputDefault",
    "PackEvidenceMinimum",
    "PackBinding",
    "InputRecord",
    "SourceLocator",
    "SourceRecord",
    "OutputReference",
    "ClaimRecord",
    "EvidenceRecord",
    "AssumptionRecord",
    "JudgementRecord",
    "DerivationRecord",
    "LimitationRecord",
    "ErrorRecord",
    "ReviewFindingRecord",
    "ReviewRecord",
    "DecisionRecord",
    "ReconciliationRecord",
    "ValidationRecord",
    "RunManifest",
    "ArtifactDisclosureBinding",
    "ArtifactRecord",
    "DistributionControl",
    "PackageRelease",
    "CapabilityBase",
    "ExecutedCapability",
    "DegradedCapability",
    "FailedCapability",
    "MissingInputCapability",
    "MissingDependencyCapability",
    "UnsupportedJurisdictionCapability",
    "UnsupportedTechnologyCapability",
    "DeferredCapability",
    "NotApplicableCapability",
    "CapabilityDisposition",
    "SectionRecord",
    "ActorRegister",
    "ResponsibilityRegister",
    "PackRegistry",
    "CapabilityRegistry",
    "InputRegister",
    "SourceRegister",
    "OutputRegister",
    "ClaimRegister",
    "EvidenceRegister",
    "AssumptionRegister",
    "JudgementRegister",
    "DerivationRegister",
    "LimitationRegister",
    "ErrorRegister",
    "ReviewFindingRegister",
    "ReviewRegister",
    "DecisionRegister",
    "ReconciliationRegister",
    "ValidationRegister",
    "ArtifactManifest",
    "DistributionRegister",
]
