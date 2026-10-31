"""Immutable, explicit YAML battery ratings shared by finance and dispatch (#1401)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

# Preserve the pre-existing BESS rating reconciliation policy; no scenario value changes.
_RATING_RELATIVE_TOLERANCE = 0.01


def _positive_rating(value: object, field: str) -> float:
    """Require a finite positive YAML number without bool/string coercion."""
    if type(value) not in (int, float):
        raise ValueError(f"{field} must be an explicit finite positive YAML number.")
    try:
        number = float(cast(int | float, value))
    except OverflowError as exc:
        raise ValueError(f"{field} must be a finite positive YAML number.") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field} must be an explicit finite positive YAML number.")
    return number


@dataclass(frozen=True)
class BessSizing:
    """Power, supply duration and energy ratings with no implicit size defaults.

    The authored energy rating is retained when present and reconciled within the
    existing 1% policy. Omitted energy is derived from authored power and duration.
    This is a nameplate contract, not an SOC, dispatch-right or revenue assumption.
    """

    power_mw: float
    duration_h: float
    energy_mwh: float

    def __post_init__(self) -> None:
        """Reject invalid units/bounds and inconsistent nameplate ratings."""
        power = _positive_rating(self.power_mw, "power_mw")
        duration = _positive_rating(self.duration_h, "duration_h")
        energy = _positive_rating(self.energy_mwh, "energy_mwh")
        implied = power * duration
        if not math.isfinite(implied) or implied <= 0:
            raise ValueError(
                "power_mw*duration_h must produce finite positive energy_mwh."
            )
        if abs(energy - implied) / implied > _RATING_RELATIVE_TOLERANCE:
            raise ValueError(
                f"energy_mwh={energy} does not reconcile with "
                f"power_mw*duration_h={implied} within the existing 1% rating tolerance."
            )

    @classmethod
    def from_mapping(cls, block: Mapping[str, Any]) -> BessSizing:
        """Resolve required authored power/duration and optional authored energy.

        Args:
            block: One YAML ``generation.technologies.<name>`` battery block.

        Returns:
            An immutable, validated rating without changing the input mapping.

        Raises:
            ValueError: A required field is missing, malformed or inconsistent.
        """
        power = _positive_rating(block.get("power_mw"), "power_mw")
        duration = _positive_rating(block.get("duration_h"), "duration_h")
        energy = (
            _positive_rating(block["energy_mwh"], "energy_mwh")
            if "energy_mwh" in block
            else power * duration
        )
        return cls(power_mw=power, duration_h=duration, energy_mwh=energy)

    def model_dump(self) -> dict[str, float]:
        """Return the validated unit-labelled nameplate ratings."""
        self.__post_init__()
        return asdict(self)
