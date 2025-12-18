"""FX Module - Structured Blocks for v14R6 Pipeline.

This module provides FX-related data contracts and computation engines
for integrating multi-currency scenarios into the dutchbay-epc-model
v14 pipeline.

Key Exports:
  FXStructuredBlock: Primary FX configuration and snapshot.
  FXCurveOutput: Time-series FX projection (LKR/USD, etc.).
  FXRiskProfile: Lender-grade FX risk metrics (VaR, CVaR, concentration).

Usage:
  from analytics.fx import FXStructuredBlock, FXCurveOutput, FXRiskProfile
  
  # Create FX block
  fx_block = FXStructuredBlock(...)
  
  # Generate FX curve
  fx_curve = FXCurveOutput(...)
  
  # Wire into ScenarioResult
  result = ScenarioResult(
      ...,
      fx_block=fx_block,
      fx_curve=fx_curve,
      ...
  )

Standards:
  - GWTF: Full type hints, module docstrings
  - CASPER: Lender-grade summaries and exports
  - CESSPIT: Immutable records, fail-fast validation
  - CCCDIR: Fully commented, no config shortcuts
"""

__version__ = "1.0.0"
__author__ = "Dutchbay Analytics"

try:
    from .fx_contracts import (
        FXStructuredBlock,
        FXCurveOutput,
        FXRiskProfile,
        FXVolumetry,
    )
    
    __all__ = [
        "FXStructuredBlock",
        "FXCurveOutput",
        "FXRiskProfile",
        "FXVolumetry",
    ]
except ImportError as e:
    # fx_contracts.py not yet created; imports will be added later
    __all__ = []
    _import_error = str(e)

# EOF - analytics/fx/__init__.py
