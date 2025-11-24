# analytics/sensitivity_tail_risk.py

"""
Tail Risk Analytics (VaR, CVaR, Downside) for SensitivitySuite v14+
- Uses MonteCarloResult and Tornado for risk-prioritized reporting
- Supports Basel III/DFI-compliant tail risk (CVaR, breach probability)
"""

from typing import Sequence, Dict, Any, Optional
import numpy as np
import pandas as pd
from analytics.contracts_v14 import SensitivitySuite
from analytics.monte_carlo_v14 import MonteCarloResult

def enrich_tornado_with_tail_risk(
    tornado_suite: SensitivitySuite,
    mc_result: MonteCarloResult,
    metric: str = "project_irr",
    confidence: float = 0.9
) -> pd.DataFrame:
    """
    Enrich tornado table with VaR, CVaR, P10/P90, and breach probabilities.
    Returns a DataFrame ready for Excel/DFI reporting (adds risk columns).
    """
    # Get MC sample for the metric
    values = np.array([rec[metric] for rec in mc_result.raw_results if metric in rec])
    var_pct = 100* (1 - confidence)
    var = np.percentile(values, var_pct)
    cvar = values[values <= var].mean() if np.any(values <= var) else var
    p10 = np.percentile(values, 10)
    p90 = np.percentile(values, 90)

    tdf = tornado_suite_to_dataframe(tornado_suite)
    # Add tail risk columns
    tdf["VaR"] = var
    tdf["CVaR"] = cvar
    tdf["P10"] = p10
    tdf["P90"] = p90
    tdf["BreachProb"] = np.mean(values < tdf["Low Metric"])  # probability < low
    return tdf

def tornado_suite_to_dataframe(tornado_suite: SensitivitySuite) -> pd.DataFrame:
    """Wraps export module for use here, keeps the contract."""
    import analytics.sensitivity_export as sxp
    return sxp.tornado_suite_to_dataframe(tornado_suite)
