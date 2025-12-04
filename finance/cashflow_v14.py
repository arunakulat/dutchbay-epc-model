"""Cash flow engine for DutchBay V14 (CFADS and annual rows).

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
- calculate_single_year_cfads(...) -> dict[str, float]

`build_annual_rows` is the primary feedstock for:
- debt_v14.plan_debt (DSCR / covenants)
- contracts_v14.build_cashflow_result_from_annual_rows (CashflowResult)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from analytics.config_schema import RequiredFieldSpec, register_required_fields

logger = logging.getLogger(__name__)

# =============================================================================
# Generic helpers
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


def get_nested(d: dict[str, Any], keys: list[str], default: Any = None) -> Any:
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
    Interpret a numeric as a percentage if > 1.0, otherwise as a decimal.

    Examples
    --------
    24   -> 0.24
    0.24 -> 0.24
    """
    if raw is None:
        return None
    if raw > 1.0:
        return raw / 100.0
    return raw


def _resolve_first(cfg: dict[str, Any], *candidates: Any) -> Any:
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
# Core production / CFADS helpers
# =============================================================================


def _calculate_net_production(
    capacity_mw: float,
    capacity_factor: float,
    degradation: float,
    grid_loss_pct: float,
    year: int,
) -> tuple[float, float]:
    """
    Calculate gross and net kWh for a given year.

    Parameters
    ----------
    capacity_mw :
        Installed capacity (MW).
    capacity_factor :
        Net capacity factor (decimal).
    degradation :
        Annual degradation rate (decimal).
    grid_loss_pct :
        Grid losses (decimal share of gross).
    year :
        Zero-based year index (0 = first operating year).
    """
    hours_per_year = 8760.0
    effective_cf = capacity_factor * ((1.0 - degradation) ** year)
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
) -> dict[str, float]:
    """
    Calculate statutory charges as percentages of revenue.

    All arguments are decimals (e.g. 0.01 = 1%).
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
    return cfads_lkr * (1.0 - risk_haircut_pct)


# =============================================================================
# Tax & Depreciation (BOI / Inland Revenue Act)
# =============================================================================


def _compute_depreciation_schedule(
    capex_total: Optional[float],
    depreciation_years: int,
    enhanced_capital_allowance_pct: float,
) -> list[float]:
    """
    Build a straight-line depreciation schedule over depreciation_years.

    If capex_total is None or depreciation_years <= 0, an empty schedule
    is returned.
    """
    if capex_total is None or depreciation_years <= 0:
        return []
    total_depreciable = capex_total * enhanced_capital_allowance_pct
    annual = total_depreciable / float(depreciation_years)
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
) -> tuple[float, float]:
    """
    Calculate BOI-compliant tax with interest shield for a given year.

    Parameters
    ----------
    pretax_cfads :
        CFADS before tax and interest shield.
    corporate_tax_rate :
        Headline corporate tax rate (decimal; 0.24 = 24%).
        If <= 0, no tax is applied.
    capex_total :
        Total depreciable capex in LKR (or None to disable depreciation).
    depreciation_years :
        Straight-line depreciation horizon in years.
    interest_expense_lkr :
        Interest expense for the year (LKR).
    year_index :
        Zero-based year index.
    tax_holiday_years :
        Number of tax holiday years (0 = none).
    tax_holiday_start_year :
        1-based start year of the tax holiday.
    enhanced_capital_allowance_pct :
        Factor for enhanced capital allowance (e.g. 1.2 for 120%).

    Returns
    -------
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

    if capex_total is None or depreciation_years <= 0:
        depreciation_schedule: list[float] = []
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
# FX and project life extraction
# =============================================================================


def _fx_curve(p: dict[str, Any], years: int) -> list[float]:
    """
    Build an FX curve (LKR per USD) for `years`.

    Supports:
      fx:
        curve: [ .. ]
      fx:
        curve_lkr_per_usd: [ .. ]
      fx:
        start_lkr_per_usd: 375
        annual_depr_pct: 3   # or 0.03
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

            out: list[float] = []
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
        out2: list[float] = []
        cur2 = start_val
        for _ in range(years):
            out2.append(cur2)
            cur2 *= 1.0 + depr
        return out2

    # Final hard fallback – should be rare
    default_fx = 375.0
    logger.warning(
        "FX configuration missing or invalid; "
        "falling back to flat %.2f LKR/USD for %d years",
        default_fx,
        years,
    )
    return [default_fx] * years


def _extract_project_life_years(raw: dict[str, Any]) -> int:
    """
    Robust extraction of project life (in years) for v14.

    Tries explicit fields first, then falls back to a heuristic scan.
    """
    explicit_candidates: list[tuple[tuple[str, ...], str]] = [
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

    from collections.abc import Mapping, Sequence

    hits: list[tuple[str, int]] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
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
                t in path_str for t in ("life", "lifetime", "horizon", "year", "yrs")
            ):
                hits.append(("/".join(path), iv))

    walk(raw, ())

    if hits:
        chosen_path, chosen_val = hits[0]
        logger.warning(
            "Project life not found in explicit fields; "
            "using heuristic match %r = %d years",
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


# =============================================================================
# Parameter extraction
# =============================================================================


def _extract_parameters(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Extract and normalize parameters required for v14 CFADS calculation.

    Returns
    -------
    dict[str, Any]
        Normalized parameters. Raises ValueError if required fields are
        missing or invalid.
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

    depreciation_years = (
        as_int(
            _resolve_first(
                raw,
                ("tax", "depreciation_years"),
                ("parameters", "depreciation_years"),
                "depreciation_years",
            ),
            default=20,
        )
        or 20
    )

    tax_holiday_years = (
        as_int(
            _resolve_first(
                raw,
                ("tax", "holiday_years"),
                ("tax", "tax_holiday_years"),
                ("parameters", "tax_holiday_years"),
                "tax_holiday_years",
            ),
            default=0,
        )
        or 0
    )

    tax_holiday_start_year = (
        as_int(
            _resolve_first(
                raw,
                ("tax", "holiday_start_year"),
                ("tax", "tax_holiday_start_year"),
                ("parameters", "tax_holiday_start_year"),
                "tax_holiday_start_year",
            ),
            default=1,
        )
        or 1
    )

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

    params: dict[str, Any] = {
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

    missing_or_invalid: list[str] = []

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
        lambda v: isinstance(v, (int, float))
        and v is not None
        and 0.0 < float(v) <= 1.0,
    )
    _check_required(
        "tariff_lkr_per_kwh",
        lambda v: isinstance(v, (int, float)) and v is not None and v >= 0,
    )
    _check_required(
        "opex_usd_per_year",
        lambda v: isinstance(v, (int, float)) and v is not None and v >= 0,
    )
    _check_required(
        "corporate_tax_rate",
        lambda v: isinstance(v, (int, float))
        and v is not None
        and 0.0 <= float(v) <= 1.0,
    )

    if missing_or_invalid:
        raise ValueError(
            "Missing or invalid required fields for v14 cashflow: "
            + ", ".join(sorted(missing_or_invalid))
        )

    return params


# =============================================================================
# Parameter validation (public API)
# =============================================================================


def validate_parameters(config: dict[str, Any]) -> list[str]:
    """Validate cashflow parameters from configuration.

    This is a human-readable guard that complements schema_guard.

    Raises ValueError with detailed message if validation fails; returns an
    empty list on success (backward compatible).

    Key rules (decimals after normalization):
      - 0.0 <= corporate_tax_rate <= 1.0
      - project_life_years >= 1
      - capacity_mw > 0
      - 0 < capacity_factor <= 1.0
      - tariff_lkr_per_kwh >= 0
      - opex_usd_per_year >= 0
    """
    errors: list[str] = []

    # Extract and validate tax rate
    tax_rate_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("tax", "corporate_tax_rate_pct"),
            ("tax", "corporate_tax_rate"),
            ("project", "corporate_tax_rate_pct"),
            "corporate_tax_rate_pct",
            "corporate_tax_rate",
        )
    )

    if tax_rate_raw is None:
        errors.append("corporate_tax_rate: missing (required field)")
    else:
        tax_rate = _pct_to_decimal(tax_rate_raw)
        if tax_rate is None or not (0.0 <= tax_rate <= 1.0):
            errors.append(
                "corporate_tax_rate: "
                f"{tax_rate} out of range "
                "(must be 0.0-1.0 or 0-100%)"
            )

    # Extract and validate project life
    try:
        project_life = _extract_project_life_years(config)
        if project_life < 1:
            errors.append(f"project_life_years: {project_life} invalid (must be >= 1)")
    except ValueError as e:
        errors.append(f"project_life_years: {e}")

    # Validate capacity
    capacity_mw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "capacity_mw"),
            ("project", "capacity"),
            "capacity_mw",
        )
    )
    if capacity_mw is None or capacity_mw <= 0:
        errors.append(f"capacity_mw: {capacity_mw} invalid (must be > 0)")

    # Validate capacity factor
    cf_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "capacity_factor_pct"),
            ("project", "capacity_factor"),
            "capacity_factor_pct",
            "capacity_factor",
        )
    )
    if cf_raw is None:
        errors.append("capacity_factor: missing (required field)")
    else:
        cf = _pct_to_decimal(cf_raw)
        if cf is None or not (0.0 < cf <= 1.0):
            errors.append(
                f"capacity_factor: {cf} out of range (must be 0.0-1.0 or 0-100%)"
            )

    # Validate tariff (allow zero for edge case testing)
    tariff = _as_float_or_none(
        _resolve_first(
            config,
            ("tariff", "lkr_per_kwh"),
            ("tariff", "tariff_lkr_per_kwh"),
            "tariff_lkr_per_kwh",
            "tariff",
        )
    )
    if tariff is None or tariff < 0:
        errors.append(f"tariff_lkr_per_kwh: {tariff} invalid (must be >= 0)")

    # Validate OPEX
    opex = _as_float_or_none(
        _resolve_first(
            config,
            ("opex", "usd_per_year"),
            ("opex", "annual_opex_usd"),
            "opex_usd_per_year",
        )
    )
    if opex is None or opex < 0:
        errors.append(f"opex_usd_per_year: {opex} invalid (must be >= 0)")

    # Optional field validations (if present)
    degradation_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "degradation_pct"),
            "degradation_pct",
        )
    )
    if degradation_raw is not None:
        deg = _pct_to_decimal(degradation_raw)
        if deg and not (0.0 <= deg < 1.0):
            errors.append(f"degradation: {deg} out of range (must be 0.0-1.0)")

    grid_loss_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "grid_loss_pct"),
            "grid_loss_pct",
        )
    )
    if grid_loss_raw is not None:
        loss = _pct_to_decimal(grid_loss_raw)
        if loss and not (0.0 <= loss < 1.0):
            errors.append(f"grid_loss_pct: {loss} out of range (must be 0.0-1.0)")

    risk_haircut_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("risk", "haircut_pct"),
            "risk_haircut_pct",
        )
    )
    if risk_haircut_raw is not None:
        risk = _pct_to_decimal(risk_haircut_raw)
        if risk and not (0.0 <= risk < 1.0):
            errors.append(f"risk_haircut_pct: {risk} out of range (must be 0.0-1.0)")

    depreciation_years = as_int(
        _resolve_first(
            config,
            ("tax", "depreciation_years"),
            "depreciation_years",
        )
    )
    if depreciation_years is not None and depreciation_years < 1:
        errors.append(
            f"depreciation_years: {depreciation_years} invalid (must be >= 1)"
        )

    # Raise comprehensive error if any validation failed
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(
            f"  • {err}" for err in errors
        )
        raise ValueError(error_msg)

    # Return empty list on success (backward compatible)
    return []


# =============================================================================
# Internal context preparation
# =============================================================================


def _prepare_cashflow_context(
    p: dict[str, Any],
    fx_curve: Optional[list[float]],
    capex_total: Optional[float],
    interest_expense_series: Optional[list[float]],
) -> tuple[dict[str, Any], list[float], Optional[float], list[float], int]:
    """
    Shared context builder for build_annual_cfads and build_annual_rows.

    Returns
    -------
    (params, fx_curve_resolved, capex_total_resolved, interest_series, years)
    """
    # Validate parameters before expensive calculations
    validate_parameters(p)

    params = _extract_parameters(p)
    years = int(params["project_life_years"])

    if fx_curve is None:
        fx_curve = _fx_curve(p, years)
    else:
        # Ensure we have at least `years` FX points; extend with last known.
        if len(fx_curve) < years and fx_curve:
            fx_curve = fx_curve + [fx_curve[-1]] * (years - len(fx_curve))
        elif not fx_curve:
            fx_curve = _fx_curve(p, years)

    if capex_total is None:
        capex_usd = as_float(get_nested(p, ["capex", "usd_total"], None))
        if capex_usd is not None:
            capex_total = capex_usd * fx_curve[0]

    if interest_expense_series is None:
        interest_expense_series = [0.0] * years
    else:
        # Pad or trim to project life
        if len(interest_expense_series) < years:
            interest_expense_series = interest_expense_series + [0.0] * (
                years - len(interest_expense_series)
            )
        elif len(interest_expense_series) > years:
            interest_expense_series = interest_expense_series[:years]

    return params, fx_curve, capex_total, interest_expense_series, years


# =============================================================================
# Public CFADS API
# =============================================================================


def calculate_single_year_cfads(
    params: dict[str, Any],
    fx_rate: float,
    year: int,
    capex_total: Optional[float] = None,
    interest_expense_lkr: float = 0.0,
    verbose: bool = False,
) -> dict[str, float]:
    """Compute detailed CFADS breakdown for a single year.

    Parameters
    ----------
    params :
        Normalized parameter dict from _extract_parameters.
    fx_rate :
        LKR per USD FX rate for the given year.
    year :
        Zero-based year index.
    capex_total :
        Total capex in LKR (used for depreciation).
    interest_expense_lkr :
        Interest expense in LKR for the year.
    verbose :
        If True, log the per-year CFADS breakdown.

    Returns
    -------
    dict[str, float]
        Per-year breakdown, including `cfads_final_lkr` which is the
        canonical CFADS used by debt_v14 and CashflowResult.
    """
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

    result: dict[str, float] = {
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
    p: dict[str, Any],
    fx_curve: Optional[list[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[list[float]] = None,
    verbose: bool = False,
) -> list[float]:
    """Return list of CFADS (LKR) for each project year.

    This is the primary numeric surface used by debt_v14 and covenant tests.
    """
    params, fx_curve_resolved, capex_total_resolved, interest_series, years = (
        _prepare_cashflow_context(p, fx_curve, capex_total, interest_expense_series)
    )

    cfads_list: list[float] = []
    for year in range(years):
        fx_rate = fx_curve_resolved[year]
        interest_lkr = interest_series[year]
        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_total=capex_total_resolved,
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
    p: dict[str, Any],
    fx_curve: Optional[list[float]] = None,
    capex_total: Optional[float] = None,
    interest_expense_series: Optional[list[float]] = None,
) -> list[dict[str, float]]:
    """Return list of per-year breakdown rows including CFADS in USD.

    This is the canonical *row-wise* surface for:
      - debt_v14.plan_debt (DSCR / covenants)
      - CashflowResult (via contracts_v14)
      - analytics exports and dashboards.
    """
    params, fx_curve_resolved, capex_total_resolved, interest_series, years = (
        _prepare_cashflow_context(p, fx_curve, capex_total, interest_expense_series)
    )

    rows: list[dict[str, float]] = []
    for year in range(years):
        fx_rate = fx_curve_resolved[year]
        interest_lkr = interest_series[year]

        result = calculate_single_year_cfads(
            params=params,
            fx_rate=fx_rate,
            year=year,
            capex_total=capex_total_resolved,
            interest_expense_lkr=interest_lkr,
            verbose=False,
        )
        revenue_lkr = result["revenue_lkr"]
        cfads_final_lkr = result["cfads_final_lkr"]

        if fx_rate > 0.0:
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
    ]

    register_required_fields("cashflow", specs)


try:  # pragma: no cover
    _register_cashflow_schema()
except Exception:
    # Never allow schema registration to break the core finance engine.
    pass

__all__ = [
    "validate_parameters",
    "calculate_single_year_cfads",
    "build_annual_cfads",
    "build_annual_rows",
]
# EOF
