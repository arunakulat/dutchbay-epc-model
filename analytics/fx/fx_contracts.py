"""FX Structured Blocks - v14 Type-safe contracts for FX analytics.

Provides comprehensive FX data structures following v14 governance:
- FXStructuredBlock: Core FX configuration (v14R6 compliant)
- FXRegimeScenario: Multi-regime analysis support
- FXRiskProfile: Lender-grade FX risk metrics
- FXSensitivityConfig: Sensitivity/tornado inputs
- FXMonteCarloConfig: Monte Carlo simulation parameters
- FXCurveOutput: Time-series FX projections
- FXCorrelationMatrix: Multi-currency correlation

All dataclasses are frozen (immutable) per v2.3V239.
Full type hints and mypy-strict per v2.3V236/V2368.

Example
-------
>>> config = FXStructuredBlock(
...     start_lkr_per_usd=375.0,
...     annual_depr=0.03,
...     base_currency="USD",
...     target_currency="LKR",
... )
>>> print(f"{config.start_lkr_per_usd:.2f} LKR/USD")
375.00 LKR/USD

Part of: analytics/fx/ subpackage
Specs: v14R6 (FX mapping requirement), v2.3V239 (frozen dataclasses)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence


class RegimeType(str, Enum):
    """FX regime classification for analysis."""

    HISTORICAL = "historical"
    RECENT = "recent"
    STRESSED = "stressed"


class VolatilityMethod(str, Enum):
    """Method for calculating FX volatility."""

    HISTORICAL_STD = "historical_std"
    GARCH = "garch"
    IMPLIED = "implied"
    MONTE_CARLO = "monte_carlo"


@dataclass(frozen=True)
class FXStructuredBlock:
    """Core FX configuration per v14R6 structured blocks requirement.

    This is the canonical v14 FX config structure. All scenarios must
    provide an FX mapping (not scalar) with these mandatory fields.

    Attributes
    ----------
    start_lkr_per_usd : float
        Initial exchange rate (LKR per USD) at COD or Year 0.
    annual_depr : float
        Annual depreciation rate (decimal, e.g. 0.03 = 3%).
        Negative values represent appreciation.
    base_currency : str
        Base currency code (typically 'USD').
    target_currency : str
        Target currency code (typically 'LKR').
    regime : RegimeType
        Regime classification for this FX projection.
    volatility : float
        Annual volatility (std dev of log returns), default 0.10.
    correlation_with_revenue : float
        Correlation between FX and project revenue, range [-1, 1].
    hedge_ratio : float
        Proportion of FX exposure hedged, range [0, 1].
    metadata : dict[str, Any]
        Additional regime-specific metadata.

    Raises
    ------
    ValueError
        If start_rate <= 0, volatility < 0, or correlations/ratios
        are outside valid ranges.

    Example
    -------
    >>> fx = FXStructuredBlock(
    ...     start_lkr_per_usd=375.0,
    ...     annual_depr=0.03,
    ...     base_currency="USD",
    ...     target_currency="LKR",
    ... )
    >>> fx.start_lkr_per_usd
    375.0
    """

    start_lkr_per_usd: float
    annual_depr: float
    base_currency: str = "USD"
    target_currency: str = "LKR"
    regime: RegimeType = RegimeType.RECENT
    volatility: float = 0.10
    correlation_with_revenue: float = 0.0
    hedge_ratio: float = 0.0
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate FX structured block parameters."""
        if self.start_lkr_per_usd <= 0:
            raise ValueError(
                f"start_lkr_per_usd must be > 0, got "
                f"{self.start_lkr_per_usd}"
            )

        if self.volatility < 0:
            raise ValueError(
                f"volatility must be >= 0, got {self.volatility}"
            )

        if not -1.0 <= self.correlation_with_revenue <= 1.0:
            raise ValueError(
                f"correlation_with_revenue must be in [-1, 1], "
                f"got {self.correlation_with_revenue}"
            )

        if not 0.0 <= self.hedge_ratio <= 1.0:
            raise ValueError(
                f"hedge_ratio must be in [0, 1], got {self.hedge_ratio}"
            )


@dataclass(frozen=True)
class FXRegimeScenario:
    """Multi-regime FX scenario for sensitivity/tornado analysis.

    Attributes
    ----------
    scenario_name : str
        Descriptive name (e.g., 'Base', 'Stressed', 'Optimistic').
    structured_block : FXStructuredBlock
        Core FX configuration for this regime.
    probability : float
        Probability weight for this scenario (0-1).
    years : int
        Number of projection years.
    apply_shock : bool
        Whether to apply a one-time shock in Year 1.
    shock_magnitude : float
        Magnitude of one-time shock (if apply_shock=True).

    Raises
    ------
    ValueError
        If probability not in [0, 1], years < 1.

    Example
    -------
    >>> base_fx = FXStructuredBlock(
    ...     start_lkr_per_usd=375.0, annual_depr=0.03
    ... )
    >>> scenario = FXRegimeScenario(
    ...     scenario_name="Base Case",
    ...     structured_block=base_fx,
    ...     probability=0.6,
    ...     years=20,
    ... )
    >>> scenario.scenario_name
    'Base Case'
    """

    scenario_name: str
    structured_block: FXStructuredBlock
    probability: float
    years: int
    apply_shock: bool = False
    shock_magnitude: float = 0.0

    def __post_init__(self) -> None:
        """Validate regime scenario parameters."""
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(
                f"probability must be in [0, 1], got {self.probability}"
            )

        if self.years < 1:
            raise ValueError(f"years must be >= 1, got {self.years}")


@dataclass(frozen=True)
class FXRiskProfile:
    """Lender-grade FX risk analytics output.

    Attributes
    ----------
    scenario_name : str
        Associated scenario name.
    var_95 : float
        Value at Risk at 95% confidence (currency units).
    var_99 : float
        Value at Risk at 99% confidence (currency units).
    expected_shortfall : float
        Conditional VaR (CVaR) beyond 95th percentile.
    max_drawdown_pct : float
        Maximum drawdown as percentage of start rate.
    sharpe_ratio : float
        Risk-adjusted return metric.
    volatility_realized : float
        Realized annual volatility (historical or simulated).
    correlation_matrix : tuple[tuple[float, ...], ...] | None
        Multi-currency correlation matrix if applicable.

    Example
    -------
    >>> risk = FXRiskProfile(
    ...     scenario_name="Base",
    ...     var_95=15.0,
    ...     var_99=22.5,
    ...     expected_shortfall=18.0,
    ...     max_drawdown_pct=12.5,
    ...     sharpe_ratio=0.85,
    ...     volatility_realized=0.10,
    ... )
    >>> risk.var_95
    15.0
    """

    scenario_name: str
    var_95: float
    var_99: float
    expected_shortfall: float
    max_drawdown_pct: float
    sharpe_ratio: float
    volatility_realized: float
    correlation_matrix: tuple[tuple[float, ...], ...] | None = None


@dataclass(frozen=True)
class FXSensitivityConfig:
    """FX sensitivity/tornado analysis configuration.

    Attributes
    ----------
    base_block : FXStructuredBlock
        Baseline FX configuration.
    parameter_name : str
        Parameter to vary ('annual_depr', 'volatility', etc.).
    low_value : float
        Low-end parameter value for sensitivity.
    high_value : float
        High-end parameter value for sensitivity.
    num_steps : int
        Number of steps between low and high (default 5).

    Raises
    ------
    ValueError
        If num_steps < 2.

    Example
    -------
    >>> base = FXStructuredBlock(
    ...     start_lkr_per_usd=375.0, annual_depr=0.03
    ... )
    >>> sens = FXSensitivityConfig(
    ...     base_block=base,
    ...     parameter_name="annual_depr",
    ...     low_value=0.01,
    ...     high_value=0.05,
    ...     num_steps=5,
    ... )
    >>> sens.parameter_name
    'annual_depr'
    """

    base_block: FXStructuredBlock
    parameter_name: str
    low_value: float
    high_value: float
    num_steps: int = 5

    def __post_init__(self) -> None:
        """Validate sensitivity configuration."""
        if self.num_steps < 2:
            raise ValueError(
                f"num_steps must be >= 2, got {self.num_steps}"
            )


@dataclass(frozen=True)
class FXMonteCarloConfig:
    """Monte Carlo simulation configuration for FX.

    Attributes
    ----------
    base_block : FXStructuredBlock
        Baseline FX configuration.
    num_simulations : int
        Number of Monte Carlo paths (recommend 100k).
    time_horizon_years : int
        Projection horizon in years.
    volatility_method : VolatilityMethod
        Method for generating volatility.
    correlation_matrix : tuple[tuple[float, ...], ...] | None
        Correlation matrix for multi-variate simulations.
    seed : int | None
        Random seed for reproducibility.

    Raises
    ------
    ValueError
        If num_simulations < 1000 or time_horizon_years < 1.

    Example
    -------
    >>> base = FXStructuredBlock(
    ...     start_lkr_per_usd=375.0, annual_depr=0.03
    ... )
    >>> mc = FXMonteCarloConfig(
    ...     base_block=base,
    ...     num_simulations=100_000,
    ...     time_horizon_years=20,
    ... )
    >>> mc.num_simulations
    100000
    """

    base_block: FXStructuredBlock
    num_simulations: int
    time_horizon_years: int
    volatility_method: VolatilityMethod = VolatilityMethod.HISTORICAL_STD
    correlation_matrix: tuple[tuple[float, ...], ...] | None = None
    seed: int | None = None

    def __post_init__(self) -> None:
        """Validate Monte Carlo configuration."""
        if self.num_simulations < 1000:
            raise ValueError(
                f"num_simulations must be >= 1000, "
                f"got {self.num_simulations}"
            )

        if self.time_horizon_years < 1:
            raise ValueError(
                f"time_horizon_years must be >= 1, "
                f"got {self.time_horizon_years}"
            )


@dataclass(frozen=True)
class FXCurveOutput:
    """Time-series FX rate projection output.

    Attributes
    ----------
    years : Sequence[int]
        Year indices (0, 1, 2, ..., N).
    rates : Sequence[float]
        FX rates for each year (LKR/USD or other pair).
    regime : RegimeType
        Regime used for this projection.
    confidence_interval_lower : Sequence[float] | None
        Lower bound of 95% confidence interval (if available).
    confidence_interval_upper : Sequence[float] | None
        Upper bound of 95% confidence interval (if available).
    metadata : dict[str, Any]
        Additional metadata (source, method, etc.).

    Raises
    ------
    ValueError
        If length of years != length of rates.

    Example
    -------
    >>> output = FXCurveOutput(
    ...     years=[0, 1, 2],
    ...     rates=[375.0, 386.25, 397.84],
    ...     regime=RegimeType.RECENT,
    ...     metadata={"method": "geometric"},
    ... )
    >>> len(output.rates)
    3
    """

    years: Sequence[int]
    rates: Sequence[float]
    regime: RegimeType
    confidence_interval_lower: Sequence[float] | None = None
    confidence_interval_upper: Sequence[float] | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate curve output consistency."""
        if len(self.years) != len(self.rates):
            raise ValueError(
                f"Length mismatch: years ({len(self.years)}) != "
                f"rates ({len(self.rates)})"
            )

        if self.confidence_interval_lower is not None:
            if len(self.confidence_interval_lower) != len(self.years):
                raise ValueError(
                    "confidence_interval_lower length mismatch"
                )

        if self.confidence_interval_upper is not None:
            if len(self.confidence_interval_upper) != len(self.years):
                raise ValueError(
                    "confidence_interval_upper length mismatch"
                )


@dataclass(frozen=True)
class FXCorrelationMatrix:
    """Multi-currency correlation structure.

    Attributes
    ----------
    currencies : Sequence[str]
        Currency pair labels (e.g., ['USD/LKR', 'USD/INR']).
    correlation_matrix : tuple[tuple[float, ...], ...]
        NxN correlation matrix (frozen tuple of tuples).
    regime : RegimeType
        Regime used for correlation calculation.
    metadata : dict[str, Any]
        Additional metadata (data source, time period, etc.).

    Raises
    ------
    ValueError
        If matrix dimensions don't match number of currencies.

    Example
    -------
    >>> corr = FXCorrelationMatrix(
    ...     currencies=["USD/LKR", "USD/INR"],
    ...     correlation_matrix=((1.0, 0.75), (0.75, 1.0)),
    ...     regime=RegimeType.HISTORICAL,
    ...     metadata={"period": "2020-2023"},
    ... )
    >>> len(corr.currencies)
    2
    """

    currencies: Sequence[str]
    correlation_matrix: tuple[tuple[float, ...], ...]
    regime: RegimeType = RegimeType.RECENT
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate correlation matrix structure."""
        n_currencies = len(self.currencies)
        n_rows = len(self.correlation_matrix)

        if n_rows != n_currencies:
            raise ValueError(
                f"Matrix rows ({n_rows}) != currencies "
                f"({n_currencies})"
            )

        for idx, row in enumerate(self.correlation_matrix):
            if len(row) != n_currencies:
                raise ValueError(
                    f"Row {idx} has {len(row)} elements, expected "
                    f"{n_currencies}"
                )


__all__ = [
    "RegimeType",
    "VolatilityMethod",
    "FXStructuredBlock",
    "FXRegimeScenario",
    "FXRiskProfile",
    "FXSensitivityConfig",
    "FXMonteCarloConfig",
    "FXCurveOutput",
    "FXCorrelationMatrix",
]
# EOF
