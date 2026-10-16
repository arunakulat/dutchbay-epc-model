"""Deterministic non-canonical operational energy accounting (#1333 D3).

The estimator reconciles D2-normalized, matched-period meter, turbine,
availability, and curtailment evidence with exact rational arithmetic.  It can
also represent separately provenance-bound resource-gross and combined
wake/performance energy.  It never infers either quantity from reanalysis data,
and it never estimates long-term-average energy or uncertainty.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from typing import Any, Final, Literal, TypeAlias
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from analytics.operational.contracts import OperationalAssessmentInput
from analytics.operational.normalization import (
    OperationalNormalizationError,
    OperationalNormalizationResult,
    OperationalRowExclusion,
    normalize_operational_csv,
)

OPERATIONAL_AEP_SCHEMA: Final = "dutchbay.operational_aep.v1"
_AEP_METHOD_VERSION: Final = "operational_energy_reconciliation_v1"
_AEP_RESULT_TOKEN: Final = object()
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_MAX_NUMERIC_CHARACTERS: Final = 4_096
_MAX_PROVENANCE_BYTES: Final = 1_048_576
_MAX_INTEGER_BITS: Final = 16_384

OperationalAEPErrorCode: TypeAlias = Literal[
    "INVALID_INPUT",
    "SELECTOR_AMBIGUITY",
    "PROVENANCE_MISMATCH",
    "BOUNDARY_MISMATCH",
    "INTERVAL_MISMATCH",
    "UNSUPPORTED_EVIDENCE",
    "ENERGY_IDENTITY_FAILED",
]
OperationalTemporalBasis: TypeAlias = Literal[
    "observed_period_total", "actual_calendar_year"
]
OperationalEnergyComponentName: TypeAlias = Literal[
    "net_meter_energy",
    "turbine_terminal_energy",
    "availability_loss",
    "electrical_loss",
    "curtailment_loss",
    "meter_loss_restored_gross",
    "turbine_known_gross",
    "resource_gross_energy",
    "wake_performance_loss",
    "unknown_residual_loss",
    "long_term_average_energy",
]
OperationalSupplementalComponent: TypeAlias = Literal[
    "resource_gross_energy", "wake_performance_loss"
]
OperationalComponentStatus: TypeAlias = Literal["available", "unavailable"]

_COMPONENT_NAMES = frozenset(
    {
        "net_meter_energy",
        "turbine_terminal_energy",
        "availability_loss",
        "electrical_loss",
        "curtailment_loss",
        "meter_loss_restored_gross",
        "turbine_known_gross",
        "resource_gross_energy",
        "wake_performance_loss",
        "unknown_residual_loss",
        "long_term_average_energy",
    }
)
_SUPPLEMENTAL_COMPONENTS = frozenset({"resource_gross_energy", "wake_performance_loss"})
_D2_SOURCE_ROLES = frozenset(
    {
        "net_meter_energy",
        "turbine_terminal_energy",
        "availability_loss",
        "curtailment_loss",
    }
)
_AEP_SOURCE_ROLES = _D2_SOURCE_ROLES | _SUPPLEMENTAL_COMPONENTS


class OperationalAEPError(ValueError):
    """Raised when operational energy inputs cannot be reconciled safely."""

    code: OperationalAEPErrorCode

    def __init__(self, code: OperationalAEPErrorCode, message: str) -> None:
        """Initialize a closed operational-energy failure."""
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class OperationalEnergyQuantity:
    """An exact reduced rational quantity denominated in kWh."""

    numerator: int
    denominator: int = 1
    unit: Literal["kWh"] = "kWh"

    def __post_init__(self) -> None:
        """Validate canonical reduced rational representation."""
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("energy numerator and denominator must be real integers.")
        if self.denominator <= 0:
            raise ValueError("energy denominator must be positive.")
        if self.unit != "kWh":
            raise ValueError("operational energy quantities must use kWh.")
        if self.numerator.bit_length() > _MAX_INTEGER_BITS or (
            self.denominator.bit_length() > _MAX_INTEGER_BITS
        ):
            raise ValueError(
                "energy quantity exceeds the bounded exact representation."
            )
        if math.gcd(self.numerator, self.denominator) != 1:
            raise ValueError("energy quantity must be in lowest terms.")

    @classmethod
    def from_fraction(cls, value: Fraction) -> OperationalEnergyQuantity:
        """Construct a canonical quantity from an exact fraction."""
        if not isinstance(value, Fraction):
            raise ValueError("value must be Fraction.")
        return cls(value.numerator, value.denominator)

    def as_fraction(self) -> Fraction:
        """Return the exact standard-library fraction."""
        return Fraction(self.numerator, self.denominator)

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible exact representation."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalEnergyComponent:
    """One available exact energy value or one explicit unavailable state."""

    name: OperationalEnergyComponentName
    status: OperationalComponentStatus
    value: OperationalEnergyQuantity | None
    evidence_ids: tuple[str, ...]
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        """Keep evidenced zero structurally distinct from unavailable data."""
        if not isinstance(self.name, str) or self.name not in _COMPONENT_NAMES:
            raise ValueError("energy component name is not supported.")
        if self.status == "available":
            if not isinstance(self.value, OperationalEnergyQuantity):
                raise ValueError("available energy components require an exact value.")
            if self.unavailable_reason is not None or not self.evidence_ids:
                raise ValueError(
                    "available energy components require evidence and no unavailable reason."
                )
        elif self.status == "unavailable":
            if self.value is not None or self.evidence_ids:
                raise ValueError(
                    "unavailable energy components cannot carry a value or evidence IDs."
                )
            _require_text(self.unavailable_reason, "unavailable_reason")
        else:
            raise ValueError("component status must be 'available' or 'unavailable'.")
        if not isinstance(self.evidence_ids, tuple) or any(
            not isinstance(item, str) or _IDENTIFIER_RE.fullmatch(item) is None
            for item in self.evidence_ids
        ):
            raise ValueError("evidence_ids must be a tuple of closed identifiers.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible component representation."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalRatio:
    """One exact dimensionless ratio or an explicit unavailable state."""

    name: str
    status: OperationalComponentStatus
    numerator: int | None
    denominator: int | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        """Validate a reduced exact ratio without floating-point conversion."""
        _require_identifier(self.name, "ratio name")
        if self.status == "available":
            if type(self.numerator) is not int or type(self.denominator) is not int:
                raise ValueError("available ratios require integer terms.")
            if self.denominator <= 0 or math.gcd(self.numerator, self.denominator) != 1:
                raise ValueError(
                    "available ratios require a positive reduced denominator."
                )
            if self.unavailable_reason is not None:
                raise ValueError("available ratios cannot carry an unavailable reason.")
        elif self.status == "unavailable":
            if self.numerator is not None or self.denominator is not None:
                raise ValueError("unavailable ratios cannot carry numeric terms.")
            _require_text(self.unavailable_reason, "unavailable_reason")
        else:
            raise ValueError("ratio status must be 'available' or 'unavailable'.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible exact ratio representation."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalBoundaryEvidence:
    """Caller-attested matched plant boundary and interval semantics."""

    project_id: str
    effective_start_utc: str
    effective_end_exclusive_utc: str
    meter_logical_id: str
    turbine_logical_id: str
    availability_logical_id: str
    curtailment_logical_id: str
    meter_energy_basis: Literal["net_export_interval_energy"]
    turbine_energy_basis: Literal["complete_turbine_terminal_interval_energy"]
    loss_energy_basis: Literal["non_overlapping_positive_reduction_energy"]
    interval_boundary: Literal["interval_start_end_exclusive"]
    excluded_flows: Literal["imports_storage_solar_and_shared_poc_excluded"]
    asset_universe_basis: Literal["d2_verified_complete"]
    source_locator: str
    source_bytes: bytes
    source_sha256: str
    method_bytes: bytes
    method_sha256: str

    def __post_init__(self) -> None:
        """Validate explicit semantics and their immutable provenance bytes."""
        _require_identifier(self.project_id, "project_id")
        start = _parse_utc(self.effective_start_utc, "effective_start_utc")
        end = _parse_utc(
            self.effective_end_exclusive_utc, "effective_end_exclusive_utc"
        )
        if start >= end:
            raise ValueError("effective interval must be positive and end-exclusive.")
        for field_name in (
            "meter_logical_id",
            "turbine_logical_id",
            "availability_logical_id",
            "curtailment_logical_id",
        ):
            _require_identifier(getattr(self, field_name), field_name)
        exact_semantics = {
            "meter_energy_basis": "net_export_interval_energy",
            "turbine_energy_basis": "complete_turbine_terminal_interval_energy",
            "loss_energy_basis": "non_overlapping_positive_reduction_energy",
            "interval_boundary": "interval_start_end_exclusive",
            "excluded_flows": "imports_storage_solar_and_shared_poc_excluded",
            "asset_universe_basis": "d2_verified_complete",
        }
        for field_name, expected in exact_semantics.items():
            if getattr(self, field_name) != expected:
                raise ValueError(f"{field_name} must equal {expected!r}.")
        _validate_provenance(
            self.source_locator,
            self.source_bytes,
            self.source_sha256,
            self.method_bytes,
            self.method_sha256,
        )

    def model_dump(self) -> dict[str, Any]:
        """Return metadata and digests without serializing retained source bytes."""
        return {
            "project_id": self.project_id,
            "effective_start_utc": self.effective_start_utc,
            "effective_end_exclusive_utc": self.effective_end_exclusive_utc,
            "meter_logical_id": self.meter_logical_id,
            "turbine_logical_id": self.turbine_logical_id,
            "availability_logical_id": self.availability_logical_id,
            "curtailment_logical_id": self.curtailment_logical_id,
            "meter_energy_basis": self.meter_energy_basis,
            "turbine_energy_basis": self.turbine_energy_basis,
            "loss_energy_basis": self.loss_energy_basis,
            "interval_boundary": self.interval_boundary,
            "excluded_flows": self.excluded_flows,
            "asset_universe_basis": self.asset_universe_basis,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "method_sha256": self.method_sha256,
        }


@dataclass(frozen=True)
class OperationalSupplementalEnergyEvidence:
    """Provenance-bound scalar energy outside the current D1/D2 role set."""

    evidence_id: str
    component: OperationalSupplementalComponent
    project_id: str
    effective_start_utc: str
    effective_end_exclusive_utc: str
    value_kwh: str
    boundary: Literal[
        "upstream_resource_potential",
        "resource_to_turbine_combined_wake_performance",
    ]
    source_locator: str
    source_bytes: bytes
    source_sha256: str
    method_bytes: bytes
    method_sha256: str

    def __post_init__(self) -> None:
        """Validate an exact non-negative value and immutable provenance binding."""
        _require_identifier(self.evidence_id, "evidence_id")
        _require_identifier(self.project_id, "project_id")
        if (
            not isinstance(self.component, str)
            or self.component not in _SUPPLEMENTAL_COMPONENTS
        ):
            raise ValueError("supplemental component is not supported.")
        expected_boundary = (
            "upstream_resource_potential"
            if self.component == "resource_gross_energy"
            else "resource_to_turbine_combined_wake_performance"
        )
        if self.boundary != expected_boundary:
            raise ValueError(
                f"{self.component} requires boundary={expected_boundary!r}."
            )
        start = _parse_utc(self.effective_start_utc, "effective_start_utc")
        end = _parse_utc(
            self.effective_end_exclusive_utc, "effective_end_exclusive_utc"
        )
        if start >= end:
            raise ValueError("supplemental evidence interval must be positive.")
        if _fraction_from_decimal(self.value_kwh) < 0:
            raise ValueError(
                "supplemental energy must use positive-means-loss semantics."
            )
        _validate_provenance(
            self.source_locator,
            self.source_bytes,
            self.source_sha256,
            self.method_bytes,
            self.method_sha256,
        )

    def model_dump(self) -> dict[str, Any]:
        """Return metadata and digests without serializing retained source bytes."""
        return {
            "evidence_id": self.evidence_id,
            "component": self.component,
            "project_id": self.project_id,
            "effective_start_utc": self.effective_start_utc,
            "effective_end_exclusive_utc": self.effective_end_exclusive_utc,
            "value_kwh": self.value_kwh,
            "boundary": self.boundary,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "method_sha256": self.method_sha256,
        }


@dataclass(frozen=True)
class OperationalAEPSpec:
    """Explicit selectors, temporal label, and reconciliation tolerance."""

    project_id: str
    assessment_id: str
    effective_start_utc: str
    effective_end_exclusive_utc: str
    temporal_basis: OperationalTemporalBasis
    meter_logical_id: str
    turbine_logical_id: str
    availability_logical_id: str
    curtailment_logical_id: str
    absolute_tolerance_kwh: str

    def __post_init__(self) -> None:
        """Validate selectors and prohibit long-term or exceedance relabelling."""
        for field_name in (
            "project_id",
            "assessment_id",
            "meter_logical_id",
            "turbine_logical_id",
            "availability_logical_id",
            "curtailment_logical_id",
        ):
            _require_identifier(getattr(self, field_name), field_name)
        start = _parse_utc(self.effective_start_utc, "effective_start_utc")
        end = _parse_utc(
            self.effective_end_exclusive_utc, "effective_end_exclusive_utc"
        )
        if start >= end:
            raise ValueError("effective interval must be positive and end-exclusive.")
        if self.temporal_basis not in {
            "observed_period_total",
            "actual_calendar_year",
        }:
            raise ValueError("temporal_basis is not a supported observed-period label.")
        if self.temporal_basis == "actual_calendar_year" and not (
            start.month == 1
            and start.day == 1
            and start.time() == datetime.min.time()
            and end.month == 1
            and end.day == 1
            and end.time() == datetime.min.time()
            and end.year == start.year + 1
        ):
            raise ValueError(
                "actual_calendar_year requires one complete UTC Jan-1 to Jan-1 interval."
            )
        if _fraction_from_decimal(self.absolute_tolerance_kwh) < 0:
            raise ValueError("absolute_tolerance_kwh must be non-negative.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible specification."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalAEPInput:
    """Retained D1/D2 artifacts and optional D3 supplemental evidence."""

    assessments: tuple[OperationalAssessmentInput, ...]
    normalized_results: tuple[OperationalNormalizationResult, ...]
    boundary_evidence: OperationalBoundaryEvidence
    supplemental_evidence: tuple[OperationalSupplementalEnergyEvidence, ...] = ()

    def __post_init__(self) -> None:
        """Reject mutable containers and wrong runtime artifact types."""
        if (
            not isinstance(self.assessments, tuple)
            or not self.assessments
            or not all(
                isinstance(item, OperationalAssessmentInput)
                for item in self.assessments
            )
        ):
            raise ValueError("assessments must be a non-empty tuple of D1 inputs.")
        if (
            not isinstance(self.normalized_results, tuple)
            or not self.normalized_results
            or not all(
                isinstance(item, OperationalNormalizationResult)
                for item in self.normalized_results
            )
        ):
            raise ValueError(
                "normalized_results must be a non-empty tuple of D2 results."
            )
        if not isinstance(self.boundary_evidence, OperationalBoundaryEvidence):
            raise ValueError("boundary_evidence has the wrong runtime type.")
        if not isinstance(self.supplemental_evidence, tuple) or not all(
            isinstance(item, OperationalSupplementalEnergyEvidence)
            for item in self.supplemental_evidence
        ):
            raise ValueError("supplemental_evidence must be an immutable typed tuple.")


@dataclass(frozen=True)
class OperationalAEPSourceBinding:
    """Digest-only binding for one selected D2 or D3 input role."""

    role: str
    logical_id: str
    source_sha256: str
    normalized_sha256: str | None
    method_sha256: str
    claim_sha256: str | None = None

    def __post_init__(self) -> None:
        """Validate stable role identifiers and SHA-256 identities."""
        if not isinstance(self.role, str) or self.role not in _AEP_SOURCE_ROLES:
            raise ValueError("source binding role is not supported.")
        _require_identifier(self.logical_id, "logical_id")
        for field_name in ("source_sha256", "method_sha256"):
            if _SHA256_RE.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
        if self.normalized_sha256 is not None and (
            _SHA256_RE.fullmatch(self.normalized_sha256) is None
        ):
            raise ValueError("normalized_sha256 must be null or a lowercase digest.")
        if self.claim_sha256 is not None and (
            _SHA256_RE.fullmatch(self.claim_sha256) is None
        ):
            raise ValueError("claim_sha256 must be null or a lowercase digest.")
        if self.role in _D2_SOURCE_ROLES:
            if self.normalized_sha256 is None or self.claim_sha256 is not None:
                raise ValueError(
                    "D2 source bindings require a normalized digest and no scalar claim."
                )
        elif self.normalized_sha256 is not None or self.claim_sha256 is None:
            raise ValueError(
                "supplemental bindings require a scalar claim and no normalized digest."
            )

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible source binding."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalAEPReceipt:
    """Deterministic provenance, method, identity, and authority receipt."""

    schema: str
    project_id: str
    assessment_id: str
    temporal_basis: OperationalTemporalBasis
    effective_start_utc: str
    effective_end_exclusive_utc: str
    absolute_tolerance: OperationalEnergyQuantity
    source_bindings: tuple[OperationalAEPSourceBinding, ...]
    source_manifest_sha256: str
    boundary_source_sha256: str
    boundary_method_sha256: str
    method_sha256: str
    meter_to_turbine_residual: OperationalEnergyQuantity
    known_gross_to_net_residual: OperationalEnergyQuantity
    full_gross_to_net_residual: OperationalEnergyQuantity | None
    annual_uncertainty_status: Literal["unavailable_not_estimated"]
    annual_uncertainty_basis: None
    annual_exceedance_probabilities: tuple[()] = ()
    long_term_average_uncertainty_status: Literal["unavailable_not_estimated"] = (
        "unavailable_not_estimated"
    )
    long_term_average_uncertainty_basis: None = None
    long_term_average_exceedance_probabilities: tuple[()] = ()
    raw_operational_only: Literal[True] = True
    canonical_finance_eligible: Literal[False] = False
    bankable: Literal[False] = False
    lender_eligible: Literal[False] = False
    board_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        """Validate receipt identity, unavailable uncertainty, and authority fences."""
        if self.schema != OPERATIONAL_AEP_SCHEMA:
            raise ValueError("operational AEP receipt schema is not supported.")
        _require_identifier(self.project_id, "project_id")
        _require_identifier(self.assessment_id, "assessment_id")
        if not isinstance(self.source_bindings, tuple) or not self.source_bindings:
            raise ValueError("source_bindings must be a non-empty tuple.")
        if not all(
            isinstance(item, OperationalAEPSourceBinding)
            for item in self.source_bindings
        ):
            raise ValueError("source_bindings contain an invalid object.")
        binding_roles = tuple(item.role for item in self.source_bindings)
        if len(binding_roles) != len(
            set(binding_roles)
        ) or not _D2_SOURCE_ROLES.issubset(binding_roles):
            raise ValueError(
                "source_bindings require unique roles and every mandatory D2 role."
            )
        if self.temporal_basis not in {
            "observed_period_total",
            "actual_calendar_year",
        }:
            raise ValueError("receipt temporal_basis is not an observed-period label.")
        start = _parse_utc(self.effective_start_utc, "effective_start_utc")
        end = _parse_utc(
            self.effective_end_exclusive_utc, "effective_end_exclusive_utc"
        )
        if start >= end:
            raise ValueError("receipt effective interval must be positive.")
        if self.temporal_basis == "actual_calendar_year" and not (
            start.month == 1
            and start.day == 1
            and start.time() == datetime.min.time()
            and end.month == 1
            and end.day == 1
            and end.time() == datetime.min.time()
            and end.year == start.year + 1
        ):
            raise ValueError(
                "actual_calendar_year receipt requires one complete UTC year."
            )
        quantities = (
            self.absolute_tolerance,
            self.meter_to_turbine_residual,
            self.known_gross_to_net_residual,
        )
        if not all(isinstance(item, OperationalEnergyQuantity) for item in quantities):
            raise ValueError(
                "receipt tolerances and residuals must be exact quantities."
            )
        if self.full_gross_to_net_residual is not None and not isinstance(
            self.full_gross_to_net_residual, OperationalEnergyQuantity
        ):
            raise ValueError("full gross-to-net residual must be null or exact.")
        tolerance = self.absolute_tolerance.as_fraction()
        if tolerance < 0:
            raise ValueError("receipt tolerance must be non-negative.")
        residuals = (
            self.meter_to_turbine_residual,
            self.known_gross_to_net_residual,
        ) + (
            (self.full_gross_to_net_residual,)
            if self.full_gross_to_net_residual is not None
            else ()
        )
        if any(abs(item.as_fraction()) > tolerance for item in residuals):
            raise ValueError("receipt energy residual exceeds its explicit tolerance.")
        for field_name in (
            "source_manifest_sha256",
            "boundary_source_sha256",
            "boundary_method_sha256",
            "method_sha256",
        ):
            if _SHA256_RE.fullmatch(getattr(self, field_name)) is None:
                raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
        if (
            self.annual_uncertainty_status != "unavailable_not_estimated"
            or self.annual_uncertainty_basis is not None
            or self.annual_exceedance_probabilities != ()
            or self.long_term_average_uncertainty_status != "unavailable_not_estimated"
            or self.long_term_average_uncertainty_basis is not None
            or self.long_term_average_exceedance_probabilities != ()
        ):
            raise ValueError(
                "annual and long-term uncertainty/exceedance outputs must remain unavailable."
            )
        exact_flags = {
            "raw_operational_only": True,
            "canonical_finance_eligible": False,
            "bankable": False,
            "lender_eligible": False,
            "board_eligible": False,
        }
        for field_name, expected in exact_flags.items():
            value = getattr(self, field_name)
            if type(value) is not bool or value is not expected:
                raise ValueError(
                    f"{field_name} must be the exact boolean {expected!r}."
                )

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible receipt."""
        return asdict(self)


@dataclass(frozen=True)
class OperationalAEPResult:
    """Factory-only exact operational energy and loss-attribution result."""

    inputs: OperationalAEPInput
    spec: OperationalAEPSpec
    components: tuple[OperationalEnergyComponent, ...]
    ratios: tuple[OperationalRatio, ...]
    receipt: OperationalAEPReceipt
    _factory_token: InitVar[object] = None

    def __post_init__(self, _factory_token: object) -> None:
        """Replay the complete calculation and reject detached result substitution."""
        if _factory_token is not _AEP_RESULT_TOKEN:
            raise ValueError(
                "operational AEP results must be constructed by estimate_operational_aep."
            )
        artifacts = _build_artifacts(self.inputs, self.spec)
        if (
            self.components != artifacts.components
            or self.ratios != artifacts.ratios
            or self.receipt != artifacts.receipt
        ):
            raise ValueError(
                "operational AEP result does not replay from retained inputs."
            )

    def component(
        self, name: OperationalEnergyComponentName
    ) -> OperationalEnergyComponent:
        """Return one named energy component."""
        for component in self.components:
            if component.name == name:
                return component
        raise KeyError(name)

    def ratio(self, name: str) -> OperationalRatio:
        """Return one named exact ratio."""
        for ratio in self.ratios:
            if ratio.name == name:
                return ratio
        raise KeyError(name)

    def model_dump(self) -> dict[str, Any]:
        """Return result values and receipts without retained source bytes."""
        return {
            "schema": self.receipt.schema,
            "components": [item.model_dump() for item in self.components],
            "ratios": [item.model_dump() for item in self.ratios],
            "receipt": self.receipt.model_dump(),
        }


@dataclass(frozen=True)
class _AEPArtifacts:
    components: tuple[OperationalEnergyComponent, ...]
    ratios: tuple[OperationalRatio, ...]
    receipt: OperationalAEPReceipt


def _require_identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a closed identifier.")
    return value


def _require_text(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.strip() != value
        or "\n" in value
        or "\r" in value
    ):
        raise ValueError(f"{field_name} must be non-empty closed text.")
    return value


def _parse_utc(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be an RFC3339 UTC timestamp ending in Z.")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid UTC timestamp.") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field_name} must resolve to UTC.")
    return parsed


def _format_utc(value: datetime) -> str:
    rendered = (
        f"{value.year:04d}-{value.month:02d}-{value.day:02d}T"
        f"{value.hour:02d}:{value.minute:02d}:{value.second:02d}"
    )
    if value.microsecond:
        rendered += f".{value.microsecond:06d}".rstrip("0")
    return rendered + "Z"


def _fraction_from_decimal(value: object) -> Fraction:
    if (
        not isinstance(value, str)
        or len(value) > _MAX_NUMERIC_CHARACTERS
        or _DECIMAL_RE.fullmatch(value) is None
    ):
        raise ValueError("energy values must be bounded finite decimal strings.")
    sign = -1 if value.startswith("-") else 1
    unsigned = value.lstrip("+-")
    coefficient, exponent_text = (re.split(r"[eE]", unsigned, maxsplit=1) + ["0"])[:2]
    exponent = int(exponent_text)
    if abs(exponent) > _MAX_NUMERIC_CHARACTERS:
        raise ValueError("energy exponent exceeds the bounded representation.")
    integer, dot, fractional = coefficient.partition(".")
    digits = (integer or "0") + (fractional if dot else "")
    numerator = sign * int(digits)
    scale = len(fractional) - exponent
    if scale >= 0:
        return Fraction(numerator, 10**scale)
    return Fraction(numerator * 10 ** (-scale), 1)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_sha(payload: object) -> str:
    return _sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    )


def _validate_provenance(
    source_locator: object,
    source_bytes: object,
    source_sha256: object,
    method_bytes: object,
    method_sha256: object,
) -> None:
    _require_text(source_locator, "source_locator")
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValueError("source_bytes must be non-empty immutable bytes.")
    if not isinstance(method_bytes, bytes) or not method_bytes:
        raise ValueError("method_bytes must be non-empty immutable bytes.")
    if (
        len(source_bytes) > _MAX_PROVENANCE_BYTES
        or len(method_bytes) > _MAX_PROVENANCE_BYTES
    ):
        raise ValueError("provenance artifacts must not exceed 1 MiB each.")
    if not isinstance(source_sha256, str) or _sha256(source_bytes) != source_sha256:
        raise ValueError("source bytes do not match source_sha256.")
    if not isinstance(method_sha256, str) or _sha256(method_bytes) != method_sha256:
        raise ValueError("method bytes do not match method_sha256.")
    if source_sha256 == method_sha256:
        raise ValueError("source and method artifacts must have distinct identities.")


def _effective_bounds(result: OperationalNormalizationResult) -> tuple[str, str]:
    evidence = result.evidence
    start = _parse_utc(evidence.coverage_start_utc, "coverage_start_utc")
    end = _parse_utc(evidence.coverage_end_utc, "coverage_end_utc")
    if evidence.interval_basis == "fixed_seconds":
        if evidence.interval_seconds is None:
            raise OperationalAEPError(
                "INTERVAL_MISMATCH", "fixed evidence has no interval length."
            )
        effective_end = end + timedelta(seconds=evidence.interval_seconds)
    elif evidence.interval_basis == "calendar_month":
        if evidence.timezone_treatment == "source_utc":
            year = end.year + int(end.month == 12)
            month = 1 if end.month == 12 else end.month + 1
            effective_end = end.replace(year=year, month=month)
        elif evidence.timezone_treatment == "named_zone_to_utc":
            rules = result.timezone_rules
            if rules is None:
                raise OperationalAEPError(
                    "INTERVAL_MISMATCH",
                    "named-zone calendar evidence lacks retained TZif rules.",
                )
            zone = ZoneInfo.from_file(
                io.BytesIO(rules.tzif_bytes), key=rules.source_timezone
            )
            wall = end.astimezone(zone).replace(tzinfo=None)
            year = wall.year + int(wall.month == 12)
            month = 1 if wall.month == 12 else wall.month + 1
            next_wall = wall.replace(year=year, month=month)
            fold = int(evidence.ambiguous_time_policy == "fold_1")
            effective_end = next_wall.replace(tzinfo=zone, fold=fold).astimezone(
                timezone.utc
            )
        else:
            raise OperationalAEPError(
                "UNSUPPORTED_EVIDENCE",
                "calendar-month D3 inputs require source UTC or supplied named-zone rules.",
            )
    else:
        raise OperationalAEPError(
            "UNSUPPORTED_EVIDENCE", "D3 requires time-series evidence."
        )
    return _format_utc(start), _format_utc(effective_end)


def _selected_results(
    inputs: OperationalAEPInput, spec: OperationalAEPSpec
) -> dict[str, OperationalNormalizationResult]:
    by_id: dict[str, OperationalNormalizationResult] = {}
    for result in inputs.normalized_results:
        logical_id = result.evidence.logical_id
        if logical_id in by_id:
            raise OperationalAEPError(
                "SELECTOR_AMBIGUITY",
                f"logical_id {logical_id!r} has more than one D2 result.",
            )
        by_id[logical_id] = result
    selected_ids = {
        spec.meter_logical_id,
        spec.turbine_logical_id,
        spec.availability_logical_id,
        spec.curtailment_logical_id,
    }
    missing = sorted(selected_ids - set(by_id))
    extra = sorted(set(by_id) - selected_ids)
    if missing or extra:
        raise OperationalAEPError(
            "SELECTOR_AMBIGUITY",
            f"explicit D2 selection mismatch; missing={missing}, unselected={extra}.",
        )
    return by_id


def _replay_d2_result(result: OperationalNormalizationResult) -> None:
    """Prove that retained D2 source, method, rows, and receipt still replay."""
    try:
        replay = normalize_operational_csv(
            result.source_bytes,
            result.evidence,
            lineage_source_bytes=result.lineage_source_bytes,
            derivation_method_bytes=result.derivation_method_bytes,
            timezone_rules=result.timezone_rules,
            group_universe=result.group_universe,
            column_exclusions=result.receipt.column_exclusions,
            row_exclusions=tuple(
                OperationalRowExclusion(item.source_row_number, item.reason)
                for item in result.receipt.row_exclusions
            ),
        )
    except (OperationalNormalizationError, ValueError) as exc:
        raise OperationalAEPError(
            "PROVENANCE_MISMATCH",
            f"D2 result {result.evidence.logical_id!r} no longer replays.",
        ) from exc
    if replay != result:
        raise OperationalAEPError(
            "PROVENANCE_MISMATCH",
            f"D2 result {result.evidence.logical_id!r} differs from its replay.",
        )


def _assessment_claim(assessment: OperationalAssessmentInput) -> dict[str, Any]:
    """Return an order-independent D1 assessment claim for method binding."""
    claim = assessment.model_dump()
    claim["datasets"] = tuple(
        sorted(claim["datasets"], key=lambda item: item["logical_id"])
    )
    return claim


def _validate_assessments(
    inputs: OperationalAEPInput,
    spec: OperationalAEPSpec,
    selected: dict[str, OperationalNormalizationResult],
) -> None:
    if any(item.project_id != spec.project_id for item in inputs.assessments):
        raise OperationalAEPError(
            "BOUNDARY_MISMATCH", "all D1 assessments must bind the selected project."
        )

    def contains(assessment: OperationalAssessmentInput, logical_id: str) -> bool:
        result = selected[logical_id]
        return any(dataset == result.evidence for dataset in assessment.datasets)

    electrical_matches = [
        item
        for item in inputs.assessments
        if item.purpose == "electrical_losses"
        and contains(item, spec.meter_logical_id)
        and contains(item, spec.turbine_logical_id)
    ]
    long_term_matches = [
        item
        for item in inputs.assessments
        if item.purpose == "long_term_aep"
        and contains(item, spec.meter_logical_id)
        and contains(item, spec.availability_logical_id)
        and contains(item, spec.curtailment_logical_id)
    ]
    if len(electrical_matches) != 1 or len(long_term_matches) != 1:
        raise OperationalAEPError(
            "SELECTOR_AMBIGUITY",
            "selected evidence must appear once in matched electrical-loss and "
            "long-term-AEP D1 envelopes.",
        )


def _validate_role(
    result: OperationalNormalizationResult,
    *,
    kind: str,
    role: str,
    grouped: bool,
) -> None:
    if result.evidence.kind != kind or role not in result.receipt.normalized_roles:
        raise OperationalAEPError(
            "UNSUPPORTED_EVIDENCE",
            f"{result.evidence.logical_id!r} must be {kind!r} evidence with role {role!r}.",
        )
    has_asset = "asset_id" in result.receipt.normalized_roles
    if grouped != has_asset:
        raise OperationalAEPError(
            "BOUNDARY_MISMATCH",
            f"{result.evidence.logical_id!r} has the wrong grouped boundary semantics.",
        )
    if grouped and (
        result.group_universe is None
        or not result.receipt.expected_group_keys
        or result.receipt.missing_group_keys
        or result.receipt.unexpected_group_keys
    ):
        raise OperationalAEPError(
            "BOUNDARY_MISMATCH", "turbine evidence lacks a complete D2 asset universe."
        )


def _sum_energy(result: OperationalNormalizationResult, role: str) -> Fraction:
    roles = result.receipt.normalized_roles
    if role not in roles:
        raise OperationalAEPError(
            "UNSUPPORTED_EVIDENCE", f"source lacks selected role {role!r}."
        )
    value_index = roles.index(role)
    total = Fraction(0)
    for row in result.normalized_rows:
        value = _fraction_from_decimal(row[value_index])
        if value < 0:
            raise OperationalAEPError(
                "ENERGY_IDENTITY_FAILED",
                f"{role} must use non-negative positive-means-loss values.",
            )
        total += value
    if role == "power_kw":
        interval = result.evidence.interval_seconds
        if result.evidence.interval_basis != "fixed_seconds" or interval is None:
            raise OperationalAEPError(
                "UNSUPPORTED_EVIDENCE",
                "interval-average power requires a fixed-second interval.",
            )
        total *= Fraction(interval, 3_600)
    return total


def _available(
    name: OperationalEnergyComponentName,
    value: Fraction,
    *evidence_ids: str,
) -> OperationalEnergyComponent:
    return OperationalEnergyComponent(
        name=name,
        status="available",
        value=OperationalEnergyQuantity.from_fraction(value),
        evidence_ids=tuple(evidence_ids),
        unavailable_reason=None,
    )


def _unavailable(
    name: OperationalEnergyComponentName, reason: str
) -> OperationalEnergyComponent:
    return OperationalEnergyComponent(
        name=name,
        status="unavailable",
        value=None,
        evidence_ids=(),
        unavailable_reason=reason,
    )


def _ratio(name: str, numerator: Fraction, denominator: Fraction) -> OperationalRatio:
    if denominator == 0:
        return OperationalRatio(
            name=name,
            status="unavailable",
            numerator=None,
            denominator=None,
            unavailable_reason="denominator_is_zero",
        )
    value = numerator / denominator
    return OperationalRatio(
        name=name,
        status="available",
        numerator=value.numerator,
        denominator=value.denominator,
        unavailable_reason=None,
    )


def _d2_binding(
    role: str, result: OperationalNormalizationResult
) -> OperationalAEPSourceBinding:
    normalized_sha = result.receipt.normalized_sha256
    assert normalized_sha is not None
    return OperationalAEPSourceBinding(
        role=role,
        logical_id=result.evidence.logical_id,
        source_sha256=result.evidence.source_sha256,
        normalized_sha256=normalized_sha,
        method_sha256=result.receipt.method_sha256,
        claim_sha256=None,
    )


def _supplemental_binding(
    evidence: OperationalSupplementalEnergyEvidence,
) -> OperationalAEPSourceBinding:
    return OperationalAEPSourceBinding(
        role=evidence.component,
        logical_id=evidence.evidence_id,
        source_sha256=evidence.source_sha256,
        normalized_sha256=None,
        method_sha256=evidence.method_sha256,
        claim_sha256=_json_sha(evidence.model_dump()),
    )


def _build_artifacts(
    inputs: OperationalAEPInput, spec: OperationalAEPSpec
) -> _AEPArtifacts:
    if not isinstance(inputs, OperationalAEPInput) or not isinstance(
        spec, OperationalAEPSpec
    ):
        raise OperationalAEPError(
            "INVALID_INPUT", "inputs and spec must use the public D3 contracts."
        )
    # Frozen dataclasses reject ordinary mutation, while reconstruction here also
    # closes object-level or untyped substitution before any arithmetic begins.
    spec = OperationalAEPSpec(**spec.model_dump())
    original_boundary = inputs.boundary_evidence
    boundary = OperationalBoundaryEvidence(
        project_id=original_boundary.project_id,
        effective_start_utc=original_boundary.effective_start_utc,
        effective_end_exclusive_utc=original_boundary.effective_end_exclusive_utc,
        meter_logical_id=original_boundary.meter_logical_id,
        turbine_logical_id=original_boundary.turbine_logical_id,
        availability_logical_id=original_boundary.availability_logical_id,
        curtailment_logical_id=original_boundary.curtailment_logical_id,
        meter_energy_basis=original_boundary.meter_energy_basis,
        turbine_energy_basis=original_boundary.turbine_energy_basis,
        loss_energy_basis=original_boundary.loss_energy_basis,
        interval_boundary=original_boundary.interval_boundary,
        excluded_flows=original_boundary.excluded_flows,
        asset_universe_basis=original_boundary.asset_universe_basis,
        source_locator=original_boundary.source_locator,
        source_bytes=original_boundary.source_bytes,
        source_sha256=original_boundary.source_sha256,
        method_bytes=original_boundary.method_bytes,
        method_sha256=original_boundary.method_sha256,
    )
    supplements_validated = tuple(
        OperationalSupplementalEnergyEvidence(
            evidence_id=item.evidence_id,
            component=item.component,
            project_id=item.project_id,
            effective_start_utc=item.effective_start_utc,
            effective_end_exclusive_utc=item.effective_end_exclusive_utc,
            value_kwh=item.value_kwh,
            boundary=item.boundary,
            source_locator=item.source_locator,
            source_bytes=item.source_bytes,
            source_sha256=item.source_sha256,
            method_bytes=item.method_bytes,
            method_sha256=item.method_sha256,
        )
        for item in inputs.supplemental_evidence
    )
    inputs = OperationalAEPInput(
        assessments=inputs.assessments,
        normalized_results=inputs.normalized_results,
        boundary_evidence=boundary,
        supplemental_evidence=supplements_validated,
    )
    selected = _selected_results(inputs, spec)
    for result in selected.values():
        _replay_d2_result(result)
    boundary_pairs = (
        (boundary.project_id, spec.project_id),
        (boundary.effective_start_utc, spec.effective_start_utc),
        (boundary.effective_end_exclusive_utc, spec.effective_end_exclusive_utc),
        (boundary.meter_logical_id, spec.meter_logical_id),
        (boundary.turbine_logical_id, spec.turbine_logical_id),
        (boundary.availability_logical_id, spec.availability_logical_id),
        (boundary.curtailment_logical_id, spec.curtailment_logical_id),
    )
    if any(actual != expected for actual, expected in boundary_pairs):
        raise OperationalAEPError(
            "BOUNDARY_MISMATCH",
            "boundary evidence does not match the D3 specification.",
        )
    _validate_assessments(inputs, spec, selected)

    meter = selected[spec.meter_logical_id]
    turbine = selected[spec.turbine_logical_id]
    availability = selected[spec.availability_logical_id]
    curtailment = selected[spec.curtailment_logical_id]
    meter_role = "energy_kwh"
    turbine_role = "power_kw"
    _validate_role(meter, kind="revenue_meter", role=meter_role, grouped=False)
    _validate_role(turbine, kind="scada", role=turbine_role, grouped=True)
    _validate_role(
        availability,
        kind="curtailment",
        role="availability_loss_kwh",
        grouped=False,
    )
    _validate_role(
        curtailment,
        kind="curtailment",
        role="curtailment_loss_kwh",
        grouped=False,
    )
    required_loss_roles = {"availability_loss_kwh", "curtailment_loss_kwh"}
    for result in (availability, curtailment):
        if not required_loss_roles.issubset(result.receipt.normalized_roles):
            raise OperationalAEPError(
                "UNSUPPORTED_EVIDENCE",
                "selected loss evidence must be an individually complete D1 curtailment product.",
            )
    expected_bounds = (spec.effective_start_utc, spec.effective_end_exclusive_utc)
    for result in {id(item): item for item in selected.values()}.values():
        if _effective_bounds(result) != expected_bounds:
            raise OperationalAEPError(
                "INTERVAL_MISMATCH",
                f"{result.evidence.logical_id!r} does not share the exact effective interval.",
            )

    meter_value = _sum_energy(meter, meter_role)
    turbine_value = _sum_energy(turbine, turbine_role)
    availability_value = _sum_energy(availability, "availability_loss_kwh")
    curtailment_value = _sum_energy(curtailment, "curtailment_loss_kwh")
    if meter_value > turbine_value:
        raise OperationalAEPError(
            "ENERGY_IDENTITY_FAILED",
            "meter energy exceeds turbine-terminal energy; negative electrical loss is not masked.",
        )
    electrical_value = turbine_value - meter_value
    meter_gross = meter_value + availability_value + curtailment_value
    turbine_gross = turbine_value + availability_value + curtailment_value

    supplements: dict[str, OperationalSupplementalEnergyEvidence] = {}
    evidence_ids: set[str] = set()
    for evidence in inputs.supplemental_evidence:
        if evidence.component in supplements or evidence.evidence_id in evidence_ids:
            raise OperationalAEPError(
                "SELECTOR_AMBIGUITY", "supplemental evidence selectors must be unique."
            )
        if (
            evidence.project_id != spec.project_id
            or evidence.effective_start_utc != spec.effective_start_utc
            or evidence.effective_end_exclusive_utc != spec.effective_end_exclusive_utc
        ):
            raise OperationalAEPError(
                "BOUNDARY_MISMATCH",
                "supplemental energy does not share project and effective interval.",
            )
        supplements[evidence.component] = evidence
        evidence_ids.add(evidence.evidence_id)

    resource_evidence = supplements.get("resource_gross_energy")
    wake_evidence = supplements.get("wake_performance_loss")
    resource_value = (
        _fraction_from_decimal(resource_evidence.value_kwh)
        if resource_evidence is not None
        else None
    )
    wake_value = (
        _fraction_from_decimal(wake_evidence.value_kwh)
        if wake_evidence is not None
        else None
    )
    if resource_value is not None and resource_value < turbine_gross:
        raise OperationalAEPError(
            "ENERGY_IDENTITY_FAILED",
            "resource gross is below the matched known-loss-restored gross.",
        )
    unknown_value: Fraction | None = None
    if resource_value is not None and wake_value is not None:
        unknown_value = resource_value - turbine_gross - wake_value
        if unknown_value < 0:
            raise OperationalAEPError(
                "ENERGY_IDENTITY_FAILED",
                "resource gross cannot cover known and wake/performance losses; residual is negative.",
            )

    components = (
        _available("net_meter_energy", meter_value, meter.evidence.logical_id),
        _available(
            "turbine_terminal_energy", turbine_value, turbine.evidence.logical_id
        ),
        _available(
            "availability_loss", availability_value, availability.evidence.logical_id
        ),
        _available(
            "electrical_loss",
            electrical_value,
            meter.evidence.logical_id,
            turbine.evidence.logical_id,
        ),
        _available(
            "curtailment_loss", curtailment_value, curtailment.evidence.logical_id
        ),
        _available(
            "meter_loss_restored_gross",
            meter_gross,
            meter.evidence.logical_id,
            availability.evidence.logical_id,
            curtailment.evidence.logical_id,
        ),
        _available(
            "turbine_known_gross",
            turbine_gross,
            turbine.evidence.logical_id,
            availability.evidence.logical_id,
            curtailment.evidence.logical_id,
        ),
        (
            _available(
                "resource_gross_energy", resource_value, resource_evidence.evidence_id
            )
            if resource_value is not None and resource_evidence is not None
            else _unavailable(
                "resource_gross_energy", "no_separately_provenance_bound_resource_gross"
            )
        ),
        (
            _available("wake_performance_loss", wake_value, wake_evidence.evidence_id)
            if wake_value is not None and wake_evidence is not None
            else _unavailable(
                "wake_performance_loss",
                "no_separately_provenance_bound_wake_performance_loss",
            )
        ),
        (
            _available(
                "unknown_residual_loss",
                unknown_value,
                resource_evidence.evidence_id,
                wake_evidence.evidence_id,
                meter.evidence.logical_id,
                turbine.evidence.logical_id,
                availability.evidence.logical_id,
                curtailment.evidence.logical_id,
            )
            if unknown_value is not None
            and resource_evidence is not None
            and wake_evidence is not None
            else _unavailable(
                "unknown_residual_loss",
                "requires_resource_gross_and_wake_performance_evidence",
            )
        ),
        _unavailable(
            "long_term_average_energy", "no_governed_long_term_correction_method"
        ),
    )

    ratios_list = [
        _ratio("electrical_loss_fraction_of_turbine", electrical_value, turbine_value)
    ]
    if resource_value is None:
        for name in (
            "net_fraction_of_resource_gross",
            "availability_loss_fraction_of_resource_gross",
            "electrical_loss_fraction_of_resource_gross",
            "curtailment_loss_fraction_of_resource_gross",
            "wake_performance_loss_fraction_of_resource_gross",
            "unknown_residual_fraction_of_resource_gross",
        ):
            ratios_list.append(
                OperationalRatio(
                    name=name,
                    status="unavailable",
                    numerator=None,
                    denominator=None,
                    unavailable_reason="resource_gross_unavailable",
                )
            )
    else:
        ratio_values: tuple[tuple[str, Fraction | None], ...] = (
            ("net_fraction_of_resource_gross", meter_value),
            ("availability_loss_fraction_of_resource_gross", availability_value),
            ("electrical_loss_fraction_of_resource_gross", electrical_value),
            ("curtailment_loss_fraction_of_resource_gross", curtailment_value),
            ("wake_performance_loss_fraction_of_resource_gross", wake_value),
            ("unknown_residual_fraction_of_resource_gross", unknown_value),
        )
        for name, value in ratio_values:
            if value is None:
                ratios_list.append(
                    OperationalRatio(
                        name=name,
                        status="unavailable",
                        numerator=None,
                        denominator=None,
                        unavailable_reason="component_unavailable",
                    )
                )
            else:
                ratios_list.append(_ratio(name, value, resource_value))
    ratios = tuple(ratios_list)

    meter_residual = turbine_value - meter_value - electrical_value
    known_residual = (
        turbine_gross
        - meter_value
        - electrical_value
        - availability_value
        - curtailment_value
    )
    full_residual = (
        resource_value
        - meter_value
        - electrical_value
        - availability_value
        - curtailment_value
        - wake_value
        - unknown_value
        if resource_value is not None
        and wake_value is not None
        and unknown_value is not None
        else None
    )
    tolerance = _fraction_from_decimal(spec.absolute_tolerance_kwh)
    if (
        abs(meter_residual) > tolerance
        or abs(known_residual) > tolerance
        or (full_residual is not None and abs(full_residual) > tolerance)
    ):
        raise OperationalAEPError(
            "ENERGY_IDENTITY_FAILED", "an energy identity exceeds explicit tolerance."
        )

    bindings = (
        _d2_binding("net_meter_energy", meter),
        _d2_binding("turbine_terminal_energy", turbine),
        _d2_binding("availability_loss", availability),
        _d2_binding("curtailment_loss", curtailment),
    ) + tuple(
        _supplemental_binding(item)
        for item in sorted(
            inputs.supplemental_evidence, key=lambda item: item.component
        )
    )
    source_manifest: list[dict[str, Any]] = [item.model_dump() for item in bindings]
    source_manifest.append(
        {
            "role": "boundary_attestation",
            "claim": boundary.model_dump(),
            "claim_sha256": _json_sha(boundary.model_dump()),
        }
    )
    source_manifest.extend(
        {
            "role": "d1_assessment_envelope",
            "assessment_id": assessment.assessment_id,
            "claim_sha256": _json_sha(_assessment_claim(assessment)),
        }
        for assessment in sorted(
            inputs.assessments, key=lambda item: (item.purpose, item.assessment_id)
        )
    )
    source_manifest_sha = _json_sha(source_manifest)
    method_sha = _json_sha(
        {
            "version": _AEP_METHOD_VERSION,
            "spec": spec.model_dump(),
            "source_manifest_sha256": source_manifest_sha,
            "arithmetic": "fractions.Fraction_exact_v1",
            "power_integration": "interval_average_kw_times_seconds_over_3600",
            "loss_sign": "positive_means_reduction",
            "missing": "unavailable_not_zero",
            "unknown_residual": "derive_only_with_resource_and_wake_inputs",
            "uncertainty": "unavailable_not_estimated",
        }
    )
    receipt = OperationalAEPReceipt(
        schema=OPERATIONAL_AEP_SCHEMA,
        project_id=spec.project_id,
        assessment_id=spec.assessment_id,
        temporal_basis=spec.temporal_basis,
        effective_start_utc=spec.effective_start_utc,
        effective_end_exclusive_utc=spec.effective_end_exclusive_utc,
        absolute_tolerance=OperationalEnergyQuantity.from_fraction(tolerance),
        source_bindings=bindings,
        source_manifest_sha256=source_manifest_sha,
        boundary_source_sha256=boundary.source_sha256,
        boundary_method_sha256=boundary.method_sha256,
        method_sha256=method_sha,
        meter_to_turbine_residual=OperationalEnergyQuantity.from_fraction(
            meter_residual
        ),
        known_gross_to_net_residual=OperationalEnergyQuantity.from_fraction(
            known_residual
        ),
        full_gross_to_net_residual=(
            OperationalEnergyQuantity.from_fraction(full_residual)
            if full_residual is not None
            else None
        ),
        annual_uncertainty_status="unavailable_not_estimated",
        annual_uncertainty_basis=None,
    )
    return _AEPArtifacts(components=components, ratios=ratios, receipt=receipt)


def estimate_operational_aep(
    inputs: OperationalAEPInput, spec: OperationalAEPSpec
) -> OperationalAEPResult:
    """Reconcile matched D2 evidence into an exact non-canonical D3 result."""
    try:
        artifacts = _build_artifacts(inputs, spec)
        return OperationalAEPResult(
            inputs=inputs,
            spec=spec,
            components=artifacts.components,
            ratios=artifacts.ratios,
            receipt=artifacts.receipt,
            _factory_token=_AEP_RESULT_TOKEN,
        )
    except OperationalAEPError:
        raise
    except (ArithmeticError, OverflowError, ValueError, ZoneInfoNotFoundError) as exc:
        raise OperationalAEPError(
            "INVALID_INPUT", f"operational energy calculation failed closed: {exc}"
        ) from exc


__all__ = [
    "OPERATIONAL_AEP_SCHEMA",
    "OperationalAEPError",
    "OperationalAEPErrorCode",
    "OperationalAEPInput",
    "OperationalAEPReceipt",
    "OperationalAEPResult",
    "OperationalAEPSpec",
    "OperationalAEPSourceBinding",
    "OperationalBoundaryEvidence",
    "OperationalComponentStatus",
    "OperationalEnergyComponent",
    "OperationalEnergyComponentName",
    "OperationalEnergyQuantity",
    "OperationalRatio",
    "OperationalSupplementalComponent",
    "OperationalSupplementalEnergyEvidence",
    "OperationalTemporalBasis",
    "estimate_operational_aep",
]
