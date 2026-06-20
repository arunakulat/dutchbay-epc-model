from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields

from .cashflow_v14_contracts import CashflowParams
from .cashflow_v14_fx import _fx_curve
from .cashflow_v14_params import _build_cashflow_params, validate_parameters
from .cashflow_v14_production import (
    _apply_risk_haircut,
    _calculate_net_production,
    _calculate_opex_lkr,
    _calculate_revenue_lkr,
    _calculate_statutory_deductions,
)
from .cashflow_v14_tax import (
    DepreciationSchedule,
    TaxConfig,
    TaxProfile,
    TaxResult,
    build_tax_profile,
    build_tax_series,
    calculate_tax,
)
from .cashflow_v14_utils import as_float, get_nested

logger = logging.getLogger(__name__)

"""
Cash flow engine for DutchBay V14 (CFADS and annual rows).

This module is the **canonical** place where project CFADS is defined
for the v14 finance stack. It is designed to be:

- Lender-grade (DFI / World Bank / IFC compatible)
- Statute-aware for Sri Lanka BOI / Inland Revenue Act (interest shield,
  tax holidays, enhanced capital allowances)
- YAML-driven (scenarios feed a single config dict)
- Stable and schema-guard-friendly for the v14 pipeline.

Public surface
--------------

- validate_parameters(config) -> [] or raises ValueError
- build_annual_cfads(config, ...) -> list[float]
- build_annual_rows(config, ...) -> list[dict[str, float]]
- build_annual_rows_efficient(config, ...) -> list[dict[str, float]] (NEW: with loss carry-forward)
- calculate_single_year_cfads(params, ...) -> dict[str, float]

`build_annual_rows` is the primary feedstock for:

- debt_v14.plan_debt (DSCR / covenants)
- contracts_v14.build_cashflow_result_from_annual_rows (CashflowResult)

CFADS DEFINITION (v14)
----------------------

For each year t, this engine defines CFADS as:

cfads_final_lkr[t] =
    revenue_lkr
    - statutory_deductions
    - opex_lkr
    - tax_lkr(pretax_cfads, interest_shield, depreciation, loss_carryforward)
    - risk_haircut

This is the only definition that debt_v14 and the analytics stack are
allowed to rely on. Any alternative "CFADS" views must be derived from
the row-wise breakdown returned here.

Tax Engine (v14)
----------------

The new TaxProfile engine provides:

1. TaxConfig: YAML contract (immutable)
2. TaxProfile: Execution-ready config (with pre-computed depreciation schedule)
3. TaxResult: Per-year result (immutable)
4. build_tax_series: Batch processing with loss carry-forward tracking
5. calculate_tax: Per-year calculation (for single-year views)

Key improvements over v13:
- Loss carry-forward correctly accumulated across years
- Tax holiday years explicit (no ambiguity)
- Interest deductibility config-driven
- WHT separated from CIT (correct cash flow modeling)
- All tax parameters unified in TaxProfile (not scattered across calls)
"""

# =============================================================================
# Internal context preparation
# =============================================================================


def _prepare_cashflow_context(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]],
    capex_depreciable_lkr: Optional[float],
    interest_expense_series: Optional[List[float]],
) -> Tuple[
    Dict[str, Any],
    List[float],
    Optional[float],
    List[float],
    int,
    TaxProfile,
    DepreciationSchedule,
]:
    """
    Shared context builder for build_annual_cfads and build_annual_rows.

    Returns
    -------
    (params_dict, fx_curve_resolved, capex_depreciable_resolved,
     interest_series, years, tax_profile, depreciation_schedule)

    The TaxProfile and DepreciationSchedule are now built upfront and
    reused for all years, avoiding repeated computation and ensuring
    consistent loss carry-forward tracking.
    """
    # Validate parameters before expensive calculations
    validate_parameters(config)

    params_obj: CashflowParams = _build_cashflow_params(config)
    params_dict: Dict[str, Any] = asdict(params_obj)

    years = int(params_obj.project_life_years)

    if fx_curve is None:
        fx_curve_resolved = _fx_curve(config, years)
    else:
        fx_curve_resolved = list(fx_curve)

    # Ensure we have at least `years` FX points; extend with last known.
    if len(fx_curve_resolved) < years and fx_curve_resolved:
        fx_curve_resolved = fx_curve_resolved + [fx_curve_resolved[-1]] * (
            years - len(fx_curve_resolved)
        )
    elif not fx_curve_resolved:
        fx_curve_resolved = _fx_curve(config, years)

    # Depreciable capex base in LKR – explicit tax base takes precedence.
    capex_dep_resolved = capex_depreciable_lkr

    if capex_dep_resolved is None:
        # 1) Explicit tax base if provided
        dep_lkr = as_float(get_nested(config, ["tax", "depreciable_capex_lkr"], None))

        if dep_lkr is None:
            dep_lkr = as_float(get_nested(config, ["tax", "dep_base_lkr"], None))

        if dep_lkr is not None:
            capex_dep_resolved = dep_lkr
        else:
            # 2) Project-wide LKR capex
            capex_lkr = as_float(get_nested(config, ["capex", "lkr_total"], None))

            if capex_lkr is not None:
                capex_dep_resolved = capex_lkr
            else:
                # 3) USD capex translated at year-0 FX
                capex_usd = as_float(get_nested(config, ["capex", "usd_total"], None))

                if capex_usd is not None:
                    capex_dep_resolved = capex_usd * fx_curve_resolved[0]

    # Interest series alignment
    if interest_expense_series is None:
        interest_series = [0.0] * years
    else:
        interest_series = list(interest_expense_series)

    # Pad or trim to project life
    if len(interest_series) < years:
        interest_series = interest_series + [0.0] * (years - len(interest_series))
    elif len(interest_series) > years:
        interest_series = interest_series[:years]

    # === NEW: Build TaxConfig and TaxProfile upfront ===
    # This avoids repeated computation and ensures consistent tax modeling
    # across all years (especially important for loss carry-forward).

    tax_config = TaxConfig.from_yaml(config)

    # Build depreciation schedule
    _split_mode = tax_config.plant_capex_share is not None
    if capex_dep_resolved is not None and (
        _split_mode or tax_config.depreciation_years > 0
    ):
        # Apply enhancement factor if enabled (to the whole base, before any split)
        capex_for_depreciation = capex_dep_resolved * (
            tax_config.enhanced_capital_allowance_pct
            if tax_config.enhanced_allowance_applies
            else 1.0
        )
        if _split_mode:
            # Post-2025 SL Fourth-Schedule split: plant (short life) + civils (long life).
            # TaxConfig.validate guarantees all three fields are populated whenever
            # plant_capex_share is set (the _split_mode trigger); re-assert here so the
            # contract is explicit and fail-loud at the call site (CESSPIT).
            plant_share = tax_config.plant_capex_share
            plant_life = tax_config.plant_depreciation_years
            civil_life = tax_config.civil_depreciation_years
            if plant_share is None or plant_life is None or civil_life is None:
                raise ValueError(
                    "Split-depreciation mode requires tax.plant_capex_share, "
                    "tax.plant_depreciation_years and tax.civil_depreciation_years "
                    "to all be set."
                )
            depreciation_schedule = DepreciationSchedule.build_split_straight_line(
                total_capex=capex_for_depreciation,
                plant_capex_share=plant_share,
                plant_useful_life=plant_life,
                civil_useful_life=civil_life,
                project_life=years,
            )
        else:
            depreciation_schedule = DepreciationSchedule.build_straight_line(
                capex_lkr=capex_for_depreciation,
                useful_life=tax_config.depreciation_years,
                project_life=years,
            )
    else:
        # No depreciation: all-zero schedule
        depreciation_schedule = DepreciationSchedule.build_straight_line(
            capex_lkr=0.0,
            useful_life=1,
            project_life=years,
        )

    # Build execution-ready TaxProfile
    tax_profile = build_tax_profile(
        config=tax_config,
        depreciation_schedule=depreciation_schedule,
        project_life_years=years,
    )

    return (
        params_dict,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
    )


# =============================================================================
# Public CFADS API
# =============================================================================


def calculate_single_year_cfads(
    params: Dict[str, Any],
    fx_rate: float,
    year: int,
    tax_profile: TaxProfile,
    depreciation_schedule: DepreciationSchedule,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
    prior_year_losses: float = 0.0,
) -> Dict[str, float]:
    """
    Compute detailed CFADS breakdown for a single year.

    Parameters
    ----------
    params :
        Normalized parameter dict from _extract_parameters.

    fx_rate :
        LKR per USD FX rate for the given year.

    year :
        Project year (1-based, matching tax_profile.tax_holidays_by_year keys).

    tax_profile :
        Pre-built TaxProfile with unified tax config and depreciation schedule.

    depreciation_schedule :
        Pre-computed DepreciationSchedule (includes annual amounts and metadata).

    interest_expense_lkr :
        Interest expense in LKR for the year.

    verbose :
        If True, log the per-year CFADS breakdown.

    prior_year_losses :
        Losses carried from prior year (for multi-year loss tracking).

    Returns
    -------
    dict[str, float]
        Per-year breakdown, including:
        - `cfads_final_lkr`: Canonical CFADS (used by debt_v14)
        - `effective_tax_rate`: Actual tax rate (for transparency)
        - `tax_holiday_applied`: 1.0 or 0.0 (for audit)
        - `carried_forward_losses`: Losses for next year (for tracking)
        - `wht_on_interest`: Withholding tax on interest AIT (for lender reporting)
    """

    # --- Production and revenue ------------------------------------------------
    # Year is 1-based; production calculation expects 0-based index
    year_index = year - 1

    gross_kwh, net_kwh = _calculate_net_production(
        float(params["capacity_mw"]),
        float(params["capacity_factor"]),
        float(params["degradation"]),
        float(params["grid_loss_pct"]),
        year_index,
    )

    revenue_lkr = _calculate_revenue_lkr(net_kwh, float(params["tariff_lkr_per_kwh"]))

    # --- Statutory charges and OPEX -------------------------------------------
    statutory = _calculate_statutory_deductions(
        revenue_lkr,
        float(params["success_fee_pct"]),
        float(params["env_surcharge_pct"]),
        float(params["social_levy_pct"]),
    )

    # OpEx escalates in USD at opex_escalation_pct/yr (O&M inflation), THEN is
    # translated to LKR at the per-year FX rate — so the LKR cost carries both the
    # inflation and the FX-depreciation effect. year_index is 0-based (ops year 1 = base).
    opex_escalation = float(params.get("opex_escalation_pct", 0.0))
    opex_usd_year = float(params["opex_usd_per_year"]) * (1.0 + opex_escalation) ** year_index
    opex_lkr = _calculate_opex_lkr(opex_usd_year, fx_rate)

    # For this engine, EBITDA and EBIT coincide (no other non-cash items)
    # Depreciation is NOT in EBIT; it's a tax deduction
    ebitda_lkr = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr
    ebit = ebitda_lkr

    # --- Tax and depreciation (with loss carry-forward) ----------------------
    # Use new calculate_tax with unified TaxProfile
    depreciation_for_year = depreciation_schedule.annual_amounts[year_index]

    tax_result: TaxResult = calculate_tax(
        year=year,  # 1-based (matches tax_profile.tax_holidays_by_year keys)
        ebit=ebit,
        interest_expense=interest_expense_lkr,
        depreciation=depreciation_for_year,
        tax_profile=tax_profile,
        prior_year_losses=prior_year_losses,
    )

    tax = tax_result.tax_liability
    total_depr = tax_result.depreciation
    wht_on_interest = tax_result.wht_on_interest

    posttax_cfads = ebit - tax

    # --- Risk haircut on post-tax CFADS (v14 definition) ----------------------
    risk_haircut_pct = float(params.get("risk_haircut_pct", 0.0))

    cfads_final_lkr = _apply_risk_haircut(posttax_cfads, risk_haircut_pct)

    risk_haircut_amount = posttax_cfads - cfads_final_lkr

    # --- USD views ------------------------------------------------------------
    if fx_rate > 0.0:
        revenue_usd = revenue_lkr / fx_rate
        cfads_usd = cfads_final_lkr / fx_rate
    else:
        revenue_usd = 0.0
        cfads_usd = 0.0

    result: Dict[str, float] = {
        "year": float(year),
        "gross_kwh": gross_kwh,
        "grid_loss": gross_kwh - net_kwh,
        "net_kwh": net_kwh,
        "revenue_lkr": revenue_lkr,
        "success_fee_lkr": statutory["success_fee"],
        "env_surcharge_lkr": statutory["environmental_surcharge"],
        "social_levy_lkr": statutory["social_services_levy"],
        "total_statutory_deductions_lkr": statutory["total_statutory_deductions"],
        "opex_usd": opex_usd_year,  # escalated (year-1 base x (1+esc)^year_index)
        "fx_rate": fx_rate,
        "opex_lkr": opex_lkr,
        "ebitda_lkr": ebitda_lkr,
        "pretax_cfads_lkr": ebit,
        "total_depreciation_lkr": total_depr,
        "interest_expense_lkr": interest_expense_lkr,
        "taxable_income_lkr": tax_result.taxable_income,
        "tax_lkr": tax,
        "posttax_cfads_lkr": posttax_cfads,
        "risk_haircut_pct": risk_haircut_pct,
        "risk_haircut_amount_lkr": risk_haircut_amount,
        # Canonical CFADS after haircut (existing name, used by build_annual_rows logging, debt, etc.)
        "cfads_final_lkr": cfads_final_lkr,
        # Alias for readability in exports / dashboards
        "cfads_risk_adjusted_lkr": cfads_final_lkr,
        "revenue_usd": revenue_usd,
        "cfads_usd": cfads_usd,
        # === NEW: Enhanced transparency fields ===
        "effective_tax_rate": tax_result.effective_tax_rate,
        "tax_holiday_applied": float(tax_result.tax_holiday_applied),  # 1.0 or 0.0
        "carried_forward_losses": tax_result.carried_forward_losses,
        "wht_on_interest": wht_on_interest,
    }

    if verbose:
        logger.info("Year %d CFADS: %s", year, result)

    return result


def build_annual_cfads(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    verbose: bool = False,
) -> List[float]:
    """
    Return list of CFADS (LKR) for each project year.

    This is the primary numeric surface used by debt_v14 and covenant tests.
    """

    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
    )

    cfads_list: List[float] = []
    carried_losses = 0.0

    for year in range(1, years + 1):
        year_index = year - 1
        fx_rate = fx_curve_resolved[year_index]
        interest_lkr = interest_series[year_index]

        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            tax_profile=tax_profile,
            depreciation_schedule=depreciation_schedule,
            interest_expense_lkr=interest_lkr,
            verbose=verbose,
            prior_year_losses=carried_losses,
        )

        cfads_list.append(result["cfads_final_lkr"])
        carried_losses = result["carried_forward_losses"]

    if cfads_list:
        logger.info(
            "Calculated CFADS for %d years, range: %.0f to %.0f",
            years,
            min(cfads_list),
            max(cfads_list),
        )
    else:
        logger.info("Calculated CFADS for 0 years")

    return cfads_list


def build_annual_rows(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    """
    Return list of per-year breakdown rows including CFADS in LKR and USD.

    This is the canonical *row-wise* surface for:

    - debt_v14.plan_debt (DSCR / covenants)
    - CashflowResult (via contracts_v14)
    - analytics exports and dashboards.

    NOTE: This function now correctly tracks loss carry-forward across years.
    """

    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
    )

    rows: List[Dict[str, float]] = []
    carried_losses = 0.0

    for year in range(1, years + 1):
        year_index = year - 1
        fx_rate = fx_curve_resolved[year_index]
        interest_lkr = interest_series[year_index]

        row = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            tax_profile=tax_profile,
            depreciation_schedule=depreciation_schedule,
            interest_expense_lkr=interest_lkr,
            verbose=False,
            prior_year_losses=carried_losses,
        )

        rows.append(row)
        carried_losses = row["carried_forward_losses"]

    if rows:
        logger.info(
            "Built annual cashflow rows for %d years, CFADS range: %.0f to %.0f, "
            "with loss carry-forward tracking",
            years,
            min(r["cfads_final_lkr"] for r in rows),
            max(r["cfads_final_lkr"] for r in rows),
        )
    else:
        logger.info("Built annual cashflow rows for 0 years")

    return rows


def build_annual_rows_efficient(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    """
    Build annual rows using batch tax calculation (build_tax_series).

    This version processes all taxes at once using build_tax_series(),
    ensuring consistent loss carry-forward across the entire project life.
    It is slightly more efficient than build_annual_rows() for large projects.

    Returns
    -------
    List[Dict[str, float]]
        Identical structure to build_annual_rows().
    """

    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
    )

    # Step 1: Compute all production/revenue/opex data
    ebit_series: List[float] = []
    production_data: List[Dict[str, float]] = []

    for year_index in range(years):
        year = year_index + 1
        fx_rate = fx_curve_resolved[year_index]

        gross_kwh, net_kwh = _calculate_net_production(
            float(params["capacity_mw"]),
            float(params["capacity_factor"]),
            float(params["degradation"]),
            float(params["grid_loss_pct"]),
            year_index,
        )

        revenue_lkr = _calculate_revenue_lkr(
            net_kwh, float(params["tariff_lkr_per_kwh"])
        )

        statutory = _calculate_statutory_deductions(
            revenue_lkr,
            float(params["success_fee_pct"]),
            float(params["env_surcharge_pct"]),
            float(params["social_levy_pct"]),
        )

        # OpEx escalates in USD at opex_escalation_pct/yr, then x the per-year FX rate.
        opex_escalation = float(params.get("opex_escalation_pct", 0.0))
        opex_usd_year = (
            float(params["opex_usd_per_year"]) * (1.0 + opex_escalation) ** year_index
        )
        opex_lkr = _calculate_opex_lkr(opex_usd_year, fx_rate)

        ebitda_lkr = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr

        production_data.append(
            {
                "year": float(year),
                "gross_kwh": gross_kwh,
                "grid_loss": gross_kwh - net_kwh,
                "net_kwh": net_kwh,
                "revenue_lkr": revenue_lkr,
                "success_fee_lkr": statutory["success_fee"],
                "env_surcharge_lkr": statutory["environmental_surcharge"],
                "social_levy_lkr": statutory["social_services_levy"],
                "total_statutory_deductions_lkr": statutory[
                    "total_statutory_deductions"
                ],
                "opex_usd": opex_usd_year,  # escalated (year-1 base x (1+esc)^year_index)
                "fx_rate": fx_rate,
                "opex_lkr": opex_lkr,
                "ebitda_lkr": ebitda_lkr,
            }
        )

        ebit_series.append(ebitda_lkr)

    # Step 2: Compute all taxes at once (with loss carry-forward)
    years_list = list(range(1, years + 1))
    tax_results = build_tax_series(
        years=years_list,
        ebit_series=ebit_series,
        interest_series=interest_series,
        depreciation_schedule=depreciation_schedule,
        tax_profile=tax_profile,
    )

    # Step 3: Combine production + tax data
    rows: List[Dict[str, float]] = []

    for year_index, (prod_data, tax_result) in enumerate(
        zip(production_data, tax_results)
    ):
        fx_rate = fx_curve_resolved[year_index]

        # Start with production data
        row = prod_data.copy()

        # Add tax data
        row.update(
            {
                "pretax_cfads_lkr": tax_result.ebit,
                "total_depreciation_lkr": tax_result.depreciation,
                "interest_expense_lkr": tax_result.interest_expense,
                "taxable_income_lkr": tax_result.taxable_income,
                "tax_lkr": tax_result.tax_liability,
                "effective_tax_rate": tax_result.effective_tax_rate,
                "tax_holiday_applied": float(tax_result.tax_holiday_applied),
                "carried_forward_losses": tax_result.carried_forward_losses,
                "wht_on_interest": tax_result.wht_on_interest,
            }
        )

        # Post-tax CFADS
        posttax_cfads = tax_result.ebit - tax_result.tax_liability
        risk_haircut_pct = float(params.get("risk_haircut_pct", 0.0))
        cfads_final_lkr = _apply_risk_haircut(posttax_cfads, risk_haircut_pct)
        risk_haircut_amount = posttax_cfads - cfads_final_lkr

        row.update(
            {
                "posttax_cfads_lkr": posttax_cfads,
                "risk_haircut_pct": risk_haircut_pct,
                "risk_haircut_amount_lkr": risk_haircut_amount,
                "cfads_final_lkr": cfads_final_lkr,
                "cfads_risk_adjusted_lkr": cfads_final_lkr,
            }
        )

        # USD views
        if fx_rate > 0.0:
            row.update(
                {
                    "revenue_usd": row["revenue_lkr"] / fx_rate,
                    "cfads_usd": cfads_final_lkr / fx_rate,
                }
            )
        else:
            row.update(
                {
                    "revenue_usd": 0.0,
                    "cfads_usd": 0.0,
                }
            )

        rows.append(row)

    if rows:
        logger.info(
            "Built annual cashflow rows (efficient) for %d years, "
            "CFADS range: %.0f to %.0f, with loss carry-forward tracking",
            years,
            min(r["cfads_final_lkr"] for r in rows),
            max(r["cfads_final_lkr"] for r in rows),
        )
    else:
        logger.info("Built annual cashflow rows (efficient) for 0 years")

    return rows


# =============================================================================
# Schema registration for v14 cashflow
# =============================================================================


def _register_cashflow_schema() -> None:
    """
    Register the core v14 cashflow-required fields with the global schema
    registry. Mirrors the checks in _extract_parameters and validate_parameters.

    This gives schema_guard a precise view of what cashflow_v14 expects.
    """

    specs = [
        RequiredFieldSpec(
            module="cashflow",
            name="project_life_years",
            paths=(
                ("project", "project_life_years"),
                ("project", "life_years"),
                ("parameters", "project_life_years"),
                ("Financing_Terms", "tenor_years"),
            ),
            required=True,
            severity="error",
            description="Project life in years; drives CFADS horizon.",
            validator=lambda v: isinstance(v, int) and v > 0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="capacity_mw",
            paths=(
                ("project", "capacity_mw"),
                ("project", "capacity"),
                ("parameters", "capacity_mw"),
                ("parameters", "capacity"),
            ),
            required=True,
            severity="error",
            description="Net installed capacity in MW.",
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and float(v) > 0.0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="capacity_factor",
            paths=(
                ("project", "capacity_factor_pct"),
                ("project", "capacity_factor"),
                ("parameters", "capacity_factor_pct"),
                ("parameters", "capacity_factor"),
                ("capacity_factor_pct",),
                ("capacity_factor",),
            ),
            required=True,
            severity="error",
            description="Net capacity factor (percent or decimal).",
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and 0.0 < float(v) <= 100.0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="tariff_lkr_per_kwh",
            paths=(
                ("tariff", "lkr_per_kwh"),
                ("tariff", "lkr_kwh"),
                ("tariff", "tariff_lkr_per_kwh"),
                ("revenue", "tariff_lkr_per_kwh"),
                ("parameters", "tariff_lkr_per_kwh"),
                ("parameters", "tariff_lkr"),
                ("tariff_lkr_per_kwh",),
                ("tariff_lkr",),
                ("tariff",),
            ),
            required=True,
            severity="error",
            description="Front-of-meter tariff in LKR per kWh.",
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and float(v) >= 0.0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="opex_usd_per_year",
            paths=(
                ("opex", "usd_per_year"),
                ("opex", "usd_annual"),
                ("opex", "annual_opex_usd"),
                ("costs", "opex_usd_per_year"),
                ("parameters", "opex_usd_per_year"),
                ("opex_usd_per_year",),
            ),
            required=True,
            severity="error",
            description="Steady-state operating expenditure in USD per year.",
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and float(v) >= 0.0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="corporate_tax_rate",
            paths=(
                ("tax", "corporate_tax_rate_pct"),
                ("tax", "corporate_tax_rate"),
                ("project", "corporate_tax_rate_pct"),
                ("project", "corporate_tax_rate"),
                ("parameters", "corporate_tax_rate_pct"),
                ("parameters", "corporate_tax_rate"),
                ("corporate_tax_rate_pct",),
                ("corporate_tax_rate",),
            ),
            required=True,
            severity="error",
            description="Headline corporate income tax rate for the project company.",
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and 0.0 <= float(v) <= 100.0,
        ),
        RequiredFieldSpec(
            module="cashflow",
            name="fx_start_lkr_per_usd",
            paths=(("fx", "start_lkr_per_usd"),),
            required=True,
            severity="error",
            description=(
                "FX base rate in LKR per USD (fx.start_lkr_per_usd). "
                "Ensures structured FX config instead of scalar fallbacks."
            ),
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and float(v) > 0.0,
        ),
    ]

    register_required_fields("cashflow", specs)


try:  # pragma: no cover
    _register_cashflow_schema()
except Exception:
    # Never allow schema registration to break the core finance engine.
    logger.exception("Failed to register cashflow schema; proceeding without it.")


__all__ = [
    "validate_parameters",
    "calculate_single_year_cfads",
    "build_annual_cfads",
    "build_annual_rows",
    "build_annual_rows_efficient",
]
