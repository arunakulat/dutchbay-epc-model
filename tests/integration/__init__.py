"""Integration tests for DutchBay EPC Model v14.

Tests cross-module interactions and end-to-end pipeline flows:
- Wind assessment → Cashflow model integration
- Cashflow → Monte Carlo integration
- Dual DSCR → Sensitivity analysis integration
- Complete pipeline validation

Framework Compliance:
- TEST-01: Regression pins for integrated behavior
- CASPER: Tail-risk validation across modules
- NO REGRESSION: Integration tests only, no code changes

Usage:
    pytest tests/integration/
    pytest tests/integration/test_pipeline_end_to_end.py -v
"""

__all__ = []
