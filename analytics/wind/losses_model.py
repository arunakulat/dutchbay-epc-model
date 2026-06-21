"""AEP losses model (#23) — explicit gross → net loss stack.

Applies the ``resource.losses`` stack multiplicatively to a gross AEP to produce
net AEP, the net capacity factor, and a per-component breakdown for lender KPI
outputs. All loss percentages come from config (GWTF ARCH-01) — nothing is
hardcoded here.

Loss taxonomy (config-first, IEC 61400-15-2 aligned)
----------------------------------------------------
Each loss line is classified by a *taxonomy* mapping ``key -> kind``:

    - ``reduction`` → an energy reduction; retention = 1 - pct/100
    - ``uptime``    → an availability-style uptime; retention = pct/100

The taxonomy is resolved config-first from ``config/defaults.yaml``
``defaults.wind_resource.loss_taxonomy`` (falling back to
:data:`DEFAULT_LOSS_TAXONOMY`). This lets a scenario itemise finer IEC 61400-15-2
sub-losses (turbine performance, high-wind hysteresis, icing, transmission, …) and
have them ACTUALLY reduce net AEP.

Critically, any ``*_pct`` loss key that is NOT in the taxonomy now RAISES. The
previous implementation iterated a hardcoded four-key whitelist, so a finer loss a
scenario author added was *silently dropped* and never reduced AEP — a CASPER
silent-failure hazard. Result-shaped ``*_pct`` fields that legitimately ride along
in a losses block (e.g. ``total_loss_pct``) are listed in
:data:`_NON_LOSS_PCT_KEYS` and skipped rather than treated as unknown losses.

For the DutchBay canonical stack (wake 7.28, availability 97, electrical 2,
curtailment 2, other 1) the back-compat keys are all in the taxonomy, so the
retention product is unchanged and the canonical net AEP (≈473.8 GWh) reproduces
exactly.

Context:
    Sprint 10 - Issue #23 (Implement AEP losses model).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

HOURS_PER_YEAR = 8760.0

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.yaml"

#: Loss components expressed as a percentage *reduction* of energy.
#: Retained for backward-compatible imports; the live source of truth for which
#: keys are reductions vs uptimes is now the config-driven taxonomy
#: (see :func:`default_loss_taxonomy`).
REDUCTION_LOSS_KEYS = (
    "wake_loss_pct",
    "electrical_loss_pct",
    "curtailment_pct",
    "other_pct",
)
#: Availability is expressed as an *uptime* percentage, not a loss percentage.
AVAILABILITY_KEY = "availability_pct"

#: Built-in fallback loss taxonomy (IEC 61400-15-2 aligned), used only when
#: ``config/defaults.yaml`` does not define ``defaults.wind_resource.loss_taxonomy``.
#: ``reduction`` → retention 1 - pct/100; ``uptime`` → retention pct/100.
DEFAULT_LOSS_TAXONOMY: Dict[str, str] = {
    "wake_loss_pct": "reduction",
    "electrical_loss_pct": "reduction",
    "transmission_loss_pct": "reduction",
    "turbine_performance_pct": "reduction",
    "high_wind_hysteresis_pct": "reduction",
    "icing_pct": "reduction",
    "soiling_pct": "reduction",
    "blade_degradation_pct": "reduction",
    "environmental_pct": "reduction",
    "curtailment_pct": "reduction",
    "other_pct": "reduction",
    "availability_pct": "uptime",
    "grid_availability_pct": "uptime",
}

#: ``*_pct``-suffixed fields that are NOT loss inputs — results/metadata that may
#: legitimately ride along inside a ``losses`` mapping (e.g. the summary's own
#: ``total_loss_pct``). Skipped by the retention builder rather than rejected as an
#: unknown loss key.
_NON_LOSS_PCT_KEYS = frozenset({"total_loss_pct"})

#: Industry-typical default wind losses, used ONLY as an overridable fallback when a
#: scenario does not specify ``resource.losses``. These are generic (not project- or
#: DutchBay-specific) and a real assessment should override them with site values via
#: ``resource.losses``. Centralised here (single source) instead of scattered magic
#: numbers across the AEP/Monte-Carlo modules (ARCH-01 / DRY).
DEFAULT_WIND_LOSSES: Dict[str, float] = {
    "wake_loss_pct": 8.0,
    "availability_pct": 97.0,
    "electrical_loss_pct": 2.0,
}


@lru_cache(maxsize=1)
def default_loss_taxonomy() -> Dict[str, str]:
    """The config-sourced loss taxonomy (config/defaults.yaml), else the built-in.

    Mirrors :func:`analytics.cost.cost_basis.default_cost_basis_year` — config-first
    (CESSPIT / CCCDIR). Each value is normalised to ``reduction`` or ``uptime``;
    anything else is a config error and raises. If the config has no taxonomy block
    at all, the built-in :data:`DEFAULT_LOSS_TAXONOMY` is used.
    """
    import yaml  # project core dep

    try:
        data = yaml.safe_load(_DEFAULTS_PATH.read_text())
        tax = data["defaults"]["wind_resource"]["loss_taxonomy"]
    except (KeyError, TypeError):
        return dict(DEFAULT_LOSS_TAXONOMY)

    if not isinstance(tax, Mapping) or not tax:
        return dict(DEFAULT_LOSS_TAXONOMY)
    out: Dict[str, str] = {}
    for key, kind in tax.items():
        norm = str(kind).strip().lower()
        if norm not in ("reduction", "uptime"):
            raise ValueError(
                f"loss_taxonomy[{key!r}] must be 'reduction' or 'uptime', got {kind!r}"
            )
        out[str(key)] = norm
    return out


@dataclass(frozen=True)
class LossResult:
    """Result of applying the loss stack to a gross AEP."""

    gross_aep_gwh: float
    net_aep_gwh: float
    net_factor: float
    total_loss_pct: float
    components: Dict[str, float]  # per-component retention factor applied


def _retention_from_pct(value: Any, *, is_availability: bool) -> float:
    """Convert a config percentage to a multiplicative retention factor.

    Raises:
        ValueError: If the percentage is outside ``[0, 100]``.
    """
    pct = float(value)
    if not (0.0 <= pct <= 100.0):
        raise ValueError(f"Percentage must be in [0, 100], got {pct}")
    return pct / 100.0 if is_availability else 1.0 - pct / 100.0


def _component_retentions(
    losses: Mapping[str, Any],
    taxonomy: Optional[Mapping[str, str]] = None,
    *,
    exclude: Iterable[str] = (),
) -> Dict[str, float]:
    """Build the per-component retention factor for every loss line in ``losses``.

    Every ``*_pct`` key is classified via the taxonomy (config-first). A loss-shaped
    key that is not in the taxonomy RAISES — no silent drop. Result-shaped fields
    (:data:`_NON_LOSS_PCT_KEYS`), non-``_pct`` metadata, and ``exclude``d keys are
    skipped.
    """
    tax = taxonomy if taxonomy is not None else default_loss_taxonomy()
    excluded = set(exclude)
    retentions: Dict[str, float] = {}
    for key, value in losses.items():
        if value is None:
            continue
        if not key.endswith("_pct"):
            continue  # non-loss metadata
        if key in _NON_LOSS_PCT_KEYS or key in excluded:
            continue
        kind = tax.get(key)
        if kind is None:
            raise ValueError(
                f"Unknown loss key {key!r} is not in the loss taxonomy — refusing to "
                f"silently drop a loss. Register it in config/defaults.yaml "
                f"defaults.wind_resource.loss_taxonomy as 'reduction' or 'uptime'."
            )
        retentions[key] = _retention_from_pct(value, is_availability=(kind == "uptime"))
    return retentions


def compute_net_factor(
    losses: Mapping[str, Any],
    taxonomy: Optional[Mapping[str, str]] = None,
    *,
    exclude: Iterable[str] = (),
) -> float:
    """Return the multiplicative net retention factor for a losses mapping.

    ``exclude`` omits named keys (e.g. a wake term modelled separately upstream).
    """
    factor = 1.0
    for retention in _component_retentions(losses, taxonomy, exclude=exclude).values():
        factor *= retention
    return factor


def validate_loss_keys(
    losses: Mapping[str, Any],
    taxonomy: Optional[Mapping[str, str]] = None,
    *,
    exclude: Iterable[str] = (),
) -> None:
    """Raise ``ValueError`` if ``losses`` carries a loss-shaped key absent from the
    taxonomy. A cheap fail-loud guard for callers (e.g. the Monte-Carlo path) that
    apply losses by a bespoke route rather than through :func:`apply_losses`.
    """
    _component_retentions(losses, taxonomy, exclude=exclude)


def apply_losses(gross_aep_gwh: float, losses: Mapping[str, Any]) -> LossResult:
    """Apply the loss stack to a gross AEP.

    Args:
        gross_aep_gwh: Gross annual energy production (GWh), pre-loss.
        losses: A ``resource.losses`` mapping. Every ``*_pct`` loss key must be in
            the config-driven loss taxonomy (see module docstring).

    Returns:
        A :class:`LossResult` with net AEP, the net factor, total loss %, and
        the per-component retention breakdown.

    Raises:
        ValueError: If ``gross_aep_gwh`` is negative, a percentage is invalid, or a
            loss-shaped key is not in the taxonomy.
    """
    if gross_aep_gwh < 0.0:
        raise ValueError(f"gross_aep_gwh must be non-negative, got {gross_aep_gwh}")
    components = _component_retentions(losses)
    factor = 1.0
    for retention in components.values():
        factor *= retention
    net = gross_aep_gwh * factor
    return LossResult(
        gross_aep_gwh=gross_aep_gwh,
        net_aep_gwh=net,
        net_factor=factor,
        total_loss_pct=100.0 * (1.0 - factor),
        components=components,
    )


def net_capacity_factor(
    net_aep_gwh: float,
    capacity_mw: float,
    hours: float = HOURS_PER_YEAR,
) -> float:
    """Net capacity factor = net AEP / (installed capacity × hours).

    Args:
        net_aep_gwh: Net AEP (GWh).
        capacity_mw: Installed farm capacity (MW).
        hours: Hours in the period (default 8760).

    Raises:
        ValueError: If ``capacity_mw`` is not positive.
    """
    if capacity_mw <= 0.0:
        raise ValueError(f"capacity_mw must be positive, got {capacity_mw}")
    return (net_aep_gwh * 1000.0) / (capacity_mw * hours)


def build_aep_losses_block(
    gross_aep_gwh: float,
    losses: Mapping[str, Any],
    capacity_mw: float,
) -> Dict[str, Any]:
    """Build the losses + net-AEP block for lender KPI outputs / summary JSON."""
    result = apply_losses(gross_aep_gwh, losses)
    return {
        "gross_aep_gwh": round(result.gross_aep_gwh, 4),
        "net_aep_gwh": round(result.net_aep_gwh, 4),
        "net_capacity_factor": round(
            net_capacity_factor(result.net_aep_gwh, capacity_mw), 6
        ),
        "total_loss_pct": round(result.total_loss_pct, 4),
        "loss_components": {k: round(v, 6) for k, v in result.components.items()},
    }


__all__ = [
    "HOURS_PER_YEAR",
    "REDUCTION_LOSS_KEYS",
    "AVAILABILITY_KEY",
    "DEFAULT_LOSS_TAXONOMY",
    "DEFAULT_WIND_LOSSES",
    "LossResult",
    "default_loss_taxonomy",
    "compute_net_factor",
    "validate_loss_keys",
    "apply_losses",
    "net_capacity_factor",
    "build_aep_losses_block",
]
