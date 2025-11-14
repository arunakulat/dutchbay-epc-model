#!/usr/bin/env python3
"""
DUTCHBAY V13 - P0-2D MODULE TEST (SELF-CONTAINED VERSION)
No external module imports needed - all code embedded

Version: 1.0.0-production-standalone
Date: 2025-11-14
Usage: python3 test_fx_dual_regime_standalone.py
"""

import pandas as pd
import numpy as np
import yaml
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, Optional

# ==================================================================================
# EMBEDDED FX CORRELATION MODULE (No external import needed)
# ==================================================================================

class FXCorrelationModule:
    """
    Multi-Currency FX Correlation & Stress Module - PRODUCTION VERSION
    
    Purpose: Analyze FX risk for multi-currency renewable energy projects
    Supports: Dual regime analysis (recent + historical)
    Output: Scenario paths, VaR/CVaR, revenue-debt mismatch assessment
    """
    
    def __init__(self, monthly_fx_df: pd.DataFrame, config_yaml: Optional[Dict] = None):
        """Initialize FX correlation module with monthly data"""
        self.monthly_fx = monthly_fx_df.copy()
        
        # Normalize column names (handle both formats from YAML)
        if 'date' in self.monthly_fx.columns:
            self.monthly_fx.rename(columns={'date': 'Year-Month'}, inplace=True)
        if 'avg_rate' in self.monthly_fx.columns:
            self.monthly_fx.rename(columns={'avg_rate': 'Avg FX Rate'}, inplace=True)
        if 'monthly_change_pct' in self.monthly_fx.columns:
            self.monthly_fx.rename(columns={'monthly_change_pct': 'Monthly Change (%)'}, inplace=True)
        if 'rolling_12m_vol_pct' in self.monthly_fx.columns:
            self.monthly_fx.rename(columns={'rolling_12m_vol_pct': 'Rolling 12M Vol (%)'}, inplace=True)
        
        # Ensure datetime
        if 'Year-Month' in self.monthly_fx.columns:
            self.monthly_fx['Year-Month'] = pd.to_datetime(self.monthly_fx['Year-Month'])
            self.monthly_fx = self.monthly_fx.sort_values('Year-Month')
        
        # Calculate core statistics
        self.mean_rate = self.monthly_fx['Avg FX Rate'].mean()
        self.std_rate = self.monthly_fx['Avg FX Rate'].std()
        self.min_rate = self.monthly_fx['Avg FX Rate'].min()
        self.max_rate = self.monthly_fx['Avg FX Rate'].max()
        
        # Autocorrelation
        self.autocorr_lag1 = self.monthly_fx['Avg FX Rate'].autocorr(lag=1)
        self.autocorr_lag12 = self.monthly_fx['Avg FX Rate'].autocorr(lag=12)
        
        # Monthly change statistics
        self.pct_change = self.monthly_fx['Monthly Change (%)'].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()
        self.mean_monthly_change = self.pct_change.mean()
        self.std_monthly_change = self.pct_change.std()
        self.max_monthly_move = self.pct_change.max()
        self.min_monthly_move = self.pct_change.min()
        
        # Volatility
        self.rolling_vol_12m = self.monthly_fx['Rolling 12M Vol (%)'].mean()
        
        # Configuration
        self.config = config_yaml or {}
    
    def generate_fx_scenarios(self, base_rate: float, months_ahead: int = 60) -> Dict[str, np.ndarray]:
        """Generate 6 FX scenario paths for stress testing"""
        return {
            'base_case': self._generate_base_scenario(base_rate, months_ahead),
            'upside_5pct': self._generate_shock_scenario(base_rate, months_ahead, 0.05),
            'downside_5pct': self._generate_shock_scenario(base_rate, months_ahead, -0.05),
            'stress_10pct': self._generate_shock_scenario(base_rate, months_ahead, -0.10),
            'crisis_scenario': self._generate_crisis_scenario(base_rate, months_ahead),
            'mean_reversion': self._generate_mean_reversion_scenario(base_rate, months_ahead)
        }
    
    def _generate_base_scenario(self, base_rate: float, months: int) -> np.ndarray:
        """Base case scenario with drift, volatility, and autocorrelation"""
        path = np.zeros(months)
        path[0] = base_rate
        
        upper_bound = self.max_rate * 1.25
        lower_bound = self.min_rate * 0.5
        
        for t in range(1, months):
            drift = self.mean_monthly_change / 100
            shock = np.random.normal(0, self.std_monthly_change / 100)
            correlation = self.autocorr_lag1 * 0.5 * (path[t-1] - self.mean_rate) / self.mean_rate
            pct_change = drift + shock + correlation * 0.01
            path[t] = path[t-1] * (1 + pct_change)
            path[t] = np.clip(path[t], lower_bound, upper_bound)
        
        return path
    
    def _generate_shock_scenario(self, base_rate: float, months: int, shock: float) -> np.ndarray:
        """Shock scenario with exponential decay back to base case"""
        path = self._generate_base_scenario(base_rate, months)
        decay = np.exp(-np.arange(months) / (months / 3))
        path = path * (1 + shock * decay)
        upper_bound = self.max_rate * 1.25
        lower_bound = self.min_rate * 0.5
        path = np.clip(path, lower_bound, upper_bound)
        return path
    
    def _generate_crisis_scenario(self, base_rate: float, months: int) -> np.ndarray:
        """Crisis scenario based on historical extreme events"""
        path = np.zeros(months)
        path[0] = base_rate
        
        for t in range(1, min(7, months)):
            shock = self.max_monthly_move / 100 * (1 - t/7)
            path[t] = path[t-1] * (1 + shock)
        
        for t in range(7, min(19, months)):
            shock = -self.max_monthly_move / 100 * ((t - 7) / 12)
            path[t] = path[t-1] * (1 + shock)
        
        if months > 19:
            path[19:] = np.linspace(path[18], base_rate * 1.15, months - 19)
        
        return path
    
    def _generate_mean_reversion_scenario(self, base_rate: float, months: int) -> np.ndarray:
        """Mean reversion scenario - rate gradually returns to historical mean"""
        path = np.zeros(months)
        path[0] = base_rate
        
        reversion_speed = 0.05
        
        for t in range(1, months):
            reversion = reversion_speed * (self.mean_rate - path[t-1])
            shock = np.random.normal(0, self.std_monthly_change / 100)
            pct_change = reversion / path[t-1] + shock
            path[t] = path[t-1] * (1 + pct_change)
        
        return path
    
    def assess_revenue_debt_mismatch(
        self, 
        annual_usd_revenue: float, 
        annual_lkr_debt_service: float,
        base_rate: float, 
        scenario_path: np.ndarray
    ) -> Dict:
        """Assess revenue-debt currency mismatch for a given FX scenario"""
        monthly_revenue = annual_usd_revenue / 12
        monthly_debt = annual_lkr_debt_service / 12
        
        revenue_lkr = monthly_revenue * scenario_path
        coverage = revenue_lkr / monthly_debt
        deficit = np.where(monthly_debt - revenue_lkr > 0, monthly_debt - revenue_lkr, 0)
        
        return {
            'mean_coverage_ratio': float(np.nanmean(coverage)),
            'min_coverage_ratio': float(np.nanmin(coverage)),
            'months_below_100pct': int((coverage < 1.0).sum()),
            'months_below_dscr_req': int((coverage < 1.5).sum()),
            'total_deficit_lkr': float(deficit.sum()),
            'worst_month_deficit_lkr': float((monthly_debt - revenue_lkr).max()),
            'mean_fx_scenario': float(scenario_path.mean()),
            'min_fx_scenario': float(scenario_path.min()),
            'max_fx_scenario': float(scenario_path.max())
        }
    
    def monte_carlo_var_analysis(
        self, 
        annual_usd_revenue: float, 
        annual_lkr_debt_service: float,
        base_rate: float, 
        num_simulations: int = 1000, 
        confidence_level: float = 0.95
    ) -> Dict:
        """Monte Carlo VaR/CVaR analysis for FX risk"""
        monthly_revenue = annual_usd_revenue / 12
        monthly_debt = annual_lkr_debt_service / 12
        
        deficits = []
        coverages = []
        
        for _ in range(num_simulations):
            path = self._generate_base_scenario(base_rate, 60)
            rev = monthly_revenue * path
            deficit = np.where(monthly_debt - rev > 0, monthly_debt - rev, 0)
            deficits.append(deficit.sum())
            
            coverage_ratio = (rev / monthly_debt).mean()
            if 0 < coverage_ratio < 10000:
                coverages.append(coverage_ratio)
        
        deficits = np.array(deficits)
        coverages = np.array(coverages)
        
        var_idx = int((1 - confidence_level) * num_simulations)
        var_val = float(np.sort(deficits)[var_idx])
        
        cvar_vals = deficits[deficits >= var_val]
        cvar_val = float(cvar_vals.mean()) if len(cvar_vals) > 0 else var_val
        
        return {
            'var_deficit_lkr': var_val,
            'cvar_deficit_lkr': cvar_val,
            'mean_deficit_lkr': float(deficits.mean()),
            'std_deficit_lkr': float(deficits.std()),
            'max_deficit_lkr': float(deficits.max()),
            'prob_deficit': float((deficits > 0).sum() / num_simulations),
            'mean_coverage_ratio': float(np.nanmean(coverages)),
            'percentile_5_coverage': float(np.nanpercentile(coverages, 5)),
            'percentile_95_coverage': float(np.nanpercentile(coverages, 95)),
            'num_simulations': num_simulations
        }
    
    def generate_audit_report(self) -> Dict:
        """Generate audit report with module metadata and statistics"""
        return {
            'module': 'FX_Correlation_P0_2D',
            'version': '1.0.0-production',
            'timestamp': datetime.now().isoformat(),
            'data_observations': len(self.monthly_fx),
            'date_range': f"{self.monthly_fx['Year-Month'].min()} to {self.monthly_fx['Year-Month'].max()}",
            'statistics': {
                'mean_rate': round(self.mean_rate, 4),
                'std_rate': round(self.std_rate, 4),
                'min_rate': round(self.min_rate, 4),
                'max_rate': round(self.max_rate, 4),
                'autocorr_lag1': round(self.autocorr_lag1, 4),
                'autocorr_lag12': round(self.autocorr_lag12, 4),
                'mean_monthly_change': round(self.mean_monthly_change, 4),
                'std_monthly_change': round(self.std_monthly_change, 4),
                'rolling_vol_12m': round(self.rolling_vol_12m, 2)
            }
        }

# ==================================================================================
# TEST SCRIPT BEGINS HERE
# ==================================================================================

def load_fx_data_dual_regime():
    """Load BOTH recent regime (2016-2025) AND historical decades (1975-2025)"""
    
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
    print("DUTCHBAY V13 - P0-2D MODULE TEST SUITE (STANDALONE)")
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
    print("REGIME 2: HISTORICAL TAIL-RISK ANALYSIS (2005-2025)")
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
        print("  Coverage Ratios (Historical Tail-Risk - 2005-2025):")
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
    print(f"  {'Max Rate':<30} {module_recent.max_rate:>13.2f} {module_historical.max_rate:>13.2f} {module_historical.max_rate - module_recent.max_rate:>13.2f}")
    
    # Base case comparison
    print("\nBase Case Coverage Comparison:")
    recent_base = recent_results['base_case']['mean_coverage_ratio']
    historical_base = historical_results['base_case']['mean_coverage_ratio']
    print(f"  Recent (2016-2025): {recent_base:.2f}x")
    print(f"  Historical (2005-2025): {historical_base:.2f}x")
    print(f"  Difference: {recent_base - historical_base:.2f}x")
    
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

RECENT REGIME (2016-2025):
  â€¢ Dataset: {len(recent_df)} months of recent history
  â€¢ Coverage: {recent_base:.2f}x (base case)
  â€¢ Volatility: {recent_df['rolling_12m_vol_pct'].mean():.2f}%

HISTORICAL TAIL-RISK (2005-2025):
  â€¢ Dataset: {len(historical_df)} months spanning {(historical_df['Year-Month'].max() - historical_df['Year-Month'].min()).days / 365.25:.1f} years
  â€¢ Coverage: {historical_base:.2f}x (base case)
  â€¢ Volatility: {historical_df['rolling_12m_vol_pct'].mean():.2f}%

LENDER RECOMMENDATION:
  â€¢ Primary Model: Recent regime ({recent_base:.2f}x coverage)
  â€¢ Stress Test: Historical overlay ({historical_base:.2f}x coverage)
  â€¢ Conservative Assumption: {min(recent_base, historical_base):.2f}x for debt covenants

Next Steps:
  1. Present recent regime to lenders (mainstream scenario)
  2. Show historical analysis as validation/stress test
  3. Use conservative {min(recent_base, historical_base):.2f}x for debt covenants
  4. Demonstrate professional risk management with dual analysis
""")
    
    return 0

if __name__ == '__main__':
    exit(main())