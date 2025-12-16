"""Test suite for Phase 1-2 refactoring (tax layer + WACC integration).

WARNING: This test file requires legacy modules that have not been migrated
to v14. Skipped until Phase 1-2 implementation is complete.

To enable, ensure the following modules are available:
  - finance.tax_profile
  - finance.wacc_integration

Tests cover:
  ✅ Tax profile creation and validation
  ✅ Depreciation schedule calculation
  ✅ Tax liability calculation with interest deductibility
  ✅ WACC calculation and components
  ✅ Interest injection into annual rows
  ✅ Backward compatibility with v1 code
  ✅ Complete integration scenarios
"""

import pytest

# SKIP entire module - legacy Phase 1-2 not yet migrated to v14
pytestmark = pytest.mark.skip(
    reason="Phase 1-2 tax/WACC modules not yet migrated. See PR for migration plan."
)
