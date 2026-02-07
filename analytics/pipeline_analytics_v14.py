"""Enhanced V14 pipeline with comprehensive analytics integration.

This module extends the base pipeline_v14.py with optional analytics:
- Returns analysis (project & equity IRR/NPV/MIRR)
- Risk metrics (VaR, CVaR, tail risk)
- Sensitivity analysis (tornado charts)
- Scenario comparison
- Monte Carlo simulation

All analytics are CONFIG-DRIVEN and OPTIONAL.
Disabled by default to maintain backward compatibility.

Usage:
------
>>> from analytics.pipeline_analytics_v14 import run_v14_pipeline_with_analytics
>>> result = run_v14_pipeline_with_analytics(
...     config='scenarios/dutchbay_basecase_2025Q4.yaml',
...     enable_returns=True,
...     enable_risk=True,
... )
>>> print(result['returns_analysis'].project_returns.project_irr)
0.1245
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

# Base pipeline
from analytics.pipeline_v14 import run_v14_pipeline

# Analytics modules (optional imports with graceful degradation)
try:
    from analytics.returns import (
        AllReturns,
        ReturnsConfig,
        summarize_all_returns,
    )

    RETURNS_AVAILABLE = True
except ImportError:
    RETURNS_AVAILABLE = False

try:
    from analytics.risk_metrics import (
        RiskConfig,
        TailRiskAnalyzer,
        VaRCVaRResult,
        calculate_percentile_analysis,
        calculate_var_cvar,
    )

    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False

# Scenario comparison (builtin - no external dependency)
SCENARIO_COMPARISON_AVAILABLE = True

logger = logging.getLogger(__name__)

# ═════════════════════════════════════════════════════════════════════════════
# ANALYTICS RESULT CONTRACTS
# ═════════════════════════════════════════════════════════════════════════════


class AnalyticsEnablement(BaseModel):
    """Tracks which analytics modules are enabled and available."""

    model_config = ConfigDict(frozen=True)

    returns_enabled: bool = Field(default=False)
    returns_available: bool = Field(default=False)

    risk_enabled: bool = Field(default=False)
    risk_available: bool = Field(default=False)

    sensitivity_enabled: bool = Field(default=False)
    sensitivity_available: bool = Field(default=False)

    monte_carlo_enabled: bool = Field(default=False)
    monte_carlo_available: bool = Field(default=False)

    scenario_comparison_enabled: bool = Field(default=False)
    scenario_comparison_available: bool = Field(default=True)


class SensitivityPoint(BaseModel):
    """Single sensitivity analysis data point."""

    model_config = ConfigDict(frozen=True)

    parameter: str = Field(description="Parameter name")
    variation_pct: float = Field(description="% change from base")
    project_npv: float = Field(description="Resulting project NPV")
    project_irr: Optional[float] = Field(default=None, description="Resulting IRR")
    min_dscr: float = Field(description="Minimum DSCR")


class SensitivityAnalysisResult(BaseModel):
    """Sensitivity analysis (tornado chart data)."""

    model_config = ConfigDict(frozen=True)

    parameters_tested: List[str] = Field(description="Parameters swept")
    sensitivity_points: List[SensitivityPoint] = Field(
        description="All data points"
    )
    base_npv: float = Field(description="Base case NPV")
    base_irr: Optional[float] = Field(default=None, description="Base case IRR")
    base_dscr: float = Field(description="Base case min DSCR")

    # Tornado ranking (by NPV impact)
    npv_impact_ranking: List[tuple[str, float]] = Field(
        description="Parameters ranked by NPV sensitivity"
    )


class ScenarioComparisonResult(BaseModel):
    """Comparison of multiple scenarios (base/optimistic/pessimistic)."""

    model_config = ConfigDict(frozen=True)

    scenario_names: List[str] = Field(description="Scenario labels")
    project_npvs: List[float] = Field(description="Project NPVs by scenario")
    project_irrs: List[Optional[float]] = Field(description="Project IRRs")
    equity_npvs: List[float] = Field(description="Equity NPVs")
    equity_irrs: List[Optional[float]] = Field(description="Equity IRRs")
    min_dscrs: List[float] = Field(description="Min DSCRs")

    # Summary statistics
    npv_range: float = Field(description="Max NPV - Min NPV")
    irr_range: float = Field(description="Max IRR - Min IRR")


class MonteCarloResult(BaseModel):
    """Monte Carlo simulation results."""

    model_config = ConfigDict(frozen=True)

    iterations: int = Field(ge=1000, description="Number of MC iterations")
    project_npv_mean: float = Field(description="Mean NPV")
    project_npv_std: float = Field(ge=0.0, description="Std dev NPV")
    project_npv_p10: float = Field(description="10th percentile NPV")
    project_npv_p50: float = Field(description="50th percentile (median) NPV")
    project_npv_p90: float = Field(description="90th percentile NPV")

    project_irr_mean: Optional[float] = Field(default=None, description="Mean IRR")
    project_irr_std: Optional[float] = Field(default=None, description="Std dev IRR")

    # Full distribution (optional - can be large)
    npv_distribution: Optional[List[float]] = Field(
        default=None, description="Full NPV samples"
    )
    irr_distribution: Optional[List[float]] = Field(
        default=None, description="Full IRR samples"
    )


class EnhancedAnalyticsResult(BaseModel):
    """Complete analytics result (extends base pipeline)."""

    model_config = ConfigDict(frozen=True)

    # Base pipeline result (all keys preserved)
    base_result: Dict[str, Any] = Field(description="Full base pipeline result")

    # Analytics enablement status
    analytics_enabled: AnalyticsEnablement = Field(
        description="Which analytics ran"
    )

    # Optional analytics results
    returns_analysis: Optional[AllReturns] = Field(
        default=None, description="Project & equity returns"
    )
    risk_analysis: Optional[Dict[str, Any]] = Field(
        default=None, description="VaR/CVaR/tail risk"
    )
    sensitivity_analysis: Optional[SensitivityAnalysisResult] = Field(
        default=None, description="Tornado chart data"
    )
    monte_carlo_analysis: Optional[MonteCarloResult] = Field(
        default=None, description="Monte Carlo simulation"
    )
    scenario_comparison: Optional[ScenarioComparisonResult] = Field(
        default=None, description="Multi-scenario comparison"
    )


# ═════════════════════════════════════════════════════════════════════════════
# ANALYTICS CALCULATION FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════


def _calculate_returns_analysis(
    base_result: Dict[str, Any],
    config: Dict[str, Any],
) -> Optional[AllReturns]:
    """Calculate project & equity returns from base pipeline result."""
    if not RETURNS_AVAILABLE:
        logger.warning("Returns module not available; skipping returns analysis")
        return None

    try:
        # Extract required data from base pipeline result
        annual_rows = base_result.get("annual_rows", [])
        debt_result = base_result.get("debt_result", {})

        if not annual_rows:
            logger.warning("No annual_rows in base result; skipping returns")
            return None

        # Build CFADS series
        cfads_series = [float(row.get("cfads_final_lkr", 0.0)) for row in annual_rows]

        # Build debt service series
        debt_service_total = debt_result.get("debt_service_total", [])
        if not debt_service_total:
            logger.warning("No debt_service_total; using zeros")
            debt_service_series = [0.0] * len(cfads_series)
        else:
            debt_service_series = list(debt_service_total[: len(cfads_series)])
            # Pad if shorter
            while len(debt_service_series) < len(cfads_series):
                debt_service_series.append(0.0)

        # Build ReturnsConfig from scenario config
        returns_config = ReturnsConfig.from_yaml(config)

        # Calculate all returns
        all_returns = summarize_all_returns(
            cfads_series=cfads_series,
            debt_service_series=debt_service_series,
            config=returns_config,
        )

        logger.info(
            "Returns analysis complete: Project IRR=%.2f%%, Equity IRR=%.2f%%",
            (all_returns.project_returns.project_irr or 0.0) * 100,
            (all_returns.equity_returns.equity_irr or 0.0) * 100,
        )

        return all_returns

    except Exception as exc:
        logger.error("Returns analysis failed: %s", exc, exc_info=True)
        return None


def _calculate_risk_analysis(
    base_result: Dict[str, Any],
    config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Calculate risk metrics (VaR, CVaR, tail risk)."""
    if not RISK_AVAILABLE:
        logger.warning("Risk module not available; skipping risk analysis")
        return None

    try:
        annual_rows = base_result.get("annual_rows", [])
        if not annual_rows:
            logger.warning("No annual_rows; skipping risk analysis")
            return None

        cfads_series = [float(row.get("cfads_final_lkr", 0.0)) for row in annual_rows]

        # Default risk config (can be made configurable later)
        risk_config = RiskConfig(
            var_confidence_level=0.95,
            cvar_confidence_level=0.95,
            tail_percentile=0.05,
            monte_carlo_iterations=10000,
        )

        # VaR/CVaR
        var_cvar = calculate_var_cvar(
            data=cfads_series,
            confidence_level=risk_config.var_confidence_level,
        )

        # Tail risk analysis
        tail_analyzer = TailRiskAnalyzer(config=risk_config)
        tail_risk_report = tail_analyzer.analyze_tail_risk(cashflows=cfads_series)

        # Percentile analysis
        percentiles = calculate_percentile_analysis(
            data=cfads_series,
            percentiles=[0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95],
        )

        logger.info(
            "Risk analysis complete: VaR(95%%)=%.2f M, CVaR(95%%)=%.2f M",
            var_cvar.var_value,
            var_cvar.cvar_value,
        )

        # Return as dict (could create Pydantic contract later)
        return {
            "var_cvar": var_cvar.model_dump(),
            "tail_risk": tail_risk_report.model_dump(),
            "percentiles": percentiles.model_dump(),
        }

    except Exception as exc:
        logger.error("Risk analysis failed: %s", exc, exc_info=True)
        return None


def _calculate_sensitivity_analysis(
    config_path: str | Path,
    base_result: Dict[str, Any],
) -> Optional[SensitivityAnalysisResult]:
    """Calculate sensitivity analysis (tornado chart).

    NOTE: This is a STUB - full implementation requires re-running pipeline
    with parameter variations.
    """
    logger.warning(
        "Sensitivity analysis requires full pipeline re-runs with parameter sweeps. "
        "This is a stub implementation - returning None."
    )
    return None


def _calculate_monte_carlo(
    config_path: str | Path,
    base_result: Dict[str, Any],
    iterations: int = 10000,
) -> Optional[MonteCarloResult]:
    """Calculate Monte Carlo simulation.

    NOTE: This is a STUB - full implementation requires stochastic parameter
    sampling and repeated pipeline runs.
    """
    logger.warning(
        "Monte Carlo simulation requires stochastic parameter sampling "
        "and repeated pipeline runs. This is a stub implementation - returning None."
    )
    return None


def _calculate_scenario_comparison(
    config_path: str | Path,
    base_result: Dict[str, Any],
) -> Optional[ScenarioComparisonResult]:
    """Compare multiple scenarios (base/optimistic/pessimistic).

    NOTE: This is a STUB - full implementation requires loading and running
    multiple scenario files.
    """
    logger.warning(
        "Scenario comparison requires loading multiple scenario configs. "
        "This is a stub implementation - returning None."
    )
    return None


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENHANCED PIPELINE FUNCTION
# ═════════════════════════════════════════════════════════════════════════════


def run_v14_pipeline_with_analytics(
    config: str | Path | Mapping[str, Any],
    validation_mode: str = "strict",
    validation_modules: List[str] | None = None,
    allow_fx_degradation: bool = False,
    # Analytics enablement flags
    enable_returns: bool = False,
    enable_risk: bool = False,
    enable_sensitivity: bool = False,
    enable_monte_carlo: bool = False,
    enable_scenario_comparison: bool = False,
    # Analytics parameters
    monte_carlo_iterations: int = 10000,
) -> Dict[str, Any]:
    """Run V14 pipeline with optional analytics modules.

    This is a WRAPPER around the base run_v14_pipeline() that adds optional
    analytics calculations.

    Parameters
    ----------
    config : str | Path | Mapping[str, Any]
        Scenario config (same as base pipeline).
    validation_mode : str, default "strict"
        Validation mode (same as base pipeline).
    validation_modules : list[str] | None
        Modules to validate (same as base pipeline).
    allow_fx_degradation : bool, default False
        FX degradation mode (same as base pipeline).
    enable_returns : bool, default False
        Enable returns analysis (IRR/NPV/MIRR).
    enable_risk : bool, default False
        Enable risk metrics (VaR/CVaR/tail risk).
    enable_sensitivity : bool, default False
        Enable sensitivity analysis (tornado charts).
    enable_monte_carlo : bool, default False
        Enable Monte Carlo simulation.
    enable_scenario_comparison : bool, default False
        Enable multi-scenario comparison.
    monte_carlo_iterations : int, default 10000
        Number of MC iterations (if enabled).

    Returns
    -------
    dict[str, Any]
        Enhanced result with:
        - All base pipeline keys (annual_rows, debt_result, kpis, etc.)
        - analytics_result: EnhancedAnalyticsResult contract

    Examples
    --------
    >>> result = run_v14_pipeline_with_analytics(
    ...     config='scenarios/dutchbay_basecase_2025Q4.yaml',
    ...     enable_returns=True,
    ...     enable_risk=True,
    ... )
    >>> print(result['analytics_result'].returns_analysis.project_returns.project_irr)
    0.1245
    """
    # ──────────────────────────────────────────────────────────────────────────
    # 1. Run base pipeline (unchanged)
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("Running base V14 pipeline...")
    base_result = run_v14_pipeline(
        config=config,
        validation_mode=validation_mode,
        validation_modules=validation_modules,
        allow_fx_degradation=allow_fx_degradation,
    )

    logger.info("Base pipeline complete. Starting analytics modules...")

    # Resolve config path for analytics that need it
    if isinstance(config, (str, Path)):
        config_path = str(config)
        cfg = base_result["config"]
    else:
        config_path = "<inline_config>"
        cfg = dict(config)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Calculate optional analytics
    # ──────────────────────────────────────────────────────────────────────────

    returns_analysis = None
    if enable_returns:
        logger.info("Calculating returns analysis...")
        returns_analysis = _calculate_returns_analysis(base_result, cfg)

    risk_analysis = None
    if enable_risk:
        logger.info("Calculating risk analysis...")
        risk_analysis = _calculate_risk_analysis(base_result, cfg)

    sensitivity_analysis = None
    if enable_sensitivity:
        logger.info("Calculating sensitivity analysis...")
        sensitivity_analysis = _calculate_sensitivity_analysis(config_path, base_result)

    monte_carlo_analysis = None
    if enable_monte_carlo:
        logger.info("Running Monte Carlo simulation (%d iterations)...", monte_carlo_iterations)
        monte_carlo_analysis = _calculate_monte_carlo(
            config_path, base_result, iterations=monte_carlo_iterations
        )

    scenario_comparison = None
    if enable_scenario_comparison:
        logger.info("Comparing scenarios...")
        scenario_comparison = _calculate_scenario_comparison(config_path, base_result)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Package analytics result
    # ──────────────────────────────────────────────────────────────────────────

    analytics_enabled = AnalyticsEnablement(
        returns_enabled=enable_returns,
        returns_available=RETURNS_AVAILABLE,
        risk_enabled=enable_risk,
        risk_available=RISK_AVAILABLE,
        sensitivity_enabled=enable_sensitivity,
        sensitivity_available=False,  # Stub only
        monte_carlo_enabled=enable_monte_carlo,
        monte_carlo_available=False,  # Stub only
        scenario_comparison_enabled=enable_scenario_comparison,
        scenario_comparison_available=SCENARIO_COMPARISON_AVAILABLE,
    )

    analytics_result = EnhancedAnalyticsResult(
        base_result=base_result,
        analytics_enabled=analytics_enabled,
        returns_analysis=returns_analysis,
        risk_analysis=risk_analysis,
        sensitivity_analysis=sensitivity_analysis,
        monte_carlo_analysis=monte_carlo_analysis,
        scenario_comparison=scenario_comparison,
    )

    logger.info(
        "Analytics pipeline complete: returns=%s, risk=%s, sensitivity=%s, MC=%s",
        "✓" if returns_analysis else "✗",
        "✓" if risk_analysis else "✗",
        "✓" if sensitivity_analysis else "✗",
        "✓" if monte_carlo_analysis else "✗",
    )

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Return enhanced result (backward compatible)
    # ──────────────────────────────────────────────────────────────────────────

    # Preserve all base_result keys at top level
    enhanced_result = dict(base_result)

    # Add analytics under new key
    enhanced_result["analytics_result"] = analytics_result.model_dump()

    return enhanced_result


__all__ = [
    # Main function
    "run_v14_pipeline_with_analytics",
    # Contracts
    "EnhancedAnalyticsResult",
    "AnalyticsEnablement",
    "SensitivityAnalysisResult",
    "MonteCarloResult",
    "ScenarioComparisonResult",
]
