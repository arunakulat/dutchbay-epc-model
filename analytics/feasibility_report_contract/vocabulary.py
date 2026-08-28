"""Strict vocabulary for the global feasibility-report package contract.

The tokens in this module implement DBAY-FRC-001 v1.0.0.  They intentionally keep
run posture, applicability, production, evidence, review, assessment grade, and
release authority orthogonal.  Section identities are *not* declared here: the
only source of those identities and their order remains
``config/feasibility_sections.yaml`` through
``analytics.feasibility_sections.load_feasibility_taxonomy``.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

FEASIBILITY_REPORT_SCHEMA_ID: Literal["dutchbay.feasibility_report_package.v1"] = (
    "dutchbay.feasibility_report_package.v1"
)
FEASIBILITY_REPORT_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
SECTION_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256Hex = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
]
GitCommit = Annotated[
    str, StringConstraints(pattern=r"^[0-9a-f]{7,64}$", min_length=7, max_length=64)
]
SemanticVersion = Annotated[
    str,
    StringConstraints(
        pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
    ),
]
CurrencyCode = Annotated[
    str, StringConstraints(pattern=r"^[A-Z]{3}$", min_length=3, max_length=3)
]
UnitToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9%][A-Za-z0-9%._/*^()\-]*$",
    ),
]
JurisdictionCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=2,
        max_length=32,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    ),
]


class StrictFrozenModel(BaseModel):
    """Base for deeply immutable report contracts.

    Child models use tuples and other frozen child models for collections.  Pydantic's
    ``frozen`` setting alone is only shallow, so mutable list/dict fields are prohibited
    from this new public contract surface.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )


class Applicability(str, Enum):
    """Whether a section belongs to the declared project scope."""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNDETERMINED = "undetermined"


class ProductionStatus(str, Enum):
    """What happened when the section's governed production path was considered."""

    COMPLETE = "complete"
    COMPLETE_WITH_LIMITATIONS = "complete_with_limitations"
    NOT_REQUIRED_BY_SCOPE = "not_required_by_scope"
    NOT_RUN_MISSING_INPUT = "not_run_missing_input"
    NOT_RUN_MISSING_DEPENDENCY = "not_run_missing_dependency"
    NOT_RUN_UNSUPPORTED_JURISDICTION = "not_run_unsupported_jurisdiction"
    NOT_RUN_UNSUPPORTED_TECHNOLOGY = "not_run_unsupported_technology"
    FAILED = "failed"
    DEGRADED = "degraded"
    INTENTIONALLY_DEFERRED = "intentionally_deferred"


class EvidenceStatus(str, Enum):
    """Sufficiency of evidence for the section's achieved-grade claim."""

    NOT_REQUIRED = "not_required"
    SUFFICIENT_FOR_ACHIEVED_GRADE = "sufficient_for_achieved_grade"
    LIMITED = "limited"
    MISSING = "missing"
    SYNTHETIC_ONLY = "synthetic_only"
    EXTERNAL_EVIDENCE_HOLD = "external_evidence_hold"


class ReviewStatus(str, Enum):
    """Review state, separate from production and release."""

    NOT_REQUIRED = "not_required"
    NOT_REVIEWED = "not_reviewed"
    SELF_CHECKED = "self_checked"
    INDEPENDENT_REVIEW_PENDING = "independent_review_pending"
    INDEPENDENT_REVIEW_COMPLETED_WITH_FINDINGS = (
        "independent_review_completed_with_findings"
    )
    INDEPENDENTLY_ACCEPTED = "independently_accepted"


class SectionReleaseStatus(str, Enum):
    """Section-local release state; never package-release authority."""

    NOT_APPLICABLE = "not_applicable"
    HOLD = "hold"
    AUTHORIZED = "authorized"


class PackageReleaseStatus(str, Enum):
    """Final package distribution state."""

    HOLD = "hold"
    AUTHORIZED = "authorized"


class AssessmentGrade(str, Enum):
    """A requested/target assessment grade."""

    ILLUSTRATIVE = "illustrative"
    SCREENING = "screening"
    DECISION_GRADE = "decision_grade"
    LENDER_GRADE = "lender_grade"


class AchievedGrade(str, Enum):
    """A report-level achieved grade, including the fail-closed sentinel."""

    UNGRADED = "ungraded"
    ILLUSTRATIVE = "illustrative"
    SCREENING = "screening"
    DECISION_GRADE = "decision_grade"
    LENDER_GRADE = "lender_grade"


class SectionAchievedGrade(str, Enum):
    """Section-level grade, including its dedicated N/A sentinel."""

    NOT_APPLICABLE = "not_applicable"
    UNGRADED = "ungraded"
    ILLUSTRATIVE = "illustrative"
    SCREENING = "screening"
    DECISION_GRADE = "decision_grade"
    LENDER_GRADE = "lender_grade"


class Materiality(str, Enum):
    """Whether an item participates in report-level blocker assessment."""

    MATERIAL = "material"
    NON_MATERIAL = "non_material"


class PackKind(str, Enum):
    """Pack contribution boundary."""

    JURISDICTION = "jurisdiction"
    TECHNOLOGY = "technology"


class GovernedSubjectKind(str, Enum):
    """Project-level subject to which a jurisdictional rule set applies."""

    PROJECT = "project"
    SITE = "site"
    GRID_CONNECTION = "grid_connection"
    LEGAL_ENTITY = "legal_entity"
    OFFTAKE = "offtake"
    TAX = "tax"
    PERMIT = "permit"
    ENVIRONMENTAL_SOCIAL = "environmental_social"


class PackStatus(str, Enum):
    """Support/assurance state of a jurisdiction or technology pack."""

    UNSUPPORTED = "unsupported"
    SUPPORTED = "supported"
    ASSURED = "assured"


class CapabilityOutcome(str, Enum):
    """Discriminator vocabulary for capability dispositions."""

    EXECUTED = "executed"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_RUN_MISSING_INPUT = "not_run_missing_input"
    NOT_RUN_MISSING_DEPENDENCY = "not_run_missing_dependency"
    NOT_RUN_UNSUPPORTED_JURISDICTION = "not_run_unsupported_jurisdiction"
    NOT_RUN_UNSUPPORTED_TECHNOLOGY = "not_run_unsupported_technology"
    INTENTIONALLY_DEFERRED = "intentionally_deferred"
    NOT_APPLICABLE = "not_applicable"


class InputKind(str, Enum):
    """How an input entered the resolved report basis."""

    SUPPLIED = "supplied"
    ENRICHED = "enriched"
    RESOLVED = "resolved"
    DERIVED = "derived"


class InputResolutionStatus(str, Enum):
    """Whether an input requirement is usable by the current run."""

    RESOLVED = "resolved"
    MISSING = "missing"
    INVALID = "invalid"


class ValueType(str, Enum):
    """Lexical type of a canonical value; values remain precision-preserving text."""

    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"


class SourceClass(str, Enum):
    """DBAY-FRC-001 source classification."""

    AUTHENTICATED_PROJECT = "authenticated_project"
    OFFICIAL_PRIMARY = "official_primary"
    CONTRACTED = "contracted"
    VENDOR = "vendor"
    LICENSED = "licensed"
    BENCHMARK = "benchmark"
    DERIVED = "derived"
    ASSUMPTION = "assumption"
    SYNTHETIC = "synthetic"
    MISSING = "missing"


class AuthenticityStatus(str, Enum):
    """Authentication state of a source/evidence item."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    AUTHENTICATED = "authenticated"


class ActorKind(str, Enum):
    """Human and automated actors are deliberately distinct."""

    HUMAN = "human"
    INSTITUTION = "institution"
    SOFTWARE = "software"
    AI_AGENT = "ai_agent"


class ResponsibilityRole(str, Enum):
    """Controlled human document-responsibility roles."""

    PREPARED = "prepared"
    CHECKED = "checked"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class ResponsibilityStatus(str, Enum):
    """Whether a responsibility was performed for its stated scope."""

    PERFORMED = "performed"
    NOT_PERFORMED = "not_performed"
    NOT_REQUIRED = "not_required"


class IndependenceStatus(str, Enum):
    """Reviewer's relationship to the work under review."""

    NOT_ASSESSED = "not_assessed"
    INTERNAL = "internal"
    INDEPENDENT = "independent"


class FindingStatus(str, Enum):
    """Disposition of a review finding."""

    OPEN_BLOCKING = "open_blocking"
    OPEN_NON_BLOCKING = "open_non_blocking"
    CLOSED = "closed"


class DecisionKind(str, Enum):
    """Scope of authority represented by a decision record."""

    SCOPE = "scope"
    GRADE = "grade"
    REVIEW = "review"
    PACK_ASSURANCE = "pack_assurance"
    RELEASE = "release"
    WAIVER = "waiver"
    OTHER = "other"


class DecisionOutcome(str, Enum):
    """Typed decision disposition; prose cannot silently reverse this outcome."""

    APPROVED = "approved"
    ACCEPTED = "accepted"
    AUTHORIZED = "authorized"
    RECORDED = "recorded"
    DENIED = "denied"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class SubjectKind(str, Enum):
    """Authority/review subject classes with distinct exact-binding requirements."""

    REPORT_SECTIONS = "report_sections"
    PACK_VERSION = "pack_version"


class ReconciliationStatus(str, Enum):
    """Outcome of a cross-section or cross-artifact reconciliation."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ReconciliationFamily(str, Enum):
    """Intrinsic D1 section 8.2 reconciliation families."""

    PROJECT_BASIS = "project_basis"
    ENERGY = "energy"
    COST = "cost"
    REVENUE_TAX_CURRENCY = "revenue_tax_currency"
    DEBT = "debt"
    NON_FINANCIAL_GAPS = "non_financial_gaps"


class OutputClass(str, Enum):
    """Evidence boundary carried by a referenced output."""

    CANONICAL = "canonical"
    ADVISORY = "advisory"
    BENCHMARK = "benchmark"
    SYNTHETIC = "synthetic"


class ArtifactFormat(str, Enum):
    """Delivery projection formats governed by the package."""

    HTML = "html"
    DBPL_PDF = "dbpl_pdf"
    NON_DBPL_PDF = "non_dbpl_pdf"
    XLSX = "xlsx"
    JSON = "json"
    API = "api"
    OTHER = "other"


class ConfidentialityClass(str, Enum):
    """Distribution classification for reports and evidence references."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ValidationStatus(str, Enum):
    """Status of a recorded validation/pre-flight check."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class DisclosureAction(str, Enum):
    """Structured treatment of one source in one delivery artifact."""

    INCLUDE = "include"
    REDACT = "redact"
    OMIT = "omit"
    REFERENCE_ONLY = "reference_only"


__all__ = [
    "FEASIBILITY_REPORT_SCHEMA_ID",
    "FEASIBILITY_REPORT_CONTRACT_VERSION",
    "SECTION_CONTRACT_VERSION",
    "Identifier",
    "NonEmptyText",
    "Sha256Hex",
    "GitCommit",
    "SemanticVersion",
    "CurrencyCode",
    "UnitToken",
    "JurisdictionCode",
    "StrictFrozenModel",
    "Applicability",
    "ProductionStatus",
    "EvidenceStatus",
    "ReviewStatus",
    "SectionReleaseStatus",
    "PackageReleaseStatus",
    "AssessmentGrade",
    "AchievedGrade",
    "SectionAchievedGrade",
    "Materiality",
    "PackKind",
    "GovernedSubjectKind",
    "PackStatus",
    "CapabilityOutcome",
    "InputKind",
    "InputResolutionStatus",
    "ValueType",
    "SourceClass",
    "AuthenticityStatus",
    "ActorKind",
    "ResponsibilityRole",
    "ResponsibilityStatus",
    "IndependenceStatus",
    "FindingStatus",
    "DecisionKind",
    "DecisionOutcome",
    "SubjectKind",
    "ReconciliationStatus",
    "ReconciliationFamily",
    "OutputClass",
    "ArtifactFormat",
    "ConfidentialityClass",
    "ValidationStatus",
    "DisclosureAction",
]
