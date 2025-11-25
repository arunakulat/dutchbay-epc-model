#!/usr/bin/env python3
"""
DUTCHBAY V13 - P0-2D MODULE TEST (DUAL REGIME ANALYSIS)
Load both recent regime AND historical tail-risk data

Dual Model Approach:
1. PRIMARY: Recent Regime (2016-2025) - Lender presentation
2. OVERLAY: Historical Tail-Risk (1975-2025) - Risk extremes

Version: 1.0.0-dual-regime
Date: 2025-11-14
Usage: python3 test_fx_dual_regime.py
"""

import pandas as pd
import numpy as np
import yaml
from datetime import datetime
from glob import glob
from pathlib import Path
from fx_correlation_module import FXCorrelationModule

def load_fx_data_dual_regime():
    """
    Load BOTH recent regime (2016-2025) AND historical decades (1975-2025)
    Returns: (recent_df, historical_df)
    """
    
    recent_files = sorted(glob('fx_data_recent_Period*.yaml'))
    historical_files = sorted(glob('fx_data_historical_Decade*.yaml'))
    
    if not recent_files or not historical_files:
        print("âœ— ERROR: Missing YAML files!")
        print("  Recent files found:", len(recent_files))
        print("  Historical files found:", len(historical_files))
        print("\n  Run: python3 fx_data_processor_dual_regime.py data.csv")
        return None, None
    
    print(f"\nâœ“ Found {len(recent_files)} recent regime files")
    print(f"âœ“ Found {len(historical_files)} historical decade files")
    
    # Load recent regime
    print("\n[RECENT REGIME] Loading 2016-2025 periods...")
    recent_records = []
    for yaml_file in recent_files:
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
            period = data['metadata']['period']
            total_months = data['metadata']['total_months']
            print(f"  âœ“ {period}: {total_months} months")
            recent_records.extend(data['fx_monthly_data'])
        except Exception as e:
            print(f"  âœ— Error loading {yaml_file}: {e}")
            return None, None
    
    # Load historical decades
    print("\n[HISTORICAL DECADES] Loading 1975-2025 for tail-risk...")
    historical_records = []
    for yaml_file in historical_files:
        try:
            with open(yaml_file, 'r') as f:
                data = yaml.safe_load(f)
            period = data['metadata']['period']
            regime = data['metadata']['regime_name']
            total_months = data['metadata']['total_months']
            print(f"  âœ“ {period} ({regime}): {total_months} months")
            historical_records.extend(data['fx_monthly_data'])
        except Exception as e:
            print(f"  âœ— Error loading {yaml_file}: {e}")
            return None, None
    
    # Convert to DataFrames
    recent_df = pd.DataFrame(recent_records)
    recent_df['Year-Month'] = pd.to_datetime(recent_df['date'])
    recent_df = recent_df.sort_values('Year-Month').reset_index(drop=True)
    
    historical_df = pd.DataFrame(historical_records)
    historical_df['Year-Month'] = pd.to_datetime(historical_df['date'])
    historical_df = historical_df.sort_values('Year-Month').reset_index(drop=True)
    
    return recent_df, historical_df

def main():
    """Run comprehensive dual-regime test"""
    
    print("\n" + "="*90)
    print("DUTCHBAY V13 - P0-2D MODULE TEST SUITE")
    print("Dual Regime Analysis: Recent + Historical Tail-Risk")
    print("="*90)
    
    # Load both regimes
    recent_df, historical_df = load_fx_data_dual_regime()
    if recent_df is None or historical_df is None:
        print("\nâœ— SETUP FAILED")
        return 1
    
    # ========================================================================
    # REGIME 1: RECENT (Primary Analysis)
    # ========================================================================
    print("\n" + "â–ˆ"*90)
    print("REGIME 1: RECENT REGIME ANALYSIS (2016-2025)")
    print("Primary model for lender presentation")
    print("â–ˆ"*90)
    
    print(f"\nâœ“ Recent regime data:")
    print(f"  Total records: {len(recent_df)} months")
    print(f"  Date range: {recent_df['Year-Month'].min().strftime('%Y-%m')} to {recent_df['Year-Month'].max().strftime('%Y-%m')}")
    print(f"  FX range: {recent_df['avg_rate'].min():.2f} - {recent_df['avg_rate'].max():.2f} LKR/USD")
    print(f"  Mean rate: {recent_df['avg_rate'].mean():.2f}")
    print(f"  Mean volatility: {recent_df['rolling_12m_vol_pct'].mean():.2f}%")
    
    # Initialize module with recent data
    try:
        module_recent = FXCorrelationModule(recent_df.rename(columns={
            'avg_rate': 'Avg FX Rate',
            'rolling_12m_vol_pct': 'Rolling 12M Vol (%)',
            'monthly_change_pct': 'Monthly Change (%)'
        }))
    except Exception as e:
        print(f"âœ— ERROR initializing recent module: {e}")
        return 1
    
    # Test recent regime
    print("\n[TEST 1.1] Recent Regime Module Initialization")
    print("-"*90)
    try:
        print(f"  âœ“ Mean rate: {module_recent.mean_rate:.4f}")
        print(f"  âœ“ Std deviation: {module_recent.std_rate:.4f}")
        print(f"  âœ“ Autocorr (lag-1): {module_recent.autocorr_lag1:.4f}")
        print("  RESULT: âœ“ PASS")
    except Exception as e:
        print(f"  âœ— FAIL: {e}")
        return 1
    
    print("\n[TEST 1.2] Recent Regime - Scenario Generation & Coverage")
    print("-"*90)
    try:
        recent_scenarios = module_recent.generate_fx_scenarios(305.0, 60)
        recent_results = {}
        print("  Coverage Ratios (Recent Regime - 2016-2025):")
        for name, path in recent_scenarios.items():
            result = module_recent.assess_revenue_debt_mismatch(40_000_000, 2_400_000_000, 305.0, path)
            recent_results[name] = result
            status = "âœ“ VIABLE" if result['mean_coverage_ratio'] >= 1.5 else "âœ— RISK"
            print(f"    {name:.<28} {result['mean_coverage_ratio']:>6.2f}x [{status}]")
        print("  RESULT: âœ“ PASS")
    except Exception as e:
        print(f"  âœ— FAIL: {e}")
        return 1
    
    # ========================================================================
    # REGIME 2: HISTORICAL (Tail-Risk Overlay)
    # ========================================================================
    print("\n" + "â–ˆ"*90)
    print("REGIME 2: HISTORICAL TAIL-RISK ANALYSIS (1975-2025)")
    print("Overlay for extreme scenario calibration")
    print("â–ˆ"*90)
    
    print(f"\nâœ“ Historical regime data:")
    print(f"  Total records: {len(historical_df)} months")
    print(f"  Date range: {historical_df['Year-Month'].min().strftime('%Y-%m')} to {historical_df['Year-Month'].max().strftime('%Y-%m')}")
    print(f"  Coverage: {(historical_df['Year-Month'].max() - historical_df['Year-Month'].min()).days / 365.25:.1f} years")
    print(f"  FX range: {historical_df['avg_rate'].min():.2f} - {historical_df['avg_rate'].max():.2f} LKR/USD")
    print(f"  Mean rate: {historical_df['avg_rate'].mean():.2f}")
    print(f"  Mean volatility: {historical_df['rolling_12m_vol_pct'].mean():.2f}%")
    
    # Initialize module with historical data
    try:
        module_historical = FXCorrelationModule(historical_df.rename(columns={
            'avg_rate': 'Avg FX Rate',
            'rolling_12m_vol_pct': 'Rolling 12M Vol (%)',
            'monthly_change_pct': 'Monthly Change (%)'
        }))
    except Exception as e:
        print(f"âœ— ERROR initializing historical module: {e}")
        return 1
    
    print("\n[TEST 2.1] Historical Regime Module Initialization")
    print("-"*90)
    try:
        print(f"  âœ“ Mean rate: {module_historical.mean_rate:.4f}")
        print(f"  âœ“ Std deviation: {module_historical.std_rate:.4f}")
        print(f"  âœ“ Autocorr (lag-1): {module_historical.autocorr_lag1:.4f}")
        print(f"  âœ“ Min rate: {module_historical.min_rate:.4f} (Historical extreme)")
        print(f"  âœ“ Max rate: {module_historical.max_rate:.4f} (Historical extreme)")
        print("  RESULT: âœ“ PASS")
    except Exception as e:
        print(f"  âœ— FAIL: {e}")
        return 1
    
    print("\n[TEST 2.2] Historical Regime - Extreme Scenario Analysis")
    print("-"*90)
    try:
        historical_scenarios = module_historical.generate_fx_scenarios(305.0, 60)
        historical_results = {}
        print("  Coverage Ratios (Historical Tail-Risk - 1975-2025):")
        for name, path in historical_scenarios.items():
            result = module_historical.assess_revenue_debt_mismatch(40_000_000, 2_400_000_000, 305.0, path)
            historical_results[name] = result
            status = "âœ“ VIABLE" if result['mean_coverage_ratio'] >= 1.5 else "âœ— RISK"
            print(f"    {name:.<28} {result['mean_coverage_ratio']:>6.2f}x [{status}]")
        print("  RESULT: âœ“ PASS")
    except Exception as e:
        print(f"  âœ— FAIL: {e}")
        return 1
    
    # ========================================================================
    # COMPARATIVE ANALYSIS
    # ========================================================================
    print("\n" + "â–ˆ"*90)
    print("COMPARATIVE ANALYSIS: Recent vs Historical")
    print("â–ˆ"*90)
    
    print("\n[TEST 3] Regime Comparison")
    print("-"*90)
    
    # Statistics comparison
    print("\nStatistical Comparison:")
    print(f"  {'Metric':<30} {'Recent':<15} {'Historical':<15} {'Difference':<15}")
    print(f"  {'-'*70}")
    print(f"  {'Mean FX Rate':<30} {module_recent.mean_rate:>13.2f} {module_historical.mean_rate:>13.2f} {module_historical.mean_rate - module_recent.mean_rate:>13.2f}")
    print(f"  {'Std Deviation':<30} {module_recent.std_rate:>13.4f} {module_historical.std_rate:>13.4f} {module_historical.std_rate - module_recent.std_rate:>13.4f}")
    print(f"  {'Autocorr (lag-1)':<30} {module_recent.autocorr_lag1:>13.4f} {module_historical.autocorr_lag1:>13.4f} {module_historical.autocorr_lag1 - module_recent.autocorr_lag1:>13.4f}")
    print(f"  {'Max Rate':<30} {module_recent.max_rate:>13.2f} {module_historical.max_rate:>13.2f} {module_historical.max_rate - module_recent.max_rate:>13.2f}")
    
    # Base case comparison
    print("\nBase Case Coverage Comparison:")
    recent_base = recent_results['base_case']['mean_coverage_ratio']
    historical_base = historical_results['base_case']['mean_coverage_ratio']
    print(f"  Recent (2016-2025): {recent_base:.2f}x")
    print(f"  Historical (1975-2025): {historical_base:.2f}x")
    print(f"  Difference: {recent_base - historical_base:.2f}x")
    print(f"  Interpretation: Historical scenarios show {abs(historical_base - recent_base):.1%} {'lower' if historical_base < recent_base else 'higher'} coverage")
    
    print("\n  RECOMMENDATION FOR LENDERS:")
    print(f"  - Optimistic case: Use Recent {recent_base:.2f}x")
    print(f"  - Conservative case: Use Historical {historical_base:.2f}x")
    print(f"  - Suggested assumption: {min(recent_base, historical_base):.2f}x (conservative)")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*90)
    print("âœ“âœ“âœ“ DUAL REGIME ANALYSIS COMPLETE âœ“âœ“âœ“")
    print("="*90)
    
    print(f"""
SUMMARY:
â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”

RECENT REGIME (2016-2025):
  â€¢ Dataset: {len(recent_df)} months of recent history
  â€¢ Primary use: Lender presentation, current dynamics
  â€¢ Coverage: {recent_base:.2f}x (base case)
  â€¢ Volatility: {recent_df['rolling_12m_vol_pct'].mean():.2f}%

HISTORICAL TAIL-RISK (1975-2025):
  â€¢ Dataset: {len(historical_df)} months spanning {(historical_df['Year-Month'].max() - historical_df['Year-Month'].min()).days / 365.25:.1f} years
  â€¢ Primary use: Stress testing, extreme scenarios
  â€¢ Coverage: {historical_base:.2f}x (base case)
  â€¢ Volatility: {historical_df['rolling_12m_vol_pct'].mean():.2f}%

KEY FINDINGS:
  âœ“ Recent regime is {('more' if recent_base > historical_base else 'less')} conservative
  âœ“ Historical data reveals {('higher' if historical_base > recent_base else 'lower')} tail risks
  âœ“ Combined analysis: Use both for comprehensive risk assessment

LENDER RECOMMENDATION:
  â€¢ Primary Model: Recent regime ({recent_base:.2f}x coverage)
  â€¢ Stress Test: Historical overlay ({historical_base:.2f}x coverage)
  â€¢ Conservative Assumption: {min(recent_base, historical_base):.2f}x

Next Steps:
  1. Present recent regime to lenders (mainstream scenario)
  2. Show historical analysis as validation/stress test
  3. Use conservative {min(recent_base, historical_base):.2f}x for debt covenants
  4. Demonstrate professional risk management with dual analysis
""")
    
    return 0

if __name__ == '__main__':
    exit(main())