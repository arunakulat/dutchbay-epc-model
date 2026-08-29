"""Executable branch controls for the DBAY-FRC-001 machine contract.

These tests complement the adversarial scenario suite with narrow mutations of an
otherwise valid record or package.  Each mutation names the invariant it exercises;
none changes production semantics or treats test execution as assurance authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from analytics.feasibility_report_contract.package import FeasibilityReportPackage
from analytics.feasibility_report_contract.records import (
    ActorRecord,
    ArtifactDisclosureBinding,
    CanonicalValue,
    CapabilityBase,
    ClaimRecord,
    DecisionRecord,
    DerivationRecord,
    DistributionControl,
    EvidenceRecord,
    ExecutedCapability,
    JurisdictionSubjectBinding,
    MissingInputCapability,
    PackageRelease,
    PackBinding,
    PackInputDefault,
    PackVersionSubjectBinding,
    ReconciliationRecord,
    ResponsibilityAssignment,
    ReviewFindingRecord,
    ReviewRecord,
    ScopeDeclaration,
    SectionRecord,
    SourceLocator,
    SourceRecord,
)
from analytics.feasibility_report_contract.vocabulary import (
    AchievedGrade,
    ActorKind,
    Applicability,
    AssessmentGrade,
    CapabilityOutcome,
    ConfidentialityClass,
    DecisionKind,
    DisclosureAction,
    EvidenceStatus,
    FindingStatus,
    IndependenceStatus,
    InputKind,
    InputResolutionStatus,
    Materiality,
    OutputClass,
    PackageReleaseStatus,
    PackStatus,
    ProductionStatus,
    ReconciliationFamily,
    ReconciliationStatus,
    ResponsibilityRole,
    ResponsibilityStatus,
    ReviewStatus,
    SectionAchievedGrade,
    SectionReleaseStatus,
    SourceClass,
    SubjectKind,
    ValidationStatus,
    ValueType,
)
from tests.contracts.test_feasibility_report_machine_contract import (
    _DAY,
    _NOW,
    _artifact,
    _build_package,
    _first_applicable,
    _make_assured_lk_pack,
    _payload,
)


def _rejects(
    model: type[BaseModel], payload: dict[str, Any], match: str | None
) -> ValidationError:
    """Validate one deliberately invalid record and return its typed failure."""
    with pytest.raises(ValidationError, match=match) as captured:
        model.model_validate(payload)
    return captured.value


@pytest.mark.parametrize(
    ("value_type", "value", "unit", "precision", "match"),
    [
        (ValueType.DECIMAL, "not-a-number", "1", None, "invalid lexical"),
        (ValueType.DATETIME, "not-a-datetime", None, None, "ISO 8601"),
        (ValueType.BOOLEAN, "true", None, 1, "precision is valid only"),
    ],
)
def test_canonical_value_rejects_unparseable_or_incoherent_lexemes(
    value_type: ValueType,
    value: str,
    unit: str | None,
    precision: int | None,
    match: str,
) -> None:
    with pytest.raises(ValidationError, match=match):
        CanonicalValue(
            value_type=value_type, value=value, unit=unit, precision=precision
        )


@pytest.mark.parametrize("case", ["audience", "pack"])
def test_scope_requires_delivery_and_pack_boundaries(case: str) -> None:
    payload = _payload(_build_package())["scope"]
    if case == "audience":
        payload["intended_audiences"] = ()
    else:
        payload["jurisdiction_pack_ids"] = ()
    _rejects(ScopeDeclaration, payload, "scope requires")


def test_jurisdiction_subject_requires_named_contribution() -> None:
    payload = _payload(_build_package())["jurisdiction_subject_bindings"][0]
    payload["contribution_section_ids"] = ()
    _rejects(JurisdictionSubjectBinding, payload, "contribution_section_ids")


@pytest.mark.parametrize("kind", [ActorKind.SOFTWARE, ActorKind.HUMAN])
def test_actor_kind_requires_its_intrinsic_identity_fields(kind: ActorKind) -> None:
    payload = _payload(_build_package())["actor_register"]["records"][0]
    payload["kind"] = kind
    if kind is ActorKind.SOFTWARE:
        payload["version"] = None
        payload["operation"] = None
        match = "version and operation"
    else:
        payload["organization"] = None
        match = "require organization"
    _rejects(ActorRecord, payload, match)


def test_pack_version_subject_period_must_be_ordered() -> None:
    payload = {
        "pack_id": "pack:test",
        "pack_version": "1.0.0",
        "grade": AssessmentGrade.SCREENING,
        "effective_from": _DAY,
        "effective_until": _DAY - timedelta(days=1),
    }
    _rejects(PackVersionSubjectBinding, payload, "precedes")


def test_unperformed_responsibility_requires_reason() -> None:
    payload = {
        "assignment_id": "assignment:test",
        "role": ResponsibilityRole.PREPARED,
        "status": ResponsibilityStatus.NOT_PERFORMED,
        "scope": "Controlled test",
        "subject_binding": {
            "kind": SubjectKind.REPORT_SECTIONS,
            "report_id": "report:fixture",
            "run_id": "run:fixture",
        },
    }
    _rejects(ResponsibilityAssignment, payload, "requires a reason")


def test_pack_default_requires_source_provenance() -> None:
    payload = {
        "input_id": "input:test",
        "value": {"value_type": ValueType.INTEGER, "value": "1", "unit": "count"},
        "source_ids": (),
        "applicability_predicate": "Controlled test",
    }
    _rejects(PackInputDefault, payload, "source provenance")


@pytest.mark.parametrize(
    "case",
    [
        "jurisdiction_axis",
        "technology_axis",
        "contract_version",
        "empty_structure",
        "input_overlap",
        "undeclared_default",
        "foreign_default_source",
        "foreign_evidence_section",
        "empty_rules",
        "unsupported_grade",
        "supported_no_grade",
        "sentinel_grade",
        "incomplete_evidence_minima",
        "assured_no_authority",
    ],
)
def test_pack_binding_intrinsic_fail_closed_matrix(case: str) -> None:
    package = _payload(_build_package())
    jurisdiction = deepcopy(package["pack_registry"]["records"][0])
    technology = deepcopy(package["pack_registry"]["records"][1])
    payload = jurisdiction
    match = ""
    if case == "jurisdiction_axis":
        payload["technology_ids"] = ("wind",)
        match = "jurisdiction pack requires"
    elif case == "technology_axis":
        payload = technology
        payload["technology_ids"] = ()
        match = "technology pack requires"
    elif case == "contract_version":
        payload["compatible_contract_versions"] = ("9.9.9",)
        match = "not compatible"
    elif case == "empty_structure":
        payload["project_stages"] = ()
        match = "requires project stages"
    elif case == "input_overlap":
        payload["optional_input_ids"] = (payload["required_input_ids"][0],)
        match = "must be disjoint"
    elif case == "undeclared_default":
        payload["input_defaults"] = (
            {
                "input_id": "input:undeclared",
                "value": {
                    "value_type": ValueType.INTEGER,
                    "value": "1",
                    "unit": "count",
                },
                "source_ids": ("source:lk",),
                "applicability_predicate": "Controlled mutation",
            },
        )
        match = "undeclared input"
    elif case == "foreign_default_source":
        payload["input_defaults"] = (
            {
                "input_id": payload["required_input_ids"][0],
                "value": {
                    "value_type": ValueType.INTEGER,
                    "value": "1",
                    "unit": "count",
                },
                "source_ids": ("source:wind",),
                "applicability_predicate": "Controlled mutation",
            },
        )
        match = "source must be declared"
    elif case == "foreign_evidence_section":
        payload["evidence_minima"] = (
            {
                "section_id": "section:not-in-pack",
                "target_grade": AssessmentGrade.SCREENING,
                "requirement": "Controlled mutation",
            },
        )
        match = "unconstrained section"
    elif case == "empty_rules":
        payload["cross_field_rules"] = ()
        match = "cross-field rules"
    elif case == "unsupported_grade":
        payload["status"] = PackStatus.UNSUPPORTED
        match = "must not claim"
    elif case == "supported_no_grade":
        payload["grade_ceiling"] = None
        match = "requires grade ceiling"
    elif case == "sentinel_grade":
        payload["grade_ceiling"] = AchievedGrade.UNGRADED
        match = "non-sentinel"
    elif case == "incomplete_evidence_minima":
        payload["evidence_minima"] = payload["evidence_minima"][:1]
        match = "evidence minima for every section"
    else:
        payload["status"] = PackStatus.ASSURED
        match = "requires review and decision"
    _rejects(PackBinding, payload, match)


@pytest.mark.parametrize("case", ["resolved_without_value", "missing_without_remedy"])
def test_input_resolution_requires_value_or_recovery(case: str) -> None:
    payload = _payload(_build_package())["input_register"]["records"][0]
    if case == "resolved_without_value":
        payload["resolution_status"] = InputResolutionStatus.RESOLVED
        match = "requires resolved_value"
    else:
        payload["remedy"] = None
        match = "requires reason and remedy"
    from analytics.feasibility_report_contract.records import InputRecord

    _rejects(InputRecord, payload, match)


def test_source_locator_requires_a_real_location() -> None:
    _rejects(
        SourceLocator,
        {"url": None, "evidence_path": None, "pinpoint": "record 1"},
        "requires url or evidence_path",
    )


@pytest.mark.parametrize("case", ["sections", "quality"])
def test_source_requires_scope_and_quality(case: str) -> None:
    payload = _payload(_build_package())["source_register"]["records"][0]
    payload["section_ids" if case == "sections" else "quality_checks"] = ()
    _rejects(SourceRecord, payload, "source requires")


def test_synthetic_output_requires_persistent_warning() -> None:
    from analytics.feasibility_report_contract.records import OutputReference
    from analytics.feasibility_report_contract.vocabulary import OutputClass

    payload = {
        "output_id": "output:synthetic",
        "report_id": "report:fixture",
        "run_id": "run:fixture",
        "section_ids": ("resource_and_energy_yield",),
        "producing_contract": "contract:test",
        "producing_version": "1.0.0",
        "output_class": OutputClass.SYNTHETIC,
        "locator": "memory://fixture",
    }
    _rejects(OutputReference, payload, "persistent warning")


def test_claim_requires_evidence_disposition() -> None:
    payload = _payload(_build_package())["claim_register"]["records"][0]
    payload["evidence_ids"] = ()
    _rejects(ClaimRecord, payload, "evidence disposition")


@pytest.mark.parametrize(
    "case",
    ["nonmissing_without_source", "missing_without_request", "independent_no_review"],
)
def test_evidence_intrinsic_disposition_matrix(case: str) -> None:
    payload = _payload(_build_package())["evidence_register"]["records"][0]
    if case == "nonmissing_without_source":
        payload["sufficiency"] = EvidenceStatus.LIMITED
        payload["source_id"] = None
        match = "non-missing evidence requires source_id"
    elif case == "missing_without_request":
        payload["required_external_item"] = None
        match = "requires required_external_item"
    else:
        payload["independence_status"] = IndependenceStatus.INDEPENDENT
        payload["review_ids"] = ()
        match = "requires a review record"
    _rejects(EvidenceRecord, payload, match)


@pytest.mark.parametrize("case", ["operands", "result"])
def test_derivation_requires_operands_and_result(case: str) -> None:
    payload = {
        "derivation_id": "derivation:test",
        "method_contract": "contract:test",
        "method_version": "1.0.0",
        "input_ids": ("input:test",),
        "source_ids": (),
        "assumption_ids": (),
        "derived_input_ids": (),
        "output_ids": ("output:test",),
        "validation_ids": (),
        "precision_policy": "Preserve lexical precision",
    }
    if case == "operands":
        payload["input_ids"] = ()
        payload["source_ids"] = ()
        match = "requires input_ids or source_ids"
    else:
        payload["derived_input_ids"] = ()
        payload["output_ids"] = ()
        match = "requires a derived input or output"
    _rejects(DerivationRecord, payload, match)


def test_closed_review_finding_requires_disposition() -> None:
    payload = {
        "finding_id": "finding:test",
        "status": FindingStatus.CLOSED,
        "statement": "Controlled finding",
        "affected_claim_ids": (),
        "affected_section_ids": ("resource_and_energy_yield",),
    }
    _rejects(ReviewFindingRecord, payload, "requires response and decision_id")


@pytest.mark.parametrize("case", ["unsigned_complete", "signed_incomplete"])
def test_review_completion_and_signature_are_bijective(case: str) -> None:
    payload: dict[str, Any] = {
        "review_id": "review:test",
        "reviewer_actor_id": "actor:scope-authority",
        "independence_status": IndependenceStatus.INTERNAL,
        "scope": "Controlled test",
        "subject_binding": {
            "kind": SubjectKind.REPORT_SECTIONS,
            "report_id": "report:fixture",
            "run_id": "run:fixture",
        },
        "method": "Exact fixture review",
        "finding_ids": (),
        "response": "Controlled response",
    }
    if case == "unsigned_complete":
        payload["completed_at"] = _NOW
        match = "completed review requires"
    else:
        payload["signed_decision_id"] = "decision:review"
        match = "incomplete review cannot"
    _rejects(ReviewRecord, payload, match)


@pytest.mark.parametrize(
    "case", ["grade_missing", "grade_for_scope", "pack_assurance_report", "scope_pack"]
)
def test_decision_kind_controls_grade_and_subject(case: str) -> None:
    payload = _payload(_build_package())["decision_register"]["records"][0]
    if case == "grade_missing":
        payload["kind"] = DecisionKind.GRADE
        match = "requires a grade"
    elif case == "grade_for_scope":
        payload["grade"] = AssessmentGrade.SCREENING
        match = "only grade"
    elif case == "pack_assurance_report":
        payload["kind"] = DecisionKind.PACK_ASSURANCE
        payload["grade"] = AssessmentGrade.SCREENING
        match = "exact pack-version binding"
    else:
        payload["subject_binding"] = {
            "kind": "pack_version",
            "pack_id": "pack:lk",
            "pack_version": "1.0.0-fixture",
            "grade": AssessmentGrade.SCREENING,
            "effective_from": _DAY,
            "effective_until": _DAY,
        }
        match = "only pack-assurance/review"
    _rejects(DecisionRecord, payload, match)


def test_failed_reconciliation_requires_limitation() -> None:
    payload = {
        "reconciliation_id": "reconciliation:test",
        "family": ReconciliationFamily.ENERGY,
        "name": "Controlled failed reconciliation",
        "status": ReconciliationStatus.FAILED,
        "section_ids": ("resource_and_energy_yield", "base_case_financial_outputs"),
        "output_ids": ("output:a", "output:b"),
        "detail": "Mismatch",
        "limitation_ids": (),
    }
    _rejects(ReconciliationRecord, payload, "requires a limitation")


def test_redaction_binding_requires_validation_identity() -> None:
    payload = {
        "artifact_id": "artifact:test",
        "source_id": "source:test",
        "action": DisclosureAction.OMIT,
        "reason": "Publication restriction",
    }
    _rejects(ArtifactDisclosureBinding, payload, "requires validation_id")


def test_distribution_requires_audience_and_use() -> None:
    payload = _payload(_build_package())["distribution_register"]["records"][0]
    payload["intended_audiences"] = ()
    _rejects(DistributionControl, payload, "requires intended audiences")


def test_release_rejects_duplicate_distribution_bindings() -> None:
    payload = {
        "status": PackageReleaseStatus.AUTHORIZED,
        "report_id": "report:fixture",
        "artifact_ids": ("artifact:test",),
        "distribution_ids": ("distribution:test", "distribution:test"),
        "scope": "Controlled release",
        "conditions": (),
        "authority_actor_id": "actor:authority",
        "decision_id": "decision:release",
        "decided_at": _NOW,
        "reason": "Controlled test",
    }
    _rejects(PackageRelease, payload, "duplicate distribution_ids")


def test_capability_base_requires_section_and_pack_links() -> None:
    payload = {
        "capability_id": "cap:test",
        "section_ids": (),
        "owning_contract": "contract:test",
        "implementation_version": "1.0.0",
        "activation_predicate": "Controlled test",
        "pack_ids": ("pack:test",),
    }
    _rejects(CapabilityBase, payload, "requires section_ids and pack_ids")


def test_executed_and_missing_input_capabilities_require_payloads() -> None:
    common = {
        "capability_id": "cap:test",
        "section_ids": ("resource_and_energy_yield",),
        "owning_contract": "contract:test",
        "implementation_version": "1.0.0",
        "activation_predicate": "Controlled test",
        "pack_ids": ("pack:test",),
    }
    _rejects(ExecutedCapability, {**common, "output_ids": ()}, "requires output_ids")
    _rejects(
        MissingInputCapability,
        {
            **common,
            "missing_input_ids": (),
            "consequence": "No result",
            "remedy": "Supply input",
        },
        "requires missing_input_ids",
    )


@pytest.mark.parametrize(
    "case",
    [
        "na_production",
        "na_evidence",
        "na_review",
        "na_release",
        "na_grade",
        "na_decision",
        "na_timestamp",
        "applicable_na_production",
        "applicable_na_grade",
        "applicable_na_release",
        "complete",
        "complete_with_limits",
        "missing_input",
        "failed",
        "degraded",
        "deferred",
        "evidence_without_record",
        "review_without_record",
        "authorized_without_decision",
        "one_timestamp",
        "reversed_timestamps",
    ],
)
def test_section_axis_intrinsic_fail_closed_matrix(case: str) -> None:
    package = _payload(_build_package())
    applicable = deepcopy(_first_applicable(package))
    not_applicable = deepcopy(
        next(
            item
            for item in package["sections"]
            if item["applicability"] is Applicability.NOT_APPLICABLE
        )
    )
    payload = not_applicable if case.startswith("na_") else applicable
    if case == "na_production":
        payload["production_status"] = ProductionStatus.FAILED
    elif case == "na_evidence":
        payload["evidence_status"] = EvidenceStatus.MISSING
    elif case == "na_review":
        payload["review_status"] = ReviewStatus.NOT_REVIEWED
    elif case == "na_release":
        payload["release_status"] = SectionReleaseStatus.HOLD
    elif case == "na_grade":
        payload["achieved_grade"] = SectionAchievedGrade.UNGRADED
    elif case == "na_decision":
        payload["decision_ids"] = ()
    elif case == "na_timestamp":
        payload["started_at"] = _NOW
        payload["completed_at"] = _NOW
    elif case == "applicable_na_production":
        payload["production_status"] = ProductionStatus.NOT_REQUIRED_BY_SCOPE
    elif case == "applicable_na_grade":
        payload["achieved_grade"] = SectionAchievedGrade.NOT_APPLICABLE
    elif case == "applicable_na_release":
        payload["release_status"] = SectionReleaseStatus.NOT_APPLICABLE
    elif case == "complete":
        payload["production_status"] = ProductionStatus.COMPLETE
    elif case == "complete_with_limits":
        payload["production_status"] = ProductionStatus.COMPLETE_WITH_LIMITATIONS
    elif case == "missing_input":
        payload["resolved_inputs"] = payload["required_inputs"]
    elif case == "failed":
        payload["production_status"] = ProductionStatus.FAILED
    elif case == "degraded":
        payload["production_status"] = ProductionStatus.DEGRADED
    elif case == "deferred":
        payload["production_status"] = ProductionStatus.INTENTIONALLY_DEFERRED
    elif case == "evidence_without_record":
        payload["evidence_status"] = EvidenceStatus.LIMITED
        payload["evidence_ids"] = ()
    elif case == "review_without_record":
        payload["review_status"] = ReviewStatus.INDEPENDENT_REVIEW_PENDING
        payload["review_ids"] = ()
    elif case == "authorized_without_decision":
        payload["release_status"] = SectionReleaseStatus.AUTHORIZED
    elif case == "one_timestamp":
        payload["started_at"] = _NOW
    else:
        payload["started_at"] = _NOW
        payload["completed_at"] = _NOW - timedelta(seconds=1)
    _rejects(SectionRecord, payload, None)


def test_section_id_must_resolve_from_the_taxonomy_ssot() -> None:
    payload = deepcopy(_first_applicable(_payload(_build_package())))
    payload["section_id"] = "unknown_section"
    _rejects(SectionRecord, payload, "taxonomy SSOT")


@pytest.mark.parametrize(
    "case",
    [
        "target_grade",
        "distribution_required",
        "delivery_scope",
        "duplicate_scope",
        "section_target",
        "always_applicable",
        "duplicate_section_ref",
        "manifest_identity",
        "manifest_created",
        "manifest_valuation",
        "manifest_cutoff",
        "manifest_revision",
        "manifest_registry",
        "foreign_output_identity",
        "section_started_before_report",
        "responsibility_pack_subject",
        "foreign_report_subject",
        "claim_outside_subject",
        "evidence_outside_subject",
    ],
)
def test_package_identity_taxonomy_and_subject_matrix(case: str) -> None:
    payload = _payload(_build_package())
    if case == "target_grade":
        payload["target_grade"] = AssessmentGrade.LENDER_GRADE
    elif case == "distribution_required":
        payload["distribution_register"]["records"] = ()
    elif case == "delivery_scope":
        payload["distribution_register"]["records"][0]["intended_audiences"] = (
            "Different audience",
        )
    elif case == "duplicate_scope":
        payload["scope"]["technology_ids"] = ("wind", "wind")
    elif case == "section_target":
        _first_applicable(payload)["target_grade"] = AssessmentGrade.LENDER_GRADE
    elif case == "always_applicable":
        _first_applicable(payload)["applicability"] = Applicability.UNDETERMINED
    elif case == "duplicate_section_ref":
        section = _first_applicable(payload)
        section["source_ids"] = ("source:lk", "source:lk")
    elif case == "manifest_identity":
        payload["run_manifest"]["project_id"] = "project:foreign"
    elif case == "manifest_created":
        payload["run_manifest"]["created_at"] = _NOW + timedelta(seconds=1)
    elif case == "manifest_valuation":
        payload["run_manifest"]["valuation_date"] = _DAY - timedelta(days=1)
    elif case == "manifest_cutoff":
        payload["run_manifest"]["evidence_cutoff"] = _DAY - timedelta(days=1)
    elif case == "manifest_revision":
        payload["run_manifest"]["report_revision"] = 1
    elif case == "manifest_registry":
        payload["run_manifest"]["pack_ids"] = ()
    elif case == "foreign_output_identity":
        payload["output_register"]["records"] = (
            {
                "output_id": "output:foreign-identity",
                "report_id": "report:foreign",
                "run_id": payload["identity"]["run_id"],
                "section_ids": (_first_applicable(payload)["section_id"],),
                "producing_contract": "contract:coverage",
                "producing_version": "1.0.0",
                "output_class": OutputClass.CANONICAL,
                "locator": "memory://coverage",
            },
        )
    elif case == "section_started_before_report":
        section = _first_applicable(payload)
        section["started_at"] = payload["identity"]["created_at"] - timedelta(seconds=1)
        section["completed_at"] = payload["identity"]["created_at"]
    elif case == "responsibility_pack_subject":
        payload["responsibility_register"]["records"] = (
            {
                "assignment_id": "assignment:coverage",
                "role": ResponsibilityRole.PREPARED,
                "status": ResponsibilityStatus.NOT_PERFORMED,
                "scope": "Controlled coverage mutation",
                "subject_binding": {
                    "kind": SubjectKind.PACK_VERSION,
                    "pack_id": "pack:lk",
                    "pack_version": "1.0.0-fixture",
                    "grade": AssessmentGrade.SCREENING,
                    "effective_from": _DAY,
                    "effective_until": _DAY,
                },
                "reason": "Not performed in the held fixture.",
            },
        )
    elif case == "foreign_report_subject":
        subject = payload["decision_register"]["records"][0]["subject_binding"]
        subject["report_id"] = "report:foreign"
    elif case == "claim_outside_subject":
        decision = payload["decision_register"]["records"][0]
        decision["subject_binding"]["claim_ids"] = (
            payload["claim_register"]["records"][0]["claim_id"],
        )
    else:
        decision = payload["decision_register"]["records"][0]
        claim = payload["claim_register"]["records"][0]
        decision["subject_binding"]["section_ids"] = (claim["section_id"],)
        decision["subject_binding"]["evidence_ids"] = (claim["evidence_ids"][0],)
    with pytest.raises(ValidationError):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize(
    "case",
    [
        "section_evidence_exact",
        "section_claim_identity",
        "claim_output_section",
        "section_output_identity",
        "output_section_backlink",
        "section_source_identity",
        "input_section_backlink",
        "capability_pack_backlink",
        "capability_section_backlink",
    ],
)
def test_package_reciprocal_graph_matrix(case: str) -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    other_section = next(
        item
        for item in payload["sections"]
        if item["section_id"] != section["section_id"]
        and item["applicability"] is Applicability.APPLICABLE
    )
    if case == "section_evidence_exact":
        section["evidence_ids"] = (other_section["evidence_ids"][0],)
    elif case == "section_claim_identity":
        section["claim_ids"] = (other_section["claim_ids"][0],)
        section["evidence_ids"] = (other_section["evidence_ids"][0],)
    elif case in {
        "claim_output_section",
        "section_output_identity",
        "output_section_backlink",
    }:
        output = {
            "output_id": "output:coverage",
            "report_id": payload["identity"]["report_id"],
            "run_id": payload["identity"]["run_id"],
            "section_ids": (other_section["section_id"],),
            "producing_contract": "contract:coverage",
            "producing_version": "1.0.0",
            "output_class": OutputClass.CANONICAL,
            "locator": "memory://coverage",
        }
        if case == "output_section_backlink":
            output["section_ids"] = (section["section_id"],)
        payload["output_register"]["records"] = (output,)
        if case == "claim_output_section":
            payload["claim_register"]["records"][0]["output_ids"] = ("output:coverage",)
        elif case == "section_output_identity":
            section["output_references"] = ("output:coverage",)
    elif case == "section_source_identity":
        source_id = section["source_ids"][0]
        source = next(
            item
            for item in payload["source_register"]["records"]
            if item["source_id"] == source_id
        )
        source["section_ids"] = tuple(
            item for item in source["section_ids"] if item != section["section_id"]
        )
    elif case == "input_section_backlink":
        input_id = section["required_inputs"][0]
        item = next(
            record
            for record in payload["input_register"]["records"]
            if record["input_id"] == input_id
        )
        item["affected_section_ids"] = (
            section["section_id"],
            other_section["section_id"],
        )
    elif case == "capability_pack_backlink":
        capability_id = section["capability_dispositions"][0]
        pack = payload["pack_registry"]["records"][0]
        pack["capability_ids"] = tuple(
            item for item in pack["capability_ids"] if item != capability_id
        )
    else:
        section["capability_dispositions"] = ()
    with pytest.raises(
        ValidationError,
        match="reciprocal|identity mismatch|links are not exact|bind back",
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_unlinked_evidence_is_rejected_by_the_claim_backlink() -> None:
    payload = _payload(_build_package())
    evidence = deepcopy(payload["evidence_register"]["records"][0])
    evidence["evidence_id"] = "evidence:unlinked-coverage"
    payload["evidence_register"]["records"] = (
        *payload["evidence_register"]["records"],
        evidence,
    )
    with pytest.raises(ValidationError, match="evidence/claim reciprocal identity"):
        FeasibilityReportPackage.model_validate(payload)


def test_derived_input_requires_a_section_derived_input_backlink() -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    target_input = next(
        item
        for item in payload["input_register"]["records"]
        if item["input_id"] == section["required_inputs"][0]
    )
    operand_input = next(
        item
        for item in payload["input_register"]["records"]
        if item["input_id"] != target_input["input_id"]
    )
    target_input["kind"] = InputKind.DERIVED
    target_input["derivation_ids"] = ("derivation:coverage",)
    payload["derivation_register"]["records"] = (
        {
            "derivation_id": "derivation:coverage",
            "method_contract": "contract:coverage",
            "method_version": "1.0.0",
            "input_ids": (operand_input["input_id"],),
            "source_ids": (),
            "assumption_ids": (),
            "derived_input_ids": (target_input["input_id"],),
            "output_ids": (),
            "validation_ids": (),
            "precision_policy": "Preserve lexical precision",
        },
    )
    with pytest.raises(ValidationError, match="derived input lacks reciprocal section"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("case", ["output_names_derivation", "derivation_names_output"])
def test_output_and_derivation_links_are_reciprocal(case: str) -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    input_id = section["required_inputs"][0]
    output_ids = ("output:coverage-a", "output:coverage-b")
    outputs = []
    for output_id in output_ids:
        outputs.append(
            {
                "output_id": output_id,
                "report_id": payload["identity"]["report_id"],
                "run_id": payload["identity"]["run_id"],
                "section_ids": (section["section_id"],),
                "producing_contract": "contract:coverage",
                "producing_version": "1.0.0",
                "output_class": OutputClass.CANONICAL,
                "locator": f"memory://{output_id}",
                "derivation_ids": (),
            }
        )
    if case == "output_names_derivation":
        outputs[0]["derivation_ids"] = ("derivation:coverage",)
        outputs[1]["derivation_ids"] = ("derivation:coverage",)
        derivation_output_ids = (output_ids[1],)
        match = "output/derivation reciprocal identity"
    else:
        derivation_output_ids = (output_ids[0],)
        match = "derivation/output reciprocal identity"
    section["output_references"] = output_ids
    payload["output_register"]["records"] = tuple(outputs)
    payload["derivation_register"]["records"] = (
        {
            "derivation_id": "derivation:coverage",
            "method_contract": "contract:coverage",
            "method_version": "1.0.0",
            "input_ids": (input_id,),
            "source_ids": (),
            "assumption_ids": (),
            "derived_input_ids": (),
            "output_ids": derivation_output_ids,
            "validation_ids": (),
            "precision_policy": "Preserve lexical precision",
        },
    )
    with pytest.raises(ValidationError, match=match):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize(
    "case",
    [
        "source_project",
        "source_technology",
        "claim_scope",
        "evidence_scope",
        "evidence_expired",
        "evidence_grade_claim",
        "wrong_jurisdiction_pack_kind",
        "wrong_technology_pack_kind",
        "foreign_project_subject",
        "pack_stage",
        "pack_future",
        "pack_structural_source",
        "pack_validation",
        "pack_limitation_boundary",
        "jurisdiction_pack_source_scope",
        "technology_pack_source_scope",
        "resolved_input",
        "evidence_state",
    ],
)
def test_package_scope_currency_and_state_matrix(case: str) -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    if case == "source_project":
        payload["source_register"]["records"][0]["project_boundary"] = "foreign"
    elif case == "source_technology":
        payload["source_register"]["records"][0]["technology_ids"] = ("bess",)
    elif case == "claim_scope":
        payload["claim_register"]["records"][0]["project_boundary"] = "foreign"
    elif case == "evidence_scope":
        payload["evidence_register"]["records"][0]["project_boundary"] = "foreign"
    elif case == "evidence_expired":
        payload["evidence_register"]["records"][0]["expiry_date"] = _DAY - timedelta(
            days=1
        )
    elif case == "evidence_grade_claim":
        evidence = payload["evidence_register"]["records"][0]
        evidence["sufficiency"] = EvidenceStatus.SUFFICIENT_FOR_ACHIEVED_GRADE
        evidence["source_id"] = "source:lk"
        evidence["required_external_item"] = None
    elif case == "wrong_jurisdiction_pack_kind":
        payload["scope"]["jurisdiction_pack_ids"] = ("pack:wind",)
    elif case == "wrong_technology_pack_kind":
        payload["scope"]["technology_pack_ids"] = ("pack:lk",)
    elif case == "foreign_project_subject":
        payload["jurisdiction_subject_bindings"][0]["subject_id"] = "project:foreign"
    elif case == "pack_stage":
        payload["pack_registry"]["records"][0]["project_stages"] = ("construction",)
    elif case == "pack_future":
        payload["pack_registry"]["records"][0]["review_date"] = _DAY + timedelta(days=1)
    elif case == "pack_structural_source":
        source = payload["source_register"]["records"][0]
        source["source_class"] = SourceClass.ASSUMPTION
    elif case == "pack_validation":
        payload["validation_register"]["records"][0]["status"] = ValidationStatus.FAILED
    elif case == "pack_limitation_boundary":
        payload["limitation_register"]["records"][0]["affected_section_ids"] = (
            "section:foreign",
        )
    elif case == "jurisdiction_pack_source_scope":
        payload["source_register"]["records"][0]["jurisdictions"] = ()
    elif case == "technology_pack_source_scope":
        payload["source_register"]["records"][1]["technology_ids"] = ()
    elif case == "resolved_input":
        section["resolved_inputs"] = section["required_inputs"]
    else:
        section["evidence_status"] = EvidenceStatus.LIMITED
    with pytest.raises(ValidationError):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize(
    "case",
    [
        "artifact_foreign",
        "artifact_predates",
        "artifact_uncontrolled",
        "full_artifact_sources",
        "duplicate_disclosure",
        "disclosure_outside_control",
        "disclosure_source_absent",
        "public_private_artifact",
    ],
)
def test_package_artifact_and_distribution_matrix(case: str) -> None:
    payload = _payload(_build_package())
    artifact = _artifact(full=False).model_dump(mode="python")
    artifact["source_ids"] = ("source:lk",)
    payload["artifact_manifest"]["records"] = (artifact,)
    control = payload["distribution_register"]["records"][0]
    control["artifact_ids"] = (artifact["artifact_id"],)
    if case == "artifact_foreign":
        artifact["report_id"] = "report:foreign"
    elif case == "artifact_predates":
        artifact["created_at"] = payload["identity"]["created_at"] - timedelta(
            seconds=1
        )
    elif case == "artifact_uncontrolled":
        control["artifact_ids"] = ()
    elif case == "full_artifact_sources":
        artifact["is_full_package"] = True
    elif case in {
        "duplicate_disclosure",
        "disclosure_outside_control",
        "disclosure_source_absent",
    }:
        binding = {
            "artifact_id": artifact["artifact_id"],
            "source_id": "source:lk",
            "action": DisclosureAction.OMIT,
            "reason": "Controlled restriction",
            "validation_id": "validation:lk-pack",
        }
        if case == "duplicate_disclosure":
            control["disclosure_bindings"] = (binding, binding)
        elif case == "disclosure_outside_control":
            binding["artifact_id"] = "artifact:foreign"
            second = deepcopy(artifact)
            second["artifact_id"] = "artifact:foreign"
            payload["artifact_manifest"]["records"] = (artifact, second)
            control["disclosure_bindings"] = (binding,)
        else:
            binding["source_id"] = "source:wind"
            control["disclosure_bindings"] = (binding,)
    else:
        control["distribution_class"] = ConfidentialityClass.PUBLIC
    with pytest.raises(ValidationError):
        FeasibilityReportPackage.model_validate(payload)


def test_assured_pack_subject_version_is_exact() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    review = payload["review_register"]["records"][0]
    review["subject_binding"]["pack_version"] = "9.9.9"
    with pytest.raises(ValidationError, match="exact pack version"):
        FeasibilityReportPackage.model_validate(payload)


def test_valid_derivation_and_closed_finding_reach_their_success_paths() -> None:
    derivation = DerivationRecord(
        derivation_id="derivation:valid",
        method_contract="contract:test",
        method_version="1.0.0",
        input_ids=("input:test",),
        output_ids=("output:test",),
        validation_ids=(),
        precision_policy="Preserve lexical precision",
    )
    finding = ReviewFindingRecord(
        finding_id="finding:closed",
        status=FindingStatus.CLOSED,
        statement="Controlled finding",
        affected_claim_ids=(),
        affected_section_ids=("resource_and_energy_yield",),
        response="Accepted for controlled verification.",
        decision_id="decision:test",
    )
    assert derivation.output_ids == ("output:test",)
    assert finding.status is FindingStatus.CLOSED


@pytest.mark.parametrize(
    "case",
    [
        "capability_output",
        "source_supersession",
        "assumption_owner",
        "assumption_claim",
        "assumption_section",
        "assumption_decision",
        "judgement_actor",
        "judgement_claim",
        "judgement_section",
        "judgement_review",
        "derivation_input",
        "derivation_source",
        "derivation_assumption",
        "derivation_derived_input",
        "derivation_output",
        "derivation_validation",
        "error_capability",
        "error_section",
        "finding_claim",
        "finding_section",
        "finding_decision",
        "decision_supersession",
        "artifact_supersession",
    ],
)
def test_cross_registry_reference_fail_closed_matrix(case: str) -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    section_id = section["section_id"]
    input_id = section["required_inputs"][0]
    actor_id = payload["actor_register"]["records"][0]["actor_id"]
    if case == "capability_output":
        capability = payload["capability_registry"]["records"][0]
        capability.clear()
        capability.update(
            capability_id=section["capability_dispositions"][0],
            outcome=CapabilityOutcome.EXECUTED,
            section_ids=(section_id,),
            owning_contract="DBAY-FRC-001",
            implementation_version="1.0.0",
            activation_predicate="Controlled coverage mutation",
            pack_ids=("pack:lk", "pack:wind"),
            output_ids=("output:absent",),
        )
    elif case == "source_supersession":
        source = payload["source_register"]["records"][0]
        source["supersedes_source_id"] = "source:absent"
    elif case.startswith("assumption_"):
        assumption = {
            "assumption_id": "assumption:coverage",
            "statement": "Controlled coverage assumption",
            "owner_actor_id": actor_id,
            "basis": "Coverage-only reference control",
            "materiality": Materiality.NON_MATERIAL,
            "sensitivity": "No production consequence",
            "affected_claim_ids": (),
            "affected_section_ids": (),
            "approval_decision_id": None,
            "review_date": _DAY,
            "replacement_action": "Replace only in a controlled fixture.",
        }
        if case == "assumption_owner":
            assumption["owner_actor_id"] = "actor:absent"
        elif case == "assumption_claim":
            assumption["affected_claim_ids"] = ("claim:absent",)
        elif case == "assumption_section":
            assumption["affected_section_ids"] = ("section:absent",)
        else:
            assumption["approval_decision_id"] = "decision:absent"
        payload["assumption_register"]["records"] = (assumption,)
    elif case.startswith("judgement_"):
        judgement = {
            "judgement_id": "judgement:coverage",
            "statement": "Controlled coverage judgement",
            "actor_id": actor_id,
            "basis": "Coverage-only reference control",
            "alternatives_considered": ("No alternative required",),
            "affected_claim_ids": (),
            "affected_section_ids": (),
            "review_ids": (),
        }
        if case == "judgement_actor":
            judgement["actor_id"] = "actor:absent"
        elif case == "judgement_claim":
            judgement["affected_claim_ids"] = ("claim:absent",)
        elif case == "judgement_section":
            judgement["affected_section_ids"] = ("section:absent",)
        else:
            judgement["review_ids"] = ("review:absent",)
        payload["judgement_register"]["records"] = (judgement,)
    elif case.startswith("derivation_"):
        derivation = {
            "derivation_id": "derivation:coverage",
            "method_contract": "contract:coverage",
            "method_version": "1.0.0",
            "input_ids": (input_id,),
            "source_ids": (),
            "assumption_ids": (),
            "derived_input_ids": (input_id,),
            "output_ids": (),
            "validation_ids": (),
            "precision_policy": "Preserve lexical precision",
        }
        if case == "derivation_input":
            derivation["input_ids"] = ("input:absent",)
        elif case == "derivation_source":
            derivation["input_ids"] = ()
            derivation["source_ids"] = ("source:absent",)
        elif case == "derivation_assumption":
            derivation["assumption_ids"] = ("assumption:absent",)
        elif case == "derivation_derived_input":
            derivation["derived_input_ids"] = ("input:absent",)
        elif case == "derivation_output":
            derivation["derived_input_ids"] = ()
            derivation["output_ids"] = ("output:absent",)
        else:
            derivation["validation_ids"] = ("validation:absent",)
        payload["derivation_register"]["records"] = (derivation,)
    elif case.startswith("error_"):
        error = {
            "error_id": "error:coverage",
            "code": "coverage_error",
            "capability_id": section["capability_dispositions"][0],
            "section_ids": (section_id,),
            "safe_user_message": "Controlled error",
            "technical_cause_reference": "coverage-only",
            "remedy": "Correct the controlled reference.",
            "partial_output_valid": False,
            "consequence": "No production consequence.",
            "grade_ceiling": AchievedGrade.UNGRADED,
            "release_blocking": True,
        }
        if case == "error_capability":
            error["capability_id"] = "cap:absent"
        else:
            error["section_ids"] = ("section:absent",)
        payload["error_register"]["records"] = (error,)
    elif case.startswith("finding_"):
        finding = {
            "finding_id": "finding:coverage",
            "status": FindingStatus.OPEN_NON_BLOCKING,
            "statement": "Controlled finding",
            "affected_claim_ids": (),
            "affected_section_ids": (),
        }
        if case == "finding_claim":
            finding["affected_claim_ids"] = ("claim:absent",)
        elif case == "finding_section":
            finding["affected_section_ids"] = ("section:absent",)
        else:
            finding.update(
                status=FindingStatus.CLOSED,
                response="Controlled response",
                decision_id="decision:absent",
            )
        payload["review_finding_register"]["records"] = (finding,)
    elif case == "decision_supersession":
        decision = payload["decision_register"]["records"][0]
        decision["supersedes_decision_id"] = "decision:absent"
    else:
        artifact = _artifact(full=False).model_dump(mode="python")
        artifact["supersedes_artifact_id"] = "artifact:absent"
        payload["artifact_manifest"]["records"] = (artifact,)
    with pytest.raises(ValidationError, match="unresolved references"):
        FeasibilityReportPackage.model_validate(payload)
