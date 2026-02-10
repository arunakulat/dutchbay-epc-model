"""Refinancing Module Compatibility Stubs (Sprint 12).

Temporary backward-compatibility layer for refinancing tests
during Pydantic v2 migration. These stubs allow existing tests
to import and instantiate refinancing classes without breaking.

Full implementation in:
- finance/refinancing_v14_hydra.py (Hydra-based)
- finance/refinancing_v14.py (Core logic)

Removal: Sprint 13 after test migration complete.
"""

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict


class RefinancingEngine(BaseModel):
    """Temporary stub for legacy test imports.
    
    Real implementation: finance.refinancing_v14_hydra.RefinancingEngineHydra
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    scenario_name: str = "base"
    config: Dict[str, Any] = {}


class RefinancingV14(BaseModel):
    """Temporary stub for legacy test imports.
    
    Real implementation: finance.refinancing_v14_hydra.run_refinancing_scenario
    """
    model_config = ConfigDict(extra='allow', arbitrary_types_allowed=True)
    
    year: int = 0
    trigger_dscr: float = 0.0
    post_refi_npv: float = 0.0


__all__ = ["RefinancingEngine", "RefinancingV14"]
