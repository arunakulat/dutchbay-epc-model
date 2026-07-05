"""FastAPI router for the full v14 finance pipeline.

A thin adapter (like ``api.sensitivity_api``): it accepts a scenario — either a path
to a committed YAML or a full inline config (the YAML fields as JSON), with optional
dotted-key overrides — runs the canonical ``run_v14_pipeline`` engine, and serialises
the headline outputs a lender/customer report needs: financial KPIs, the sculpted
(dual-DSCR) debt schedule + tranche breakdown, and the bankable AEP (P50/P75/P90).

No modelling logic lives here; everything is delegated to analytics/finance.
"""

from __future__ import annotations

import copy
import json
import logging
import math
from typing import Any, Dict, List, Literal, Mapping, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from analytics.aep_provenance import (
    AepProvenanceError,
    enforce_aep_provenance,
    register_scenario_approved_sources,
)
from analytics.aep_reconciliation import (
    AepReconciliationError,
    reconcile_capacity_factor_with_bankable_aep,
)
from analytics.conditions_precedent import validate_conditions_precedent
from analytics.cost.benchmark import capex_benchmark
from analytics.cost.cost_basis import resolve_cost_basis_year
from analytics.cost.estimate_class import resolve_accuracy_band
from analytics.development_readiness import validate_development_readiness
from analytics.evidence_register import validate_evidence_register
from analytics.feasibility_sections import validate_feasibility_sections
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import build_run_manifest
from analytics.scenario_loader import _assert_fx_spot_consistency, load_scenario_config
from analytics.schema_guard import ConfigValidationError
from api.path_safety import UnsafePathError, confined_path
from finance.debt_v14 import _extract_capex_usd

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class RunPipelineRequest(BaseModel):
    """Run the full finance pipeline for a scenario.

    Provide EXACTLY ONE of ``config_path`` (a committed scenario YAML) or ``config``
    (a full inline scenario, e.g. assembled by a customer-facing form). ``overrides``
    are dotted-key edits applied on top of either, e.g.
    ``{"capex.usd_total": 207500000, "fx.start_lkr_per_usd": 333.79}``.
    """

    config_path: Optional[str] = Field(
        default=None, description="Path to a committed scenario YAML to run."
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None, description="Full inline scenario config (YAML fields as JSON)."
    )
    overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dotted-key overrides applied on top, e.g. {'capex.usd_total': 2.075e8}.",
    )
    validation_mode: Literal["strict", "off"] = Field(
        default="strict",
        description="schema_guard validation mode: 'strict' (enforce) or 'off' (skip). "
        "Constrained to these two — run_v14_pipeline accepts no others; an unsupported "
        "value is rejected at the API boundary with a 422 rather than deep in the engine.",
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "RunPipelineRequest":
        if bool(self.config_path) == bool(self.config):
            raise ValueError("Provide exactly one of 'config_path' or 'config'.")
        return self


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class AepBlock(BaseModel):
    net_p50_gwh: Optional[float] = None
    net_p75_gwh: Optional[float] = None
    net_p90_gwh: Optional[float] = None
    gross_gwh: Optional[float] = None
    capacity_factor: Optional[float] = None
    source_id: Optional[str] = None


class KpiBlock(BaseModel):
    project_irr: Optional[float] = None
    equity_irr: Optional[float] = None
    project_npv_usd: Optional[float] = None
    equity_npv_usd: Optional[float] = None
    min_dscr: Optional[float] = None
    avg_dscr: Optional[float] = None
    llcr: Optional[float] = None
    plcr: Optional[float] = None
    discount_rate_used: Optional[float] = None
    wacc_label: Optional[str] = None
    equity_multiple: Optional[float] = None
    equity_payback_years: Optional[float] = None


class TrancheBlock(BaseModel):
    principal_usd: float
    idc_usd: float


class DebtScheduleRow(BaseModel):
    year: int
    dscr: Optional[float] = None
    debt_outstanding_usd: Optional[float] = None
    debt_service_usd: Optional[float] = None


class DebtBlock(BaseModel):
    debt_total_usd: Optional[float] = None
    total_idc_usd: Optional[float] = None
    gearing: Optional[float] = None
    binding_constraint: Optional[str] = None
    binding_production_case: Optional[str] = (
        None  # "P50" | "P90" (downside-binding sizing)
    )
    # P90 (downside) sizing detail — populated only when a scenario opts into
    # Financing_Terms.bind_downside; absent (None) for the default P50-only solve, so
    # the lender-pack rows render only for a downside-binding scenario. Pure
    # serialisation from debt_result['dual_dscr'] (no finance logic here).
    solved_gearing_p50: Optional[float] = None
    solved_gearing_p90: Optional[float] = None
    target_dscr_p90: Optional[float] = None
    downside_ratio: Optional[float] = None
    downside_source: Optional[str] = None
    sizing_mode: Optional[str] = None
    tenor_years: Optional[int] = None
    construction_years: Optional[int] = None
    avg_debt_rate_pct: Optional[float] = None
    min_dscr: Optional[float] = None
    avg_dscr: Optional[float] = None
    tranches: Dict[str, TrancheBlock] = Field(default_factory=dict)
    balloon_pct: Optional[float] = None
    balloon_remaining_usd: Optional[float] = None
    balloon_covenant_breach: Optional[bool] = None
    schedule: List[DebtScheduleRow] = Field(default_factory=list)


class CostBlock(BaseModel):
    capex_total_usd: Optional[float] = None
    capex_per_kw_usd: Optional[float] = None
    irena_benchmark_per_kw: Optional[float] = None
    ratio_to_benchmark: Optional[float] = None
    within_band: Optional[bool] = None
    note: Optional[str] = None
    estimate_class: Optional[int] = None  # AACE class 5..1 (estimate maturity)
    accuracy_low_pct: Optional[float] = None  # AACE expected-accuracy band (low side)
    accuracy_high_pct: Optional[float] = None  # AACE expected-accuracy band (high side)


class ManifestBlock(BaseModel):
    """Auditable reproducibility stamp: ties the output to inputs + engine + commit."""

    config_sha256: str
    engine_version: str
    git_sha: str
    generated_at: str
    seed: Optional[int] = None
    validation_mode: Optional[str] = None
    manifest_schema_version: str


class FundingBlock(BaseModel):
    """Sources-and-Uses at financial close (+ a DSRA funded at close when opted in)."""

    fund_at_close: Optional[bool] = None
    dsra_target_months: Optional[float] = None
    initial_dsra_usd: Optional[float] = None
    capex_usd: Optional[float] = None
    # of-which disclosure (#738): import duties + unrecoverable VAT already
    # INSIDE capex_usd (a breakdown line, not a uses_total addend).
    import_levies_usd: Optional[float] = None
    idc_usd: Optional[float] = None
    senior_debt_usd: Optional[float] = None
    equity_usd: Optional[float] = None
    uses_total_usd: Optional[float] = None
    sources_total_usd: Optional[float] = None
    balanced: Optional[bool] = None


class RunPipelineResponse(BaseModel):
    scenario_name: str
    config_path: Optional[str] = None
    validation_mode: str
    cost_basis_year: int  # USD vintage the CAPEX/OPEX figures are expressed in
    kpis: KpiBlock
    aep: AepBlock
    debt: DebtBlock
    cost: CostBlock
    funding: FundingBlock  # sources-and-uses + DSRA-at-close
    manifest: ManifestBlock  # reproducibility stamp over the RESOLVED config


# ---------------------------------------------------------------------------
# Helpers (pure serialisation — no modelling)
# ---------------------------------------------------------------------------
def _apply_overrides(
    cfg: Dict[str, Any], overrides: Mapping[str, Any]
) -> Dict[str, Any]:
    out = copy.deepcopy(cfg)
    for dotted, value in overrides.items():
        parts = str(dotted).split(".")
        node: Dict[str, Any] = out
        for part in parts[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[parts[-1]] = value
    return out


def _as_map(value: Any) -> Dict[str, Any]:
    """Narrow an arbitrary value to a dict (empty if it isn't a mapping)."""
    return dict(value) if isinstance(value, Mapping) else {}


def _avg_finite_dscr(debt: Mapping[str, Any]) -> Optional[float]:
    """Mean of the finite DSCR values, or None. The debt_result has no 'dscr_mean' key, so
    DebtBlock.avg_dscr was structurally always null; derive it from the raw (full-timeline)
    DSCR series, dropping None/non-finite construction-period sentinels."""
    series = debt.get("raw_dscr_series") or debt.get("dscr_series") or []
    vals = [
        float(x)
        for x in series
        if isinstance(x, (int, float))
        and not isinstance(x, bool)
        and math.isfinite(float(x))
    ]
    return sum(vals) / len(vals) if vals else None


# The LKR/USD spot is pinned in three places (the cashflow reads fx.start_lkr_per_usd, the
# FX reporting block reads fx.rates.lkr_per_usd first); _assert_fx_spot_consistency requires
# them equal. A client tuning the documented fx.start_lkr_per_usd override would otherwise
# leave the other two stale and trip a 422.
_FX_SPOT_OVERRIDE_KEYS = (
    "fx.start_lkr_per_usd",
    "fx.rates.lkr_per_usd",
    "fx.source.pinned_rate",
)


def _sync_fx_spot_override(
    cfg: Dict[str, Any], overrides: Mapping[str, Any]
) -> Dict[str, Any]:
    """Fan a single-lever FX-spot override out to all three pinned spot keys.

    If the client overrode any of fx.start_lkr_per_usd / fx.rates.lkr_per_usd /
    fx.source.pinned_rate, set ALL three to the new rate so the post-override config stays
    self-consistent (else the documented single-key FX-rate override would fail the spot
    cross-assert). No-op when no FX-spot key was overridden.
    """
    touched = [k for k in _FX_SPOT_OVERRIDE_KEYS if k in overrides]
    if not touched:
        return cfg
    # Only fan out when the touched spot keys AGREE (or just one was set). If a client
    # overrides two/three spot keys to DIFFERENT values, do NOT silently pick a winner —
    # leave them as-authored so the downstream _assert_fx_spot_consistency rejects the
    # contradiction with a clear 422 (its whole purpose; round-4 fix).
    try:
        distinct = {float(overrides[k]) for k in touched}
    except (TypeError, ValueError):
        return cfg  # non-numeric override -> let the engine/validator handle it
    if len(distinct) > 1:
        return cfg
    # Prefer the canonical start key; otherwise the first key the client actually set.
    new_rate = overrides.get("fx.start_lkr_per_usd", overrides[touched[0]])
    fx = cfg.get("fx")
    if not isinstance(fx, dict):
        return cfg
    fx["start_lkr_per_usd"] = new_rate
    rates = fx.setdefault("rates", {})
    if isinstance(rates, dict):
        rates["lkr_per_usd"] = new_rate
    source = fx.setdefault("source", {})
    if isinstance(source, dict):
        source["pinned_rate"] = new_rate
    return cfg


def _f(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _at(seq: Any, index: int) -> Optional[float]:
    if isinstance(seq, (list, tuple)) and 0 <= index < len(seq):
        return _f(seq[index])
    return None


def _extract_aep(cfg: Mapping[str, Any]) -> AepBlock:
    resource = _as_map(cfg.get("resource"))
    wind = _as_map(resource.get("wind"))
    summary: Dict[str, Any] = {}
    path = resource.get("aep_summary_path")
    if isinstance(path, str) and path.strip():
        # Confine a caller-supplied summary path to the allowed roots; an
        # out-of-bounds path (traversal/absolute) reads nothing rather than
        # leaking an arbitrary file.
        try:
            safe = confined_path(path, must_exist=True)
            summary = _as_map(json.loads(safe.read_text()))
        except (UnsafePathError, OSError, ValueError):
            summary = {}
    exc = _as_map(summary.get("exceedance"))
    return AepBlock(
        net_p50_gwh=_f(summary.get("net_site_aep_gwh") or wind.get("aep_gwh")),
        net_p75_gwh=_f(exc.get("net_aep_p75_gwh")),
        net_p90_gwh=_f(
            exc.get("net_aep_p90_1yr_gwh") or exc.get("net_aep_p90_life_gwh")
        ),
        gross_gwh=_f(summary.get("gross_aep_gwh")),
        capacity_factor=_f(
            summary.get("capacity_factor") or wind.get("capacity_factor")
        ),
        source_id=(summary.get("source_id") or wind.get("source_id")),
    )


def _extract_debt(debt: Mapping[str, Any]) -> DebtBlock:
    dual = _as_map(debt.get("dual_dscr"))
    principals = _as_map(debt.get("principal_by_tranche"))
    idcs = _as_map(debt.get("idc_by_tranche"))
    tranches = {
        name: TrancheBlock(
            principal_usd=_f(principals.get(name)) or 0.0,
            idc_usd=_f(idcs.get(name)) or 0.0,
        )
        for name in principals
    }

    # Use the FULL-TIMELINE raw_dscr_series (length matches debt_outstanding /
    # debt_service_total, with None in construction periods), NOT the compacted public
    # dscr_series (operating years only) — zipping the compacted series row-by-row against
    # the full-timeline outstanding/service misaligned each row's DSCR by the construction
    # offset (round-4 fix). Falls back to the compacted series only if raw is absent.
    dscr_series = (
        debt.get("raw_dscr_series")
        or debt.get("dscr_series")
        or list((debt.get("dscr_by_year") or {}).values())
    )
    outstanding = debt.get("debt_outstanding") or []
    service = debt.get("debt_service_total") or debt.get("total_service") or []
    n_rows = max(len(dscr_series), len(outstanding), len(service))
    schedule = [
        DebtScheduleRow(
            year=i + 1,
            dscr=_at(dscr_series, i),
            debt_outstanding_usd=_at(outstanding, i),
            debt_service_usd=_at(service, i),
        )
        for i in range(n_rows)
    ]

    avg_rate = _f(debt.get("avg_debt_rate"))
    return DebtBlock(
        debt_total_usd=_f(debt.get("debt_total")),
        total_idc_usd=_f(debt.get("total_idc")),
        gearing=_f(dual.get("solved_gearing")),
        binding_constraint=dual.get("binding_constraint"),
        binding_production_case=dual.get("binding_production_case"),
        solved_gearing_p50=_f(dual.get("solved_gearing_p50")),
        solved_gearing_p90=_f(dual.get("solved_gearing_p90")),
        target_dscr_p90=_f(dual.get("target_dscr_p90")),
        downside_ratio=_f(dual.get("downside_ratio")),
        downside_source=dual.get("downside_source"),
        sizing_mode=dual.get("sizing_mode"),
        tenor_years=(
            int(debt["tenor_years"]) if debt.get("tenor_years") is not None else None
        ),
        construction_years=(
            int(debt["construction_years"])
            if debt.get("construction_years") is not None
            else None
        ),
        avg_debt_rate_pct=None if avg_rate is None else round(avg_rate * 100.0, 4),
        min_dscr=_f(debt.get("min_dscr")),
        avg_dscr=_avg_finite_dscr(debt),
        tranches=tranches,
        balloon_pct=_f(debt.get("balloon_pct")),
        balloon_remaining_usd=_f(debt.get("balloon_remaining")),
        balloon_covenant_breach=(
            bool(debt["balloon_covenant_breach"])
            if debt.get("balloon_covenant_breach") is not None
            else None
        ),
        schedule=schedule,
    )


def _extract_funding(debt: Mapping[str, Any]) -> FundingBlock:
    """Sources-and-Uses + DSRA-at-close from the debt result (pure serialisation)."""
    f = _as_map(debt.get("funding"))
    su = _as_map(f.get("sources_and_uses"))
    uses = _as_map(su.get("uses"))
    sources = _as_map(su.get("sources"))
    return FundingBlock(
        fund_at_close=bool(f.get("fund_at_close")) if f else None,
        dsra_target_months=_f(f.get("dsra_target_months")),
        initial_dsra_usd=_f(f.get("initial_dsra_usd")),
        capex_usd=_f(uses.get("capex_usd")),
        import_levies_usd=_f(uses.get("import_levies_usd")),
        idc_usd=_f(uses.get("idc_usd")),
        senior_debt_usd=_f(sources.get("senior_debt_usd")),
        equity_usd=_f(sources.get("equity_usd")),
        uses_total_usd=_f(su.get("uses_total_usd")),
        sources_total_usd=_f(su.get("sources_total_usd")),
        balanced=bool(su.get("balanced")) if su else None,
    )


def _capacity_mw(cfg: Mapping[str, Any]) -> float:
    project = _as_map(cfg.get("project"))
    if isinstance(project.get("capacity_mw"), (int, float)):
        return float(project["capacity_mw"])
    turbines = _as_map(_as_map(cfg.get("resource")).get("turbines"))
    total = turbines.get("total_capacity_mw")
    if isinstance(total, (int, float)):
        return float(total)
    count, rated = turbines.get("count"), turbines.get("rated_power_mw")
    if isinstance(count, (int, float)) and isinstance(rated, (int, float)):
        return float(count) * float(rated)
    return 0.0


def _extract_cost(cfg: Mapping[str, Any]) -> CostBlock:
    """CAPEX total + the IRENA $/kW sanity-check banner (pure serialisation)."""
    try:
        capex = _extract_capex_usd(dict(cfg))
    except (ValueError, KeyError, TypeError):
        return CostBlock()
    cap_mw = _capacity_mw(cfg)
    if cap_mw <= 0:
        return CostBlock(capex_total_usd=capex)
    b = capex_benchmark(capex, cap_mw)
    ec: Optional[int] = None
    lo: Optional[float] = None
    hi: Optional[float] = None
    try:
        band = resolve_accuracy_band(cfg)
        ec, lo, hi = band.estimate_class, band.low_pct, band.high_pct
    except Exception:
        pass
    return CostBlock(
        capex_total_usd=capex,
        capex_per_kw_usd=b["capex_per_kw_usd"],
        irena_benchmark_per_kw=b["irena_benchmark_per_kw"],
        ratio_to_benchmark=b["ratio_to_benchmark"],
        within_band=b["within_band"],
        note=b["note"],
        estimate_class=ec,
        accuracy_low_pct=lo,
        accuracy_high_pct=hi,
    )


def _extract_kpis(kpis: Mapping[str, Any]) -> KpiBlock:
    return KpiBlock(
        project_irr=_f(kpis.get("project_irr")),
        equity_irr=_f(kpis.get("equity_irr")),
        project_npv_usd=_f(kpis.get("project_npv")),
        equity_npv_usd=_f(kpis.get("equity_npv")),
        min_dscr=_f(kpis.get("min_dscr")),
        avg_dscr=_f(kpis.get("avg_dscr")),
        llcr=_f(kpis.get("llcr")),
        plcr=_f(kpis.get("plcr")),
        discount_rate_used=_f(kpis.get("discount_rate_used")),
        wacc_label=kpis.get("wacc_label"),
        equity_multiple=_f(kpis.get("equity_multiple") or kpis.get("equity_moic")),
        equity_payback_years=_f(kpis.get("equity_payback_period_years")),
    )


class FinanceReportBlocks(BaseModel):
    """The serialised finance blocks a lender report renders (RPT-1).

    A public seam over the private ``_extract_*`` serialisers so the report
    builder (``app.reports``) reuses ONE serialisation source rather than
    re-deriving these shapes — the report and the ``/run-pipeline`` API can never
    drift apart (CCCDIR).
    """

    kpis: KpiBlock
    aep: AepBlock
    debt: DebtBlock
    cost: CostBlock
    funding: FundingBlock


def extract_finance_report_blocks(
    scenario_config: Mapping[str, Any],
    debt_result: Mapping[str, Any],
    kpis: Mapping[str, Any],
) -> FinanceReportBlocks:
    """Serialise the lender-report finance blocks from a finance run (RPT-1).

    Reuses the canonical ``_extract_*`` serialisers (the same ones the
    ``/run-pipeline`` response is built from) so the generated report and the API
    surface never diverge.

    Args:
        scenario_config: The resolved scenario config (drives the AEP + CAPEX blocks).
        debt_result: The pipeline's ``debt_result`` mapping (drives the debt schedule
            / DSCR profile and the sources-and-uses).
        kpis: The pipeline's ``kpis`` mapping (drives the executive KPI callout).

    Returns:
        The five serialised blocks, ready for the report renderer.
    """
    return FinanceReportBlocks(
        kpis=_extract_kpis(kpis),
        aep=_extract_aep(scenario_config),
        debt=_extract_debt(debt_result),
        cost=_extract_cost(scenario_config),
        funding=_extract_funding(debt_result),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/run-pipeline", response_model=RunPipelineResponse)
def run_pipeline(payload: RunPipelineRequest) -> RunPipelineResponse:
    """Run the full v14 finance pipeline and return KPIs + sculpted debt + AEP."""
    if payload.config_path:
        try:
            safe_path = confined_path(payload.config_path, must_exist=True)
            cfg: Dict[str, Any] = dict(load_scenario_config(str(safe_path)))
        except (UnsafePathError, ValueError) as exc:
            # Authored, actionable path/validation messages — safe to surface.
            raise HTTPException(
                status_code=400, detail=f"Could not load config_path: {exc}"
            )
        except OSError as exc:
            # A filesystem error can embed absolute internal paths; log it
            # server-side and return only the class + a generic message
            # (mirrors app/jobs/runner.py).
            logger.exception("run-pipeline: failed to load config_path")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{type(exc).__name__}: could not load config_path; "
                    "see the server logs."
                ),
            )
    else:
        cfg = dict(payload.config or {})

    if payload.overrides:
        cfg = _apply_overrides(cfg, payload.overrides)
        cfg = _sync_fx_spot_override(cfg, payload.overrides)

    # An inline payload.config and any post-load overrides reach the engine as a dict,
    # which bypasses the load-time reconciliation in load_scenario_config. Re-check the
    # final authored config here so a stale/injected capacity_mw or capacity_factor that
    # disagrees with a declared bankable AEP fails loud over the API too (a client
    # override is a stale-value injection, NOT a deliberate sensitivity perturbation).
    try:
        reconcile_capacity_factor_with_bankable_aep(
            cfg, payload.config_path or "<inline>"
        )
        register_scenario_approved_sources(cfg, payload.config_path or "<inline>")
        enforce_aep_provenance(cfg, payload.config_path or "<inline>")
        validate_evidence_register(cfg, payload.config_path or "<inline>")
        validate_development_readiness(cfg, payload.config_path or "<inline>")
        validate_conditions_precedent(cfg, payload.config_path or "<inline>")
        validate_feasibility_sections(cfg, payload.config_path or "<inline>")
        # Same rationale for the FX spot keys: an inline/overridden authored config bypasses
        # the load-time cross-assert, so a divergent fx.rates/start/pinned would yield a
        # self-inconsistent lender pack (#236 class). A client authoring/overriding the
        # config is NOT a deliberate MC perturbation, so enforce it here.
        _assert_fx_spot_consistency(cfg, payload.config_path or "<inline>")
        result = run_v14_pipeline(config=cfg, validation_mode=payload.validation_mode)
    except (
        ConfigValidationError,
        AepReconciliationError,
        AepProvenanceError,
        ValueError,
    ) as exc:
        # Authored, actionable validation/reconciliation messages — safe to surface.
        raise HTTPException(status_code=422, detail=f"Pipeline run failed: {exc}")
    except Exception as exc:
        # Unexpected engine error: the raw message can embed internal paths/config,
        # so log the full trace server-side and return only the class + a generic
        # message (mirrors app/jobs/runner.py).
        logger.exception("run-pipeline: pipeline execution failed")
        raise HTTPException(
            status_code=422,
            detail=f"{type(exc).__name__}: pipeline run failed; see the server logs.",
        )

    kpis = result.get("kpis") or {}
    debt = result.get("debt_result") or {}
    # Engine-stamped manifest preferred (#577): run_v14_pipeline stamps
    # result["run_manifest"] from the RESOLVED config it actually evaluated, so the
    # response binds to the engine's own resolution. Rebuilding from this boundary's
    # cfg is retained only as a fallback for a result without one (e.g. a patched
    # engine in tests).
    manifest_raw = result.get("run_manifest")
    manifest_dict: Dict[str, Any] = (
        dict(manifest_raw)
        if isinstance(manifest_raw, Mapping)
        else build_run_manifest(cfg, validation_mode=payload.validation_mode).as_dict()
    )
    return RunPipelineResponse(
        scenario_name=str(kpis.get("scenario_name") or cfg.get("name") or "<inline>"),
        config_path=payload.config_path,
        validation_mode=payload.validation_mode,
        cost_basis_year=resolve_cost_basis_year(cfg),
        kpis=_extract_kpis(kpis),
        aep=_extract_aep(cfg),
        debt=_extract_debt(debt),
        cost=_extract_cost(cfg),
        funding=_extract_funding(debt),
        manifest=ManifestBlock(**manifest_dict),
    )
