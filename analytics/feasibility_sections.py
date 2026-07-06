"""Feasibility-report section schema — the 20-section taxonomy resolver (issue #616).

A full renewable-energy **project feasibility report** is broader than the lender
financial-model report the pipeline already renders: it wraps the model outputs in the
complete IC/DFI document skeleton — executive investment thesis, site & permits, technology
basis, E&S and climate resilience, construction logistics, risk register, appendices (the
static-audit §11 twenty-section list). This module is the config-first schema for that
skeleton: WHICH sections exist, in WHAT order, under WHICH group (technical / financial /
legal / environmental & social / grid / logistics / risk), and how a scenario's authored
coverage rolls up.

A scenario may declare a ``feasibility_sections.sections`` block mapping each canonical
section to a declaration record (``status`` complete/draft/not_applicable, optional
``narrative``, optional ``na_reason``); this validates it against the taxonomy and rolls
coverage up per group and overall — critically the list of canonical sections still
**missing**, because an IC pack with holes is not decision-grade.

It mirrors :mod:`analytics.conditions_precedent` (slice 2) deliberately:

- **Config-first** (CESSPIT / CCCDIR — never a Python literal). The taxonomy (the ordered
  declaration scale + the canonical groups + the ordered 20 sections) lives in
  ``config/feasibility_sections.yaml``; the enforcement policy resolves
  ``scenario feasibility_sections.{enforce,require_complete}`` →
  ``config/defaults.yaml`` ``defaults.feasibility_sections.*``.
- **Pure presentation schema**: raises / warns / no-ops; it changes no computed number
  (byte-identical economics) and recomputes nothing — every number a rendered section will
  ever show originates from the canonical pipeline run (no IRR/NPV outside
  ``finance/irr.py``). The models are frozen pydantic ``extra="forbid"`` contracts,
  consistent with :mod:`app.reports.report_model`'s section models — this schema EXTENDS the
  lender ``ReportContext`` pattern; it does not fork a second report model.

**Soft by default** (``enforce: false``, ``require_complete: false``) — a scenario with no /
partial authored sections is *reported on*, never broken (render-when-present). An IC-grade
scenario opts into hard enforcement (``require_complete: true`` to demand a declared status
for all 20 canonical sections).

The analysis is split (CCCDIR): :func:`build_feasibility_report` is a *pure, tolerant*
builder (the report pack consumes it too); :func:`validate_feasibility_sections` applies the
policy.

This is slice 1 of 5 of the feasibility-report generator (issue #616): the section schema +
taxonomy. The remaining slices (IC summary + red-flag section #706, evidence-completeness
score #707, route/template wiring #708) build on these models.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from pydantic import BaseModel, ConfigDict

from analytics.config_schema import RequiredFieldSpec, register_required_fields

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"
_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "feasibility_sections.yaml"
)

#: The one declaration that documents an exclusion (needs a reason, not rendered).
_NOT_APPLICABLE_STATUS = "not_applicable"

#: Recognised OPTIONAL per-section technology lens (issue #851). PRESENTATION metadata only —
#: it never gates coverage. ``shared`` = spans every active technology (rendered as a per-tech
#: sub-chapter for each active tech); a specific tag = reads under one technology only.
_SECTION_TECHNOLOGIES: Tuple[str, ...] = ("wind", "solar", "bess", "shared")


class FeasibilitySectionsError(ValueError):
    """Raised when a scenario's feasibility-section coverage is not IC-grade."""


class SectionDefinition(BaseModel):
    """One canonical feasibility section's definition (name, group, title, description).

    ``technology`` (issue #851) is an OPTIONAL presentation lens — ``wind | solar | bess |
    shared`` — declaring which technology the section reads under; ``None`` (the default,
    untagged) behaves exactly as before. It never gates coverage; the report layer uses it to
    render per-technology sub-chapters (a ``shared`` section is rendered once per active
    generation technology).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    group: str
    title: str
    description: str = ""
    technology: str | None = None


class FeasibilityTaxonomy(BaseModel):
    """The config-sourced taxonomy: the declaration scale + groups + ordered sections.

    ``statuses`` is ordered BEST → WORST; ``status_rank`` maps a status to its index. The
    ``sections`` are the canonical ORDERED feasibility-report skeleton (list position =
    report order), each tagged to a ``group``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    statuses: Tuple[str, ...]
    groups: Tuple[str, ...]
    sections: Tuple[SectionDefinition, ...]

    @property
    def status_rank(self) -> Mapping[str, int]:
        return {name: i for i, name in enumerate(self.statuses)}

    @property
    def section_names(self) -> Tuple[str, ...]:
        return tuple(d.name for d in self.sections)

    @property
    def group_of(self) -> Mapping[str, str]:
        """Map each canonical section name to its declared group."""
        return {d.name: d.group for d in self.sections}

    @property
    def technology_of(self) -> Mapping[str, str]:
        """Map each canonical section name to its OPTIONAL technology lens (#851).

        Only sections that declare a ``technology`` tag appear; an untagged section is absent
        (its lens is ``None``). Used by the report layer to decide which sections render
        per-technology sub-chapters (``shared``) — never a coverage gate.
        """
        return {d.name: d.technology for d in self.sections if d.technology is not None}


class FeasibilityPolicy(BaseModel):
    """Resolved feasibility-section enforcement policy for a scenario.

    Attributes:
        enforce: Treat findings as errors (raise) rather than warnings. Default False (soft).
        require_complete: Every canonical section must have a declared status; a missing
            section becomes a finding.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    enforce: bool
    require_complete: bool


class FeasibilityFinding(BaseModel):
    """One issue found in a scenario's feasibility-section declarations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str  # unknown_section | unknown_status | missing_field | incomplete
    section: str
    detail: str


class FeasibilitySection(BaseModel):
    """One declared section (canonical name, group, title, status, authored narrative)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    group: str
    title: str
    status: str
    narrative: str = ""
    na_reason: str = ""

    @property
    def is_excluded(self) -> bool:
        """True when this section is a documented exclusion (``not_applicable``)."""
        return self.status == _NOT_APPLICABLE_STATUS


class FeasibilityReport(BaseModel):
    """Structured feasibility-section coverage of a scenario (pure, policy-free).

    ``all_complete`` is the headline gate: True only when at least one section is declared
    AND every canonical section is either ``complete`` or a documented ``not_applicable``
    (nothing missing, nothing still in draft). ``missing`` lists the canonical sections with
    no declared status — the holes in the IC pack. ``by_group_missing`` gives the missing
    count per group so the report can flag exactly which parts of the skeleton are unwritten.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    sections: Tuple[FeasibilitySection, ...]
    n_complete: int
    n_draft: int
    n_not_applicable: int
    by_group_missing: Mapping[str, int]
    covered: Tuple[str, ...]
    missing: Tuple[str, ...]
    findings: Tuple[FeasibilityFinding, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.findings

    @property
    def all_complete(self) -> bool:
        """True when sections are declared, none is missing, and none is still a draft."""
        return bool(self.sections) and not self.missing and self.n_draft == 0


@lru_cache(maxsize=1)
def load_feasibility_taxonomy() -> FeasibilityTaxonomy:
    """The single config-sourced section taxonomy (``config/feasibility_sections.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_TAXONOMY_PATH.read_text())
    try:
        statuses = tuple(str(s) for s in data["section_statuses"])
        groups = tuple(str(g) for g in data["section_groups"])
        raw_sections = data["sections"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/feasibility_sections.yaml must define a non-empty 'section_statuses' "
            "list (best->worst), a 'section_groups' list, and a 'sections' list "
            f"({_TAXONOMY_PATH})"
        ) from exc
    if not statuses or not groups or not raw_sections:
        raise ValueError(
            "config/feasibility_sections.yaml 'section_statuses', 'section_groups', and "
            f"'sections' must all be non-empty ({_TAXONOMY_PATH})"
        )
    group_set = set(groups)
    sections: List[SectionDefinition] = []
    for rec in raw_sections:
        if not isinstance(rec, Mapping) or "name" not in rec or "group" not in rec:
            raise ValueError(
                "config/feasibility_sections.yaml sections entries must be mappings with "
                f"'name' and 'group' keys; got {rec!r}"
            )
        group = str(rec["group"])
        if group not in group_set:
            raise ValueError(
                f"config/feasibility_sections.yaml section {rec['name']!r} declares "
                f"group {group!r} which is not in section_groups ({', '.join(groups)})"
            )
        technology = rec.get("technology")
        if technology is not None:
            technology = str(technology).strip().lower()
            if technology not in _SECTION_TECHNOLOGIES:
                raise ValueError(
                    f"config/feasibility_sections.yaml section {rec['name']!r} declares "
                    f"technology {technology!r} which is not recognised "
                    f"({', '.join(_SECTION_TECHNOLOGIES)})"
                )
        sections.append(
            SectionDefinition(
                name=str(rec["name"]),
                group=group,
                title=str(rec.get("title", str(rec["name"]))),
                description=str(rec.get("description", "")),
                technology=technology,
            )
        )
    names = [d.name for d in sections]
    if len(set(names)) != len(names):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise ValueError(
            "config/feasibility_sections.yaml sections must have unique names; duplicated: "
            f"{', '.join(dupes)} ({_TAXONOMY_PATH})"
        )
    return FeasibilityTaxonomy(
        statuses=statuses, groups=groups, sections=tuple(sections)
    )


@lru_cache(maxsize=1)
def default_feasibility_policy() -> FeasibilityPolicy:
    """The single config-sourced enforcement policy (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["feasibility_sections"]
        return FeasibilityPolicy(
            enforce=bool(block["enforce"]),
            require_complete=bool(block["require_complete"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.feasibility_sections "
            f"{{enforce, require_complete}} ({_DEFAULTS_PATH})"
        ) from exc


def _resolve_bool(block: Mapping[str, Any], key: str, fallback: bool) -> bool:
    if key not in block:
        return fallback
    value = block[key]
    if not isinstance(value, bool):
        raise ValueError(f"feasibility_sections.{key} must be a boolean; got {value!r}")
    return value


def resolve_feasibility_policy(config: Mapping[str, Any]) -> FeasibilityPolicy:
    """Resolve the section policy for a scenario (scenario keys override the defaults)."""
    default = default_feasibility_policy()
    block = config.get("feasibility_sections")
    if not isinstance(block, Mapping):
        return default
    return FeasibilityPolicy(
        enforce=_resolve_bool(block, "enforce", default.enforce),
        require_complete=_resolve_bool(
            block, "require_complete", default.require_complete
        ),
    )


def _declared(config: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Extract ``feasibility_sections.sections`` as (section-name, record) pairs.

    Accepts a mapping (section -> record) or a list of records each carrying a ``name``
    key. Returns [] when no block / no sections are declared.
    """
    block = config.get("feasibility_sections")
    if not isinstance(block, Mapping):
        return []
    sections = block.get("sections")
    if sections is None:
        return []
    if isinstance(sections, Mapping):
        return [(str(k), v) for k, v in sections.items()]
    if isinstance(sections, (list, tuple)):
        out: List[Tuple[str, Mapping[str, Any]]] = []
        for rec in sections:
            if not isinstance(rec, Mapping) or "name" not in rec:
                raise FeasibilitySectionsError(
                    "feasibility_sections.sections list entries must be mappings with a "
                    f"'name' key; got {rec!r}"
                )
            out.append((str(rec["name"]), rec))
        return out
    raise FeasibilitySectionsError(
        "feasibility_sections.sections must be a mapping or a list of {name, ...} "
        f"records; got {type(sections).__name__}"
    )


def build_feasibility_report(config: Mapping[str, Any]) -> FeasibilityReport:
    """Build a tolerant, policy-free feasibility-section report for a scenario.

    Records findings (unknown section / unknown status / missing status / incomplete
    coverage) but never raises on *content* — only on a structurally malformed ``sections``
    container. Rolls the valid declarations up to the coverage counts (overall and the
    missing count per group). The policy decision (raise / warn / no-op) is
    :func:`validate_feasibility_sections`'s job.

    Rendered sections keep the TAXONOMY order (report order), not declaration order; the
    group and title a rendered section carries are the CANONICAL ones from the taxonomy. A
    section not in the taxonomy is flagged (unknown_section) and dropped from the rollup —
    the skeleton is fixed config, a scenario cannot invent report sections.
    """
    taxonomy = load_feasibility_taxonomy()
    pairs = _declared(config)
    findings: List[FeasibilityFinding] = []
    valid: Dict[str, FeasibilitySection] = {}
    group_of = taxonomy.group_of
    title_of = {d.name: d.title for d in taxonomy.sections}

    for name, rec in pairs:
        if not isinstance(rec, Mapping):
            findings.append(
                FeasibilityFinding(
                    kind="missing_field", section=name, detail="entry is not a mapping"
                )
            )
            continue
        if name not in group_of:
            findings.append(
                FeasibilityFinding(
                    kind="unknown_section",
                    section=name,
                    detail=(
                        "not a canonical feasibility section "
                        f"({', '.join(taxonomy.section_names)})"
                    ),
                )
            )
            continue
        status = rec.get("status")
        if status is None or status == "":
            findings.append(
                FeasibilityFinding(
                    kind="missing_field",
                    section=name,
                    detail="missing required 'status'",
                )
            )
            continue
        status = str(status)
        if status not in taxonomy.status_rank:
            findings.append(
                FeasibilityFinding(
                    kind="unknown_status",
                    section=name,
                    detail=(
                        f"status {status!r} is not in the section scale "
                        f"({', '.join(taxonomy.statuses)})"
                    ),
                )
            )
            continue
        valid[name] = FeasibilitySection(
            name=name,
            group=group_of[name],
            title=title_of[name],
            status=status,
            narrative=str(rec.get("narrative", "")),
            na_reason=str(rec.get("na_reason", "")),
        )

    # Taxonomy order = report order.
    rendered = tuple(valid[n] for n in taxonomy.section_names if n in valid)
    declared_names = {name for name, _ in pairs}
    missing = tuple(n for n in taxonomy.section_names if n not in declared_names)
    policy = resolve_feasibility_policy(config)
    if policy.require_complete:
        for n in missing:
            findings.append(
                FeasibilityFinding(
                    kind="incomplete",
                    section=n,
                    detail="section has no declared status",
                )
            )

    n_complete = sum(1 for s in rendered if s.status == "complete")
    n_draft = sum(1 for s in rendered if s.status == "draft")
    n_na = sum(1 for s in rendered if s.status == _NOT_APPLICABLE_STATUS)
    by_group_missing: Dict[str, int] = {}
    for n in missing:
        g = group_of[n]
        by_group_missing[g] = by_group_missing.get(g, 0) + 1
    covered = tuple(n for n in taxonomy.section_names if n in declared_names)
    return FeasibilityReport(
        sections=rendered,
        n_complete=n_complete,
        n_draft=n_draft,
        n_not_applicable=n_na,
        by_group_missing=by_group_missing,
        covered=covered,
        missing=missing,
        findings=tuple(findings),
    )


def validate_feasibility_sections(
    config: Mapping[str, Any], config_path: str | None = None
) -> FeasibilityReport:
    """Validate a scenario's feasibility-section coverage against the resolved policy.

    Builds the report and applies the policy: when ``enforce`` is set, any finding raises
    :class:`FeasibilitySectionsError`; otherwise findings are logged as warnings (soft — the
    default). Always returns the report (so the report pack can consume the rollup). No-op
    (clean report, no log) when the scenario declares no sections and completeness is not
    required. Changes no computed number.
    """
    policy = resolve_feasibility_policy(config)
    where = f" in '{config_path}'" if config_path else ""
    report = build_feasibility_report(config)

    if report.is_clean:
        if report.sections:
            logger.debug(
                "Feasibility sections%s: %d complete, %d draft, %d n/a, %d missing.",
                where,
                report.n_complete,
                report.n_draft,
                report.n_not_applicable,
                len(report.missing),
            )
        return report

    summary = "; ".join(f"[{f.kind}] {f.section}: {f.detail}" for f in report.findings)
    if policy.enforce:
        raise FeasibilitySectionsError(
            f"Feasibility-section coverage is not IC-grade{where}: {summary}"
        )
    logger.warning(
        "Feasibility-section findings%s (soft; enforce=false): %s", where, summary
    )
    return report


# Declare feasibility_sections in the central config schema (CCCDIR) so it appears in the
# lender schema export (build_schema_dataframe). It is OPTIONAL and WARNING-only — the field
# is enforced (softly) by validate_feasibility_sections, not by the required-field guard, so
# a scenario without it is never blocked.
_FEASIBILITY_SCHEMA_SPECS = [
    RequiredFieldSpec(
        module="feasibility_sections",
        name="feasibility_sections",
        paths=[("feasibility_sections", "sections")],
        required=False,
        severity="warning",
        description=(
            "Feasibility-report section declarations (section -> status/narrative) against "
            "the canonical 20-section skeleton. Optional; validated softly by "
            "analytics.feasibility_sections.validate_feasibility_sections."
        ),
    ),
]
register_required_fields("feasibility_sections", _FEASIBILITY_SCHEMA_SPECS)


__all__ = [
    "FeasibilitySectionsError",
    "SectionDefinition",
    "FeasibilityTaxonomy",
    "FeasibilityPolicy",
    "FeasibilityFinding",
    "FeasibilitySection",
    "FeasibilityReport",
    "load_feasibility_taxonomy",
    "default_feasibility_policy",
    "resolve_feasibility_policy",
    "build_feasibility_report",
    "validate_feasibility_sections",
]
