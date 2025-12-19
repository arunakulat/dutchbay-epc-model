"""FX Structured Block Contracts (v14R6).

Provides canonical FX data structures for multi-currency project scenarios.
All structures follow CESSPIT (immutable, validated) and CCCDIR (fully commented)
standards for production use.

Key Structures:
  - FXStructuredBlock: Configuration and snapshot of FX strategy.
  - FXCurveOutput: Time-series FX rates (LKR/USD, LKR/CNY, etc.).
  - FXRiskProfile: Lender-grade FX risk metrics (VaR, CVaR, concentration).
  - FXVolumetry: Debt and revenue exposure by currency and time.

Integration:
  Wired into ScenarioResult.fx_block, ScenarioResult.fx_curve,
  and ScenarioResult.fx_risk_profile during pipeline_v14 execution.

Usage Pattern (GWTF):
  1. Create FXStructuredBlock from config or default strategy
  2. Run compute_fx_curve() to generate time-series projection
  3. Compute risk metrics via compute_fx_risk_profile()
  4. Attach all three to ScenarioResult for export/dashboarding
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# ═════════════════════════════════════════════════════════════════════════════
# FXVolumetry – Debt and Revenue Exposure by Currency and Time
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FXVolumetry:
    """Per-period (annual) FX exposure snapshot.

    Captures total debt and revenue exposure by currency for a given period.
    Used to compute portfolio-level FX risk (VaR, CVaR, concentration).

    Fields:
        period: Period index (0 = Year 0, 1 = Year 1, etc.)
        total_debt_lkr: Total debt outstanding in LKR at end of period.
        total_debt_usd: Total debt outstanding in USD at end of period.
        total_debt_cny: Total debt outstanding in CNY at end of period (if applicable).
        revenue_lkr: Annual revenue in LKR during period.
        revenue_usd: Annual revenue in USD during period (if any).
        interest_lkr: Annual interest expense in LKR.
        principal_lkr: Annual principal repayment in LKR.
    """

    period: int
    total_debt_lkr: float
    total_debt_usd: float
    total_debt_cny: float = 0.0
    revenue_lkr: float = 0.0
    revenue_usd: float = 0.0
    interest_lkr: float = 0.0
    principal_lkr: float = 0.0

    @property
    def total_usd_exposure_equivalent(self) -> float:
        """Sum of all debt and debt service (interest + principal) in USD equiv.

        Approximation: assumes all LKR denominations remain at spot rate
        (not risk-adjusted). For risk analysis, use FXRiskProfile instead.
        """
        # Assume ~300 LKR/USD at computation time; actual rates from fx_curve
        assumed_spot_lkr_usd = 300.0
        lkr_in_usd = (self.total_debt_lkr + self.interest_lkr) / assumed_spot_lkr_usd
        return self.total_debt_usd + lkr_in_usd


# ═════════════════════════════════════════════════════════════════════════════
# FXCurveOutput – Time-Series FX Rates
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FXCurveOutput:
    """Time-series FX rate projections (canonical format).

    Stores annual FX rates for each currency pair required by the model.
    All rates are spot rates (not forward); used for P&L conversion and risk.

    Fields:
        years: Annual year labels [0, 1, 2, ..., n_periods-1].
        lkr_usd: Annual LKR/USD rates (e.g., [300, 302, 305, ...]).
        lkr_cny: Annual LKR/CNY rates (optional, for DFI tranches).
        lkr_eur: Annual LKR/EUR rates (optional, if EUR debt exists).
        lkr_gbp: Annual LKR/GBP rates (optional).
        source: Description of curve source ('base_case', 'stress', 'ppp_adjusted').
        notes: Free-form documentation (e.g., 'historical_avg_volatility_15pct').
    """

    years: List[int]
    lkr_usd: List[float]  # LKR per USD
    lkr_cny: Optional[List[float]] = None
    lkr_eur: Optional[List[float]] = None
    lkr_gbp: Optional[List[float]] = None
    source: str = "base_case"
    notes: str = ""

    def __post_init__(self) -> None:
        """CESSPIT Validation: Ensure curve consistency."""
        if len(self.years) != len(self.lkr_usd):
            raise ValueError(
                f"FXCurveOutput: years and lkr_usd must have same length. "
                f"Got len(years)={len(self.years)}, len(lkr_usd)={len(self.lkr_usd)}"
            )

        # Validate optional curves if present
        for curve_name, curve_data in [
            ("lkr_cny", self.lkr_cny),
            ("lkr_eur", self.lkr_eur),
            ("lkr_gbp", self.lkr_gbp),
        ]:
            if curve_data is not None:
                if len(curve_data) != len(self.years):
                    raise ValueError(
                        f"FXCurveOutput: {curve_name} must have same length as years. "
                        f"Got len({curve_name})={len(curve_data)}, len(years)={len(self.years)}"
                    )

        # Validate all rates are positive
        for idx, rate in enumerate(self.lkr_usd):
            if rate <= 0:
                raise ValueError(f"FXCurveOutput: lkr_usd[{idx}]={rate} must be > 0")

    def get_rate(self, year: int, pair: str = "lkr_usd") -> float:
        """Retrieve FX rate for a given year and currency pair.

        Args:
            year: Year index (0-based).
            pair: Currency pair name ('lkr_usd', 'lkr_cny', 'lkr_eur', 'lkr_gbp').

        Returns:
            Float rate (e.g., 300.5 for LKR/USD).

        Raises:
            IndexError if year not in curve.
            ValueError if pair not available.
        """
        if year not in self.years:
            raise IndexError(f"FXCurveOutput: year {year} not in curve {self.years}")

        idx = self.years.index(year)

        if pair == "lkr_usd":
            return self.lkr_usd[idx]
        elif pair == "lkr_cny":
            if self.lkr_cny is None:
                raise ValueError(f"FXCurveOutput: pair '{pair}' not available in curve")
            return self.lkr_cny[idx]
        elif pair == "lkr_eur":
            if self.lkr_eur is None:
                raise ValueError(f"FXCurveOutput: pair '{pair}' not available in curve")
            return self.lkr_eur[idx]
        elif pair == "lkr_gbp":
            if self.lkr_gbp is None:
                raise ValueError(f"FXCurveOutput: pair '{pair}' not available in curve")
            return self.lkr_gbp[idx]
        else:
            raise ValueError(f"FXCurveOutput: unknown currency pair '{pair}'")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for export/dashboarding."""
        return {
            "years": self.years,
            "lkr_usd": self.lkr_usd,
            "lkr_cny": self.lkr_cny,
            "lkr_eur": self.lkr_eur,
            "lkr_gbp": self.lkr_gbp,
            "source": self.source,
            "notes": self.notes,
        }


# ═════════════════════════════════════════════════════════════════════════════
# FXRiskProfile – Lender-Grade FX Risk Metrics
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FXRiskProfile:
    """Lender-grade FX risk assessment (CASPER output).

    Provides VaR, CVaR, and portfolio concentration metrics for:
    - Debt service (principal + interest) by currency
    - Revenue exposure by currency
    - Correlation break risk (e.g., LKR weakening while local rates rise)

    Used in credit memos and covenant dashboards to communicate FX risk
    to lenders and equity investors.

    Fields:
        var_95_usd_million: 95% VaR of portfolio (USD millions).
        cvar_95_usd_million: 95% CVaR (expected shortfall) of portfolio.
        debt_lkr_pct: Percentage of debt in LKR.
        debt_usd_pct: Percentage of debt in USD.
        debt_cny_pct: Percentage of debt in CNY (if applicable).
        debt_concentration_hhi: Herfindahl index of debt concentration (0 = uniform, 1 = all in one).
        revenues_lkr_pct: Percentage of revenues in LKR.
        correlation_shock_scenario: Description of stress test applied (e.g., 'LKR -15% with rate shock').
        worst_case_year: Year of maximum stress (from simulation).
        recovery_years_to_1x_llcr: Years until LLCR recovers to 1.0x (from stress year).
    """

    var_95_usd_million: float
    cvar_95_usd_million: float
    debt_lkr_pct: float
    debt_usd_pct: float
    debt_cny_pct: float = 0.0
    debt_concentration_hhi: float = 0.5  # Default: moderate concentration
    revenues_lkr_pct: float = 100.0
    correlation_shock_scenario: str = ""
    worst_case_year: Optional[int] = None
    recovery_years_to_1x_llcr: Optional[int] = None

    def __post_init__(self) -> None:
        """CESSPIT Validation: Ensure risk profile coherence."""
        # Check debt percentages sum to ~100%
        debt_sum = self.debt_lkr_pct + self.debt_usd_pct + self.debt_cny_pct
        if not (95.0 <= debt_sum <= 105.0):
            raise ValueError(
                f"FXRiskProfile: debt percentages must sum to ~100%. "
                f"Got {debt_sum}% (LKR={self.debt_lkr_pct}, USD={self.debt_usd_pct}, CNY={self.debt_cny_pct})"
            )

        # Check VaR < CVaR
        if self.var_95_usd_million > self.cvar_95_usd_million:
            raise ValueError(
                f"FXRiskProfile: VaR ({self.var_95_usd_million}) must be <= CVaR ({self.cvar_95_usd_million})"
            )

        # Check HHI in valid range [0, 1]
        if not (0.0 <= self.debt_concentration_hhi <= 1.0):
            raise ValueError(
                f"FXRiskProfile: debt_concentration_hhi must be in [0, 1]. Got {self.debt_concentration_hhi}"
            )

    def is_high_risk(self, var_threshold_usd_million: float = 5.0) -> bool:
        """Convenience flag: True if VaR exceeds risk threshold."""
        return self.var_95_usd_million > var_threshold_usd_million

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for dashboards."""
        return {
            "var_95_usd_million": round(self.var_95_usd_million, 3),
            "cvar_95_usd_million": round(self.cvar_95_usd_million, 3),
            "debt_lkr_pct": round(self.debt_lkr_pct, 1),
            "debt_usd_pct": round(self.debt_usd_pct, 1),
            "debt_cny_pct": round(self.debt_cny_pct, 1),
            "debt_concentration_hhi": round(self.debt_concentration_hhi, 3),
            "revenues_lkr_pct": round(self.revenues_lkr_pct, 1),
            "correlation_shock_scenario": self.correlation_shock_scenario,
            "worst_case_year": self.worst_case_year,
            "recovery_years_to_1x_llcr": self.recovery_years_to_1x_llcr,
            "is_high_risk": self.is_high_risk(),
        }


# ═════════════════════════════════════════════════════════════════════════════
# FXStructuredBlock – Primary FX Configuration and Snapshot
# ═════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class FXStructuredBlock:
    """Complete FX strategy and execution snapshot for a scenario.

    Combines configuration (how FX risk is managed) with volumetry
    (actual debt/revenue by currency) and risk metrics.

    This is the PRIMARY FX artifact attached to ScenarioResult;
    FXCurveOutput and FXRiskProfile provide supporting detail.

    Fields:
        strategy: FX risk management approach ('natural_hedge', 'fixed_ccy', 'hedged', 'blended').
        base_currency: Scenario base currency (usually 'USD' for NPV).
        reporting_currency: Currency for P&L reporting (usually same as base_currency).
        volumetry: List of FXVolumetry snapshots (one per period).
        debt_tranches: Dict mapping tranche name to currency (e.g., {'LKR_Tranche': 'LKR'}).
        revenue_currencies: List of currencies in which revenues are generated.
        fx_match_ratio: Percentage of debt matched to revenue currency (0-100).
        hedging_coverage_pct: Percentage of FX exposure covered via forwards/hedges.
        notes: Documentation of any special FX assumptions.
    """

    strategy: Literal["natural_hedge", "fixed_ccy", "hedged", "blended"] = "blended"
    base_currency: str = "USD"
    reporting_currency: str = "USD"
    volumetry: List[FXVolumetry] = field(default_factory=list)
    debt_tranches: Dict[str, str] = field(default_factory=dict)
    revenue_currencies: List[str] = field(default_factory=lambda: ["LKR"])
    fx_match_ratio: float = 0.0  # Percentage [0, 100]
    hedging_coverage_pct: float = 0.0  # Percentage [0, 100]
    notes: str = ""

    def __post_init__(self) -> None:
        """CESSPIT Validation: Ensure FX block coherence."""
        # Validate percentages
        if not (0.0 <= self.fx_match_ratio <= 100.0):
            raise ValueError(
                f"FXStructuredBlock: fx_match_ratio must be in [0, 100]. Got {self.fx_match_ratio}"
            )

        if not (0.0 <= self.hedging_coverage_pct <= 100.0):
            raise ValueError(
                f"FXStructuredBlock: hedging_coverage_pct must be in [0, 100]. Got {self.hedging_coverage_pct}"
            )

        # Validate base and reporting currencies
        valid_currencies = {"USD", "LKR", "CNY", "EUR", "GBP"}
        if self.base_currency not in valid_currencies:
            raise ValueError(
                f"FXStructuredBlock: base_currency '{self.base_currency}' not in {valid_currencies}"
            )

        if self.reporting_currency not in valid_currencies:
            raise ValueError(
                f"FXStructuredBlock: reporting_currency '{self.reporting_currency}' not in {valid_currencies}"
            )

    def total_periods(self) -> int:
        """Return number of periods in volumetry."""
        return len(self.volumetry)

    def total_debt_usd_equivalent(self, spot_rate_lkr_usd: float = 300.0) -> float:
        """Approximate total debt in USD equivalent at spot rate.

        Args:
            spot_rate_lkr_usd: Exchange rate for LKR/USD (default: 300.0).

        Returns:
            Sum of all debt in USD equivalent (approx).
        """
        if not self.volumetry:
            return 0.0

        # Use final period debt (end of loan tenor)
        final_period = self.volumetry[-1]
        lkr_in_usd = final_period.total_debt_lkr / spot_rate_lkr_usd
        return final_period.total_debt_usd + lkr_in_usd + final_period.total_debt_cny

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict for export/dashboarding."""
        return {
            "strategy": self.strategy,
            "base_currency": self.base_currency,
            "reporting_currency": self.reporting_currency,
            "volumetry": [
                {
                    "period": v.period,
                    "total_debt_lkr": round(v.total_debt_lkr, 2),
                    "total_debt_usd": round(v.total_debt_usd, 2),
                    "total_debt_cny": round(v.total_debt_cny, 2),
                    "revenue_lkr": round(v.revenue_lkr, 2),
                    "revenue_usd": round(v.revenue_usd, 2),
                    "interest_lkr": round(v.interest_lkr, 2),
                    "principal_lkr": round(v.principal_lkr, 2),
                }
                for v in self.volumetry
            ],
            "debt_tranches": self.debt_tranches,
            "revenue_currencies": self.revenue_currencies,
            "fx_match_ratio": round(self.fx_match_ratio, 1),
            "hedging_coverage_pct": round(self.hedging_coverage_pct, 1),
            "notes": self.notes,
        }


__all__ = [
    "FXVolumetry",
    "FXCurveOutput",
    "FXRiskProfile",
    "FXStructuredBlock",
]

# EOF - analytics/fx/fx_contracts.py


# Backward compatibility stub (Sprint 12 Pydantic v2 migration)
from pydantic import BaseModel, ConfigDict


class FXMonteCarloConfig(BaseModel):
    """Legacy stub for FX Monte Carlo test compatibility."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)
