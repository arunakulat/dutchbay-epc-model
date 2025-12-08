"""
Stochastic Tornado Sensitivity for v14+ analytics.

PURPOSE
-------
Provides an advanced sensitivity tool that not only sweeps
parameters from min→max but, for each parameter, simulates a
distribution of outcomes by jittering all other parameters with
random noise. This helps expose nonlinearities and risk
distributions for DFI / board-level and risk-focused dashboards.

USAGE
-----
Example: Plot violin or P10/P50/P90 impact bands for each driver param.

    from analytics.sensitivity.stochastic import run_stochastic_tornado

    df = run_stochastic_tornado(config_path, parameters)
    # Plot df["sweep"] vs df["P10"], df["P50"], df["P90"] for each df["variable"]

INPUTS
------
- base_config_path (str): Path to a scenario YAML/JSON.
- parameters (list[ParameterRangeConfig]): Driver param configs.
- metric (str): Output KPI, e.g. "project_irr".
- n_samples (int): Number of MC samples per sweep point.
- sweep_size (int): How many points to sample through min→max range.
- jitter_pct (float): Standard deviation for random jitter (percent)
  applied to all non-driver params.

RETURNS
-------
Pandas DataFrame with columns:

- "variable": driver name.
- "sweep": sweep point value (driver value).
- "P10" / "P50" / "P90": percentiles of output metric at this point.
- "samples": list[float] of all simulated values for custom plotting.
"""

from __future__ import annotations

from typing import Any, Dict, List

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
    Run a stochastic tornado-style sensitivity analysis.

    For each driver parameter, this function:
    - Sweeps the driver from (base * (1 + low_pct)) to (base * (1 + high_pct)).
    - At each sweep value, performs n_samples simulations.
    - In each simulation, jitters all non-driver parameters
      with independent Gaussian noise (mean 0, std = jitter_pct %).
    - Evaluates the configured KPI and aggregates percentiles.

    Args:
        base_config_path: Path to base scenario configuration.
        parameters: List of driver parameter configurations.
        metric: Name of KPI in evaluate_with_overrides result to analyze.
        n_samples: Number of Monte Carlo samples per sweep point.
        sweep_size: Number of discrete points across the driver range.
        jitter_pct: Standard deviation of jitter applied to non-driver
            parameters, in percent of base value.

    Returns:
        DataFrame with one row per driver × sweep point.
    """
    records: List[Dict[str, Any]] = []

    # Index parameters by their variable path
    all_vars: Dict[str, ParameterRangeConfig] = {p.variable_name: p for p in parameters}

    for driver in parameters:
        low_val = driver.base_value * (1.0 + driver.low_pct / 100.0)
        high_val = driver.base_value * (1.0 + driver.high_pct / 100.0)
        sweep_vals = np.linspace(low_val, high_val, sweep_size)

        for sv in sweep_vals:
            metric_samples: List[float] = []

            for _ in range(n_samples):
                overrides: Dict[str, Any] = {}

                # Add random noise to all non-driver parameters
                for var_name, param in all_vars.items():
                    if var_name == driver.variable_name:
                        continue
                    noise = float(np.random.normal(loc=0.0, scale=jitter_pct))
                    val = param.base_value * (1.0 + noise / 100.0)
                    overrides.update(_build_nested_override(var_name, val))

                # Set the swept value for the driver
                overrides.update(_build_nested_override(driver.variable_name, sv))

                kpis = evaluate_with_overrides(base_config_path, overrides)
                metric_value = float(kpis[metric])
                metric_samples.append(metric_value)

            records.append(
                {
                    "variable": driver.variable_name,
                    "sweep": float(sv),
                    "P10": float(np.percentile(metric_samples, 10)),
                    "P50": float(np.percentile(metric_samples, 50)),
                    "P90": float(np.percentile(metric_samples, 90)),
                    "samples": metric_samples,
                }
            )

    return pd.DataFrame(records)


def _build_nested_override(variable_name: str, value: Any) -> Dict[str, Any]:
    """
    Convert a dot-separated path and value into a nested override dict.

    Example:
        variable_name = "project.tariff.lkr_per_kwh"
        value = 1.05

        returns:
            {
                "project": {
                    "tariff": {
                        "lkr_per_kwh": 1.05
                    }
                }
            }

    Args:
        variable_name: Dot-separated path into the config structure.
        value: Value to set at the leaf.

    Returns:
        Nested dict suitable for use as an overrides structure.
    """
    keys = variable_name.split(".")
    d: Any = value
    for key in reversed(keys):
        d = {key: d}
    return d
