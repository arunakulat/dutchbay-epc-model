"""Tax Calculator V14 - Canonical v14 tax computation engine.

Provides depreciation scheduling and corporate tax calculations
for project finance models.

Migrated from: legacy/v14chat/finance/v14/tax_calculator.py
Part of: Task 1C - Tax Calculator Migration (Sprint Day 5)
"""

from __future__ import annotations

from typing import Any


def calculate_depreciation_schedule(
    asset_value: float,
    method: str,
    years: int,
    operational_years: int = 20,
) -> list[float]:
    """Calculate depreciation schedule for an asset.

    Args:
        asset_value: Total asset value to depreciate
        method: Depreciation method ('straight_line' supported)
        years: Number of years to depreciate over
        operational_years: Total operational life of project

    Returns:
        List of annual depreciation amounts (length = operational_years)

    Example:
        >>> calculate_depreciation_schedule(100_000, "straight_line", 10, 20)
        [10000.0, 10000.0, ..., 10000.0, 0.0, ..., 0.0]
        # 10 years of depreciation, then 10 years of zero
    """
    if method == "straight_line":
        annual = asset_value / years
        active_years = min(years, operational_years)
        tail_years = max(0, operational_years - years)
        return [annual] * active_years + [0.0] * tail_years

    # Future: Add declining_balance, double_declining, etc.
    return []


class TaxCalculatorV14:
    """Tax calculation engine for project finance models.

    Handles:
    - Depreciation scheduling (straight-line, future: declining balance)
    - Corporate tax rate application
    - Tax holiday and enhanced capital allowance support (future)

    Attributes:
        config: Full scenario configuration dict
        tax_config: Tax-specific configuration block
        corporate_rate: Corporate tax rate (decimal, e.g., 0.30 for 30%)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize tax calculator from scenario config.

        Args:
            config: Scenario configuration dict with optional 'tax' block

        Example config structure:
            {
                "tax": {
                    "corporate_tax_rate": 0.30,
                    "depreciation_method": "straight_line",
                    "depreciation_years": 15
                }
            }
        """
        self.config: dict[str, Any] = config
        self.tax_config: dict[str, Any] = config.get("tax", {})
        self.corporate_rate: float = float(
            self.tax_config.get("corporate_tax_rate", 0.30)
        )

    def calculate_depreciation(
        self,
        asset_value: float,
        operational_years: int = 20,
    ) -> list[float]:
        """Calculate depreciation schedule from config parameters.

        Args:
            asset_value: Total asset value to depreciate
            operational_years: Total operational life of project

        Returns:
            List of annual depreciation amounts

        Note:
            Depreciation method and years are read from self.tax_config.
            Defaults: straight_line method, 15 years.
        """
        method: str = self.tax_config.get("depreciation_method", "straight_line")
        years_raw: Any = self.tax_config.get("depreciation_years", 15)
        years: int = int(years_raw)

        return calculate_depreciation_schedule(
            asset_value, method, years, operational_years
        )
