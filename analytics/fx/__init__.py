"""FX and Risk Analytics Subpackage (v14).

Provides advanced FX modeling, correlation analysis, and risk metrics
for project finance models. Independent of core v14 pipeline.

**Modules:**
- processor: Dual-regime FX data processor
- correlation: FX correlation engine and VaR/CVaR
- risk: Risk metrics (DSCR distributions, LLCR, PLCR)
- returns: Project and equity return calculations
- fx_contracts: Type-safe FX dataclasses
- fx_loader: Unified FX configuration loader

**Usage Example:**
    from analytics.fx import FXRegimeConfig, build_fx_curve

    config = FXRegimeConfig(
        base_currency='USD',
        target_currency='LKR',
        regime_type='recent',
        years=20,
        annual_depr=0.03,
        start_rate=330.0
    )

    curve = build_fx_curve(config)
    print(curve.rates)  # [330.0, 319.9, 310.1, ...]

**Note:**
This subpackage is independent from the main v14 pipeline.
Use only when advanced FX/risk analysis is required.

Part of: Sprint Day 5, Task 2 - FX-Risk Analytics Subpackage
"""

from __future__ import annotations

# Import contracts first (no dependencies)
from .fx_contracts import FXCorrelationMatrix, FXCurveOutput, FXRegimeConfig

# Import loaders second (depends on contracts)
from .fx_loader import build_fx_curve, discover_fx_files, load_fx_regime

__all__ = [
    # Contracts - Type-safe dataclasses
    "FXRegimeConfig",
    "FXCurveOutput",
    "FXCorrelationMatrix",
    # Loaders - FX configuration and curve building
    "load_fx_regime",
    "discover_fx_files",
    "build_fx_curve",
]
