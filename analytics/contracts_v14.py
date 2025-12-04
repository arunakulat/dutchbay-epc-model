#!/usr/bin/env python3
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

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

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

        dscr_series = list(debt_result.get("dscr_series") or [])
        years_below = 0
        first_breach: Optional[int] = None
        last_breach: Optional[int] = None

        for idx, value in enumerate(dscr_series):
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
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

        audit_status = str(debt_result.get("audit_status") or "REVIEW")

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

        # If everything looks fine but debt engine labelled REVIEW, we can
        # conservatively promote to PASS here based on covenant view.
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
    financing_cfg = (
        config.get("Financing_Terms")
        or config.get("financing")
        or config.get("finance")
        or {}
    )
    cov_cfg = (
        (financing_cfg.get("covenants") or {})
        if isinstance(financing_cfg, dict)
        else {}
    )

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

    This is the *only* place that should define how the cashflow engine is
    exposed to lenders, dashboards, and analytics. It wraps the raw
    `annual_rows` table from `cashflow_v14` and provides series that are
    explicitly labelled and easy to audit.

    All series are aligned by `years` and correspond to operating periods.
    Construction-phase flows should be handled separately by the debt engine.
    """

    # Core axis
    years: List[int]

    # Raw table from cashflow_v14.build_annual_rows (one dict per year)
    annual_rows: List[Dict[str, float]]

    # Generation
    gross_generation_kwh: List[float]
    net_generation_kwh: List[float]

    # Top-line and deductions
    revenue_lkr: List[float]
    statutory_deductions_lkr: List[float]
    opex_lkr: List[float]

    # Tax and CFADS
    pretax_cfads_lkr: List[float]
    tax_lkr: List[float]
    posttax_cfads_lkr: List[float]
    cfads_final_lkr: List[float]

    # Structural internals
    depreciation_lkr: List[float]
    interest_expense_lkr: List[float]
    taxable_income_lkr: List[float]

    # Risk haircut metadata
    risk_haircut_pct: float
    risk_haircut_amount_lkr: List[float]

    # FX metadata (optional: depends on config shape)
    fx_curve_lkr_per_usd: Optional[List[float]] = None

    # Hooks for diagnostics and flags
    notes: List[str] = field(default_factory=list)
    flags: Dict[str, bool] = field(default_factory=dict)

    def as_dict_rows(self) -> List[Dict[str, float]]:
        """
        Return a shallow copy of the underlying annual rows for tabular export.

        This is intentionally simple: dashboards and Excel exporters can use
        this when they want the familiar year-by-year table.
        """
        return list(self.annual_rows)


def build_cashflow_result_from_annual_rows(
    config: Mapping[str, Any],
    annual_rows: Sequence[Mapping[str, Any]],
    fx_curve_lkr_per_usd: Optional[Sequence[float]] = None,
) -> CashflowResult:
    """
    Construct a CashflowResult from the raw annual_rows table produced by
    the cashflow engine, plus the original config.

    This keeps the contracts layer independent of the finance module
    (no direct import of cashflow_v14) and avoids recomputing cashflows.
    """
    # Years
    years: List[int] = [
        int(row.get("year", i + 1)) for i, row in enumerate(annual_rows)
    ]

    # Generation
    gross_generation_kwh = [float(row.get("gross_kwh", 0.0)) for row in annual_rows]
    net_generation_kwh = [float(row.get("net_kwh", 0.0)) for row in annual_rows]

    # Top-line and deductions
    revenue_lkr = [float(row.get("revenue_lkr", 0.0)) for row in annual_rows]
    statutory_deductions_lkr = [
        float(row.get("total_statutory_deductions", 0.0)) for row in annual_rows
    ]
    opex_lkr = [float(row.get("opex_lkr", 0.0)) for row in annual_rows]

    # Tax and CFADS
    pretax_cfads_lkr = [float(row.get("pretax_cfads", 0.0)) for row in annual_rows]
    tax_lkr = [float(row.get("tax", 0.0)) for row in annual_rows]
    posttax_cfads_lkr = [float(row.get("posttax_cfads", 0.0)) for row in annual_rows]
    cfads_final_lkr = [float(row.get("cfads_final_lkr", 0.0)) for row in annual_rows]

    # Structural internals
    depreciation_lkr = [
        float(row.get("total_depreciation", 0.0)) for row in annual_rows
    ]
    interest_expense_lkr = [
        float(row.get("interest_expense_lkr", 0.0)) for row in annual_rows
    ]
    taxable_income_lkr = [float(row.get("taxable_income", 0.0)) for row in annual_rows]

    # Risk haircut
    risk_cfg = config.get("risk_adjustment") or config.get("risk") or {}
    risk_haircut_pct = float(
        risk_cfg.get("cfads_haircut_pct") or risk_cfg.get("risk_haircut_pct") or 0.0
    )
    risk_haircut_amount_lkr = [
        float(row.get("risk_haircut_amount", 0.0)) for row in annual_rows
    ]

    fx_list: Optional[List[float]] = (
        list(fx_curve_lkr_per_usd) if fx_curve_lkr_per_usd is not None else None
    )

    return CashflowResult(
        years=years,
        annual_rows=[dict(row) for row in annual_rows],
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

    This is the canonical, lender/deck-facing result contract for a single
    v14 scenario. It combines:

    - Core project metrics (NPV, IRR, DSCR profile, max debt)
    - WACC result (including prudential rate)
    - Equity performance overlay (when available)
    - Debt profile (tranche-level) and covenant snapshot
    - Raw engine outputs (config, annual rows, debt_result, kpis)

    Downstream consumers (dashboards, Excel exporters, lender reports) should
    prefer this struct rather than poking into raw dicts.
    """

    # Core ID / KPIs
    scenario_name: str
    config_path: str
    project_npv: float
    project_irr: float
    dscr_series: List[float]
    min_dscr: float
    max_debt_usd: float

    # WACC / discounting
    wacc: Optional[WaccResult] = None
    discount_rate_used: Optional[float] = None
    wacc_label: Optional[str] = None
    wacc_is_real: Optional[bool] = None

    # Engine + validation context
    validation_mode: str = "strict"
    config: Dict[str, Any] = field(default_factory=dict)
    annual_rows: Sequence[Dict[str, Any]] = field(default_factory=list)
    debt_result: Dict[str, Any] = field(default_factory=dict)
    kpis: Dict[str, Any] = field(default_factory=dict)
    cashflow: Optional["CashflowResult"] = None

    # Overlays (Phase 2 / 3)
    equity_performance: Optional["EquityPerformance"] = None
    debt_profile: Optional["TrancheDebtProfile"] = None
    debt_covenants: Optional["DebtCovenantSnapshot"] = None

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
            "Parameter to sweep (dot-separated path, " "e.g. project.capex_usd_per_kw)"
        ),
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
        """
        return self.base_value * (1 + self.low_pct / 100.0)

    @property
    def high_value(self) -> float:
        """
        Calculate absolute high value from base and high_pct.

        Formula: base_value * (1 + high_pct/100)
        """
        return self.base_value * (1 + self.high_pct / 100.0)


@dataclass
class TornadoResult:
    """
    Single tornado sweep result row (for tables, export, ranking).

    Stores sensitivity analysis results for one parameter.
    Uses dataclass for performance (no validation overhead on results).
    """

    variable: str
    base_irr: float
    low_irr: float
    high_irr: float

    @property
    def impact_abs(self) -> float:
        """
        Absolute magnitude of IRR movement, rounded for test stability.
        """
        delta = self.high_irr - self.low_irr
        if delta != delta:  # NaN check
            return float("nan")
        return round(abs(delta), 10)

    @property
    def impact_pct(self) -> float:
        """
        Signed percentage impact relative to base_irr.
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
    Used by risk_metrics/stochastic overlays (VaR/CVaR/tail).
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

        # Defensive
        raise ValueError(f"Unsupported distribution type: {dt!r}")


@dataclass
class DerivedParameter:
    """
    Configuration for a *derived* MC parameter.
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
        """
        if self.iterations <= 0:
            return 0.0
        successful = max(self.iterations - self.failed_iterations, 0)
        return 100.0 * successful / float(self.iterations)

    def probability_above_threshold(self, metric: str, threshold: float) -> float:
        """
        Percentage of raw_results where raw_result[metric] >= threshold.
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
    Canonical descriptor for a config/scenario. Used by analytics pipeline & reporting.
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
# EOF - analytics/contracts_v14.py
