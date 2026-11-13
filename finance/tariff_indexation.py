"""Yearly indexation of a regulated tariff's escalable O&M component.

A two-part feed-in tariff, such as the PUCSL 2026 tariff for Sri Lankan power plants, pays
a non-escalable component that is constant for the SPPA term plus an escalable base O&M
component that the regulator escalates every year. The PUCSL *Methodology for Renewable
Energy Feed-in Tariffs 2026 (Approved)*, s.3.1 item 2, states the basis: "A base O&M
component will be approved considering existing market rates (no escalation assumed).
Annual escalation rate for the base rate, will be published by the Commission considering
CCPI and LKR/USD exchange rate variations."

This module reads an optional ``tariff.om_indexation`` block from a scenario and returns
the per-year index the engine applies to that component only:

    tariff(t) = tariff.lkr_per_kwh + escalable_om_lkr_per_kwh * (index(t) - 1)
    index(t)  = (1 + g) ** (t + pre_operation_years),   t = 0 for operating year 1

so the non-escalable remainder (``lkr_per_kwh - escalable_om_lkr_per_kwh``) stays flat and
an override of ``tariff.lkr_per_kwh`` (a sensitivity or a solve) moves only the base. The
yearly rate ``g`` comes from one of two bases:

* ``ccpi_fx_weighted``: ``g = ccpi_weight * ccpi_inflation + lkr_usd_weight * lkr_usd_
  depreciation``. The weights must add up to 1. The depreciation is either a number or
  ``relative_ppp``, which derives it from ``ccpi_inflation_pct`` and ``usd_inflation_pct``
  as ``(1 + ccpi) / (1 + usd) - 1``.
* ``fixed_rate``: ``g = annual_rate_pct``, for a rate the regulator has published or a
  single-rate sensitivity.

A scenario without the block is byte-identical: the index is exactly 1.0 every year.
Every business value is read from YAML (config-first). Unknown keys, a missing input or an
out-of-range value raise ``ValueError`` (FRAMEWORK-02 fail-loud).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

#: The block's path in a scenario.
OM_INDEXATION_PATH = ("tariff", "om_indexation")

#: Supported index bases.
BASIS_CCPI_FX_WEIGHTED = "ccpi_fx_weighted"
BASIS_FIXED_RATE = "fixed_rate"
SUPPORTED_BASES = (BASIS_CCPI_FX_WEIGHTED, BASIS_FIXED_RATE)

#: The keyword that derives the LKR/USD depreciation from the two inflation inputs.
RELATIVE_PPP = "relative_ppp"

_COMMON_KEYS = frozenset(
    {"escalable_om_lkr_per_kwh", "basis", "pre_operation_years", "source"}
)
_BASIS_KEYS = {
    BASIS_CCPI_FX_WEIGHTED: frozenset(
        {
            "ccpi_weight",
            "lkr_usd_weight",
            "ccpi_inflation_pct",
            "lkr_usd_depreciation_pct",
            "usd_inflation_pct",
        }
    ),
    BASIS_FIXED_RATE: frozenset({"annual_rate_pct"}),
}
_WEIGHT_SUM_TOLERANCE = 1e-9
#: A yearly rate outside this band (percent) is refused as a probable unit error.
_RATE_PCT_BOUNDS = (-50.0, 100.0)


@dataclass(frozen=True)
class OmIndexation:
    """A resolved ``tariff.om_indexation`` block.

    Attributes:
        escalable_om_lkr_per_kwh: The escalable O&M component at the base year (LKR/kWh).
        annual_rate: The yearly index growth, as a decimal (0.032 = 3.2%/yr).
        pre_operation_years: Escalation steps applied before operating year 1.
        basis: The basis the rate was derived on (one of ``SUPPORTED_BASES``).
    """

    escalable_om_lkr_per_kwh: float
    annual_rate: float
    pre_operation_years: int
    basis: str

    def index(self, year_index: int) -> float:
        """The index for a 0-based operating year (operating year 1 is ``0``).

        Args:
            year_index: Zero-based operating-year index.

        Returns:
            ``(1 + annual_rate) ** (year_index + pre_operation_years)``.
        """
        if year_index < 0:
            raise ValueError(f"year_index must be >= 0, got {year_index}")
        return (1.0 + self.annual_rate) ** (year_index + self.pre_operation_years)

    def uplift_lkr_per_kwh(self, year_index: int) -> float:
        """The tariff uplift over the base for one operating year (LKR/kWh)."""
        return self.escalable_om_lkr_per_kwh * (self.index(year_index) - 1.0)


def _number(block: Mapping[str, Any], key: str) -> float:
    """A required finite number from the block, refusing booleans and strings."""
    value = block.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"tariff.om_indexation.{key} must be a number, got {value!r}")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"tariff.om_indexation.{key} must be finite, got {value!r}")
    return number


def _rate_pct(block: Mapping[str, Any], key: str) -> float:
    """A required yearly rate in percent, inside ``_RATE_PCT_BOUNDS``."""
    pct = _number(block, key)
    low, high = _RATE_PCT_BOUNDS
    if not low < pct < high:
        raise ValueError(
            f"tariff.om_indexation.{key}={pct} is outside ({low}, {high}) percent a "
            "year; state rates in percent (5.0 = 5%/yr)"
        )
    return pct


def _weight(block: Mapping[str, Any], key: str) -> float:
    """A required weight in [0, 1]."""
    weight = _number(block, key)
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"tariff.om_indexation.{key}={weight} must be in [0, 1]")
    return weight


def _ccpi_fx_weighted_rate(block: Mapping[str, Any]) -> float:
    """The yearly rate (decimal) on the ``ccpi_fx_weighted`` basis."""
    ccpi_weight = _weight(block, "ccpi_weight")
    fx_weight = _weight(block, "lkr_usd_weight")
    if abs(ccpi_weight + fx_weight - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            "tariff.om_indexation.ccpi_weight + lkr_usd_weight must equal 1, got "
            f"{ccpi_weight} + {fx_weight}"
        )
    ccpi = _rate_pct(block, "ccpi_inflation_pct") / 100.0
    depreciation_raw = block.get("lkr_usd_depreciation_pct")
    if depreciation_raw == RELATIVE_PPP:
        usd = _rate_pct(block, "usd_inflation_pct") / 100.0
        depreciation = (1.0 + ccpi) / (1.0 + usd) - 1.0
    else:
        if "usd_inflation_pct" in block:
            raise ValueError(
                "tariff.om_indexation.usd_inflation_pct is read only when "
                f"lkr_usd_depreciation_pct is {RELATIVE_PPP!r}; remove it or derive "
                "the depreciation from it"
            )
        depreciation = _rate_pct(block, "lkr_usd_depreciation_pct") / 100.0
    return ccpi_weight * ccpi + fx_weight * depreciation


def resolve_om_indexation(
    config: Mapping[str, Any], *, base_tariff_lkr_per_kwh: Optional[float] = None
) -> Optional[OmIndexation]:
    """Resolve a scenario's ``tariff.om_indexation`` block.

    Args:
        config: The scenario mapping.
        base_tariff_lkr_per_kwh: The resolved ``tariff.lkr_per_kwh``. When given, the
            escalable component must not exceed it (the non-escalable remainder cannot
            be negative).

    Returns:
        The resolved indexation, or ``None`` when the scenario has no block.

    Raises:
        ValueError: If the block is malformed, names an unknown key or basis, misses an
            input, or holds an out-of-range value.
    """
    tariff = config.get("tariff")
    if not isinstance(tariff, Mapping):
        return None
    block = tariff.get("om_indexation")
    if block is None:  # absent, or switched off by an override to None
        return None
    if not isinstance(block, Mapping):
        raise ValueError("tariff.om_indexation must be a mapping")

    basis = block.get("basis")
    if basis not in SUPPORTED_BASES:
        raise ValueError(
            f"tariff.om_indexation.basis={basis!r} is not one of {SUPPORTED_BASES}"
        )
    allowed = _COMMON_KEYS | _BASIS_KEYS[basis]
    unknown = sorted(set(block) - allowed)
    if unknown:
        raise ValueError(
            f"tariff.om_indexation has keys {unknown} not allowed for basis "
            f"{basis!r}; allowed: {sorted(allowed)}"
        )

    escalable = _number(block, "escalable_om_lkr_per_kwh")
    if escalable < 0.0:
        raise ValueError(
            f"tariff.om_indexation.escalable_om_lkr_per_kwh={escalable} must be >= 0"
        )
    if base_tariff_lkr_per_kwh is not None and escalable > base_tariff_lkr_per_kwh:
        raise ValueError(
            f"tariff.om_indexation.escalable_om_lkr_per_kwh={escalable} exceeds "
            f"tariff.lkr_per_kwh={base_tariff_lkr_per_kwh}: the non-escalable "
            "remainder would be negative"
        )

    pre_raw = block.get("pre_operation_years")
    if isinstance(pre_raw, bool) or not isinstance(pre_raw, int) or pre_raw < 0:
        raise ValueError(
            "tariff.om_indexation.pre_operation_years must be a whole number >= 0 "
            f"(escalation steps before operating year 1), got {pre_raw!r}"
        )

    if basis == BASIS_CCPI_FX_WEIGHTED:
        rate = _ccpi_fx_weighted_rate(block)
    else:
        rate = _rate_pct(block, "annual_rate_pct") / 100.0

    return OmIndexation(
        escalable_om_lkr_per_kwh=escalable,
        annual_rate=rate,
        pre_operation_years=pre_raw,
        basis=str(basis),
    )


def tariff_lkr_per_kwh_for_year(
    base_tariff_lkr_per_kwh: float,
    indexation: Optional[OmIndexation],
    year_index: int,
) -> float:
    """The generation tariff for one 0-based operating year (LKR/kWh).

    Args:
        base_tariff_lkr_per_kwh: The resolved ``tariff.lkr_per_kwh``.
        indexation: The resolved block, or ``None``.
        year_index: Zero-based operating-year index.

    Returns:
        The base tariff unchanged when ``indexation`` is ``None`` (byte-identical),
        otherwise the base plus the indexed uplift of the escalable component.
    """
    if indexation is None:
        return base_tariff_lkr_per_kwh
    return base_tariff_lkr_per_kwh + indexation.uplift_lkr_per_kwh(year_index)


__all__ = [
    "BASIS_CCPI_FX_WEIGHTED",
    "BASIS_FIXED_RATE",
    "OM_INDEXATION_PATH",
    "OmIndexation",
    "RELATIVE_PPP",
    "SUPPORTED_BASES",
    "resolve_om_indexation",
    "tariff_lkr_per_kwh_for_year",
]
