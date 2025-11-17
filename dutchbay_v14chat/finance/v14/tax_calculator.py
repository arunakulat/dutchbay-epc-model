"""Tax Calculator V14"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple

def calculate_depreciation_schedule(asset_value, method, years, operational_years=20):
    if method == 'straight_line':
        annual = asset_value / years
        return [annual] * min(years, operational_years) + [0.0] * max(0, operational_years - years)
    return []

class TaxCalculatorV14:
    """Tax calculation engine"""
    def __init__(self, config):
        self.config = config
        self.tax_config = config.get('tax', {})
        self.corporate_rate = self.tax_config.get('corporate_tax_rate', 0.30)
    
    def calculate_depreciation(self, asset_value, operational_years=20):
        method = self.tax_config.get('depreciation_method', 'straight_line')
        years = self.tax_config.get('depreciation_years', 15)
        return calculate_depreciation_schedule(asset_value, method, years, operational_years)
