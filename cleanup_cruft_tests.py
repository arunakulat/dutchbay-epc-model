#!/usr/bin/env python3
"""
Delete v14 test cruft (duplicate / legacy files).

Run from the repo root:

    python cleanup_cruft_tests.py
    python cleanup_cruft_tests.py --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

# Explicit list of files we consider "cruft" right now.
CRUFT_FILES: List[str] = [
    # Duplicate / superseded debt tests
    "tests/api/test_debt_v14_construction_refactored.py",
    "tests/api/test_debt_construction_idc_regression_v14.py",
    "tests/api/test_debt_construction_idc_regression.py.bak",
    # Duplicate / superseded covenants tests
    "tests/api/test_covenants_v14_refactored.py",
    "tests/api/test_covenants_lendercase_refactored.py",
    # Duplicate ScenarioAnalytics/schema-guard integration test
    "tests/api/test_scenario_analytics_schema_guard_integration_refactored.py",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete known cruft test files.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be deleted but do not remove anything.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent

    deleted = []
    missing = []

    for rel in CRUFT_FILES:
        path = repo_root / rel
        if path.exists():
            if args.dry_run:
                print(f"[DRY-RUN] Would delete: {rel}")
            else:
                try:
                    path.unlink()
                    print(f"Deleted: {rel}")
                    deleted.append(rel)
                except Exception as exc:  # noqa: BLE001
                    print(f"FAILED to delete {rel}: {exc}")
        else:
            missing.append(rel)

    if missing:
        print("\nThese files were not found (already gone or never created):")
        for rel in missing:
            print(f"  - {rel}")

    if not args.dry_run:
        print("\nCleanup complete.")
        if deleted:
            print("Deleted files:")
            for rel in deleted:
                print(f"  - {rel}")


if __name__ == "__main__":
    main()
