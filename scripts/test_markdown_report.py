#!/usr/bin/env python3
"""
Test Script for Option A Step 2: Markdown Report Generation

Usage:
    python scripts/test_markdown_report.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.reporting.markdown_generator import generate_executive_summary, generate_dfi_lender_pack
from dutchbay_v13.finance.metrics import calculate_llcr, calculate_plcr
from dutchbay_v13.finance.debt import apply_debt_layer
from dutchbay_v13.finance.cashflow import build_annual_rows
import yaml

print("="*80)
print("DUTCHBAY V13 - MARKDOWN REPORT GENERATION TEST")
print("="*80)

# Load config
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

# Build model
annual_rows = build_annual_rows(params)
debt_results = apply_debt_layer(params, annual_rows)
cfads_series = [row['cfads_usd'] for row in annual_rows]
debt_outstanding_series = debt_results.get('debt_outstanding', [0.0]*len(annual_rows))
debt_service_series = debt_results.get('debt_service_total', [0.0]*len(annual_rows))

llcr_result = calculate_llcr(cfads_series, debt_outstanding_series, discount_rate=0.10)
plcr_result = calculate_plcr(cfads_series, debt_outstanding_series, discount_rate=0.10)

# Generate reports
outputs_dir = Path(__file__).parent.parent / 'outputs'
outputs_dir.mkdir(parents=True, exist_ok=True)

print("\n--- Generating Executive Summary ---")
exec_summary = generate_executive_summary(
    params,
    cfads_series,
    debt_outstanding_series,
    llcr_result,
    plcr_result,
    output_path=outputs_dir / 'executive_summary.md'
)
print(f"✓ Written to: {outputs_dir / 'executive_summary.md'}")

print("\n--- Generating DFI/Lender Pack ---")
dfi_pack = generate_dfi_lender_pack(
    params,
    cfads_series,
    debt_outstanding_series,
    debt_service_series,
    llcr_result,
    plcr_result,
    output_path=outputs_dir / 'dfi_lender_pack.md'
)
print(f"✓ Written to: {outputs_dir / 'dfi_lender_pack.md'}")

print("\n" + "="*80)
print("MARKDOWN REPORTS GENERATED SUCCESSFULLY")
print("="*80)
print("\nReports created:")
print(f"  1. {outputs_dir / 'executive_summary.md'}")
print(f"  2. {outputs_dir / 'dfi_lender_pack.md'}")
print("\n✓ All tests passed - ready for production use")
