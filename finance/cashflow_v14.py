from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields

from .bess_revenue import (
    bess_augmentation_capex_lkr_for_year,
    bess_revenue_lkr_for_year,
    resolve_bess_specs,
)
from .cashflow_v14_contracts import CashflowParams, FxHedge
from .cashflow_v14_fx import _fx_curve, _hedged_usd, _resolve_fx_hedge
from .cashflow_v14_params import _build_cashflow_params, validate_parameters
from .cashflow_v14_production import (
    _apply_risk_haircut,
    _calculate_opex_lkr,
    _calculate_revenue_lkr,
    _calculate_statutory_deductions,
    calculate_net_production_for_year,
    resolve_tech_generation_specs,
    validate_storage_capex_declared,
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
    extra_depreciable_usd: Optional[float] = None,
    senior_fee_lkr_series: Optional[List[float]] = None,
) -> Tuple[
    Dict[str, Any],
    List[float],
    Optional[float],
    List[float],
    int,
    TaxProfile,
    DepreciationSchedule,
    FxHedge,
    List[float],
]:
    """
    Shared context builder for build_annual_cfads and build_annual_rows.

    Returns
    -------
    (params_dict, fx_curve_resolved, capex_depreciable_resolved,
     interest_series, years, tax_profile, depreciation_schedule, fx_hedge,
     senior_fee_series)

    The TaxProfile and DepreciationSchedule are now built upfront and
    reused for all years, avoiding repeated computation and ensuring
    consistent loss carry-forward tracking.

    ``fx_hedge`` carries the resolved FX-forward hedge state (ratio, spread, CIP forward
    curve). It is the null :class:`FxHedge` unless ``fx.hedge_ratio > 0`` — in which case
    the USD-view conversion blends spot with the locked forward (see ``_hedged_usd``).
    """
    # Validate parameters before expensive calculations
    validate_parameters(config)

    params_obj: CashflowParams = _build_cashflow_params(config)
    params_dict: Dict[str, Any] = asdict(params_obj)

    # Multi-tech generation (M3): when a generation.technologies block is present,
    # carry per-tech specs so production sums each tech with its own degradation.
    # None for the legacy single-tech path (byte-identical wind-only behaviour).
    params_dict["tech_generation_specs"] = resolve_tech_generation_specs(
        config, params_dict
    )

    # BESS (storage) capacity-charge revenue: a `type: bess` technology earns an
    # availability-based Capacity Charge (LKR/MW/month), NOT generation revenue.
    # None when no BESS block is present -> wind/solar runs stay byte-identical.
    params_dict["bess_revenue_specs"] = resolve_bess_specs(config)

    # BESS-3 / CESSPIT: reject a storage asset booked as free revenue — a revenue-
    # producing type:bess block must declare a positive capex_usd (it must then be
    # included in the financed capex.usd_total; full per-tech coupling is ARCH-3).
    validate_storage_capex_declared(config)

    # Tax-loss carry-forward ledger (vintage-aware): the live per-year builders thread
    # this through calculate_single_year_cfads so losses expire after the statutory
    # window (loss_carryforward_years) and survive holiday years. Starts empty.
    params_dict["loss_vintages"] = ()

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

    # Optionally augment the depreciable base with extra USD capex — used by the
    # equity-facing pass to capitalize debt IDC into the tax base (#36/#75). The IDC is a
    # debt-financing artifact (interest during construction), so it belongs to the levered
    # equity view, exactly like the interest tax shield; the project/unlevered pass leaves
    # this None and stays byte-identical. Translated at the SAME year-0 FX the USD capex
    # base above uses, so the two are consistent. Applied only when a base was resolved
    # (no base -> no depreciation regardless of any extra).
    if extra_depreciable_usd is not None and capex_dep_resolved is not None:
        capex_dep_resolved += float(extra_depreciable_usd) * fx_curve_resolved[0]

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

    # Senior credit-support fee series (#737): per-operating-year LKR fee (guarantee +
    # PRI on outstanding senior debt), computed by the debt engine and FX-translated by
    # the pipeline. Aligned exactly like the interest series; None -> zeros ->
    # byte-identical rows.
    if senior_fee_lkr_series is None:
        senior_fee_series = [0.0] * years
    else:
        senior_fee_series = [float(v or 0.0) for v in senior_fee_lkr_series]
    if len(senior_fee_series) < years:
        senior_fee_series = senior_fee_series + [0.0] * (years - len(senior_fee_series))
    elif len(senior_fee_series) > years:
        senior_fee_series = senior_fee_series[:years]

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
            tax_config.enhanced_capital_allowance_multiple
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
                start_year=tax_config.depreciation_start_year,
            )
        else:
            depreciation_schedule = DepreciationSchedule.build_straight_line(
                capex_lkr=capex_for_depreciation,
                useful_life=tax_config.depreciation_years,
                project_life=years,
                start_year=tax_config.depreciation_start_year,
            )
        # Guard the newly-wired depreciation_start_year: if start_year pushes the useful-life
        # window past project_life the tail years are silently forfeited. Warn so the
        # truncated capital allowance is visible (dormant at the canonical start_year=1).
        # FIN-7 (#482, reviewed): forfeiting the tail allowance is the INTENTIONAL, correct
        # treatment — under the SL Inland Revenue Act the unrecovered basis on an asset held
        # only to project end-of-life is not carried forward as a deduction. The warning is
        # the right response (no silent understatement); no further change. KPI-neutral for
        # the committed scenarios (all use start_year=1, so nothing is forfeited).
        _scheduled = sum(depreciation_schedule.annual_amounts)
        if capex_for_depreciation > 0.0 and _scheduled < capex_for_depreciation - 1.0:
            logger.warning(
                "Depreciation recovers only %.0f of %.0f capex base: "
                "depreciation_start_year=%d plus the useful life overruns project_life=%d, "
                "forfeiting the tail-year allowance.",
                _scheduled,
                capex_for_depreciation,
                tax_config.depreciation_start_year,
                years,
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

    # Resolve the FX-forward hedge AFTER fx_curve_resolved is finalized, so the CIP
    # forward is anchored on the SAME spot_0 the per-year spot path uses. Null (pure
    # spot, byte-identical) unless fx.hedge_ratio > 0.
    fx_hedge = _resolve_fx_hedge(config, fx_curve_resolved)

    return (
        params_dict,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
        fx_hedge,
        senior_fee_series,
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
    hedge_ratio: float = 0.0,
    spread: float = 0.0,
    forward_rate: float = 0.0,
    senior_fee_lkr: float = 0.0,
) -> Dict[str, float]:
    """
    Compute detailed CFADS breakdown for a single year.

    Parameters
    ----------
    params :
        Normalized parameter dict from _extract_parameters.

    fx_rate :
        LKR per USD spot FX rate for the given year.

    hedge_ratio :
        Fraction (0-1) of this year's LKR CFADS/revenue converted to USD at the CIP
        forward instead of spot. Default 0.0 -> pure-spot conversion (byte-identical).

    spread :
        Hedging cost (decimal) loaded onto the forward rate as ``forward * (1 + spread)``.

    forward_rate :
        LKR per USD CIP forward rate for the given year (used only when hedge_ratio > 0).

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

    gross_kwh, net_kwh = calculate_net_production_for_year(params, year_index)

    generation_revenue_lkr = _calculate_revenue_lkr(
        net_kwh, float(params["tariff_lkr_per_kwh"])
    )

    # BESS capacity-charge revenue (availability tolling), additive to generation
    # revenue. 0.0 when no `type: bess` block -> byte-identical wind/solar behaviour.
    bess_revenue_lkr = bess_revenue_lkr_for_year(
        params.get("bess_revenue_specs"), year_index
    )
    revenue_lkr = generation_revenue_lkr + bess_revenue_lkr

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
    opex_usd_year = (
        float(params["opex_usd_per_year"]) * (1.0 + opex_escalation) ** year_index
    )
    opex_lkr = _calculate_opex_lkr(opex_usd_year, fx_rate)

    # For this engine, EBITDA and EBIT coincide (no other non-cash items)
    # Depreciation is NOT in EBIT; it's a tax deduction.
    # senior_fee_lkr (#737) is the annual credit-support fee (guarantee + PRI on
    # outstanding senior debt, computed by the debt engine and FX-translated by the
    # pipeline). It ranks senior/above debt service, so it comes out at this line —
    # reducing CFADS and, because ebit == ebitda feeds the tax engine, taxable income
    # and tax automatically (deductible opex). 0.0 -> byte-identical.
    ebitda_lkr = (
        revenue_lkr
        - statutory["total_statutory_deductions"]
        - opex_lkr
        - senior_fee_lkr
    )
    ebit = ebitda_lkr

    # --- Tax and depreciation (with loss carry-forward) ----------------------
    # Use new calculate_tax with unified TaxProfile
    depreciation_for_year = depreciation_schedule.annual_amounts[year_index]

    # Loss carry-forward state threads through the per-evaluation params context as a
    # vintage ledger (so losses expire after the statutory window and survive holiday
    # years). When params carries no ledger (direct unit-test callers) we fall back to
    # the legacy scalar prior_year_losses path (byte-identical).
    loss_vintages = params.get("loss_vintages")
    tax_result: TaxResult = calculate_tax(
        year=year,  # 1-based (matches tax_profile.tax_holidays_by_year keys)
        ebit=ebit,
        interest_expense=interest_expense_lkr,
        depreciation=depreciation_for_year,
        tax_profile=tax_profile,
        prior_year_losses=prior_year_losses,
        prior_loss_vintages=loss_vintages,
    )
    if loss_vintages is not None:
        # FIN-8 (#482, reviewed): this writes the carried-forward loss VINTAGES back onto the
        # caller's params dict to thread them across years (parallel to the scalar
        # carried_losses, which threads via prior_year_losses + the returned row key). It is a
        # callee side-effect, but a DELIBERATE and contained one: the vintages are a tuple and
        # the per-year row is typed Dict[str, float], so they cannot ride back in the row —
        # the params channel is the only float-free path. The behaviour is correct and
        # byte-identical to build_annual_rows_efficient (build_tax_series), which the
        # both-builders-agree tests pin. A full explicit-threading refactor (a (row, vintages)
        # return tuple) is tracked but deferred as risk-disproportionate to a low-severity,
        # KPI-neutral code-smell.
        params["loss_vintages"] = tax_result.carried_forward_vintages

    tax = tax_result.tax_liability
    total_depr = tax_result.depreciation
    wht_on_interest = tax_result.wht_on_interest

    posttax_cfads = ebit - tax

    # --- Risk haircut on post-tax CFADS (v14 definition) ----------------------
    risk_haircut_pct = float(params.get("risk_haircut_pct", 0.0))

    cfads_final_lkr = _apply_risk_haircut(posttax_cfads, risk_haircut_pct)

    risk_haircut_amount = posttax_cfads - cfads_final_lkr

    # --- Mid-life BESS augmentation capex (cash outflow) ----------------------
    # A scheduled cell top-up is a cash outflow netted out of CFADS in its year (so it
    # depresses that year's DSCR). 0.0 without an augmentation_schedule -> byte-identical.
    bess_augmentation_capex_lkr = bess_augmentation_capex_lkr_for_year(
        params.get("bess_revenue_specs"), year_index, fx_rate
    )
    cfads_final_lkr = cfads_final_lkr - bess_augmentation_capex_lkr

    # --- USD views ------------------------------------------------------------
    # FX risk enters the USD-numeraire engine ONLY here. With a null hedge (hedge_ratio
    # 0.0, the default) _hedged_usd returns exactly `value_lkr / fx_rate` — byte-identical
    # to the pre-hedge path. With a hedge, part of the flow is converted at the locked CIP
    # forward instead of the projected spot (see finance.cashflow_v14_fx._hedged_usd).
    if fx_rate > 0.0:
        revenue_usd = _hedged_usd(
            revenue_lkr, fx_rate, forward_rate, hedge_ratio, spread
        )
        cfads_usd = _hedged_usd(
            cfads_final_lkr, fx_rate, forward_rate, hedge_ratio, spread
        )
    else:
        revenue_usd = 0.0
        cfads_usd = 0.0

    result: Dict[str, float] = {
        "year": float(year),
        "gross_kwh": gross_kwh,
        "grid_loss": gross_kwh - net_kwh,
        "net_kwh": net_kwh,
        "revenue_lkr": revenue_lkr,
        "generation_revenue_lkr": generation_revenue_lkr,
        "bess_revenue_lkr": bess_revenue_lkr,
        "success_fee_lkr": statutory["success_fee"],
        "env_surcharge_lkr": statutory["environmental_surcharge"],
        "social_levy_lkr": statutory["social_services_levy"],
        "total_statutory_deductions_lkr": statutory["total_statutory_deductions"],
        "opex_usd": opex_usd_year,  # escalated (year-1 base x (1+esc)^year_index)
        "fx_rate": fx_rate,
        "opex_lkr": opex_lkr,
        "senior_fee_lkr": senior_fee_lkr,
        "ebitda_lkr": ebitda_lkr,
        "pretax_cfads_lkr": ebit,
        "total_depreciation_lkr": total_depr,
        "interest_expense_lkr": interest_expense_lkr,
        "taxable_income_lkr": tax_result.taxable_income,
        "tax_lkr": tax,
        "posttax_cfads_lkr": posttax_cfads,
        "risk_haircut_pct": risk_haircut_pct,
        "risk_haircut_amount_lkr": risk_haircut_amount,
        "bess_augmentation_capex_lkr": bess_augmentation_capex_lkr,
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
    senior_fee_lkr_series: Optional[List[float]] = None,
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
        fx_hedge,
        senior_fee_series,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
        senior_fee_lkr_series=senior_fee_lkr_series,
    )

    cfads_list: List[float] = []
    carried_losses = 0.0

    for year in range(1, years + 1):
        year_index = year - 1
        fx_rate = fx_curve_resolved[year_index]
        interest_lkr = interest_series[year_index]
        forward_rate = (
            fx_hedge.forward_curve[year_index] if fx_hedge.forward_curve else 0.0
        )

        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            tax_profile=tax_profile,
            depreciation_schedule=depreciation_schedule,
            interest_expense_lkr=interest_lkr,
            verbose=verbose,
            prior_year_losses=carried_losses,
            hedge_ratio=fx_hedge.hedge_ratio,
            spread=fx_hedge.spread,
            forward_rate=forward_rate,
            senior_fee_lkr=senior_fee_series[year_index],
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
    extra_depreciable_usd: Optional[float] = None,
    senior_fee_lkr_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    """
    Return list of per-year breakdown rows including CFADS in LKR and USD.

    This is the canonical *row-wise* surface for:

    - debt_v14.plan_debt (DSCR / covenants)
    - CashflowResult (via contracts_v14)
    - analytics exports and dashboards.

    NOTE: This function now correctly tracks loss carry-forward across years.

    ``extra_depreciable_usd`` augments the depreciable tax base by an extra USD capex
    amount (translated at year-0 FX). It is used by the equity-facing pass to capitalize
    debt IDC (#36/#75); the unlevered project pass leaves it None and is byte-identical.

    ``senior_fee_lkr_series`` charges the per-operating-year senior credit-support fee
    (#737: guarantee + PRI on outstanding senior debt, LKR-translated by the pipeline)
    at the EBITDA line — reducing CFADS and, through ebit == ebitda, taxable income.
    None is byte-identical.
    """

    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        tax_profile,
        depreciation_schedule,
        fx_hedge,
        senior_fee_series,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
        extra_depreciable_usd=extra_depreciable_usd,
        senior_fee_lkr_series=senior_fee_lkr_series,
    )

    rows: List[Dict[str, float]] = []
    carried_losses = 0.0

    for year in range(1, years + 1):
        year_index = year - 1
        fx_rate = fx_curve_resolved[year_index]
        interest_lkr = interest_series[year_index]
        forward_rate = (
            fx_hedge.forward_curve[year_index] if fx_hedge.forward_curve else 0.0
        )

        row = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            tax_profile=tax_profile,
            depreciation_schedule=depreciation_schedule,
            interest_expense_lkr=interest_lkr,
            verbose=False,
            prior_year_losses=carried_losses,
            hedge_ratio=fx_hedge.hedge_ratio,
            spread=fx_hedge.spread,
            forward_rate=forward_rate,
            senior_fee_lkr=senior_fee_series[year_index],
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
    senior_fee_lkr_series: Optional[List[float]] = None,
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
        fx_hedge,
        senior_fee_series,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
        senior_fee_lkr_series=senior_fee_lkr_series,
    )

    # Step 1: Compute all production/revenue/opex data
    ebit_series: List[float] = []
    production_data: List[Dict[str, float]] = []

    for year_index in range(years):
        year = year_index + 1
        fx_rate = fx_curve_resolved[year_index]

        gross_kwh, net_kwh = calculate_net_production_for_year(params, year_index)

        generation_revenue_lkr = _calculate_revenue_lkr(
            net_kwh, float(params["tariff_lkr_per_kwh"])
        )
        # BESS capacity-charge revenue (additive; 0.0 when no `type: bess` block) —
        # mirrors calculate_single_year_cfads so the two builders stay identical.
        bess_revenue_lkr = bess_revenue_lkr_for_year(
            params.get("bess_revenue_specs"), year_index
        )
        revenue_lkr = generation_revenue_lkr + bess_revenue_lkr

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

        # Senior credit-support fee at the EBITDA line (#737) — mirrors
        # calculate_single_year_cfads so the two builders stay identical.
        senior_fee_lkr = senior_fee_series[year_index]
        ebitda_lkr = (
            revenue_lkr
            - statutory["total_statutory_deductions"]
            - opex_lkr
            - senior_fee_lkr
        )

        production_data.append(
            {
                "year": float(year),
                "gross_kwh": gross_kwh,
                "grid_loss": gross_kwh - net_kwh,
                "net_kwh": net_kwh,
                "revenue_lkr": revenue_lkr,
                "generation_revenue_lkr": generation_revenue_lkr,
                "bess_revenue_lkr": bess_revenue_lkr,
                "success_fee_lkr": statutory["success_fee"],
                "env_surcharge_lkr": statutory["environmental_surcharge"],
                "social_levy_lkr": statutory["social_services_levy"],
                "total_statutory_deductions_lkr": statutory[
                    "total_statutory_deductions"
                ],
                "opex_usd": opex_usd_year,  # escalated (year-1 base x (1+esc)^year_index)
                "fx_rate": fx_rate,
                "opex_lkr": opex_lkr,
                "senior_fee_lkr": senior_fee_lkr,
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
        zip(production_data, tax_results, strict=True)
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
        # Mid-life BESS augmentation capex netted out of CFADS (mirrors
        # calculate_single_year_cfads so the two builders stay identical).
        bess_augmentation_capex_lkr = bess_augmentation_capex_lkr_for_year(
            params.get("bess_revenue_specs"), year_index, fx_rate
        )
        cfads_final_lkr = cfads_final_lkr - bess_augmentation_capex_lkr

        row.update(
            {
                "posttax_cfads_lkr": posttax_cfads,
                "risk_haircut_pct": risk_haircut_pct,
                "risk_haircut_amount_lkr": risk_haircut_amount,
                "bess_augmentation_capex_lkr": bess_augmentation_capex_lkr,
                "cfads_final_lkr": cfads_final_lkr,
                "cfads_risk_adjusted_lkr": cfads_final_lkr,
            }
        )

        # USD views — spot/forward blend (mirrors calculate_single_year_cfads so the two
        # builders stay identical). Null hedge -> byte-identical `value_lkr / fx_rate`.
        forward_rate = (
            fx_hedge.forward_curve[year_index] if fx_hedge.forward_curve else 0.0
        )
        if fx_rate > 0.0:
            row.update(
                {
                    "revenue_usd": _hedged_usd(
                        row["revenue_lkr"],
                        fx_rate,
                        forward_rate,
                        fx_hedge.hedge_ratio,
                        fx_hedge.spread,
                    ),
                    "cfads_usd": _hedged_usd(
                        cfads_final_lkr,
                        fx_rate,
                        forward_rate,
                        fx_hedge.hedge_ratio,
                        fx_hedge.spread,
                    ),
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


def _is_positive_whole_years(value: Any) -> bool:
    """Schema validator for year-count fields: a positive whole number of years.

    Accepts ``int`` (20) and integral ``float`` (20.0) — YAML authors write
    both, and the engine's own extraction (``as_int_or_none`` -> ``int(value)``)
    already treats 20.0 as 20, so the pre-flight guard must not be stricter
    than the engine it protects (#586). Rejects ``bool`` (a subclass of int,
    never a year count — the old ``isinstance(v, int)`` check let ``True``
    through), non-integral floats (fail loud rather than let the engine
    silently truncate 20.5 -> 20), and anything <= 0. Strings stay rejected:
    schema-strict configs must carry numeric year counts (CESSPIT).
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, float):
        return value > 0.0 and value.is_integer()
    return False


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
            # #586: int OR integral float (20.0), matching the engine's own
            # as_int_or_none coercion; bool / non-integral / <=0 rejected.
            validator=_is_positive_whole_years,
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
            description="Net capacity factor (percent or decimal); 0 for a "
            "storage-only scenario whose revenue is the BESS capacity charge.",
            # BESS-5 (#486): allow 0.0 — a standalone-BESS scenario has no generation
            # capacity factor (its revenue is the capacity charge), so a literal 0 is
            # valid rather than the former 0.0001 placeholder. Still reject negatives.
            validator=lambda v: isinstance(v, (int, float))
            and v is not None
            and 0.0 <= float(v) <= 100.0,
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
