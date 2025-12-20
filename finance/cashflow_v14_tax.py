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
            raise ValueError(
                f"tax.corporate_tax_rate_pct must be 0-100, got {pct}"
            )
        
        # Convert percentage to decimal
        # Example: 30.0 -> 0.30
        return pct / 100.0
    
    # Neither format found - fail fast
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
        
        Mypy Justification
        ------------------
        # type: ignore[arg-type] annotations are used for TaxConfig() constructor
        because:
        - YAML dict values have type Any
        - Explicit casts narrow types (e.g., int(_require_key(...)))
        - Runtime validation in _validate() ensures correctness
        - Alternative would be complex type guards for each field
        
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
        # Note: All values are explicitly cast above, safe for dataclass
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


# NOTE: Rest of file (TaxProfile, DepreciationSchedule, TaxResult, etc.) 
# remains unchanged from original implementation.
# This update focuses on type safety in the configuration layer.

__all__ = [
    "TaxConfig",
    # "TaxProfile",  # Commented out - not shown in excerpt
    # "TaxResult",
    # "DepreciationSchedule",
    # "build_tax_profile",
    # "build_tax_series",
    # "calculate_tax",
]
