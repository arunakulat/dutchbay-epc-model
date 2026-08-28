"""Contract and veto-regression tests for DBAY-FRC-001 Dolphin 2."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from analytics.contracts_v14 import FeasibilityReportPackage as PublicPackage
from analytics.feasibility_report_contract.package import FeasibilityReportPackage
from analytics.feasibility_report_contract.records import (
    ActorRecord,
    ActorRegister,
    ArtifactDisclosureBinding,
    ArtifactManifest,
    ArtifactRecord,
    AssumptionRegister,
    CanonicalValue,
    CapabilityDisposition,
    CapabilityRegistry,
    ClaimRecord,
    ClaimRegister,
    DecisionRecord,
    DecisionRegister,
    DeferredCapability,
    DegradedCapability,
    DerivationRegister,
    Digest,
    DistributionControl,
    DistributionRegister,
    ErrorRegister,
    EvidenceRecord,
    EvidenceRegister,
    ExecutedCapability,
    FailedCapability,
    InputRecord,
    InputRegister,
    JudgementRegister,
    JurisdictionSubjectBinding,
    LimitationRecord,
    LimitationRegister,
    MissingDependencyCapability,
    MissingInputCapability,
    NotApplicableCapability,
    OutputReference,
    OutputRegister,
    PackageRelease,
    PackBinding,
    PackEvidenceMinimum,
    PackInputDefault,
    PackRegistry,
    PackVersionSubjectBinding,
    ReconciliationRecord,
    ReconciliationRegister,
    ReportIdentity,
    ReportSubjectBinding,
    ResponsibilityAssignment,
    ResponsibilityRegister,
    ReviewFindingRegister,
    ReviewRecord,
    ReviewRegister,
    RunManifest,
    ScopeDeclaration,
    SectionRecord,
    SourceLocator,
    SourceRecord,
    SourceRegister,
    UnsupportedJurisdictionCapability,
    UnsupportedTechnologyCapability,
    ValidationRecord,
    ValidationRegister,
)
from analytics.feasibility_report_contract.vocabulary import (
    FEASIBILITY_REPORT_CONTRACT_VERSION,
    AchievedGrade,
    ActorKind,
    Applicability,
    ArtifactFormat,
    AssessmentGrade,
    AuthenticityStatus,
    ConfidentialityClass,
    DecisionKind,
    DecisionOutcome,
    DisclosureAction,
    EvidenceStatus,
    GovernedSubjectKind,
    IndependenceStatus,
    InputKind,
    InputResolutionStatus,
    Materiality,
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
    SourceClass,
    ValidationStatus,
    ValueType,
)
from analytics.feasibility_sections import load_feasibility_taxonomy
from analytics.run_modes import RunMode

_NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
_DAY = date(2026, 8, 28)
_SHA = "0" * 64
_ALWAYS_APPLICABLE = {
    "executive_investment_thesis",
    "project_description_and_structure",
    "risk_register_and_mitigations",
    "decision_checklist_conditions_precedent",
    "appendices_provenance_audit_trail",
}


def _report_subject(
    *,
    section_ids: tuple[str, ...] = (),
    claim_ids: tuple[str, ...] = (),
    evidence_ids: tuple[str, ...] = (),
    artifact_ids: tuple[str, ...] = (),
    review_ids: tuple[str, ...] = (),
) -> ReportSubjectBinding:
    return ReportSubjectBinding(
        report_id="report:fixture",
        run_id="run:fixture",
        section_ids=section_ids,
        claim_ids=claim_ids,
        evidence_ids=evidence_ids,
        artifact_ids=artifact_ids,
        review_ids=review_ids,
    )


def _build_package() -> FeasibilityReportPackage:
    """Build an honestly held package with all 20 sections dispositioned."""
    section_ids = load_feasibility_taxonomy().section_names
    applicable_ids = tuple(item for item in section_ids if item in _ALWAYS_APPLICABLE)
    na_ids = tuple(item for item in section_ids if item not in _ALWAYS_APPLICABLE)
    capabilities: list[MissingInputCapability | NotApplicableCapability] = []
    inputs: list[InputRecord] = []
    claims: list[ClaimRecord] = []
    evidence: list[EvidenceRecord] = []
    sections: list[SectionRecord] = []

    for section_id in section_ids:
        capability_id = f"cap:{section_id}"
        common_capability = {
            "capability_id": capability_id,
            "section_ids": (section_id,),
            "owning_contract": "DBAY-FRC-001",
            "implementation_version": "1.0.0",
            "pack_ids": ("pack:lk", "pack:wind"),
        }
        if section_id in _ALWAYS_APPLICABLE:
            input_id = f"input:{section_id}"
            claim_id = f"claim:{section_id}"
            evidence_id = f"evidence:{section_id}"
            capabilities.append(
                MissingInputCapability(
                    **common_capability,  # type: ignore[arg-type]
                    activation_predicate="always applicable",
                    missing_input_ids=(input_id,),
                    consequence="Section output is unavailable.",
                    remedy="Supply and validate the required project input.",
                )
            )
            inputs.append(
                InputRecord(
                    input_id=input_id,
                    kind=InputKind.SUPPLIED,
                    resolution_status=InputResolutionStatus.MISSING,
                    name=f"Required input for {section_id}",
                    affected_claim_ids=(claim_id,),
                    affected_section_ids=(section_id,),
                    reason="The project-specific input was not supplied.",
                    remedy="Obtain and authenticate the project-specific input.",
                )
            )
            claims.append(
                ClaimRecord(
                    claim_id=claim_id,
                    section_id=section_id,
                    statement=f"Material claim for {section_id}",
                    materiality=Materiality.MATERIAL,
                    jurisdictions=("LK",),
                    technology_ids=("wind",),
                    project_boundary="Controlled global contract fixture",
                    evidence_ids=(evidence_id,),
                )
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    claim_id=claim_id,
                    locator="External evidence request",
                    authenticity_status=AuthenticityStatus.UNVERIFIED,
                    relevance="Required to substantiate the material section claim.",
                    jurisdictions=("LK",),
                    technology_ids=("wind",),
                    project_boundary="Controlled global contract fixture",
                    period="As at the evidence cutoff",
                    independence_status=IndependenceStatus.NOT_ASSESSED,
                    sufficiency=EvidenceStatus.MISSING,
                    required_external_item="Authenticated project evidence",
                )
            )
            sections.append(
                SectionRecord(
                    section_id=section_id,
                    applicability=Applicability.APPLICABLE,
                    applicability_reason="Always applicable under DBAY-FRC-001 section 8.",
                    production_status=ProductionStatus.NOT_RUN_MISSING_INPUT,
                    evidence_status=EvidenceStatus.MISSING,
                    review_status=ReviewStatus.NOT_REVIEWED,
                    release_status=SectionReleaseStatus.HOLD,
                    target_grade=AssessmentGrade.SCREENING,
                    achieved_grade=SectionAchievedGrade.UNGRADED,
                    materiality=Materiality.MATERIAL,
                    summary="Held: a named project input and its evidence are missing.",
                    output_references=(),
                    required_inputs=(input_id,),
                    resolved_inputs=(),
                    derived_inputs=(),
                    capability_dispositions=(capability_id,),
                    jurisdiction_pack_ids=("pack:lk",),
                    technology_pack_ids=("pack:wind",),
                    source_ids=("source:lk", "source:wind"),
                    claim_ids=(claim_id,),
                    evidence_ids=(evidence_id,),
                    assumption_ids=(),
                    judgement_ids=(),
                    limitation_ids=(),
                    error_ids=(),
                    review_ids=(),
                    decision_ids=(),
                )
            )
        else:
            capabilities.append(
                NotApplicableCapability(
                    **common_capability,  # type: ignore[arg-type]
                    activation_predicate="outside the controlled fixture scope",
                    reason="The controlled fixture excludes this subject from scope.",
                    decision_id="decision:scope",
                )
            )
            sections.append(
                SectionRecord(
                    section_id=section_id,
                    applicability=Applicability.NOT_APPLICABLE,
                    applicability_reason="Named authority excluded this subject.",
                    production_status=ProductionStatus.NOT_REQUIRED_BY_SCOPE,
                    evidence_status=EvidenceStatus.NOT_REQUIRED,
                    review_status=ReviewStatus.NOT_REQUIRED,
                    release_status=SectionReleaseStatus.NOT_APPLICABLE,
                    target_grade=AssessmentGrade.SCREENING,
                    achieved_grade=SectionAchievedGrade.NOT_APPLICABLE,
                    materiality=Materiality.NON_MATERIAL,
                    summary="Not required by the approved project boundary.",
                    output_references=(),
                    required_inputs=(),
                    resolved_inputs=(),
                    derived_inputs=(),
                    capability_dispositions=(capability_id,),
                    jurisdiction_pack_ids=("pack:lk",),
                    technology_pack_ids=("pack:wind",),
                    source_ids=(),
                    claim_ids=(),
                    evidence_ids=(),
                    assumption_ids=(),
                    judgement_ids=(),
                    limitation_ids=(),
                    error_ids=(),
                    review_ids=(),
                    decision_ids=("decision:scope",),
                )
            )

    actor = ActorRecord(
        actor_id="actor:scope-authority",
        kind=ActorKind.HUMAN,
        name="Controlled fixture authority",
        organization="DutchBay test fixture",
        identity_verified=True,
        authority_basis="Named fixture authority for contract verification.",
    )
    scope_decision = DecisionRecord(
        decision_id="decision:scope",
        kind=DecisionKind.SCOPE,
        outcome=DecisionOutcome.APPROVED,
        authority_actor_id=actor.actor_id,
        authority_basis="Named fixture authority for applicability only.",
        scope="Applicability decisions for the controlled fixture",
        subject_binding=_report_subject(section_ids=na_ids),
        decision="Approve the explicit fixture exclusions only.",
        conditions=(),
        evidence_ids=(),
        decided_at=_NOW,
    )
    sources = (
        SourceRecord(
            source_id="source:lk",
            title="Controlled Sri Lanka structural source",
            issuer_or_author="Fixture authority",
            document_or_dataset_id="lk-structure-v1",
            revision="1",
            publication_date=date(2026, 8, 1),
            effective_date=date(2026, 8, 1),
            observation_date=date(2026, 8, 1),
            retrieval_date=date(2026, 8, 2),
            locator=SourceLocator(
                evidence_path="tests/fixtures/lk-structure.json", pinpoint="record 1"
            ),
            source_class=SourceClass.OFFICIAL_PRIMARY,
            authenticity_status=AuthenticityStatus.VERIFIED,
            authority="Controlled structural fixture only.",
            jurisdictions=("LK",),
            technology_ids=("wind",),
            project_boundary="Controlled global contract fixture",
            section_ids=applicable_ids,
            period="2026 fixture",
            licence_or_publication_rights="Internal test use only.",
            publication_permitted=False,
            access_restrictions="Internal verification only.",
            confidentiality=ConfidentialityClass.RESTRICTED,
            extraction_method="Controlled fixture construction.",
            extracting_actor_id=actor.actor_id,
            quality_checks=("Exact scope and date checked.",),
        ),
        SourceRecord(
            source_id="source:wind",
            title="Controlled wind structural source",
            issuer_or_author="Fixture authority",
            document_or_dataset_id="wind-structure-v1",
            revision="1",
            publication_date=date(2026, 8, 1),
            effective_date=date(2026, 8, 1),
            observation_date=date(2026, 8, 1),
            retrieval_date=date(2026, 8, 2),
            locator=SourceLocator(
                evidence_path="tests/fixtures/wind-structure.json", pinpoint="record 1"
            ),
            source_class=SourceClass.VENDOR,
            authenticity_status=AuthenticityStatus.VERIFIED,
            authority="Controlled structural fixture only.",
            jurisdictions=("LK",),
            technology_ids=("wind",),
            project_boundary="Controlled global contract fixture",
            section_ids=applicable_ids,
            period="2026 fixture",
            licence_or_publication_rights="Internal test use only.",
            publication_permitted=False,
            access_restrictions="Internal verification only.",
            confidentiality=ConfidentialityClass.RESTRICTED,
            extraction_method="Controlled fixture construction.",
            extracting_actor_id=actor.actor_id,
            quality_checks=("Exact scope and date checked.",),
        ),
    )
    validations = (
        ValidationRecord(
            validation_id="validation:lk-pack",
            name="LK fixture pack structure",
            status=ValidationStatus.PASSED,
            checked_at=_NOW,
            detail="Fixture-only structural validation.",
        ),
        ValidationRecord(
            validation_id="validation:wind-pack",
            name="Wind fixture pack structure",
            status=ValidationStatus.PASSED,
            checked_at=_NOW,
            detail="Fixture-only structural validation.",
        ),
    )
    first_section = applicable_ids[0]
    first_claim = f"claim:{first_section}"
    limitations = (
        LimitationRecord(
            limitation_id="limitation:lk-pack",
            statement="Fixture pack is not project evidence.",
            materiality=Materiality.MATERIAL,
            affected_claim_ids=(first_claim,),
            affected_section_ids=(first_section,),
            consequence="No feasibility conclusion is authorized.",
            grade_ceiling=AchievedGrade.SCREENING,
            owner_actor_id=actor.actor_id,
            remedy="Replace with authenticated project and jurisdiction evidence.",
        ),
        LimitationRecord(
            limitation_id="limitation:wind-pack",
            statement="Fixture technology pack is not a technology validation.",
            materiality=Materiality.MATERIAL,
            affected_claim_ids=(first_claim,),
            affected_section_ids=(first_section,),
            consequence="No feasibility conclusion is authorized.",
            grade_ceiling=AchievedGrade.SCREENING,
            owner_actor_id=actor.actor_id,
            remedy="Replace with independently validated technology evidence.",
        ),
    )
    capability_ids = tuple(item.capability_id for item in capabilities)
    input_ids = tuple(item.input_id for item in inputs)
    pack_common = {
        "status": PackStatus.SUPPORTED,
        "version": "1.0.0-fixture",
        "owner_actor_id": actor.actor_id,
        "effective_date": date(2026, 8, 1),
        "review_date": date(2026, 8, 2),
        "compatible_contract_versions": (FEASIBILITY_REPORT_CONTRACT_VERSION,),
        "project_stages": ("screening",),
        "section_ids": section_ids,
        "capability_ids": capability_ids,
        "required_input_ids": input_ids,
        "evidence_minima": tuple(
            PackEvidenceMinimum(
                section_id=section_id,
                target_grade=AssessmentGrade.SCREENING,
                requirement="Fixture-specific evidence state must be explicit.",
            )
            for section_id in section_ids
        ),
        "permitted_degradations": ("Only explicitly recorded holds are permitted.",),
        "grade_ceiling": AchievedGrade.SCREENING,
    }
    jurisdiction_pack = PackBinding(
        pack_id="pack:lk",
        kind=PackKind.JURISDICTION,
        jurisdiction_codes=("LK",),
        validation_ids=("validation:lk-pack",),
        source_ids=("source:lk",),
        limitation_ids=("limitation:lk-pack",),
        cross_field_rules=("Jurisdiction must match the activated pack.",),
        prohibited_substitutions=(
            "Sri Lankan values cannot fill another jurisdiction.",
        ),
        **pack_common,  # type: ignore[arg-type]
    )
    technology_pack = PackBinding(
        pack_id="pack:wind",
        kind=PackKind.TECHNOLOGY,
        technology_ids=("wind",),
        validation_ids=("validation:wind-pack",),
        source_ids=("source:wind",),
        limitation_ids=("limitation:wind-pack",),
        cross_field_rules=("Technology must match the activated pack.",),
        prohibited_substitutions=("Wind values cannot fill another technology.",),
        **pack_common,  # type: ignore[arg-type]
    )
    identity = ReportIdentity(
        report_id="report:fixture",
        project_id="project:fixture",
        case_id="case:base",
        run_id="run:fixture",
        issue=1,
        revision=0,
        created_at=_NOW,
    )
    scope = ScopeDeclaration(
        project_boundary="Controlled global contract fixture",
        technology_ids=("wind",),
        jurisdictions=("LK",),
        project_stage="screening",
        intended_audiences=("Internal contract reviewers",),
        intended_uses=("Machine-contract validation",),
        run_mode=RunMode.LENDER,
        target_grade=AssessmentGrade.SCREENING,
        valuation_date=_DAY,
        evidence_cutoff=_DAY,
        reporting_currency="USD",
        price_basis="Real 2026 USD",
        materiality_rule="Every fixture claim is tested explicitly.",
        jurisdiction_pack_ids=(jurisdiction_pack.pack_id,),
        technology_pack_ids=(technology_pack.pack_id,),
    )
    manifest = RunManifest(
        report_id=identity.report_id,
        project_id=identity.project_id,
        case_id=identity.case_id,
        run_id=identity.run_id,
        engine_version="v14-fixture",
        code_commit="22d342ac32b7921de9b5cde0156f483fecf26294",
        dirty_worktree=False,
        resolved_config_digest=Digest(value=_SHA),
        pack_ids=(jurisdiction_pack.pack_id, technology_pack.pack_id),
        input_ids=input_ids,
        source_ids=tuple(item.source_id for item in sources),
        assumption_ids=(),
        capability_ids=capability_ids,
        environment=("python=3.12.13",),
        dependency_versions=("pydantic=2",),
        validation_ids=tuple(item.validation_id for item in validations),
        reconciliation_ids=tuple(
            f"reconciliation:{family.value}" for family in ReconciliationFamily
        ),
        created_at=_NOW,
        valuation_date=_DAY,
        evidence_cutoff=_DAY,
        report_issue=identity.issue,
        report_revision=identity.revision,
    )
    reconciliations = tuple(
        ReconciliationRecord(
            reconciliation_id=f"reconciliation:{family.value}",
            family=family,
            name=f"{family.value} fixture reconciliation",
            status=ReconciliationStatus.NOT_APPLICABLE,
            section_ids=(),
            output_ids=(),
            detail="No current outputs exist in the deliberately held fixture.",
        )
        for family in ReconciliationFamily
    )
    return FeasibilityReportPackage(
        identity=identity,
        scope=scope,
        target_grade=AssessmentGrade.SCREENING,
        captured_at=_NOW,
        sections=tuple(sections),
        jurisdiction_subject_bindings=(
            JurisdictionSubjectBinding(
                binding_id="jurisdiction-binding:lk-project",
                jurisdiction="LK",
                subject_id=identity.project_id,
                subject_kind=GovernedSubjectKind.PROJECT,
                disposition_pack_id=jurisdiction_pack.pack_id,
                contribution_section_ids=applicable_ids,
            ),
        ),
        actor_register=ActorRegister(records=(actor,)),
        responsibility_register=ResponsibilityRegister(records=()),
        pack_registry=PackRegistry(records=(jurisdiction_pack, technology_pack)),
        capability_registry=CapabilityRegistry(records=tuple(capabilities)),
        input_register=InputRegister(records=tuple(inputs)),
        source_register=SourceRegister(records=sources),
        output_register=OutputRegister(records=()),
        claim_register=ClaimRegister(records=tuple(claims)),
        evidence_register=EvidenceRegister(records=tuple(evidence)),
        assumption_register=AssumptionRegister(records=()),
        judgement_register=JudgementRegister(records=()),
        derivation_register=DerivationRegister(records=()),
        limitation_register=LimitationRegister(records=limitations),
        error_register=ErrorRegister(records=()),
        review_finding_register=ReviewFindingRegister(records=()),
        review_register=ReviewRegister(records=()),
        decision_register=DecisionRegister(records=(scope_decision,)),
        reconciliation_register=ReconciliationRegister(records=reconciliations),
        validation_register=ValidationRegister(records=validations),
        run_manifest=manifest,
        artifact_manifest=ArtifactManifest(records=()),
        distribution_register=DistributionRegister(
            records=(
                DistributionControl(
                    distribution_id="distribution:package",
                    artifact_ids=(),
                    intended_audiences=("Internal contract reviewers",),
                    permitted_uses=("Machine-contract validation",),
                    permitted_reliance="No external reliance.",
                    distribution_class=ConfidentialityClass.INTERNAL,
                    confidentiality="Internal controlled test fixture.",
                    publication_rights="No publication rights granted.",
                    reliance_exclusions=("Not a feasibility conclusion.",),
                    expiry_or_review_date=date(2027, 8, 28),
                    redaction_policy="Do not include restricted source content.",
                ),
            )
        ),
        package_release=PackageRelease(
            report_id=identity.report_id,
            artifact_ids=(),
            scope="All projections and distribution",
            conditions=("Independent domain and assurance review remain outstanding.",),
            reason="Dolphin 2 defines a contract and cannot authorize release.",
        ),
    )


@pytest.fixture
def valid_package() -> FeasibilityReportPackage:
    return _build_package()


def _payload(package: FeasibilityReportPackage) -> dict[str, Any]:
    return package.model_dump(mode="python")


def _replace(
    records: tuple[dict[str, Any], ...], id_field: str, replacement: dict[str, Any]
) -> tuple[dict[str, Any], ...]:
    return tuple(
        replacement if record[id_field] == replacement[id_field] else record
        for record in records
    )


def _first_applicable(payload: dict[str, Any]) -> dict[str, Any]:
    return next(
        section
        for section in payload["sections"]
        if section["applicability"] is Applicability.APPLICABLE
    )


def _add_second_jurisdiction(payload: dict[str, Any]) -> None:
    """Add a truthful Fictionland jurisdiction facade without D3 policy."""
    applicable_sections = tuple(
        item["section_id"]
        for item in payload["sections"]
        if item["applicability"] is Applicability.APPLICABLE
    )
    applicable_capabilities = tuple(
        item["capability_dispositions"][0]
        for item in payload["sections"]
        if item["section_id"] in applicable_sections
    )
    applicable_inputs = tuple(
        item["required_inputs"][0]
        for item in payload["sections"]
        if item["section_id"] in applicable_sections
    )
    source = dict(payload["source_register"]["records"][0])
    source.update(
        source_id="source:fic",
        title="Controlled Fictionland structural source",
        document_or_dataset_id="fic-structure-v1",
        locator=SourceLocator(
            evidence_path="tests/fixtures/fic-structure.json", pinpoint="record 1"
        ).model_dump(mode="python"),
        jurisdictions=("FIC",),
        section_ids=applicable_sections,
    )
    validation = ValidationRecord(
        validation_id="validation:fic-pack",
        name="Fictionland fixture pack structure",
        status=ValidationStatus.PASSED,
        checked_at=_NOW,
        detail="Fixture-only structural validation.",
    ).model_dump(mode="python")
    first_section = applicable_sections[0]
    limitation = LimitationRecord(
        limitation_id="limitation:fic-pack",
        statement="Fictionland fixture pack is not project evidence.",
        materiality=Materiality.MATERIAL,
        affected_claim_ids=(),
        affected_section_ids=(first_section,),
        consequence="No feasibility conclusion is authorized.",
        grade_ceiling=AchievedGrade.SCREENING,
        owner_actor_id="actor:scope-authority",
        remedy="Replace with authenticated Fictionland project evidence.",
    ).model_dump(mode="python")
    base_pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack = dict(base_pack)
    pack.update(
        pack_id="pack:fic",
        jurisdiction_codes=("FIC",),
        section_ids=applicable_sections,
        capability_ids=applicable_capabilities,
        required_input_ids=applicable_inputs,
        source_ids=(source["source_id"],),
        validation_ids=(validation["validation_id"],),
        limitation_ids=(limitation["limitation_id"],),
        evidence_minima=tuple(
            item
            for item in base_pack["evidence_minima"]
            if item["section_id"] in applicable_sections
        ),
        review_ids=(),
        decision_ids=(),
    )
    payload["scope"]["jurisdictions"] = (
        *payload["scope"]["jurisdictions"],
        "FIC",
    )
    payload["scope"]["jurisdiction_pack_ids"] = (
        *payload["scope"]["jurisdiction_pack_ids"],
        pack["pack_id"],
    )
    payload["pack_registry"]["records"] = (
        *payload["pack_registry"]["records"],
        pack,
    )
    payload["source_register"]["records"] = (
        *payload["source_register"]["records"],
        source,
    )
    payload["validation_register"]["records"] = (
        *payload["validation_register"]["records"],
        validation,
    )
    payload["limitation_register"]["records"] = (
        *payload["limitation_register"]["records"],
        limitation,
    )
    payload["jurisdiction_subject_bindings"] = (
        *payload["jurisdiction_subject_bindings"],
        JurisdictionSubjectBinding(
            binding_id="jurisdiction-binding:fic-project",
            jurisdiction="FIC",
            subject_id="project:fixture",
            subject_kind=GovernedSubjectKind.PROJECT,
            disposition_pack_id=pack["pack_id"],
            contribution_section_ids=applicable_sections,
        ).model_dump(mode="python"),
    )
    for section in payload["sections"]:
        if section["section_id"] in applicable_sections:
            section["jurisdiction_pack_ids"] = (
                *section["jurisdiction_pack_ids"],
                pack["pack_id"],
            )
            section["source_ids"] = (*section["source_ids"], source["source_id"])
    for capability in payload["capability_registry"]["records"]:
        if capability["capability_id"] in applicable_capabilities:
            capability["pack_ids"] = (*capability["pack_ids"], pack["pack_id"])
    manifest = payload["run_manifest"]
    manifest["pack_ids"] = (*manifest["pack_ids"], pack["pack_id"])
    manifest["source_ids"] = (*manifest["source_ids"], source["source_id"])
    manifest["validation_ids"] = (
        *manifest["validation_ids"],
        validation["validation_id"],
    )


def _make_fictionland_unsupported(payload: dict[str, Any]) -> None:
    """Replace LK support with an honest held Fictionland unsupported disposition."""
    unsupported_pack_id = "pack:fic-unsupported"
    applicable_section_ids = tuple(
        section["section_id"]
        for section in payload["sections"]
        if section["applicability"] is Applicability.APPLICABLE
    )
    applicable_capability_ids = tuple(
        section["capability_dispositions"][0]
        for section in payload["sections"]
        if section["section_id"] in applicable_section_ids
    )
    applicable_input_ids = tuple(
        section["required_inputs"][0]
        for section in payload["sections"]
        if section["section_id"] in applicable_section_ids
    )
    old_pack = next(
        pack
        for pack in payload["pack_registry"]["records"]
        if pack["pack_id"] == "pack:lk"
    )
    unsupported_pack = dict(old_pack)
    unsupported_pack.update(
        pack_id=unsupported_pack_id,
        status=PackStatus.UNSUPPORTED,
        jurisdiction_codes=("FIC",),
        section_ids=applicable_section_ids,
        capability_ids=applicable_capability_ids,
        required_input_ids=applicable_input_ids,
        source_ids=(),
        validation_ids=(),
        limitation_ids=(),
        evidence_minima=(),
        permitted_degradations=(),
        review_ids=(),
        decision_ids=(),
        grade_ceiling=None,
    )
    payload["scope"]["jurisdictions"] = ("FIC",)
    payload["scope"]["jurisdiction_pack_ids"] = (unsupported_pack_id,)
    payload["pack_registry"]["records"] = tuple(
        unsupported_pack if pack["pack_id"] == "pack:lk" else pack
        for pack in payload["pack_registry"]["records"]
    )
    capabilities_by_id = {
        capability["capability_id"]: capability
        for capability in payload["capability_registry"]["records"]
    }
    replacement_capabilities: list[dict[str, Any]] = []
    for section in payload["sections"]:
        capability_id = section["capability_dispositions"][0]
        current_capability = capabilities_by_id[capability_id]
        if section["section_id"] in applicable_section_ids:
            replacement = UnsupportedJurisdictionCapability(
                capability_id=capability_id,
                section_ids=(section["section_id"],),
                owning_contract=current_capability["owning_contract"],
                implementation_version=current_capability["implementation_version"],
                activation_predicate="Fictionland has no governed jurisdiction pack",
                pack_ids=(unsupported_pack_id, "pack:wind"),
                jurisdiction="FIC",
                pack_id=unsupported_pack_id,
                consequence="Jurisdiction-dependent section output is unavailable.",
                remedy="Provide and independently review a governed Fictionland pack.",
            ).model_dump(mode="python")
            section["production_status"] = (
                ProductionStatus.NOT_RUN_UNSUPPORTED_JURISDICTION
            )
            section["jurisdiction_pack_ids"] = (unsupported_pack_id,)
            section["source_ids"] = tuple(
                source_id
                for source_id in section["source_ids"]
                if source_id != "source:lk"
            )
        else:
            replacement = dict(current_capability)
            replacement["pack_ids"] = tuple(
                pack_id for pack_id in replacement["pack_ids"] if pack_id != "pack:lk"
            )
            section["jurisdiction_pack_ids"] = ()
        replacement_capabilities.append(replacement)
    payload["capability_registry"]["records"] = tuple(replacement_capabilities)
    payload["source_register"]["records"] = tuple(
        source
        for source in payload["source_register"]["records"]
        if source["source_id"] != "source:lk"
    )
    wind_source = next(
        source
        for source in payload["source_register"]["records"]
        if source["source_id"] == "source:wind"
    )
    wind_source["jurisdictions"] = ("FIC",)
    for claim in payload["claim_register"]["records"]:
        claim["jurisdictions"] = ("FIC",)
    for evidence in payload["evidence_register"]["records"]:
        evidence["jurisdictions"] = ("FIC",)
    binding = payload["jurisdiction_subject_bindings"][0]
    binding["jurisdiction"] = "FIC"
    binding["disposition_pack_id"] = unsupported_pack_id
    binding["contribution_section_ids"] = applicable_section_ids
    manifest = payload["run_manifest"]
    manifest["pack_ids"] = tuple(
        unsupported_pack_id if pack_id == "pack:lk" else pack_id
        for pack_id in manifest["pack_ids"]
    )
    manifest["source_ids"] = tuple(
        source_id for source_id in manifest["source_ids"] if source_id != "source:lk"
    )


def _add_bess_technology(payload: dict[str, Any]) -> None:
    """Add truthful BESS type-level coverage without modelling asset topology."""
    applicable_sections = tuple(
        item["section_id"]
        for item in payload["sections"]
        if item["applicability"] is Applicability.APPLICABLE
    )
    applicable_capabilities = tuple(
        item["capability_dispositions"][0]
        for item in payload["sections"]
        if item["section_id"] in applicable_sections
    )
    applicable_inputs = tuple(
        item["required_inputs"][0]
        for item in payload["sections"]
        if item["section_id"] in applicable_sections
    )
    source = dict(payload["source_register"]["records"][1])
    source.update(
        source_id="source:bess",
        title="Controlled BESS structural source",
        document_or_dataset_id="bess-structure-v1",
        locator=SourceLocator(
            evidence_path="tests/fixtures/bess-structure.json", pinpoint="record 1"
        ).model_dump(mode="python"),
        technology_ids=("bess",),
        section_ids=applicable_sections,
    )
    validation = ValidationRecord(
        validation_id="validation:bess-pack",
        name="BESS fixture pack structure",
        status=ValidationStatus.PASSED,
        checked_at=_NOW,
        detail="Fixture-only structural validation.",
    ).model_dump(mode="python")
    first_section = applicable_sections[0]
    limitation = LimitationRecord(
        limitation_id="limitation:bess-pack",
        statement="BESS fixture pack is type-level only.",
        materiality=Materiality.MATERIAL,
        affected_claim_ids=(),
        affected_section_ids=(first_section,),
        consequence="No asset-topology conclusion is authorized.",
        grade_ceiling=AchievedGrade.SCREENING,
        owner_actor_id="actor:scope-authority",
        remedy="D3 must add project-case asset topology.",
    ).model_dump(mode="python")
    base_pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:wind"
    )
    pack = dict(base_pack)
    pack.update(
        pack_id="pack:bess",
        technology_ids=("bess",),
        section_ids=applicable_sections,
        capability_ids=applicable_capabilities,
        required_input_ids=applicable_inputs,
        source_ids=(source["source_id"],),
        validation_ids=(validation["validation_id"],),
        limitation_ids=(limitation["limitation_id"],),
        evidence_minima=tuple(
            item
            for item in base_pack["evidence_minima"]
            if item["section_id"] in applicable_sections
        ),
        review_ids=(),
        decision_ids=(),
    )
    payload["scope"]["technology_ids"] = (
        *payload["scope"]["technology_ids"],
        "bess",
    )
    payload["scope"]["technology_pack_ids"] = (
        *payload["scope"]["technology_pack_ids"],
        pack["pack_id"],
    )
    payload["pack_registry"]["records"] = (
        *payload["pack_registry"]["records"],
        pack,
    )
    payload["source_register"]["records"] = (
        *payload["source_register"]["records"],
        source,
    )
    payload["validation_register"]["records"] = (
        *payload["validation_register"]["records"],
        validation,
    )
    payload["limitation_register"]["records"] = (
        *payload["limitation_register"]["records"],
        limitation,
    )
    for section in payload["sections"]:
        if section["section_id"] in applicable_sections:
            section["technology_pack_ids"] = (
                *section["technology_pack_ids"],
                pack["pack_id"],
            )
            section["source_ids"] = (*section["source_ids"], source["source_id"])
    for capability in payload["capability_registry"]["records"]:
        if capability["capability_id"] in applicable_capabilities:
            capability["pack_ids"] = (*capability["pack_ids"], pack["pack_id"])
    manifest = payload["run_manifest"]
    manifest["pack_ids"] = (*manifest["pack_ids"], pack["pack_id"])
    manifest["source_ids"] = (*manifest["source_ids"], source["source_id"])
    manifest["validation_ids"] = (
        *manifest["validation_ids"],
        validation["validation_id"],
    )


def _artifact(*, full: bool = False) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id="artifact:json",
        report_id="report:fixture",
        run_id="run:fixture",
        format=ArtifactFormat.JSON,
        mime_type="application/json",
        producer="contract fixture",
        producer_version="1.0.0",
        created_at=_NOW,
        content_digest=Digest(value="1" * 64),
        completeness_profile="Full semantic fixture" if full else "Partial fixture",
        is_full_package=full,
        source_ids=("source:lk", "source:wind") if full else (),
        disclosure_exceptions=(),
        confidentiality=ConfidentialityClass.INTERNAL,
    )


def _authorize_partial_artifact(payload: dict[str, Any]) -> None:
    """Add a minimal evidence-backed release without lifting any real hold."""
    artifact = _artifact().model_dump(mode="python")
    section = _first_applicable(payload)
    evidence_id = section["evidence_ids"][0]
    claim_id = section["claim_ids"][0]
    evidence = next(
        item
        for item in payload["evidence_register"]["records"]
        if item["evidence_id"] == evidence_id
    )
    evidence["source_id"] = "source:lk"
    evidence["sufficiency"] = EvidenceStatus.LIMITED
    evidence["required_external_item"] = None
    evidence["period"] = "2026 fixture"
    section["evidence_status"] = EvidenceStatus.LIMITED
    authority = ActorRecord(
        actor_id="actor:release-authority",
        kind=ActorKind.HUMAN,
        name="Controlled release authority",
        organization="Independent Release Authority Ltd",
        identity_verified=True,
        authority_basis="Named partial-artifact release appointment.",
    ).model_dump(mode="python")
    binding = _report_subject(
        section_ids=(section["section_id"],),
        claim_ids=(claim_id,),
        evidence_ids=(evidence_id,),
        artifact_ids=(artifact["artifact_id"],),
    )
    decision = DecisionRecord(
        decision_id="decision:release-authorized",
        kind=DecisionKind.RELEASE,
        outcome=DecisionOutcome.AUTHORIZED,
        authority_actor_id=authority["actor_id"],
        authority_basis="Named partial-artifact release appointment.",
        scope="Exact partial JSON artifact",
        subject_binding=binding,
        decision="Authorize only the exact controlled partial artifact.",
        conditions=(),
        evidence_ids=(evidence_id,),
        decided_at=_NOW,
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        authority,
    )
    payload["artifact_manifest"]["records"] = (artifact,)
    payload["distribution_register"]["records"][0]["artifact_ids"] = (
        artifact["artifact_id"],
    )
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["package_release"] = PackageRelease(
        status=PackageReleaseStatus.AUTHORIZED,
        report_id="report:fixture",
        artifact_ids=(artifact["artifact_id"],),
        distribution_ids=("distribution:package",),
        scope="Exact partial JSON artifact",
        conditions=(),
        authority_actor_id=authority["actor_id"],
        decision_id=decision["decision_id"],
        decided_at=_NOW,
        reason="Controlled positive chronology fixture only.",
    ).model_dump(mode="python")


def test_public_v14_seam_reexports_machine_contract() -> None:
    assert PublicPackage is FeasibilityReportPackage


def test_held_fixture_has_exact_taxonomy_and_sentinel_authority(
    valid_package: FeasibilityReportPackage,
) -> None:
    assert tuple(item.section_id for item in valid_package.sections) == (
        load_feasibility_taxonomy().section_names
    )
    assert len(valid_package.sections) == 20
    assert valid_package.achieved_grade is AchievedGrade.UNGRADED
    assert valid_package.grade_decision_id is None
    assert valid_package.package_release.status is PackageReleaseStatus.HOLD
    assert all(
        item.production_status is not ProductionStatus.COMPLETE
        for item in valid_package.sections
    )


def test_generated_schema_and_instance_validate_independently(
    valid_package: FeasibilityReportPackage,
) -> None:
    schema = FeasibilityReportPackage.model_json_schema()
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(
        valid_package.model_dump(mode="json")
    )


def test_json_round_trip_and_deep_immutability(
    valid_package: FeasibilityReportPackage,
) -> None:
    restored = FeasibilityReportPackage.model_validate_json(
        valid_package.model_dump_json()
    )
    assert restored == valid_package
    with pytest.raises(ValidationError, match="frozen"):
        valid_package.achieved_grade = AchievedGrade.LENDER_GRADE  # type: ignore[misc]
    with pytest.raises(TypeError):
        valid_package.sections[0] = valid_package.sections[1]  # type: ignore[index]


@settings(max_examples=30, deadline=None)
@given(st.integers(min_value=0, max_value=19), st.integers(min_value=0, max_value=19))
def test_any_nontrivial_section_reordering_fails_taxonomy_parity(
    left: int, right: int
) -> None:
    if left == right:
        return
    payload = _payload(_build_package())
    sections = list(payload["sections"])
    sections[left], sections[right] = sections[right], sections[left]
    payload["sections"] = tuple(sections)
    with pytest.raises(ValidationError, match="taxonomy SSOT IDs in order"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_missing_or_duplicate_section_fails(mutation: str) -> None:
    payload = _payload(_build_package())
    sections = list(payload["sections"])
    if mutation == "missing":
        sections.pop()
    else:
        sections[-1] = sections[0]
    payload["sections"] = tuple(sections)
    with pytest.raises(ValidationError, match="taxonomy SSOT IDs in order"):
        FeasibilityReportPackage.model_validate(payload)


def test_unknown_fields_and_implicit_coercion_fail() -> None:
    scope = _build_package().scope.model_dump(mode="python")
    scope["hidden_default"] = "LK"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ScopeDeclaration.model_validate(scope)
    scope.pop("hidden_default")
    scope["valuation_date"] = "2026-08-28"
    with pytest.raises(ValidationError):
        ScopeDeclaration.model_validate(scope)


@pytest.mark.parametrize(
    ("value_type", "value", "unit"),
    [
        (ValueType.INTEGER, "1.5", "count"),
        (ValueType.DECIMAL, "NaN", "fraction"),
        (ValueType.BOOLEAN, "yes", None),
        (ValueType.DATE, "2026-99-99", None),
        (ValueType.DATETIME, "2026-08-28T08:00:00+05:30", None),
    ],
)
def test_canonical_value_lexical_type_is_fail_closed(
    value_type: ValueType, value: str, unit: str | None
) -> None:
    with pytest.raises((ValidationError, ValueError)):
        CanonicalValue(value_type=value_type, value=value, unit=unit)


@pytest.mark.parametrize("value_type", [ValueType.INTEGER, ValueType.DECIMAL])
def test_numeric_canonical_value_requires_explicit_unit(value_type: ValueType) -> None:
    with pytest.raises(ValidationError, match="explicit unit"):
        CanonicalValue(value_type=value_type, value="1")
    assert CanonicalValue(value_type=value_type, value="1", unit="1").unit == "1"


def test_capability_union_is_discriminated_and_every_variant_round_trips() -> None:
    common: dict[str, Any] = {
        "section_ids": ("resource_and_energy_yield",),
        "owning_contract": "DBAY-FRC-001",
        "implementation_version": "1.0.0",
        "activation_predicate": "controlled contract test",
        "pack_ids": ("pack:test",),
    }
    variants = (
        ExecutedCapability(
            capability_id="cap:executed", output_ids=("output:current",), **common
        ),
        DegradedCapability(
            capability_id="cap:degraded",
            failed_path="Canonical method unavailable",
            sanctioned_substitute="Declared advisory method",
            warning="Advisory substitute; not canonical evidence.",
            limitation_id="limitation:degraded",
            error_id="error:degraded",
            output_ids=("output:advisory",),
            grade_ceiling=AchievedGrade.ILLUSTRATIVE,
            **common,
        ),
        FailedCapability(capability_id="cap:failed", error_id="error:failed", **common),
        MissingInputCapability(
            capability_id="cap:missing-input",
            missing_input_ids=("input:missing",),
            consequence="Material output unavailable.",
            remedy="Supply the named input.",
            **common,
        ),
        MissingDependencyCapability(
            capability_id="cap:missing-dependency",
            dependency="optional-grid-engine",
            error_id="error:dependency",
            consequence="Grid result unavailable.",
            remedy="Install the governed dependency.",
            **common,
        ),
        UnsupportedJurisdictionCapability(
            capability_id="cap:unsupported-jurisdiction",
            jurisdiction="FIC",
            pack_id="pack:test",
            consequence="Local result unavailable.",
            remedy="Provide a reviewed jurisdiction pack.",
            **common,
        ),
        UnsupportedTechnologyCapability(
            capability_id="cap:unsupported-technology",
            technology_id="unknown-wave-device",
            pack_id="pack:test",
            consequence="Technology result unavailable.",
            remedy="Provide a reviewed technology pack.",
            **common,
        ),
        DeferredCapability(
            capability_id="cap:deferred",
            decision_id="decision:defer",
            owner_actor_id="actor:owner",
            reason="Deferred to the named gate.",
            target_date_or_gate="Before investment decision",
            consequence="No present conclusion.",
            **common,
        ),
        NotApplicableCapability(
            capability_id="cap:not-applicable",
            reason="Outside approved scope.",
            decision_id="decision:scope",
            **common,
        ),
    )
    adapter: TypeAdapter[CapabilityDisposition] = TypeAdapter(CapabilityDisposition)
    for variant in variants:
        assert adapter.validate_python(variant.model_dump(mode="python")) == variant
    assert adapter.json_schema()["discriminator"]["propertyName"] == "outcome"


@pytest.mark.parametrize("run_mode", tuple(RunMode))
def test_run_mode_never_infers_grade_or_release(run_mode: RunMode) -> None:
    payload = _payload(_build_package())
    payload["scope"]["run_mode"] = run_mode
    package = FeasibilityReportPackage.model_validate(payload)
    assert package.achieved_grade is AchievedGrade.UNGRADED
    assert package.package_release.status is PackageReleaseStatus.HOLD


@pytest.mark.parametrize(
    "grade",
    [
        AchievedGrade.ILLUSTRATIVE,
        AchievedGrade.SCREENING,
        AchievedGrade.DECISION_GRADE,
        AchievedGrade.LENDER_GRADE,
    ],
)
def test_d2_package_rejects_every_non_sentinel_grade(grade: AchievedGrade) -> None:
    payload = _payload(_build_package())
    payload["achieved_grade"] = grade
    with pytest.raises(ValidationError, match="sentinel|ungraded"):
        FeasibilityReportPackage.model_validate(payload)


def test_section_grade_above_target_is_rejected_without_d3_policy() -> None:
    payload = _payload(_build_package())
    _first_applicable(payload)["achieved_grade"] = SectionAchievedGrade.LENDER_GRADE
    with pytest.raises(ValidationError, match="section achieved_grade"):
        FeasibilityReportPackage.model_validate(payload)


def test_ungraded_package_rejects_any_grade_decision_reference() -> None:
    payload = _payload(_build_package())
    payload["grade_decision_id"] = "decision:scope"
    with pytest.raises(ValidationError, match="grade_decision_id=None"):
        FeasibilityReportPackage.model_validate(payload)


def test_claim_to_evidence_mismatch_is_rejected() -> None:
    payload = _payload(_build_package())
    records = payload["evidence_register"]["records"]
    records[0]["claim_id"] = records[1]["claim_id"]
    with pytest.raises(ValidationError, match="claim/evidence|evidence/claim"):
        FeasibilityReportPackage.model_validate(payload)


@settings(max_examples=20, deadline=None)
@given(st.sampled_from(("claim", "capability", "input", "source")))
def test_property_mutations_break_reciprocal_graph(edge: str) -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    if edge == "claim":
        section["claim_ids"] = ()
    elif edge == "capability":
        capability_id = section["capability_dispositions"][0]
        capability = next(
            item
            for item in payload["capability_registry"]["records"]
            if item["capability_id"] == capability_id
        )
        capability["pack_ids"] = ("pack:lk",)
    elif edge == "input":
        input_id = section["required_inputs"][0]
        item = next(
            item
            for item in payload["input_register"]["records"]
            if item["input_id"] == input_id
        )
        item["affected_section_ids"] = (payload["sections"][1]["section_id"],)
    else:
        section["source_ids"] = ("source:lk",)
    with pytest.raises(ValidationError, match="reciprocal|exact|bind back"):
        FeasibilityReportPackage.model_validate(payload)


def test_not_applicable_section_forbids_stale_or_foreign_output() -> None:
    payload = _payload(_build_package())
    na_section = next(
        section
        for section in payload["sections"]
        if section["applicability"] is Applicability.NOT_APPLICABLE
    )
    na_section["output_references"] = ("output:foreign",)
    with pytest.raises(ValidationError, match="not-applicable section forbids"):
        SectionRecord.model_validate(na_section)


def test_not_applicable_capability_and_section_share_exact_scope_decision() -> None:
    payload = _payload(_build_package())
    scope_decision = payload["decision_register"]["records"][0]
    scope_decision["subject_binding"]["section_ids"] = ()
    with pytest.raises(ValidationError, match="exact positive scope decision"):
        FeasibilityReportPackage.model_validate(payload)


def test_not_applicable_scope_authority_must_be_verified() -> None:
    payload = _payload(_build_package())
    payload["actor_register"]["records"][0]["identity_verified"] = False
    with pytest.raises(ValidationError, match="N/A scope decision requires a verified"):
        FeasibilityReportPackage.model_validate(payload)


def test_applicable_section_without_pack_links_is_rejected() -> None:
    payload = _payload(_build_package())
    _first_applicable(payload)["jurisdiction_pack_ids"] = ()
    with pytest.raises(
        ValidationError, match="requires jurisdiction and technology pack"
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_unknown_technology_cannot_be_relabelled_supported_without_structure() -> None:
    payload = _payload(_build_package())
    payload["scope"]["technology_ids"] = ("unknown-wave-device",)
    tech_pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["kind"] is PackKind.TECHNOLOGY
    )
    tech_pack["technology_ids"] = ("unknown-wave-device",)
    tech_pack["source_ids"] = ()
    tech_pack["validation_ids"] = ()
    tech_pack["limitation_ids"] = ()
    with pytest.raises(ValidationError, match="sources, validations, limitations"):
        FeasibilityReportPackage.model_validate(payload)


def test_fictionland_pack_rejects_sri_lanka_source_and_default() -> None:
    payload = _payload(_build_package())
    payload["scope"]["jurisdictions"] = ("FIC",)
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["kind"] is PackKind.JURISDICTION
    )
    pack["jurisdiction_codes"] = ("FIC",)
    input_id = pack["required_input_ids"][0]
    pack["input_defaults"] = (
        PackInputDefault(
            input_id=input_id,
            value=CanonicalValue(
                value_type=ValueType.DECIMAL, value="0.30", unit="fraction"
            ),
            source_ids=("source:lk",),
            applicability_predicate="Fictionland default",
        ).model_dump(mode="python"),
    )
    with pytest.raises(ValidationError, match="wrong jurisdiction"):
        FeasibilityReportPackage.model_validate(payload)


def test_absent_jurisdiction_and_untyped_technology_fail_closed() -> None:
    payload = _payload(_build_package())
    payload["scope"]["jurisdictions"] = ()
    with pytest.raises(ValidationError, match="explicit jurisdiction"):
        FeasibilityReportPackage.model_validate(payload)
    payload = _payload(_build_package())
    payload["scope"]["technology_ids"] = ()
    with pytest.raises(ValidationError, match="typed technology"):
        FeasibilityReportPackage.model_validate(payload)


def test_two_jurisdictions_require_and_accept_two_real_disposition_packs() -> None:
    payload = _payload(_build_package())
    _add_second_jurisdiction(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert set(package.scope.jurisdictions) == {"LK", "FIC"}
    assert {
        item.disposition_pack_id for item in package.jurisdiction_subject_bindings
    } == {
        "pack:lk",
        "pack:fic",
    }


def test_wind_and_bess_require_and_accept_distinct_type_level_packs() -> None:
    payload = _payload(_build_package())
    _add_bess_technology(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert set(package.scope.technology_ids) == {"wind", "bess"}
    assert set(package.scope.technology_pack_ids) == {"pack:wind", "pack:bess"}


def test_jurisdiction_pack_cannot_govern_multiple_jurisdictions() -> None:
    payload = _payload(_build_package())
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack["jurisdiction_codes"] = ("LK", "FIC")
    with pytest.raises(ValidationError, match="exactly one jurisdiction"):
        FeasibilityReportPackage.model_validate(payload)


def test_technology_pack_cannot_blur_multiple_technology_types() -> None:
    payload = _payload(_build_package())
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:wind"
    )
    pack["technology_ids"] = ("wind", "bess")
    with pytest.raises(ValidationError, match="exactly one technology type"):
        FeasibilityReportPackage.model_validate(payload)


def test_each_scoped_jurisdiction_requires_a_governed_subject_mapping() -> None:
    payload = _payload(_build_package())
    _add_second_jurisdiction(payload)
    payload["jurisdiction_subject_bindings"] = payload["jurisdiction_subject_bindings"][
        :1
    ]
    with pytest.raises(ValidationError, match="cover every scoped jurisdiction"):
        FeasibilityReportPackage.model_validate(payload)


def test_fictionland_can_fail_closed_through_an_unsupported_jurisdiction_pack() -> None:
    payload = _payload(_build_package())
    _make_fictionland_unsupported(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert package.scope.jurisdictions == ("FIC",)
    assert package.achieved_grade is AchievedGrade.UNGRADED
    assert package.package_release.status is PackageReleaseStatus.HOLD
    assert all(
        section.production_status is ProductionStatus.NOT_RUN_UNSUPPORTED_JURISDICTION
        for section in package.sections
        if section.applicability is Applicability.APPLICABLE
    )


def test_unsupported_jurisdiction_binding_rejects_wrong_pack_kind() -> None:
    payload = _payload(_build_package())
    _make_fictionland_unsupported(payload)
    payload["jurisdiction_subject_bindings"][0]["disposition_pack_id"] = "pack:wind"
    with pytest.raises(ValidationError, match="exact contributing disposition pack"):
        FeasibilityReportPackage.model_validate(payload)


def test_unsupported_jurisdiction_binding_rejects_silent_section_omission() -> None:
    payload = _payload(_build_package())
    _make_fictionland_unsupported(payload)
    section = _first_applicable(payload)
    section["production_status"] = ProductionStatus.NOT_RUN_MISSING_INPUT
    with pytest.raises(
        ValidationError, match="each affected section.*unsupported-jurisdiction"
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_unsupported_jurisdiction_binding_rejects_mismatched_capability() -> None:
    payload = _payload(_build_package())
    _make_fictionland_unsupported(payload)
    capability_id = _first_applicable(payload)["capability_dispositions"][0]
    capability = next(
        item
        for item in payload["capability_registry"]["records"]
        if item["capability_id"] == capability_id
    )
    capability["jurisdiction"] = "LK"
    with pytest.raises(
        ValidationError, match="each affected section.*unsupported-jurisdiction"
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_unsupported_fictionland_binding_rejects_sri_lanka_fallback_source() -> None:
    payload = _payload(_build_package())
    sri_lanka_source = dict(payload["source_register"]["records"][0])
    _make_fictionland_unsupported(payload)
    sri_lanka_source["source_id"] = "source:lk-fallback"
    payload["source_register"]["records"] = (
        *payload["source_register"]["records"],
        sri_lanka_source,
    )
    payload["run_manifest"]["source_ids"] = (
        *payload["run_manifest"]["source_ids"],
        sri_lanka_source["source_id"],
    )
    unsupported_pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:fic-unsupported"
    )
    unsupported_pack["source_ids"] = (sri_lanka_source["source_id"],)
    for section in payload["sections"]:
        if section["applicability"] is Applicability.APPLICABLE:
            section["source_ids"] = (
                *section["source_ids"],
                sri_lanka_source["source_id"],
            )
    with pytest.raises(ValidationError, match="wrong jurisdiction scope"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("duplicate_id", [True, False])
def test_jurisdiction_router_rejects_duplicate_binding_or_subject_mapping(
    duplicate_id: bool,
) -> None:
    payload = _payload(_build_package())
    duplicate = dict(payload["jurisdiction_subject_bindings"][0])
    if not duplicate_id:
        duplicate["binding_id"] = "jurisdiction-binding:lk-project-duplicate"
    payload["jurisdiction_subject_bindings"] = (
        *payload["jurisdiction_subject_bindings"],
        duplicate,
    )
    expected = (
        "duplicate jurisdiction subject binding IDs"
        if duplicate_id
        else "duplicate governed-subject mappings"
    )
    with pytest.raises(ValidationError, match=expected):
        FeasibilityReportPackage.model_validate(payload)


def test_derived_input_requires_derivation_and_reciprocal_section_link() -> None:
    base = _build_package().input_register.records[0].model_dump(mode="python")
    base["kind"] = InputKind.DERIVED
    with pytest.raises(ValidationError, match="derived input requires derivation_ids"):
        InputRecord.model_validate(base)
    base["derivation_ids"] = ("derivation:x",)
    base["affected_section_ids"] = ()
    with pytest.raises(ValidationError, match="affected section"):
        InputRecord.model_validate(base)


def test_passed_reconciliation_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="at least two distinct"):
        ReconciliationRecord(
            reconciliation_id="reconciliation:empty",
            family=ReconciliationFamily.PROJECT_BASIS,
            name="Empty false pass",
            status=ReconciliationStatus.PASSED,
            section_ids=(),
            output_ids=(),
            detail="No operands.",
        )


def test_reasoned_not_applicable_records_cover_all_reconciliation_families() -> None:
    package = _build_package()
    assert {item.family for item in package.reconciliation_register.records} == set(
        ReconciliationFamily
    )
    assert all(
        item.status is ReconciliationStatus.NOT_APPLICABLE
        and item.detail
        and not item.section_ids
        and not item.output_ids
        for item in package.reconciliation_register.records
    )


@pytest.mark.parametrize("mutation", ["empty", "missing", "duplicate", "all_same"])
def test_reconciliation_register_requires_exactly_one_of_all_six_families(
    mutation: str,
) -> None:
    payload = _payload(_build_package())
    records = list(payload["reconciliation_register"]["records"])
    if mutation == "empty":
        records = []
    elif mutation == "missing":
        records.pop()
    elif mutation == "duplicate":
        records[1]["family"] = records[0]["family"]
    else:
        for record in records:
            record["family"] = ReconciliationFamily.PROJECT_BASIS
    payload["reconciliation_register"]["records"] = tuple(records)
    with pytest.raises(ValidationError, match="exactly one reconciliation record"):
        FeasibilityReportPackage.model_validate(payload)


def test_not_applicable_reconciliation_forbids_hidden_operands() -> None:
    with pytest.raises(ValidationError, match="forbids operands"):
        ReconciliationRecord(
            reconciliation_id="reconciliation:fake-na",
            family=ReconciliationFamily.PROJECT_BASIS,
            name="False N/A",
            status=ReconciliationStatus.NOT_APPLICABLE,
            section_ids=("one",),
            output_ids=(),
            detail="It carries an operand and therefore is not honestly N/A.",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("retrieval_date", _DAY + timedelta(days=1), "after evidence cutoff"),
        (
            "effective_date",
            _DAY + timedelta(days=1),
            "not effective at evidence cutoff",
        ),
        ("expiry_date", _DAY - timedelta(days=1), "expired before evidence cutoff"),
        ("jurisdictions", ("FIC",), "wrong jurisdiction scope"),
    ],
)
def test_source_cutoff_expiry_and_jurisdiction_are_enforced(
    field: str, value: Any, message: str
) -> None:
    payload = _payload(_build_package())
    payload["source_register"]["records"][0][field] = value
    with pytest.raises(ValidationError, match=message):
        FeasibilityReportPackage.model_validate(payload)


def test_future_wrong_scope_source_cannot_be_marked_sufficient() -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    evidence_id = section["evidence_ids"][0]
    item = next(
        record
        for record in payload["evidence_register"]["records"]
        if record["evidence_id"] == evidence_id
    )
    item["source_id"] = "source:lk"
    item["sufficiency"] = EvidenceStatus.SUFFICIENT_FOR_ACHIEVED_GRADE
    item["required_external_item"] = None
    payload["source_register"]["records"][0]["retrieval_date"] = _DAY + timedelta(
        days=1
    )
    with pytest.raises(ValidationError, match="sufficient_for_achieved_grade|cutoff"):
        FeasibilityReportPackage.model_validate(payload)


def test_synthetic_source_must_remain_synthetic_only() -> None:
    payload = _payload(_build_package())
    payload["source_register"]["records"][0]["source_class"] = SourceClass.SYNTHETIC
    section = _first_applicable(payload)
    evidence_id = section["evidence_ids"][0]
    item = next(
        record
        for record in payload["evidence_register"]["records"]
        if record["evidence_id"] == evidence_id
    )
    item["source_id"] = "source:lk"
    item["sufficiency"] = EvidenceStatus.LIMITED
    item["required_external_item"] = None
    item["period"] = "2026 fixture"
    section["evidence_status"] = EvidenceStatus.LIMITED
    with pytest.raises(ValidationError, match="synthetic source"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize(
    ("evidence_field", "evidence_value", "message"),
    [
        ("period", "unrelated period", "exact claim scope and period"),
        (
            "authenticity_status",
            AuthenticityStatus.AUTHENTICATED,
            "authenticity cannot exceed",
        ),
    ],
)
def test_evidence_cannot_exceed_source_period_or_authenticity(
    evidence_field: str, evidence_value: Any, message: str
) -> None:
    payload = _payload(_build_package())
    source = payload["source_register"]["records"][0]
    source["authenticity_status"] = AuthenticityStatus.UNVERIFIED
    section = _first_applicable(payload)
    evidence_id = section["evidence_ids"][0]
    item = next(
        record
        for record in payload["evidence_register"]["records"]
        if record["evidence_id"] == evidence_id
    )
    item["source_id"] = "source:lk"
    item["sufficiency"] = EvidenceStatus.LIMITED
    item["required_external_item"] = None
    item["period"] = "2026 fixture"
    item[evidence_field] = evidence_value
    section["evidence_status"] = EvidenceStatus.LIMITED
    with pytest.raises(ValidationError, match=message):
        FeasibilityReportPackage.model_validate(payload)


def _add_independent_evidence_review(payload: dict[str, Any]) -> str:
    section = _first_applicable(payload)
    section_id = section["section_id"]
    claim_id = section["claim_ids"][0]
    evidence_id = section["evidence_ids"][0]
    actor = ActorRecord(
        actor_id="actor:evidence-reviewer",
        kind=ActorKind.HUMAN,
        name="Independent evidence reviewer",
        organization="Evidence Review Ltd",
        identity_verified=True,
        authority_basis="Named independent evidence-review appointment.",
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        actor,
    )
    binding = _report_subject(
        section_ids=(section_id,),
        claim_ids=(claim_id,),
        evidence_ids=(evidence_id,),
    )
    decision = DecisionRecord(
        decision_id="decision:evidence-review",
        kind=DecisionKind.REVIEW,
        outcome=DecisionOutcome.ACCEPTED,
        authority_actor_id=actor["actor_id"],
        authority_basis="Named independent evidence-review appointment.",
        scope="Exact evidence item",
        subject_binding=binding,
        decision="Accept the evidence review for its exact subject only.",
        conditions=(),
        evidence_ids=(evidence_id,),
        decided_at=_NOW,
    ).model_dump(mode="python")
    review = ReviewRecord(
        review_id="review:evidence",
        reviewer_actor_id=actor["actor_id"],
        independence_status=IndependenceStatus.INDEPENDENT,
        scope="Exact evidence item",
        subject_binding=binding,
        method="Independent evidence review.",
        finding_ids=(),
        response="Accepted for exact claim/evidence scope.",
        signed_decision_id=decision["decision_id"],
        completed_at=_NOW,
    ).model_dump(mode="python")
    payload["review_register"]["records"] = (review,)
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    item = next(
        record
        for record in payload["evidence_register"]["records"]
        if record["evidence_id"] == evidence_id
    )
    item["independence_status"] = IndependenceStatus.INDEPENDENT
    item["review_ids"] = (review["review_id"],)
    return str(evidence_id)


def test_independent_evidence_requires_completed_current_exact_review() -> None:
    payload = _payload(_build_package())
    _add_independent_evidence_review(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert (
        package.evidence_register.records[0].independence_status
        is IndependenceStatus.INDEPENDENT
    )


def test_independent_evidence_rejects_unrelated_review_binding() -> None:
    payload = _payload(_build_package())
    evidence_id = _add_independent_evidence_review(payload)
    other = payload["evidence_register"]["records"][1]
    review = payload["review_register"]["records"][0]
    decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:evidence-review"
    )
    wrong_binding = _report_subject(
        section_ids=(other["claim_id"].removeprefix("claim:"),),
        claim_ids=(other["claim_id"],),
        evidence_ids=(other["evidence_id"],),
    ).model_dump(mode="python")
    review["subject_binding"] = wrong_binding
    decision["subject_binding"] = wrong_binding
    assert evidence_id != other["evidence_id"]
    with pytest.raises(ValidationError, match="exact-evidence review"):
        FeasibilityReportPackage.model_validate(payload)


def test_completed_review_and_decision_chronology_is_enforced() -> None:
    payload = _payload(_build_package())
    _add_independent_evidence_review(payload)
    completion = _NOW + timedelta(hours=1)
    payload["captured_at"] = _NOW + timedelta(hours=2)
    payload["review_register"]["records"][0]["completed_at"] = completion
    decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:evidence-review"
    )
    decision["decided_at"] = completion - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="cannot predate review completion"):
        FeasibilityReportPackage.model_validate(payload)


def test_completed_review_after_package_capture_is_rejected() -> None:
    payload = _payload(_build_package())
    _add_independent_evidence_review(payload)
    future = _NOW + timedelta(days=1)
    payload["review_register"]["records"][0]["completed_at"] = future
    decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:evidence-review"
    )
    decision["decided_at"] = future
    with pytest.raises(ValidationError, match="postdates package captured_at"):
        FeasibilityReportPackage.model_validate(payload)


def test_review_after_evidence_cutoff_but_before_capture_is_allowed() -> None:
    payload = _payload(_build_package())
    _add_independent_evidence_review(payload)
    completion = _NOW + timedelta(hours=1)
    payload["captured_at"] = completion + timedelta(hours=1)
    payload["review_register"]["records"][0]["completed_at"] = completion
    decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:evidence-review"
    )
    decision["decided_at"] = completion
    assert FeasibilityReportPackage.model_validate(payload).captured_at > _NOW


def test_package_capture_cannot_predate_report_identity() -> None:
    payload = _payload(_build_package())
    payload["captured_at"] = _NOW - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="captured_at cannot predate"):
        FeasibilityReportPackage.model_validate(payload)


def test_evidence_cutoff_cannot_postdate_package_snapshot() -> None:
    payload = _payload(_build_package())
    future_cutoff = _DAY + timedelta(days=1)
    payload["scope"]["evidence_cutoff"] = future_cutoff
    payload["run_manifest"]["evidence_cutoff"] = future_cutoff
    with pytest.raises(ValidationError, match="evidence_cutoff cannot postdate"):
        FeasibilityReportPackage.model_validate(payload)


def test_validation_event_cannot_postdate_package_snapshot() -> None:
    payload = _payload(_build_package())
    payload["validation_register"]["records"][0]["checked_at"] = _NOW + timedelta(
        seconds=1
    )
    with pytest.raises(ValidationError, match="validation .* postdates package"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("position", ["before_report", "after_capture"])
def test_held_artifact_must_exist_within_report_snapshot_lifecycle(
    position: str,
) -> None:
    payload = _payload(_build_package())
    artifact = _artifact().model_dump(mode="python")
    artifact["created_at"] = (
        _NOW - timedelta(seconds=1)
        if position == "before_report"
        else _NOW + timedelta(seconds=1)
    )
    payload["artifact_manifest"]["records"] = (artifact,)
    payload["distribution_register"]["records"][0]["artifact_ids"] = (
        artifact["artifact_id"],
    )
    expected = "predates ReportIdentity" if position == "before_report" else "postdates"
    with pytest.raises(ValidationError, match=expected):
        FeasibilityReportPackage.model_validate(payload)


def test_section_production_event_cannot_escape_package_snapshot() -> None:
    payload = _payload(_build_package())
    section = _first_applicable(payload)
    section["started_at"] = _NOW
    section["completed_at"] = _NOW + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="section .* completed after package"):
        FeasibilityReportPackage.model_validate(payload)


def test_report_bound_decision_cannot_predate_report_identity() -> None:
    payload = _payload(_build_package())
    payload["decision_register"]["records"][0]["decided_at"] = _NOW - timedelta(
        seconds=1
    )
    with pytest.raises(ValidationError, match="report-bound decision predates"):
        FeasibilityReportPackage.model_validate(payload)


def test_report_bound_review_cannot_predate_report_identity() -> None:
    payload = _payload(_build_package())
    _add_completed_section_review(payload)
    payload["review_register"]["records"][0]["completed_at"] = _NOW - timedelta(
        seconds=1
    )
    with pytest.raises(ValidationError, match="report-bound review predates"):
        FeasibilityReportPackage.model_validate(payload)


def _add_completed_section_review(
    payload: dict[str, Any], *, signer_kind: ActorKind = ActorKind.HUMAN
) -> str:
    section_id = _first_applicable(payload)["section_id"]
    actor = ActorRecord(
        actor_id="actor:reviewer",
        kind=signer_kind,
        name="Independent reviewer",
        organization=(
            "Independent Review Ltd" if signer_kind is ActorKind.HUMAN else None
        ),
        version="model-fixture" if signer_kind is ActorKind.AI_AGENT else None,
        operation="Review sign-off" if signer_kind is ActorKind.AI_AGENT else None,
        identity_verified=signer_kind is ActorKind.HUMAN,
        authority_basis=(
            "Named independent reviewer appointment."
            if signer_kind is ActorKind.HUMAN
            else None
        ),
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        actor,
    )
    binding = _report_subject(section_ids=(section_id,))
    decision = DecisionRecord(
        decision_id="decision:review",
        kind=DecisionKind.REVIEW,
        outcome=DecisionOutcome.ACCEPTED,
        authority_actor_id=actor["actor_id"],
        authority_basis="Review signatory appointment.",
        scope="Exact section review",
        subject_binding=binding,
        decision="Accept the review record only.",
        conditions=(),
        evidence_ids=(),
        decided_at=_NOW,
    ).model_dump(mode="python")
    review = ReviewRecord(
        review_id="review:section",
        reviewer_actor_id=actor["actor_id"],
        independence_status=IndependenceStatus.INDEPENDENT,
        scope="Exact section review",
        subject_binding=binding,
        method="Controlled independent contract review.",
        finding_ids=(),
        response="Accepted for the exact subject only.",
        signed_decision_id=decision["decision_id"],
        completed_at=_NOW,
    ).model_dump(mode="python")
    payload["review_register"]["records"] = (review,)
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    section = _first_applicable(payload)
    section["review_ids"] = (review["review_id"],)
    section["review_status"] = ReviewStatus.INDEPENDENTLY_ACCEPTED
    return str(section_id)


def test_exact_completed_human_review_can_mark_only_its_section_accepted() -> None:
    payload = _payload(_build_package())
    _add_completed_section_review(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert (
        _first_applicable(package.model_dump(mode="python"))["review_status"]
        is ReviewStatus.INDEPENDENTLY_ACCEPTED
    )


def test_ai_cannot_sign_completed_independent_review() -> None:
    payload = _payload(_build_package())
    _add_completed_section_review(payload, signer_kind=ActorKind.AI_AGENT)
    with pytest.raises(ValidationError, match="verified human/institution signatory"):
        FeasibilityReportPackage.model_validate(payload)


def test_unrelated_or_reused_review_cannot_mark_other_section_accepted() -> None:
    payload = _payload(_build_package())
    bound_section_id = _add_completed_section_review(payload)
    other = next(
        section
        for section in payload["sections"]
        if section["applicability"] is Applicability.APPLICABLE
        and section["section_id"] != bound_section_id
    )
    other["review_ids"] = ("review:section",)
    other["review_status"] = ReviewStatus.INDEPENDENTLY_ACCEPTED
    with pytest.raises(ValidationError, match="exact section subject binding"):
        FeasibilityReportPackage.model_validate(payload)


def test_performed_human_responsibility_requires_scope_bound_positive_decision() -> (
    None
):
    binding = _report_subject(section_ids=("executive_investment_thesis",))
    with pytest.raises(ValidationError, match="decision_id"):
        ResponsibilityAssignment(
            assignment_id="responsibility:approved",
            role=ResponsibilityRole.APPROVED,
            status=ResponsibilityStatus.PERFORMED,
            scope="Executive section",
            subject_binding=binding,
            actor_id="actor:scope-authority",
            performed_at=_NOW,
        )


def _add_performed_role(
    payload: dict[str, Any],
    *,
    role: ResponsibilityRole,
    performed_at: datetime,
    decided_at: datetime,
) -> None:
    section_id = _first_applicable(payload)["section_id"]
    binding = _report_subject(section_ids=(section_id,))
    decision = DecisionRecord(
        decision_id=f"decision:chronology:{role.value}",
        kind=DecisionKind.OTHER,
        outcome=DecisionOutcome.APPROVED,
        authority_actor_id="actor:scope-authority",
        authority_basis="Exact named performer authority.",
        scope=f"{role.value} chronology control",
        subject_binding=binding,
        decision="Support the exact performed responsibility.",
        conditions=(),
        evidence_ids=(),
        decided_at=decided_at,
    ).model_dump(mode="python")
    assignment = ResponsibilityAssignment(
        assignment_id=f"responsibility:chronology:{role.value}",
        role=role,
        status=ResponsibilityStatus.PERFORMED,
        scope=f"{role.value} chronology control",
        subject_binding=binding,
        actor_id="actor:scope-authority",
        performed_at=performed_at,
        decision_id=decision["decision_id"],
    ).model_dump(mode="python")
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["responsibility_register"]["records"] = (assignment,)


def test_approved_responsibility_actor_must_match_decision_authority() -> None:
    payload = _payload(_build_package())
    binding = _report_subject(section_ids=("executive_investment_thesis",))
    assignment = ResponsibilityAssignment(
        assignment_id="responsibility:approved",
        role=ResponsibilityRole.APPROVED,
        status=ResponsibilityStatus.PERFORMED,
        scope="Executive section",
        subject_binding=binding,
        actor_id="actor:scope-authority",
        performed_at=_NOW,
        decision_id="decision:approval",
    ).model_dump(mode="python")
    second_actor = ActorRecord(
        actor_id="actor:second",
        kind=ActorKind.HUMAN,
        name="Second authority",
        organization="Independent Review Ltd",
        identity_verified=True,
        authority_basis="Named approval authority.",
    ).model_dump(mode="python")
    decision = DecisionRecord(
        decision_id="decision:approval",
        kind=DecisionKind.OTHER,
        outcome=DecisionOutcome.APPROVED,
        authority_actor_id="actor:second",
        authority_basis="Named approval authority.",
        scope="Executive section",
        subject_binding=binding,
        decision="Approve responsibility record.",
        conditions=(),
        evidence_ids=(),
        decided_at=_NOW,
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        second_actor,
    )
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["responsibility_register"]["records"] = (assignment,)
    with pytest.raises(
        ValidationError, match="actor must be the exact decision authority"
    ):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("role", tuple(ResponsibilityRole))
def test_every_performed_human_role_accepts_exact_verified_performer_authority(
    role: ResponsibilityRole,
) -> None:
    payload = _payload(_build_package())
    section_id = _first_applicable(payload)["section_id"]
    binding = _report_subject(section_ids=(section_id,))
    decision = DecisionRecord(
        decision_id=f"decision:responsibility:{role.value}",
        kind=DecisionKind.OTHER,
        outcome=DecisionOutcome.APPROVED,
        authority_actor_id="actor:scope-authority",
        authority_basis="Exact named performer authority.",
        scope=f"{role.value} responsibility for one section",
        subject_binding=binding,
        decision="Record the exact human performer decision.",
        conditions=(),
        evidence_ids=(),
        decided_at=_NOW,
    ).model_dump(mode="python")
    assignment = ResponsibilityAssignment(
        assignment_id=f"responsibility:{role.value}",
        role=role,
        status=ResponsibilityStatus.PERFORMED,
        scope=f"{role.value} responsibility for one section",
        subject_binding=binding,
        actor_id="actor:scope-authority",
        performed_at=_NOW,
        decision_id=decision["decision_id"],
    ).model_dump(mode="python")
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["responsibility_register"]["records"] = (assignment,)
    package = FeasibilityReportPackage.model_validate(payload)
    assert package.responsibility_register.records[0].role is role


@pytest.mark.parametrize("role", tuple(ResponsibilityRole))
@pytest.mark.parametrize(
    "chronology",
    [
        "performance_before_report",
        "decision_before_performance",
        "decision_after_capture",
    ],
)
def test_every_performed_role_rejects_impossible_chronology(
    role: ResponsibilityRole, chronology: str
) -> None:
    payload = _payload(_build_package())
    payload["captured_at"] = _NOW + timedelta(hours=2)
    performed_at = _NOW + timedelta(hours=1)
    decided_at = _NOW + timedelta(hours=1)
    if chronology == "performance_before_report":
        performed_at = _NOW - timedelta(seconds=1)
        decided_at = _NOW
    elif chronology == "decision_before_performance":
        decided_at = performed_at - timedelta(seconds=1)
    else:
        decided_at = payload["captured_at"] + timedelta(seconds=1)
    _add_performed_role(
        payload,
        role=role,
        performed_at=performed_at,
        decided_at=decided_at,
    )
    with pytest.raises(
        ValidationError,
        match="performed responsibility chronology|decision postdates package captured_at",
    ):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize("role", tuple(ResponsibilityRole))
@pytest.mark.parametrize("authority_kind", [ActorKind.AI_AGENT, ActorKind.SOFTWARE])
def test_every_performed_human_role_rejects_automated_decision_authority(
    role: ResponsibilityRole, authority_kind: ActorKind
) -> None:
    payload = _payload(_build_package())
    section_id = _first_applicable(payload)["section_id"]
    binding = _report_subject(section_ids=(section_id,))
    automated_actor = ActorRecord(
        actor_id=f"actor:{authority_kind.value}",
        kind=authority_kind,
        name="Automated fixture authority",
        version="1.0.0",
        operation="Attempted human-role authorization",
    ).model_dump(mode="python")
    decision = DecisionRecord(
        decision_id=f"decision:{role.value}:{authority_kind.value}",
        kind=DecisionKind.OTHER,
        outcome=DecisionOutcome.APPROVED,
        authority_actor_id=automated_actor["actor_id"],
        authority_basis="Automated actors cannot perform this human role.",
        scope=f"{role.value} responsibility for one section",
        subject_binding=binding,
        decision="Attempt to authorize the performed human role.",
        conditions=(),
        evidence_ids=(),
        decided_at=_NOW,
    ).model_dump(mode="python")
    assignment = ResponsibilityAssignment(
        assignment_id=f"responsibility:{role.value}",
        role=role,
        status=ResponsibilityStatus.PERFORMED,
        scope=f"{role.value} responsibility for one section",
        subject_binding=binding,
        actor_id="actor:scope-authority",
        performed_at=_NOW,
        decision_id=decision["decision_id"],
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        automated_actor,
    )
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["responsibility_register"]["records"] = (assignment,)
    with pytest.raises(ValidationError, match="exact decision authority"):
        FeasibilityReportPackage.model_validate(payload)


def _make_assured_lk_pack(payload: dict[str, Any], *, pending: bool = False) -> None:
    section = _first_applicable(payload)
    evidence_id = section["evidence_ids"][0]
    evidence = next(
        item
        for item in payload["evidence_register"]["records"]
        if item["evidence_id"] == evidence_id
    )
    evidence["source_id"] = "source:lk"
    evidence["sufficiency"] = EvidenceStatus.LIMITED
    evidence["required_external_item"] = None
    evidence["period"] = "2026 fixture"
    section["evidence_status"] = EvidenceStatus.LIMITED
    actor = ActorRecord(
        actor_id="actor:pack-reviewer",
        kind=ActorKind.HUMAN,
        name="Independent pack reviewer",
        organization="Independent Pack Review Ltd",
        identity_verified=True,
        authority_basis="Named pack reviewer and assurance signatory.",
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        actor,
    )
    review_binding = PackVersionSubjectBinding(
        pack_id="pack:lk",
        pack_version="1.0.0-fixture",
        grade=AssessmentGrade.SCREENING,
        effective_from=date(2026, 8, 1),
        effective_until=date(2027, 8, 1),
    )
    review_decision = DecisionRecord(
        decision_id="decision:pack-review",
        kind=DecisionKind.REVIEW,
        outcome=DecisionOutcome.ACCEPTED,
        authority_actor_id=actor["actor_id"],
        authority_basis="Named independent pack review appointment.",
        scope="Exact LK pack/version review",
        subject_binding=review_binding,
        decision="Accept the exact pack review.",
        conditions=(),
        evidence_ids=(evidence_id,),
        decided_at=_NOW,
    ).model_dump(mode="python")
    review = ReviewRecord(
        review_id="review:pack-lk",
        reviewer_actor_id=actor["actor_id"],
        independence_status=(
            IndependenceStatus.INTERNAL if pending else IndependenceStatus.INDEPENDENT
        ),
        scope="Exact LK pack/version review",
        subject_binding=review_binding,
        method="Controlled pack review.",
        finding_ids=(),
        response="Pending." if pending else "Accepted for exact scope.",
        signed_decision_id=None if pending else review_decision["decision_id"],
        completed_at=None if pending else _NOW,
    ).model_dump(mode="python")
    assurance_binding = PackVersionSubjectBinding(
        pack_id="pack:lk",
        pack_version="1.0.0-fixture",
        grade=AssessmentGrade.SCREENING,
        effective_from=date(2026, 8, 1),
        effective_until=date(2027, 8, 1),
        review_ids=(review["review_id"],),
    )
    assurance = DecisionRecord(
        decision_id="decision:pack-assurance",
        kind=DecisionKind.PACK_ASSURANCE,
        outcome=DecisionOutcome.AUTHORIZED,
        authority_actor_id=actor["actor_id"],
        authority_basis="Named assurance authority.",
        scope="Exact LK pack/version assurance",
        subject_binding=assurance_binding,
        decision="Authorize the exact pack assurance record.",
        grade=AssessmentGrade.SCREENING,
        conditions=(),
        evidence_ids=() if pending else (evidence_id,),
        decided_at=_NOW,
    ).model_dump(mode="python")
    payload["review_register"]["records"] = (review,)
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        *(() if pending else (review_decision,)),
        assurance,
    )
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack["status"] = PackStatus.ASSURED
    pack["review_ids"] = (review["review_id"],)
    pack["decision_ids"] = (assurance["decision_id"],)


def test_assured_pack_requires_exact_independent_evidence_backed_authority() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    pack = next(
        item for item in package.pack_registry.records if item.pack_id == "pack:lk"
    )
    assert pack.status is PackStatus.ASSURED


def test_pack_assurance_follows_review_completion_and_signed_decision() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    completion = _NOW + timedelta(hours=1)
    review_decision_time = _NOW + timedelta(hours=2)
    assurance_time = _NOW + timedelta(hours=3)
    payload["captured_at"] = assurance_time
    payload["review_register"]["records"][0]["completed_at"] = completion
    for decision in payload["decision_register"]["records"]:
        if decision["decision_id"] == "decision:pack-review":
            decision["decided_at"] = review_decision_time
        elif decision["decision_id"] == "decision:pack-assurance":
            decision["decided_at"] = assurance_time
    package = FeasibilityReportPackage.model_validate(payload)
    assurance = next(
        item
        for item in package.decision_register.records
        if item.decision_id == "decision:pack-assurance"
    )
    assert assurance.decided_at == assurance_time


@pytest.mark.parametrize("late_event", ["completion", "signed_decision"])
def test_pack_assurance_cannot_predate_qualifying_review_events(
    late_event: str,
) -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    future = _NOW + timedelta(hours=1)
    payload["captured_at"] = future
    if late_event == "completion":
        payload["review_register"]["records"][0]["completed_at"] = future
        review_decision = next(
            item
            for item in payload["decision_register"]["records"]
            if item["decision_id"] == "decision:pack-review"
        )
        review_decision["decided_at"] = future
    else:
        review_decision = next(
            item
            for item in payload["decision_register"]["records"]
            if item["decision_id"] == "decision:pack-review"
        )
        review_decision["decided_at"] = future
    with pytest.raises(ValidationError, match="pack-assurance decision cannot predate"):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_review_may_predate_report_identity_but_not_package_capture() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    pack_review_time = _NOW - timedelta(days=1)
    payload["review_register"]["records"][0]["completed_at"] = pack_review_time
    review_decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:pack-review"
    )
    review_decision["decided_at"] = pack_review_time
    package = FeasibilityReportPackage.model_validate(payload)
    completed_at = package.review_register.records[0].completed_at
    assert completed_at is not None
    assert completed_at < package.identity.created_at


def test_assured_pack_rejects_pending_internal_review_and_empty_decision_evidence() -> (
    None
):
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload, pending=True)
    with pytest.raises(
        ValidationError, match="current independent review|positive assurance"
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_assured_pack_rejects_owner_as_independent_reviewer() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack["owner_actor_id"] = "actor:pack-reviewer"
    with pytest.raises(ValidationError, match="current independent review"):
        FeasibilityReportPackage.model_validate(payload)


def test_assured_pack_accepts_verified_institution_owner() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    owner = payload["actor_register"]["records"][0]
    owner["kind"] = ActorKind.INSTITUTION
    owner["name"] = "DutchBay controlled owning institution"
    package = FeasibilityReportPackage.model_validate(payload)
    pack = next(
        item for item in package.pack_registry.records if item.pack_id == "pack:lk"
    )
    assert pack.status is PackStatus.ASSURED


@pytest.mark.parametrize("owner_kind", [ActorKind.AI_AGENT, ActorKind.SOFTWARE])
def test_assured_pack_rejects_automated_owner(owner_kind: ActorKind) -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    automated_owner = ActorRecord(
        actor_id=f"actor:pack-owner:{owner_kind.value}",
        kind=owner_kind,
        name="Automated pack owner",
        version="1.0.0",
        operation="Pack production",
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        automated_owner,
    )
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack["owner_actor_id"] = automated_owner["actor_id"]
    with pytest.raises(ValidationError, match="assured pack owner requires a verified"):
        FeasibilityReportPackage.model_validate(payload)


def test_assured_pack_reviewer_must_have_distinct_organization() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    reviewer = next(
        item
        for item in payload["actor_register"]["records"]
        if item["actor_id"] == "actor:pack-reviewer"
    )
    reviewer["organization"] = "DutchBay test fixture"
    with pytest.raises(ValidationError, match="current independent review"):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_assurance_authority_must_be_independent_of_owner() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    assurance = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:pack-assurance"
    )
    assurance["authority_actor_id"] = "actor:scope-authority"
    with pytest.raises(ValidationError, match="independent of the pack owner"):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_assurance_authority_must_have_distinct_organization() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    weak_authority = ActorRecord(
        actor_id="actor:same-org-assurance",
        kind=ActorKind.HUMAN,
        name="Separate person at producing organization",
        organization="DutchBay test fixture",
        identity_verified=True,
        authority_basis="Named assurance appointment.",
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        weak_authority,
    )
    assurance = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:pack-assurance"
    )
    assurance["authority_actor_id"] = weak_authority["actor_id"]
    with pytest.raises(ValidationError, match="independent of the pack owner"):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_review_and_assurance_evidence_must_belong_to_exact_pack() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    evidence_id = _first_applicable(payload)["evidence_ids"][0]
    evidence = next(
        item
        for item in payload["evidence_register"]["records"]
        if item["evidence_id"] == evidence_id
    )
    evidence["source_id"] = "source:wind"
    for decision in payload["decision_register"]["records"]:
        if decision["decision_id"] in {
            "decision:pack-review",
            "decision:pack-assurance",
        }:
            decision["evidence_ids"] = (evidence_id,)
    with pytest.raises(
        ValidationError,
        match="current independent review|usable pack evidence",
    ):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_review_evidence_must_be_relevant_and_usable() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    evidence_id = _first_applicable(payload)["evidence_ids"][0]
    evidence = next(
        item
        for item in payload["evidence_register"]["records"]
        if item["evidence_id"] == evidence_id
    )
    evidence["sufficiency"] = EvidenceStatus.MISSING
    evidence["required_external_item"] = "Obtain usable review evidence."
    _first_applicable(payload)["evidence_status"] = EvidenceStatus.MISSING
    with pytest.raises(ValidationError, match="current independent review"):
        FeasibilityReportPackage.model_validate(payload)


def test_pack_assurance_review_set_must_equal_exact_qualifying_set() -> None:
    payload = _payload(_build_package())
    _make_assured_lk_pack(payload)
    extra_review = ReviewRecord(
        review_id="review:pack-lk-pending",
        reviewer_actor_id="actor:pack-reviewer",
        independence_status=IndependenceStatus.INDEPENDENT,
        scope="Pending second review of exact LK pack",
        subject_binding=PackVersionSubjectBinding(
            pack_id="pack:lk",
            pack_version="1.0.0-fixture",
            grade=AssessmentGrade.SCREENING,
            effective_from=date(2026, 8, 1),
            effective_until=date(2027, 8, 1),
        ),
        method="Controlled pending rereview.",
        finding_ids=(),
        response="Pending.",
    ).model_dump(mode="python")
    payload["review_register"]["records"] = (
        *payload["review_register"]["records"],
        extra_review,
    )
    pack = next(
        item
        for item in payload["pack_registry"]["records"]
        if item["pack_id"] == "pack:lk"
    )
    pack["review_ids"] = (*pack["review_ids"], extra_review["review_id"])
    assurance = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:pack-assurance"
    )
    assurance["subject_binding"]["review_ids"] = (
        *assurance["subject_binding"]["review_ids"],
        extra_review["review_id"],
    )
    with pytest.raises(ValidationError, match="exact positive assurance decision"):
        FeasibilityReportPackage.model_validate(payload)


def test_denial_outcome_and_unverified_human_cannot_authorize_release() -> None:
    payload = _payload(_build_package())
    artifact = _artifact().model_dump(mode="python")
    payload["artifact_manifest"]["records"] = (artifact,)
    payload["distribution_register"]["records"][0]["artifact_ids"] = (
        artifact["artifact_id"],
    )
    weak_actor = ActorRecord(
        actor_id="actor:weak-release",
        kind=ActorKind.HUMAN,
        name="Unverified release actor",
        organization="Unknown organization",
    ).model_dump(mode="python")
    payload["actor_register"]["records"] = (
        *payload["actor_register"]["records"],
        weak_actor,
    )
    evidence_id = _first_applicable(payload)["evidence_ids"][0]
    release_section = _first_applicable(payload)
    release_claim_id = release_section["claim_ids"][0]
    decision = DecisionRecord(
        decision_id="decision:release-denied",
        kind=DecisionKind.RELEASE,
        outcome=DecisionOutcome.DENIED,
        authority_actor_id=weak_actor["actor_id"],
        authority_basis="Unverified assertion.",
        scope="Whole fixture",
        subject_binding=_report_subject(
            section_ids=(release_section["section_id"],),
            claim_ids=(release_claim_id,),
            evidence_ids=(evidence_id,),
            artifact_ids=(artifact["artifact_id"],),
        ),
        decision="Release is denied.",
        conditions=(),
        evidence_ids=(evidence_id,),
        decided_at=_NOW,
    ).model_dump(mode="python")
    payload["decision_register"]["records"] = (
        *payload["decision_register"]["records"],
        decision,
    )
    payload["package_release"] = PackageRelease(
        status=PackageReleaseStatus.AUTHORIZED,
        report_id="report:fixture",
        artifact_ids=(artifact["artifact_id"],),
        distribution_ids=("distribution:package",),
        scope="Whole fixture",
        conditions=(),
        authority_actor_id=weak_actor["actor_id"],
        decision_id=decision["decision_id"],
        decided_at=_NOW,
        reason="Negative control.",
    ).model_dump(mode="python")
    with pytest.raises(ValidationError, match="positive evidence-backed authority"):
        FeasibilityReportPackage.model_validate(payload)


@pytest.mark.parametrize(
    "metadata",
    [
        {"authority_actor_id": "actor:scope-authority"},
        {"decision_id": "decision:scope"},
        {"decided_at": _NOW},
        {
            "authority_actor_id": "actor:scope-authority",
            "decision_id": "decision:scope",
            "decided_at": _NOW,
        },
    ],
)
def test_held_release_rejects_positive_authority_metadata(
    metadata: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="held package forbids release authority"):
        PackageRelease(
            report_id="report:fixture",
            artifact_ids=(),
            scope="Controlled hold",
            conditions=("Independent acceptance remains pending.",),
            reason="Held means held.",
            **metadata,
        )


def test_held_release_rejects_distribution_authorization_metadata() -> None:
    with pytest.raises(ValidationError, match="forbids release distribution"):
        PackageRelease(
            report_id="report:fixture",
            artifact_ids=(),
            distribution_ids=("distribution:package",),
            scope="Controlled hold",
            conditions=("Independent acceptance remains pending.",),
            reason="Held means no selected release controls.",
        )


def test_authorized_release_requires_distribution_binding() -> None:
    with pytest.raises(ValidationError, match="distribution binding"):
        PackageRelease(
            status=PackageReleaseStatus.AUTHORIZED,
            report_id="report:fixture",
            artifact_ids=("artifact:json",),
            scope="Invalid unbound release",
            conditions=(),
            authority_actor_id="actor:release-authority",
            decision_id="decision:release",
            decided_at=_NOW,
            reason="Negative control.",
        )


def test_evidence_backed_partial_release_obeys_snapshot_chronology() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    package = FeasibilityReportPackage.model_validate(payload)
    assert package.package_release.status is PackageReleaseStatus.AUTHORIZED
    assert package.package_release.decided_at == package.captured_at
    assert package.package_release.distribution_ids == ("distribution:package",)


def test_authorized_release_binds_every_exact_artifact_distribution_control() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    extra_control = dict(payload["distribution_register"]["records"][0])
    extra_control["distribution_id"] = "distribution:additional-audience"
    payload["distribution_register"]["records"] = (
        *payload["distribution_register"]["records"],
        extra_control,
    )
    with pytest.raises(ValidationError, match="every exact distribution control"):
        FeasibilityReportPackage.model_validate(payload)


def test_release_distribution_control_cannot_cover_unreleased_artifacts() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    extra_artifact = _artifact().model_dump(mode="python")
    extra_artifact["artifact_id"] = "artifact:extra"
    extra_artifact["content_digest"]["value"] = "2" * 64
    payload["artifact_manifest"]["records"] = (
        *payload["artifact_manifest"]["records"],
        extra_artifact,
    )
    control = payload["distribution_register"]["records"][0]
    control["artifact_ids"] = (*control["artifact_ids"], extra_artifact["artifact_id"])
    with pytest.raises(ValidationError, match="exactly cover released artifacts"):
        FeasibilityReportPackage.model_validate(payload)


def test_authorized_release_rejects_expired_distribution_control() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    payload["distribution_register"]["records"][0]["expiry_or_review_date"] = (
        _DAY - timedelta(days=1)
    )
    with pytest.raises(ValidationError, match="distribution control is expired"):
        FeasibilityReportPackage.model_validate(payload)


def test_authorized_artifact_cannot_predate_report_identity() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    payload["artifact_manifest"]["records"][0]["created_at"] = _NOW - timedelta(
        seconds=1
    )
    with pytest.raises(ValidationError, match="predates ReportIdentity"):
        FeasibilityReportPackage.model_validate(payload)


def test_release_decision_cannot_predate_bound_artifact() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    artifact_time = _NOW + timedelta(hours=1)
    payload["captured_at"] = artifact_time
    payload["artifact_manifest"]["records"][0]["created_at"] = artifact_time
    with pytest.raises(ValidationError, match="artifact-bound decision predates"):
        FeasibilityReportPackage.model_validate(payload)


def test_release_decision_cannot_postdate_package_capture() -> None:
    payload = _payload(_build_package())
    _authorize_partial_artifact(payload)
    future = _NOW + timedelta(seconds=1)
    decision = next(
        item
        for item in payload["decision_register"]["records"]
        if item["decision_id"] == "decision:release-authorized"
    )
    decision["decided_at"] = future
    payload["package_release"]["decided_at"] = future
    with pytest.raises(ValidationError, match="postdates package captured_at"):
        FeasibilityReportPackage.model_validate(payload)


def test_public_full_artifact_rejects_restricted_sources_without_bindings() -> None:
    payload = _payload(_build_package())
    artifact = _artifact(full=True).model_dump(mode="python")
    artifact["confidentiality"] = ConfidentialityClass.PUBLIC
    payload["artifact_manifest"]["records"] = (artifact,)
    control = payload["distribution_register"]["records"][0]
    control["artifact_ids"] = (artifact["artifact_id"],)
    control["distribution_class"] = ConfidentialityClass.PUBLIC
    with pytest.raises(ValidationError, match="structured redaction"):
        FeasibilityReportPackage.model_validate(payload)


def test_public_full_artifact_accepts_validated_structured_omissions() -> None:
    payload = _payload(_build_package())
    artifact = _artifact(full=True).model_dump(mode="python")
    artifact["confidentiality"] = ConfidentialityClass.PUBLIC
    payload["artifact_manifest"]["records"] = (artifact,)
    control = payload["distribution_register"]["records"][0]
    control["artifact_ids"] = (artifact["artifact_id"],)
    control["distribution_class"] = ConfidentialityClass.PUBLIC
    control["disclosure_bindings"] = tuple(
        ArtifactDisclosureBinding(
            artifact_id=artifact["artifact_id"],
            source_id=source_id,
            action=DisclosureAction.OMIT,
            reason="Restricted fixture source is omitted from public projection.",
            validation_id=(
                "validation:lk-pack"
                if source_id == "source:lk"
                else "validation:wind-pack"
            ),
        ).model_dump(mode="python")
        for source_id in artifact["source_ids"]
    )
    package = FeasibilityReportPackage.model_validate(payload)
    assert package.package_release.status is PackageReleaseStatus.HOLD


def test_disclosure_binding_must_belong_to_control_and_artifact() -> None:
    payload = _payload(_build_package())
    artifact = _artifact().model_dump(mode="python")
    artifact["source_ids"] = ("source:lk",)
    payload["artifact_manifest"]["records"] = (artifact,)
    control = payload["distribution_register"]["records"][0]
    control["artifact_ids"] = (artifact["artifact_id"],)
    control["disclosure_bindings"] = (
        ArtifactDisclosureBinding(
            artifact_id=artifact["artifact_id"],
            source_id="source:wind",
            action=DisclosureAction.OMIT,
            reason="Wrong artifact/source edge negative control.",
            validation_id="validation:wind-pack",
        ).model_dump(mode="python"),
    )
    with pytest.raises(ValidationError, match="source is absent from its artifact"):
        FeasibilityReportPackage.model_validate(payload)


def test_full_artifact_cannot_omit_source_identity_from_manifest() -> None:
    payload = _payload(_build_package())
    artifact = _artifact(full=True).model_dump(mode="python")
    artifact["source_ids"] = ("source:lk",)
    payload["artifact_manifest"]["records"] = (artifact,)
    payload["distribution_register"]["records"][0]["artifact_ids"] = (
        artifact["artifact_id"],
    )
    with pytest.raises(ValidationError, match="complete source registry"):
        FeasibilityReportPackage.model_validate(payload)


def test_unknown_capability_discriminator_fails() -> None:
    payload = _payload(_build_package())
    payload["capability_registry"]["records"][0]["outcome"] = "silently_skipped"
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        FeasibilityReportPackage.model_validate(payload)


def test_non_utc_timestamp_fails() -> None:
    identity = _build_package().identity.model_dump(mode="python")
    identity["created_at"] = datetime(2026, 8, 28, 8, 0)
    with pytest.raises(ValidationError, match="RFC 3339 UTC"):
        ReportIdentity.model_validate(identity)


def test_unresolved_cross_registry_reference_fails() -> None:
    payload = _payload(_build_package())
    _first_applicable(payload)["assumption_ids"] = ("assumption:ghost",)
    with pytest.raises(ValidationError, match="unresolved references"):
        FeasibilityReportPackage.model_validate(payload)


def test_output_and_derivation_models_require_explicit_unit_when_numeric() -> None:
    output = OutputReference(
        output_id="output:test",
        report_id="report:fixture",
        run_id="run:fixture",
        section_ids=("resource_and_energy_yield",),
        producing_contract="contract:test",
        producing_version="1.0.0",
        output_class=OutputClass.CANONICAL,
        locator="memory:test",
        value=CanonicalValue(value_type=ValueType.DECIMAL, value="1.0", unit="MWh"),
    )
    assert output.value is not None and output.value.unit == "MWh"
