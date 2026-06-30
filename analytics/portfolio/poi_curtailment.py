"""Shared point-of-interconnection (POI) curtailment for hybrid plants (ARCH-5, #476).

The deep-research audit flagged that a hybrid sharing one POI has a curtailment interaction
that was *asserted but not modelled*: when the combined instantaneous injection of several
technologies exceeds the shared export limit, the excess is physically curtailed and lost
(distinct from grid-instructed curtailment, which the CEB SPPA pays as deemed energy).

This module models that honestly, from per-technology **hourly** injection profiles — the
only physically correct basis, since combined output exceeds the limit only in specific
hours, not on annual averages. It is **opt-in**: a scenario must declare
``generation.shared_poi.limit_mw`` and supply hourly per-tech profiles
(``generation.technologies.<tech>.hourly_profile_mw``). Absent either, the interaction is not
modelled and :func:`resolve_shared_poi_curtailment` returns ``None`` — so no committed
scenario is affected (KPI-neutral). For DutchBay specifically the 220 kV evacuation line is a
separate CEB project sized for the plant, so the POI is not a binding constraint; the seam is
here for hybrids where it is, and dovetails with the hourly TMY/wind profiles tracked in #529.

Frozen-export note: like the producer physics, curtailment computed here is a producer-side
loss. For a committed scenario consuming a frozen AEP it is disclosure-only until a dated,
authorized re-freeze folds it into the export — it never silently moves committed economics.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from analytics.contracts_v14 import SharedPoiCurtailmentResult

logger = logging.getLogger(__name__)


def estimate_poi_curtailment(
    per_tech_hourly_mw: Mapping[str, Sequence[float]],
    poi_limit_mw: float,
    *,
    step_hours: float = 1.0,
) -> SharedPoiCurtailmentResult:
    """Estimate shared-POI curtailment from per-technology hourly injection profiles.

    Args:
        per_tech_hourly_mw: ``{technology: [MW per step]}``. Profiles must share a length
            (the modelled horizon, typically 8760 hourly steps) and carry non-negative
            injection (MW). A per-step combined injection is the sum across technologies.
        poi_limit_mw: The shared export limit (MW). Combined injection above this is
            curtailed.
        step_hours: Hours per timestep (default 1.0 for hourly profiles). Energy (MWh) is
            ``MW summed over steps x step_hours`` — so sub-hourly profiles scale correctly
            instead of silently mis-claiming MWh (relevant when #529 supplies real profiles).

    Returns:
        A :class:`~analytics.contracts_v14.SharedPoiCurtailmentResult`.

    Raises:
        ValueError: ``poi_limit_mw`` or ``step_hours`` is non-positive, ``per_tech_hourly_mw``
            is empty, the profiles differ in length, or any injection value is negative
            (CESSPIT — a negative MW would deflate gross energy and inflate the curtailment
            percentage; an ambiguous combined profile must not be silently truncated).
    """
    if poi_limit_mw <= 0:
        raise ValueError(f"poi_limit_mw must be positive; got {poi_limit_mw}")
    if step_hours <= 0:
        raise ValueError(f"step_hours must be positive; got {step_hours}")
    if not per_tech_hourly_mw:
        raise ValueError("per_tech_hourly_mw must contain at least one profile")
    lengths = {len(p) for p in per_tech_hourly_mw.values()}
    if len(lengths) != 1:
        raise ValueError(
            f"per-tech hourly profiles must share one length; got {sorted(lengths)}"
        )
    (steps_total,) = lengths
    if steps_total == 0:
        raise ValueError("per-tech hourly profiles are empty")

    gross_mw_steps = 0.0
    curtailed_mw_steps = 0.0
    hours_curtailed = 0
    for step in range(steps_total):
        combined = 0.0
        for tech, profile in per_tech_hourly_mw.items():
            value = float(profile[step])
            if value < 0:
                raise ValueError(
                    f"per-tech injection must be non-negative; {tech!r} has {value} "
                    f"at step {step}"
                )
            combined += value
        gross_mw_steps += combined
        excess = combined - poi_limit_mw
        if excess > 0:
            curtailed_mw_steps += excess
            hours_curtailed += 1

    gross_mwh = gross_mw_steps * step_hours
    curtailed_mwh = curtailed_mw_steps * step_hours
    curtailment_pct = (curtailed_mwh / gross_mwh * 100.0) if gross_mwh > 0 else 0.0
    return SharedPoiCurtailmentResult(
        poi_limit_mw=float(poi_limit_mw),
        gross_energy_mwh=gross_mwh,
        curtailed_energy_mwh=curtailed_mwh,
        curtailment_pct=curtailment_pct,
        hours_curtailed=hours_curtailed,
        hours_total=steps_total,
    )


def _nested_get(config: Mapping[str, Any], *path: str) -> Any:
    cur: Any = config
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def _hourly_profile(block: Mapping[str, Any]) -> Optional[Sequence[float]]:
    """A technology's hourly injection profile (MW), if declared and well-formed."""
    profile = block.get("hourly_profile_mw")
    if not isinstance(profile, (list, tuple)) or not profile:
        return None
    try:
        return [float(v) for v in profile]
    except (TypeError, ValueError):
        return None


def resolve_shared_poi_curtailment(
    config: Mapping[str, Any],
) -> Optional[SharedPoiCurtailmentResult]:
    """Resolve shared-POI curtailment for a scenario, or ``None`` when not modelled.

    Reads ``generation.shared_poi.limit_mw`` and the per-technology
    ``generation.technologies.<tech>.hourly_profile_mw`` arrays. Returns ``None`` (the
    interaction is not modelled — opt-in) when no POI limit is declared, or when fewer than
    two technologies supply an hourly profile (a single profile cannot exceed a POI sized
    for it via *sharing*). This keeps every committed scenario byte-identical.
    """
    limit = _nested_get(config, "generation", "shared_poi", "limit_mw")
    if limit is None:
        return None
    try:
        poi_limit_mw = float(limit)
    except (TypeError, ValueError):
        logger.warning(
            "generation.shared_poi.limit_mw is non-numeric (%r); skipping.", limit
        )
        return None

    techs = _nested_get(config, "generation", "technologies")
    if not isinstance(techs, Mapping):
        return None
    profiles: dict[str, Sequence[float]] = {}
    for name, block in techs.items():
        if isinstance(block, Mapping):
            profile = _hourly_profile(block)
            if profile is not None:
                profiles[str(name)] = profile
    if len(profiles) < 2:
        return None

    try:
        return estimate_poi_curtailment(profiles, poi_limit_mw)
    except ValueError as exc:
        logger.warning("shared-POI curtailment not modelled: %s", exc)
        return None


__all__ = [
    "estimate_poi_curtailment",
    "resolve_shared_poi_curtailment",
]
