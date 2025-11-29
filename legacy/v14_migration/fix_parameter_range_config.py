#!/usr/bin/env python3
"""
Auto-fix script for DutchBay ParameterRangeConfig validation.

This script automatically adds the missing @field_validator to enforce base_value > 0.

Usage:
    python fix_parameter_range_config.py

Result:
    - analytics/contractsv14.py is modified in-place
    - Backup created as analytics/contractsv14.py.backup
    - Tests should pass after running this script

Author: Go-With-The-Flow CI System
Date: 2025-11-26
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

TARGET_FILE = Path(__file__).parent / "analytics" / "contractsv14.py"

# The validator we're adding (will be inserted after the base_value field)
NEW_VALIDATOR = '''
    @field_validator('base_value')
    @classmethod
    def validate_base_value(cls, v):
        """Ensure base_value is strictly positive (> 0)."""
        if v <= 0:
            raise ValueError(f'base_value must be positive (> 0), got {v}')
        return v'''

# Pattern to find: the base_value field definition
# We look for the line where base_value is defined with Field(..., gt=0)
BASE_VALUE_PATTERN = re.compile(
    r"(\s+base_value:\s*float\s*=\s*Field\([^)]*gt=0[^)]*\))", re.MULTILINE
)

# We need to find where to insert the validator (right after the base_value field)
# Pattern to find the end of base_value field (looking for the next non-indented or field definition)
INSERT_PATTERN = re.compile(
    r"(base_value:\s*float\s*=\s*Field\([^)]*gt=0[^)]*\))\s*\n", re.MULTILINE
)

# ═════════════════════════════════════════════════════════════════════════════
# MAIN FIX LOGIC
# ═════════════════════════════════════════════════════════════════════════════


def check_file_exists() -> bool:
    """Verify target file exists."""
    if not TARGET_FILE.exists():
        print(f"❌ ERROR: File not found: {TARGET_FILE}")
        print(f"   Current working directory: {Path.cwd()}")
        print(f"   Looking for: {TARGET_FILE.absolute()}")
        return False
    return True


def check_validator_already_exists(content: str) -> bool:
    """Check if the validator is already present."""
    if "validate_base_value" in content:
        print("✓ Validator 'validate_base_value' already exists in file")
        return True
    return False


def find_base_value_field(content: str) -> tuple[int, int] | None:
    """
    Find the position of the base_value field definition.

    Returns: (start_pos, end_pos) tuple or None if not found
    """
    match = INSERT_PATTERN.search(content)
    if not match:
        print("❌ ERROR: Could not find 'base_value' field definition")
        print("   Expected pattern: base_value: float = Field(..., gt=0)")
        return None

    # Return positions: start of match and end of the line (where newline is)
    return (match.start(), match.end())


def apply_fix(content: str) -> tuple[str, bool]:
    """
    Apply the fix by inserting the validator after base_value field.

    Returns: (modified_content, success) tuple
    """
    # Find where to insert
    positions = find_base_value_field(content)
    if not positions:
        return (content, False)

    start_pos, end_pos = positions

    # Insert the validator after the base_value field
    modified_content = content[:end_pos] + NEW_VALIDATOR + "\n" + content[end_pos:]

    return (modified_content, True)


def create_backup(file_path: Path) -> Path:
    """Create a backup of the original file."""
    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
    shutil.copy2(file_path, backup_path)
    return backup_path


def write_file(file_path: Path, content: str) -> bool:
    """Write content to file."""
    try:
        file_path.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"❌ ERROR writing to file: {e}")
        return False


def verify_fix(file_path: Path) -> bool:
    """Verify that the fix was applied correctly."""
    content = file_path.read_text(encoding="utf-8")

    # Check that validator exists
    if "validate_base_value" not in content:
        print("❌ Verification FAILED: Validator not found in file")
        return False

    # Check that the validator has the correct logic
    if "if v <= 0:" not in content:
        print("❌ Verification FAILED: Validator logic not found")
        return False

    if (
        "raise ValueError" not in content
        or "base_value must be positive" not in content
    ):
        print("❌ Verification FAILED: Error message not found")
        return False

    print("✓ Verification PASSED: All validator components present")
    return True


def main() -> int:
    """
    Main execution flow.

    Returns: Exit code (0 = success, 1 = failure)
    """
    print("╔" + "═" * 76 + "╗")
    print("║  🔧 AUTO-FIX: ParameterRangeConfig Validator                          ║")
    print("║  Adds @field_validator to enforce base_value > 0                      ║")
    print("╚" + "═" * 76 + "╝")
    print()

    # Step 1: Check file exists
    print("[1/6] Checking if target file exists...")
    if not check_file_exists():
        return 1
    print(f"✓ Found: {TARGET_FILE}")
    print()

    # Step 2: Read file
    print("[2/6] Reading file...")
    try:
        content = TARGET_FILE.read_text(encoding="utf-8")
        print(f"✓ Read {len(content)} characters")
    except Exception as e:
        print(f"❌ ERROR reading file: {e}")
        return 1
    print()

    # Step 3: Check if validator already exists
    print("[3/6] Checking if validator already exists...")
    if check_validator_already_exists(content):
        print("ⓘ Validator already present - no changes needed")
        return 0
    print("✓ Validator not present - proceeding with fix")
    print()

    # Step 4: Create backup
    print("[4/6] Creating backup...")
    try:
        backup_path = create_backup(TARGET_FILE)
        print(f"✓ Backup created: {backup_path}")
    except Exception as e:
        print(f"❌ ERROR creating backup: {e}")
        return 1
    print()

    # Step 5: Apply fix
    print("[5/6] Applying fix...")
    modified_content, success = apply_fix(content)
    if not success:
        print("❌ ERROR: Could not apply fix")
        print("   The file structure may have changed. Manual intervention needed.")
        return 1
    print("✓ Fix applied successfully")
    print()

    # Step 6: Write file and verify
    print("[6/6] Writing file and verifying...")
    if not write_file(TARGET_FILE, modified_content):
        print("❌ ERROR: Could not write file")
        return 1
    print("✓ File written successfully")
    print()

    # Verify the fix
    print("[VERIFY] Verifying the fix...")
    if not verify_fix(TARGET_FILE):
        print("❌ Verification failed - restoring backup")
        shutil.copy2(
            TARGET_FILE.with_suffix(TARGET_FILE.suffix + ".backup"), TARGET_FILE
        )
        return 1
    print()

    # Success!
    print("╔" + "═" * 76 + "╗")
    print("║  ✅ FIX SUCCESSFUL                                                     ║")
    print("╚" + "═" * 76 + "╝")
    print()
    print("📝 Summary:")
    print(f"  • File: {TARGET_FILE}")
    print(f"  • Backup: {TARGET_FILE.with_suffix(TARGET_FILE.suffix + '.backup')}")
    print(f"  • Added: @field_validator('base_value') with logic to enforce > 0")
    print()
    print("🧪 Next steps:")
    print(
        "  1. Run tests: pytest tests/finance/test_contracts.py::TestParameterRangeConfig -v"
    )
    print("  2. Verify all tests pass")
    print("  3. Commit the change:")
    print("     git add analytics/contractsv14.py")
    print("     git commit -m 'fix: add explicit validator for base_value > 0'")
    print()
    print("💡 If tests still fail:")
    print(f"  • Restore backup: cp {TARGET_FILE}.backup {TARGET_FILE}")
    print("  • Check file structure may have changed")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
