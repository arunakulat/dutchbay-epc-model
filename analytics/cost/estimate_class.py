"""AACE estimate class — the maturity/accuracy band of the CAPEX estimate.

AACE RP 17R-97 / 18R-97 attach an expected accuracy RANGE to a cost estimate by its
class (5 = concept → 1 = check estimate). This lifts the estimate class out of the
QRA-only path (analytics.cost.contingency) into a first-class, config-first attribute:

    scenario ``capex.estimate_class``  ->  else  ``config/defaults.yaml``
    ``defaults.cost_reference.estimate_class``

and resolves the asymmetric low/high accuracy band from
``defaults.cost_reference.estimate_class_bands``. The band also provides a sanity FLOOR
for the probabilistic-CAPEX 1-sigma (a configured spread tighter than the class implies
is flagged). Mirrors :mod:`analytics.cost.cost_basis` (CESSPIT / CCCDIR — never a literal).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

_DEFAULTS_PATH = Path(__file__).resolve().parents[2] / "config" / "defaults.yaml"


@dataclass(frozen=True)
class AccuracyBand:
    """AACE expected accuracy range for an estimate class (% of the point estimate)."""

    estimate_class: int
    low_pct: float
    high_pct: float

    @property
    def implied_sigma_pct(self) -> float:
        """A representative 1-sigma %, treating the full band as ~±2-sigma."""
        return (abs(self.low_pct) + self.high_pct) / 2.0 / 2.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "estimate_class": self.estimate_class,
            "low_pct": self.low_pct,
            "high_pct": self.high_pct,
            "implied_sigma_pct": round(self.implied_sigma_pct, 4),
        }


@lru_cache(maxsize=1)
def _cost_reference() -> Mapping[str, Any]:
    import yaml  # project core dep

    data = yaml.safe_load(_DEFAULTS_PATH.read_text())
    ref = data["defaults"]["cost_reference"]
    if not isinstance(ref, Mapping):
        raise ValueError(f"config/defaults.yaml defaults.cost_reference malformed ({_DEFAULTS_PATH})")
    return ref


@lru_cache(maxsize=1)
def default_estimate_class() -> int:
    """The config-sourced default AACE estimate class (config/defaults.yaml)."""
    try:
        return int(_cost_reference()["estimate_class"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"config/defaults.yaml missing defaults.cost_reference.estimate_class ({_DEFAULTS_PATH})"
        ) from exc


def resolve_estimate_class(config: Mapping[str, Any]) -> int:
    """Resolve the AACE estimate class: scenario ``capex.estimate_class`` else the default."""
    capex = config.get("capex")
    if isinstance(capex, Mapping):
        ec = capex.get("estimate_class")
        if ec is not None:
            try:
                return int(ec)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"capex.estimate_class must be an integer 1-5; got {ec!r}") from exc
    return default_estimate_class()


def accuracy_band(estimate_class: int) -> AccuracyBand:
    """The asymmetric low/high accuracy band for an estimate class (config-sourced)."""
    bands = _cost_reference().get("estimate_class_bands")
    if not isinstance(bands, Mapping):
        raise ValueError("config/defaults.yaml missing defaults.cost_reference.estimate_class_bands")
    row = bands.get(str(int(estimate_class)))
    if not isinstance(row, Mapping):
        raise ValueError(f"no estimate_class_bands entry for class {estimate_class}")
    return AccuracyBand(
        estimate_class=int(estimate_class),
        low_pct=float(row["low_pct"]),
        high_pct=float(row["high_pct"]),
    )


def resolve_accuracy_band(config: Mapping[str, Any]) -> AccuracyBand:
    """Resolve the estimate class for a scenario and return its accuracy band."""
    return accuracy_band(resolve_estimate_class(config))


__all__ = [
    "AccuracyBand",
    "default_estimate_class",
    "resolve_estimate_class",
    "accuracy_band",
    "resolve_accuracy_band",
]
