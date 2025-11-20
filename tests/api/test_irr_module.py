"""Smoke tests for the finance.irr module (v14 canonical).

Canonical engine path (from repo root):
    dutchbay_v14chat/finance/irr.py

These tests pin the public IRR/NPV API surface so that future refactors
can't silently break behaviour. They are intentionally simple and fast.
"""

from datetime import datetime
from pathlib import Path
import sys

import pytest

# ---------------------------------------------------------------------------
# Ensure repo root (/DutchBay_EPC_Model) is on sys.path
# ---------------------------------------------------------------------------

# This file lives at: <repo_root>/tests/api/test_irr_module.py
THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[2]  # .../DutchBay_EPC_Model

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Canonical import: v14chat IRR engine
# ---------------------------------------------------------------------------

from dutchbay_v14chat.finance import irr as irr_mod  # type: ignore


def test_irr_module_path_is_v14chat():
    """Ensure we are really testing the v14chat IRR engine at the expected path."""
    irr_path = Path(irr_mod.__file__).as_posix()
    # We don't lock the absolute prefix (user dir may vary), but the repo-relative
    # path segment must match the canonical location:
    assert "dutchbay_v14chat/finance/irr.py" in irr_path, irr_path


def test_npv_basic_positive_case():
    """Simple positive NPV case: classic project finance toy example."""
    cashflows = [-1000.0, 500.0, 500.0, 500.0]
    result = irr_mod.npv(0.10, cashflows)
    # Hand-computed NPV is ~243.426 at 10%; allow for FP rounding.
    assert result == pytest.approx(243.426, rel=1e-3)


def test_irr_basic_case():
    """IRR for a simple series should be in a reasonable range."""
    cashflows = [-1000.0, 500.0, 500.0, 500.0]
    result = irr_mod.irr(cashflows)
    assert result is not None
    # Known IRR for this pattern is around 23.38%
    assert 0.23 < result < 0.24


def test_irr_no_sign_change_returns_none():
    """If cashflows never change sign, IRR should be None."""
    assert irr_mod.irr([100.0, 100.0, 100.0]) is None
    assert irr_mod.irr([-100.0, -50.0]) is None


def test_xnpv_and_xirr_basic_case():
    """XNPV/XIRR should behave consistently on irregular dates."""
    cashflows = [-1000.0, 400.0, 400.0, 400.0]
    dates = [
        datetime(2020, 1, 1),
        datetime(2020, 7, 1),
        datetime(2021, 1, 1),
        datetime(2021, 7, 1),
    ]

    rate = 0.10
    xnpv_value = irr_mod.xnpv(rate, cashflows, dates)
    # Just assert magnitude is reasonable; sign depends on exact timing.
    assert abs(xnpv_value) < 200.0

    xirr_value = irr_mod.xirr(cashflows, dates)
    # IRR should be a sensible positive rate
    assert xirr_value is not None
    assert 0.10 < xirr_value < 0.30


def test_xirr_mismatched_lengths_raises():
    """Mismatched cashflows/dates must raise ValueError."""
    cashflows = [-1000.0, 500.0]
    dates = [datetime(2020, 1, 1)]
    with pytest.raises(ValueError):
        irr_mod.xirr(cashflows, dates)
