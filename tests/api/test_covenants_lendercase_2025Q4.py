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

from pathlib import Path
import math

from analytics.scenario_loader import load_scenario_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import plan_debt


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

    debt_outstanding = debt["debt_outstanding"]
    debt_service_total = debt["debt_service_total"]

    assert len(debt_outstanding) == timeline
    assert len(debt_service_total) == timeline

    # No negative balances or service flows
    assert all(v >= 0.0 for v in debt_outstanding), "Negative debt outstanding found"
    assert all(v >= 0.0 for v in debt_service_total), "Negative debt service found"

    # IDC should be strictly positive in a construction case
    total_idc = float(debt.get("total_idc_capitalized", 0.0))
    assert total_idc > 0.0, "Expected some IDC to be capitalised for lender case"


def test_lendercase_covenants_min_dscr_and_audit_status():
    """
    Lender-case covenant expectations:

    1. min_dscr must be numerically sane and comfortably above bare
       break-even (we require >= 1.20 but do NOT force 1.30 here).

    2. audit_status must be consistent with the debt engine's own rule:
         - PASS if min_dscr >= 1.30
         - REVIEW otherwise

       We explicitly do NOT force a commercial outcome (e.g. insisting
       that the lender case "must" be PASS). The test's job is to
       verify the mapping and numerical sanity, not to override credit
       committee judgement via assertions.
    """
    config = _load_lendercase_config()

    annual_rows = build_annual_rows(config)
    debt = plan_debt(annual_rows=annual_rows, config=config)

    min_dscr = float(debt["min_dscr"])
    audit_status = str(debt.get("audit_status", "")).upper()

    # DSCR should be finite and numerically sane
    assert math.isfinite(min_dscr), "min_dscr is not finite"
    assert -10.0 < min_dscr < 50.0, f"min_dscr looks insane: {min_dscr}"

    # Lender case should be above bare break-even
    assert min_dscr >= 1.20, (
        f"Expected lender-case min DSCR >= 1.20, got {min_dscr:.3f}"
    )

    # Pin the mapping from min_dscr -> audit_status to the engine's rule.
    # The debt engine currently does:
    #   audit_status = "PASS" if dscr_min >= 1.30 else "REVIEW"
    expected_audit = "PASS" if min_dscr >= 1.30 else "REVIEW"
    assert audit_status == expected_audit, (
        "audit_status/min_dscr mismatch: "
        f"min_dscr={min_dscr:.3f}, audit_status={audit_status!r}, "
        f"expected {expected_audit!r} under engine mapping"
    )
