from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from .cashflow_v14_contracts import CashflowParams
from .cashflow_v14_utils import (
    _as_float_or_none,
    _pct_to_decimal,
    _resolve_first,
    as_int,
    as_int_or_none,
)

logger = logging.getLogger(__name__)


def _extract_project_life_years(
    raw: Dict[str, Any],
    *,
    log: bool = True,
) -> int:
    """
    Robust extraction of project life (in years) for v14.

    Tries explicit fields first, then falls back to a heuristic scan.

    Parameters
    ----------
    raw :
        Raw configuration dict.
    log :
        If True, emit INFO / WARNING logs when resolving project life.
        If False, perform the same resolution silently (no logs).
    """
    explicit_candidates: List[Tuple[Tuple[str, ...], str]] = [
        (("project", "life_years"), "project.life_years"),
        (("project", "project_life_years"), "project.project_life_years"),
        (("parameters", "project_life_years"), "parameters.project_life_years"),
        (("parameters", "life_years"), "parameters.life_years"),
        (("Financing_Terms", "tenor_years"), "Financing_Terms.tenor_years"),
    ]

    from .cashflow_v14_utils import get_nested  # local import to avoid cycle

    for path, label in explicit_candidates:
        v = as_int_or_none(get_nested(raw, list(path), None))
        if v is not None and 5 <= v <= 60:
            if log:
                logger.info("Project life resolved from %s = %d years", label, v)
            return v

    from collections.abc import Mapping
    from collections.abc import Sequence as Seq  # local alias to avoid conflict

    hits: List[Tuple[str, int]] = []

    def walk(node: Any, path: Tuple[str, ...]) -> None:
        if isinstance(node, Mapping):
            for k, v in node.items():
                walk(v, path + (str(k),))
        elif isinstance(node, Seq) and not isinstance(node, (str, bytes)):
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
        if log:
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


def _build_cashflow_params(raw: Dict[str, Any]) -> CashflowParams:
    """
    Extract and normalize parameters required for v14 CFADS calculation.

    Raises ValueError if required fields are missing or invalid.
    """

    # Project life (hard fail if absent)
    project_life_years = _extract_project_life_years(raw, log=True)

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

    # Degradation is *always* interpreted as a percentage value.
    degradation_pct_raw = _as_float_or_none(
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
    if degradation_pct_raw is None:
        degradation = 0.0
    else:
        if degradation_pct_raw < 0:
            raise ValueError(
                f"degradation_pct: {degradation_pct_raw} invalid (must be >= 0, percent)"
            )
        degradation = degradation_pct_raw / 100.0  # e.g. 0.5 -> 0.005
        if degradation > 0.05:
            logger.warning(
                "Unusually high degradation_pct=%.3f%% (%.4f per year). "
                "Check if config units are correct.",
                degradation_pct_raw,
                degradation,
            )

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

    # Risk haircut: percent or decimal
    risk_haircut_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("risk_adjustment", "cfads_haircut_pct"),
            ("risk_adjustment", "risk_haircut_pct"),
            ("risk", "haircut_pct"),
            ("parameters", "risk_haircut_pct"),
            "risk_haircut_pct",
            "risk_haircut",
        )
    )
    risk_haircut_pct = _pct_to_decimal(risk_haircut_raw) or 0.0

    params = CashflowParams(
        project_life_years=project_life_years,
        capacity_mw=float(capacity_mw) if capacity_mw is not None else 0.0,
        capacity_factor=float(capacity_factor) if capacity_factor is not None else 0.0,
        degradation=float(degradation),
        grid_loss_pct=float(grid_loss_pct),
        tariff_lkr_per_kwh=(
            float(tariff_lkr_per_kwh) if tariff_lkr_per_kwh is not None else 0.0
        ),
        opex_usd_per_year=(
            float(opex_usd_per_year) if opex_usd_per_year is not None else 0.0
        ),
        success_fee_pct=float(success_fee_pct),
        env_surcharge_pct=float(env_surcharge_pct),
        social_levy_pct=float(social_levy_pct),
        corporate_tax_rate=(
            float(corporate_tax_rate) if corporate_tax_rate is not None else 0.0
        ),
        depreciation_years=int(depreciation_years),
        tax_holiday_years=int(tax_holiday_years),
        tax_holiday_start_year=int(tax_holiday_start_year),
        enhanced_capital_allowance_pct=float(enhanced_capital_allowance_pct),
        risk_haircut_pct=float(risk_haircut_pct),
    )

    # Mirror the previous validation behaviour to preserve error surfaces.
    missing_or_invalid: List[str] = []

    def _check_required(name: str, predicate: Any) -> None:
        value = getattr(params, name)
        if not predicate(value):
            missing_or_invalid.append(name)

    _check_required("project_life_years", lambda v: isinstance(v, int) and v > 0)
    _check_required("capacity_mw", lambda v: isinstance(v, (int, float)) and v > 0)
    _check_required(
        "capacity_factor",
        lambda v: isinstance(v, (int, float)) and 0.0 < float(v) <= 1.0,
    )
    _check_required(
        "tariff_lkr_per_kwh",
        lambda v: isinstance(v, (int, float)) and v >= 0,
    )
    _check_required(
        "opex_usd_per_year",
        lambda v: isinstance(v, (int, float)) and v >= 0,
    )
    _check_required(
        "corporate_tax_rate",
        lambda v: isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0,
    )

    if missing_or_invalid:
        raise ValueError(
            "Missing or invalid required fields for v14 cashflow: "
            + ", ".join(sorted(missing_or_invalid))
        )

    return params


def _extract_parameters(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize parameters required for v14 CFADS calculation.

    Returns a plain dict for backward compatibility. Prefer using the
    internal CashflowParams model when working within this module.
    """
    params = _build_cashflow_params(raw)
    return asdict(params)


def validate_parameters(config: Dict[str, Any], *, strict: bool = True) -> List[str]:
    """Validate cashflow parameters from configuration.

    This is a human-readable guard that complements schema_guard.

    🦌 REINDEER-3: Added strict parameter for test-friendly validation.

    Parameters
    ----------
    config : dict
        Configuration dictionary to validate
    strict : bool, default=True
        If True: Raise ValueError on missing/invalid required fields (production mode)
        If False: Log warnings and provide sensible defaults (test/development mode)

    Returns
    -------
    list[str]
        Empty list on success (backward compatible)

    Raises
    ------
    ValueError
        If validation fails in strict mode with detailed error message

    Key rules (decimals after normalization):
      - 0.0 <= corporate_tax_rate <= 1.0
      - project_life_years >= 1
      - capacity_mw > 0
      - 0 < capacity_factor <= 1.0
      - tariff_lkr_per_kwh >= 0
      - opex_usd_per_year >= 0

    Defaults (non-strict mode):
      - corporate_tax_rate: 0.24 (24%, typical LK rate)
      - capacity_mw: 100 MW (reasonable test value)
      - capacity_factor: 0.25 (25%, conservative)
      - tariff_lkr_per_kwh: 20 (reasonable LK tariff)
      - opex_usd_per_year: 1,000,000 ($1M/year)

    Example
    -------
    >>> # Production: strict validation
    >>> validate_parameters(prod_config, strict=True)

    >>> # Test: lenient validation with defaults
    >>> validate_parameters(test_config, strict=False)
    """

    errors: List[str] = []
    warnings: List[str] = []

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
        msg = "corporate_tax_rate: missing (required field)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 24%")
    else:
        tax_rate = _pct_to_decimal(tax_rate_raw)
        if tax_rate is None or not (0.0 <= tax_rate <= 1.0):
            msg = (
                f"corporate_tax_rate: {tax_rate} out of range "
                "(must be 0.0-1.0 or 0-100%)"
            )
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using default 24%")

    # Extract and validate project life (silent to avoid double-logging)
    try:
        project_life = _extract_project_life_years(config, log=False)
        if project_life < 1:
            msg = f"project_life_years: {project_life} invalid (must be >= 1)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using default 20 years")
    except ValueError as e:
        msg = f"project_life_years: {e}"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 20 years")

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
        msg = f"capacity_mw: {capacity_mw} invalid (must be > 0)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 100 MW")

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
        msg = "capacity_factor: missing (required field)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 25%")
    else:
        cf = _pct_to_decimal(cf_raw)
        if cf is None or not (0.0 < cf <= 1.0):
            msg = f"capacity_factor: {cf} out of range (must be 0.0-1.0 or 0-100%)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using default 25%")

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
        msg = f"tariff_lkr_per_kwh: {tariff} invalid (must be >= 0)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 20 LKR/kWh")

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
        msg = f"opex_usd_per_year: {opex} invalid (must be >= 0)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default $1M/year")

    # Optional field validations (if present)

    # Degradation is validated as a percentage (not decimal)
    degradation_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "degradation_pct"),
            "degradation_pct",
        )
    )
    if degradation_raw is not None:
        if degradation_raw < 0:
            msg = (
                f"degradation_pct: {degradation_raw} invalid (must be >= 0, percent)"
            )
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using 0%")
        elif degradation_raw > 30:
            msg = (
                f"degradation_pct: {degradation_raw}% implausibly high (>30%/year). "
                "Check units."
            )
            # This is always a warning, even in strict mode
            warnings.append(msg)

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
            msg = f"grid_loss_pct: {loss} out of range (must be 0.0-1.0)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using 0%")

    # Risk haircut – mirror _build_cashflow_params resolution so validators
    # and engine see the same surface.
    risk_haircut_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("risk_adjustment", "cfads_haircut_pct"),
            ("risk_adjustment", "risk_haircut_pct"),
            ("risk", "haircut_pct"),
            "risk_haircut_pct",
        )
    )
    if risk_haircut_raw is not None:
        risk = _pct_to_decimal(risk_haircut_raw)
        if risk and not (0.0 <= risk < 1.0):
            msg = f"risk_haircut_pct: {risk} out of range (must be 0.0-1.0)"
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - using 0%")

    depreciation_years = as_int(
        _resolve_first(
            config,
            ("tax", "depreciation_years"),
            "depreciation_years",
        )
    )
    if depreciation_years is not None and depreciation_years < 1:
        msg = f"depreciation_years: {depreciation_years} invalid (must be >= 1)"
        if strict:
            errors.append(msg)
        else:
            warnings.append(f"{msg} - using default 20 years")

    # FX must be structured if present
    fx_cfg = config.get("fx")
    if isinstance(fx_cfg, dict):
        start = fx_cfg.get("start_lkr_per_usd")
        curve = fx_cfg.get("curve") or fx_cfg.get("curve_lkr_per_usd")
        if start is None and not isinstance(curve, (list, tuple)):
            msg = (
                "fx: invalid configuration; expected 'start_lkr_per_usd' "
                "or an explicit 'curve' list"
            )
            if strict:
                errors.append(msg)
            else:
                warnings.append(f"{msg} - FX integration may fail")

    # Log warnings in non-strict mode
    if not strict and warnings:
        logger.warning(
            "⚠️  Configuration validation warnings (non-strict mode):\n%s",
            "\n".join(f"  • {w}" for w in warnings),
        )

    # Raise comprehensive error if any validation failed (strict mode only)
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(
            f"  • {err}" for err in errors
        )
        raise ValueError(error_msg)

    # Return empty list on success (backward compatible)
    return []


__all__ = [
    "_extract_project_life_years",
    "_build_cashflow_params",
    "_extract_parameters",
    "validate_parameters",
]
