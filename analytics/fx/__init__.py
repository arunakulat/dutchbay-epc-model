"""FX (Foreign Exchange) Integration Package.

This package handles foreign exchange (FX) integration for multi-currency
projects, including FX hedging strategies, currency conversion, and risk
profiles.

Modules:
    fx_integration: Main entry point for integrating FX blocks into
                   ScenarioResult during pipeline execution.
                   
    fx_builder: Low-level FX computation functions (compute_fx_curve,
               compute_fx_structured_block, compute_fx_risk_profile).

Public API:
    integrate_fx_into_scenario_result: Wire FX blocks into ScenarioResult.
                                      Called from pipeline_v14.

Usage:
    # Preferred import
    from analytics.fx import integrate_fx_into_scenario_result
    
    # Or specific module import
    from analytics.fx.fx_integration import integrate_fx_into_scenario_result
    
    # Legacy (still works via shim)
    from analytics.fx_integration import integrate_fx_into_scenario_result

FX Strategy Types:
    - Natural hedge: Use revenues in same currency as expenses
    - Forward contracts: Lock in FX rates for future dates
    - Blended: Combination of natural hedge + forwards
    - Spot: No hedging (market rates at transaction time)

Framework Compliance:
    - GWTF: Full type hints, comprehensive docstrings
    - CASPER: Lender-grade FX risk calculations
    - CESSPIT: Fail-fast validation, clear error messages
    - CCCDIR: Fully documented FX logic

Migration:
    - Priority 3 (FX Module)
    - 1 file moved from analytics/ root
    - 1 backward compatibility shim created
    - Clean isolation of FX subsystem

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 1.0.0
"""

from __future__ import annotations

# Public API: Main FX integration function
from analytics.fx.fx_integration import integrate_fx_into_scenario_result

__all__ = [
    "integrate_fx_into_scenario_result",
]
