from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

"""
Phase 2 Refactoring: Tax Profile Module (CCCDIR / CASPER / CESSPIT / GWTF)

This module provides a clean, configuration-driven tax engine for DutchBay v14.

Goals
-----
- Config-driven (CCCDIR):
  * All tax parameters come from the scenario YAML `tax.*` block.
  * No hidden defaults; any behaviour change is visible in YAML.

- Contract-first:
  * Typed, frozen dataclasses for configuration and results.
  * No untyped dicts escaping this module.

- CASPER / CESSPIT / GWTF-aligned:
  * Pure functions (no I/O, no logging, no global state).
  * Single responsibility: this module only deals with tax logic.
  * Explicit handling of tax holiday, loss carry-forward, and interest WHT.

YAML Expectations
-----------------
The scenario configuration must provide at least:

tax:
  corporate_tax_rate: 0.30  # CANONICAL - use this
  # OR (deprecated, backward compat):
  # corporate_tax_rate_pct: 30  # Will convert to 0.30
  depreciation_method: "straight_line"
  depreciation_start_year: 1
  depreciation_years: 15
  enhanced_allowance_applies: false
  enhanced_capital_allowance_pct: 1.5
  loss_carryforward_years: 25
  tax_holiday_start_year: 1
  tax_holiday_years: 12

  # Interest withholding tax (AIT/WHT)
  wht_on_interest_to_nonresidents: 0.10
  wht_on_interest_enabled: true
  wht_gross_up: false

This module does NOT know about SSCL or other statutory levies; those are
handled by StatutoryProfile in a separate module.
"""
# ---------------------------------------------------------------------------
# Helpers for safe config access (no magic defaults)
# ---------------------------------------------------------------------------


def _require_section(cfg: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return a named subsection or raise if missing."""
    section = cfg.get(name)
    if not isinstance(section, Mapping):
        raise KeyError(f"Missing required YAML section: {name}")
    return section


def _require_key(section: Mapping[str, Any], key: str, ctx: str) -> Any:
    """Return a required key from a section or raise with context."""
    if key not in section:
        raise KeyError(f"Missing required YAML key: {ctx}.{key}")
    return section[key]


def _get_tax_rate_with_compat(tax: Mapping[str, Any]) -> float:
    """
    Extract tax rate with backward compatibility.

    CANONICAL: tax.corporate_tax_rate (decimal 0.0-1.0)
    DEPRECATED: tax.corporate_tax_rate_pct (percentage 0-100)

    Returns decimal rate (0.30 for 30%).
    """
    # Try canonical first
    if "corporate_tax_rate" in tax:
        rate = float(tax["corporate_tax_rate"])
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be decimal 0.0-1.0, got {rate}"
            )
        return rate

    # Fall back to deprecated _pct version
    if "corporate_tax_rate_pct" in tax:
        warnings.warn(
            "tax.corporate_tax_rate_pct is deprecated. "
            "Use tax.corporate_tax_rate (decimal) instead. "
            "This will be removed in v15.",
            DeprecationWarning,
            stacklevel=3,
        )
        pct = float(tax["corporate_tax_rate_pct"])
        if not (0.0 <= pct <= 100.0):
            raise ValueError(f"tax.corporate_tax_rate_pct must be 0-100, got {pct}")
        return pct / 100.0

    # Neither found - fail
    raise KeyError(
        "Missing required YAML key: tax.corporate_tax_rate "
        "(or deprecated tax.corporate_tax_rate_pct)"
    )


# ---------------------------------------------------------------------------
# Configuration-level profile (maps 1:1 to YAML)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaxConfig:
    """
    YAML-level tax configuration (contract-first).

    This is an exact mirror of the `tax` block in scenario YAML. It does not
    contain derived values like per-year depreciation or holiday maps.
    """

    corporate_tax_rate: float
    depreciation_method: str
    depreciation_start_year: int
    depreciation_years: int
    enhanced_allowance_applies: bool
    enhanced_capital_allowance_pct: float
    loss_carryforward_years: int
    tax_holiday_start_year: int
    tax_holiday_years: int

    # Interest WHT (AIT) controls
    wht_on_interest_to_nonresidents: float
    wht_on_interest_enabled: bool
    wht_gross_up: bool

    # Optional, for regimes where interest is not deductible (default: True)
    interest_deductibility: bool = True

    @classmethod
    def from_yaml(cls, cfg: Mapping[str, Any]) -> "TaxConfig":
        """
        Build TaxConfig from the full scenario dict (expects `tax` section).
        """
        tax = _require_section(cfg, "tax")

        # Required keys with backward compatibility
        corporate_tax_rate = _get_tax_rate_with_compat(tax)

        depreciation_method = str(_require_key(tax, "depreciation_method", "tax"))
        depreciation_start_year = int(
            _require_key(tax, "depreciation_start_year", "tax")
        )
        depreciation_years = int(_require_key(tax, "depreciation_years", "tax"))
        enhanced_allowance_applies = bool(
            _require_key(tax, "enhanced_allowance_applies", "tax")
        )
        enhanced_capital_allowance_pct = float(
            _require_key(tax, "enhanced_capital_allowance_pct", "tax")
        )
        loss_carryforward_years = int(
            _require_key(tax, "loss_carryforward_years", "tax")
        )
        tax_holiday_start_year = int(_require_key(tax, "tax_holiday_start_year", "tax"))
        tax_holiday_years = int(_require_key(tax, "tax_holiday_years", "tax"))

        # Interest WHT knobs (no hidden defaults)
        wht_on_interest_to_nonresidents = float(
            _require_key(tax, "wht_on_interest_to_nonresidents", "tax")
        )
        wht_on_interest_enabled = bool(
            _require_key(tax, "wht_on_interest_enabled", "tax")
        )
        wht_gross_up = bool(_require_key(tax, "wht_gross_up", "tax"))

        # Optional: interest deductibility (default True if omitted)
        interest_deductibility = bool(tax.get("interest_deductibility", True))

        obj = cls(
            corporate_tax_rate=corporate_tax_rate,
            depreciation_method=depreciation_method,
            depreciation_start_year=depreciation_start_year,
            depreciation_years=depreciation_years,
            enhanced_allowance_applies=enhanced_allowance_applies,
            enhanced_capital_allowance_pct=enhanced_capital_allowance_pct,
            loss_carryforward_years=loss_carryforward_years,
            tax_holiday_start_year=tax_holiday_start_year,
            tax_holiday_years=tax_holiday_years,
            wht_on_interest_to_nonresidents=wht_on_interest_to_nonresidents,
            wht_on_interest_enabled=wht_on_interest_enabled,
            wht_gross_up=wht_gross_up,
            interest_deductibility=interest_deductibility,
        )
        obj._validate()
        return obj

    def _validate(self) -> None:
        """Validate basic ranges and consistency."""
        if not (0.0 <= self.corporate_tax_rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be in [0,1], got {self.corporate_tax_rate}"
            )
        if self.depreciation_years < 0:
            raise ValueError("tax.depreciation_years must be >= 0")
        if self.depreciation_start_year < 1:
            raise ValueError("tax.depreciation_start_year must be >= 1")
        if self.tax_holiday_start_year < 1 or self.tax_holiday_years < 0:
            raise ValueError("tax holiday parameters invalid")
        if self.loss_carryforward_years < 0:
            raise ValueError("tax.loss_carryforward_years must be >= 0")
        if not (0.0 <= self.wht_on_interest_to_nonresidents <= 1.0):
            raise ValueError("tax.wht_on_interest_to_nonresidents must be in [0,1]")
        if self.depreciation_method not in (
            "straight_line",
            "accelerated",
            "none",
        ):
            raise ValueError(
                f"tax.depreciation_method unsupported: {self.depreciation_method}"
            )


# ---------------------------------------------------------------------------
# Runtime Tax Profile (derived from config + capital inputs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DepreciationSchedule:
    """Per-year depreciation amounts."""

    annual_depreciation: Dict[int, float]
    total_depreciable_base: float
    method: str

    def get_depreciation(self, year: int) -> float:
        """Get depreciation for a given year."""
        return self.annual_depreciation.get(year, 0.0)


@dataclass(frozen=True)
class TaxProfile:
    """
    Runtime tax profile combining config + derived values.

    This is built once from TaxConfig and used throughout the simulation.
    """

    config: TaxConfig
    depreciation_schedule: DepreciationSchedule

    def is_tax_holiday(self, year: int) -> bool:
        """Check if a year is within the tax holiday period."""
        start = self.config.tax_holiday_start_year
        end = start + self.config.tax_holiday_years - 1
        return start <= year <= end


@dataclass(frozen=True)
class TaxResult:
    """Single-year tax calculation result."""

    year: int
    ebt: float  # Earnings before tax
    depreciation: float
    interest_expense: float
    taxable_income: float
    tax_rate: float
    tax_before_holiday: float
    is_tax_holiday: bool
    tax_after_holiday: float
    loss_carryforward_used: float
    loss_carryforward_remaining: float
    final_tax: float
    eat: float  # Earnings after tax

    # Interest WHT components
    interest_wht: float
    interest_wht_grossup: float


# ---------------------------------------------------------------------------
# Pure functions for tax calculations
# ---------------------------------------------------------------------------


def build_depreciation_schedule(
    capex: float,
    config: TaxConfig,
    total_years: int,
) -> DepreciationSchedule:
    """
    Build depreciation schedule from capex and config.

    Args:
        capex: Total capital expenditure
        config: Tax configuration
        total_years: Total simulation years

    Returns:
        DepreciationSchedule with annual amounts
    """
    if config.depreciation_method == "none":
        return DepreciationSchedule(
            annual_depreciation={},
            total_depreciable_base=0.0,
            method="none",
        )

    # Enhanced capital allowance
    depreciable_base = capex
    if config.enhanced_allowance_applies:
        depreciable_base *= config.enhanced_capital_allowance_pct

    annual_amounts: Dict[int, float] = {}

    if config.depreciation_method == "straight_line":
        # Equal depreciation over depreciation_years
        if config.depreciation_years > 0:
            annual_amount = depreciable_base / config.depreciation_years
            start = config.depreciation_start_year
            end = min(start + config.depreciation_years, total_years + 1)

            for year in range(start, end):
                annual_amounts[year] = annual_amount

    elif config.depreciation_method == "accelerated":
        # Double declining balance or similar
        # For now, implement simple accelerated: 40% year 1, 30% year 2, etc.
        remaining = depreciable_base
        start = config.depreciation_start_year
        rates = [0.40, 0.30, 0.20, 0.10]  # Sum to 100% over 4 years

        for i, rate in enumerate(rates):
            year = start + i
            if year > total_years:
                break
            amount = depreciable_base * rate
            annual_amounts[year] = amount
            remaining -= amount

        # Any remainder goes to the last year
        if remaining > 0.01 and year <= total_years:
            annual_amounts[year] = annual_amounts.get(year, 0.0) + remaining

    return DepreciationSchedule(
        annual_depreciation=annual_amounts,
        total_depreciable_base=depreciable_base,
        method=config.depreciation_method,
    )


def build_tax_profile(
    config: TaxConfig,
    capex: float,
    total_years: int,
) -> TaxProfile:
    """
    Build runtime tax profile from config and capex.

    Args:
        config: Tax configuration from YAML
        capex: Total capital expenditure
        total_years: Total simulation years

    Returns:
        TaxProfile ready for use in calculations
    """
    depreciation = build_depreciation_schedule(capex, config, total_years)
    return TaxProfile(config=config, depreciation_schedule=depreciation)


def calculate_tax(
    profile: TaxProfile,
    year: int,
    ebt: float,
    interest_expense: float,
    loss_carryforward: float,
) -> TaxResult:
    """
    Calculate tax for a single year (pure function).

    Args:
        profile: Tax profile with config and schedules
        year: Current year
        ebt: Earnings before tax
        interest_expense: Interest expense for the year
        loss_carryforward: Accumulated losses from previous years

    Returns:
        TaxResult with all tax calculations
    """
    cfg = profile.config

    # Depreciation
    depreciation = profile.depreciation_schedule.get_depreciation(year)

    # Deductible interest
    deductible_interest = interest_expense if cfg.interest_deductibility else 0.0

    # Taxable income before loss carryforward
    taxable_income_before_lcf = ebt - depreciation - deductible_interest

    # Apply loss carryforward
    loss_used = 0.0
    if taxable_income_before_lcf > 0 and loss_carryforward > 0:
        loss_used = min(taxable_income_before_lcf, loss_carryforward)

    taxable_income = max(0.0, taxable_income_before_lcf - loss_used)

    # Tax before holiday
    tax_before_holiday = taxable_income * cfg.corporate_tax_rate

    # Tax holiday
    is_holiday = profile.is_tax_holiday(year)
    tax_after_holiday = 0.0 if is_holiday else tax_before_holiday

    # Interest WHT (applied to non-resident lenders)
    interest_wht = 0.0
    interest_wht_grossup = 0.0

    if cfg.wht_on_interest_enabled and interest_expense > 0:
        interest_wht = interest_expense * cfg.wht_on_interest_to_nonresidents

        if cfg.wht_gross_up:
            # Gross-up: SPV pays additional tax to cover WHT burden
            interest_wht_grossup = interest_wht / (
                1.0 - cfg.wht_on_interest_to_nonresidents
            )
            interest_wht = interest_wht_grossup

    # Final tax
    final_tax = tax_after_holiday + interest_wht

    # EAT
    eat = ebt - final_tax

    # Update loss carryforward
    new_lcf = loss_carryforward - loss_used
    if taxable_income_before_lcf < 0:
        # Add new loss (negative taxable income)
        new_lcf += abs(taxable_income_before_lcf)

    return TaxResult(
        year=year,
        ebt=ebt,
        depreciation=depreciation,
        interest_expense=interest_expense,
        taxable_income=taxable_income,
        tax_rate=cfg.corporate_tax_rate,
        tax_before_holiday=tax_before_holiday,
        is_tax_holiday=is_holiday,
        tax_after_holiday=tax_after_holiday,
        loss_carryforward_used=loss_used,
        loss_carryforward_remaining=new_lcf,
        final_tax=final_tax,
        eat=eat,
        interest_wht=interest_wht,
        interest_wht_grossup=interest_wht_grossup,
    )


def build_tax_series(
    profile: TaxProfile,
    ebt_series: Sequence[float],
    interest_series: Sequence[float],
    start_year: int = 1,
) -> List[TaxResult]:
    """
    Build complete tax series for all years.

    Args:
        profile: Tax profile
        ebt_series: EBT for each year
        interest_series: Interest expense for each year
        start_year: Starting year number (default 1)

    Returns:
        List of TaxResult for each year
    """
    results: List[TaxResult] = []
    loss_carryforward = 0.0

    for i, (ebt, interest) in enumerate(zip(ebt_series, interest_series)):
        year = start_year + i
        result = calculate_tax(
            profile=profile,
            year=year,
            ebt=ebt,
            interest_expense=interest,
            loss_carryforward=loss_carryforward,
        )
        results.append(result)
        loss_carryforward = result.loss_carryforward_remaining

    return results


__all__ = [
    "TaxConfig",
    "TaxProfile",
    "TaxResult",
    "DepreciationSchedule",
    "build_tax_profile",
    "build_tax_series",
    "calculate_tax",
]
