"""
Finance module configuration contracts using Pydantic v2.

This module provides type-safe configuration models for sensitivity analysis
and other financial modeling scenarios. All models follow Pydantic v2 syntax
with proper Field() wrappers and validators.

Example:
    >>> from finance.contracts import ParameterRangeConfig
    >>> param = ParameterRangeConfig(
    ...     variable_name="tariff_usd_per_kwh",
    ...     base_value=0.085,
    ...     low_pct=10.0,
    ...     high_pct=15.0,
    ...     steps=5,
    ...     label="Tariff (USD/kWh)"
    ... )
    >>> param.low_value  # Automatically computed
    0.0765
    >>> param.high_value
    0.09775
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ParameterRangeConfig(BaseModel):
    """Configuration for a single parameter's sensitivity range.

    Defines how a parameter should vary across a sensitivity analysis,
    including percentage-based ranges and step counts. Low/high values
    are automatically computed from base_value and percentages.

    Args:
        variable_name: Name of the variable to vary (e.g., 'tariff_usd_per_kwh')
        base_value: Base/nominal value for the parameter
        low_pct: Percentage decrease for low bound (0-100, e.g., 10.0 = -10%)
        high_pct: Percentage increase for high bound (0-100, e.g., 15.0 = +15%)
        steps: Number of evaluation points across the range (2-20)
        label: Optional human-readable label for charts/reports
        shock_type: Type of shock application ('scalar', 'additive', 'multiplicative')
        low_value: Computed lower bound (base_value * (1 - low_pct/100))
        high_value: Computed upper bound (base_value * (1 + high_pct/100))

    Raises:
        ValueError: If shock_type is not one of allowed values
        ValueError: If percentages or steps are out of valid ranges
    """

    variable_name: str
    base_value: float
    low_pct: float = Field(
        ge=0, le=100, description="Percentage decrease for low bound"
    )
    high_pct: float = Field(
        ge=0, le=100, description="Percentage increase for high bound"
    )
    steps: int = Field(
        default=5, ge=2, le=20, description="Number of evaluation points"
    )
    label: Optional[str] = Field(default=None, description="Human-readable label")
    shock_type: str = Field(default="scalar", description="Shock application type")
    low_value: Optional[float] = Field(default=None, description="Computed lower bound")
    high_value: Optional[float] = Field(
        default=None, description="Computed upper bound"
    )

    @field_validator("shock_type")
    @classmethod
    def validate_shock_type(cls, v: str) -> str:
        """Validate shock_type is one of allowed values.

        Args:
            v: Proposed shock_type value

        Returns:
            Validated shock_type

        Raises:
            ValueError: If shock_type not in allowed set
        """
        allowed = {"scalar", "additive", "multiplicative"}
        if v not in allowed:
            raise ValueError(f"shock_type must be one of {allowed}, got {v}")
        return v

    @model_validator(mode="after")
    def compute_range_values(self) -> "ParameterRangeConfig":
        """Compute low_value and high_value from base_value and percentages.

        If low_value or high_value are not explicitly provided, computes them
        from base_value using the percentage adjustments. This ensures
        consistency and reduces config redundancy.

        Returns:
            Self with computed low_value and high_value
        """
        if self.low_value is None:
            self.low_value = self.base_value * (1 - self.low_pct / 100)
        if self.high_value is None:
            self.high_value = self.base_value * (1 + self.high_pct / 100)
        return self


class SensitivityConfig(BaseModel):
    """Configuration for sensitivity analysis across multiple parameters.

    Orchestrates multi-parameter sensitivity runs by defining which parameters
    to vary, what metrics to track, and analysis options like correlation
    and tornado charts.

    Args:
        parameters: List of ParameterRangeConfig objects defining sensitivity ranges
        output_metrics: Metrics to track (e.g., ["npv", "irr", "dscr_min"])
        correlation_enabled: Whether to compute parameter correlations
        tornado_chart: Whether to generate tornado chart visualization

    Raises:
        ValueError: If no output metrics specified
        ValueError: If parameter variable names are not unique
    """

    parameters: list[ParameterRangeConfig]
    output_metrics: list[str] = Field(
        default_factory=lambda: ["npv", "irr"],
        description="Metrics to track during sensitivity",
    )
    correlation_enabled: bool = Field(
        default=False,
        description="Compute parameter correlation matrix",
    )
    tornado_chart: bool = Field(
        default=True,
        description="Generate tornado chart visualization",
    )

    @field_validator("output_metrics")
    @classmethod
    def validate_metrics(cls, v: list[str]) -> list[str]:
        """Ensure at least one output metric is specified.

        Args:
            v: List of metric names

        Returns:
            Validated metric list

        Raises:
            ValueError: If metric list is empty
        """
        if not v:
            raise ValueError("At least one output metric required")
        return v

    @model_validator(mode="after")
    def validate_parameter_uniqueness(self) -> "SensitivityConfig":
        """Ensure parameter variable names are unique.

        Prevents configuration errors where the same parameter is varied
        multiple times, which would create ambiguous analysis results.

        Returns:
            Self with validated unique parameters

        Raises:
            ValueError: If duplicate parameter variable names found
        """
        names = [p.variable_name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("Parameter variable_names must be unique")
        return self


# ═══════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Result Contracts (Pydantic V2)
# ═══════════════════════════════════════════════════════════════════════════


class TornadoResult(BaseModel):
    """Single parameter tornado sensitivity result.

    Captures the impact of varying one parameter across its low/high range
    on a target metric (typically IRR or NPV). Used by sensitivity_v14 module
    for one-way sensitivity analysis.

    Args:
        variable: Parameter name or display label
        base_irr: Baseline metric value (unshocked configuration)
        low_irr: Metric value at low parameter bound
        high_irr: Metric value at high parameter bound
        impact_abs: Absolute impact magnitude (auto-computed)
        impact_dir: Direction of impact: +1 or -1 (auto-computed)

    Example:
        >>> result = TornadoResult(
        ...     variable="Tariff (USD/kWh)",
        ...     base_irr=0.12,
        ...     low_irr=0.10,
        ...     high_irr=0.14
        ... )
        >>> result.impact_abs
        0.02
        >>> result.impact_dir
        1
    """

    variable: str = Field(description="Parameter name or display label")
    base_irr: float = Field(description="Baseline metric value")
    low_irr: float = Field(description="Metric at low parameter bound")
    high_irr: float = Field(description="Metric at high parameter bound")
    impact_abs: Optional[float] = Field(default=None, description="Absolute impact")
    impact_dir: Optional[int] = Field(default=None, description="Impact direction")

    @model_validator(mode="after")
    def compute_impact(self) -> "TornadoResult":
        """Compute impact_abs and impact_dir from metric values.

        Calculates absolute impact as the maximum deviation from base,
        and direction based on whether high > base.

        Returns:
            Self with computed impact_abs and impact_dir
        """
        if self.impact_abs is None:
            self.impact_abs = max(
                abs(self.low_irr - self.base_irr),
                abs(self.high_irr - self.base_irr),
            )
        if self.impact_dir is None:
            self.impact_dir = 1 if self.high_irr >= self.base_irr else -1
        return self


class MultiMetricTornadoResult(BaseModel):
    """Multi-metric tornado result for a single parameter.

    Extends TornadoResult to track multiple KPI metrics simultaneously
    (e.g., project_irr, equity_irr, min_dscr). Used by sensitivity_v14
    for multi-metric tornado analysis.

    Args:
        variable: Parameter name
        label: Display label for charts/reports
        base_values: Dict of base metric values {metric_name: value}
        low_values: Dict of low-bound metric values
        high_values: Dict of high-bound metric values
        impacts: Dict of absolute impacts per metric (auto-computed)
        impact_dirs: Dict of impact directions per metric (auto-computed)

    Example:
        >>> result = MultiMetricTornadoResult(
        ...     variable="tariff_usd_per_kwh",
        ...     label="Tariff",
        ...     base_values={"project_irr": 0.12, "equity_irr": 0.15},
        ...     low_values={"project_irr": 0.10, "equity_irr": 0.13},
        ...     high_values={"project_irr": 0.14, "equity_irr": 0.17}
        ... )
        >>> result.impacts["project_irr"]
        0.02
    """

    variable: str
    label: str
    base_values: dict[str, float]
    low_values: dict[str, float]
    high_values: dict[str, float]
    impacts: Optional[dict[str, float]] = None
    impact_dirs: Optional[dict[str, int]] = None

    @model_validator(mode="after")
    def compute_multi_impacts(self) -> "MultiMetricTornadoResult":
        """Compute impacts and directions for all metrics.

        For each metric in base_values, calculates absolute impact
        and direction based on low/high deviations.

        Returns:
            Self with computed impacts and impact_dirs
        """
        if self.impacts is None:
            self.impacts = {}
        if self.impact_dirs is None:
            self.impact_dirs = {}

        for metric in self.base_values:
            base = self.base_values[metric]
            low = self.low_values.get(metric, base)
            high = self.high_values.get(metric, base)

            self.impacts[metric] = max(abs(low - base), abs(high - base))
            self.impact_dirs[metric] = 1 if high >= base else -1

        return self


class BreakevenResult(BaseModel):
    """Breakeven parameter search result.

    Captures the parameter value that yields a target metric value
    (e.g., IRR = 0 for breakeven). Used by sensitivity_v14.run_breakeven_parameter().

    Args:
        variable: Parameter name
        breakeven_value: Solved parameter value at target
        bracket: Search bounds tuple (low, high)
        status: Solver status ("success", "max_iter_exceeded", etc.)
        iterations: Number of solver iterations (optional)
        target_value: Target metric value (optional, default 0.0)

    Example:
        >>> result = BreakevenResult(
        ...     variable="tariff_usd_per_kwh",
        ...     breakeven_value=0.075,
        ...     bracket=(0.05, 0.10),
        ...     status="success",
        ...     target_value=0.0
        ... )
    """

    variable: str
    breakeven_value: float
    bracket: tuple[float, float]
    status: str = Field(default="success")
    iterations: Optional[int] = None
    target_value: Optional[float] = 0.0


class TailRiskSnapshot(BaseModel):
    """Tail risk metrics snapshot for a scenario.

    Captures downside risk metrics like VaR and CVaR for IRR or NPV.
    Used by casper_v14 module for tail risk analysis.

    Args:
        metric_name: Name of metric (e.g., "project_irr")
        var_95: Value at Risk at 95% confidence level
        cvar_95: Conditional VaR (expected shortfall) at 95%
        var_99: Value at Risk at 99% confidence level (optional)
        cvar_99: Conditional VaR at 99% (optional)
        downside_prob: Probability of metric falling below threshold
        threshold: Risk threshold value

    Example:
        >>> snapshot = TailRiskSnapshot(
        ...     metric_name="project_irr",
        ...     var_95=0.08,
        ...     cvar_95=0.06,
        ...     downside_prob=0.15,
        ...     threshold=0.10
        ... )
    """

    metric_name: str
    var_95: float = Field(description="Value at Risk 95%")
    cvar_95: float = Field(description="Conditional VaR 95%")
    var_99: Optional[float] = None
    cvar_99: Optional[float] = None
    downside_prob: Optional[float] = None
    threshold: Optional[float] = None


class TechnologyBreakdown(BaseModel):
    """Technology cost/performance breakdown.

    Captures technology-specific metrics for hybrid or multi-technology
    projects. Used for technology-level reporting in multi-tech scenarios.

    Args:
        technology: Technology name (e.g., "solar", "wind", "storage")
        capacity_mw: Installed capacity in MW
        capex_usd: Capital expenditure in USD
        opex_annual_usd: Annual operating expense in USD
        generation_gwh: Annual generation in GWh (optional)
        capacity_factor_pct: Capacity factor percentage (optional)

    Example:
        >>> tech = TechnologyBreakdown(
        ...     technology="solar",
        ...     capacity_mw=50.0,
        ...     capex_usd=50_000_000,
        ...     opex_annual_usd=500_000,
        ...     generation_gwh=120.0,
        ...     capacity_factor_pct=27.4
        ... )
    """

    technology: str
    capacity_mw: float
    capex_usd: float
    opex_annual_usd: float
    generation_gwh: Optional[float] = None
    capacity_factor_pct: Optional[float] = None


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result.

    Captures probabilistic analysis results with distribution statistics.
    Used by monte_carlo_v14 module for stochastic analysis.

    Args:
        metric_name: Name of metric (e.g., "project_irr")
        mean: Mean value across simulations
        std: Standard deviation
        percentile_05: 5th percentile (P05)
        percentile_50: 50th percentile (P50/median)
        percentile_95: 95th percentile (P95)
        iterations: Number of Monte Carlo iterations
        seed: Random seed for reproducibility (optional)

    Example:
        >>> result = MonteCarloResult(
        ...     metric_name="project_irr",
        ...     mean=0.12,
        ...     std=0.02,
        ...     p05=0.09,
        ...     p50=0.12,
        ...     p95=0.15,
        ...     iterations=10000,
        ...     seed=42
        ... )

    Note:
        Supports both snake_case (percentile_05) and alias (p05) field names.
    """

    metric_name: str
    mean: float
    std: float
    percentile_05: float = Field(alias="p05")
    percentile_50: float = Field(alias="p50")
    percentile_95: float = Field(alias="p95")
    iterations: int
    seed: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)


# EOF - finance/contracts.py
