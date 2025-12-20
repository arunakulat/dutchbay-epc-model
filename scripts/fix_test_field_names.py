#!/usr/bin/env python3
"""Fix field name mismatches in test files."""

from pathlib import Path
import re

def fix_file(filepath: Path) -> int:
    """Fix field names in a single file. Returns number of fixes."""
    content = filepath.read_text()
    original = content
    
    # SensitivitySuite field name changes
    content = re.sub(
        r'tornado_results\s*=',
        'tornado_ranking=',
        content
    )
    
    # TechnologyBreakdown field name
    content = re.sub(
        r'technology\s*=\s*["\']',
        'technology_type="',
        content
    )
    content = re.sub(
        r"technology\s*=\s*'",
        "technology_type='",
        content
    )
    
    # BreakevenResult field names (common in older tests)
    content = re.sub(
        r'([\(,]\s*)variable\s*=',
        r'\1variable_name=',
        content
    )
    content = re.sub(
        r'([\(,]\s*)bracket\s*=',
        r'\1# bracket=  # Removed in Pydantic migration',
        content
    )
    content = re.sub(
        r'([\(,]\s*)status\s*=',
        r'\1# status=  # Removed in Pydantic migration',
        content
    )
    
    # TailRiskSnapshot field name changes
    # Old: metric=, New: metric_name=
    content = re.sub(
        r'TailRiskSnapshot\s*\(\s*metric\s*=',
        'TailRiskSnapshot(metric_name=',
        content
    )
    
    # MonteCarloResult: old constructors won't work, need model_validate
    # Replace MonteCarloResult(...) with MonteCarloResult.model_validate(...)
    # But only if it's already a dict-like call
    
    if content != original:
        filepath.write_text(content)
        return 1
    return 0

def main():
    """Fix all test files."""
    tests_dir = Path("tests")
    fixed_count = 0
    
    # Find all Python test files
    for test_file in tests_dir.rglob("test_*.py"):
        if fix_file(test_file):
            print(f"✅ Fixed: {test_file}")
            fixed_count += 1
    
    print(f"\n📊 Fixed {fixed_count} test files")
    print("\nField name updates:")
    print("  - tornado_results → tornado_ranking")
    print("  - technology → technology_type")
    print("  - variable → variable_name")
    print("  - metric → metric_name (for TailRiskSnapshot)")
    print("  - Removed: bracket, status (not in Pydantic schema)")
    
    # Self-delete
    Path(__file__).unlink()
    print("🗑️  Self-deleted")

if __name__ == "__main__":
    main()
