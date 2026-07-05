"""Enhanced Pipeline v14 - Production-Ready Analytics Orchestration.

GWTF Compliance:
- Single evaluation gateway (lazy-loaded)
- No direct finance imports by external modules
- Config-driven behavior
- Type-safe throughout

CASPER Compliance:
- Full metadata tracking (timestamps, config paths)
- Audit trail for all calculations
- Tail risk integration ready
- Covenant breach detection built-in

CESSPIT Compliance:
- Pre-flight schema validation
- Fail-fast error handling
- Defensive rehydration
- Graceful degradation for optional features

CCCDIR Compliance:
- Config-driven (not hardcoded)
- Clear, DRY implementation
- Pragmatic typing: Pydantic models for the equity-distribution config and dataclass
  contracts where they add value, with Mapping[str, Any] / dict[str, Any] kept at the
  flexible config-in / result-out boundary. Fully typed ScenarioConfig / DebtResult /
  CashflowRow / KPIResult models are a tracked refinement, NOT a current guarantee — do
  not read this as "no dict[str, Any] in any signature".
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from analytics.contracts_v14 import (
    DebtCovenantSnapshot,
    EquityPerformance,
    ScenarioResult,
    TrancheDebtProfile,
)
from analytics.contracts_v14 import WaccComponents as ContractWaccComponents
from analytics.contracts_v14 import (
    WaccResult,
)
from analytics.core.metrics import DEFAULT_DISCOUNT_RATE, calculate_scenario_kpis
from analytics.run_manifest import build_run_manifest, engine_version
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.debt_v14 import _extract_capex_usd, plan_debt
from finance.utils import get_nested
from finance.wacc_v14 import compute_build_up_wacc, compute_wacc_from_config

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    """CASPER: Pipeline execution metrics for monitoring and audit."""

    total_runtime_sec: float
    config_load_time_sec: float
    validation_time_sec: float
    cashflow_time_sec: float
    debt_time_sec: float
    kpi_time_sec: float
    wacc_time_sec: float
    fx_integration_time_sec: float
    annual_rows_count: int
    kpis_count: int
    equity_distribution_time_sec: float = 0.0
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)
    fx_integration_attempted: bool = False
    fx_integration_succeeded: bool = False
    # Tz-aware UTC (was the deprecated naive ``datetime.utcnow()``); the ISO string
    # now carries an explicit ``+00:00`` offset, matching the tz-aware run manifest.
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Read from the repo VERSION file (single source of truth) — was a hardcoded
    # 'v14.3.0' literal that had drifted from the real version (CESSPIT/CCCDIR).
    pipeline_version: str = field(default_factory=engine_version)


class PipelineValidationError(Exception):
    """CESSPIT: Raised when pipeline validation fails in strict mode."""

    pass


class PipelineConfigError(Exception):
    """CCCDIR: Raised when config is invalid or missing required fields."""

    pass


def _validate_config_type_and_structure(config: Any) -> dict[str, Any]:
    """CESSPIT: Strict type and structure validation for config."""
    if isinstance(config, (str, Path)):
        try:
            cfg = load_scenario_config(str(config))
            if not isinstance(cfg, dict):
                raise PipelineConfigError(
                    f"Loaded config from {config} is not a dict: {type(cfg)}"
                )
            return cfg
        except Exception as exc:
            raise PipelineConfigError(
                f"Failed to load config from {config}: {exc}"
            ) from exc

    if isinstance(config, Mapping):
        cfg = dict(config)
        if not cfg:
            raise PipelineConfigError("Config mapping is empty")
        # NOTE: the FX spot cross-assert is deliberately NOT run here. Like the AEP
        # reconciliation / provenance guards, it is a LOAD-TIME (authored-config) check —
        # run_v14_pipeline is also the per-trial entry for Monte-Carlo / sensitivity, which
        # legitimately perturb fx.start_lkr_per_usd in-memory while leaving fx.rates/pinned
        # at the base. Enforcing it here would reject every MC draw. Authored inline/API
        # configs are cross-asserted at their own entry point (api.pipeline_api).
        return cfg

    raise PipelineConfigError(
        f"Config must be str, Path, or Mapping; got {type(config).__name__}"
    )


def _validate_annual_rows_structure(
    annual_rows: Any, require_debt_fields: bool = False
) -> list[dict[str, Any]]:
    """CESSPIT: Strict validation of annual_rows structure."""
    if not isinstance(annual_rows, list):
        raise PipelineValidationError(
            f"annual_rows must be list, got {type(annual_rows).__name__}"
        )

    if len(annual_rows) == 0:
        raise PipelineValidationError("annual_rows cannot be empty")

    first_row = annual_rows[0]
    if not isinstance(first_row, dict):
        raise PipelineValidationError(
            f"annual_rows[0] must be dict, got {type(first_row).__name__}"
        )

    required_keys = {"year"}
    if require_debt_fields:
        required_keys.update({"cf_pre_debt", "debt_service_total"})

    missing_keys = required_keys - set(first_row.keys())
    if missing_keys:
        raise PipelineValidationError(
            f"annual_rows[0] missing required keys: {missing_keys}"
        )

    for key in required_keys:
        if key not in first_row:
            continue
        try:
            float(first_row[key])
        except (TypeError, ValueError):
            raise PipelineValidationError(
                f"annual_rows[0]['{key}'] not convertible to float: {first_row[key]}"
            ) from None

    logger.debug(
        "Validated annual_rows: %d rows, first_row_keys=%s",
        len(annual_rows),
        list(first_row.keys()),
    )
    return annual_rows


def _validate_debt_result_structure(debt_result: Any) -> dict[str, Any]:
    """CESSPIT: Strict validation of debt_result from plan_debt()."""
    if not isinstance(debt_result, dict):
        raise PipelineValidationError(
            f"debt_result must be dict, got {type(debt_result).__name__}"
        )

    required_keys = {"min_dscr", "dscr_series", "balloon_remaining"}
    missing_keys = required_keys - set(debt_result.keys())
    if missing_keys:
        raise PipelineValidationError(
            f"debt_result missing required keys: {missing_keys}"
        )

    try:
        float(debt_result["min_dscr"])
        list(debt_result["dscr_series"])
        float(debt_result["balloon_remaining"])
    except (TypeError, ValueError) as exc:
        raise PipelineValidationError(
            f"debt_result critical field type validation failed: {exc}"
        ) from exc

    logger.debug(
        "Validated debt_result: %d keys, min_dscr=%.2f",
        len(debt_result),
        float(debt_result["min_dscr"]),
    )
    return debt_result


def _enrich_annual_rows_with_debt(
    annual_rows: list[dict[str, Any]],
    debt_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Overlay lender-facing debt columns onto annual rows."""
    debt_service = list(debt_result.get("debt_service_total") or [])
    # Per-period scheduled INTEREST, same PERIOD index as debt_service_total. Surfaced on
    # each operating row (interest_usd) so the equity waterfall can charge a grossed-up
    # non-resident interest WHT; informational here — it does NOT touch cf_after_debt
    # (which feeds DSCR). The WHT deduction happens only in the equity path.
    interest_series = list(debt_result.get("interest_total") or [])
    # Post-maturity cash diverted from equity to retire the balloon (sweep/refi/
    # bullet). Same PERIOD index as debt_service_total; senior to equity but NOT
    # part of scheduled debt service, so it does not enter the DSCR.
    balloon_resolution = list(debt_result.get("balloon_resolution") or [])
    # debt_service_total is PERIOD-indexed (offset by the construction + bridge
    # lead-in). Align each annual row to its debt period via the canonical map;
    # positional indexing attributed each year an earlier (higher-CFADS) year's
    # service, collapsing the achieved DSCR ~3 years out of phase and triggering a
    # phantom covenant lockup. Falls back to positional when no map is present.
    period_map = debt_result.get("annual_row_debt_period_map") or []
    row_to_period: dict[int, int] = {}
    for mapping in period_map:
        try:
            row_to_period[int(mapping["annual_row_index"])] = int(
                mapping["debt_period"]
            )
        except (KeyError, TypeError, ValueError):
            continue

    # The "bridge" lead-in period carries real scheduled debt service but maps to no
    # operating row, so without this it was ORPHANED from the equity waterfall: ~$8.5M
    # of debt service never reduced equity distributions, flattering equity IRR (audit
    # finding 2.1). It is the first post-construction period, so fold its service into
    # operating year 1 (the nearest equity period). Years 2+ stay aligned to their own
    # sculpted period, so the per-year DSCR and covenant timing are unchanged for them.
    mapped_periods = set(row_to_period.values())
    bridge_period = debt_result.get("cfads_bridge_debt_period")
    bridge_extra_service = 0.0
    if (
        bridge_period is not None
        and int(bridge_period) not in mapped_periods
        and 0 <= int(bridge_period) < len(debt_service)
    ):
        try:
            bridge_extra_service = float(debt_service[int(bridge_period)] or 0.0)
        except (TypeError, ValueError):
            bridge_extra_service = 0.0

    # Bridge-period interest, folded into operating year 1 the same way as its service.
    bridge_extra_interest = 0.0
    if (
        bridge_period is not None
        and int(bridge_period) not in mapped_periods
        and 0 <= int(bridge_period) < len(interest_series)
    ):
        try:
            bridge_extra_interest = float(interest_series[int(bridge_period)] or 0.0)
        except (TypeError, ValueError):
            bridge_extra_interest = 0.0

    enriched: list[dict[str, Any]] = []

    for idx, row in enumerate(annual_rows):
        out = dict(row)
        cfads_usd = out.get("cfads_usd", out.get("cf_pre_debt", 0.0))
        try:
            cf_pre_debt = float(cfads_usd or 0.0)
        except (TypeError, ValueError):
            cf_pre_debt = 0.0

        period_idx = row_to_period.get(idx, idx)
        service = (
            debt_service[period_idx] if 0 <= period_idx < len(debt_service) else 0.0
        )
        try:
            debt_service_value = float(service or 0.0)
        except (TypeError, ValueError):
            debt_service_value = 0.0

        # Operating year 1 also bears the orphaned bridge-period service (finding 2.1).
        if idx == 0 and bridge_extra_service > 0.0:
            debt_service_value += bridge_extra_service

        resolution = (
            balloon_resolution[period_idx]
            if 0 <= period_idx < len(balloon_resolution)
            else 0.0
        )
        try:
            balloon_resolution_value = float(resolution or 0.0)
        except (TypeError, ValueError):
            balloon_resolution_value = 0.0

        interest = (
            interest_series[period_idx]
            if 0 <= period_idx < len(interest_series)
            else 0.0
        )
        try:
            interest_value = float(interest or 0.0)
        except (TypeError, ValueError):
            interest_value = 0.0
        if idx == 0 and bridge_extra_interest > 0.0:
            interest_value += bridge_extra_interest

        out["cf_pre_debt"] = cf_pre_debt
        out["debt_service_total"] = debt_service_value
        out["interest_usd"] = interest_value
        out["balloon_resolution"] = balloon_resolution_value
        out["cf_after_debt"] = (
            cf_pre_debt - debt_service_value - balloon_resolution_value
        )
        enriched.append(out)

    return _validate_annual_rows_structure(enriched, require_debt_fields=True)


def _debt_fee_rate(config: Mapping[str, Any]) -> float:
    """Annualised debt fee load (guarantee/PRI + amortised upfront) for a fee-inclusive kd.

    The guarantee/PRI premium (guarantee_revenue_pct) loads the kd ONLY when the deal buys
    it — gated on Financing_Terms.use_revenue_guarantee (default off). Previously the premium
    was charged unconditionally, so a scenario with use_revenue_guarantee: false advertised
    the guarantee OFF yet still paid its 75bps fee in the WACC (round-9 fix). fees.upfront_pct
    (amortised over the tenor) always loads.
    NOTE: Financing_Terms.fees.commitment_pct was DECORATIVE — never read here, so it was
    removed from the scenarios (round-8) rather than wired. A commitment fee on the undrawn
    balance is a real cost, but modelling it needs the construction drawdown profile this
    function does not have; if added later, charge it on the committed-but-undrawn balance.
    """
    fin = config.get("Financing_Terms") or {}
    if not isinstance(fin, Mapping):
        return 0.0
    use_guarantee = bool(fin.get("use_revenue_guarantee", False))
    guarantee = float(fin.get("guarantee_revenue_pct") or 0.0) if use_guarantee else 0.0
    fees = fin.get("fees") or {}
    upfront = (
        float(fees.get("upfront_pct") or 0.0) if isinstance(fees, Mapping) else 0.0
    )
    tenor = float(fin.get("tenor_years") or 15.0) or 15.0
    return guarantee + (upfront / tenor)


def _resolve_wacc_and_discounts(
    config: Mapping[str, Any], debt_result: Mapping[str, Any]
) -> tuple[dict[str, Any], float, float | None]:
    """Resolve the WACC dict and the project/equity discount rates.

    ``build_up`` mode computes the after-tax WACC from the ACTUAL sized debt (gearing
    + blended rate from the debt engine) plus the configured cost of equity. When
    ``wacc.drives_discount_rate`` is set, the project NPV is discounted at the WACC and
    equity at the cost of equity; otherwise the legacy default rate is used and the
    WACC stays informational (contract only) — preserving pre-existing behaviour.
    """
    wacc_cfg = config.get("wacc", {}) or {}
    mode = str(wacc_cfg.get("mode", "")).lower()
    if mode == "build_up":
        capex = _extract_capex_usd(dict(config))
        debt_total = float(debt_result.get("debt_total") or 0.0)
        d_to_v = debt_total / capex if capex > 0 else 0.0
        kd_pretax = float(debt_result.get("avg_debt_rate") or 0.0)
        wacc_dict = compute_build_up_wacc(
            dict(config),
            debt_to_value=d_to_v,
            cost_of_debt_pretax=kd_pretax,
            debt_fee_rate=_debt_fee_rate(config),
        )
    else:
        wacc_dict = compute_wacc_from_config(dict(config))

    project_discount = DEFAULT_DISCOUNT_RATE
    equity_discount: float | None = None
    if wacc_dict and wacc_cfg.get("drives_discount_rate"):
        project_discount = float(wacc_dict.get("wacc_nominal") or DEFAULT_DISCOUNT_RATE)
        ke = wacc_dict.get("cost_of_equity")
        equity_discount = float(ke) if ke else None
    elif wacc_dict and not wacc_cfg.get("drives_discount_rate"):
        # A1/#45: the scenario built a WACC / cost-of-equity block but did not opt it in
        # (drives_discount_rate falsy), so the published NPV is discounted at the bare
        # DEFAULT_DISCOUNT_RATE — the computed WACC is informational-only and the declared
        # equity hurdle is ignored for the equity NPV. Surface that loudly rather than let
        # the gap pass silently. (Re-pointing the default to returns.equity_discount_rate
        # would MOVE equity NPV — a re-baseline, deliberately out of scope for this guard.)
        logger.warning(
            "wacc block present but drives_discount_rate is not set — project/equity NPV is "
            "discounted at the default %.2f, NOT the computed WACC (wacc_nominal=%s). Set "
            "wacc.drives_discount_rate to discount at the built WACC.",
            DEFAULT_DISCOUNT_RATE,
            wacc_dict.get("wacc_nominal"),
        )
    return wacc_dict, project_discount, equity_discount


def _build_wacc_contract(wacc_dict: Mapping[str, Any] | None) -> WaccResult | None:
    """CCCDIR: Adapter from finance.wacc_v14 dict to contracts_v14 WaccResult."""
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
        logger.warning("WACC dict validation failed: %s; skipping WaccResult", exc)
        return None

    return WaccResult(
        base=base,
        prudential_rate=base.wacc_prudential,
        prudential_npv=None,
        meta={"mode": base.mode},
    )


def _build_tranche_debt_profile(
    config: dict[str, Any],
    debt_result: dict[str, Any],
) -> TrancheDebtProfile:
    """CCCDIR: Build TrancheDebtProfile from v14 debt_result."""
    principal_by = debt_result.get("principal_by_tranche") or {}
    lkr = debt_result.get("lkr") or {}
    usd = debt_result.get("usd") or {}
    dfi = debt_result.get("dfi") or {}

    construction_years = int(debt_result.get("construction_years") or 0)
    tenor_years = int(debt_result.get("tenor_years") or 0)
    timeline_periods = int(debt_result.get("timeline_periods") or 0)

    total_debt = float(sum(principal_by.values()) or 0.0)
    total_idc = float(debt_result.get("total_idc") or 0.0)

    rates = get_nested(config, ["Financing_Terms", "rates"], {}) or {}
    lkr_rate = rates.get("lkr_nominal") or rates.get("lkr_min")
    usd_rate = rates.get("usd_nominal") or rates.get("usd_commercial_min")
    dfi_rate = rates.get("dfi_nominal") or rates.get("dfi_min")

    interest_only_years = int(
        get_nested(config, ["Financing_Terms", "interest_only_years"]) or 0
    )

    amortization_style = (
        get_nested(config, ["Financing_Terms", "amortization_style"]) or "sculpted"
    )
    amortization_style = str(amortization_style).lower()

    dscr_target_raw = get_nested(config, ["Financing_Terms", "target_dscr"])
    try:
        dscr_target = float(dscr_target_raw) if dscr_target_raw is not None else None
    except (TypeError, ValueError):
        logger.warning("Could not parse target_dscr: %s; using None", dscr_target_raw)
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
        lkr_rate=lkr_rate,
        usd_rate=usd_rate,
        dfi_rate=dfi_rate,
        interest_only_years=interest_only_years,
        amortization_style=amortization_style,
        dscr_target=dscr_target,
    )


def _build_debt_covenant_snapshot(
    config: dict[str, Any],
    debt_result: dict[str, Any],
) -> DebtCovenantSnapshot:
    """CASPER: Build DebtCovenantSnapshot for tail risk tracking."""
    dscr_series = list(debt_result.get("dscr_series") or [])
    dscr_min = float(debt_result.get("min_dscr") or 0.0)

    dscr_threshold_raw = get_nested(config, ["Financing_Terms", "target_dscr"])
    try:
        dscr_threshold = (
            float(dscr_threshold_raw) if dscr_threshold_raw is not None else 1.30
        )
    except (TypeError, ValueError):
        logger.warning(
            "Could not parse target_dscr for covenant: %s; using 1.30",
            dscr_threshold_raw,
        )
        dscr_threshold = 1.30

    years_below = 0
    first_breach_year: Optional[int] = None
    last_breach_year: Optional[int] = None

    for idx, value in enumerate(dscr_series, start=1):
        if value is None:
            continue
        try:
            dscr_value = float(value)
        except (TypeError, ValueError):
            logger.debug(
                "Skipping non-numeric DSCR covenant value at position %d: %r",
                idx,
                value,
            )
            continue
        if dscr_value == float("inf"):
            continue
        if dscr_value < dscr_threshold:
            years_below += 1
            if first_breach_year is None:
                first_breach_year = idx
            last_breach_year = idx

    balloon_remaining = float(debt_result.get("balloon_remaining") or 0.0)
    balloon_flag = balloon_remaining > 1000.0

    if years_below == 0:
        audit_status = "PASS"
        notes = "All DSCR covenant requirements met"
    elif years_below <= 2:
        audit_status = "REVIEW"
        notes = f"Minor breach in {years_below} year(s)"
    else:
        audit_status = "FAIL"
        notes = f"Significant breach in {years_below} year(s)"

    if balloon_flag:
        balloon_pct = float(debt_result.get("balloon_pct") or 0.0)
        treatment = str(debt_result.get("balloon_treatment") or "")
        notes += f"; Balloon: ${balloon_remaining:,.0f} ({balloon_pct:.1%}"
        if treatment:
            notes += f", {treatment}"
        notes += ")"
        if bool(debt_result.get("balloon_covenant_breach")):
            max_pct = float(debt_result.get("max_balloon_pct") or 0.10)
            notes += f" — BREACHES max_balloon_pct {max_pct:.0%}"

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


def _update_kpis_with_equity_distribution(
    kpis: dict[str, Any], equity_distribution: Mapping[str, Any]
) -> EquityPerformance | None:
    """Merge computed equity distribution metrics into the KPI surface."""
    status = str(equity_distribution.get("status", "failed"))
    kpis["equity_distribution_status"] = status

    if status not in {"computed", "defaulted"}:
        return None

    summary_raw = equity_distribution.get("equity_summary")
    if not isinstance(summary_raw, Mapping):
        return None

    for source_key, target_key in (
        ("equity_irr", "equity_irr"),
        ("equity_npv", "equity_npv"),
        ("equity_multiple", "equity_multiple"),
        ("moic", "equity_moic"),
        ("payback_period_years", "equity_payback_period_years"),
        ("total_equity_distributed_usd", "total_equity_distributed_usd"),
        ("average_cash_on_cash", "average_equity_cash_on_cash"),
        ("covenant_locked_years", "equity_covenant_locked_years"),
    ):
        value = summary_raw.get(source_key)
        if value is not None:
            kpis[target_key] = value

    return EquityPerformance(
        equity_irr=summary_raw.get("equity_irr"),
        equity_npv=summary_raw.get("equity_npv"),
        equity_multiple=summary_raw.get("equity_multiple"),
        metadata={
            "source": "equity_distribution_v14_hydra",
            "status": status,
            "equity_investment_source": summary_raw.get("equity_investment_source"),
        },
    )


def run_v14_pipeline_enhanced(
    config: str | Path | Mapping[str, Any],
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
    enable_monitoring: bool = True,
    allow_fx_degradation: bool = False,
) -> dict[str, Any]:
    """GWTF Gateway: Enhanced v14 pipeline with comprehensive hardening.

    The success result carries a ``run_manifest`` key (analytics.run_manifest):
    a reproducibility stamp whose ``config_sha256`` hashes the RESOLVED config
    this run evaluated, plus engine version, commit SHA, and validation mode
    (#577). Additive metadata only — no KPI is touched.
    """
    del allow_fx_degradation
    start_time = time.time()
    metrics = PipelineMetrics(
        total_runtime_sec=0,
        config_load_time_sec=0,
        validation_time_sec=0,
        cashflow_time_sec=0,
        debt_time_sec=0,
        kpi_time_sec=0,
        wacc_time_sec=0,
        fx_integration_time_sec=0,
        annual_rows_count=0,
        kpis_count=0,
    )

    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: {validation_mode!r}"
        )

    try:
        phase_start = time.time()

        cfg = _validate_config_type_and_structure(config)
        config_path_label = (
            str(config) if isinstance(config, (str, Path)) else "<inline>"
        )

        metrics.config_load_time_sec = time.time() - phase_start
        logger.info(
            "Config loaded in %.3f sec from %s",
            metrics.config_load_time_sec,
            config_path_label,
        )

        phase_start = time.time()
        if mode == "strict":
            modules = validation_modules or ["cashflow", "debt"]
            validate_config_for_v14(
                raw_config=cfg,
                config_path=config_path_label,
                modules=modules,
            )
            logger.info("Schema validation passed: %s", ", ".join(modules))
        else:
            logger.info("Schema validation skipped (mode=off)")

        metrics.validation_time_sec = time.time() - phase_start

        # Reproducibility stamp (#577): built INSIDE the engine from the ALREADY-
        # RESOLVED ``cfg`` (no config re-load), immediately after resolution + schema
        # validation, so ``config_sha256`` binds to the exact post-override config the
        # engine evaluates. Every caller — CLI, web API, evaluation_v14 gateway,
        # MC/sensitivity per-trial entries, scripts — now receives the manifest;
        # outer stampers defer to it (stamp-if-absent). Additive metadata only.
        run_manifest = build_run_manifest(cfg, validation_mode=mode).as_dict()

        phase_start = time.time()
        # Lazy import: breaks the cashflow_v14 <-> analytics cold-import cycle
        # (cashflow_v14 imports analytics.config_schema, which pulls in this module
        # via the analytics package init). debt_v14 has no such edge, so its
        # imports above stay eager.
        from finance.cashflow_v14 import build_annual_rows

        annual_rows = build_annual_rows(cfg)
        annual_rows = _validate_annual_rows_structure(annual_rows)
        metrics.annual_rows_count = len(annual_rows)
        metrics.cashflow_time_sec = time.time() - phase_start
        logger.info(
            "Cashflow built in %.3f sec: %d rows",
            metrics.cashflow_time_sec,
            len(annual_rows),
        )

        phase_start = time.time()
        debt_result = plan_debt(annual_rows=annual_rows, config=cfg)
        debt_result = _validate_debt_result_structure(debt_result)

        # Senior credit-support fees (#737): the debt engine sized the debt with the
        # guarantee + PRI fee inside the sculpt and exposes the per-period USD fee
        # (rate x opening outstanding). Translate it to LKR at each operating row's
        # spot FX (same basis as opex/interest; the fee base is USD debt, so no
        # _hedged_usd) and REBUILD the unlevered rows with the fee charged at the
        # EBITDA line — so reported CFADS, project NPV/IRR and (levered) tax all bear
        # the SAME fee the sculpt and the DSCR series charged. Construction periods
        # carry no operating row and a 0.0 engine fee. No fees configured -> the
        # original rows pass through untouched (byte-identical).
        senior_fee_usd = [
            float(v or 0.0) for v in (debt_result.get("senior_fee_usd") or [])
        ]
        senior_fee_lkr_series: list[float] | None = None
        if any(fee > 0.0 for fee in senior_fee_usd):
            fee_period_map = debt_result.get("annual_row_debt_period_map") or []
            fee_row_to_period: dict[int, int] = {}
            for mapping in fee_period_map:
                try:
                    fee_row_to_period[int(mapping["annual_row_index"])] = int(
                        mapping["debt_period"]
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            senior_fee_lkr_series = []
            for row_idx, row in enumerate(annual_rows):
                period_idx = fee_row_to_period.get(row_idx, row_idx)
                fee_usd = (
                    senior_fee_usd[period_idx]
                    if 0 <= period_idx < len(senior_fee_usd)
                    else 0.0
                )
                senior_fee_lkr_series.append(fee_usd * float(row.get("fx_rate") or 0.0))
            annual_rows = build_annual_rows(
                cfg, senior_fee_lkr_series=senior_fee_lkr_series
            )
            annual_rows = _validate_annual_rows_structure(annual_rows)

        annual_rows_enriched = _enrich_annual_rows_with_debt(annual_rows, debt_result)
        metrics.debt_time_sec = time.time() - phase_start
        logger.info("Debt structured in %.3f sec", metrics.debt_time_sec)

        # WACC + discount rates resolved BEFORE the NPV so a build_up WACC (derived
        # from the sized debt) can drive the project/equity discounting instead of a
        # hardcoded rate. Default (no drives_discount_rate flag) preserves the legacy
        # DEFAULT_DISCOUNT_RATE and leaves the WACC informational.
        phase_start = time.time()
        wacc_dict, project_discount, equity_discount = _resolve_wacc_and_discounts(
            cfg, debt_result
        )
        wacc_contract = _build_wacc_contract(wacc_dict)
        # Single source of truth for the discount basis: `drives_discount_rate`
        # is what made `project_discount` the build-up WACC instead of the
        # legacy default. Both the KPI surface and the ScenarioResult contract
        # below report from these same values so they cannot disagree.
        wacc_cfg = cfg.get("wacc", {}) or {}
        wacc_drives = bool(wacc_dict) and bool(wacc_cfg.get("drives_discount_rate"))
        wacc_label_val = (
            str(wacc_dict.get("mode")) if (wacc_drives and wacc_dict) else "base"
        )
        metrics.wacc_time_sec = time.time() - phase_start
        logger.info(
            "WACC resolved in %.3f sec: project discount %.3f%%",
            metrics.wacc_time_sec,
            project_discount * 100.0,
        )

        phase_start = time.time()
        # Prudential (downside) NPV: discount the same CFADS at the haircut WACC
        # (wacc_dict['wacc_prudential']) so the lender surface carries a conservative
        # valuation alongside the base NPV. The metrics consumer + WaccResult.prudential_npv
        # were de-decorated by PR #369 but never fed here, so project_npv_prudential was never
        # computed live and the CASPER payload published a prudential RATE with a None NPV.
        prudential_rate = wacc_dict.get("wacc_prudential") if wacc_dict else None
        kpis = calculate_scenario_kpis(
            config=cfg,
            annual_rows=annual_rows_enriched,
            debt_result=debt_result,
            discount_rate=project_discount,
            wacc_is_real=wacc_drives,
            wacc_label=wacc_label_val,
            prudential_rate=prudential_rate,
        )
        # Populate the (frozen) WaccResult contract's prudential_npv from the freshly
        # computed metric so the CASPER payload no longer advertises a rate beside a None NPV.
        if wacc_contract is not None and kpis.get("project_npv_prudential") is not None:
            wacc_contract = replace(
                wacc_contract,
                prudential_npv=float(kpis["project_npv_prudential"]),
            )
        metrics.kpis_count = len(kpis)
        metrics.kpi_time_sec = time.time() - phase_start
        logger.info(
            "KPIs calculated in %.3f sec: %d metrics", metrics.kpi_time_sec, len(kpis)
        )

        phase_start = time.time()
        equity_cfg: Mapping[str, Any] = cfg
        if equity_discount is not None:
            equity_cfg = dict(cfg)
            equity_block = dict(equity_cfg.get("equity", {}) or {})
            equity_block["discount_rate"] = equity_discount
            equity_cfg["equity"] = equity_block
        # Two-pass interest tax shield (round-5 #5). The first build_annual_rows pass
        # computed CFADS with UNLEVERED tax (interest_expense=0) — correct for the DSCR
        # sizing and the project-IRR-vs-after-tax-WACC path (there the shield is captured in
        # the after-tax cost of debt inside the WACC, so adding it to CFADS would double
        # count). But the levered EQUITY waterfall must bear LEVERED tax: the SPV legally
        # deducts its actual debt interest and that tax saving accrues to equity. The prior
        # single-pass charged equity unlevered tax, understating equity cash and equity IRR,
        # and left tax.interest_deductibility decorative (toggling it changed nothing).
        # Rebuild an EQUITY-FACING cashflow with the real per-operating-year interest (the
        # enriched rows already carry interest_usd with the bridge folded into year 1; the
        # tax engine deducts it in LKR). Unlevered annual_rows_enriched stays the basis for
        # the project KPIs/DSCR/LLCR/PLCR above — the shield is confined to the equity path.
        # Capitalized debt IDC in the depreciable tax base (#36/#75) is the second
        # equity-only adjustment: IDC is interest incurred during construction — a
        # debt-financing artifact — so the extra depreciation it generates is a levered
        # (equity) shield, applied here alongside the interest shield, never to the
        # unlevered project/DSCR pass. Default-off -> byte-identical. total_idc is the
        # USD IDC; build_annual_rows translates it at year-0 FX (same basis as USD capex).
        tax_block = cfg.get("tax", {}) or {}
        interest_deductible = bool(tax_block.get("interest_deductibility", True))
        capitalize_idc = bool(
            tax_block.get("capitalize_idc_in_depreciable_base", False)
        )
        idc_usd = float(debt_result.get("total_idc") or 0.0) if capitalize_idc else None
        if interest_deductible or capitalize_idc:
            op_interest_lkr = (
                [
                    float(row.get("interest_usd") or 0.0)
                    * float(row.get("fx_rate") or 0.0)
                    for row in annual_rows_enriched
                ]
                if interest_deductible
                else None
            )
            equity_rows = _enrich_annual_rows_with_debt(
                build_annual_rows(
                    cfg,
                    interest_expense_series=op_interest_lkr,
                    extra_depreciable_usd=idc_usd,
                    # The equity waterfall bears the same senior fee (#737) the
                    # project pass charged; None when no fees are configured.
                    senior_fee_lkr_series=senior_fee_lkr_series,
                ),
                debt_result,
            )
        else:
            equity_rows = annual_rows_enriched

        # Lazy import: breaks the analytics<->finance module-load cycle. This
        # module is pulled in by the analytics package init, and the hydra module
        # imports back into analytics, so a cold finance-side import would hit a
        # partially-initialized module (ImportError). Imported at its one call site.
        from finance.equity_distribution_v14_hydra import (
            calculate_equity_distribution_from_pipeline,
        )

        equity_distribution = calculate_equity_distribution_from_pipeline(
            config=equity_cfg,
            annual_rows=equity_rows,
            debt_result=debt_result,
            kpis=kpis,
        )
        equity_performance = _update_kpis_with_equity_distribution(
            kpis, equity_distribution
        )
        metrics.equity_distribution_time_sec = time.time() - phase_start
        metrics.kpis_count = len(kpis)
        logger.info(
            "Equity distribution %s in %.3f sec",
            equity_distribution.get("status", "unknown"),
            metrics.equity_distribution_time_sec,
        )

        project_npv = float(kpis.get("project_npv", 0.0))
        project_irr = float(kpis.get("project_irr", 0.0))
        dscr_series = list(debt_result.get("dscr_series") or [])
        min_dscr = float(debt_result.get("min_dscr", 0.0))
        max_debt_usd = float(kpis.get("max_debt_usd", 0.0))

        scenario_name = str(cfg.get("scenario_name", Path(config_path_label).stem))

        debt_profile = _build_tranche_debt_profile(cfg, debt_result)
        debt_covenants = _build_debt_covenant_snapshot(cfg, debt_result)

        scenario_result = ScenarioResult(
            scenario_name=scenario_name,
            config_path=config_path_label,
            project_npv=project_npv,
            project_irr=project_irr,
            dscr_series=dscr_series,
            min_dscr=min_dscr,
            max_debt_usd=max_debt_usd,
            wacc=wacc_contract,
            discount_rate_used=project_discount,
            wacc_label=wacc_label_val,
            wacc_is_real=wacc_drives,
            validation_mode=mode,
            config=cfg,
            annual_rows=annual_rows_enriched,
            debt_result=debt_result,
            kpis=kpis,
            debt_profile=debt_profile,
            debt_covenants=debt_covenants,
            equity_performance=equity_performance,
            metadata={"equity_distribution_status": equity_distribution.get("status")},
        )

        # Populate the FX structured block / curve / risk profile on the ScenarioResult. The
        # integrator was previously never called from the live pipeline, so fx_block /
        # fx_curve / fx_risk_profile stayed None in production despite the contract fields and
        # docstrings claiming otherwise. It is additive (reporting only — no effect on
        # IRR/NPV/DSCR) and non-fatal: a malformed fx config must not fail the financed run.
        _fx_t0 = time.perf_counter()
        # #736: on failure the FX block is a log-only warning today, so a stale/fallback FX
        # assumption is invisible to a report reader. Capture the failure into the result (below)
        # so the report/user layer can surface it explicitly, not just the logs.
        fx_integration_warning: Optional[str] = None
        # #785: SILENT fallbacks (integration succeeds on stale/default FX data) are
        # collected here by the fx builders — distinct from the exception path below.
        fx_degraded_reasons: list[str] = []
        try:
            from analytics.fx.fx_integration import integrate_fx_into_scenario_result

            scenario_result = integrate_fx_into_scenario_result(
                scenario_result=scenario_result,
                config=cfg,
                debt_result=debt_result,
                annual_rows=annual_rows_enriched,
                degraded_out=fx_degraded_reasons,
            )
            metrics.fx_integration_succeeded = True
        except Exception as exc:  # pragma: no cover - defensive (reporting-only slice)
            logger.warning("FX integration failed (non-fatal, reporting-only): %s", exc)
            metrics.fx_integration_succeeded = False
            fx_integration_warning = (
                "FX integration failed: the report's FX curve and risk profile are "
                "unavailable, so any FX-sensitive figures rely on the scenario's static FX "
                f"assumption rather than a calibrated path. Cause: {exc}"
            )
        metrics.fx_integration_attempted = True
        metrics.fx_integration_time_sec = time.perf_counter() - _fx_t0

        logger.info(
            "ScenarioResult assembled: project_irr=%.2f%%, min_dscr=%.2f, project_npv=%.0f",
            project_irr * 100,
            min_dscr,
            project_npv,
        )

        metrics.total_runtime_sec = time.time() - start_time

        result: dict[str, Any] = {
            "status": "success",
            "config_path": config_path_label,
            "validation_mode": mode,
            "scenario_result": asdict(scenario_result),
            "kpis": kpis,
            "annual_rows": annual_rows_enriched,
            "debt_result": debt_result,
            "equity_distribution": equity_distribution,
            "metrics": asdict(metrics) if enable_monitoring else {},
            # #736: FX-integration status, surfaced unconditionally (not gated on monitoring) so
            # the report layer can render an explicit warning when it failed. ``warning`` is None
            # on success -> the report banner is omitted (render-when-present, byte-identical).
            # #785: ``degraded``/``degraded_reasons`` disclose SILENT fallbacks — the
            # integration SUCCEEDED but one or more FX surfaces were built from
            # stale/default substitutions (empty on a clean run; additive keys).
            "fx_integration": {
                "attempted": metrics.fx_integration_attempted,
                "succeeded": metrics.fx_integration_succeeded,
                "warning": fx_integration_warning,
                "degraded": bool(fx_degraded_reasons),
                "degraded_reasons": list(fx_degraded_reasons),
            },
            "run_manifest": run_manifest,
        }

        logger.info(
            "Pipeline complete in %.3f sec: project_irr=%.2f%%, min_dscr=%.2f",
            metrics.total_runtime_sec,
            project_irr * 100,
            min_dscr,
        )
        return result

    except Exception as exc:
        metrics.total_runtime_sec = time.time() - start_time
        logger.error(
            "Pipeline failed in %.3f sec: %s (%s)",
            metrics.total_runtime_sec,
            type(exc).__name__,
            str(exc),
        )

        if isinstance(exc, (PipelineConfigError, PipelineValidationError)):
            raise

        raise PipelineValidationError(f"Pipeline execution failed: {exc}") from exc


run_v14_pipeline = run_v14_pipeline_enhanced

__all__ = [
    "run_v14_pipeline_enhanced",
    "run_v14_pipeline",
    "PipelineMetrics",
    "PipelineValidationError",
    "PipelineConfigError",
]
