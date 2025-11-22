"""
Risk Metrics Module for DutchBay V13 - Tail Risk Analytics (VaR/CVaR)
P0-2B Implementation

Computes Value-at-Risk (VaR), Conditional Value-at-Risk (CVaR), percentile analysis,
and tail risk metrics from Monte Carlo simulation results.

Author: DutchBay V13 Team, Nov 2025
Version: 1.0
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, List, Tuple, Any, Optional

logger = logging.getLogger('dutchbay.finance.risk_metrics')

class TailRiskAnalyzer:
    """
    Comprehensive tail risk analysis for renewable energy project finance.
    
    Computes VaR, CVaR, downside deviation, and covenant breach probabilities
    from Monte Carlo simulation results.
    """
    
    def __init__(self, confidence_level: float = 0.95):
        """
        Initialize risk analyzer.
        
        Parameters
        ----------
        confidence_level : float, default 0.95
            Confidence level for VaR/CVaR (e.g., 0.95 = 95% confidence)
        """
        self.confidence_level = confidence_level
        self.var_index = int((1 - confidence_level) * 100)  # Percentile index
    
    def calculate_var_cvar(
        self, 
        returns: np.ndarray, 
        return_type: str = 'equity_irr'
    ) -> Dict[str, float]:
        """
        Calculate Value-at-Risk (VaR) and Conditional Value-at-Risk (CVaR).
        
        VaR(95%) = worst outcome at 95% confidence (5th percentile)
        CVaR(95%) = average of outcomes worse than VaR (expected shortfall)
        
        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes from Monte Carlo (e.g., IRR or NPV values)
        return_type : str
            Type of return for labeling ('equity_irr', 'project_npv', etc.)
        
        Returns
        -------
        dict
            {
                'var': float,
                'cvar': float,
                'var_label': str,
                'cvar_label': str
            }
        """
        sorted_returns = np.sort(returns)
        var_index = int((1 - self.confidence_level) * len(returns))
        
        var = sorted_returns[var_index]
        cvar = sorted_returns[:var_index].mean()
        
        return {
            'var': var,
            'cvar': cvar,
            'var_label': f"VaR({int(self.confidence_level*100)}%)",
            'cvar_label': f"CVaR({int(self.confidence_level*100)}%)",
            'return_type': return_type,
            'confidence': self.confidence_level
        }
    
    def percentile_analysis(
        self, 
        returns: np.ndarray, 
        percentiles: List[int] = [10, 25, 50, 75, 90]
    ) -> Dict[str, float]:
        """
        Calculate percentile distribution of returns.
        
        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes from Monte Carlo
        percentiles : list of int
            Percentiles to calculate (default: [10, 25, 50, 75, 90])
        
        Returns
        -------
        dict
            {p: value for p in percentiles, ...}
        """
        result = {}
        for p in percentiles:
            result[f'p{p}'] = np.percentile(returns, p)
        return result
    
    def downside_risk(
        self, 
        returns: np.ndarray, 
        target_return: float = 0.0
    ) -> Dict[str, float]:
        """
        Calculate downside risk metrics below a target return.
        
        Downside Deviation = std dev of returns below target
        Sortino Ratio = (mean - target) / downside_deviation
        
        Parameters
        ----------
        returns : np.ndarray
            Array of outcomes
        target_return : float, default 0.0
            Target return threshold
        
        Returns
        -------
        dict
            {
                'downside_deviation': float,
                'sortino_ratio': float,
                'returns_below_target': int,
                'probability_below_target': float
            }
        """
        downside_returns = returns[returns < target_return]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        
        mean_return = returns.mean()
        sortino = (mean_return - target_return) / downside_std if downside_std > 0 else np.inf
        
        return {
            'downside_deviation': downside_std,
            'sortino_ratio': sortino,
            'returns_below_target': len(downside_returns),
            'probability_below_target': len(downside_returns) / len(returns),
            'target_return': target_return
        }
    
    def covenant_breach_probability(
        self,
        metric_series: List[np.ndarray],
        min_thresholds: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Calculate probability of covenant breach (DSCR, LLCR, PLCR minimum).
        
        Parameters
        ----------
        metric_series : list of np.ndarray
            List of arrays: [dscr_results, llcr_results, plcr_results]
            Each with shape (n_scenarios, n_years)
        min_thresholds : dict
            {
                'min_dscr': 1.20,
                'min_llcr': 1.25,
                'min_plcr': 1.40
            }
        
        Returns
        -------
        dict
            Breach probabilities and severity analysis
        """
        dscr_arr, llcr_arr, plcr_arr = metric_series
        n_scenarios = dscr_arr.shape[0]
        
        # Find minimum of each metric across all years (per scenario)
        dscr_min = np.min(dscr_arr, axis=1)
        llcr_min = np.min(llcr_arr, axis=1)
        plcr_min = np.min(plcr_arr, axis=1)
        
        # Probability of breach
        dscr_breach = (dscr_min < min_thresholds['min_dscr']).sum() / n_scenarios
        llcr_breach = (llcr_min < min_thresholds['min_llcr']).sum() / n_scenarios
        plcr_breach = (plcr_min < min_thresholds['min_plcr']).sum() / n_scenarios
        
        return {
            'dscr_breach_probability': dscr_breach,
            'llcr_breach_probability': llcr_breach,
            'plcr_breach_probability': plcr_breach,
            'dscr_min_scenarios': dscr_min,
            'llcr_min_scenarios': llcr_min,
            'plcr_min_scenarios': plcr_min,
            'thresholds': min_thresholds
        }
    
    def tail_risk_report(
        self,
        equity_irr: np.ndarray,
        project_irr: np.ndarray,
        equity_npv: np.ndarray,
        project_npv: np.ndarray,
        covenant_results: Dict[str, Any],
        target_equity_irr: float = 0.12
    ) -> Dict[str, Any]:
        """
        Generate comprehensive tail risk report for equity/lender review.
        
        Parameters
        ----------
        equity_irr : np.ndarray
            Monte Carlo equity IRR results
        project_irr : np.ndarray
            Monte Carlo project IRR results
        equity_npv : np.ndarray
            Monte Carlo equity NPV results
        project_npv : np.ndarray
            Monte Carlo project NPV results
        covenant_results : dict
            From covenant_breach_probability()
        target_equity_irr : float
            Equity investor hurdle rate
        
        Returns
        -------
        dict
            Complete risk report for executive/lender presentation
        """
        equity_irr_var_cvar = self.calculate_var_cvar(equity_irr, 'equity_irr')
        equity_irr_percentiles = self.percentile_analysis(equity_irr)
        equity_irr_downside = self.downside_risk(equity_irr, target_equity_irr)
        
        project_irr_var_cvar = self.calculate_var_cvar(project_irr, 'project_irr')
        project_irr_percentiles = self.percentile_analysis(project_irr)
        
        report = {
            'equity_irr': {
                'mean': equity_irr.mean(),
                'std': equity_irr.std(),
                'min': equity_irr.min(),
                'max': equity_irr.max(),
                'var_cvar': equity_irr_var_cvar,
                'percentiles': equity_irr_percentiles,
                'downside': equity_irr_downside,
                'probability_below_hurdle': (equity_irr < target_equity_irr).sum() / len(equity_irr)
            },
            'project_irr': {
                'mean': project_irr.mean(),
                'std': project_irr.std(),
                'min': project_irr.min(),
                'max': project_irr.max(),
                'var_cvar': project_irr_var_cvar,
                'percentiles': project_irr_percentiles
            },
            'equity_npv': {
                'mean': equity_npv.mean(),
                'std': equity_npv.std(),
                'min': equity_npv.min(),
                'max': equity_npv.max(),
                'var_cvar': self.calculate_var_cvar(equity_npv, 'equity_npv')
            },
            'project_npv': {
                'mean': project_npv.mean(),
                'std': project_npv.std(),
                'min': project_npv.min(),
                'max': project_npv.max(),
                'var_cvar': self.calculate_var_cvar(project_npv, 'project_npv')
            },
            'covenant_breaches': covenant_results
        }
        
        return report
    
    def to_dataframe(self, report: Dict[str, Any]) -> pd.DataFrame:
        """Convert tail risk report to summary dataframe."""
        summary = []
        
        for metric_name in ['equity_irr', 'project_irr', 'equity_npv', 'project_npv']:
            metric_data = report[metric_name]
            summary.append({
                'metric': metric_name,
                'mean': metric_data['mean'],
                'std': metric_data['std'],
                'min': metric_data['min'],
                'max': metric_data['max'],
                'var': metric_data['var_cvar']['var'],
                'cvar': metric_data['var_cvar']['cvar']
            })
        
        return pd.DataFrame(summary)
