"""FX Data Contracts - Type-safe dataclasses for v14 FX analytics.

Provides:
- FXRegimeConfig: Dual-regime FX model configuration
- FXCurveOutput: Output from FX curve generation
- FXCorrelationMatrix: FX correlation structures

Part of: analytics/fx/ subpackage (Task 2, Sprint Day 5)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class FXRegimeConfig:
    """Configuration for dual-regime FX model.

    Attributes:
        base_currency: Base currency code (e.g., 'USD')
        target_currency: Target currency code (e.g., 'LKR')
        regime_type: Regime classification ('historical' | 'recent' | 'stressed')
        years: Number of years to project
        annual_depr: Annual depreciation rate (default 0.0)
        start_rate: Starting FX rate (initial value)
    """

    base_currency: str
    target_currency: str
    regime_type: str  # 'historical' | 'recent' | 'stressed'
    years: int
    annual_depr: float = 0.0
    start_rate: float = 1.0

    def __post_init__(self) -> None:
        """Validate configuration."""
        valid_regimes = {"historical", "recent", "stressed"}
        if self.regime_type not in valid_regimes:
            raise ValueError(
                f"regime_type must be one of {valid_regimes}, "
                f"got '{self.regime_type}'"
            )
        if self.years < 1:
            raise ValueError(f"years must be >= 1, got {self.years}")


@dataclass(frozen=True)
class FXCurveOutput:
    """Output from FX curve generation.

    Attributes:
        years: Year indices (0, 1, 2, ..., N)
        rates: FX rates for each year
        regime: Regime used ('historical' | 'recent' | 'stressed')
        metadata: Additional metadata (source, calculation method, etc.)
    """

    years: Sequence[int]
    rates: Sequence[float]
    regime: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate output consistency."""
        if len(self.years) != len(self.rates):
            raise ValueError(
                f"Length mismatch: years ({len(self.years)}) "
                f"!= rates ({len(self.rates)})"
            )


@dataclass(frozen=True)
class FXCorrelationMatrix:
    """FX correlation structure for multi-currency analysis.

    Attributes:
        currencies: List of currency pairs (e.g., ['USD/LKR', 'USD/INR'])
        correlation_matrix: 2D correlation matrix (frozen)
        regime: Regime used for calculation
    """

    currencies: Sequence[str]
    correlation_matrix: tuple[tuple[float, ...], ...]
    regime: str = "recent"
