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


def main():
    """Scan protected directories for violations."""
    repo_root = Path(__file__).parent.parent
    violations = []

    for dir_name in PROTECTED_DIRS:
        dir_path = repo_root / dir_name
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            violations.extend(check_file(py_file))

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
