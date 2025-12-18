#!/usr/bin/env python3
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
    from analytics.fx import FXStructuredBlock, build_fx_curve

    config = FXStructuredBlock(
        start_lkr_per_usd=375.0,
        annual_depr=0.03,
        base_currency='USD',
        target_currency='LKR',
    )

    curve = build_fx_curve(config)
    print(curve.rates)  # [375.0, 386.25, 397.84, ...]

**Note:**
This subpackage is independent from the main v14 pipeline.
Use only when advanced FX/risk analysis is required.

Part of: Sprint 14, Task 31 - FX-Risk Analytics Consolidation
"""
from __future__ import annotations

# =============================================================================
# v14 Structured Blocks Imports (Primary API)
# =============================================================================
from .fx_contracts import FXStructuredBlock  # ⭐ Primary v14 name
from .fx_contracts import (
    FXCorrelationMatrix,
    FXCurveOutput,
    FXMonteCarloConfig,
    FXRegimeScenario,
    FXRiskProfile,
    FXSensitivityConfig,
    RegimeType,
    VolatilityMethod,
)
from .fx_loader import build_fx_curve, discover_fx_files, load_fx_regime

# =============================================================================
# Backward Compatibility Alias (GWTF Compliant - NO REGRESSION)
# =============================================================================
FXRegimeConfig = FXStructuredBlock  # Deprecated: use FXStructuredBlock

# =============================================================================
# Explicit Exports
# =============================================================================
__all__ = [
    # Core Contracts (v14 Primary)
    "FXStructuredBlock",  # ⭐ New v14-compliant name
    "FXCurveOutput",
    "FXCorrelationMatrix",
    # Enums
    "RegimeType",
    "VolatilityMethod",
    # Scenario & Risk Contracts
    "FXRegimeScenario",
    "FXRiskProfile",
    "FXSensitivityConfig",
    "FXMonteCarloConfig",
    # Loaders
    "load_fx_regime",
    "discover_fx_files",
    "build_fx_curve",
    # Backward Compatibility (Deprecated)
    "FXRegimeConfig",  # Alias to FXStructuredBlock - remove in v15+
]
