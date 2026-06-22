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

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

# Base pipeline: the FINANCE engine (returns annual_rows / debt_result / kpis).
# NOT analytics.pipeline_v14, which is the wind-resource pipeline — a different
# result shape that lacks the finance keys the analytics below consume.
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config

# Analytics modules (optional imports with graceful degradation)
try:
    from analytics.core.returns import (
        AllReturns,
        ReturnsConfig,
        summarize_all_returns,
    )

    RETURNS_AVAILABLE = True
except ImportError:
    RETURNS_AVAILABLE = False

try:
    from analytics.core.risk_metrics import (
        RiskConfig,
        TailRiskAnalyzer,
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

        # Deterministic risk metrics on the scenario CFADS series.
        cfads_arr = np.asarray(cfads_series, dtype=float)

        # RiskConfig requires covenant/target thresholds, but the VaR/CVaR and
        # percentile metrics computed here use only confidence_level. Source all
        # fields from config (config-first, no hardcoded model constants); fall
        # back to the DSCR covenant for LLCR/PLCR when the scenario does not
        # specify them separately (those fields are unused on this path).
        constraints = config.get("constraints", {})
        dscr_cov = float(constraints.get("min_dscr_covenant", 1.0))
        risk_config = RiskConfig(
            confidence_level=float(config.get("risk", {}).get("confidence_level", 0.95)),
            target_return=float(config.get("returns", {}).get("equity_discount_rate", 0.0)),
            min_dscr=dscr_cov,
            min_llcr=float(constraints.get("min_llcr_covenant", dscr_cov)),
            min_plcr=float(constraints.get("min_plcr_covenant", dscr_cov)),
        )
        analyzer = TailRiskAnalyzer(config=risk_config)

        var_cvar = analyzer.calculate_var_cvar(
            returns=cfads_arr, return_type="cfads_final_lkr"
        )
        percentiles = analyzer.percentile_analysis(returns=cfads_arr)

        logger.info(
            "Risk analysis complete: %s=%.2f, %s=%.2f",
            var_cvar.var_label,
            var_cvar.var,
            var_cvar.cvar_label,
            var_cvar.cvar,
        )

        # NOTE: TailRiskAnalyzer.tail_risk_report() requires full Monte Carlo
        # distributions (equity/project IRR & NPV, DSCR/LLCR/PLCR arrays). That
        # path depends on the parked Monte Carlo engine work (#60); the
        # deterministic VaR/CVaR + percentile metrics above stand alone.
        return {
            "var_cvar": var_cvar.model_dump(),
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
    # The base pipeline loads its config from a path; an inline Mapping config
    # cannot drive it (that path never worked — it raised inside Path(config)).
    # Fail fast with a clear message. allow_fx_degradation is a no-op in the base
    # pipeline (see run_v14_pipeline_enhanced, which discards it) and is
    # intentionally not forwarded.
    if not isinstance(config, (str, Path)):
        raise TypeError(
            "run_v14_pipeline_with_analytics requires a path-based config "
            "(str | Path) to run the base pipeline; inline Mapping configs are "
            "not supported."
        )
    base_result = run_v14_pipeline(
        config=config,
        validation_mode=validation_mode,
        validation_modules=validation_modules,
    )

    # Fail loud if the base pipeline did not return the finance result shape the
    # analytics consume (annual_rows / debt_result / kpis). This wrapper used to
    # import the *wind* run_v14_pipeline, whose result lacks these keys, so the
    # returns/risk analytics silently always returned None.
    missing = [k for k in ("annual_rows", "debt_result", "kpis") if k not in base_result]
    if missing:
        raise RuntimeError(
            f"Base pipeline result is missing finance keys {missing}; "
            "run_v14_pipeline_with_analytics must drive the finance pipeline "
            "(analytics.pipeline_v14_enhanced)."
        )

    logger.info("Base pipeline complete. Starting analytics modules...")

    # config is guaranteed path-based (guarded above); resolve for analytics.
    # The finance result does not echo the input config, so load it explicitly.
    config_path = str(config)
    cfg = dict(load_scenario_config(config_path))

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
