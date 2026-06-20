from __future__ import annotations

import logging
from collections.abc import Mapping
from collections.abc import Sequence as Seq
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from .cashflow_v14_contracts import CashflowParams
from .cashflow_v14_utils import (
    _as_float_or_none,
    _pct_to_decimal,
    _resolve_first,
    as_int,
    as_int_or_none,
    get_nested,
)

logger = logging.getLogger(__name__)


def _resolve_project_life_components(
    raw: Dict[str, Any],
    *,
    log: bool,
) -> int | None:
    """Resolve project life from construction + operating years if available."""
    construction_years = as_int_or_none(
        _resolve_first(
            raw,
            ("project", "construction_years"),
            ("parameters", "construction_years"),
            "construction_years",
        )
    )
    operating_years = as_int_or_none(
        _resolve_first(
            raw,
            ("project", "operating_years"),
            ("project", "operations_years"),
            ("parameters", "operating_years"),
            ("parameters", "operations_years"),
            "operating_years",
            "operations_years",
        )
    )
    if operating_years is None or operating_years <= 0:
        return None
    construction = max(0, construction_years or 0)
    project_life = construction + operating_years
    if 5 <= project_life <= 60:
        if log:
            logger.info(
                "Project life resolved from construction_years + operating_years = %d years",
                project_life,
            )
        return project_life
    return None


def _resolve_fx_start(raw: Dict[str, Any]) -> float:
    """Resolve a start FX rate for USD tariff translation.

    Prefers the scenario's explicit ``fx.start_lkr_per_usd``; when no fx block is
    present (lightweight / hand-authored configs) falls back to the single
    config-sourced reference rate (``config/defaults.yaml``), never a Python
    literal (CESSPIT / ARCH-01).
    """
    from analytics.fx.fx_fetch import default_fx_lkr_per_usd

    fx_start = _as_float_or_none(
        _resolve_first(
            raw,
            ("fx", "start_lkr_per_usd"),
            ("fx", "start"),
            ("fx", "base"),
            ("fx", "base_rate"),
            "start_lkr_per_usd",
        )
    )
    if fx_start is not None and fx_start > 0:
        return fx_start
    return default_fx_lkr_per_usd()


def _resolve_tariff_lkr_per_kwh(raw: Dict[str, Any]) -> float | None:
    """Resolve tariff in canonical LKR/kWh units.

    Canonical scenarios provide LKR/kWh directly. Lightweight lender-stack
    tests and some hand-authored scenario dictionaries provide USD/MWh; convert
    those using the same legacy FX fallback as cashflow_v14_fx when no explicit
    FX block exists.
    """
    tariff_lkr = _as_float_or_none(
        _resolve_first(
            raw,
            ("tariff", "lkr_per_kwh"),
            ("tariff", "lkr_kwh"),
            ("tariff", "tariff_lkr_per_kwh"),
            ("revenue", "tariff_lkr_per_kwh"),
            ("revenue", "tariff_lkr_kwh"),
            "tariff_lkr_per_kwh",
            "tariff_lkr",
            "tariff",
        )
    )
    if tariff_lkr is not None:
        return tariff_lkr

    tariff_usd_mwh = _as_float_or_none(
        _resolve_first(
            raw,
            ("tariff", "usd_per_mwh"),
            ("tariff", "tariff_usd_per_mwh"),
            ("revenue", "tariff_usd_per_mwh"),
            "tariff_usd_per_mwh",
        )
    )
    if tariff_usd_mwh is not None:
        return tariff_usd_mwh * _resolve_fx_start(raw) / 1000.0

    tariff_usd_kwh = _as_float_or_none(
        _resolve_first(
            raw,
            ("tariff", "usd_per_kwh"),
            ("tariff", "tariff_usd_per_kwh"),
            ("revenue", "tariff_usd_per_kwh"),
            "tariff_usd_per_kwh",
        )
    )
    if tariff_usd_kwh is not None:
        return tariff_usd_kwh * _resolve_fx_start(raw)

    return None


def _extract_project_life_years(
    raw: Dict[str, Any],
    *,
    log: bool = True,
) -> int:
    """Robust extraction of project life in years for v14."""
    explicit_candidates: List[Tuple[Tuple[str, ...], str]] = [
        (("project", "life_years"), "project.life_years"),
        (("project", "project_life_years"), "project.project_life_years"),
        (("parameters", "project_life_years"), "parameters.project_life_years"),
        (("parameters", "life_years"), "parameters.life_years"),
    ]

    for path, label in explicit_candidates:
        v = as_int_or_none(get_nested(raw, list(path), None))
        if v is not None and 5 <= v <= 60:
            if log:
                logger.info("Project life resolved from %s = %d years", label, v)
            return v

    component_life = _resolve_project_life_components(raw, log=log)
    if component_life is not None:
        return component_life

    financing_life = as_int_or_none(get_nested(raw, ["Financing_Terms", "tenor_years"], None))
    if financing_life is not None and 5 <= financing_life <= 60:
        if log:
            logger.info(
                "Project life resolved from Financing_Terms.tenor_years = %d years",
                financing_life,
            )
        return financing_life

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
            if iv is None or not (5 <= iv <= 60):
                return
            path_str = "/".join(path).lower()
            if any(
                token in path_str
                for token in ("life", "lifetime", "horizon", "operating", "operation")
            ):
                hits.append(("/".join(path), iv))

    walk(raw, ())

    if hits:
        chosen_path, chosen_val = hits[0]
        if log:
            logger.warning(
                "Project life not found in explicit fields; using heuristic match %r = %d years",
                chosen_path,
                chosen_val,
            )
        return chosen_val

    raise ValueError(
        "Missing or invalid project life: expected explicit life fields, "
        "Project.construction_years + Project.operating_years, or a plausible "
        "project-life integer."
    )


def _build_cashflow_params(raw: Dict[str, Any]) -> CashflowParams:
    """Extract and normalize parameters required for v14 CFADS calculation."""
    project_life_years = _extract_project_life_years(raw, log=True)

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
            ("production", "capacity_factor_net"),
            ("production", "capacity_factor"),
            ("parameters", "capacity_factor_pct"),
            ("parameters", "capacity_factor"),
            "capacity_factor_pct",
            "capacity_factor",
        )
    )
    capacity_factor = _pct_to_decimal(capacity_factor_raw)

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
        degradation = degradation_pct_raw / 100.0
        if degradation > 0.05:
            logger.warning(
                "Unusually high degradation_pct=%.3f%% (%.4f per year). Check units.",
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

    tariff_lkr_per_kwh = _resolve_tariff_lkr_per_kwh(raw)

    opex_usd_per_year = _as_float_or_none(
        _resolve_first(
            raw,
            ("opex", "usd_per_year"),
            ("opex", "usd_annual"),
            ("opex", "annual_opex_usd"),
            ("costs", "opex_usd_per_year"),
            ("costs", "opex_annual_usd"),
            "opex_usd_per_year",
        )
    )

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

    corporate_tax_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("tax", "corporate_tax_rate_pct"),
            ("tax", "corporate_tax_rate"),
            ("tax", "corporate_rate"),
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
    enhanced_capital_allowance_pct = (
        enhanced_capital_allowance_raw / 100.0
        if enhanced_capital_allowance_raw and enhanced_capital_allowance_raw > 1
        else enhanced_capital_allowance_raw or 1.0
    )

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
    """Return normalized cashflow parameters as a plain dict."""
    params = _build_cashflow_params(raw)
    return asdict(params)


def validate_parameters(config: Dict[str, Any]) -> List[str]:
    """Validate cashflow parameters from configuration."""
    errors: List[str] = []

    tax_rate_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("tax", "corporate_tax_rate_pct"),
            ("tax", "corporate_tax_rate"),
            ("tax", "corporate_rate"),
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
                f"{tax_rate} out of range (must be 0.0-1.0 or 0-100%)"
            )

    try:
        project_life = _extract_project_life_years(config, log=False)
        if project_life < 1:
            errors.append(f"project_life_years: {project_life} invalid (must be >= 1)")
    except ValueError as e:
        errors.append(f"project_life_years: {e}")

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

    cf_raw = _as_float_or_none(
        _resolve_first(
            config,
            ("project", "capacity_factor_pct"),
            ("project", "capacity_factor"),
            ("production", "capacity_factor_net"),
            ("production", "capacity_factor"),
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

    tariff = _resolve_tariff_lkr_per_kwh(config)
    if tariff is None or tariff < 0:
        errors.append(f"tariff_lkr_per_kwh: {tariff} invalid (must be >= 0)")

    opex = _as_float_or_none(
        _resolve_first(
            config,
            ("opex", "usd_per_year"),
            ("opex", "annual_opex_usd"),
            ("costs", "opex_usd_per_year"),
            ("costs", "opex_annual_usd"),
            "opex_usd_per_year",
        )
    )
    if opex is None or opex < 0:
        errors.append(f"opex_usd_per_year: {opex} invalid (must be >= 0)")

    degradation_raw = _as_float_or_none(
        _resolve_first(config, ("project", "degradation_pct"), "degradation_pct")
    )
    if degradation_raw is not None:
        if degradation_raw < 0:
            errors.append(
                f"degradation_pct: {degradation_raw} invalid (must be >= 0, percent)"
            )
        elif degradation_raw > 30:
            errors.append(
                f"degradation_pct: {degradation_raw}% implausibly high (>30%/year). Check units."
            )

    grid_loss_raw = _as_float_or_none(
        _resolve_first(config, ("project", "grid_loss_pct"), "grid_loss_pct")
    )
    if grid_loss_raw is not None:
        loss = _pct_to_decimal(grid_loss_raw)
        if loss and not (0.0 <= loss < 1.0):
            errors.append(f"grid_loss_pct: {loss} out of range (must be 0.0-1.0)")

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
            errors.append(f"risk_haircut_pct: {risk} out of range (must be 0.0-1.0)")

    depreciation_years = as_int(
        _resolve_first(config, ("tax", "depreciation_years"), "depreciation_years")
    )
    if depreciation_years is not None and depreciation_years < 1:
        errors.append(
            f"depreciation_years: {depreciation_years} invalid (must be >= 1)"
        )

    fx_cfg = config.get("fx") or config.get("FX")
    if isinstance(fx_cfg, dict):
        start = fx_cfg.get("start_lkr_per_usd")
        curve = fx_cfg.get("curve") or fx_cfg.get("curve_lkr_per_usd")
        if start is None and not isinstance(curve, (list, tuple)):
            errors.append(
                "fx: invalid configuration; expected 'start_lkr_per_usd' or an explicit 'curve' list"
            )

    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(
            f"  • {err}" for err in errors
        )
        raise ValueError(error_msg)

    return []


__all__ = [
    "_extract_project_life_years",
    "_build_cashflow_params",
    "_extract_parameters",
    "validate_parameters",
]
