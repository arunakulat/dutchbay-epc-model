#!/usr/bin/env python3
"""
Fix all YAML scenario files by adding depreciation_method field.

This script scans scenarios/ and tests/ directories for YAML files,
detects missing 'depreciation_method' fields in tax sections, and
adds 'depreciation_method: "straight_line"' with proper formatting.

Follows GWTF rules R24 (docstring-first), R17 (Google docstrings),
TYPE-01 (typed-first), R14 (scripts in scripts/).

Usage:
    python scripts/fix_yaml_depreciation_method.py

The script:
    1. Finds all .yaml and .yml files
    2. Checks for existing depreciation_method
    3. Creates .bak backups before modifying
    4. Adds field to tax section with preserved indentation
    5. Reports results for each file

Example:
    $ python scripts/fix_yaml_depreciation_method.py
    🔍 Searching for YAML files...
    📝 Found 45 YAML files
    ✓ FIXED scenarios/example_a.yaml
      Backup: scenarios/example_a.yaml.bak
    ✓ SKIP tests/api/test_debt_fixture.yaml - already has depreciation_method
    ...
    ✅ Complete! Modified 20/45 files

Args:
    None (all configuration is internal)

Returns:
    Exit code 0 on success, 1 on critical error

Raises:
    SystemExit: If critical filesystem error occurs
"""

import re
import shutil
import sys
from pathlib import Path
from typing import List


def find_yaml_files() -> List[Path]:
    """Find all YAML files in scenarios and tests directories.

    Searches recursively through:
    - scenarios/ directory
    - tests/ directory

    Returns:
        List of Path objects for .yaml and .yml files

    Example:
        >>> files = find_yaml_files()
        >>> len(files)
        45
        >>> files[0]
        PosixPath('scenarios/example_a.yaml')
    """
    yaml_files: List[Path] = []

    # Search in scenarios directory
    scenarios_dir = Path("scenarios")
    if scenarios_dir.exists():
        yaml_files.extend(scenarios_dir.rglob("*.yaml"))
        yaml_files.extend(scenarios_dir.rglob("*.yml"))

    # Search in tests directory
    tests_dir = Path("tests")
    if tests_dir.exists():
        yaml_files.extend(tests_dir.rglob("*.yaml"))
        yaml_files.extend(tests_dir.rglob("*.yml"))

    return yaml_files


def fix_yaml_file(file_path: Path) -> bool:
    """Add depreciation_method to tax section if missing.

    Reads YAML file, detects missing depreciation_method in tax section,
    creates backup, and adds field with preserved indentation.

    Args:
        file_path: Path to YAML file to fix

    Returns:
        True if file was modified, False if skipped

    Raises:
        IOError: If file read/write fails
        ValueError: If YAML structure is invalid

    Example:
        >>> fix_yaml_file(Path("scenarios/example.yaml"))
        True  # File was modified
        >>> fix_yaml_file(Path("scenarios/already_fixed.yaml"))
        False  # File already has depreciation_method
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        # Check if depreciation_method already exists
        if re.search(r"depreciation_method\s*:", content):
            print(f"✓ SKIP {file_path} - already has depreciation_method")
            return False

        # Check if tax section exists
        if not re.search(r"tax\s*:", content):
            print(f"⚠ SKIP {file_path} - no tax section found")
            return False

        # Create backup
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)

        # Pattern to match tax section and add depreciation_method after first line
        # Handles various indentation levels
        pattern = r"(tax\s*:\s*\n)([ \t]+)"

        def add_depreciation(match: re.Match[str]) -> str:
            """Insert depreciation_method with matched indentation.

            Args:
                match: Regex match object with tax line and indentation

            Returns:
                Modified string with depreciation_method added
            """
            tax_line = match.group(1)
            indent = match.group(2)
            return f'{tax_line}{indent}depreciation_method: "straight_line"\n{indent}'

        modified_content = re.sub(pattern, add_depreciation, content, count=1)

        if modified_content == content:
            # Try alternative pattern for inline tax sections
            pattern2 = r"(tax\s*:\s*\{)"
            modified_content = re.sub(
                pattern2,
                r'\1"depreciation_method": "straight_line", ',
                content,
                count=1,
            )

        if modified_content != content:
            file_path.write_text(modified_content, encoding="utf-8")
            print(f"✓ FIXED {file_path}")
            print(f"  Backup: {backup_path}")
            return True
        else:
            print(f"⚠ SKIP {file_path} - could not find insertion point")
            backup_path.unlink()  # Remove unnecessary backup
            return False

    except Exception as e:
        print(f"✗ ERROR {file_path}: {e}")
        return False


def main() -> int:
    """Main execution function.

    Orchestrates the YAML fixing workflow:
    1. Find all YAML files
    2. Process each file
    3. Report summary

    Returns:
        Exit code: 0 on success, 1 on error

    Example:
        $ python scripts/fix_yaml_depreciation_method.py
        🔍 Searching for YAML files...
        📝 Found 45 YAML files
        ============================================================
        ✓ FIXED scenarios/example_a.yaml
        ✓ SKIP tests/fixtures/debt.yaml - already has depreciation_method
        ...
        ============================================================
        ✅ Complete! Modified 20/45 files
        💾 Backups created with .bak extension

        To remove backups after verification:
        find . -name '*.yaml.bak' -delete
    """
    print("🔍 Searching for YAML files...")
    yaml_files = find_yaml_files()

    if not yaml_files:
        print("❌ No YAML files found in scenarios/ or tests/ directories")
        return 1

    print(f"\n📝 Found {len(yaml_files)} YAML files")
    print("\n" + "=" * 60)

    fixed_count = 0
    for yaml_file in sorted(yaml_files):
        if fix_yaml_file(yaml_file):
            fixed_count += 1

    print("\n" + "=" * 60)
    print(f"\n✅ Complete! Modified {fixed_count}/{len(yaml_files)} files")
    print("💾 Backups created with .bak extension")
    print("\nTo remove backups after verification:")
    print("  find . -name '*.yaml.bak' -delete")

    return 0


if __name__ == "__main__":
    sys.exit(main())

# EOF - scripts/fix_yaml_depreciation_method.py
