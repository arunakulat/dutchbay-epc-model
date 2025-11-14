#!/usr/bin/env python3
"""
Diagnostic Script: Wind Production Logic and Capacity Factor Check

Usage:
  python scripts/diagnose_capacity_factor.py

Checks what value is used for cap_factor and details energy calculation logic for the model.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dutchbay_v13.finance.cashflow import _capacity_mw, _availability, _loss_factor, kwh_per_year
import yaml

print("="*80)
print("DUTCHBAY V13 - WIND PRODUCTION LOGIC DIAGNOSTIC")
print("="*80)

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'
with open(yaml_path) as f:
    params = yaml.safe_load(f)

cap_mw = _capacity_mw(params)
avail = _availability(params)
loss = _loss_factor(params)

# Check for 'capacity_factor'
cf_key = None
cf_val = None
if 'capacity_factor' in params.get('project', {}):
    cf_key = 'project.capacity_factor'
    cf_val = float(params['project']['capacity_factor'])
elif 'capacity_factor' in params:
    cf_key = 'capacity_factor'
    cf_val = float(params['capacity_factor'])
else:
    cf_key = 'N/A (model default)' 
    cf_val = None

print(f"Capacity (MW):    {cap_mw}")
print(f"Availability:     {avail*100:.1f}% (used if no capacity_factor)")
print(f"Loss factor:      {loss*100:.2f}%)")
print(f"Capacity factor origin: {cf_key} value: {cf_val}")

kwh = kwh_per_year(params)

print(f"\nAnnual Gross Production (kWh): {kwh:,.2f}")

print("\n--- Compute by logic ---")
if cf_val is not None:
    cap_factor = cf_val
    print(f"Model uses explicit capacity_factor: {cap_factor}")
else:
    cap_factor = avail
    print(f"Model falls back to availability: {cap_factor}")
print(f"Final hourly calculation: {cap_mw} MW x 1000 x 8760 x {cap_factor} x (1-loss)")

def _manual_calc():
    return cap_mw * 1000 * 8760 * cap_factor * (1 - loss)
manual = _manual_calc()
print(f"Manual production check: {manual:,.2f} kWh")

print("\nDiagnostic complete. If cap_factor is not what you expect, edit your YAML to set 'capacity_factor' under 'project:' to your desired annual average.")
print("="*80)
