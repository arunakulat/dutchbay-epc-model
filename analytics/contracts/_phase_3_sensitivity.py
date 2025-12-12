from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3: SENSITIVITY ANALYSIS - Core Data Contracts
# ═════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ShockSpec:
    """Specification for a single sensitivity shock.
    
    Defines the low and high values for a variable to test its impact on metrics.
    Immutable (frozen=True) ensures contracts cannot be accidentally modified.
    """
    variable_name: str
    low_value: float
    high_value: float
    label: Optional[str] = None


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
            label="CAPEX ±10%"
        )

    @staticmethod
    def opex_overrun(base_opex: float) -> ShockSpec:
        """OPEX Overrun: ±10% of operating expenses."""
        return ShockSpec(
            variable_name="opex_annual",
            low_value=base_opex * 0.90,
            high_value=base_opex * 1.10,
            label="OPEX ±10%"
        )

    @staticmethod
    def interest_rate_rise(base_rate: float) -> ShockSpec:
        """Interest Rate Increase: ±100 basis points."""
        return ShockSpec(
            variable_name="interest_rate",
            low_value=base_rate - 0.01,
            high_value=base_rate + 0.01,
            label="Interest Rate ±1%"
        )

    @staticmethod
    def inflation_rate_rise(base_inflation: float) -> ShockSpec:
        """Inflation Rate Increase: ±100 basis points."""
        return ShockSpec(
            variable_name="inflation_rate",
            low_value=base_inflation - 0.01,
            high_value=base_inflation + 0.01,
            label="Inflation ±1%"
        )

    @staticmethod
    def production_shortfall(base_output: float) -> ShockSpec:
        """Production Shortfall: ±10% variation in output."""
        return ShockSpec(
            variable_name="annual_output",
            low_value=base_output * 0.90,
            high_value=base_output * 1.10,
            label="Production ±10%"
        )

    @staticmethod
    def tariff_reduction(base_tariff: float) -> ShockSpec:
        """Tariff Reduction: ±10% change in tariff or revenue rate."""
        return ShockSpec(
            variable_name="tariff_rate",
            low_value=base_tariff * 0.90,
            high_value=base_tariff * 1.10,
            label="Tariff ±10%"
        )

    @staticmethod
    def construction_delay(months_delay: float) -> ShockSpec:
        """Construction Delay: ±months_delay months delay in project COD."""
        return ShockSpec(
            variable_name="construction_period",
            low_value=0.0 if months_delay > 0 else months_delay,
            high_value=months_delay,
            label=f"Construction Delay ±{months_delay} months"
        )


__all__ = [
    "ShockSpec",
    "ShockResult",
    "SensitivitySuite",
    "StandardShockLibrary",
]
