"""Solar PV P50/P75/P90 exceedance build-up (IEC 61724-1 / IEA-PVPS Task 13).

The photovoltaic analogue of ``wind_resource.bankable_aep``'s IEC 61400-15-2 uncertainty
build-up: turn a deterministic P50 annual energy into bankable P75/P90 exceedance levels
from a config-first 1-sigma uncertainty budget. The maths is identical to the wind side
(normal-distribution exceedance, root-sum-of-squares category combination with an optional
uniform correlation, and a time-averageable interannual term divided by ``sqrt(N)`` for the
project-life P90); only the uncertainty *categories* differ — they are PV categories
(GHI dataset, transposition, simulation, soiling, module tolerance, thermal, availability)
rather than wind categories.

This module is **pure** — it imports neither ``pvlib`` nor ``numpy``; it consumes a P50
energy (GWh) that the producer has already computed and returns the exceedance levels. So
the frozen-export adapter can build P75/P90 exports without dragging the optional ``[solar]``
toolchain (CASPER). The exceedance z-table is the SHARED ``analytics.core.exceedance`` table
(one table for wind and solar — parity-tested, never forked).

Default budget provenance: the 1-sigma defaults below are literature-typical for a tropical
fixed-tilt utility-scale plant (IEA-PVPS Task 13 "Uncertainties in Yield Assessments",
IEC 61724-1). They are NOT site-specific; a real lender energy-yield assessment overrides
them per scenario via ``resource.solar.uncertainty`` (the same override pattern as the
itemised loss stack). The combined 1-year sigma at the defaults is ~7.6%.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Any, Mapping

from analytics.core.exceedance import EXCEEDANCE_Z, exceedance_value

__all__ = [
    "SolarUncertaintyBudget",
    "SolarExceedanceResult",
    "exceedance_levels_solar",
]


@dataclass(frozen=True)
class SolarUncertaintyBudget:
    """Relative (% of P50 energy) 1-sigma PV uncertainties — IEA-PVPS Task 13 categories.

    All but ``interannual_ghi_variability_pct`` are treated as *systematic* (constant over
    the project life); the interannual GHI term is the single time-averageable component and
    is divided by ``sqrt(life_years)`` for the multi-year P90, exactly mirroring the wind
    budget's interannual handling. The defaults are tropical-fixed-tilt literature typicals;
    override per scenario via ``resource.solar.uncertainty``.

    Boundary note (avoids double-counting): year-1 DC degradation and multi-year degradation
    belong in the *loss/degradation* chain and the finance degradation schedule respectively,
    NOT here — this budget is energy-yield *uncertainty*, not an energy *derate*.
    """

    interannual_ghi_variability_pct: float = 3.0
    ghi_dataset_pct: float = 4.0
    transposition_pct: float = 2.5
    pv_simulation_pct: float = 4.0
    soiling_pct: float = 2.0
    module_power_tolerance_pct: float = 2.0
    thermal_model_pct: float = 1.5
    availability_pct: float = 1.0

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{f.name} must be numeric; got {value!r}")
            if value < 0.0:
                raise ValueError(f"{f.name} must be >= 0 (percent); got {value}")

    def systematic_sigma_pct(self, correlation: float = 0.0) -> float:
        """Combined sigma of the systematic (non-interannual) categories.

        ``correlation`` rho in [0, 1] is a uniform inter-category correlation. With a single
        uniform rho the variance is ``(1-rho)*RSS^2 + rho*(sum sigma)^2``, so rho=0 -> the
        IEC/IEA-PVPS root-sum-of-squares baseline and rho=1 -> the fully-correlated linear
        sum. Default 0.0 preserves the RSS baseline (identical convention to the wind budget).
        """
        rho = min(max(float(correlation), 0.0), 1.0)
        sigmas = (
            self.ghi_dataset_pct,
            self.transposition_pct,
            self.pv_simulation_pct,
            self.soiling_pct,
            self.module_power_tolerance_pct,
            self.thermal_model_pct,
            self.availability_pct,
        )
        rss_sq = float(sum(s**2 for s in sigmas))
        lin_sq = float(sum(sigmas)) ** 2
        return math.sqrt((1.0 - rho) * rss_sq + rho * lin_sq)

    def combined_sigma_pct(self, life_years: float, correlation: float = 0.0) -> float:
        """Total sigma for an averaging window of ``life_years`` years."""
        iav = self.interannual_ghi_variability_pct / math.sqrt(
            max(float(life_years), 1.0)
        )
        return math.sqrt(self.systematic_sigma_pct(correlation) ** 2 + iav**2)

    @classmethod
    def from_scenario(cls, block: Mapping[str, Any]) -> "SolarUncertaintyBudget":
        """Build from a ``resource.solar.uncertainty`` mapping (CESSPIT: explicit keys).

        Unknown keys RAISE rather than being silently dropped, so a typo (e.g.
        ``soling_pct``) fails loud instead of reverting to a default.
        """
        known = {f.name for f in fields(cls)}
        unknown = [k for k in block if k not in known]
        if unknown:
            raise KeyError(
                f"resource.solar.uncertainty has unknown field(s): {sorted(unknown)}; "
                f"valid keys: {sorted(known)}"
            )
        return cls(**block)


@dataclass(frozen=True)
class SolarExceedanceResult:
    """P50/P75/P90 annual energy (GWh) — shape-identical to wind ``ExceedanceResult``.

    ``p90_1yr_gwh`` uses the single-year sigma (the interannual term un-reduced); ``p90_life_gwh``
    uses the project-life sigma (interannual term divided by ``sqrt(life_years)``), so it sits
    above the 1-year P90.
    """

    p50_gwh: float
    p75_gwh: float
    p90_1yr_gwh: float
    p90_life_gwh: float
    sigma_1yr_pct: float
    sigma_life_pct: float
    life_years: int


def exceedance_levels_solar(
    p50_gwh: float,
    budget: SolarUncertaintyBudget,
    life_years: int = 20,
    p50_haircut_pct: float = 0.0,
    correlation: float = 0.0,
) -> SolarExceedanceResult:
    """P50/P75/P90 (1-year and project-life) PV energy from an uncertainty budget.

    The PV analogue of ``wind_resource.bankable_aep.exceedance_levels``, sharing the
    ``analytics.core.exceedance`` z-table and formula.

    Args:
        p50_gwh: The deterministic (modelled) P50 annual energy in GWh. Must be > 0.
        budget: The 1-sigma uncertainty budget (% of P50).
        life_years: Averaging window for the project-life P90 (the interannual term is
            divided by ``sqrt(life_years)``).
        p50_haircut_pct: A bankability haircut applied to the modelled P50 BEFORE the
            exceedance build-up (default 0.0 = no haircut).
        correlation: Uniform inter-category correlation rho in [0, 1] (0.0 = RSS baseline).

    Returns:
        A :class:`SolarExceedanceResult`.

    Raises:
        ValueError: if ``p50_gwh`` is not positive.
    """
    if p50_gwh <= 0.0:
        raise ValueError(f"p50_gwh must be > 0; got {p50_gwh}")
    p50 = p50_gwh * (1.0 - float(p50_haircut_pct) / 100.0)
    sig1 = budget.combined_sigma_pct(1.0, correlation)
    sigl = budget.combined_sigma_pct(life_years, correlation)
    return SolarExceedanceResult(
        p50_gwh=p50,
        p75_gwh=exceedance_value(p50, sig1, EXCEEDANCE_Z[75]),
        p90_1yr_gwh=exceedance_value(p50, sig1, EXCEEDANCE_Z[90]),
        p90_life_gwh=exceedance_value(p50, sigl, EXCEEDANCE_Z[90]),
        sigma_1yr_pct=sig1,
        sigma_life_pct=sigl,
        life_years=life_years,
    )
