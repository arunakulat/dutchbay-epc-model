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
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from analytics.loader.aep_loader import load_aep_from_summary
from analytics.power_curves.oem_parser import compute_aep_from_curve, parse_power_curve

# DEFAULT_WIND_LOSSES is imported LAZILY inside run_monte_carlo_aep (not here) to avoid a
# circular import: analytics.wind.__init__ -> analytics.wind.pipeline_aep_v14 ->
# analytics.simulation.monte_carlo_aep. A module-level `from analytics.wind.losses_model
# import ...` triggers analytics.wind.__init__ while this module is still importing (when
# monte_carlo_aep is imported BEFORE analytics.wind), raising ImportError.

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
) -> Dict[str, Any]:
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
    # MC-5 (#473): use an ISOLATED modern Generator (PCG64) seeded locally instead of the
    # process-global np.random state. The old np.random.seed(seed) + module-global draws
    # polluted/were-polluted-by any other code touching np.random and were not thread-safe;
    # default_rng(seed) confines the stream to this call. Same seed -> reproducible (MRM-01);
    # default_rng(None) self-seeds. The absolute MC-band stats shift vs the legacy Mersenne
    # stream (PCG64 != MT19937) but no committed scenario KPI / lender case depends on them —
    # they are an uncertainty sidecar, asserted by structure/tolerance, not exact value.
    rng = np.random.default_rng(seed)

    logger.info(f"Starting Monte Carlo AEP simulation with {n_scenarios:,} scenarios")

    # Lazy import (breaks the analytics.wind <-> monte_carlo_aep cycle; see module top).
    from analytics.wind.losses_model import DEFAULT_WIND_LOSSES

    # Load AEP summary
    aep_data = load_aep_from_summary(aep_summary_path, validate_manifest=True)

    n_turbines = aep_data["n_turbines"]
    capacity_mw = aep_data["rated_power_kw"] / 1000.0

    # Extract loss factors
    losses = aep_data.get("losses", {})
    wake_loss_base = (
        wake_loss_mean_pct
        if wake_loss_mean_pct is not None
        else losses.get("wake_loss_pct", DEFAULT_WIND_LOSSES["wake_loss_pct"])
    )
    avail_base = (
        availability_mean_pct
        if availability_mean_pct is not None
        else losses.get("availability_pct", DEFAULT_WIND_LOSSES["availability_pct"])
    )
    elec_loss_base = (
        electrical_loss_mean_pct
        if electrical_loss_mean_pct is not None
        else losses.get(
            "electrical_loss_pct", DEFAULT_WIND_LOSSES["electrical_loss_pct"]
        )
    )

    # compute_aep_from_curve only samples wake/availability/electrical. Every OTHER
    # reduction line in the taxonomy (curtailment, other, and any finer IEC sub-loss
    # a scenario itemises — turbine performance, icing, transmission, …) is applied
    # as a fixed multiplicative retention so the net stack is complete. Delegating to
    # losses_model.compute_net_factor (excluding the sampled wake/electrical and the
    # uptime availability) means new taxonomy keys are honoured automatically and an
    # unknown loss key fails loud instead of being silently dropped — the same
    # config-driven taxonomy as apply_losses. For the canonical stack this is exactly
    # curtailment × other, so the result is numerically unchanged.
    from analytics.wind.losses_model import compute_net_factor

    fixed_loss_retention = compute_net_factor(
        losses,
        exclude={"wake_loss_pct", "electrical_loss_pct", "availability_pct"},
    )

    # Estimate Weibull parameters from AEP (if not provided)
    if weibull_a_mean is None:
        # Rough estimate: A ≈ mean_ws ≈ (AEP / (CF * 8760 * capacity))^(1/3) * 7.5
        cf = aep_data["capacity_factor"]
        mean_ws_estimate = 7.5 * (cf / 0.35) ** (1 / 3)  # Heuristic
        weibull_a_mean = mean_ws_estimate

    if weibull_k_mean is None:
        weibull_k_mean = 2.0  # Rayleigh distribution (typical for wind)

    logger.info(
        f"Weibull parameters: A={weibull_a_mean:.2f} m/s, k={weibull_k_mean:.2f}\n"
        f"Loss factors: wake={wake_loss_base:.1f}%, avail={avail_base:.1f}%, elec={elec_loss_base:.1f}%"
    )

    # Load the power curve the AEP summary was computed with (the model's
    # selection), not a hardwired turbine (GWTF ARCH-01). REQUIRED — a summary
    # without a recorded curve must fail loud rather than silently Monte-Carlo the
    # legacy Envision turbine. Every valid summary records power_curve_key.
    if not aep_data.get("power_curve_key"):
        raise KeyError(
            "AEP summary is missing 'power_curve_key' — cannot Monte-Carlo without "
            "the project's turbine curve (no silent fallback to the legacy curve)."
        )
    curve_key = str(aep_data["power_curve_key"])
    power_curve = parse_power_curve(curve_key, air_density_kgm3=air_density_kgm3)

    # Monte Carlo sampling
    aep_scenarios = []

    # Sample Weibull parameters
    weibull_a_samples = rng.normal(
        weibull_a_mean, weibull_a_mean * weibull_uncertainty_pct / 100.0, n_scenarios
    )
    weibull_a_samples = np.clip(weibull_a_samples, 4.0, 15.0)  # Realistic range

    weibull_k_samples = rng.normal(
        weibull_k_mean, weibull_k_mean * weibull_uncertainty_pct / 100.0, n_scenarios
    )
    weibull_k_samples = np.clip(weibull_k_samples, 1.5, 3.0)  # Realistic range

    # Sample loss factors
    wake_loss_samples = rng.normal(wake_loss_base, wake_loss_std_pct, n_scenarios)
    wake_loss_samples = np.clip(wake_loss_samples, 0.0, 20.0)

    avail_samples = rng.normal(avail_base, availability_std_pct, n_scenarios)
    avail_samples = np.clip(avail_samples, 90.0, 100.0)

    elec_loss_samples = rng.normal(elec_loss_base, electrical_loss_std_pct, n_scenarios)
    elec_loss_samples = np.clip(elec_loss_samples, 0.0, 5.0)

    # Run scenarios (vectorized for speed)
    logger.info("Generating wind distributions and computing AEP...")

    for i in range(n_scenarios):
        if (i + 1) % 10000 == 0:
            logger.info(f"  Scenario {i+1:,} / {n_scenarios:,}")

        # Generate 8760-hour wind distribution
        wind_8760 = rng.weibull(weibull_k_samples[i], 8760) * weibull_a_samples[i]

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

        # Apply the remaining fixed loss components (curtailment + other) that
        # compute_aep_from_curve does not model, so the net stack is complete.
        aep_gwh *= fixed_loss_retention
        cf *= fixed_loss_retention

        aep_scenarios.append(
            {
                "scenario_id": i,
                "aep_gwh": aep_gwh,
                "capacity_factor": cf,
                "weibull_a": weibull_a_samples[i],
                "weibull_k": weibull_k_samples[i],
                "wake_loss_pct": wake_loss_samples[i],
                "availability_pct": avail_samples[i],
                "electrical_loss_pct": elec_loss_samples[i],
            }
        )

    # Convert to DataFrame
    scenarios_df = pd.DataFrame(aep_scenarios)

    # Compute statistics
    aep_values = scenarios_df["aep_gwh"].to_numpy()

    # Wind EXCEEDANCE convention: P90 = the AEP exceeded in 90% of years = the
    # 10th percentile of the sampled distribution (conservative, lender-facing);
    # P75 -> 25th, P99 -> 1st, P50 -> 50th. The prior code used the distribution
    # percentile directly (p90 = 90th = the *upside*), inverting the meaning and
    # injecting an over-optimistic "P90" into revenue/DSCR/IRR. This mirrors the
    # canonical analytics/wind/mc_aep_weibull.py:EXCEEDANCE_TO_PERCENTILE (kept
    # local to avoid the analytics.wind <-> analytics.simulation import cycle; the
    # two MC-AEP engines are slated for consolidation in the thinning pass).
    exceedance_to_pct = {"p50": 50.0, "p75": 25.0, "p90": 10.0, "p99": 1.0}
    percentiles = {
        name: float(np.percentile(aep_values, pct))
        for name, pct in exceedance_to_pct.items()
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
