"""Hydra CLI for Complete Wind Resource Analysis.

Runs complete wind resource assessment including:
- ERA5 data download
- Statistical analysis (Weibull, temporal patterns, variability)
- Energy production calculations (gross/net AEP, P50/P75/P90)
- Revenue projections
- JSON export for cashflow model integration

Follows GWTF R3 (Hydra-only) and CLI-03 (JSON-first) compliance.

Usage:
    Basic (DutchBay with Envision turbine):
        python run_wind_analysis_v14.py location=dutchbay
    
    With custom turbine model:
        python run_wind_analysis_v14.py \
            location=dutchbay \
            turbine_model=vestas_v150_5p6 \
            num_turbines=20
    
    Different date range:
        python run_wind_analysis_v14.py \
            location=dutchbay \
            start_date=2020-01-01 \
            end_date=2023-12-31
    
    Export different P-level scenario:
        python run_wind_analysis_v14.py \
            location=dutchbay \
            export_scenario=P90

Output:
    JSON to stdout with complete assessment results including:
    - Wind resource statistics (Weibull, variability)
    - Energy production (gross/net AEP for P50/P75/P90)
    - Revenue projections
    - Cashflow model export

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (GWTF R3, CLI-03 Compliant)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
import yaml
from omegaconf import DictConfig

from wind_resource import WindPipeline

logger = logging.getLogger(__name__)

# Remember original working directory (Hydra changes it)
_ORIG_CWD = Path.cwd()


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="wind_analysis",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI entry point for complete wind resource analysis.
    
    Args:
        cfg: Hydra configuration from conf/wind_analysis.yaml.
        
    Returns:
        None. Prints JSON result to stdout.
        
    Raises:
        SystemExit: If required parameters missing or errors occur.
    """
    # Undo Hydra's job-chdir to work from repo root
    os.chdir(_ORIG_CWD)
    
    # Validate required parameter
    location_name = cfg.get("location")
    if not location_name:
        error_result = {
            "status": "error",
            "error": "Missing required parameter 'location'",
            "usage": "python run_wind_analysis_v14.py location=dutchbay",
            "available_locations": _get_available_locations()
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)
    
    try:
        # Load location from config
        locations_file = Path("wind_resource/config/locations.yaml")
        if not locations_file.exists():
            raise FileNotFoundError(
                f"Locations config not found: {locations_file}"
            )
        
        with open(locations_file) as f:
            locations = yaml.safe_load(f)
        
        if location_name not in locations:
            error_result = {
                "status": "error",
                "error": f"Unknown location: {location_name}",
                "available_locations": list(locations.keys())
            }
            print(json.dumps(error_result, indent=2))
            raise SystemExit(1)
        
        location = locations[location_name]
        
        # Extract parameters from config
        start_date = cfg.get("start_date")
        end_date = cfg.get("end_date")
        hub_height = float(cfg.get("hub_height"))
        turbine_model = cfg.get("turbine_model")
        num_turbines = int(cfg.get("num_turbines"))
        force_download = bool(cfg.get("force_download", False))
        cache_dir = cfg.get("cache_dir")
        output_dir = cfg.get("output_dir")
        export_scenario = cfg.get("export_scenario", "P75")
        
        logger.info("=" * 70)
        logger.info("COMPLETE WIND RESOURCE ASSESSMENT")
        logger.info("=" * 70)
        logger.info(f"Location: {location_name} ({location['lat']:.2f}°N, {location['lon']:.2f}°E)")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Hub height: {hub_height}m")
        logger.info(f"Turbine: {turbine_model} x {num_turbines}")
        logger.info(f"Export scenario: {export_scenario}")
        
        # Initialize pipeline
        pipeline = WindPipeline(
            location=location,
            hub_height=hub_height,
            turbine_model=turbine_model,
            num_turbines=num_turbines,
            cache_dir=cache_dir,
            output_dir=output_dir
        )
        
        # Run complete assessment
        logger.info("\nRunning complete assessment pipeline...")
        assessment_results = pipeline.run_complete_assessment(
            start_date=start_date,
            end_date=end_date,
            force_download=force_download
        )
        
        # Export for cashflow model
        logger.info(f"\nExporting {export_scenario} scenario for cashflow model...")
        cashflow_export = pipeline.export_for_cashflow_model(scenario=export_scenario)
        
        # Build comprehensive result (JSON-first, CLI-03 compliance)
        result = {
            "status": "success",
            "location": {
                "name": location_name,
                "lat": location['lat'],
                "lon": location['lon']
            },
            "parameters": {
                "start_date": start_date,
                "end_date": end_date,
                "hub_height_m": hub_height,
                "turbine_model": turbine_model,
                "num_turbines": num_turbines,
                "total_capacity_mw": (num_turbines * assessment_results['metadata']['configuration']['rated_capacity_kw']) / 1000
            },
            "wind_resource": {
                "mean_wind_speed_ms": assessment_results['wind_data']['mean_ws'],
                "weibull_shape_k": assessment_results['statistical_analysis']['weibull']['shape_k'],
                "weibull_scale_c_ms": assessment_results['statistical_analysis']['weibull']['scale_c'],
                "r_squared": assessment_results['statistical_analysis']['weibull']['r_squared'],
                "interannual_cov_percent": assessment_results['statistical_analysis']['variability']['cov_annual_ws'],
                "windiest_month": assessment_results['statistical_analysis']['temporal']['windiest_month'],
                "calmest_month": assessment_results['statistical_analysis']['temporal']['calmest_month']
            },
            "energy_production": {
                "gross_capacity_factor_percent": assessment_results['energy_production']['gross_aep']['capacity_factor_gross'],
                "gross_aep_gwh": assessment_results['energy_production']['gross_aep']['windfarm_aep_mwh'] / 1000,
                "net_aep_p50_gwh": assessment_results['energy_production']['net_aep']['net_aep_p50_mwh'] / 1000,
                "net_aep_p75_gwh": assessment_results['energy_production']['net_aep']['net_aep_p75_mwh'] / 1000,
                "net_aep_p90_gwh": assessment_results['energy_production']['net_aep']['net_aep_p90_mwh'] / 1000,
                "net_capacity_factor_p50_percent": assessment_results['energy_production']['net_aep']['capacity_factor_net_p50'],
                "net_capacity_factor_p75_percent": assessment_results['energy_production']['net_aep']['capacity_factor_net_p75'],
                "net_capacity_factor_p90_percent": assessment_results['energy_production']['net_aep']['capacity_factor_net_p90'],
                "total_loss_factor": assessment_results['energy_production']['net_aep']['total_loss_factor'],
                "individual_losses": assessment_results['energy_production']['net_aep']['individual_losses']
            },
            "revenue": {
                "tariff_lkr_per_kwh": assessment_results['energy_production']['revenue']['tariff_lkr_per_kwh'],
                "exchange_rate_lkr_usd": assessment_results['energy_production']['revenue']['exchange_rate_lkr_usd'],
                "ppa_years": assessment_results['energy_production']['revenue']['ppa_years'],
                "annual_revenue_p50_usd": assessment_results['energy_production']['revenue']['annual_revenue_p50_usd'],
                "annual_revenue_p75_usd": assessment_results['energy_production']['revenue']['annual_revenue_p75_usd'],
                "annual_revenue_p90_usd": assessment_results['energy_production']['revenue']['annual_revenue_p90_usd'],
                "cumulative_revenue_p50_usd": assessment_results['energy_production']['revenue']['cumulative_revenue_p50_usd'],
                "cumulative_revenue_p75_usd": assessment_results['energy_production']['revenue']['cumulative_revenue_p75_usd'],
                "cumulative_revenue_p90_usd": assessment_results['energy_production']['revenue']['cumulative_revenue_p90_usd']
            },
            "cashflow_export": cashflow_export,
            "output_files": {
                "complete_assessment": str(Path(output_dir) / f"{location_name}_assessment_{start_date}_to_{end_date}.json"),
                "cashflow_export": str(Path(output_dir) / f"{location_name}_cashflow_export_{export_scenario}.json")
            },
            "message": f"✓ Complete assessment finished for {location_name} ({export_scenario} scenario)"
        }
        
        logger.info("\n" + "=" * 70)
        logger.info("✓ ASSESSMENT COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Mean Wind Speed: {result['wind_resource']['mean_wind_speed_ms']:.2f} m/s")
        logger.info(f"Gross CF: {result['energy_production']['gross_capacity_factor_percent']:.1f}%")
        logger.info(f"Net AEP {export_scenario}: {result['energy_production'][f'net_aep_{export_scenario.lower()}_gwh']:.1f} GWh/year")
        logger.info(f"Annual Revenue {export_scenario}: ${result['revenue'][f'annual_revenue_{export_scenario.lower()}_usd']:,.0f}")
        logger.info("=" * 70)
        
        # Output JSON (CLI-03 compliance)
        print(json.dumps(result, indent=2, sort_keys=True))
        
    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "location": location_name if 'location_name' in locals() else None
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Error during wind resource analysis")
        raise SystemExit(1) from e


def _get_available_locations() -> list[str]:
    """Get list of available locations from config.
    
    Returns:
        List of location names, or empty list if config not found.
    """
    try:
        locations_file = Path("wind_resource/config/locations.yaml")
        if locations_file.exists():
            with open(locations_file) as f:
                locations = yaml.safe_load(f)
            return list(locations.keys())
        return []
    except Exception:
        return []


if __name__ == "__main__":
    cli()
