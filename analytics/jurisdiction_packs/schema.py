"""Schema and loader for versioned jurisdiction rule packs (#1842).

A jurisdiction pack holds one country's *statutory* parameters as sourced,
effective-dated data, so that a project in that country can later be resolved
against it rather than carrying its own copy of the law in every scenario.

Each parameter records:

* the value, its unit and the governed subject it applies to (the ``ProjectCase``
  ``JurisdictionSubject`` vocabulary);
* the scenario key that carries the same value today, so a later slice of #1841 can
  move the engine onto the pack without changing an output;
* where the value comes from: instrument, clause, link or file hash, and the
  repository record that first carried it;
* when it applies: ``effective_from`` with how that date is known, an optional
  ``effective_to``, and the date the value was recorded;
* how far the source has been checked (``status``).

The pack-level fields follow ``docs/FEASIBILITY_REPORT_CONTRACT.md`` section 3.1 and the
``PackBinding`` record. A v1 pack can be ``unsupported`` or ``supported`` but never
``assured``: assurance needs a scope-specific independent review record, which v1 has no
type for.

The schema is strict. Unknown keys, coerced types, a parameter without a source,
overlapping effective windows and duplicate parameters are refused with an error that
names the field. Nothing in the engine reads a pack yet.
"""

from __future__ import annotations

import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import Field, StrictBool, StrictFloat, StrictInt, model_validator

from analytics.feasibility_report_contract.project_case import JurisdictionSubject
from analytics.feasibility_report_contract.vocabulary import (
    Identifier,
    JurisdictionCode,
    NonEmptyText,
    PackKind,
    PackStatus,
    SemanticVersion,
    Sha256Hex,
    StrictFrozenModel,
)

JURISDICTION_PACK_SCHEMA_ID: Literal["dutchbay.jurisdiction_pack.v1"] = (
    "dutchbay.jurisdiction_pack.v1"
)

#: Directory holding the registered packs: ``<code lower case>/<version>.yaml``.
PACKS_ROOT: Path = Path(__file__).resolve().parents[2] / "conf" / "jurisdiction_packs"

ScalarValue = Union[StrictBool, StrictInt, StrictFloat]


class ParameterUnit(str, Enum):
    """Unit of a pack parameter value."""

    FRACTION = "fraction"
    YEARS = "years"
    MULTIPLE = "multiple"
    FLAG = "flag"


class ParameterStatus(str, Enum):
    """How far a parameter's source has been checked.

    ``published``: the primary instrument is pinned (link and file hash) and the clause
    is named. ``as_recorded``: the value and its citation are as the repository recorded
    them; the primary text is not pinned. ``analogy_unpublished``: no instrument sets the
    value; it is derived by analogy from one that does. ``unconfirmed``: no reliable
    source is recorded.
    """

    PUBLISHED = "published"
    AS_RECORDED = "as_recorded"
    ANALOGY_UNPUBLISHED = "analogy_unpublished"
    UNCONFIRMED = "unconfirmed"


class EffectiveFromBasis(str, Enum):
    """How a parameter's ``effective_from`` date is known.

    ``instrument``: the date the instrument says the value takes effect.
    ``in_force_by``: the value is recorded as in force on this date; it may have taken
    effect earlier, and a valuation before this date is outside what the pack knows.
    """

    INSTRUMENT = "instrument"
    IN_FORCE_BY = "in_force_by"


class SourceCitation(StrictFrozenModel):
    """Where a parameter value comes from.

    Attributes:
        instrument: The statute, regulation, decision or tariff guide, as cited.
        clause: The section, schedule or line, when known.
        official_url: A link to the official text, when recorded.
        document_sha256: SHA-256 of the official document read, when pinned.
        repository_record: The repository file and commit that first carried the
            value with this citation.
    """

    instrument: NonEmptyText
    clause: Optional[NonEmptyText] = None
    official_url: Optional[NonEmptyText] = None
    document_sha256: Optional[Sha256Hex] = None
    repository_record: NonEmptyText


class PackParameter(StrictFrozenModel):
    """One statutory value, its source and the window in which it applies.

    Attributes:
        parameter_id: Stable identifier, unique within a pack per effective window.
        subject: Governed subject (``ProjectCase`` vocabulary).
        scenario_key: Dotted scenario key that carries the same value today.
        value: The value, in ``unit``.
        unit: Unit of ``value``.
        conditions: When the value applies, in words. Machine predicates come later.
        effective_from: First date the value applies (see ``effective_from_basis``).
        effective_from_basis: How ``effective_from`` is known.
        effective_to: First date the value no longer applies, or ``None`` if open.
        recorded_at: Date the repository recorded the value.
        status: How far the source has been checked.
        sources: At least one citation.
        note: Anything a reader needs to use the value correctly.
    """

    parameter_id: Identifier
    subject: JurisdictionSubject
    scenario_key: Identifier
    value: ScalarValue
    unit: ParameterUnit
    conditions: tuple[NonEmptyText, ...] = ()
    effective_from: date
    effective_from_basis: EffectiveFromBasis
    effective_to: Optional[date] = None
    recorded_at: date
    status: ParameterStatus
    sources: tuple[SourceCitation, ...] = Field(min_length=1)
    note: Optional[NonEmptyText] = None

    @model_validator(mode="after")
    def _check_parameter(self) -> "PackParameter":
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError(
                f"parameter {self.parameter_id}: effective_to {self.effective_to} must be "
                f"after effective_from {self.effective_from}"
            )
        is_flag = isinstance(self.value, bool)
        if (self.unit is ParameterUnit.FLAG) != is_flag:
            raise ValueError(
                f"parameter {self.parameter_id}: unit 'flag' needs a true/false value and "
                f"a true/false value needs unit 'flag'"
            )
        if self.unit is ParameterUnit.FRACTION and not 0.0 <= float(self.value) <= 1.0:
            raise ValueError(
                f"parameter {self.parameter_id}: a fraction must lie in [0, 1], "
                f"got {self.value}"
            )
        if (
            self.unit in (ParameterUnit.YEARS, ParameterUnit.MULTIPLE)
            and float(self.value) < 0
        ):
            raise ValueError(
                f"parameter {self.parameter_id}: value must not be negative"
            )
        if self.status is ParameterStatus.PUBLISHED and not any(
            s.clause and s.official_url and s.document_sha256 for s in self.sources
        ):
            raise ValueError(
                f"parameter {self.parameter_id}: status 'published' needs a source with a "
                f"clause, an official_url and a document_sha256"
            )
        if (
            self.status is ParameterStatus.PUBLISHED
            and self.effective_from_basis is not EffectiveFromBasis.INSTRUMENT
        ):
            raise ValueError(
                f"parameter {self.parameter_id}: status 'published' needs "
                f"effective_from_basis 'instrument'"
            )
        return self


class JurisdictionPack(StrictFrozenModel):
    """A versioned, sourced set of one jurisdiction's statutory parameters.

    Attributes:
        schema_id: Fixed schema identifier.
        pack_id: Stable pack identifier.
        kind: Always ``jurisdiction``.
        version: Semantic version of the pack.
        jurisdiction_code: Code the pack governs, as used by ``ProjectCase``.
        jurisdiction_name: Human-readable name.
        status: ``unsupported`` or ``supported``; v1 refuses ``assured``.
        owner: Who maintains the pack.
        effective_date: Date this pack version was issued.
        review_date: Date by which the pack must be reviewed.
        limitations: Known limitations a user must read.
        prohibited_substitutions: Things the pack must never be used to do.
        parameters: The parameters.
    """

    schema_id: Literal["dutchbay.jurisdiction_pack.v1"]
    pack_id: Identifier
    kind: Literal[PackKind.JURISDICTION]
    version: SemanticVersion
    jurisdiction_code: JurisdictionCode
    jurisdiction_name: NonEmptyText
    status: PackStatus
    owner: NonEmptyText
    effective_date: date
    review_date: date
    limitations: tuple[NonEmptyText, ...] = Field(min_length=1)
    prohibited_substitutions: tuple[NonEmptyText, ...] = Field(min_length=1)
    parameters: tuple[PackParameter, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_pack(self) -> "JurisdictionPack":
        if self.status is PackStatus.ASSURED:
            raise ValueError(
                f"pack {self.pack_id}: v1 cannot be 'assured'; assurance needs an "
                f"independent review record (FEASIBILITY_REPORT_CONTRACT section 3)"
            )
        if self.review_date <= self.effective_date:
            raise ValueError(
                f"pack {self.pack_id}: review_date must be after effective_date"
            )
        windows: dict[str, list[tuple[date, Optional[date]]]] = {}
        keys: dict[str, str] = {}
        for p in self.parameters:
            windows.setdefault(p.parameter_id, []).append(
                (p.effective_from, p.effective_to)
            )
            other = keys.setdefault(p.scenario_key, p.parameter_id)
            if other != p.parameter_id:
                raise ValueError(
                    f"pack {self.pack_id}: scenario_key {p.scenario_key} is claimed by both "
                    f"{other} and {p.parameter_id}"
                )
        for pid, spans in windows.items():
            spans.sort(key=lambda s: s[0])
            for (start, end), (next_start, _) in zip(spans, spans[1:], strict=False):
                if start == next_start or end is None or end > next_start:
                    raise ValueError(
                        f"pack {self.pack_id}: parameter {pid} has overlapping effective "
                        f"windows starting {start} and {next_start}"
                    )
        return self


def load_pack_file(path: Path) -> JurisdictionPack:
    """Load and validate one pack file.

    Args:
        path: Path to a pack YAML file.

    Returns:
        The validated pack.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a mapping or fails validation.
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: a jurisdiction pack must be a YAML mapping")
    # Validate in JSON mode: strict mode then accepts ISO dates and enum values as the
    # file spells them, while still refusing coercions such as "0.3" for 0.3.
    return JurisdictionPack.model_validate_json(json.dumps(data, default=_json_default))


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"unsupported value in a jurisdiction pack: {value!r}")


def load_registered_pack(
    jurisdiction_code: str, version: str, root: Optional[Path] = None
) -> JurisdictionPack:
    """Load a registered pack by jurisdiction code and version.

    The file is ``<root>/<code lower case>/<version>.yaml`` and must declare the same
    code and version it is filed under.

    Args:
        jurisdiction_code: Jurisdiction code, for example ``LK``.
        version: Pack semantic version, for example ``1.0.0``.
        root: Packs directory; defaults to :data:`PACKS_ROOT`.

    Returns:
        The validated pack.

    Raises:
        FileNotFoundError: If no pack is registered under that code and version.
        ValueError: If the file fails validation or declares another code or version.
    """
    base = PACKS_ROOT if root is None else Path(root)
    path = base / jurisdiction_code.lower() / f"{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"no jurisdiction pack registered for {jurisdiction_code} {version} at {path}"
        )
    pack = load_pack_file(path)
    if pack.jurisdiction_code != jurisdiction_code or pack.version != version:
        raise ValueError(
            f"{path}: declares {pack.jurisdiction_code} {pack.version}, but is filed "
            f"under {jurisdiction_code} {version}"
        )
    return pack
