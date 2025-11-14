#!/usr/bin/env python3
"""
Diagnostics Script: Cashflow and Debt Outstanding Negative Value Check

File Name: scripts/diagnostic_check_cashflow_debt.py
Location: /Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/scripts/

Instructions:
1. Save this file to the scripts directory above.
2. Run the script from your venv:
      python scripts/diagnostic_check_cashflow_debt.py
3. Inspect the output to see if/when negative cashflows or debt balances occur, and send the output for corrective action.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.finance.cashflow import build_annual_rows
from dutchbay_v13.finance.debt import apply_debt_layer
import yaml

print("="*80)
print("DUTCHBAY V13 - CASHFLOW & DEBT NEGATIVE DIAGNOSTIC CHECK")
print("="*80)

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

annual_rows = build_annual_rows(params)

print("\nYEAR | CFADS_USD | REVENUE_USD | OPEX_USD")
for i, row in enumerate(annual_rows):
    cfads = row.get('cfads_usd', None)
    rev = row.get('revenue_usd', None)
    opex = row.get('opex_usd', None)
    warning = ''
    if cfads is not None and cfads < 0:
        warning += ' <NEGATIVE CFADS>'
    if rev is not None and rev < 0:
        warning += ' <NEGATIVE REVENUE>'
    if opex is not None and opex < 0:
        warning += ' <NEGATIVE OPEX>'
    print(f"{i+1:4} | {cfads:10,.2f} | {rev:12,.2f} | {opex:10,.2f} {warning}")

print("\nYEAR | DEBT_OUTSTANDING")
debt_results = apply_debt_layer(params, annual_rows)
for i, balance in enumerate(debt_results.get('debt_outstanding', [])):
    warning = ''
    if balance < 0:
        warning += ' <NEGATIVE DEBT BALANCE>'
    print(f"{i+1:4} | {balance:15,.2f} {warning}")

print("\nIf any row is flagged as NEGATIVE, review your YAML, cashflow, and debt logic.")
print("Send the output for targeted corrections.")
print("="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
