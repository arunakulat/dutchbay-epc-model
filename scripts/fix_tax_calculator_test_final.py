#!/usr/bin/env python3
"""Fix test_tax_calculator_v14.py to use canonical finance.tax_v14 module."""
from pathlib import Path

test_file = Path("tests/api/test_tax_calculator_v14.py")
content = test_file.read_text()

# Remove skip marker and try block
content = content.replace(
    '''# Tax calculator was integrated into cashflow_v14 but these specific
# functions may have been refactored. Skipping until confirmed.
pytestmark = pytest.mark.skip(reason="Tax calculator refactor in progress")

try:
    from finance.cashflow_v14 import (''',
    'from finance.tax_v14 import ('
)

# Update docstring
content = content.replace(
    'Smoke + behaviour tests for analytics.tax_calculator.',
    'Smoke + behaviour tests for finance.tax_v14.'
)

test_file.write_text(content)
print("✅ Fixed test_tax_calculator_v14.py to use finance.tax_v14")
