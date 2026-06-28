"""Assumption evidence register — lender/DFI assumption-provenance control (review C5).

A DFI/lender financial model is only as credible as the *evidence* behind its material
assumptions. The information memorandum / lender's-engineer review asks, for every number
that moves the economics (tariff, capex, opex, capacity factor, FX, debt terms,
degradation): *where did this come from, as of when, and how strong is that source?*
The model already enforces source provenance for ONE assumption — the AEP power curve
(:mod:`analytics.aep_provenance`). This module generalizes that idea into an
**assumption-level evidence register**: a scenario may declare an ``evidence_register``
block mapping each material assumption to a provenance record (``source``, ``as_of``,
``tier``), and this validates the register's completeness and evidence strength.

It mirrors :mod:`analytics.aep_provenance` deliberately:

- **Config-first policy** (CESSPIT / CCCDIR — never a Python literal). The *taxonomy*
  (the ordered evidence tiers + the canonical list of material assumptions) lives in one
  place, ``config/evidence_register.yaml``; the *enforcement policy* resolves::

      scenario ``evidence_register.{enforce,require_complete,min_tier}``  →  else
      ``config/defaults.yaml`` ``defaults.evidence_register.*``

- **Runs at AUTHORED-scenario LOAD time** (``analytics.scenario_loader``) and on authored
  configs **at the API boundary** (``api.pipeline_api`` / ``app.services``), NOT on every
  derived run — so deliberate sensitivity / Monte-Carlo perturbations are unaffected.

- **Pure detector**: it raises or it is a no-op (or warns); it changes no computed number,
  so it preserves byte-identical economics.

**Soft by default** (the deliberate difference from ``aep_provenance``): the house policy
is ``enforce: false`` (warn, don't reject) and ``require_complete: false`` — so a scenario
that declares no ``evidence_register`` block, or a partial one, is *reported on*, not
broken. A lender-grade scenario opts in to hard enforcement (``enforce: true``,
``require_complete: true``, ``min_tier: benchmark``) to make an incomplete or weakly-
evidenced assumption set a hard failure.

The analysis is split (CCCDIR — single-purpose contracts): :func:`build_evidence_report`
is a *pure, tolerant* builder that returns a structured coverage report (used by the
report pack too); :func:`validate_evidence_register` applies the *policy* (raise / warn /
no-op) to that report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).resolve().parents[1] / "config" / "defaults.yaml"
_REGISTER_PATH = Path(__file__).resolve().parents[1] / "config" / "evidence_register.yaml"

#: Provenance fields every evidence entry must carry to be well-formed.
_REQUIRED_FIELDS: Tuple[str, ...] = ("source", "as_of", "tier")


class EvidenceRegisterError(ValueError):
    """Raised when a scenario's assumption evidence register is not lender-grade."""


@dataclass(frozen=True)
class EvidenceTaxonomy:
    """The config-sourced taxonomy: ordered evidence tiers + canonical material assumptions.

    ``tiers`` is ordered STRONGEST → WEAKEST; ``tier_rank`` maps a tier name to its index
    (lower = stronger) so ``min_tier`` comparisons are a simple integer test.
    """

    tiers: Tuple[str, ...]
    assumptions: Tuple[str, ...]

    @property
    def tier_rank(self) -> Mapping[str, int]:
        return {name: i for i, name in enumerate(self.tiers)}

    def is_weaker(self, tier: str, than: str) -> bool:
        """True if ``tier`` is weaker (later in the order) than ``than``."""
        return self.tier_rank[tier] > self.tier_rank[than]


@dataclass(frozen=True)
class EvidencePolicy:
    """Resolved evidence-register enforcement policy for a scenario.

    Attributes:
        enforce: Treat findings as errors (raise) rather than warnings. Default False
            (soft) — the register is reported on but never blocks a run.
        require_complete: Every canonical material assumption must have a register entry;
            a missing assumption becomes a finding.
        min_tier: If set, an entry whose tier is WEAKER than this (e.g. ``placeholder``
            when ``min_tier: benchmark``) becomes a finding. None disables the check.
    """

    enforce: bool
    require_complete: bool
    min_tier: Optional[str]


@dataclass(frozen=True)
class EvidenceFinding:
    """One issue found in a scenario's evidence register."""

    kind: str  # unknown_assumption | unknown_tier | missing_field | below_min_tier | incomplete
    assumption: str
    detail: str


@dataclass(frozen=True)
class EvidenceReport:
    """Structured coverage of a scenario's assumption evidence (pure, policy-free)."""

    entries: Mapping[str, Mapping[str, Any]]  # assumption -> {source, as_of, tier, note?}
    covered: Tuple[str, ...]
    missing: Tuple[str, ...]
    findings: Tuple[EvidenceFinding, ...] = field(default_factory=tuple)

    @property
    def is_clean(self) -> bool:
        return not self.findings


@lru_cache(maxsize=1)
def load_taxonomy() -> EvidenceTaxonomy:
    """The single config-sourced evidence taxonomy (``config/evidence_register.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_REGISTER_PATH.read_text())
    try:
        tiers = tuple(str(t) for t in data["evidence_tiers"])
        assumptions = tuple(str(a) for a in data["material_assumptions"])
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/evidence_register.yaml must define a non-empty 'evidence_tiers' "
            f"list (strongest→weakest) and a 'material_assumptions' list ({_REGISTER_PATH})"
        ) from exc
    if not tiers or not assumptions:
        raise ValueError(
            "config/evidence_register.yaml 'evidence_tiers' and 'material_assumptions' "
            f"must both be non-empty ({_REGISTER_PATH})"
        )
    return EvidenceTaxonomy(tiers=tiers, assumptions=assumptions)


@lru_cache(maxsize=1)
def default_evidence_policy() -> EvidencePolicy:
    """The single config-sourced enforcement policy (``config/defaults.yaml``)."""
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    try:
        block = data["defaults"]["evidence_register"]
        min_tier = block["min_tier"]
        return EvidencePolicy(
            enforce=bool(block["enforce"]),
            require_complete=bool(block["require_complete"]),
            min_tier=None if min_tier in (None, "", "none") else str(min_tier),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/defaults.yaml missing defaults.evidence_register "
            "{enforce, require_complete, min_tier} "
            f"({_DEFAULTS_PATH})"
        ) from exc


def _resolve_bool(block: Mapping[str, Any], key: str, fallback: bool) -> bool:
    if key not in block:
        return fallback
    value = block[key]
    if not isinstance(value, bool):
        raise ValueError(f"evidence_register.{key} must be a boolean; got {value!r}")
    return value


def resolve_evidence_policy(config: Mapping[str, Any]) -> EvidencePolicy:
    """Resolve the evidence policy for a scenario (scenario keys override the defaults)."""
    default = default_evidence_policy()
    block = config.get("evidence_register")
    if not isinstance(block, Mapping):
        return default
    if "min_tier" in block:
        raw = block["min_tier"]
        min_tier = None if raw in (None, "", "none") else str(raw)
    else:
        min_tier = default.min_tier
    if min_tier is not None and min_tier not in load_taxonomy().tier_rank:
        raise ValueError(
            f"evidence_register.min_tier={min_tier!r} is not a known evidence tier "
            f"({', '.join(load_taxonomy().tiers)})"
        )
    return EvidencePolicy(
        enforce=_resolve_bool(block, "enforce", default.enforce),
        require_complete=_resolve_bool(block, "require_complete", default.require_complete),
        min_tier=min_tier,
    )


def _entries(config: Mapping[str, Any]) -> Mapping[str, Mapping[str, Any]]:
    """Extract ``evidence_register.entries`` as an assumption→record mapping.

    Accepts either a mapping (assumption -> record) or a list of records each carrying an
    ``assumption`` key. Returns {} when no block / no entries are declared.
    """
    block = config.get("evidence_register")
    if not isinstance(block, Mapping):
        return {}
    entries = block.get("entries")
    if entries is None:
        return {}
    if isinstance(entries, Mapping):
        return {str(k): v for k, v in entries.items()}
    if isinstance(entries, (list, tuple)):
        out: dict[str, Mapping[str, Any]] = {}
        for rec in entries:
            if not isinstance(rec, Mapping) or "assumption" not in rec:
                raise EvidenceRegisterError(
                    "evidence_register.entries list items must be mappings with an "
                    f"'assumption' key; got {rec!r}"
                )
            out[str(rec["assumption"])] = rec
        return out
    raise EvidenceRegisterError(
        "evidence_register.entries must be a mapping or a list of {assumption, ...} "
        f"records; got {type(entries).__name__}"
    )


def build_evidence_report(config: Mapping[str, Any]) -> EvidenceReport:
    """Build a tolerant, policy-free coverage report of a scenario's evidence register.

    Records findings (unknown assumption / unknown tier / missing field / weak tier /
    incomplete coverage) but never raises on *content* — only on a structurally malformed
    ``entries`` container (which is broken config, not a lender-policy matter). The policy
    decision (raise vs warn vs no-op) is :func:`validate_evidence_register`'s job.
    """
    taxonomy = load_taxonomy()
    policy = resolve_evidence_policy(config)
    entries = _entries(config)
    findings: List[EvidenceFinding] = []

    for name, rec in entries.items():
        if not isinstance(rec, Mapping):
            findings.append(EvidenceFinding("missing_field", name, "entry is not a mapping"))
            continue
        if name not in taxonomy.assumptions:
            findings.append(
                EvidenceFinding(
                    "unknown_assumption", name,
                    f"not a canonical material assumption ({', '.join(taxonomy.assumptions)})",
                )
            )
        missing = [f for f in _REQUIRED_FIELDS if not rec.get(f)]
        if missing:
            findings.append(
                EvidenceFinding("missing_field", name, f"missing required field(s): {', '.join(missing)}")
            )
        tier = rec.get("tier")
        if tier is not None and tier != "":
            if str(tier) not in taxonomy.tier_rank:
                findings.append(
                    EvidenceFinding(
                        "unknown_tier", name,
                        f"tier {tier!r} is not in the taxonomy ({', '.join(taxonomy.tiers)})",
                    )
                )
            elif policy.min_tier is not None and taxonomy.is_weaker(str(tier), policy.min_tier):
                findings.append(
                    EvidenceFinding(
                        "below_min_tier", name,
                        f"tier {tier!r} is weaker than required min_tier {policy.min_tier!r}",
                    )
                )

    covered = tuple(a for a in taxonomy.assumptions if a in entries)
    missing_required = tuple(a for a in taxonomy.assumptions if a not in entries)
    if policy.require_complete:
        for a in missing_required:
            findings.append(
                EvidenceFinding("incomplete", a, "material assumption has no evidence entry")
            )

    return EvidenceReport(
        entries=entries,
        covered=covered,
        missing=missing_required,
        findings=tuple(findings),
    )


def validate_evidence_register(
    config: dict[str, Any], config_path: str | None = None
) -> EvidenceReport:
    """Validate a scenario's assumption evidence register against the resolved policy.

    Builds the coverage report and applies the policy: when ``enforce`` is set, any finding
    raises :class:`EvidenceRegisterError`; otherwise findings are logged as warnings (soft —
    the default). Always returns the report (so callers / the report pack can consume the
    coverage). No-op (clean report, no log) when the scenario declares no register and
    completeness is not required. Changes no computed number.
    """
    policy = resolve_evidence_policy(config)
    where = f" in '{config_path}'" if config_path else ""
    report = build_evidence_report(config)

    if report.is_clean:
        if report.entries:
            logger.debug(
                "Evidence register OK%s: %d/%d material assumptions evidenced.",
                where, len(report.covered), len(report.covered) + len(report.missing),
            )
        return report

    summary = "; ".join(f"[{f.kind}] {f.assumption}: {f.detail}" for f in report.findings)
    if policy.enforce:
        raise EvidenceRegisterError(
            f"Assumption evidence register is not lender-grade{where}: {summary}"
        )
    logger.warning("Evidence-register findings%s (soft; enforce=false): %s", where, summary)
    return report


__all__ = [
    "EvidenceRegisterError",
    "EvidenceTaxonomy",
    "EvidencePolicy",
    "EvidenceFinding",
    "EvidenceReport",
    "load_taxonomy",
    "default_evidence_policy",
    "resolve_evidence_policy",
    "build_evidence_report",
    "validate_evidence_register",
]
