#!/usr/bin/env python3
"""Debug import chain for sensitivity modules."""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

print("\n" + "=" * 70)
print("IMPORT CHAIN DEBUG - Sensitivity Modules")
print("=" * 70)

# Step 1: Check file existence
print("\n[1] FILE EXISTENCE CHECK")
print("-" * 70)
files_to_check = [
    "analytics/sensitivity/__init__.py",
    "analytics/sensitivity_v14.py",
    "analytics/evaluate_scenario.py",
    "analytics/contracts_v14.py",
]
for f in files_to_check:
    path = repo_root / f
    exists = path.exists()
    status = "✅ EXISTS" if exists else "❌ MISSING"
    print(f"  {status}: {f}")

# Step 2: Check imports in sensitivity/__init__.py
print("\n[2] SENSITIVITY/__INIT__.PY IMPORTS")
print("-" * 70)
try:
    init_path = repo_root / "analytics/sensitivity/__init__.py"
    with open(init_path) as f:
        content = f.read()

    import_lines = [
        line
        for line in content.split("\n")
        if "from analytics.sensitivity_v14 import" in line
    ]
    print(f"  Found {len(import_lines)} import statement(s)")

    if import_lines:
        import_block = "\n".join(import_lines)
        if "(" in import_block:
            start = import_block.find("(")
            end = import_block.rfind(")")
            functions_str = import_block[start + 1 : end]
            functions = [
                f.strip().rstrip(",") for f in functions_str.split("\n") if f.strip()
            ]
            print(f"  Importing {len(functions)} items:")
            for func in functions[:5]:
                print(f"    - {func}")
            if len(functions) > 5:
                print(f"    ... and {len(functions) - 5} more")
except Exception as e:
    print(f"  ❌ Error reading file: {e}")

# Step 3: Check sensitivity_v14.py exports
print("\n[3] SENSITIVITY_V14.PY EXPORTS")
print("-" * 70)
try:
    v14_path = repo_root / "analytics/sensitivity_v14.py"
    with open(v14_path) as f:
        content = f.read()

    if "__all__" in content:
        start = content.find("__all__ = [")
        end = content.find("]", start) + 1
        all_block = content[start:end]
        items = [
            line.strip().strip('"') for line in all_block.split("\n") if '"' in line
        ]
        print(f"  __all__ exports {len(items)} items:")
        for item in items[:5]:
            print(f"    - {item}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")
    else:
        print("  ⚠️  No __all__ found")
except Exception as e:
    print(f"  ❌ Error reading file: {e}")

# Step 4: Try actual imports
print("\n[4] RUNTIME IMPORT TEST")
print("-" * 70)

import_tests = [
    ("analytics.sensitivity_v14", ["SensitivityRequest", "run_tornado_sensitivity"]),
    ("analytics.sensitivity", ["SensitivityRequest", "run_tornado_sensitivity"]),
]

for module_name, items in import_tests:
    print(f"\n  Testing: {module_name}")
    try:
        module = __import__(module_name, fromlist=items)
        for item in items:
            if hasattr(module, item):
                print(f"    ✅ {item}")
            else:
                print(f"    ❌ {item} NOT FOUND")
    except ImportError as e:
        print(f"    ❌ Import failed: {e}")
    except Exception as e:
        print(f"    ❌ Error: {e}")

print("\n" + "=" * 70)
print("END DEBUG")
print("=" * 70 + "\n")
