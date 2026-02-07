#!/usr/bin/env python
"""Wind Resource Assessment and Financial Analysis Pipeline.

Integrates wind_resource module for complete wind-to-finance workflow:
1. ERA5 data download and processing (wind_resource.ERA5Fetcher)
2. Statistical analysis with Weibull fitting (wind_resource.WindAnalyzer)
3. Energy calculations with loss factors (wind_resource.EnergyCalculator)
4. Monte Carlo simulation for uncertainty
5. Financial analysis integration

Usage:
    # CLI (Hydra)
    python run_full_pipeline_v14.py \\
      config=scenarios/dutchbay_lendercase_2025Q4.yaml
    
    # Python API
    from analytics.pipeline_v14 import run_v14_pipeline
    
    results = run_v14_pipeline(
        config='scenarios/dutchbay_lendercase_2025Q4.yaml',
        validation_mode='strict'
    )

GWTF Compliance:
- R3: Hydra-only (no argparse)
- CCCDIR: All config from YAML files
- R24: Google-style docstrings
- TYPE-01: Full type hints

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 2.0.0 (Integrated wind_resource)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from omegaconf import DictConfig, OmegaConf

from wind_resource import WindPipeline

logger = logging.getLogger(__name__)


def run_v14_pipeline(
    config: str,
    validation_mode: str = "strict",
    validation_modules: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """Run complete v14 pipeline with wind resource integration.

    Args:
        config: Path to scenario YAML file.
        validation_mode: Validation mode ('strict' or 'off').
        validation_modules: List of modules to validate.

    Returns:
        Dictionary containing:
            - wind_assessment: Complete wind resource analysis
            - aep_p50_mwh: P50 net AEP (MWh/year)
            - aep_p75_mwh: P75 net AEP (MWh/year)
            - revenue_annual_p75_usd: Annual revenue P75
            - capacity_factor: Net capacity factor
            - status: 'success' or 'error'

    Raises:
        FileNotFoundError: If config file not found.
        ValueError: If config validation fails.

    Example:
        >>> results = run_v14_pipeline(
        ...     config='scenarios/dutchbay_lendercase_2025Q4.yaml',
        ...     validation_mode='strict'
        ... )
        >>> print(f"P75 AEP: {results['aep_p75_mwh']:,.0f} MWh/year")
    """
    logger.info("=" * 80)
    logger.info("DUTCHBAY WIND FARM - INTEGRATED PIPELINE V14")
    logger.info("=" * 80)

    # Load scenario configuration
    config_path = Path(config)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config}")

    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    cfg = OmegaConf.create(cfg)

    logger.info(f"Project: {cfg.project.name}")
    logger.info(f"Scenario: {config_path.stem}")
    logger.info(f"Capacity: {cfg.project.capacity_mw} MW")
    logger.info("=" * 80)

    # Step 1: Schema validation (if enabled)
    if validation_mode == "strict":
        logger.info("\n[1/4] Running schema validation...")
        from schema import schema_guard

        validation_result = schema_guard.validate_config(
            cfg,
            modules=validation_modules or ["all"]
        )

        if not validation_result["valid"]:
            error_msg = f"Schema validation failed: {validation_result['errors']}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "validation_result": validation_result
            }

        logger.info("✓ Schema validation passed")

    # Step 2: Wind Resource Assessment
    logger.info("\n[2/4] Running wind resource assessment...")

    # Extract wind farm configuration from scenario
    location = {
        "name": cfg.project.location,
        "lat": cfg.project.get("latitude", 8.33),
        "lon": cfg.project.get("longitude", 79.76)
    }

    # Initialize WindPipeline
    pipeline = WindPipeline(
        location=location,
        hub_height=cfg.turbine.hub_height_m,
        turbine_model=cfg.turbine.model,
        num_turbines=cfg.turbine.n_turbines,
        cache_dir="inputs/wind_data",
        output_dir="outputs/wind_assessment"
    )

    # Run complete assessment
    wind_results = pipeline.run_complete_assessment(
        start_date=cfg.wind_resource.get("start_date", "2014-12-01"),
        end_date=cfg.wind_resource.get("end_date", "2025-12-31"),
        force_download=False
    )

    logger.info(f"✓ Wind assessment complete")
    logger.info(f"  Mean wind speed: {wind_results['wind_data']['mean_ws']:.2f} m/s")
    logger.info(f"  Gross CF: {wind_results['energy_production']['gross_aep']['capacity_factor_gross']:.1f}%")
    logger.info(f"  Net AEP P75: {wind_results['energy_production']['net_aep']['net_aep_p75_mwh']:,.0f} MWh/year")

    # Step 3: Export for cashflow model
    logger.info("\n[3/4] Exporting for cashflow model integration...")

    export_scenario = cfg.get("export_scenario", "P75")
    cashflow_data = pipeline.export_for_cashflow_model(scenario=export_scenario)

    # Save cashflow export
    output_dir = Path("outputs/wind_assessment")
    output_dir.mkdir(parents=True, exist_ok=True)

    cashflow_export_path = output_dir / f"cashflow_export_{export_scenario}.json"
    with open(cashflow_export_path, "w") as f:
        json.dump(cashflow_data, f, indent=2)

    logger.info(f"✓ Cashflow export saved: {cashflow_export_path}")

    # Step 4: Build complete results
    logger.info("\n[4/4] Building pipeline results...")

    results = {
        "status": "success",
        "config": {
            "scenario": config_path.stem,
            "project_name": cfg.project.name,
            "capacity_mw": cfg.project.capacity_mw,
            "turbines": cfg.turbine.n_turbines,
            "turbine_model": cfg.turbine.model
        },
        "wind_assessment": wind_results,
        "cashflow_export": cashflow_data,
        # Key metrics for downstream use
        "aep_p50_mwh": wind_results['energy_production']['net_aep']['net_aep_p50_mwh'],
        "aep_p75_mwh": wind_results['energy_production']['net_aep']['net_aep_p75_mwh'],
        "aep_p90_mwh": wind_results['energy_production']['net_aep']['net_aep_p90_mwh'],
        "capacity_factor_net_p75": wind_results['energy_production']['net_aep']['capacity_factor_net_p75'],
        "revenue_annual_p75_usd": cashflow_data['revenue_annual_usd'],
        "weibull_k": wind_results['statistical_analysis']['weibull']['shape_k'],
        "weibull_c": wind_results['statistical_analysis']['weibull']['scale_c'],
        "mean_wind_speed_ms": wind_results['wind_data']['mean_ws'],
        "output_files": {
            "assessment": str(output_dir / f"{location['name']}_assessment.json"),
            "cashflow_export": str(cashflow_export_path)
        }
    }

    logger.info("\n" + "=" * 80)
    logger.info("✓ PIPELINE COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Net AEP P75: {results['aep_p75_mwh']:,.0f} MWh/year")
    logger.info(f"Net CF P75: {results['capacity_factor_net_p75']:.1f}%")
    logger.info(f"Annual Revenue P75: ${results['revenue_annual_p75_usd']:,.0f}")
    logger.info("=" * 80)

    return results
