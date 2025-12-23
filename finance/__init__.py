"""Finance module for DutchBay EPC Model.

Sprint 12 Status:
- Refinancing module: Hydra + compatibility stubs
- Equity distribution module: Pydantic v2 contracts
- Tax module: Stable (Sprint 11)
"""

# Re-export compatibility stubs for legacy tests
from finance.refinancing_v14_compat import RefinancingEngine, RefinancingV14

__all__ = ["RefinancingEngine", "RefinancingV14"]
