"""
Minimal smoke test to ensure analytics.executive_workbook is imported.

This exists primarily to:
- Pull analytics/executive_workbook.py into the coverage set.
- Guarantee that the module remains import-safe under v14.
"""

def test_import_executive_workbook_module():
    # Import should succeed without side effects or errors.
    import analytics.executive_workbook  # noqa: F401
