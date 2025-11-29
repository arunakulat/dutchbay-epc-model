#!/usr/bin/env python3
"""
DutchBay Debt Module - Diagnostic & Automatic Repair
Run from project root with: python scripts/debt_module_diagnostic.py
"""

import json
import os
import sys
from pathlib import Path

# Ensure we're in the right directory
if not Path("finance").exists():
    print(
        "❌ ERROR: This script must be run from the DutchBay_EPC_Model root directory"
    )
    print(f"   Current dir: {os.getcwd()}")
    sys.exit(1)

print("=" * 80)
print("DEBT MODULE DIAGNOSTIC")
print("=" * 80)

try:
    from finance.cashflow_v14 import build_annual_rows
    from finance.debt_v14 import plan_debt
    from tests.api.test_covenants_v14 import _build_base_config

    print("\n✓ Imports successful")

    # Run minimal test case
    print("\n" + "=" * 80)
    print("RUNNING MINIMAL TEST CASE")
    print("=" * 80)

    config = _build_base_config()
    annual_rows = build_annual_rows(config)
    debt = plan_debt(annual_rows=annual_rows, config=config)

    print(f"\n✓ plan_debt() executed successfully")
    print(f"✓ Return type: {type(debt).__name__}")
    print(f"✓ Return keys: {list(debt.keys())}")

    print("\n" + "-" * 80)
    print("DETAILED STRUCTURE")
    print("-" * 80)

    for key, value in debt.items():
        val_type = type(value).__name__
        if isinstance(value, (list, tuple)):
            print(f"  {key:30s} : {val_type:20s} (len={len(value)})")
        elif isinstance(value, dict):
            print(f"  {key:30s} : {val_type:20s} (keys={list(value.keys())[:3]}...)")
        else:
            val_str = str(value)[:40]
            print(f"  {key:30s} : {val_type:20s} ({val_str})")

    # Check specifically for missing keys
    print("\n" + "-" * 80)
    print("TEST EXPECTATIONS vs ACTUAL")
    print("-" * 80)

    expected_keys = [
        "timeline_periods",
        "debt_outstanding",
        "debt_service",
        "total_service",
        "idcs",
        "idc_cumulative",
    ]

    for key in expected_keys:
        status = "✓ PRESENT" if key in debt else "✗ MISSING"
        print(f"  {key:30s} : {status}")

    # Export diagnostic data
    diagnostic_data = {
        "actual_keys": list(debt.keys()),
        "expected_keys_in_tests": expected_keys,
        "missing_keys": [k for k in expected_keys if k not in debt],
        "extra_keys": [k for k in debt.keys() if k not in expected_keys],
        "return_type": type(debt).__name__,
    }

    output_file = Path("outputs/debt_diagnostic.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(diagnostic_data, f, indent=2, default=str)

    print(f"\n✓ Diagnostic exported to: {output_file}")

    # Print analysis
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)

    missing = diagnostic_data.get("missing_keys", [])
    extra = diagnostic_data.get("extra_keys", [])

    if missing:
        print("\n⚠️  TESTS EXPECT BUT DON'T FIND:")
        for key in missing:
            print(f"   ✗ {key}")
    else:
        print("\n✓ All expected keys present!")

    if extra:
        print("\n✓ Extra keys available (bonus):")
        for key in extra:
            print(f"   + {key}")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print(
        """
1. Review: cat outputs/debt_diagnostic.json
2. Check finance/debt_v14.py plan_debt() implementation
3. Choose strategy:
   A) Add missing keys to plan_debt() return dict
   B) Update tests to use actual keys
   C) Create wrapper to add missing keys
4. Implement fix and re-run tests
"""
    )

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
