"""Conditions-precedent (CP) checklist — first-drawdown / financial-close gate (issue #616).

A DFI/lender loan agreement lists specific **conditions precedent** to first drawdown: the
discrete documentary, legal, and technical deliverables that must be in place (or explicitly
waived by the lender) before funds flow — e.g. the PPA executed, the ESIA approved, the EPC
contract signed, all permits issued, the security package perfected. This is finer-grained
than the development-readiness R/A/G register (:mod:`analytics.development_readiness`, which
rolls a whole workstream to one status): a CP checklist tracks each *named condition* to a
satisfied / waived / pending state, so the lender knows exactly which line items still gate
the first drawdown.

This module is the config-first register for that checklist: a scenario may declare a
``conditions_precedent.items`` block mapping each named CP to a status record
(``status``, optional ``note``, optional ``waived_reason``), and this validates it against the
taxonomy and rolls each workstream and the overall schedule up to a satisfaction summary —
critically, the count of CPs still **outstanding** (``pending``), because a single outstanding
CP blocks first drawdown.

It mirrors :mod:`analytics.development_readiness` (C11) and :mod:`analytics.evidence_register`
(C5) deliberately:

- **Config-first** (CESSPIT / CCCDIR — never a Python literal). The taxonomy (the ordered
  satisfaction scale + the canonical CP workstreams + the named CP items) lives in
  ``config/conditions_precedent.yaml``; the enforcement policy resolves
  ``scenario conditions_precedent.{enforce,require_complete}`` →
  ``config/defaults.yaml`` ``defaults.conditions_precedent.*``.
- **Pure detector**: raises / warns / no-ops; it changes no computed number (byte-identical
  economics), and the report layer surfaces the rollup read-only.

**Soft by default** (``enforce: false``, ``require_complete: false``) — a scenario with no /
partial checklist is *reported on*, never broken. A lender-grade scenario opts into hard
enforcement (e.g. ``require_complete: true`` to demand a status for every canonical CP item).

The analysis is split (CCCDIR): :func:`build_cp_report` is a *pure, tolerant* builder (used by
the report pack too); :func:`validate_conditions_precedent` applies the policy.

This is slice 2 of 5 of the feasibility-report generator (issue #616): the CP-checklist data
model. The remaining slices (feasibility section schema, IC summary + red-flag section,
evidence-completeness score, route/template wiring) are tracked in follow-up issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"
_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "conditions_precedent.yaml"
)

#: The one CP status that leaves a condition outstanding (still gates first drawdown).
_OUTSTANDING_STATUS = "pending"


class ConditionsPrecedentError(ValueError):
    """Raised when a scenario's conditions-precedent checklist is not lender-grade."""


@dataclass(frozen=True)
class CpDefinition:
    """One canonical CP line item's definition (name, its workstream, a description)."""

    name: str
    workstream: str
    description: str = ""


@dataclass(frozen=True)
class CpTaxonomy:
    """The config-sourced taxonomy: the satisfaction scale + workstreams + named CP items.

    ``statuses`` is ordered BEST → WORST; ``status_rank`` maps a status to its index. The
    ``items`` are the canonical named conditions precedent, each tagged to a ``workstream``.
    """

    statuses: Tuple[str, ...]
    workstreams: Tuple[str, ...]
    items: Tuple[CpDefinition, ...]

    @property
    def status_rank(self) -> Mapping[str, int]:
        return {name: i for i, name in enumerate(self.statuses)}

    @property
    def item_names(self) -> Tuple[str, ...]:
        return tuple(d.name for d in self.items)

    @property
    def workstream_of(self) -> Mapping[str, str]:
        """Map each canonical CP item name to its declared workstream."""
        return {d.name: d.workstream for d in self.items}


@dataclass(frozen=True)
class CpPolicy:
    """Resolved conditions-precedent enforcement policy for a scenario.

    Attributes:
        enforce: Treat findings as errors (raise) rather than warnings. Default False (soft).
        require_complete: Every canonical CP item must have a declared status; a missing item
            becomes a finding.
    """

    enforce: bool
    require_complete: bool


@dataclass(frozen=True)
class CpFinding:
    """One issue found in a scenario's conditions-precedent checklist."""

    kind: str  # unknown_item | unknown_status | missing_field | incomplete
    item: str
    detail: str


@dataclass(frozen=True)
class CpItem:
    """One rendered CP line (item name, workstream, status, note, waived reason)."""

    name: str
    workstream: str
    status: str
    note: str = ""
    waived_reason: str = ""

    @property
    def is_outstanding(self) -> bool:
        """True when this CP still gates first drawdown (status ``pending``)."""
        return self.status == _OUTSTANDING_STATUS


@dataclass(frozen=True)
class CpReport:
    """Structured conditions-precedent coverage of a scenario (pure, policy-free).

    ``all_satisfied`` is the headline gate: True only when at least one CP is declared AND
    no declared CP is outstanding (``pending``). ``n_outstanding`` is the count of CPs that
    still gate first drawdown. ``by_workstream_outstanding`` gives the outstanding count per
    workstream so the report can flag exactly which buckets block drawdown.
    """

    items: Tuple[CpItem, ...]
    n_outstanding: int
    n_satisfied: int
    n_waived: int
    by_workstream_outstanding: Mapping[str, int]
    covered: Tuple[str, ...]
    missing: Tuple[str, ...]
    findings: Tuple[CpFinding, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.findings

    @property
    def all_satisfied(self) -> bool:
        """True when the checklist has declared CPs and none is outstanding."""
        return bool(self.items) and self.n_outstanding == 0


@lru_cache(maxsize=1)
def load_cp_taxonomy() -> CpTaxonomy:
    """The single config-sourced CP taxonomy (``config/conditions_precedent.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_TAXONOMY_PATH.read_text())
    try:
        statuses = tuple(str(s) for s in data["cp_statuses"])
        workstreams = tuple(str(w) for w in data["cp_workstreams"])
        raw_items = data["cp_items"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/conditions_precedent.yaml must define a non-empty 'cp_statuses' list "
            "(best->worst), a 'cp_workstreams' list, and a 'cp_items' list "
            f"({_TAXONOMY_PATH})"
        ) from exc
    if not statuses or not workstreams or not raw_items:
        raise ValueError(
            "config/conditions_precedent.yaml 'cp_statuses', 'cp_workstreams', and "
            f"'cp_items' must all be non-empty ({_TAXONOMY_PATH})"
        )
    items: List[CpDefinition] = []
    workstream_set = set(workstreams)
    for rec in raw_items:
        if not isinstance(rec, Mapping) or "name" not in rec or "workstream" not in rec:
            raise ValueError(
                "config/conditions_precedent.yaml cp_items entries must be mappings with "
                f"'name' and 'workstream' keys; got {rec!r}"
            )
        ws = str(rec["workstream"])
        if ws not in workstream_set:
            raise ValueError(
                f"config/conditions_precedent.yaml cp_item {rec['name']!r} declares "
                f"workstream {ws!r} which is not in cp_workstreams "
                f"({', '.join(workstreams)})"
            )
        items.append(
            CpDefinition(
                name=str(rec["name"]),
                workstream=ws,
                description=str(rec.get("description", "")),
            )
        )
    return CpTaxonomy(statuses=statuses, workstreams=workstreams, items=tuple(items))


@lru_cache(maxsize=1)
def default_cp_policy() -> CpPolicy:
    """The single config-sourced enforcement policy (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["conditions_precedent"]
        return CpPolicy(
            enforce=bool(block["enforce"]),
            require_complete=bool(block["require_complete"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.conditions_precedent "
            f"{{enforce, require_complete}} ({_DEFAULTS_PATH})"
        ) from exc


def _resolve_bool(block: Mapping[str, Any], key: str, fallback: bool) -> bool:
    if key not in block:
        return fallback
    value = block[key]
    if not isinstance(value, bool):
        raise ValueError(f"conditions_precedent.{key} must be a boolean; got {value!r}")
    return value


def resolve_cp_policy(config: Mapping[str, Any]) -> CpPolicy:
    """Resolve the CP policy for a scenario (scenario keys override the defaults)."""
    default = default_cp_policy()
    block = config.get("conditions_precedent")
    if not isinstance(block, Mapping):
        return default
    return CpPolicy(
        enforce=_resolve_bool(block, "enforce", default.enforce),
        require_complete=_resolve_bool(
            block, "require_complete", default.require_complete
        ),
    )


def _items(config: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Extract ``conditions_precedent.items`` as a list of (item-name, record) pairs.

    Accepts a mapping (item -> record) or a list of records each carrying a ``name`` key.
    Returns [] when no block / no items are declared.
    """
    block = config.get("conditions_precedent")
    if not isinstance(block, Mapping):
        return []
    items = block.get("items")
    if items is None:
        return []
    if isinstance(items, Mapping):
        return [(str(k), v) for k, v in items.items()]
    if isinstance(items, (list, tuple)):
        out: List[Tuple[str, Mapping[str, Any]]] = []
        for rec in items:
            if not isinstance(rec, Mapping) or "name" not in rec:
                raise ConditionsPrecedentError(
                    "conditions_precedent.items list entries must be mappings with a "
                    f"'name' key; got {rec!r}"
                )
            out.append((str(rec["name"]), rec))
        return out
    raise ConditionsPrecedentError(
        "conditions_precedent.items must be a mapping or a list of {name, ...} records; "
        f"got {type(items).__name__}"
    )


def build_cp_report(config: Mapping[str, Any]) -> CpReport:
    """Build a tolerant, policy-free conditions-precedent report for a scenario.

    Records findings (unknown item / unknown status / missing status / incomplete coverage)
    but never raises on *content* — only on a structurally malformed ``items`` container.
    Rolls the valid per-item statuses up to the outstanding-CP counts (overall and per
    workstream). The policy decision (raise / warn / no-op) is
    :func:`validate_conditions_precedent`'s job.

    The workstream a rendered item is attributed to is the CANONICAL one from the taxonomy
    (so the rollup is consistent with the CP schedule); an item not in the taxonomy is
    flagged (unknown_item) and attributed to its self-declared ``workstream`` for display
    only.
    """
    taxonomy = load_cp_taxonomy()
    pairs = _items(config)
    findings: List[CpFinding] = []
    rendered: List[CpItem] = []
    canonical_ws = taxonomy.workstream_of

    for name, rec in pairs:
        if not isinstance(rec, Mapping):
            findings.append(CpFinding("missing_field", name, "entry is not a mapping"))
            continue
        known = name in taxonomy.item_names
        if not known:
            findings.append(
                CpFinding(
                    "unknown_item",
                    name,
                    f"not a canonical condition precedent ({', '.join(taxonomy.item_names)})",
                )
            )
        status = rec.get("status")
        if status is None or status == "":
            findings.append(
                CpFinding("missing_field", name, "missing required 'status'")
            )
            continue
        status = str(status)
        if status not in taxonomy.status_rank:
            findings.append(
                CpFinding(
                    "unknown_status",
                    name,
                    f"status {status!r} is not in the CP scale ({', '.join(taxonomy.statuses)})",
                )
            )
            continue
        workstream = canonical_ws.get(name, str(rec.get("workstream", "")))
        rendered.append(
            CpItem(
                name=name,
                workstream=workstream,
                status=status,
                note=str(rec.get("note", "")),
                waived_reason=str(rec.get("waived_reason", "")),
            )
        )

    declared = {name for name, _ in pairs}
    missing = tuple(n for n in taxonomy.item_names if n not in declared)
    policy = resolve_cp_policy(config)
    if policy.require_complete:
        for n in missing:
            findings.append(
                CpFinding("incomplete", n, "condition precedent has no declared status")
            )

    n_outstanding = sum(1 for i in rendered if i.status == "pending")
    n_satisfied = sum(1 for i in rendered if i.status == "satisfied")
    n_waived = sum(1 for i in rendered if i.status == "waived")
    by_ws: Dict[str, int] = {}
    for i in rendered:
        if i.is_outstanding:
            by_ws[i.workstream] = by_ws.get(i.workstream, 0) + 1
    covered = tuple(n for n in taxonomy.item_names if n in declared)
    return CpReport(
        items=tuple(rendered),
        n_outstanding=n_outstanding,
        n_satisfied=n_satisfied,
        n_waived=n_waived,
        by_workstream_outstanding=by_ws,
        covered=covered,
        missing=missing,
        findings=tuple(findings),
    )


def validate_conditions_precedent(
    config: dict[str, Any], config_path: str | None = None
) -> CpReport:
    """Validate a scenario's conditions-precedent checklist against the resolved policy.

    Builds the report and applies the policy: when ``enforce`` is set, any finding raises
    :class:`ConditionsPrecedentError`; otherwise findings are logged as warnings (soft — the
    default). Always returns the report (so the report pack can consume the rollup). No-op
    (clean report, no log) when the scenario declares no checklist and completeness is not
    required. Changes no computed number.
    """
    policy = resolve_cp_policy(config)
    where = f" in '{config_path}'" if config_path else ""
    report = build_cp_report(config)

    if report.is_clean:
        if report.items:
            logger.debug(
                "Conditions precedent%s: %d/%d satisfied, %d waived, %d outstanding.",
                where,
                report.n_satisfied,
                len(report.items),
                report.n_waived,
                report.n_outstanding,
            )
        return report

    summary = "; ".join(f"[{f.kind}] {f.item}: {f.detail}" for f in report.findings)
    if policy.enforce:
        raise ConditionsPrecedentError(
            f"Conditions-precedent checklist is not lender-grade{where}: {summary}"
        )
    logger.warning(
        "Conditions-precedent findings%s (soft; enforce=false): %s", where, summary
    )
    return report


# Declare conditions_precedent in the central config schema (CCCDIR) so it appears in the
# lender schema export (build_schema_dataframe). It is OPTIONAL and WARNING-only — the field
# is enforced (softly) by validate_conditions_precedent, not by the required-field guard, so
# a scenario without it is never blocked.
_CP_SCHEMA_SPECS = [
    RequiredFieldSpec(
        module="conditions_precedent",
        name="conditions_precedent",
        paths=[("conditions_precedent", "items")],
        required=False,
        severity="warning",
        description=(
            "Conditions-precedent (CP) checklist (item -> status) gating first drawdown. "
            "Optional; validated softly by "
            "analytics.conditions_precedent.validate_conditions_precedent."
        ),
    ),
]
register_required_fields("conditions_precedent", _CP_SCHEMA_SPECS)


__all__ = [
    "ConditionsPrecedentError",
    "CpDefinition",
    "CpTaxonomy",
    "CpPolicy",
    "CpFinding",
    "CpItem",
    "CpReport",
    "load_cp_taxonomy",
    "default_cp_policy",
    "resolve_cp_policy",
    "build_cp_report",
    "validate_conditions_precedent",
]
