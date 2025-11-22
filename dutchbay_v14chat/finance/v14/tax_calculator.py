"""Tax Calculator V14"""
from __future__ import annotations

from typing import Any, Dict, List


def calculate_depreciation_schedule(
    asset_value: float,
    method: str,
    years: int,
    operational_years: int = 20,
) -> List[float]:
    if method == "straight_line":
        annual = asset_value / years
        active_years = min(years, operational_years)
        tail_years = max(0, operational_years - years)
        return [annual] * active_years + [0.0] * tail_years
    return []


class TaxCalculatorV14:
    """Tax calculation engine"""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = config
        self.tax_config: Dict[str, Any] = config.get("tax", {})
        self.corporate_rate: float = float(self.tax_config.get("corporate_tax_rate", 0.30))

    def calculate_depreciation(
        self,
        asset_value: float,
        operational_years: int = 20,
    ) -> List[float]:
        method: str = self.tax_config.get("depreciation_method", "straight_line")
        years_raw: Any = self.tax_config.get("depreciation_years", 15)
        years: int = int(years_raw)
        return calculate_depreciation_schedule(asset_value, method, years, operational_years)

