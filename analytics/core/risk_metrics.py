"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   DUTCHBAY V14 - RISK METRICS MODULE                         ║
║              Tail Risk Analytics (VaR, CVaR, Downside Risk)                  ║
║                                                                              ║
║  CASPER Compliance: Contract-first with Pydantic V2 outputs                  ║
║  CESSPIT Compliance: Config-driven risk parameters                           ║
║  GWTF Compliance: Evidence-based, reproducible analytics                     ║
║  CCCDIR Compliance: Single responsibility - risk metrics only                ║
║                                                                              ║
║  Author: DutchBay Analytics Team                                             ║
║  Version: 2.0.0 (Pydantic V2 Migration - Sprint 15)                          ║
║  Last Updated: 2025-12-21                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

__version__ = "2.0.0"
__author__ = "DutchBay Analytics Team"

logger = logging.getLogger("dutchbay.analytics.core.risk_metrics")

# ═════════════════════════════════════════════════════════════════════════════
# PYDANTIC V2 CONTRACTS (CASPER Compliance)
# ═════════════════════════════════════════════════════════════════════════════


class RiskConfig(BaseModel):
    """
    Risk analysis configuration.

    CESSPIT: All risk parameters from config, no hardcoded defaults.
    """

    model_config = ConfigDict(frozen=True)

    confidence_level: float = Field(
        ge=0.0, le=1.0, description="Confidence level for VaR/CVaR (e.g., 0.95)"
    )
    target_return: float = Field(
        description="Target return threshold for downside risk (decimal)"
    )

    # Covenant thresholds
    min_dscr: float = Field(gt=0.0, description="Minimum DSCR threshold")
    min_llcr: float = Field(gt=0.0, description="Minimum LLCR threshold")
    min_plcr: float = Field(gt=0.0, description="Minimum PLCR threshold")

    @field_validator("confidence_level")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Confidence level must be reasonable (typically 0.90-0.99)."""
        if not 0.80 <= v <= 0.99:
            logger.warning("Unusual confidence level %s (typical: 0.90-0.99)", v)
        return v


class VaRCVaRResult(BaseModel):
    """
    Value-at-Risk and Conditional VaR result.

    CASPER: Frozen, typed contract for risk metrics.
    """

    model_config = ConfigDict(frozen=True)

    var: float = Field(description="Value at Risk at confidence level")
    cvar: float = Field(
        description="Conditional VaR == Expected Shortfall (ES): mean of the tail at/below VaR"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level")
    return_type: str = Field(description="Metric type (equity_irr, project_npv, etc)")
    var_label: str = Field(description="Display label for VaR")
    cvar_label: str = Field(description="Display label for CVaR / Expected Shortfall")


class PercentileAnalysis(BaseModel):
    """
    Percentile distribution of returns.

    CASPER: Structured percentile results.
    """

    model_config = ConfigDict(frozen=True)

    p10: float = Field(description="10th percentile")
    p25: float = Field(description="25th percentile (Q1)")
    p50: float = Field(description="50th percentile (median)")
    p75: float = Field(description="75th percentile (Q3)")
    p90: float = Field(description="90th percentile")


class DownsideRisk(BaseModel):
    """
    Downside risk metrics below target return.

    CASPER: Frozen contract for downside analytics.
    """

    model_config = ConfigDict(frozen=True)

    downside_deviation: float = Field(ge=0.0, description="Std dev below target")
    sortino_ratio: float = Field(description="(Mean - Target) / Downside Dev")
    returns_below_target: int = Field(ge=0, description="Count below target")
    probability_below_target: float = Field(
        ge=0.0, le=1.0, description="Probability of underperformance"
    )
    target_return: float = Field(description="Target return threshold")


class CovenantBreachAnalysis(BaseModel):
    """
    Covenant breach probability analysis.

    CASPER: Lender-grade covenant risk metrics.
    """

    model_config = ConfigDict(frozen=True)

    dscr_breach_probability: float = Field(
        ge=0.0, le=1.0, description="Probability DSCR < threshold"
    )
    llcr_breach_probability: float = Field(
        ge=0.0, le=1.0, description="Probability LLCR < threshold"
    )
    plcr_breach_probability: float = Field(
        ge=0.0, le=1.0, description="Probability PLCR < threshold"
    )

    # Minimum values across scenarios
    dscr_min_mean: float = Field(description="Mean of min DSCR across scenarios")
    llcr_min_mean: float = Field(description="Mean of min LLCR across scenarios")
    plcr_min_mean: float = Field(description="Mean of min PLCR across scenarios")

    # Thresholds used
    thresholds: Dict[str, float] = Field(description="Covenant thresholds")


class MetricRiskSummary(BaseModel):
    """
    Risk summary for a single metric.

    CASPER: Complete risk profile for one metric (IRR, NPV, etc).
    """

    model_config = ConfigDict(frozen=True)

    metric_name: str = Field(description="Metric name (equity_irr, project_npv, etc)")
    mean: float = Field(description="Mean value")
    std: float = Field(ge=0.0, description="Standard deviation")
    min: float = Field(description="Minimum value")
    max: float = Field(description="Maximum value")

    var_cvar: VaRCVaRResult = Field(description="VaR/CVaR analysis")
    percentiles: PercentileAnalysis = Field(description="Percentile distribution")
    downside: Optional[DownsideRisk] = Field(
        default=None, description="Downside risk (if applicable)"
    )


class TailRiskReport(BaseModel):
    """
    Comprehensive tail risk report for equity/lender review.

    CASPER: Executive summary contract for all risk metrics.
    """

    model_config = ConfigDict(frozen=True)

    equity_irr: MetricRiskSummary = Field(description="Equity IRR risk profile")
    project_irr: MetricRiskSummary = Field(description="Project IRR risk profile")
    equity_npv: MetricRiskSummary = Field(description="Equity NPV risk profile")
    project_npv: MetricRiskSummary = Field(description="Project NPV risk profile")

    covenant_breaches: CovenantBreachAnalysis = Field(
        description="Covenant breach analysis"
    )

    # Additional context
    probability_below_hurdle: float = Field(
        ge=0.0, le=1.0, description="Probability equity IRR < hurdle rate"
    )
    target_equity_irr: float = Field(description="Equity hurdle rate used")


# ═════════════════════════════════════════════════════════════════════════════
# TAIL RISK ANALYZER CLASS
# ═════════════════════════════════════════════════════════════════════════════


class TailRiskAnalyzer:
    """
    Comprehensive tail risk analysis for renewable energy project finance.

    CASPER: Returns Pydantic V2 contracts for all analyses.
    CESSPIT: Configured via RiskConfig, no hardcoded parameters.
    GWTF: Evidence-based calculations with full audit trail.
    CCCDIR: Single responsibility - risk analytics only.
    """

    def __init__(self, config: RiskConfig):
        """
        Initialize risk analyzer with configuration.

        Parameters
        ----------
        config : RiskConfig
            Risk analysis configuration (CESSPIT compliant).
        """
        self.config = config
        self.var_percentile = int((1 - config.confidence_level) * 100)

        logger.info(
            "TailRiskAnalyzer initialized: confidence=%s, target_return=%s",
            config.confidence_level,
            config.target_return,
        )

    def calculate_var_cvar(
        self, returns: np.ndarray, return_type: str = "equity_irr"
    ) -> VaRCVaRResult:
        """
        Calculate Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR).

        CVaR is the Expected Shortfall (ES) — the two names denote the same
        statistic and the display label reports both (``CVaR/ES(95%)``).

        VaR(95%) = worst outcome at 95% confidence (5th percentile)
        CVaR/ES(95%) = average of outcomes worse than VaR (Expected Shortfall)

        Small-sample caveat: CVaR/ES is a tail MEAN, estimated from only the
        ``(1 - confidence) * n`` worst trials — at n=1000 a 99% ES averages ~10
        raw trials and a 95% ES ~50, so the estimate is noisy and unstable for a
        covenant or pricing input at typical trial counts. ES converges slower
        than the mean: a tight mean confidence interval from the post-hoc
        convergence diagnostic (``analytics.mc.convergence``, #643) does NOT
        certify the tail. The ``>= 20``-sample floor in
        ``analytics.capital_risk_layer_v14.compute_capital_risk_layer`` is a
        degeneracy guard, not a sufficiency certificate; size ``n`` so the tail
        itself holds enough trials for the use at hand.

        CASPER: Returns Pydantic V2 contract.

        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes from Monte Carlo (e.g., IRR or NPV values).
        return_type : str
            Type of return for labeling ('equity_irr', 'project_npv', etc).

        Returns
        -------
        VaRCVaRResult
            Pydantic V2 contract with VaR/CVaR metrics.
        """
        sorted_returns = np.sort(returns)
        # max(1, ...) so the CVaR tail always averages at least one point. A small sample
        # rounds the index to 0, making sorted_returns[:0].mean() NaN (audit R1). For
        # samples large enough that the index is already >= 1 this is a no-op, so VaR/CVaR
        # on the canonical risk path are byte-identical.
        var_index = max(1, int((1 - self.config.confidence_level) * len(returns)))

        var = float(sorted_returns[var_index])
        cvar = float(sorted_returns[:var_index].mean())

        confidence_pct = int(self.config.confidence_level * 100)

        return VaRCVaRResult(
            var=var,
            cvar=cvar,
            confidence=self.config.confidence_level,
            return_type=return_type,
            var_label=f"VaR({confidence_pct}%)",
            cvar_label=f"CVaR/ES({confidence_pct}%)",
        )

    def percentile_analysis(
        self,
        returns: np.ndarray,
    ) -> PercentileAnalysis:
        """
        Calculate percentile distribution of returns.

        CASPER: Returns Pydantic V2 contract.

        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes from Monte Carlo.

        Returns
        -------
        PercentileAnalysis
            Pydantic V2 contract with standard percentiles.
        """
        return PercentileAnalysis(
            p10=float(np.percentile(returns, 10)),
            p25=float(np.percentile(returns, 25)),
            p50=float(np.percentile(returns, 50)),
            p75=float(np.percentile(returns, 75)),
            p90=float(np.percentile(returns, 90)),
        )

    def downside_risk(self, returns: np.ndarray) -> DownsideRisk:
        """
        Calculate downside risk metrics below target return.

        Downside Deviation = std dev of returns below target
        Sortino Ratio = (mean - target) / downside_deviation

        CASPER: Returns Pydantic V2 contract.

        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes.

        Returns
        -------
        DownsideRisk
            Pydantic V2 contract with downside metrics.
        """
        target = self.config.target_return
        downside_returns = returns[returns < target]

        downside_std = (
            float(downside_returns.std()) if len(downside_returns) > 0 else 0.0
        )

        mean_return = float(returns.mean())

        # Sortino Ratio: avoid division by zero
        if downside_std > 0:
            sortino = (mean_return - target) / downside_std
        else:
            sortino = float("inf") if mean_return > target else 0.0

        return DownsideRisk(
            downside_deviation=downside_std,
            sortino_ratio=sortino,
            returns_below_target=len(downside_returns),
            probability_below_target=float(len(downside_returns) / len(returns)),
            target_return=target,
        )

    def covenant_breach_probability(
        self,
        dscr_results: np.ndarray,
        llcr_results: np.ndarray,
        plcr_results: np.ndarray,
    ) -> CovenantBreachAnalysis:
        """
        Calculate probability of covenant breach (DSCR, LLCR, PLCR minimum).

        CASPER: Returns Pydantic V2 contract.
        CESSPIT: Thresholds from config, not hardcoded.

        Parameters
        ----------
        dscr_results : np.ndarray
            DSCR values with shape (n_scenarios, n_years).
        llcr_results : np.ndarray
            LLCR values with shape (n_scenarios, n_years).
        plcr_results : np.ndarray
            PLCR values with shape (n_scenarios, n_years).

        Returns
        -------
        CovenantBreachAnalysis
            Pydantic V2 contract with breach probabilities.
        """
        n_scenarios = dscr_results.shape[0]

        # Find minimum of each metric across all years (per scenario)
        dscr_min = np.min(dscr_results, axis=1)
        llcr_min = np.min(llcr_results, axis=1)
        plcr_min = np.min(plcr_results, axis=1)

        # Probability of breach (min < threshold)
        dscr_breach = float((dscr_min < self.config.min_dscr).sum() / n_scenarios)
        llcr_breach = float((llcr_min < self.config.min_llcr).sum() / n_scenarios)
        plcr_breach = float((plcr_min < self.config.min_plcr).sum() / n_scenarios)

        return CovenantBreachAnalysis(
            dscr_breach_probability=dscr_breach,
            llcr_breach_probability=llcr_breach,
            plcr_breach_probability=plcr_breach,
            dscr_min_mean=float(dscr_min.mean()),
            llcr_min_mean=float(llcr_min.mean()),
            plcr_min_mean=float(plcr_min.mean()),
            thresholds={
                "min_dscr": self.config.min_dscr,
                "min_llcr": self.config.min_llcr,
                "min_plcr": self.config.min_plcr,
            },
        )

    def tail_risk_report(
        self,
        equity_irr: np.ndarray,
        project_irr: np.ndarray,
        equity_npv: np.ndarray,
        project_npv: np.ndarray,
        dscr_results: np.ndarray,
        llcr_results: np.ndarray,
        plcr_results: np.ndarray,
    ) -> TailRiskReport:
        """
        Generate comprehensive tail risk report for equity/lender review.

        CASPER: Returns Pydantic V2 contract with all risk metrics.
        GWTF: Complete audit trail for reproducibility.

        Parameters
        ----------
        equity_irr : np.ndarray
            Monte Carlo equity IRR results.
        project_irr : np.ndarray
            Monte Carlo project IRR results.
        equity_npv : np.ndarray
            Monte Carlo equity NPV results.
        project_npv : np.ndarray
            Monte Carlo project NPV results.
        dscr_results : np.ndarray
            DSCR time series (n_scenarios, n_years).
        llcr_results : np.ndarray
            LLCR time series (n_scenarios, n_years).
        plcr_results : np.ndarray
            PLCR time series (n_scenarios, n_years).

        Returns
        -------
        TailRiskReport
            Pydantic V2 contract with complete risk analysis.
        """
        # Equity IRR analysis
        equity_irr_summary = MetricRiskSummary(
            metric_name="equity_irr",
            mean=float(equity_irr.mean()),
            std=float(equity_irr.std()),
            min=float(equity_irr.min()),
            max=float(equity_irr.max()),
            var_cvar=self.calculate_var_cvar(equity_irr, "equity_irr"),
            percentiles=self.percentile_analysis(equity_irr),
            downside=self.downside_risk(equity_irr),
        )

        # Project IRR analysis
        project_irr_summary = MetricRiskSummary(
            metric_name="project_irr",
            mean=float(project_irr.mean()),
            std=float(project_irr.std()),
            min=float(project_irr.min()),
            max=float(project_irr.max()),
            var_cvar=self.calculate_var_cvar(project_irr, "project_irr"),
            percentiles=self.percentile_analysis(project_irr),
            downside=None,  # No target for project IRR
        )

        # Equity NPV analysis
        equity_npv_summary = MetricRiskSummary(
            metric_name="equity_npv",
            mean=float(equity_npv.mean()),
            std=float(equity_npv.std()),
            min=float(equity_npv.min()),
            max=float(equity_npv.max()),
            var_cvar=self.calculate_var_cvar(equity_npv, "equity_npv"),
            percentiles=self.percentile_analysis(equity_npv),
            downside=None,  # Target is typically 0 for NPV
        )

        # Project NPV analysis
        project_npv_summary = MetricRiskSummary(
            metric_name="project_npv",
            mean=float(project_npv.mean()),
            std=float(project_npv.std()),
            min=float(project_npv.min()),
            max=float(project_npv.max()),
            var_cvar=self.calculate_var_cvar(project_npv, "project_npv"),
            percentiles=self.percentile_analysis(project_npv),
            downside=None,
        )

        # Covenant breach analysis
        covenant_analysis = self.covenant_breach_probability(
            dscr_results, llcr_results, plcr_results
        )

        # Probability equity IRR < hurdle
        prob_below_hurdle = float(
            (equity_irr < self.config.target_return).sum() / len(equity_irr)
        )

        return TailRiskReport(
            equity_irr=equity_irr_summary,
            project_irr=project_irr_summary,
            equity_npv=equity_npv_summary,
            project_npv=project_npv_summary,
            covenant_breaches=covenant_analysis,
            probability_below_hurdle=prob_below_hurdle,
            target_equity_irr=self.config.target_return,
        )

    def to_dataframe(self, report: TailRiskReport) -> pd.DataFrame:
        """
        Convert tail risk report to summary dataframe.

        GWTF: Human-readable summary for reports.

        Parameters
        ----------
        report : TailRiskReport
            Tail risk report contract.

        Returns
        -------
        pd.DataFrame
            Summary table with key metrics.
        """
        summary = []

        for metric in ["equity_irr", "project_irr", "equity_npv", "project_npv"]:
            metric_data = getattr(report, metric)
            summary.append(
                {
                    "metric": metric_data.metric_name,
                    "mean": metric_data.mean,
                    "std": metric_data.std,
                    "min": metric_data.min,
                    "max": metric_data.max,
                    "var": metric_data.var_cvar.var,
                    "cvar": metric_data.var_cvar.cvar,
                    "p50": metric_data.percentiles.p50,
                }
            )

        return pd.DataFrame(summary)


# ═════════════════════════════════════════════════════════════════════════════
# EXPORTS
# ═════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Contracts
    "RiskConfig",
    "VaRCVaRResult",
    "PercentileAnalysis",
    "DownsideRisk",
    "CovenantBreachAnalysis",
    "MetricRiskSummary",
    "TailRiskReport",
    # Analyzer
    "TailRiskAnalyzer",
]
