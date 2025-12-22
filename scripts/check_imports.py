#!/usr/bin/env python3
"""
Quick check of import status in the repository.
"""

from collections import defaultdict
from pathlib import Path


def check_imports():
    """Check for v14 and broken imports."""

    repo_root = Path.cwd()
    print(f"Checking imports in: {repo_root}")
    print("=" * 70)

    v14_patterns = [
        ("contractsv14", "analytics.contractsv14"),
        ("sensitivityv14", "analytics.sensitivityv14"),
        ("cashflowv14", "finance.cashflowv14"),
        ("equityv14", "finance.equityv14"),
        ("debtv14", "finance.debtv14"),
        ("waccv14", "finance.waccv14"),
        ("irrconfig", "finance.irrconfig"),  # Should be finance.equity.irrconfig
        (
            "from finance.equity.irr import",
            "finance.irr (should be finance.equity.irr)",
        ),
    ]

    correct_patterns = [
        ("from analytics.contracts import", "analytics.contracts"),
        ("from analytics.sensitivity import", "analytics.sensitivity"),
        ("from analytics.core.configschema import", "analytics.core.configschema"),
        ("from finance.cashflow import", "finance.cashflow"),
        ("from finance.equity import", "finance.equity"),
        ("from finance.equity.irr import", "finance.equity.irr"),
    ]

    found_v14 = defaultdict(list)
    found_correct = defaultdict(list)
    files_scanned = 0

    for py_file in repo_root.rglob("*.py"):
        # Skip venv, cache, git
        if any(
            part in str(py_file) for part in [".venv", "__pycache__", ".git", ".bak"]
        ):
            continue

        files_scanned += 1

        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            rel_path = py_file.relative_to(repo_root)

            # Check for v14 patterns
            for pattern, label in v14_patterns:
                if pattern.lower() in content.lower():
                    found_v14[label].append(str(rel_path))

            # Check for correct patterns
            for pattern, label in correct_patterns:
                if pattern in content:
                    found_correct[label].append(str(rel_path))

        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    print(f"\n✅ Scanned {files_scanned} Python files")
    print("\n" + "=" * 70)
    print("BROKEN v14 IMPORTS FOUND:")
    print("=" * 70)

    if found_v14:
        for pattern, files in sorted(found_v14.items()):
            print(f"\n❌ {pattern} ({len(files)} files):")
            for f in sorted(files)[:5]:
                print(f"    {f}")
            if len(files) > 5:
                print(f"    ... and {len(files)-5} more")
    else:
        print("\n✅ NO v14 IMPORTS FOUND! (Good!)")

    print("\n" + "=" * 70)
    print("CORRECT IMPORTS FOUND:")
    print("=" * 70)

    for pattern, files in sorted(found_correct.items()):
        print(f"\n✅ {pattern} ({len(files)} files)")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_v14 = sum(len(files) for files in found_v14.values())
    total_correct = sum(len(files) for files in found_correct.values())

    print(f"\nFiles with v14 imports:      {total_v14}")
    print(f"Files with correct imports:  {total_correct}")
    print(f"Total files scanned:         {files_scanned}")

    if total_v14 == 0:
        print("\n🎉 ALL IMPORTS APPEAR TO BE CORRECT!")
        return True
    else:
        print(f"\n⚠️  {total_v14} import issues remain")
        return False


if __name__ == "__main__":
    success = check_imports()
    exit(0 if success else 1)
