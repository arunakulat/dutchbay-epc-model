"""
Finance Contracts Package for v14 Analytics.

Sprint 16 Consolidation
═══════════════════════════════════════════════════════════════
Consolidates all contract definitions into a single clean import location.

Public API
──────────────────────────────────────────────────────────────
From v14 contracts:
    - CASPER_CONTRACT_VERSION   # Contract versioning
    
    Monte Carlo (Sprint 16 - Issue #43):
    - Distribution              # Distribution specification
    - DerivedParameter          # Computed parameters
    - MonteCarloScenario        # MC scenario config
    - MonteCarloResult          # MC execution output
    
    WACC:
    - WaccComponents            # WACC breakdown
    - WaccResult                # Complete WACC result
    - ScenarioResult            # Full scenario evaluation
    
    FX (Sprint 15 integration):
    - FXStructuredBlock         # FX configuration blocks
    - FXCurveOutput             # FX curves
    - FXRiskProfile             # FX risk profiling
    
    Sensitivity:
    - TornadoResult             # Single-metric tornado
    - MultiMetricTornadoResult  # Multi-metric tornado
    - ParameterRangeConfig      # Parameter shock config
    - SensitivitySuite          # Complete sensitivity suite
    - SensitivityRequest        # Sensitivity request
    - BreakevenResult           # Breakeven analysis
    
    CASPER:
    - CasperResult              # Unified analysis result
    - ShockResult               # Single shock result

From phase 3 (legacy):
    - SensitivitySuite (legacy) # Old sensitivity suite
    - ShockSpec                 # Shock specification
    - StandardShockLibrary      # Predefined shocks

Backward Compatibility
──────────────────────────────────────────────────────────────
All imports work from multiple locations:
    
    # Old way (still works)
    from analytics.contracts_v14 import MonteCarloScenario
    from analytics.contracts import ShockSpec
    
    # New way (recommended)
    from analytics.contracts import MonteCarloScenario, ShockSpec

Architecture Principles
──────────────────────────────────────────────────────────────
GWTF:     Single source of truth for all data contracts
CASSPER:  Contract-first API with Pydantic V2
CESSPIT:  Fail-fast validation with clear error messages
CCCDIR:   Comprehensive documentation with usage examples
"""

from __future__ import annotations

# Phase 3 legacy sensitivity contracts (backward compat)
from analytics.contracts._phase_3_sensitivity import (
    SensitivitySuite as LegacySensitivitySuite,
    ShockResult as LegacyShockResult,
    ShockSpec,
    StandardShockLibrary,
)

# Main v14 contracts (Pydantic V2)
from analytics.contracts_v14 import (
    # Version
    CASPER_CONTRACT_VERSION,
    
    # Monte Carlo (Sprint 16 - Issue #43)
    Distribution,
    DerivedParameter,
    MonteCarloScenario,
    MonteCarloResult,
    
    # WACC
    WaccComponents,
    WaccResult,
    ScenarioResult,
    
    # FX (Sprint 15 integration - Issue #31)
    FXStructuredBlock,
    FXCurveOutput,
    FXRiskProfile,
    
    # Sensitivity (Pydantic V2)
    TornadoResult,
    MultiMetricTornadoResult,
    ParameterRangeConfig,
    SensitivitySuite,
    SensitivityRequest,
    BreakevenResult,
    
    # CASPER
    CasperResult,
    ShockResult,
)


__all__ = [
    # Version
    "CASPER_CONTRACT_VERSION",
    
    # Monte Carlo
    "Distribution",
    "DerivedParameter",
    "MonteCarloScenario",
    "MonteCarloResult",
    
    # WACC
    "WaccComponents",
    "WaccResult",
    "ScenarioResult",
    
    # FX
    "FXStructuredBlock",
    "FXCurveOutput",
    "FXRiskProfile",
    
    # Sensitivity (V2)
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "SensitivityRequest",
    "BreakevenResult",
    "ShockResult",
    
    # CASPER
    "CasperResult",
    
    # Legacy (Phase 3)
    "LegacySensitivitySuite",
    "LegacyShockResult",
    "ShockSpec",
    "StandardShockLibrary",
]

# EOF
