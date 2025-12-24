"""Analytics pipeline for v14 scenarios.

Orchestrates risk metrics, sensitivity analysis, and reporting.

DOLPHIN #10b: Removed unused import VaRCVaRResult
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

try:
    from analytics.risk_metrics import (
        PercentileAnalysis,
        RiskConfig,
        TailRiskAnalyzer,
        calculate_percentile_analysis,
        calculate_var_cvar,
    )
    HAS_RISK_METRICS = True
except ImportError:
    HAS_RISK_METRICS = False

from analytics.evaluation_v14 import evaluate_with_overrides

logger = logging.getLogger(__name__)


def run_analytics_pipeline(
    config_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run full analytics pipeline.
    
    Args:
        config_path: Path to scenario YAML
        output_dir: Optional output directory for reports
        
    Returns:
        dict with analytics results
    """
    config_path = Path(config_path)
    
    # 1. Baseline evaluation
    logger.info("Evaluating baseline scenario: %s", config_path)
    kpis = evaluate_with_overrides(config_path)
    
    # 2. Risk metrics (if available)
    risk_metrics = {}
    if HAS_RISK_METRICS:
        logger.info("Calculating risk metrics")
        # TODO: Implement risk metrics pipeline
        pass
    
    # 3. Package results
    results = {
        "baseline_kpis": kpis,
        "risk_metrics": risk_metrics,
        "config_path": str(config_path),
    }
    
    # 4. Write outputs if requested
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        logger.info("Writing analytics results to %s", output_path)
    
    return results
