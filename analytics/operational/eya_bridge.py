"""Immutable EYA-to-actual reconciliation and inert finance proposal (#1334 D4).

The bridge snapshots one frozen pre-construction ``ResourceAssessment`` and
replays one D3 ``OperationalAEPResult`` before comparing them.  Category
attribution is admitted only as paired, provenance-bound expected and actual
net-energy effects.  Missing categories remain unavailable and the signed
unknown residual always closes the exact arithmetic identity.

The finance proposal is data only.  It has no apply path, carries no candidate
finance values, and is structurally default-off pending a separate R3
re-baseline with real evidence and independent KPI oracles.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import InitVar, asdict, dataclass
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any, Final, Literal, TypeAlias

from analytics.operational.aep import (
    OperationalAEPError,
    OperationalAEPInput,
    OperationalAEPResult,
    OperationalAEPSpec,
    OperationalBoundaryEvidence,
    OperationalEnergyQuantity,
    OperationalSupplementalEnergyEvidence,
    estimate_operational_aep,
)
from analytics.operational.contracts import (
    OperationalAssessmentInput,
    OperationalColumnBinding,
    OperationalDatasetEvidence,
)
from analytics.operational.normalization import (
    OperationalColumnExclusion,
    OperationalExcludedRowReceipt,
    OperationalGroupUniverse,
    OperationalNormalizationError,
    OperationalNormalizationResult,
    OperationalQualityReceipt,
    OperationalRowExclusion,
    OperationalTimezoneRules,
    normalize_operational_csv,
)
from analytics.resource_contracts import (
    DEFAULT_IDENTITY_RTOL,
    P_LEVELS,
    ResourceAssessment,
    ResourceAssessmentError,
)

EYA_ACTUAL_BRIDGE_SCHEMA: Final = "dutchbay.eya_actual_bridge.v1"
_BRIDGE_METHOD_VERSION: Final = "eya_actual_exact_bridge_v1"
_BRIDGE_RESULT_TOKEN: Final = object()
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_MAX_NUMERIC_CHARACTERS: Final = 4_096
_MAX_PROVENANCE_BYTES: Final = 1_048_576
_MAX_MANIFEST_DEPTH: Final = 32
_MAX_MANIFEST_CONTAINERS: Final = 1_000
_MAX_MANIFEST_SCALARS: Final = 10_000
_MAX_MANIFEST_TEXT: Final = 1_000_000

EYAGapCategory: TypeAlias = Literal[
    "measurement_boundary",
    "weather_resource",
    "availability",
    "curtailment",
    "electrical",
    "wake_performance",
    "method_model",
]
EYAActualBridgeErrorCode: TypeAlias = Literal[
    "INVALID_INPUT",
    "EYA_PROVENANCE_MISMATCH",
    "OPERATIONAL_PROVENANCE_MISMATCH",
    "BOUNDARY_MISMATCH",
    "TEMPORAL_MISMATCH",
    "ATTRIBUTION_MISMATCH",
    "ARITHMETIC_FAILED",
]

EYA_GAP_CATEGORIES: Final[tuple[EYAGapCategory, ...]] = (
    "measurement_boundary",
    "weather_resource",
    "availability",
    "curtailment",
    "electrical",
    "wake_performance",
    "method_model",
)
_CATEGORY_SET = frozenset(EYA_GAP_CATEGORIES)
_D3_COMPONENT_BY_CATEGORY: Final[dict[str, str]] = {
    "availability": "availability_loss",
    "curtailment": "curtailment_loss",
    "electrical": "electrical_loss",
    "wake_performance": "wake_performance_loss",
}


class EYAActualBridgeError(ValueError):
    """A predictable D4 failure with one closed error code."""

    code: EYAActualBridgeErrorCode

    def __init__(self, code: EYAActualBridgeErrorCode, message: str) -> None:
        """Initialize a closed bridge failure."""
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ResourceAssessmentSnapshot:
    """Deeply immutable binary64-exact snapshot of a ResourceAssessment."""

    capacity_mw_hex: str
    n_turbines: int
    net_aep_p50_gwh_hex: str
    net_aep_p75_gwh_hex: str
    net_aep_p90_gwh_hex: str
    capacity_factor_p50_hex: str
    capacity_factor_p75_hex: str
    capacity_factor_p90_hex: str
    selected_p_level: str
    report_grade: str
    run_manifest_json: str | None
    run_manifest_sha256: str | None
    source_id: str | None
    power_curve_key: str | None
    hours_per_year_hex: str
    identity_rtol_hex: str

    def __post_init__(self) -> None:
        """Validate the canonical immutable projection."""
        for field_name in (
            "capacity_mw_hex",
            "net_aep_p50_gwh_hex",
            "net_aep_p75_gwh_hex",
            "net_aep_p90_gwh_hex",
            "capacity_factor_p50_hex",
            "capacity_factor_p75_hex",
            "capacity_factor_p90_hex",
            "hours_per_year_hex",
            "identity_rtol_hex",
        ):
            _float_from_canonical_hex(getattr(self, field_name), field_name)
        if type(self.n_turbines) is not int or self.n_turbines <= 0:
            raise ValueError("n_turbines must be a positive real integer.")
        if (
            type(self.selected_p_level) is not str
            or self.selected_p_level not in P_LEVELS
        ):
            raise ValueError("selected_p_level must be canonical P50/P75/P90 text.")
        _require_text(self.report_grade, "report_grade")
        for field_name in ("source_id", "power_curve_key"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
        if self.run_manifest_json is None:
            if self.run_manifest_sha256 is not None:
                raise ValueError("absent run manifest cannot carry a digest.")
        else:
            if (
                type(self.run_manifest_json) is not str
                or type(self.run_manifest_sha256) is not str
                or _sha256(self.run_manifest_json.encode("utf-8"))
                != self.run_manifest_sha256
            ):
                raise ValueError("run manifest JSON does not match its digest.")
            parsed = json.loads(self.run_manifest_json)
            if not isinstance(parsed, dict):
                raise ValueError("run manifest snapshot must decode to an object.")
            if _canonical_json(parsed).decode("utf-8") != self.run_manifest_json:
                raise ValueError("run manifest snapshot is not canonical JSON.")

    @property
    def selected_net_aep_kwh(self) -> OperationalEnergyQuantity:
        """Return the selected EYA energy projected from exact binary64 bits."""
        selected = {
            "P50": self.net_aep_p50_gwh_hex,
            "P75": self.net_aep_p75_gwh_hex,
            "P90": self.net_aep_p90_gwh_hex,
        }[self.selected_p_level]
        value = Fraction.from_float(float.fromhex(selected)) * 1_000_000
        return OperationalEnergyQuantity.from_fraction(value)

    @property
    def hours_per_year(self) -> Fraction:
        """Return exact stored standard-year hours."""
        return Fraction.from_float(float.fromhex(self.hours_per_year_hex))

    def model_dump(self) -> dict[str, Any]:
        """Return the stable claim projection."""
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True)
class EYAActualBridgeSpec:
    """Expected source identities and closed arithmetic policy for one bridge."""

    bridge_id: str
    eya_p_level: Literal["P50", "P75", "P90"]
    expected_eya_claim_sha256: str
    expected_operational_claim_sha256: str
    category_partition_id: str
    arithmetic_policy: Literal["binary64_hex_to_fraction_kwh_v1"] = (
        "binary64_hex_to_fraction_kwh_v1"
    )

    def __post_init__(self) -> None:
        """Validate closed selectors and expected claims."""
        _require_identifier(self.bridge_id, "bridge_id")
        if type(self.eya_p_level) is not str or self.eya_p_level not in P_LEVELS:
            raise ValueError("eya_p_level must be P50, P75, or P90.")
        _require_digest(self.expected_eya_claim_sha256, "expected_eya_claim_sha256")
        _require_digest(
            self.expected_operational_claim_sha256,
            "expected_operational_claim_sha256",
        )
        _require_identifier(self.category_partition_id, "category_partition_id")
        if (
            type(self.arithmetic_policy) is not str
            or self.arithmetic_policy != "binary64_hex_to_fraction_kwh_v1"
        ):
            raise ValueError("arithmetic_policy is not supported.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible specification."""
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True)
class EYAActualBoundaryEvidence:
    """Provenance-bound common project, asset, and delivery boundary attestation."""

    project_id: str
    asset_identity: str
    delivery_boundary: Literal["net_export_at_common_delivery_boundary"]
    temporal_comparison: Literal["frozen_standard_year_eya_to_actual_calendar_year"]
    partition_semantics: Literal["mutually_exclusive_named_net_effect_categories"]
    category_partition_id: str
    eya_claim_sha256: str
    operational_claim_sha256: str
    source_locator: str
    source_bytes: bytes
    source_sha256: str
    method_bytes: bytes
    method_sha256: str

    def __post_init__(self) -> None:
        """Validate exact semantics and retained provenance bytes."""
        _require_identifier(self.project_id, "project_id")
        _require_text(self.asset_identity, "asset_identity")
        if (
            type(self.delivery_boundary) is not str
            or self.delivery_boundary != "net_export_at_common_delivery_boundary"
        ):
            raise ValueError("delivery_boundary must use the closed common boundary.")
        if (
            type(self.temporal_comparison) is not str
            or self.temporal_comparison
            != "frozen_standard_year_eya_to_actual_calendar_year"
        ):
            raise ValueError("temporal_comparison is not supported.")
        if (
            type(self.partition_semantics) is not str
            or self.partition_semantics
            != "mutually_exclusive_named_net_effect_categories"
        ):
            raise ValueError("partition_semantics is not supported.")
        _require_identifier(self.category_partition_id, "category_partition_id")
        _require_digest(self.eya_claim_sha256, "eya_claim_sha256")
        _require_digest(self.operational_claim_sha256, "operational_claim_sha256")
        _validate_provenance(
            self.source_locator,
            self.source_bytes,
            self.source_sha256,
            self.method_bytes,
            self.method_sha256,
        )

    def model_dump(self) -> dict[str, Any]:
        """Return the attested claim without retained source bytes."""
        self.__post_init__()
        return {
            "project_id": self.project_id,
            "asset_identity": self.asset_identity,
            "delivery_boundary": self.delivery_boundary,
            "temporal_comparison": self.temporal_comparison,
            "partition_semantics": self.partition_semantics,
            "category_partition_id": self.category_partition_id,
            "eya_claim_sha256": self.eya_claim_sha256,
            "operational_claim_sha256": self.operational_claim_sha256,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "method_sha256": self.method_sha256,
        }


@dataclass(frozen=True)
class EYAGapAttributionEvidence:
    """Paired expected/actual net-energy effects for one exclusive category."""

    evidence_id: str
    category: EYAGapCategory
    project_id: str
    category_partition_id: str
    eya_claim_sha256: str
    operational_claim_sha256: str
    eya_expected_net_effect_kwh: str
    operational_actual_net_effect_kwh: str
    sign_convention: Literal["positive_increases_actual_vs_eya"]
    source_locator: str
    source_bytes: bytes
    source_sha256: str
    method_bytes: bytes
    method_sha256: str

    def __post_init__(self) -> None:
        """Validate a complete paired comparison and immutable provenance."""
        _require_identifier(self.evidence_id, "evidence_id")
        if type(self.category) is not str or self.category not in _CATEGORY_SET:
            raise ValueError("category is not supported.")
        _require_identifier(self.project_id, "project_id")
        _require_identifier(self.category_partition_id, "category_partition_id")
        _require_digest(self.eya_claim_sha256, "eya_claim_sha256")
        _require_digest(self.operational_claim_sha256, "operational_claim_sha256")
        _fraction_from_decimal(self.eya_expected_net_effect_kwh)
        _fraction_from_decimal(self.operational_actual_net_effect_kwh)
        if (
            type(self.sign_convention) is not str
            or self.sign_convention != "positive_increases_actual_vs_eya"
        ):
            raise ValueError("sign_convention is not supported.")
        _validate_provenance(
            self.source_locator,
            self.source_bytes,
            self.source_sha256,
            self.method_bytes,
            self.method_sha256,
        )

    @property
    def delta(self) -> Fraction:
        """Return actual net effect minus EYA expected net effect."""
        return _fraction_from_decimal(
            self.operational_actual_net_effect_kwh
        ) - _fraction_from_decimal(self.eya_expected_net_effect_kwh)

    def model_dump(self) -> dict[str, Any]:
        """Return the paired claim without retained source bytes."""
        self.__post_init__()
        return {
            "evidence_id": self.evidence_id,
            "category": self.category,
            "project_id": self.project_id,
            "category_partition_id": self.category_partition_id,
            "eya_claim_sha256": self.eya_claim_sha256,
            "operational_claim_sha256": self.operational_claim_sha256,
            "eya_expected_net_effect_kwh": self.eya_expected_net_effect_kwh,
            "operational_actual_net_effect_kwh": (
                self.operational_actual_net_effect_kwh
            ),
            "sign_convention": self.sign_convention,
            "source_locator": self.source_locator,
            "source_sha256": self.source_sha256,
            "method_sha256": self.method_sha256,
        }


@dataclass(frozen=True)
class EYAGapComponent:
    """One exact signed category delta or an explicit unavailable state."""

    category: EYAGapCategory
    status: Literal["available", "unavailable"]
    signed_delta_kwh: OperationalEnergyQuantity | None
    eya_expected_net_effect_kwh: OperationalEnergyQuantity | None
    operational_actual_net_effect_kwh: OperationalEnergyQuantity | None
    evidence_id: str | None
    evidence_claim_sha256: str | None
    unavailable_reason: str | None

    def __post_init__(self) -> None:
        """Keep evidenced zero distinct from missing paired evidence."""
        if type(self.category) is not str or self.category not in _CATEGORY_SET:
            raise ValueError("gap component category is not supported.")
        values = (
            self.signed_delta_kwh,
            self.eya_expected_net_effect_kwh,
            self.operational_actual_net_effect_kwh,
        )
        if type(self.status) is not str:
            raise ValueError("gap component status is not supported.")
        if self.status == "available":
            fractions = tuple(
                _exact_energy_fraction(item, "gap component value") for item in values
            )
            _require_identifier(self.evidence_id, "evidence_id")
            _require_digest(self.evidence_claim_sha256, "evidence_claim_sha256")
            if self.unavailable_reason is not None:
                raise ValueError("available gap components cannot carry a reason.")
            delta, expected, actual = fractions
            if actual - expected != delta:
                raise ValueError("gap component values do not reconcile.")
        elif self.status == "unavailable":
            if any(item is not None for item in values) or any(
                item is not None
                for item in (self.evidence_id, self.evidence_claim_sha256)
            ):
                raise ValueError(
                    "unavailable gap components cannot carry evidence values."
                )
            _require_text(self.unavailable_reason, "unavailable_reason")
        else:
            raise ValueError("gap component status is not supported.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible component."""
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True)
class FinanceUpdateProposal:
    """Structurally inert proposal retaining the current canonical basis."""

    eya_claim_sha256: str
    operational_claim_sha256: str
    decision: Literal["retain_current_canonical_basis_pending_r3"] = (
        "retain_current_canonical_basis_pending_r3"
    )
    default_off: Literal[True] = True
    proposed_updates: tuple[()] = ()
    target_scenario_id: None = None
    candidate_capacity_factor: None = None
    candidate_p50: None = None
    candidate_p90: None = None
    candidate_debt: None = None
    candidate_tariff: None = None
    apply_authorized: Literal[False] = False
    requires_separate_r3_rebaseline: Literal[True] = True
    issue_1110_state: Literal["OPEN_HOLD"] = "OPEN_HOLD"
    canonical_finance_eligible: Literal[False] = False
    bankable: Literal[False] = False
    lender_eligible: Literal[False] = False
    board_eligible: Literal[False] = False
    release_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        """Reject any candidate value, update, authority, or HOLD laundering."""
        _require_digest(self.eya_claim_sha256, "eya_claim_sha256")
        _require_digest(self.operational_claim_sha256, "operational_claim_sha256")
        if (
            type(self.decision) is not str
            or self.decision != "retain_current_canonical_basis_pending_r3"
        ):
            raise ValueError("finance proposal decision must retain the current basis.")
        if type(self.default_off) is not bool or self.default_off is not True:
            raise ValueError("finance proposal must be exactly default_off=True.")
        if type(self.proposed_updates) is not tuple or self.proposed_updates != ():
            raise ValueError("finance proposal updates must be the empty tuple.")
        for field_name in (
            "target_scenario_id",
            "candidate_capacity_factor",
            "candidate_p50",
            "candidate_p90",
            "candidate_debt",
            "candidate_tariff",
        ):
            if getattr(self, field_name) is not None:
                raise ValueError(f"{field_name} must remain unavailable.")
        if (
            type(self.requires_separate_r3_rebaseline) is not bool
            or self.requires_separate_r3_rebaseline is not True
        ):
            raise ValueError("a separate R3 re-baseline must remain required.")
        if (
            type(self.issue_1110_state) is not str
            or self.issue_1110_state != "OPEN_HOLD"
        ):
            raise ValueError("issue_1110_state must remain OPEN_HOLD.")
        for field_name in (
            "apply_authorized",
            "canonical_finance_eligible",
            "bankable",
            "lender_eligible",
            "board_eligible",
            "release_eligible",
        ):
            value = getattr(self, field_name)
            if type(value) is not bool or value is not False:
                raise ValueError(f"{field_name} must be the exact boolean False.")

    def model_dump(self) -> dict[str, Any]:
        """Return an inert JSON-compatible proposal."""
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True)
class EYAActualBridgeReceipt:
    """Exact source, method, arithmetic, and authority receipt."""

    schema: str
    bridge_id: str
    project_id: str
    asset_identity: str
    eya_claim_sha256: str
    operational_claim_sha256: str
    boundary_claim_sha256: str
    attribution_manifest_sha256: str
    method_sha256: str
    finance_proposal_sha256: str
    arithmetic_policy: Literal["binary64_hex_to_fraction_kwh_v1"]
    sign_convention: Literal["positive_increases_actual_vs_eya"]
    full_reconciliation_residual_kwh: OperationalEnergyQuantity
    full_reconciliation_semantics: Literal[
        "arithmetic_identity_not_independent_check"
    ] = "arithmetic_identity_not_independent_check"
    original_sources_preserved: Literal[True] = True
    canonical_mutation_performed: Literal[False] = False
    issue_1110_state: Literal["OPEN_HOLD"] = "OPEN_HOLD"
    canonical_finance_eligible: Literal[False] = False
    bankable: Literal[False] = False
    lender_eligible: Literal[False] = False
    board_eligible: Literal[False] = False
    release_eligible: Literal[False] = False

    def __post_init__(self) -> None:
        """Validate reconciliation identity and non-authority fences."""
        if (
            type(self.full_reconciliation_semantics) is not str
            or self.full_reconciliation_semantics
            != "arithmetic_identity_not_independent_check"
        ):
            raise ValueError(
                "full reconciliation must disclose arithmetic identity semantics."
            )
        if type(self.schema) is not str or self.schema != EYA_ACTUAL_BRIDGE_SCHEMA:
            raise ValueError("bridge receipt schema is not supported.")
        _require_identifier(self.bridge_id, "bridge_id")
        _require_identifier(self.project_id, "project_id")
        _require_text(self.asset_identity, "asset_identity")
        for field_name in (
            "eya_claim_sha256",
            "operational_claim_sha256",
            "boundary_claim_sha256",
            "attribution_manifest_sha256",
            "method_sha256",
            "finance_proposal_sha256",
        ):
            _require_digest(getattr(self, field_name), field_name)
        if (
            type(self.arithmetic_policy) is not str
            or self.arithmetic_policy != "binary64_hex_to_fraction_kwh_v1"
        ):
            raise ValueError("bridge receipt arithmetic policy is not supported.")
        if (
            type(self.sign_convention) is not str
            or self.sign_convention != "positive_increases_actual_vs_eya"
        ):
            raise ValueError("bridge receipt sign convention is not supported.")
        if (
            _exact_energy_fraction(
                self.full_reconciliation_residual_kwh,
                "full_reconciliation_residual_kwh",
            )
            != 0
        ):
            raise ValueError("full bridge reconciliation residual must be exact zero.")
        if (
            type(self.original_sources_preserved) is not bool
            or self.original_sources_preserved is not True
        ):
            raise ValueError("original source preservation must be exactly true.")
        if (
            type(self.issue_1110_state) is not str
            or self.issue_1110_state != "OPEN_HOLD"
        ):
            raise ValueError("issue_1110_state must remain OPEN_HOLD.")
        for field_name in (
            "canonical_mutation_performed",
            "canonical_finance_eligible",
            "bankable",
            "lender_eligible",
            "board_eligible",
            "release_eligible",
        ):
            value = getattr(self, field_name)
            if type(value) is not bool or value is not False:
                raise ValueError(f"{field_name} must be the exact boolean False.")

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-compatible receipt."""
        self.__post_init__()
        return asdict(self)


@dataclass(frozen=True)
class EYAActualBridgeResult:
    """Factory-only additive bridge over exact immutable source claims."""

    resource_snapshot: ResourceAssessmentSnapshot
    operational_result: OperationalAEPResult
    spec: EYAActualBridgeSpec
    boundary_evidence: EYAActualBoundaryEvidence
    attribution_evidence: tuple[EYAGapAttributionEvidence, ...]
    eya_net_energy_kwh: OperationalEnergyQuantity
    actual_net_energy_kwh: OperationalEnergyQuantity
    total_gap_kwh: OperationalEnergyQuantity
    category_components: tuple[EYAGapComponent, ...]
    unknown_residual_kwh: OperationalEnergyQuantity
    finance_proposal: FinanceUpdateProposal
    receipt: EYAActualBridgeReceipt
    _factory_token: InitVar[object] = None

    def __post_init__(self, _factory_token: object) -> None:
        """Replay every source claim, category, proposal, and arithmetic output."""
        if _factory_token is not _BRIDGE_RESULT_TOKEN:
            raise ValueError(
                "EYA-to-actual results must be constructed by build_eya_actual_bridge."
            )
        artifacts = _build_artifacts(
            self.resource_snapshot,
            self.operational_result,
            self.spec,
            self.boundary_evidence,
            self.attribution_evidence,
        )
        actual_outputs = _result_output_projection(
            self.eya_net_energy_kwh,
            self.actual_net_energy_kwh,
            self.total_gap_kwh,
            self.category_components,
            self.unknown_residual_kwh,
            self.finance_proposal,
            self.receipt,
        )
        expected_outputs = _result_output_projection(
            artifacts.eya_net_energy_kwh,
            artifacts.actual_net_energy_kwh,
            artifacts.total_gap_kwh,
            artifacts.category_components,
            artifacts.unknown_residual_kwh,
            artifacts.finance_proposal,
            artifacts.receipt,
        )
        if _canonical_json(actual_outputs) != _canonical_json(expected_outputs):
            raise ValueError(
                "EYA-to-actual result does not replay from retained inputs."
            )

    def component(self, category: EYAGapCategory) -> EYAGapComponent:
        """Return one named category component."""
        for component in self.category_components:
            if component.category == category:
                return component
        raise KeyError(category)

    def model_dump(self) -> dict[str, Any]:
        """Return bridge outputs without retained provenance or D3 source bytes."""
        self.__post_init__(_BRIDGE_RESULT_TOKEN)
        return {
            "schema": self.receipt.schema,
            "resource_snapshot": self.resource_snapshot.model_dump(),
            "eya_net_energy_kwh": _energy_payload(
                self.eya_net_energy_kwh, "eya_net_energy_kwh"
            ),
            "actual_net_energy_kwh": _energy_payload(
                self.actual_net_energy_kwh, "actual_net_energy_kwh"
            ),
            "total_gap_kwh": _energy_payload(self.total_gap_kwh, "total_gap_kwh"),
            "category_components": [
                item.model_dump() for item in self.category_components
            ],
            "unknown_residual_kwh": _energy_payload(
                self.unknown_residual_kwh, "unknown_residual_kwh"
            ),
            "finance_proposal": self.finance_proposal.model_dump(),
            "receipt": self.receipt.model_dump(),
        }


@dataclass(frozen=True)
class _BridgeArtifacts:
    eya_net_energy_kwh: OperationalEnergyQuantity
    actual_net_energy_kwh: OperationalEnergyQuantity
    total_gap_kwh: OperationalEnergyQuantity
    category_components: tuple[EYAGapComponent, ...]
    unknown_residual_kwh: OperationalEnergyQuantity
    finance_proposal: FinanceUpdateProposal
    receipt: EYAActualBridgeReceipt


def _exact_energy_fraction(value: object, field_name: str) -> Fraction:
    """Validate and return one exact built-in D3 quantity without dispatch."""
    if type(value) is not OperationalEnergyQuantity:
        raise ValueError(
            f"{field_name} must use the exact OperationalEnergyQuantity contract."
        )
    numerator = value.numerator
    denominator = value.denominator
    unit = value.unit
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or type(unit) is not str
    ):
        raise ValueError(f"{field_name} has a non-canonical stored representation.")
    canonical = OperationalEnergyQuantity(numerator, denominator, unit)
    return Fraction(canonical.numerator, canonical.denominator)


def _energy_payload(value: object, field_name: str) -> dict[str, Any]:
    """Return a validated quantity payload without calling overridable methods."""
    _exact_energy_fraction(value, field_name)
    assert type(value) is OperationalEnergyQuantity
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "unit": value.unit,
    }


def _result_output_projection(
    eya_net_energy_kwh: object,
    actual_net_energy_kwh: object,
    total_gap_kwh: object,
    category_components: object,
    unknown_residual_kwh: object,
    finance_proposal: object,
    receipt: object,
) -> dict[str, Any]:
    """Return the revalidated D4-owned state used for replay comparison."""
    if type(category_components) is not tuple or not all(
        type(item) is EYAGapComponent for item in category_components
    ):
        raise ValueError("category_components must use the exact immutable contracts.")
    if type(finance_proposal) is not FinanceUpdateProposal:
        raise ValueError("finance_proposal must use the exact D4 contract.")
    if type(receipt) is not EYAActualBridgeReceipt:
        raise ValueError("receipt must use the exact D4 contract.")
    return {
        "eya_net_energy_kwh": _energy_payload(eya_net_energy_kwh, "eya_net_energy_kwh"),
        "actual_net_energy_kwh": _energy_payload(
            actual_net_energy_kwh, "actual_net_energy_kwh"
        ),
        "total_gap_kwh": _energy_payload(total_gap_kwh, "total_gap_kwh"),
        "category_components": [item.model_dump() for item in category_components],
        "unknown_residual_kwh": _energy_payload(
            unknown_residual_kwh, "unknown_residual_kwh"
        ),
        "finance_proposal": finance_proposal.model_dump(),
        "receipt": receipt.model_dump(),
    }


def _require_identifier(value: object, field_name: str) -> str:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a closed identifier.")
    return value


def _require_text(value: object, field_name: str) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or "\n" in value
        or "\r" in value
    ):
        raise ValueError(f"{field_name} must be non-empty closed text.")
    return value


def _require_digest(value: object, field_name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return value


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _claim_digest(domain: str, payload: object) -> str:
    return _sha256(domain.encode("ascii") + b"\x00" + _canonical_json(payload))


def _float_from_canonical_hex(value: object, field_name: str) -> float:
    if type(value) is not str:
        raise ValueError(f"{field_name} must be canonical binary64 hex text.")
    try:
        parsed = float.fromhex(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} is not valid binary64 hex text.") from exc
    if not math.isfinite(parsed) or parsed.hex() != value:
        raise ValueError(f"{field_name} must be finite canonical binary64 hex text.")
    return parsed


def _fraction_from_decimal(value: object) -> Fraction:
    if (
        type(value) is not str
        or len(value) > _MAX_NUMERIC_CHARACTERS
        or _DECIMAL_RE.fullmatch(value) is None
    ):
        raise ValueError("energy effects must be bounded finite decimal strings.")
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


def _validate_provenance(
    source_locator: object,
    source_bytes: object,
    source_sha256: object,
    method_bytes: object,
    method_sha256: object,
) -> None:
    _require_text(source_locator, "source_locator")
    if type(source_bytes) is not bytes or not source_bytes:
        raise ValueError("source_bytes must be non-empty exact built-in bytes.")
    if type(method_bytes) is not bytes or not method_bytes:
        raise ValueError("method_bytes must be non-empty exact built-in bytes.")
    if (
        len(source_bytes) > _MAX_PROVENANCE_BYTES
        or len(method_bytes) > _MAX_PROVENANCE_BYTES
    ):
        raise ValueError("provenance artifacts must not exceed 1 MiB each.")
    if type(source_sha256) is not str or _sha256(source_bytes) != source_sha256:
        raise ValueError("source bytes do not match source_sha256.")
    if type(method_sha256) is not str or _sha256(method_bytes) != method_sha256:
        raise ValueError("method bytes do not match method_sha256.")
    if source_sha256 == method_sha256:
        raise ValueError("source and method artifacts must have distinct identities.")


def _manifest_snapshot(value: object) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if type(value) is not dict:
        raise ValueError("run_manifest must be None or an exact dictionary.")
    active: set[int] = set()
    counts = [0, 0, 0]

    def detach(item: object, depth: int) -> object:
        if depth > _MAX_MANIFEST_DEPTH:
            raise ValueError("run_manifest exceeds the maximum depth.")
        if type(item) is dict:
            marker = id(item)
            if marker in active:
                raise ValueError("run_manifest contains a cycle.")
            counts[0] += 1
            if counts[0] > _MAX_MANIFEST_CONTAINERS:
                raise ValueError("run_manifest contains too many containers.")
            active.add(marker)
            try:
                detached: dict[str, object] = {}
                for key, nested in item.items():
                    if type(key) is not str:
                        raise ValueError("run_manifest keys must be exact strings.")
                    counts[2] += len(key)
                    detached[key] = detach(nested, depth + 1)
                return detached
            finally:
                active.remove(marker)
        if type(item) is list:
            marker = id(item)
            if marker in active:
                raise ValueError("run_manifest contains a cycle.")
            counts[0] += 1
            if counts[0] > _MAX_MANIFEST_CONTAINERS:
                raise ValueError("run_manifest contains too many containers.")
            active.add(marker)
            try:
                return [detach(nested, depth + 1) for nested in item]
            finally:
                active.remove(marker)
        counts[1] += 1
        if counts[1] > _MAX_MANIFEST_SCALARS:
            raise ValueError("run_manifest contains too many scalar values.")
        if item is None or type(item) is bool:
            return item
        if type(item) is str:
            counts[2] += len(item)
            if counts[2] > _MAX_MANIFEST_TEXT:
                raise ValueError("run_manifest text exceeds the bounded volume.")
            return item
        if type(item) is int:
            if item.bit_length() > 4_096:
                raise ValueError("run_manifest integer exceeds the bounded size.")
            return item
        if type(item) is float and math.isfinite(item):
            return item
        raise ValueError("run_manifest contains an unsupported scalar or container.")

    detached = detach(value, 0)
    encoded = _canonical_json(detached)
    if len(encoded) > _MAX_PROVENANCE_BYTES:
        raise ValueError("run_manifest canonical JSON exceeds 1 MiB.")
    rendered = encoded.decode("ascii")
    return rendered, _sha256(encoded)


def _snapshot_resource_assessment(value: object) -> ResourceAssessmentSnapshot:
    if type(value) is not ResourceAssessment:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "resource_assessment must use the exact public contract."
        )
    float_fields = (
        "capacity_mw",
        "net_aep_p50_gwh",
        "net_aep_p75_gwh",
        "net_aep_p90_gwh",
        "capacity_factor_p50",
        "capacity_factor_p75",
        "capacity_factor_p90",
        "hours_per_year",
        "identity_rtol",
    )
    for field_name in float_fields:
        item = getattr(value, field_name)
        if type(item) is not float or not math.isfinite(item):
            raise EYAActualBridgeError(
                "INVALID_INPUT",
                f"ResourceAssessment.{field_name} must be a finite exact float.",
            )
    if type(value.n_turbines) is not int or value.n_turbines <= 0:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "ResourceAssessment.n_turbines must be a positive integer."
        )
    if (
        type(value.selected_p_level) is not str
        or value.selected_p_level not in P_LEVELS
    ):
        raise EYAActualBridgeError(
            "INVALID_INPUT", "ResourceAssessment selected P-level must be canonical."
        )
    try:
        _require_text(value.report_grade, "report_grade")
        for field_name in ("source_id", "power_curve_key"):
            item = getattr(value, field_name)
            if item is not None:
                _require_text(item, field_name)
        if not 0.0 <= value.identity_rtol <= DEFAULT_IDENTITY_RTOL:
            raise ValueError(
                "identity_rtol cannot exceed the canonical ResourceAssessment default."
            )
        manifest_json, manifest_sha = _manifest_snapshot(value.run_manifest)
        manifest_copy = None if manifest_json is None else json.loads(manifest_json)
        reconstructed = ResourceAssessment(
            capacity_mw=value.capacity_mw,
            n_turbines=value.n_turbines,
            net_aep_p50_gwh=value.net_aep_p50_gwh,
            net_aep_p75_gwh=value.net_aep_p75_gwh,
            net_aep_p90_gwh=value.net_aep_p90_gwh,
            capacity_factor_p50=value.capacity_factor_p50,
            capacity_factor_p75=value.capacity_factor_p75,
            capacity_factor_p90=value.capacity_factor_p90,
            selected_p_level=value.selected_p_level,
            report_grade=value.report_grade,
            run_manifest=manifest_copy,
            source_id=value.source_id,
            power_curve_key=value.power_curve_key,
            hours_per_year=value.hours_per_year,
            identity_rtol=value.identity_rtol,
        )
    except (AttributeError, ResourceAssessmentError, TypeError, ValueError) as exc:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "ResourceAssessment failed defensive reconstruction."
        ) from exc
    if any(
        getattr(reconstructed, field_name) != getattr(value, field_name)
        for field_name in float_fields
    ):
        raise EYAActualBridgeError(
            "INVALID_INPUT", "ResourceAssessment changed during reconstruction."
        )
    return ResourceAssessmentSnapshot(
        capacity_mw_hex=value.capacity_mw.hex(),
        n_turbines=value.n_turbines,
        net_aep_p50_gwh_hex=value.net_aep_p50_gwh.hex(),
        net_aep_p75_gwh_hex=value.net_aep_p75_gwh.hex(),
        net_aep_p90_gwh_hex=value.net_aep_p90_gwh.hex(),
        capacity_factor_p50_hex=value.capacity_factor_p50.hex(),
        capacity_factor_p75_hex=value.capacity_factor_p75.hex(),
        capacity_factor_p90_hex=value.capacity_factor_p90.hex(),
        selected_p_level=value.selected_p_level,
        report_grade=value.report_grade,
        run_manifest_json=manifest_json,
        run_manifest_sha256=manifest_sha,
        source_id=value.source_id,
        power_curve_key=value.power_curve_key,
        hours_per_year_hex=value.hours_per_year.hex(),
        identity_rtol_hex=value.identity_rtol.hex(),
    )


def _resource_snapshot_claim_sha256(snapshot: ResourceAssessmentSnapshot) -> str:
    return _claim_digest(
        "dutchbay.resource_assessment.binary64_snapshot.v1", snapshot.model_dump()
    )


def resource_assessment_claim_sha256(value: ResourceAssessment) -> str:
    """Return the domain-separated digest of a defensive EYA snapshot."""
    try:
        return _resource_snapshot_claim_sha256(_snapshot_resource_assessment(value))
    except EYAActualBridgeError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "resource assessment claim could not be constructed."
        ) from exc


def _exact_buffer_bytes(value: object, field_name: str) -> bytes:
    """Detach one bytes-compatible retained artifact through its buffer."""
    if not isinstance(value, bytes):
        raise ValueError(f"{field_name} must be immutable bytes.")
    return memoryview(value).tobytes()


def _reconstruct_d1_evidence(value: object) -> OperationalDatasetEvidence:
    """Reconstruct one exact D1 envelope and its exact tuple of columns."""
    if (
        type(value) is not OperationalDatasetEvidence
        or type(value.columns) is not tuple
    ):
        raise ValueError("retained D1 evidence must use exact public contracts.")
    columns = tuple(
        OperationalColumnBinding(item.role, item.source_column, item.unit)
        for item in value.columns
        if type(item) is OperationalColumnBinding
    )
    if len(columns) != len(value.columns):
        raise ValueError("retained D1 columns contain a non-exact binding.")
    if type(value.lineage_source_sha256) is not tuple:
        raise ValueError("retained D1 lineage must use an exact tuple.")
    return OperationalDatasetEvidence(
        logical_id=value.logical_id,
        kind=value.kind,
        source_class=value.source_class,
        timezone_treatment=value.timezone_treatment,
        source_timezone=value.source_timezone,
        ambiguous_time_policy=value.ambiguous_time_policy,
        nonexistent_time_policy=value.nonexistent_time_policy,
        observation_status=value.observation_status,
        lineage_source_sha256=tuple(value.lineage_source_sha256),
        derivation_method_sha256=value.derivation_method_sha256,
        source_locator=value.source_locator,
        source_sha256=value.source_sha256,
        coverage_start_utc=value.coverage_start_utc,
        coverage_end_utc=value.coverage_end_utc,
        interval_basis=value.interval_basis,
        interval_seconds=value.interval_seconds,
        row_count=value.row_count,
        columns=columns,
    )


def _reconstruct_assessment(value: object) -> OperationalAssessmentInput:
    """Reconstruct one exact D1 assessment before D3 replay."""
    if (
        type(value) is not OperationalAssessmentInput
        or type(value.datasets) is not tuple
    ):
        raise ValueError("retained D1 assessments must use exact public contracts.")
    return OperationalAssessmentInput(
        schema=value.schema,
        project_id=value.project_id,
        assessment_id=value.assessment_id,
        purpose=value.purpose,
        assessment_start_utc=value.assessment_start_utc,
        assessment_end_utc=value.assessment_end_utc,
        datasets=tuple(_reconstruct_d1_evidence(item) for item in value.datasets),
        raw_evidence_only=value.raw_evidence_only,
        canonical_finance_eligible=value.canonical_finance_eligible,
        bankable=value.bankable,
        lender_eligible=value.lender_eligible,
        board_eligible=value.board_eligible,
    )


def _reconstruct_timezone_rules(value: object) -> OperationalTimezoneRules | None:
    """Detach retained TZif bytes before any parser receives them."""
    if value is None:
        return None
    if type(value) is not OperationalTimezoneRules:
        raise ValueError("retained timezone rules use the wrong runtime contract.")
    return OperationalTimezoneRules(
        source_timezone=value.source_timezone,
        tzif_bytes=_exact_buffer_bytes(value.tzif_bytes, "tzif_bytes"),
        source_locator=value.source_locator,
    )


def _replay_d2_with_exact_bytes(
    value: object,
    *,
    active: set[int],
) -> OperationalNormalizationResult:
    """Replay D2 after detaching every retained byte-bearing input."""
    if type(value) is not OperationalNormalizationResult:
        raise ValueError("retained D2 result uses the wrong runtime contract.")
    marker = id(value)
    if marker in active:
        raise ValueError("retained D2 result graph contains a cycle.")
    active.add(marker)
    try:
        evidence = _reconstruct_d1_evidence(value.evidence)
        if type(value.lineage_source_bytes) is not tuple:
            raise ValueError("retained D2 lineage bytes must use an exact tuple.")
        lineage = tuple(
            _exact_buffer_bytes(item, "lineage_source_bytes")
            for item in value.lineage_source_bytes
        )
        derivation = (
            None
            if value.derivation_method_bytes is None
            else _exact_buffer_bytes(
                value.derivation_method_bytes, "derivation_method_bytes"
            )
        )
        timezone_rules = _reconstruct_timezone_rules(value.timezone_rules)
        group_universe = value.group_universe
        if group_universe is not None:
            if type(group_universe) is not OperationalGroupUniverse:
                raise ValueError("retained group universe uses the wrong contract.")
            group_universe = OperationalGroupUniverse(
                _replay_d2_with_exact_bytes(
                    group_universe.asset_result,
                    active=active,
                )
            )
        receipt = value.receipt
        if type(receipt) is not OperationalQualityReceipt:
            raise ValueError("retained D2 receipt uses the wrong runtime contract.")
        if (
            type(receipt.column_exclusions) is not tuple
            or type(receipt.row_exclusions) is not tuple
        ):
            raise ValueError("retained D2 exclusions must use exact tuples.")
        column_exclusions = tuple(
            OperationalColumnExclusion(item.source_column, item.reason)
            for item in receipt.column_exclusions
            if type(item) is OperationalColumnExclusion
        )
        row_exclusions = tuple(
            OperationalRowExclusion(item.source_row_number, item.reason)
            for item in receipt.row_exclusions
            if type(item) is OperationalExcludedRowReceipt
        )
        if len(column_exclusions) != len(receipt.column_exclusions) or len(
            row_exclusions
        ) != len(receipt.row_exclusions):
            raise ValueError("retained D2 exclusions contain non-exact contracts.")
        return normalize_operational_csv(
            _exact_buffer_bytes(value.source_bytes, "source_bytes"),
            evidence,
            lineage_source_bytes=lineage,
            derivation_method_bytes=derivation,
            timezone_rules=timezone_rules,
            group_universe=group_universe,
            column_exclusions=column_exclusions,
            row_exclusions=row_exclusions,
        )
    finally:
        active.remove(marker)


def _reconstruct_operational_inputs(value: object) -> OperationalAEPInput:
    """Reconstruct exact D1-D3 inputs before operational replay."""
    if type(value) is not OperationalAEPInput:
        raise ValueError("retained D3 inputs use the wrong runtime contract.")
    for field_name in ("assessments", "normalized_results", "supplemental_evidence"):
        if type(getattr(value, field_name)) is not tuple:
            raise ValueError(f"retained D3 {field_name} must use an exact tuple.")
    boundary = value.boundary_evidence
    if type(boundary) is not OperationalBoundaryEvidence:
        raise ValueError("retained D3 boundary uses the wrong runtime contract.")
    reconstructed_boundary = OperationalBoundaryEvidence(
        project_id=boundary.project_id,
        effective_start_utc=boundary.effective_start_utc,
        effective_end_exclusive_utc=boundary.effective_end_exclusive_utc,
        meter_logical_id=boundary.meter_logical_id,
        turbine_logical_id=boundary.turbine_logical_id,
        availability_logical_id=boundary.availability_logical_id,
        curtailment_logical_id=boundary.curtailment_logical_id,
        meter_energy_basis=boundary.meter_energy_basis,
        turbine_energy_basis=boundary.turbine_energy_basis,
        loss_energy_basis=boundary.loss_energy_basis,
        interval_boundary=boundary.interval_boundary,
        excluded_flows=boundary.excluded_flows,
        asset_universe_basis=boundary.asset_universe_basis,
        source_locator=boundary.source_locator,
        source_bytes=_exact_buffer_bytes(boundary.source_bytes, "source_bytes"),
        source_sha256=boundary.source_sha256,
        method_bytes=_exact_buffer_bytes(boundary.method_bytes, "method_bytes"),
        method_sha256=boundary.method_sha256,
    )
    supplements: list[OperationalSupplementalEnergyEvidence] = []
    for item in value.supplemental_evidence:
        if type(item) is not OperationalSupplementalEnergyEvidence:
            raise ValueError("retained D3 supplement uses the wrong runtime contract.")
        supplements.append(
            OperationalSupplementalEnergyEvidence(
                evidence_id=item.evidence_id,
                component=item.component,
                project_id=item.project_id,
                effective_start_utc=item.effective_start_utc,
                effective_end_exclusive_utc=item.effective_end_exclusive_utc,
                value_kwh=item.value_kwh,
                boundary=item.boundary,
                source_locator=item.source_locator,
                source_bytes=_exact_buffer_bytes(item.source_bytes, "source_bytes"),
                source_sha256=item.source_sha256,
                method_bytes=_exact_buffer_bytes(item.method_bytes, "method_bytes"),
                method_sha256=item.method_sha256,
            )
        )
    active: set[int] = set()
    return OperationalAEPInput(
        assessments=tuple(_reconstruct_assessment(item) for item in value.assessments),
        normalized_results=tuple(
            _replay_d2_with_exact_bytes(item, active=active)
            for item in value.normalized_results
        ),
        boundary_evidence=reconstructed_boundary,
        supplemental_evidence=tuple(supplements),
    )


def _reconstruct_operational_spec(value: object) -> OperationalAEPSpec:
    """Reconstruct the exact D3 specification without mapping dispatch."""
    if type(value) is not OperationalAEPSpec:
        raise ValueError("retained D3 spec uses the wrong runtime contract.")
    return OperationalAEPSpec(
        project_id=value.project_id,
        assessment_id=value.assessment_id,
        effective_start_utc=value.effective_start_utc,
        effective_end_exclusive_utc=value.effective_end_exclusive_utc,
        temporal_basis=value.temporal_basis,
        meter_logical_id=value.meter_logical_id,
        turbine_logical_id=value.turbine_logical_id,
        availability_logical_id=value.availability_logical_id,
        curtailment_logical_id=value.curtailment_logical_id,
        absolute_tolerance_kwh=value.absolute_tolerance_kwh,
    )


def _replay_operational_result(value: object) -> OperationalAEPResult:
    if type(value) is not OperationalAEPResult:
        raise EYAActualBridgeError(
            "OPERATIONAL_PROVENANCE_MISMATCH",
            "operational result must use the exact D3 public contract.",
        )
    try:
        replay = estimate_operational_aep(
            _reconstruct_operational_inputs(value.inputs),
            _reconstruct_operational_spec(value.spec),
        )
    except (
        OperationalAEPError,
        OperationalNormalizationError,
        AttributeError,
        BufferError,
        TypeError,
        ValueError,
    ) as exc:
        raise EYAActualBridgeError(
            "OPERATIONAL_PROVENANCE_MISMATCH",
            "operational result no longer replays from retained D1-D3 inputs.",
        ) from exc
    if replay != value:
        raise EYAActualBridgeError(
            "OPERATIONAL_PROVENANCE_MISMATCH",
            "operational result differs from its deterministic replay.",
        )
    return replay


def _operational_result_claim_sha256(value: OperationalAEPResult) -> str:
    replay = _replay_operational_result(value)
    return _claim_digest(
        "dutchbay.operational_aep_result.v1",
        {"spec": replay.spec.model_dump(), "result": replay.model_dump()},
    )


def operational_aep_claim_sha256(value: OperationalAEPResult) -> str:
    """Replay D3 and return its domain-separated exact-result digest."""
    return _operational_result_claim_sha256(value)


def _attribution_claim_sha256(value: EYAGapAttributionEvidence) -> str:
    return _claim_digest("dutchbay.eya_gap_attribution_pair.v1", value.model_dump())


def _unavailable_component(category: EYAGapCategory) -> EYAGapComponent:
    return EYAGapComponent(
        category=category,
        status="unavailable",
        signed_delta_kwh=None,
        eya_expected_net_effect_kwh=None,
        operational_actual_net_effect_kwh=None,
        evidence_id=None,
        evidence_claim_sha256=None,
        unavailable_reason="no_paired_provenance_bound_comparison",
    )


def _available_component(value: EYAGapAttributionEvidence) -> EYAGapComponent:
    expected = _fraction_from_decimal(value.eya_expected_net_effect_kwh)
    actual = _fraction_from_decimal(value.operational_actual_net_effect_kwh)
    return EYAGapComponent(
        category=value.category,
        status="available",
        signed_delta_kwh=OperationalEnergyQuantity.from_fraction(actual - expected),
        eya_expected_net_effect_kwh=OperationalEnergyQuantity.from_fraction(expected),
        operational_actual_net_effect_kwh=OperationalEnergyQuantity.from_fraction(
            actual
        ),
        evidence_id=value.evidence_id,
        evidence_claim_sha256=_attribution_claim_sha256(value),
        unavailable_reason=None,
    )


def _actual_net_energy(value: OperationalAEPResult) -> Fraction:
    component = value.component("net_meter_energy")
    if component.status != "available" or component.value is None:
        raise EYAActualBridgeError(
            "OPERATIONAL_PROVENANCE_MISMATCH",
            "D3 net meter energy must be available.",
        )
    return component.value.as_fraction()


def _validate_category_actual(
    evidence: EYAGapAttributionEvidence, operational: OperationalAEPResult
) -> None:
    component_name = _D3_COMPONENT_BY_CATEGORY.get(evidence.category)
    if component_name is None:
        return
    component = operational.component(component_name)  # type: ignore[arg-type]
    if component.status != "available" or component.value is None:
        raise EYAActualBridgeError(
            "ATTRIBUTION_MISMATCH",
            f"category {evidence.category!r} lacks an available D3 component.",
        )
    claimed = _fraction_from_decimal(evidence.operational_actual_net_effect_kwh)
    if claimed != -component.value.as_fraction():
        raise EYAActualBridgeError(
            "ATTRIBUTION_MISMATCH",
            f"category {evidence.category!r} actual net effect does not match D3.",
        )


def _build_artifacts(
    resource_snapshot: ResourceAssessmentSnapshot,
    operational_result: OperationalAEPResult,
    spec: EYAActualBridgeSpec,
    boundary: EYAActualBoundaryEvidence,
    attributions: tuple[EYAGapAttributionEvidence, ...],
) -> _BridgeArtifacts:
    if type(resource_snapshot) is not ResourceAssessmentSnapshot:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "resource snapshot type is invalid."
        )
    if type(spec) is not EYAActualBridgeSpec:
        raise EYAActualBridgeError("INVALID_INPUT", "bridge spec type is invalid.")
    if type(boundary) is not EYAActualBoundaryEvidence:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "boundary evidence type is invalid."
        )
    if type(attributions) is not tuple or not all(
        type(item) is EYAGapAttributionEvidence for item in attributions
    ):
        raise EYAActualBridgeError(
            "INVALID_INPUT", "attribution evidence must be an exact immutable tuple."
        )
    try:
        resource_snapshot = ResourceAssessmentSnapshot(**resource_snapshot.model_dump())
        spec = EYAActualBridgeSpec(**spec.model_dump())
        boundary = EYAActualBoundaryEvidence(
            project_id=boundary.project_id,
            asset_identity=boundary.asset_identity,
            delivery_boundary=boundary.delivery_boundary,
            temporal_comparison=boundary.temporal_comparison,
            partition_semantics=boundary.partition_semantics,
            category_partition_id=boundary.category_partition_id,
            eya_claim_sha256=boundary.eya_claim_sha256,
            operational_claim_sha256=boundary.operational_claim_sha256,
            source_locator=boundary.source_locator,
            source_bytes=boundary.source_bytes,
            source_sha256=boundary.source_sha256,
            method_bytes=boundary.method_bytes,
            method_sha256=boundary.method_sha256,
        )
        validated_attributions = tuple(
            EYAGapAttributionEvidence(
                evidence_id=item.evidence_id,
                category=item.category,
                project_id=item.project_id,
                category_partition_id=item.category_partition_id,
                eya_claim_sha256=item.eya_claim_sha256,
                operational_claim_sha256=item.operational_claim_sha256,
                eya_expected_net_effect_kwh=item.eya_expected_net_effect_kwh,
                operational_actual_net_effect_kwh=(
                    item.operational_actual_net_effect_kwh
                ),
                sign_convention=item.sign_convention,
                source_locator=item.source_locator,
                source_bytes=item.source_bytes,
                source_sha256=item.source_sha256,
                method_bytes=item.method_bytes,
                method_sha256=item.method_sha256,
            )
            for item in attributions
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise EYAActualBridgeError(
            "INVALID_INPUT", "bridge inputs failed defensive reconstruction."
        ) from exc
    operational = _replay_operational_result(operational_result)
    eya_claim = _resource_snapshot_claim_sha256(resource_snapshot)
    operational_claim = _operational_result_claim_sha256(operational)
    if eya_claim != spec.expected_eya_claim_sha256:
        raise EYAActualBridgeError(
            "EYA_PROVENANCE_MISMATCH", "EYA claim does not match the expected digest."
        )
    if operational_claim != spec.expected_operational_claim_sha256:
        raise EYAActualBridgeError(
            "OPERATIONAL_PROVENANCE_MISMATCH",
            "operational claim does not match the expected digest.",
        )
    if resource_snapshot.selected_p_level != spec.eya_p_level:
        raise EYAActualBridgeError(
            "EYA_PROVENANCE_MISMATCH", "selected EYA P-level does not match the spec."
        )
    if (
        boundary.project_id != operational.receipt.project_id
        or boundary.category_partition_id != spec.category_partition_id
        or boundary.eya_claim_sha256 != eya_claim
        or boundary.operational_claim_sha256 != operational_claim
    ):
        raise EYAActualBridgeError(
            "BOUNDARY_MISMATCH",
            "common project, partition, or source claims do not match the bridge.",
        )
    if (
        type(operational.receipt.temporal_basis) is not str
        or operational.receipt.temporal_basis != "actual_calendar_year"
    ):
        raise EYAActualBridgeError(
            "TEMPORAL_MISMATCH",
            "D4 requires a replayed D3 actual_calendar_year result.",
        )
    start = _parse_utc(operational.receipt.effective_start_utc)
    end = _parse_utc(operational.receipt.effective_end_exclusive_utc)
    elapsed = end - start
    actual_seconds = elapsed.days * 86_400 + elapsed.seconds
    actual_hours = Fraction(actual_seconds, 3_600)
    if actual_hours != resource_snapshot.hours_per_year:
        raise EYAActualBridgeError(
            "TEMPORAL_MISMATCH",
            "actual calendar hours do not equal the frozen EYA standard-year hours.",
        )

    by_category: dict[str, EYAGapAttributionEvidence] = {}
    evidence_ids: set[str] = set()
    for item in validated_attributions:
        if item.category in by_category or item.evidence_id in evidence_ids:
            raise EYAActualBridgeError(
                "ATTRIBUTION_MISMATCH",
                "category and attribution evidence selectors must be unique.",
            )
        if (
            item.project_id != boundary.project_id
            or item.category_partition_id != spec.category_partition_id
            or item.eya_claim_sha256 != eya_claim
            or item.operational_claim_sha256 != operational_claim
        ):
            raise EYAActualBridgeError(
                "ATTRIBUTION_MISMATCH",
                "paired attribution does not bind the common project and source claims.",
            )
        _validate_category_actual(item, operational)
        by_category[item.category] = item
        evidence_ids.add(item.evidence_id)

    components = tuple(
        (
            _available_component(by_category[category])
            if category in by_category
            else _unavailable_component(category)
        )
        for category in EYA_GAP_CATEGORIES
    )
    eya_value = resource_snapshot.selected_net_aep_kwh.as_fraction()
    actual_value = _actual_net_energy(operational)
    attributed = sum(
        (
            item.signed_delta_kwh.as_fraction()
            for item in components
            if item.status == "available" and item.signed_delta_kwh is not None
        ),
        Fraction(0),
    )
    unknown = actual_value - eya_value - attributed
    total_gap = actual_value - eya_value
    residual = actual_value - eya_value - attributed - unknown
    # This is an identity because unknown is defined immediately above from the same
    # exact Fractions. Zero is not independent validation of the retained categories;
    # the receipt discloses that limitation explicitly (#1381 O-1 / #1404).
    if residual != 0:
        raise EYAActualBridgeError(
            "ARITHMETIC_FAILED", "EYA-to-actual identity failed exact reconciliation."
        )

    proposal = FinanceUpdateProposal(
        eya_claim_sha256=eya_claim,
        operational_claim_sha256=operational_claim,
    )
    boundary_claim = _claim_digest(
        "dutchbay.eya_actual_common_boundary.v1", boundary.model_dump()
    )
    attribution_manifest = [
        {
            "category": component.category,
            "status": component.status,
            "evidence_claim_sha256": component.evidence_claim_sha256,
        }
        for component in components
    ]
    attribution_manifest_sha = _claim_digest(
        "dutchbay.eya_gap_attribution_manifest.v1", attribution_manifest
    )
    method_sha = _claim_digest(
        "dutchbay.eya_actual_bridge_method.v1",
        {
            "version": _BRIDGE_METHOD_VERSION,
            "spec": spec.model_dump(),
            "boundary_claim_sha256": boundary_claim,
            "attribution_manifest_sha256": attribution_manifest_sha,
            "equation": "actual=eya+available_signed_deltas+unknown_residual",
            "sign": "positive_increases_actual_vs_eya",
            "missing": "unavailable_not_zero",
            "eya_projection": "float.hex_to_Fraction_times_1e6_kWh",
            "finance": "default_off_no_apply_path",
        },
    )
    proposal_sha = _claim_digest(
        "dutchbay.finance_update_proposal.v1", proposal.model_dump()
    )
    receipt = EYAActualBridgeReceipt(
        schema=EYA_ACTUAL_BRIDGE_SCHEMA,
        bridge_id=spec.bridge_id,
        project_id=boundary.project_id,
        asset_identity=boundary.asset_identity,
        eya_claim_sha256=eya_claim,
        operational_claim_sha256=operational_claim,
        boundary_claim_sha256=boundary_claim,
        attribution_manifest_sha256=attribution_manifest_sha,
        method_sha256=method_sha,
        finance_proposal_sha256=proposal_sha,
        arithmetic_policy=spec.arithmetic_policy,
        sign_convention="positive_increases_actual_vs_eya",
        full_reconciliation_residual_kwh=OperationalEnergyQuantity.from_fraction(
            residual
        ),
    )
    return _BridgeArtifacts(
        eya_net_energy_kwh=OperationalEnergyQuantity.from_fraction(eya_value),
        actual_net_energy_kwh=OperationalEnergyQuantity.from_fraction(actual_value),
        total_gap_kwh=OperationalEnergyQuantity.from_fraction(total_gap),
        category_components=components,
        unknown_residual_kwh=OperationalEnergyQuantity.from_fraction(unknown),
        finance_proposal=proposal,
        receipt=receipt,
    )


def _parse_utc(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        raise EYAActualBridgeError(
            "TEMPORAL_MISMATCH", "operational bounds must be RFC3339 UTC timestamps."
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EYAActualBridgeError(
            "TEMPORAL_MISMATCH", "operational bounds are not valid UTC timestamps."
        ) from exc
    if parsed.tzinfo != timezone.utc:
        raise EYAActualBridgeError(
            "TEMPORAL_MISMATCH", "operational bounds must resolve to UTC."
        )
    return parsed


def build_eya_actual_bridge(
    resource_assessment: ResourceAssessment,
    operational_result: OperationalAEPResult,
    spec: EYAActualBridgeSpec,
    boundary_evidence: EYAActualBoundaryEvidence,
    attribution_evidence: tuple[EYAGapAttributionEvidence, ...] = (),
) -> EYAActualBridgeResult:
    """Build one exact additive bridge without mutating either source artifact."""
    try:
        snapshot = _snapshot_resource_assessment(resource_assessment)
        artifacts = _build_artifacts(
            snapshot,
            operational_result,
            spec,
            boundary_evidence,
            attribution_evidence,
        )
        return EYAActualBridgeResult(
            resource_snapshot=snapshot,
            operational_result=operational_result,
            spec=spec,
            boundary_evidence=boundary_evidence,
            attribution_evidence=attribution_evidence,
            eya_net_energy_kwh=artifacts.eya_net_energy_kwh,
            actual_net_energy_kwh=artifacts.actual_net_energy_kwh,
            total_gap_kwh=artifacts.total_gap_kwh,
            category_components=artifacts.category_components,
            unknown_residual_kwh=artifacts.unknown_residual_kwh,
            finance_proposal=artifacts.finance_proposal,
            receipt=artifacts.receipt,
            _factory_token=_BRIDGE_RESULT_TOKEN,
        )
    except EYAActualBridgeError:
        raise
    except (
        ArithmeticError,
        AttributeError,
        OverflowError,
        TypeError,
        ValueError,
    ) as exc:
        raise EYAActualBridgeError(
            "INVALID_INPUT", f"EYA-to-actual bridge failed closed: {exc}"
        ) from exc


__all__ = [
    "EYA_ACTUAL_BRIDGE_SCHEMA",
    "EYA_GAP_CATEGORIES",
    "EYAActualBoundaryEvidence",
    "EYAActualBridgeError",
    "EYAActualBridgeErrorCode",
    "EYAActualBridgeReceipt",
    "EYAActualBridgeResult",
    "EYAActualBridgeSpec",
    "EYAGapAttributionEvidence",
    "EYAGapCategory",
    "EYAGapComponent",
    "FinanceUpdateProposal",
    "ResourceAssessmentSnapshot",
    "build_eya_actual_bridge",
    "operational_aep_claim_sha256",
    "resource_assessment_claim_sha256",
]
