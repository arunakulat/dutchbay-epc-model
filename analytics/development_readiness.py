"""Development-readiness / E&S status register — lender financial-close tracker (review C11).

Before a DFI/lender reaches financial close it tracks the project's **development readiness**
across a set of workstreams — land, permits, environmental & social (ESIA / IFC Performance
Standards), grid connection, the PPA, the EPC contract, and financing — each on a
Red/Amber/Green maturity scale. This module is the config-first register for that tracker:
a scenario may declare a ``development_readiness`` block mapping each workstream to a status
record (``status``, optional ``note``), and this validates it and rolls the per-workstream
statuses up to one overall RAG (the WORST declared status — the conservative lender view).

It mirrors :mod:`analytics.evidence_register` (C5) deliberately:

- **Config-first** (CESSPIT / CCCDIR — never a Python literal). The taxonomy (the ordered
  RAG scale + the canonical workstreams) lives in ``config/development_readiness.yaml``; the
  enforcement policy resolves ``scenario development_readiness.{enforce,require_complete}`` →
  ``config/defaults.yaml`` ``defaults.development_readiness.*``.
- **Runs at AUTHORED-scenario LOAD time** (``analytics.scenario_loader``), NOT on derived runs.
- **Pure detector**: raises / warns / no-ops; it changes no computed number (byte-identical
  economics), and the report layer surfaces the rollup read-only.

**Soft by default** (``enforce: false``, ``require_complete: false``) — a scenario with no /
partial register is *reported on*, never broken. A lender-grade scenario opts into hard
enforcement (e.g. ``require_complete: true`` to demand a status for every workstream).

The analysis is split (CCCDIR): :func:`build_readiness_report` is a *pure, tolerant* builder
(used by the report pack too); :func:`validate_development_readiness` applies the policy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"
_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "development_readiness.yaml"
)


class DevelopmentReadinessError(ValueError):
    """Raised when a scenario's development-readiness register is not lender-grade."""


@dataclass(frozen=True)
class ReadinessTaxonomy:
    """The config-sourced taxonomy: the ordered RAG scale + canonical workstreams.

    ``statuses`` is ordered BEST → WORST; ``status_rank`` maps a status to its index so the
    overall rollup is ``max(rank)`` (the worst declared status).
    """

    statuses: Tuple[str, ...]
    workstreams: Tuple[str, ...]

    @property
    def status_rank(self) -> Mapping[str, int]:
        return {name: i for i, name in enumerate(self.statuses)}

    def worst(self, statuses: List[str]) -> Optional[str]:
        """Return the worst (highest-rank) status, or None for an empty list."""
        if not statuses:
            return None
        return max(statuses, key=lambda s: self.status_rank[s])


@dataclass(frozen=True)
class ReadinessPolicy:
    """Resolved development-readiness enforcement policy for a scenario.

    Attributes:
        enforce: Treat findings as errors (raise) rather than warnings. Default False (soft).
        require_complete: Every canonical workstream must have a declared status; a missing
            workstream becomes a finding.
    """

    enforce: bool
    require_complete: bool


@dataclass(frozen=True)
class ReadinessFinding:
    """One issue found in a scenario's development-readiness register."""

    kind: str  # unknown_workstream | unknown_status | missing_field | incomplete
    workstream: str
    detail: str


@dataclass(frozen=True)
class ReadinessItem:
    """One rendered readiness line (workstream, status, note)."""

    workstream: str
    status: str
    note: str = ""


@dataclass(frozen=True)
class ReadinessReport:
    """Structured development-readiness coverage of a scenario (pure, policy-free)."""

    items: Tuple[ReadinessItem, ...]
    overall_status: Optional[str]
    counts: Mapping[str, int]
    covered: Tuple[str, ...]
    missing: Tuple[str, ...]
    findings: Tuple[ReadinessFinding, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.findings


@lru_cache(maxsize=1)
def load_readiness_taxonomy() -> ReadinessTaxonomy:
    """The single config-sourced readiness taxonomy (``config/development_readiness.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_TAXONOMY_PATH.read_text())
    try:
        statuses = tuple(str(s) for s in data["rag_statuses"])
        workstreams = tuple(str(w) for w in data["workstreams"])
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/development_readiness.yaml must define a non-empty 'rag_statuses' "
            f"list (best→worst) and a 'workstreams' list ({_TAXONOMY_PATH})"
        ) from exc
    if not statuses or not workstreams:
        raise ValueError(
            "config/development_readiness.yaml 'rag_statuses' and 'workstreams' must both "
            f"be non-empty ({_TAXONOMY_PATH})"
        )
    return ReadinessTaxonomy(statuses=statuses, workstreams=workstreams)


@lru_cache(maxsize=1)
def default_readiness_policy() -> ReadinessPolicy:
    """The single config-sourced enforcement policy (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["development_readiness"]
        return ReadinessPolicy(
            enforce=bool(block["enforce"]),
            require_complete=bool(block["require_complete"]),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.development_readiness "
            f"{{enforce, require_complete}} ({_DEFAULTS_PATH})"
        ) from exc


def _resolve_bool(block: Mapping[str, Any], key: str, fallback: bool) -> bool:
    if key not in block:
        return fallback
    value = block[key]
    if not isinstance(value, bool):
        raise ValueError(
            f"development_readiness.{key} must be a boolean; got {value!r}"
        )
    return value


def resolve_readiness_policy(config: Mapping[str, Any]) -> ReadinessPolicy:
    """Resolve the readiness policy for a scenario (scenario keys override the defaults)."""
    default = default_readiness_policy()
    block = config.get("development_readiness")
    if not isinstance(block, Mapping):
        return default
    return ReadinessPolicy(
        enforce=_resolve_bool(block, "enforce", default.enforce),
        require_complete=_resolve_bool(
            block, "require_complete", default.require_complete
        ),
    )


def _items(config: Mapping[str, Any]) -> List[Tuple[str, Mapping[str, Any]]]:
    """Extract ``development_readiness.items`` as a list of (workstream, record) pairs.

    Accepts a mapping (workstream -> record) or a list of records each carrying a
    ``workstream`` key. Returns [] when no block / no items are declared.
    """
    block = config.get("development_readiness")
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
            if not isinstance(rec, Mapping) or "workstream" not in rec:
                raise DevelopmentReadinessError(
                    "development_readiness.items list entries must be mappings with a "
                    f"'workstream' key; got {rec!r}"
                )
            out.append((str(rec["workstream"]), rec))
        return out
    raise DevelopmentReadinessError(
        "development_readiness.items must be a mapping or a list of {workstream, ...} "
        f"records; got {type(items).__name__}"
    )


def build_readiness_report(config: Mapping[str, Any]) -> ReadinessReport:
    """Build a tolerant, policy-free development-readiness report for a scenario.

    Records findings (unknown workstream / unknown status / missing status / incomplete
    coverage) but never raises on *content* — only on a structurally malformed ``items``
    container. Rolls the valid per-workstream statuses up to one overall RAG (the worst
    declared status). The policy decision (raise / warn / no-op) is
    :func:`validate_development_readiness`'s job.
    """
    taxonomy = load_readiness_taxonomy()
    policy = resolve_readiness_policy(config)
    pairs = _items(config)
    findings: List[ReadinessFinding] = []
    rendered: List[ReadinessItem] = []
    valid_statuses: List[str] = []

    for name, rec in pairs:
        if not isinstance(rec, Mapping):
            findings.append(
                ReadinessFinding("missing_field", name, "entry is not a mapping")
            )
            continue
        if name not in taxonomy.workstreams:
            findings.append(
                ReadinessFinding(
                    "unknown_workstream",
                    name,
                    f"not a canonical workstream ({', '.join(taxonomy.workstreams)})",
                )
            )
        status = rec.get("status")
        if status is None or status == "":
            findings.append(
                ReadinessFinding("missing_field", name, "missing required 'status'")
            )
            continue
        status = str(status)
        if status not in taxonomy.status_rank:
            findings.append(
                ReadinessFinding(
                    "unknown_status",
                    name,
                    f"status {status!r} is not in the RAG scale ({', '.join(taxonomy.statuses)})",
                )
            )
            continue
        valid_statuses.append(status)
        rendered.append(
            ReadinessItem(workstream=name, status=status, note=str(rec.get("note", "")))
        )

    declared = {name for name, _ in pairs}
    missing = tuple(w for w in taxonomy.workstreams if w not in declared)
    if policy.require_complete:
        for w in missing:
            findings.append(
                ReadinessFinding(
                    "incomplete", w, "workstream has no declared readiness status"
                )
            )

    counts = {s: valid_statuses.count(s) for s in taxonomy.statuses}
    covered = tuple(w for w in taxonomy.workstreams if w in declared)
    return ReadinessReport(
        items=tuple(rendered),
        overall_status=taxonomy.worst(valid_statuses),
        counts=counts,
        covered=covered,
        missing=missing,
        findings=tuple(findings),
    )


def validate_development_readiness(
    config: dict[str, Any], config_path: str | None = None
) -> ReadinessReport:
    """Validate a scenario's development-readiness register against the resolved policy.

    Builds the report and applies the policy: when ``enforce`` is set, any finding raises
    :class:`DevelopmentReadinessError`; otherwise findings are logged as warnings (soft —
    the default). Always returns the report (so the report pack can consume the rollup).
    No-op (clean report, no log) when the scenario declares no register and completeness is
    not required. Changes no computed number.
    """
    policy = resolve_readiness_policy(config)
    where = f" in '{config_path}'" if config_path else ""
    report = build_readiness_report(config)

    if report.is_clean:
        if report.items:
            logger.debug(
                "Development readiness%s: overall=%s (%d workstreams declared).",
                where,
                report.overall_status,
                len(report.covered),
            )
        return report

    summary = "; ".join(
        f"[{f.kind}] {f.workstream}: {f.detail}" for f in report.findings
    )
    if policy.enforce:
        raise DevelopmentReadinessError(
            f"Development-readiness register is not lender-grade{where}: {summary}"
        )
    logger.warning(
        "Development-readiness findings%s (soft; enforce=false): %s", where, summary
    )
    return report


# Declare development_readiness in the central config schema (CCCDIR) so it appears in the
# lender schema export (build_schema_dataframe). It is OPTIONAL and WARNING-only — the field
# is enforced (softly) by validate_development_readiness, not by the required-field guard, so
# a scenario without it is never blocked.
_READINESS_SCHEMA_SPECS = [
    RequiredFieldSpec(
        module="development_readiness",
        name="development_readiness",
        paths=[("development_readiness", "items")],
        required=False,
        severity="warning",
        description=(
            "Development-readiness / E&S R/A/G register (workstream -> status). Optional; "
            "validated softly by analytics.development_readiness.validate_development_readiness."
        ),
    ),
]
register_required_fields("development_readiness", _READINESS_SCHEMA_SPECS)


__all__ = [
    "DevelopmentReadinessError",
    "ReadinessTaxonomy",
    "ReadinessPolicy",
    "ReadinessFinding",
    "ReadinessItem",
    "ReadinessReport",
    "load_readiness_taxonomy",
    "default_readiness_policy",
    "resolve_readiness_policy",
    "build_readiness_report",
    "validate_development_readiness",
]
