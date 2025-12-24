from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from analytics.fx.fx_contracts import (
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
)

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     DUTCHBAY v14 DATA CONTRACTS                             ║
║                  (Fully Refactored with Pydantic V2)                        ║
║                                                                              ║
║  CESSPIT/CASPER/GWTF/CCCDIR Compliance:                                     ║
║  - Contract-first: All models explicitly typed                               ║
║  - Evidence-based: Validation rules from test requirements                   ║
║  - Scenario-stable: Frozen configs, reproducible outputs                     ║
║  - Config-driven: No hardcoded constants                                     ║
║                                                                              ║
║  All pipeline modules must import analytics results ONLY from here.          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# Contract version tracking
CASPER_CONTRACT_VERSION = "v1.0"

# ═════════════════════════════════════════════════════════════════════════════
# Covenant Breach Detection with Floating-Point Tolerance (Sprint 18 - Issue #4)
# ═════════════════════════════════════════════════════════════════════════════


def check_covenant_breach_with_tolerance(
    actual: float,
    threshold: float,
    tolerance_bps: int = 1,
    covenant_type: str = "floor",
) -> bool:
    """Check if covenant breaches threshold with floating-point tolerance.
    
    Prevents false breach warnings from floating-point rounding errors
    by applying industry-standard 1 basis point (0.01%) tolerance.
    
    Args:
        actual: Actual covenant metric value (e.g., DSCR = 1.299)
        threshold: Covenant threshold (e.g., 1.30 for DSCR floor)
        tolerance_bps: Tolerance in basis points (default 1bp = 0.01%)
        covenant_type: "floor" (minimum) or "ceiling" (maximum)
    
    Returns:
        True if covenant BREACHES (actual violates threshold beyond tolerance)
        False if covenant OK (actual within acceptable range)
    """
    # Input validation
    if tolerance_bps < 0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance_bps}bp")
    
    if covenant_type not in ("floor", "ceiling"):
        raise ValueError(
            f"covenant_type must be 'floor' or 'ceiling', got '{covenant_type}'"
        )
    
    # Convert basis points to absolute tolerance
    tolerance_abs = abs(threshold) * (tolerance_bps / 10000.0)
    
    # Floor covenant: breach if actual < threshold (allowing tolerance)
    if covenant_type == "floor":
        return actual < (threshold - tolerance_abs)
    
    # Ceiling covenant: breach if actual > threshold (allowing tolerance)
    else:
        return actual > (threshold + tolerance_abs)


# ═════════════════════════════════════════════════════════════════════════════
# Sensitivity Analysis Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class ShockSpec(BaseModel):
    """Individual parameter shock specification for sensitivity analysis."""
    
    model_config = ConfigDict(frozen=True)
    
    parameter: str = Field(description="Parameter name to shock")
    shocks: List[float] = Field(description="List of shock percentages as decimals")
    label: Optional[str] = Field(default=None, description="Display label")
    
    @field_validator("shocks")
    @classmethod
    def validate_shocks(cls, v: List[float]) -> List[float]:
        """Validate shock list is non-empty and reasonable."""
        if not v:
            raise ValueError("Shock list cannot be empty")
        if any(s < -1.0 or s > 5.0 for s in v):
            raise ValueError("Shock values must be in range [-1.0, 5.0]")
        return v
    
    @computed_field  # type: ignore[misc]
    @property
    def variablename(self) -> str:
        """Backward compatibility property."""
        return self.parameter
    
    @computed_field  # type: ignore[misc]
    @property
    def lowvalue(self) -> float:
        """Lowest shock value."""
        return min(self.shocks) if self.shocks else 0.0
    
    @computed_field  # type: ignore[misc]
    @property
    def highvalue(self) -> float:
        """Highest shock value."""
        return max(self.shocks) if self.shocks else 0.0
    
    @computed_field  # type: ignore[misc]
    @property
    def basevalue(self) -> float:
        """Base value (0.0 for relative shocks)."""
        return 0.0


class StandardShockLibrary:
    """Predefined library of standard sensitivity shocks."""
    
    @staticmethod
    def standard_shocks() -> List[ShockSpec]:
        """Return standard shock library."""
        return [
            ShockSpec(parameter="capex", shocks=[-0.10, -0.05, 0.05, 0.10], label="Capital Cost"),
            ShockSpec(parameter="tariff", shocks=[-0.10, -0.05, 0.05, 0.10], label="Tariff Rate"),
            ShockSpec(parameter="capacityfactor", shocks=[-0.10, -0.05, 0.05, 0.10], label="Capacity Factor"),
            ShockSpec(parameter="opex", shocks=[-0.10, -0.05, 0.05, 0.10], label="Operating Cost"),
            ShockSpec(parameter="discountrate", shocks=[-0.01, -0.005, 0.005, 0.01], label="Discount Rate"),
        ]


class ParameterRangeConfig(BaseModel):
    """Parameter shock configuration for sensitivity analysis."""
    
    model_config = ConfigDict(frozen=True)
    
    variablename: str = Field(description="Dotted path to parameter")
    basevalue: float = Field(description="Base case value")
    lowpct: float = Field(description="Low shock as %")
    highpct: float = Field(description="High shock as %")
    label: Optional[str] = Field(default=None, description="Display label")
    
    @field_validator("lowpct", "highpct")
    @classmethod
    def validate_shock_range(cls, v: float) -> float:
        """Shocks must be reasonable [-100 to 500%]."""
        if not -100.0 <= v <= 500.0:
            raise ValueError(f"Shock percentage must be in [-100, 500], got {v}")
        return v


class ShockResult(BaseModel):
    """Single shock result for one direction."""
    
    model_config = ConfigDict(frozen=True)
    
    lowcase: float = Field(description="Metric value at low shock")
    highcase: float = Field(description="Metric value at high shock")
    impact: float = Field(description="Absolute impact (high - low)")


class TornadoResult(BaseModel):
    """Single variable tornado sensitivity result."""
    
    model_config = ConfigDict(frozen=True)
    
    metricname: str = Field(description="Variable being shocked")
    basemetric: float = Field(description="Base case metric value")
    shockresults: List[ShockResult] = Field(description="Shock outcomes")
    label: Optional[str] = Field(default=None, description="Display label")
    impactabs: float = Field(default=0.0, description="Total impact magnitude")
    
    @computed_field
    @property
    def impact(self) -> float:
        """Computed impact from shock results."""
        if self.shockresults:
            return self.shockresults[0].impact
        return 0.0


class SensitivitySuite(BaseModel):
    """Complete sensitivity analysis suite."""
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    metric: str = Field(description="Target metric analyzed")
    baseconfigpath: str = Field(description="Base scenario path")
    tornadoresults: List[TornadoResult] = Field(description="Tornado results")
    basekpis: Optional[Dict[str, float]] = Field(default=None)


class SensitivityRequest(BaseModel):
    """Request structure for sensitivity analysis."""
    
    model_config = ConfigDict(frozen=True)
    
    baseconfigpath: str
    parameters: List[ParameterRangeConfig]
    metric: Optional[str] = Field(default="projectirr")


class BreakevenResult(BaseModel):
    """Breakeven parameter solution."""
    
    model_config = ConfigDict(frozen=True)
    
    variable: str
    targetmetric: str
    targetvalue: float
    breakevenvalue: float
    status: str = Field(default="success")
    bracket: Tuple[float, float] = Field(default=(0.0, 0.0))


class MultiMetricTornadoResult(BaseModel):
    """Container for multiple TornadoResult objects keyed by metric name."""
    
    model_config = ConfigDict(frozen=True)
    
    results: Dict[str, TornadoResult] = Field(
        default_factory=dict,
        description="Tornado results keyed by metric name"
    )
    
    def asdict(self) -> Dict[str, dict]:
        """Stable dump surface for exporters/payloads."""
        return {k: v.model_dump() for k, v in self.results.items()}
    
    @classmethod
    def from_mapping(cls, results: Mapping[str, TornadoResult]) -> "MultiMetricTornadoResult":
        """Create from mapping of metric name to TornadoResult."""
        return cls(results=dict(results))


class MultiMetricSensitivitySuite(BaseModel):
    """Container for multiple SensitivitySuite objects keyed by metric name."""
    
    model_config = ConfigDict(frozen=True)
    
    suites: Dict[str, SensitivitySuite] = Field(
        default_factory=dict,
        description="Sensitivity suites keyed by metric name"
    )
    
    def asdict(self) -> Dict[str, dict]:
        """Stable dump surface for exporters/payloads."""
        return {k: v.model_dump() for k, v in self.suites.items()}
    
    @classmethod
    def from_mapping(cls, suites: Mapping[str, SensitivitySuite]) -> "MultiMetricSensitivitySuite":
        """Create from mapping of metric name to SensitivitySuite."""
        return cls(suites=dict(suites))


# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo Contracts (Pydantic V2)
# ═════════════════════════════════════════════════════════════════════════════


class Distribution(BaseModel):
    """Distribution specification for Monte Carlo sampling."""
    
    model_config = ConfigDict(frozen=True)
    
    variablename: str = Field(description="Variable name")
    disttype: Literal["normal", "triangular", "uniform", "lognormal"] = Field(
        description="Distribution type"
    )
    mean: Optional[float] = Field(default=None, description="Mean for normal/lognormal")
    std: Optional[float] = Field(default=None, description="Standard deviation")
    minval: Optional[float] = Field(default=None, description="Minimum value")
    maxval: Optional[float] = Field(default=None, description="Maximum value")
    mode: Optional[float] = Field(default=None, description="Mode for triangular")
    description: Optional[str] = Field(default=None, description="Description")


class DerivedParameter(BaseModel):
    """Derived parameter computed from other sampled parameters."""
    
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Derived parameter name")
    formula: str = Field(description="Python expression to compute value")
    dependson: List[str] = Field(
        default_factory=list,
        description="List of parameter names this depends on"
    )


class MonteCarloScenario(BaseModel):
    """Monte Carlo scenario configuration."""
    
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(description="Scenario name")
    niterations: int = Field(gt=0, description="Number of iterations")
    distributions: List[Distribution] = Field(
        default_factory=list,
        description="Parameter distributions"
    )
    derivedparameters: List[DerivedParameter] = Field(
        default_factory=list,
        description="Derived parameters"
    )
    seed: Optional[int] = Field(default=None, description="Random seed")
    samplingmethod: str = Field(default="lhs", description="Sampling method (lhs/random)")


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation result with lender-grade analytics support."""
    
    model_config = ConfigDict(frozen=True)
    
    summary: Dict[str, Any] = Field(
        description="Aggregated statistics per metric (mean, std, percentiles)"
    )
    metadata: Dict[str, Any] = Field(
        description="Execution metadata (ntrials, seed, correlationenabled, etc.)"
    )
    trials: Optional[Dict[str, List[float]]] = Field(
        default=None,
        description="Raw per-trial arrays for each metric (REQUIRED for lender analytics)"
    )
    percentiles: Optional[Dict[int, Dict[str, float]]] = Field(
        default=None,
        description="Percentile lookup table {50: {'dscrmin': 1.45, ...}, 90: {...}}"
    )
    
    @field_validator("trials")
    @classmethod
    def validate_trials_consistent(cls, v: Optional[Dict[str, List[float]]]) -> Optional[Dict[str, List[float]]]:
        """Validate all trial arrays have same length."""
        if v is None:
            return v
        if not v:
            return v
        
        lengths = {k: len(arr) for k, arr in v.items()}
        unique_lengths = set(lengths.values())
        
        if len(unique_lengths) > 1:
            raise ValueError(
                f"All trial arrays must have same length. Got {lengths}"
            )
        
        return v


# ═════════════════════════════════════════════════════════════════════════════
# CASPER Result Container
# ═════════════════════════════════════════════════════════════════════════════


class CasperResult(BaseModel):
    """CASPER unified analysis result."""
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    scenario: Optional[str] = Field(default=None)
    baselinekpis: Dict[str, float] = Field(default_factory=dict)
    sensitivities: Optional[Any] = Field(default=None)
    montecarlo: Optional[Any] = Field(default=None)
    multitechgenerationbreakdown: Optional[Any] = Field(default=None)
    
    @computed_field
    @property
    def contractversion(self) -> str:
        """Contract version - computed property."""
        return CASPER_CONTRACT_VERSION


# ═════════════════════════════════════════════════════════════════════════════
# WACC, Debt, Cashflow, Equity Contracts (Dataclasses)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class WaccComponents:
    """WACC calculation component breakdown."""
    mode: str
    waccnominal: float
    waccreal: Optional[float]
    waccprudential: float
    riskfreerate: float
    marketriskpremium: float
    assetbeta: float
    targetdebttoequity: float
    targetdebttovalue: float
    targetequitytovalue: float
    costofdebtpretax: float
    costofdebtaftertax: float
    equitybetalevered: float
    costofequity: float
    taxrate: float
    inflationrate: Optional[float]
    prudentialspreadbps: int


@dataclass(frozen=True)
class WaccResult:
    """Complete WACC result including base and prudential valuations."""
    base: WaccComponents
    prudentialrate: Optional[float] = None
    prudentialnpv: Optional[float] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrancheDebtProfile:
    """Aggregate per-tranche debt profile."""
    constructionyears: int = 0
    tenoryears: int = 0
    timelineperiods: int = 0
    totaldebt: float = 0.0
    totalidc: float = 0.0
    lkrprincipal: float = 0.0
    usdprincipal: float = 0.0
    dfiprincipal: float = 0.0
    lkridc: float = 0.0
    usdidc: float = 0.0
    dfiidc: float = 0.0
    lkrrate: Optional[float] = None
    usdrate: Optional[float] = None
    dfirate: Optional[float] = None
    interestonlyyears: int = 0
    amortizationstyle: str = "sculpted"
    dscrtarget: Optional[float] = None


@dataclass(frozen=True)
class DebtCovenantSnapshot:
    """Covenant snapshot for a single debt case (DSCR, LLCR, PLCR)."""
    dscrmin: float
    dscrthreshold: float
    yearsbelowthreshold: int
    firstbreachyear: Optional[int] = None
    lastbreachyear: Optional[int] = None
    balloonflag: bool = False
    balloonremaining: float = 0.0
    llcr: Optional[float] = None
    plcr: Optional[float] = None
    llcrthreshold: Optional[float] = None
    plcrthreshold: Optional[float] = None
    fxmin: Optional[float] = None
    fxmax: Optional[float] = None
    fxavg: Optional[float] = None
    notes: str = ""
    auditstatus: str = "REVIEW"
    
    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CashflowResult:
    """Canonical multi-year project cashflow surface in LKR."""
    years: List[int]
    annualrows: List[Dict[str, float]]
    grossgenerationkwh: List[float]
    netgenerationkwh: List[float]
    revenuelkr: List[float]
    statutorydeductionslkr: List[float]
    opexlkr: List[float]
    pretaxcfadslkr: List[float]
    taxlkr: List[float]
    posttaxcfadslkr: List[float]
    cfadsfinallkr: List[float]
    depreciationlkr: List[float]
    interestexpenselkr: List[float]
    taxableincomelkr: List[float]
    riskhaircutpct: float
    riskhaircutamountlkr: List[float]
    fxcurvelkrperusd: Optional[List[float]] = None
    notes: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)
    
    def asdict_rows(self) -> List[Dict[str, float]]:
        return list(self.annualrows)


@dataclass(frozen=True)
class DownsideMetrics:
    """Downside risk metrics for equity performance."""
    probnegativenpv: Optional[float] = None
    probbelowhurdle: Optional[float] = None
    worstcaseirr: Optional[float] = None
    maxdrawdown: Optional[float] = None


@dataclass(frozen=True)
class EquityPerformance:
    """Equity performance metrics."""
    equityirr: Optional[float] = None
    equitynpv: Optional[float] = None
    moic: Optional[float] = None
    dpi: Optional[float] = None
    rvpi: Optional[float] = None
    tvpi: Optional[float] = None
    annualcoc: List[float] = field(default_factory=list)
    averagecoc: float = 0.0
    paybackperiodyears: Optional[float] = None
    downside: Optional[DownsideMetrics] = None


@dataclass
class ScenarioResult:
    """Complete scenario evaluation result with WACC and full outputs."""
    scenarioname: str
    configpath: str
    projectnpv: float
    projectirr: float
    dscrseries: List[float]
    mindscr: float
    maxdebtusd: float
    wacc: Optional[WaccResult] = None
    discountrateused: Optional[float] = None
    wacclabel: Optional[str] = None
    waccisreal: Optional[bool] = None
    
    # FX structured blocks and curves
    fxblock: Optional[FXStructuredBlock] = None
    fxcurve: Optional[FXCurveOutput] = None
    fxriskprofile: Optional[FXRiskProfile] = None
    
    validationmode: str = "strict"
    config: Dict[str, Any] = field(default_factory=dict)
    annualrows: Sequence[Dict[str, Any]] = field(default_factory=list)
    debtresult: Dict[str, Any] = field(default_factory=dict)
    kpis: Dict[str, Any] = field(default_factory=dict)
    cashflow: Optional[CashflowResult] = None
    equityperformance: Optional[EquityPerformance] = None
    debtprofile: Optional[TrancheDebtProfile] = None
    debtcovenants: Optional[DebtCovenantSnapshot] = None
    
    def asdict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "scenarioname": self.scenarioname,
            "configpath": self.configpath,
            "projectnpv": self.projectnpv,
            "projectirr": self.projectirr,
            "mindscr": self.mindscr,
            "maxdebtusd": self.maxdebtusd,
        }
        data.update(self.kpis)
        return data


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "check_covenant_breach_with_tolerance",
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    # Sensitivity contracts
    "ShockSpec",
    "StandardShockLibrary",
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "MultiMetricSensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "ShockResult",
    # Monte Carlo contracts
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    # CASPER
    "CasperResult",
    # Debt & Cashflow contracts
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    "CashflowResult",
    "EquityPerformance",
    "DownsideMetrics",
]
