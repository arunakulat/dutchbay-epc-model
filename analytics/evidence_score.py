"""Bankability evidence-completeness score — analytics/evidence_score.py (issue #616).

The evidence REGISTER (:mod:`analytics.evidence_register`) validates a scenario's assumption
provenance and builds COVERAGE (covered vs missing material assumptions) — but computes no
score. This module adds the scoring layer on top: a single numeric **bankability
evidence-completeness score** in [0, 100] plus a plain band label, derived purely from the
register coverage and the per-tier evidence strength.

The score answers a lender question the raw coverage does not: *how strong is the evidence
base overall?* Two scenarios can both "cover" all material assumptions yet be worlds apart if
one cites metered data and executed contracts while the other cites un-sourced placeholders.
The score weights each covered assumption by its evidence tier's strength and treats a
missing (or ungradeable) assumption as the missing-evidence floor.

Config-first (CESSPIT / CCCDIR — never a Python literal):

- The tier strength weights, the missing-evidence floor, and the score→label bands live in
  ``config/evidence_score.yaml``; the material-assumption set and the tier hierarchy stay in
  ``config/evidence_register.yaml`` (single source — this module reads the register taxonomy,
  it does not redefine it). :func:`load_evidence_score_weights` **fails loud** if the two
  configs drift (a register tier with no weight, or a weight for a non-tier).
- **Pure read-only derivation**: it calls :func:`analytics.evidence_register.build_evidence_report`
  and scores its coverage. It recomputes no finance metric and moves no KPI (byte-identical
  economics); the report layer surfaces the score read-only.

**Soft by default** — a scenario with no register scores 0.0 / "insufficiently evidenced" and
is reported on, never broken (mirrors the register's soft default). This is a completeness
*measure*, not a gate: nothing here raises on a low score.

This is slice 4 of 5 of the feasibility-report generator (issue #616): the bankability
evidence-completeness score. It builds on :mod:`analytics.evidence_register` (coverage +
tier strength).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Tuple

from analytics.evidence_register import build_evidence_report, load_taxonomy

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "config" / "evidence_score.yaml"

#: The three evidence fields the register requires for a gradeable entry (source/as_of/tier);
#: the score only credits an entry whose ``tier`` is present AND a known taxonomy tier.


@dataclass(frozen=True)
class ScoreBand:
    """One score→label band: the inclusive lower bound on the 0-100 score and its label."""

    min: float
    label: str


@dataclass(frozen=True)
class EvidenceScoreWeights:
    """The config-sourced scoring weights: per-tier strength + missing floor + bands.

    ``tier_weights`` maps every evidence tier (from the register taxonomy) to a strength in
    [0, 1]. ``missing_weight`` is the strength credited to a material assumption with no
    gradeable evidence. ``bands`` is ordered BEST → WORST by ``min``; :meth:`band_for`
    returns the label of the first band the score meets or exceeds.
    """

    tier_weights: Mapping[str, float]
    missing_weight: float
    bands: Tuple[ScoreBand, ...]

    def band_for(self, score: float) -> str:
        """The band label for a 0-100 score (first band whose ``min`` the score meets)."""
        for band in self.bands:
            if score >= band.min:
                return band.label
        # bands are validated to include a min=0 floor, so this is unreachable.
        return self.bands[-1].label if self.bands else ""


@dataclass(frozen=True)
class AssumptionScore:
    """One material assumption's contribution to the score (its tier + strength)."""

    assumption: str
    tier: str  # the declared tier, or "" when missing / ungradeable
    strength: float  # the credited strength in [0, 1]
    covered: bool  # True when a gradeable evidence entry was found


@dataclass(frozen=True)
class EvidenceScore:
    """The bankability evidence-completeness score for a scenario (pure, read-only).

    ``score`` is in [0, 100]: the mean credited strength across ALL canonical material
    assumptions, scaled to 100. ``band`` is its plain label. ``n_total`` is the canonical
    assumption count; ``n_covered`` those with a gradeable entry; ``n_missing`` the rest
    (the missing-evidence gap). ``mean_covered_strength`` is the average tier strength over
    the covered entries only (0.0 when none) — it separates "how much is evidenced" (coverage)
    from "how strong the evidence is" (tier strength). ``weakest`` lists the covered entries
    at or below the weakest configured tier weight, so the report can point at the soft spots.
    """

    score: float
    band: str
    n_total: int
    n_covered: int
    n_missing: int
    mean_covered_strength: float
    assumptions: Tuple[AssumptionScore, ...]
    missing: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def coverage_fraction(self) -> float:
        """Fraction of canonical material assumptions with a gradeable entry (0..1)."""
        return self.n_covered / self.n_total if self.n_total else 0.0


@lru_cache(maxsize=1)
def load_evidence_score_weights() -> EvidenceScoreWeights:
    """The single config-sourced scoring weights (``config/evidence_score.yaml``).

    Fails loud (CESSPIT) if the weights drift from the register taxonomy: EVERY tier in
    ``config/evidence_register.yaml`` ``evidence_tiers`` must have a weight here, and every
    weighted key must be a real tier — so the two configs cannot silently disagree.
    """
    import yaml  # project core dep

    data = yaml.safe_load(_WEIGHTS_PATH.read_text())
    try:
        raw_weights = data["tier_weights"]
        missing_weight = data["missing_weight"]
        raw_bands = data["bands"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "config/evidence_score.yaml must define 'tier_weights' (tier -> weight), "
            f"'missing_weight', and a 'bands' list ({_WEIGHTS_PATH})"
        ) from exc
    if not isinstance(raw_weights, Mapping) or not raw_weights or not raw_bands:
        raise ValueError(
            "config/evidence_score.yaml 'tier_weights' and 'bands' must be non-empty "
            f"({_WEIGHTS_PATH})"
        )

    try:
        tier_weights = {str(k): float(v) for k, v in raw_weights.items()}
        missing_weight_f = float(missing_weight)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "config/evidence_score.yaml tier_weights values and missing_weight must be "
            f"numbers ({_WEIGHTS_PATH})"
        ) from exc
    for name, weight in tier_weights.items():
        if not math.isfinite(weight) or not 0.0 <= weight <= 1.0:
            raise ValueError(
                f"config/evidence_score.yaml tier_weight {name!r}={weight} must be a finite "
                f"number in [0, 1] ({_WEIGHTS_PATH})"
            )
    if not math.isfinite(missing_weight_f) or not 0.0 <= missing_weight_f <= 1.0:
        raise ValueError(
            f"config/evidence_score.yaml missing_weight={missing_weight_f} must be a finite "
            f"number in [0, 1] ({_WEIGHTS_PATH})"
        )

    # CESSPIT cross-check: the weighted tiers must exactly match the register taxonomy.
    taxonomy_tiers = set(load_taxonomy().tiers)
    weighted_tiers = set(tier_weights)
    if weighted_tiers != taxonomy_tiers:
        missing_from_weights = taxonomy_tiers - weighted_tiers
        extra_in_weights = weighted_tiers - taxonomy_tiers
        parts = []
        if missing_from_weights:
            parts.append(
                f"register tiers with no weight: {', '.join(sorted(missing_from_weights))}"
            )
        if extra_in_weights:
            parts.append(
                f"weights for non-tiers: {', '.join(sorted(extra_in_weights))}"
            )
        raise ValueError(
            "config/evidence_score.yaml tier_weights must exactly match "
            f"config/evidence_register.yaml evidence_tiers ({'; '.join(parts)})"
        )

    bands = []
    seen_mins: set[float] = set()
    for rec in raw_bands:
        if not isinstance(rec, Mapping) or "min" not in rec or "label" not in rec:
            raise ValueError(
                "config/evidence_score.yaml bands entries must be mappings with 'min' and "
                f"'label' keys; got {rec!r}"
            )
        try:
            band_min = float(rec["min"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"config/evidence_score.yaml band min {rec['min']!r} must be a number "
                f"({_WEIGHTS_PATH})"
            ) from exc
        # A non-finite min silently never matches; an out-of-range min is a permanently
        # unreachable label; a duplicate min makes the second label dead. Reject all three
        # so a future retune fails loud instead of shipping a dead band (CESSPIT).
        if not math.isfinite(band_min) or not 0.0 <= band_min <= 100.0:
            raise ValueError(
                f"config/evidence_score.yaml band min={band_min} must be a finite number "
                f"in [0, 100] ({_WEIGHTS_PATH})"
            )
        if band_min in seen_mins:
            raise ValueError(
                f"config/evidence_score.yaml has a duplicate band min={band_min} — the "
                f"second label would be unreachable ({_WEIGHTS_PATH})"
            )
        seen_mins.add(band_min)
        bands.append(ScoreBand(min=band_min, label=str(rec["label"])))
    bands.sort(key=lambda b: b.min, reverse=True)  # BEST -> WORST
    if bands[-1].min != 0.0:
        raise ValueError(
            "config/evidence_score.yaml bands must include a min=0 floor so every score "
            f"maps to a label ({_WEIGHTS_PATH})"
        )

    return EvidenceScoreWeights(
        tier_weights=tier_weights,
        missing_weight=missing_weight_f,
        bands=tuple(bands),
    )


#: Register finding kinds that DISQUALIFY a canonical assumption from earning evidence credit.
#: An entry the register flagged for a missing required field (source/as_of/tier), an
#: unknown/ungradeable tier, or a tier weaker than the scenario's own declared min_tier is
#: NOT lender-grade evidence, so the score credits it the missing floor — never its tier
#: weight. The register (analytics.evidence_register) is the single source of what counts as
#: well-formed evidence (CCCDIR); the score does not re-derive well-formedness.
_DISQUALIFYING_FINDING_KINDS = frozenset(
    {"missing_field", "unknown_tier", "below_min_tier"}
)


def build_evidence_score(config: Mapping[str, Any]) -> EvidenceScore:
    """Compute the bankability evidence-completeness score for a scenario (pure, read-only).

    Builds the register coverage via :func:`analytics.evidence_register.build_evidence_report`,
    then scores it. A canonical material assumption earns its tier's strength weight ONLY when
    the register deems its entry well-formed — i.e. it has a known tier AND the register
    recorded no disqualifying finding against it (no missing source/as_of/tier, no unknown
    tier, and not below the scenario's own declared ``min_tier``). Any other assumption —
    absent, un-sourced, ungradeable, or below the scenario's evidence bar — earns the
    missing-evidence floor. The overall score is the mean credited strength across ALL
    canonical assumptions, scaled to 100, so missing coverage, weak tiers, and un-sourced or
    below-bar entries all pull it down. Recomputes no finance metric.

    Crediting is gated on the register's OWN findings (CCCDIR single source): a scenario
    declaring ``{tier: measured}`` with no ``source``/``as_of`` is flagged ``missing_field``
    by the register and therefore earns the floor here — it does NOT read as bankable. This is
    the load-bearing faithfulness property: the score cannot overstate a zero-provenance
    evidence base.
    """
    weights = load_evidence_score_weights()
    report = build_evidence_report(config)
    taxonomy = load_taxonomy()
    entries = report.entries
    disqualified = {
        f.assumption for f in report.findings if f.kind in _DISQUALIFYING_FINDING_KINDS
    }

    per_assumption: list[AssumptionScore] = []
    covered_strengths: list[float] = []
    for name in taxonomy.assumptions:
        rec = entries.get(name)
        tier = ""
        # Creditable only when the entry has a known tier AND the register raised no
        # disqualifying finding against it (missing source/as_of/tier, unknown tier, or
        # below the scenario's min_tier). Otherwise it earns the missing floor.
        if isinstance(rec, Mapping) and name not in disqualified:
            raw_tier = rec.get("tier")
            if raw_tier is not None and str(raw_tier) in weights.tier_weights:
                tier = str(raw_tier)
        if tier:
            strength = weights.tier_weights[tier]
            covered_strengths.append(strength)
            per_assumption.append(
                AssumptionScore(
                    assumption=name, tier=tier, strength=strength, covered=True
                )
            )
        else:
            per_assumption.append(
                AssumptionScore(
                    assumption=name,
                    tier="",
                    strength=weights.missing_weight,
                    covered=False,
                )
            )

    n_total = len(taxonomy.assumptions)
    total_strength = sum(a.strength for a in per_assumption)
    score = round(100.0 * total_strength / n_total if n_total else 0.0, 2)
    n_covered = sum(1 for a in per_assumption if a.covered)
    mean_covered = (
        sum(covered_strengths) / len(covered_strengths) if covered_strengths else 0.0
    )
    missing = tuple(a.assumption for a in per_assumption if not a.covered)

    return EvidenceScore(
        score=score,
        # Band from the ROUNDED score so the label always matches the displayed number.
        band=weights.band_for(score),
        n_total=n_total,
        n_covered=n_covered,
        n_missing=n_total - n_covered,
        mean_covered_strength=round(mean_covered, 4),
        assumptions=tuple(per_assumption),
        missing=missing,
    )


__all__ = [
    "ScoreBand",
    "EvidenceScoreWeights",
    "AssumptionScore",
    "EvidenceScore",
    "load_evidence_score_weights",
    "build_evidence_score",
]
