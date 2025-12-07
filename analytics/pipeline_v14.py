from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from analytics.contracts_v14 import (
    DebtCovenantSnapshot,
    ScenarioResult,
    TrancheDebtProfile,
)
from analytics.contracts_v14 import WaccComponents as ContractWaccComponents
from analytics.contracts_v14 import (
    WaccResult,
    build_cashflow_result_from_annual_rows,
)
from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt
from finance.utils import get_nested
from finance.wacc_v14 import compute_wacc_from_config

logger = logging.getLogger(__name__)


# =============================================================================
# Helpers
# =============================================================================


def _build_tranche_debt_profile(
    config: dict[str, Any],
    debt_result: dict[str, Any],
) -> TrancheDebtProfile:
    """
    Adapter: build a TrancheDebtProfile from the v14 debt_result (plan_debt surface).

    This is a lender-facing summary: totals, IDC, tenor, IO years, and target DSCR.
    """
    principal_by = (debt_result.get("principal_by_tranche") or {}) or {}

    lkr = debt_result.get("lkr") or {}
    usd = debt_result.get("usd") or {}
    dfi = debt_result.get("dfi") or {}

    construction_years = int(debt_result.get("construction_years") or 0)
    tenor_years = int(debt_result.get("tenor_years") or 0)
    timeline_periods = int(debt_result.get("timeline_periods") or 0)

    total_debt = float(sum(principal_by.values()) or 0.0)
    total_idc = float(debt_result.get("total_idc") or 0.0)

    # Optional cost-of-debt metadata (if present in config)
    rates = get_nested(config, ["Financing_Terms", "rates"], {}) or {}
    lkr_rate = rates.get("lkr_nominal") or rates.get("lkr_min")
    usd_rate = rates.get("usd_nominal") or rates.get("usd_commercial_min")
    dfi_rate = rates.get("dfi_nominal") or rates.get("dfi_min")

    io_years = int(
        (get_nested(config, ["Financing_Terms", "interest_only_years"]) or 0)
    )

    amortization_style = (
        get_nested(config, ["Financing_Terms", "amortization_style"]) or "sculpted"
    )
    amortization_style = str(amortization_style).lower()

    dscr_target_raw = get_nested(config, ["Financing_Terms", "target_dscr"])
    try:
        dscr_target = float(dscr_target_raw) if dscr_target_raw is not None else None
    except (TypeError, ValueError):
        dscr_target = None

    return TrancheDebtProfile(
        construction_years=construction_years,
        tenor_years=tenor_years,
        timeline_periods=timeline_periods,
        total_debt=total_debt,
        total_idc=total_idc,
        lkr_principal=float(lkr.get("principal") or 0.0),
        usd_principal=float(usd.get("principal") or 0.0),
        dfi_principal=float(dfi.get("principal") or 0.0),
        lkr_idc=float(lkr.get("idc") or 0.0),
        usd_idc=float(usd.get("idc") or 0.0),
        dfi_idc=float(dfi.get("idc") or 0.0),
        lkr_rate=float(lkr_rate) if lkr_rate is not None else None,
        usd_rate=float(usd_rate) if usd_rate is not None else None,
        dfi_rate=float(dfi_rate) if dfi_rate is not None else None,
        interest_only_years=io_years,
        amortization_style=amortization_style,
        dscr_target=dscr_target,
    )


def _build_debt_covenant_snapshot(
    config: dict[str, Any],
    debt_result: dict[str, Any],
) -> DebtCovenantSnapshot:
    """
    Build a DebtCovenantSnapshot from the v14 debt_result dict.

    Encodes DSCR profile vs lender threshold and balloon flag for ring-fence views.
    """
    dscr_series = list(debt_result.get("dscr_series") or [])
    dscr_min = float(debt_result.get("min_dscr") or 0.0)

    # Threshold: if explicit target_dscr is present, use it; else default to 1.30
    dscr_threshold_raw = get_nested(config, ["Financing_Terms", "target_dscr"])
    try:
        dscr_threshold = (
            float(dscr_threshold_raw) if dscr_threshold_raw is not None else 1.30
        )
    except (TypeError, ValueError):
        dscr_threshold = 1.30

    years_below = 0
    first_breach_year: int | None = None
    last_breach_year: int | None = None

    for idx, value in enumerate(dscr_series, start=1):
        if value == float("inf"):
            # Construction / grace years – ignore for covenant counting.
            continue
        if value < dscr_threshold:
            years_below += 1
            if first_breach_year is None:
                first_breach_year = idx
            last_breach_year = idx

    balloon_remaining = float(debt_result.get("balloon_remaining") or 0.0)
    balloon_flag = balloon_remaining > 1e-6

    audit_status = str(debt_result.get("audit_status") or "REVIEW")

    notes_parts: list[str] = []
    notes_parts.append(f"min DSCR={dscr_min:.2f} vs threshold={dscr_threshold:.2f}")
    if years_below > 0:
        notes_parts.append(f"{years_below} periods below threshold")
    if balloon_flag:
        notes_parts.append("balloon remaining at end of tenor")

    notes = "; ".join(notes_parts)

    return DebtCovenantSnapshot(
        dscr_min=dscr_min,
        dscr_threshold=dscr_threshold,
        years_below_threshold=years_below,
        first_breach_year=first_breach_year,
        last_breach_year=last_breach_year,
        balloon_remaining=balloon_remaining,
        balloon_flag=balloon_flag,
        audit_status=audit_status,
        notes=notes,
    )


def _build_wacc_contract(
    wacc_dict: Mapping[str, Any] | None,
) -> WaccResult | None:
    """
    Adapter: map the finance.wacc_v14 dict surface into the contracts_v14 WaccResult.

    If the dict is missing core fields, we fail soft and return None.
    """
    if not wacc_dict:
        return None

    try:
        base = ContractWaccComponents(
            mode=str(wacc_dict.get("mode", "capm")),
            wacc_nominal=float(wacc_dict["wacc_nominal"]),
            wacc_real=wacc_dict.get("wacc_real"),
            wacc_prudential=float(
                wacc_dict.get("wacc_prudential", wacc_dict["wacc_nominal"])
            ),
            risk_free_rate=float(wacc_dict.get("risk_free_rate", 0.0)),
            market_risk_premium=float(wacc_dict.get("market_risk_premium", 0.0)),
            asset_beta=float(wacc_dict.get("asset_beta", 0.0)),
            target_debt_to_equity=float(wacc_dict.get("target_debt_to_equity", 0.0)),
            target_debt_to_value=float(wacc_dict.get("target_debt_to_value", 0.0)),
            target_equity_to_value=float(wacc_dict.get("target_equity_to_value", 1.0)),
            cost_of_debt_pretax=float(wacc_dict.get("cost_of_debt_pretax", 0.0)),
            cost_of_debt_aftertax=float(wacc_dict.get("cost_of_debt_aftertax", 0.0)),
            equity_beta_levered=float(wacc_dict.get("equity_beta_levered", 0.0)),
            cost_of_equity=float(wacc_dict.get("cost_of_equity", 0.0)),
            tax_rate=float(wacc_dict.get("tax_rate", 0.0)),
            inflation_rate=wacc_dict.get("inflation_rate"),
            prudential_spread_bps=int(wacc_dict.get("prudential_spread_bps", 0)),
        )
    except KeyError as exc:  # pragma: no cover - defensive
        logger.warning(
            "WACC dict missing core fields (%s); skipping WaccResult build.", exc
        )
        return None

    return WaccResult(
        base=base,
        prudential_rate=base.wacc_prudential,
        prudential_npv=None,
        meta={},
    )


# =============================================================================
# Core pipeline facade
# =============================================================================


def run_v14_pipeline(
    config: str | Path | Mapping[str, Any],
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the v14 engine for a single scenario.

    Parameters
    ----------
    config
        Either:
        - Path to YAML/JSON scenario file (str or Path), or
        - A pre-loaded config mapping (dict-like).
    validation_mode : {"strict", "off"}, default "strict"
        - "strict": run schema guard before evaluation
        - "off": skip schema guard
    validation_modules : list[str] or None
        Modules to validate. Defaults to ["cashflow", "debt"].

    Returns
    -------
    dict[str, Any]
        ScenarioResult-like dict with keys (superset of legacy surface):
        - validation_mode
        - config_path
        - config
        - annual_rows
        - debt_result
        - kpis
        - wacc
        - scenario_result
        - debt_profile
        - debt_covenants
    """
    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: {validation_mode!r}"
        )

    # ------------------------------------------------------------------
    # 1. Resolve config + label
    # ------------------------------------------------------------------
    if isinstance(config, (str, Path)):
        config_path_label = str(config)
        cfg = load_scenario_config(str(config))
    elif isinstance(config, Mapping):
        config_path_label = "<inline_config>"
        # Shallow copy to decouple from callers
        cfg = dict(config)
    else:
        raise TypeError(
            "config must be a path (str/Path) or a mapping, "
            f"got {type(config).__name__}"
        )

    # ------------------------------------------------------------------
    # 2. Pre-flight validation
    # ------------------------------------------------------------------
    if mode == "strict":
        modules = validation_modules or ["cashflow", "debt"]
        validate_config_for_v14(
            raw_config=cfg,
            config_path=config_path_label,
            modules=modules,
        )
        logger.info("Schema validation passed for modules: %s", ", ".join(modules))
    else:
        modules = validation_modules or []

    # ------------------------------------------------------------------
    # 3. Canonical v14 finance engine
    # ------------------------------------------------------------------

    # 3a. Cashflow – build annual rows from the v14 cashflow engine.
    annual_rows = build_annual_rows(cfg)
    logger.debug("Built %d annual rows", len(annual_rows))

    # 3b. Debt – covenant-friendly debt surface (plan_debt is canonical v14).
    debt_result = plan_debt(annual_rows=annual_rows, config=cfg)
    logger.debug("Debt result contains %d keys", len(debt_result))

    # 3c. Structured cashflow contract (for analytics / exports / lenders).
    cashflow_contract = build_cashflow_result_from_annual_rows(
        config=cfg,
        annual_rows=annual_rows,
    )

    # 3d. WACC (kept parallel to KPIs for now; KPIs still use legacy 10% discount).
    wacc_dict = compute_wacc_from_config(cfg)
    logger.debug("WACC dict keys: %s", list(wacc_dict.keys()) if wacc_dict else "none")

    # Legacy discount rate for KPIs – wiring WACC into discount_rate is a
    # deliberate future step (tests currently assume 10%).
    discount_rate_for_kpis = 0.10

    kpis = calculate_scenario_kpis(
        config=cfg,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=discount_rate_for_kpis,
    )
    logger.debug("Calculated %d KPIs", len(kpis))

    # Equity overlay
    #
    # NOTE: v14 equity engine is designed to operate on *equity cashflows*
    # (negative = contributions, positive = distributions). The canonical
    # equity series is not yet exposed by the cashflow/debt pipeline, so we
    # do not attempt to fabricate it here.

    # WACC contracts layer
    wacc_contract = _build_wacc_contract(wacc_dict)

    # Debt ring-fence surfaces
    debt_profile = _build_tranche_debt_profile(cfg, debt_result)
    debt_covenants = _build_debt_covenant_snapshot(cfg, debt_result)

    # ------------------------------------------------------------------
    # 4. ScenarioResult assembly (for dashboards / lender decks)
    # ------------------------------------------------------------------
    project_npv = float(kpis.get("project_npv", 0.0))
    project_irr = float(kpis.get("project_irr", 0.0))
    dscr_series = list(debt_result.get("dscr_series") or [])
    min_dscr = float(debt_result.get("min_dscr") or 0.0)
    max_debt_usd = float(kpis.get("max_debt_usd", 0.0))

    scenario_name = str(cfg.get("scenario_name", Path(config_path_label).stem))

    scenario_result = ScenarioResult(
        scenario_name=scenario_name,
        config_path=config_path_label,
        project_npv=project_npv,
        project_irr=project_irr,
        dscr_series=dscr_series,
        min_dscr=min_dscr,
        max_debt_usd=max_debt_usd,
        wacc=wacc_contract,
        discount_rate_used=discount_rate_for_kpis,
        wacc_label=wacc_dict.get("mode") if wacc_dict else None,
        wacc_is_real=(
            bool(wacc_dict.get("wacc_real") is not None) if wacc_dict else None
        ),
        validation_mode=mode,
        config=cfg,
        annual_rows=annual_rows,
        debt_result=debt_result,
        kpis=kpis,
        cashflow=cashflow_contract,
        equity_performance=None,
        debt_profile=debt_profile,
        debt_covenants=debt_covenants,
    )

    scenario_result_dict = asdict(scenario_result)

    # ------------------------------------------------------------------
    # 5. Package result (JSON-safe, superset of legacy surface)
    # ------------------------------------------------------------------
    result: dict[str, Any] = {
        "config": cfg,
        "config_path": config_path_label,
        "validation_mode": mode,
        "validated_modules": modules,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
        # New overlays / contracts
        "wacc": wacc_dict,
        "scenario_result": scenario_result_dict,
        "debt_profile": asdict(debt_profile),
        "debt_covenants": asdict(debt_covenants),
    }

    logger.info(
        "Pipeline complete: config_path=%s, annual_rows=%d, kpis=%d, "
        "min_dscr=%.2f, project_irr=%.4f",
        config_path_label,
        len(annual_rows),
        len(kpis),
        min_dscr,
        project_irr,
    )

    return result
