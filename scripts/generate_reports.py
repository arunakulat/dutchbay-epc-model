#!/usr/bin/env python3
"""
Report Generation Script

Runs full model and generates all institutional reports.

Usage:
    python scripts/generate_reports.py
"""

import sys
import yaml
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.finance.metrics import summarize_project_metrics
from dutchbay_v13.finance.reporting import generate_all_reports

print("="*80)
print("DUTCHBAY V13 - INSTITUTIONAL REPORT GENERATOR")
print("="*80)

# Load YAML
yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

print(f"\n✓ Loaded: {yaml_path.name}")

# TODO: Run full model here to get actual results
# For now, use test data
print("\n⚠️  Using test data (integrate with full model run for production)")

# Simplified test data
annual_rows = [
    {
        'year': i,
        'cfads_usd': 25_000_000,
        'debt_service': 12_000_000 if i < 15 else 0,
        'debt_outstanding': max(0, 105_000_000 * (1 - i/15))
    }
    for i in range(20)
]

# Calculate metrics
metrics_result = summarize_project_metrics(annual_rows, params)

# Mock IRR result (would come from irr.py in production)
irr_result = {
    'equity_irr': 0.18,
    'project_irr': 0.12,
    'npv_10': 45_000_000
}

print("\n--- Generating Reports ---")

# Generate all reports
reports = generate_all_reports(
    metrics_result=metrics_result,
    irr_result=irr_result,
    params=params,
    reporting_period="Q4 2025",
    lender_name="International Finance Corporation (IFC)"
)

print(f"\n✓ Covenant Certificate: {reports['covenant_cert']}")
print(f"✓ IC Summary: {reports['ic_summary']}")

print("\n" + "="*80)
print("REPORT GENERATION COMPLETE")
print("="*80)
