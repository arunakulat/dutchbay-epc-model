"""Resolve jurisdiction pack values by subject and valuation date (#1843).

The resolver takes a project's jurisdiction bindings (the ``ProjectCase``
``JurisdictionBinding`` record: one governed subject bound to one pack id and version),
the valuation dates of its periods and any project overrides, and returns, for each
bound subject and each date, the pack values in force on that date.

It is pure. It imports no engine module, and nothing in the engine calls it yet: a later
slice of #1841 wires it in.

Rules:

1. **Fail closed.** An unknown jurisdiction code, an unregistered version, a pack whose
   identity differs from the binding, a missing binding for a required subject, a subject
   the bound pack does not cover, or a date on which a parameter has no value in force
   raises :class:`JurisdictionRefusal` with a :class:`RefusalReason`. Nothing falls back
   to another jurisdiction.
2. **Effective dating.** A period takes the value whose ``[effective_from, effective_to)``
   window contains its valuation date. A date before the first window, in a gap between
   windows or after the last window closes is refused, not guessed. Overlapping windows
   are already refused by the pack schema.
3. **Conflicts are reported, never resolved silently.** Two different packs bound to one
   subject, or an override without provenance, produce :class:`ConflictRecord` entries
   that carry every candidate value. A conflicted value is withheld from the resolved
   periods, so a caller cannot use it without settling the conflict.
4. **Determinism.** The output is ordered and carries a SHA-256 digest of its canonical
   JSON form, so equal inputs give equal outputs and digests.

A subject whose binding is declared ``unsupported``, or whose pack has status
``unsupported``, resolves to the disposition ``not_run_unsupported_jurisdiction`` with no
values. Two packs claiming one subject give ``not_run_conflict``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Protocol

from pydantic import Field, model_validator

from analytics.feasibility_report_contract.project_case import (
    ContractSupportStatus,
    JurisdictionBinding,
    JurisdictionSubject,
    StableIdentifier,
)
from analytics.feasibility_report_contract.vocabulary import (
    Identifier,
    JurisdictionCode,
    NonEmptyText,
    PackStatus,
    SemanticVersion,
    Sha256Hex,
    StrictFrozenModel,
)
from analytics.jurisdiction_packs.schema import (
    PACKS_ROOT,
    JurisdictionPack,
    PackParameter,
    ParameterStatus,
    ParameterUnit,
    ScalarValue,
    load_registered_pack,
)

JURISDICTION_RESOLUTION_SCHEMA_ID: Literal["dutchbay.jurisdiction_resolution.v1"] = (
    "dutchbay.jurisdiction_resolution.v1"
)

_SUBJECT_ORDER = {subject: index for index, subject in enumerate(JurisdictionSubject)}


class RefusalReason(str, Enum):
    """Why the resolver refused to resolve."""

    NO_VALUATION_DATES = "no_valuation_dates"
    UNKNOWN_JURISDICTION = "unknown_jurisdiction"
    UNSUPPORTED_VERSION = "unsupported_version"
    INVALID_PACK = "invalid_pack"
    PACK_IDENTITY_MISMATCH = "pack_identity_mismatch"
    MISSING_BINDING = "missing_binding"
    SUBJECT_NOT_COVERED = "subject_not_covered"
    NO_VALUE_IN_FORCE = "no_value_in_force"
    UNKNOWN_OVERRIDE = "unknown_override"
    INVALID_OVERRIDE = "invalid_override"


class JurisdictionRefusal(ValueError):
    """A typed refusal: the inputs cannot be resolved without guessing."""

    def __init__(self, reason: RefusalReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}")


class SubjectDisposition(str, Enum):
    """What the resolver could do for one subject."""

    SUPPORTED = "supported"
    NOT_RUN_UNSUPPORTED_JURISDICTION = "not_run_unsupported_jurisdiction"
    NOT_RUN_CONFLICT = "not_run_conflict"


class ValueOrigin(str, Enum):
    """Where a resolved value came from."""

    PACK = "pack"
    OVERRIDE = "override"


class ConflictKind(str, Enum):
    """Kind of conflict the resolver reports instead of settling."""

    SUBJECT_CLAIMED_BY_TWO_PACKS = "subject_claimed_by_two_packs"
    OVERRIDE_WITHOUT_PROVENANCE = "override_without_provenance"


class ProjectOverride(StrictFrozenModel):
    """A project-specific value that replaces a pack value for every period.

    Attributes:
        parameter_id: The pack parameter it replaces.
        value: The project value, in the parameter's unit.
        provenance: Why the project departs from the pack (relief, exemption, ruling).
            An override without provenance is reported as a conflict, not applied.
    """

    parameter_id: Identifier
    value: ScalarValue
    provenance: Optional[NonEmptyText] = None


class PackRef(StrictFrozenModel):
    """Identity of a pack used in a resolution."""

    jurisdiction_code: JurisdictionCode
    pack_id: Identifier
    version: SemanticVersion
    status: PackStatus
    content_sha256: Sha256Hex


class ResolvedParameter(StrictFrozenModel):
    """One value in force for one subject on one valuation date.

    The window's end is deliberately not recorded: an amendment made after a run closes
    the window, and recording the end would let a later amendment change the run's
    output (bitemporal safety, #1843 rule 3).
    """

    parameter_id: Identifier
    scenario_key: Identifier
    unit: ParameterUnit
    value: ScalarValue
    origin: ValueOrigin
    pack_value: ScalarValue
    status: ParameterStatus
    effective_from: date


class PeriodValues(StrictFrozenModel):
    """The values in force for one subject on one valuation date."""

    valuation_date: date
    values: tuple[ResolvedParameter, ...]


class SubjectResolution(StrictFrozenModel):
    """The resolution of one governed subject."""

    subject: JurisdictionSubject
    disposition: SubjectDisposition
    binding_ids: tuple[StableIdentifier, ...] = Field(min_length=1)
    packs: tuple[PackRef, ...] = ()
    periods: tuple[PeriodValues, ...] = ()


class AppliedOverride(StrictFrozenModel):
    """An override applied on one date, with the pack value it replaced."""

    parameter_id: Identifier
    subject: JurisdictionSubject
    valuation_date: date
    pack_value: ScalarValue
    override_value: ScalarValue
    provenance: NonEmptyText


class ConflictCandidate(StrictFrozenModel):
    """One of the values a conflict could be settled with."""

    origin: NonEmptyText
    value: Optional[ScalarValue] = None


class ConflictRecord(StrictFrozenModel):
    """A conflict reported, with every candidate value, and left unsettled."""

    kind: ConflictKind
    subject: JurisdictionSubject
    parameter_id: Identifier
    valuation_date: date
    candidates: tuple[ConflictCandidate, ...] = Field(min_length=2)


class JurisdictionResolution(StrictFrozenModel):
    """Everything the resolver decided, with a digest of its canonical form."""

    schema_id: Literal["dutchbay.jurisdiction_resolution.v1"]
    valuation_dates: tuple[date, ...] = Field(min_length=1)
    subjects: tuple[SubjectResolution, ...]
    overrides_applied: tuple[AppliedOverride, ...] = ()
    conflicts: tuple[ConflictRecord, ...] = ()
    digest: Sha256Hex

    @model_validator(mode="after")
    def _digest_matches(self) -> "JurisdictionResolution":
        expected = _digest(self.model_dump(mode="json", exclude={"digest"}))
        if self.digest != expected:
            raise ValueError(
                f"resolution digest {self.digest} does not match its content ({expected})"
            )
        return self

    def subject(self, subject: JurisdictionSubject) -> SubjectResolution:
        """Return the resolution for ``subject``.

        Raises:
            KeyError: If no binding was resolved for that subject.
        """
        for entry in self.subjects:
            if entry.subject is subject:
                return entry
        raise KeyError(subject.value)


class PackSource(Protocol):
    """Where the resolver finds registered packs."""

    def versions(self, jurisdiction_code: str) -> frozenset[str]:
        """Registered versions for a code; empty if the code is unknown."""
        ...

    def load(self, jurisdiction_code: str, version: str) -> JurisdictionPack:
        """Load one registered pack."""
        ...


class DirectoryPackSource:
    """Packs filed as ``<root>/<code lower case>/<version>.yaml``."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = PACKS_ROOT if root is None else Path(root)

    def versions(self, jurisdiction_code: str) -> frozenset[str]:
        folder = self.root / jurisdiction_code.lower()
        if not folder.is_dir():
            return frozenset()
        return frozenset(path.stem for path in folder.glob("*.yaml"))

    def load(self, jurisdiction_code: str, version: str) -> JurisdictionPack:
        return load_registered_pack(jurisdiction_code, version, root=self.root)


class InMemoryPackSource:
    """Packs held in memory, keyed by their own code and version."""

    def __init__(self, packs: Iterable[JurisdictionPack]) -> None:
        self._packs: dict[tuple[str, str], JurisdictionPack] = {}
        for pack in packs:
            key = (pack.jurisdiction_code, pack.version)
            if key in self._packs:
                raise ValueError(f"two packs registered for {key[0]} {key[1]}")
            self._packs[key] = pack

    def versions(self, jurisdiction_code: str) -> frozenset[str]:
        return frozenset(v for c, v in self._packs if c == jurisdiction_code)

    def load(self, jurisdiction_code: str, version: str) -> JurisdictionPack:
        return self._packs[(jurisdiction_code, version)]


def resolve(
    bindings: Iterable[JurisdictionBinding],
    valuation_dates: Iterable[date],
    *,
    required_subjects: Iterable[JurisdictionSubject] = (),
    overrides: Iterable[ProjectOverride] = (),
    source: Optional[PackSource] = None,
) -> JurisdictionResolution:
    """Resolve pack values for each bound subject on each valuation date.

    Args:
        bindings: Jurisdiction bindings, one or more per subject.
        valuation_dates: The periods' valuation dates. Duplicates are merged.
        required_subjects: Subjects that must have a binding.
        overrides: Project overrides of pack parameters.
        source: Where to find packs; defaults to the registered packs directory.

    Returns:
        The resolution, with its digest.

    Raises:
        JurisdictionRefusal: If the inputs cannot be resolved without guessing.
    """
    pack_source: PackSource = DirectoryPackSource() if source is None else source
    dates = tuple(sorted(set(valuation_dates)))
    if not dates:
        raise JurisdictionRefusal(
            RefusalReason.NO_VALUATION_DATES, "at least one valuation date is needed"
        )

    by_subject: dict[JurisdictionSubject, list[JurisdictionBinding]] = {}
    for binding in bindings:
        by_subject.setdefault(binding.subject, []).append(binding)
    for subject in sorted(set(required_subjects), key=_SUBJECT_ORDER.__getitem__):
        if subject not in by_subject:
            raise JurisdictionRefusal(
                RefusalReason.MISSING_BINDING,
                f"no jurisdiction binding for required subject '{subject.value}'",
            )

    override_map = _index_overrides(overrides)
    claimed_overrides: set[str] = set()
    subjects: list[SubjectResolution] = []
    applied: list[AppliedOverride] = []
    conflicts: list[ConflictRecord] = []

    for subject in sorted(by_subject, key=_SUBJECT_ORDER.__getitem__):
        subject_bindings = sorted(by_subject[subject], key=lambda b: b.binding_id)
        binding_ids = tuple(b.binding_id for b in subject_bindings)
        if any(
            b.support_status is ContractSupportStatus.UNSUPPORTED
            for b in subject_bindings
        ):
            subjects.append(
                SubjectResolution(
                    subject=subject,
                    disposition=SubjectDisposition.NOT_RUN_UNSUPPORTED_JURISDICTION,
                    binding_ids=binding_ids,
                )
            )
            continue

        packs: dict[tuple[str, str, str], JurisdictionPack] = {}
        for binding in subject_bindings:
            pack = _load_bound_pack(binding, pack_source)
            packs[(pack.jurisdiction_code, pack.pack_id, pack.version)] = pack
        ordered = [packs[key] for key in sorted(packs)]
        refs = tuple(_pack_ref(pack) for pack in ordered)

        if any(pack.status is PackStatus.UNSUPPORTED for pack in ordered):
            subjects.append(
                SubjectResolution(
                    subject=subject,
                    disposition=SubjectDisposition.NOT_RUN_UNSUPPORTED_JURISDICTION,
                    binding_ids=binding_ids,
                    packs=refs,
                )
            )
            continue

        if len(ordered) > 1:
            conflicts.extend(_two_pack_conflicts(subject, ordered, refs, dates))
            subjects.append(
                SubjectResolution(
                    subject=subject,
                    disposition=SubjectDisposition.NOT_RUN_CONFLICT,
                    binding_ids=binding_ids,
                    packs=refs,
                )
            )
            continue

        pack = ordered[0]
        parameters = _subject_parameters(pack, subject)
        periods: list[PeriodValues] = []
        for when in dates:
            values: list[ResolvedParameter] = []
            for parameter_id in sorted(parameters):
                in_force = _in_force(parameter_id, parameters[parameter_id], when)
                override = override_map.get(parameter_id)
                if override is None:
                    values.append(_resolved(in_force, in_force.value, ValueOrigin.PACK))
                    continue
                claimed_overrides.add(parameter_id)
                _check_override_value(override, in_force)
                if override.provenance is None:
                    conflicts.append(
                        ConflictRecord(
                            kind=ConflictKind.OVERRIDE_WITHOUT_PROVENANCE,
                            subject=subject,
                            parameter_id=parameter_id,
                            valuation_date=when,
                            candidates=(
                                ConflictCandidate(
                                    origin=_origin(refs[0]), value=in_force.value
                                ),
                                ConflictCandidate(
                                    origin="project override (no provenance)",
                                    value=override.value,
                                ),
                            ),
                        )
                    )
                    continue
                values.append(_resolved(in_force, override.value, ValueOrigin.OVERRIDE))
                applied.append(
                    AppliedOverride(
                        parameter_id=parameter_id,
                        subject=subject,
                        valuation_date=when,
                        pack_value=in_force.value,
                        override_value=override.value,
                        provenance=override.provenance,
                    )
                )
            periods.append(PeriodValues(valuation_date=when, values=tuple(values)))
        subjects.append(
            SubjectResolution(
                subject=subject,
                disposition=SubjectDisposition.SUPPORTED,
                binding_ids=binding_ids,
                packs=refs,
                periods=tuple(periods),
            )
        )

    unclaimed = sorted(set(override_map) - claimed_overrides)
    if unclaimed:
        raise JurisdictionRefusal(
            RefusalReason.UNKNOWN_OVERRIDE,
            f"overrides {unclaimed} name no parameter of a subject that resolved "
            f"as supported",
        )

    def build(digest: str) -> JurisdictionResolution:
        return JurisdictionResolution(
            schema_id=JURISDICTION_RESOLUTION_SCHEMA_ID,
            valuation_dates=dates,
            subjects=tuple(subjects),
            overrides_applied=tuple(applied),
            conflicts=tuple(conflicts),
            digest=digest,
        )

    # Dump an unvalidated draft to compute the digest, then build the validated
    # result, whose validator recomputes and checks it.
    draft = JurisdictionResolution.model_construct(
        schema_id=JURISDICTION_RESOLUTION_SCHEMA_ID,
        valuation_dates=dates,
        subjects=tuple(subjects),
        overrides_applied=tuple(applied),
        conflicts=tuple(conflicts),
        digest="0" * 64,
    )
    return build(_digest(draft.model_dump(mode="json", exclude={"digest"})))


def _index_overrides(
    overrides: Iterable[ProjectOverride],
) -> dict[str, ProjectOverride]:
    index: dict[str, ProjectOverride] = {}
    for override in overrides:
        if override.parameter_id in index:
            raise JurisdictionRefusal(
                RefusalReason.INVALID_OVERRIDE,
                f"two overrides for parameter {override.parameter_id}",
            )
        index[override.parameter_id] = override
    return index


def _load_bound_pack(
    binding: JurisdictionBinding, source: PackSource
) -> JurisdictionPack:
    code = binding.jurisdiction_code
    version = binding.contract_pack_version
    versions = source.versions(code)
    if not versions:
        raise JurisdictionRefusal(
            RefusalReason.UNKNOWN_JURISDICTION,
            f"binding {binding.binding_id}: no pack is registered for jurisdiction {code}",
        )
    if version not in versions:
        raise JurisdictionRefusal(
            RefusalReason.UNSUPPORTED_VERSION,
            f"binding {binding.binding_id}: {code} has no pack version {version} "
            f"(registered: {', '.join(sorted(versions))})",
        )
    try:
        pack = source.load(code, version)
    except (FileNotFoundError, ValueError) as error:
        raise JurisdictionRefusal(
            RefusalReason.INVALID_PACK,
            f"binding {binding.binding_id}: {code} {version} did not load: {error}",
        ) from error
    if (
        pack.pack_id != binding.contract_pack_id
        or pack.jurisdiction_code != code
        or pack.version != version
    ):
        raise JurisdictionRefusal(
            RefusalReason.PACK_IDENTITY_MISMATCH,
            f"binding {binding.binding_id} names {binding.contract_pack_id} {code} "
            f"{version}, but the registered pack is {pack.pack_id} "
            f"{pack.jurisdiction_code} {pack.version}",
        )
    return pack


def _subject_parameters(
    pack: JurisdictionPack, subject: JurisdictionSubject
) -> dict[str, list[PackParameter]]:
    parameters: dict[str, list[PackParameter]] = {}
    for parameter in pack.parameters:
        if parameter.subject is subject:
            parameters.setdefault(parameter.parameter_id, []).append(parameter)
    if not parameters:
        raise JurisdictionRefusal(
            RefusalReason.SUBJECT_NOT_COVERED,
            f"pack {pack.pack_id} {pack.version} has no parameter for subject "
            f"'{subject.value}'",
        )
    for windows in parameters.values():
        windows.sort(key=lambda p: p.effective_from)
    return parameters


def _window_for(windows: list[PackParameter], when: date) -> Optional[PackParameter]:
    for parameter in windows:
        if parameter.effective_from <= when and (
            parameter.effective_to is None or when < parameter.effective_to
        ):
            return parameter
    return None


def _in_force(
    parameter_id: str, windows: list[PackParameter], when: date
) -> PackParameter:
    found = _window_for(windows, when)
    if found is not None:
        return found
    if when < windows[0].effective_from:
        where = f"before its first window, which opens {windows[0].effective_from}"
    elif windows[-1].effective_to is not None and when >= windows[-1].effective_to:
        where = f"after its last window, which closed {windows[-1].effective_to}"
    else:
        where = "in a gap between its windows"
    raise JurisdictionRefusal(
        RefusalReason.NO_VALUE_IN_FORCE,
        f"parameter {parameter_id} has no value in force on {when}: the date falls {where}",
    )


def _check_override_value(override: ProjectOverride, parameter: PackParameter) -> None:
    is_flag = isinstance(override.value, bool)
    if (parameter.unit is ParameterUnit.FLAG) != is_flag:
        raise JurisdictionRefusal(
            RefusalReason.INVALID_OVERRIDE,
            f"override of {override.parameter_id}: value {override.value!r} does not "
            f"fit unit '{parameter.unit.value}'",
        )
    if (
        parameter.unit is ParameterUnit.FRACTION
        and not 0.0 <= float(override.value) <= 1.0
    ):
        raise JurisdictionRefusal(
            RefusalReason.INVALID_OVERRIDE,
            f"override of {override.parameter_id}: a fraction must lie in [0, 1], "
            f"got {override.value}",
        )
    if parameter.unit in (ParameterUnit.YEARS, ParameterUnit.MULTIPLE) and (
        float(override.value) < 0
    ):
        raise JurisdictionRefusal(
            RefusalReason.INVALID_OVERRIDE,
            f"override of {override.parameter_id}: value must not be negative",
        )


def _resolved(
    parameter: PackParameter, value: ScalarValue, origin: ValueOrigin
) -> ResolvedParameter:
    return ResolvedParameter(
        parameter_id=parameter.parameter_id,
        scenario_key=parameter.scenario_key,
        unit=parameter.unit,
        value=value,
        origin=origin,
        pack_value=parameter.value,
        status=parameter.status,
        effective_from=parameter.effective_from,
    )


def _two_pack_conflicts(
    subject: JurisdictionSubject,
    packs: list[JurisdictionPack],
    refs: tuple[PackRef, ...],
    dates: tuple[date, ...],
) -> list[ConflictRecord]:
    per_pack: list[dict[str, list[PackParameter]]] = []
    for pack in packs:
        parameters: dict[str, list[PackParameter]] = {}
        for parameter in pack.parameters:
            if parameter.subject is subject:
                parameters.setdefault(parameter.parameter_id, []).append(parameter)
        per_pack.append(parameters)
    parameter_ids = sorted({pid for parameters in per_pack for pid in parameters})
    records: list[ConflictRecord] = []
    for parameter_id in parameter_ids:
        for when in dates:
            candidates = []
            for ref, parameters in zip(refs, per_pack, strict=True):
                found = _window_for(parameters.get(parameter_id, []), when)
                candidates.append(
                    ConflictCandidate(
                        origin=_origin(ref),
                        value=None if found is None else found.value,
                    )
                )
            records.append(
                ConflictRecord(
                    kind=ConflictKind.SUBJECT_CLAIMED_BY_TWO_PACKS,
                    subject=subject,
                    parameter_id=parameter_id,
                    valuation_date=when,
                    candidates=tuple(candidates),
                )
            )
    return records


def _origin(ref: PackRef) -> str:
    return f"pack {ref.pack_id} {ref.jurisdiction_code} {ref.version}"


def _pack_ref(pack: JurisdictionPack) -> PackRef:
    return PackRef(
        jurisdiction_code=pack.jurisdiction_code,
        pack_id=pack.pack_id,
        version=pack.version,
        status=pack.status,
        content_sha256=_digest(pack.model_dump(mode="json")),
    )


def _digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
