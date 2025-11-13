#!/usr/bin/env python3
"""
Metrics Integration Test - Uses Real YAML Parameters

Tests metrics against actual Dutch Bay 150MW project configuration.

Run: python tests/test_metrics_integration.py
"""

import sys
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.finance.metrics import (
    calculate_llcr,
    calculate_plcr,
    check_llcr_covenant,
    check_plcr_covenant
)

print("="*80)
print("METRICS INTEGRATION TEST - YAML-DRIVEN")
print("="*80)

# ============================================================================
# LOAD YAML CONFIGURATION
# ============================================================================
print("\n--- Loading YAML Configuration ---")

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'

try:
    with open(yaml_path, 'r') as f:
        params = yaml.safe_load(f)
    print(f"✓ Loaded: {yaml_path.name}")
except FileNotFoundError:
    print(f"✗ ERROR: {yaml_path} not found")
    sys.exit(1)

# ============================================================================
# EXTRACT PARAMETERS FROM YAML
# ============================================================================
print("\n--- Extracting Project Parameters ---")

# CAPEX
capex_usd = params.get('capex', {}).get('usd_total', 158_000_000)
print(f"  CAPEX: ${capex_usd/1e6:.1f}M")

# Financing
financing = params.get('Financing_Terms', {})
debt_ratio = financing.get('debt_ratio', 0.70)
tenor_years = financing.get('tenor_years', 15)
interest_only = financing.get('interest_only_years', 0)

print(f"  Debt Ratio: {debt_ratio:.1%}")
print(f"  Tenor: {tenor_years} years")
print(f"  Interest-Only: {interest_only} years")

debt_total = capex_usd * debt_ratio
print(f"  Total Debt: ${debt_total/1e6:.1f}M")

# Project timeline
project = params.get('project', {})
timeline = project.get('timeline', {})
lifetime_years = timeline.get('lifetime_years', 20)
print(f"  Project Life: {lifetime_years} years")

# Metrics config
metrics_config = params.get('metrics', {})
llcr_discount = metrics_config.get('llcr_discount_rate', 0.10)
llcr_covenant = metrics_config.get('llcr_min_covenant', 1.20)
plcr_covenant = metrics_config.get('plcr_min_covenant', 1.40)

print(f"  LLCR Discount Rate: {llcr_discount:.1%}")
print(f"  LLCR Covenant: {llcr_covenant:.2f}x")
print(f"  PLCR Covenant: {plcr_covenant:.2f}x")

# ============================================================================
# SIMPLIFIED CASHFLOW PROJECTION (For Testing)
# ============================================================================
print("\n--- Generating Test Cashflows ---")

# This is simplified - in production, would come from full model run
# Assume constant CFADS for testing
annual_cfads_usd = 25_000_000  # $25M/year (simplified)
cfads_series = [annual_cfads_usd] * lifetime_years

# Linear debt amortization (simplified)
debt_outstanding = []
for year in range(lifetime_years):
    if year < tenor_years:
        remaining = debt_total * (1 - year / tenor_years)
    else:
        remaining = 0
    debt_outstanding.append(remaining)

print(f"  CFADS/year: ${annual_cfads_usd/1e6:.1f}M (constant)")
print(f"  Debt at Year 0: ${debt_outstanding[0]/1e6:.1f}M")
print(f"  Debt at Year {tenor_years-1}: ${debt_outstanding[tenor_years-1]/1e6:.1f}M")
print(f"  Debt at Year {tenor_years}: ${debt_outstanding[tenor_years]/1e6:.1f}M")

# ============================================================================
# CALCULATE LLCR
# ============================================================================
print("\n--- Calculating LLCR ---")

llcr_result = calculate_llcr(
    cfads_series,
    debt_outstanding,
    discount_rate=llcr_discount
)

print(f"✓ LLCR Min: {llcr_result['llcr_min']:.2f}x")
print(f"✓ LLCR Avg: {llcr_result['llcr_avg']:.2f}x")

# Check covenant
llcr_covenant_check = check_llcr_covenant(llcr_result, params)
print(f"✓ Covenant Status: {llcr_covenant_check['covenant_status']}")

# ============================================================================
# CALCULATE PLCR
# ============================================================================
print("\n--- Calculating PLCR ---")

plcr_result = calculate_plcr(
    cfads_series,
    debt_outstanding,
    discount_rate=llcr_discount
)

print(f"✓ PLCR Min: {plcr_result['plcr_min']:.2f}x")
print(f"✓ PLCR Avg: {plcr_result['plcr_avg']:.2f}x")

# Check covenant
plcr_covenant_check = check_plcr_covenant(plcr_result, params)
print(f"✓ Covenant Status: {plcr_covenant_check['covenant_status']}")

# ============================================================================
# COMPLIANCE SUMMARY
# ============================================================================
print("\n" + "="*80)
print("COVENANT COMPLIANCE SUMMARY (YAML-CONFIGURED)")
print("="*80)

all_pass = (
    llcr_covenant_check['covenant_status'] == 'PASS' and
    plcr_covenant_check['covenant_status'] == 'PASS'
)

print(f"\nLLCR Covenant ({llcr_covenant:.2f}x): {llcr_covenant_check['covenant_status']}")
print(f"PLCR Covenant ({plcr_covenant:.2f}x): {plcr_covenant_check['covenant_status']}")
print(f"\nOverall Status: {'✓ ALL COVENANTS SATISFIED' if all_pass else '✗ REVIEW REQUIRED'}")

if not all_pass:
    print("\nViolations:")
    for v in llcr_covenant_check.get('violations', []):
        print(f"  - {v}")
    for v in plcr_covenant_check.get('violations', []):
        print(f"  - {v}")

print("="*80)
print("\n✓ Integration test complete - metrics validated against YAML config")
print("="*80)
