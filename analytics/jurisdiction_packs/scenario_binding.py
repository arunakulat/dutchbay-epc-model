"""Bind a scenario to its jurisdiction pack (#1841 PR 3).

A scenario names its jurisdiction in ``project.jurisdiction``. The committed binding
registry (``conf/jurisdiction_scenario_bindings.yaml``) maps that name to one registered
pack id and version, and :func:`scenario_jurisdiction_bindings` turns it into the
``ProjectCase`` :class:`JurisdictionBinding` records the resolver takes: one per subject
the bound pack covers.

Fail closed, as the resolver does. A scenario without ``project.jurisdiction``, a name
the registry does not know, a non-string value, or a registry entry whose pack is not
registered raises :class:`JurisdictionRefusal`. Nothing falls back to Sri Lanka.

Every committed scenario that has a ``project`` section must declare its jurisdiction:
``tests/jurisdiction_packs/test_scenario_jurisdiction_binding.py`` checks each file and
resolves its bindings through the pack.

Pure. It imports no engine module, and the engine does not call it yet.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import Field, model_validator

from analytics.feasibility_report_contract.project_case import (
    ContractSupportStatus,
    JurisdictionBinding,
)
from analytics.feasibility_report_contract.vocabulary import (
    Identifier,
    JurisdictionCode,
    NonEmptyText,
    PackStatus,
    SemanticVersion,
    StrictFrozenModel,
)
from analytics.jurisdiction_packs.resolver import JurisdictionRefusal, RefusalReason
from analytics.jurisdiction_packs.schema import load_registered_pack

SCENARIO_BINDINGS_SCHEMA_ID: Literal["dutchbay.jurisdiction_scenario_bindings.v1"] = (
    "dutchbay.jurisdiction_scenario_bindings.v1"
)
SCENARIO_BINDINGS_PATH: Path = (
    Path(__file__).resolve().parents[2] / "conf" / "jurisdiction_scenario_bindings.yaml"
)


class ScenarioBindingEntry(StrictFrozenModel):
    """One jurisdiction a scenario may name, and the pack it binds to."""

    jurisdiction_code: JurisdictionCode
    names: tuple[NonEmptyText, ...] = Field(min_length=1)
    pack_id: Identifier
    pack_version: SemanticVersion


class ScenarioBindingRegistry(StrictFrozenModel):
    """The committed map from a scenario's jurisdiction name to a pack."""

    schema_id: Literal["dutchbay.jurisdiction_scenario_bindings.v1"]
    jurisdictions: tuple[ScenarioBindingEntry, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _spellings_are_unique(self) -> "ScenarioBindingRegistry":
        seen: dict[str, str] = {}
        for entry in self.jurisdictions:
            for spelling in (entry.jurisdiction_code, *entry.names):
                key = spelling.strip().casefold()
                if key in seen and seen[key] != entry.jurisdiction_code:
                    raise ValueError(
                        f"jurisdiction spelling {spelling!r} names both "
                        f"{seen[key]} and {entry.jurisdiction_code}"
                    )
                seen[key] = entry.jurisdiction_code
        codes = [entry.jurisdiction_code for entry in self.jurisdictions]
        if len(codes) != len(set(codes)):
            raise ValueError("each jurisdiction code may appear once")
        return self

    def entry_for(self, declared: str) -> Optional[ScenarioBindingEntry]:
        """Return the entry a declared name or code selects, or ``None``."""
        key = declared.strip().casefold()
        for entry in self.jurisdictions:
            spellings = (entry.jurisdiction_code, *entry.names)
            if key in {spelling.strip().casefold() for spelling in spellings}:
                return entry
        return None


def load_scenario_binding_registry(
    path: Optional[Path] = None,
) -> ScenarioBindingRegistry:
    """Load and validate the binding registry (defaults to the committed file)."""
    if path is None:
        return _committed_registry()
    return _load_registry(Path(path))


@lru_cache(maxsize=1)
def _committed_registry() -> ScenarioBindingRegistry:
    return _load_registry(SCENARIO_BINDINGS_PATH)


def _load_registry(path: Path) -> ScenarioBindingRegistry:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: the scenario binding registry must be a mapping")
    return ScenarioBindingRegistry.model_validate_json(json.dumps(data))


def _declared_jurisdiction(config: Mapping[str, Any]) -> str:
    project = None
    for key, value in config.items():
        if isinstance(key, str) and key.lower() == "project":
            project = value
            break
    declared: Any = None
    if isinstance(project, Mapping):
        for key, value in project.items():
            if isinstance(key, str) and key.lower() == "jurisdiction":
                declared = value
                break
    if declared is None:
        raise JurisdictionRefusal(
            RefusalReason.MISSING_BINDING,
            "the scenario declares no project.jurisdiction, so it binds to no "
            "jurisdiction pack (#1841). Name it, for example 'Sri Lanka'.",
        )
    if not isinstance(declared, str) or not declared.strip():
        raise JurisdictionRefusal(
            RefusalReason.UNKNOWN_JURISDICTION,
            f"project.jurisdiction must be a non-empty string; got {declared!r}",
        )
    return declared


def scenario_jurisdiction_entry(
    config: Mapping[str, Any],
    *,
    registry: Optional[ScenarioBindingRegistry] = None,
) -> ScenarioBindingEntry:
    """Return the registry entry a scenario's ``project.jurisdiction`` selects.

    Raises:
        JurisdictionRefusal: The scenario names no jurisdiction, or one the registry
            does not know.
    """
    declared = _declared_jurisdiction(config)
    reg = load_scenario_binding_registry() if registry is None else registry
    entry = reg.entry_for(declared)
    if entry is None:
        raise JurisdictionRefusal(
            RefusalReason.UNKNOWN_JURISDICTION,
            f"project.jurisdiction {declared!r} names no jurisdiction in the scenario "
            "binding registry (conf/jurisdiction_scenario_bindings.yaml); no other "
            "jurisdiction is assumed (#1841)",
        )
    return entry


def scenario_jurisdiction_bindings(
    config: Mapping[str, Any],
    *,
    registry: Optional[ScenarioBindingRegistry] = None,
    packs_root: Optional[Path] = None,
) -> tuple[JurisdictionBinding, ...]:
    """Return a scenario's jurisdiction bindings, one per subject its pack covers.

    The bindings are ordered by subject. Each one is ``declared``, or ``unsupported``
    when the bound pack's status is ``unsupported``, so the resolver then reports the
    subject as not run rather than resolving it.

    Raises:
        JurisdictionRefusal: As :func:`scenario_jurisdiction_entry`, or when the
            bound pack is not registered or declares another pack id.
    """
    entry = scenario_jurisdiction_entry(config, registry=registry)
    try:
        pack = load_registered_pack(
            entry.jurisdiction_code, entry.pack_version, root=packs_root
        )
    except FileNotFoundError as exc:
        raise JurisdictionRefusal(RefusalReason.UNSUPPORTED_VERSION, str(exc)) from exc
    except ValueError as exc:
        raise JurisdictionRefusal(RefusalReason.INVALID_PACK, str(exc)) from exc
    if pack.pack_id != entry.pack_id:
        raise JurisdictionRefusal(
            RefusalReason.PACK_IDENTITY_MISMATCH,
            f"the binding registry names pack {entry.pack_id} for "
            f"{entry.jurisdiction_code}, but {entry.jurisdiction_code} "
            f"{entry.pack_version} is pack {pack.pack_id}",
        )
    support = (
        ContractSupportStatus.UNSUPPORTED
        if pack.status is PackStatus.UNSUPPORTED
        else ContractSupportStatus.DECLARED
    )
    subjects = sorted({parameter.subject for parameter in pack.parameters})
    return tuple(
        JurisdictionBinding.model_validate_json(
            json.dumps(
                {
                    "binding_id": (
                        f"jb:{entry.jurisdiction_code.lower()}:{subject.value}"
                    ),
                    "jurisdiction_code": entry.jurisdiction_code,
                    "subject": subject.value,
                    "support_status": support.value,
                    "contract_pack_id": entry.pack_id,
                    "contract_pack_version": entry.pack_version,
                }
            )
        )
        for subject in subjects
    )


__all__ = [
    "SCENARIO_BINDINGS_PATH",
    "SCENARIO_BINDINGS_SCHEMA_ID",
    "ScenarioBindingEntry",
    "ScenarioBindingRegistry",
    "load_scenario_binding_registry",
    "scenario_jurisdiction_bindings",
    "scenario_jurisdiction_entry",
]
