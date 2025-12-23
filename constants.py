"""Project-wide constants and conversions.

This module contains ONLY immutable physical constants and unit conversions.
All project defaults, thresholds, and configurable values MUST be in:
- config/defaults.yaml
- scenarios/*.yaml

GWTF Compliance:
- CCCDIR: Configuration in Config DIRectory
- No magic numbers or hardcoded business logic values
- Only universal physical/mathematical constants allowed

Author: Dutch Bay EPC Model Team
Date: December 2025
Version: 2.0.0 (CCCDIR Compliant)
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# PHYSICAL CONSTANTS (Immutable - OK to keep here)
# =============================================================================

# Time conversions (universal constants)
HOURS_PER_YEAR: Final[float] = 8760.0
DAYS_PER_YEAR: Final[int] = 365
MONTHS_PER_YEAR: Final[int] = 12
QUARTERS_PER_YEAR: Final[int] = 4

# Energy conversions
KW_TO_MW: Final[float] = 0.001
MW_TO_GW: Final[float] = 0.001
KWH_TO_MWH: Final[float] = 0.001
MWH_TO_GWH: Final[float] = 0.001

# Percentage to decimal
PERCENT_TO_DECIMAL: Final[float] = 0.01

# =============================================================================
# REMOVED: All project defaults moved to config/defaults.yaml
# =============================================================================
# The following were REMOVED for CCCDIR compliance:
# - DEFAULT_FX_USD_TO_LKR → config/defaults.yaml: fx.start_lkr_per_usd
# - DEFAULT_PROJECT_LIFE_YEARS → config/defaults.yaml: project.life_years
# - DEFAULT_CAPACITY_FACTOR → wind_resource/config/era5_config.yaml
# - DEFAULT_DEGRADATION → config/defaults.yaml: degradation.annual_rate
# - DEFAULT_DISCOUNT_RATE → scenarios/*.yaml: financial.discount_rate_pct
# - DEFAULT_DSCR_THRESHOLD → config/defaults.yaml: debt.min_dscr
# - DEFAULT_DEBT_RATIO → scenarios/*.yaml: debt.ratio
# - DEFAULT_TENOR_YEARS → scenarios/*.yaml: debt.tenor_years
# - MIN/MAX_CAPACITY_MW → config/defaults.yaml: validation.capacity_mw_range
# - MIN/MAX_CAPACITY_FACTOR → config/defaults.yaml: validation.cf_range
# - SENSITIVITY_RANGES → config/defaults.yaml: sensitivity.ranges
# - MONTE_CARLO_ITERATIONS → config/defaults.yaml: monte_carlo.iterations

# =============================================================================
# Migration Note
# =============================================================================
# If you need these values, import from:
#   from omegaconf import OmegaConf
#   config = OmegaConf.load('config/defaults.yaml')
#   fx_rate = config.fx.start_lkr_per_usd
#
# For scenario-specific values:
#   config = OmegaConf.load(f'scenarios/{scenario_name}.yaml')
#   discount_rate = config.financial.discount_rate_pct
# =============================================================================
