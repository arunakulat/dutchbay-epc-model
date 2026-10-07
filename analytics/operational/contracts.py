"""Frozen post-COD operational-evidence envelope (#1331 D1).

This module defines the dependency-free boundary for evidence that may later feed
operational AEP and loss analyses.  Its vocabulary follows the data categories and
analysis minima in OpenOA v3.2 (SCADA, meter, tower, curtailment, reanalysis, and
asset metadata), but it neither imports OpenOA nor claims equivalence with an OpenOA
``PlantData`` object.

The contract describes *evidence*, not an assessment result.  It cannot populate a
canonical capacity factor, AEP, finance scenario, lender pack, or Board pack.  Later
dolphins may normalize source tables and calculate non-canonical results only after
this envelope has failed loud on ambiguous time, units, provenance, and scope.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Final, Literal, Mapping, TypeAlias

OPERATIONAL_EVIDENCE_SCHEMA: Final = "dutchbay.operational_evidence.v1"

OperationalDatasetKind: TypeAlias = Literal[
    "scada",
    "revenue_meter",
    "met_tower",
    "status",
    "curtailment",
    "reanalysis",
    "asset",
]
OperationalAnalysisPurpose: TypeAlias = Literal[
    "long_term_aep",
    "turbine_gross_energy",
    "electrical_losses",
    "wake_losses_scada",
    "wake_losses_tower",
]
OperationalSourceClass: TypeAlias = Literal[
    "observed_plant",
    "reference_reanalysis",
    "declared_asset",
]

_DATASET_KINDS = frozenset(
    {
        "scada",
        "revenue_meter",
        "met_tower",
        "status",
        "curtailment",
        "reanalysis",
        "asset",
    }
)
_ANALYSIS_PURPOSES = frozenset(
    {
        "long_term_aep",
        "turbine_gross_energy",
        "electrical_losses",
        "wake_losses_scada",
        "wake_losses_tower",
    }
)
_SOURCE_CLASS_BY_KIND: Mapping[str, str] = MappingProxyType(
    {
        "scada": "observed_plant",
        "revenue_meter": "observed_plant",
        "met_tower": "observed_plant",
        "status": "observed_plant",
        "curtailment": "observed_plant",
        "reanalysis": "reference_reanalysis",
        "asset": "declared_asset",
    }
)

# Canonical semantic roles and the only units D1 admits.  D2 may convert source
# units into these roles, but no implicit conversion happens at this boundary.
_ROLE_UNITS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "timestamp_utc": frozenset({"iso8601_utc"}),
        "asset_id": frozenset({"1"}),
        "status_code": frozenset({"1"}),
        "energy_kwh": frozenset({"kWh"}),
        "power_kw": frozenset({"kW"}),
        "wind_speed_ms": frozenset({"m/s"}),
        "wind_direction_deg": frozenset({"degree"}),
        "air_density_kgm3": frozenset({"kg/m^3"}),
        "air_temperature_c": frozenset({"degC"}),
        "availability_loss_kwh": frozenset({"kWh"}),
        "curtailment_loss_kwh": frozenset({"kWh"}),
        "rated_power_kw": frozenset({"kW"}),
        "latitude_deg": frozenset({"degree_north"}),
        "longitude_deg": frozenset({"degree_east"}),
    }
)

_ALLOWED_ROLES_BY_KIND: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "scada": frozenset(
            {
                "timestamp_utc",
                "asset_id",
                "status_code",
                "energy_kwh",
                "power_kw",
                "wind_speed_ms",
                "wind_direction_deg",
                "air_density_kgm3",
                "air_temperature_c",
            }
        ),
        "revenue_meter": frozenset({"timestamp_utc", "energy_kwh", "power_kw"}),
        "met_tower": frozenset(
            {
                "timestamp_utc",
                "asset_id",
                "wind_speed_ms",
                "wind_direction_deg",
                "air_density_kgm3",
                "air_temperature_c",
            }
        ),
        "status": frozenset({"timestamp_utc", "asset_id", "status_code"}),
        "curtailment": frozenset(
            {"timestamp_utc", "availability_loss_kwh", "curtailment_loss_kwh"}
        ),
        "reanalysis": frozenset(
            {
                "timestamp_utc",
                "wind_speed_ms",
                "wind_direction_deg",
                "air_density_kgm3",
                "air_temperature_c",
            }
        ),
        "asset": frozenset(
            {"asset_id", "rated_power_kw", "latitude_deg", "longitude_deg"}
        ),
    }
)

# Minimum evidence sets mirror OpenOA v3.2 ANALYSIS_REQUIREMENTS, translated to
# DutchBay names.  Status data is representable but is not fabricated as a minimum
# for analyses whose upstream comparator does not require it.
OPERATIONAL_REQUIRED_DATASET_KINDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "long_term_aep": frozenset({"revenue_meter", "curtailment", "reanalysis"}),
        "turbine_gross_energy": frozenset({"scada", "reanalysis", "asset"}),
        "electrical_losses": frozenset({"scada", "revenue_meter"}),
        "wake_losses_scada": frozenset({"scada", "reanalysis", "asset"}),
        "wake_losses_tower": frozenset({"scada", "met_tower", "reanalysis", "asset"}),
    }
)

OPERATIONAL_REQUIRED_ROLES: Mapping[str, Mapping[str, frozenset[str]]] = (
    MappingProxyType(
        {
            "long_term_aep": MappingProxyType(
                {
                    "revenue_meter": frozenset({"timestamp_utc", "energy_kwh"}),
                    "curtailment": frozenset(
                        {
                            "timestamp_utc",
                            "availability_loss_kwh",
                            "curtailment_loss_kwh",
                        }
                    ),
                    "reanalysis": frozenset(
                        {"timestamp_utc", "wind_speed_ms", "air_density_kgm3"}
                    ),
                }
            ),
            "turbine_gross_energy": MappingProxyType(
                {
                    "scada": frozenset(
                        {"timestamp_utc", "asset_id", "wind_speed_ms", "power_kw"}
                    ),
                    "reanalysis": frozenset(
                        {
                            "timestamp_utc",
                            "wind_speed_ms",
                            "wind_direction_deg",
                            "air_density_kgm3",
                        }
                    ),
                    "asset": frozenset({"asset_id", "rated_power_kw"}),
                }
            ),
            "electrical_losses": MappingProxyType(
                {
                    "scada": frozenset({"timestamp_utc", "asset_id", "power_kw"}),
                    "revenue_meter": frozenset({"timestamp_utc", "energy_kwh"}),
                }
            ),
            "wake_losses_scada": MappingProxyType(
                {
                    "scada": frozenset(
                        {
                            "timestamp_utc",
                            "asset_id",
                            "wind_speed_ms",
                            "wind_direction_deg",
                            "power_kw",
                        }
                    ),
                    "reanalysis": frozenset(
                        {"timestamp_utc", "wind_speed_ms", "wind_direction_deg"}
                    ),
                    "asset": frozenset(
                        {"asset_id", "latitude_deg", "longitude_deg", "rated_power_kw"}
                    ),
                }
            ),
            "wake_losses_tower": MappingProxyType(
                {
                    "scada": frozenset(
                        {"timestamp_utc", "asset_id", "wind_speed_ms", "power_kw"}
                    ),
                    "met_tower": frozenset(
                        {"timestamp_utc", "asset_id", "wind_direction_deg"}
                    ),
                    "reanalysis": frozenset(
                        {"timestamp_utc", "wind_speed_ms", "wind_direction_deg"}
                    ),
                    "asset": frozenset(
                        {"asset_id", "latitude_deg", "longitude_deg", "rated_power_kw"}
                    ),
                }
            ),
        }
    )
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


class OperationalEvidenceError(ValueError):
    """Raised when operational evidence is ambiguous or internally inconsistent."""


def _require_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise OperationalEvidenceError(
            f"{field_name} must match {_IDENTIFIER_RE.pattern!r}; got {value!r}."
        )
    return value


def _parse_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise OperationalEvidenceError(
            f"{field_name} must be an RFC3339 UTC timestamp ending in 'Z'; got {value!r}."
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OperationalEvidenceError(
            f"{field_name} is not a valid UTC timestamp: {value!r}."
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise OperationalEvidenceError(f"{field_name} must resolve to UTC.")
    return parsed


@dataclass(frozen=True)
class OperationalColumnBinding:
    """Bind one source column to a closed, unit-bearing semantic role."""

    role: str
    source_column: str
    unit: str

    def __post_init__(self) -> None:
        if self.role not in _ROLE_UNITS:
            raise OperationalEvidenceError(
                f"Unsupported operational column role {self.role!r}; "
                f"choose from {sorted(_ROLE_UNITS)}."
            )
        if (
            not isinstance(self.source_column, str)
            or not self.source_column
            or self.source_column.strip() != self.source_column
        ):
            raise OperationalEvidenceError(
                "source_column must be a non-empty string without surrounding whitespace."
            )
        if self.unit not in _ROLE_UNITS[self.role]:
            raise OperationalEvidenceError(
                f"Role {self.role!r} requires one of {sorted(_ROLE_UNITS[self.role])}; "
                f"got unit {self.unit!r}."
            )

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(frozen=True)
class OperationalDatasetEvidence:
    """Provenance and semantic mapping for one logical operational dataset."""

    logical_id: str
    kind: OperationalDatasetKind
    source_class: OperationalSourceClass
    source_locator: str
    source_sha256: str
    coverage_start_utc: str
    coverage_end_utc: str
    interval_seconds: int | None
    row_count: int
    columns: tuple[OperationalColumnBinding, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.logical_id, "logical_id")
        if self.kind not in _DATASET_KINDS:
            raise OperationalEvidenceError(
                f"kind must be one of {sorted(_DATASET_KINDS)}; got {self.kind!r}."
            )
        expected_class = _SOURCE_CLASS_BY_KIND[self.kind]
        if self.source_class != expected_class:
            raise OperationalEvidenceError(
                f"kind {self.kind!r} requires source_class {expected_class!r}; "
                f"got {self.source_class!r}."
            )
        if (
            not isinstance(self.source_locator, str)
            or not self.source_locator
            or self.source_locator.strip() != self.source_locator
        ):
            raise OperationalEvidenceError(
                "source_locator must be a non-empty string without surrounding whitespace."
            )
        if (
            not isinstance(self.source_sha256, str)
            or _SHA256_RE.fullmatch(self.source_sha256) is None
        ):
            raise OperationalEvidenceError(
                "source_sha256 must be exactly 64 lowercase hexadecimal characters."
            )
        start = _parse_utc(self.coverage_start_utc, "coverage_start_utc")
        end = _parse_utc(self.coverage_end_utc, "coverage_end_utc")
        if start >= end:
            raise OperationalEvidenceError(
                "coverage_start_utc must be earlier than coverage_end_utc."
            )
        if self.kind == "asset":
            if self.interval_seconds is not None:
                raise OperationalEvidenceError(
                    "asset metadata is non-timeseries evidence and requires "
                    "interval_seconds=None."
                )
        elif type(self.interval_seconds) is not int or self.interval_seconds <= 0:
            raise OperationalEvidenceError(
                "timeseries interval_seconds must be a real integer > 0."
            )
        if type(self.row_count) is not int or self.row_count <= 0:
            raise OperationalEvidenceError("row_count must be a real integer > 0.")
        if not isinstance(self.columns, tuple) or not self.columns:
            raise OperationalEvidenceError("columns must be a non-empty tuple.")
        if not all(isinstance(item, OperationalColumnBinding) for item in self.columns):
            raise OperationalEvidenceError(
                "columns must contain only OperationalColumnBinding instances."
            )
        roles = [item.role for item in self.columns]
        source_columns = [item.source_column for item in self.columns]
        invalid_roles = sorted(set(roles) - _ALLOWED_ROLES_BY_KIND[self.kind])
        if invalid_roles:
            raise OperationalEvidenceError(
                f"Dataset kind {self.kind!r} does not admit roles {invalid_roles}."
            )
        if len(roles) != len(set(roles)):
            raise OperationalEvidenceError(
                f"Dataset {self.logical_id!r} contains duplicate semantic roles."
            )
        if len(source_columns) != len(set(source_columns)):
            raise OperationalEvidenceError(
                f"Dataset {self.logical_id!r} maps one source column more than once."
            )

    @property
    def roles(self) -> frozenset[str]:
        return frozenset(item.role for item in self.columns)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(frozen=True)
class OperationalAssessmentInput:
    """Immutable evidence envelope for one declared operational analysis purpose.

    The hard-false classification fields are an honesty fence.  They are runtime
    validated because ``Literal`` annotations alone do not prevent laundering via
    ``dataclasses.replace`` or untyped callers.
    """

    schema: str
    project_id: str
    assessment_id: str
    purpose: OperationalAnalysisPurpose
    assessment_start_utc: str
    assessment_end_utc: str
    datasets: tuple[OperationalDatasetEvidence, ...]
    raw_evidence_only: Literal[True] = True
    canonical_finance_eligible: Literal[False] = False
    bankable: Literal[False] = False
    lender_eligible: Literal[False] = False
    board_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        if self.schema != OPERATIONAL_EVIDENCE_SCHEMA:
            raise OperationalEvidenceError(
                f"schema must equal {OPERATIONAL_EVIDENCE_SCHEMA!r}; got {self.schema!r}."
            )
        _require_identifier(self.project_id, "project_id")
        _require_identifier(self.assessment_id, "assessment_id")
        if self.purpose not in _ANALYSIS_PURPOSES:
            raise OperationalEvidenceError(
                f"purpose must be one of {sorted(_ANALYSIS_PURPOSES)}; "
                f"got {self.purpose!r}."
            )
        start = _parse_utc(self.assessment_start_utc, "assessment_start_utc")
        end = _parse_utc(self.assessment_end_utc, "assessment_end_utc")
        if start >= end:
            raise OperationalEvidenceError(
                "assessment_start_utc must be earlier than assessment_end_utc."
            )
        if not isinstance(self.datasets, tuple) or not self.datasets:
            raise OperationalEvidenceError("datasets must be a non-empty tuple.")
        if not all(
            isinstance(item, OperationalDatasetEvidence) for item in self.datasets
        ):
            raise OperationalEvidenceError(
                "datasets must contain only OperationalDatasetEvidence instances."
            )
        logical_ids = [item.logical_id for item in self.datasets]
        if len(logical_ids) != len(set(logical_ids)):
            raise OperationalEvidenceError("dataset logical_id values must be unique.")

        required_kinds = OPERATIONAL_REQUIRED_DATASET_KINDS[self.purpose]
        present_kinds = {item.kind for item in self.datasets}
        missing_kinds = sorted(required_kinds - present_kinds)
        if missing_kinds:
            raise OperationalEvidenceError(
                f"purpose {self.purpose!r} is missing required dataset kinds "
                f"{missing_kinds}."
            )

        required_roles = OPERATIONAL_REQUIRED_ROLES[self.purpose]
        for kind, roles in required_roles.items():
            matching = [item for item in self.datasets if item.kind == kind]
            available = frozenset().union(*(item.roles for item in matching))
            missing_roles = sorted(roles - available)
            if missing_roles:
                raise OperationalEvidenceError(
                    f"purpose {self.purpose!r}, kind {kind!r} is missing roles "
                    f"{missing_roles}."
                )
            for dataset in matching:
                dataset_start = _parse_utc(
                    dataset.coverage_start_utc, "coverage_start_utc"
                )
                dataset_end = _parse_utc(dataset.coverage_end_utc, "coverage_end_utc")
                if dataset_start > start or dataset_end < end:
                    raise OperationalEvidenceError(
                        f"Required dataset {dataset.logical_id!r} does not cover the "
                        "declared assessment window."
                    )

        exact_flags = {
            "raw_evidence_only": True,
            "canonical_finance_eligible": False,
            "bankable": False,
            "lender_eligible": False,
            "board_eligible": False,
        }
        for field_name, expected in exact_flags.items():
            value = getattr(self, field_name)
            if type(value) is not bool or value is not expected:
                raise OperationalEvidenceError(
                    f"{field_name} must be the exact boolean {expected!r}."
                )

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


__all__ = [
    "OPERATIONAL_EVIDENCE_SCHEMA",
    "OPERATIONAL_REQUIRED_DATASET_KINDS",
    "OPERATIONAL_REQUIRED_ROLES",
    "OperationalAnalysisPurpose",
    "OperationalAssessmentInput",
    "OperationalColumnBinding",
    "OperationalDatasetEvidence",
    "OperationalDatasetKind",
    "OperationalEvidenceError",
    "OperationalSourceClass",
]
