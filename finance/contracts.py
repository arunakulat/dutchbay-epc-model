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

from pydantic import BaseModel, Field, field_validator, model_validator


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
