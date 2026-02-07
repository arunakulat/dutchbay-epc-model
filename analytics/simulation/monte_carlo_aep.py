#!/usr/bin/env python
"""Monte Carlo simulation for AEP uncertainty quantification.

Implements 100k-scenario Monte Carlo with Weibull parameter uncertainty,
loss factor variation, and P50/P75/P90/P99 percentile calculations.

Usage:
    from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep

    results = run_monte_carlo_aep(
        aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        n_scenarios=100000,
        export_scenarios=True,
        output_path='outputs/mc_aep_100k.parquet'
    )

    print(f"P50 AEP: {results['percentiles']['p50']:.2f} GWh")
    print(f"P90 AEP: {results['percentiles']['p90']:.2f} GWh")
    print(f"95% CI: [{results['confidence_intervals']['ci95_lower']:.2f}, "
          f"{results['confidence_intervals']['ci95_upper']:.2f}] GWh")

References:
    - IEC 61400-15-1:2025 Assessment of site-specific wind conditions
    - NREL Technical Report TP-500-38977 (Wind energy uncertainty)
    - DFI Bankability Guidelines for Wind Projects

Context:
    Sprint 17 - Issue #20: Monte Carlo AEP Simulation
    Part of risk quantification for lender-grade financial modeling
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from analytics.loader.aep_loader import load_aep_from_summary
from analytics.power_curves.oem_parser import (
    compute_aep_from_curve,
    parse_envision_en171_curve,
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# MONTE CARLO CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

MC_CONFIG_PRODUCTION = {
    "n_scenarios": 100000,
    "weibull_uncertainty_pct": 10.0,  # ±10% on A and k
    "wake_loss_std_pct": 2.0,  # ±2% on wake loss
    "availability_std_pct": 1.0,  # ±1% on availability
    "electrical_loss_std_pct": 0.5,  # ±0.5% on electrical loss
}

MC_CONFIG_TESTING = {
    "n_scenarios": 1000,  # For fast testing
    "weibull_uncertainty_pct": 10.0,
    "wake_loss_std_pct": 2.0,
    "availability_std_pct": 1.0,
    "electrical_loss_std_pct": 0.5,
}


def run_monte_carlo_aep(
    aep_summary_path: str,
    n_scenarios: int = 100000,
    weibull_a_mean: Optional[float] = None,
    weibull_k_mean: Optional[float] = None,
    weibull_uncertainty_pct: float = 10.0,
    wake_loss_mean_pct: Optional[float] = None,
    availability_mean_pct: Optional[float] = None,
    electrical_loss_mean_pct: Optional[float] = None,
    wake_loss_std_pct: float = 2.0,
    availability_std_pct: float = 1.0,
    electrical_loss_std_pct: float = 0.5,
    air_density_kgm3: float = 1.15,
    export_scenarios: bool = False,
    output_path: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict:
    """Run Monte Carlo simulation for AEP uncertainty quantification.

    Samples Weibull wind distribution parameters and loss factors to generate
    distribution of net AEP values with P50/P75/P90/P99 percentiles.

    Args:
        aep_summary_path: Path to AEP summary JSON (from Data Lake)
        n_scenarios: Number of Monte Carlo scenarios (100k for production)
        weibull_a_mean: Mean Weibull A parameter (m/s). If None, estimated from AEP.
        weibull_k_mean: Mean Weibull k parameter. If None, uses 2.0 (Rayleigh).
        weibull_uncertainty_pct: Uncertainty range on A and k (±%)
        wake_loss_mean_pct: Mean wake loss (%). If None, from aep_summary.
        availability_mean_pct: Mean availability (%). If None, from aep_summary.
        electrical_loss_mean_pct: Mean electrical loss (%). If None, from aep_summary.
        wake_loss_std_pct: Std dev of wake loss (±%)
        availability_std_pct: Std dev of availability (±%)
        electrical_loss_std_pct: Std dev of electrical loss (±%)
        air_density_kgm3: Site air density (kg/m³)
        export_scenarios: If True, export scenarios to parquet
        output_path: Path to save scenarios (required if export_scenarios=True)
        seed: Random seed for reproducibility

    Returns:
        Dictionary with:
            - percentiles: {p50, p75, p90, p99} AEP values (GWh)
            - confidence_intervals: {ci95_lower, ci95_upper} (GWh)
            - statistics: {mean, std, cv} of AEP distribution
            - scenarios: DataFrame (if export_scenarios=True)

    Example:
        >>> results = run_monte_carlo_aep(
        ...     aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        ...     n_scenarios=100000,
        ...     export_scenarios=True,
        ...     output_path='outputs/mc_aep_100k.parquet'
        ... )
        >>> print(f"P50: {results['percentiles']['p50']:.2f} GWh")
        >>> print(f"P90: {results['percentiles']['p90']:.2f} GWh")
    """
    if seed is not None:
        np.random.seed(seed)

    logger.info(f"Starting Monte Carlo AEP simulation with {n_scenarios:,} scenarios")

    # Load AEP summary
    aep_data = load_aep_from_summary(aep_summary_path, validate_manifest=True)

    n_turbines = aep_data["n_turbines"]
    capacity_mw = aep_data["rated_power_kw"] / 1000.0

    # Extract loss factors
    losses = aep_data.get("losses", {})
    wake_loss_base = wake_loss_mean_pct if wake_loss_mean_pct is not None else losses.get("wake_loss_pct", 8.0)
    avail_base = availability_mean_pct if availability_mean_pct is not None else losses.get("availability_pct", 97.0)
    elec_loss_base = electrical_loss_mean_pct if electrical_loss_mean_pct is not None else losses.get("electrical_loss_pct", 2.0)

    # Estimate Weibull parameters from AEP (if not provided)
    if weibull_a_mean is None:
        # Rough estimate: A ≈ mean_ws ≈ (AEP / (CF * 8760 * capacity))^(1/3) * 7.5
        cf = aep_data["capacity_factor"]
        mean_ws_estimate = 7.5 * (cf / 0.35) ** (1/3)  # Heuristic
        weibull_a_mean = mean_ws_estimate

    if weibull_k_mean is None:
        weibull_k_mean = 2.0  # Rayleigh distribution (typical for wind)

    logger.info(
        f"Weibull parameters: A={weibull_a_mean:.2f} m/s, k={weibull_k_mean:.2f}\n"
        f"Loss factors: wake={wake_loss_base:.1f}%, avail={avail_base:.1f}%, elec={elec_loss_base:.1f}%"
    )

    # Load power curve
    power_curve = parse_envision_en171_curve(air_density_kgm3=air_density_kgm3)

    # Monte Carlo sampling
    aep_scenarios = []

    # Sample Weibull parameters
    weibull_a_samples = np.random.normal(
        weibull_a_mean,
        weibull_a_mean * weibull_uncertainty_pct / 100.0,
        n_scenarios
    )
    weibull_a_samples = np.clip(weibull_a_samples, 4.0, 15.0)  # Realistic range

    weibull_k_samples = np.random.normal(
        weibull_k_mean,
        weibull_k_mean * weibull_uncertainty_pct / 100.0,
        n_scenarios
    )
    weibull_k_samples = np.clip(weibull_k_samples, 1.5, 3.0)  # Realistic range

    # Sample loss factors
    wake_loss_samples = np.random.normal(
        wake_loss_base,
        wake_loss_std_pct,
        n_scenarios
    )
    wake_loss_samples = np.clip(wake_loss_samples, 0.0, 20.0)

    avail_samples = np.random.normal(
        avail_base,
        availability_std_pct,
        n_scenarios
    )
    avail_samples = np.clip(avail_samples, 90.0, 100.0)

    elec_loss_samples = np.random.normal(
        elec_loss_base,
        electrical_loss_std_pct,
        n_scenarios
    )
    elec_loss_samples = np.clip(elec_loss_samples, 0.0, 5.0)

    # Run scenarios (vectorized for speed)
    logger.info("Generating wind distributions and computing AEP...")

    for i in range(n_scenarios):
        if (i + 1) % 10000 == 0:
            logger.info(f"  Scenario {i+1:,} / {n_scenarios:,}")

        # Generate 8760-hour wind distribution
        wind_8760 = np.random.weibull(weibull_k_samples[i], 8760) * weibull_a_samples[i]

        # Compute AEP with sampled loss factors
        aep_gwh, cf, _ = compute_aep_from_curve(
            wind_dist_ms=wind_8760,
            curve=power_curve,
            n_turbines=n_turbines,
            capacity_mw=capacity_mw,
            apply_losses=True,
            wake_loss_pct=wake_loss_samples[i],
            availability_pct=avail_samples[i],
            electrical_loss_pct=elec_loss_samples[i],
        )

        aep_scenarios.append({
            "scenario_id": i,
            "aep_gwh": aep_gwh,
            "capacity_factor": cf,
            "weibull_a": weibull_a_samples[i],
            "weibull_k": weibull_k_samples[i],
            "wake_loss_pct": wake_loss_samples[i],
            "availability_pct": avail_samples[i],
            "electrical_loss_pct": elec_loss_samples[i],
        })

    # Convert to DataFrame
    scenarios_df = pd.DataFrame(aep_scenarios)

    # Compute statistics
    aep_values = scenarios_df["aep_gwh"].values

    percentiles = {
        "p50": float(np.percentile(aep_values, 50)),
        "p75": float(np.percentile(aep_values, 75)),
        "p90": float(np.percentile(aep_values, 90)),
        "p99": float(np.percentile(aep_values, 99)),
    }

    confidence_intervals = {
        "ci95_lower": float(np.percentile(aep_values, 2.5)),
        "ci95_upper": float(np.percentile(aep_values, 97.5)),
    }

    statistics = {
        "mean": float(aep_values.mean()),
        "std": float(aep_values.std()),
        "cv": float(aep_values.std() / aep_values.mean()),  # Coefficient of variation
        "min": float(aep_values.min()),
        "max": float(aep_values.max()),
    }

    logger.info(
        f"\nMonte Carlo Results ({n_scenarios:,} scenarios):\n"
        f"  P50 AEP: {percentiles['p50']:.2f} GWh\n"
        f"  P75 AEP: {percentiles['p75']:.2f} GWh\n"
        f"  P90 AEP: {percentiles['p90']:.2f} GWh\n"
        f"  P99 AEP: {percentiles['p99']:.2f} GWh\n"
        f"  95% CI: [{confidence_intervals['ci95_lower']:.2f}, {confidence_intervals['ci95_upper']:.2f}] GWh\n"
        f"  Mean: {statistics['mean']:.2f} GWh\n"
        f"  Std: {statistics['std']:.2f} GWh\n"
        f"  CV: {statistics['cv']:.2%}"
    )

    # Export scenarios if requested
    if export_scenarios:
        if output_path is None:
            raise ValueError("output_path required when export_scenarios=True")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        scenarios_df.to_parquet(output_file, index=False, compression="snappy")
        logger.info(f"Scenarios exported to {output_path}")

    results = {
        "percentiles": percentiles,
        "confidence_intervals": confidence_intervals,
        "statistics": statistics,
        "n_scenarios": n_scenarios,
        "config": {
            "weibull_a_mean": weibull_a_mean,
            "weibull_k_mean": weibull_k_mean,
            "wake_loss_mean_pct": wake_loss_base,
            "availability_mean_pct": avail_base,
            "electrical_loss_mean_pct": elec_loss_base,
        },
    }

    if export_scenarios:
        results["scenarios"] = scenarios_df

    return results


__all__ = [
    "MC_CONFIG_PRODUCTION",
    "MC_CONFIG_TESTING",
    "run_monte_carlo_aep",
]
