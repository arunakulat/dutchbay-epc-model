"""Wind Resource Analysis Module for Dutch Bay Wind Farm.

This module provides comprehensive wind resource assessment capabilities including:
- ERA5 data download from Copernicus CDS
- Statistical wind analysis (Weibull, patterns, variability)
- Energy production calculations (gross/net AEP)
- Integration with financial models

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from .era5_fetcher import ERA5Fetcher
from .wind_analyzer import WindAnalyzer
from .energy_calculator import EnergyCalculator
from .wind_pipeline import WindPipeline

__all__ = [
    'ERA5Fetcher',
    'WindAnalyzer',
    'EnergyCalculator',
    'WindPipeline'
]

__version__ = '1.0.0'
