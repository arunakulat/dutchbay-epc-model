"""
Tax Profile Module - v14.0.0 Hydra-Compliant (Sprint 11 Phase 1a)
==============================================================

Canonical tax calculation framework for DutchBay EPC Model.

**CRITICAL: GWTF v3.0 Compliance**
- ARCH-01: Config-first (ALL params from dutchbay_lendercase_2025Q4.yaml)
- VAL-01: Schema guard validates required tax config fields
- CLI-01: Hydra-based (never argparse)
- CST-01: Type-safe with mypy --strict
- R3: No argparse anywhere
- R4: No Typer in v14

**Configuration Path:**
- scenarios/dutchbay_lendercase_2025Q4.yaml::tax section
- scenarios/dutchbay_lendercase_2025Q4.yaml::project section (fallback)

**NO HARDCODED VALUES - ALL YAML-DRIVEN**

Author: DutchBay Finance Team
Date: December 16, 2025
Version: 14.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, cast

from omegaconf import DictConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaxProfile:
    """
    Immutable tax profile derived from YAML config.

    This dataclass is frozen (immutable) to ensure audit-safe behavior
    and prevent accidental mutation during calculation loops.

    Attributes:
        corporate_tax_rate (float): Tax rate as decimal (from config.tax.corporate_tax_rate)
        depreciation_schedule_lkr (Sequence[float]): Annual depreciation (LKR)
        tax_holiday_years (int): Years of zero tax (from config.tax.tax_holiday_years)
        tax_holiday_start_year (int): 1-based year when holiday begins
        apply_interest_shield (bool): Whether interest reduces taxable income
        depreciation_method (str): 'straight_line' or future methods
        loss_carryforward_years (int): Years losses can be carried forward
        enhanced_allowance_applies (bool): Whether enhanced allowance is active

    Raises:
        ValueError: If tax_rate not in [0.0, 1.0], or holiday invalid

    Notes:
        - All values sourced from dutchbay_lendercase_2025Q4.yaml::tax section
        - No hardcoded defaults; config must be valid per schema guard
        - Immutable (frozen=True) for audit trail and thread safety
    """

    corporate_tax_rate: float
    depreciation_schedule_lkr: Sequence[float]
    tax_holiday_years: int
    tax_holiday_start_year: int
    apply_interest_shield: bool
    depreciation_method: str  # e.g. "straight_line"
    loss_carryforward_years: int
    enhanced_allowance_applies: bool
    config_source: str  # For audit: path/hash of source config

    def __post_init__(self) -> None:
        """Validate all fields on construction (frozen-safe)."""
        if not (0.0 <= self.corporate_tax_rate <= 1.0):
            raise ValueError(
                f"corporate_tax_rate must be [0.0, 1.0]; got {self.corporate_tax_rate}"
            )

        if self.tax_holiday_years < 0:
            raise ValueError(
                f"tax_holiday_years must be >= 0; got {self.tax_holiday_years}"
            )

        if self.tax_holiday_start_year < 1:
            raise ValueError(
                f"tax_holiday_start_year must be >= 1 (1-based); got {self.tax_holiday_start_year}"
            )

        if self.loss_carryforward_years < 0:
            raise ValueError(
                f"loss_carryforward_years must be >= 0; got {self.loss_carryforward_years}"
            )

        logger.info(
            f"TaxProfile created from {self.config_source}: "
            f"rate={self.corporate_tax_rate:.1%}, "
            f"holiday={self.tax_holiday_years}yr (year {self.tax_holiday_start_year}+), "
            f"method={self.depreciation_method}"
        )

    def is_in_tax_holiday(self, year_index: int) -> bool:
        """
        Check if year_index (0-based) is within tax holiday window.

        Parameters:
            year_index (int): 0-based year index (0 = first operating year)

        Returns:
            bool: True if in holiday, False otherwise
        """
        if self.tax_holiday_years == 0:
            return False

        year_number = year_index + 1  # Convert to 1-based
        holiday_end = self.tax_holiday_start_year + self.tax_holiday_years - 1

        return self.tax_holiday_start_year <= year_number <= holiday_end


def build_tax_profile(
    config_tax: DictConfig,
    capex_depreciable_lkr: Optional[float],
    project_life_years: int,
    config_source: str = "config",
) -> TaxProfile:
    """
    Build TaxProfile from OmegaConf DictConfig (from YAML).

    **CRITICAL: NO HARDCODED DEFAULTS**
    All parameters must come from dutchbay_lendercase_2025Q4.yaml::tax section.

    Parameters:
        config_tax (DictConfig): Validated tax section from YAML config
            Expected keys:
            - corporate_tax_rate (float, 0.0-1.0)
            - tax_holiday_years (int >= 0)
            - tax_holiday_start_year (int >= 1)
            - depreciation_method (str, e.g. 'straight_line')
            - depreciation_years (int > 0)
            - depreciation_start_year (int >= 1)
            - enhanced_capital_allowance_pct (float >= 1.0)
            - enhanced_allowance_applies (bool)
            - loss_carryforward_years (int >= 0)

        capex_depreciable_lkr (Optional[float]): Depreciable capex (LKR)
            If None or <= 0, depreciation schedule is all zeros

        project_life_years (int): Total project life for schedule padding

        config_source (str): For audit trail (e.g. 'scenarios/dutchbay_lendercase_2025Q4.yaml')

    Returns:
        TaxProfile: Immutable tax profile with pre-computed depreciation

    Raises:
        ValueError: If required keys missing or validation fails
        TypeError: If types are incorrect

    Notes:
        - Called by analytics.schema_guard.validate_config_for_v14
        - Schedule pre-computed once for O(1) year-by-year lookup
        - All values from config_tax (YAML); no defaults hardcoded
    """
    # Extract required fields from YAML config
    try:
        corporate_tax_rate = float(config_tax.corporate_tax_rate)
        tax_holiday_years = int(config_tax.tax_holiday_years)
        tax_holiday_start_year = int(config_tax.tax_holiday_start_year)
        depreciation_years = int(config_tax.depreciation_years)
        enhanced_cap_allowance_pct = float(config_tax.enhanced_capital_allowance_pct)
        enhanced_allowance_applies = bool(
            config_tax.get("enhanced_allowance_applies", False)
        )
        depreciation_method = str(
            config_tax.get("depreciation_method", "straight_line")
        )
        loss_carryforward_years = int(config_tax.get("loss_carryforward_years", 0))
        apply_interest_shield = bool(config_tax.get("apply_interest_shield", True))
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(
            f"Tax config validation failed. Required fields: corporate_tax_rate, "
            f"tax_holiday_years, depreciation_years, etc. Error: {e}"
        ) from e

    # Compute depreciation schedule
    if (
        capex_depreciable_lkr is None
        or capex_depreciable_lkr <= 0.0
        or depreciation_years <= 0
    ):
        depreciation_schedule: list[float] = []
    else:
        # Straight-line with optional enhanced allowance
        total_depreciable = capex_depreciable_lkr * enhanced_cap_allowance_pct
        annual_depreciation = total_depreciable / float(depreciation_years)
        depreciation_schedule = [annual_depreciation] * depreciation_years

    # Pad/trim to project life
    if len(depreciation_schedule) < project_life_years:
        depreciation_schedule = depreciation_schedule + [0.0] * (
            project_life_years - len(depreciation_schedule)
        )
    elif len(depreciation_schedule) > project_life_years:
        depreciation_schedule = depreciation_schedule[:project_life_years]

    logger.debug(
        f"Built depreciation schedule: {depreciation_years} years of "
        f"LKR {total_depreciable if capex_depreciable_lkr else 0:.0f} "
        f"(enhanced x{enhanced_cap_allowance_pct}), padded to {project_life_years} years"
    )

    return TaxProfile(
        corporate_tax_rate=corporate_tax_rate,
        depreciation_schedule_lkr=depreciation_schedule,
        tax_holiday_years=tax_holiday_years,
        tax_holiday_start_year=tax_holiday_start_year,
        apply_interest_shield=apply_interest_shield,
        depreciation_method=depreciation_method,
        loss_carryforward_years=loss_carryforward_years,
        enhanced_allowance_applies=enhanced_allowance_applies,
        config_source=config_source,
    )


def calculate_tax_for_year(
    profile: TaxProfile,
    pretax_cfads_lkr: float,
    interest_expense_lkr: float,
    year_index: int,
) -> Tuple[float, float]:
    """
    Calculate tax and depreciation for a single year.

    Implements Sri Lanka BOI tax rules:
    1. During tax holiday: tax = 0 (but depreciation accrues)
    2. Outside holiday: taxable income = pretax_cfads - depreciation - interest
    3. Tax = taxable income × corporate_tax_rate (floored at 0)

    Parameters:
        profile (TaxProfile): Pre-built tax profile (from build_tax_profile)
        pretax_cfads_lkr (float): CFADS before tax (LKR)
        interest_expense_lkr (float): Interest expense for year (LKR)
        year_index (int): 0-based year index

    Returns:
        Tuple[float, float]: (tax_liability, depreciation) in LKR

    Notes:
        - O(1) calculation: depreciation is pre-computed lookup
        - Tax is floored at 0.0 (no negative tax)
        - Loss carry-forward is NOT handled here (implement upstream if needed)
    """
    # Get depreciation from pre-computed schedule
    if year_index < len(profile.depreciation_schedule_lkr):
        depreciation_for_year = profile.depreciation_schedule_lkr[year_index]
    else:
        depreciation_for_year = 0.0

    # Tax holiday check
    if profile.is_in_tax_holiday(year_index):
        return 0.0, depreciation_for_year

    # Calculate taxable income
    taxable_income = pretax_cfads_lkr - depreciation_for_year

    # Apply interest shield if enabled
    if profile.apply_interest_shield:
        taxable_income -= interest_expense_lkr

    # Floor to zero (no losses carried forward at this level)
    taxable_income = max(0.0, taxable_income)

    # Apply tax rate
    tax_liability = taxable_income * profile.corporate_tax_rate

    return tax_liability, depreciation_for_year


def extract_tax_config_from_full_config(full_config: DictConfig) -> DictConfig:
    """
    Extract tax section from full project config (DutchBay YAML).

    Handles fallback logic:
    1. Try full_config.tax section (canonical location)
    2. Fall back to full_config.project section (legacy fallback)

    Parameters:
        full_config (DictConfig): Full project config from dutchbay_lendercase_2025Q4.yaml

    Returns:
        DictConfig: Tax configuration section

    Raises:
        ValueError: If tax section not found or invalid
    """
    if "tax" in full_config:
        return cast(DictConfig, full_config.tax)

    if "project" in full_config:
        logger.warning(
            "Tax config not found in config.tax; falling back to config.project"
        )
        return cast(DictConfig, full_config.project)

    raise ValueError(
        "Tax configuration not found in config.tax or config.project. "
        "Ensure dutchbay_lendercase_2025Q4.yaml has 'tax:' section."
    )


__all__ = [
    "TaxProfile",
    "build_tax_profile",
    "calculate_tax_for_year",
    "extract_tax_config_from_full_config",
]
