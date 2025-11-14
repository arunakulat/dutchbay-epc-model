#!/usr/bin/env python3
"""
Test Script to Verify LLCR/PLCR Use Real Debt Balances

Verifies debt_outstanding is used in calculations from debt.py enhancement.
Usage:
    python scripts/test_llcr_plcr_real_debt.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr, summarize_project_metrics
from dutchbay_v13.finance.debt import apply_debt_layer
from dutchbay_v13.finance.cashflow import build_annual_rows
import yaml

print("="*80)
print("DUTCHBAY V13 - LLCR/PLCR REAL DEBT BALANCE TEST")
print("="*80)

# Load user YAML config (update path if needed)
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

# Build cashflows and apply debt schedule
annual_rows = build_annual_rows(params)
debt_results = apply_debt_layer(params, annual_rows)

assert 'debt_outstanding' in debt_results and len(debt_results['debt_outstanding']) > 0, "Debt outstanding not found!"

cfads_series = [row['cfads_usd'] for row in annual_rows]
debt_out_series = debt_results['debt_outstanding']

# Calculate LLCR and PLCR based on real balances
llcr_result = calculate_llcr(cfads_series, debt_out_series, discount_rate=0.10)
plcr_result = calculate_plcr(cfads_series, debt_out_series, discount_rate=0.10)

print("\nLLCR Result (first 5 years):", llcr_result['llcr_series'][:5])
print("PLCR Result (first 5 years):", plcr_result['plcr_series'][:5])

print(f"LLCR Min: {llcr_result['llcr_min']:.3f}x")
print(f"PLCR Min: {plcr_result['plcr_min']:.3f}x")

assert all(x >= 0 for x in llcr_result['llcr_series']), "LLCR calculation negative value!"
assert all(x >= 0 for x in plcr_result['plcr_series']), "PLCR calculation negative value!"
assert 0.95 < min(plcr_result['plcr_series']) / min(llcr_result['llcr_series']) <= 1.5, "PLCR should always be >= LLCR but not wildly greater"

# Full project metrics summary
metrics_summary = summarize_project_metrics(annual_rows, params)

print("\nMetrics DSCR Summary:", metrics_summary['dscr']['summary'])
print("LLCR (from metrics.py):", metrics_summary['llcr'])
print("PLCR (from metrics.py):", metrics_summary['plcr'])

# Confirm metrics.py uses the real OUTSTANDING series
assert metrics_summary['llcr']['llcr_min'] == llcr_result['llcr_min'], "metrics.py LLCR does not match direct calculation."
assert metrics_summary['plcr']['plcr_min'] == plcr_result['plcr_min'], "metrics.py PLCR does not match direct calculation."

print("\nALL LLCR/PLCR TESTS PASSED - REAL DEBT BALANCES IN USE\n")
print("="*80)
print("OK")
print("="*80)
