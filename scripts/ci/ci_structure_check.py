#!/usr/bin/env python3
"""CI Structure Check - Validate repository file layout and imports.

Go with the Flow Compliance:
- Validates expected directory structure
- Checks for forbidden legacy imports
- Verifies no orphaned files in root
- Ensures all __init__.py files present

Usage:
    python scripts/ci_structure_check.py

Exit Codes:
    0: All checks pass
    1: Structure violations found
"""

from __future__ import annotations

import sys
from pathlib import Path

# Expected directory structure
EXPECTED_DIRS = [
    "analytics",
    "analytics/core",
    "analytics/fx",
    "analytics/sensitivity",
    "finance",
    "legacy",
    "legacy/dutchbay_v13",
    "legacy/v14chat",
    "legacy/patch_archive",
    "scripts",
    "scripts/research",
    "scenarios",
    "tests",
    "tests/api",
    "tests/analytics",
]

# Required __init__.py files
REQUIRED_INIT_FILES = [
    "analytics/__init__.py",
    "analytics/core/__init__.py",
    "analytics/fx/__init__.py",
    "analytics/sensitivity/__init__.py",
    "finance/__init__.py",
]

# Forbidden patterns (legacy imports)
FORBIDDEN_PATTERNS = [
    "from dutchbay_v14chat",
    "import dutchbay_v14chat",
    "from legacy.",
    "import legacy.",
]

# Allowed root-level files
ALLOWED_ROOT_FILES = [
    ".gitignore",
    ".pre-commit-config.yaml",
    "README.md",
    "LICENSE",
    "requirements.txt",
    "pytest.ini",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "constants.py",
    "run_full_pipeline_v14.py",
]


def check_directory_structure(repo_root: Path) -> list[str]:
    """Verify expected directories exist."""
    issues = []

    for dir_path in EXPECTED_DIRS:
        full_path = repo_root / dir_path
        if not full_path.exists():
            issues.append(f"Missing directory: {dir_path}")
        elif not full_path.is_dir():
            issues.append(f"Not a directory: {dir_path}")

    return issues


def check_init_files(repo_root: Path) -> list[str]:
    """Verify required __init__.py files exist."""
    issues = []

    for init_file in REQUIRED_INIT_FILES:
        full_path = repo_root / init_file
        if not full_path.exists():
            issues.append(f"Missing __init__.py: {init_file}")

    return issues


def check_forbidden_imports(repo_root: Path) -> list[str]:
    """Check for forbidden legacy imports in production code."""
    issues = []

    # Directories to check
    check_dirs = ["analytics", "finance", "tests/api", "tests/analytics"]

    for check_dir in check_dirs:
        dir_path = repo_root / check_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            try:
                content = py_file.read_text()
                for pattern in FORBIDDEN_PATTERNS:
                    if pattern in content:
                        rel_path = py_file.relative_to(repo_root)
                        issues.append(f"Forbidden import in {rel_path}: '{pattern}'")
            except Exception as e:
                issues.append(f"Error reading {py_file}: {e}")

    return issues


def check_root_orphans(repo_root: Path) -> list[str]:
    """Check for orphaned Python files in root directory."""
    issues = []

    for item in repo_root.iterdir():
        if item.is_file() and item.suffix == ".py":
            if item.name not in ALLOWED_ROOT_FILES:
                issues.append(
                    f"Orphaned Python file in root: {item.name} "
                    f"(should be in scripts/ or appropriate package)"
                )

    return issues


def check_eof_markers(repo_root: Path) -> list[str]:
    """Verify all scripts end with # EOF marker."""
    issues = []

    script_dirs = ["scripts", "scripts/research"]

    for script_dir in script_dirs:
        dir_path = repo_root / script_dir
        if not dir_path.exists():
            continue

        for script_file in dir_path.glob("*.py"):
            try:
                content = script_file.read_text()
                if not content.strip().endswith("# EOF"):
                    rel_path = script_file.relative_to(repo_root)
                    issues.append(f"Missing # EOF marker: {rel_path}")
            except Exception as e:
                issues.append(f"Error reading {script_file}: {e}")

        for script_file in dir_path.glob("*.sh"):
            try:
                content = script_file.read_text()
                if not content.strip().endswith("# EOF"):
                    rel_path = script_file.relative_to(repo_root)
                    issues.append(f"Missing # EOF marker: {rel_path}")
            except Exception as e:
                issues.append(f"Error reading {script_file}: {e}")

    return issues


def main() -> int:
    """Run all structure checks."""
    repo_root = Path(__file__).parent.parent

    print("🔍 Running CI Structure Checks...")
    print(f"   Repository: {repo_root}\n")

    all_issues: list[str] = []

    # Run all checks
    checks = [
        ("Directory Structure", check_directory_structure),
        ("Required __init__.py Files", check_init_files),
        ("Forbidden Legacy Imports", check_forbidden_imports),
        ("Root-Level Orphans", check_root_orphans),
        ("EOF Markers", check_eof_markers),
    ]

    for check_name, check_func in checks:
        print(f"Checking: {check_name}")
        issues = check_func(repo_root)

        if issues:
            all_issues.extend(issues)
            print(f"  ❌ {len(issues)} issue(s) found")
            for issue in issues:
                print(f"     • {issue}")
        else:
            print("  ✅ Pass")
        print()

    # Summary
    if all_issues:
        print(f"❌ CI Structure Check FAILED: {len(all_issues)} issue(s) found")
        return 1
    else:
        print("✅ CI Structure Check PASSED: All checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())

# EOF
