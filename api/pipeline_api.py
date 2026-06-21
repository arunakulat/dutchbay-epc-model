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
import os
from typing import Any, Dict, List, Mapping, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from analytics.cost.benchmark import capex_benchmark
from analytics.cost.cost_basis import resolve_cost_basis_year
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import build_run_manifest
from analytics.scenario_loader import load_scenario_config
from finance.debt_v14 import _extract_capex_usd

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
    validation_mode: str = Field(
        default="strict", description="schema_guard validation mode (strict|lenient)."
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


class ManifestBlock(BaseModel):
    """Auditable reproducibility stamp: ties the output to inputs + engine + commit."""

    config_sha256: str
    engine_version: str
    git_sha: str
    generated_at: str
    seed: Optional[int] = None
    validation_mode: Optional[str] = None
    manifest_schema_version: str


class RunPipelineResponse(BaseModel):
    scenario_name: str
    config_path: Optional[str] = None
    validation_mode: str
    cost_basis_year: int  # USD vintage the CAPEX/OPEX figures are expressed in
    kpis: KpiBlock
    aep: AepBlock
    debt: DebtBlock
    cost: CostBlock
    manifest: ManifestBlock  # reproducibility stamp over the RESOLVED config


# ---------------------------------------------------------------------------
# Helpers (pure serialisation — no modelling)
# ---------------------------------------------------------------------------
def _apply_overrides(cfg: Dict[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
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
    if isinstance(path, str) and os.path.exists(path):
        try:
            summary = _as_map(json.loads(open(path).read()))
        except (OSError, ValueError):
            summary = {}
    exc = _as_map(summary.get("exceedance"))
    return AepBlock(
        net_p50_gwh=_f(summary.get("net_site_aep_gwh") or wind.get("aep_gwh")),
        net_p75_gwh=_f(exc.get("net_aep_p75_gwh")),
        net_p90_gwh=_f(exc.get("net_aep_p90_1yr_gwh") or exc.get("net_aep_p90_life_gwh")),
        gross_gwh=_f(summary.get("gross_aep_gwh")),
        capacity_factor=_f(summary.get("capacity_factor") or wind.get("capacity_factor")),
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

    dscr_series = debt.get("dscr_series") or list((debt.get("dscr_by_year") or {}).values())
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
        sizing_mode=dual.get("sizing_mode"),
        tenor_years=int(debt["tenor_years"]) if debt.get("tenor_years") is not None else None,
        construction_years=(
            int(debt["construction_years"]) if debt.get("construction_years") is not None else None
        ),
        avg_debt_rate_pct=None if avg_rate is None else round(avg_rate * 100.0, 4),
        min_dscr=_f(debt.get("min_dscr")),
        avg_dscr=_f(debt.get("dscr_mean")),
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
    return CostBlock(
        capex_total_usd=capex,
        capex_per_kw_usd=b["capex_per_kw_usd"],
        irena_benchmark_per_kw=b["irena_benchmark_per_kw"],
        ratio_to_benchmark=b["ratio_to_benchmark"],
        within_band=b["within_band"],
        note=b["note"],
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


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/run-pipeline", response_model=RunPipelineResponse)
def run_pipeline(payload: RunPipelineRequest) -> RunPipelineResponse:
    """Run the full v14 finance pipeline and return KPIs + sculpted debt + AEP."""
    if payload.config_path:
        try:
            cfg: Dict[str, Any] = dict(load_scenario_config(payload.config_path))
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Could not load config_path: {exc}")
    else:
        cfg = dict(payload.config or {})

    if payload.overrides:
        cfg = _apply_overrides(cfg, payload.overrides)

    try:
        result = run_v14_pipeline(config=cfg, validation_mode=payload.validation_mode)
    except Exception as exc:  # config/validation/engine errors -> 422, not 500
        raise HTTPException(status_code=422, detail=f"Pipeline run failed: {exc}")

    kpis = result.get("kpis") or {}
    debt = result.get("debt_result") or {}
    manifest = build_run_manifest(cfg, validation_mode=payload.validation_mode)
    return RunPipelineResponse(
        scenario_name=str(kpis.get("scenario_name") or cfg.get("name") or "<inline>"),
        config_path=payload.config_path,
        validation_mode=payload.validation_mode,
        cost_basis_year=resolve_cost_basis_year(cfg),
        kpis=_extract_kpis(kpis),
        aep=_extract_aep(cfg),
        debt=_extract_debt(debt),
        cost=_extract_cost(cfg),
        manifest=ManifestBlock(**manifest.as_dict()),
    )
