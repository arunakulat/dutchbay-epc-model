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

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional

#: The block's path in a scenario.
OM_INDEXATION_PATH = ("tariff", "om_indexation")
NON_ESCALABLE_ADJUSTMENT_PATH = ("tariff", "non_escalable_adjustment")

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


_NON_ESCALABLE_ALLOWED_KEYS = frozenset(
    {
        "adjusted_component_lkr_per_kwh",
        "non_escalable_lkr_per_kwh",
        "ccpi_weight",
        "lkr_usd_weight",
        "ccpi_inflation_pct",
        "lkr_usd_depreciation_pct",
        "usd_inflation_pct",
        "sppa_signing_offset_months",
        "start_operating_year",
        "sppa_signing_date",
        "cod_date",
        "cod_year",
        "source",
    }
)


@dataclass(frozen=True)
class NonEscalableAdjustment:
    """A resolved ``tariff.non_escalable_adjustment`` block (PUCSL s.3.1 item 1).

    Attributes:
        adjusted_component_lkr_per_kwh: The non-escalable component in SPPA (LKR/kWh).
        adjustment_multiplier: The one-off multiplier (70% * FX2/FX1 + 30% * CCPI2/CCPI1).
        start_year_index: 0-based operating year from which the adjustment applies (0 = year 1).
        sppa_signing_offset_months: Optional offset relative to COD in months.
    """

    adjusted_component_lkr_per_kwh: float
    adjustment_multiplier: float
    start_year_index: int
    sppa_signing_offset_months: Optional[int] = None

    def uplift_lkr_per_kwh(self, year_index: int) -> float:
        """The non-escalable tariff uplift over the base for one operating year (LKR/kWh)."""
        if year_index < self.start_year_index:
            return 0.0
        return self.adjusted_component_lkr_per_kwh * (self.adjustment_multiplier - 1.0)


def _resolve_start_year_index(block: Mapping[str, Any]) -> int:
    """Derive 0-based operating start year from offset or explicit start year."""
    if "start_operating_year" in block:
        val = block["start_operating_year"]
        if isinstance(val, bool) or not isinstance(val, int) or val < 1:
            raise ValueError(
                f"tariff.non_escalable_adjustment.start_operating_year must be an integer >= 1, got {val!r}"
            )
        return int(val) - 1

    if "sppa_signing_offset_months" in block:
        offset = block["sppa_signing_offset_months"]
        if isinstance(offset, bool) or not isinstance(offset, int):
            raise ValueError(
                f"tariff.non_escalable_adjustment.sppa_signing_offset_months must be an integer, got {offset!r}"
            )
        months_after_cod = offset + 12
        if months_after_cod <= 0:
            return 0
        return int(math.ceil(months_after_cod / 12.0))

    raise ValueError(
        "tariff.non_escalable_adjustment requires either 'start_operating_year' or 'sppa_signing_offset_months'"
    )


def resolve_non_escalable_adjustment(
    config: Mapping[str, Any], *, base_tariff_lkr_per_kwh: Optional[float] = None
) -> Optional[NonEscalableAdjustment]:
    """Resolve a scenario's ``tariff.non_escalable_adjustment`` block."""
    tariff = config.get("tariff")
    if not isinstance(tariff, Mapping):
        return None
    block = tariff.get("non_escalable_adjustment")
    if block is None:
        return None
    if not isinstance(block, Mapping):
        raise ValueError("tariff.non_escalable_adjustment must be a mapping")

    unknown = sorted(set(block) - _NON_ESCALABLE_ALLOWED_KEYS)
    if unknown:
        raise ValueError(
            f"tariff.non_escalable_adjustment has unknown keys {unknown}; allowed: {sorted(_NON_ESCALABLE_ALLOWED_KEYS)}"
        )

    if "adjusted_component_lkr_per_kwh" in block:
        adjusted_comp = _number(block, "adjusted_component_lkr_per_kwh")
    elif "non_escalable_lkr_per_kwh" in block:
        adjusted_comp = _number(block, "non_escalable_lkr_per_kwh")
    else:
        raise ValueError(
            "tariff.non_escalable_adjustment requires 'adjusted_component_lkr_per_kwh' (or 'non_escalable_lkr_per_kwh')"
        )

    if adjusted_comp < 0.0:
        raise ValueError(
            f"tariff.non_escalable_adjustment component must be >= 0, got {adjusted_comp}"
        )
    if base_tariff_lkr_per_kwh is not None and adjusted_comp > base_tariff_lkr_per_kwh:
        raise ValueError(
            f"tariff.non_escalable_adjustment component={adjusted_comp} exceeds tariff.lkr_per_kwh={base_tariff_lkr_per_kwh}"
        )

    ccpi_weight = _weight(block, "ccpi_weight")
    fx_weight = _weight(block, "lkr_usd_weight")
    if abs(ccpi_weight + fx_weight - 1.0) > _WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"tariff.non_escalable_adjustment ccpi_weight + lkr_usd_weight must equal 1, got {ccpi_weight} + {fx_weight}"
        )

    ccpi_move = _rate_pct(block, "ccpi_inflation_pct") / 100.0
    deprec_raw = block.get("lkr_usd_depreciation_pct")
    if deprec_raw == RELATIVE_PPP:
        usd_move = _rate_pct(block, "usd_inflation_pct") / 100.0
        fx_move = (1.0 + ccpi_move) / (1.0 + usd_move) - 1.0
    else:
        if "usd_inflation_pct" in block:
            raise ValueError(
                "tariff.non_escalable_adjustment.usd_inflation_pct is read only when "
                f"lkr_usd_depreciation_pct is {RELATIVE_PPP!r}"
            )
        fx_move = _rate_pct(block, "lkr_usd_depreciation_pct") / 100.0

    multiplier = ccpi_weight * (1.0 + ccpi_move) + fx_weight * (1.0 + fx_move)
    start_year_index = _resolve_start_year_index(block)
    offset_raw = block.get("sppa_signing_offset_months")
    offset_months = (
        int(offset_raw)
        if isinstance(offset_raw, int) and not isinstance(offset_raw, bool)
        else None
    )

    return NonEscalableAdjustment(
        adjusted_component_lkr_per_kwh=adjusted_comp,
        adjustment_multiplier=multiplier,
        start_year_index=start_year_index,
        sppa_signing_offset_months=offset_months,
    )


def tariff_lkr_per_kwh_for_year(
    base_tariff_lkr_per_kwh: float,
    indexation: Optional[OmIndexation],
    year_index: int,
    non_escalable_adjustment: Optional[NonEscalableAdjustment] = None,
) -> float:
    """The generation tariff for one 0-based operating year (LKR/kWh).

    Args:
        base_tariff_lkr_per_kwh: The resolved ``tariff.lkr_per_kwh``.
        indexation: The resolved block, or ``None``.
        year_index: Zero-based operating-year index.
        non_escalable_adjustment: The resolved one-off adjustment block, or ``None``.

    Returns:
        The base tariff unchanged when both adjustments are ``None`` (byte-identical),
        otherwise the base plus the indexed uplift of the escalable component and the
        one-off uplift of the adjusted non-escalable component.
    """
    uplift = 0.0
    if indexation is not None:
        uplift += indexation.uplift_lkr_per_kwh(year_index)
    if non_escalable_adjustment is not None:
        uplift += non_escalable_adjustment.uplift_lkr_per_kwh(year_index)
    return base_tariff_lkr_per_kwh + uplift


__all__ = [
    "BASIS_CCPI_FX_WEIGHTED",
    "BASIS_FIXED_RATE",
    "NON_ESCALABLE_ADJUSTMENT_PATH",
    "NonEscalableAdjustment",
    "OM_INDEXATION_PATH",
    "OmIndexation",
    "RELATIVE_PPP",
    "SUPPORTED_BASES",
    "resolve_non_escalable_adjustment",
    "resolve_om_indexation",
    "tariff_lkr_per_kwh_for_year",
]
