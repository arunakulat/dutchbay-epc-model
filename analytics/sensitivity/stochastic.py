"""
stochastic.py – Stochastic Tornado Sensitivity for v14+ analytics

PURPOSE:
    Provides an advanced sensitivity tool that not only sweeps parameters from min→max but, for each parameter,
    simulates a distribution of outcomes by jittering all other parameters with random noise.
    Used to expose nonlinearities and risk distributions—essential for DFI/board-level and risk-focused dashboards.

USAGE:
    Example: Plot violin or P10/P50/P90 impact bands for each driver param.
    from analytics.sensitivity.stochastic import run_stochastic_tornado
    df = run_stochastic_tornado(config_path, parameters)
    # Plot df["sweep"] vs df["P10"], df["P50"], df["P90"] for each df["variable"]

INPUTS:
    - base_config_path (str): Path to a scenario YAML/JSON.
    - parameters (list of ParameterRangeConfig): Driver param configs.
    - metric (str): Output KPI, e.g. "project_irr".
    - n_samples (int): Number of MC samples per sweep point.
    - sweep_size (int): How many points to sample through min→max range.
    - jitter_pct (float): Standard deviation for random jitter of all non-driver params (percent).

RETURNS:
    DataFrame with:
    - "variable": driver name
    - "sweep": sweep point value
    - "P10"/"P50"/"P90": percentiles of output metric at this point
    - "samples": list of all simulated values for custom plotting
"""

from typing import List

import numpy as np
import pandas as pd

from analytics.contracts_v14 import ParameterRangeConfig
from analytics.evaluate_scenario import evaluate_with_overrides


def run_stochastic_tornado(
    base_config_path: str,
    parameters: List[ParameterRangeConfig],
    metric: str = "project_irr",
    n_samples: int = 300,
    sweep_size: int = 5,
    jitter_pct: float = 5.0,
) -> pd.DataFrame:
    """
    See module docstring above for purpose and usage.
    """
    records = []
    all_vars = {p.variable_name: p for p in parameters}
    for driver in parameters:
        sweep_vals = np.linspace(
            driver.base_value * (1 + driver.low_pct / 100),
            driver.base_value * (1 + driver.high_pct / 100),
            sweep_size,
        )
        for sv in sweep_vals:
            metric_samples = []
            for _ in range(n_samples):
                overrides = {}
                # Add small random noise to all other parameters
                for ovn, op in all_vars.items():
                    if ovn != driver.variable_name:
                        noise = np.random.normal(loc=0, scale=jitter_pct)
                        val = op.base_value * (1 + noise / 100)
                        overrides.update(_build_nested_override(ovn, val))
                # Sweep this parameter through value of interest
                overrides.update(_build_nested_override(driver.variable_name, sv))
                kpis = evaluate_with_overrides(base_config_path, overrides)
                metric_samples.append(float(kpis[metric]))
            records.append(
                {
                    "variable": driver.variable_name,
                    "sweep": sv,
                    "P10": np.percentile(metric_samples, 10),
                    "P50": np.percentile(metric_samples, 50),
                    "P90": np.percentile(metric_samples, 90),
                    "samples": metric_samples,
                }
            )
    return pd.DataFrame(records)


def _build_nested_override(variable_name: str, value):
    """
    Helper (you can unify with other analytics modules as needed).
    Converts a dot.separated path and value to a nested dict override.
    """
    keys = variable_name.split(".")
    d = value
    for key in reversed(keys):
        d = {key: d}
    return d
