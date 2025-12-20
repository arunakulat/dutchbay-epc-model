"""
Phase 2 Refactoring: Tax Profile Module (CCCDIR / CASPER / CESSPIT / GWTF)

This module provides a clean, configuration-driven tax engine for DutchBay v14.

**CONSOLIDATED MODULE** (v14.2+)
---------------------------------
This module consolidates:
- Phase 2 TaxConfig (from cashflow_v14_tax.py)
- Complete execution engine (from dutchbay_finmodel/tax_profile.py)
- Wave 2 type safety enhancements

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

- Type Safety (Wave 2):
  * Explicit type casts with validation
  * Mypy justifications for all type: ignore comments
  * Enhanced docstrings with type narrowing strategy

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

from __future__ import annotations

import warnings
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


def _get_tax_rate_with_compat(tax: Mapping[str, Any]) -> float:
    """
    Extract tax rate with backward compatibility and explicit type narrowing.

    Type Safety Strategy
    --------------------
    This function accepts untyped YAML dict (Mapping[str, Any]) and returns
    a validated float in range [0.0, 1.0]. Type narrowing is achieved through:

    1. Explicit float() cast on YAML value (may be int, float, or string)
    2. Runtime range validation (raises ValueError if out of bounds)
    3. Return type annotation guarantees float to caller

    Mypy Justification
    ------------------
    The explicit cast from Any -> float is safe because:
    - Runtime validation ensures correct range [0.0, 1.0]
    - ValueError raised immediately if conversion fails
    - All code paths return validated float or raise

    Backward Compatibility Layer
    -----------------------------
    CANONICAL: tax.corporate_tax_rate (decimal 0.0-1.0)
        - Preferred format for v14+
        - Direct usage, no conversion needed

    DEPRECATED: tax.corporate_tax_rate_pct (percentage 0-100)
        - Legacy format from v13 and earlier
        - Converted to decimal via division by 100.0
        - Will be removed in v15

    Parameters
    ----------
    tax : Mapping[str, Any]
        Untyped YAML tax configuration section.

    Returns
    -------
    float
        Tax rate as decimal in range [0.0, 1.0].
        Example: 0.30 for 30% tax rate.

    Raises
    ------
    KeyError
        If neither tax.corporate_tax_rate nor tax.corporate_tax_rate_pct exists.
    ValueError
        If tax rate value is outside valid range.
    TypeError
        If tax rate value cannot be converted to float.

    Examples
    --------
    >>> _get_tax_rate_with_compat({"corporate_tax_rate": 0.30})
    0.3

    >>> _get_tax_rate_with_compat({"corporate_tax_rate_pct": 30})
    0.3

    >>> _get_tax_rate_with_compat({"corporate_tax_rate": 1.5})
    ValueError: tax.corporate_tax_rate must be decimal 0.0-1.0, got 1.5
    """
    # Try canonical format first (decimal 0.0-1.0)
    if "corporate_tax_rate" in tax:
        # Explicit type cast: Any -> float
        # Safe because: runtime validation ensures correct range
        rate: float = float(tax["corporate_tax_rate"])

        # Type narrowing: validate range [0.0, 1.0]
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be decimal 0.0-1.0, got {rate}"
            )
        return rate

    # Fall back to deprecated percentage format (0-100)
    if "corporate_tax_rate_pct" in tax:
        warnings.warn(
            "tax.corporate_tax_rate_pct is deprecated. "
            "Use tax.corporate_tax_rate (decimal) instead. "
            "This will be removed in v15.",
            DeprecationWarning,
            stacklevel=3,
        )

        # Explicit type cast: Any -> float
        # Safe because: runtime validation + conversion to decimal
        pct: float = float(tax["corporate_tax_rate_pct"])

        # Type narrowing: validate percentage range [0.0, 100.0]
        if not (0.0 <= pct <= 100.0):
            raise ValueError(f"tax.corporate_tax_rate_pct must be 0-100, got {pct}")

        # Convert percentage to decimal
        # Example: 30.0 -> 0.30
        return pct / 100.0

    # Neither format found - fail fast
    raise KeyError(
        "Missing required YAML key: tax.corporate_tax_rate "
        "(or deprecated tax.corporate_tax_rate_pct)"
    )


# ===========================================================================
# CONFIGURATION LAYER - Maps 1:1 to YAML
# ===========================================================================


@dataclass(frozen=True)
class TaxConfig:
    """
    YAML-level tax configuration (contract-first).

    This is an exact mirror of the `tax` block in scenario YAML. It does not
    contain derived values like per-year depreciation or holiday maps.

    Type Safety
    -----------
    All fields are strongly typed with runtime validation in _validate().
    The from_yaml() classmethod safely converts untyped YAML dict to typed
    dataclass through explicit casts and validation.
    """

    corporate_tax_rate: float  # Decimal 0.0-1.0 (e.g., 0.30 for 30%)
    depreciation_method: str  # "straight_line", "accelerated", or "none"
    depreciation_start_year: int  # Year index (1-based)
    depreciation_years: int  # Total depreciation period
    enhanced_allowance_applies: bool  # Enhanced capital allowance flag
    enhanced_capital_allowance_pct: float  # Multiplier (e.g., 1.5 for 150%)
    loss_carryforward_years: int  # Max years to carry forward losses
    tax_holiday_start_year: int  # Year index (1-based)
    tax_holiday_years: int  # Duration of tax holiday

    # Interest WHT (AIT) controls
    wht_on_interest_to_nonresidents: float  # Decimal 0.0-1.0
    wht_on_interest_enabled: bool  # Enable/disable WHT
    wht_gross_up: bool  # Gross up interest for WHT

    # Optional, for regimes where interest is not deductible (default: True)
    interest_deductibility: bool = True

    @classmethod
    def from_yaml(cls, cfg: Mapping[str, Any]) -> "TaxConfig":
        """
        Build TaxConfig from the full scenario dict (expects `tax` section).

        Type Safety Strategy
        --------------------
        Converts untyped YAML dict to strongly-typed TaxConfig through:
        1. Explicit type casts (int(), float(), bool(), str())
        2. Runtime validation in _validate()
        3. Fail-fast on missing or invalid keys

        Parameters
        ----------
        cfg : Mapping[str, Any]
            Full scenario configuration dict with 'tax' section.

        Returns
        -------
        TaxConfig
            Validated, frozen tax configuration.

        Raises
        ------
        KeyError
            If required YAML keys are missing.
        ValueError
            If values are outside valid ranges.
        """
        tax = _require_section(cfg, "tax")

        # Required keys with backward compatibility and explicit type narrowing
        corporate_tax_rate = _get_tax_rate_with_compat(tax)

        # Explicit type casts for all config parameters
        # Safe because: _require_key ensures key exists, cast validates type
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

        # Construct validated config
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
        """
        Validate basic ranges and consistency.

        Type Safety
        -----------
        Runtime validation ensures all values are within expected ranges,
        providing additional type safety beyond static type hints.

        Raises
        ------
        ValueError
            If any field value is outside valid range or logically inconsistent.
        """
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


# ===========================================================================
# EXECUTION LAYER - Derived from TaxConfig for runtime calculations
# ===========================================================================


@dataclass(frozen=True)
class TaxProfile:
    """
    Execution-ready tax profile for annual calculations.

    This is derived from TaxConfig + DepreciationSchedule and holds only the
    values needed in the per-year engine (calculate_tax).

    Type Safety
    -----------
    All fields validated in __post_init__. Used by calculate_tax() which
    expects strongly-typed, validated configuration.
    """

    tax_rate: float  # Corporate tax rate (decimal 0.0-1.0)
    interest_deductibility: bool  # Whether interest reduces taxable income
    depreciation_method: str  # Depreciation method used
    depreciation_schedule: List[float]  # Annual depreciation amounts
    allowable_losses_carryforward: bool  # Loss carryforward enabled
    withholding_tax_rate: float  # Interest WHT rate (decimal 0.0-1.0)
    tax_holidays_by_year: Dict[int, bool]  # {year: is_holiday}

    def __post_init__(self) -> None:
        """Validate execution-ready profile."""
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

        Parameters
        ----------
        capex_lkr:
            Total capital expenditure (LKR).
        useful_life:
            Depreciation period (years).
        project_life:
            Project economic life (years).

        Returns
        -------
        DepreciationSchedule
            Pre-computed schedule with annual amounts, accumulated, and book values.

        Raises
        ------
        ValueError
            If useful_life <= 0.
        """
        if useful_life <= 0:
            raise ValueError("useful_life must be > 0 for straight_line")

        annual_depr: float = capex_lkr / useful_life

        annual_amounts: List[float] = []
        accumulated: List[float] = []
        book_values: List[float] = []
        acc: float = 0.0

        for year in range(1, project_life + 1):
            if year <= useful_life:
                depr = annual_depr
            else:
                depr = 0.0
            annual_amounts.append(depr)
            acc += depr
            accumulated.append(acc)
            bv: float = max(capex_lkr - acc, 0.0)
            book_values.append(bv)

        return DepreciationSchedule(
            method="straight_line",
            capex_base=capex_lkr,
            useful_life_years=useful_life,
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )


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


# ===========================================================================
# BUILDERS - Convert TaxConfig to execution-ready TaxProfile
# ===========================================================================


def build_tax_holiday_map(
    config: TaxConfig,
    project_life_years: int,
) -> Dict[int, bool]:
    """
    Build a {year: is_holiday} map from TaxConfig.

    Parameters
    ----------
    config : TaxConfig
        Tax configuration with holiday parameters.
    project_life_years : int
        Total project life to generate map for.

    Returns
    -------
    Dict[int, bool]
        Mapping of year (1-based) to whether it's a tax holiday year.

    Examples
    --------
    >>> config = TaxConfig(..., tax_holiday_start_year=2, tax_holiday_years=3, ...)
    >>> build_tax_holiday_map(config, 5)
    {1: False, 2: True, 3: True, 4: True, 5: False}
    """
    holidays: Dict[int, bool] = {}
    start: int = config.tax_holiday_start_year
    end: int = start + config.tax_holiday_years - 1

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

    Parameters
    ----------
    config : TaxConfig
        YAML-level tax configuration.
    depreciation_schedule : DepreciationSchedule
        Pre-computed depreciation schedule.
    project_life_years : int
        Total project life (for tax holiday map).

    Returns
    -------
    TaxProfile
        Execution-ready tax profile for calculate_tax() engine.

    Notes
    -----
    - Loss carryforward enabled if config.loss_carryforward_years > 0
    - WHT rate = 0.0 if wht_on_interest_enabled is False
    - Tax holidays pre-computed for O(1) yearly lookup
    """
    tax_holidays: Dict[int, bool] = build_tax_holiday_map(config, project_life_years)

    # Allowable losses carryforward: enabled if horizon > 0
    # Expiry window (25y, etc.) can be layered in later if required
    allow_losses: bool = config.loss_carryforward_years > 0

    # Withholding tax is modelled as a separate cash outflow
    # It does not reduce taxable income (CIT) directly in this engine
    wht_rate: float = (
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


# ===========================================================================
# TAX ENGINE - Per-year and multi-year calculations
# ===========================================================================


def calculate_tax(
    year: int,
    ebit: float,
    interest_expense: float,
    depreciation: float,
    tax_profile: TaxProfile,
    prior_year_losses: float = 0.0,
) -> TaxResult:
    """
    Calculate corporate tax and WHT for a single year.

    Logic
    -----
    1. Determine if year is within a tax holiday.
    2. Start from EBIT.
    3. Deduct interest expense if deductible.
    4. Deduct depreciation.
    5. Apply prior-year loss carryforward (no expiry in this engine).
    6. Calculate CIT on positive taxable income only.
    7. Compute interest WHT as a separate cash outflow (no offset).
    8. Track updated loss carryforward.

    Parameters
    ----------
    year : int
        Project year (1-based).
    ebit : float
        Earnings before interest and tax (LKR).
    interest_expense : float
        Debt interest expense (gross coupon, LKR).
    depreciation : float
        Depreciation deduction for this year (LKR).
    tax_profile : TaxProfile
        Execution-ready tax configuration.
    prior_year_losses : float, optional
        Losses carried forward from prior year (default: 0.0).

    Returns
    -------
    TaxResult
        Immutable tax calculation result with all components.

    Notes
    -----
    - Tax holiday: tax_liability = 0.0 regardless of taxable income
    - Negative taxable income tracked as carried_forward_losses
    - WHT computed independently of CIT
    - Effective rate guards against division by zero (ebit = 0)
    """
    # 1) Holiday flag
    is_holiday: bool = tax_profile.tax_holidays_by_year.get(year, False)

    # 2) Start from EBIT
    taxable: float = ebit

    # 3) Interest deductibility
    if tax_profile.interest_deductibility:
        taxable -= interest_expense

    # 4) Depreciation
    taxable -= depreciation

    # 5) Prior-year losses
    carried_forward: float = 0.0
    if tax_profile.allowable_losses_carryforward and prior_year_losses > 0.0:
        loss_offset: float = min(prior_year_losses, max(taxable, 0.0))
        taxable -= loss_offset
        carried_forward = prior_year_losses - loss_offset

    # 6) CIT computation (no negative taxable income)
    taxable_income: float = max(taxable, 0.0)

    if is_holiday:
        tax_liability: float = 0.0
    else:
        tax_liability = taxable_income * tax_profile.tax_rate

    # New losses if taxable is negative this year
    new_losses: float = max(-taxable, 0.0) + carried_forward

    # Effective rate
    if ebit > 0.0:
        effective_rate: float = tax_liability / ebit
    else:
        effective_rate = 0.0

    # 7) Interest WHT (AIT) – separate from CIT
    wht_on_interest: float = interest_expense * tax_profile.withholding_tax_rate

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

    Parameters
    ----------
    years : Sequence[int]
        Project years (1-based).
    ebit_series : Sequence[float]
        Annual EBIT values (length == len(years)).
    interest_series : Sequence[float]
        Annual interest expense (gross coupon, from debt module).
    depreciation_schedule : DepreciationSchedule
        Pre-computed depreciation schedule (length must cover years).
    tax_profile : TaxProfile
        Execution-ready TaxProfile.

    Returns
    -------
    List[TaxResult]
        Complete tax calculation results for all years.

    Raises
    ------
    ValueError
        If input sequences have mismatched lengths.

    Notes
    -----
    - Loss carryforward is tracked year-over-year
    - Each year's calculation depends on prior year's losses
    - WHT computed independently per year
    """
    if not (
        len(years)
        == len(ebit_series)
        == len(interest_series)
        == len(depreciation_schedule.annual_amounts)
    ):
        raise ValueError("Mismatched lengths in tax series inputs")

    results: List[TaxResult] = []
    carried_losses: float = 0.0

    for idx, year in enumerate(years):
        tax_result: TaxResult = calculate_tax(
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
    "build_tax_holiday_map",
]
