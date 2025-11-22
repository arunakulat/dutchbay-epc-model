"""Cash Flow Module for DutchBay V14 Project Finance (BOI Tax Holiday/Enhancement Compliant)

COMPLIANCE:
-----------
- IFC/DFI/World Bank project finance standards
- Sri Lanka Inland Revenue Act (interest expense deductibility, BOI incentives)
- YAML-driven configuration (sourced from full_model_variables_updated.yaml)
- Complete statutory, regulatory, and risk deduction framework
- Audit-ready: full calculation trail and parameter validation

FEATURES & TAX/DEPRECIATION LOGIC:
----------------------------------
- Multi-year, FX-aware, grid-loss-adjusted, statutorily correct LKR cashflows
- CFADS reflects correct order: post all deductions, post-tax, pre-debt service
- Interest expense is deductible for tax calculation (with BOI-compliant tax shield)
- Tax holiday and enhanced capital allowance handling
- Straight-line depreciation by default across specified depreciation years
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from analytics.config_schema import RequiredFieldSpec, register_required_fields

logger = logging.getLogger(__name__)

# =============================================================================
# Helper utilities
# =============================================================================


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Safely convert a value to float, with default fallback."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Safely convert a value to int, with default fallback."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_int_or_none(value: Any) -> Optional[int]:
    """Return int(value) or None if conversion fails."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def get_nested(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely navigate nested dictionaries by list of keys."""
    current: Any = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def _as_float_or_none(value: Any) -> Optional[float]:
    """Return float(value) or None."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_to_decimal(raw: Optional[float]) -> Optional[float]:
    """
    Interpret a numeric as a percentage if > 1.0, otherwise as a decimal:
      24   -> 0.24
      0.24 -> 0.24
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw


def _resolve_first(cfg: Dict[str, Any], *candidates: Any) -> Any:
    """
    Resolve the first non-None value using a list of candidate paths/keys.

    Each candidate can be:
      - A string (top-level key)
      - A (k1, k2, ...) tuple representing a nested path
    """
    for cand in candidates:
        if isinstance(cand, tuple):
            val = get_nested(cfg, list(cand), None)
        else:
            val = cfg.get(cand)
        if val is not None:
            return val
    return None


# =============================================================================
# Core CFADS calculations
# =============================================================================


def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
) -> Tuple[float, float]:
    """
    Calculate gross and net kWh for a given year.
    """
    hours_per_year = 8760
    effective_cf = capacity_factor * ((1 - degradation) ** year)
    gross_kwh = capacity_mw * 1e3 * hours_per_year * effective_cf
    grid_loss = gross_kwh * grid_loss_pct
    net_kwh = gross_kwh - grid_loss
    return gross_kwh, net_kwh


def _calculate_revenue_lkr(net_kwh: float, tariff_lkr_per_kwh: float) -> float:
    """Compute revenue in LKR = net energy * tariff."""
    return net_kwh * tariff_lkr_per_kwh


def _calculate_statutory_deductions(
    revenue_lkr: float,
    success_fee_pct: float,
    env_surcharge_pct: float,
    social_levy_pct: float,
) -> Dict[str, float]:
    """
    Calculate statutory charges as percentages of revenue.
    """
    success_fee = revenue_lkr * success_fee_pct
    env_surcharge = revenue_lkr * env_surcharge_pct
    social_levy = revenue_lkr * social_levy_pct
    total = success_fee + env_surcharge + social_levy
    return {
        "success_fee": success_fee,
        "environmental_surcharge": env_surcharge,
        "social_services_levy": social_levy,
        "total_statutory_deductions": total,
    }


def _calculate_opex_lkr(opex_usd_per_year: float, fx_rate: float) -> float:
    """Convert annual OPEX from USD to LKR at a given FX rate."""
    return opex_usd_per_year * fx_rate


def _apply_risk_haircut(cfads_lkr: float, risk_haircut_pct: float) -> float:
    """Apply risk haircut: CFADS * (1 - haircut)."""
    return cfads_lkr * (1 - risk_haircut_pct)


# =============================================================================
# Tax & Depreciation (BOI / Inland Revenue Act)
# =============================================================================


def _compute_depreciation_schedule(
    capex_total: Optional[float],
    depreciation_years: int,
    enhanced_capital_allowance_pct: float,
) -> List[float]:
    """
    Build a straight-line depreciation schedule over depreciation_years.
    """
    if capex_total is None or depreciation_years <= 0:
        return []
    total_depreciable = capex_total * enhanced_capital_allowance_pct
    annual = total_depreciable / depreciation_years
    return [annual] * depreciation_years


def calculate_tax_with_interest_shield(
    pretax_cfads: float,
    corporate_tax_rate: float,
    capex_total: Optional[float],
    depreciation_years: int,
    interest_expense_lkr: float,
    year_index: int,
    tax_holiday_years: int = 0,
    tax_holiday_start_year: int = 1,
    enhanced_capital_allowance_pct: float = 1.0,
) -> Tuple[float, float]:
    """
    Calculate BOI-compliant tax with interest shield for a given year.

    Returns (tax_lkr, depreciation_for_year_lkr).
    """
    if corporate_tax_rate <= 0.0:
        return 0.0, 0.0

    current_year = year_index + 1

    # Determine whether the year is within the tax holiday window.
    in_holiday = False
    if tax_holiday_years > 0:
        start = tax_holiday_start_year
        end = start + tax_holiday_years - 1
        in_holiday = start <= current_year <= end

    if capex_total is None or depreciation_years <= 0:
        depreciation_schedule: List[float] = []
    else:
        depreciation_schedule = _compute_depreciation_schedule(
            capex_total,
            depreciation_years,
            enhanced_capital_allowance_pct,
        )

    if year_index < len(depreciation_schedule):
        depreciation_for_year = depreciation_schedule[year_index]
    else:
        depreciation_for_year = 0.0

    if in_holiday:
        # During BOI tax holiday, tax is zero regardless of taxable income.
        return 0.0, depreciation_for_year

    taxable_income = pretax_cfads - depreciation_for_year - interest_expense_lkr
    taxable_income = max(0.0, taxable_income)
    tax = taxable_income * corporate_tax_rate
    return tax, depreciation_for_year


# =============================================================================
# Parameter extraction & FX
# =============================================================================


def _fx_curve(p: Dict[str, Any], years: int) -> List[float]:
    """
    Build an FX curve (LKR per USD) for `years`.
    """
    years = max(1, int(years))
    fx_cfg = p.get("fx")

    # Explicit curve list
    if isinstance(fx_cfg, dict):
        curve = fx_cfg.get("curve") or fx_cfg.get("curve_lkr_per_usd")
        if isinstance(curve, (list, tuple)):
            clean = [float(x) for x in curve]
            if len(clean) >= years:
                return clean[:years]
            if clean:
                return clean + [clean[-1]] * (years - len(clean))

        start = (
            fx_cfg.get("start_lkr_per_usd")
            or fx_cfg.get("start")
            or fx_cfg.get("base")
            or fx_cfg.get("base_rate")
        )
        if start is not None:
            start_val = float(start)
            depr_pct = fx_cfg.get("annual_depr_pct") or fx_cfg.get("depr_pct") or 0.0
            depr = _pct_to_decimal(_as_float_or_none(depr_pct) or 0.0) or 0.0

            out: List[float] = []
            cur = start_val
            for _ in range(years):
                out.append(cur)
                cur *= 1.0 + depr
            return out

    # Legacy nested keys
    start_nested = get_nested(p, ["fx", "start_lkr_per_usd"])
    depr_nested = get_nested(p, ["fx", "annual_depr_pct"])
    if start_nested is not None:
        start_val = float(start_nested)
        depr = _pct_to_decimal(_as_float_or_none(depr_nested) or 0.0) or 0.0
        out2: List[float] = []
        cur2 = start_val
        for _ in range(years):
            out2.append(cur2)
            cur2 *= 1.0 + depr
        return out2

    # Final hard fallback – should be rare
    default_fx = 375.0
    logger.warning(
        "FX configuration missing or invalid; falling back to flat %.2f LKR/USD for %d years",
        default_fx,
        years,
    )
    return [default_fx] * years


def _extract_project_life_years(raw: Dict[str, Any]) -> int:
    """
    Robust extraction of project life (in years) for v14.
    """
    explicit_candidates: List[Tuple[Tuple[str, ...], str]] = [
        (("project", "life_years"), "project.life_years"),
        (("project", "project_life_years"), "project.project_life_years"),
        (("parameters", "project_life_years"), "parameters.project_life_years"),
        (("parameters", "life_years"), "parameters.life_years"),
        (("Financing_Terms", "tenor_years"), "Financing_Terms.tenor_years"),
    ]

    for path, label in explicit_candidates:
        v = as_int_or_none(get_nested(raw, list(path), None))
        if v is not None and 5 <= v <= 60:
            logger.info("Project life resolved from %s = %d years", label, v)
            return v

    hits: List[Tuple[str, int]] = []

    from collections.abc import Mapping, Sequence

    def walk(node: Any, path: Tuple[str, ...]) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                walk(v, path + (str(k),))
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            for idx, item in enumerate(node):
                walk(item, path + (f"[{idx}]",))
        else:
            iv = as_int_or_none(node)
            if iv is None:
                return
            if not (5 <= iv <= 60):
                return
            path_str = "/".join(path).lower()
            if any(
                t in path_str
                for t in ("life", "lifetime", "horizon", "year", "yrs")
            ):
                hits.append(("/".join(path), iv))

    walk(raw, ())

    if hits:
        chosen_path, chosen_val = hits[0]
        logger.warning(
            "Project life not found in explicit fields; using heuristic match %r = %d years",
            chosen_path,
            chosen_val,
        )
        return chosen_val

    raise ValueError(
        "Missing or invalid project life: expected one of "
        "project.life_years / project.project_life_years / "
        "parameters.project_life_years / parameters.life_years / "
        "Financing_Terms.tenor_years, or a plausible '*life*' integer anywhere"
    )


def _extract_parameters(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize parameters required for v14 CFADS calculation.
    """

    # Project life (hard fail if absent)
    project_life_years = _extract_project_life_years(raw)

    # Core project properties
    capacity_mw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "capacity_mw"),
            ("project", "capacity"),
            ("parameters", "capacity_mw"),
            "capacity_mw",
        )
    )

    capacity_factor_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "capacity_factor_pct"),
            ("project", "capacity_factor"),
            ("parameters", "capacity_factor_pct"),
            ("parameters", "capacity_factor"),
            "capacity_factor_pct",
            "capacity_factor",
        )
    )
    capacity_factor = _pct_to_decimal(capacity_factor_raw)

    degradation_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "degradation_pct"),
            ("project", "degradation"),
            ("parameters", "degradation_pct"),
            ("parameters", "degradation"),
            "degradation_pct",
            "degradation",
        )
    )
    degradation = _pct_to_decimal(degradation_raw) or 0.0

    grid_loss_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "grid_loss_pct"),
            ("parameters", "grid_loss_pct"),
            "grid_loss_pct",
        )
    )
    grid_loss_pct = _pct_to_decimal(grid_loss_raw) or 0.0

    # Tariff (LKR per kWh)
    tariff_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("tariff", "lkr_per_kwh"),
            ("tariff", "lkr_kwh"),
            ("tariff", "tariff_lkr_per_kwh"),
            ("revenue", "tariff_lkr_per_kwh"),
            "tariff_lkr_per_kwh",
            "tariff_lkr",
            "tariff",
        )
    )
    tariff_lkr_per_kwh = tariff_raw

    # OPEX (USD per year)
    opex_usd_per_year = _as_float_or_none(
        _resolve_first(
            raw,
            ("opex", "usd_per_year"),
            ("opex", "usd_annual"),
            ("opex", "annual_opex_usd"),
            ("costs", "opex_usd_per_year"),
            "opex_usd_per_year",
        )
    )

    # Statutory deductions
    success_fee_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("statutory", "success_fee_pct"),
            ("statutory", "success_fee"),
            ("parameters", "success_fee_pct"),
            "success_fee_pct",
            "success_fee",
        )
    )
    success_fee_pct = _pct_to_decimal(success_fee_raw) or 0.0

    env_surcharge_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("statutory", "env_surcharge_pct"),
            ("statutory", "environmental_surcharge_pct"),
            ("parameters", "env_surcharge_pct"),
            "env_surcharge_pct",
            "environmental_surcharge_pct",
        )
    )
    env_surcharge_pct = _pct_to_decimal(env_surcharge_raw) or 0.0

    social_levy_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("statutory", "social_levy_pct"),
            ("statutory", "social_services_levy_pct"),
            ("parameters", "social_levy_pct"),
            "social_levy_pct",
            "social_services_levy_pct",
        )
    )
    social_levy_pct = _pct_to_decimal(social_levy_raw) or 0.0

    # Tax / BOI structure
    corporate_tax_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("tax", "corporate_tax_rate_pct"),
            ("tax", "corporate_tax_rate"),
            ("project", "corporate_tax_rate_pct"),
            ("project", "corporate_tax_rate"),
            ("parameters", "corporate_tax_rate_pct"),
            ("parameters", "corporate_tax_rate"),
            "corporate_tax_rate_pct",
            "corporate_tax_rate",
        )
    )
    corporate_tax_rate = _pct_to_decimal(corporate_tax_raw)

    depreciation_years = as_int(
        _resolve_first(
            raw,
            ("tax", "depreciation_years"),
            ("parameters", "depreciation_years"),
            "depreciation_years",
        ),
        default=20,
    ) or 20

    tax_holiday_years = as_int(
        _resolve_first(
            raw,
            ("tax", "holiday_years"),
            ("tax", "tax_holiday_years"),
            ("parameters", "tax_holiday_years"),
            "tax_holiday_years",
        ),
        default=0,
    ) or 0

    tax_holiday_start_year = as_int(
        _resolve_first(
            raw,
            ("tax", "holiday_start_year"),
            ("tax", "tax_holiday_start_year"),
            ("parameters", "tax_holiday_start_year"),
            "tax_holiday_start_year",
        ),
        default=1,
    ) or 1

    enhanced_capital_allowance_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("tax", "enhanced_capital_allowance_pct"),
            ("parameters", "enhanced_capital_allowance_pct"),
            "enhanced_capital_allowance_pct",
        )
    )
    if enhanced_capital_allowance_raw and enhanced_capital_allowance_raw > 1:
        enhanced_capital_allowance_pct = enhanced_capital_allowance_raw / 100.0
    else:
        enhanced_capital_allowance_pct = enhanced_capital_allowance_raw or 1.0

    # Risk haircut
    risk_haircut_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("risk", "haircut_pct"),
            ("parameters", "risk_haircut_pct"),
            "risk_haircut_pct",
            "risk_haircut",
        )
    )
    risk_haircut_pct = _pct_to_decimal(risk_haircut_raw) or 0.0

    params: Dict[str, Any] = {
        "project_life_years": project_life_years,
        "capacity_mw": capacity_mw,
        "capacity_factor": capacity_factor,
        "degradation": degradation,
        "grid_loss_pct": grid_loss_pct,
        "tariff_lkr_per_kwh": tariff_lkr_per_kwh,
        "opex_usd_per_year": opex_usd_per_year,
        "success_fee_pct": success_fee_pct,
        "env_surcharge_pct": env_surcharge_pct,
        "social_levy_pct": social_levy_pct,
        "corporate_tax_rate": corporate_tax_rate,
        "depreciation_years": depreciation_years,
        "tax_holiday_years": tax_holiday_years,
        "tax_holiday_start_year": tax_holiday_start_year,
        "enhanced_capital_allowance_pct": enhanced_capital_allowance_pct,
        "risk_haircut_pct": risk_haircut_pct,
    }

    missing_or_invalid: List[str] = []

    def _check_required(name: str, predicate: Any) -> None:
        val = params.get(name, None)
        if not predicate(val):
            missing_or_invalid.append(name)

    _check_required("project_life_years", lambda v: isinstance(v, int) and v > 0)
    _check_required(
        "capacity_mw",
        lambda v: isinstance(v, (int, float)) and v is not None and v > 0,
    )
    _check_required(
        "capacity_factor",
        lambda v: isinstance(v, (int, float)) and 0 < v <= 1,
    )
    _check_required(
        "tariff_lkr_per_kwh",
        lambda v: isinstance(v, (int, float)) and v > 0,
    )
    _check_required(
        "opex_usd_per_year",
        lambda v: isinstance(v, (int, float)) and v >= 0,
    )
    _check_required(
        "corporate_tax_rate",
        lambda v: isinstance(v, (int, float)) and v 
    )

    if missing_or_invalid:
        raise ValueError(
            "Missing or invalid required fields for v14 cashflow: "
            + ", ".join(sorted(missing_or_invalid))
        )

    return params


# =============================================================================
# Public CFADS API
# =============================================================================


def calculate_single_year_cfads(
    params: Dict[str, Any],
    fx_rate: float,
    year: int,
    capex_total: Optional[float] = None,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
) -> Dict[str, float]:
    """Compute detailed CFADS breakdown for a single year."""
    gross_kwh, net_kwh = _calculate_net_production(
        float(params["capacity_mw"]),
        float(params["capacity_factor"]),
        float(params["degradation"]),
        float(params["grid_loss_pct"]),
        year,
    )
    revenue_lkr = _calculate_revenue_lkr(net_kwh, float(params["tariff_lkr_per_kwh"]))
    statutory = _calculate_statutory_deductions(
        revenue_lkr,
        float(params["success_fee_pct"]),
        float(params["env_surcharge_pct"]),
        float(params["social_levy_pct"]),
    )
    opex_lkr = _calculate_opex_lkr(float(params["opex_usd_per_year"]), fx_rate)
    pretax_cfads = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr

    tax, total_depr = calculate_tax_with_interest_shield(
        pretax_cfads=pretax_cfads,
        corporate_tax_rate=float(params["corporate_tax_rate"]),
        capex_total=capex_total,
        depreciation_years=int(params["depreciation_years"]),
        interest_expense_lkr=interest_expense_lkr,
        year_index=year,
        tax_holiday_years=int(params.get("tax_holiday_years", 0)),
        tax_holiday_start_year=int(params.get("tax_holiday_start_year", 1)),
        enhanced_capital_allowance_pct=float(
            params.get("enhanced_capital_allowance_pct", 1.0)
        ),
    )
    posttax_cfads = pretax_cfads - tax
    cfads_final = _apply_risk_haircut(posttax_cfads, float(params["risk_haircut_pct"]))

    result: Dict[str, float] = {
        "year": float(year + 1),
        "gross_kwh": gross_kwh,
        "grid_loss": gross_kwh - net_kwh,
        "net_kwh": net_kwh,
        "revenue_lkr": revenue_lkr,
        "success_fee": statutory["success_fee"],
        "env_surcharge": statutory["environmental_surcharge"],
        "social_levy": statutory["social_services_levy"],
        "total_statutory_deductions": statutory["total_statutory_deductions"],
        "opex_usd": float(params["opex_usd_per_year"]),
        "fx_rate": fx_rate,
        "opex_lkr": opex_lkr,
        "pretax_cfads": pretax_cfads,
        "total_depreciation": total_depr,
        "interest_expense_lkr": interest_expense_lkr,
        "taxable_income": max(0.0, pretax_cfads - total_depr - interest_expense_lkr),
        "tax": tax,
        "posttax_cfads": posttax_cfads,
        "risk_haircut_amount": posttax_cfads - cfads_final,
        "cfads_final_lkr": cfads_final,
    }
    if verbose:
        logger.info("Year %d CFADS: %s", year + 1, result)
    return result


def build_annual_cfads(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    verbose: bool = False,
) -> List[float]:
    """Return list of CFADS (LKR) for each project year."""
    params = _extract_parameters(p)
    years = int(params["project_life_years"])
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = as_float(get_nested(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years

    cfads_list: List[float] = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = (
            interest_expense_series[year]
            if year < len(interest_expense_series)
            else 0.0
        )
        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_total=capex_total,
            interest_expense_lkr=interest_lkr,
            verbose=verbose,
        )
        cfads_list.append(result["cfads_final_lkr"])

    logger.info(
        "Calculated CFADS for %d years, range: %.0f to %.0f",
        years,
        min(cfads_list) if cfads_list else 0.0,
        max(cfads_list) if cfads_list else 0.0,
    )
    return cfads_list


def build_annual_rows(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    """Return list of per-year breakdown rows including CFADS in USD."""
    params = _extract_parameters(p)
    years = int(params["project_life_years"])
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = as_float(get_nested(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years

    rows: List[Dict[str, float]] = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = (
            interest_expense_series[year]
            if year < len(interest_expense_series)
            else 0.0
        )
        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_total=capex_total,
            interest_expense_lkr=interest_lkr,
            verbose=False,
        )
        revenue_lkr = result["revenue_lkr"]
        cfads_final_lkr = result["cfads_final_lkr"]
        if fx_rate > 0:
            result["revenue_usd"] = revenue_lkr / fx_rate
            result["cfads_usd"] = cfads_final_lkr / fx_rate
        else:
            result["revenue_usd"] = 0.0
            result["cfads_usd"] = 0.0
        rows.append(result)
    return rows


# =============================================================================
# Schema registration for v14 cashflow
# =============================================================================


def _register_cashflow_schema() -> None:
    """
    Register the core v14 cashflow-required fields with the global schema
    registry. Mirrors the checks in _extract_parameters.
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
            and float(v) > 0.0,
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
    ]

    register_required_fields("cashflow", specs)


try:  # pragma: no cover
    _register_cashflow_schema()
except Exception:
    # Never allow schema registration to break the core finance engine
    pass

    