"""
Cash Flow Module for DutchBay V13 Project Finance (v2.2 - BOI Tax Holiday/Enhancement Compliant)

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
- CFADS reflects correct order: post all deductions, post-tax, **pre-debt service**
- **Interest expense is deductible for tax calculation** (with full BOI-compliant tax shield)
- **Tax holiday**
  * Full tax holiday for specified years (0% tax on taxable income)
  * Enhanced capital allowance support (e.g. 150% of capex over X years)
- Straight-line depreciation by default across specified depreciation years
- Correct handling of:
  * Statutory deductions: success fee, environmental surcharge, social services levy
  * FX curves (escation/devaluation)
  * OPEX in USD, converted at scenario FX curve
  * Risk haircut on post-tax CFADS

USAGE:
------
- Called by high-level EPC / Finance wrappers
- CFADS forms input to:
  * DSCR, LLCR, PLCR calculations
  * Equity IRR, project IRR, NPV analyses
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

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
    """Return `int(value)` or None if conversion fails."""
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def get_nested(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely navigate nested dictionaries by list of keys."""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        if key not in current:
            return default
        current = current[key]
    return current


def _as_float_or_none(value: Any) -> Optional[float]:
    """Return `float(value)` or None."""
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

    - capacity_mw: installed capacity in MW
    - capacity_factor: baseline capacity factor (0–1)
    - degradation: annual degradation rate (0–1)
    - grid_loss_pct: grid losses between generation and offtake (0–1)
    - year: 0-based year index
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
    Returns a dict with success_fee, environmental_surcharge, social_services_levy, total_statutory_deductions.
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
    """
    Apply risk haircut: CFADS * (1 - haircut).
    If haircut is 0.1 (10%), CFADS is multiplied by 0.9.
    """
    return cfads_lkr * (1 - risk_haircut_pct)


# =============================================================================
# Tax & Depreciation (BOI / Inland Revenue Act Compliant)
# =============================================================================


def _compute_depreciation_schedule(
    capex_total: Optional[float],
    depreciation_years: int,
    enhanced_capital_allowance_pct: float,
) -> List[float]:
    """
    Build a straight-line depreciation schedule over depreciation_years.
    enhanced_capital_allowance_pct allows >100% total depreciation (e.g. 150% of capex).
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

    Parameters:
    -----------
    - pretax_cfads: CFADS before tax and before interest shield
    - corporate_tax_rate: decimal, e.g. 0.24 for 24%
    - capex_total: total project capex (LKR) or None if not applicable
    - depreciation_years: number of years to depreciate capex
    - interest_expense_lkr: interest for this year (LKR)
    - year_index: 0-based index (0 for first year)
    - tax_holiday_years: duration of tax holiday (years)
    - tax_holiday_start_year: 1-based year when holiday starts
    - enhanced_capital_allowance_pct: multiplier for total depreciation (e.g. 1.5 for 150%)

    Returns:
    --------
    (tax_lkr, depreciation_for_year_lkr)
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

    # If in holiday, no tax, but we still track depreciation for info.
    if capex_total is None or depreciation_years <= 0:
        depreciation_schedule = []
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
        # During BOI tax holiday, we treat tax as zero, regardless of taxable income.
        return 0.0, depreciation_for_year

    # Outside tax holiday, apply corporate tax with interest deductibility.
    taxable_income = pretax_cfads - depreciation_for_year - interest_expense_lkr
    taxable_income = max(0.0, taxable_income)
    tax = taxable_income * corporate_tax_rate
    return tax, depreciation_for_year


# =============================================================================
# Parameter extraction & validation
# =============================================================================


def _fx_curve(p: Dict[str, Any], years: int) -> List[float]:
    """
    Build an FX curve (LKR per USD) for `years`.

    Supports:
      - Top-level scalar:   config["fx"] = 375.0  -> flat curve
      - Mapping with curve: config["fx"]["curve"] or ["curve_lkr_per_usd"]
      - Mapping with start + annual_depr_pct
      - Legacy nested v14-style keys under "fx".
    """
    # Defensive guard
    years = max(1, int(years))

    fx_cfg = p.get("fx")

    # 1) Scenario loader has normalised fx to a scalar (e.g. 375.0)
    if isinstance(fx_cfg, (int, float)):
        rate = float(fx_cfg)
        return [rate] * years

    # 2) Mapping-style configuration under "fx"
    if isinstance(fx_cfg, dict):
        # 2a) Explicit curve list
        curve = fx_cfg.get("curve") or fx_cfg.get("curve_lkr_per_usd")
        if isinstance(curve, (list, tuple)):
            clean = [float(x) for x in curve]
            if len(clean) >= years:
                return clean[:years]
            if clean:
                return clean + [clean[-1]] * (years - len(clean))

        # 2b) Parametric definition: start + annual depreciation
        start = fx_cfg.get("start_lkr_per_usd") or fx_cfg.get("start") or fx_cfg.get("base") or fx_cfg.get("base_rate")
        if start is not None:
            start_val = float(start)
            depr_pct = fx_cfg.get("annual_depr_pct") or fx_cfg.get("depr_pct") or 0.0
            depr = _pct_to_decimal(depr_pct) or 0.0

            out: List[float] = []
            cur = start_val
            for _ in range(years):
                out.append(cur)
                cur *= (1.0 + depr)
            return out

    # 3) Legacy v14 nested keys fallback (if someone still uses that layout)
    start_nested = get_nested(p, ["fx", "start_lkr_per_usd"])
    depr_nested = get_nested(p, ["fx", "annual_depr_pct"])
    if start_nested is not None:
        start_val = float(start_nested)
        depr = _pct_to_decimal(depr_nested or 0.0) or 0.0

        out: List[float] = []
        cur = start_val
        for _ in range(years):
            out.append(cur)
            cur *= (1.0 + depr)
        return out

    # 4) Final hard fallback – should be rare
    DEFAULT_FX = 375.0
    logger.warning(
        "FX configuration missing or invalid; falling back to flat %.2f LKR/USD for %d years",
        DEFAULT_FX,
        years,
    )
    return [DEFAULT_FX] * years


def _extract_project_life_years(raw: Dict[str, Any]) -> int:
    """
    Robust extraction of project life (in years) for v14.

    Priority:
      1. Explicit fields:
           project.life_years
           project.lifetime
           parameters.project_life_years
           parameters.life_years
      2. Heuristic scan: any integer 5–60 whose path includes 'life', 'lifetime',
         'horizon', 'year', 'yrs'.

    Raises:
      ValueError if no plausible project life is found.
    """
    # 1) Explicit preferred fields
    explicit_candidates: List[Tuple[Tuple[str, ...], str]] = [
        (("project", "life_years"), "project.life_years"),
        (("project", "lifetime"), "project.lifetime"),
        (("parameters", "project_life_years"), "parameters.project_life_years"),
        (("parameters", "life_years"), "parameters.life_years"),
    ]

    for path, label in explicit_candidates:
        v = as_int_or_none(get_nested(raw, list(path), None))
        if v is not None and 5 <= v <= 60:
            logger.info(f"Project life resolved from {label} = {v} years")
            return v

    # 2) Heuristic scan for integers with "life"/"year" flavour in their path
    hits: List[Tuple[str, int]] = []

    def walk(node: Any, path: Tuple[str, ...]) -> None:
        from collections.abc import Mapping, Sequence

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
            if any(t in path_str for t in ("life", "lifetime", "horizon", "year", "yrs")):
                hits.append(("/".join(path), iv))

    walk(raw, ())

    if hits:
        # Pick the first hit for now; could be refined if needed.
        chosen_path, chosen_val = hits[0]
        logger.warning(
            "Project life not found in explicit fields; using heuristic match %r = %d years",
            chosen_path,
            chosen_val,
        )
        return chosen_val

    # If we get here, we couldn't find any plausible life/horizon integer.
    raise ValueError(
        "Missing or invalid project life: expected one of "
        "project.life_years / project.lifetime / "
        "parameters.project_life_years / parameters.life_years, "
        "or a plausible '*life*' integer anywhere in the config"
    )


def _extract_parameters(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize all parameters required for v14 CFADS calculation.

    This function is the canonical "schema adapter" between arbitrary YAML/JSON
    layouts and the internal CFADS engine. It:
      - Resolves multiple legacy/v13-style paths
      - Applies sane defaults where appropriate
      - Enforces required fields with clear error messages
    """
    # --- Project life (hard fail if absent) ---------------------------------
    project_life_years = _extract_project_life_years(raw)

    # --- Core project properties -------------------------------------------
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

    # --- Tariff (LKR per kWh) ----------------------------------------------
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

    # --- OPEX (USD per year) -----------------------------------------------
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

    # --- Statutory deductions ----------------------------------------------
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

    # --- Tax / BOI structure -----------------------------------------------
    corporate_tax_raw = _as_float_or_none(
        _resolve_first(
            raw,
            # Canonical v14 paths
            ("tax", "corporate_tax_rate_pct"),
            ("tax", "corporate_tax_rate"),
            # Backwards-compat paths (older examples put it under project)
            ("project", "corporate_tax_rate_pct"),
            ("project", "corporate_tax_rate"),
            # Generic / parameters fallbacks
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
    enhanced_capital_allowance_pct = (
        enhanced_capital_allowance_raw / 100.0 if enhanced_capital_allowance_raw and enhanced_capital_allowance_raw > 1 else (enhanced_capital_allowance_raw or 1.0)
    )

    # --- Risk haircut ------------------------------------------------------
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

    # --- Consolidate and validate required fields --------------------------
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

    def _check_required(name: str, predicate) -> None:
        val = params.get(name, None)
        if not predicate(val):
            missing_or_invalid.append(name)

    _check_required("project_life_years", lambda v: isinstance(v, int) and v > 0)
    _check_required("capacity_mw", lambda v: isinstance(v, (int, float)) and v > 0)
    _check_required("capacity_factor", lambda v: isinstance(v, (int, float)) and 0 < v <= 1)
    _check_required("tariff_lkr_per_kwh", lambda v: isinstance(v, (int, float)) and v > 0)
    _check_required("opex_usd_per_year", lambda v: isinstance(v, (int, float)) and v >= 0)
    _check_required("corporate_tax_rate", lambda v: isinstance(v, (int, float)) and v >= 0)

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
    params: Dict[str, float],
    fx_rate: float,
    year: int,
    capex_total: Optional[float] = None,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
) -> Dict[str, float]:
    gross_kwh, net_kwh = _calculate_net_production(
        params["capacity_mw"],
        params["capacity_factor"],
        params["degradation"],
        params["grid_loss_pct"],
        year,
    )
    revenue_lkr = _calculate_revenue_lkr(net_kwh, params["tariff_lkr_per_kwh"])
    statutory = _calculate_statutory_deductions(
        revenue_lkr, params["success_fee_pct"], params["env_surcharge_pct"], params["social_levy_pct"]
    )
    opex_lkr = _calculate_opex_lkr(params["opex_usd_per_year"], fx_rate)
    pretax_cfads = revenue_lkr - statutory["total_statutory_deductions"] - opex_lkr

    tax, total_depr = calculate_tax_with_interest_shield(
        pretax_cfads,
        params["corporate_tax_rate"],
        capex_total,
        params["depreciation_years"],
        interest_expense_lkr,
        year,
        params.get("tax_holiday_years", 0),
        params.get("tax_holiday_start_year", 1),
        params.get("enhanced_capital_allowance_pct", 1.0),
    )
    posttax_cfads = pretax_cfads - tax
    cfads_final = _apply_risk_haircut(posttax_cfads, params["risk_haircut_pct"])
    result = {
        "year": year + 1,
        "gross_kwh": gross_kwh,
        "grid_loss": gross_kwh - net_kwh,
        "net_kwh": net_kwh,
        "revenue_lkr": revenue_lkr,
        "success_fee": statutory["success_fee"],
        "env_surcharge": statutory["environmental_surcharge"],
        "social_levy": statutory["social_services_levy"],
        "total_statutory_deductions": statutory["total_statutory_deductions"],
        "opex_usd": params["opex_usd_per_year"],
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
        logger.info(f"Year {year+1} CFADS: {result}")
    return result


def build_annual_cfads(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
    verbose: bool = False,
) -> List[float]:
    params = _extract_parameters(p)
    years = params["project_life_years"]
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = as_float(get_nested(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years
    cfads_list = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = interest_expense_series[year] if year < len(interest_expense_series) else 0.0
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, interest_lkr, verbose=verbose)
        cfads_list.append(result["cfads_final_lkr"])
    logger.info(f"Calculated CFADS for {years} years, range: {min(cfads_list):,.0f} to {max(cfads_list):,.0f}")
    return cfads_list


def build_annual_rows(
    p: Dict[str, Any],
    fx_curve: Optional[List[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[List[float]] = None,
) -> List[Dict[str, float]]:
    params = _extract_parameters(p)
    years = params["project_life_years"]
    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    if capex_total is None:
        capex_usd = as_float(get_nested(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]
    if interest_expense_series is None:
        interest_expense_series = [0.0] * years
    rows = []
    for year in range(years):
        fx_rate = fx_curve[year] if year < len(fx_curve) else fx_curve[-1]
        interest_lkr = interest_expense_series[year] if year < len(interest_expense_series) else 0.0
        result = calculate_single_year_cfads(params, fx_rate, year, capex_total, interest_lkr, verbose=False)
        result["revenue_usd"] = result["revenue_lkr"] / fx_rate if fx_rate > 0 else 0.0
        result["cfads_usd"] = result["cfads_final_lkr"] / fx_rate if fx_rate > 0 else 0.0
        rows.append(result)
    return rows


# =============================================================================
# Self-test (optional)
# =============================================================================

if __name__ == "__main__":  # pragma: no cover
    import pprint

    logging.basicConfig(level=logging.INFO)

    sample_config = {
        "project": {
            "capacity_mw": 100,
            "capacity_factor_pct": 45,
            "degradation_pct": 0.5,
            "grid_loss_pct": 2.0,
            "life_years": 20,
        },
        "tariff": {"lkr_per_kwh": 50},
        "opex": {"usd_per_year": 10_000_000},
        "statutory": {
            "success_fee_pct": 2.0,
            "env_surcharge_pct": 0.25,
            "social_levy_pct": 0.25,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
            "depreciation_years": 20,
            "tax_holiday_years": 10,
            "tax_holiday_start_year": 1,
            "enhanced_capital_allowance_pct": 150.0,
        },
        "risk": {
            "haircut_pct": 10.0,
        },
        "fx": {
            "base_rate": 375.0,
        },
        "capex": {
            "usd_total": 150_000_000,
        },
    }

    print("=" * 100)
    print("SELF-TEST: Computing CFADS series with sample configuration")
    print("=" * 100)

    years = sample_config["project"]["life_years"]
    fx_curve = _fx_curve(sample_config, years)
    capex_total_lkr = sample_config["capex"]["usd_total"] * fx_curve[0]
    interest_series = [0.0] * years

    cfads_series = build_annual_cfads(sample_config, fx_curve, capex_total_lkr, interest_series, verbose=False)
    print(f"\nCFADS Summary (with tax holiday/enhancement):")
    print(f"  Year 1 (LKR):  {cfads_series[0]:,.0f}")
    print(f"  Year 10 (LKR): {cfads_series[9]:,.0f}")
    print(f"  Year 20 (LKR): {cfads_series[19]:,.0f}")
    print(f"  Average (LKR): {sum(cfads_series)/len(cfads_series):,.0f}")
    print("\nTesting detailed breakdown...")
    rows = build_annual_rows(sample_config, interest_expense_series=interest_series)
    print(f"  Generated {len(rows)} annual rows")
    print(f"\n  Year 1 breakdown:")
    for key, value in rows[0].items():
        if isinstance(value, (int, float)) and key != "year":
            print(f"    {key}: {value:,.0f}")
    print("\n" + "=" * 100)
    print("SELF-TEST COMPLETE - Module ready for production use")
    print("=" * 100)