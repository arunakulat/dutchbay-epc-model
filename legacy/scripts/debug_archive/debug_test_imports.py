#!/usr/bin/env python3
"""Debug what test_sensitivity_regression.py is trying to import."""

import sys
from pathlib import Path

repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

print("\n" + "=" * 70)
print("TEST FILE IMPORT ANALYSIS")
print("=" * 70)

test_file = repo_root / "tests/analytics_layer/test_sensitivity_regression.py"

print(f"\n[1] READING TEST FILE")
print("-" * 70)
print(f"  File: {test_file}")
print(f"  Exists: {test_file.exists()}")

if test_file.exists():
    with open(test_file) as f:
        lines = f.readlines()

    # Find import section
    print(f"\n[2] IMPORT STATEMENTS (lines 1-30)")
    print("-" * 70)
    for i, line in enumerate(lines[:30], 1):
        if "import" in line.lower() or "from" in line.lower():
            print(f"  Line {i}: {line.rstrip()}")

    # Find what's being imported from analytics.sensitivity
    print(f"\n[3] SENSITIVITY IMPORTS")
    print("-" * 70)
    in_sensitivity_import = False
    sensitivity_imports = []
    for i, line in enumerate(lines[:50], 1):
        if "from analytics.sensitivity import" in line:
            in_sensitivity_import = True
            print(f"  Found at line {i}")

        if in_sensitivity_import:
            print(f"    {line.rstrip()}")
            sensitivity_imports.append(line.rstrip())

            if ")" in line:
                in_sensitivity_import = False

    # Parse what's needed
    if sensitivity_imports:
        full_text = "\n".join(sensitivity_imports)
        if "(" in full_text:
            start = full_text.find("(")
            end = full_text.rfind(")")
            imports_str = full_text[start + 1 : end]
            items = [x.strip() for x in imports_str.split(",") if x.strip()]

            print(f"\n[4] PARSED IMPORTS ({len(items)} items)")
            print("-" * 70)
            for item in items:
                print(f"  - {item}")
else:
    print("  ❌ Test file not found")

print("\n" + "=" * 70)
print("END ANALYSIS")
print("=" * 70 + "\n")
