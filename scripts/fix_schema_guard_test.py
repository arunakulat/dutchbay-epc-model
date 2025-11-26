#!/usr/bin/env python3
"""Fix test_config_schema_guard.py to include capex in good_cfg.

The test's good_cfg is missing the capex section which is now required
by the schema validator.

Go with the Flow Compliance:
- Surgical edit to test file
- Add missing capex section
- Preserve all existing test logic
"""
from __future__ import annotations

from pathlib import Path


def fix_schema_guard_test() -> None:
    """Add capex section to good_cfg in test."""

    test_file = Path("tests/api/test_config_schema_guard.py")
    if not test_file.exists():
        print("❌ Test file not found")
        return

    content = test_file.read_text()

    # Find and replace the good_cfg definition
    old_good_cfg = """    good_cfg = {
        "Financing_Terms": {
            "tenor_years": 20,
        },
        "project": {
            "capacity_mw": 150.0,
            "capacity_factor_pct": 40.0,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 2_400_000.0,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
        },
    }"""

    new_good_cfg = """    good_cfg = {
        "Financing_Terms": {
            "tenor_years": 20,
        },
        "project": {
            "capacity_mw": 150.0,
            "capacity_factor_pct": 40.0,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 2_400_000.0,
        },
        "capex": {
            "usd_total": 225_000_000.0,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
        },
    }"""

    if old_good_cfg in content:
        content = content.replace(old_good_cfg, new_good_cfg)
        test_file.write_text(content)
        print("✅ Fixed test_config_schema_guard.py - added capex section")
    else:
        print("⚠️  Could not find exact pattern - manual fix needed")
        print("\nAdd this after opex section in good_cfg:")
        print('        "capex": {')
        print('            "usd_total": 225_000_000.0,')
        print("        },")


if __name__ == "__main__":
    fix_schema_guard_test()

# EOF
