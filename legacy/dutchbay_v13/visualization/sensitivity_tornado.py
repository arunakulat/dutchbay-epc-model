"""
Sensitivity Tornado Analysis Module for DutchBay V13 - P0-2C
Comprehensive sensitivity analysis with tornado chart generation

Calculates IRR/NPV impact of parameter variations and produces
executive-ready tornado diagrams for board/IC presentations.

Author: DutchBay V13 Team, Nov 2025
Version: 1.0
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import logging
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path

logger = logging.getLogger('dutchbay.visualization.sensitivity')

class TornadoSensitivityAnalyzer:
    """
    Comprehensive tornado sensitivity analysis for project finance.
    
    Measures impact of parameter variations on key metrics (IRR, NPV, DSCR).
    Produces tornado diagrams showing which variables drive most value.
    """
    
    def __init__(self, base_case_returns: Dict[str, Any], params: Dict[str, Any]):
        """
        Initialize tornado analyzer with base case.
        
        Parameters
        ----------
        base_case_returns : dict
            Base case returns from calculate_all_returns()
        params : dict
            YAML parameters
        """
        self.base_returns = base_case_returns
        self.params = params
        self.sensitivities = {}
    
    def calculate_sensitivity(
        self,
        param_name: str,
        param_path: List[str],
        low_pct: float,
        high_pct: float,
        calc_func,
        metric: str = 'equity_irr'
    ) -> Dict[str, Any]:
        """
        Calculate sensitivity for single parameter variation.
        
        Parameters
        ----------
        param_name : str
            Human-readable parameter name (e.g., "Capacity Factor")
        param_path : list of str
            Path to parameter in params dict (e.g., ['project', 'capacity_factor'])
        low_pct : float
            Low case % change (e.g., -0.05 for -5%)
        high_pct : float
            High case % change (e.g., +0.05 for +5%)
        calc_func : callable
            Function to run scenario (e.g., calculate_all_returns)
        metric : str
            Metric to extract ('equity_irr', 'equity_npv', 'dscr_min', etc.)
        
        Returns
        -------
        dict
            {
                'param_name': str,
                'base_value': float,
                'low_value': float,
                'high_value': float,
                'low_impact': float,
                'high_impact': float,
                'total_swing': float,
                'upside_swing': float,
                'downside_swing': float
            }
        """
        # Get base case value from params
        base_value = self._get_nested_value(self.params, param_path)
        base_metric = self._get_nested_value(self.base_returns, metric.split('/'))
        
        # Low case
        low_params = self._deep_copy_params(self.params)
        low_value = base_value * (1 + low_pct)
        self._set_nested_value(low_params, param_path, low_value)
        low_returns = calc_func(low_params)
        low_metric = self._get_nested_value(low_returns, metric.split('/'))
        
        # High case
        high_params = self._deep_copy_params(self.params)
        high_value = base_value * (1 + high_pct)
        self._set_nested_value(high_params, param_path, high_value)
        high_returns = calc_func(high_params)
        high_metric = self._get_nested_value(high_returns, metric.split('/'))
        
        # Calculate impacts
        low_impact = low_metric - base_metric
        high_impact = high_metric - base_metric
        total_swing = abs(high_impact - low_impact)
        
        return {
            'param_name': param_name,
            'base_value': base_value,
            'low_value': low_value,
            'high_value': high_value,
            'low_metric': low_metric,
            'high_metric': high_metric,
            'base_metric': base_metric,
            'low_impact': low_impact,
            'high_impact': high_impact,
            'total_swing': total_swing,
            'upside_swing': max(high_impact, low_impact),
            'downside_swing': min(high_impact, low_impact)
        }
    
    def tornado_chart(
        self,
        sensitivities: Dict[str, Dict[str, Any]],
        metric_name: str = 'Equity IRR',
        title: str = 'Sensitivity Tornado Chart',
        output_path: Optional[Path] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> plt.Figure:
        """
        Generate tornado chart visualization.
        
        Parameters
        ----------
        sensitivities : dict
            Dictionary of sensitivity results
        metric_name : str
            Name of metric being analyzed
        title : str
            Chart title
        output_path : Path, optional
            Path to save PNG
        figsize : tuple
            Figure size (width, height)
        
        Returns
        -------
        matplotlib.figure.Figure
            Generated figure
        """
        # Sort by total swing (largest at bottom)
        sorted_sens = sorted(
            sensitivities.items(),
            key=lambda x: x[1]['total_swing'],
            reverse=False  # Ascending for bottom-to-top tornado shape
        )
        
        param_names = [s[0] for s in sorted_sens]
        downside_swings = [s[1]['downside_swing'] for s in sorted_sens]
        upside_swings = [s[1]['upside_swing'] for s in sorted_sens]
        
        # Create figure
        fig, ax = plt.subplots(figsize=figsize)
        
        y_pos = np.arange(len(param_names))
        
        # Plot horizontal bars
        ax.barh(
            y_pos,
            downside_swings,
            left=0,
            color='#d73027',  # Red for downside
            label='Downside',
            alpha=0.8
        )
        ax.barh(
            y_pos,
            upside_swings,
            left=0,
            color='#4575b4',  # Blue for upside
            label='Upside',
            alpha=0.8
        )
        
        # Add vertical line at x=0 (base case)
        ax.axvline(0, color='black', linewidth=1.5, linestyle='-')
        
        # Labels and formatting
        ax.set_yticks(y_pos)
        ax.set_yticklabels(param_names, fontsize=11, fontweight='bold')
        ax.set_xlabel(f'Impact on {metric_name}', fontsize=12, fontweight='bold')
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        
        # Add value labels on bars
        for i, (down, up) in enumerate(zip(downside_swings, upside_swings)):
            if down < 0:
                ax.text(down - 0.5, i, f'{down:.2f}%', ha='right', va='center', fontsize=9)
            if up > 0:
                ax.text(up + 0.5, i, f'{up:.2f}%', ha='left', va='center', fontsize=9)
        
        ax.legend(loc='lower right', fontsize=11)
        ax.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            logger.info(f"Tornado chart saved: {output_path}")
        
        return fig
    
    def sensitivity_table(
        self,
        sensitivities: Dict[str, Dict[str, Any]],
        metric_type: str = 'IRR'
    ) -> pd.DataFrame:
        """
        Generate sensitivity analysis table.
        
        Parameters
        ----------
        sensitivities : dict
            Dictionary of sensitivity results
        metric_type : str
            'IRR', 'NPV', or 'DSCR' for formatting
        
        Returns
        -------
        pd.DataFrame
            Sensitivity summary table
        """
        rows = []
        
        for param_name, sens in sorted(
            sensitivities.items(),
            key=lambda x: x[1]['total_swing'],
            reverse=True
        ):
            if metric_type == 'IRR':
                fmt_base = f"{sens['base_metric']*100:.2f}%"
                fmt_low = f"{sens['low_metric']*100:.2f}%"
                fmt_high = f"{sens['high_metric']*100:.2f}%"
                fmt_impact = f"{sens['total_swing']*100:.2f}%"
            elif metric_type == 'NPV':
                fmt_base = f"${sens['base_metric']:,.0f}"
                fmt_low = f"${sens['low_metric']:,.0f}"
                fmt_high = f"${sens['high_metric']:,.0f}"
                fmt_impact = f"${sens['total_swing']:,.0f}"
            else:  # DSCR
                fmt_base = f"{sens['base_metric']:.2f}x"
                fmt_low = f"{sens['low_metric']:.2f}x"
                fmt_high = f"{sens['high_metric']:.2f}x"
                fmt_impact = f"{sens['total_swing']:.2f}x"
            
            rows.append({
                'Parameter': param_name,
                'Base Case': fmt_base,
                'Low Case': fmt_low,
                'High Case': fmt_high,
                'Total Swing': fmt_impact
            })
        
        return pd.DataFrame(rows)
    
    # Helper methods
    def _get_nested_value(self, d: Dict, path: List[str]) -> Any:
        """Get value from nested dict using path."""
        value = d
        for key in path:
            value = value[key]
        return value
    
    def _set_nested_value(self, d: Dict, path: List[str], value: Any):
        """Set value in nested dict using path."""
        for key in path[:-1]:
            d = d[key]
        d[path[-1]] = value
    
    def _deep_copy_params(self, params: Dict) -> Dict:
        """Deep copy parameters dict."""
        import copy
        return copy.deepcopy(params)
    
    def generate_summary_report(
        self,
        sensitivities: Dict[str, Dict[str, Any]],
        output_path: Optional[Path] = None
    ) -> str:
        """Generate markdown sensitivity report."""
        report = """# Sensitivity Analysis Report

## Executive Summary

This tornado analysis quantifies the impact of key parameter variations on project returns.

## Key Findings

"""
        # Sort by swing magnitude
        sorted_sens = sorted(
            sensitivities.items(),
            key=lambda x: x[1]['total_swing'],
            reverse=True
        )
        
        report += "### Parameter Ranking (by Impact):\n\n"
        for i, (param_name, sens) in enumerate(sorted_sens, 1):
            total_swing_pct = sens['total_swing'] * 100
            report += f"{i}. **{param_name}**: {total_swing_pct:.2f}% swing\n"
        
        report += "\n### Sensitivity Details:\n\n"
        for param_name, sens in sorted_sens:
            report += f"#### {param_name}\n"
            report += f"- Base Case: {sens['base_metric']:.4f}\n"
            report += f"- Low Case: {sens['low_metric']:.4f} (Impact: {sens['low_impact']:+.4f})\n"
            report += f"- High Case: {sens['high_metric']:.4f} (Impact: {sens['high_impact']:+.4f})\n"
            report += f"- Total Swing: {sens['total_swing']:.4f}\n\n"
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            logger.info(f"Sensitivity report saved: {output_path}")
        
        return report


