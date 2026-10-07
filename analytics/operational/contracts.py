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
OperationalTimezoneTreatment: TypeAlias = Literal[
    "source_utc",
    "offset_aware_to_utc",
    "named_zone_to_utc",
    "not_applicable",
]
OperationalObservationStatus: TypeAlias = Literal[
    "observed",
    "reference_reanalysis",
    "declared_metadata",
]
OperationalIntervalBasis: TypeAlias = Literal[
    "fixed_seconds",
    "calendar_month",
    "not_applicable",
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
_SOURCE_CLASSES = frozenset(_SOURCE_CLASS_BY_KIND.values())
_TIMEZONE_TREATMENTS = frozenset(
    {
        "source_utc",
        "offset_aware_to_utc",
        "named_zone_to_utc",
        "not_applicable",
    }
)
_TIMESERIES_TIMEZONE_TREATMENTS = _TIMEZONE_TREATMENTS - {"not_applicable"}
_OBSERVATION_STATUS_BY_KIND: Mapping[str, str] = MappingProxyType(
    {
        "scada": "observed",
        "revenue_meter": "observed",
        "met_tower": "observed",
        "status": "observed",
        "curtailment": "observed",
        "reanalysis": "reference_reanalysis",
        "asset": "declared_metadata",
    }
)
_OBSERVATION_STATUSES = frozenset(_OBSERVATION_STATUS_BY_KIND.values())
_INTERVAL_BASES = frozenset({"fixed_seconds", "calendar_month", "not_applicable"})
_CALENDAR_MONTH_CAPABLE_KINDS = frozenset(
    {"revenue_meter", "curtailment", "reanalysis"}
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

# Maximum declared cadence for each required purpose/kind pair. Calendar-month
# inputs are admitted only for pairs listed separately below because a calendar
# month has no single truthful duration in seconds. D2 validates actual timestamps.
OPERATIONAL_MAX_INTERVAL_SECONDS: Mapping[str, Mapping[str, int | None]] = (
    MappingProxyType(
        {
            "long_term_aep": MappingProxyType(
                {
                    "revenue_meter": 31 * 86_400,
                    "curtailment": 31 * 86_400,
                    "reanalysis": 31 * 86_400,
                }
            ),
            "turbine_gross_energy": MappingProxyType(
                {"scada": 86_400, "reanalysis": 86_400, "asset": None}
            ),
            "electrical_losses": MappingProxyType(
                {"scada": 86_400, "revenue_meter": 31 * 86_400}
            ),
            "wake_losses_scada": MappingProxyType(
                {"scada": 3_600, "reanalysis": 3_600, "asset": None}
            ),
            "wake_losses_tower": MappingProxyType(
                {
                    "scada": 3_600,
                    "met_tower": 3_600,
                    "reanalysis": 3_600,
                    "asset": None,
                }
            ),
        }
    )
)

OPERATIONAL_CALENDAR_MONTH_ALLOWED: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "long_term_aep": frozenset({"revenue_meter", "curtailment", "reanalysis"}),
        "turbine_gross_energy": frozenset(),
        "electrical_losses": frozenset({"revenue_meter"}),
        "wake_losses_scada": frozenset(),
        "wake_losses_tower": frozenset(),
    }
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


def _require_closed_string(
    value: object, field_name: str, allowed: frozenset[str]
) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise OperationalEvidenceError(
            f"{field_name} must be one of {sorted(allowed)}; got {value!r}."
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
        _require_closed_string(self.role, "role", frozenset(_ROLE_UNITS))
        if (
            not isinstance(self.source_column, str)
            or not self.source_column
            or self.source_column.strip() != self.source_column
        ):
            raise OperationalEvidenceError(
                "source_column must be a non-empty string without surrounding whitespace."
            )
        allowed_units = _ROLE_UNITS[self.role]
        if not isinstance(self.unit, str) or self.unit not in allowed_units:
            raise OperationalEvidenceError(
                f"Role {self.role!r} requires one of {sorted(allowed_units)}; "
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
    timezone_treatment: OperationalTimezoneTreatment
    observation_status: OperationalObservationStatus
    source_locator: str
    source_sha256: str
    coverage_start_utc: str
    coverage_end_utc: str
    interval_basis: OperationalIntervalBasis
    interval_seconds: int | None
    row_count: int
    columns: tuple[OperationalColumnBinding, ...]

    def __post_init__(self) -> None:
        _require_identifier(self.logical_id, "logical_id")
        _require_closed_string(self.kind, "kind", _DATASET_KINDS)
        expected_class = _SOURCE_CLASS_BY_KIND[self.kind]
        _require_closed_string(self.source_class, "source_class", _SOURCE_CLASSES)
        if self.source_class != expected_class:
            raise OperationalEvidenceError(
                f"kind {self.kind!r} requires source_class {expected_class!r}; "
                f"got {self.source_class!r}."
            )
        _require_closed_string(
            self.timezone_treatment, "timezone_treatment", _TIMEZONE_TREATMENTS
        )
        if self.kind == "asset":
            if self.timezone_treatment != "not_applicable":
                raise OperationalEvidenceError(
                    "asset metadata requires timezone_treatment='not_applicable'."
                )
        elif self.timezone_treatment not in _TIMESERIES_TIMEZONE_TREATMENTS:
            raise OperationalEvidenceError(
                "timeseries evidence requires an explicit UTC normalization treatment."
            )
        expected_status = _OBSERVATION_STATUS_BY_KIND[self.kind]
        _require_closed_string(
            self.observation_status, "observation_status", _OBSERVATION_STATUSES
        )
        if self.observation_status != expected_status:
            raise OperationalEvidenceError(
                f"kind {self.kind!r} requires observation_status "
                f"{expected_status!r}; got {self.observation_status!r}."
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
        _require_closed_string(self.interval_basis, "interval_basis", _INTERVAL_BASES)
        if self.kind == "asset":
            if (
                self.interval_basis != "not_applicable"
                or self.interval_seconds is not None
            ):
                raise OperationalEvidenceError(
                    "asset metadata is non-timeseries evidence and requires "
                    "interval_basis='not_applicable' and interval_seconds=None."
                )
        elif self.interval_basis == "fixed_seconds":
            if type(self.interval_seconds) is not int or self.interval_seconds <= 0:
                raise OperationalEvidenceError(
                    "fixed_seconds evidence requires interval_seconds as a real integer > 0."
                )
        elif self.interval_basis == "calendar_month":
            if self.kind not in _CALENDAR_MONTH_CAPABLE_KINDS:
                raise OperationalEvidenceError(
                    f"kind {self.kind!r} does not admit calendar-month evidence."
                )
            if self.interval_seconds is not None:
                raise OperationalEvidenceError(
                    "calendar_month evidence requires interval_seconds=None because "
                    "calendar months have variable duration."
                )
        else:
            raise OperationalEvidenceError(
                "timeseries evidence requires interval_basis='fixed_seconds' or "
                "'calendar_month'."
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
        _require_closed_string(self.purpose, "purpose", _ANALYSIS_PURPOSES)
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
            complete = [item for item in matching if roles.issubset(item.roles)]
            if not complete:
                raise OperationalEvidenceError(
                    f"purpose {self.purpose!r}, kind {kind!r} requires at least one "
                    f"individually complete logical dataset with roles {sorted(roles)}."
                )
            for dataset in matching:
                max_interval = OPERATIONAL_MAX_INTERVAL_SECONDS[self.purpose][kind]
                if dataset.interval_basis == "calendar_month":
                    if kind not in OPERATIONAL_CALENDAR_MONTH_ALLOWED[self.purpose]:
                        raise OperationalEvidenceError(
                            f"purpose {self.purpose!r}, kind {kind!r} does not admit "
                            "calendar-month evidence."
                        )
                elif (
                    max_interval is not None
                    and dataset.interval_seconds is not None
                    and dataset.interval_seconds > max_interval
                ):
                    raise OperationalEvidenceError(
                        f"purpose {self.purpose!r}, kind {kind!r} requires "
                        f"interval_seconds <= {max_interval}; got "
                        f"{dataset.interval_seconds}."
                    )
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
    "OPERATIONAL_CALENDAR_MONTH_ALLOWED",
    "OPERATIONAL_EVIDENCE_SCHEMA",
    "OPERATIONAL_MAX_INTERVAL_SECONDS",
    "OPERATIONAL_REQUIRED_DATASET_KINDS",
    "OPERATIONAL_REQUIRED_ROLES",
    "OperationalAnalysisPurpose",
    "OperationalAssessmentInput",
    "OperationalColumnBinding",
    "OperationalDatasetEvidence",
    "OperationalDatasetKind",
    "OperationalEvidenceError",
    "OperationalIntervalBasis",
    "OperationalObservationStatus",
    "OperationalSourceClass",
    "OperationalTimezoneTreatment",
]
