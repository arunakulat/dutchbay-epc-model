#!/usr/bin/env python3
"""
DUTCHBAY V13 - FX CORRELATION MODULE (CORRECTED)
Currency Risk Analysis with USD Debt Paydown Optimization

CORRECTED LOGIC:
  âœ“ Revenue: Fixed in LKR (not USD)
  âœ“ Debt: Mixed LKR + USD components
  âœ“ DSCR = LKR Revenue / [LKR Debt + (USD Debt Ã— FX)]
  âœ“ FX correlation: NEGATIVE (weaker LKR = worse DSCR)
  âœ“ Strategy: Accelerated USD debt paydown reduces FX exposure

SAVE TO:
/Users/aruna/Desktop/DutchBay_EPC_Extracted/DutchBay_EPC_Model/fx_correlation_module_corrected.py

Version: 2.0.0-corrected
Date: 2025-11-14
Author: DutchBay EPC Team
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')


class FXCorrelationModuleCorrected:
    """
    CORRECTED FX Correlation Module with USD Debt Paydown Optimization
    
    Correct Model:
      DSCR = LKR Revenue / [LKR Debt + (USD Debt Ã— FX)]
      
    Features:
      â€¢ Fixed LKR tariff revenue
      â€¢ Mixed currency debt structure
      â€¢ Negative FX correlation (correct)
      â€¢ USD debt paydown scheduling
      â€¢ Sensitivity and scenario analysis
      â€¢ Monte Carlo optimization
    """
    
    def __init__(self, 
                 monthly_fx_df: pd.DataFrame,
                 annual_lkr_revenue: float,
                 annual_lkr_debt: float,
                 annual_usd_debt: float,
                 base_fx_rate: float = 305.0):
        """
        Initialize corrected FX correlation module
        
        Args:
            monthly_fx_df: DataFrame with FX rate history
            annual_lkr_revenue: Fixed annual revenue in LKR (from fixed tariff)
            annual_lkr_debt: Annual LKR debt service (fixed)
            annual_usd_debt: Annual USD debt service (fixed, in USD)
            base_fx_rate: Current/baseline FX rate for initial calculation
        """
        self.monthly_fx = monthly_fx_df.copy()
        
        # Ensure datetime and sorted
        if 'Year-Month' in self.monthly_fx.columns:
            self.monthly_fx['Year-Month'] = pd.to_datetime(self.monthly_fx['Year-Month'])
            self.monthly_fx = self.monthly_fx.sort_values('Year-Month')
        
        # Financial structure (CORRECT)
        self.annual_lkr_revenue = annual_lkr_revenue
        self.annual_lkr_debt = annual_lkr_debt
        self.annual_usd_debt_origination = annual_usd_debt
        self.base_fx_rate = base_fx_rate
        
        # Calculate current ratios
        total_debt_usd_equiv = (annual_lkr_debt / base_fx_rate) + annual_usd_debt
        self.usd_debt_ratio = annual_usd_debt / total_debt_usd_equiv
        self.lkr_debt_ratio = (annual_lkr_debt / base_fx_rate) / total_debt_usd_equiv
        
        # FX statistics
        if 'avg_rate' in self.monthly_fx.columns:
            fx_col = 'avg_rate'
        elif 'Avg FX Rate' in self.monthly_fx.columns:
            fx_col = 'Avg FX Rate'
        else:
            fx_col = self.monthly_fx.columns[1]
        
        self.mean_fx = self.monthly_fx[fx_col].mean()
        self.std_fx = self.monthly_fx[fx_col].std()
        self.min_fx = self.monthly_fx[fx_col].min()
        self.max_fx = self.monthly_fx[fx_col].max()
        self.autocorr_lag1 = self.monthly_fx[fx_col].autocorr(lag=1)
        
        # For scenarios
        self.fx_column = fx_col
    
    def calculate_dscr(self, 
                      annual_lkr_revenue: float,
                      annual_lkr_debt: float,
                      annual_usd_debt: float,
                      fx_rate: float) -> float:
        """
        CORRECTED DSCR Calculation
        
        DSCR = LKR Revenue / [LKR Debt + (USD Debt Ã— FX)]
        
        Args:
            annual_lkr_revenue: Annual revenue in LKR
            annual_lkr_debt: Annual debt service in LKR
            annual_usd_debt: Annual debt service in USD
            fx_rate: Current FX rate (LKR/USD)
        
        Returns:
            DSCR ratio
        """
        # Convert USD debt to LKR
        usd_debt_in_lkr = annual_usd_debt * fx_rate
        
        # Total debt service in LKR
        total_debt_lkr = annual_lkr_debt + usd_debt_in_lkr
        
        # DSCR
        if total_debt_lkr == 0:
            return np.nan
        
        dscr = annual_lkr_revenue / total_debt_lkr
        return dscr
    
    def fx_sensitivity_analysis(self, 
                               fx_range_pct: List[float] = None) -> Dict:
        """
        Sensitivity analysis: How DSCR changes with FX movements
        
        Shows NEGATIVE correlation (as correct)
        
        Args:
            fx_range_pct: List of FX change percentages to test
                         Default: [-30, -20, -10, -5, 0, 5, 10, 20, 30]
        
        Returns:
            Dictionary with sensitivity results
        """
        if fx_range_pct is None:
            fx_range_pct = [-30, -20, -10, -5, 0, 5, 10, 20, 30]
        
        results = {}
        base_dscr = self.calculate_dscr(
            self.annual_lkr_revenue,
            self.annual_lkr_debt,
            self.annual_usd_debt_origination,
            self.base_fx_rate
        )
        
        for pct_change in fx_range_pct:
            fx_rate = self.base_fx_rate * (1 + pct_change / 100)
            dscr = self.calculate_dscr(
                self.annual_lkr_revenue,
                self.annual_lkr_debt,
                self.annual_usd_debt_origination,
                fx_rate
            )
            
            dscr_change_pct = ((dscr - base_dscr) / base_dscr * 100) if base_dscr != 0 else 0
            
            results[f"{pct_change:+d}%"] = {
                'fx_rate': fx_rate,
                'dscr': dscr,
                'dscr_change_pct': dscr_change_pct
            }
        
        return {
            'base_fx': self.base_fx_rate,
            'base_dscr': base_dscr,
            'sensitivity': results
        }
    
    def paydown_schedule_analysis(self,
                                 paydown_scenarios: Dict[str, float] = None,
                                 years: int = 15) -> Dict:
        """
        Analyze DSCR improvement with different USD debt paydown schedules
        
        Args:
            paydown_scenarios: Dict with scenario names and target USD debt % reduction
                             Default: {'Current': 0%, 'Target': 50%, 'Full': 100%}
            years: Number of years to project
        
        Returns:
            Dictionary with paydown analysis for each scenario
        """
        if paydown_scenarios is None:
            paydown_scenarios = {
                'Current (55% USD)': 0.00,
                'Phase 1 (25% USD)': 0.55,  # Reduce to 25% of original
                'Phase 2 (10% USD)': 0.82,  # Reduce to 10% of original
                'Full Payoff (0% USD)': 1.00  # Eliminate USD debt
            }
        
        results = {}
        
        for scenario_name, paydown_pct in paydown_scenarios.items():
            scenario_results = []
            
            for year in range(1, years + 1):
                # Linear paydown schedule
                usd_debt_remaining = self.annual_usd_debt_origination * (1 - paydown_pct * (year / years))
                
                # DSCR at current FX
                dscr = self.calculate_dscr(
                    self.annual_lkr_revenue,
                    self.annual_lkr_debt,
                    usd_debt_remaining,
                    self.base_fx_rate
                )
                
                # USD debt ratio
                total_debt_usd = (self.annual_lkr_debt / self.base_fx_rate) + usd_debt_remaining
                usd_ratio = usd_debt_remaining / total_debt_usd if total_debt_usd > 0 else 0
                
                scenario_results.append({
                    'year': year,
                    'usd_debt': usd_debt_remaining,
                    'usd_ratio_pct': usd_ratio * 100,
                    'dscr': dscr
                })
            
            results[scenario_name] = scenario_results
        
        return results
    
    def stress_test_paydown_scenarios(self,
                                     paydown_scenarios: Dict[str, float] = None,
                                     fx_shocks: List[float] = None) -> Dict:
        """
        Stress test different paydown scenarios against FX shocks
        
        Args:
            paydown_scenarios: USD debt paydown targets (% reduction)
            fx_shocks: List of FX rate levels to test
                      Default: [220, 250, 305, 350, 365, 396]  (includes 2022 crisis)
        
        Returns:
            DSCR under each combination of paydown scenario + FX shock
        """
        if paydown_scenarios is None:
            paydown_scenarios = {
                'Current (55% USD)': 0.00,
                'Phase 1 (25% USD)': 0.55,
                'Phase 2 (10% USD)': 0.82,
                'Full Payoff (0% USD)': 1.00
            }
        
        if fx_shocks is None:
            fx_shocks = [220, 250, 305, 350, 365, 396]
        
        results = {}
        
        for scenario_name, paydown_pct in paydown_scenarios.items():
            usd_debt = self.annual_usd_debt_origination * (1 - paydown_pct)
            
            fx_results = {}
            for fx_rate in fx_shocks:
                dscr = self.calculate_dscr(
                    self.annual_lkr_revenue,
                    self.annual_lkr_debt,
                    usd_debt,
                    fx_rate
                )
                
                # Interpret FX rate
                fx_description = self._interpret_fx_rate(fx_rate)
                
                fx_results[f"{fx_rate} ({fx_description})"] = {
                    'fx_rate': fx_rate,
                    'dscr': dscr,
                    'viable': dscr >= 1.0
                }
            
            results[scenario_name] = fx_results
        
        return results
    
    def monte_carlo_paydown_optimization(self,
                                        fx_scenarios: int = 1000,
                                        years_ahead: int = 15,
                                        target_dscr: float = 1.25) -> Dict:
        """
        Monte Carlo optimization: Find optimal USD debt paydown schedule
        
        Args:
            fx_scenarios: Number of FX paths to simulate
            years_ahead: Projection horizon
            target_dscr: Target DSCR to maintain
        
        Returns:
            Optimization results with recommended paydown path
        """
        results = {
            'scenarios_tested': fx_scenarios,
            'years_ahead': years_ahead,
            'target_dscr': target_dscr,
            'paydown_recommendations': {}
        }
        
        # Test different paydown speeds
        paydown_speeds = np.linspace(0, 1.0, 11)  # 0% to 100% over period
        
        for paydown_speed in paydown_speeds:
            breaches = 0
            min_dscr = 1.0
            
            for _ in range(fx_scenarios):
                # Generate FX path
                fx_path = self._generate_fx_path(years_ahead)
                
                # For each year, calculate DSCR with paydown
                for year, fx_rate in enumerate(fx_path, 1):
                    usd_debt = self.annual_usd_debt_origination * (1 - paydown_speed * (year / years_ahead))
                    
                    dscr = self.calculate_dscr(
                        self.annual_lkr_revenue,
                        self.annual_lkr_debt,
                        usd_debt,
                        fx_rate
                    )
                    
                    min_dscr = min(min_dscr, dscr)
                    
                    if dscr < 1.0:
                        breaches += 1
            
            breach_probability = breaches / (fx_scenarios * years_ahead)
            
            recommendation = "âœ“ Recommended" if breach_probability < 0.05 else ""
            
            results['paydown_recommendations'][f"{paydown_speed*100:.0f}% USD reduction"] = {
                'paydown_speed': paydown_speed,
                'breach_probability': breach_probability,
                'min_dscr_observed': min_dscr,
                'recommendation': recommendation
            }
        
        return results
    
    def _generate_fx_path(self, months: int) -> np.ndarray:
        """Generate FX path using historical properties"""
        path = np.zeros(months)
        path[0] = self.base_fx_rate
        
        for t in range(1, months):
            # Random walk with autocorrelation
            drift = (self.mean_fx - self.base_fx_rate) / (months * 12)  # Mean reversion
            shock = np.random.normal(0, self.std_fx / 100)
            correlation = self.autocorr_lag1 * (path[t-1] - self.base_fx_rate) / self.base_fx_rate
            
            pct_change = drift + shock + correlation * 0.01
            path[t] = path[t-1] * (1 + pct_change)
            
            # Bounds
            path[t] = np.clip(path[t], self.min_fx * 0.8, self.max_fx * 1.2)
        
        return path
    
    def _interpret_fx_rate(self, fx_rate: float) -> str:
        """Interpret FX rate description"""
        if fx_rate < 220:
            return "Strong LKR"
        elif fx_rate < 280:
            return "Pre-2022"
        elif fx_rate < 330:
            return "Current zone"
        elif fx_rate < 365:
            return "Weak/Crisis"
        else:
            return "Extreme (2022-like)"
    
    def generate_audit_report(self) -> Dict:
        """Generate audit report"""
        base_dscr = self.calculate_dscr(
            self.annual_lkr_revenue,
            self.annual_lkr_debt,
            self.annual_usd_debt_origination,
            self.base_fx_rate
        )
        
        return {
            'module': 'FX_Correlation_Corrected_P0_2D',
            'version': '2.0.0-corrected',
            'timestamp': datetime.now().isoformat(),
            'financial_structure': {
                'annual_lkr_revenue': self.annual_lkr_revenue,
                'annual_lkr_debt': self.annual_lkr_debt,
                'annual_usd_debt': self.annual_usd_debt_origination,
                'usd_debt_ratio': f"{self.usd_debt_ratio*100:.1f}%",
                'base_fx_rate': self.base_fx_rate,
                'base_dscr': round(base_dscr, 4)
            },
            'fx_statistics': {
                'mean_fx': round(self.mean_fx, 2),
                'std_fx': round(self.std_fx, 2),
                'min_fx': round(self.min_fx, 2),
                'max_fx': round(self.max_fx, 2),
                'autocorr_lag1': round(self.autocorr_lag1, 4)
            },
            'model_type': 'Negative FX correlation (correct)',
            'status': 'CORRECTED - Production Ready'
        }