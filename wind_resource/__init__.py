"""Wind Resource Assessment Module for Dutch Bay Wind Farm.

Provides comprehensive wind resource analysis tools including:
- ERA5 reanalysis data fetching (ERA5Fetcher)
- Statistical analysis and Weibull fitting (WindAnalyzer)
- Energy production calculations (EnergyCalculator)
- Complete assessment pipeline (WindPipeline)

All modules are CCCDIR compliant with configuration loaded from YAML files.

Quick Start (turbine/site identity is config-driven — no built-in defaults):
    >>> from wind_resource import WindPipeline
    >>> location = {'name': 'YourSite', 'lat': 8.33, 'lon': 79.76}
    >>> pipeline = WindPipeline(
    ...     location=location,
    ...     hub_height=cfg['turbine']['hub_height_m'],
    ...     turbine_model=cfg['turbine']['model'],
    ...     num_turbines=cfg['turbine']['n_turbines'],
    ... )
    >>> results = pipeline.run_complete_assessment(
    ...     start_date='2014-12-01',
    ...     end_date='2025-12-31'
    ... )

Modules:
    era5_fetcher: Download and process ERA5 wind data from Copernicus CDS.
    wind_analyzer: Statistical analysis including Weibull fitting and variability.
    energy_calculator: AEP calculations with loss factors and P-levels.
    wind_pipeline: Orchestrate complete assessment workflow.

Configuration:
    All configuration is centralized in wind_resource/config/:
    - era5_config.yaml: API settings, loss factors, P-levels
    - power_curves.yaml: Turbine power curve data
    - locations.yaml: Wind farm location definitions

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0 (CCCDIR Compliant)
"""

from wind_resource.energy_calculator import EnergyCalculator
from wind_resource.era5_fetcher import ERA5Fetcher
from wind_resource.wind_analyzer import WindAnalyzer
from wind_resource.wind_pipeline import WindPipeline

__version__ = "1.0.0"
__all__ = [
    "ERA5Fetcher",
    "WindAnalyzer",
    "EnergyCalculator",
    "WindPipeline",
]
