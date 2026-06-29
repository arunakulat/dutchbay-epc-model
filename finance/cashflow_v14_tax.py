"""Tax Profile Module for DutchBay v14 cashflow.

Configuration-driven corporate tax, depreciation, loss carry-forward and
interest withholding-tax handling for the v14 CFADS engine. This is the single
canonical tax engine (the parallel ``finance/tax_v14.py`` wrapper, which carried
contradictory silent defaults, was deleted in #483 / FIN-1).

Tax scope — what the model includes vs excludes (Sri Lanka regime, #483 / FIN-4):

* MODELLED: corporate income tax (CIT, 30%), straight-line depreciation with a
  plant/civil split, tax-loss carry-forward (6-year SL window, vintage-tracked),
  withholding tax on interest to non-residents (10%) and on dividends (15%, on the
  equity path), and the Social Services Contribution Levy (SSCL, 2.5% of revenue —
  booked as ``social_levy_lkr`` in the cashflow via ``statutory.social_services_levy_pct``).
* EXCLUDED — VAT (18%): deliberately NOT modelled as a project P&L cost. VAT on a
  BOO IPP's energy sales is a pass-through — output VAT is collected from the offtaker
  and remitted, input VAT on capex/opex is recoverable — so at steady state it is
  cashflow-neutral to the SPV and would only distort the lender economics if booked as
  a cost. (Any genuine VAT timing/cash-lock effect during construction is a working-
  capital refinement, not an operating-cashflow tax, and is out of scope here.)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: A tax-loss carry-forward ledger: an immutable tuple of (origin_year, amount)
#: vintages. Tracking vintages (not a single scalar) lets losses EXPIRE after the
#: statutory carry-forward window (Sri Lanka: 6 years) and be preserved through
#: tax-holiday years instead of being silently consumed.
LossVintages = Tuple[Tuple[int, float], ...]


def _lookup_case_insensitive(section: Mapping[str, Any], key: str) -> Any:
    """Return exact key first, then case-insensitive key, else None."""
    if key in section:
        return section[key]
    key_lower = key.lower()
    for existing_key, value in section.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def _require_section(cfg: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    """Return a named subsection or raise if missing.

    Resolution is exact first, then case-insensitive. This keeps canonical
    ``tax`` configs unchanged while accepting compact hand-authored ``Tax``
    dictionaries used by v14 lender-stack smoke tests.
    """
    section = _lookup_case_insensitive(cfg, name)
    if not isinstance(section, Mapping):
        raise KeyError(f"Missing required YAML section: {name}")
    return section


def _get_key_with_default(
    section: Mapping[str, Any], key: str, default: Any, type_cast: type = str
) -> Any:
    """Get a key from section with a default fallback."""
    value = _lookup_case_insensitive(section, key)
    if value is not None:
        return type_cast(value)
    return default


def _require_key(section: Mapping[str, Any], key: str, ctx: str) -> Any:
    """Return a required key from a section or raise with context."""
    value = _lookup_case_insensitive(section, key)
    if value is None:
        raise KeyError(f"Missing required YAML key: {ctx}.{key}")
    return value


def _opt_float(value: Any) -> Optional[float]:
    """Cast to float, or None when the key was absent."""
    return float(value) if value is not None else None


def _opt_int(value: Any) -> Optional[int]:
    """Cast to int, or None when the key was absent."""
    return int(value) if value is not None else None


def _get_tax_rate_with_compat(tax: Mapping[str, Any]) -> float:
    """Extract corporate tax rate from canonical or compact aliases."""
    canonical = _lookup_case_insensitive(tax, "corporate_tax_rate")
    if canonical is not None:
        rate = float(canonical)
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_tax_rate must be decimal 0.0-1.0, got {rate}"
            )
        return rate

    compact = _lookup_case_insensitive(tax, "corporate_rate")
    if compact is not None:
        rate = float(compact)
        if rate > 1.0:
            rate = rate / 100.0
        if not (0.0 <= rate <= 1.0):
            raise ValueError(
                f"tax.corporate_rate must be decimal 0.0-1.0 or percent 0-100, got {compact}"
            )
        return rate

    pct_value = _lookup_case_insensitive(tax, "corporate_tax_rate_pct")
    if pct_value is not None:
        warnings.warn(
            "tax.corporate_tax_rate_pct is deprecated. Use tax.corporate_tax_rate instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        pct = float(pct_value)
        if not (0.0 <= pct <= 100.0):
            raise ValueError(f"tax.corporate_tax_rate_pct must be 0-100, got {pct}")
        return pct / 100.0

    raise KeyError(
        "Missing required YAML key: tax.corporate_tax_rate "
        "(or compact tax.corporate_rate / deprecated tax.corporate_tax_rate_pct)"
    )


@dataclass(frozen=True)
class TaxConfig:
    corporate_tax_rate: float
    depreciation_method: str
    depreciation_start_year: int
    depreciation_years: int
    enhanced_allowance_applies: bool
    enhanced_capital_allowance_pct: float
    loss_carryforward_years: int
    tax_holiday_start_year: int
    tax_holiday_years: int
    wht_on_interest_to_nonresidents: float
    wht_on_interest_enabled: bool
    wht_gross_up: bool
    interest_deductibility: bool = True
    # Optional post-2025-regime fields — default-absent → legacy single-class mode.
    tax_holiday_route: str = (
        "none"  # "none" | "sdp" (descriptive; tax_holiday_years drives calc)
    )
    plant_capex_share: Optional[float] = (
        None  # set → split depreciation (plant vs civil)
    )
    plant_depreciation_years: Optional[int] = (
        None  # SL Class 2 plant & machinery = 5 yr
    )
    civil_depreciation_years: Optional[int] = (
        None  # SL Class 4 buildings/civils = 20 yr
    )

    def __post_init__(self) -> None:
        # enhanced_capital_allowance_pct is an explicit MULTIPLIER on the depreciable base
        # (1.0 = standard 100% allowance, 1.5 = a 150% enhanced allowance) — only applied
        # when enhanced_allowance_applies is true (see cashflow_v14.py). This is the SINGLE
        # live resolution point; validate here so a negative multiplier fails loud
        # regardless of construction path (the parallel CashflowParams resolver that once
        # carried this check fed a dead field and was removed).
        if self.enhanced_capital_allowance_pct < 0.0:
            raise ValueError(
                "tax.enhanced_capital_allowance_pct must be a non-negative multiplier "
                "(1.0 = standard 100% allowance, 1.5 = a 150% enhanced allowance); got "
                f"{self.enhanced_capital_allowance_pct}"
            )
        # Upper-bound sanity: the field is a MULTIPLIER, not a percent. A value > 3.0 is
        # almost certainly a percent-for-multiplier unit error (e.g. 150 meaning 1.5),
        # which would inflate the depreciable base ~100x and zero out tax for the whole
        # tenor. Real enhanced allowances are <= ~3.0 (300%); reject above that loudly.
        # Caught for ALL configs (not just applied ones) so a latent typo cannot lie
        # dormant until enhanced_allowance_applies flips to true.
        if self.enhanced_capital_allowance_pct > 3.0:
            raise ValueError(
                "tax.enhanced_capital_allowance_pct looks like a PERCENT, not a multiplier:"
                f" got {self.enhanced_capital_allowance_pct} (> 3.0). Use the multiplier "
                "convention: 100% allowance = 1.0, 150% = 1.5."
            )

    @classmethod
    def from_yaml(cls, cfg: Mapping[str, Any]) -> "TaxConfig":
        """Build TaxConfig from the full scenario dict.

        CESSPIT / R22 — schema-strict, no hidden defaults: every tax field is
        REQUIRED and a missing key fails fast with ``KeyError: ... tax.<key>``
        rather than silently substituting a default. The single optional field
        is ``interest_deductibility`` (documented default ``True``).
        """
        tax = _require_section(cfg, "tax")

        # Required + range-validated; canonical/compact/deprecated aliases are
        # accepted, but absence raises (no silent default fallback).
        corporate_tax_rate = _get_tax_rate_with_compat(tax)

        obj = cls(
            corporate_tax_rate=corporate_tax_rate,
            depreciation_method=str(_require_key(tax, "depreciation_method", "tax")),
            depreciation_start_year=int(
                _require_key(tax, "depreciation_start_year", "tax")
            ),
            depreciation_years=int(_require_key(tax, "depreciation_years", "tax")),
            enhanced_allowance_applies=bool(
                _require_key(tax, "enhanced_allowance_applies", "tax")
            ),
            enhanced_capital_allowance_pct=float(
                _require_key(tax, "enhanced_capital_allowance_pct", "tax")
            ),
            loss_carryforward_years=int(
                _require_key(tax, "loss_carryforward_years", "tax")
            ),
            tax_holiday_start_year=int(
                _require_key(tax, "tax_holiday_start_year", "tax")
            ),
            tax_holiday_years=int(_require_key(tax, "tax_holiday_years", "tax")),
            wht_on_interest_to_nonresidents=float(
                _require_key(tax, "wht_on_interest_to_nonresidents", "tax")
            ),
            wht_on_interest_enabled=bool(
                _require_key(tax, "wht_on_interest_enabled", "tax")
            ),
            wht_gross_up=bool(_require_key(tax, "wht_gross_up", "tax")),
            interest_deductibility=bool(
                _lookup_case_insensitive(tax, "interest_deductibility")
                if _lookup_case_insensitive(tax, "interest_deductibility") is not None
                else True
            ),
            # Optional post-2025-regime fields — absent → legacy single-class mode.
            tax_holiday_route=str(
                _lookup_case_insensitive(tax, "tax_holiday_route") or "none"
            ),
            plant_capex_share=_opt_float(
                _lookup_case_insensitive(tax, "plant_capex_share")
            ),
            plant_depreciation_years=_opt_int(
                _lookup_case_insensitive(tax, "plant_depreciation_years")
            ),
            civil_depreciation_years=_opt_int(
                _lookup_case_insensitive(tax, "civil_depreciation_years")
            ),
        )
        obj._validate()
        return obj

    def _validate(self) -> None:
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
        if self.tax_holiday_route not in ("none", "sdp"):
            raise ValueError(
                f"tax.tax_holiday_route must be 'none' or 'sdp', got {self.tax_holiday_route}"
            )
        if self.plant_capex_share is not None:
            if not (0.0 <= self.plant_capex_share <= 1.0):
                raise ValueError("tax.plant_capex_share must be in [0,1]")
            if not self.plant_depreciation_years or self.plant_depreciation_years < 1:
                raise ValueError(
                    "tax.plant_depreciation_years must be >= 1 when plant_capex_share is set"
                )
            if not self.civil_depreciation_years or self.civil_depreciation_years < 1:
                raise ValueError(
                    "tax.civil_depreciation_years must be >= 1 when plant_capex_share is set"
                )


@dataclass(frozen=True)
class TaxProfile:
    tax_rate: float
    interest_deductibility: bool
    depreciation_method: str
    depreciation_schedule: List[float]
    allowable_losses_carryforward: bool
    withholding_tax_rate: float
    tax_holidays_by_year: Dict[int, bool]
    #: Statutory carry-forward window in years (Sri Lanka: 6). ``0`` means no cap
    #: (unlimited carry — the historical behaviour, kept as the default so direct
    #: TaxProfile constructions stay byte-identical). A loss originating in year ``y``
    #: can offset income through year ``y + loss_carryforward_years``.
    loss_carryforward_years: int = 0

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


@dataclass(frozen=True)
class DepreciationSchedule:
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
        start_year: int = 1,
    ) -> "DepreciationSchedule":
        if useful_life <= 0:
            raise ValueError("useful_life must be > 0 for straight_line")
        if start_year < 1:
            raise ValueError("depreciation start_year must be >= 1")

        annual_depr = capex_lkr / useful_life
        annual_amounts: List[float] = []
        accumulated: List[float] = []
        book_values: List[float] = []
        acc = 0.0

        # Depreciation runs for ``useful_life`` years beginning at ``start_year`` (1-based).
        # start_year=1 is the standard case and is byte-identical to ``year <= useful_life``.
        last_depr_year = start_year + useful_life - 1
        for year in range(1, project_life + 1):
            depr = annual_depr if start_year <= year <= last_depr_year else 0.0
            annual_amounts.append(depr)
            acc += depr
            accumulated.append(acc)
            book_values.append(max(capex_lkr - acc, 0.0))

        return DepreciationSchedule(
            method="straight_line",
            capex_base=capex_lkr,
            useful_life_years=useful_life,
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )

    @staticmethod
    def build_split_straight_line(
        total_capex: float,
        plant_capex_share: float,
        plant_useful_life: int,
        civil_useful_life: int,
        project_life: int,
        start_year: int = 1,
    ) -> "DepreciationSchedule":
        """Combined straight-line schedule for a split capex base.

        Splits ``total_capex`` into a plant/machinery component
        (``plant_capex_share``, depreciated over ``plant_useful_life``) and a
        civil-works component (the remainder, over ``civil_useful_life``), builds
        each straight-line, and sums them — modelling the Sri Lanka Fourth-Schedule
        asset-class split (plant & machinery 5 yr / buildings & civils 20 yr).
        """
        if not (0.0 <= plant_capex_share <= 1.0):
            raise ValueError("plant_capex_share must be in [0,1]")
        plant = DepreciationSchedule.build_straight_line(
            total_capex * plant_capex_share, plant_useful_life, project_life, start_year
        )
        civil = DepreciationSchedule.build_straight_line(
            total_capex * (1.0 - plant_capex_share),
            civil_useful_life,
            project_life,
            start_year,
        )
        annual_amounts = [
            p + c for p, c in zip(plant.annual_amounts, civil.annual_amounts)
        ]
        accumulated: List[float] = []
        acc = 0.0
        for amount in annual_amounts:
            acc += amount
            accumulated.append(acc)
        book_values = [max(total_capex - a, 0.0) for a in accumulated]
        return DepreciationSchedule(
            method="straight_line_split",
            capex_base=total_capex,
            useful_life_years=max(plant_useful_life, civil_useful_life),
            annual_amounts=annual_amounts,
            accumulated_depreciation=accumulated,
            book_value=book_values,
        )


@dataclass(frozen=True)
class TaxResult:
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
    #: The updated loss-vintage ledger to thread into the next year (empty for the
    #: legacy scalar path). ``carried_forward_losses`` is its running total.
    carried_forward_vintages: LossVintages = ()


def build_tax_holiday_map(
    config: TaxConfig,
    project_life_years: int,
) -> Dict[int, bool]:
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
    tax_holidays = build_tax_holiday_map(config, project_life_years)
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
        allowable_losses_carryforward=config.loss_carryforward_years > 0,
        loss_carryforward_years=config.loss_carryforward_years,
        withholding_tax_rate=wht_rate,
        tax_holidays_by_year=tax_holidays,
    )


def _apply_loss_vintages(
    year: int,
    pre_offset_taxable: float,
    is_holiday: bool,
    prior_vintages: Sequence[Tuple[int, float]],
    cap: int,
    allowable: bool,
) -> Tuple[float, LossVintages]:
    """Expire, (conditionally) offset, and update the loss-vintage ledger.

    Returns ``(taxable_after_offset, new_vintages)``. Vintages older than ``cap`` years
    expire before any offset (``cap <= 0`` means unlimited). A holiday year does NOT
    consume losses (the shield would be wasted — tax is 0 regardless). A year with
    negative pre-offset income adds a new vintage. Offsets are FIFO (oldest first).
    """
    if not allowable:
        return max(pre_offset_taxable, 0.0), ()
    live = [
        (oy, amt)
        for (oy, amt) in prior_vintages
        if amt > 0.0 and (cap <= 0 or (year - oy) <= cap)
    ]
    if pre_offset_taxable < 0.0:
        new = sorted(live) + [(year, -pre_offset_taxable)]
        return 0.0, tuple(new)
    if is_holiday:
        return pre_offset_taxable, tuple(sorted(live))
    budget = pre_offset_taxable
    remaining: List[Tuple[int, float]] = []
    for oy, amt in sorted(live):
        use = min(amt, budget)
        budget -= use
        leftover = amt - use
        if leftover > 1e-9:
            remaining.append((oy, leftover))
    return budget, tuple(remaining)


def calculate_tax(
    year: int,
    ebit: float,
    interest_expense: float,
    depreciation: float,
    tax_profile: TaxProfile,
    prior_year_losses: float = 0.0,
    prior_loss_vintages: Optional[Sequence[Tuple[int, float]]] = None,
) -> TaxResult:
    """Per-year tax. When ``prior_loss_vintages`` is supplied (the live path) losses are
    tracked per vintage so they EXPIRE after ``loss_carryforward_years`` and are PRESERVED
    through holiday years. When it is ``None`` the legacy scalar carry-forward applies
    (no expiry) — kept byte-identical for direct scalar callers."""
    is_holiday = tax_profile.tax_holidays_by_year.get(year, False)
    taxable = ebit
    if tax_profile.interest_deductibility:
        taxable -= interest_expense
    taxable -= depreciation

    new_vintages: LossVintages = ()
    if prior_loss_vintages is None:
        # Legacy scalar path (no expiry, consumes during holidays) — byte-identical.
        carried_forward = 0.0
        if tax_profile.allowable_losses_carryforward and prior_year_losses > 0.0:
            loss_offset = min(prior_year_losses, max(taxable, 0.0))
            taxable -= loss_offset
            carried_forward = prior_year_losses - loss_offset
        taxable_income = max(taxable, 0.0)
        new_losses = max(-taxable, 0.0) + carried_forward
    else:
        taxable_after, new_vintages = _apply_loss_vintages(
            year,
            taxable,
            is_holiday,
            prior_loss_vintages,
            tax_profile.loss_carryforward_years,
            tax_profile.allowable_losses_carryforward,
        )
        taxable_income = max(taxable_after, 0.0)
        new_losses = sum(amt for _, amt in new_vintages)

    tax_liability = 0.0 if is_holiday else taxable_income * tax_profile.tax_rate
    effective_rate = tax_liability / ebit if ebit > 0.0 else 0.0
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
        carried_forward_vintages=new_vintages,
    )


def build_tax_series(
    years: Sequence[int],
    ebit_series: Sequence[float],
    interest_series: Sequence[float],
    depreciation_schedule: DepreciationSchedule,
    tax_profile: TaxProfile,
) -> List[TaxResult]:
    if not (
        len(years)
        == len(ebit_series)
        == len(interest_series)
        == len(depreciation_schedule.annual_amounts)
    ):
        raise ValueError("Mismatched lengths in tax series inputs")

    results: List[TaxResult] = []
    carried_vintages: LossVintages = ()
    for idx, year in enumerate(years):
        tax_result = calculate_tax(
            year=year,
            ebit=ebit_series[idx],
            interest_expense=interest_series[idx],
            depreciation=depreciation_schedule.annual_amounts[idx],
            tax_profile=tax_profile,
            prior_loss_vintages=carried_vintages,
        )
        results.append(tax_result)
        carried_vintages = tax_result.carried_forward_vintages
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
