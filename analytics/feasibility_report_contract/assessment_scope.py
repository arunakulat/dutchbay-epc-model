"""Pure assessment-scope and v14 scenario-binding request contracts.

The models in this module are the Dolphin 3B-0 input boundary.  They bind one
exact :class:`~analytics.feasibility_report_contract.project_case.ProjectCase`
identity to an explicit assessment intent and to a declared, hash-bound authored
v14 scenario.  They do not load a scenario, map values, run the engine, assemble a
report package, infer an achieved grade, or grant review/release authority.

The later D3B executor may use this policy only as a closed compatibility plan.
ProjectCase technical and commercial values are assertions against the authored
scenario, not a generic merge surface.  The only contemplated v1 override is the
scope-owned canonical ``run.mode`` token, under the exact policy declared below.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Annotated, Any, Literal, Union, cast

from pydantic import (
    Field,
    GetJsonSchemaHandler,
    PositiveInt,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from analytics.run_modes import RunMode

from .project_case import (
    ElectricalBasis,
    GenerationCapacityBasis,
    JurisdictionSubject,
    PriceNominality,
    StorageCapacityBasis,
    StorageElectricalBasis,
    TechnologyAssetClass,
)
from .vocabulary import (
    AssessmentGrade,
    Sha256Hex,
    StrictFrozenModel,
)

ASSESSMENT_SCOPE_SCHEMA_ID: Literal["dutchbay.assessment_scope.v1"] = (
    "dutchbay.assessment_scope.v1"
)
ASSESSMENT_SCOPE_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
EVALUATION_REQUEST_SCHEMA_ID: Literal["dutchbay.evaluation_request.v1"] = (
    "dutchbay.evaluation_request.v1"
)
EVALUATION_REQUEST_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
BASE_SCENARIO_IDENTITY_SCHEMA_ID: Literal["dutchbay.base_scenario_identity.v1"] = (
    "dutchbay.base_scenario_identity.v1"
)
BASE_SCENARIO_IDENTITY_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
AUTHORED_SCENARIO_VALIDATION_SCHEMA_ID: Literal[
    "dutchbay.authored_scenario_validation_receipt.v1"
] = "dutchbay.authored_scenario_validation_receipt.v1"
AUTHORED_SCENARIO_VALIDATION_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"
V14_BINDING_POLICY_SCHEMA_ID: Literal["dutchbay.v14_binding_policy.v1"] = (
    "dutchbay.v14_binding_policy.v1"
)
V14_BINDING_POLICY_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"

_MAX_ASSESSMENT_TEXT_LENGTH = 4096
_ASSESSMENT_BLANK_CODEPOINT_CLASS = (
    r"\u0000-\u0020\u007f-\u00a0\u1680\u2000-\u200a"
    r"\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_ASSESSMENT_TEXT_PATTERN = (
    rf"^(?=[\s\S]*[^{_ASSESSMENT_BLANK_CODEPOINT_CLASS}])[\s\S]*(?![\s\S])"
)
_ASSESSMENT_JURISDICTION_CODE_PATTERN = r"^[A-Z0-9][A-Z0-9_-]{1,31}(?![\s\S])"
_ASSESSMENT_CURRENCY_CODE_PATTERN = r"^[A-Z]{3}(?![\s\S])"
_BINDING_UNIT_TOKEN_PATTERN = r"^[A-Za-z0-9%][A-Za-z0-9%._/*^()\-]{0,63}(?![\s\S])"
_STABLE_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*(?![\s\S])"
_SEMVER_NUMERIC_IDENTIFIER = r"(?:0|[1-9][0-9]*)"
_SEMVER_PRERELEASE_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
_PROJECT_CASE_SEMVER_PATTERN = (
    rf"^{_SEMVER_NUMERIC_IDENTIFIER}\."
    rf"{_SEMVER_NUMERIC_IDENTIFIER}\."
    rf"{_SEMVER_NUMERIC_IDENTIFIER}"
    rf"(?:-{_SEMVER_PRERELEASE_IDENTIFIER}"
    rf"(?:\.{_SEMVER_PRERELEASE_IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?![\s\S])"
)
_MAX_RESOLVED_CONFIG_CONTAINERS = 10_000
_MAX_RESOLVED_CONFIG_SCALARS = 100_000
_MAX_RESOLVED_CONFIG_DEPTH = 128
_MAX_RESOLVED_CONFIG_TEXT_CODEPOINTS = 1_000_000
_MAX_RESOLVED_CONFIG_INTEGER_BITS = 4096


@dataclass(frozen=True, slots=True)
class _ExactStringJsonSchema:
    """Immutable schema metadata that returns a fresh exact-string schema."""

    min_length: int
    max_length: int | None
    pattern: str

    def __get_pydantic_json_schema__(
        self,
        _core_schema: CoreSchema,
        _handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        """Return fresh schema data so no process-global object can be mutated."""
        schema: JsonSchemaValue = {
            "type": "string",
            "minLength": self.min_length,
            "pattern": self.pattern,
        }
        if self.max_length is not None:
            schema["maxLength"] = self.max_length
        return schema


def _validate_stable_identifier(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate one exact D3B identity token without normalization."""
    value = cast(str, handler(raw_value))
    if len(value) > 160 or re.fullmatch(_STABLE_IDENTIFIER_PATTERN, value) is None:
        raise ValueError(
            "stable identifier requires 1-160 exact ASCII letters, digits, "
            "dot, underscore, colon, slash, or hyphen"
        )
    return value


def _validate_project_case_semver(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate one exact portable D3B SemVer token without normalization."""
    value = cast(str, handler(raw_value))
    if re.fullmatch(_PROJECT_CASE_SEMVER_PATTERN, value) is None:
        raise ValueError("contract pack version requires exact ASCII SemVer")
    return value


# These D3B-local aliases deliberately reproduce the accepted D3A lexical
# semantics without retaining D3A's mutable ``WithJsonSchema`` dictionaries.
# The package root continues to export D3A's canonical public aliases; D3B
# request fields use these private, immutable-metadata equivalents only.
StableIdentifier = Annotated[
    str,
    WrapValidator(_validate_stable_identifier),
    _ExactStringJsonSchema(1, 160, _STABLE_IDENTIFIER_PATTERN),
]
ProjectCaseSemanticVersion = Annotated[
    str,
    WrapValidator(_validate_project_case_semver),
    _ExactStringJsonSchema(5, None, _PROJECT_CASE_SEMVER_PATTERN),
]


def _validate_assessment_text(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate bounded non-blank text without changing its code points."""
    value = cast(str, handler(raw_value))
    if (
        len(value) > _MAX_ASSESSMENT_TEXT_LENGTH
        or re.fullmatch(_ASSESSMENT_TEXT_PATTERN, value) is None
    ):
        raise ValueError(
            "assessment text requires 1-4096 exact code points and at least "
            "one code point outside the declared blank/control class"
        )
    return value


AssessmentText = Annotated[
    str,
    WrapValidator(_validate_assessment_text),
    _ExactStringJsonSchema(1, _MAX_ASSESSMENT_TEXT_LENGTH, _ASSESSMENT_TEXT_PATTERN),
]


def _validate_assessment_jurisdiction_code(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate one exact uppercase ASCII jurisdiction token."""
    value = cast(str, handler(raw_value))
    if re.fullmatch(_ASSESSMENT_JURISDICTION_CODE_PATTERN, value) is None:
        raise ValueError(
            "assessment jurisdiction code requires 2-32 exact uppercase ASCII "
            "letters, digits, underscore, or hyphen"
        )
    return value


def _validate_binding_unit_token(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate one exact ASCII unit selector without normalization."""
    value = cast(str, handler(raw_value))
    if re.fullmatch(_BINDING_UNIT_TOKEN_PATTERN, value) is None:
        raise ValueError("binding unit requires 1-64 exact ASCII unit-token characters")
    return value


def _validate_assessment_currency_code(
    raw_value: Any,
    handler: ValidatorFunctionWrapHandler,
) -> str:
    """Validate one exact uppercase three-letter ASCII currency code."""
    value = cast(str, handler(raw_value))
    if re.fullmatch(_ASSESSMENT_CURRENCY_CODE_PATTERN, value) is None:
        raise ValueError(
            "assessment currency requires exactly three uppercase ASCII letters"
        )
    return value


AssessmentJurisdictionCode = Annotated[
    str,
    WrapValidator(_validate_assessment_jurisdiction_code),
    _ExactStringJsonSchema(2, 32, _ASSESSMENT_JURISDICTION_CODE_PATTERN),
]
AssessmentCurrencyCode = Annotated[
    str,
    WrapValidator(_validate_assessment_currency_code),
    _ExactStringJsonSchema(3, 3, _ASSESSMENT_CURRENCY_CODE_PATTERN),
]
BindingUnitToken = Annotated[
    str,
    WrapValidator(_validate_binding_unit_token),
    _ExactStringJsonSchema(1, 64, _BINDING_UNIT_TOKEN_PATTERN),
]


class ValidationModule(str, Enum):
    """Closed public v14 validation-module vocabulary for one request."""

    CASHFLOW = "cashflow"
    DEBT = "debt"
    WIND = "wind"
    ERA5 = "era5"
    CROSSVAL = "crossval"
    GRID = "grid"


class BaseConfigDomain(str, Enum):
    """Material authored-scenario domains that retain explicit ownership."""

    SCENARIO_IDENTITY = "scenario_identity"
    PROJECT_IDENTITY_LOCATION = "project_identity_location"
    PROJECT_RESOURCE = "project_resource"
    PROJECT_LIFECYCLE_TIMELINE = "project_lifecycle_timeline"
    TECHNOLOGY_RESOURCE = "technology_resource"
    REVENUE_TARIFF = "revenue_tariff"
    CAPEX = "capex"
    OPEX = "opex"
    TAX_STATUTORY = "tax_statutory"
    FX = "fx"
    GRID = "grid"
    ACCOUNTING = "accounting"
    FINANCING_DEBT = "financing_debt"
    WACC = "wacc"
    RUN_POSTURE = "run_posture"


class AuthoredTechnologyKind(str, Enum):
    """Closed authored-v14 technology capabilities used by binding selectors."""

    WIND_TURBINE = "wind_turbine"
    SOLAR_PV = "solar_pv"
    GENERIC_GENERATION = "generic_generation"
    STORAGE = "storage"


class ProjectCaseMaterialCategory(str, Enum):
    """Complete v1 inventory of ProjectCase material categories."""

    IDENTITY = "identity"
    LOCATION = "location"
    JURISDICTION_SUBJECT = "jurisdiction_subject"
    TECHNOLOGY_BINDING = "technology_binding"
    GENERATION_CAPACITY = "generation_capacity"
    STORAGE_CAPACITY = "storage_capacity"
    STORAGE_CHARGING_SOURCE = "storage_charging_source"
    TOPOLOGY = "topology"
    CAPEX = "capex"
    OPEX = "opex"
    CURRENCY_CONVERSION = "currency_conversion"
    PRICE_BASIS = "price_basis"
    SOURCE_PROVENANCE = "source_provenance"
    ASSUMPTION_PROVENANCE = "assumption_provenance"
    MISSING_INPUT = "missing_input"


class MaterialDispositionKind(str, Enum):
    """How one ProjectCase category participates in the D3B v1 binding."""

    ASSERT_EXACT_BASE_COMPATIBILITY = "assert_exact_base_compatibility"
    REFUSE_UNBOUND = "refuse_unbound"
    EXPLICITLY_OUT_OF_V1 = "explicitly_out_of_v1"


class MaterialDispositionAction(str, Enum):
    """Required execution consequence for every live category element."""

    ASSERT_BEFORE_GATEWAY = "assert_before_gateway"
    REFUSE_BEFORE_GATEWAY = "refuse_before_gateway"
    EXCLUDE_FROM_V1_NO_FALLBACK = "exclude_from_v1_no_fallback"


class BaseDomainDispositionKind(str, Enum):
    """How one complete authored-scenario domain is treated in v1."""

    RETAINED_AUTHORED_AUTHORITY = "retained_authored_authority"
    DECLARED_ABSENT = "declared_absent"
    REFUSE_IF_PRESENT = "refuse_if_present"


class GenerationCapacitySourceField(str, Enum):
    """Closed ProjectCase generation-capacity selectors."""

    TOTAL_POWER_CAPACITY = "total_power_capacity"
    UNIT_RATED_POWER = "unit_rated_power"
    UNIT_COUNT = "unit_count"


class V14GenerationCapacitySelector(str, Enum):
    """Closed authored-v14 selectors for generation capacity assertions."""

    PROJECT_CAPACITY_MW = "project_capacity_mw"
    TECHNOLOGY_CAPACITY_MW = "technology_capacity_mw"
    SOLAR_RESOURCE_DC_CAPACITY_MW = "solar_resource_dc_capacity_mw"
    TURBINE_COUNT = "turbine_count"
    TURBINE_RATED_POWER_MW = "turbine_rated_power_mw"
    TURBINE_TOTAL_CAPACITY_MW = "turbine_total_capacity_mw"


class StorageCapacitySourceField(str, Enum):
    """Closed ProjectCase storage-capacity selectors."""

    POWER = "power"
    ENERGY = "energy"
    DURATION = "duration"


class V14StorageCapacitySelector(str, Enum):
    """Closed authored-v14 selectors for storage assertions."""

    TECHNOLOGY_POWER_MW = "technology_power_mw"
    TECHNOLOGY_ENERGY_MWH = "technology_energy_mwh"
    TECHNOLOGY_DURATION_H = "technology_duration_h"


class LocationSourceField(str, Enum):
    """ProjectCase text eligible for an exact location assertion."""

    SITE_NAME = "site_name"
    DESCRIPTION = "description"


class V14LocationSelector(str, Enum):
    """Closed authored-v14 location selector."""

    PROJECT_LOCATION = "project_location"


class V14CostSelector(str, Enum):
    """Closed authored-v14 aggregate cost selectors."""

    CAPEX_USD_TOTAL = "capex_usd_total"
    OPEX_USD_PER_YEAR = "opex_usd_per_year"


class CostAssertionPeriodicity(str, Enum):
    """Only cost periodicities with a reviewed v1 authored counterpart."""

    ONE_TIME = "one_time"
    ANNUAL = "annual"


_DOMAINS_WITHOUT_JURISDICTION_ROUTE = frozenset(
    {
        BaseConfigDomain.SCENARIO_IDENTITY,
        BaseConfigDomain.RUN_POSTURE,
    }
)
_DOMAIN_ALLOWED_SUBJECTS = MappingProxyType(
    {
        BaseConfigDomain.PROJECT_IDENTITY_LOCATION: frozenset(
            {JurisdictionSubject.SITE}
        ),
        BaseConfigDomain.PROJECT_RESOURCE: frozenset({JurisdictionSubject.SITE}),
        BaseConfigDomain.PROJECT_LIFECYCLE_TIMELINE: frozenset(
            {
                JurisdictionSubject.SITE,
                JurisdictionSubject.PERMIT,
                JurisdictionSubject.CONTRACT,
            }
        ),
        BaseConfigDomain.TECHNOLOGY_RESOURCE: frozenset(
            {JurisdictionSubject.SITE, JurisdictionSubject.SUPPLY}
        ),
        BaseConfigDomain.REVENUE_TARIFF: frozenset(
            {JurisdictionSubject.CONTRACT, JurisdictionSubject.GRID}
        ),
        BaseConfigDomain.CAPEX: frozenset(
            {
                JurisdictionSubject.SITE,
                JurisdictionSubject.CONTRACT,
                JurisdictionSubject.ACCOUNTING,
                JurisdictionSubject.SUPPLY,
            }
        ),
        BaseConfigDomain.OPEX: frozenset(
            {
                JurisdictionSubject.SITE,
                JurisdictionSubject.CONTRACT,
                JurisdictionSubject.ACCOUNTING,
                JurisdictionSubject.SUPPLY,
            }
        ),
        BaseConfigDomain.TAX_STATUTORY: frozenset(
            {JurisdictionSubject.TAX, JurisdictionSubject.CORPORATE}
        ),
        BaseConfigDomain.FX: frozenset(
            {
                JurisdictionSubject.FINANCING,
                JurisdictionSubject.ACCOUNTING,
                JurisdictionSubject.CONTRACT,
                JurisdictionSubject.CORPORATE,
            }
        ),
        BaseConfigDomain.GRID: frozenset({JurisdictionSubject.GRID}),
        BaseConfigDomain.ACCOUNTING: frozenset(
            {JurisdictionSubject.ACCOUNTING, JurisdictionSubject.CORPORATE}
        ),
        BaseConfigDomain.FINANCING_DEBT: frozenset({JurisdictionSubject.FINANCING}),
        BaseConfigDomain.WACC: frozenset({JurisdictionSubject.FINANCING}),
    }
)


def _require_jurisdiction_subject_can_govern_domain(
    subject: JurisdictionSubject,
    domain: BaseConfigDomain,
) -> None:
    """Require one jurisdiction subject to be admissible for an authored domain."""
    if domain in _DOMAINS_WITHOUT_JURISDICTION_ROUTE:
        raise ValueError(f"{domain.value} authority routes must be project-global")
    if subject not in _DOMAIN_ALLOWED_SUBJECTS[domain]:
        raise ValueError(
            f"jurisdiction subject {subject.value} cannot govern {domain.value}"
        )


class ProjectCaseReference(StrictFrozenModel):
    """Exact identity and contract revision of one ProjectCase."""

    schema_id: Literal["dutchbay.project_case.v1"]
    contract_version: Literal["1.0.0"]
    project_id: StableIdentifier
    case_id: StableIdentifier
    revision: PositiveInt

    @model_validator(mode="after")
    def _identity_axes_are_distinct(self) -> ProjectCaseReference:
        if self.project_id == self.case_id:
            raise ValueError("project_id and case_id must be distinct")
        return self


class ScopedTechnology(StrictFrozenModel):
    """Exact ProjectCase technology binding included in assessment scope."""

    technology_binding_id: StableIdentifier
    technology_id: StableIdentifier
    asset_class: TechnologyAssetClass


class ScopedJurisdictionSubject(StrictFrozenModel):
    """Exact ProjectCase jurisdiction-subject binding included in scope."""

    jurisdiction_binding_id: StableIdentifier
    jurisdiction_code: AssessmentJurisdictionCode
    subject: JurisdictionSubject


class AudienceIntent(StrictFrozenModel):
    """Named intended audience; this is not distribution authorization."""

    audience_id: StableIdentifier
    statement: AssessmentText


class UseIntent(StrictFrozenModel):
    """Named intended use; this is not reliance or release authority."""

    use_id: StableIdentifier
    statement: AssessmentText


class IntendedDecision(StrictFrozenModel):
    """Decision question requested from a named owner role, not a decision."""

    decision_id: StableIdentifier
    decision_question: AssessmentText
    decision_owner_role: AssessmentText


class AssessmentExclusion(StrictFrozenModel):
    """Explicit scope exclusion with a stable identity and rationale."""

    exclusion_id: StableIdentifier
    subject: AssessmentText
    rationale: AssessmentText


class MaterialityRule(StrictFrozenModel):
    """Declared materiality rule; D3B does not adjudicate it."""

    rule_id: StableIdentifier
    statement: AssessmentText


class AssessmentScope(StrictFrozenModel):
    """Explicit assessment intent bound to one exact ProjectCase revision."""

    schema_id: Literal["dutchbay.assessment_scope.v1"]
    contract_version: Literal["1.0.0"]
    scope_id: StableIdentifier
    project_case: ProjectCaseReference
    project_boundary: AssessmentText
    technology_scope: tuple[ScopedTechnology, ...]
    jurisdiction_scope: tuple[ScopedJurisdictionSubject, ...]
    project_stage: AssessmentText
    intended_audiences: tuple[AudienceIntent, ...]
    intended_uses: tuple[UseIntent, ...]
    intended_decision: IntendedDecision
    run_mode: RunMode
    target_grade_request: AssessmentGrade
    evidence_cutoff: date
    valuation_date: date
    reporting_currency: AssessmentCurrencyCode
    price_nominality: PriceNominality
    price_basis_id: StableIdentifier
    price_basis_description: AssessmentText
    exclusions: tuple[AssessmentExclusion, ...]
    materiality_rule: MaterialityRule

    @model_validator(mode="after")
    def _scope_is_closed_and_explicit(self) -> AssessmentScope:
        if not self.technology_scope:
            raise ValueError("assessment scope requires at least one technology")
        if not self.jurisdiction_scope:
            raise ValueError(
                "assessment scope requires at least one jurisdiction subject"
            )
        if not self.intended_audiences or not self.intended_uses:
            raise ValueError("assessment scope requires intended audiences and uses")
        _require_unique(
            (item.technology_binding_id for item in self.technology_scope),
            "technology_binding_id",
        )
        _require_unique(
            ((item.technology_id, item.asset_class) for item in self.technology_scope),
            "technology scope",
        )
        _require_unique(
            (item.jurisdiction_binding_id for item in self.jurisdiction_scope),
            "jurisdiction_binding_id",
        )
        _require_unique(
            (
                (item.jurisdiction_code, item.subject)
                for item in self.jurisdiction_scope
            ),
            "jurisdiction subject scope",
        )
        site_subjects = tuple(
            item
            for item in self.jurisdiction_scope
            if item.subject is JurisdictionSubject.SITE
        )
        if len(site_subjects) != 1:
            raise ValueError("assessment scope requires exactly one site jurisdiction")
        _require_unique(
            (item.audience_id for item in self.intended_audiences), "audience_id"
        )
        _require_unique((item.use_id for item in self.intended_uses), "use_id")
        _require_unique((item.exclusion_id for item in self.exclusions), "exclusion_id")
        return self


class AuthoredScenarioValidationReceipt(StrictFrozenModel):
    """Declared validation receipt for one resolved authored v14 scenario.

    ``resolved_config_sha256`` uses the public
    :func:`analytics.run_manifest.config_sha256` semantics after the caller has
    proved the mapping is finite and JSON-compatible.  The receipt is a declared
    validation statement, not independent assurance or release authority.
    """

    schema_id: Literal["dutchbay.authored_scenario_validation_receipt.v1"]
    contract_version: Literal["1.0.0"]
    receipt_id: StableIdentifier
    receipt_scope: Literal["declared_authored_scenario_validation"]
    resolved_config_sha256: Sha256Hex
    validator_id: StableIdentifier
    validator_version: ProjectCaseSemanticVersion
    validator_control_ids: tuple[StableIdentifier, ...]
    validation_modules: tuple[ValidationModule, ...]
    outcome: Literal["pass"]
    v14_schema_guard_id: Literal["analytics.schema_guard.validate_config_for_v14"]
    v14_gateway_id: Literal["analytics.evaluation_v14.evaluate_with_overrides"]
    authority_source_id: StableIdentifier

    @model_validator(mode="after")
    def _validation_statement_is_explicit(self) -> AuthoredScenarioValidationReceipt:
        if not self.validator_control_ids:
            raise ValueError("validation receipt requires validator_control_ids")
        _require_unique(self.validator_control_ids, "validator_control_id")
        _require_validation_modules(self.validation_modules)
        return self


class BaseSubjectAuthority(StrictFrozenModel):
    """Bind one base-scenario subject to exact jurisdiction and source authority."""

    jurisdiction_binding_id: StableIdentifier
    jurisdiction_code: AssessmentJurisdictionCode
    subject: JurisdictionSubject
    authority_source_id: StableIdentifier


class BaseTechnologyAuthority(StrictFrozenModel):
    """Bind one authored technology key to a ProjectCase technology binding."""

    base_config_key: StableIdentifier
    technology_binding_id: StableIdentifier
    technology_id: StableIdentifier
    asset_class: TechnologyAssetClass
    authored_technology_kind: AuthoredTechnologyKind
    authority_source_id: StableIdentifier

    @model_validator(mode="after")
    def _kind_matches_asset_class(self) -> BaseTechnologyAuthority:
        expected_class = (
            TechnologyAssetClass.STORAGE
            if self.authored_technology_kind is AuthoredTechnologyKind.STORAGE
            else TechnologyAssetClass.GENERATION
        )
        if self.asset_class is not expected_class:
            raise ValueError(
                "authored technology kind and ProjectCase asset class must agree"
            )
        return self


class BaseDomainAuthorityRoute(StrictFrozenModel):
    """One exact authority route within a retained authored domain."""

    authority_source_id: StableIdentifier
    jurisdiction_binding_id: StableIdentifier | None
    technology_binding_id: StableIdentifier | None


class BaseDomainDisposition(StrictFrozenModel):
    """Complete disposition and authority routes for one authored domain."""

    domain: BaseConfigDomain
    disposition: BaseDomainDispositionKind
    authority_routes: tuple[BaseDomainAuthorityRoute, ...]
    rationale: AssessmentText

    @model_validator(mode="after")
    def _authority_routes_match_disposition(self) -> BaseDomainDisposition:
        retained = (
            self.disposition is BaseDomainDispositionKind.RETAINED_AUTHORED_AUTHORITY
        )
        if retained != bool(self.authority_routes):
            raise ValueError(
                "retained domains require authority routes and non-retained domains "
                "forbid them"
            )
        _require_unique(
            (
                (
                    route.jurisdiction_binding_id,
                    route.technology_binding_id,
                )
                for route in self.authority_routes
            ),
            "base domain authority route",
        )
        return self


class BaseScenarioIdentity(StrictFrozenModel):
    """Versioned authored-scenario identity, digests, and retained authorities."""

    schema_id: Literal["dutchbay.base_scenario_identity.v1"]
    contract_version: Literal["1.0.0"]
    config_id: StableIdentifier
    config_version: ProjectCaseSemanticVersion
    source_file_sha256: Sha256Hex
    resolved_config_sha256: Sha256Hex
    authority_source_id: StableIdentifier
    authority_basis: AssessmentText
    validation_receipt: AuthoredScenarioValidationReceipt
    subject_authorities: tuple[BaseSubjectAuthority, ...]
    technology_authorities: tuple[BaseTechnologyAuthority, ...]
    domain_dispositions: tuple[BaseDomainDisposition, ...]

    @model_validator(mode="after")
    def _base_authorities_are_closed(self) -> BaseScenarioIdentity:
        if (
            self.validation_receipt.resolved_config_sha256
            != self.resolved_config_sha256
        ):
            raise ValueError(
                "validation receipt resolved digest must match base scenario identity"
            )
        if not self.subject_authorities:
            raise ValueError("base scenario requires subject authorities")
        if not self.technology_authorities:
            raise ValueError("base scenario requires technology authorities")
        if self.validation_receipt.authority_source_id != self.authority_source_id:
            raise ValueError(
                "validation receipt authority source must match base scenario authority"
            )
        _require_unique(
            (
                (item.jurisdiction_code, item.subject)
                for item in self.subject_authorities
            ),
            "base subject authority",
        )
        _require_unique(
            (item.jurisdiction_binding_id for item in self.subject_authorities),
            "base subject jurisdiction_binding_id",
        )
        _require_unique(
            (item.base_config_key for item in self.technology_authorities),
            "base technology config key",
        )
        _require_unique(
            (item.technology_binding_id for item in self.technology_authorities),
            "base technology_binding_id",
        )
        _require_unique(
            (
                (item.technology_id, item.asset_class)
                for item in self.technology_authorities
            ),
            "base technology authority",
        )
        domains = tuple(item.domain for item in self.domain_dispositions)
        _require_unique(domains, "base domain disposition")
        expected_domains = set(BaseConfigDomain)
        if set(domains) != expected_domains:
            missing = sorted(item.value for item in expected_domains - set(domains))
            extra = sorted(item.value for item in set(domains) - expected_domains)
            raise ValueError(
                "base scenario must disposition every authored domain; "
                f"missing={missing}, extra={extra}"
            )

        subject_by_id = {
            item.jurisdiction_binding_id: item for item in self.subject_authorities
        }
        technology_by_id = {
            item.technology_binding_id: item for item in self.technology_authorities
        }
        routed_subjects: set[str] = set()
        routed_technologies: set[str] = set()
        for disposition in self.domain_dispositions:
            for route in disposition.authority_routes:
                if disposition.domain in _DOMAINS_WITHOUT_JURISDICTION_ROUTE:
                    if (
                        route.jurisdiction_binding_id is not None
                        or route.technology_binding_id is not None
                    ):
                        raise ValueError(
                            f"{disposition.domain.value} authority routes must be "
                            "project-global"
                        )
                    if route.authority_source_id != self.authority_source_id:
                        raise ValueError(
                            f"{disposition.domain.value} authority must use the base "
                            "scenario authority source"
                        )
                    continue

                jurisdiction_binding_id = route.jurisdiction_binding_id
                if jurisdiction_binding_id is None:
                    raise ValueError(
                        f"{disposition.domain.value} requires a "
                        "jurisdiction-subject route"
                    )
                subject_authority = subject_by_id.get(jurisdiction_binding_id)
                if subject_authority is None:
                    raise ValueError(
                        "base domain route has a dangling jurisdiction binding"
                    )
                _require_jurisdiction_subject_can_govern_domain(
                    subject_authority.subject,
                    disposition.domain,
                )
                routed_subjects.add(jurisdiction_binding_id)

                route_authority_sources = {
                    self.authority_source_id,
                    subject_authority.authority_source_id,
                }
                technology_binding_id = route.technology_binding_id
                if technology_binding_id is not None:
                    technology_authority = technology_by_id.get(technology_binding_id)
                    if technology_authority is None:
                        raise ValueError(
                            "base domain route has a dangling technology binding"
                        )
                    routed_technologies.add(technology_binding_id)
                    route_authority_sources.add(
                        technology_authority.authority_source_id
                    )
                elif disposition.domain is BaseConfigDomain.TECHNOLOGY_RESOURCE:
                    raise ValueError(
                        "technology_resource authority routes require a technology "
                        "binding"
                    )
                if route.authority_source_id not in route_authority_sources:
                    raise ValueError(
                        "base domain route authority source must be declared by its "
                        "base, subject, or technology authority"
                    )

        if routed_subjects != set(subject_by_id):
            raise ValueError(
                "every base subject authority requires a retained domain route"
            )
        if routed_technologies != set(technology_by_id):
            raise ValueError(
                "every base technology authority requires a retained domain route"
            )
        return self


class ScenarioIdentityAssertion(StrictFrozenModel):
    """Require exact ProjectCase case-name and authored scenario-name equality."""

    kind: Literal["scenario_identity_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.IDENTITY]
    project_case_selector: Literal["identity.case_name"]
    base_selector: Literal["scenario_name"]


class LocationAssertion(StrictFrozenModel):
    """Require one exact ProjectCase site string to match authored location."""

    kind: Literal["location_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.LOCATION]
    project_case_selector: LocationSourceField
    base_selector: V14LocationSelector


class JurisdictionSubjectAssertion(StrictFrozenModel):
    """Route a ProjectCase jurisdiction subject to an authored domain."""

    kind: Literal["jurisdiction_subject_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.JURISDICTION_SUBJECT]
    jurisdiction_binding_id: StableIdentifier
    jurisdiction_code: AssessmentJurisdictionCode
    subject: JurisdictionSubject
    base_domain: BaseConfigDomain

    @model_validator(mode="after")
    def _subject_can_govern_domain(self) -> JurisdictionSubjectAssertion:
        _require_jurisdiction_subject_can_govern_domain(
            self.subject,
            self.base_domain,
        )
        return self


class TechnologyBindingAssertion(StrictFrozenModel):
    """Require one asset technology to match one authored technology key."""

    kind: Literal["technology_binding_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.TECHNOLOGY_BINDING]
    asset_id: StableIdentifier
    technology_binding_id: StableIdentifier
    technology_id: StableIdentifier
    asset_class: TechnologyAssetClass
    authored_technology_kind: AuthoredTechnologyKind
    base_config_key: StableIdentifier

    @model_validator(mode="after")
    def _kind_matches_asset_class(self) -> TechnologyBindingAssertion:
        expected_class = (
            TechnologyAssetClass.STORAGE
            if self.authored_technology_kind is AuthoredTechnologyKind.STORAGE
            else TechnologyAssetClass.GENERATION
        )
        if self.asset_class is not expected_class:
            raise ValueError(
                "authored technology kind and ProjectCase asset class must agree"
            )
        return self


class GenerationCapacityAssertion(StrictFrozenModel):
    """Require one exact generation proposition to match one authored value."""

    kind: Literal["generation_capacity_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.GENERATION_CAPACITY]
    asset_id: StableIdentifier
    base_config_key: StableIdentifier | None
    project_case_selector: GenerationCapacitySourceField
    base_selector: V14GenerationCapacitySelector
    expected_unit: BindingUnitToken
    electrical_basis: ElectricalBasis
    capacity_basis: GenerationCapacityBasis
    authored_technology_kind: Literal[
        AuthoredTechnologyKind.WIND_TURBINE,
        AuthoredTechnologyKind.SOLAR_PV,
        AuthoredTechnologyKind.GENERIC_GENERATION,
    ]

    @model_validator(mode="after")
    def _target_key_matches_selector(self) -> GenerationCapacityAssertion:
        project_level = (
            self.base_selector is V14GenerationCapacitySelector.PROJECT_CAPACITY_MW
        )
        if project_level and self.base_config_key is not None:
            raise ValueError(
                "project capacity assertion must not name a technology key"
            )
        if not project_level and self.base_config_key is None:
            raise ValueError("technology capacity assertion requires base_config_key")
        valid_targets = {
            GenerationCapacitySourceField.TOTAL_POWER_CAPACITY: {
                V14GenerationCapacitySelector.PROJECT_CAPACITY_MW,
                V14GenerationCapacitySelector.TECHNOLOGY_CAPACITY_MW,
                V14GenerationCapacitySelector.SOLAR_RESOURCE_DC_CAPACITY_MW,
                V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW,
            },
            GenerationCapacitySourceField.UNIT_RATED_POWER: {
                V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW,
            },
            GenerationCapacitySourceField.UNIT_COUNT: {
                V14GenerationCapacitySelector.TURBINE_COUNT,
            },
        }
        if self.base_selector not in valid_targets[self.project_case_selector]:
            raise ValueError(
                "generation source and authored selector dimensions must match"
            )
        turbine_targets = {
            V14GenerationCapacitySelector.TURBINE_COUNT,
            V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW,
            V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW,
        }
        if self.base_selector in turbine_targets:
            if self.authored_technology_kind is not AuthoredTechnologyKind.WIND_TURBINE:
                raise ValueError(
                    "turbine selectors require authored_technology_kind=wind_turbine"
                )
            if self.electrical_basis is ElectricalBasis.DC:
                raise ValueError("turbine selectors cannot bind DC capacity")
            if self.capacity_basis is not GenerationCapacityBasis.NAMEPLATE:
                raise ValueError("turbine selectors require nameplate capacity basis")

        solar_dc_target = (
            self.base_selector
            is V14GenerationCapacitySelector.SOLAR_RESOURCE_DC_CAPACITY_MW
        )
        if solar_dc_target:
            if self.authored_technology_kind is not AuthoredTechnologyKind.SOLAR_PV:
                raise ValueError(
                    "solar DC selector requires authored_technology_kind=solar_pv"
                )
            if self.electrical_basis is not ElectricalBasis.DC:
                raise ValueError("solar DC selector requires electrical_basis=dc")
            if self.capacity_basis is not GenerationCapacityBasis.NAMEPLATE:
                raise ValueError("solar DC selector requires nameplate capacity basis")
        elif self.electrical_basis is ElectricalBasis.DC:
            raise ValueError(
                "DC generation capacity cannot bind an authored AC/MW selector"
            )

        if self.project_case_selector is GenerationCapacitySourceField.UNIT_COUNT:
            if self.expected_unit != "count":
                raise ValueError("generation selector requires expected_unit=count")
            return self

        expected_units = {
            ElectricalBasis.AC: frozenset({"MWac"}),
            ElectricalBasis.DC: frozenset({"MWdc", "MWp"}),
            ElectricalBasis.NOT_APPLICABLE: frozenset({"MW"}),
        }[self.electrical_basis]
        if self.expected_unit not in expected_units:
            units = ", ".join(sorted(expected_units))
            raise ValueError(
                f"generation electrical basis requires expected_unit in {{{units}}}"
            )
        return self


class StorageCapacityAssertion(StrictFrozenModel):
    """Require one storage power, energy, or duration value to match the base."""

    kind: Literal["storage_capacity_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.STORAGE_CAPACITY]
    asset_id: StableIdentifier
    base_config_key: StableIdentifier
    project_case_selector: StorageCapacitySourceField
    base_selector: V14StorageCapacitySelector
    expected_unit: BindingUnitToken
    electrical_basis: StorageElectricalBasis
    capacity_basis: StorageCapacityBasis
    authored_technology_kind: Literal[AuthoredTechnologyKind.STORAGE]

    @model_validator(mode="after")
    def _source_and_target_dimensions_match(self) -> StorageCapacityAssertion:
        pairs = {
            StorageCapacitySourceField.POWER: V14StorageCapacitySelector.TECHNOLOGY_POWER_MW,
            StorageCapacitySourceField.ENERGY: V14StorageCapacitySelector.TECHNOLOGY_ENERGY_MWH,
            StorageCapacitySourceField.DURATION: V14StorageCapacitySelector.TECHNOLOGY_DURATION_H,
        }
        if pairs[self.project_case_selector] is not self.base_selector:
            raise ValueError(
                "storage source and authored selector dimensions must match"
            )
        if self.electrical_basis is StorageElectricalBasis.DC:
            raise ValueError(
                "D3B v1 authored storage selectors do not establish a DC-to-AC basis"
            )
        expected_units = {
            StorageCapacitySourceField.POWER: frozenset({"MW", "MWac"}),
            StorageCapacitySourceField.ENERGY: frozenset({"MWh", "MWhac"}),
            StorageCapacitySourceField.DURATION: frozenset({"hour"}),
        }[self.project_case_selector]
        if self.expected_unit not in expected_units:
            units = ", ".join(sorted(expected_units))
            raise ValueError(f"storage selector requires expected_unit in {{{units}}}")
        return self


class CostCompatibilityAssertion(StrictFrozenModel):
    """Require the complete selected ProjectCase cost set to match the base."""

    kind: Literal["cost_compatibility_assertion"]
    assertion_id: StableIdentifier
    category: Literal[
        ProjectCaseMaterialCategory.CAPEX,
        ProjectCaseMaterialCategory.OPEX,
    ]
    included_line_ids: tuple[StableIdentifier, ...]
    price_basis_id: StableIdentifier
    reporting_currency: AssessmentCurrencyCode
    periodicity: CostAssertionPeriodicity
    base_selector: V14CostSelector

    @model_validator(mode="after")
    def _cost_dimension_is_exact(self) -> CostCompatibilityAssertion:
        if not self.included_line_ids:
            raise ValueError("cost assertion requires included_line_ids")
        _require_unique(self.included_line_ids, "included cost line_id")
        expected = {
            ProjectCaseMaterialCategory.CAPEX: (
                CostAssertionPeriodicity.ONE_TIME,
                V14CostSelector.CAPEX_USD_TOTAL,
            ),
            ProjectCaseMaterialCategory.OPEX: (
                CostAssertionPeriodicity.ANNUAL,
                V14CostSelector.OPEX_USD_PER_YEAR,
            ),
        }
        if expected[self.category] != (self.periodicity, self.base_selector):
            raise ValueError("cost category, periodicity, and base selector must agree")
        if self.reporting_currency != "USD":
            raise ValueError(
                "D3B v1 cost compatibility supports authored USD totals only"
            )
        return self


class PriceBasisAssertion(StrictFrozenModel):
    """Require project-wide scope and ProjectCase price-basis identity to agree."""

    kind: Literal["price_basis_assertion"]
    assertion_id: StableIdentifier
    category: Literal[ProjectCaseMaterialCategory.PRICE_BASIS]
    price_basis_id: StableIdentifier
    valuation_date: date
    reporting_currency: AssessmentCurrencyCode
    nominality: PriceNominality


CompatibilityAssertion = Annotated[
    Union[
        ScenarioIdentityAssertion,
        LocationAssertion,
        JurisdictionSubjectAssertion,
        TechnologyBindingAssertion,
        GenerationCapacityAssertion,
        StorageCapacityAssertion,
        CostCompatibilityAssertion,
        PriceBasisAssertion,
    ],
    Field(discriminator="kind"),
]


class ProjectCaseMaterialDisposition(StrictFrozenModel):
    """Closed disposition of one complete ProjectCase material category."""

    category: ProjectCaseMaterialCategory
    disposition: MaterialDispositionKind
    action: MaterialDispositionAction
    rationale: AssessmentText

    @model_validator(mode="after")
    def _action_matches_disposition(self) -> ProjectCaseMaterialDisposition:
        expected = {
            MaterialDispositionKind.ASSERT_EXACT_BASE_COMPATIBILITY: (
                MaterialDispositionAction.ASSERT_BEFORE_GATEWAY
            ),
            MaterialDispositionKind.REFUSE_UNBOUND: (
                MaterialDispositionAction.REFUSE_BEFORE_GATEWAY
            ),
            MaterialDispositionKind.EXPLICITLY_OUT_OF_V1: (
                MaterialDispositionAction.EXCLUDE_FROM_V1_NO_FALLBACK
            ),
        }
        if self.action is not expected[self.disposition]:
            raise ValueError("material disposition and execution action must agree")
        return self


class RunModeBindingPolicy(StrictFrozenModel):
    """The sole scope-owned v1 override policy."""

    kind: Literal["canonical_run_mode_only"]
    absent_canonical_mode: Literal["add_scope_run_mode"]
    present_canonical_mode: Literal["require_exact_scope_match"]
    legacy_alias: Literal["refuse"]
    unknown_run_keys: Literal["refuse"]


class V14BindingPolicy(StrictFrozenModel):
    """Closed compatibility plan between ProjectCase, scope, and authored v14."""

    schema_id: Literal["dutchbay.v14_binding_policy.v1"]
    contract_version: Literal["1.0.0"]
    policy_id: StableIdentifier
    policy_version: ProjectCaseSemanticVersion
    project_case: ProjectCaseReference
    assertions: tuple[CompatibilityAssertion, ...]
    material_dispositions: tuple[ProjectCaseMaterialDisposition, ...]
    run_mode_policy: RunModeBindingPolicy

    @model_validator(mode="after")
    def _policy_covers_every_material_category(self) -> V14BindingPolicy:
        if not self.assertions:
            raise ValueError("v14 binding policy requires compatibility assertions")
        _require_unique((item.assertion_id for item in self.assertions), "assertion_id")
        route_pairs: set[tuple[tuple[object, ...], tuple[object, ...]]] = set()
        target_routes: set[tuple[object, ...]] = set()
        cost_line_ids: set[str] = set()
        source_route: tuple[object, ...]
        target_route: tuple[object, ...]
        for assertion in _ordered_policy_assertions(self.assertions):
            if isinstance(assertion, ScenarioIdentityAssertion):
                source_route = (assertion.category, assertion.project_case_selector)
                target_route = (assertion.category, assertion.base_selector)
            elif isinstance(assertion, LocationAssertion):
                source_route = (assertion.category, assertion.project_case_selector)
                target_route = (assertion.category, assertion.base_selector)
            elif isinstance(assertion, JurisdictionSubjectAssertion):
                source_route = (
                    assertion.category,
                    assertion.jurisdiction_binding_id,
                    assertion.subject,
                )
                target_route = (
                    assertion.category,
                    assertion.base_domain,
                    assertion.jurisdiction_binding_id,
                )
            elif isinstance(assertion, TechnologyBindingAssertion):
                source_route = (assertion.category, assertion.asset_id)
                target_route = (assertion.category, assertion.base_config_key)
            elif isinstance(assertion, GenerationCapacityAssertion):
                source_route = (
                    assertion.category,
                    assertion.asset_id,
                    assertion.project_case_selector,
                )
                target_route = (
                    assertion.category,
                    assertion.base_config_key,
                    assertion.base_selector,
                )
            elif isinstance(assertion, StorageCapacityAssertion):
                source_route = (
                    assertion.category,
                    assertion.asset_id,
                    assertion.project_case_selector,
                )
                target_route = (
                    assertion.category,
                    assertion.base_config_key,
                    assertion.base_selector,
                )
            elif isinstance(assertion, CostCompatibilityAssertion):
                source_route = (assertion.category, *assertion.included_line_ids)
                target_route = (assertion.category, assertion.base_selector)
                overlap = cost_line_ids.intersection(assertion.included_line_ids)
                if overlap:
                    raise ValueError(
                        "cost compatibility assertions must not reuse line IDs; "
                        f"overlap={sorted(overlap)}"
                    )
                cost_line_ids.update(assertion.included_line_ids)
            else:
                assert isinstance(assertion, PriceBasisAssertion)
                source_route = (assertion.category, assertion.price_basis_id)
                target_route = (assertion.category, "scope_price_basis")
            route_pair = (source_route, target_route)
            if route_pair in route_pairs:
                raise ValueError("duplicate compatibility source/target route")
            if target_route in target_routes:
                raise ValueError("duplicate authored compatibility target route")
            route_pairs.add(route_pair)
            target_routes.add(target_route)
        categories = [item.category for item in self.material_dispositions]
        _require_unique(categories, "ProjectCase material category")
        expected_categories = frozenset(ProjectCaseMaterialCategory)
        if set(categories) != expected_categories:
            missing = sorted(
                item.value for item in expected_categories - set(categories)
            )
            extra = sorted(item.value for item in set(categories) - expected_categories)
            raise ValueError(
                "binding policy must disposition every ProjectCase material category; "
                f"missing={missing}, extra={extra}"
            )
        asserted_categories = {item.category for item in self.assertions}
        disposition_by_category = {
            item.category: item.disposition for item in self.material_dispositions
        }
        for category in ProjectCaseMaterialCategory:
            asserts = category in asserted_categories
            disposition_asserts = (
                disposition_by_category[category]
                is MaterialDispositionKind.ASSERT_EXACT_BASE_COMPATIBILITY
            )
            if asserts != disposition_asserts:
                raise ValueError(
                    "compatibility assertions and material dispositions must agree for "
                    f"{category.value}"
                )
        _require_internal_policy_graph(self)
        return self


class EvaluationRequest(StrictFrozenModel):
    """Versioned D3B request for one later, compatibility-gated v14 run."""

    schema_id: Literal["dutchbay.evaluation_request.v1"]
    contract_version: Literal["1.0.0"]
    request_id: StableIdentifier
    project_case: ProjectCaseReference
    scope: AssessmentScope
    base_scenario: BaseScenarioIdentity
    validation_modules: tuple[ValidationModule, ...]
    binding_policy: V14BindingPolicy

    @model_validator(mode="after")
    def _request_axes_are_bound(self) -> EvaluationRequest:
        if self.scope.project_case != self.project_case:
            raise ValueError(
                "scope ProjectCase reference must match evaluation request"
            )
        if self.binding_policy.project_case != self.project_case:
            raise ValueError(
                "binding-policy ProjectCase reference must match evaluation request"
            )
        _require_validation_modules(self.validation_modules)
        if set(self.validation_modules) != set(
            self.base_scenario.validation_receipt.validation_modules
        ):
            raise ValueError(
                "request validation_modules must match authored validation receipt"
            )
        _require_internal_request_graph(self)
        return self


def _require_unique(values: Any, label: str) -> None:
    """Require one finite iterable to contain unique hashable values."""
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        raise ValueError(f"duplicate {label}")


def _require_validation_modules(modules: tuple[ValidationModule, ...]) -> None:
    """Require unique modules and the canonical cashflow/debt core."""
    if not modules:
        raise ValueError("validation modules must not be empty")
    _require_unique(modules, "validation module")
    required = {ValidationModule.CASHFLOW, ValidationModule.DEBT}
    if not required.issubset(set(modules)):
        raise ValueError("validation modules must include cashflow and debt")


def _ordered_policy_assertions(
    assertions: tuple[CompatibilityAssertion, ...],
) -> tuple[CompatibilityAssertion, ...]:
    """Return a canonical validation order without changing authored tuple order."""
    categories = tuple(ProjectCaseMaterialCategory)
    return tuple(
        sorted(
            assertions,
            key=lambda item: (categories.index(item.category), item.assertion_id),
        )
    )


def _require_internal_policy_graph(policy: V14BindingPolicy) -> None:
    """Close every relationship whose operands live inside one binding policy."""
    assertions = _ordered_policy_assertions(policy.assertions)
    technology_assertions = tuple(
        item for item in assertions if isinstance(item, TechnologyBindingAssertion)
    )
    technology_by_asset = {item.asset_id: item for item in technology_assertions}
    if len(technology_by_asset) != len(technology_assertions):
        raise ValueError("technology assertions must use unique ProjectCase asset IDs")
    technology_by_binding = {
        item.technology_binding_id: item for item in technology_assertions
    }
    if len(technology_by_binding) != len(technology_assertions):
        raise ValueError(
            "D3B v1 requires one policy-owned physical asset per technology binding ID"
        )
    _require_unique(
        ((item.technology_id, item.asset_class) for item in technology_assertions),
        "technology assertion scope",
    )

    jurisdiction_identity_by_binding: dict[str, tuple[str, JurisdictionSubject]] = {}
    jurisdiction_binding_by_identity: dict[tuple[str, JurisdictionSubject], str] = {}
    generation_by_asset: dict[str, list[GenerationCapacityAssertion]] = {}
    storage_by_asset: dict[str, list[StorageCapacityAssertion]] = {}
    cost_assertions: list[CostCompatibilityAssertion] = []
    price_assertions: list[PriceBasisAssertion] = []

    for assertion in assertions:
        if isinstance(assertion, JurisdictionSubjectAssertion):
            identity = (assertion.jurisdiction_code, assertion.subject)
            prior_identity = jurisdiction_identity_by_binding.setdefault(
                assertion.jurisdiction_binding_id,
                identity,
            )
            if prior_identity != identity:
                raise ValueError(
                    "jurisdiction assertions for one binding ID must share exact "
                    "jurisdiction code and subject"
                )
            prior_binding = jurisdiction_binding_by_identity.setdefault(
                identity,
                assertion.jurisdiction_binding_id,
            )
            if prior_binding != assertion.jurisdiction_binding_id:
                raise ValueError(
                    "jurisdiction assertions must use one binding ID per exact "
                    "jurisdiction code and subject"
                )
        elif isinstance(assertion, GenerationCapacityAssertion):
            generation_by_asset.setdefault(assertion.asset_id, []).append(assertion)
        elif isinstance(assertion, StorageCapacityAssertion):
            storage_by_asset.setdefault(assertion.asset_id, []).append(assertion)
        elif isinstance(assertion, CostCompatibilityAssertion):
            cost_assertions.append(assertion)
        elif isinstance(assertion, PriceBasisAssertion):
            price_assertions.append(assertion)

    for asset_id in sorted(generation_by_asset):
        technology = technology_by_asset.get(asset_id)
        if technology is None or (
            technology.asset_class is not TechnologyAssetClass.GENERATION
        ):
            raise ValueError(
                "generation capacity assertion requires a matching generation asset "
                "technology assertion"
            )
        generation_assertions = generation_by_asset[asset_id]
        for assertion in generation_assertions:
            if (
                assertion.authored_technology_kind
                is not technology.authored_technology_kind
            ):
                raise ValueError(
                    "generation capacity and technology assertions must use the same "
                    "authored technology kind"
                )
            if (
                assertion.base_config_key is not None
                and assertion.base_config_key != technology.base_config_key
            ):
                raise ValueError(
                    "generation capacity and technology assertions must use the same "
                    "base config key"
                )
        generation_bases = {
            (item.electrical_basis, item.capacity_basis)
            for item in generation_assertions
        }
        if len(generation_bases) != 1:
            raise ValueError(
                "generation capacity assertions for one ProjectCase asset must share "
                "electrical and capacity bases"
            )

    for asset_id in sorted(storage_by_asset):
        technology = technology_by_asset.get(asset_id)
        if technology is None or (
            technology.asset_class is not TechnologyAssetClass.STORAGE
        ):
            raise ValueError(
                "storage capacity assertion requires a matching storage asset "
                "technology assertion"
            )
        storage_assertions = storage_by_asset[asset_id]
        for assertion in storage_assertions:
            if (
                assertion.authored_technology_kind
                is not technology.authored_technology_kind
            ):
                raise ValueError(
                    "storage capacity and technology assertions must use the same "
                    "authored technology kind"
                )
            if assertion.base_config_key != technology.base_config_key:
                raise ValueError(
                    "storage capacity and technology assertions must use the same base "
                    "config key"
                )
        storage_bases = {
            (item.electrical_basis, item.capacity_basis) for item in storage_assertions
        }
        if len(storage_bases) != 1:
            raise ValueError(
                "storage capacity assertions for one ProjectCase asset must share "
                "electrical and capacity bases"
            )

    for technology in technology_assertions:
        if technology.asset_class is TechnologyAssetClass.GENERATION:
            has_technology_route = any(
                item.base_config_key is not None
                for item in generation_by_asset.get(technology.asset_id, ())
            )
            if not has_technology_route:
                raise ValueError(
                    "generation compatibility requires one per-technology capacity route"
                )
        else:
            selectors = {
                item.base_selector
                for item in storage_by_asset.get(technology.asset_id, ())
            }
            if selectors != set(V14StorageCapacitySelector):
                raise ValueError(
                    "storage compatibility requires power, energy, and duration routes"
                )

    if len(price_assertions) != 1:
        raise ValueError(
            "v14 binding policy requires exactly one price-basis assertion"
        )
    price_assertion = price_assertions[0]
    for cost_assertion in cost_assertions:
        if (
            cost_assertion.price_basis_id != price_assertion.price_basis_id
            or cost_assertion.reporting_currency != price_assertion.reporting_currency
        ):
            raise ValueError(
                "cost and price-basis assertions must share price basis and reporting "
                "currency"
            )


def _require_internal_request_graph(request: EvaluationRequest) -> None:
    """Close every duplicated authority, scope, and policy axis in one request."""
    scope_subjects = {
        item.jurisdiction_binding_id: (item.jurisdiction_code, item.subject)
        for item in request.scope.jurisdiction_scope
    }
    base_subjects = {
        item.jurisdiction_binding_id: (item.jurisdiction_code, item.subject)
        for item in request.base_scenario.subject_authorities
    }
    if scope_subjects != base_subjects:
        raise ValueError(
            "scope and base scenario jurisdiction-subject bindings must match exactly"
        )

    scope_technologies = {
        item.technology_binding_id: (item.technology_id, item.asset_class)
        for item in request.scope.technology_scope
    }
    base_technologies = {
        item.technology_binding_id: (item.technology_id, item.asset_class)
        for item in request.base_scenario.technology_authorities
    }
    if scope_technologies != base_technologies:
        raise ValueError(
            "scope and base scenario technology bindings must match exactly"
        )

    base_technology_by_key = {
        item.base_config_key: item
        for item in request.base_scenario.technology_authorities
    }
    retained_domains = {
        item.domain
        for item in request.base_scenario.domain_dispositions
        if item.disposition is BaseDomainDispositionKind.RETAINED_AUTHORED_AUTHORITY
    }
    technology_domain_routes = {
        (item.domain, route.technology_binding_id)
        for item in request.base_scenario.domain_dispositions
        for route in item.authority_routes
        if route.technology_binding_id is not None
    }
    jurisdiction_domain_routes: set[tuple[str, BaseConfigDomain]] = set()
    for disposition in request.base_scenario.domain_dispositions:
        for route in disposition.authority_routes:
            jurisdiction_binding_id = route.jurisdiction_binding_id
            if jurisdiction_binding_id is not None:
                jurisdiction_domain_routes.add(
                    (jurisdiction_binding_id, disposition.domain)
                )

    jurisdiction_assertions: set[str] = set()
    technology_assertions: set[str] = set()
    for assertion in _ordered_policy_assertions(request.binding_policy.assertions):
        if isinstance(assertion, ScenarioIdentityAssertion):
            if BaseConfigDomain.SCENARIO_IDENTITY not in retained_domains:
                raise ValueError(
                    "scenario identity assertion requires retained authored identity"
                )
        elif isinstance(assertion, LocationAssertion):
            if BaseConfigDomain.PROJECT_IDENTITY_LOCATION not in retained_domains:
                raise ValueError(
                    "location assertion requires retained authored project location"
                )
        elif isinstance(assertion, JurisdictionSubjectAssertion):
            expected_subject = scope_subjects.get(assertion.jurisdiction_binding_id)
            if expected_subject != (
                assertion.jurisdiction_code,
                assertion.subject,
            ):
                raise ValueError(
                    "jurisdiction assertion must match the exact scoped/base subject"
                )
            assertion_route = (
                assertion.jurisdiction_binding_id,
                assertion.base_domain,
            )
            if assertion_route not in jurisdiction_domain_routes:
                raise ValueError(
                    "jurisdiction assertion must name a retained authority route"
                )
            jurisdiction_assertions.add(assertion.jurisdiction_binding_id)
        elif isinstance(assertion, TechnologyBindingAssertion):
            expected_technology = scope_technologies.get(
                assertion.technology_binding_id
            )
            if expected_technology != (
                assertion.technology_id,
                assertion.asset_class,
            ):
                raise ValueError(
                    "technology assertion must match the exact scoped/base technology"
                )
            authority = base_technology_by_key.get(assertion.base_config_key)
            if authority is None or (
                authority.technology_binding_id != assertion.technology_binding_id
                or authority.technology_id != assertion.technology_id
                or authority.asset_class is not assertion.asset_class
                or authority.authored_technology_kind
                is not assertion.authored_technology_kind
            ):
                raise ValueError(
                    "technology assertion must name its exact base technology authority"
                )
            if (
                BaseConfigDomain.TECHNOLOGY_RESOURCE,
                assertion.technology_binding_id,
            ) not in technology_domain_routes:
                raise ValueError(
                    "technology assertion requires a retained technology-resource "
                    "authority route"
                )
            technology_assertions.add(assertion.technology_binding_id)
        elif isinstance(assertion, GenerationCapacityAssertion):
            if assertion.base_config_key is not None:
                required_domain = BaseConfigDomain.TECHNOLOGY_RESOURCE
            else:
                required_domain = BaseConfigDomain.PROJECT_RESOURCE
            if required_domain not in retained_domains:
                raise ValueError(
                    "generation capacity assertion requires its retained authored "
                    "resource domain"
                )
        elif isinstance(assertion, StorageCapacityAssertion):
            if BaseConfigDomain.TECHNOLOGY_RESOURCE not in retained_domains:
                raise ValueError(
                    "storage capacity assertion requires retained authored "
                    "technology resources"
                )
        elif isinstance(assertion, CostCompatibilityAssertion):
            required_domain = {
                ProjectCaseMaterialCategory.CAPEX: BaseConfigDomain.CAPEX,
                ProjectCaseMaterialCategory.OPEX: BaseConfigDomain.OPEX,
            }[assertion.category]
            if required_domain not in retained_domains:
                raise ValueError(
                    "cost assertion requires its retained authored cost domain"
                )
            if (
                assertion.price_basis_id != request.scope.price_basis_id
                or assertion.reporting_currency != request.scope.reporting_currency
            ):
                raise ValueError(
                    "cost assertions must match scope price basis and reporting currency"
                )
        elif isinstance(assertion, PriceBasisAssertion):
            if (
                assertion.price_basis_id != request.scope.price_basis_id
                or assertion.valuation_date != request.scope.valuation_date
                or assertion.reporting_currency != request.scope.reporting_currency
                or assertion.nominality is not request.scope.price_nominality
            ):
                raise ValueError(
                    "price-basis assertion must match every corresponding scope axis"
                )

    if jurisdiction_assertions != set(scope_subjects):
        raise ValueError(
            "compatibility assertions must cover every scoped jurisdiction subject"
        )
    if technology_assertions != set(scope_technologies):
        raise ValueError(
            "compatibility assertions must cover every scoped technology binding"
        )


def _json_pointer_child(pointer: str, segment: str) -> str:
    """Append one RFC 6901-escaped segment to an internal JSON pointer."""
    escaped = segment.replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}"


def _display_json_pointer(pointer: str) -> str:
    """Display the empty root pointer as ``/`` in validation errors."""
    return pointer or "/"


def resolved_config_sha256(config: dict[str, object]) -> str:
    """Hash one finite JSON-native resolved config with the public v14 primitive.

    The engine's :func:`analytics.run_manifest.config_sha256` intentionally uses
    ``default=str`` for historical callers.  D3B must not let that fallback turn a
    Decimal, path, custom object, non-string key, NaN, infinity, tuple, or cyclic
    container into an apparently governed digest.  This guard first proves the
    loaded tree is composed only of exact JSON-native dictionaries, lists, and
    finite scalar values. Repeated container identities, excessive depth, node
    counts, text volume, and integer magnitude fail closed before JSON encoding.
    Accepted input then delegates the hash bytes to the existing public v14
    function so the binding receipt and engine manifest use one algorithm.

    Args:
        config: Resolved authored scenario mapping.

    Returns:
        Lowercase SHA-256 hex using ``analytics.run_manifest.config_sha256``.

    Raises:
        TypeError: If the tree contains a non-JSON-native value or key.
        ValueError: If the tree is non-finite, aliased, cyclic, outside the
            declared resource domain, or cannot be encoded deterministically.
    """
    if type(config) is not dict:
        raise TypeError("resolved config path / root must be an exact dictionary")

    stack: list[tuple[object, int, str]] = [(config, 0, "")]
    seen_container_paths: dict[int, str] = {}
    container_count = 0
    scalar_count = 0
    text_codepoints = 0
    while stack:
        value, depth, pointer = stack.pop()
        display_pointer = _display_json_pointer(pointer)
        if type(value) is dict:
            identity = id(value)
            if identity in seen_container_paths:
                raise ValueError(
                    "resolved config must be a tree without shared or cyclic containers; "
                    f"path {display_pointer} repeats container first seen at "
                    f"{seen_container_paths[identity]}"
                )
            seen_container_paths[identity] = display_pointer
            container_count += 1
            if container_count > _MAX_RESOLVED_CONFIG_CONTAINERS:
                raise ValueError(
                    "resolved config exceeds the container-count limit at path "
                    f"{display_pointer}"
                )
            if depth > _MAX_RESOLVED_CONFIG_DEPTH:
                raise ValueError(
                    "resolved config exceeds the nesting-depth limit at path "
                    f"{display_pointer}"
                )
            mapping = cast(dict[object, object], value)
            if any(type(key) is not str for key in mapping):
                raise TypeError(
                    "resolved config dictionary keys must be exact strings at path "
                    f"{display_pointer}"
                )
            exact_mapping = cast(dict[str, object], mapping)
            keys = sorted(exact_mapping)
            text_codepoints += sum(len(key) for key in keys)
            if text_codepoints > _MAX_RESOLVED_CONFIG_TEXT_CODEPOINTS:
                raise ValueError(
                    "resolved config exceeds the text-size limit at path "
                    f"{display_pointer}"
                )
            for key in reversed(keys):
                stack.append(
                    (
                        exact_mapping[key],
                        depth + 1,
                        _json_pointer_child(pointer, key),
                    )
                )
            continue
        if type(value) is list:
            identity = id(value)
            if identity in seen_container_paths:
                raise ValueError(
                    "resolved config must be a tree without shared or cyclic containers; "
                    f"path {display_pointer} repeats container first seen at "
                    f"{seen_container_paths[identity]}"
                )
            seen_container_paths[identity] = display_pointer
            container_count += 1
            if container_count > _MAX_RESOLVED_CONFIG_CONTAINERS:
                raise ValueError(
                    "resolved config exceeds the container-count limit at path "
                    f"{display_pointer}"
                )
            if depth > _MAX_RESOLVED_CONFIG_DEPTH:
                raise ValueError(
                    "resolved config exceeds the nesting-depth limit at path "
                    f"{display_pointer}"
                )
            sequence = cast(list[object], value)
            for index in range(len(sequence) - 1, -1, -1):
                stack.append(
                    (
                        sequence[index],
                        depth + 1,
                        _json_pointer_child(pointer, str(index)),
                    )
                )
            continue
        scalar_count += 1
        if scalar_count > _MAX_RESOLVED_CONFIG_SCALARS:
            raise ValueError(
                "resolved config exceeds the scalar-count limit at path "
                f"{display_pointer}"
            )
        if value is None:
            text_codepoints += 4
        elif type(value) is bool:
            text_codepoints += 4 if value else 5
        elif type(value) is str:
            text_codepoints += len(value)
        elif type(value) is int:
            if value.bit_length() > _MAX_RESOLVED_CONFIG_INTEGER_BITS:
                raise ValueError(
                    "resolved config integer exceeds the magnitude limit at path "
                    f"{display_pointer}"
                )
            text_codepoints += len(str(value))
        elif type(value) is float:
            if not math.isfinite(value):
                raise ValueError(
                    f"resolved config floats must be finite at path {display_pointer}"
                )
            text_codepoints += len(repr(value))
        else:
            raise TypeError(
                "resolved config requires JSON-native dict/list/scalar values at path "
                f"{display_pointer}; got {type(value).__name__}"
            )
        if text_codepoints > _MAX_RESOLVED_CONFIG_TEXT_CODEPOINTS:
            raise ValueError(
                f"resolved config exceeds the text-size limit at path {display_pointer}"
            )

    from analytics.run_manifest import config_sha256

    try:
        return config_sha256(config)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ValueError(
            "resolved config could not be encoded deterministically at path /"
        ) from exc


__all__ = [
    "ASSESSMENT_SCOPE_CONTRACT_VERSION",
    "ASSESSMENT_SCOPE_SCHEMA_ID",
    "AUTHORED_SCENARIO_VALIDATION_CONTRACT_VERSION",
    "AUTHORED_SCENARIO_VALIDATION_SCHEMA_ID",
    "BASE_SCENARIO_IDENTITY_CONTRACT_VERSION",
    "BASE_SCENARIO_IDENTITY_SCHEMA_ID",
    "EVALUATION_REQUEST_CONTRACT_VERSION",
    "EVALUATION_REQUEST_SCHEMA_ID",
    "V14_BINDING_POLICY_CONTRACT_VERSION",
    "V14_BINDING_POLICY_SCHEMA_ID",
    "AssessmentCurrencyCode",
    "AssessmentExclusion",
    "AssessmentJurisdictionCode",
    "AssessmentScope",
    "AssessmentText",
    "AudienceIntent",
    "AuthoredTechnologyKind",
    "AuthoredScenarioValidationReceipt",
    "BaseConfigDomain",
    "BaseDomainAuthorityRoute",
    "BaseDomainDisposition",
    "BaseDomainDispositionKind",
    "BaseScenarioIdentity",
    "BaseSubjectAuthority",
    "BaseTechnologyAuthority",
    "BindingUnitToken",
    "CompatibilityAssertion",
    "CostAssertionPeriodicity",
    "CostCompatibilityAssertion",
    "EvaluationRequest",
    "GenerationCapacityAssertion",
    "GenerationCapacitySourceField",
    "IntendedDecision",
    "JurisdictionSubjectAssertion",
    "LocationAssertion",
    "LocationSourceField",
    "MaterialDispositionKind",
    "MaterialDispositionAction",
    "MaterialityRule",
    "PriceBasisAssertion",
    "ProjectCaseMaterialCategory",
    "ProjectCaseMaterialDisposition",
    "ProjectCaseReference",
    "RunModeBindingPolicy",
    "ScenarioIdentityAssertion",
    "ScopedJurisdictionSubject",
    "ScopedTechnology",
    "StorageCapacityAssertion",
    "StorageCapacitySourceField",
    "TechnologyBindingAssertion",
    "UseIntent",
    "V14BindingPolicy",
    "V14CostSelector",
    "V14GenerationCapacitySelector",
    "V14LocationSelector",
    "V14StorageCapacitySelector",
    "ValidationModule",
    "resolved_config_sha256",
]
