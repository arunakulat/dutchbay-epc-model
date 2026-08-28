"""Immutable DBAY-FRC-001 v1 feasibility-report package root.

The root owns exact taxonomy parity, identity binding, reciprocal registry
integrity and fail-closed authority checks.  It deliberately does not aggregate
grades, infer release, render artifacts, orchestrate calculations or implement
the future ProjectCase/section-result facade.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from pydantic import model_validator

from analytics.feasibility_sections import load_feasibility_taxonomy

from .records import (
    ActorRegister,
    ArtifactManifest,
    AssumptionRegister,
    CapabilityRegistry,
    ClaimRegister,
    DecisionRecord,
    DecisionRegister,
    DerivationRegister,
    DistributionRegister,
    ErrorRegister,
    EvidenceRegister,
    InputRegister,
    JudgementRegister,
    JurisdictionSubjectBinding,
    LimitationRegister,
    OutputRegister,
    PackageRelease,
    PackRegistry,
    PackVersionSubjectBinding,
    ReconciliationRegister,
    ReportIdentity,
    ReportSubjectBinding,
    ResponsibilityRegister,
    ReviewFindingRegister,
    ReviewRecord,
    ReviewRegister,
    RunManifest,
    ScopeDeclaration,
    SectionRecord,
    SourceRegister,
    SubjectBinding,
    UnsupportedJurisdictionCapability,
    UtcDateTime,
    ValidationRegister,
)
from .vocabulary import (
    FEASIBILITY_REPORT_CONTRACT_VERSION,
    FEASIBILITY_REPORT_SCHEMA_ID,
    AchievedGrade,
    ActorKind,
    Applicability,
    AssessmentGrade,
    AuthenticityStatus,
    CapabilityOutcome,
    ConfidentialityClass,
    DecisionKind,
    DecisionOutcome,
    DisclosureAction,
    EvidenceStatus,
    FindingStatus,
    GovernedSubjectKind,
    Identifier,
    IndependenceStatus,
    InputKind,
    InputResolutionStatus,
    Materiality,
    PackageReleaseStatus,
    PackKind,
    PackStatus,
    ProductionStatus,
    ReconciliationFamily,
    ReconciliationStatus,
    ResponsibilityStatus,
    ReviewStatus,
    SectionAchievedGrade,
    SectionReleaseStatus,
    SourceClass,
    StrictFrozenModel,
    ValidationStatus,
)

# DBAY-FRC-001 section 8 requirements enrich the YAML-resolved taxonomy; this is
# intentionally not a competing section identity or order source.
_ALWAYS_APPLICABLE = frozenset(
    {
        "executive_investment_thesis",
        "project_description_and_structure",
        "risk_register_and_mitigations",
        "decision_checklist_conditions_precedent",
        "appendices_provenance_audit_trail",
    }
)
_POSITIVE_OUTCOMES = frozenset(
    {
        DecisionOutcome.APPROVED,
        DecisionOutcome.ACCEPTED,
        DecisionOutcome.AUTHORIZED,
    }
)
_STRUCTURAL_SOURCE_CLASSES = frozenset(
    {
        SourceClass.AUTHENTICATED_PROJECT,
        SourceClass.OFFICIAL_PRIMARY,
        SourceClass.CONTRACTED,
        SourceClass.VENDOR,
        SourceClass.LICENSED,
        SourceClass.BENCHMARK,
    }
)
_AUTHENTICITY_RANK = {
    AuthenticityStatus.UNVERIFIED: 0,
    AuthenticityStatus.VERIFIED: 1,
    AuthenticityStatus.AUTHENTICATED: 2,
}


def _ids(records: Iterable[object], attribute: str, label: str) -> frozenset[str]:
    """Return unique registry IDs or fail on an ambiguous duplicate."""
    values = tuple(str(getattr(record, attribute)) for record in records)
    if len(values) != len(set(values)):
        duplicates = sorted({value for value in values if values.count(value) > 1})
        raise ValueError(f"duplicate {label}: {duplicates}")
    return frozenset(values)


def _require_refs(
    references: Iterable[str], available: frozenset[str], label: str
) -> None:
    """Fail closed when a reference is absent from its typed registry."""
    missing = sorted(set(references) - available)
    if missing:
        raise ValueError(f"{label} contains unresolved references: {missing}")


class FeasibilityReportPackage(StrictFrozenModel):
    """Complete immutable semantic package for one report/run identity."""

    schema_id: Literal["dutchbay.feasibility_report_package.v1"] = (
        FEASIBILITY_REPORT_SCHEMA_ID
    )
    contract_version: Literal["1.0.0"] = FEASIBILITY_REPORT_CONTRACT_VERSION
    identity: ReportIdentity
    scope: ScopeDeclaration
    target_grade: AssessmentGrade
    captured_at: UtcDateTime
    achieved_grade: AchievedGrade = AchievedGrade.UNGRADED
    grade_decision_id: Identifier | None = None
    sections: tuple[SectionRecord, ...]
    jurisdiction_subject_bindings: tuple[JurisdictionSubjectBinding, ...]
    actor_register: ActorRegister
    responsibility_register: ResponsibilityRegister
    pack_registry: PackRegistry
    capability_registry: CapabilityRegistry
    input_register: InputRegister
    source_register: SourceRegister
    output_register: OutputRegister
    claim_register: ClaimRegister
    evidence_register: EvidenceRegister
    assumption_register: AssumptionRegister
    judgement_register: JudgementRegister
    derivation_register: DerivationRegister
    limitation_register: LimitationRegister
    error_register: ErrorRegister
    review_finding_register: ReviewFindingRegister
    review_register: ReviewRegister
    decision_register: DecisionRegister
    reconciliation_register: ReconciliationRegister
    validation_register: ValidationRegister
    run_manifest: RunManifest
    artifact_manifest: ArtifactManifest
    distribution_register: DistributionRegister
    package_release: PackageRelease

    @model_validator(mode="after")
    def _validate_package(self) -> FeasibilityReportPackage:
        self._validate_taxonomy_scope_and_v1_grade_boundary()
        ids = self._registry_ids()
        self._validate_references(ids)
        self._validate_identity_and_subjects(ids)
        self._validate_reciprocal_graph()
        self._validate_pack_and_state_bindings()
        self._validate_authority_and_review()
        self._validate_distribution()
        return self

    def _validate_taxonomy_scope_and_v1_grade_boundary(self) -> None:
        expected = load_feasibility_taxonomy().section_names
        actual = tuple(section.section_id for section in self.sections)
        if actual != expected:
            raise ValueError(
                "sections must contain exactly the taxonomy SSOT IDs in order; "
                f"expected={expected!r}, actual={actual!r}"
            )
        if self.target_grade != self.scope.target_grade:
            raise ValueError("package target_grade must equal scope.target_grade")
        if (
            self.achieved_grade is not AchievedGrade.UNGRADED
            or self.grade_decision_id is not None
        ):
            raise ValueError(
                "DBAY-FRC-001 v1 accepts only achieved_grade=ungraded and "
                "grade_decision_id=None; non-sentinel grading requires a future "
                "typed grade-policy receipt"
            )
        if not self.distribution_register.records:
            raise ValueError("package requires at least one distribution control")
        reconciliation_families = tuple(
            item.family for item in self.reconciliation_register.records
        )
        if (
            len(reconciliation_families) != len(ReconciliationFamily)
            or len(set(reconciliation_families)) != len(ReconciliationFamily)
            or set(reconciliation_families) != set(ReconciliationFamily)
        ):
            raise ValueError(
                "package requires exactly one reconciliation record for each "
                "ReconciliationFamily"
            )
        if not any(
            set(self.scope.intended_audiences) <= set(control.intended_audiences)
            and set(self.scope.intended_uses) <= set(control.permitted_uses)
            for control in self.distribution_register.records
        ):
            raise ValueError(
                "distribution controls do not cover the scope audience and intended use"
            )
        for attribute in (
            "technology_ids",
            "jurisdictions",
            "jurisdiction_pack_ids",
            "technology_pack_ids",
        ):
            values = getattr(self.scope, attribute)
            if len(values) != len(set(values)):
                raise ValueError(f"scope {attribute} contains duplicate references")
        for section in self.sections:
            if section.target_grade is not self.target_grade:
                raise ValueError(
                    f"section {section.section_id} target_grade does not match package target"
                )
            if section.achieved_grade not in {
                SectionAchievedGrade.UNGRADED,
                SectionAchievedGrade.NOT_APPLICABLE,
            }:
                raise ValueError(
                    "DBAY-FRC-001 v1 section achieved_grade must be ungraded or "
                    "not_applicable; graded sections require future grade policy"
                )
            if (
                section.section_id in _ALWAYS_APPLICABLE
                and section.applicability is not Applicability.APPLICABLE
            ):
                raise ValueError(
                    f"{section.section_id} is always applicable under DBAY-FRC-001 section 8"
                )
            if section.applicability is Applicability.APPLICABLE and (
                not section.jurisdiction_pack_ids or not section.technology_pack_ids
            ):
                raise ValueError(
                    f"applicable section {section.section_id} requires jurisdiction and "
                    "technology pack links"
                )
            for attribute in (
                "output_references",
                "required_inputs",
                "resolved_inputs",
                "derived_inputs",
                "capability_dispositions",
                "jurisdiction_pack_ids",
                "technology_pack_ids",
                "source_ids",
                "claim_ids",
                "evidence_ids",
                "assumption_ids",
                "judgement_ids",
                "limitation_ids",
                "error_ids",
                "review_ids",
                "decision_ids",
            ):
                values = getattr(section, attribute)
                if len(values) != len(set(values)):
                    raise ValueError(
                        f"section {section.section_id} {attribute} contains duplicates"
                    )

    def _registry_ids(self) -> dict[str, frozenset[str]]:
        return {
            "actors": _ids(self.actor_register.records, "actor_id", "actor IDs"),
            "responsibilities": _ids(
                self.responsibility_register.records,
                "assignment_id",
                "responsibility assignment IDs",
            ),
            "jurisdiction_bindings": _ids(
                self.jurisdiction_subject_bindings,
                "binding_id",
                "jurisdiction subject binding IDs",
            ),
            "packs": _ids(self.pack_registry.records, "pack_id", "pack IDs"),
            "capabilities": _ids(
                self.capability_registry.records, "capability_id", "capability IDs"
            ),
            "inputs": _ids(self.input_register.records, "input_id", "input IDs"),
            "sources": _ids(self.source_register.records, "source_id", "source IDs"),
            "outputs": _ids(self.output_register.records, "output_id", "output IDs"),
            "claims": _ids(self.claim_register.records, "claim_id", "claim IDs"),
            "evidence": _ids(
                self.evidence_register.records, "evidence_id", "evidence IDs"
            ),
            "assumptions": _ids(
                self.assumption_register.records, "assumption_id", "assumption IDs"
            ),
            "judgements": _ids(
                self.judgement_register.records, "judgement_id", "judgement IDs"
            ),
            "derivations": _ids(
                self.derivation_register.records, "derivation_id", "derivation IDs"
            ),
            "limitations": _ids(
                self.limitation_register.records, "limitation_id", "limitation IDs"
            ),
            "errors": _ids(self.error_register.records, "error_id", "error IDs"),
            "findings": _ids(
                self.review_finding_register.records, "finding_id", "finding IDs"
            ),
            "reviews": _ids(self.review_register.records, "review_id", "review IDs"),
            "decisions": _ids(
                self.decision_register.records, "decision_id", "decision IDs"
            ),
            "reconciliations": _ids(
                self.reconciliation_register.records,
                "reconciliation_id",
                "reconciliation IDs",
            ),
            "validations": _ids(
                self.validation_register.records, "validation_id", "validation IDs"
            ),
            "artifacts": _ids(
                self.artifact_manifest.records, "artifact_id", "artifact IDs"
            ),
            "distributions": _ids(
                self.distribution_register.records,
                "distribution_id",
                "distribution IDs",
            ),
            "sections": frozenset(section.section_id for section in self.sections),
        }

    def _validate_subject_refs(
        self,
        binding: SubjectBinding,
        ids: dict[str, frozenset[str]],
        label: str,
    ) -> None:
        if isinstance(binding, ReportSubjectBinding):
            _require_refs(binding.section_ids, ids["sections"], f"{label} sections")
            _require_refs(binding.claim_ids, ids["claims"], f"{label} claims")
            _require_refs(binding.evidence_ids, ids["evidence"], f"{label} evidence")
            _require_refs(binding.artifact_ids, ids["artifacts"], f"{label} artifacts")
            _require_refs(binding.review_ids, ids["reviews"], f"{label} reviews")
        else:
            _require_refs((binding.pack_id,), ids["packs"], f"{label} pack")
            _require_refs(binding.review_ids, ids["reviews"], f"{label} reviews")

    def _validate_references(self, ids: dict[str, frozenset[str]]) -> None:
        for actor in self.actor_register.records:
            _require_refs(actor.input_ids, ids["inputs"], "actor input_ids")
            _require_refs(actor.review_ids, ids["reviews"], "actor review_ids")
        for responsibility in self.responsibility_register.records:
            self._validate_subject_refs(
                responsibility.subject_binding, ids, "responsibility subject"
            )
            if responsibility.actor_id is not None:
                _require_refs(
                    (responsibility.actor_id,), ids["actors"], "responsibility actor"
                )
            if responsibility.decision_id is not None:
                _require_refs(
                    (responsibility.decision_id,),
                    ids["decisions"],
                    "responsibility decision",
                )
        for binding in self.jurisdiction_subject_bindings:
            _require_refs(
                (binding.disposition_pack_id,),
                ids["packs"],
                "jurisdiction subject disposition pack",
            )
            _require_refs(
                binding.contribution_section_ids,
                ids["sections"],
                "jurisdiction subject contribution sections",
            )
        for pack in self.pack_registry.records:
            _require_refs((pack.owner_actor_id,), ids["actors"], "pack owner")
            _require_refs(
                pack.compatible_pack_ids, ids["packs"], "pack compatible_pack_ids"
            )
            _require_refs(pack.section_ids, ids["sections"], "pack section_ids")
            _require_refs(
                pack.capability_ids, ids["capabilities"], "pack capability_ids"
            )
            _require_refs(
                pack.required_input_ids, ids["inputs"], "pack required inputs"
            )
            _require_refs(
                pack.optional_input_ids, ids["inputs"], "pack optional inputs"
            )
            for default in pack.input_defaults:
                _require_refs(
                    default.source_ids, ids["sources"], "pack default sources"
                )
            _require_refs(pack.output_ids, ids["outputs"], "pack outputs")
            _require_refs(pack.validation_ids, ids["validations"], "pack validations")
            _require_refs(pack.source_ids, ids["sources"], "pack sources")
            _require_refs(pack.review_ids, ids["reviews"], "pack reviews")
            _require_refs(pack.decision_ids, ids["decisions"], "pack decisions")
            _require_refs(pack.limitation_ids, ids["limitations"], "pack limitations")
        for capability in self.capability_registry.records:
            _require_refs(
                capability.section_ids, ids["sections"], "capability sections"
            )
            _require_refs(capability.pack_ids, ids["packs"], "capability packs")
            if hasattr(capability, "output_ids"):
                _require_refs(
                    capability.output_ids, ids["outputs"], "capability outputs"
                )
            for attribute, registry in (
                ("error_id", "errors"),
                ("limitation_id", "limitations"),
                ("decision_id", "decisions"),
                ("owner_actor_id", "actors"),
                ("pack_id", "packs"),
            ):
                value = getattr(capability, attribute, None)
                if value is not None:
                    _require_refs((value,), ids[registry], f"capability {attribute}")
            if hasattr(capability, "missing_input_ids"):
                _require_refs(
                    capability.missing_input_ids, ids["inputs"], "capability inputs"
                )
        for item in self.input_register.records:
            _require_refs(item.source_ids, ids["sources"], "input sources")
            _require_refs(item.derivation_ids, ids["derivations"], "input derivations")
            _require_refs(item.validation_ids, ids["validations"], "input validations")
            _require_refs(item.affected_claim_ids, ids["claims"], "input claims")
            _require_refs(item.affected_section_ids, ids["sections"], "input sections")
        for source in self.source_register.records:
            _require_refs((source.extracting_actor_id,), ids["actors"], "source actor")
            _require_refs(source.section_ids, ids["sections"], "source sections")
            _require_refs(
                source.limitation_ids, ids["limitations"], "source limitations"
            )
            _require_refs(source.review_ids, ids["reviews"], "source reviews")
            if source.supersedes_source_id is not None:
                _require_refs(
                    (source.supersedes_source_id,),
                    ids["sources"],
                    "source supersession",
                )
        for output in self.output_register.records:
            _require_refs(output.section_ids, ids["sections"], "output sections")
            _require_refs(
                output.derivation_ids, ids["derivations"], "output derivations"
            )
        for claim in self.claim_register.records:
            _require_refs((claim.section_id,), ids["sections"], "claim section")
            _require_refs(claim.output_ids, ids["outputs"], "claim outputs")
            _require_refs(claim.evidence_ids, ids["evidence"], "claim evidence")
        for evidence in self.evidence_register.records:
            _require_refs((evidence.claim_id,), ids["claims"], "evidence claim")
            if evidence.source_id is not None:
                _require_refs((evidence.source_id,), ids["sources"], "evidence source")
            _require_refs(
                evidence.limitation_ids, ids["limitations"], "evidence limits"
            )
            _require_refs(evidence.review_ids, ids["reviews"], "evidence reviews")
        for assumption in self.assumption_register.records:
            _require_refs(
                (assumption.owner_actor_id,), ids["actors"], "assumption owner"
            )
            _require_refs(
                assumption.affected_claim_ids, ids["claims"], "assumption claims"
            )
            _require_refs(
                assumption.affected_section_ids, ids["sections"], "assumption sections"
            )
            if assumption.approval_decision_id is not None:
                _require_refs(
                    (assumption.approval_decision_id,),
                    ids["decisions"],
                    "assumption decision",
                )
        for judgement in self.judgement_register.records:
            _require_refs((judgement.actor_id,), ids["actors"], "judgement actor")
            _require_refs(
                judgement.affected_claim_ids, ids["claims"], "judgement claims"
            )
            _require_refs(
                judgement.affected_section_ids, ids["sections"], "judgement sections"
            )
            _require_refs(judgement.review_ids, ids["reviews"], "judgement reviews")
        for derivation in self.derivation_register.records:
            _require_refs(derivation.input_ids, ids["inputs"], "derivation inputs")
            _require_refs(derivation.source_ids, ids["sources"], "derivation sources")
            _require_refs(
                derivation.assumption_ids, ids["assumptions"], "derivation assumptions"
            )
            _require_refs(
                derivation.derived_input_ids, ids["inputs"], "derivation derived inputs"
            )
            _require_refs(derivation.output_ids, ids["outputs"], "derivation outputs")
            _require_refs(
                derivation.validation_ids, ids["validations"], "derivation validations"
            )
        for limitation in self.limitation_register.records:
            _require_refs(
                limitation.affected_claim_ids, ids["claims"], "limitation claims"
            )
            _require_refs(
                limitation.affected_section_ids, ids["sections"], "limitation sections"
            )
            _require_refs(
                (limitation.owner_actor_id,), ids["actors"], "limitation owner"
            )
        for error in self.error_register.records:
            _require_refs(
                (error.capability_id,), ids["capabilities"], "error capability"
            )
            _require_refs(error.section_ids, ids["sections"], "error sections")
        for finding in self.review_finding_register.records:
            _require_refs(finding.affected_claim_ids, ids["claims"], "finding claims")
            _require_refs(
                finding.affected_section_ids, ids["sections"], "finding sections"
            )
            if finding.decision_id is not None:
                _require_refs(
                    (finding.decision_id,), ids["decisions"], "finding decision"
                )
        for review in self.review_register.records:
            _require_refs((review.reviewer_actor_id,), ids["actors"], "review actor")
            _require_refs(review.finding_ids, ids["findings"], "review findings")
            self._validate_subject_refs(review.subject_binding, ids, "review subject")
            if review.signed_decision_id is not None:
                _require_refs(
                    (review.signed_decision_id,), ids["decisions"], "review decision"
                )
        for decision in self.decision_register.records:
            _require_refs(
                (decision.authority_actor_id,), ids["actors"], "decision actor"
            )
            _require_refs(decision.evidence_ids, ids["evidence"], "decision evidence")
            self._validate_subject_refs(
                decision.subject_binding, ids, "decision subject"
            )
            if decision.supersedes_decision_id is not None:
                _require_refs(
                    (decision.supersedes_decision_id,),
                    ids["decisions"],
                    "decision supersession",
                )
        for reconciliation in self.reconciliation_register.records:
            _require_refs(
                reconciliation.section_ids, ids["sections"], "reconciliation sections"
            )
            _require_refs(
                reconciliation.output_ids, ids["outputs"], "reconciliation outputs"
            )
            _require_refs(
                reconciliation.limitation_ids,
                ids["limitations"],
                "reconciliation limitations",
            )
        for artifact in self.artifact_manifest.records:
            _require_refs(artifact.source_ids, ids["sources"], "artifact sources")
            if artifact.supersedes_artifact_id is not None:
                _require_refs(
                    (artifact.supersedes_artifact_id,),
                    ids["artifacts"],
                    "artifact supersession",
                )
        for control in self.distribution_register.records:
            _require_refs(
                control.artifact_ids, ids["artifacts"], "distribution artifacts"
            )
            for disclosure_binding in control.disclosure_bindings:
                _require_refs(
                    (disclosure_binding.artifact_id,),
                    ids["artifacts"],
                    "disclosure artifact",
                )
                _require_refs(
                    (disclosure_binding.source_id,),
                    ids["sources"],
                    "disclosure source",
                )
                if disclosure_binding.validation_id is not None:
                    _require_refs(
                        (disclosure_binding.validation_id,),
                        ids["validations"],
                        "disclosure validation",
                    )
        _require_refs(
            self.package_release.artifact_ids, ids["artifacts"], "release artifacts"
        )
        _require_refs(
            self.package_release.distribution_ids,
            ids["distributions"],
            "release distributions",
        )
        for section in self.sections:
            for attribute, registry in (
                ("output_references", "outputs"),
                ("required_inputs", "inputs"),
                ("resolved_inputs", "inputs"),
                ("derived_inputs", "inputs"),
                ("capability_dispositions", "capabilities"),
                ("jurisdiction_pack_ids", "packs"),
                ("technology_pack_ids", "packs"),
                ("source_ids", "sources"),
                ("claim_ids", "claims"),
                ("evidence_ids", "evidence"),
                ("assumption_ids", "assumptions"),
                ("judgement_ids", "judgements"),
                ("limitation_ids", "limitations"),
                ("error_ids", "errors"),
                ("review_ids", "reviews"),
                ("decision_ids", "decisions"),
            ):
                _require_refs(
                    getattr(section, attribute),
                    ids[registry],
                    f"section {section.section_id} {attribute}",
                )

    def _validate_report_subject(
        self, binding: SubjectBinding, label: str
    ) -> ReportSubjectBinding:
        if not isinstance(binding, ReportSubjectBinding):
            raise ValueError(f"{label} requires an exact report/run subject")
        if (binding.report_id, binding.run_id) != (
            self.identity.report_id,
            self.identity.run_id,
        ):
            raise ValueError(f"{label} has foreign report/run subject")
        claims = {item.claim_id: item for item in self.claim_register.records}
        evidence = {item.evidence_id: item for item in self.evidence_register.records}

        for claim_id in binding.claim_ids:
            if claims[claim_id].section_id not in binding.section_ids:
                raise ValueError(f"{label} claim is outside its section binding")
        for evidence_id in binding.evidence_ids:
            claim = claims[evidence[evidence_id].claim_id]
            if (
                claim.claim_id not in binding.claim_ids
                or claim.section_id not in binding.section_ids
            ):
                raise ValueError(
                    f"{label} evidence is outside its claim/section binding"
                )
        return binding

    def _validate_identity_and_subjects(self, ids: dict[str, frozenset[str]]) -> None:
        identity = self.identity
        manifest = self.run_manifest
        for actual, expected, label in (
            (manifest.report_id, identity.report_id, "run manifest report_id"),
            (manifest.project_id, identity.project_id, "run manifest project_id"),
            (manifest.case_id, identity.case_id, "run manifest case_id"),
            (manifest.run_id, identity.run_id, "run manifest run_id"),
            (
                self.package_release.report_id,
                identity.report_id,
                "package release report_id",
            ),
        ):
            if actual != expected:
                raise ValueError(f"{label} does not match ReportIdentity")
        if manifest.created_at != identity.created_at:
            raise ValueError("run manifest created_at does not match ReportIdentity")
        if self.captured_at < identity.created_at:
            raise ValueError(
                "package captured_at cannot predate ReportIdentity.created_at"
            )
        if self.scope.evidence_cutoff > self.captured_at.date():
            raise ValueError("evidence_cutoff cannot postdate package captured_at")
        if manifest.valuation_date != self.scope.valuation_date:
            raise ValueError("run manifest valuation_date does not match scope")
        if manifest.evidence_cutoff != self.scope.evidence_cutoff:
            raise ValueError("run manifest evidence_cutoff does not match scope")
        if (manifest.report_issue, manifest.report_revision) != (
            identity.issue,
            identity.revision,
        ):
            raise ValueError(
                "run manifest issue/revision does not match ReportIdentity"
            )
        exact_manifest_sets = {
            "pack_ids": ids["packs"],
            "input_ids": ids["inputs"],
            "source_ids": ids["sources"],
            "assumption_ids": ids["assumptions"],
            "capability_ids": ids["capabilities"],
            "validation_ids": ids["validations"],
            "reconciliation_ids": ids["reconciliations"],
        }
        for attribute, expected_ids in exact_manifest_sets.items():
            values = getattr(manifest, attribute)
            if len(values) != len(set(values)) or frozenset(values) != expected_ids:
                raise ValueError(
                    f"run manifest {attribute} must exactly bind its registry"
                )
        for output in self.output_register.records:
            if (output.report_id, output.run_id) != (
                identity.report_id,
                identity.run_id,
            ):
                raise ValueError(
                    f"output {output.output_id} has foreign report/run identity"
                )
        for artifact in self.artifact_manifest.records:
            if (artifact.report_id, artifact.run_id) != (
                identity.report_id,
                identity.run_id,
            ):
                raise ValueError(
                    f"artifact {artifact.artifact_id} has foreign identity"
                )
            if artifact.created_at > self.captured_at:
                raise ValueError(
                    f"artifact {artifact.artifact_id} postdates package captured_at"
                )
            if artifact.created_at < identity.created_at:
                raise ValueError(
                    f"artifact {artifact.artifact_id} predates ReportIdentity.created_at"
                )
        for validation in self.validation_register.records:
            if validation.checked_at > self.captured_at:
                raise ValueError(
                    f"validation {validation.validation_id} postdates package captured_at"
                )
        for section in self.sections:
            if section.started_at is None:
                continue
            assert section.completed_at is not None
            if section.started_at < identity.created_at:
                raise ValueError(
                    f"section {section.section_id} started before ReportIdentity.created_at"
                )
            if section.completed_at > self.captured_at:
                raise ValueError(
                    f"section {section.section_id} completed after package captured_at"
                )
        for responsibility in self.responsibility_register.records:
            self._validate_report_subject(
                responsibility.subject_binding, "responsibility assignment"
            )
        for report_binding, label in (
            *(
                (review.subject_binding, f"review {review.review_id}")
                for review in self.review_register.records
                if isinstance(review.subject_binding, ReportSubjectBinding)
            ),
            *(
                (decision.subject_binding, f"decision {decision.decision_id}")
                for decision in self.decision_register.records
                if not isinstance(decision.subject_binding, PackVersionSubjectBinding)
            ),
        ):
            self._validate_report_subject(report_binding, label)
        for pack_binding, label in (
            *(
                (review.subject_binding, f"review {review.review_id}")
                for review in self.review_register.records
                if isinstance(review.subject_binding, PackVersionSubjectBinding)
            ),
            *(
                (decision.subject_binding, f"decision {decision.decision_id}")
                for decision in self.decision_register.records
                if isinstance(decision.subject_binding, PackVersionSubjectBinding)
            ),
        ):
            assert isinstance(pack_binding, PackVersionSubjectBinding)
            pack = next(
                item
                for item in self.pack_registry.records
                if item.pack_id == pack_binding.pack_id
            )
            if pack_binding.pack_version != pack.version:
                raise ValueError(f"{label} does not bind the exact pack version")

    def _validate_reciprocal_graph(self) -> None:
        sections = {item.section_id: item for item in self.sections}
        packs = {item.pack_id: item for item in self.pack_registry.records}
        capabilities = {
            item.capability_id: item for item in self.capability_registry.records
        }
        inputs = {item.input_id: item for item in self.input_register.records}
        outputs = {item.output_id: item for item in self.output_register.records}
        claims = {item.claim_id: item for item in self.claim_register.records}
        evidence = {item.evidence_id: item for item in self.evidence_register.records}
        derivations = {
            item.derivation_id: item for item in self.derivation_register.records
        }
        sources = {item.source_id: item for item in self.source_register.records}

        for claim in claims.values():
            section = sections[claim.section_id]
            if claim.claim_id not in section.claim_ids:
                raise ValueError(
                    f"claim {claim.claim_id} does not bind back from its section"
                )
            for evidence_id in claim.evidence_ids:
                if evidence[evidence_id].claim_id != claim.claim_id:
                    raise ValueError("claim/evidence reciprocal identity mismatch")
            for output_id in claim.output_ids:
                if claim.section_id not in outputs[output_id].section_ids:
                    raise ValueError("claim/output section identity mismatch")
        for item in evidence.values():
            if item.evidence_id not in claims[item.claim_id].evidence_ids:
                raise ValueError("evidence/claim reciprocal identity mismatch")
        for section in sections.values():
            expected_evidence = {
                evidence_id
                for claim_id in section.claim_ids
                for evidence_id in claims[claim_id].evidence_ids
            }
            if set(section.evidence_ids) != expected_evidence:
                raise ValueError(
                    f"section {section.section_id} claim/evidence links are not exact"
                )
            for claim_id in section.claim_ids:
                if claims[claim_id].section_id != section.section_id:
                    raise ValueError("section/claim reciprocal identity mismatch")
            for output_id in section.output_references:
                if section.section_id not in outputs[output_id].section_ids:
                    raise ValueError("section/output reciprocal identity mismatch")
            for input_id in (
                set(section.required_inputs)
                | set(section.resolved_inputs)
                | set(section.derived_inputs)
            ):
                if section.section_id not in inputs[input_id].affected_section_ids:
                    raise ValueError("section/input reciprocal identity mismatch")
            for source_id in section.source_ids:
                if section.section_id not in sources[source_id].section_ids:
                    raise ValueError("section/source reciprocal identity mismatch")
            for pack_id in (
                *section.jurisdiction_pack_ids,
                *section.technology_pack_ids,
            ):
                if section.section_id not in packs[pack_id].section_ids:
                    raise ValueError("section/pack reciprocal identity mismatch")
        for output in outputs.values():
            for section_id in output.section_ids:
                if output.output_id not in sections[section_id].output_references:
                    raise ValueError("output/section reciprocal identity mismatch")
            for derivation_id in output.derivation_ids:
                if output.output_id not in derivations[derivation_id].output_ids:
                    raise ValueError("output/derivation reciprocal identity mismatch")
        for source in sources.values():
            for section_id in source.section_ids:
                if source.source_id not in sections[section_id].source_ids:
                    raise ValueError("source/section reciprocal identity mismatch")
        for input_record in inputs.values():
            for section_id in input_record.affected_section_ids:
                section_input_ids = (
                    set(sections[section_id].required_inputs)
                    | set(sections[section_id].resolved_inputs)
                    | set(sections[section_id].derived_inputs)
                )
                if input_record.input_id not in section_input_ids:
                    raise ValueError("input/section reciprocal identity mismatch")
            if input_record.kind is InputKind.DERIVED:
                for section_id in input_record.affected_section_ids:
                    if input_record.input_id not in sections[section_id].derived_inputs:
                        raise ValueError(
                            "derived input lacks reciprocal section derived_inputs link"
                        )
                for derivation_id in input_record.derivation_ids:
                    if (
                        input_record.input_id
                        not in derivations[derivation_id].derived_input_ids
                    ):
                        raise ValueError(
                            "derived input/derivation reciprocal identity mismatch"
                        )
        for derivation in derivations.values():
            for derived_input_id in derivation.derived_input_ids:
                derived_input = inputs[derived_input_id]
                if (
                    derived_input.kind is not InputKind.DERIVED
                    or derivation.derivation_id not in derived_input.derivation_ids
                ):
                    raise ValueError(
                        "derivation/derived-input reciprocal identity mismatch"
                    )
            for output_id in derivation.output_ids:
                if derivation.derivation_id not in outputs[output_id].derivation_ids:
                    raise ValueError("derivation/output reciprocal identity mismatch")
        for pack in packs.values():
            section_pack_attribute = (
                "jurisdiction_pack_ids"
                if pack.kind is PackKind.JURISDICTION
                else "technology_pack_ids"
            )
            for section_id in pack.section_ids:
                if pack.pack_id not in getattr(
                    sections[section_id], section_pack_attribute
                ):
                    raise ValueError("pack/section reciprocal identity mismatch")
            for capability_id in pack.capability_ids:
                capability = capabilities[capability_id]
                if pack.pack_id not in capability.pack_ids:
                    raise ValueError("pack/capability reciprocal identity mismatch")
                if not set(capability.section_ids) <= set(pack.section_ids):
                    raise ValueError(
                        "pack capability escapes the pack section boundary"
                    )
        for capability in capabilities.values():
            for pack_id in capability.pack_ids:
                if capability.capability_id not in packs[pack_id].capability_ids:
                    raise ValueError("capability/pack reciprocal identity mismatch")
            for section_id in capability.section_ids:
                section = sections[section_id]
                if capability.capability_id not in section.capability_dispositions:
                    raise ValueError("capability/section reciprocal identity mismatch")
                if not set(capability.pack_ids) <= (
                    set(section.jurisdiction_pack_ids)
                    | set(section.technology_pack_ids)
                ):
                    raise ValueError("capability pack is absent from its section")

    def _validate_pack_and_state_bindings(self) -> None:
        cutoff = self.scope.evidence_cutoff
        sections = {item.section_id: item for item in self.sections}
        packs = {item.pack_id: item for item in self.pack_registry.records}
        capabilities = {
            item.capability_id: item for item in self.capability_registry.records
        }
        inputs = {item.input_id: item for item in self.input_register.records}
        outputs = {item.output_id: item for item in self.output_register.records}
        claims = {item.claim_id: item for item in self.claim_register.records}
        evidence = {item.evidence_id: item for item in self.evidence_register.records}
        sources = {item.source_id: item for item in self.source_register.records}
        validations = {
            item.validation_id: item for item in self.validation_register.records
        }
        reviews = {item.review_id: item for item in self.review_register.records}
        limitations = {
            item.limitation_id: item for item in self.limitation_register.records
        }

        scope_jurisdictions = set(self.scope.jurisdictions)
        scope_technologies = set(self.scope.technology_ids)
        active_pack_ids = set(self.scope.jurisdiction_pack_ids) | set(
            self.scope.technology_pack_ids
        )
        current_source_ids = {
            source_id
            for pack_id in active_pack_ids
            for source_id in packs[pack_id].source_ids
        } | {item.source_id for item in evidence.values() if item.source_id is not None}
        for source in sources.values():
            if source.project_boundary != self.scope.project_boundary:
                raise ValueError(
                    f"source {source.source_id} has foreign project boundary"
                )
            if not set(source.jurisdictions) <= scope_jurisdictions:
                raise ValueError(
                    f"source {source.source_id} has wrong jurisdiction scope"
                )
            if not set(source.technology_ids) <= scope_technologies:
                raise ValueError(
                    f"source {source.source_id} has wrong technology scope"
                )
            dated_events = {
                "publication": source.publication_date,
                "observation": source.observation_date,
                "retrieval": source.retrieval_date,
            }
            future = sorted(
                name
                for name, value in dated_events.items()
                if value is not None and value > cutoff
            )
            if future:
                raise ValueError(
                    f"source {source.source_id} is after evidence cutoff: {future}"
                )
            if source.expiry_date is not None and source.expiry_date < cutoff:
                raise ValueError(
                    f"source {source.source_id} expired before evidence cutoff"
                )
            if (
                source.source_id in current_source_ids
                and source.effective_date is not None
                and source.effective_date > cutoff
            ):
                raise ValueError(
                    f"source {source.source_id} is not effective at evidence cutoff"
                )
        for claim in claims.values():
            if (
                claim.project_boundary != self.scope.project_boundary
                or not claim.jurisdictions
                or not claim.technology_ids
                or not set(claim.jurisdictions) <= scope_jurisdictions
                or not set(claim.technology_ids) <= scope_technologies
            ):
                raise ValueError(
                    f"claim {claim.claim_id} has inconsistent project scope"
                )
        for item in evidence.values():
            claim = claims[item.claim_id]
            if (
                item.project_boundary != claim.project_boundary
                or set(item.jurisdictions) != set(claim.jurisdictions)
                or set(item.technology_ids) != set(claim.technology_ids)
            ):
                raise ValueError(
                    "claim/evidence jurisdiction, technology or project scope mismatch"
                )
            if item.expiry_date is not None and item.expiry_date < cutoff:
                raise ValueError(f"evidence {item.evidence_id} expired before cutoff")
            if item.sufficiency is EvidenceStatus.SUFFICIENT_FOR_ACHIEVED_GRADE:
                raise ValueError(
                    "D2 v1 cannot assert sufficient_for_achieved_grade while section grades are sentinel-only"
                )
            if item.source_id is not None:
                source = sources[item.source_id]
                if (
                    not set(item.jurisdictions) <= set(source.jurisdictions)
                    or not set(item.technology_ids) <= set(source.technology_ids)
                    or item.project_boundary != source.project_boundary
                    or claim.section_id not in source.section_ids
                    or item.period != source.period
                ):
                    raise ValueError(
                        "evidence source does not cover its exact claim scope and period"
                    )
                if (
                    _AUTHENTICITY_RANK[item.authenticity_status]
                    > _AUTHENTICITY_RANK[source.authenticity_status]
                ):
                    raise ValueError(
                        "evidence authenticity cannot exceed source authenticity"
                    )
                if (
                    source.source_class is SourceClass.SYNTHETIC
                    and item.sufficiency is not EvidenceStatus.SYNTHETIC_ONLY
                ):
                    raise ValueError(
                        "synthetic source must remain synthetic_only evidence"
                    )
            if item.independence_status is IndependenceStatus.INDEPENDENT:
                exact_reviews = []
                for review_id in item.review_ids:
                    review = reviews[review_id]
                    binding = review.subject_binding
                    if (
                        review.independence_status is IndependenceStatus.INDEPENDENT
                        and review.completed_at is not None
                        and isinstance(binding, ReportSubjectBinding)
                        and claim.section_id in binding.section_ids
                        and claim.claim_id in binding.claim_ids
                        and item.evidence_id in binding.evidence_ids
                    ):
                        exact_reviews.append(review)
                if not exact_reviews:
                    raise ValueError(
                        "independent evidence requires a completed current exact-evidence review"
                    )

        jurisdiction_packs = tuple(
            packs[pack_id] for pack_id in self.scope.jurisdiction_pack_ids
        )
        technology_packs = tuple(
            packs[pack_id] for pack_id in self.scope.technology_pack_ids
        )
        if any(pack.kind is not PackKind.JURISDICTION for pack in jurisdiction_packs):
            raise ValueError(
                "scope jurisdiction_pack_ids contains a non-jurisdiction pack"
            )
        if any(pack.kind is not PackKind.TECHNOLOGY for pack in technology_packs):
            raise ValueError("scope technology_pack_ids contains a non-technology pack")
        jurisdiction_bindings = self.jurisdiction_subject_bindings
        jurisdiction_subject_keys = tuple(
            (
                jurisdiction_binding.jurisdiction,
                jurisdiction_binding.subject_kind,
                jurisdiction_binding.subject_id,
            )
            for jurisdiction_binding in jurisdiction_bindings
        )
        if len(jurisdiction_subject_keys) != len(set(jurisdiction_subject_keys)):
            raise ValueError(
                "jurisdiction subject bindings contain duplicate governed-subject mappings"
            )
        if set(
            jurisdiction_binding.jurisdiction
            for jurisdiction_binding in jurisdiction_bindings
        ) != set(self.scope.jurisdictions):
            raise ValueError(
                "jurisdiction subject bindings must cover every scoped jurisdiction"
            )
        used_disposition_packs: set[str] = set()
        for jurisdiction_binding in jurisdiction_bindings:
            pack = packs[jurisdiction_binding.disposition_pack_id]
            if (
                jurisdiction_binding.disposition_pack_id
                not in self.scope.jurisdiction_pack_ids
                or pack.kind is not PackKind.JURISDICTION
                or pack.jurisdiction_codes != (jurisdiction_binding.jurisdiction,)
                or not set(jurisdiction_binding.contribution_section_ids)
                <= set(pack.section_ids)
            ):
                raise ValueError(
                    "jurisdiction subject binding lacks an exact contributing disposition pack"
                )
            if (
                jurisdiction_binding.subject_kind is GovernedSubjectKind.PROJECT
                and jurisdiction_binding.subject_id != self.identity.project_id
            ):
                raise ValueError(
                    "project jurisdiction binding must name ReportIdentity.project_id"
                )
            for section_id in jurisdiction_binding.contribution_section_ids:
                if (
                    jurisdiction_binding.disposition_pack_id
                    not in sections[section_id].jurisdiction_pack_ids
                ):
                    raise ValueError(
                        "jurisdiction disposition pack does not contribute to its named section"
                    )
            if pack.status is PackStatus.UNSUPPORTED:
                if set(jurisdiction_binding.contribution_section_ids) != set(
                    pack.section_ids
                ):
                    raise ValueError(
                        "unsupported jurisdiction disposition must cover the exact pack sections"
                    )
                for section_id in jurisdiction_binding.contribution_section_ids:
                    section = sections[section_id]
                    matching: list[UnsupportedJurisdictionCapability] = []
                    for capability_id in section.capability_dispositions:
                        capability = capabilities[capability_id]
                        if (
                            isinstance(capability, UnsupportedJurisdictionCapability)
                            and capability.pack_id == pack.pack_id
                            and capability.jurisdiction
                            == jurisdiction_binding.jurisdiction
                            and section_id in capability.section_ids
                        ):
                            matching.append(capability)
                    if (
                        section.applicability is not Applicability.APPLICABLE
                        or section.production_status
                        is not ProductionStatus.NOT_RUN_UNSUPPORTED_JURISDICTION
                        or len(matching) != 1
                    ):
                        raise ValueError(
                            "unsupported jurisdiction contribution requires each affected "
                            "section to carry one exact unsupported-jurisdiction capability"
                        )
            used_disposition_packs.add(jurisdiction_binding.disposition_pack_id)
        if used_disposition_packs != set(self.scope.jurisdiction_pack_ids):
            raise ValueError(
                "every scoped jurisdiction pack must disposition a governed subject"
            )
        technology_pack_counts = {
            technology_id: sum(
                pack.technology_ids == (technology_id,) for pack in technology_packs
            )
            for technology_id in self.scope.technology_ids
        }
        if any(count != 1 for count in technology_pack_counts.values()) or any(
            pack.technology_ids[0] not in self.scope.technology_ids
            for pack in technology_packs
        ):
            raise ValueError(
                "each scoped technology type requires exactly one truthful technology pack"
            )
        covered_jurisdictions = {
            code for pack in jurisdiction_packs for code in pack.jurisdiction_codes
        }
        covered_technologies = {
            technology
            for pack in technology_packs
            for technology in pack.technology_ids
        }
        missing_jurisdictions = sorted(scope_jurisdictions - covered_jurisdictions)
        missing_technologies = sorted(scope_technologies - covered_technologies)
        if missing_jurisdictions:
            raise ValueError(
                "scope has no explicit matching jurisdiction pack for "
                f"{missing_jurisdictions}; jurisdiction defaults are forbidden"
            )
        if missing_technologies:
            raise ValueError(
                "scope has no explicit matching technology pack for "
                f"{missing_technologies}; untyped technologies are forbidden"
            )
        for pack in packs.values():
            if self.scope.project_stage not in pack.project_stages:
                raise ValueError(
                    f"pack {pack.pack_id} does not support the project stage"
                )
            if pack.effective_date > cutoff or pack.review_date > cutoff:
                raise ValueError(
                    f"pack {pack.pack_id} is not current at evidence cutoff"
                )
            if pack.status is not PackStatus.UNSUPPORTED:
                structural_sources = [
                    sources[source_id]
                    for source_id in pack.source_ids
                    if sources[source_id].source_class in _STRUCTURAL_SOURCE_CLASSES
                ]
                if not structural_sources:
                    raise ValueError(
                        f"supported pack {pack.pack_id} lacks a structural source"
                    )
                if not pack.validation_ids or any(
                    validations[item].status is not ValidationStatus.PASSED
                    for item in pack.validation_ids
                ):
                    raise ValueError(
                        f"supported pack {pack.pack_id} lacks passed validation"
                    )
                if not pack.limitation_ids:
                    raise ValueError(f"supported pack {pack.pack_id} lacks limitations")
                for limitation_id in pack.limitation_ids:
                    if not set(limitations[limitation_id].affected_section_ids) <= set(
                        pack.section_ids
                    ):
                        raise ValueError(
                            "pack limitation escapes the pack section boundary"
                        )
                for source_id in pack.source_ids:
                    source = sources[source_id]
                    if pack.kind is PackKind.JURISDICTION and (
                        not source.jurisdictions
                        or not set(source.jurisdictions) <= set(pack.jurisdiction_codes)
                    ):
                        raise ValueError(
                            "jurisdiction pack source has wrong jurisdiction"
                        )
                    if pack.kind is PackKind.TECHNOLOGY and (
                        not source.technology_ids
                        or not set(source.technology_ids) <= set(pack.technology_ids)
                    ):
                        raise ValueError("technology pack source has wrong technology")
                for default in pack.input_defaults:
                    for source_id in default.source_ids:
                        source = sources[source_id]
                        if pack.kind is PackKind.JURISDICTION and (
                            not source.jurisdictions
                            or not set(source.jurisdictions)
                            <= set(pack.jurisdiction_codes)
                        ):
                            raise ValueError(
                                "pack default source has wrong jurisdiction"
                            )
                        if pack.kind is PackKind.TECHNOLOGY and (
                            not source.technology_ids
                            or not set(source.technology_ids)
                            <= set(pack.technology_ids)
                        ):
                            raise ValueError("pack default source has wrong technology")

        outcome_by_status = {
            ProductionStatus.NOT_RUN_MISSING_INPUT: CapabilityOutcome.NOT_RUN_MISSING_INPUT,
            ProductionStatus.NOT_RUN_MISSING_DEPENDENCY: CapabilityOutcome.NOT_RUN_MISSING_DEPENDENCY,
            ProductionStatus.NOT_RUN_UNSUPPORTED_JURISDICTION: CapabilityOutcome.NOT_RUN_UNSUPPORTED_JURISDICTION,
            ProductionStatus.NOT_RUN_UNSUPPORTED_TECHNOLOGY: CapabilityOutcome.NOT_RUN_UNSUPPORTED_TECHNOLOGY,
            ProductionStatus.FAILED: CapabilityOutcome.FAILED,
            ProductionStatus.DEGRADED: CapabilityOutcome.DEGRADED,
            ProductionStatus.INTENTIONALLY_DEFERRED: CapabilityOutcome.INTENTIONALLY_DEFERRED,
            ProductionStatus.NOT_REQUIRED_BY_SCOPE: CapabilityOutcome.NOT_APPLICABLE,
        }
        for section in sections.values():
            dispositions = tuple(
                capabilities[item] for item in section.capability_dispositions
            )
            if section.production_status is ProductionStatus.COMPLETE and (
                not dispositions
                or any(
                    item.outcome is not CapabilityOutcome.EXECUTED
                    for item in dispositions
                )
            ):
                raise ValueError(
                    f"complete section {section.section_id} requires executed capabilities"
                )
            if section.production_status is ProductionStatus.COMPLETE and any(
                limitations[item].materiality is Materiality.MATERIAL
                for item in section.limitation_ids
            ):
                raise ValueError(
                    f"complete section {section.section_id} has a material limitation"
                )
            required_outcome = outcome_by_status.get(section.production_status)
            if required_outcome is not None and not any(
                item.outcome is required_outcome for item in dispositions
            ):
                raise ValueError(
                    f"section {section.section_id} requires capability outcome {required_outcome.value}"
                )
            for input_id in section.resolved_inputs:
                if (
                    inputs[input_id].resolution_status
                    is not InputResolutionStatus.RESOLVED
                ):
                    raise ValueError(
                        f"section {section.section_id} labels unresolved input as resolved"
                    )
            if section.evidence_status is not EvidenceStatus.NOT_REQUIRED and not any(
                evidence[item].sufficiency is section.evidence_status
                for item in section.evidence_ids
            ):
                raise ValueError(
                    f"section {section.section_id} lacks matching evidence state"
                )
            if section.applicability is Applicability.NOT_APPLICABLE:
                na_capabilities = [
                    item
                    for item in dispositions
                    if item.outcome is CapabilityOutcome.NOT_APPLICABLE
                ]
                if not na_capabilities:
                    raise ValueError("not-applicable section lacks N/A capability")
                for na_capability in na_capabilities:
                    if na_capability.decision_id not in section.decision_ids:
                        raise ValueError(
                            "N/A section and capability must share scope decision"
                        )
        for candidate in capabilities.values():
            if candidate.outcome is CapabilityOutcome.NOT_RUN_UNSUPPORTED_JURISDICTION:
                pack = packs[candidate.pack_id]
                if (
                    pack.kind is not PackKind.JURISDICTION
                    or pack.status is not PackStatus.UNSUPPORTED
                    or candidate.jurisdiction not in pack.jurisdiction_codes
                    or candidate.jurisdiction not in self.scope.jurisdictions
                ):
                    raise ValueError(
                        "invalid unsupported-jurisdiction capability/pack binding"
                    )
            if candidate.outcome is CapabilityOutcome.NOT_RUN_UNSUPPORTED_TECHNOLOGY:
                pack = packs[candidate.pack_id]
                if (
                    pack.kind is not PackKind.TECHNOLOGY
                    or pack.status is not PackStatus.UNSUPPORTED
                    or candidate.technology_id not in pack.technology_ids
                    or candidate.technology_id not in self.scope.technology_ids
                ):
                    raise ValueError(
                        "invalid unsupported-technology capability/pack binding"
                    )
        for reconciliation in self.reconciliation_register.records:
            if reconciliation.status in {
                ReconciliationStatus.PASSED,
                ReconciliationStatus.FAILED,
            }:
                for output_id in reconciliation.output_ids:
                    if not set(outputs[output_id].section_ids) & set(
                        reconciliation.section_ids
                    ):
                        raise ValueError(
                            "passed/failed reconciliation output is unrelated to its sections"
                        )

    def _validate_authority_actor(self, actor_id: str, label: str) -> None:
        actors = {item.actor_id: item for item in self.actor_register.records}
        actor = actors[actor_id]
        if (
            actor.kind not in {ActorKind.HUMAN, ActorKind.INSTITUTION}
            or actor.organization is None
            or not actor.identity_verified
            or actor.authority_basis is None
        ):
            raise ValueError(
                f"{label} requires a verified human/institution signatory with "
                "organization and authority basis"
            )

    def _validate_authority_and_review(self) -> None:
        cutoff = self.scope.evidence_cutoff
        actors = {item.actor_id: item for item in self.actor_register.records}
        decisions = {item.decision_id: item for item in self.decision_register.records}
        reviews = {item.review_id: item for item in self.review_register.records}
        findings = {
            item.finding_id: item for item in self.review_finding_register.records
        }
        packs = {item.pack_id: item for item in self.pack_registry.records}
        claims = {item.claim_id: item for item in self.claim_register.records}
        evidence = {item.evidence_id: item for item in self.evidence_register.records}
        artifacts = {item.artifact_id: item for item in self.artifact_manifest.records}

        for decision_record in decisions.values():
            decision_binding = decision_record.subject_binding
            if isinstance(decision_binding, ReportSubjectBinding) and not set(
                decision_record.evidence_ids
            ) <= set(decision_binding.evidence_ids):
                raise ValueError(
                    "decision evidence must be included in its exact subject binding"
                )
            if decision_record.decided_at > self.captured_at:
                raise ValueError("decision postdates package captured_at")
            if isinstance(decision_binding, ReportSubjectBinding):
                if decision_record.decided_at < self.identity.created_at:
                    raise ValueError(
                        "report-bound decision predates ReportIdentity.created_at"
                    )
                if decision_binding.artifact_ids and any(
                    decision_record.decided_at < artifacts[item].created_at
                    for item in decision_binding.artifact_ids
                ):
                    raise ValueError("artifact-bound decision predates its artifact")

        for assignment in self.responsibility_register.records:
            if assignment.status is not ResponsibilityStatus.PERFORMED:
                continue
            assert (
                assignment.actor_id is not None and assignment.decision_id is not None
            )
            actor = actors[assignment.actor_id]
            decision = decisions[assignment.decision_id]
            if (
                actor.kind is not ActorKind.HUMAN
                or actor.organization is None
                or not actor.identity_verified
            ):
                raise ValueError(
                    "performed responsibility requires a verified organized human"
                )
            self._validate_authority_actor(
                assignment.actor_id, "performed responsibility"
            )
            if decision.outcome not in _POSITIVE_OUTCOMES:
                raise ValueError(
                    "only a positive decision can support performed responsibility"
                )
            if decision.subject_binding != assignment.subject_binding:
                raise ValueError(
                    "responsibility decision must bind the exact assignment subject"
                )
            if decision.authority_actor_id != assignment.actor_id:
                raise ValueError(
                    "performed responsibility actor must be the exact decision authority"
                )
            assert assignment.performed_at is not None
            if not (
                self.identity.created_at
                <= assignment.performed_at
                <= decision.decided_at
                <= self.captured_at
            ):
                raise ValueError(
                    "performed responsibility chronology requires report creation <= "
                    "performance <= supporting decision <= package capture"
                )

        for review in reviews.values():
            if review.completed_at is None:
                continue
            assert review.signed_decision_id is not None
            decision = decisions[review.signed_decision_id]
            if (
                decision.kind is not DecisionKind.REVIEW
                or decision.outcome not in _POSITIVE_OUTCOMES
            ):
                raise ValueError(
                    "completed review requires a positive typed review decision"
                )
            if decision.subject_binding != review.subject_binding:
                raise ValueError("review decision must bind the exact review subject")
            if review.completed_at > self.captured_at:
                raise ValueError("completed review postdates package captured_at")
            if isinstance(review.subject_binding, ReportSubjectBinding):
                if review.completed_at < self.identity.created_at:
                    raise ValueError(
                        "report-bound review predates ReportIdentity.created_at"
                    )
                if review.subject_binding.artifact_ids and any(
                    review.completed_at < artifacts[item].created_at
                    for item in review.subject_binding.artifact_ids
                ):
                    raise ValueError("artifact-bound review predates its artifact")
            if decision.decided_at < review.completed_at:
                raise ValueError("review decision cannot predate review completion")
            self._validate_authority_actor(
                decision.authority_actor_id, "review sign-off"
            )
            if review.independence_status is IndependenceStatus.INDEPENDENT:
                self._validate_authority_actor(
                    review.reviewer_actor_id, "independent review"
                )
                if decision.authority_actor_id != review.reviewer_actor_id:
                    raise ValueError(
                        "independent review must be signed by its exact reviewer"
                    )

        for section in self.sections:
            for review_id in section.review_ids:
                binding = self._validate_report_subject(
                    reviews[review_id].subject_binding, "section review"
                )
                if section.section_id not in binding.section_ids:
                    raise ValueError(
                        "section review lacks exact section subject binding"
                    )
            if section.review_status is ReviewStatus.SELF_CHECKED and not any(
                reviews[item].independence_status is IndependenceStatus.INTERNAL
                and reviews[item].completed_at is not None
                for item in section.review_ids
            ):
                raise ValueError("self-checked section lacks completed internal review")
            if (
                section.review_status is ReviewStatus.INDEPENDENT_REVIEW_PENDING
                and not any(
                    reviews[item].independence_status is IndependenceStatus.INDEPENDENT
                    and reviews[item].completed_at is None
                    for item in section.review_ids
                )
            ):
                raise ValueError("section lacks pending independent review")
            if (
                section.review_status
                is ReviewStatus.INDEPENDENT_REVIEW_COMPLETED_WITH_FINDINGS
                and not any(
                    reviews[item].independence_status is IndependenceStatus.INDEPENDENT
                    and reviews[item].completed_at is not None
                    and reviews[item].finding_ids
                    for item in section.review_ids
                )
            ):
                raise ValueError("section lacks completed independent review findings")
            has_accepted_review = any(
                reviews[item].independence_status is IndependenceStatus.INDEPENDENT
                and reviews[item].completed_at is not None
                and not any(
                    findings[finding].status is FindingStatus.OPEN_BLOCKING
                    for finding in reviews[item].finding_ids
                )
                for item in section.review_ids
            )
            if (
                section.review_status is ReviewStatus.INDEPENDENTLY_ACCEPTED
                and not has_accepted_review
            ):
                raise ValueError(
                    "independently accepted section lacks exact accepted review"
                )
            if section.applicability is Applicability.NOT_APPLICABLE:
                for capability_id in section.capability_dispositions:
                    capability = next(
                        item
                        for item in self.capability_registry.records
                        if item.capability_id == capability_id
                    )
                    if capability.outcome is not CapabilityOutcome.NOT_APPLICABLE:
                        continue
                    decision = decisions[capability.decision_id]
                    binding = self._validate_report_subject(
                        decision.subject_binding, "N/A scope decision"
                    )
                    if (
                        decision.kind is not DecisionKind.SCOPE
                        or decision.outcome is not DecisionOutcome.APPROVED
                        or section.section_id not in binding.section_ids
                    ):
                        raise ValueError(
                            "N/A capability requires exact positive scope decision"
                        )
                    self._validate_authority_actor(
                        decision.authority_actor_id, "N/A scope decision"
                    )
            if section.release_status is SectionReleaseStatus.AUTHORIZED:
                release_decisions = [
                    decisions[item]
                    for item in section.decision_ids
                    if decisions[item].kind is DecisionKind.RELEASE
                ]
                if not release_decisions:
                    raise ValueError("authorized section lacks release decision")
                for decision in release_decisions:
                    binding = self._validate_report_subject(
                        decision.subject_binding, "section release"
                    )
                    if (
                        decision.outcome is not DecisionOutcome.AUTHORIZED
                        or section.section_id not in binding.section_ids
                        or not decision.evidence_ids
                        or any(
                            evidence[item].source_id is None
                            or evidence[item].sufficiency
                            in {
                                EvidenceStatus.MISSING,
                                EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
                                EvidenceStatus.NOT_REQUIRED,
                            }
                            for item in decision.evidence_ids
                        )
                    ):
                        raise ValueError(
                            "section release requires exact positive evidence-backed authority"
                        )
                    self._validate_authority_actor(
                        decision.authority_actor_id, "section release"
                    )

        for pack in packs.values():
            if pack.status is not PackStatus.ASSURED:
                continue
            assert pack.grade_ceiling is not None
            self._validate_authority_actor(pack.owner_actor_id, "assured pack owner")
            owner_actor = actors[pack.owner_actor_id]
            qualifying_reviews: list[ReviewRecord] = []
            for review_id in pack.review_ids:
                review = reviews[review_id]
                review_binding = review.subject_binding
                review_actor = actors[review.reviewer_actor_id]
                review_decision = (
                    decisions[review.signed_decision_id]
                    if review.signed_decision_id is not None
                    else None
                )
                if (
                    review.independence_status is IndependenceStatus.INDEPENDENT
                    and review.completed_at is not None
                    and isinstance(review_binding, PackVersionSubjectBinding)
                    and review_binding.pack_id == pack.pack_id
                    and review_binding.pack_version == pack.version
                    and review_binding.effective_from
                    <= cutoff
                    <= review_binding.effective_until
                    and review_binding.grade.value == pack.grade_ceiling.value
                    and not any(
                        findings[item].status is FindingStatus.OPEN_BLOCKING
                        for item in review.finding_ids
                    )
                    and review.reviewer_actor_id != pack.owner_actor_id
                    and review_actor.kind is ActorKind.HUMAN
                    and review_actor.organization is not None
                    and owner_actor.organization is not None
                    and review_actor.organization != owner_actor.organization
                    and review_decision is not None
                    and bool(review_decision.evidence_ids)
                    and all(
                        claims[evidence[item].claim_id].section_id in pack.section_ids
                        and evidence[item].source_id in pack.source_ids
                        and evidence[item].sufficiency
                        not in {
                            EvidenceStatus.MISSING,
                            EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
                            EvidenceStatus.NOT_REQUIRED,
                        }
                        for item in review_decision.evidence_ids
                    )
                ):
                    qualifying_reviews.append(review)
            if not qualifying_reviews:
                raise ValueError(
                    f"assured pack {pack.pack_id} lacks exact current independent review"
                )
            qualifying_ids = {item.review_id for item in qualifying_reviews}
            qualifying_decisions: list[DecisionRecord] = []
            for decision_id in pack.decision_ids:
                decision = decisions[decision_id]
                decision_binding = decision.subject_binding
                if (
                    decision.kind is DecisionKind.PACK_ASSURANCE
                    and decision.outcome is DecisionOutcome.AUTHORIZED
                    and decision.evidence_ids
                    and isinstance(decision_binding, PackVersionSubjectBinding)
                    and decision_binding.pack_id == pack.pack_id
                    and decision_binding.pack_version == pack.version
                    and decision_binding.grade.value == pack.grade_ceiling.value
                    and decision.grade is decision_binding.grade
                    and decision_binding.effective_from
                    <= cutoff
                    <= decision_binding.effective_until
                    and qualifying_ids == set(decision_binding.review_ids)
                ):
                    qualifying_decisions.append(decision)
            if not qualifying_decisions:
                raise ValueError(
                    f"assured pack {pack.pack_id} lacks exact positive assurance decision"
                )
            for decision in qualifying_decisions:
                for review in qualifying_reviews:
                    assert review.completed_at is not None
                    assert review.signed_decision_id is not None
                    signed_review_decision = decisions[review.signed_decision_id]
                    if (
                        decision.decided_at < review.completed_at
                        or decision.decided_at < signed_review_decision.decided_at
                    ):
                        raise ValueError(
                            "pack-assurance decision cannot predate a qualifying review "
                            "or its signed review decision"
                        )
                self._validate_authority_actor(
                    decision.authority_actor_id, "pack assurance"
                )
                assurance_actor = actors[decision.authority_actor_id]
                if (
                    assurance_actor.actor_id == pack.owner_actor_id
                    or assurance_actor.organization is None
                    or owner_actor.organization is None
                    or assurance_actor.organization == owner_actor.organization
                ):
                    raise ValueError(
                        "pack assurance authority must be independent of the pack owner"
                    )
                if any(
                    claims[evidence[item].claim_id].section_id not in pack.section_ids
                    or evidence[item].source_id is None
                    or evidence[item].source_id not in pack.source_ids
                    or evidence[item].sufficiency
                    in {
                        EvidenceStatus.MISSING,
                        EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
                        EvidenceStatus.NOT_REQUIRED,
                    }
                    for item in decision.evidence_ids
                ):
                    raise ValueError(
                        "pack-assurance decision evidence is not relevant usable pack evidence"
                    )

        release = self.package_release
        if release.status is PackageReleaseStatus.AUTHORIZED:
            assert release.authority_actor_id is not None
            assert release.decision_id is not None
            decision = decisions[release.decision_id]
            binding = self._validate_report_subject(
                decision.subject_binding, "package release"
            )
            if (
                decision.kind is not DecisionKind.RELEASE
                or decision.outcome is not DecisionOutcome.AUTHORIZED
                or not decision.evidence_ids
                or set(binding.artifact_ids) != set(release.artifact_ids)
                or decision.authority_actor_id != release.authority_actor_id
                or decision.decided_at != release.decided_at
                or any(
                    evidence[item].source_id is None
                    or evidence[item].sufficiency
                    in {
                        EvidenceStatus.MISSING,
                        EvidenceStatus.EXTERNAL_EVIDENCE_HOLD,
                        EvidenceStatus.NOT_REQUIRED,
                    }
                    for item in decision.evidence_ids
                )
            ):
                raise ValueError(
                    "package release requires exact positive evidence-backed authority"
                )
            self._validate_authority_actor(
                release.authority_actor_id, "package release"
            )
            assert release.decided_at is not None
            if release.decided_at > self.captured_at:
                raise ValueError("package release postdates package captured_at")
            controls = {
                item.distribution_id: item
                for item in self.distribution_register.records
            }
            release_artifact_ids = set(release.artifact_ids)
            exact_control_ids = {
                control.distribution_id
                for control in controls.values()
                if set(control.artifact_ids) & release_artifact_ids
            }
            if set(release.distribution_ids) != exact_control_ids:
                raise ValueError(
                    "package release must bind every exact distribution control for its artifacts"
                )
            selected_controls = [
                controls[distribution_id]
                for distribution_id in release.distribution_ids
            ]
            if {
                artifact_id
                for control in selected_controls
                for artifact_id in control.artifact_ids
            } != release_artifact_ids:
                raise ValueError(
                    "release distribution controls must exactly cover released artifacts"
                )
            if any(
                control.expiry_or_review_date < self.captured_at.date()
                for control in selected_controls
            ):
                raise ValueError(
                    "release distribution control is expired at package captured_at"
                )

    def _validate_distribution(self) -> None:
        artifacts = {item.artifact_id: item for item in self.artifact_manifest.records}
        sources = {item.source_id: item for item in self.source_register.records}
        validations = {
            item.validation_id: item for item in self.validation_register.records
        }
        controlled_artifacts = {
            artifact_id
            for control in self.distribution_register.records
            for artifact_id in control.artifact_ids
        }
        if set(artifacts) - controlled_artifacts:
            raise ValueError("every artifact requires a distribution control")
        for artifact in artifacts.values():
            if artifact.is_full_package and set(artifact.source_ids) != set(sources):
                raise ValueError(
                    "full-package artifact must enumerate the complete source registry"
                )
        for control in self.distribution_register.records:
            bindings = {
                (item.artifact_id, item.source_id): item
                for item in control.disclosure_bindings
            }
            if len(bindings) != len(control.disclosure_bindings):
                raise ValueError("distribution has duplicate disclosure bindings")
            for binding in control.disclosure_bindings:
                if binding.artifact_id not in control.artifact_ids:
                    raise ValueError(
                        "disclosure binding artifact is outside its distribution control"
                    )
                if binding.source_id not in artifacts[binding.artifact_id].source_ids:
                    raise ValueError(
                        "disclosure binding source is absent from its artifact"
                    )
            if control.distribution_class is not ConfidentialityClass.PUBLIC:
                continue
            for artifact_id in control.artifact_ids:
                artifact = artifacts[artifact_id]
                if artifact.confidentiality is not ConfidentialityClass.PUBLIC:
                    raise ValueError(
                        "public distribution requires a public-classified artifact"
                    )
                for source_id in artifact.source_ids:
                    source = sources[source_id]
                    restricted = (
                        not source.publication_permitted
                        or source.confidentiality is not ConfidentialityClass.PUBLIC
                    )
                    if not restricted:
                        continue
                    disclosure_binding = bindings.get((artifact_id, source_id))
                    if (
                        disclosure_binding is None
                        or disclosure_binding.action is DisclosureAction.INCLUDE
                    ):
                        raise ValueError(
                            "public artifact with restricted/no-publication source "
                            "requires structured redaction, omission or reference-only binding"
                        )
                    assert disclosure_binding.validation_id is not None
                    if (
                        validations[disclosure_binding.validation_id].status
                        is not ValidationStatus.PASSED
                    ):
                        raise ValueError(
                            "public disclosure transformation lacks passed validation"
                        )


__all__ = ["FeasibilityReportPackage"]
