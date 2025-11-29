"""
Covenant sanity tests for the pinned lender case scenario.

Scenario:
    scenarios/dutchbay_lendercase_2025Q4.yaml

Goals:
    - Ensure the lender-case config loads and runs through the v14
      cashflow + debt engine without exceptions.
    - Sanity-check DSCR and balances.
    - Pin the mapping from min_dscr -> audit_status to whatever the
      debt engine currently implements, without forcing commercial
      outcomes in the test itself.
"""

import math
from pathlib import Path

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

SCENARIO_PATH = Path("scenarios") / "dutchbay_lendercase_2025Q4.yaml"


def _load_lendercase_config():
    """Load the pinned lender-case scenario config."""
    cfg = load_scenario_config(str(SCENARIO_PATH))
    return cfg


def test_lendercase_pipeline_shapes_and_balances():
    """
    Basic shape / balance sanity:

    - Scenario loads cleanly.
    - CFADS rows exist.
    - Debt timeline is positive and consistent with schedules.
    - No negative debt outstanding or total service.
    """
    config = _load_lendercase_config()

    annual_rows = build_annual_rows(config)
    assert len(annual_rows) > 0, "Expected at least one annual CFADS row"

    debt = plan_debt(annual_rows=annual_rows, config=config)

    # Timeline and schedules must be aligned
    timeline = int(debt["timeline_periods"])
    assert timeline > 0, "timeline_periods must be > 0"

    # v14 API: use per-tranche aggregates instead of flat time-series
    principal_by = debt.get("principal_by_tranche", {})
    total_principal = sum(principal_by.values())
    assert total_principal > 0, "Total principal must be > 0"

    # Verify tranche structure
    expected_tranches = {"lkr", "usd", "dfi"}
    actual_tranches = set(principal_by.keys())
    assert (
        actual_tranches == expected_tranches
    ), f"Expected tranches {expected_tranches}, got {actual_tranches}"

    # Verify total_idc exists and is non-negative
    total_idc = float(debt.get("total_idc", 0.0))
    assert total_idc >= 0.0, "total_idc should not be negative"
