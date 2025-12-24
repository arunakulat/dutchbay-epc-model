"""Sensitivity analysis runner.

Engine for running one-way parameter sensitivity sweeps.

TODO:
- Add multi-parameter sensitivity (heatmaps)
- Add shock specifications from config
- Add tail risk analysis integration
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.contracts_v14 import SensitivitySuite, TornadoResult
from analytics.sensitivity.engine import build_one_way_sensitivity_suite

logger = logging.getLogger(__name__)


def run_sensitivity_analysis(
    config_path: str,
    metric: str = "project_irr",
    validation_modules: list[str] | None = None,
) -> SensitivitySuite:
    """Run sensitivity analysis on a scenario.
    
    Args:
        config_path: Path to scenario YAML file
        metric: Metric to analyze (default: project_irr)
        validation_modules: Validation modules to run
        
    Returns:
        SensitivitySuite with tornado results
        
    Example:
        >>> suite = run_sensitivity_analysis(
        ...     "scenarios/dutchbay.yaml",
        ...     metric="equity_irr"
        ... )
        >>> print(f"Analyzed {len(suite.tornado_results)} parameters")
    """
    # 1. Load base scenario
    base_path = Path(config_path)
    
    # 2. Evaluate baseline
    base_kpis = evaluate_with_overrides(
        base_path,
        validation_modules=validation_modules or ["cashflow", "debt"],
    )
    # Baseline scenario name extracted but not used in tornado
    base_metric_value = float(base_kpis.get(metric, 0.0))
    # 3. Build default shock specifications if none provided
    # TODO: Load from config when shock specifications supported
    
    # 4. Run sensitivity engine
    suite = build_one_way_sensitivity_suite(
        str(base_path),
        metric=metric,
        # TODO: Pass shock specs when implemented
    )
    
    logger.info(
        "Sensitivity analysis complete: %d parameters, metric=%s, baseline=%.4f",
        len(suite.tornado_results),
        metric,
        base_metric_value
    )
    
    return suite
