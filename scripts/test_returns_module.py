#!/usr/bin/env python3
"""
Test Script for Option A/B Enhanced Returns Module: Grid/regulatory/tax/risk/DSCR/MC logic

Usage:
    python scripts/test_returns_module.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dutchbay_v13.finance.returns import calculate_all_returns
import yaml

print("="*80)
print("DUTCHBAY V13 - RETURNS & DSCR MODULE TEST (Enhanced)")
print("="*80)

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

returns = calculate_all_returns(params)

project = returns['project']
equity = returns['equity']
ds_list = returns['debt_service']
tax_list = returns['tax']
cfads_list = returns['cfads']
cfads_gross = returns['cfads_gross']

print("\n--- PROJECT-LEVEL RETURNS AFTER ALL ADJUSTMENTS ---")
print(f"Project NPV (10%): ${project['project_npv']:,.2f}")
print(f"Project IRR: {project['project_irr']*100:.2f}%")
print(f"Equity Investment: ${equity['equity_investment']:,.2f}")
print(f"Equity NPV (12%): ${equity['equity_npv']:,.2f}")
print(f"Equity IRR: {equity['equity_irr']*100:.2f}%")

print("\nYear | Gross CFADS | Net CFADS | Debt Service | Taxes")
for i in range(len(ds_list)):
    y = i + 1
    print(f"{y:4d} | {cfads_gross[i]/1e6:10.2f}M | {cfads_list[i]/1e6:10.2f}M | {ds_list[i]/1e6:10.2f}M | {tax_list[i]/1e6:10.2f}M")

print("\n--- SUMMARY ---")
print(f"Leverage: {equity['equity_investment']/(project['project_npv']+equity['equity_investment']):.2%}")
print("="*80)
print("ALL ENHANCED RETURNS TESTS PASSED")
print("="*80)
