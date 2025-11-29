#!/usr/bin/env python3
"""Debug contracts_v14.py dataclass signatures."""

import inspect
import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

print("\n" + "=" * 70)
print("CONTRACTS_V14.PY DATACLASS DEBUG")
print("=" * 70)

# Step 1: Load module
print("\n[1] MODULE LOADING")
print("-" * 70)
try:
    from analytics import contracts_v14

    print("  ✅ Module loaded successfully")
except ImportError as e:
    print(f"  ❌ Import failed: {e}")
    sys.exit(1)

# Step 2: Check key dataclasses
print("\n[2] KEY DATACLASSES")
print("-" * 70)
dataclasses_to_check = [
    "TornadoResult",
    "MultiMetricTornadoResult",
    "ParameterRangeConfig",
    "SensitivitySuite",
    "BreakevenResult",
]

for dc_name in dataclasses_to_check:
    if hasattr(contracts_v14, dc_name):
        dc = getattr(contracts_v14, dc_name)
        print(f"\n  {dc_name}:")
        print(f"    ✅ Exists")

        try:
            sig = inspect.signature(dc)
            print(f"    Signature: {sig}")
        except Exception as e:
            print(f"    ⚠️  Could not get signature: {e}")

        if hasattr(dc, "__dataclass_fields__"):
            fields = dc.__dataclass_fields__
            print(f"    Fields ({len(fields)}):")
            for field_name, field in fields.items():
                print(f"      - {field_name}: {field.type}")
    else:
        print(f"\n  ❌ {dc_name}: NOT FOUND")

print("\n" + "=" * 70)
print("END DEBUG")
print("=" * 70 + "\n")
