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
from analytics.fx_integration import integrate_fx_into_scenario_result
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt
from finance.equity_distribution_v14 import (
    EquityDistributionConfig,
    calculate_equity_distribution,
)
from finance.refinancing_v14 import (
    RefinancingConfig,
    calculate_refinancing,
)
from finance.utils import get_nested
from finance.wacc_v14 import compute_wacc_from_config

logger = logging.getLogger(__name__)


# =============================================================================
# Validation helpers
# =============================================================================


def _validate_annual_rows(annual_rows: list[dict[str, Any]]) -> None:
    """Validate annual_rows structure from build_annual_rows.

    Ensures:
    - annual_rows is a list
    - Each row is a dict
    - Required keys present (year, cf_pre_debt, etc)

    Raises ValueError if structure invalid.
    """
    if not isinstance(annual_rows, list):
        raise ValueError(f"annual_rows must be list, got {type(annual_rows).__name__}")

    if len(annual_rows) == 0:
        raise ValueError("annual_rows cannot be empty")

    # Check first row has expected keys
    first_row = annual_rows[0]
    if not isinstance(first_row, dict):
        raise ValueError(
            f"annual_rows[0] must be dict, got {type(first_row).__name__}"
        )

    required_keys = {"year", "cfads_final_lkr", "revenue_lkr", "ebitda_lkr"}
    missing_keys = required_keys - set(first_row.keys())
    if missing_keys:
        raise ValueError(f"annual_rows missing required keys: {missing_keys}")

    logger.debug(
        "Validated annual_rows: %d rows, keys=%s",
        len(annual_rows),
        list(first_row.keys())[:10],
    )


def _validate_debt_result(debt_result: dict[str, Any]) -> None:
    """Validate debt_result structure from plan_debt.

    Ensures required keys present:
    - min_dscr, dscr_series, balloon_remaining
    - lkr, usd, dfi sub-dicts

    Raises ValueError if structure invalid.
    """
    if not isinstance(debt_result, dict):
        raise ValueError(f"debt_result must be dict, got {type(debt_result).__name__}")

    required_keys = {
        "min_dscr",
        "dscr_series",
        "balloon_remaining",
        "lkr",
        "usd",
        "dfi",
    }
    missing_keys = required_keys - set(debt_result.keys())
    if missing_keys:
        logger.warning(
            "debt_result missing keys: %s (will use defaults)", missing_keys
        )

    logger.debug(
        "Validated debt_result: keys=%s",
        list(debt_result.keys())[:5]
        + ([f"... +{len(debt_result) - 5} more"] if len(debt_result) > 5 else []),
    )


def _validate_kpis_result(kpis: dict[str, Any]) -> None:
    """Validate KPIs structure from calculate_scenario_kpis.

    Ensures minimum KPI keys are present:
    - project_npv, project_irr, max_debt_usd

    Logs warning if structure incomplete but doesn't raise.
    """
    if not isinstance(kpis, dict):
        raise ValueError(f"kpis must be dict, got {type(kpis).__name__}")

    expected_keys = {"project_npv", "project_irr", "max_debt_usd"}
    missing = expected_keys - set(kpis.keys())
    if missing:
        logger.warning("KPIs missing expected keys: %s", missing)

    logger.debug("Validated KPIs: %d keys present", len(kpis))


def _merge_debt_service_into_annual_rows(
    annual_rows: list[dict[str, Any]],
    debt_result: dict[str, Any],
) -> None:
    """Merge debt service schedule AND interest breakdown from debt_result into annual_rows.
    
    ENHANCEMENT: Now also adds 'interest_usd' and 'principal_repayment_usd' fields
    for complete debt service visibility in Excel exports.
    
    Adds these fields to each annual row:
    - debt_service_usd: Total debt service (interest + principal)
    - interest_usd: Interest component only
    - principal_repayment_usd: Principal repayment component only
    - dscr: Debt Service Coverage Ratio
    
    Modifies annual_rows in-place.
    
    Parameters
    ----------
    annual_rows : list[dict[str, Any]]
        Annual cashflow rows from build_annual_rows
    debt_result : dict[str, Any]
        Debt result from plan_debt containing:
        - debt_service_total: Total service schedule
        - dscr_series: DSCR series
        - debt_schedules: Per-tranche schedules with (interest, principal, service) tuples
        
    Notes
    -----
    Period mapping: Year 1 → Period 2 (after 2 construction periods 0-1)
    inf DSCR values (construction years) are converted to 0.0
    Interest is aggregated from all tranches (LKR, USD, DFI)
    """
    debt_service_schedule = debt_result.get('debt_service_total', [])
    dscr_series = debt_result.get('dscr_series', [])
    debt_schedules = debt_result.get('debt_schedules', {})
    
    logger.info("Merging debt service + interest breakdown into %d annual rows", len(annual_rows))
    
    # Build aggregated interest and principal schedules
    # debt_schedules is dict: {'LKR': [(int, prin, svc), ...], 'USD': [...], 'DFI': [...]}
    max_periods = max(len(sched) for sched in debt_schedules.values()) if debt_schedules else 0
    
    interest_schedule_usd = []
    principal_schedule_usd = []
    
    for period in range(max_periods):
        period_interest = 0.0
        period_principal = 0.0
        
        for tranche_name, schedule in debt_schedules.items():
            if period < len(schedule):
                interest, principal, service = schedule[period]
                period_interest += float(interest)
                period_principal += float(principal)
        
        interest_schedule_usd.append(period_interest)
        principal_schedule_usd.append(period_principal)
    
    logger.debug(
        "Built interest schedule: %d periods, range $%.0f to $%.0f",
        len(interest_schedule_usd),
        min(interest_schedule_usd) if interest_schedule_usd else 0,
        max(interest_schedule_usd) if interest_schedule_usd else 0,
    )
    
    # Merge into annual_rows
    for idx, row in enumerate(annual_rows):
        year = int(row.get('year', idx + 1))
        # Period mapping: construction years + operational years
        # Year 1 maps to period 2 (after 2 construction periods 0-1)
        period = year + 1
        
        if period < len(debt_service_schedule):
            # Debt service (already in USD)
            row['debt_service_usd'] = debt_service_schedule[period]
            
            # DSCR
            dscr_val = dscr_series[period] if period < len(dscr_series) else 0.0
            row['dscr'] = dscr_val if dscr_val != float('inf') else 0.0
            
            # ENHANCEMENT: Interest and principal breakdown
            if period < len(interest_schedule_usd):
                row['interest_usd'] = interest_schedule_usd[period]
                row['principal_repayment_usd'] = principal_schedule_usd[period]
            else:
                row['interest_usd'] = 0.0
                row['principal_repayment_usd'] = 0.0
        else:
            row['debt_service_usd'] = 0.0
            row['dscr'] = 0.0
            row['interest_usd'] = 0.0
            row['principal_repayment_usd'] = 0.0
    
    # Log statistics
    dscr_values = [r.get('dscr', 0) for r in annual_rows if r.get('dscr', 0) > 0]
    interest_values = [r.get('interest_usd', 0) for r in annual_rows if r.get('interest_usd', 0) > 0]
    
    if dscr_values:
        logger.info(
            "Successfully merged debt service: min DSCR=%.2f, max DSCR=%.2f, avg DSCR=%.2f",
            min(dscr_values),
            max(dscr_values),
            sum(dscr_values) / len(dscr_values),
        )
    
    if interest_values:
        logger.info(
            "Successfully merged interest: min=$%.0f, max=$%.0f, avg=$%.0f",
            min(interest_values),
            max(interest_values),
            sum(interest_values) / len(interest_values),
        )
    else:
        logger.warning("No positive interest values found after merge")


# =============================================================================
# Helpers
# =============================================================================


def _build_tranche_debt_profile(
    config: dict[str, Any],
    debt_result: dict[str, Any],
) -> TrancheDebtProfile:
    """Adapter: build a TrancheDebtProfile from the v14 debt_result (plan_debt surface).

    This is a lender-facing summary: totals, IDC, tenor, IO years, and target DSCR.
    Uses defensive .get() to avoid KeyError on missing fields.
    """
    # Extract with defaults to prevent KeyError
    principal_by = debt_result.get("principal_by_tranche") or {}
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
        logger.warning(
            "Could not parse target_dscr: %s; using None",
            dscr_target_raw,
        )
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
    """Build a DebtCovenantSnapshot from the v14 debt_result dict.

    Encodes DSCR profile vs lender threshold and balloon flag for ring-fence views.
    Uses defensive .get() to avoid KeyError on missing fields.
    """
    # Extract with defaults
    dscr_series = list(debt_result.get("dscr_series") or [])
    dscr_min = float(debt_result.get("min_dscr") or 0.0)

    # Threshold: if explicit target_dscr is present, use it; else default to 1.30
    dscr_threshold_raw = get_nested(config, ["Financing_Terms", "target_dscr"])
    try:
        dscr_threshold = (
            float(dscr_threshold_raw) if dscr_threshold_raw is not None else 1.30
        )
    except (TypeError, ValueError):
        logger.warning(
            "Could not parse target_dscr for covenant snapshot: %s; using 1.30",
            dscr_threshold_raw,
        )
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
    """Adapter: map the finance.wacc_v14 dict surface into the contracts_v14 WaccResult.

    If the dict is missing core fields, we fail soft and return None.
    Uses defensive .get() to avoid KeyError.
    """
    if not wacc_dict:
        logger.debug("WACC dict is None/empty; returning None")
        return None

    try:
        base = ContractWaccComponents(
            mode=str(wacc_dict.get("mode", "capm")),
            wacc_nominal=float(wacc_dict.get("wacc_nominal", 0.0)),
            wacc_real=wacc_dict.get("wacc_real"),
            wacc_prudential=float(
                wacc_dict.get("wacc_prudential", wacc_dict.get("wacc_nominal", 0.0))
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
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "WACC dict missing/invalid fields (%s); skipping WaccResult build.",
            exc,
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
    allow_fx_degradation: bool = False,
) -> dict[str, Any]:
    """Run the v14 engine for a single scenario.

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
    allow_fx_degradation : bool, default False
        If True, FX integration failures are logged but don't crash pipeline.
        If False, FX errors re-raised (stops pipeline).

    Returns
    -------
    dict[str, Any]
        ScenarioResult-like dict with keys (superset of legacy surface):
        - validation_mode
        - config_path
        - config
        - annual_rows (WITH debt_service_usd, interest_usd, principal_repayment_usd, dscr fields)
        - debt_result
        - kpis
        - wacc
        - scenario_result
        - debt_profile
        - debt_covenants
        - refinancing_result (if enabled in config)
        - equity_distribution_result (if enabled in config)
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

    logger.info("Pipeline starting: config_path=%s", config_path_label)

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
        logger.info("Schema validation skipped (validation_mode=off)")

    # ------------------------------------------------------------------
    # 3. Canonical v14 finance engine
    # ------------------------------------------------------------------

    # 3a. Cashflow – build annual rows from the v14 cashflow engine.
    logger.info("Step 1/5: Building annual cashflow rows...")
    annual_rows = build_annual_rows(cfg)

    # Validate annual_rows structure
    try:
        _validate_annual_rows(annual_rows)
    except ValueError as e:
        logger.error("Annual rows validation failed: %s", e)
        raise

    logger.debug("Built %d annual rows", len(annual_rows))

    # 3b. Debt – covenant-friendly debt surface (plan_debt is canonical v14).
    logger.info("Step 2/5: Planning debt structure...")
    debt_result = plan_debt(annual_rows=annual_rows, config=cfg)

    # Validate debt_result structure
    try:
        _validate_debt_result(debt_result)
    except ValueError as e:
        logger.error("Debt result validation failed: %s", e)
        raise

    logger.debug("Debt result contains %d keys", len(debt_result))
    
    # 3b.1 ENHANCEMENT: Merge debt service + interest breakdown into annual_rows
    logger.info("Step 2.5/5: Merging debt service + interest breakdown into annual rows...")
    _merge_debt_service_into_annual_rows(annual_rows, debt_result)

    # 3c. Structured cashflow contract (for analytics / exports / lenders).
    logger.info("Step 3/5: Building cashflow contract...")
    cashflow_contract = build_cashflow_result_from_annual_rows(
        config=cfg,
        annual_rows=annual_rows,
    )

    # 3d. WACC (kept parallel to KPIs for now; KPIs still use legacy 10% discount).
    logger.info("Step 4/5: Computing WACC and KPIs...")
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

    try:
        _validate_kpis_result(kpis)
    except ValueError as e:
        logger.error("KPIs validation failed: %s", e)
        raise

    logger.debug("Calculated %d KPIs", len(kpis))

    # Equity overlay
    #
    # NOTE: v14 equity engine is designed to operate on *equity cashflows*
    # (negative = contributions, positive = distributions). The canonical
    # equity series is not yet exposed by the cashflow/debt pipeline, so we
    # do not attempt to fabricate it here.
    logger.debug(
        "Equity performance: not implemented (v14 equity engine deferred to future sprint)"
    )

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

    # Base ScenarioResult without FX overlays
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

    # ------------------------------------------------------------------
    # 4a. FX integration (optional, config-driven)
    # ------------------------------------------------------------------
    if cfg.get("FX") or cfg.get("fx"):
        logger.info("FX configuration detected; attempting FX integration.")
        try:
            scenario_result = integrate_fx_into_scenario_result(
                scenario_result=scenario_result,
                config=cfg,
                debt_result=debt_result,
                annual_rows=annual_rows,
            )
            if scenario_result.fx_block is not None:
                logger.info(
                    "FX integration successful: strategy=%s, fx_match_ratio=%.1f, "
                    "hedging_coverage_pct=%.1f",
                    scenario_result.fx_block.strategy,
                    scenario_result.fx_block.fx_match_ratio,
                    scenario_result.fx_block.hedging_coverage_pct,
                )
            else:
                logger.warning(
                    "FX integration completed but fx_block is None; "
                    "check FX configuration for issues."
                )
        except (TypeError, ValueError, KeyError) as exc:
            if allow_fx_degradation:
                logger.warning(
                    "FX integration failed (degradation enabled): %s; "
                    "continuing with FX fields as None",
                    exc,
                )
            else:
                logger.error("FX integration failed (degradation disabled): %s", exc)
                raise
    else:
        logger.debug("No FX configuration found; skipping FX integration.")

    scenario_result_dict = asdict(scenario_result)

    # ------------------------------------------------------------------
    # 4b. Refinancing module (optional, config-driven)
    # ------------------------------------------------------------------
    refinancing_result = None
    if cfg.get("Refinancing") or cfg.get("refinancing"):
        logger.info("Step 5/5: Calculating refinancing impacts...")
        try:
            refi_config_raw = cfg.get("Refinancing") or cfg.get("refinancing")
            if isinstance(refi_config_raw, dict):
                refi_config = RefinancingConfig(**refi_config_raw)
            else:
                refi_config = RefinancingConfig()

            # Derive actual values from pipeline state
            current_year = len(annual_rows)
            current_dscr = float(debt_result.get("min_dscr", 0.0))

            # Weighted average debt rate from debt_result
            current_interest_rate = float(debt_result.get("avg_debt_rate", 0.06))

            # Total debt principal
            current_debt_balance = float(debt_result.get("debt_total", 0.0))

            # Remaining tenor from debt_result
            tenor_years = int(debt_result.get("tenor_years", 15))
            remaining_years = max(1, tenor_years - current_year)

            # Use last year's CFADS as proxy for annual cashflow
            if annual_rows:
                annual_cashflow = float(annual_rows[-1].get("cfads_final_lkr", 0.0))
                ebitda = float(annual_rows[-1].get("ebitda_lkr", 0.0))
            else:
                annual_cashflow = 0.0
                ebitda = 0.0

            refinancing_result = calculate_refinancing(
                config=refi_config,
                current_year=current_year,
                current_dscr=current_dscr,
                current_interest_rate=current_interest_rate,
                current_debt_balance=current_debt_balance,
                remaining_years=remaining_years,
                annual_cashflow=annual_cashflow,
                ebitda=ebitda,
            )
            logger.info(
                "Refinancing calculated: triggered=%s, net_benefit=%.2f M",
                refinancing_result.refinancing_triggered,
                refinancing_result.net_benefit,
            )
        except (TypeError, ValueError, AttributeError) as exc:
            logger.warning(
                "Refinancing calculation failed: %s; continuing without refinancing",
                exc,
            )
            refinancing_result = None
    else:
        logger.debug("No Refinancing configuration found; skipping refinancing.")

    # ------------------------------------------------------------------
    # 4c. Equity distribution module (optional, config-driven)
    # ------------------------------------------------------------------
    equity_distribution_result = None
    if cfg.get("EquityDistribution") or cfg.get("equity_distribution"):
        logger.info("Step 5/5: Calculating equity distributions...")
        try:
            eq_config_raw = cfg.get("EquityDistribution") or cfg.get(
                "equity_distribution"
            )
            if isinstance(eq_config_raw, dict):
                eq_config = EquityDistributionConfig(**eq_config_raw)
            else:
                eq_config = EquityDistributionConfig()

            # Derive actual values from pipeline state
            current_year = len(annual_rows)

            if annual_rows:
                # Use last year's data
                last_row = annual_rows[-1]
                annual_cashflow = float(last_row.get("cfads_final_lkr", 0.0))
                debt_service_required = float(
                    debt_result.get("debt_service_total", [0.0])[-1]
                    if debt_result.get("debt_service_total")
                    else 0.0
                )
                monthly_debt_service = debt_service_required / 12.0

                # Derive monthly opex from annual opex in LKR
                opex_lkr = float(last_row.get("opex_lkr", 0.0))
                monthly_operating_costs = opex_lkr / 12.0
            else:
                annual_cashflow = 0.0
                debt_service_required = 0.0
                monthly_debt_service = 0.0
                monthly_operating_costs = 0.0

            current_dscr = float(debt_result.get("min_dscr", 0.0))

            # Calculate LLCR from debt_result if available
            current_llcr = float(debt_result.get("llcr", 1.5))

            # Derive equity capital from config financing terms
            capex_total = float(
                get_nested(cfg, ["capex", "usd_total"], 100_000_000.0)
            )
            debt_ratio = float(
                get_nested(cfg, ["Financing_Terms", "debt_ratio"], 0.70)
            )
            equity_ratio = 1.0 - debt_ratio

            # Assume 60/40 split between Class A and Class B
            total_equity = capex_total * equity_ratio
            class_a_invested = total_equity * 0.60
            class_b_invested = total_equity * 0.40

            equity_distribution_result = calculate_equity_distribution(
                config=eq_config,
                year=current_year,
                annual_cashflow=annual_cashflow,
                debt_service_required=debt_service_required,
                monthly_debt_service=monthly_debt_service,
                monthly_operating_costs=monthly_operating_costs,
                current_dscr=current_dscr,
                current_llcr=current_llcr,
                class_a_invested=class_a_invested,
                class_b_invested=class_b_invested,
            )
            logger.info(
                "Equity distribution calculated: enabled=%s, total_dist=%.2f M",
                equity_distribution_result.distribution_enabled,
                equity_distribution_result.total_equity_distribution,
            )
        except (TypeError, ValueError, AttributeError, KeyError) as exc:
            logger.warning(
                "Equity distribution calculation failed: %s; continuing without distributions",
                exc,
            )
            equity_distribution_result = None
    else:
        logger.debug(
            "No EquityDistribution configuration found; skipping distributions."
        )

    # ------------------------------------------------------------------
    # 5. Package result (JSON-safe, superset of legacy surface)
    # ------------------------------------------------------------------
    result: dict[str, Any] = {
        "config": cfg,
        "config_path": config_path_label,
        "validation_mode": mode,
        "validated_modules": modules,
        "annual_rows": annual_rows,  # NOW INCLUDES debt_service_usd, interest_usd, principal_repayment_usd, dscr
        "debt_result": debt_result,
        "kpis": kpis,
        # New overlays / contracts
        "wacc": wacc_dict,
        "scenario_result": scenario_result_dict,
        "debt_profile": asdict(debt_profile),
        "debt_covenants": asdict(debt_covenants),
        # New modules (may be None)
        "refinancing_result": (
            refinancing_result.to_dict() if refinancing_result else None
        ),
        "equity_distribution_result": (
            equity_distribution_result.to_dict() if equity_distribution_result else None
        ),
    }

    logger.info(
        "Pipeline complete: config_path=%s, annual_rows=%d, kpis=%d, "
        "min_dscr=%.2f, project_irr=%.4f, fx_block=%s, refinancing=%s, equity_dist=%s",
        config_path_label,
        len(annual_rows),
        len(kpis),
        min_dscr,
        project_irr,
        "present" if scenario_result.fx_block else "absent",
        "calculated" if refinancing_result else "skipped",
        "calculated" if equity_distribution_result else "skipped",
    )

    return result
