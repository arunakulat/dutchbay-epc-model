from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from collections.abc import Sequence as Seq
from dataclasses import asdict
from typing import Any, Dict, List, Tuple

from .cashflow_v14_contracts import CashflowParams
from .cashflow_v14_utils import (
    CAPACITY_FACTOR_PATHS,
    CAPACITY_MW_PATHS,
    _as_float_or_none,
    _pct_to_decimal,
    _resolve_first,
    as_int,
    as_int_or_none,
    get_nested,
)
from .import_levies import resolve_indirect_taxes

logger = logging.getLogger(__name__)


def _resolve_self_curtailment_composed(
    raw: Dict[str, Any], config_curtailment_pct: float
) -> float:
    """Compose the self-curtailment fraction into curtailment_pct — DEFAULT-OFF (#885, D6b).

    Returns ``config_curtailment_pct`` UNCHANGED (byte-identical) unless the explicit
    finance-wiring opt-in ``grid.qsts.finance_wiring.enabled: true`` is set. The opt-in
    check runs FIRST and short-circuits before any grid/QSTS import, so the committed canon
    never touches the ``[grid]`` extra and stays byte-identical.

    When the opt-in IS set, it runs the gated D6a QSTS study
    (:func:`analytics.grid.curtailment_qsts.run_qsts_curtailment` — itself default-off /
    real-feeder-guarded) and composes ONLY ``self_curtailed_pct`` (never deemed-paid) into
    the loss key via :func:`finance.self_curtailment_v14.compose_curtailment`.
    """
    # Lazy imports: keep the committed cashflow free of the analytics.grid / self_curtailment
    # dependency surface (and the [grid] OpenDSS extra) on the default-off path.
    from .self_curtailment_v14 import (
        compose_curtailment,
        resolve_self_curtailment_decimal,
        self_curtailment_finance_wiring_enabled,
    )

    if not self_curtailment_finance_wiring_enabled(raw):
        return config_curtailment_pct

    from analytics.grid.curtailment_qsts import run_qsts_curtailment

    result = run_qsts_curtailment(raw)
    self_curtail = resolve_self_curtailment_decimal(raw, result)
    if self_curtail <= 0.0:
        return config_curtailment_pct
    composed = compose_curtailment(config_curtailment_pct, self_curtail)
    logger.info(
        "D6b self-curtailment wired into curtailment_pct: config=%.6f self=%.6f "
        "composed=%.6f (deemed-paid excluded — KPI-neutral per CEB SPPA).",
        config_curtailment_pct,
        self_curtail,
        composed,
    )
    return composed


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

    financing_life = as_int_or_none(
        get_nested(raw, ["Financing_Terms", "tenor_years"], None)
    )
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

    # Path lists centralised in cashflow_v14_utils so the AEP reconciliation guard
    # reconciles EXACTLY the capacity / capacity_factor this engine bills off.
    capacity_mw = _as_float_or_none(_resolve_first(raw, *CAPACITY_MW_PATHS))

    capacity_factor_raw = _as_float_or_none(_resolve_first(raw, *CAPACITY_FACTOR_PATHS))
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
        # A1/#92/#109: a missing degradation input means NO turbine aging — the most
        # optimistic possible assumption. Keep the 0.0 default (byte-identical; every banked
        # scenario sets degradation explicitly) but WARN so an omission cannot silently
        # flatter output. The documented house default is 0.6/yr
        # (config/defaults.yaml degradation.annual_rate_pct).
        degradation = 0.0
        logger.warning(
            "degradation input missing — assuming 0.0/yr (no aging), the most optimistic "
            "case. Set project.degradation_pct explicitly; the documented house default is "
            "0.6/yr (config/defaults.yaml degradation.annual_rate_pct)."
        )
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

    # Incremental financed grid-curtailment haircut (default 0.0 → byte-identical; the
    # physical/embedded curtailment is already in the bankable net AEP / capacity_factor).
    # First-class risk lever: stressed by the tornado + Monte-Carlo (see sensitivity_runner).
    curtailment_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "curtailment_pct"),
            ("parameters", "curtailment_pct"),
            "curtailment_pct",
        )
    )
    curtailment_pct = _pct_to_decimal(curtailment_raw) or 0.0

    # D6b (#885) — the SOLE KPI-mover of grid-epic #870, DEFAULT-OFF. ONLY when the explicit
    # finance-wiring opt-in (grid.qsts.finance_wiring.enabled: true) is set AND a real QSTS
    # study ran do we compose the plant's OWN self-curtailment fraction into curtailment_pct.
    # The deemed-paid / grid-instructed fraction is NEVER read (CEB SPPA: paid as deemed
    # energy → KPI-neutral). Absent the opt-in, resolve_self_curtailment_decimal short-
    # circuits to 0.0 BEFORE any QSTS is consulted, so no [grid] dep is touched and the
    # committed curtailment_pct (hence the whole cashflow) is byte-identical.
    curtailment_pct = _resolve_self_curtailment_composed(raw, curtailment_pct)

    # Incremental grid-UNAVAILABILITY / outage haircut (default 0.0 → byte-identical; the
    # embedded availability is already in the bankable net AEP / capacity_factor). The
    # config-first grid-outage assumptions input (#744): documented ADDITIONAL grid
    # downtime, applied after curtailment. Distinct from curtailment_pct (economic dispatch
    # curtailment). Do not also declare resource.losses.grid_availability_pct for the same
    # downtime (that reduces the AEP summary) or the haircut double-counts.
    grid_outage_raw = _as_float_or_none(
        _resolve_first(
            raw,
            ("project", "grid_outage_pct"),
            ("parameters", "grid_outage_pct"),
            "grid_outage_pct",
        )
    )
    grid_outage_pct = _pct_to_decimal(grid_outage_raw) or 0.0

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

    # Annual O&M escalation (USD-real inflation), e.g. opex.escalation_pct: 2.5 -> 0.025.
    # Optional; defaults to 0.0 (flat USD) so existing scenarios are unchanged. The LKR
    # opex then escalates further via the per-year FX curve (inflation AND FX effects).
    opex_escalation_pct = (
        _pct_to_decimal(
            _as_float_or_none(
                _resolve_first(
                    raw,
                    ("opex", "escalation_pct"),
                    ("opex", "annual_escalation_pct"),
                    ("opex", "inflation_pct"),
                    "opex_escalation_pct",
                )
            )
        )
        or 0.0
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

    # NOTE: the corporate tax RATE and the tax-detail inputs (enhanced_capital_allowance_multiple,
    # depreciation_years, tax_holiday_years, tax_holiday_start_year) are resolved + validated
    # by finance.cashflow_v14_tax.TaxConfig — the LIVE tax/depreciation/holiday path reads them
    # off that object (tax_config.tax_rate, .depreciation_years, .tax_holiday_years, .holiday
    # window). The parallel resolution that once lived here fed CashflowParams fields that NO
    # computation ever read — dead second sources of truth that could silently drift from the
    # live TaxConfig — so they were removed (CCCDIR). The config KEY is still required + range-
    # validated for the whole config in validate_parameters() below.

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

    # #738: unrecoverable input VAT on O&M — resolved via the single indirect-tax
    # authority (finance.import_levies; strict decimals, fail-loud). The effective
    # rate is 0.0 when the taxes_indirect block is absent or
    # relief.vat_opex_relieved is true -> byte-identical opex line.
    indirect_taxes = resolve_indirect_taxes(raw)
    opex_vat_pct = indirect_taxes.opex_vat_rate if indirect_taxes is not None else 0.0

    params = CashflowParams(
        project_life_years=project_life_years,
        capacity_mw=float(capacity_mw) if capacity_mw is not None else 0.0,
        capacity_factor=float(capacity_factor) if capacity_factor is not None else 0.0,
        degradation=float(degradation),
        grid_loss_pct=float(grid_loss_pct),
        curtailment_pct=float(curtailment_pct),
        grid_outage_pct=float(grid_outage_pct),
        tariff_lkr_per_kwh=(
            float(tariff_lkr_per_kwh) if tariff_lkr_per_kwh is not None else 0.0
        ),
        opex_usd_per_year=(
            float(opex_usd_per_year) if opex_usd_per_year is not None else 0.0
        ),
        opex_escalation_pct=float(opex_escalation_pct),
        success_fee_pct=float(success_fee_pct),
        env_surcharge_pct=float(env_surcharge_pct),
        social_levy_pct=float(social_levy_pct),
        risk_haircut_pct=float(risk_haircut_pct),
        opex_vat_pct=float(opex_vat_pct),
    )

    missing_or_invalid: List[str] = []

    def _check_required(name: str, predicate: Any) -> None:
        value = getattr(params, name)
        if not predicate(value):
            missing_or_invalid.append(name)

    _check_required("project_life_years", lambda v: isinstance(v, int) and v > 0)
    _check_required("capacity_mw", lambda v: isinstance(v, (int, float)) and v > 0)
    # BESS-5 (#486): 0.0 is valid for a storage-only scenario (no generation CF; revenue
    # is the BESS capacity charge). Negatives and >1 remain invalid.
    _check_required(
        "capacity_factor",
        lambda v: isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0,
    )
    _check_required(
        "tariff_lkr_per_kwh",
        lambda v: isinstance(v, (int, float)) and v >= 0,
    )
    _check_required(
        "opex_usd_per_year",
        lambda v: isinstance(v, (int, float)) and v >= 0,
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

    def _pct_or_raw(raw: float | None) -> float | None:
        """Normalize a rate for validation, degrading to the raw value on failure.

        ``pct_to_decimal`` now fails loud on an impossible (>100) rate (audit D7,
        #573). In *validation* we want the field-named "out of range" error rather
        than a bare ``ValueError``, so an out-of-range value falls back to the raw
        (which is >100, hence outside every valid band) and trips the caller's own
        range check with the offending field named.
        """
        try:
            return _pct_to_decimal(raw)
        except ValueError:
            return raw

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
        tax_rate = _pct_or_raw(tax_rate_raw)
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
        cf = _pct_or_raw(cf_raw)
        # BESS-5 (#486): admit 0.0 — a storage-only scenario has no generation capacity
        # factor (its revenue is the BESS capacity charge), so a literal 0 is valid rather
        # than the former 0.0001 placeholder. Negatives and >1 remain config errors.
        if cf is None or not (0.0 <= cf <= 1.0):
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
        loss = _pct_or_raw(grid_loss_raw)
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
        risk = _pct_or_raw(risk_haircut_raw)
        if risk and not (0.0 <= risk < 1.0):
            errors.append(f"risk_haircut_pct: {risk} out of range (must be 0.0-1.0)")

    # as_int fails loud on a present-but-malformed value (#585); convert that into a
    # field-named validation error so this collector keeps its report-all contract
    # (mirrors the project_life_years try/except above). Previously a malformed
    # depreciation_years silently coerced to None and PASSED validation.
    try:
        depreciation_years = as_int(
            _resolve_first(config, ("tax", "depreciation_years"), "depreciation_years")
        )
    except ValueError as e:
        errors.append(f"depreciation_years: {e}")
        depreciation_years = None
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

        # FX-forward hedge levers (both optional; default 0.0 -> pure-spot, byte-identical).
        # fx.hedge_ratio: fraction 0.0-1.0 of CFADS converted at the CIP forward; fail-loud
        # rather than silently clamp an out-of-band ratio (CESSPIT / FIN-2 unit naming).
        # Bools are rejected (a YAML `hedge_ratio: true` would float() to a silent FULL
        # hedge) and non-finite values are rejected (`.nan` would otherwise pass a bare
        # `< 0.0` check and propagate NaN into the load-bearing cfads_usd stream) —
        # mirroring analytics.schema_guard._is_finite_number (Fable review of cfb3908).
        hedge_ratio_raw = fx_cfg.get("hedge_ratio")
        if hedge_ratio_raw is not None:
            hedge_ratio = (
                None
                if isinstance(hedge_ratio_raw, bool)
                else _as_float_or_none(hedge_ratio_raw)
            )
            if (
                hedge_ratio is None
                or not math.isfinite(hedge_ratio)
                or not (0.0 <= hedge_ratio <= 1.0)
            ):
                errors.append(
                    f"fx.hedge_ratio: {hedge_ratio_raw!r} out of range "
                    "(must be a finite decimal 0.0-1.0)"
                )
        # fx.spread_bps: hedging cost in basis points, finite and >= 0.
        spread_bps_raw = fx_cfg.get("spread_bps")
        if spread_bps_raw is not None:
            spread_bps = (
                None
                if isinstance(spread_bps_raw, bool)
                else _as_float_or_none(spread_bps_raw)
            )
            if spread_bps is None or not math.isfinite(spread_bps) or spread_bps < 0.0:
                errors.append(
                    f"fx.spread_bps: {spread_bps_raw!r} invalid "
                    "(must be finite and >= 0 basis points)"
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
