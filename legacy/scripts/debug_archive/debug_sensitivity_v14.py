#!/usr/bin/env python3
"""Debug sensitivity_v14.py module structure."""

import inspect
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

print("\n" + "=" * 70)
print("SENSITIVITY_V14.PY STRUCTURE DEBUG")
print("=" * 70)

# Step 1: Load module
print("\n[1] MODULE LOADING")
print("-" * 70)
try:
    from analytics import sensitivity_v14

    print("  ✅ Module loaded successfully")
except ImportError as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Step 2: Check module attributes
print("\n[2] MODULE ATTRIBUTES")
print("-" * 70)
all_attrs = dir(sensitivity_v14)
print(f"  Total attributes: {len(all_attrs)}")

functions = [a for a in all_attrs if not a.startswith("_")]
print(f"  Public items: {len(functions)}")

print("\n  Functions/Classes:")
for item in sorted(functions):
    obj = getattr(sensitivity_v14, item)
    obj_type = type(obj).__name__
    print(f"    - {item:<40} ({obj_type})")

# Step 3: Check __all__
print("\n[3] __ALL__ EXPORT LIST")
print("-" * 70)
if hasattr(sensitivity_v14, "__all__"):
    all_list = sensitivity_v14.__all__
    print(f"  __all__ = {len(all_list)} items")
    for item in all_list:
        has_it = hasattr(sensitivity_v14, item)
        status = "✅" if has_it else "❌ MISSING"
        print(f"    {status} {item}")
else:
    print("  ⚠️  No __all__ defined")

# Step 4: Check required functions
print("\n[4] REQUIRED FUNCTIONS CHECK")
print("-" * 70)
required = [
    "SensitivityRequest",
    "run_tornado_sensitivity",
    "run_multi_metric_tornado",
    "run_breakeven_parameter",
    "tornado_suite_to_dataframe",
    "multi_metric_suite_to_dataframe",
    "plot_tornado_chart",
    "plot_spider_chart",
    "enrich_tornado_with_tail_risk",
    "optimize_from_sensitivity_insights",
    "run_two_way_sensitivity",
    "plot_two_way_heatmap",
]

missing = []
for name in required:
    has_it = hasattr(sensitivity_v14, name)
    status = "✅" if has_it else "❌"
    print(f"  {status} {name}")
    if not has_it:
        missing.append(name)

if missing:
    print(f"\n  ⚠️  MISSING: {', '.join(missing)}")

print("\n" + "=" * 70)
print("END DEBUG")
print("=" * 70 + "\n")
