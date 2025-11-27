#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     DUTCHBAY v14 DATA CONTRACTS                             ║
║                  (Fully Refactored with Validators)                         ║
║                                                                              ║
║  All canonical data structures (dataclasses, pydantic models) used for:      ║
║  - Valuation, WACC, and scenario results                                    ║
║  - Equity metrics, downside risk                                            ║
║  - Sensitivity/tornado/optimizer/Monte Carlo surfaces for analytics         ║
║  - Ready for export, reporting, dashboard use                               ║
║                                                                              ║
║  ALWAYS update comments and docstrings in this file for future maintainers. ║
║  All pipeline modules must import *analytics results* only from here.       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ═════════════════════════════════════════════════════════════════════════════
# WACC, Lender/Scenario Results (Phase 1)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class WaccComponents:
    """
    WACC calculation component breakdown for scenario and audit.
    """

    mode: str
    wacc_nominal: float
    wacc_real: Optional[float]
    wacc_prudential: float
    risk_free_rate: float
    market_risk_premium: float
    asset_beta: float
    target_debt_to_equity: float
    target_debt_to_value: float
    target_equity_to_value: float
    cost_of_debt_pretax: float
    cost_of_debt_aftertax: float
    equity_beta_levered: float
    cost_of_equity: float
    tax_rate: float
    inflation_rate: Optional[float]
    prudential_spread_bps: int


@dataclass
class WaccResult:
    """
    Complete WACC result including base and prudential valuations.
    """

    base: WaccComponents
    prudential_rate: Optional[float] = None
    prudential_npv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    """
    Complete scenario evaluation result with WACC and full outputs.
    """

    scenario_name: str
    config_path: str
    project_npv: float
    project_irr: float
    dscr_series: List[float]
    min_dscr: float
    max_debt_usd: float
    wacc: Optional[WaccResult] = None
    discount_rate_used: Optional[float] = None
    wacc_label: Optional[str] = None
    wacc_is_real: Optional[bool] = None
    validation_mode: str = "strict"
    config: Dict[str, Any] = field(default_factory=dict)
    annual_rows: Sequence[Dict[str, Any]] = field(default_factory=list)
    debt_result: Dict[str, Any] = field(default_factory=dict)
    kpis: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """
        Normalise the result into a flat KPI dict.

        This is intentionally conservative – we expose core KPIs plus any
        extra kpis dict that has been populated by the metrics layer.
        """
        data: Dict[str, Any] = {
            "scenario_name": self.scenario_name,
            "config_path": self.config_path,
            "project_npv": self.project_npv,
            "project_irr": self.project_irr,
            "min_dscr": self.min_dscr,
            "max_debt_usd": self.max_debt_usd,
        }
        data.update(self.kpis)
        return data


# ═════════════════════════════════════════════════════════════════════════════
# Equity Performance & Downside Risk Metrics (Phase 2)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class DownsideMetrics:
    """
    Tracks downside risk metrics for equity investors. Typically MC output.
    """

    prob_negative_npv: Optional[float] = None
    prob_below_hurdle: Optional[float] = None
    worst_case_irr: Optional[float] = None
    max_drawdown: Optional[float] = None


@dataclass
class EquityPerformance:
    """
    Equity-focused KPI structure for results, dashboards, and PE comparables.
    """

    equity_irr: Optional[float] = None
    equity_npv: Optional[float] = None
    moic: Optional[float] = None
    dpi: Optional[float] = None
    rvpi: Optional[float] = None
    tvpi: Optional[float] = None
    annual_coc: List[float] = field(default_factory=list)
    average_coc: float = 0.0
    payback_period_years: Optional[float] = None
    downside: Optional[DownsideMetrics] = None


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity/Tornado/Spider/Pareto/Advanced Analytics (Phase 3)
# ═════════════════════════════════════════════════════════════════════════════


class ParameterRangeConfig(BaseModel):
    """
    Sensitivity parameter range configuration.

    Validates parameter sweep configurations loaded from YAML files.
    Uses Pydantic v2 for robust input validation at config boundaries.

    Used by tornado, two-way, optimization, MC parameter loaders, etc.

    Attributes:
        variable_name: Dot-separated parameter path (e.g., project.capex_usd_per_kw)
        base_value: Base case value for the parameter (must be > 0)
        low_pct: Lower bound as percentage change (-50 to 0)
        high_pct: Upper bound as percentage change (0 to 100)
        steps: Number of steps in sensitivity sweep (3 to 20)

    Example:
        >>> config = ParameterRangeConfig(
        ...     variable_name="project.capex_usd_per_kw",
        ...     base_value=850.0,
        ...     low_pct=-20.0,
        ...     high_pct=20.0,
        ...     steps=5
        ... )
        >>> config.low_value
        680.0
        >>> config.high_value
        1020.0

    Validation Rules:
        - variable_name: Non-empty string
        - base_value: Must be strictly positive (> 0)
        - low_pct: Between -50 and 0 (inclusive)
        - high_pct: Between 0 and 100 (inclusive)
        - high_pct must be >= abs(low_pct) for meaningful range
        - steps: Between 3 and 20 (inclusive)
    """

    model_config = ConfigDict(
        validate_default=True,
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=False,
    )

    variable_name: str = Field(
        ...,
        min_length=1,
        description="Parameter to sweep (dot-separated path e.g. project.capex_usd_per_kw)",
    )

    base_value: float = Field(
        ...,
        description="Base case value (must be strictly positive > 0)",
    )

    @field_validator("base_value")
    @classmethod
    def validate_base_value(cls, v: float) -> float:
        """
        Ensure base_value is strictly positive (> 0).

        For financial models, zero or negative base values break sensitivity analysis:
            low_value = base_value * (1 + low_pct/100)
            high_value = base_value * (1 + high_pct/100)

        If base_value <= 0, the range becomes degenerate and meaningless.

        Args:
            v: The base_value to validate

        Returns:
            The validated value (unchanged)

        Raises:
            ValueError: If v <= 0
        """
        if v <= 0:
            raise ValueError(f"base_value must be positive (> 0), got {v}")
        return v

    low_pct: float = Field(
        ...,
        ge=-50.0,
        le=0.0,
        description="Lower bound as percentage change (e.g., -20 for -20%)",
    )

    high_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Upper bound as percentage change (e.g., 20 for +20%)",
    )

    steps: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Number of steps in sensitivity sweep",
    )

    @field_validator("high_pct")
    @classmethod
    def validate_high_exceeds_low(cls, v: float, info: Any) -> float:
        """
        Ensure high_pct is at least as large as abs(low_pct).

        This ensures the sensitivity range is meaningful and symmetric.
        For example, high_pct=-20 and low_pct=-30 would be inverted and rejected.

        Allows symmetric ranges like low_pct=-20, high_pct=20.

        Args:
            v: The high_pct value
            info: Validation context with other field values

        Returns:
            The validated value (unchanged)

        Raises:
            ValueError: If v < abs(low_pct)
        """
        low_pct = info.data.get("low_pct")
        if low_pct is not None and v < abs(low_pct):
            raise ValueError(
                f"High bound ({v}%) must be at least {abs(low_pct)}% "
                f"(abs of low bound {low_pct}%)"
            )
        return v

    @property
    def low_value(self) -> float:
        """
        Calculate absolute low value from base and low_pct.

        Formula: base_value * (1 + low_pct/100)

        Example:
            >>> config = ParameterRangeConfig(
            ...     variable_name="test",
            ...     base_value=100.0,
            ...     low_pct=-20.0,
            ...     high_pct=20.0
            ... )
            >>> config.low_value
            80.0
        """
        return self.base_value * (1 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        """
        Calculate absolute high value from base and high_pct.

        Formula: base_value * (1 + high_pct/100)

        Example:
            >>> config = ParameterRangeConfig(
            ...     variable_name="test",
            ...     base_value=100.0,
            ...     low_pct=-20.0,
            ...     high_pct=20.0
            ... )
            >>> config.high_value
            120.0
        """
        return self.base_value * (1 + self.high_pct / 100.0)


@dataclass
class TornadoResult:
    """
    Single tornado sweep result row (for tables, export, ranking).

    Stores sensitivity analysis results for one parameter.
    Uses dataclass for performance (no validation overhead on results).

    Attributes:
        variable: Parameter name/identifier (e.g., "capex_usd_per_kw")
        base_irr: Base case IRR (or other metric)
        low_irr: IRR when parameter at low bound
        high_irr: IRR when parameter at high bound

    Properties:
        impact_abs: Absolute impact (|high_irr - low_irr|)
        impact_pct: Signed percentage impact relative to base

    Examples:
        >>> result = TornadoResult(
        ...     variable="capex",
        ...     base_irr=0.10,
        ...     low_irr=0.08,
        ...     high_irr=0.12,
        ... )
        >>> result.impact_abs
        0.04
        >>> result.impact_pct
        40.0

        Inverted case (high < low):

        >>> inv = TornadoResult(
        ...     variable="test",
        ...     base_irr=0.10,
        ...     low_irr=0.12,
        ...     high_irr=0.08,
        ... )
        >>> inv.impact_abs
        0.04          # magnitude stays positive
        >>> inv.impact_pct
        -40.0         # direction is negative

        NaN handling:

        >>> import numpy as np
        >>> nan_case = TornadoResult(
        ...     variable="test",
        ...     base_irr=0.10,
        ...     low_irr=np.nan,
        ...     high_irr=0.12,
        ... )
        >>> math.isnan(nan_case.impact_abs)
        True
        >>> math.isnan(nan_case.impact_pct)
        True
    """

    variable: str
    base_irr: float
    low_irr: float
    high_irr: float

    @property
    def impact_abs(self) -> float:
        """
        Absolute impact: |high_irr - low_irr|.

        - Always non-negative when inputs are finite.
        - Propagates NaN if either low_irr or high_irr is NaN.
        """
        delta = self.high_irr - self.low_irr

        # NaN check without extra imports
        if delta != delta:  # NaN is not equal to itself
            return float("nan")

        return float(abs(delta))

    @property
    def impact_pct(self) -> float:
        """
        Signed percentage impact relative to base_irr.

        - Direction comes from (high_irr - low_irr):
            * positive when high_irr > low_irr
            * negative when high_irr < low_irr
        - Returns 0.0 when base_irr == 0.0 (avoid division by zero).
        - Propagates NaN if any of base_irr, low_irr, high_irr is NaN.
        """
        # NaN propagation
        for v in (self.base_irr, self.low_irr, self.high_irr):
            if v != v:  # NaN check
                return float("nan")

        if self.base_irr == 0.0:
            return 0.0

        delta = self.high_irr - self.low_irr
        return float(delta / self.base_irr * 100.0)


@dataclass
class SensitivitySuite:
    """
    Complete tornado/sensitivity table, for export/analytics.

    Aggregates tornado analysis results for multiple parameters,
    ranks them by impact, and identifies top risk drivers.
    """

    tornado_results: List[TornadoResult]
    base_metric: float
    base_config_path: str
    metric: str


@dataclass
class BreakevenResult:
    """
    Result from breakeven solver ("what capex for IRR=12%?").

    Stores the solution and bracketing information.
    """

    variable: str
    breakeven_value: Optional[float]
    bracket: Tuple[float, float]
    status: str


@dataclass
class MultiMetricTornadoResult:
    """
    Multi-metric spider/radar tornado result (all KPI deltas for a driver).

    Extends single-metric tornado to track impact on multiple metrics
    (e.g., IRR, NPV, DSCR) for same parameter sweep.
    """

    variable: str
    label: str
    base_values: Dict[str, float]
    low_values: Dict[str, float]
    high_values: Dict[str, float]
    impacts: Dict[str, float]
    impact_dirs: Dict[str, int]


@dataclass
class MultiMetricSensitivitySuite:
    """
    Table of MultiMetricTornadoResult; for spider/radar, advanced analytics.
    """

    tornado_results: List[MultiMetricTornadoResult]
    base_metrics: Dict[str, float]
    base_config_path: str
    metrics: List[str]


@dataclass
class ParetoFrontierResult:
    """
    Results of multi-objective optimizer grid search (for efficient frontier/Pareto).

    Stores frontier points and objectives for Pareto optimization.
    """

    frontier_points: List[Dict[str, Any]]
    objectives: List[str]


@dataclass
class TailRiskMetrics:
    """
    Used by risk_metrics/stochastic overlays (VaR/CVaR/tail).

    Captures downside tail risk quantiles and breach probabilities.
    """

    var: float
    cvar: float
    p10: float
    p50: float
    p90: float
    breach_prob: float


# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo Distribution + Scenario Contracts (Phase 3 / 4)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class Distribution:
    """
    Probability distribution for MC—used in both MC config and derived parameter tools.

    This is intentionally a *thin* config object; all the heavy lifting happens
    in analytics.monte_carlo_v14._transform_to_distribution.

    Validation rules (mirrored in tests/analytics_layer/test_monte_carlo_v14.py):

    - dist_type == "normal":
        * std must be > 0
        * if std <= 0, raise ValueError with message containing
          "requires std > 0"

    - dist_type == "triangular":
        * min_val, mode, max_val must all be provided (not None)
        * must satisfy: min_val <= mode <= max_val
        * if not, raise ValueError with message containing
          "requires min <= mode <= max"

    - dist_type == "uniform":
        * min_val and max_val must be provided
        * must satisfy: min_val < max_val

    - dist_type == "lognormal":
        * std must be > 0 (same shape as normal)
    """

    variable_name: str
    dist_type: Literal["normal", "triangular", "uniform", "lognormal"]
    mean: float = 0.0
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mode: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate distribution parameters based on type."""
        dt = self.dist_type

        # ──── Normal ────────────────────────────────────────────────────────
        if dt == "normal":
            if self.std is None or self.std <= 0:
                raise ValueError("normal distribution requires std > 0")
            return

        # ──── Lognormal ─────────────────────────────────────────────────────
        if dt == "lognormal":
            if self.std is None or self.std <= 0:
                raise ValueError("lognormal distribution requires std > 0")
            return

        # ──── Triangular ────────────────────────────────────────────────────
        if dt == "triangular":
            if self.min_val is None or self.mode is None or self.max_val is None:
                raise ValueError("triangular distribution requires min <= mode <= max")

            if not (self.min_val <= self.mode <= self.max_val):
                raise ValueError("triangular distribution requires min <= mode <= max")
            return

        # ──── Uniform ───────────────────────────────────────────────────────
        if dt == "uniform":
            if self.min_val is None or self.max_val is None:
                raise ValueError("uniform distribution requires min and max")
            if not (self.min_val < self.max_val):
                raise ValueError("uniform distribution requires min < max")
            return

        # Defensive: if someone ever adds a new dist_type without updating
        # this method, fail loudly rather than silently accepting bad shapes.
        raise ValueError(f"Unsupported distribution type: {dt!r}")


@dataclass
class DerivedParameter:
    """
    Configuration for a *derived* MC parameter.

    Example: "solve for capex such that project_irr ~= target_distribution".

    Fields mirror what analytics.monte_carlo_v14 expects:
    - variable_name: dot-path in the scenario config to set
    - derive_from: identifier for the solver to use (registered via get_solver)
    - target_distribution: Distribution describing the target metric
    - solver_config: free-form dict passed to the solver
    - enabled: whether this derived parameter is active
    - description: human-readable note for docs/dashboards
    """

    variable_name: str
    derive_from: str
    target_distribution: Distribution
    solver_config: Dict[str, Any]
    enabled: bool = True
    description: str = ""


@dataclass
class MonteCarloScenario:
    """
    Monte Carlo scenario configuration.

    Each scenario bundles:
    - A friendly name
    - Optional description
    - A list of standard parameter Distributions
    - A list of DerivedParameters
    - An enabled flag (used when filtering scenarios to run)
    """

    name: str
    description: str
    standard_parameters: List[Distribution]
    derived_parameters: List[DerivedParameter]
    enabled: bool = True


@dataclass
class MonteCarloResult:
    """
    Aggregated Monte Carlo output for a single scenario.

    This matches the expectations in:
    - tests/analytics_layer/test_monte_carlo_v14.py
    - analytics.monte_carlo_v14._aggregate_results
    """

    iterations: int
    project_irr_mean: float
    project_irr_std: float
    project_irr_p10: float
    project_irr_p50: float
    project_irr_p90: float
    project_npv_mean: float
    project_npv_p10: float
    project_npv_p50: float
    project_npv_p90: float
    dscr_min_p10: float
    dscr_min_p50: float
    failed_iterations: int
    raw_results: List[Dict[str, float]] = field(default_factory=list)
    scenario_name: str = ""

    def success_rate(self) -> float:
        """
        Percentage of iterations that produced a usable result.

        The tests treat this as:
            100 * (iterations - failed_iterations) / iterations
        """
        if self.iterations <= 0:
            return 0.0
        successful = max(self.iterations - self.failed_iterations, 0)
        return 100.0 * successful / float(self.iterations)

    def probability_above_threshold(self, metric: str, threshold: float) -> float:
        """
        Percentage of raw_results where raw_result[metric] >= threshold.

        tests/analytics_layer/test_monte_carlo_v14.py builds a MonteCarloResult
        with a small raw_results list and expects a percentage based ONLY on
        that list, not on `iterations`.
        """
        if not self.raw_results:
            return 0.0

        total = len(self.raw_results)
        hits = 0
        for record in self.raw_results:
            value = record.get(metric)
            if value is not None and value >= threshold:
                hits += 1

        return 100.0 * hits / float(total)


# ═════════════════════════════════════════════════════════════════════════════
# Scenario Descriptor for Analytics/Workbook (Phase 4)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ScenarioDescriptor:
    """
    Canonical descriptor for a config/scenario. Used by analytics pipeline and reporting.
    """

    scenario_name: str
    config_path: str
    config: Dict[str, Any]

    def path(self) -> Path:
        """Return config_path as a Path object."""
        return Path(self.config_path)

    def to_dict(self) -> Dict[str, Any]:
        """Convert descriptor to plain dict for serialization."""
        return {
            "scenario_name": self.scenario_name,
            "config_path": self.config_path,
            "config": self.config,
        }


# ═════════════════════════════════════════════════════════════════════════════
# END OF CONTRACTS FILE
# ═════════════════════════════════════════════════════════════════════════════
#
# MAINTENANCE NOTES:
#
# 1. Update docstrings and comments when extending this file
# 2. All pipeline modules MUST import analytics results from here
# 3. New contract types should follow established patterns:
#    - Use @dataclass for performance-critical types
#    - Use BaseModel for config validation (pydantic v2)
#    - Add comprehensive docstrings with examples
#    - Include validation rules and error handling
# 4. Validators use @field_validator decorator (pydantic v2 pattern)
# 5. Keep this file focused on contracts only - no business logic
#
# ═════════════════════════════════════════════════════════════════════════════
# EOF - analytics/contractsv14.py
