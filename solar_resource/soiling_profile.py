"""Time-varying soiling profile (OPTIONAL; default-off byte-identical to flat soiling).

Today soiling is modelled as a single FLAT factor: the ``soiling_pct`` term in the itemised
loss chain (:mod:`solar_resource.loss_model`) and the ``soiling_pct`` 1-sigma in the
uncertainty budget (:mod:`solar_resource.exceedance`). A real plant soils gradually between
cleanings: dust accumulates day by day (a rate, in tropical / near-desert sites often
0.1-0.3%/day), each wash resets it toward a clean floor, and the *energy-weighted mean*
soiling loss over the wash cycle is what actually derates annual yield.

This module adds an OPTIONAL ``resource.solar.soiling_profile`` block — an accumulation rate
plus a wash cadence (and an optional clean floor / cap) — and reduces it to a single
**effective flat soiling percent** that the producer's loss path consumes IN PLACE OF the flat
``soiling_pct``. It is opt-in and default-off, exactly like the ``resource.solar.uncertainty``
block (#604): a scenario WITHOUT the block is byte-identical to the flat-soiling behaviour.
The committed hybrid does NOT declare it.

Byte-identity + the re-baseline gate
------------------------------------
The producer only *substitutes* the effective soiling when the block is present; with no
block, ``compute_soiling_profile_effective_pct`` is never called and the flat ``soiling_pct``
/ ``system_loss_pct`` derate runs unchanged. Applying a soiling profile to the COMMITTED solar
CF would move the frozen 0.1685 P50 — a producer-driven re-baseline and therefore a USER GATE
of the same class as #529 (SOLAR-6/12) and the #587 P50-haircut policy. This module never does
that; it only provides the opt-in mechanism.

Model (documented, lender-auditable)
------------------------------------
Over a wash cycle of ``wash_interval_days`` D, starting from a clean floor loss ``s0`` (%),
soiling loss on day t is ``s(t) = min(s0 + rate * t, cap)`` for a daily accumulation
``rate`` (%/day) and an optional saturation ``cap`` (%). Assuming roughly uniform daily energy
(a reasonable P50 simplification for a fixed-tilt tropical site with low seasonal spread), the
energy-weighted mean soiling loss over the cycle is the average of ``s(t)`` for t = 0..D-1.
That mean is the effective flat soiling percent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

__all__ = [
    "SoilingProfile",
    "compute_soiling_profile_effective_pct",
    "soiling_profile_from_config",
]

#: Valid keys in a ``resource.solar.soiling_profile`` block (CESSPIT typo protection).
_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "accumulation_rate_pct_per_day",
        "wash_interval_days",
        "clean_floor_pct",
        "saturation_cap_pct",
    }
)


@dataclass(frozen=True)
class SoilingProfile:
    """A time-varying soiling accumulation + wash-cadence profile.

    Attributes:
        accumulation_rate_pct_per_day: Daily soiling-loss accumulation (%/day, >= 0).
        wash_interval_days: Days between washes (>= 1); soiling resets to ``clean_floor_pct``
            immediately after each wash.
        clean_floor_pct: Residual soiling loss right after a wash (%, >= 0; default 0.0).
        saturation_cap_pct: Optional cap on accumulated soiling loss (%); None = uncapped.
    """

    accumulation_rate_pct_per_day: float
    wash_interval_days: int
    clean_floor_pct: float = 0.0
    saturation_cap_pct: Optional[float] = None

    def __post_init__(self) -> None:
        if self.accumulation_rate_pct_per_day < 0.0:
            raise ValueError(
                "accumulation_rate_pct_per_day must be >= 0; got "
                f"{self.accumulation_rate_pct_per_day}"
            )
        if self.wash_interval_days < 1:
            raise ValueError(
                f"wash_interval_days must be >= 1; got {self.wash_interval_days}"
            )
        if self.clean_floor_pct < 0.0:
            raise ValueError(
                f"clean_floor_pct must be >= 0; got {self.clean_floor_pct}"
            )
        if self.saturation_cap_pct is not None:
            if self.saturation_cap_pct < 0.0:
                raise ValueError(
                    f"saturation_cap_pct must be >= 0; got {self.saturation_cap_pct}"
                )
            if self.saturation_cap_pct < self.clean_floor_pct:
                raise ValueError(
                    "saturation_cap_pct must be >= clean_floor_pct; got "
                    f"{self.saturation_cap_pct} < {self.clean_floor_pct}"
                )

    def effective_soiling_pct(self) -> float:
        """Energy-weighted mean soiling loss (%) over one wash cycle (uniform-energy P50).

        The average of ``s(t) = min(clean_floor + rate*t, cap)`` for t = 0..D-1 over the
        wash interval D. This is the single flat soiling percent the loss chain consumes in
        place of the static ``soiling_pct``.
        """
        total = 0.0
        for day in range(self.wash_interval_days):
            loss = self.clean_floor_pct + self.accumulation_rate_pct_per_day * float(
                day
            )
            if self.saturation_cap_pct is not None:
                loss = min(loss, self.saturation_cap_pct)
            total += loss
        return total / float(self.wash_interval_days)


def compute_soiling_profile_effective_pct(profile: SoilingProfile) -> float:
    """Return the effective flat soiling percent for a :class:`SoilingProfile`.

    Thin wrapper around :meth:`SoilingProfile.effective_soiling_pct` for callers that hold a
    profile without wanting to reach into the dataclass method (parity with the loss-model
    functional surface).
    """
    return profile.effective_soiling_pct()


def soiling_profile_from_config(
    block: Optional[Mapping[str, Any]],
) -> Optional[SoilingProfile]:
    """Build a :class:`SoilingProfile` from a ``resource.solar.soiling_profile`` mapping (#743).

    With ``block=None`` (the committed hybrid declares none) this returns None, and the
    producer keeps its flat ``soiling_pct`` / ``system_loss_pct`` derate — byte-identical to
    the pre-wiring behaviour. Unknown keys RAISE (CESSPIT typo protection).

    Args:
        block: The ``resource.solar.soiling_profile`` mapping, or None.

    Returns:
        A :class:`SoilingProfile`, or None when no block is declared.

    Raises:
        KeyError: an unknown key is present, or a required key is missing.
        TypeError: ``block`` is not a mapping.
    """
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise TypeError(
            "resource.solar.soiling_profile must be a mapping; got "
            f"{type(block).__name__}"
        )
    unknown = [k for k in block if k not in _CONFIG_KEYS]
    if unknown:
        raise KeyError(
            f"resource.solar.soiling_profile has unknown field(s): {sorted(unknown)}; "
            f"valid keys: {sorted(_CONFIG_KEYS)}"
        )
    for required in ("accumulation_rate_pct_per_day", "wash_interval_days"):
        if block.get(required) is None:
            raise KeyError(
                f"resource.solar.soiling_profile is missing required field: {required!r}"
            )
    kwargs: dict[str, Any] = {
        "accumulation_rate_pct_per_day": float(block["accumulation_rate_pct_per_day"]),
        "wash_interval_days": int(block["wash_interval_days"]),
    }
    if "clean_floor_pct" in block:
        kwargs["clean_floor_pct"] = float(block["clean_floor_pct"])
    if "saturation_cap_pct" in block:
        cap = block["saturation_cap_pct"]
        kwargs["saturation_cap_pct"] = None if cap is None else float(cap)
    return SoilingProfile(**kwargs)
