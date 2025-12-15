"""
DutchBay Financial Model Library (v14 Rebuilt & Hardened)
"""

from .statutory_profile import StatutoryProfile

# Public API
from .tax_profile import (
    DepreciationSchedule,
    TaxConfig,
    TaxProfile,
    TaxResult,
    build_tax_profile,
    build_tax_series,
    calculate_tax,
)

__all__ = [
    "TaxConfig",
    "TaxProfile",
    "TaxResult",
    "DepreciationSchedule",
    "build_tax_profile",
    "build_tax_series",
    "calculate_tax",
    "StatutoryProfile",
]
