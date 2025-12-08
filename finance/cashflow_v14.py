from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    _compute_depreciation_schedule,
    calculate_tax_with_interest_shield,
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
- validate_parameters(config)  -> [] or raises ValueError
- build_annual_cfads(config, ...) -> list[float]
- build_annual_rows(config, ...) -> list[dict[str, float]]
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
      - tax_lkr(pretax_cfads, interest_shield, depreciation)
      - risk_haircut

This is the only definition that debt_v14 and the analytics stack are
allowed to rely on. Any alternative “CFADS” views must be derived from
the row-wise breakdown returned here.
"""


# =============================================================================
# Internal context preparation
# =============================================================================


def _prepare_cashflow_context(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]],
    capex_depreciable_lkr: Optional[float],
    interest_expense_series: Optional[List[float]],
) -> Tuple[Dict[str, Any], List[float], Optional[float], List[float], int, List[float]]:
    """
    Shared context builder for build_annual_cfads and build_annual_rows.

    Returns
    -------
    (params_dict, fx_curve_resolved, capex_depreciable_resolved,
     interest_series, years, depreciation_schedule)
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

    # Pre-compute depreciation schedule for the whole project life for efficiency.
    if capex_dep_resolved is not None and params_obj.depreciation_years > 0:
        base_schedule = _compute_depreciation_schedule(
            capex_dep_resolved,
            params_obj.depreciation_years,
            params_obj.enhanced_capital_allowance_pct,
        )
    else:
        base_schedule = []

    if len(base_schedule) < years:
        depreciation_schedule = base_schedule + [0.0] * (years - len(base_schedule))
    else:
        depreciation_schedule = base_schedule[:years]

    return (
        params_dict,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        depreciation_schedule,
    )


# =============================================================================
# Public CFADS API
# =============================================================================


def calculate_single_year_cfads(
    params: Dict[str, Any],
    fx_rate: float,
    year: int,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
    depreciation_schedule: Optional[Sequence[float]] = None,
) -> Dict[str, float]:
    """Compute detailed CFADS breakdown for a single year.

    Parameters
    ----------
    params :
        Normalized parameter dict from _extract_parameters.
    fx_rate :
        LKR per USD FX rate for the given year.
    year :
        Zero-based year index.
    capex_depreciable_lkr :
        Depreciable capex base in LKR (used for depreciation).
    interest_expense_lkr :
        Interest expense in LKR for the year.
    verbose :
        If True, log the per-year CFADS breakdown.
    depreciation_schedule :
        Optional pre-computed depreciation schedule for the whole project life.
        When provided, it is passed through to the tax calculator to avoid
        re-building the schedule on every year.

    Returns
    -------
    dict[str, float]
        Per-year breakdown, including `cfads_final_lkr` which is the
        canonical CFADS used by debt_v14 and CashflowResult.
    """
    # --- Production and revenue ------------------------------------------------
    gross_kwh, net_kwh = _calculate_net_production(
        float(params["capacity_mw"]),
        float(params["capacity_factor"]),
        float(params["degradation"]),
        float(params["grid_loss_pct"]),
        year,
    )
    revenue_lkr = _calculate_revenue_lkr(net_kwh, float(params["tariff_lkr_per_kwh"]))

    # --- Statutory charges and OPEX -------------------------------------------
    statutory = _calculate_statutory_deductions(
        revenue_lkr,
        float(params["success_fee_pct"]),
        float(params["env_surcharge_pct"]),
        float(params["social_levy_pct"]),
    )
    opex_lkr = _calculate_opex_lkr(float(params["opex_usd_per_year"]), fx_rate)

    # For this engine, EBITDA and pretax CFADS coincide (no other non-cash items)
    ebitda_lkr = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr
    pretax_cfads = ebitda_lkr

    # --- Tax and depreciation (with interest shield) --------------------------
    tax, total_depr = calculate_tax_with_interest_shield(
        pretax_cfads=pretax_cfads,
        corporate_tax_rate=float(params["corporate_tax_rate"]),
        capex_depreciable_lkr=capex_depreciable_lkr,
        depreciation_years=int(params["depreciation_years"]),
        interest_expense_lkr=interest_expense_lkr,
        year_index=year,
        tax_holiday_years=int(params.get("tax_holiday_years", 0)),
        tax_holiday_start_year=int(params.get("tax_holiday_start_year", 1)),
        enhanced_capital_allowance_pct=float(
            params.get("enhanced_capital_allowance_pct", 1.0)
        ),
        precomputed_depr_schedule=depreciation_schedule,
    )

    posttax_cfads = pretax_cfads - tax

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
        "year": float(year + 1),
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
        "pretax_cfads_lkr": pretax_cfads,
        "total_depreciation_lkr": total_depr,
        "interest_expense_lkr": interest_expense_lkr,
        "taxable_income_lkr": max(
            0.0, pretax_cfads - total_depr - interest_expense_lkr
        ),
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
    }

    if verbose:
        logger.info("Year %d CFADS: %s", year + 1, result)

    return result


def build_annual_cfads(
    config: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_depreciable_lkr: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    verbose: bool = False,
) -> List[float]:
    """Return list of CFADS (LKR) for each project year.

    This is the primary numeric surface used by debt_v14 and covenant tests.
    """
    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        depreciation_schedule,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
    )

    cfads_list: List[float] = []
    for year in range(years):
        fx_rate = fx_curve_resolved[year]
        interest_lkr = interest_series[year]
        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_depreciable_lkr=capex_dep_resolved,
            interest_expense_lkr=interest_lkr,
            verbose=verbose,
            depreciation_schedule=depreciation_schedule,
        )
        cfads_list.append(result["cfads_final_lkr"])

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
    """
    (
        params,
        fx_curve_resolved,
        capex_dep_resolved,
        interest_series,
        years,
        depreciation_schedule,
    ) = _prepare_cashflow_context(
        config,
        fx_curve,
        capex_depreciable_lkr,
        interest_expense_series,
    )

    rows: List[Dict[str, float]] = []
    for year in range(years):
        fx_rate = fx_curve_resolved[year]
        interest_lkr = interest_series[year]

        row = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_depreciable_lkr=capex_dep_resolved,
            interest_expense_lkr=interest_lkr,
            verbose=False,
            depreciation_schedule=depreciation_schedule,
        )
        rows.append(row)

    if rows:
        logger.info(
            "Built annual cashflow rows for %d years, CFADS range: %.0f to %.0f",
            years,
            min(r["cfads_final_lkr"] for r in rows),
            max(r["cfads_final_lkr"] for r in rows),
        )
    else:
        logger.info("Built annual cashflow rows for 0 years")

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
        # FX structure alignment – require a structured FX block for cashflow.
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
]
