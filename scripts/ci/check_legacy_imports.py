#!/usr/bin/env python3
"""Check for forbidden imports from legacy code.

Part of Task 1: Legacy Quarantine Sweep
Ensures no production code imports from legacy/ or dutchbay_v14chat/
"""
import re
import sys
from pathlib import Path

FORBIDDEN_PATTERNS = [
    r"from legacy",
    r"import legacy",
    r"from dutchbay_v14chat",
    r"import dutchbay_v14chat",
]

PROTECTED_DIRS = ["analytics", "finance", "tests/api", "tests/analytics"]

#: Repo root: scripts/ci/check_legacy_imports.py -> parents[2]. (The previous
#: ``parent.parent`` pointed at ``scripts/``, so the scan found none of the
#: protected dirs and passed vacuously — the guard checked nothing.)
REPO_ROOT = Path(__file__).resolve().parents[2]


def check_file(filepath: Path) -> list[str]:
    """Check single file for forbidden imports."""
    violations = []
    try:
        content = filepath.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            # Skip comments
            if line.strip().startswith("#"):
                continue
            for pattern in FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    violations.append(f"{filepath}:{i}: {line.strip()}")
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
    return violations


def find_violations(repo_root: Path = REPO_ROOT) -> list[str]:
    """Return all forbidden-legacy-import violations under the protected dirs."""
    violations: list[str] = []
    for dir_name in PROTECTED_DIRS:
        dir_path = repo_root / dir_name
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            violations.extend(check_file(py_file))
    return violations


def main():
    """Scan protected directories for violations (CLI; nonzero exit on any)."""
    violations = find_violations()

    if violations:
        print("❌ FORBIDDEN IMPORTS DETECTED:\n")
        for v in violations:
            print(f"  {v}")
        print("\nLegacy imports are not allowed in production code.")
        print("Please refactor to use analytics/ or finance/ modules.")
        sys.exit(1)
    else:
        print("✅ No forbidden legacy imports found")
        print("   Checked directories:", ", ".join(PROTECTED_DIRS))
        sys.exit(0)


if __name__ == "__main__":
    main()

# EOF
