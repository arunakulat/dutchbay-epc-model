#!/usr/bin/env python3
"""
Extract actual v14 engine output values for regression test pins
Run from project root to see what the engine ACTUALLY produces
"""

from pathlib import Path

from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt


def print_debt_result(scenario_name: str):
    """Load scenario and print actual debt engine output."""
    print()
    print("=" * 70)
    print(f"Scenario: {scenario_name}")
    print("=" * 70)

    scenario_path = Path("scenarios") / scenario_name
    cfg = load_scenario_config(str(scenario_path))
    annual_rows = build_annual_rows(cfg)
    result = plan_debt(annual_rows=annual_rows, config=cfg)

    # Print tranche principals and IDC
    for tranche in ["lkr", "usd", "dfi"]:
        if tranche in result:
            principal = result[tranche].get("principal", 0.0)
            idc = result[tranche].get("idc", 0.0)
            print(f"\n{tranche.upper()}:")
            print(f"  principal: {principal:,.2f}")
            print(f"  idc: {idc:,.2f}")

    print("\nAggregate:")
    print(f"  total_idc: {result.get('total_idc', 0.0):,.2f}")
    print(f"  min_dscr: {result.get('min_dscr', 0.0):.4f}")
    print(f"  audit_status: {result.get('audit_status', 'N/A')}")


# Extract values
print("\n" + "🔍 ACTUAL v14 ENGINE OUTPUTS" + "\n")

try:
    print_debt_result("dutchbay_lendercase_2025Q4.yaml")
except Exception as e:
    print(f"Error: {e}")

try:
    print_debt_result("edge_extreme_stress.yaml")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("Copy the values above into the regression test")
print("=" * 70 + "\n")
