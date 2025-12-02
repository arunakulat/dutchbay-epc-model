"""
Legacy debt construction + IDC regression pins.

Canonical v14 suite now lives in:
    tests/api/test_debt_construction_idc_regression_v14.py

This module is kept only as a historical placeholder and is skipped by default.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    "Superseded by tests/api/test_debt_construction_idc_regression_v14.py – "
    "use that file as the canonical v14 debt/IDC regression suite."
)
