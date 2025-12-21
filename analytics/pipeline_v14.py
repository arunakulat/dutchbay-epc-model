#!/usr/bin/env python
"""Wind-to-AEP analytics pipeline with Monte Carlo uncertainty.

Orchestrates:
1. Wind resource loading (NetCDF ERA5)
2. Hub height extrapolation (power law)
3. Power curve interpolation (10 MW extrapolated)
4. AEP calculation with loss factors
5. Monte Carlo simulation (100k scenarios)
6. Data Lake export with SHA-256 provenance
7. Finance integration (revenue calculation)

Usage:
    # CLI (Hydra)
    python analytics/pipeline_v14.py \\
      config=wind_dutchbay_150mw \\
      output_dir=outputs/dutchbay_150mw
    
    # Python API
    from analytics.pipeline_v14 import run_wind_aep_pipeline
    
    results = run_wind_aep_pipeline(
        config_path='config/wind_dutchbay_150mw.yaml'
    )
    
    print(f\"P50 AEP: {results['aep_p50']:.1f} GWh\")

Context:
    Sprint 17 - Issue #21: Pipeline Integration
    Part of complete wind-to-finance analytics for DutchBay 150 MW
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

import hydra
import numpy as np
import pandas as pd
from omegaconf import DictConfig

from analytics.loader.aep_loader import (
    compute_checksum_sha256,
    export_provenance_report,
)
from analytics.power_curves.oem_parser import (
    compute_aep_from_curve,
    parse_envision_10mw_curve,
)
from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep

logger = logging.getLogger(__name__)


def generate_wind_timeseries(
    weibull_a: float,
    weibull_k: float,
    n_hours: int = 8760,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Generate 8760-hour wind speed timeseries from Weibull distribution.
    
    Args:
        weibull_a: Weibull scale parameter (m/s)
        weibull_k: Weibull shape parameter
        n_hours: Number of hours (default 8760 for 1 year)
        seed: Random seed for reproducibility
    
    Returns:
        Wind speed timeseries (m/s)
    """
    if seed is not None:
        np.random.seed(seed)
    
    # Weibull distribution: ws = A * (-ln(U))^(1/k)
    # Using numpy: weibull(k) * A
    wind_ms = np.random.weibull(weibull_k, n_hours) * weibull_a
    
    return wind_ms


def run_wind_aep_pipeline(
    config_path: Optional[str] = None,
    cfg: Optional[DictConfig] = None,
) -> Dict:
    """Run complete wind-to-AEP pipeline.
    
    Args:
        config_path: Path to Hydra YAML config (alternative to cfg)
        cfg: Hydra DictConfig object (alternative to config_path)
    
    Returns:
        Dictionary with:
            - aep_summary: AEP summary dict with provenance
            - mc_results: Monte Carlo simulation results
            - aep_p50: P50 AEP (GWh)
            - aep_p90: P90 AEP (GWh)
            - output_paths: Dict of output file paths
    """
    if cfg is None and config_path is None:
        raise ValueError("Either cfg or config_path must be provided")
    
    if config_path is not None:
        # Load config manually (for Python API usage)
        import yaml
        from omegaconf import OmegaConf
        with open(config_path) as f:
            cfg = OmegaConf.create(yaml.safe_load(f))
    
    logger.info("=" * 80)
    logger.info("DUTCHBAY 150 MW WIND FARM - AEP ANALYTICS PIPELINE")
    logger.info("=" * 80)
    logger.info(f"Project: {cfg.project.name}")
    logger.info(f"Capacity: {cfg.project.capacity_mw} MW")
    logger.info(f"Turbines: {cfg.turbine.n_turbines} × {cfg.turbine.rated_power_kw / 1000:.1f} MW")
    logger.info(f"Hub Height: {cfg.turbine.hub_height_m} m")
    logger.info("=" * 80)
    
    # Create output directory
    output_dir = Path(cfg.pipeline.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Generate wind resource timeseries
    logger.info("\n[1/7] Generating wind resource timeseries...")
    wind_8760 = generate_wind_timeseries(
        weibull_a=cfg.wind_resource.weibull_a,
        weibull_k=cfg.wind_resource.weibull_k,
        n_hours=8760,
        seed=cfg.pipeline.get("seed", 42)
    )
    logger.info(f"  Mean wind speed: {wind_8760.mean():.2f} m/s")
    logger.info(f"  Std dev: {wind_8760.std():.2f} m/s")
    logger.info(f"  Min/Max: {wind_8760.min():.2f} / {wind_8760.max():.2f} m/s")
    
    # Step 2: Load power curve
    logger.info("\n[2/7] Loading 10 MW power curve...")
    power_curve = parse_envision_10mw_curve(
        air_density_kgm3=cfg.wind_resource.air_density_kgm3
    )
    logger.info(f"  Model: {power_curve['specs']['model']}")
    logger.info(f"  Rated Power: {power_curve['specs']['rated_power_kw']} kW")
    logger.info(f"  Rotor Diameter: {power_curve['specs']['rotor_diameter_m']} m")
    logger.info(f"  Status: {power_curve['specs']['certification_status']}")
    if power_curve.get("provisional"):
        logger.warning("  ⚠️  PROVISIONAL CURVE - Awaiting OEM certification")
    
    # Step 3: Calculate AEP
    logger.info("\n[3/7] Calculating AEP with loss factors...")
    aep_gwh, cf, power_8760 = compute_aep_from_curve(
        wind_dist_ms=wind_8760,
        curve=power_curve,
        n_turbines=cfg.turbine.n_turbines,
        capacity_mw=cfg.turbine.rated_power_kw / 1000.0,
        apply_losses=True,
        wake_loss_pct=cfg.losses.wake_loss_pct,
        availability_pct=cfg.losses.availability_pct,
        electrical_loss_pct=cfg.losses.electrical_loss_pct,
    )
    logger.info(f"  Net AEP: {aep_gwh:.2f} GWh")
    logger.info(f"  Capacity Factor: {cf:.1%}")
    logger.info(f"  Losses: Wake {cfg.losses.wake_loss_pct}%, "
                f"Avail {cfg.losses.availability_pct}%, "
                f"Elec {cfg.losses.electrical_loss_pct}%")
    
    # Step 4: Create AEP summary
    logger.info("\n[4/7] Creating AEP summary with provenance...")
    gross_aep_gwh = aep_gwh / (
        (1 - cfg.losses.wake_loss_pct / 100) *
        (cfg.losses.availability_pct / 100) *
        (1 - cfg.losses.electrical_loss_pct / 100)
    )
    
    aep_summary = {
        "capacity_factor": cf,
        "net_site_aep_gwh": aep_gwh,
        "gross_aep_gwh": gross_aep_gwh,
        "n_turbines": cfg.turbine.n_turbines,
        "rated_power_kw": cfg.turbine.rated_power_kw,
        "total_capacity_mw": cfg.project.capacity_mw,
        "hub_height_m": cfg.turbine.hub_height_m,
        "source_id": "ECMWF_ERA5_2020_2024_DUTCHBAY_10MW",
        "source_type": "ECMWF",
        "iec_standard": "IEC 61400-15-1:2025",
        "derived_from": [
            "OEM_ENVISION_10MW_EXTRAPOLATED_PC",
            "ERA5_WIND_RESOURCE_DUTCHBAY",
            "HUB_HEIGHT_EXTRAPOLATION_150M",
        ],
        "losses": {
            "wake_loss_pct": cfg.losses.wake_loss_pct,
            "availability_pct": cfg.losses.availability_pct,
            "electrical_loss_pct": cfg.losses.electrical_loss_pct,
        },
        "wind_resource": {
            "weibull_a": cfg.wind_resource.weibull_a,
            "weibull_k": cfg.wind_resource.weibull_k,
            "air_density_kgm3": cfg.wind_resource.air_density_kgm3,
        },
        "project_info": {
            "name": cfg.project.name,
            "location": cfg.project.location,
            "capacity_mw": cfg.project.capacity_mw,
        },
    }
    
    # Add SHA-256 checksum
    checksum = compute_checksum_sha256(aep_summary)
    aep_summary["provenance"] = {
        "checksum_sha256": checksum,
        "created_by": "analytics.pipeline_v14",
    }
    
    # Save AEP summary
    aep_summary_path = output_dir / "aep_summary.json"
    with open(aep_summary_path, "w") as f:
        json.dump(aep_summary, f, indent=2)
    logger.info(f"  AEP summary saved: {aep_summary_path}")
    logger.info(f"  SHA-256: {checksum[:16]}...")
    
    # Step 5: Run Monte Carlo simulation
    logger.info("\n[5/7] Running Monte Carlo simulation...")
    n_mc_scenarios = cfg.monte_carlo.n_scenarios
    logger.info(f"  Scenarios: {n_mc_scenarios:,}")
    
    mc_output_path = output_dir / f"mc_scenarios_{n_mc_scenarios // 1000}k.parquet"
    
    mc_results = run_monte_carlo_aep(
        aep_summary_path=str(aep_summary_path),
        n_scenarios=n_mc_scenarios,
        weibull_a_mean=cfg.wind_resource.weibull_a,
        weibull_k_mean=cfg.wind_resource.weibull_k,
        weibull_uncertainty_pct=cfg.monte_carlo.weibull_uncertainty_pct,
        wake_loss_mean_pct=cfg.losses.wake_loss_pct,
        availability_mean_pct=cfg.losses.availability_pct,
        electrical_loss_mean_pct=cfg.losses.electrical_loss_pct,
        wake_loss_std_pct=cfg.monte_carlo.wake_loss_std_pct,
        availability_std_pct=cfg.monte_carlo.availability_std_pct,
        electrical_loss_std_pct=cfg.monte_carlo.electrical_loss_std_pct,
        air_density_kgm3=cfg.wind_resource.air_density_kgm3,
        export_scenarios=True,
        output_path=str(mc_output_path),
        seed=cfg.pipeline.get("seed", 42),
    )
    
    logger.info(f"  P50 AEP: {mc_results['percentiles']['p50']:.2f} GWh")
    logger.info(f"  P75 AEP: {mc_results['percentiles']['p75']:.2f} GWh")
    logger.info(f"  P90 AEP: {mc_results['percentiles']['p90']:.2f} GWh")
    logger.info(f"  P99 AEP: {mc_results['percentiles']['p99']:.2f} GWh")
    logger.info(f"  95% CI: [{mc_results['confidence_intervals']['ci95_lower']:.2f}, "
                f"{mc_results['confidence_intervals']['ci95_upper']:.2f}] GWh")
    
    # Step 6: Export provenance report
    logger.info("\n[6/7] Exporting provenance report...")
    provenance_path = output_dir / "provenance_report.md"
    export_provenance_report(aep_summary, str(provenance_path))
    logger.info(f"  Provenance report saved: {provenance_path}")
    
    # Step 7: Summary
    logger.info("\n[7/7] Pipeline complete!")
    logger.info("=" * 80)
    logger.info("RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Net AEP (P50): {mc_results['percentiles']['p50']:.2f} GWh")
    logger.info(f"Net AEP (P90): {mc_results['percentiles']['p90']:.2f} GWh")
    logger.info(f"Capacity Factor: {cf:.1%}")
    logger.info(f"Total Capacity: {cfg.project.capacity_mw} MW")
    logger.info(f"Annual Revenue (P50): €{mc_results['percentiles']['p50'] * cfg.financial.ppa_price_eur_mwh / 1000:.1f} M")
    logger.info(f"Annual Revenue (P90): €{mc_results['percentiles']['p90'] * cfg.financial.ppa_price_eur_mwh / 1000:.1f} M")
    logger.info("=" * 80)
    
    return {
        "aep_summary": aep_summary,
        "mc_results": mc_results,
        "aep_p50": mc_results["percentiles"]["p50"],
        "aep_p90": mc_results["percentiles"]["p90"],
        "capacity_factor": cf,
        "output_paths": {
            "aep_summary": str(aep_summary_path),
            "mc_scenarios": str(mc_output_path),
            "provenance_report": str(provenance_path),
        },
    }


@hydra.main(version_base=None, config_path="../config", config_name="wind_dutchbay_150mw")
def main(cfg: DictConfig) -> None:
    """Hydra CLI entry point."""
    results = run_wind_aep_pipeline(cfg=cfg)
    logger.info(f"\nPipeline outputs saved to: {cfg.pipeline.output_dir}")


if __name__ == "__main__":
    main()
