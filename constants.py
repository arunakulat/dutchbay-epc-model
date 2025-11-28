"""Project-wide constants and defaults."""

# Currency
DEFAULT_FX_USD_TO_LKR = 375.0

# Time
HOURS_PER_YEAR = 8760.0
DAYS_PER_YEAR = 365.0

# Project defaults
DEFAULT_PROJECT_LIFE_YEARS = 20
DEFAULT_CAPACITY_FACTOR = 0.40
DEFAULT_DEGRADATION = 0.005

# Financial defaults
DEFAULT_DISCOUNT_RATE = 0.08
DEFAULT_DSCR_THRESHOLD = 1.25
DEFAULT_DEBT_RATIO = 0.70
DEFAULT_TENOR_YEARS = 15

# Validation
MIN_CAPACITY_MW = 10.0
MAX_CAPACITY_MW = 1000.0
MIN_CAPACITY_FACTOR = 0.10
MAX_CAPACITY_FACTOR = 0.50
# =============================================================================
# Sensitivity Analysis Constants (Phase 3 - Added 2025-11-23)
# =============================================================================

from typing import Dict, Final

# Industry-standard sensitivity ranges (CFA/DFI benchmarks)
# Format: {parameter_name: (low_pct, high_pct)}
SENSITIVITY_RANGES: Final[Dict[str, tuple[float, float]]] = {
    "capex_usd_per_kw": (-20.0, +20.0),  # ±20% typical for Capex
    "tariff_lkr_per_kwh": (-15.0, +15.0),  # ±15% for revenue/tariff
    "capacity_factor_pct": (-10.0, +10.0),  # ±10% for generation
    "discount_rate_pct": (-3.0, +3.0),  # ±3 percentage points for WACC
    "debt_interest_rate_pct": (-2.0, +2.0),  # ±2 percentage points for debt
    "construction_months": (-6.0, +6.0),  # ±6 months schedule risk
    "opex_pct_revenue": (-5.0, +5.0),  # ±5% for O&M costs
    "grid_loss_pct": (-2.0, +2.0),  # ±2% for transmission losses
}

# Sensitivity analysis defaults
SENSITIVITY_DEFAULT_STEPS: Final[int] = 5  # Industry standard: 5 data points per sweep

# =============================================================================
# Monte Carlo Simulation Constants (Phase 3 - Added 2025-11-23)
# =============================================================================

# Default iteration count for Monte Carlo analysis (CFA Level III standard)
MONTE_CARLO_ITERATIONS: Final[int] = 10000
