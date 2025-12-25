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

"""Cash flow engine for DutchBay V14 (CFADS and annual rows).

🦌 REINDEER-3: Added strict validation parameter throughout call chain.

[Previous docstring content unchanged]
"""

# =============================================================================
# Internal context preparation
# =============================================================================


def _prepare_cashflow_context(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]],
    capex_depreciable_lkr: Optional[float],
    interest_expense_series: Optional[List[float]],
    *,
    strict: bool = True,
) -> Tuple[
    Dict[str, Any],
    List[float],
    Optional[float],
    List[float],
    int,
    TaxProfile,
    DepreciationSchedule,
]:
    """Shared context builder for build_annual_cfads and build_annual_rows.

    🦌 REINDEER-3: Added strict parameter for test-friendly validation.

    Parameters
    ----------
    config : dict
        Project configuration
    fx_curve : list[float] or None
        FX rates (LKR per USD) for each year
    capex_depreciable_lkr : float or None
        Depreciable capex base in LKR
    interest_expense_series : list[float] or None
        Interest expense per year in LKR
    strict : bool, default=True
        If True: Strict validation (production mode)
        If False: Lenient validation with defaults (test/dev mode)

    Returns
    -------
    (params_dict, fx_curve_resolved, capex_depreciable_resolved,
     interest_series, years, tax_profile, depreciation_schedule)
    """
    # 🦌 REINDEER-3: Pass strict parameter to validation
    validate_parameters(config, strict=strict)

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
    tax_config = TaxConfig.from_yaml(config)

    # Build depreciation schedule
    if capex_dep_resolved is not None and tax_config.depreciation_years > 0:
        capex_for_depreciation = capex_dep_resolved * (
            tax_config.enhanced_capital_allowance_pct
            if tax_config.enhanced_allowance_applies
            else 1.0
        )
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
# Public CFADS API (🦌 REINDEER-3: Added strict parameter)
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
    """Compute detailed CFADS breakdown for a single year.

    [Docstring unchanged - no strict parameter needed at this level]
    """

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

    statutory = _calculate_statutory_deductions(
        revenue_lkr,
        float(params["success_fee_pct"]),
        float(params["env_surcharge_pct"]),
        float(params["social_levy_pct"]),
    )

    opex_lkr = _calculate_opex_lkr(float(params["opex_usd_per_year"]), fx_rate)

    ebitda_lkr = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr
    ebit = ebitda_lkr

    depreciation_for_year = depreciation_schedule.annual_amounts[year_index]

    tax_result: TaxResult = calculate_tax(
        year=year,
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

    risk_haircut_pct = float(params.get("risk_haircut_pct", 0.0))
    cfads_final_lkr = _apply_risk_haircut(posttax_cfads, risk_haircut_pct)
    risk_haircut_amount = posttax_cfads - cfads_final_lkr

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
        "opex_usd": float(params["opex_usd_per_year"]),
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
        "cfads_final_lkr": cfads_final_lkr,
        "cfads_risk_adjusted_lkr": cfads_final_lkr,
        "revenue_usd": revenue_usd,
        "cfads_usd": cfads_usd,
        "effective_tax_rate": tax_result.effective_tax_rate,
        "tax_holiday_applied": float(tax_result.tax_holiday_applied),
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
    *,
    strict: bool = True,
) -> List[float]:
    """Return list of CFADS (LKR) for each project year.

    🦌 REINDEER-3: Added strict parameter for test-friendly validation.

    Parameters
    ----------
    [previous parameters unchanged]
    strict : bool, default=True
        Validation strictness (True=production, False=test/dev with defaults)
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
        strict=strict,
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
    *,
    strict: bool = True,
) -> List[Dict[str, float]]:
    """Return list of per-year breakdown rows including CFADS in LKR and USD.

    🦌 REINDEER-3: Added strict parameter for test-friendly validation.

    Parameters
    ----------
    [previous parameters unchanged]
    strict : bool, default=True
        Validation strictness (True=production, False=test/dev with defaults)
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
        strict=strict,
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
    *,
    strict: bool = True,
) -> List[Dict[str, float]]:
    """Build annual rows using batch tax calculation (build_tax_series).

    🦌 REINDEER-3: Added strict parameter for test-friendly validation.

    Parameters
    ----------
    [previous parameters unchanged]
    strict : bool, default=True
        Validation strictness (True=production, False=test/dev with defaults)
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
        strict=strict,
    )

    # [Rest of the function unchanged...]
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

        opex_lkr = _calculate_opex_lkr(float(params["opex_usd_per_year"]), fx_rate)

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
                "opex_usd": float(params["opex_usd_per_year"]),
                "fx_rate": fx_rate,
                "opex_lkr": opex_lkr,
                "ebitda_lkr": ebitda_lkr,
            }
        )

        ebit_series.append(ebitda_lkr)

    years_list = list(range(1, years + 1))
    tax_results = build_tax_series(
        years=years_list,
        ebit_series=ebit_series,
        interest_series=interest_series,
        depreciation_schedule=depreciation_schedule,
        tax_profile=tax_profile,
    )

    rows: List[Dict[str, float]] = []

    for year_index, (prod_data, tax_result) in enumerate(
        zip(production_data, tax_results)
    ):
        fx_rate = fx_curve_resolved[year_index]

        row = prod_data.copy()

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
    """Register the core v14 cashflow-required fields with the global schema registry."""

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
    logger.exception("Failed to register cashflow schema; proceeding without it.")


__all__ = [
    "validate_parameters",
    "calculate_single_year_cfads",
    "build_annual_cfads",
    "build_annual_rows",
    "build_annual_rows_efficient",
]
