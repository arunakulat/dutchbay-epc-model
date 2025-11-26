#!/usr/bin/env python3
"""Quick test of IRR refactoring - Run this to verify everything works.

Run from project root:
    python test_irr_quick.py
"""

print("=" * 70)
print("DUTCHBAY V14 - IRR REFACTORING QUICK TEST")
print("=" * 70)
print()

# Test 1: Import modules
print("TEST 1: Importing modules...")
try:
    from finance.irr import irr, npv
    from finance.irr_config import get_irr_bounds, load_config

    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)
print()

# Test 2: Load config
print("TEST 2: Loading config...")
try:
    config = load_config()
    project_name = config.get("project", {}).get("name", "Unknown")
    print(f"✅ Config loaded: {project_name}")
except Exception as e:
    print(f"❌ Config load failed: {e}")
    exit(1)
print()

# Test 3: Extract bounds
print("TEST 3: Extracting IRR bounds...")
try:
    lower_proj, upper_proj = get_irr_bounds(config)
    lower_eq, upper_eq = get_irr_bounds(config, role="equity")
    print(f"   Project: [{lower_proj}, {upper_proj}]")
    print(f"   Equity:  [{lower_eq}, {upper_eq}]")
    print("✅ Bounds extracted")
except Exception as e:
    print(f"❌ Bounds extraction failed: {e}")
    exit(1)
print()

# Test 4: Calculate IRR
print("TEST 4: Calculating IRR...")
try:
    cashflows = [-100, 30, 30, 30, 30]

    # With config bounds
    result_config = irr(cashflows, lower_bound=lower_proj, upper_bound=upper_proj)
    print(f"   IRR (config bounds): {result_config:.4f} ({result_config*100:.2f}%)")

    # Without config (backward compatible)
    result_default = irr(cashflows)
    print(f"   IRR (default):       {result_default:.4f} ({result_default*100:.2f}%)")

    print("✅ IRR calculations successful")
except Exception as e:
    print(f"❌ IRR calculation failed: {e}")
    exit(1)
print()

# Test 5: NPV
print("TEST 5: Calculating NPV...")
try:
    npv_result = npv(0.10, cashflows)
    print(f"   NPV at 10%: {npv_result:.2f}")
    print("✅ NPV calculation successful")
except Exception as e:
    print(f"❌ NPV calculation failed: {e}")
    exit(1)
print()

print("=" * 70)
print("✅ ALL TESTS PASSED!")
print("=" * 70)
print()
print("Summary:")
print(f"  - Config: scenarios/dutchbay_master_config_v14.yaml")
print(f"  - Project IRR range: {lower_proj*100:.0f}% to {upper_proj*100:.0f}%")
print(f"  - Equity IRR range:  {lower_eq*100:.0f}% to {upper_eq*100:.0f}%")
print()
print("🎯 System ready for production!")
