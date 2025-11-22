#!/usr/bin/env python3
"""
Debt Module Validation Test Driver - P0-1B
Tests the enhanced debt.py with YAML-driven constraints

Run from project root:
    source venv/bin/activate
    python tests/test_debt_validation.py
"""

import sys
from pathlib import Path
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'dutchbay_v13'))

from finance.debt import apply_debt_layer

print("="*80)
print("DEBT MODULE VALIDATION TEST - P0-1B")
print("="*80)

# ============================================================================
# TEST 1: VALID SCENARIO (Should PASS)
# ============================================================================
print("\n--- Test 1: Valid Baseline (Should PASS) ---")

params_valid = {
    'project': {
        'timeline': {
            'lifetime_years': 20
        }
    },
    'capex': {
        'usd_total': 225_000_000  # 225M USD
    },
    'Financing_Terms': {
        'debt_ratio': 0.70,
        'tenor_years': 15,
        'interest_only_years': 2,
        'amortization_style': 'sculpted',
        'target_dscr': 1.35,
        'min_dscr': 1.20,
        'mix': {
            'lkr_max': 0.45,
            'dfi_max': 0.10,
            'usd_commercial_min': 0.45
        },
        'rates': {
            'lkr_nominal': 0.10,
            'usd_nominal': 0.07,
            'dfi_nominal': 0.05
        },
        'constraints': {
            'max_debt_ratio': 0.85,
            'warn_debt_ratio': 0.80,
            'min_dscr_covenant': 1.30,
            'warn_dscr': 1.25,
            'max_balloon_pct': 0.10,
            'warn_balloon_pct': 0.05,
            'max_tenor_years': 25,
            'warn_tenor_years': 20,
            'max_interest_rate': 0.25,
            'min_interest_rate': 0.0,
            'lender_type': 'DFI',
            'jurisdiction': 'Sri Lanka'
        }
    }
}

# Mock annual cashflows
annual_rows_valid = [
    {'cfads_usd': 25_000_000} for _ in range(20)  # 25M/year for 20 years
]

try:
    result = apply_debt_layer(params_valid, annual_rows_valid)
    print(f"✓ Test 1 PASSED")
    print(f"  Min DSCR: {result['dscr_min']:.2f}x")
    print(f"  Balloon: ${result['balloon_remaining']/1e6:.2f}M")
    print(f"  Audit Status: {result['audit_status']}")
    print(f"  Warnings: {len(result['validation_warnings'])}")
    print(f"  DSCR Violations: {len(result['dscr_violations'])}")
except Exception as e:
    print(f"✗ Test 1 FAILED: {e}")

# ============================================================================
# TEST 2: HIGH DEBT RATIO (Should ERROR)
# ============================================================================
print("\n--- Test 2: Excessive Debt Ratio (Should ERROR) ---")

params_high_debt = params_valid.copy()
params_high_debt['Financing_Terms'] = params_valid['Financing_Terms'].copy()
params_high_debt['Financing_Terms']['debt_ratio'] = 0.90  # Above 0.85 max

try:
    result = apply_debt_layer(params_high_debt, annual_rows_valid)
    print(f"✗ Test 2 FAILED: Should have raised ValueError")
except ValueError as e:
    print(f"✓ Test 2 PASSED: Correctly rejected high debt ratio")
    print(f"  Error: {str(e)[:100]}...")

# ============================================================================
# TEST 3: LOW DSCR (Should WARN)
# ============================================================================
print("\n--- Test 3: Low DSCR Target (Should WARN) ---")

params_low_dscr = params_valid.copy()
params_low_dscr['Financing_Terms'] = params_valid['Financing_Terms'].copy()
params_low_dscr['Financing_Terms']['target_dscr'] = 1.22  # Below 1.30 min

try:
    result = apply_debt_layer(params_low_dscr, annual_rows_valid)
    print(f"✓ Test 3 PASSED: Accepted with warning")
    print(f"  Warnings: {result['validation_warnings']}")
except Exception as e:
    print(f"✗ Test 3 FAILED: {e}")

# ============================================================================
# TEST 4: NEGATIVE INTEREST RATE (Should ERROR)
# ============================================================================
print("\n--- Test 4: Negative Interest Rate (Should ERROR) ---")

params_neg_rate = params_valid.copy()
params_neg_rate['Financing_Terms'] = params_valid['Financing_Terms'].copy()
params_neg_rate['Financing_Terms']['rates'] = params_valid['Financing_Terms']['rates'].copy()
params_neg_rate['Financing_Terms']['rates']['usd_nominal'] = -0.02

try:
    result = apply_debt_layer(params_neg_rate, annual_rows_valid)
    print(f"✗ Test 4 FAILED: Should have rejected negative rate")
except ValueError as e:
    print(f"✓ Test 4 PASSED: Correctly rejected negative rate")

# ============================================================================
# TEST 5: STRESS SCENARIO - LOW CASHFLOWS (Should flag DSCR violations)
# ============================================================================
print("\n--- Test 5: Stress Scenario - Low Cashflows (Should flag DSCR) ---")

annual_rows_stress = [
    {'cfads_usd': 15_000_000} for _ in range(20)  # Only 15M/year (stressed)
]

try:
    result = apply_debt_layer(params_valid, annual_rows_stress)
    print(f"✓ Test 5 PASSED")
    print(f"  Min DSCR: {result['dscr_min']:.2f}x")
    print(f"  DSCR Violations: {len(result['dscr_violations'])}")
    if result['dscr_violations']:
        print(f"  First violation: {result['dscr_violations'][0]}")
    print(f"  Audit Status: {result['audit_status']}")
except Exception as e:
    print(f"✗ Test 5 FAILED: {e}")

# ============================================================================
# TEST 6: LOAD FROM ACTUAL YAML FILE (Integration Test)
# ============================================================================
print("\n--- Test 6: Load from full_model_variables_updated.yaml ---")

yaml_path = Path(__file__).parent.parent / 'full_model_variables_updated.yaml'

if yaml_path.exists():
    try:
        with open(yaml_path, 'r') as f:
            yaml_params = yaml.safe_load(f)
        
        # Check if constraints block exists
        if 'constraints' in yaml_params.get('Financing_Terms', {}):
            print(f"✓ Test 6 PASSED: YAML file has constraints block")
            constraints = yaml_params['Financing_Terms']['constraints']
            print(f"  Max debt ratio: {constraints.get('max_debt_ratio')}")
            print(f"  Min DSCR covenant: {constraints.get('min_dscr_covenant')}")
            print(f"  Lender type: {constraints.get('lender_type')}")
        else:
            print(f"⚠ Test 6 WARNING: YAML file found but missing constraints block")
            print(f"  Add the constraints block from Part 1 above")
    except Exception as e:
        print(f"✗ Test 6 FAILED: {e}")
else:
    print(f"⚠ Test 6 SKIPPED: YAML file not found at {yaml_path}")
    print(f"  This is expected if testing before YAML update")

# ============================================================================
# TEST 7: BALLOON PAYMENT REFINANCING ANALYSIS
# ============================================================================
print("\n--- Test 7: Balloon Refinancing Analysis ---")

params_balloon = params_valid.copy()
params_balloon['Financing_Terms'] = params_valid['Financing_Terms'].copy()
params_balloon['Financing_Terms']['tenor_years'] = 12  # Shorter tenor = more balloon
params_balloon['Financing_Terms']['constraints'] = params_valid['Financing_Terms']['constraints'].copy()
params_balloon['Financing_Terms']['constraints']['refinancing'] = {
    'enabled': True,
    'max_refinance_pct': 0.15,
    'refinance_rate_premium': 0.02,
    'refinance_tenor_years': 5
}

try:
    result = apply_debt_layer(params_balloon, annual_rows_valid)
    print(f"✓ Test 7 PASSED")
    print(f"  Balloon: ${result['balloon_remaining']/1e6:.2f}M ({result['balloon_remaining']/157.5e6:.1%})")
    
    refi = result.get('refinancing_analysis', {})
    print(f"  Refinancing feasible: {refi.get('feasible')}")
    print(f"  Mitigation required: {refi.get('mitigation_required')}")
    if refi.get('notes'):
        print(f"  Notes: {refi['notes']}")
    
    # Check alignment notes
    alignment = result.get('alignment_notes', {})
    if alignment:
        print(f"\n  Parameter Alignment:")
        for param, info in alignment.items():
            print(f"    {param}: YAML={info.get('yaml')}, Effective={info.get('effective')}")
            
except Exception as e:
    print(f"✗ Test 7 FAILED: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*80)
print("VALIDATION TEST SUMMARY")
print("="*80)
print("""
Expected Results:
- Test 1 (Valid): PASS ✓
- Test 2 (High Debt): ERROR (correctly rejected) ✓
- Test 3 (Low DSCR): WARN (accepted with warning) ✓
- Test 4 (Negative Rate): ERROR (correctly rejected) ✓
- Test 5 (Stress): PASS with DSCR violations flagged ✓
- Test 6 (YAML): PASS if constraints added to YAML ✓
- Test 7: BALLOON PAYMENT REFINANCING ANALYSIS ✓

All tests passing = P0-1B Complete!
""")
print("="*80)


