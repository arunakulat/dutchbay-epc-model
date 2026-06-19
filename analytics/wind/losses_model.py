"""AEP losses model (#23) — explicit gross → net loss stack.

Applies the ``resource.losses`` stack multiplicatively to a gross AEP to produce
net AEP, the net capacity factor, and a per-component breakdown for lender KPI
outputs. All loss percentages come from config (GWTF ARCH-01) — nothing is
hardcoded here.

Loss conventions (matching the scenario ``resource.losses`` block):
    - ``wake_loss_pct``, ``electrical_loss_pct``, ``curtailment_pct``,
      ``other_pct`` are **energy reductions** (retention = 1 - pct/100).
    - ``availability_pct`` is an **uptime** (retention = pct/100).

For the DutchBay canonical stack (wake 5, availability 97, electrical 2,
curtailment 2, other 1) the net factor is 0.87616 → net 402.6 GWh from gross
459.5 GWh (≈ 12.4% total loss), reproducing the canonical AEP summary.

Context:
    Sprint 10 - Issue #23 (Implement AEP losses model).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping

HOURS_PER_YEAR = 8760.0

#: Loss components expressed as a percentage *reduction* of energy.
REDUCTION_LOSS_KEYS = (
    "wake_loss_pct",
    "electrical_loss_pct",
    "curtailment_pct",
    "other_pct",
)
#: Availability is expressed as an *uptime* percentage, not a loss percentage.
AVAILABILITY_KEY = "availability_pct"


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


def _component_retentions(losses: Mapping[str, Any]) -> Dict[str, float]:
    """Build the per-component retention factors present in ``losses``."""
    retentions: Dict[str, float] = {}
    for key in REDUCTION_LOSS_KEYS:
        if losses.get(key) is not None:
            retentions[key] = _retention_from_pct(losses[key], is_availability=False)
    if losses.get(AVAILABILITY_KEY) is not None:
        retentions[AVAILABILITY_KEY] = _retention_from_pct(
            losses[AVAILABILITY_KEY], is_availability=True
        )
    return retentions


def compute_net_factor(losses: Mapping[str, Any]) -> float:
    """Return the multiplicative net retention factor for a losses mapping."""
    factor = 1.0
    for retention in _component_retentions(losses).values():
        factor *= retention
    return factor


def apply_losses(gross_aep_gwh: float, losses: Mapping[str, Any]) -> LossResult:
    """Apply the loss stack to a gross AEP.

    Args:
        gross_aep_gwh: Gross annual energy production (GWh), pre-loss.
        losses: A ``resource.losses`` mapping.

    Returns:
        A :class:`LossResult` with net AEP, the net factor, total loss %, and
        the per-component retention breakdown.

    Raises:
        ValueError: If ``gross_aep_gwh`` is negative or a percentage is invalid.
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
    "LossResult",
    "compute_net_factor",
    "apply_losses",
    "net_capacity_factor",
    "build_aep_losses_block",
]
