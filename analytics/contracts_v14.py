from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     DUTCHBAY v14 DATA CONTRACTS                             ║
║                  (Fully Refactored with Validators)                         ║
║                                                                              ║
║  All canonical data structures (dataclasses, pydantic models) used for:      ║
║  - Valuation, WACC, and scenario results                                     ║
║  - Equity metrics, downside risk                                             ║
║  - Sensitivity/tornado/optimizer/Monte Carlo surfaces for analytics          ║
║  - Ready for export, reporting, dashboard use                                ║
║                                                                              ║
║  ALWAYS update comments and docstrings in this file for future maintainers.  ║
║  All pipeline modules must import *analytics results* only from here.        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

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


# ═════════════════════════════════════════════════════════════════════════════
# Debt profile & covenant snapshot (Phase 1 – lender view)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class TrancheDebtProfile:
    """
    Aggregate per-tranche debt profile for a scenario.

    This is the *lender-facing* snapshot that sits on ScenarioResult and
    feeds dashboards / credit memos. It is intentionally summary-level and
    currency-agnostic in structure, while still exposing LKR / USD / DFI
    breakdowns that match the v14 debt engine.

    All values are expected to be in scenario base currency (e.g. USD),
    with LKR/DFI components converted upstream where appropriate.
    """

    # Timeline
    construction_years: int = 0
    tenor_years: int = 0
    timeline_periods: int = 0

    # Aggregate totals
    total_debt: float = 0.0
    total_idc: float = 0.0

    # Per-tranche principals (after IDC capitalisation)
    lkr_principal: float = 0.0
    usd_principal: float = 0.0
    dfi_principal: float = 0.0

    # Per-tranche IDC capitalised during construction
    lkr_idc: float = 0.0
    usd_idc: float = 0.0
    dfi_idc: float = 0.0

    # Optional cost-of-debt inputs (nominal, after fees; decimals)
    lkr_rate: Optional[float] = None
    usd_rate: Optional[float] = None
    dfi_rate: Optional[float] = None

    # Optional structure metadata
    interest_only_years: int = 0
    amortization_style: str = "sculpted"  # or "annuity", "fixed"
    dscr_target: Optional[float] = None


@dataclass
class DebtCovenantSnapshot:
    """
    Covenant snapshot for a single debt case.

    This is the CFA / lender-facing summary used in dashboards and reports.
    It captures:

    - DSCR profile vs minimum covenant threshold
    - Balloon risk
    - LLCR / PLCR vs target thresholds
    - FX profile for FX-related covenant diagnostics
    """

    # DSCR profile
    dscr_min: float
    dscr_threshold: float
    years_below_threshold: int
    first_breach_year: Optional[int]
    last_breach_year: Optional[int]

    # Balloon / residual
    balloon_flag: bool
    balloon_remaining: float

    # Coverage ratios
    llcr: Optional[float] = None
    plcr: Optional[float] = None
    llcr_threshold: Optional[float] = None
    plcr_threshold: Optional[float] = None

    # FX profile
    fx_min: Optional[float] = None
    fx_max: Optional[float] = None
    fx_avg: Optional[float] = None

    # Meta
    notes: str = ""
    audit_status: str = "REVIEW"

    @classmethod
    def from_debt_result(
        cls,
        *,
        debt_result: Mapping[str, Any],
        dscr_threshold: float,
        llcr_threshold: Optional[float] = None,
        plcr_threshold: Optional[float] = None,
    ) -> "DebtCovenantSnapshot":
        """
        Build snapshot from the v14 debt surface (plan_debt output).
        """
        dscr_min = float(
            debt_result.get("min_dscr") or debt_result.get("dscr_min") or 0.0
        )

        dscr_series_raw = debt_result.get("dscr_series") or []
        dscr_series: List[float] = []
        for value in dscr_series_raw:
            try:
                dscr_series.append(float(value))
            except (TypeError, ValueError):
                continue

        years_below = 0
        first_breach: Optional[int] = None
        last_breach: Optional[int] = None

        for idx, v in enumerate(dscr_series):
            if v == float("inf") or v != v:  # inf / NaN
                continue
            if v < dscr_threshold:
                years_below += 1
                if first_breach is None:
                    first_breach = idx
                last_breach = idx

        balloon_remaining = float(debt_result.get("balloon_remaining") or 0.0)
        balloon_flag = balloon_remaining > 1e-6

        # LLCR / PLCR from debt surface
        llcr_val_raw = debt_result.get("llcr")
        plcr_val_raw = debt_result.get("plcr")

        llcr_val = float(llcr_val_raw) if llcr_val_raw is not None else None
        plcr_val = float(plcr_val_raw) if plcr_val_raw is not None else None

        # FX surfaces
        fx_min_raw = debt_result.get("fx_min")
        fx_max_raw = debt_result.get("fx_max")
        fx_avg_raw = debt_result.get("fx_avg")

        fx_min = float(fx_min_raw) if fx_min_raw is not None else None
        fx_max = float(fx_max_raw) if fx_max_raw is not None else None
        fx_avg = float(fx_avg_raw) if fx_avg_raw is not None else None

        audit_status_raw = debt_result.get("audit_status") or "REVIEW"
        audit_status = str(audit_status_raw)

        notes_parts: List[str] = []
        if years_below > 0:
            notes_parts.append(
                f"DSCR breaches in {years_below} period(s) "
                f"(first={first_breach}, last={last_breach})."
            )
        if (
            llcr_val is not None
            and llcr_threshold is not None
            and llcr_val < llcr_threshold
        ):
            notes_parts.append(
                f"LLCR {llcr_val:.2f} below threshold {llcr_threshold:.2f}."
            )
        if (
            plcr_val is not None
            and plcr_threshold is not None
            and plcr_val < plcr_threshold
        ):
            notes_parts.append(
                f"PLCR {plcr_val:.2f} below threshold {plcr_threshold:.2f}."
            )

        notes = " ".join(notes_parts)

        if not notes and audit_status == "REVIEW":
            audit_status = "PASS"

        return cls(
            dscr_min=dscr_min,
            dscr_threshold=dscr_threshold,
            years_below_threshold=years_below,
            first_breach_year=first_breach,
            last_breach_year=last_breach,
            balloon_flag=balloon_flag,
            balloon_remaining=balloon_remaining,
            llcr=llcr_val,
            plcr=plcr_val,
            llcr_threshold=llcr_threshold,
            plcr_threshold=plcr_threshold,
            fx_min=fx_min,
            fx_max=fx_max,
            fx_avg=fx_avg,
            notes=notes,
            audit_status=audit_status,
        )

    def as_dict(self) -> Dict[str, Any]:
        """
        JSON/CLI friendly view. Used by run_full_pipeline_v14 when building
        scenario_result["debt_covenants"].
        """
        return {
            "dscr_min": self.dscr_min,
            "dscr_threshold": self.dscr_threshold,
            "years_below_threshold": self.years_below_threshold,
            "first_breach_year": self.first_breach_year,
            "last_breach_year": self.last_breach_year,
            "balloon_flag": self.balloon_flag,
            "balloon_remaining": self.balloon_remaining,
            "llcr": self.llcr,
            "plcr": self.plcr,
            "llcr_threshold": self.llcr_threshold,
            "plcr_threshold": self.plcr_threshold,
            "fx_min": self.fx_min,
            "fx_max": self.fx_max,
            "fx_avg": self.fx_avg,
            "notes": self.notes,
            "audit_status": self.audit_status,
        }


def _build_debt_covenant_snapshot(
    config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
) -> DebtCovenantSnapshot:
    """
    Convenience wrapper: read thresholds from config, then build snapshot
    from the v14 debt surface (plan_debt output).
    """
    financing_cfg_raw = (
        config.get("Financing_Terms")
        or config.get("financing")
        or config.get("finance")
        or {}
    )

    financing_cfg: Mapping[str, Any]
    if isinstance(financing_cfg_raw, Mapping):
        financing_cfg = financing_cfg_raw
    else:
        financing_cfg = {}

    cov_cfg_raw = financing_cfg.get("covenants") or {}
    cov_cfg: Mapping[str, Any] = cov_cfg_raw if isinstance(cov_cfg_raw, Mapping) else {}

    dscr_threshold = float(
        cov_cfg.get("min_dscr")
        or financing_cfg.get("target_dscr")
        or debt_result.get("dscr_threshold")
        or 1.30
    )

    llcr_threshold_raw = cov_cfg.get("llcr_min")
    plcr_threshold_raw = cov_cfg.get("plcr_min")

    llcr_threshold = (
        float(llcr_threshold_raw) if llcr_threshold_raw is not None else None
    )
    plcr_threshold = (
        float(plcr_threshold_raw) if plcr_threshold_raw is not None else None
    )

    return DebtCovenantSnapshot.from_debt_result(
        debt_result=debt_result,
        dscr_threshold=dscr_threshold,
        llcr_threshold=llcr_threshold,
        plcr_threshold=plcr_threshold,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CashflowResult – canonical cashflow surface (Phase 1.5)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class CashflowResult:
    """
    Canonical multi-year project cashflow surface in LKR for a single v14 run.
    """

    years: List[int]
    annual_rows: List[Dict[str, float]]

    gross_generation_kwh: List[float]
    net_generation_kwh: List[float]

    revenue_lkr: List[float]
    statutory_deductions_lkr: List[float]
    opex_lkr: List[float]

    pretax_cfads_lkr: List[float]
    tax_lkr: List[float]
    posttax_cfads_lkr: List[float]
    cfads_final_lkr: List[float]

    depreciation_lkr: List[float]
    interest_expense_lkr: List[float]
    taxable_income_lkr: List[float]

    risk_haircut_pct: float
    risk_haircut_amount_lkr: List[float]

    fx_curve_lkr_per_usd: Optional[List[float]] = None

    notes: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)

    def as_dict_rows(self) -> List[Dict[str, float]]:
        return list(self.annual_rows)


def build_cashflow_result_from_annual_rows(
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    fx_curve_lkr_per_usd: Optional[Sequence[float]] = None,
) -> CashflowResult:
    years: List[int] = [
        int(row.get("year", index + 1)) for index, row in enumerate(annual_rows)
    ]

    gross_generation_kwh = [float(row.get("gross_kwh", 0.0)) for row in annual_rows]
    net_generation_kwh = [float(row.get("net_kwh", 0.0)) for row in annual_rows]

    revenue_lkr = [float(row.get("revenue_lkr", 0.0)) for row in annual_rows]
    statutory_deductions_lkr = [
        float(row.get("total_statutory_deductions_lkr", 0.0)) for row in annual_rows
    ]
    opex_lkr = [float(row.get("opex_lkr", 0.0)) for row in annual_rows]

    pretax_cfads_lkr = [float(row.get("pretax_cfads_lkr", 0.0)) for row in annual_rows]
    tax_lkr = [float(row.get("tax_lkr", 0.0)) for row in annual_rows]
    posttax_cfads_lkr = [
        float(row.get("posttax_cfads_lkr", 0.0)) for row in annual_rows
    ]
    cfads_final_lkr = [float(row.get("cfads_final_lkr", 0.0)) for row in annual_rows]

    depreciation_lkr = [
        float(row.get("total_depreciation_lkr", 0.0)) for row in annual_rows
    ]
    interest_expense_lkr = [
        float(row.get("interest_expense_lkr", 0.0)) for row in annual_rows
    ]
    taxable_income_lkr = [
        float(row.get("taxable_income_lkr", 0.0)) for row in annual_rows
    ]

    risk_cfg_raw = config.get("risk_adjustment") or config.get("risk") or {}
    risk_cfg: Mapping[str, Any] = (
        risk_cfg_raw if isinstance(risk_cfg_raw, Mapping) else {}
    )

    risk_haircut_pct = float(
        risk_cfg.get("cfads_haircut_pct") or risk_cfg.get("risk_haircut_pct") or 0.0
    )
    risk_haircut_amount_lkr = [
        float(row.get("risk_haircut_amount_lkr", 0.0)) for row in annual_rows
    ]

    fx_list: Optional[List[float]] = (
        list(fx_curve_lkr_per_usd) if fx_curve_lkr_per_usd is not None else None
    )

    return CashflowResult(
        years=years,
        annual_rows=[
            {k: float(v) for k, v in row.items() if isinstance(v, (int, float))}
            for row in annual_rows
        ],
        gross_generation_kwh=gross_generation_kwh,
        net_generation_kwh=net_generation_kwh,
        revenue_lkr=revenue_lkr,
        statutory_deductions_lkr=statutory_deductions_lkr,
        opex_lkr=opex_lkr,
        pretax_cfads_lkr=pretax_cfads_lkr,
        tax_lkr=tax_lkr,
        posttax_cfads_lkr=posttax_cfads_lkr,
        cfads_final_lkr=cfads_final_lkr,
        depreciation_lkr=depreciation_lkr,
        interest_expense_lkr=interest_expense_lkr,
        taxable_income_lkr=taxable_income_lkr,
        risk_haircut_pct=risk_haircut_pct,
        risk_haircut_amount_lkr=risk_haircut_amount_lkr,
        fx_curve_lkr_per_usd=fx_list,
    )


# ═════════════════════════════════════════════════════════════════════════════
# ScenarioResult – canonical scenario surface
# ═════════════════════════════════════════════════════════════════════════════


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
    cashflow: Optional["CashflowResult"] = None

    equity_performance: Optional["EquityPerformance"] = None
    debt_profile: Optional["TrancheDebtProfile"] = None
    debt_covenants: Optional["DebtCovenantSnapshot"] = None

    def as_dict(self) -> Dict[str, Any]:
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
        description=(
            "Parameter to sweep (dot-separated path, e.g. project.capex_usd_per_kw)"
        ),
    )

    base_value: float = Field(
        ...,
        description="Base case value (must be strictly positive > 0)",
    )

    @field_validator("base_value")
    @classmethod
    def validate_base_value(cls, v: float) -> float:
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
        low_pct = None
        if hasattr(info, "data"):
            low_pct = getattr(info, "data", {}).get("low_pct")
        if low_pct is not None and v < abs(float(low_pct)):
            raise ValueError(
                f"High bound ({v}%) must be at least {abs(float(low_pct))}% "
                f"(abs of low bound {low_pct}%)"
            )
        return v

    @property
    def low_value(self) -> float:
        return self.base_value * (1 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        return self.base_value * (1 + self.high_pct / 100.0)


@dataclass
class TornadoResult:
    """
    Single tornado sweep result row (for tables, export, ranking).
    """

    variable: str
    base_irr: float
    low_irr: float
    high_irr: float

    @property
    def impact_abs(self) -> float:
        delta = self.high_irr - self.low_irr
        if delta != delta:
            return float("nan")
        return round(abs(delta), 10)

    @property
    def impact_pct(self) -> float:
        for v in (self.base_irr, self.low_irr, self.high_irr):
            if v != v:
                return float("nan")
        if self.base_irr == 0.0:
            return 0.0
        delta = self.high_irr - self.low_irr
        return float(delta / self.base_irr * 100.0)


@dataclass
class SensitivitySuite:
    """
    Complete tornado/sensitivity table, for export/analytics.
    """

    tornado_results: List[TornadoResult]
    base_metric: float
    base_config_path: str
    metric: str


@dataclass
class BreakevenResult:
    """
    Result from breakeven solver ("what capex for IRR=12%?").
    """

    variable: str
    breakeven_value: Optional[float]
    bracket: Tuple[float, float]
    status: str


@dataclass
class MultiMetricTornadoResult:
    """
    Multi-metric spider/radar tornado result (all KPI deltas for a driver).
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
    """

    frontier_points: List[Dict[str, Any]]
    objectives: List[str]


@dataclass
class TailRiskMetrics:
    """
    Tail-risk metrics for a single distribution (metric, scenario, or covenant).
    """

    var: float
    cvar: float
    p10: float
    p50: float
    p90: float
    breach_prob: float


@dataclass(frozen=True)
class TailRiskSnapshot:
    """
    Aggregated tail-risk view for a single KPI and confidence level.
    """

    metric: str
    confidence: float
    var: float
    cvar: float
    p10: float
    p50: float
    p90: float
    breach_probability: float


# ═════════════════════════════════════════════════════════════════════════════
# SENS-001 Shock Contracts (Sensitivity Analysis)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ShockSpec:
    """
    [SENS-001] Specification for a single variable shock.
    CCCDIR Compliant: Immutable, Typed, Validated.
    """

    variable_name: str  # e.g., "project.capex_usd_per_kw"
    base_value: float  # e.g., 1200.0
    low_pct: float  # e.g., -10.0
    high_pct: float  # e.g., +10.0
    label: Optional[str] = None

    def __post_init__(self) -> None:
        """CESSPIT Fail-Fast Validation."""
        if self.base_value <= 0:
            raise ValueError(f"ShockSpec: base_value must be > 0, got {self.base_value}")
        if self.low_pct > 0:
            raise ValueError(f"ShockSpec: low_pct must be <= 0, got {self.low_pct}")
        if self.high_pct < 0:
            raise ValueError(f"ShockSpec: high_pct must be >= 0, got {self.high_pct}")

    @property
    def low_value(self) -> float:
        return self.base_value * (1 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        return self.base_value * (1 + self.high_pct / 100.0)

    @property
    def display_label(self) -> str:
        return self.label or self.variable_name


@dataclass(frozen=True)
class ShockResult:
    """
    [SENS-001] Result of a single shock applied to a metric.
    Stores absolute values AND computed deltas for Tornado charts.
    """

    variable_name: str
    metric_name: str
    base_value: float  # Input parameter base
    low_value: float  # Input parameter low
    high_value: float  # Input parameter high

    base_metric: float  # Output metric base (e.g., IRR 12%)
    low_metric: float  # Output metric at low input
    high_metric: float  # Output metric at high input

    label: Optional[str] = None

    @property
    def impact(self) -> float:
        """Absolute magnitude of change (High - Low)."""
        return abs(self.high_metric - self.low_metric)

    @property
    def direction(self) -> Literal["positive", "negative", "neutral", "mixed"]:
        """Direction of correlation between Input and Output."""
        delta_input = self.high_value - self.low_value
        delta_metric = self.high_metric - self.low_metric

        if abs(delta_metric) < 1e-9:
            return "neutral"

        # If input increases and metric increases -> positive correlation
        return "positive" if (delta_metric * delta_input) > 0 else "negative"

    @property
    def sensitivity(self) -> float:
        """Elasticity: % change in metric / % change in input."""
        if self.base_value == 0 or self.base_metric == 0:
            return 0.0

        pct_change_input = (self.high_value - self.low_value) / self.base_value
        pct_change_metric = (self.high_metric - self.low_metric) / self.base_metric

        if abs(pct_change_input) < 1e-9:
            return 0.0

        return pct_change_metric / pct_change_input


@dataclass(frozen=True)
class SensitivitySuiteWithShocks:
    """
    [SENS-001] Collection of ShockResults for a scenario (Tornado).
    """

    metric_name: str
    base_metric_value: float
    scenario_name: str
    shock_results: List[ShockResult]
    analysis_timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def tornado_ranking(self) -> List[ShockResult]:
        """Return shocks sorted by impact (descending)."""
        return sorted(self.shock_results, key=lambda x: x.impact, reverse=True)


# ═════════════════════════════════════════════════════════════════════════════
# Monte Carlo Distribution + Scenario Contracts (Phase 3 / 4)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass
class Distribution:
    """
    Probability distribution for Monte Carlo parameters.
    """

    variable_name: str
    dist_type: Literal["normal", "triangular", "uniform", "lognormal"]

    mean: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mode: Optional[float] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        dt = self.dist_type

        if dt == "normal":
            if self.std is None or self.std <= 0:
                raise ValueError("normal distribution requires std > 0")
            return

        if dt == "lognormal":
            if self.std is None or self.std <= 0:
                raise ValueError("lognormal distribution requires std > 0")
            return

        if dt == "triangular":
            if self.min_val is None or self.mode is None or self.max_val is None:
                raise ValueError("triangular distribution requires min <= mode <= max")
            if not (self.min_val <= self.mode <= self.max_val):
                raise ValueError("triangular distribution requires min <= mode <= max")
            return

        if dt == "uniform":
            if self.min_val is None or self.max_val is None:
                raise ValueError("uniform distribution requires min < max")
            if not (self.min_val < self.max_val):
                raise ValueError("uniform distribution requires min < max")
            return

        raise ValueError(f"Unsupported distribution type: {dt!r}")


@dataclass
class DerivedParameter:
    """
    Configuration for a *derived* Monte Carlo parameter.
    """

    variable_name: str
    derive_from: str
    target_distribution: Distribution
    solver_config: Dict[str, Any]
    enabled: bool = True
    description: str = ""


@dataclass(init=False)
class MonteCarloScenario:
    """
    Monte Carlo scenario configuration (engine-agnostic).
    """

    name: str
    description: str
    standard_params: List[Distribution]
    derived_params: List[DerivedParameter]
    iterations: int
    enabled: bool

    def __init__(
        self,
        name: str,
        description: str = "",
        standard_params: Optional[List[Distribution]] = None,
        derived_params: Optional[List[DerivedParameter]] = None,
        *,
        standard_parameters: Optional[List[Distribution]] = None,
        derived_parameters: Optional[List[DerivedParameter]] = None,
        iterations: int = 1000,
        enabled: bool = True,
    ) -> None:
        if standard_params is not None and standard_parameters is not None:
            raise TypeError(
                "Provide either 'standard_params' or 'standard_parameters', not both."
            )
        if derived_params is not None and derived_parameters is not None:
            raise TypeError(
                "Provide either 'derived_params' or 'derived_parameters', not both."
            )

        if standard_params is None:
            standard_params = standard_parameters or []
        if derived_params is None:
            derived_params = derived_parameters or []

        self.name = name
        self.description = description
        self.standard_params = list(standard_params)
        self.derived_params = list(derived_params)
        self.iterations = iterations
        self.enabled = enabled

    @property
    def standard_parameters(self) -> List[Distribution]:
        return self.standard_params

    @property
    def derived_parameters(self) -> List[DerivedParameter]:
        return self.derived_params


@dataclass
class MonteCarloResult:
    """
    Aggregated Monte Carlo output for a single scenario.
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
    raw_results: Optional[List[Dict[str, float]]] = None
    scenario_name: Optional[str] = None

    project_irr_se: Optional[float] = None
    project_npv_se: Optional[float] = None
    dscr_min_se: Optional[float] = None

    def success_rate(self) -> float:
        if self.iterations <= 0:
            return 0.0
        successful = max(self.iterations - max(self.failed_iterations, 0), 0)
        return (successful / float(self.iterations)) * 100.0

    def probability_above_threshold(self, metric_name: str, threshold: float) -> float:
        if not self.raw_results:
            return 0.0

        hits = 0
        total = 0

        for row in self.raw_results:
            value = row.get(metric_name)
            if value is None:
                continue
            total += 1
            if value >= threshold:
                hits += 1

        if total == 0:
            return 0.0

        return 100.0 * hits / float(total)


# ═════════════════════════════════════════════════════════════════════════════
# Scenario Descriptor for Analytics/Workbook (Phase 4)
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ScenarioDescriptor:
    """
    Canonical descriptor for a config/scenario.
    """

    scenario_name: str
    config_path: str
    config: Dict[str, Any]

    def path(self) -> Path:
        return Path(self.config_path)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "config_path": self.config_path,
            "config": self.config,
        }


# ═════════════════════════════════════════════════════════════════════════════
# Generation & CASPER Aggregation Contracts
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class GenerationProfile:
    """
    Single-technology generation and CFADS snapshot.
    """

    technology: str
    annual_aep_kwh: float
    annual_cfads_usd: float
    availability_pct: float | None = None
    losses_breakdown: Mapping[str, float] | None = None


@dataclass(frozen=True)
class MultiTechGenerationResult:
    """
    Aggregated generation view across multiple technologies.
    """

    total_aep_kwh: float
    total_cfads_usd: float
    technologies: Mapping[str, GenerationProfile]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_aep_kwh": self.total_aep_kwh,
            "total_cfads_usd": self.total_cfads_usd,
            "technologies": {
                tech: {
                    "technology": profile.technology,
                    "annual_aep_kwh": profile.annual_aep_kwh,
                    "annual_cfads_usd": profile.annual_cfads_usd,
                    "availability_pct": profile.availability_pct,
                    "losses_breakdown": (
                        dict(profile.losses_breakdown)
                        if profile.losses_breakdown is not None
                        else None
                    ),
                }
                for tech, profile in self.technologies.items()
            },
        }


@dataclass(frozen=True)
class TechnologyBreakdown:
    """
    Per-technology KPI breakdown for lender / investor visibility.
    """

    technology: str
    share_of_capex_pct: float | None = None
    share_of_cfads_pct: float | None = None
    share_of_aep_pct: float | None = None
    notes: str | None = None


# CASPER / GWTF JSON contract version.
# This identifier is surfaced in CASPER payloads and must be treated
# as a frozen, test-guarded contract string.
CASPER_CONTRACT_VERSION = "casper_result_v1"


@dataclass(frozen=True)
class CasperResult:
    """
    High-level, JSON-friendly result container for CASPER / GWTF flows.

    This mirrors the JSON contract emitted by CASPER payload builders:

      - scenario           -> slender ScenarioResult descriptor
      - baseline_kpis      -> flat KPI map (IRR, DSCR, NPV, etc.)
      - sensitivities      -> SensitivitySuite (tornado) or None
      - monte_carlo        -> MonteCarloResult or None
      - generation         -> MultiTechGenerationResult or None
      - multi_tech_generation_breakdown
                            -> list[TechnologyBreakdown] or None
      - metadata           -> small JSON-safe extras

    The `contract_version` field exposes the CASPER JSON contract version
    and is pinned by tests (CASPER_CONTRACT_VERSION).
    """

    # Core surfaces
    scenario: ScenarioResult | None
    baseline_kpis: Dict[str, float]

    # Optional analytics surfaces
    sensitivities: SensitivitySuite | None = None
    monte_carlo: MonteCarloResult | None = None

    # Multi-technology view
    generation: MultiTechGenerationResult | None = None
    multi_tech_generation_breakdown: list[TechnologyBreakdown] | None = None

    # Free-form metadata (CASPER run IDs, tail-risk tables, notes, etc.)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Frozen contract version string
    contract_version: str = CASPER_CONTRACT_VERSION

    @property
    def kpis(self) -> Dict[str, float]:
        """
        Backwards-compatible alias for baseline_kpis.

        External callers should prefer baseline_kpis; kpis is kept
        for older code that accessed CasperResult.kpis directly.
        """
        return self.baseline_kpis

    @property
    def sensitivity(self) -> SensitivitySuite | None:
        """
        Backwards-compatible singular alias for sensitivities.
        """
        return self.sensitivities

    @property
    def technology_breakdown(self) -> list[TechnologyBreakdown] | None:
        """
        Alias for multi_tech_generation_breakdown to keep JSON and Python
        naming aligned.
        """
        return self.multi_tech_generation_breakdown


# ═════════════════════════════════════════════════════════════════════════════
# CASPER payload helper (JSON-safe)
# ═════════════════════════════════════════════════════════════════════════════


def build_casper_payload(
    *,
    scenario: ScenarioResult,
    baseline_kpis: Mapping[str, float] | None = None,
    sensitivities: SensitivitySuite | None = None,
    monte_carlo: MonteCarloResult | None = None,
    multi_tech_generation_breakdown: MultiTechGenerationResult | None = None,
    technology_breakdown: Sequence[TechnologyBreakdown] | None = None,
    metadata: Mapping[str, Any] | None = None,
    tail_risk_snapshots: Mapping[str, TailRiskSnapshot] | None = None,
) -> Dict[str, Any]:
    """
    Build a JSON-safe CASPER payload for dashboards and lender reports.

    This is the *only* function that should be used by UIs / APIs when they
    want a serialisable view of a v14 scenario + analytics stack.

    All numbers are left in native units; callers are responsible for any
    currency/scale transformations they need.

    CESSPIT / CASPER notes
    ----------------------
    - Contract-explicit: tail-risk summaries flow through TailRiskSnapshot.
    - Evidenced: summaries are expected to be derived from Monte Carlo samples.
    - Scenario-stable: same config + seed => same TailRiskSnapshot.
    """
    # --- Scenario / baseline KPIs ------------------------------------------------
    scenario_dict = scenario.as_dict()
    baseline_kpis_dict: Dict[str, float] = {}
    if baseline_kpis is not None:
        baseline_kpis_dict = {str(k): float(v) for k, v in baseline_kpis.items()}

    payload: Dict[str, Any] = {
        "contract_version": CASPER_CONTRACT_VERSION,
        "scenario": scenario_dict,
        "baseline_kpis": baseline_kpis_dict,
    }

    # --- Sensitivity / tornado (optional) ----------------------------------------
    if sensitivities is not None:
        tornado_rows: list[Dict[str, Any]] = []
        for row in sensitivities.tornado_results:
            tornado_rows.append(
                {
                    "variable": row.variable,
                    "base_irr": float(row.base_irr),
                    "low_irr": float(row.low_irr),
                    "high_irr": float(row.high_irr),
                    "impact_abs": float(row.impact_abs),
                    "impact_pct": float(row.impact_pct),
                }
            )

        payload["sensitivity"] = {
            "metric": sensitivities.metric,
            "base_metric": float(sensitivities.base_metric),
            "base_config_path": sensitivities.base_config_path,
            "tornado": tornado_rows,
        }

    # --- Monte Carlo (optional) --------------------------------------------------
    if monte_carlo is not None:
        mc = monte_carlo
        payload["monte_carlo"] = {
            "iterations": int(mc.iterations),
            "failed_iterations": int(mc.failed_iterations),
            "success_rate": float(mc.success_rate()),
            "project_irr": {
                "mean": float(mc.project_irr_mean),
                "std": float(mc.project_irr_std),
                "p10": float(mc.project_irr_p10),
                "p50": float(mc.project_irr_p50),
                "p90": float(mc.project_irr_p90),
                "se": None if mc.project_irr_se is None else float(mc.project_irr_se),
            },
            "project_npv": {
                "mean": float(mc.project_npv_mean),
                "p10": float(mc.project_npv_p10),
                "p50": float(mc.project_npv_p50),
                "p90": float(mc.project_npv_p90),
                "se": None if mc.project_npv_se is None else float(mc.project_npv_se),
            },
            "dscr_min": {
                "p10": float(mc.dscr_min_p10),
                "p50": float(mc.dscr_min_p50),
                "se": None if mc.dscr_min_se is None else float(mc.dscr_min_se),
            },
        }

    # --- Generation / technology breakdown (optional) ----------------------------
    if multi_tech_generation_breakdown is not None:
        payload["generation"] = multi_tech_generation_breakdown.to_dict()

    if technology_breakdown is not None:
        payload["technology_breakdown"] = [asdict(tb) for tb in technology_breakdown]

    # --- Tail-risk summary (optional, CASPER / lender-facing) --------------------
    # Expectation: tail_risk_snapshots is built from MC samples via a dedicated
    # helper (e.g. in sensitivity_tail_risk) and passed in explicitly.
    if tail_risk_snapshots is not None:
        tail_risk_block: Dict[str, Any] = {}
        for metric, snapshot in tail_risk_snapshots.items():
            tail_risk_block[metric] = {
                "metric": snapshot.metric,
                "confidence": float(snapshot.confidence),
                "var": float(snapshot.var),
                "cvar": float(snapshot.cvar),
                "p10": float(snapshot.p10),
                "p50": float(snapshot.p50),
                "p90": float(snapshot.p90),
                "breach_probability": float(snapshot.breach_probability),
            }

        if tail_risk_block:
            payload["tail_risk"] = tail_risk_block

    # --- Metadata (optional, including full tail-risk tables) --------------------
    if metadata is not None:
        payload["metadata"] = {str(k): v for k, v in metadata.items()}

    return payload


# ═════════════════════════════════════════════════════════════════════════════
# Public export surface
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    # WACC / lender stack
    "WaccComponents",
    "WaccResult",
    "TrancheDebtProfile",
    "DebtCovenantSnapshot",
    # Cashflow + scenario
    "CashflowResult",
    "ScenarioResult",
    "ScenarioDescriptor",
    # Equity / downside
    "DownsideMetrics",
    "EquityPerformance",
    # Sensitivity / analytics
    "ParameterRangeConfig",
    "TornadoResult",
    "SensitivitySuite",
    "BreakevenResult",
    "MultiMetricTornadoResult",
    "MultiMetricSensitivitySuite",
    "ParetoFrontierResult",
    "TailRiskMetrics",
    "TailRiskSnapshot",
    # SENS-001 Shock Contracts
    "ShockSpec",
    "ShockResult",
    "SensitivitySuiteWithShocks",
    # Monte Carlo
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    # Generation / CASPER
    "GenerationProfile",
    "MultiTechGenerationResult",
    "TechnologyBreakdown",
    "CasperResult",
    "CASPER_CONTRACT_VERSION",
    # CASPER helpers
    "build_casper_payload",
]

# EOF - analytics/contracts_v14.py
