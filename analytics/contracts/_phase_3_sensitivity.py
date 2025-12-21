from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3: SENSITIVITY ANALYSIS - Core Data Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ShockSpec:
    """Specification for a single sensitivity shock.

    Defines the low and high values for a variable to test its impact on metrics.
    Immutable (frozen=True) ensures contracts cannot be accidentally modified.
    
    CESSPIT Validation
    ──────────────────
    - variable_name: Must be non-empty string
    - low_value: Must be numeric
    - high_value: Must be numeric and >= low_value
    - Fails fast on contract violation
    
    Examples
    ────────
    >>> ShockSpec("capex", 180e6, 220e6, "CAPEX ±10%")  # Valid
    >>> ShockSpec("", 180e6, 220e6)  # Raises ValueError
    >>> ShockSpec("capex", 220e6, 180e6)  # Raises ValueError (high < low)
    """

    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate ShockSpec contract invariants.
        
        CESSPIT: Fail-fast validation catches violations at construction time.
        
        Raises
        ------
        ValueError
            If variable_name is empty or low_value > high_value.
        TypeError
            If low_value or high_value are not numeric.
        """
        # Validation 1: Non-empty variable name
        if not self.variable_name or not isinstance(self.variable_name, str):
            raise ValueError(
                f"ShockSpec.variable_name must be non-empty string, "
                f"got: {self.variable_name!r}"
            )
        
        # Validation 2: Numeric types
        if not isinstance(self.low_value, (int, float)):
            raise TypeError(
                f"ShockSpec.low_value must be numeric, "
                f"got {type(self.low_value).__name__}: {self.low_value!r}"
            )
        
        if not isinstance(self.high_value, (int, float)):
            raise TypeError(
                f"ShockSpec.high_value must be numeric, "
                f"got {type(self.high_value).__name__}: {self.high_value!r}"
            )
        
        # Validation 3: Logical ordering (low <= high)
        if self.low_value > self.high_value:
            raise ValueError(
                f"ShockSpec.low_value ({self.low_value}) cannot exceed "
                f"high_value ({self.high_value}) for variable '{self.variable_name}'"
            )


@dataclass(frozen=True)
class ShockResult:
    """Result of applying a shock to a variable.

    Contains computed properties like impact and direction.
    Immutable to prevent accidental modification after calculation.
    """

    variable_name: str
    label: str
    base_metric: float
    low_metric: float
    high_metric: float
    impact: float
    direction: str
    sensitivity: float


# ═════════════════════════════════════════════════════════════════════════════
# AGGREGATION CONTRACT: SensitivitySuite
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SensitivitySuite:
    """Aggregate results of sensitivity analysis.

    Contains all shock results, tornado ranking, and metadata.
    Single source of truth for sensitivity analysis output.
    """

    scenario_name: str
    metric_name: str
    base_metric_value: float
    shock_results: List[ShockResult]
    tornado_ranking: List[ShockResult]
    analysis_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert the sensitivity suite to a dictionary representation."""
        return {
            "scenario": self.scenario_name,
            "metric": self.metric_name,
            "base_value": self.base_metric_value,
            "timestamp": self.analysis_timestamp,
            "shocks": [
                {
                    "variable_name": sr.variable_name,
                    "label": sr.label,
                    "base_metric": sr.base_metric,
                    "low_metric": sr.low_metric,
                    "high_metric": sr.high_metric,
                    "impact": sr.impact,
                    "direction": sr.direction,
                    "sensitivity": sr.sensitivity,
                }
                for sr in self.shock_results
            ],
            "tornado": [
                {
                    "variable_name": sr.variable_name,
                    "label": sr.label,
                    "impact": sr.impact,
                    "direction": sr.direction,
                    "rank": i + 1,
                }
                for i, sr in enumerate(self.tornado_ranking)
            ],
        }

    def to_tornado_dict(self) -> Dict[str, Any]:
        """Export tornado ranking as dictionary."""
        return {
            "scenario": self.scenario_name,
            "metric": self.metric_name,
            "baseline": self.base_metric_value,
            "ranking": [
                {
                    "rank": i + 1,
                    "variable": sr.variable_name,
                    "label": sr.label,
                    "impact": sr.impact,
                    "direction": sr.direction,
                }
                for i, sr in enumerate(self.tornado_ranking)
            ],
        }


# ═════════════════════════════════════════════════════════════════════════════
# STANDARD SHOCK LIBRARY: Pre-defined common shocks
# ═════════════════════════════════════════════════════════════════════════════


class StandardShockLibrary:
    """Library of standard sensitivity shocks for DFI/Lender analysis.

    Provides 7 standard shock types commonly used in project finance:
    1. CAPEX Overrun
    2. OPEX Overrun
    3. Interest Rate Rise
    4. Inflation Rate Rise
    5. Production Shortfall
    6. Tariff Reduction
    7. Construction Delay

    All shocks use ±10% or ±1% (for rates) changes.
    """

    @staticmethod
    def capex_overrun(base_capex: float) -> ShockSpec:
        """CAPEX Overrun: ±10% of capital expenditures."""
        return ShockSpec(
            variable_name="capex_total",
            low_value=base_capex * 0.90,
            high_value=base_capex * 1.10,
            label="CAPEX ±10%",
        )

    @staticmethod
    def opex_overrun(base_opex: float) -> ShockSpec:
        """OPEX Overrun: ±10% of operating expenses."""
        return ShockSpec(
            variable_name="opex_annual",
            low_value=base_opex * 0.90,
            high_value=base_opex * 1.10,
            label="OPEX ±10%",
        )

    @staticmethod
    def interest_rate_rise(base_rate: float) -> ShockSpec:
        """Interest Rate Increase: ±100 basis points."""
        return ShockSpec(
            variable_name="interest_rate",
            low_value=base_rate - 0.01,
            high_value=base_rate + 0.01,
            label="Interest Rate ±1%",
        )

    @staticmethod
    def inflation_rate_rise(base_inflation: float) -> ShockSpec:
        """Inflation Rate Increase: ±100 basis points."""
        return ShockSpec(
            variable_name="inflation_rate",
            low_value=base_inflation - 0.01,
            high_value=base_inflation + 0.01,
            label="Inflation ±1%",
        )

    @staticmethod
    def production_shortfall(base_output: float) -> ShockSpec:
        """Production Shortfall: ±10% variation in output."""
        return ShockSpec(
            variable_name="annual_output",
            low_value=base_output * 0.90,
            high_value=base_output * 1.10,
            label="Production ±10%",
        )

    @staticmethod
    def tariff_reduction(base_tariff: float) -> ShockSpec:
        """Tariff Reduction: ±10% change in tariff or revenue rate."""
        return ShockSpec(
            variable_name="tariff_rate",
            low_value=base_tariff * 0.90,
            high_value=base_tariff * 1.10,
            label="Tariff ±10%",
        )

    @staticmethod
    def construction_delay(months_delay: float) -> ShockSpec:
        """Construction Delay: ±months_delay months delay in project COD."""
        return ShockSpec(
            variable_name="construction_period",
            low_value=0.0 if months_delay > 0 else months_delay,
            high_value=months_delay,
            label=f"Construction Delay ±{months_delay} months",
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAX SHOCK LIBRARY: Tax-specific sensitivity shocks
# ═════════════════════════════════════════════════════════════════════════════


class TaxShockLibrary(StandardShockLibrary):
    """Extended library with tax-specific sensitivity shocks.
    
    Provides 5 additional tax-specific shock types for enhanced tax analysis:
    1. Corporate Tax Rate (±5%)
    2. Depreciation Method (categorical: straight-line vs MACRS)
    3. Distribution Delay Period (±2 years)
    4. TLCF Carryforward Limit (±5 years)
    5. Salvage Value (±20%)
    
    Integrates with tax_optimization_v14_enhanced.py for TLCF-aware analysis.
    
    Usage Example
    ─────────────
    >>> from analytics.contracts import TaxShockLibrary
    >>> shocks = [
    ...     TaxShockLibrary.corporate_tax_rate(0.28),
    ...     TaxShockLibrary.depreciation_method(),
    ...     TaxShockLibrary.distribution_delay(4),
    ... ]
    >>> suite = run_tax_sensitivity_analysis(shocks=shocks)
    """
    
    @staticmethod
    def corporate_tax_rate(base_rate: float = 0.28) -> ShockSpec:
        """Corporate Tax Rate: ±5 percentage points (±500 basis points).
        
        DFI Compliance: OECD average corporate tax rate range 20-33%.
        
        Parameters
        ----------
        base_rate : float, default=0.28
            Base corporate tax rate as decimal (0.28 = 28%).
        
        Returns
        -------
        ShockSpec
            Shock with low=23%, high=33% for base_rate=28%.
        
        Examples
        --------
        >>> TaxShockLibrary.corporate_tax_rate(0.28)
        ShockSpec(variable_name='tax.corporate_rate', low_value=0.23, high_value=0.33)
        """
        return ShockSpec(
            variable_name="tax.corporate_rate",
            low_value=max(0.0, base_rate - 0.05),  # Floor at 0%
            high_value=min(1.0, base_rate + 0.05),  # Ceiling at 100%
            label="Tax Rate ±5%",
        )
    
    @staticmethod
    def depreciation_method() -> ShockSpec:
        """Depreciation Method: Categorical shock (straight-line vs MACRS).
        
        Categorical encoding:
        - 0 = Straight-line depreciation (conservative)
        - 1 = MACRS-7 (accelerated, higher early tax shields)
        
        Returns
        -------
        ShockSpec
            Shock with low=0 (straight-line), high=1 (MACRS).
        
        Notes
        -----
        For proper evaluation, the evaluation engine must interpret:
        - 0 → use straight-line depreciation schedule
        - 1 → use MACRS-7 year schedule (as per IRS Rev. Proc. 2011-14)
        
        Examples
        --------
        >>> TaxShockLibrary.depreciation_method()
        ShockSpec(variable_name='tax.depreciation_method', low_value=0.0, high_value=1.0)
        """
        return ShockSpec(
            variable_name="tax.depreciation_method",
            low_value=0.0,  # Straight-line
            high_value=1.0,  # MACRS-7
            label="Depreciation Method (0=SL, 1=MACRS)",
        )
    
    @staticmethod
    def distribution_delay(base_delay_years: int = 4) -> ShockSpec:
        """Distribution Delay Period: ±2 years delay in equity distributions.
        
        Parameters
        ----------
        base_delay_years : int, default=4
            Base distribution delay period in years.
        
        Returns
        -------
        ShockSpec
            Shock with low=base-2 years, high=base+2 years.
            Floors at 0 years (immediate distributions).
            Ceilings at 10 years (extreme delay case).
        
        Notes
        -----
        Longer delays reduce equity IRR but may optimize TLCF utilization.
        Integrates with optimize_distribution_timing_enhanced().
        
        Examples
        --------
        >>> TaxShockLibrary.distribution_delay(4)
        ShockSpec(variable_name='tax.distribution_delay_years', low_value=2.0, high_value=6.0)
        """
        return ShockSpec(
            variable_name="tax.distribution_delay_years",
            low_value=float(max(0, base_delay_years - 2)),
            high_value=float(min(10, base_delay_years + 2)),
            label=f"Distribution Delay ±2yr (base={base_delay_years}yr)",
        )
    
    @staticmethod
    def tlcf_carryforward_limit(base_years: int = 20) -> ShockSpec:
        """TLCF Carryforward Limit: ±5 years variation in carryforward period.
        
        Parameters
        ----------
        base_years : int, default=20
            Base TLCF carryforward limit in years.
        
        Returns
        -------
        ShockSpec
            Shock with low=base-5 years, high=base+5 years.
            Floors at 10 years (short carryforward).
            Ceilings at 30 years (extended carryforward).
        
        Notes
        -----
        Jurisdictions vary:
        - US: Indefinite carryforward post-TCJA 2017 (use 30 as proxy)
        - EU: Typically 5-10 years
        - Emerging markets: 5-20 years
        
        Examples
        --------
        >>> TaxShockLibrary.tlcf_carryforward_limit(20)
        ShockSpec(variable_name='tax.tlcf_carryforward_years', low_value=15.0, high_value=25.0)
        """
        return ShockSpec(
            variable_name="tax.tlcf_carryforward_years",
            low_value=float(max(10, base_years - 5)),
            high_value=float(min(30, base_years + 5)),
            label=f"TLCF Limit ±5yr (base={base_years}yr)",
        )
    
    @staticmethod
    def salvage_value(base_salvage: float) -> ShockSpec:
        """Salvage Value: ±20% variation in end-of-life asset value.
        
        Parameters
        ----------
        base_salvage : float
            Base salvage value at end of project life.
        
        Returns
        -------
        ShockSpec
            Shock with low=80% of base, high=120% of base.
            Floors at $0 (no salvage value).
        
        Notes
        -----
        Salvage value impacts:
        - Terminal cash flow (equity distribution)
        - Depreciation basis (for tax purposes)
        - Lender recovery in stressed scenarios
        
        Examples
        --------
        >>> TaxShockLibrary.salvage_value(10e6)
        ShockSpec(variable_name='tax.salvage_value', low_value=8000000.0, high_value=12000000.0)
        """
        return ShockSpec(
            variable_name="tax.salvage_value",
            low_value=max(0.0, base_salvage * 0.80),
            high_value=base_salvage * 1.20,
            label="Salvage Value ±20%",
        )


__all__ = [
    "ShockSpec",
    "ShockResult",
    "SensitivitySuite",
    "StandardShockLibrary",
    "TaxShockLibrary",
]
