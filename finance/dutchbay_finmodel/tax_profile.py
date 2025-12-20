"""
DEPRECATED: This module is deprecated as of v14.2.

All functionality has been consolidated into finance.cashflow_v14_tax.
This file will be removed in v15.0.0.

Migration Guide
---------------
OLD:
    from finance.dutchbay_finmodel.tax_profile import (
        TaxConfig,
        TaxProfile,
        calculate_tax,
        build_tax_series,
    )

NEW:
    from finance.cashflow_v14_tax import (
        TaxConfig,
        TaxProfile,
        calculate_tax,
        build_tax_series,
    )

Changes
-------
- v14.2: All tax logic consolidated into finance/cashflow_v14_tax.py
- v14.2: Wave 2 type safety enhancements applied
- v14.2: Backward compatibility (decimal vs percentage) added
- v15.0: This file will be deleted

For more information:
https://github.com/arunakulat/dutchbay-epc-model/blob/main/TAX_MODULE_ARCHITECTURE_ANALYSIS.md
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "finance.dutchbay_finmodel.tax_profile is deprecated. "
    "Use finance.cashflow_v14_tax instead. "
    "This module will be removed in v15.0.0.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export all symbols from canonical module
from finance.cashflow_v14_tax import (  # noqa: F401, E402
    DepreciationSchedule,
    TaxConfig,
    TaxProfile,
    TaxResult,
    build_tax_holiday_map,
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
    "build_tax_holiday_map",
]
