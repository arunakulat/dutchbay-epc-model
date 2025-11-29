#!/usr/bin/env python3
"""Allow zero tariff in validation for edge case testing.

Changes validation from > 0 to >= 0 for tariff_lkr_per_kwh.
This allows test_zero_tariff_collapses_cfads to pass.
"""
from pathlib import Path


def fix_tariff_validation():
    """Allow zero tariff (>= 0 instead of > 0)."""

    cashflow_file = Path("finance/cashflow_v14.py")
    content = cashflow_file.read_text()

    # Change tariff validation to allow zero
    content = content.replace(
        'if tariff is None or tariff <= 0:\n        errors.append(\n            f"tariff_lkr_per_kwh: {tariff} invalid (must be > 0)"\n        )',
        'if tariff is None or tariff < 0:\n        errors.append(\n            f"tariff_lkr_per_kwh: {tariff} invalid (must be >= 0)"\n        )',
    )

    cashflow_file.write_text(content)
    print("✅ Fixed tariff validation to allow zero (>= 0)")


if __name__ == "__main__":
    fix_tariff_validation()
    print("\nNext steps:")
    print("  black finance/cashflow_v14.py")
    print(
        "  python -m pytest tests/api/test_cashflow_tax_and_life.py::test_zero_tariff_collapses_cfads -v"
    )

# EOF
