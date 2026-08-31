"""Held D3B-1 ProjectCase-to-v14 execution boundary.

This module reconciles one exact D3A ``ProjectCase`` and one accepted D3B-0
``EvaluationRequest`` against one hash-bound authored scenario before making the
sole public v14 gateway call.  It does not map or override ProjectCase economics,
infer evidence sufficiency, assemble a report, grade a result, or grant release.
"""

from __future__ import annotations

import hashlib
import math
import os
import stat
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, BinaryIO, cast

from analytics.contracts_v14 import (
    AuthoredScenarioPathAuthority,
    AuthoredScenarioPathBinding,
    D3BAuthoredNumericValue,
    D3BAuthorizedJurisdictionDomain,
    D3BAuthorizedTechnologyBinding,
    D3BExecutionFailure,
    D3BExecutionFailureRecord,
    D3BExecutionPhase,
    D3BExecutionResult,
    D3BExecutionSuccess,
    D3BFailureCode,
    D3BNumericProjectionReceipt,
)
from analytics.feasibility_report_contract import (
    BaseConfigDomain,
    BaseDomainDispositionKind,
    CostCompatibilityAssertion,
    EvaluationRequest,
    GenerationAsset,
    GenerationCapacityAssertion,
    GenerationCapacitySourceField,
    JurisdictionSubjectAssertion,
    LocationAssertion,
    LocationSourceField,
    MaterialDispositionKind,
    MissingValue,
    PriceBasisAssertion,
    ProjectCase,
    ProjectCaseMaterialCategory,
    ResolvedCount,
    ResolvedValue,
    ScenarioIdentityAssertion,
    StorageAsset,
    StorageCapacityAssertion,
    StorageCapacitySourceField,
    TechnologyBindingAssertion,
    UnitizedGenerationCapacity,
    V14CostSelector,
    V14GenerationCapacitySelector,
    V14StorageCapacitySelector,
    resolved_config_sha256,
)

_MISSING = object()
_AUTHORED_SCENARIO_AUTHORITIES: Mapping[str, AuthoredScenarioPathAuthority] = (
    MappingProxyType({})
)
_MAX_RESULT_DEPTH = 128
_MAX_RESULT_CONTAINERS = 10_000
_MAX_RESULT_SCALARS = 100_000
_MAX_RESULT_TEXT_CODEPOINTS = 1_000_000
_MAX_AUTHORED_SCENARIO_BYTES = 16 * 1024 * 1024


class _MissingMaterialValue(ValueError):
    """Internal signal that a compatibility-selected ProjectCase value is missing."""


def _failure(
    request_id: str | None,
    code: D3BFailureCode,
    phase: D3BExecutionPhase,
    *,
    gateway_call_count: int = 0,
    cause: BaseException | None = None,
) -> D3BExecutionFailure:
    """Build one bounded failure without serializing arbitrary cause text."""
    cause_type = type(cause).__name__ if cause is not None else None
    if cause_type is not None and (
        len(cause_type) > 160 or not cause_type.replace("_", "").isalnum()
    ):
        cause_type = "ExternalError"
    return D3BExecutionFailure(
        request_id=request_id,
        failure=D3BExecutionFailureRecord(
            code=code,
            phase=phase,
            gateway_call_count=cast(Any, gateway_call_count),
            cause_type=cause_type,
        ),
        cause=cause,
    )


def _nested(config: Mapping[str, Any], *path: str) -> Any:
    current: Any = config
    for part in path:
        if type(current) is not dict or part not in current:
            return _MISSING
        current = current[part]
    return current


def _rational(value: Any) -> Fraction | None:
    """Expose an authored JSON number as an exact, arithmetic-safe rational."""
    if type(value) is int:
        return Fraction(value)
    if type(value) is float and math.isfinite(value):
        return Fraction.from_float(value)
    return None


def _numeric_projection_receipt(
    assertion_id: str,
    project_value: Decimal,
    authored_values: Sequence[Any],
) -> D3BNumericProjectionReceipt | None:
    """Compare through one disclosed finite binary64 projection.

    Integer-authored values must also equal the ProjectCase Decimal exactly, so
    binary64 rounding cannot collapse two distinct integer propositions.
    """
    try:
        projected = float(project_value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(projected):
        return None
    if project_value != 0 and projected == 0.0:
        return None
    projected_hex = projected.hex()
    occurrences: list[D3BAuthoredNumericValue] = []
    for value in authored_values:
        if type(value) is int:
            if Decimal(value) != project_value or float(value).hex() != projected_hex:
                return None
            occurrence = D3BAuthoredNumericValue(
                json_type="integer",
                authored_value=str(value),
                binary64_hex=float(value).hex(),
            )
        elif type(value) is float and math.isfinite(value):
            if value.hex() != projected_hex:
                return None
            occurrence = D3BAuthoredNumericValue(
                json_type="binary64",
                authored_value=repr(value),
                binary64_hex=value.hex(),
            )
        else:
            return None
        occurrences.append(occurrence)
    if not occurrences:
        return None
    return D3BNumericProjectionReceipt(
        assertion_id=assertion_id,
        project_decimal=str(project_value),
        projected_binary64_hex=projected_hex,
        authored_values=tuple(occurrences),
    )


def _all_equal_exact(values: Sequence[Any]) -> bool:
    if not values:
        return False
    first = values[0]
    if type(first) in {int, float}:
        first_rational = _rational(first)
        return first_rational is not None and all(
            _rational(value) == first_rational for value in values
        )
    return all(type(value) is type(first) and value == first for value in values)


def _recognized_values(
    config: Mapping[str, Any], paths: Sequence[tuple[str, ...]]
) -> tuple[Any, ...]:
    return tuple(
        value for path in paths if (value := _nested(config, *path)) is not _MISSING
    )


def _material_decimal(value: ResolvedValue | ResolvedCount | MissingValue) -> Decimal:
    if type(value) is MissingValue:
        raise _MissingMaterialValue("missing material value")
    if type(value) is ResolvedCount:
        return Decimal(value.value)
    if type(value) is ResolvedValue:
        return value.value
    raise TypeError("non-canonical material value")


def _material_unit(value: ResolvedValue | ResolvedCount | MissingValue) -> str:
    if type(value) not in {ResolvedValue, ResolvedCount, MissingValue}:
        raise TypeError("non-canonical material value")
    return value.unit


def _project_case_reference_matches(
    project_case: ProjectCase, request: EvaluationRequest
) -> bool:
    reference = request.project_case
    identity = project_case.identity
    return (
        project_case.schema_id == reference.schema_id
        and project_case.contract_version == reference.contract_version
        and identity.project_id == reference.project_id
        and identity.case_id == reference.case_id
        and identity.revision == reference.revision
    )


def _binding_for_request(
    request: EvaluationRequest, authority: AuthoredScenarioPathAuthority
) -> AuthoredScenarioPathBinding | None:
    for binding in authority.bindings:
        if binding.config_id == request.base_scenario.config_id:
            if binding.authority_source_id != request.base_scenario.authority_source_id:
                return None
            return binding
    return None


def _authority_binding_matches(
    binding: AuthoredScenarioPathBinding,
    project_case: ProjectCase,
    request: EvaluationRequest,
) -> bool:
    """Bind the closed path ledger to the exact case, request, dates and basis."""
    try:
        case_digest = resolved_config_sha256(project_case.model_dump(mode="json"))
        request_digest = resolved_config_sha256(request.model_dump(mode="json"))
    except (TypeError, ValueError):
        return False
    authority_ids = {item.source_id for item in project_case.sources} | {
        item.assumption_id for item in project_case.assumptions
    }
    price_bases = tuple(
        item
        for item in project_case.costs.price_bases
        if item.price_basis_id == binding.price_basis_id
    )
    if len(price_bases) != 1:
        return False
    price_basis = price_bases[0]
    expected_jurisdiction_domains = tuple(
        sorted(
            (
                D3BAuthorizedJurisdictionDomain(
                    jurisdiction_binding_id=item.jurisdiction_binding_id,
                    jurisdiction_code=item.jurisdiction_code,
                    subject=cast(Any, item.subject.value),
                    base_domain=item.base_domain.value,
                )
                for item in request.binding_policy.assertions
                if type(item) is JurisdictionSubjectAssertion
            ),
            key=lambda item: (
                item.subject,
                item.base_domain,
                item.jurisdiction_binding_id,
            ),
        )
    )
    scope_technologies = {
        item.technology_binding_id: item for item in request.scope.technology_scope
    }
    expected_technology_bindings: list[D3BAuthorizedTechnologyBinding] = []
    for item in request.base_scenario.technology_authorities:
        scoped = scope_technologies.get(item.technology_binding_id)
        if scoped is None:
            return False
        expected_technology_bindings.append(
            D3BAuthorizedTechnologyBinding(
                technology_binding_id=item.technology_binding_id,
                technology_id=item.technology_id,
                asset_class=scoped.asset_class.value,
                base_config_key=item.base_config_key,
                authored_technology_kind=item.authored_technology_kind.value,
            )
        )
    exact_technology_bindings = tuple(
        sorted(
            expected_technology_bindings,
            key=lambda item: item.technology_binding_id,
        )
    )
    return (
        binding.config_id == request.base_scenario.config_id
        and binding.config_version == request.base_scenario.config_version
        and binding.authority_source_id == request.base_scenario.authority_source_id
        and binding.source_file_sha256 == request.base_scenario.source_file_sha256
        and binding.resolved_config_sha256
        == request.base_scenario.resolved_config_sha256
        and binding.project_case_sha256 == case_digest
        and binding.evaluation_request_sha256 == request_digest
        and binding.jurisdiction_domains == expected_jurisdiction_domains
        and binding.technology_bindings == exact_technology_bindings
        and binding.evidence_cutoff == request.scope.evidence_cutoff
        and binding.valuation_date == request.scope.valuation_date
        and binding.price_basis_id == request.scope.price_basis_id
        and binding.price_nominality == request.scope.price_nominality.value
        and binding.reporting_currency == request.scope.reporting_currency
        and binding.evidence_cutoff_authority_source_id in authority_ids
        and binding.valuation_authority_source_id in authority_ids
        and price_basis.valuation_date == binding.valuation_date
        and price_basis.nominality.value == binding.price_nominality
        and price_basis.reporting_currency == binding.reporting_currency
    )


def _resolve_authorized_file(
    authority: AuthoredScenarioPathAuthority,
    binding: AuthoredScenarioPathBinding,
) -> Path:
    root = Path(authority.repository_root)
    if root.is_symlink() or root.resolve(strict=True) != root:
        raise ValueError("repository authority root is not an exact real path")
    relative = PurePosixPath(binding.repository_relative_path)
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("authored path traverses a symbolic link")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("authored path leaves its authority root or is not a file")
    return resolved


def _open_no_follow(path: Path) -> BinaryIO:
    """Open one absolute regular file through descriptor-anchored no-follow steps."""
    if not path.is_absolute() or not path.name:
        raise ValueError("authored scenario path must be an absolute file path")
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory_only = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory_only is None:
        raise OSError("platform lacks descriptor-anchored no-follow support")
    close_on_exec = getattr(os, "O_CLOEXEC", 0)
    directory_flags = os.O_RDONLY | directory_only | no_follow | close_on_exec
    file_flags = os.O_RDONLY | no_follow | close_on_exec
    directory_fd = os.open(path.anchor, directory_flags)
    file_fd: int | None = None
    try:
        for component in path.parts[1:-1]:
            next_fd = os.open(
                component,
                directory_flags,
                dir_fd=directory_fd,
            )
            os.close(directory_fd)
            directory_fd = next_fd
        file_fd = os.open(path.name, file_flags, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)
    try:
        return os.fdopen(file_fd, "rb", closefd=True)
    except Exception:
        os.close(file_fd)
        raise


def _file_receipt(path: Path) -> tuple[bytes, str, tuple[int, int, int, int]]:
    """Read one bounded exact regular-file inode and return its fstat receipt."""
    with _open_no_follow(path) as file_obj:
        before = os.fstat(file_obj.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("authored scenario descriptor is not a regular file")
        if before.st_size > _MAX_AUTHORED_SCENARIO_BYTES:
            raise ValueError("authored scenario exceeds the maximum byte size")
        source_bytes = file_obj.read(_MAX_AUTHORED_SCENARIO_BYTES + 1)
        after = os.fstat(file_obj.fileno())
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if len(source_bytes) > _MAX_AUTHORED_SCENARIO_BYTES:
        raise ValueError("authored scenario exceeds the maximum byte size")
    if before_identity != after_identity or len(source_bytes) != before.st_size:
        raise OSError("authored scenario inode changed during its verified read")
    return source_bytes, hashlib.sha256(source_bytes).hexdigest(), before_identity


def _live_material_counts(
    project_case: ProjectCase,
) -> dict[ProjectCaseMaterialCategory, int]:
    generation = tuple(
        item for item in project_case.assets if type(item) is GenerationAsset
    )
    storage = tuple(item for item in project_case.assets if type(item) is StorageAsset)
    capex = tuple(
        item for item in project_case.costs.lines if item.cost_kind == "capex"
    )
    opex = tuple(item for item in project_case.costs.lines if item.cost_kind == "opex")
    return {
        ProjectCaseMaterialCategory.IDENTITY: 1,
        ProjectCaseMaterialCategory.LOCATION: 1,
        ProjectCaseMaterialCategory.JURISDICTION_SUBJECT: len(
            project_case.jurisdiction_bindings
        ),
        ProjectCaseMaterialCategory.TECHNOLOGY_BINDING: len(
            project_case.technology_bindings
        ),
        ProjectCaseMaterialCategory.GENERATION_CAPACITY: len(generation),
        ProjectCaseMaterialCategory.STORAGE_CAPACITY: len(storage),
        ProjectCaseMaterialCategory.STORAGE_CHARGING_SOURCE: len(storage),
        ProjectCaseMaterialCategory.TOPOLOGY: 1,
        ProjectCaseMaterialCategory.CAPEX: len(capex),
        ProjectCaseMaterialCategory.OPEX: len(opex),
        ProjectCaseMaterialCategory.CURRENCY_CONVERSION: len(
            project_case.costs.currency_conversions
        ),
        ProjectCaseMaterialCategory.PRICE_BASIS: len(project_case.costs.price_bases),
        ProjectCaseMaterialCategory.SOURCE_PROVENANCE: len(project_case.sources),
        ProjectCaseMaterialCategory.ASSUMPTION_PROVENANCE: len(
            project_case.assumptions
        ),
        ProjectCaseMaterialCategory.MISSING_INPUT: len(project_case.missing_inputs),
    }


def _live_element_sets_match(
    project_case: ProjectCase, request: EvaluationRequest
) -> bool:
    live_jurisdictions = {
        (item.binding_id, item.jurisdiction_code, item.subject)
        for item in project_case.jurisdiction_bindings
    }
    scoped_jurisdictions = {
        (item.jurisdiction_binding_id, item.jurisdiction_code, item.subject)
        for item in request.scope.jurisdiction_scope
    }
    if live_jurisdictions != scoped_jurisdictions:
        return False

    live_technologies = {
        (item.binding_id, item.technology_id, item.asset_class)
        for item in project_case.technology_bindings
    }
    scoped_technologies = {
        (item.technology_binding_id, item.technology_id, item.asset_class)
        for item in request.scope.technology_scope
    }
    if live_technologies != scoped_technologies:
        return False

    physical_assets = cast(
        tuple[GenerationAsset | StorageAsset, ...],
        tuple(
            item
            for item in project_case.assets
            if type(item) in {GenerationAsset, StorageAsset}
        ),
    )
    binding_ids = tuple(item.technology_binding_id for item in physical_assets)
    if len(set(binding_ids)) != len(binding_ids):
        return False
    technology_assertions = tuple(
        item
        for item in request.binding_policy.assertions
        if type(item) is TechnologyBindingAssertion
    )
    live_assets = {
        (
            item.asset_id,
            item.technology_binding_id,
            item.technology_id,
            "generation" if type(item) is GenerationAsset else "storage",
        )
        for item in physical_assets
    }
    declared_assets = {
        (
            item.asset_id,
            item.technology_binding_id,
            item.technology_id,
            item.asset_class.value,
        )
        for item in technology_assertions
    }
    if live_assets != declared_assets:
        return False

    generation_assets = {
        item.asset_id for item in physical_assets if type(item) is GenerationAsset
    }
    declared_generation = {
        item.asset_id
        for item in request.binding_policy.assertions
        if type(item) is GenerationCapacityAssertion
    }
    if generation_assets != declared_generation:
        return False
    storage_assets = {
        item.asset_id for item in physical_assets if type(item) is StorageAsset
    }
    declared_storage = {
        item.asset_id
        for item in request.binding_policy.assertions
        if type(item) is StorageCapacityAssertion
    }
    return storage_assets == declared_storage


def _assertion_project_value(
    assertion: Any, project_case: ProjectCase
) -> tuple[Decimal | str, str | None]:
    assets = {item.asset_id: item for item in project_case.assets}
    if type(assertion) is ScenarioIdentityAssertion:
        return project_case.identity.case_name, None
    if type(assertion) is LocationAssertion:
        value = {
            LocationSourceField.SITE_NAME: project_case.location.site_name,
            LocationSourceField.DESCRIPTION: project_case.location.description,
        }[assertion.project_case_selector]
        return value, None
    if type(assertion) is GenerationCapacityAssertion:
        asset = assets.get(assertion.asset_id)
        if type(asset) is not GenerationAsset:
            raise ValueError("generation assertion asset mismatch")
        capacity = asset.capacity
        material: ResolvedValue | ResolvedCount | MissingValue
        if (
            assertion.project_case_selector
            is GenerationCapacitySourceField.TOTAL_POWER_CAPACITY
        ):
            material = capacity.total_power_capacity
        elif (
            assertion.project_case_selector
            is GenerationCapacitySourceField.UNIT_RATED_POWER
        ):
            if type(capacity) is not UnitizedGenerationCapacity:
                raise ValueError("unitized generation assertion asset mismatch")
            material = capacity.unit_power_capacity
        else:
            if type(capacity) is not UnitizedGenerationCapacity:
                raise ValueError("unitized generation assertion asset mismatch")
            material = capacity.unit_count
        return _material_decimal(material), _material_unit(material)
    if type(assertion) is StorageCapacityAssertion:
        asset = assets.get(assertion.asset_id)
        if type(asset) is not StorageAsset:
            raise ValueError("storage assertion asset mismatch")
        material = {
            StorageCapacitySourceField.POWER: asset.power_capacity.value,
            StorageCapacitySourceField.ENERGY: asset.energy_capacity.value,
            StorageCapacitySourceField.DURATION: asset.duration.value,
        }[assertion.project_case_selector]
        return _material_decimal(material), _material_unit(material)
    if type(assertion) is CostCompatibilityAssertion:
        lines = {item.line_id: item for item in project_case.costs.lines}
        selected = tuple(lines.get(line_id) for line_id in assertion.included_line_ids)
        if any(line is None for line in selected):
            raise ValueError("cost assertion line set mismatch")
        expected_kind = assertion.category.value
        total = Decimal(0)
        for line in selected:
            assert line is not None
            if (
                line.cost_kind != expected_kind
                or line.periodicity.value != assertion.periodicity.value
                or line.price_basis_id != assertion.price_basis_id
                or line.amount.reporting_currency != assertion.reporting_currency
            ):
                raise ValueError(
                    "cost assertion kind, periodicity, basis, and currency must agree"
                )
            total += _material_decimal(line.amount.reporting_amount)
        return total, assertion.reporting_currency
    raise TypeError("assertion does not carry a scalar compatibility value")


def _assertion_config_values(
    assertion: Any, config: Mapping[str, Any]
) -> tuple[Any, ...]:
    if type(assertion) is ScenarioIdentityAssertion:
        return _recognized_values(config, (("scenario_name",),))
    if type(assertion) is LocationAssertion:
        return _recognized_values(
            config, (("project", "location"), ("project_location",))
        )
    if type(assertion) is GenerationCapacityAssertion:
        selector = assertion.base_selector
        key = assertion.base_config_key
        paths = {
            V14GenerationCapacitySelector.PROJECT_CAPACITY_MW: (
                ("project", "capacity_mw"),
            ),
            V14GenerationCapacitySelector.TECHNOLOGY_CAPACITY_MW: (
                ("generation", "technologies", cast(str, key), "capacity_mw"),
            ),
            V14GenerationCapacitySelector.SOLAR_RESOURCE_DC_CAPACITY_MW: (
                ("resource", "solar", "dc_capacity_mw"),
                ("generation", "technologies", cast(str, key), "dc_capacity_mw"),
            ),
            V14GenerationCapacitySelector.TURBINE_COUNT: (
                ("turbine", "n_turbines"),
                ("resource", "turbines", "count"),
            ),
            V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW: (
                ("turbine", "rated_power_mw"),
                ("resource", "turbines", "rated_power_mw"),
            ),
            V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW: (
                ("turbine", "total_capacity_mw"),
                ("resource", "turbines", "total_capacity_mw"),
            ),
        }[selector]
        return _recognized_values(config, paths)
    if type(assertion) is StorageCapacityAssertion:
        field = {
            V14StorageCapacitySelector.TECHNOLOGY_POWER_MW: "power_mw",
            V14StorageCapacitySelector.TECHNOLOGY_ENERGY_MWH: "energy_mwh",
            V14StorageCapacitySelector.TECHNOLOGY_DURATION_H: "duration_h",
        }[assertion.base_selector]
        return _recognized_values(
            config,
            (("generation", "technologies", assertion.base_config_key, field),),
        )
    if type(assertion) is CostCompatibilityAssertion:
        paths = {
            V14CostSelector.CAPEX_USD_TOTAL: (("capex", "usd_total"),),
            V14CostSelector.OPEX_USD_PER_YEAR: (("opex", "usd_per_year"),),
        }[assertion.base_selector]
        return _recognized_values(config, paths)
    raise TypeError("assertion does not carry an authored scalar selector")


def _authored_technology_keys_match(
    config: Mapping[str, Any], request: EvaluationRequest
) -> bool:
    authorities = request.base_scenario.technology_authorities
    expected_keys = {item.base_config_key for item in authorities}
    technologies = _nested(config, "generation", "technologies")
    if technologies is not _MISSING:
        if type(technologies) is not dict or set(technologies) != expected_keys:
            return False
    legacy_turbine = _nested(config, "turbine")
    legacy_wind_authorities = tuple(
        item
        for item in authorities
        if item.authored_technology_kind.value == "wind_turbine"
    )
    if legacy_turbine is not _MISSING:
        if type(legacy_turbine) is not dict or len(legacy_wind_authorities) != 1:
            return False
        turbine_selectors = {
            item.base_selector
            for item in request.binding_policy.assertions
            if type(item) is GenerationCapacityAssertion
            and item.base_selector
            in {
                V14GenerationCapacitySelector.TURBINE_COUNT,
                V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW,
                V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW,
            }
        }
        if turbine_selectors != {
            V14GenerationCapacitySelector.TURBINE_COUNT,
            V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW,
            V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW,
        }:
            return False
    for authority in authorities:
        key = authority.base_config_key
        candidates = [
            _nested(config, "generation", "technologies", key),
            _nested(config, key),
            _nested(config, "resource", key),
        ]
        if (
            authority.authored_technology_kind.value == "wind_turbine"
            and len(legacy_wind_authorities) == 1
        ):
            candidates.append(legacy_turbine)
        if not any(
            type(value) is dict for value in candidates if value is not _MISSING
        ):
            return False
    return True


def _authored_domain_present(
    domain: BaseConfigDomain, config: Mapping[str, Any]
) -> bool:
    paths: dict[BaseConfigDomain, tuple[tuple[str, ...], ...]] = {
        BaseConfigDomain.SCENARIO_IDENTITY: (("scenario_name",),),
        BaseConfigDomain.PROJECT_IDENTITY_LOCATION: (
            ("project", "name"),
            ("project", "location"),
            ("project", "jurisdiction_code"),
        ),
        BaseConfigDomain.PROJECT_RESOURCE: (
            ("project", "capacity_mw"),
            ("project", "capacity_factor"),
            ("project", "capacity_factor_pct"),
        ),
        BaseConfigDomain.PROJECT_LIFECYCLE_TIMELINE: (
            ("project", "life_years"),
            ("project", "project_life_years"),
            ("project", "cod_year"),
        ),
        BaseConfigDomain.TECHNOLOGY_RESOURCE: (
            ("generation",),
            ("resource",),
            ("turbine",),
            ("wind",),
        ),
        BaseConfigDomain.REVENUE_TARIFF: (("tariff",), ("revenue",)),
        BaseConfigDomain.CAPEX: (("capex",),),
        BaseConfigDomain.OPEX: (("opex",),),
        BaseConfigDomain.TAX_STATUTORY: (("tax",),),
        BaseConfigDomain.FX: (("fx",),),
        BaseConfigDomain.GRID: (("grid",),),
        BaseConfigDomain.ACCOUNTING: (("accounting",),),
        BaseConfigDomain.FINANCING_DEBT: (("debt",),),
        BaseConfigDomain.WACC: (("wacc",),),
        BaseConfigDomain.RUN_POSTURE: (("run",), ("run_mode",)),
    }
    return any(_nested(config, *path) is not _MISSING for path in paths[domain])


def _authored_domain_dispositions_match(
    config: Mapping[str, Any], request: EvaluationRequest
) -> bool:
    for disposition in request.base_scenario.domain_dispositions:
        present = _authored_domain_present(disposition.domain, config)
        if (
            disposition.disposition
            is BaseDomainDispositionKind.RETAINED_AUTHORED_AUTHORITY
        ):
            if not present and disposition.domain is not BaseConfigDomain.RUN_POSTURE:
                return False
        elif present:
            return False
    return True


def _authored_jurisdictions_match(
    config: Mapping[str, Any], request: EvaluationRequest
) -> bool:
    by_binding = {
        item.jurisdiction_binding_id: item
        for item in request.base_scenario.subject_authorities
    }
    dispositions = {
        item.domain: item for item in request.base_scenario.domain_dispositions
    }
    for assertion in request.binding_policy.assertions:
        if type(assertion) is not JurisdictionSubjectAssertion:
            continue
        authority = by_binding.get(assertion.jurisdiction_binding_id)
        disposition = dispositions.get(assertion.base_domain)
        if (
            authority is None
            or authority.jurisdiction_code != assertion.jurisdiction_code
            or authority.subject is not assertion.subject
            or disposition is None
            or not any(
                route.jurisdiction_binding_id == assertion.jurisdiction_binding_id
                for route in disposition.authority_routes
            )
        ):
            return False
        domain_roots: tuple[tuple[str, ...], ...]
        if assertion.base_domain in {
            BaseConfigDomain.PROJECT_IDENTITY_LOCATION,
            BaseConfigDomain.PROJECT_RESOURCE,
            BaseConfigDomain.PROJECT_LIFECYCLE_TIMELINE,
        }:
            domain_roots = (("project",),)
        elif assertion.base_domain is BaseConfigDomain.TECHNOLOGY_RESOURCE:
            domain_roots = (("generation",), ("resource",), ("turbine",))
        elif assertion.base_domain is BaseConfigDomain.REVENUE_TARIFF:
            domain_roots = (("tariff",), ("revenue",))
        elif assertion.base_domain is BaseConfigDomain.TAX_STATUTORY:
            domain_roots = (("tax",),)
        elif assertion.base_domain is BaseConfigDomain.FINANCING_DEBT:
            domain_roots = (("debt",),)
        else:
            domain_roots = ((assertion.base_domain.value,),)
        candidates = list(
            _recognized_values(
                config,
                tuple((*root, "jurisdiction_code") for root in domain_roots)
                + ((assertion.subject.value, "jurisdiction_code"),),
            )
        )
        if assertion.subject.value == "site":
            candidates.extend(
                _recognized_values(
                    config,
                    (
                        ("project", "jurisdiction_code"),
                        ("jurisdiction", "code"),
                        ("jurisdiction_code",),
                    ),
                )
            )
            if _nested(config, "project", "jurisdiction") is not _MISSING:
                return False
        if any(
            type(value) is not str or value != assertion.jurisdiction_code
            for value in candidates
        ):
            return False
    return True


def _authored_redundancies_match(
    config: Mapping[str, Any], request: EvaluationRequest
) -> bool:
    for assertion in request.binding_policy.assertions:
        if type(assertion) in {
            ScenarioIdentityAssertion,
            LocationAssertion,
            GenerationCapacityAssertion,
            StorageCapacityAssertion,
            CostCompatibilityAssertion,
        }:
            values = _assertion_config_values(assertion, config)
            if len(values) > 1 and not _all_equal_exact(values):
                return False

    for authority in request.base_scenario.technology_authorities:
        key = authority.base_config_key
        aep_values = _recognized_values(
            config,
            (
                ("generation", "technologies", key, "aep_gwh"),
                ("resource", key, "aep_gwh"),
                (key, "aep_gwh"),
            ),
        )
        if len(aep_values) > 1 and not _all_equal_exact(aep_values):
            return False

    fx_values = _recognized_values(
        config,
        (
            ("fx", "start_lkr_per_usd"),
            ("fx", "rates", "lkr_per_usd"),
            ("fx", "source", "pinned_rate"),
        ),
    )
    if len(fx_values) > 1 and not _all_equal_exact(fx_values):
        return False

    generation_assertions = tuple(
        item
        for item in request.binding_policy.assertions
        if type(item) is GenerationCapacityAssertion
    )
    project_capacity = tuple(
        item
        for item in generation_assertions
        if item.base_selector is V14GenerationCapacitySelector.PROJECT_CAPACITY_MW
    )
    technology_capacity = tuple(
        item
        for item in generation_assertions
        if item.base_selector is V14GenerationCapacitySelector.TECHNOLOGY_CAPACITY_MW
    )
    if project_capacity and technology_capacity:
        common_basis = {
            (item.electrical_basis, item.capacity_basis, item.expected_unit)
            for item in (*project_capacity, *technology_capacity)
        }
        if len(common_basis) != 1:
            return False
        project_values = _assertion_config_values(project_capacity[0], config)
        technology_values = tuple(
            _assertion_config_values(item, config)[0] for item in technology_capacity
        )
        project_rational = _rational(project_values[0])
        technology_rationals = tuple(_rational(item) for item in technology_values)
        if (
            project_rational is None
            or any(item is None for item in technology_rationals)
            or project_rational
            != sum(
                (cast(Fraction, item) for item in technology_rationals),
                start=Fraction(0),
            )
        ):
            return False

    turbine_by_selector = {
        selector: next(
            (item for item in generation_assertions if item.base_selector is selector),
            None,
        )
        for selector in (
            V14GenerationCapacitySelector.TURBINE_COUNT,
            V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW,
            V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW,
        )
    }
    if all(turbine_by_selector.values()):
        count = _rational(
            _assertion_config_values(
                turbine_by_selector[V14GenerationCapacitySelector.TURBINE_COUNT],
                config,
            )[0]
        )
        rated = _rational(
            _assertion_config_values(
                turbine_by_selector[
                    V14GenerationCapacitySelector.TURBINE_RATED_POWER_MW
                ],
                config,
            )[0]
        )
        total = _rational(
            _assertion_config_values(
                turbine_by_selector[
                    V14GenerationCapacitySelector.TURBINE_TOTAL_CAPACITY_MW
                ],
                config,
            )[0]
        )
        if count is None or rated is None or total is None or count * rated != total:
            return False

    storage_assertions = tuple(
        item
        for item in request.binding_policy.assertions
        if type(item) is StorageCapacityAssertion
    )
    storage_by_key: dict[
        str, dict[V14StorageCapacitySelector, StorageCapacityAssertion]
    ] = {}
    for assertion in storage_assertions:
        storage_by_key.setdefault(assertion.base_config_key, {})[
            assertion.base_selector
        ] = assertion
    for selectors in storage_by_key.values():
        if set(selectors) != set(V14StorageCapacitySelector):
            return False
        power = _rational(
            _assertion_config_values(
                selectors[V14StorageCapacitySelector.TECHNOLOGY_POWER_MW], config
            )[0]
        )
        energy = _rational(
            _assertion_config_values(
                selectors[V14StorageCapacitySelector.TECHNOLOGY_ENERGY_MWH], config
            )[0]
        )
        duration = _rational(
            _assertion_config_values(
                selectors[V14StorageCapacitySelector.TECHNOLOGY_DURATION_H], config
            )[0]
        )
        if (
            power is None
            or energy is None
            or duration is None
            or power * duration != energy
        ):
            return False
    return True


def _compatibility_receipts(
    project_case: ProjectCase, request: EvaluationRequest, config: Mapping[str, Any]
) -> tuple[D3BNumericProjectionReceipt, ...] | None:
    if not _authored_domain_dispositions_match(config, request):
        return None
    if not _authored_technology_keys_match(config, request):
        return None
    if not _authored_jurisdictions_match(config, request):
        return None

    live_capex_ids = {
        item.line_id for item in project_case.costs.lines if item.cost_kind == "capex"
    }
    live_opex_ids = {
        item.line_id for item in project_case.costs.lines if item.cost_kind == "opex"
    }
    asserted_capex_ids: set[str] = set()
    asserted_opex_ids: set[str] = set()
    numeric_receipts: list[D3BNumericProjectionReceipt] = []

    for assertion in request.binding_policy.assertions:
        if type(assertion) in {
            JurisdictionSubjectAssertion,
            TechnologyBindingAssertion,
        }:
            continue
        if type(assertion) is PriceBasisAssertion:
            matching_bases = tuple(
                basis
                for basis in project_case.costs.price_bases
                if basis.price_basis_id == assertion.price_basis_id
            )
            if len(project_case.costs.price_bases) != 1 or len(matching_bases) != 1:
                return None
            basis = matching_bases[0]
            if (
                basis.valuation_date != assertion.valuation_date
                or basis.reporting_currency != assertion.reporting_currency
                or basis.nominality is not assertion.nominality
            ):
                return None
            continue
        project_value, project_unit = _assertion_project_value(assertion, project_case)
        config_values = _assertion_config_values(assertion, config)
        if not config_values:
            return None
        if type(assertion) is CostCompatibilityAssertion:
            if assertion.category is ProjectCaseMaterialCategory.CAPEX:
                asserted_capex_ids.update(assertion.included_line_ids)
            else:
                asserted_opex_ids.update(assertion.included_line_ids)
        if type(project_value) is Decimal:
            if project_unit != getattr(assertion, "expected_unit", project_unit):
                return None
            receipt = _numeric_projection_receipt(
                assertion.assertion_id, project_value, config_values
            )
            if receipt is None:
                return None
            numeric_receipts.append(receipt)
        elif any(
            type(value) is not str or value != project_value for value in config_values
        ):
            return None

    if live_capex_ids != asserted_capex_ids or live_opex_ids != asserted_opex_ids:
        return None
    return tuple(numeric_receipts)


def _run_mode_plan(
    config: Mapping[str, Any], request: EvaluationRequest
) -> tuple[dict[str, Any], dict[str, Any]]:
    if "run_mode" in config:
        raise ValueError("legacy run mode alias")
    run = config.get("run", _MISSING)
    scope_mode = request.scope.run_mode.value
    overrides: dict[str, Any] = {}
    if run is _MISSING:
        overrides = {"run": {"mode": scope_mode}}
    else:
        if type(run) is not dict or set(run) - {"mode"}:
            raise ValueError("unknown run posture")
        if "mode" not in run:
            overrides = {"run": {"mode": scope_mode}}
        elif type(run["mode"]) is not str or run["mode"] != scope_mode:
            raise ValueError("conflicting run posture")
    evaluated = _copy_json(config)
    if overrides:
        evaluated.setdefault("run", {})["mode"] = scope_mode
    return overrides, evaluated


def _copy_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _copy_json(item) for key, item in value.items()}
    if type(value) in {list, tuple}:
        return [_copy_json(item) for item in value]
    return value


def _freeze_json(
    value: Any,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
    memo: dict[int, Any] | None = None,
    counts: list[int] | None = None,
) -> Any:
    """Freeze one exact finite legacy result tree without dropping ``None``."""
    if depth > _MAX_RESULT_DEPTH:
        raise ValueError("result exceeds the maximum JSON depth")
    visited = seen if seen is not None else set()
    frozen_memo = memo if memo is not None else {}
    totals = counts if counts is not None else [0, 0, 0]
    if type(value) is dict:
        marker = id(value)
        if marker in visited:
            raise ValueError("result contains a cyclic mapping")
        if marker in frozen_memo:
            return frozen_memo[marker]
        visited.add(marker)
        totals[0] += 1
        if totals[0] > _MAX_RESULT_CONTAINERS:
            raise ValueError("result exceeds the maximum JSON container count")
        if any(
            type(key) not in {str, int, float}
            or (type(key) is float and not math.isfinite(key))
            or (type(key) is int and key.bit_length() > 4096)
            for key in value
        ):
            raise ValueError("result contains an unsupported mapping key")
        totals[2] += sum(len(key) for key in value if type(key) is str)
        if totals[2] > _MAX_RESULT_TEXT_CODEPOINTS:
            raise ValueError("result exceeds the maximum JSON text volume")
        frozen_mapping = MappingProxyType(
            {
                key: _freeze_json(
                    item,
                    depth=depth + 1,
                    seen=visited,
                    memo=frozen_memo,
                    counts=totals,
                )
                for key, item in value.items()
            }
        )
        visited.remove(marker)
        frozen_memo[marker] = frozen_mapping
        return frozen_mapping
    if type(value) in {list, tuple}:
        marker = id(value)
        if marker in visited:
            raise ValueError("result contains a cyclic sequence")
        if marker in frozen_memo:
            return frozen_memo[marker]
        visited.add(marker)
        totals[0] += 1
        if totals[0] > _MAX_RESULT_CONTAINERS:
            raise ValueError("result exceeds the maximum JSON container count")
        frozen_sequence = tuple(
            _freeze_json(
                item,
                depth=depth + 1,
                seen=visited,
                memo=frozen_memo,
                counts=totals,
            )
            for item in value
        )
        visited.remove(marker)
        frozen_memo[marker] = frozen_sequence
        return frozen_sequence
    totals[1] += 1
    if totals[1] > _MAX_RESULT_SCALARS:
        raise ValueError("result exceeds the maximum JSON scalar count")
    if value is None or type(value) is bool:
        return value
    if type(value) is str:
        totals[2] += len(value)
        if totals[2] > _MAX_RESULT_TEXT_CODEPOINTS:
            raise ValueError("result exceeds the maximum JSON text volume")
        return value
    if type(value) is int:
        if value.bit_length() > 4096:
            raise ValueError("result integer exceeds the maximum bit length")
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("result contains a non-JSON-native or non-finite value")


def _assert_frozen_occurrence_bounds(
    value: Any,
    *,
    depth: int = 0,
    active: set[int] | None = None,
    counts: list[int] | None = None,
) -> None:
    """Bound the detached occurrence shape before any recursive comparison.

    ``_freeze_json`` memoizes shared input containers. This second pass counts
    every occurrence so a small alias DAG cannot expand without limit when it is
    compared or later detached for D3C.
    """
    if depth > _MAX_RESULT_DEPTH:
        raise ValueError("result occurrence graph exceeds the maximum JSON depth")
    seen = active if active is not None else set()
    totals = counts if counts is not None else [0, 0, 0]
    if isinstance(value, MappingProxyType):
        marker = id(value)
        if marker in seen:
            raise ValueError("result occurrence graph contains a mapping cycle")
        totals[0] += 1
        totals[2] += sum(len(key) for key in value if type(key) is str)
        if (
            totals[0] > _MAX_RESULT_CONTAINERS
            or totals[2] > _MAX_RESULT_TEXT_CODEPOINTS
        ):
            raise ValueError("result occurrence graph exceeds its bounded volume")
        seen.add(marker)
        try:
            for item in value.values():
                _assert_frozen_occurrence_bounds(
                    item,
                    depth=depth + 1,
                    active=seen,
                    counts=totals,
                )
        finally:
            seen.remove(marker)
        return
    if type(value) is tuple:
        marker = id(value)
        if marker in seen:
            raise ValueError("result occurrence graph contains a sequence cycle")
        totals[0] += 1
        if totals[0] > _MAX_RESULT_CONTAINERS:
            raise ValueError("result occurrence graph exceeds its bounded volume")
        seen.add(marker)
        try:
            for item in value:
                _assert_frozen_occurrence_bounds(
                    item,
                    depth=depth + 1,
                    active=seen,
                    counts=totals,
                )
        finally:
            seen.remove(marker)
        return
    totals[1] += 1
    if totals[1] > _MAX_RESULT_SCALARS:
        raise ValueError("result occurrence graph exceeds its bounded volume")
    if type(value) is str:
        totals[2] += len(value)
        if totals[2] > _MAX_RESULT_TEXT_CODEPOINTS:
            raise ValueError("result occurrence graph exceeds its bounded volume")


def _exact_mapping_key(key: Any) -> tuple[str, Any]:
    """Return an equality token that never collapses bool/int/float identities."""
    if type(key) is str:
        return ("str", key)
    if type(key) is int:
        return ("int", key)
    if type(key) is float and math.isfinite(key):
        return ("float", key.hex())
    raise ValueError("result contains an unsupported exact mapping key")


def _bounded_exact_equal(
    left: Any,
    right: Any,
    *,
    depth: int = 0,
    compared: set[tuple[int, int]] | None = None,
) -> bool:
    """Compare frozen trees with exact scalar type and binary64 identity."""
    if depth > _MAX_RESULT_DEPTH or type(left) is not type(right):
        return False
    pairs = compared if compared is not None else set()
    if isinstance(left, MappingProxyType):
        if not isinstance(right, MappingProxyType):
            return False
        pair = (id(left), id(right))
        if pair in pairs:
            return True
        pairs.add(pair)
        try:
            left_items = {_exact_mapping_key(key): item for key, item in left.items()}
            right_items = {_exact_mapping_key(key): item for key, item in right.items()}
        except ValueError:
            return False
        if len(left_items) != len(left) or len(right_items) != len(right):
            return False
        if left_items.keys() != right_items.keys():
            return False
        return all(
            _bounded_exact_equal(
                item,
                right_items[key],
                depth=depth + 1,
                compared=pairs,
            )
            for key, item in left_items.items()
        )
    if type(left) is tuple:
        pair = (id(left), id(right))
        if pair in pairs:
            return True
        pairs.add(pair)
        return len(left) == len(right) and all(
            _bounded_exact_equal(
                left_item,
                right_item,
                depth=depth + 1,
                compared=pairs,
            )
            for left_item, right_item in zip(left, right, strict=True)
        )
    if type(left) is float:
        return (
            math.isfinite(left) and math.isfinite(right) and left.hex() == right.hex()
        )
    return bool(left == right)


def _validate_gateway_result(
    raw_result: Any, expected_config_digest: str
) -> tuple[Mapping[str, Any], Mapping[str, Any], tuple[str, ...], bool]:
    frozen = _freeze_json(raw_result)
    _assert_frozen_occurrence_bounds(frozen)
    if not isinstance(frozen, MappingProxyType) or frozen.get("status") != "success":
        raise ValueError("gateway did not return the exact success protocol")
    result = cast(Mapping[str, Any], frozen)
    required_result_types = {
        "config_path": str,
        "validation_mode": str,
        "scenario_result": MappingProxyType,
        "kpis": MappingProxyType,
        "annual_rows": tuple,
        "debt_result": MappingProxyType,
        "equity_distribution": MappingProxyType,
        "metrics": MappingProxyType,
    }
    if any(
        type(result.get(key)) is not expected
        for key, expected in required_result_types.items()
    ):
        raise ValueError("gateway result is missing a required full-result surface")
    if (
        result["config_path"] != "<inline>"
        or result["validation_mode"] != "strict"
        or not result["annual_rows"]
        or any(
            not isinstance(row, MappingProxyType) or not row
            for row in result["annual_rows"]
        )
    ):
        raise ValueError("gateway result has an invalid strict full-result surface")
    scenario_result = result["scenario_result"]
    required_scenario_types = {
        "scenario_name": str,
        "config_path": str,
        "project_npv": float,
        "project_irr": float,
        "dscr_series": tuple,
        "min_dscr": float,
        "max_debt_usd": float,
        "validation_mode": str,
        "config": MappingProxyType,
        "annual_rows": tuple,
        "debt_result": MappingProxyType,
        "kpis": MappingProxyType,
        "metadata": MappingProxyType,
    }
    if any(
        type(scenario_result.get(key)) is not expected
        for key, expected in required_scenario_types.items()
    ) or any(
        not math.isfinite(scenario_result[key])
        for key in ("project_npv", "project_irr", "min_dscr", "max_debt_usd")
    ):
        raise ValueError("gateway ScenarioResult surface is incomplete or invalid")
    if (
        not scenario_result["scenario_name"]
        or scenario_result["config_path"] != "<inline>"
        or scenario_result["validation_mode"] != "strict"
        or not scenario_result["config"]
        or not scenario_result["annual_rows"]
        or not scenario_result["debt_result"]
        or not scenario_result["kpis"]
        or not scenario_result["metadata"]
        or any(
            type(item) is not float or not math.isfinite(item)
            for item in scenario_result["dscr_series"]
        )
    ):
        raise ValueError("gateway ScenarioResult contents are incomplete or invalid")
    try:
        scenario_config_digest = resolved_config_sha256(
            _copy_json(scenario_result["config"])
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("gateway ScenarioResult config cannot be digested") from exc
    if (
        scenario_config_digest != expected_config_digest
        or not _bounded_exact_equal(
            scenario_result["config_path"], result["config_path"]
        )
        or not _bounded_exact_equal(
            scenario_result["validation_mode"], result["validation_mode"]
        )
        or not _bounded_exact_equal(
            scenario_result["annual_rows"], result["annual_rows"]
        )
        or not _bounded_exact_equal(
            scenario_result["debt_result"], result["debt_result"]
        )
        or not _bounded_exact_equal(scenario_result["kpis"], result["kpis"])
    ):
        raise ValueError("gateway duplicated result origins must reconcile exactly")
    kpis = result["kpis"]
    required_kpis = ("project_npv", "project_irr", "min_dscr", "max_debt_usd")
    if any(
        type(kpis.get(key)) is not float or not math.isfinite(kpis[key])
        for key in required_kpis
    ) or any(
        not _bounded_exact_equal(scenario_result[key], kpis[key])
        for key in required_kpis
    ):
        raise ValueError("gateway KPI and ScenarioResult mirrors must agree exactly")
    debt_result = result["debt_result"]
    if (
        type(debt_result.get("debt_total")) is not float
        or not math.isfinite(debt_result["debt_total"])
        or type(debt_result.get("min_dscr")) is not float
        or not math.isfinite(debt_result["min_dscr"])
        or not isinstance(debt_result.get("dscr_by_year"), MappingProxyType)
        or not debt_result["dscr_by_year"]
        or not _bounded_exact_equal(debt_result["debt_total"], kpis["max_debt_usd"])
        or not _bounded_exact_equal(debt_result["min_dscr"], kpis["min_dscr"])
    ):
        raise ValueError("gateway debt-result surface is incomplete or inconsistent")
    manifest = result.get("run_manifest")
    if not isinstance(manifest, MappingProxyType) or any(
        type(key) is not str for key in manifest
    ):
        raise ValueError("gateway result has no exact run manifest")
    required_manifest = {
        "config_sha256": str,
        "engine_version": str,
        "git_sha": str,
        "generated_at": str,
        "manifest_schema_version": str,
    }
    if any(
        type(manifest.get(key)) is not expected
        for key, expected in required_manifest.items()
    ):
        raise ValueError("gateway run manifest has an invalid bounded shape")
    if "seed" not in manifest or (
        manifest["seed"] is not None
        and (type(manifest["seed"]) is not int or manifest["seed"].bit_length() > 4096)
    ):
        raise ValueError("gateway run manifest seed must be an exact integer or null")
    if manifest.get("validation_mode") != "strict":
        raise ValueError("gateway run manifest validation mode must be strict")
    config_digest = manifest["config_sha256"]
    if len(config_digest) != 64 or any(
        character not in "0123456789abcdef" for character in config_digest
    ):
        raise ValueError("gateway run manifest config digest must be SHA-256 hex")
    if config_digest != expected_config_digest:
        raise RuntimeError("gateway run manifest config digest mismatch")
    from analytics.run_manifest import MANIFEST_SCHEMA_VERSION, engine_version

    if (
        manifest["engine_version"] != engine_version()
        or manifest["manifest_schema_version"] != MANIFEST_SCHEMA_VERSION
        or not 7 <= len(manifest["git_sha"]) <= 64
        or any(character not in "0123456789abcdef" for character in manifest["git_sha"])
    ):
        raise ValueError("gateway run manifest code identity is invalid")
    try:
        generated_at = datetime.fromisoformat(
            manifest["generated_at"].replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("gateway run manifest timestamp is invalid") from exc
    if generated_at.utcoffset() != timezone.utc.utcoffset(generated_at):
        raise ValueError("gateway run manifest timestamp must be UTC")

    fx = result.get("fx_integration")
    if not isinstance(fx, MappingProxyType):
        raise ValueError("gateway result has no exact FX integration disclosure")
    for key in ("attempted", "succeeded", "degraded"):
        if type(fx.get(key)) is not bool:
            raise ValueError("gateway FX integration flags must be exact booleans")
    warning = fx.get("warning")
    if warning is not None and type(warning) is not str:
        raise ValueError("gateway FX warning must be exact text or null")
    reasons = fx.get("degraded_reasons")
    if type(reasons) is not tuple or any(type(item) is not str for item in reasons):
        raise ValueError("gateway FX degraded reasons must be exact text")
    if (
        not fx["attempted"]
        or (fx["succeeded"] and warning is not None)
        or (not fx["succeeded"] and warning is None)
        or (fx["degraded"] != bool(reasons))
    ):
        raise ValueError("gateway FX integration disclosure is internally inconsistent")
    warnings: list[str] = []
    top_warnings = result.get("warnings", ())
    if type(top_warnings) is not tuple or any(
        type(item) is not str for item in top_warnings
    ):
        raise ValueError("gateway warnings must be an exact text list")
    warnings.extend(top_warnings)
    if warning is not None:
        warnings.append(warning)
    warnings.extend(reasons)
    frozen_manifest = cast(Mapping[str, Any], result["run_manifest"])
    degraded = bool(warnings) or not fx["succeeded"] or fx["degraded"]
    return result, frozen_manifest, tuple(warnings), degraded


def execute_evaluation_request(
    *,
    project_case: ProjectCase,
    request: EvaluationRequest,
    scenario_authority_id: str,
) -> D3BExecutionResult:
    """Preflight one ProjectCase and make exactly zero or one public v14 call."""
    request_id = request.request_id if type(request) is EvaluationRequest else None
    if (
        type(project_case) is not ProjectCase
        or type(request) is not EvaluationRequest
        or type(scenario_authority_id) is not str
    ):
        return _failure(
            request_id,
            D3BFailureCode.INVALID_INPUT_TYPE,
            D3BExecutionPhase.REQUEST,
        )
    scenario_authority = _AUTHORED_SCENARIO_AUTHORITIES.get(scenario_authority_id)
    if type(scenario_authority) is not AuthoredScenarioPathAuthority:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND,
            D3BExecutionPhase.AUTHORITY,
        )
    try:
        project_case_reference_matches = _project_case_reference_matches(
            project_case, request
        )
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.PROJECT_CASE_IDENTITY_MISMATCH,
            D3BExecutionPhase.REQUEST,
            cause=exc,
        )
    if not project_case_reference_matches:
        return _failure(
            request_id,
            D3BFailureCode.PROJECT_CASE_IDENTITY_MISMATCH,
            D3BExecutionPhase.REQUEST,
        )

    try:
        binding = _binding_for_request(request, scenario_authority)
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND,
            D3BExecutionPhase.AUTHORITY,
            cause=exc,
        )
    if binding is None:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_AUTHORITY_NOT_FOUND,
            D3BExecutionPhase.AUTHORITY,
        )
    try:
        authority_matches = _authority_binding_matches(binding, project_case, request)
    except (InvalidOperation, MemoryError, TypeError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_AUTHORITY_MISMATCH,
            D3BExecutionPhase.AUTHORITY,
            cause=exc,
        )
    if not authority_matches:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_AUTHORITY_MISMATCH,
            D3BExecutionPhase.AUTHORITY,
        )
    try:
        scenario_path = _resolve_authorized_file(scenario_authority, binding)
    except (MemoryError, OSError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_PATH_INVALID,
            D3BExecutionPhase.AUTHORITY,
            cause=exc,
        )
    try:
        source_bytes, source_digest, source_stat = _file_receipt(scenario_path)
    except (MemoryError, OSError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.SCENARIO_FILE_UNAVAILABLE,
            D3BExecutionPhase.AUTHORITY,
            cause=exc,
        )
    if source_digest != request.base_scenario.source_file_sha256:
        return _failure(
            request_id,
            D3BFailureCode.SOURCE_FILE_DIGEST_MISMATCH,
            D3BExecutionPhase.AUTHORITY,
        )

    try:
        from analytics.scenario_loader import load_scenario_config

        config = load_scenario_config(
            scenario_path,
            verified_bytes=source_bytes,
            allow_external_approved_sources=False,
        )
    except Exception as exc:
        return _failure(
            request_id,
            D3BFailureCode.CONFIG_LOAD_FAILED,
            D3BExecutionPhase.CONFIG_LOAD,
            cause=exc,
        )
    try:
        _, after_digest, after_stat = _file_receipt(scenario_path)
        loaded_digest = resolved_config_sha256(config)
    except Exception as exc:
        return _failure(
            request_id,
            D3BFailureCode.CONFIG_LOAD_FAILED,
            D3BExecutionPhase.CONFIG_LOAD,
            cause=exc,
        )
    if (after_digest, after_stat) != (source_digest, source_stat):
        return _failure(
            request_id,
            D3BFailureCode.CONFIG_CHANGED_DURING_LOAD,
            D3BExecutionPhase.CONFIG_LOAD,
        )
    if loaded_digest != request.base_scenario.resolved_config_sha256:
        return _failure(
            request_id,
            D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH,
            D3BExecutionPhase.CONFIG_LOAD,
        )
    try:
        authored_source_path = _nested(config, "meta", "source_path")
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH,
            D3BExecutionPhase.CONFIG_LOAD,
            cause=exc,
        )
    if authored_source_path != binding.repository_relative_path:
        return _failure(
            request_id,
            D3BFailureCode.RESOLVED_CONFIG_DIGEST_MISMATCH,
            D3BExecutionPhase.CONFIG_LOAD,
        )
    try:
        from analytics.schema_guard import validate_config_for_v14

        validate_config_for_v14(
            config,
            binding.repository_relative_path,
            [item.value for item in request.validation_modules],
        )
    except Exception as exc:
        return _failure(
            request_id,
            D3BFailureCode.CONFIG_VALIDATION_FAILED,
            D3BExecutionPhase.CONFIG_LOAD,
            cause=exc,
        )

    try:
        counts = _live_material_counts(project_case)
        unbound_material_present = any(
            disposition.disposition is MaterialDispositionKind.REFUSE_UNBOUND
            and counts[disposition.category]
            for disposition in request.binding_policy.material_dispositions
        )
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.COMPATIBILITY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )
    if unbound_material_present:
        return _failure(
            request_id,
            D3BFailureCode.UNBOUND_MATERIAL_PRESENT,
            D3BExecutionPhase.COMPATIBILITY,
        )
    try:
        live_element_sets_match = _live_element_sets_match(project_case, request)
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.PROJECT_CASE_ELEMENT_SET_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )
    if not live_element_sets_match:
        return _failure(
            request_id,
            D3BFailureCode.PROJECT_CASE_ELEMENT_SET_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        )
    try:
        authored_redundancies_match = _authored_redundancies_match(config, request)
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.AUTHORED_REDUNDANCY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )
    except (InvalidOperation, IndexError, TypeError, ValueError):
        authored_redundancies_match = False
    if not authored_redundancies_match:
        return _failure(
            request_id,
            D3BFailureCode.AUTHORED_REDUNDANCY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        )
    try:
        numeric_projection_receipts = _compatibility_receipts(
            project_case, request, config
        )
    except _MissingMaterialValue as exc:
        return _failure(
            request_id,
            D3BFailureCode.MISSING_MATERIAL_VALUE,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )
    except MemoryError as exc:
        return _failure(
            request_id,
            D3BFailureCode.COMPATIBILITY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )
    except (InvalidOperation, TypeError, ValueError):
        numeric_projection_receipts = None
    if numeric_projection_receipts is None:
        return _failure(
            request_id,
            D3BFailureCode.COMPATIBILITY_MISMATCH,
            D3BExecutionPhase.COMPATIBILITY,
        )
    try:
        overrides, evaluated_config = _run_mode_plan(config, request)
        evaluated_digest = resolved_config_sha256(evaluated_config)
    except (MemoryError, TypeError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.RUN_POSTURE_INVALID,
            D3BExecutionPhase.COMPATIBILITY,
            cause=exc,
        )

    try:
        from analytics.evaluation_v14 import evaluate_with_overrides

        raw_result = evaluate_with_overrides(
            raw_config=config,
            overrides=overrides,
            validation_modules=[item.value for item in request.validation_modules],
            return_full_result=True,
        )
    except Exception as exc:
        return _failure(
            request_id,
            D3BFailureCode.GATEWAY_FAILED,
            D3BExecutionPhase.GATEWAY,
            gateway_call_count=1,
            cause=exc,
        )

    try:
        full_result, run_manifest, warnings, fx_degraded = _validate_gateway_result(
            raw_result, evaluated_digest
        )
    except RuntimeError as exc:
        return _failure(
            request_id,
            D3BFailureCode.RUN_MANIFEST_DIGEST_MISMATCH,
            D3BExecutionPhase.RESULT_PROTOCOL,
            gateway_call_count=1,
            cause=exc,
        )
    except (MemoryError, TypeError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.GATEWAY_PROTOCOL_INVALID,
            D3BExecutionPhase.RESULT_PROTOCOL,
            gateway_call_count=1,
            cause=exc,
        )

    try:
        return D3BExecutionSuccess(
            request_id=request.request_id,
            project_id=project_case.identity.project_id,
            case_id=project_case.identity.case_id,
            project_case_revision=project_case.identity.revision,
            project_case_sha256=binding.project_case_sha256,
            evaluation_request_sha256=binding.evaluation_request_sha256,
            authority_id=scenario_authority.authority_id,
            config_id=request.base_scenario.config_id,
            source_file_sha256=source_digest,
            resolved_config_sha256=loaded_digest,
            evaluated_config_sha256=evaluated_digest,
            evidence_cutoff=request.scope.evidence_cutoff,
            valuation_date=request.scope.valuation_date,
            validation_modules=tuple(item.value for item in request.validation_modules),
            numeric_projection_receipts=numeric_projection_receipts,
            gateway_call_count=1,
            full_result=full_result,
            run_manifest=run_manifest,
            warnings=warnings,
            fx_degraded=fx_degraded,
            outcome="degraded_success" if fx_degraded or warnings else "success",
        )
    except (MemoryError, TypeError, ValueError) as exc:
        return _failure(
            request_id,
            D3BFailureCode.RESULT_SNAPSHOT_FAILED,
            D3BExecutionPhase.RESULT_PROTOCOL,
            gateway_call_count=1,
            cause=exc,
        )


__all__ = ["execute_evaluation_request"]
