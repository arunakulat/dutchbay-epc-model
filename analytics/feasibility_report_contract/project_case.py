"""Pure global ProjectCase v1 input contract.

The contract is an additive, immutable domain boundary for later orchestration and
delivery adapters.  It models project identity, jurisdiction and technology support,
asset-instance topology, cost inputs, and material-value provenance without importing
finance, evaluation, application, API, persistence, or rendering code.

``contract_supported`` and ``contract_reviewed`` describe only whether a versioned
input contract is available and has received contract-scope review.  They are not
engineering assurance, statutory approval, report grade, lender acceptance, package
release, or permission to lift any ``HOLD``.
"""

from __future__ import annotations

import math
from datetime import date
from enum import Enum
from typing import Annotated, Iterable, Literal, Union

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from .vocabulary import (
    CurrencyCode,
    JurisdictionCode,
    NonEmptyText,
    SemanticVersion,
    StrictFrozenModel,
    UnitToken,
)

PROJECT_CASE_SCHEMA_ID: Literal["dutchbay.project_case.v1"] = "dutchbay.project_case.v1"
PROJECT_CASE_CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"

StableIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    ),
]
FiniteNumber = Annotated[float, Field(allow_inf_nan=False)]

_RECONCILIATION_REL_TOL = 1e-9
_RECONCILIATION_ABS_TOL = 1e-9


class ContractSupportStatus(str, Enum):
    """Availability of a versioned input contract, not project assurance."""

    UNSUPPORTED = "unsupported"
    CONTRACT_SUPPORTED = "contract_supported"
    CONTRACT_REVIEWED = "contract_reviewed"


class JurisdictionSubject(str, Enum):
    """Project subject governed by an explicit jurisdiction binding."""

    SITE = "site"
    CORPORATE = "corporate"
    CONTRACT = "contract"
    GRID = "grid"
    PERMIT = "permit"
    TAX = "tax"
    ACCOUNTING = "accounting"
    FINANCING = "financing"
    SUPPLY = "supply"


class TechnologyAssetClass(str, Enum):
    """Physical asset class supported by one technology binding."""

    GENERATION = "generation"
    STORAGE = "storage"


class TopologyKind(str, Enum):
    """Declared physical composition of the project case."""

    SINGLE_TECHNOLOGY = "single_technology"
    HYBRID = "hybrid"
    STORAGE_ONLY = "storage_only"


class AssetLinkKind(str, Enum):
    """Supported directed relationship between project asset instances."""

    CONNECTED_TO = "connected_to"
    USES_SHARED_INFRASTRUCTURE = "uses_shared_infrastructure"
    CHARGES_FROM = "charges_from"


class CostPeriodicity(str, Enum):
    """Time basis of an itemized cost line."""

    ONE_TIME = "one_time"
    ANNUAL = "annual"
    MONTHLY = "monthly"
    PER_EVENT = "per_event"


class PriceNominality(str, Enum):
    """Whether a price basis is nominal or real."""

    NOMINAL = "nominal"
    REAL = "real"


class CostReconciliationStatus(str, Enum):
    """Whether itemized cost arithmetic is complete or input-blocked."""

    COMPLETE = "complete"
    INCOMPLETE_MISSING_INPUT = "incomplete_missing_input"


class BoundaryStatus(str, Enum):
    """Evidence status of the declared physical boundary."""

    INDICATIVE = "indicative"
    CONTRACTUAL = "contractual"
    SURVEYED = "surveyed"


class CaseSource(StrictFrozenModel):
    """Minimal source identity referenced by ProjectCase material values."""

    source_id: StableIdentifier
    title: NonEmptyText
    locator: NonEmptyText
    jurisdiction_codes: tuple[JurisdictionCode, ...] = ()
    technology_ids: tuple[StableIdentifier, ...] = ()

    @model_validator(mode="after")
    def _scope_is_explicit(self) -> CaseSource:
        _require_nonempty_unique(self.jurisdiction_codes, "source jurisdiction_codes")
        _require_unique_ids(self.technology_ids, "source technology_id")
        return self


class CaseAssumption(StrictFrozenModel):
    """Explicit assumption used where direct source evidence is insufficient."""

    assumption_id: StableIdentifier
    statement: NonEmptyText
    basis: NonEmptyText
    replacement_action: NonEmptyText
    jurisdiction_codes: tuple[JurisdictionCode, ...] = ()
    technology_ids: tuple[StableIdentifier, ...] = ()

    @model_validator(mode="after")
    def _scope_is_explicit(self) -> CaseAssumption:
        _require_nonempty_unique(
            self.jurisdiction_codes, "assumption jurisdiction_codes"
        )
        _require_unique_ids(self.technology_ids, "assumption technology_id")
        return self


class MissingInputRecord(StrictFrozenModel):
    """Declared missing input with consequence and remedy."""

    missing_input_id: StableIdentifier
    field_path: NonEmptyText
    expected_unit: UnitToken
    reason: NonEmptyText
    consequence: NonEmptyText
    remedy: NonEmptyText


class SourceReference(StrictFrozenModel):
    """Reference from a resolved material value to a case source."""

    kind: Literal["source"] = "source"
    reference_id: StableIdentifier


class AssumptionReference(StrictFrozenModel):
    """Reference from a resolved material value to a declared assumption."""

    kind: Literal["assumption"] = "assumption"
    reference_id: StableIdentifier


ValueBinding = Annotated[
    Union[SourceReference, AssumptionReference], Field(discriminator="kind")
]


class ResolvedValue(StrictFrozenModel):
    """Finite material value with an explicit unit and provenance binding."""

    state: Literal["resolved"] = "resolved"
    value: FiniteNumber
    unit: UnitToken
    bindings: tuple[ValueBinding, ...]

    @model_validator(mode="after")
    def _requires_bindings(self) -> ResolvedValue:
        if not self.bindings:
            raise ValueError(
                "resolved material value requires source/assumption binding"
            )
        if len({(item.kind, item.reference_id) for item in self.bindings}) != len(
            self.bindings
        ):
            raise ValueError("resolved material value has duplicate bindings")
        return self


class ResolvedCount(StrictFrozenModel):
    """Positive integral count with an explicit provenance binding."""

    state: Literal["resolved"] = "resolved"
    value: PositiveInt
    unit: Literal["count"] = "count"
    bindings: tuple[ValueBinding, ...]

    @model_validator(mode="after")
    def _requires_bindings(self) -> ResolvedCount:
        if not self.bindings:
            raise ValueError(
                "resolved material count requires source/assumption binding"
            )
        if len({(item.kind, item.reference_id) for item in self.bindings}) != len(
            self.bindings
        ):
            raise ValueError("resolved material count has duplicate bindings")
        return self


class MissingValue(StrictFrozenModel):
    """Explicitly absent material value bound to one missing-input record."""

    state: Literal["missing"] = "missing"
    unit: UnitToken
    missing_input_id: StableIdentifier


MaterialValue = Annotated[
    Union[ResolvedValue, MissingValue], Field(discriminator="state")
]
MaterialCount = Annotated[
    Union[ResolvedCount, MissingValue], Field(discriminator="state")
]
AnyMaterialValue = Union[ResolvedValue, ResolvedCount, MissingValue]


class ProjectIdentity(StrictFrozenModel):
    """Stable project and case identity independent of report or run identity."""

    project_id: StableIdentifier
    case_id: StableIdentifier
    case_name: NonEmptyText
    revision: PositiveInt

    @model_validator(mode="after")
    def _identity_axes_are_distinct(self) -> ProjectIdentity:
        if self.project_id == self.case_id:
            raise ValueError("project_id and case_id must be distinct")
        return self


class JurisdictionBinding(StrictFrozenModel):
    """Bind one governed subject to one versioned jurisdiction contract pack."""

    binding_id: StableIdentifier
    jurisdiction_code: JurisdictionCode
    subject: JurisdictionSubject
    support_status: ContractSupportStatus
    contract_pack_id: StableIdentifier
    contract_pack_version: SemanticVersion


class TechnologyBinding(StrictFrozenModel):
    """Bind an open technology identifier to a versioned asset-class contract."""

    binding_id: StableIdentifier
    technology_id: StableIdentifier
    asset_class: TechnologyAssetClass
    support_status: ContractSupportStatus
    contract_pack_id: StableIdentifier
    contract_pack_version: SemanticVersion


class ProjectLocation(StrictFrozenModel):
    """Explicit project location, site jurisdiction, coordinates, and boundary."""

    site_name: NonEmptyText
    description: NonEmptyText
    site_jurisdiction_code: JurisdictionCode
    site_jurisdiction_binding_id: StableIdentifier
    latitude_degrees: ResolvedValue
    longitude_degrees: ResolvedValue
    boundary_id: StableIdentifier
    boundary_status: BoundaryStatus
    boundary_binding: ValueBinding

    @model_validator(mode="after")
    def _coordinates_are_valid(self) -> ProjectLocation:
        if self.latitude_degrees.unit != "degree" or not (
            -90 <= self.latitude_degrees.value <= 90
        ):
            raise ValueError(
                "latitude_degrees requires degree unit and range [-90, 90]"
            )
        if self.longitude_degrees.unit != "degree" or not (
            -180 <= self.longitude_degrees.value <= 180
        ):
            raise ValueError(
                "longitude_degrees requires degree unit and range [-180, 180]"
            )
        return self


class AggregateGenerationCapacity(StrictFrozenModel):
    """Aggregate capacity for a non-unitized generation asset."""

    kind: Literal["aggregate"] = "aggregate"
    total_capacity_mw: MaterialValue

    @model_validator(mode="after")
    def _capacity_is_positive_mw(self) -> AggregateGenerationCapacity:
        _require_positive_material_unit(
            self.total_capacity_mw, "MW", "total_capacity_mw"
        )
        return self


class UnitizedGenerationCapacity(StrictFrozenModel):
    """Unit count/rating and reconciled aggregate generation capacity."""

    kind: Literal["unitized"] = "unitized"
    unit_count: MaterialCount
    unit_capacity_mw: MaterialValue
    total_capacity_mw: MaterialValue

    @model_validator(mode="after")
    def _unit_capacity_reconciles(self) -> UnitizedGenerationCapacity:
        _require_positive_material_unit(self.unit_capacity_mw, "MW", "unit_capacity_mw")
        _require_positive_material_unit(
            self.total_capacity_mw, "MW", "total_capacity_mw"
        )
        if isinstance(self.unit_count, MissingValue):
            if self.unit_count.unit != "count":
                raise ValueError("unit_count requires unit count")
            return self
        if isinstance(self.unit_capacity_mw, MissingValue) or isinstance(
            self.total_capacity_mw, MissingValue
        ):
            return self
        expected = self.unit_count.value * self.unit_capacity_mw.value
        if not _close(self.total_capacity_mw.value, expected):
            raise ValueError(
                "total_capacity_mw must equal unit_count * unit_capacity_mw"
            )
        return self


GenerationCapacity = Annotated[
    Union[AggregateGenerationCapacity, UnitizedGenerationCapacity],
    Field(discriminator="kind"),
]


class GenerationAsset(StrictFrozenModel):
    """One stable generating asset instance."""

    kind: Literal["generation"] = "generation"
    asset_id: StableIdentifier
    name: NonEmptyText
    technology_id: StableIdentifier
    technology_binding_id: StableIdentifier
    jurisdiction_codes: tuple[JurisdictionCode, ...]
    capacity: GenerationCapacity

    @model_validator(mode="after")
    def _has_jurisdiction(self) -> GenerationAsset:
        _require_nonempty_unique(
            self.jurisdiction_codes, "generation jurisdiction_codes"
        )
        return self


class StorageAsset(StrictFrozenModel):
    """One storage asset with mutually consistent power, energy, and duration."""

    kind: Literal["storage"] = "storage"
    asset_id: StableIdentifier
    name: NonEmptyText
    technology_id: StableIdentifier
    technology_binding_id: StableIdentifier
    jurisdiction_codes: tuple[JurisdictionCode, ...]
    power_mw: MaterialValue
    energy_mwh: MaterialValue
    duration_hours: MaterialValue

    @model_validator(mode="after")
    def _storage_capacity_reconciles(self) -> StorageAsset:
        _require_nonempty_unique(self.jurisdiction_codes, "storage jurisdiction_codes")
        _require_positive_material_unit(self.power_mw, "MW", "power_mw")
        _require_positive_material_unit(self.energy_mwh, "MWh", "energy_mwh")
        _require_positive_material_unit(self.duration_hours, "hour", "duration_hours")
        if any(
            isinstance(item, MissingValue)
            for item in (self.power_mw, self.energy_mwh, self.duration_hours)
        ):
            return self
        assert isinstance(self.power_mw, ResolvedValue)
        assert isinstance(self.energy_mwh, ResolvedValue)
        assert isinstance(self.duration_hours, ResolvedValue)
        if not _close(
            self.energy_mwh.value, self.power_mw.value * self.duration_hours.value
        ):
            raise ValueError("energy_mwh must equal power_mw * duration_hours")
        return self


class SharedInfrastructureAsset(StrictFrozenModel):
    """One shared physical asset used by generation or storage instances."""

    kind: Literal["shared_infrastructure"] = "shared_infrastructure"
    asset_id: StableIdentifier
    name: NonEmptyText
    infrastructure_type: StableIdentifier
    jurisdiction_codes: tuple[JurisdictionCode, ...]
    capacity: MaterialValue

    @model_validator(mode="after")
    def _has_jurisdiction(self) -> SharedInfrastructureAsset:
        _require_nonempty_unique(
            self.jurisdiction_codes, "shared infrastructure jurisdiction_codes"
        )
        _require_positive_material(self.capacity, "shared infrastructure capacity")
        return self


ProjectAsset = Annotated[
    Union[GenerationAsset, StorageAsset, SharedInfrastructureAsset],
    Field(discriminator="kind"),
]


class AssetLink(StrictFrozenModel):
    """One directed physical relationship between stable asset instances."""

    link_id: StableIdentifier
    kind: AssetLinkKind
    from_asset_id: StableIdentifier
    to_asset_id: StableIdentifier

    @model_validator(mode="after")
    def _does_not_self_link(self) -> AssetLink:
        if self.from_asset_id == self.to_asset_id:
            raise ValueError("asset link cannot reference the same asset twice")
        return self


class ProjectTopology(StrictFrozenModel):
    """Declared project composition and explicit asset-instance links."""

    topology_id: StableIdentifier
    kind: TopologyKind
    shared_interconnection_asset_id: StableIdentifier | None
    links: tuple[AssetLink, ...]


class PriceBasis(StrictFrozenModel):
    """Valuation basis shared by one or more itemized cost lines."""

    price_basis_id: StableIdentifier
    valuation_date: date
    price_level: NonEmptyText
    nominality: PriceNominality
    reporting_currency: CurrencyCode


class CurrencyConversion(StrictFrozenModel):
    """Explicit native-to-reporting currency conversion for cost normalization."""

    conversion_id: StableIdentifier
    from_currency: CurrencyCode
    to_currency: CurrencyCode
    rate: MaterialValue
    valuation_date: date
    price_basis_id: StableIdentifier

    @model_validator(mode="after")
    def _conversion_is_well_formed(self) -> CurrencyConversion:
        if self.from_currency == self.to_currency:
            raise ValueError("currency conversion requires different currencies")
        _require_positive_material_unit(
            self.rate,
            f"{self.to_currency}/{self.from_currency}",
            "currency conversion rate",
        )
        return self


class MonetaryAmount(StrictFrozenModel):
    """Native and normalized reporting amounts with an explicit conversion edge."""

    native_amount: MaterialValue
    native_currency: CurrencyCode
    reporting_amount: MaterialValue
    reporting_currency: CurrencyCode
    conversion_id: StableIdentifier | None = None

    @model_validator(mode="after")
    def _currencies_and_units_are_explicit(self) -> MonetaryAmount:
        _require_nonnegative_material_unit(
            self.native_amount, self.native_currency, "native_amount"
        )
        _require_nonnegative_material_unit(
            self.reporting_amount, self.reporting_currency, "reporting_amount"
        )
        if self.native_currency == self.reporting_currency:
            if self.conversion_id is not None:
                raise ValueError("same-currency amount must not name a conversion")
            if (
                isinstance(self.native_amount, ResolvedValue)
                and isinstance(self.reporting_amount, ResolvedValue)
                and not _close(self.native_amount.value, self.reporting_amount.value)
            ):
                raise ValueError("same-currency native/reporting amounts must match")
        elif self.conversion_id is None:
            raise ValueError("mixed-currency amount requires conversion_id")
        return self


class _CostLineBase(StrictFrozenModel):
    """Common strictly itemized cost fields."""

    line_id: StableIdentifier
    description: NonEmptyText
    quantity: MaterialValue
    unit_rate_native: MaterialValue
    amount: MonetaryAmount
    price_basis_id: StableIdentifier
    allocation_ids: tuple[StableIdentifier, ...]

    @model_validator(mode="after")
    def _quantity_rate_and_amount_reconcile(self) -> _CostLineBase:
        _require_positive_material(self.quantity, "quantity")
        expected_rate_unit = f"{self.amount.native_currency}/{self.quantity.unit}"
        _require_nonnegative_material_unit(
            self.unit_rate_native, expected_rate_unit, "unit_rate_native"
        )
        if (
            isinstance(self.amount.native_amount, ResolvedValue)
            and isinstance(self.quantity, ResolvedValue)
            and isinstance(self.unit_rate_native, ResolvedValue)
            and not _close(
                self.amount.native_amount.value,
                self.quantity.value * self.unit_rate_native.value,
            )
        ):
            raise ValueError("native amount must equal quantity * unit_rate_native")
        _require_nonempty_unique(self.allocation_ids, "cost allocation_ids")
        return self


class CapexCostLine(_CostLineBase):
    """One itemized capital-cost line."""

    cost_kind: Literal["capex"] = "capex"
    periodicity: Literal[CostPeriodicity.ONE_TIME] = CostPeriodicity.ONE_TIME


class OpexCostLine(_CostLineBase):
    """One itemized operating-cost line."""

    cost_kind: Literal["opex"] = "opex"
    periodicity: CostPeriodicity

    @model_validator(mode="after")
    def _opex_is_recurring(self) -> OpexCostLine:
        if self.periodicity is CostPeriodicity.ONE_TIME:
            raise ValueError("opex periodicity cannot be one_time")
        return self


CostLine = Annotated[
    Union[CapexCostLine, OpexCostLine], Field(discriminator="cost_kind")
]


class CostAllocation(StrictFrozenModel):
    """Allocate one cost line to one stable project asset instance."""

    allocation_id: StableIdentifier
    cost_line_id: StableIdentifier
    asset_id: StableIdentifier
    share: MaterialValue

    @model_validator(mode="after")
    def _share_is_fraction(self) -> CostAllocation:
        if self.share.unit != "fraction":
            raise ValueError("allocation share requires fraction unit")
        if isinstance(self.share, ResolvedValue) and not 0 < self.share.value <= 1:
            raise ValueError("allocation share requires fraction unit and range (0, 1]")
        return self


class CostSchedule(StrictFrozenModel):
    """Itemized CAPEX/OPEX, price bases, conversions, and allocations."""

    reporting_currency: CurrencyCode
    reconciliation_status: CostReconciliationStatus
    price_bases: tuple[PriceBasis, ...]
    currency_conversions: tuple[CurrencyConversion, ...] = ()
    lines: tuple[CostLine, ...]
    allocations: tuple[CostAllocation, ...]

    @model_validator(mode="after")
    def _schedule_reconciles(self) -> CostSchedule:
        _require_unique_ids(
            (item.price_basis_id for item in self.price_bases), "price_basis_id"
        )
        _require_unique_ids(
            (item.conversion_id for item in self.currency_conversions), "conversion_id"
        )
        _require_unique_ids((item.line_id for item in self.lines), "cost line_id")
        _require_unique_ids(
            (item.allocation_id for item in self.allocations), "allocation_id"
        )
        if not any(isinstance(item, CapexCostLine) for item in self.lines):
            raise ValueError("cost schedule requires at least one capex line")
        if not any(isinstance(item, OpexCostLine) for item in self.lines):
            raise ValueError("cost schedule requires at least one opex line")

        bases = {item.price_basis_id: item for item in self.price_bases}
        conversions = {item.conversion_id: item for item in self.currency_conversions}
        allocations = {item.allocation_id: item for item in self.allocations}
        used_bases: set[str] = set()
        used_conversions: set[str] = set()
        for line in self.lines:
            basis = bases.get(line.price_basis_id)
            if basis is None:
                raise ValueError(
                    f"cost line {line.line_id} has dangling price_basis_id"
                )
            used_bases.add(basis.price_basis_id)
            if basis.reporting_currency != self.reporting_currency:
                raise ValueError(
                    "price basis reporting currency does not match schedule"
                )
            if line.amount.reporting_currency != self.reporting_currency:
                raise ValueError("cost line reporting currency does not match schedule")
            selected = tuple(allocations.get(item) for item in line.allocation_ids)
            if any(item is None for item in selected):
                raise ValueError(f"cost line {line.line_id} has dangling allocation_id")
            typed_selected = tuple(item for item in selected if item is not None)
            if any(item.cost_line_id != line.line_id for item in typed_selected):
                raise ValueError("cost line/allocation reciprocal binding is broken")
            resolved_shares = tuple(
                item.share
                for item in typed_selected
                if isinstance(item.share, ResolvedValue)
            )
            if len(resolved_shares) == len(typed_selected) and not _close(
                sum(item.value for item in resolved_shares), 1.0
            ):
                raise ValueError(f"cost line {line.line_id} allocations must sum to 1")

            conversion_id = line.amount.conversion_id
            if conversion_id is not None:
                conversion = conversions.get(conversion_id)
                if conversion is None:
                    raise ValueError(
                        f"cost line {line.line_id} has dangling conversion_id"
                    )
                used_conversions.add(conversion_id)
                if (
                    conversion.from_currency != line.amount.native_currency
                    or conversion.to_currency != self.reporting_currency
                    or conversion.price_basis_id != line.price_basis_id
                    or conversion.valuation_date != basis.valuation_date
                ):
                    raise ValueError("cost line conversion scope/basis mismatch")
                if (
                    isinstance(line.amount.native_amount, ResolvedValue)
                    and isinstance(line.amount.reporting_amount, ResolvedValue)
                    and isinstance(conversion.rate, ResolvedValue)
                    and not _close(
                        line.amount.reporting_amount.value,
                        line.amount.native_amount.value * conversion.rate.value,
                    )
                ):
                    raise ValueError("cost line reporting amount does not reconcile")

        allocation_ids = {
            allocation_id
            for line in self.lines
            for allocation_id in line.allocation_ids
        }
        if allocation_ids != set(allocations):
            raise ValueError("cost allocation register has unreferenced records")
        if used_bases != set(bases):
            raise ValueError("price basis register has unreferenced records")
        if used_conversions != set(conversions):
            raise ValueError("currency conversion register has unreferenced records")
        has_missing = any(
            isinstance(value, MissingValue) for _, value in _walk_material_values(self)
        )
        expected_status = (
            CostReconciliationStatus.INCOMPLETE_MISSING_INPUT
            if has_missing
            else CostReconciliationStatus.COMPLETE
        )
        if self.reconciliation_status is not expected_status:
            raise ValueError(
                "cost reconciliation_status must reflect explicit missing inputs"
            )
        return self


class ProjectCase(StrictFrozenModel):
    """Global, immutable ProjectCase v1 domain contract.

    The object is suitable for later JSON, form, or API adapters but owns no transport,
    persistence, calculation, report-grade, review, or release policy.
    """

    schema_id: Literal["dutchbay.project_case.v1"] = PROJECT_CASE_SCHEMA_ID
    contract_version: Literal["1.0.0"] = PROJECT_CASE_CONTRACT_VERSION
    identity: ProjectIdentity
    location: ProjectLocation
    jurisdiction_bindings: tuple[JurisdictionBinding, ...]
    technology_bindings: tuple[TechnologyBinding, ...]
    assets: tuple[ProjectAsset, ...]
    topology: ProjectTopology
    costs: CostSchedule
    sources: tuple[CaseSource, ...]
    assumptions: tuple[CaseAssumption, ...] = ()
    missing_inputs: tuple[MissingInputRecord, ...] = ()

    @model_validator(mode="after")
    def _project_case_is_closed_and_explicit(self) -> ProjectCase:
        self._validate_identity_and_support_bindings()
        self._validate_assets_and_topology()
        self._validate_cost_asset_bindings()
        self._validate_material_value_bindings()
        return self

    def _validate_identity_and_support_bindings(self) -> None:
        _require_unique_ids(
            (item.binding_id for item in self.jurisdiction_bindings),
            "jurisdiction binding_id",
        )
        _require_unique_ids(
            (item.binding_id for item in self.technology_bindings),
            "technology binding_id",
        )
        jurisdiction_keys = [
            (item.jurisdiction_code, item.subject)
            for item in self.jurisdiction_bindings
        ]
        if len(set(jurisdiction_keys)) != len(jurisdiction_keys):
            raise ValueError("ambiguous duplicate jurisdiction subject binding")
        technology_keys = [
            (item.technology_id, item.asset_class) for item in self.technology_bindings
        ]
        if len(set(technology_keys)) != len(technology_keys):
            raise ValueError("ambiguous duplicate technology contract binding")
        has_unsupported_jurisdiction = any(
            item.support_status is ContractSupportStatus.UNSUPPORTED
            for item in self.jurisdiction_bindings
        )
        has_unsupported_technology = any(
            item.support_status is ContractSupportStatus.UNSUPPORTED
            for item in self.technology_bindings
        )
        if has_unsupported_jurisdiction or has_unsupported_technology:
            raise ValueError(
                "ProjectCase cannot bind unsupported jurisdiction/technology contracts"
            )

        jurisdictions = {item.binding_id: item for item in self.jurisdiction_bindings}
        site_binding = jurisdictions.get(self.location.site_jurisdiction_binding_id)
        if (
            site_binding is None
            or site_binding.jurisdiction_code != self.location.site_jurisdiction_code
            or site_binding.subject is not JurisdictionSubject.SITE
        ):
            raise ValueError(
                "location has missing, ambiguous, or unbound site jurisdiction"
            )

    def _validate_assets_and_topology(self) -> None:
        _require_unique_ids((item.asset_id for item in self.assets), "asset_id")
        _require_unique_ids((item.link_id for item in self.topology.links), "link_id")
        if not self.assets:
            raise ValueError("ProjectCase requires at least one asset instance")
        assets = {item.asset_id: item for item in self.assets}
        technology_bindings = {
            item.binding_id: item for item in self.technology_bindings
        }
        site_jurisdictions = {
            item.jurisdiction_code
            for item in self.jurisdiction_bindings
            if item.subject is JurisdictionSubject.SITE
        }
        used_technology_bindings: set[str] = set()
        active_technologies: set[str] = set()
        generation_assets = 0
        storage_assets = 0
        shared_assets: set[str] = set()
        for asset in self.assets:
            if not set(asset.jurisdiction_codes) <= site_jurisdictions:
                raise ValueError(
                    f"asset {asset.asset_id} has an unbound site jurisdiction"
                )
            if isinstance(asset, SharedInfrastructureAsset):
                shared_assets.add(asset.asset_id)
                continue
            binding = technology_bindings.get(asset.technology_binding_id)
            expected_class = (
                TechnologyAssetClass.GENERATION
                if isinstance(asset, GenerationAsset)
                else TechnologyAssetClass.STORAGE
            )
            if (
                binding is None
                or binding.technology_id != asset.technology_id
                or binding.asset_class is not expected_class
            ):
                raise ValueError(
                    f"asset {asset.asset_id} has unsupported or unbound technology"
                )
            used_technology_bindings.add(binding.binding_id)
            active_technologies.add(binding.technology_id)
            generation_assets += isinstance(asset, GenerationAsset)
            storage_assets += isinstance(asset, StorageAsset)
        if used_technology_bindings != set(technology_bindings):
            raise ValueError("technology binding register has unreferenced records")

        expected_topology = TopologyKind.HYBRID
        if generation_assets == 0 and storage_assets > 0:
            expected_topology = TopologyKind.STORAGE_ONLY
        elif storage_assets == 0 and len(active_technologies) == 1:
            expected_topology = TopologyKind.SINGLE_TECHNOLOGY
        if self.topology.kind is not expected_topology:
            raise ValueError("topology kind does not match asset composition")

        shared_interconnection = self.topology.shared_interconnection_asset_id
        if (
            shared_interconnection is not None
            and shared_interconnection not in shared_assets
        ):
            raise ValueError("shared_interconnection_asset_id must name a shared asset")
        if self.topology.kind is TopologyKind.HYBRID and shared_interconnection is None:
            raise ValueError("hybrid topology requires shared interconnection asset")

        used_shared_assets: set[str] = set()
        linked_nonshared_assets: set[str] = set()
        link_keys: set[tuple[AssetLinkKind, str, str]] = set()
        for link in self.topology.links:
            if link.from_asset_id not in assets or link.to_asset_id not in assets:
                raise ValueError(
                    f"asset link {link.link_id} has dangling asset reference"
                )
            key = (link.kind, link.from_asset_id, link.to_asset_id)
            if key in link_keys:
                raise ValueError("duplicate asset topology relationship")
            link_keys.add(key)
            source = assets[link.from_asset_id]
            target = assets[link.to_asset_id]
            if link.kind is AssetLinkKind.USES_SHARED_INFRASTRUCTURE:
                if isinstance(source, SharedInfrastructureAsset) or not isinstance(
                    target, SharedInfrastructureAsset
                ):
                    raise ValueError(
                        "uses_shared_infrastructure must point from technology asset to shared asset"
                    )
                used_shared_assets.add(target.asset_id)
                linked_nonshared_assets.add(source.asset_id)
            elif link.kind is AssetLinkKind.CHARGES_FROM:
                if not isinstance(source, StorageAsset) or isinstance(
                    target, StorageAsset
                ):
                    raise ValueError(
                        "charges_from must point from storage to generation/shared asset"
                    )
        if shared_assets != used_shared_assets:
            raise ValueError(
                "shared infrastructure has missing reciprocal topology use"
            )
        if self.topology.kind is TopologyKind.HYBRID:
            nonshared_assets = set(assets) - shared_assets
            if nonshared_assets != linked_nonshared_assets:
                raise ValueError(
                    "hybrid assets must explicitly use shared infrastructure"
                )

    def _validate_cost_asset_bindings(self) -> None:
        asset_ids = {item.asset_id for item in self.assets}
        for allocation in self.costs.allocations:
            if allocation.asset_id not in asset_ids:
                raise ValueError(
                    f"cost allocation {allocation.allocation_id} has dangling asset_id"
                )

    def _validate_material_value_bindings(self) -> None:
        _require_unique_ids((item.source_id for item in self.sources), "source_id")
        _require_unique_ids(
            (item.assumption_id for item in self.assumptions), "assumption_id"
        )
        _require_unique_ids(
            (item.missing_input_id for item in self.missing_inputs), "missing_input_id"
        )
        sources = {item.source_id: item for item in self.sources}
        assumptions = {item.assumption_id: item for item in self.assumptions}
        missing = {item.missing_input_id: item for item in self.missing_inputs}
        if set(sources) & set(assumptions) or (set(sources) | set(assumptions)) & set(
            missing
        ):
            raise ValueError(
                "source/assumption/missing-input IDs must be globally unique"
            )

        known_jurisdictions = {
            item.jurisdiction_code for item in self.jurisdiction_bindings
        }
        known_technologies = {item.technology_id for item in self.technology_bindings}
        for source in self.sources:
            if not set(source.jurisdiction_codes) <= known_jurisdictions:
                raise ValueError(
                    "source/assumption uses a jurisdiction outside ProjectCase bindings"
                )
            if not set(source.technology_ids) <= known_technologies:
                raise ValueError(
                    "source/assumption uses a technology outside ProjectCase bindings"
                )
        for assumption in self.assumptions:
            if not set(assumption.jurisdiction_codes) <= known_jurisdictions:
                raise ValueError(
                    "source/assumption uses a jurisdiction outside ProjectCase bindings"
                )
            if not set(assumption.technology_ids) <= known_technologies:
                raise ValueError(
                    "source/assumption uses a technology outside ProjectCase bindings"
                )

        used_sources: set[str] = set()
        used_assumptions: set[str] = set()
        used_missing: set[str] = set()
        for binding in (self.location.boundary_binding,):
            _resolve_binding(
                binding,
                sources,
                assumptions,
                used_sources,
                used_assumptions,
                required_jurisdictions={self.location.site_jurisdiction_code},
                required_technologies=set(),
                field_path="/location/boundary_binding",
            )
        for field_path, value in _walk_material_values(self):
            if isinstance(value, MissingValue):
                missing_record = missing.get(value.missing_input_id)
                if missing_record is None:
                    raise ValueError(
                        f"material value has dangling missing_input_id {value.missing_input_id}"
                    )
                if (
                    missing_record.field_path != field_path
                    or missing_record.expected_unit != value.unit
                ):
                    raise ValueError(
                        "missing input field_path/expected_unit does not match "
                        f"material value at {field_path}"
                    )
                used_missing.add(value.missing_input_id)
                continue
            required_jurisdictions, required_technologies = self._scope_for_field_path(
                field_path
            )
            for binding in value.bindings:
                _resolve_binding(
                    binding,
                    sources,
                    assumptions,
                    used_sources,
                    used_assumptions,
                    required_jurisdictions=required_jurisdictions,
                    required_technologies=required_technologies,
                    field_path=field_path,
                )
        if used_sources != set(sources):
            raise ValueError("source register has unreferenced records")
        if used_assumptions != set(assumptions):
            raise ValueError("assumption register has unreferenced records")
        if used_missing != set(missing):
            raise ValueError("missing-input register has unreferenced records")

    def _scope_for_field_path(self, field_path: str) -> tuple[set[str], set[str]]:
        """Return exact jurisdiction/technology scope for one material field path."""
        if field_path.startswith("/location/"):
            return {self.location.site_jurisdiction_code}, set()
        parts = field_path.split("/")
        if len(parts) > 2 and parts[1] == "assets":
            asset = self.assets[int(parts[2])]
            technologies = (
                set()
                if isinstance(asset, SharedInfrastructureAsset)
                else {asset.technology_id}
            )
            return set(asset.jurisdiction_codes), technologies
        if len(parts) > 3 and parts[1:3] == ["costs", "allocations"]:
            allocation = self.costs.allocations[int(parts[3])]
            asset = next(
                item for item in self.assets if item.asset_id == allocation.asset_id
            )
            technologies = (
                set()
                if isinstance(asset, SharedInfrastructureAsset)
                else {asset.technology_id}
            )
            return set(asset.jurisdiction_codes), technologies
        if len(parts) > 3 and parts[1:3] == ["costs", "lines"]:
            line = self.costs.lines[int(parts[3])]
            allocation_ids = set(line.allocation_ids)
            asset_ids = {
                item.asset_id
                for item in self.costs.allocations
                if item.allocation_id in allocation_ids
            }
            selected_assets = tuple(
                item for item in self.assets if item.asset_id in asset_ids
            )
            return (
                {
                    code
                    for asset in selected_assets
                    for code in asset.jurisdiction_codes
                },
                {
                    asset.technology_id
                    for asset in selected_assets
                    if not isinstance(asset, SharedInfrastructureAsset)
                },
            )
        return (
            {item.jurisdiction_code for item in self.jurisdiction_bindings},
            {item.technology_id for item in self.technology_bindings},
        )


def _close(left: float, right: float) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=_RECONCILIATION_REL_TOL,
        abs_tol=_RECONCILIATION_ABS_TOL,
    )


def _require_positive(value: ResolvedValue, field_name: str) -> None:
    if value.value <= 0:
        raise ValueError(f"{field_name} must be positive")


def _require_positive_material(value: MaterialValue, field_name: str) -> None:
    if isinstance(value, ResolvedValue):
        _require_positive(value, field_name)


def _require_positive_material_unit(
    value: MaterialValue, expected_unit: str, field_name: str
) -> None:
    if value.unit != expected_unit:
        raise ValueError(f"{field_name} requires unit {expected_unit}")
    _require_positive_material(value, field_name)


def _require_nonnegative_material_unit(
    value: MaterialValue, expected_unit: str, field_name: str
) -> None:
    if value.unit != expected_unit:
        raise ValueError(f"{field_name} requires unit {expected_unit}")
    if isinstance(value, ResolvedValue) and value.value < 0:
        raise ValueError(f"{field_name} cannot be negative")


def _require_nonempty_unique(values: Iterable[object], field_name: str) -> None:
    materialized = tuple(values)
    if not materialized:
        raise ValueError(f"{field_name} cannot be empty")
    if len(set(materialized)) != len(materialized):
        raise ValueError(f"{field_name} contains duplicates")


def _require_unique_ids(values: Iterable[str], field_name: str) -> None:
    materialized = tuple(values)
    if len(set(materialized)) != len(materialized):
        raise ValueError(f"duplicate {field_name}")


def _walk_material_values(
    value: object, path: tuple[str, ...] = ()
) -> Iterable[tuple[str, AnyMaterialValue]]:
    if isinstance(value, (ResolvedValue, ResolvedCount, MissingValue)):
        yield "/" + "/".join(path), value
        return
    if isinstance(value, StrictFrozenModel):
        for field_name in type(value).model_fields:
            yield from _walk_material_values(
                getattr(value, field_name), (*path, field_name)
            )
        return
    if isinstance(value, tuple):
        for index, item in enumerate(value):
            yield from _walk_material_values(item, (*path, str(index)))


def _resolve_binding(
    binding: ValueBinding,
    sources: dict[str, CaseSource],
    assumptions: dict[str, CaseAssumption],
    used_sources: set[str],
    used_assumptions: set[str],
    *,
    required_jurisdictions: set[str],
    required_technologies: set[str],
    field_path: str,
) -> None:
    if isinstance(binding, SourceReference):
        source_record = sources.get(binding.reference_id)
        if source_record is None:
            raise ValueError(
                f"material value has dangling source reference {binding.reference_id}"
            )
        if not required_jurisdictions <= set(source_record.jurisdiction_codes) or not (
            required_technologies <= set(source_record.technology_ids)
        ):
            raise ValueError(
                f"source {binding.reference_id} has wrong scope for {field_path}"
            )
        used_sources.add(binding.reference_id)
    else:
        assumption_record = assumptions.get(binding.reference_id)
        if assumption_record is None:
            raise ValueError(
                "material value has dangling assumption reference "
                f"{binding.reference_id}"
            )
        if not required_jurisdictions <= set(
            assumption_record.jurisdiction_codes
        ) or not (required_technologies <= set(assumption_record.technology_ids)):
            raise ValueError(
                f"assumption {binding.reference_id} has wrong scope for {field_path}"
            )
        used_assumptions.add(binding.reference_id)


__all__ = [
    "PROJECT_CASE_CONTRACT_VERSION",
    "PROJECT_CASE_SCHEMA_ID",
    "AggregateGenerationCapacity",
    "AssetLink",
    "AssetLinkKind",
    "AssumptionReference",
    "BoundaryStatus",
    "CapexCostLine",
    "CaseAssumption",
    "CaseSource",
    "ContractSupportStatus",
    "CostAllocation",
    "CostLine",
    "CostPeriodicity",
    "CostReconciliationStatus",
    "CostSchedule",
    "CurrencyConversion",
    "GenerationAsset",
    "GenerationCapacity",
    "JurisdictionBinding",
    "JurisdictionSubject",
    "MaterialCount",
    "MaterialValue",
    "MissingInputRecord",
    "MissingValue",
    "MonetaryAmount",
    "OpexCostLine",
    "PriceBasis",
    "PriceNominality",
    "ProjectAsset",
    "ProjectCase",
    "ProjectIdentity",
    "ProjectLocation",
    "ProjectTopology",
    "ResolvedCount",
    "ResolvedValue",
    "SharedInfrastructureAsset",
    "SourceReference",
    "StableIdentifier",
    "StorageAsset",
    "TechnologyAssetClass",
    "TechnologyBinding",
    "TopologyKind",
    "UnitizedGenerationCapacity",
    "ValueBinding",
]
