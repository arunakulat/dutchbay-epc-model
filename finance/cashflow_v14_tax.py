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
  corporate_tax_rate: 0.30
  depreciation_method: "straight_line"  # OPTIONAL - defaults to "straight_line"
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

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

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

        # Required keys
        corporate_tax_rate = float(_require_key(tax, "corporate_tax_rate", "tax"))
        
        # PYDANTIC V2 FIX: Make depreciation_method optional with default
        depreciation_method = str(tax.get("depreciation_method", "straight_line"))
        
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
            # Kept broad for future extension; engine currently uses 'straight_line'
            raise ValueError(
                f"tax.depreciation_method unsupported: {self.depreciation_method}"
            )


# ---------------------------------------------------------------------------
# Execution-level tax profile (what the engine actually uses)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaxProfile:
    """
    Execution-ready tax profile for annual calculations.

    This is derived from TaxConfig + DepreciationSchedule and holds only the
    values needed in the per-year engine (calculate_tax).
    """

    tax_rate: float
    interest_deductibility: bool
    depreciation_method: str
    depreciation_schedule: List[float]
    allowable_losses_carryforward: bool
    withholding_tax_rate: float
    tax_holidays_by_year: Dict[int, bool]

    def __post_init__(self) -> None:
        if not (0.0 <= self.tax_rate <= 1.0):
            raise ValueError(f"tax_rate must be in [0,1], got {self.tax_rate}")
        if not (0.0 <= self.withholding_tax_rate <= 1.0):
            raise ValueError(
                f"withholding_tax_rate must be in [0,1], got {self.withholding_tax_rate}"
            )
        if self.depreciation_method not in (
            "straight_line",
            "accelerated",
            "none",
        ):
            raise ValueError(f"Unknown depreciation_method: {self.depreciation_method}")


# ---------------------------------------------------------------------------
# Depreciation schedule
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DepreciationSchedule:
    """
    Pre-computed depreciation schedule for project life.

    Attributes
    ----------
    method:
        Depreciation method used ('straight_line', 'accelerated', or 'none').
    capex_base:
        Total capital expenditure subject to depreciation (LKR).
    useful_life_years:
        Depreciation period.
    annual_amounts:
        Depreciation per project year (length == project_life_years).
    accumulated_depreciation:
        Cumulative depreciation at end of each year.
    book_value:
        Remaining depreciable base at end of each year.
    """

    method: str
    capex_base: float
    useful_life_years: int
    annual_amounts: List[float]
    accumulated_depreciation: List[float]
    book_value: List[float]

    @staticmethod
    def build_straight_line(
        capex_lkr: float,
        useful_life: int,
        project_life: int,
    ) -> "DepreciationSchedule":
        """
        Build a straight-line depreciation schedule.

        capex_lkr:
            Total capital expenditure (LKR).
        useful_life:
            Depreciation period (years).
        project_life:
            Project economic life (years).
        """
        if useful_life <= 0:
            raise ValueError("useful_life must be > 0 for straight_line")

        annual_depr = capex_lkr / useful_life

        annual_amounts: List[float] = []
        accumulated: List[float] = []
        book_values: List[float] = []
        acc = 0.0

        for year in range(1, project_life + 1):
            if year <= useful_life:
                depr = annual_depr
            else:
                depr = 0.0
            annual_amounts.append(depr)
            acc += depr
            accumulated.append(acc)
            bv = max(capex_lkr - acc, 0.0)
            book_values.append(bv)

        return DepreciationSchedule(
            method="straight_line",
            capex_base=capex_lkr,
            useful_life_years=useful_life,
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaxResult:
    """
    Immutable tax calculation result for a single project year.

    Attributes
    ----------
    year:
        Project year (1-based).
    ebit:
        Earnings before interest and tax (LKR).
    interest_expense:
        Debt interest expense (LKR), pre-WHT (gross coupon).
    depreciation:
        Depreciation deduction (LKR).
    taxable_income:
        Taxable income after deductions (LKR, floored at zero).
    tax_liability:
        Corporate income tax owed (LKR).
    effective_tax_rate:
        Actual rate paid (tax / ebit), guards against division by zero.
    tax_holiday_applied:
        Whether the year was treated as tax-free under holiday rules.
    carried_forward_losses:
        Losses carried into the next period (LKR).
    wht_on_interest:
        Withholding tax on interest (AIT) for this year (LKR).
    """

    year: int
    ebit: float
    interest_expense: float
    depreciation: float
    taxable_income: float
    tax_liability: float
    effective_tax_rate: float
    tax_holiday_applied: bool
    carried_forward_losses: float
    wht_on_interest: float


# ---------------------------------------------------------------------------
# Builders: from TaxConfig to TaxProfile
# ---------------------------------------------------------------------------


def build_tax_holiday_map(
    config: TaxConfig,
    project_life_years: int,
) -> Dict[int, bool]:
    """
    Build a {year: is_holiday} map from TaxConfig.
    """
    holidays: Dict[int, bool] = {}
    start = config.tax_holiday_start_year
    end = start + config.tax_holiday_years - 1
    for year in range(1, project_life_years + 1):
        holidays[year] = start <= year <= end
    return holidays


def build_tax_profile(
    config: TaxConfig,
    depreciation_schedule: DepreciationSchedule,
    project_life_years: int,
) -> TaxProfile:
    """
    Build an execution-ready TaxProfile from TaxConfig and DepreciationSchedule.
    """
    tax_holidays = build_tax_holiday_map(config, project_life_years)

    # Allowable losses carryforward: enabled if horizon > 0; expiry window
    # (25y, etc.) can be layered in later if required.
    allow_losses = config.loss_carryforward_years > 0

    # Withholding tax is modelled as a separate cash outflow; it does not
    # reduce taxable income (CIT) directly in this engine.
    wht_rate = (
        config.wht_on_interest_to_nonresidents
        if config.wht_on_interest_enabled
        else 0.0
    )

    return TaxProfile(
        tax_rate=config.corporate_tax_rate,
        interest_deductibility=config.interest_deductibility,
        depreciation_method=config.depreciation_method,
        depreciation_schedule=list(depreciation_schedule.annual_amounts),
        allowable_losses_carryforward=allow_losses,
        withholding_tax_rate=wht_rate,
        tax_holidays_by_year=tax_holidays,
    )


# ---------------------------------------------------------------------------
# Core engine (per-year + series)
# ---------------------------------------------------------------------------


def calculate_tax(
    year: int,
    ebit: float,
    interest_expense: float,
    depreciation: float,
    tax_profile: TaxProfile,
    prior_year_losses: float = 0.0,
    statutory_profile=None,
) -> TaxResult:
    """
    Calculate corporate tax and WHT for a single year.

    Logic:
      1. Determine if year is within a tax holiday.
      2. Start from EBIT.
      3. Deduct interest expense if deductible.
      4. Deduct depreciation.
      5. Apply prior-year loss carryforward (no expiry in this engine).
      6. Calculate CIT on positive taxable income only.
      7. Compute interest WHT as a separate cash outflow (no offset).
      8. Track updated loss carryforward.
    """
    # 1) Holiday flag
    is_holiday = tax_profile.tax_holidays_by_year.get(year, False)

    # 2) Start from EBIT
    taxable = ebit

    # 3) Interest deductibility
    if tax_profile.interest_deductibility:
        taxable -= interest_expense

    # 4) Depreciation
    taxable -= depreciation

    # 5) Prior-year losses
    carried_forward = 0.0
    if tax_profile.allowable_losses_carryforward and prior_year_losses > 0.0:
        loss_offset = min(prior_year_losses, max(taxable, 0.0))
        taxable -= loss_offset
        carried_forward = prior_year_losses - loss_offset

    # 6) CIT computation (no negative taxable income)
    taxable_income = max(taxable, 0.0)

    if is_holiday:
        tax_liability = 0.0
    else:
        tax_liability = taxable_income * tax_profile.tax_rate

    # New losses if taxable is negative this year
    new_losses = max(-taxable, 0.0) + carried_forward

    # Effective rate
    if ebit > 0.0:
        effective_rate = tax_liability / ebit
    else:
        effective_rate = 0.0

    # 7) Interest WHT (AIT) – separate from CIT
    wht_on_interest = interest_expense * tax_profile.withholding_tax_rate

    return TaxResult(
        year=year,
        ebit=ebit,
        interest_expense=interest_expense,
        depreciation=depreciation,
        taxable_income=taxable_income,
        tax_liability=tax_liability,
        effective_tax_rate=effective_rate,
        tax_holiday_applied=is_holiday,
        carried_forward_losses=new_losses,
        wht_on_interest=wht_on_interest,
    )


def build_tax_series(
    years: Sequence[int],
    ebit_series: Sequence[float],
    interest_series: Sequence[float],
    depreciation_schedule: DepreciationSchedule,
    tax_profile: TaxProfile,
) -> List[TaxResult]:
    """
    Build a full series of TaxResult objects over the project life.

    years:
        Project years (1-based).
    ebit_series:
        Annual EBIT values (length == len(years)).
    interest_series:
        Annual interest expense (gross coupon, from debt module).
    depreciation_schedule:
        Pre-computed depreciation schedule (length must cover years).
    tax_profile:
        Execution-ready TaxProfile.
    """
    if not (
        len(years)
        == len(ebit_series)
        == len(interest_series)
        == len(depreciation_schedule.annual_amounts)
    ):
        raise ValueError("Mismatched lengths in tax series inputs")

    results: List[TaxResult] = []
    carried_losses = 0.0

    for idx, year in enumerate(years):
        tax_result = calculate_tax(
            year=year,
            ebit=ebit_series[idx],
            interest_expense=interest_series[idx],
            depreciation=depreciation_schedule.annual_amounts[idx],
            tax_profile=tax_profile,
            prior_year_losses=carried_losses,
        )
        results.append(tax_result)
        carried_losses = tax_result.carried_forward_losses

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
