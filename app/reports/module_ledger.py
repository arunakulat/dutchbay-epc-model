"""Config-first module role registry and execution ledger contracts (W1-1).

Pure contract and configuration loader surface (``CCCDIR`` / ``CESSPIT`` / ``CASPER``):

* Defines canonical pipeline stages (:class:`PipelineStage`), execution dispositions
  (:class:`ModuleExecutionStatus`), and workbook representation modes
  (:class:`ExcelRepresentationKind`).
* Loads and strictly validates ``config/module_roles.yaml`` via
  :func:`load_module_role_registry` (``extra="forbid"``, no silent defaults).
* Captures per-module runtime execution records in :class:`ModuleExecutionRecord` and
  validates ledger uniqueness, registry membership, and status summary counts via
  :func:`build_module_execution_ledger`.

Architectural boundary: imports only standard library, ``pyyaml``, and ``pydantic`` —
never ``finance`` or ``analytics.pipeline_v14_enhanced``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Optional

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    PrivateAttr,
    StringConstraints,
    field_validator,
    model_validator,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODULE_ROLES_PATH = _REPO_ROOT / "config" / "module_roles.yaml"

#: Declared runtime optional-dependency extras in ``pyproject.toml``.
KNOWN_OPTIONAL_EXTRAS: frozenset[str] = frozenset(
    {
        "wind",
        "solar",
        "grid",
        "gis",
        "micrositing",
        "pareto",
        "report",
        "api",
        "jobs",
        "ingestion",
        "dashboard",
        "feasibility",
    }
)

ModulePath = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RoleDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=12)
]
FrozenIntMapping = Annotated[
    Mapping[str, int],
    PlainSerializer(lambda value: dict(value), return_type=dict[str, int]),
]


class PipelineStage(str, Enum):
    """Canonical ordered stages of the DutchBay model and delivery pipeline."""

    GOVERNANCE = "governance"
    SITE_GIS = "site_gis"
    RESOURCE_YIELD = "resource_yield"
    TECH_HYBRID_BESS = "tech_hybrid_bess"
    GRID_QSTS = "grid_qsts"
    COST_LEVIES_EPC = "cost_levies_epc"
    CORE_FINANCE = "core_finance"
    RISK_SENSITIVITY_OPT = "risk_sensitivity_opt"
    REPORTING_DELIVERY = "reporting_delivery"


class ModuleExecutionStatus(str, Enum):
    """Disposition of a registered module for a concrete run profile."""

    EXECUTED = "executed"
    GUARD_PASSED = "guard_passed"
    GUARD_REFUSED = "guard_refused"
    NOT_APPLICABLE = "not_applicable"
    SKIPPED_MISSING_INPUTS = "skipped_missing_inputs"
    SKIPPED_OPTIONAL_EXTRA = "skipped_optional_extra"
    SKIPPED_SYNC_PROFILE = "skipped_sync_profile"
    FAILED = "failed"


class ExcelRepresentationKind(str, Enum):
    """How a module's outputs or metadata are represented in the lender workbook."""

    FORMULA = "formula"
    ENGINE_TABLE_PLUS_ROLLUP = "engine_table_plus_rollup"
    GOVERNANCE_METADATA = "governance_metadata"
    NON_MODEL_ADAPTER = "non_model_adapter"


_REASON_REQUIRED_STATUSES: frozenset[ModuleExecutionStatus] = frozenset(
    {
        ModuleExecutionStatus.FAILED,
        ModuleExecutionStatus.GUARD_REFUSED,
        ModuleExecutionStatus.NOT_APPLICABLE,
        ModuleExecutionStatus.SKIPPED_MISSING_INPUTS,
        ModuleExecutionStatus.SKIPPED_OPTIONAL_EXTRA,
        ModuleExecutionStatus.SKIPPED_SYNC_PROFILE,
    }
)


class ModuleRoleSpec(BaseModel):
    """Declared architectural role and workbook mapping for one Python module."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_path: ModulePath
    pipeline_stage: PipelineStage
    role_description: RoleDescription
    excel_representation: ExcelRepresentationKind
    optional_extra: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("optional_extra")
    @classmethod
    def _validate_optional_extra(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if value not in KNOWN_OPTIONAL_EXTRAS:
            known = ", ".join(sorted(KNOWN_OPTIONAL_EXTRAS))
            raise ValueError(
                f"Unknown optional_extra {value!r}; expected one of: {known}"
            )
        return value


class ModuleRoleRegistry(BaseModel):
    """Validated config-first registry of all model and delivery module roles."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"]
    stages: tuple[PipelineStage, ...]
    modules: tuple[ModuleRoleSpec, ...]
    _by_path: dict[str, ModuleRoleSpec] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _validate_registry_integrity(self) -> ModuleRoleRegistry:
        stage_counts = Counter(self.stages)
        duplicate_stages = sorted(
            stage.value for stage, count in stage_counts.items() if count > 1
        )
        if duplicate_stages:
            raise ValueError(
                f"Duplicate pipeline stage(s) in registry: {', '.join(duplicate_stages)}"
            )

        present_stages = set(self.stages)
        missing_stages = [
            stage.value for stage in PipelineStage if stage not in present_stages
        ]
        if missing_stages:
            raise ValueError(
                f"Missing pipeline stage(s) in registry: {', '.join(missing_stages)}"
            )

        path_counts = Counter(spec.module_path for spec in self.modules)
        duplicate_paths = sorted(
            path for path, count in path_counts.items() if count > 1
        )
        if duplicate_paths:
            raise ValueError(
                f"Duplicate module_path entries in registry: {', '.join(duplicate_paths)}"
            )

        self._by_path = {spec.module_path: spec for spec in self.modules}
        return self

    def __contains__(self, module_path: object) -> bool:
        return isinstance(module_path, str) and module_path in self._by_path

    def get(self, module_path: str) -> ModuleRoleSpec:
        """Return the role specification for ``module_path`` or fail loudly."""
        spec = self._by_path.get(module_path)
        if spec is None:
            raise KeyError(
                f"Module {module_path!r} is not registered in ModuleRoleRegistry"
            )
        return spec

    def by_stage(self, stage: PipelineStage | str) -> tuple[ModuleRoleSpec, ...]:
        """Return all registered module specifications belonging to ``stage``."""
        target = PipelineStage(stage)
        return tuple(spec for spec in self.modules if spec.pipeline_stage is target)


class ModuleExecutionRecord(BaseModel):
    """Per-module execution disposition recorded for one run profile."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    module_path: ModulePath
    pipeline_stage: PipelineStage
    role_description: NonEmptyText
    status: ModuleExecutionStatus
    excel_representation: ExcelRepresentationKind
    reason: Optional[str] = None
    key_outputs: tuple[NonEmptyText, ...] = ()
    provenance_refs: tuple[NonEmptyText, ...] = ()
    caveat: Optional[str] = None

    @model_validator(mode="after")
    def _validate_reason_required(self) -> ModuleExecutionRecord:
        if self.status in _REASON_REQUIRED_STATUSES and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError(
                f"ModuleExecutionRecord for {self.module_path!r} with status "
                f"{self.status.value!r} requires a non-empty reason"
            )
        return self


def _compute_summary_counts(
    records: tuple[ModuleExecutionRecord, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {status.value: 0 for status in ModuleExecutionStatus}
    for record in records:
        counts[record.status.value] += 1
    return counts


class ModuleExecutionLedger(BaseModel):
    """Immutable run-level ledger of module execution dispositions and status totals."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: NonEmptyText
    records: tuple[ModuleExecutionRecord, ...]
    summary_counts: FrozenIntMapping = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_ledger_integrity(self) -> ModuleExecutionLedger:
        path_counts = Counter(record.module_path for record in self.records)
        duplicates = sorted(path for path, count in path_counts.items() if count > 1)
        if duplicates:
            raise ValueError(
                f"Duplicate module_path entries in execution ledger: {', '.join(duplicates)}"
            )

        expected_counts = _compute_summary_counts(self.records)
        if "summary_counts" in self.model_fields_set:
            provided = dict(self.summary_counts)
            if provided != expected_counts:
                raise ValueError(
                    "ModuleExecutionLedger summary_counts do not match records: "
                    f"got {provided}, expected {expected_counts}"
                )

        object.__setattr__(self, "summary_counts", MappingProxyType(expected_counts))
        return self


def build_module_execution_ledger(
    profile: str,
    records: Iterable[ModuleExecutionRecord],
    registry: Optional[ModuleRoleRegistry] = None,
) -> ModuleExecutionLedger:
    """Validate and assemble a :class:`ModuleExecutionLedger` for a run profile.

    Fails loudly on duplicate ``module_path`` entries and, when ``registry`` is
    supplied, on any record whose ``module_path`` is absent from ``registry``.
    """
    records_tuple = tuple(records)

    if registry is not None:
        unregistered = sorted(
            {
                record.module_path
                for record in records_tuple
                if record.module_path not in registry
            }
        )
        if unregistered:
            raise ValueError(
                "Unregistered module_path(s) in execution ledger: "
                f"{', '.join(unregistered)}"
            )

    return ModuleExecutionLedger(profile=profile, records=records_tuple)


def load_module_role_registry(
    path: Path = DEFAULT_MODULE_ROLES_PATH,
) -> ModuleRoleRegistry:
    """Strictly load and validate the module role registry YAML without defaults."""
    resolved = Path(path)
    raw_text = resolved.read_text(encoding="utf-8")
    loaded = yaml.safe_load(raw_text)
    if not isinstance(loaded, Mapping):
        raise ValueError(
            f"Expected YAML mapping at root of {resolved}, got {type(loaded).__name__}"
        )
    return ModuleRoleRegistry.model_validate(loaded)


__all__ = [
    "DEFAULT_MODULE_ROLES_PATH",
    "ExcelRepresentationKind",
    "KNOWN_OPTIONAL_EXTRAS",
    "ModuleExecutionLedger",
    "ModuleExecutionRecord",
    "ModuleExecutionStatus",
    "ModuleRoleRegistry",
    "ModuleRoleSpec",
    "PipelineStage",
    "build_module_execution_ledger",
    "load_module_role_registry",
]
