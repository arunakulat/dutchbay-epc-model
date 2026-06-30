# analytics/casper/casper_payload.py

from __future__ import annotations

from typing import Any, Mapping, Sequence

from analytics.contracts_v14 import (
    CasperResult,
    MonteCarloResult,
    MultiTechGenerationResult,
    MultiTechWBS,
    ScenarioResult,
    SensitivitySuite,
    TechnologyBreakdown,
)

# Frozen JSON contract version for CASPER payloads.
# If this ever changes, it MUST be treated as a breaking change and guarded
# by tests + docs/api_contract_casper_result_v*.md.
CASPER_CONTRACT_VERSION = "casper_result_v1"


def build_casper_payload(
    *,
    scenario: ScenarioResult | str,
    monte_carlo: MonteCarloResult | None = None,
    sensitivity: SensitivitySuite | None = None,
    generation: MultiTechGenerationResult | None = None,
    technology_breakdown: Sequence[TechnologyBreakdown] | None = None,
    multi_tech_wbs: MultiTechWBS | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a CASPER/GWTF-compliant payload for dashboards and lenders.

    CESSPIT guardrails:
    - Contract-explicit: uses contracts_v14 types (ScenarioResult, CasperResult, …)
      as the only inputs/outputs at this layer.
    - Evidence-based: numbers are derived from engine outputs; no hidden
      recomputation here.
    - Scenario-stable: same config + same upstream results => same payload.

    Parameters
    ----------
    scenario:
        ScenarioResult from run_full_pipeline_v14 (canonical v14 surface).
    monte_carlo:
        Optional MonteCarloResult for this scenario (v14 engine).
    sensitivity:
        Optional SensitivitySuite (tornado) for this scenario.
    generation:
        Optional MultiTechGenerationResult (wind/solar/BESS aggregation).
    technology_breakdown:
        Optional per-technology breakdown for CASPER lenses
        (e.g. wind vs BESS share of AEP/CFADS/CAPEX).
    metadata:
        Free-form small JSON-safe fields for UIs / diagnostics.
        Must not contain large blobs or raw engine tables.

        Convention for tail-risk:
        - metadata["tail_risk"]         = full underlying tables
        - metadata["tail_risk_summary"] = snapshots keyed by metric name
          (this module surfaces that snapshot as top-level `tail_risk`).

    Returns
    -------
    dict
        JSON-safe payload aligned with CasperResult semantics and the
        casper_result_v1 contract, with a deliberately slender surface
        for dashboards and lender exports.
    """
    # Derive baseline KPIs from the ScenarioResult in a contract-explicit way.
    # Prefer a dedicated `kpis` mapping if available; fall back to an empty
    # mapping rather than abusing scenario.as_dict() as KPI storage.
    baseline_kpis: dict[str, float] = {}
    raw_kpis = getattr(scenario, "kpis", None)
    if isinstance(raw_kpis, Mapping):
        # The live ScenarioResult.kpis mapping carries NON-numeric entries alongside the
        # numbers — scenario_name / wacc_label (str), equity_distribution_status (str),
        # dscr_series (list). float() over the whole dict crashed the CASPER export on every
        # real run (it only survived in tests that fed numeric-only fixtures). Keep the
        # numeric scalars (excluding bool) and skip the rest.
        baseline_kpis = {
            str(k): float(v)
            for k, v in raw_kpis.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }

    # Normalise metadata into a mutable dict so we can safely read/augment it.
    metadata_dict: dict[str, Any] = dict(metadata) if metadata is not None else {}

    casper = CasperResult(
        scenario=scenario,
        baseline_kpis=baseline_kpis,
        sensitivities=sensitivity,
        monte_carlo=monte_carlo,
        generation=generation,
        multi_tech_generation_breakdown=(
            list(technology_breakdown) if technology_breakdown is not None else None
        ),
        multi_tech_wbs=multi_tech_wbs,
        metadata=metadata_dict,
    )

    return _casper_to_dict(casper)


# ────────────────────────── internal helpers ────────────────────────────


def _scenario_summary_to_dict(
    s: ScenarioResult | str | None,
    mc: MonteCarloResult | None = None,
) -> dict[str, Any] | None:
    """
    Slender, JSON-safe descriptor for the scenario.

    Intentionally avoids shipping full `config` / `annual_rows` to keep
    payloads light and lender-friendly. Those remain available on disk /
    in the model outputs when deeper audits are required.

    ``CasperResult.scenario`` may be a bare scenario-name string when the full
    ScenarioResult is not available; in that case we emit a minimal descriptor.
    """
    if s is None:
        return None
    if isinstance(s, str):
        return {"scenario_name": s}

    data: dict[str, Any] = {
        "scenario_name": s.scenario_name,
        "config_path": s.config_path,
        "validation_mode": s.validation_mode,
        "discount_rate_used": s.discount_rate_used,
        "wacc_label": s.wacc_label,
        "wacc_is_real": getattr(s, "wacc_is_real", None),
        "min_dscr": s.min_dscr,
        "max_debt_usd": s.max_debt_usd,
    }

    # WACC summary (if available)
    # CRITICAL FIX: Handle both WaccResult objects AND dict representations
    if s.wacc is not None:
        w = s.wacc

        # Check if w is a dict (legacy/serialized format) or WaccResult object
        if isinstance(w, dict):
            # Already serialized - use as-is
            data["wacc"] = dict(w)
        else:
            # WaccResult object - serialize it
            data["wacc"] = {
                "mode": w.base.mode,
                "wacc_nominal": w.base.wacc_nominal,
                "wacc_real": w.base.wacc_real,
                "wacc_prudential": w.base.wacc_prudential,
                "prudential_rate": w.prudential_rate,
                "prudential_npv": w.prudential_npv,
                "risk_free_rate": w.base.risk_free_rate,
                "market_risk_premium": w.base.market_risk_premium,
                "asset_beta": w.base.asset_beta,
                "target_debt_to_equity": w.base.target_debt_to_equity,
                "target_debt_to_value": w.base.target_debt_to_value,
                "target_equity_to_value": w.base.target_equity_to_value,
                "cost_of_debt_pretax": w.base.cost_of_debt_pretax,
                "cost_of_debt_aftertax": w.base.cost_of_debt_aftertax,
                "cost_of_equity": w.base.cost_of_equity,
                "tax_rate": w.base.tax_rate,
                "inflation_rate": w.base.inflation_rate,
                "prudential_spread_bps": w.base.prudential_spread_bps,
                "meta": dict(w.meta),
            }

    # Debt profile (if attached). The live ScenarioResult carries this as a DICT (the raw
    # debt_result), not the typed TrancheDebtProfile — same dict-or-object split the wacc
    # block handles. Reading .attrs on a dict crashed the whole CASPER export; emit the dict
    # as-is, only walk attributes for the typed form.
    if s.debt_profile is not None:
        dp = s.debt_profile
        if isinstance(dp, Mapping):
            data["debt_profile"] = dict(dp)
        else:
            data["debt_profile"] = {
                "construction_years": dp.construction_years,
                "tenor_years": dp.tenor_years,
                "timeline_periods": dp.timeline_periods,
                "total_debt": dp.total_debt,
                "total_idc": dp.total_idc,
                "lkr_principal": dp.lkr_principal,
                "usd_principal": dp.usd_principal,
                "dfi_principal": dp.dfi_principal,
                "lkr_idc": dp.lkr_idc,
                "usd_idc": dp.usd_idc,
                "dfi_idc": dp.dfi_idc,
                "lkr_rate": dp.lkr_rate,
                "usd_rate": dp.usd_rate,
                "dfi_rate": dp.dfi_rate,
                "interest_only_years": dp.interest_only_years,
                "amortization_style": dp.amortization_style,
                "dscr_target": dp.dscr_target,
            }

    # Debt covenants (if attached). Pydantic model -> model_dump; a dict passes through; a
    # bare status string (the live shape) is not a structured covenant set -> omit.
    if s.debt_covenants is not None:
        dc = s.debt_covenants
        if hasattr(dc, "model_dump"):
            data["debt_covenants"] = dc.model_dump()
        elif isinstance(dc, Mapping):
            data["debt_covenants"] = dict(dc)

    # Equity performance overlay (if available).
    #
    # Canonical EquityPerformance exposes only equity_irr, equity_npv,
    # equity_multiple and metadata. Legacy PE metrics (moic/dpi/rvpi/tvpi/
    # average_coc/payback_period_years) are retained inside ep.metadata by
    # finance/equity_v14.py; we surface them defensively with .get() so the
    # payload also tolerates leaner producers (e.g. pipeline_v14_enhanced).
    #
    # Downside is synthesised from MonteCarloResult when provided, since
    # DownsideMetrics is declared in contracts but not attached to any
    # ScenarioResult in the current pipeline.
    if s.equity_performance is not None:
        ep = s.equity_performance
        downside_dict: dict[str, Any] | None = None
        if mc is not None:
            downside_dict = {
                "project_irr_p10": mc.project_irr_p10,
                "project_npv_p10": mc.project_npv_p10,
                "dscr_min_p10": mc.dscr_min_p10,
            }
        if isinstance(ep, Mapping):
            # Live shape: a dict {equity_irr, equity_npv, equity_multiple, metadata}.
            ep_dict = dict(ep)
            ep_dict["downside"] = downside_dict
            data["equity_performance"] = ep_dict
        else:
            ep_meta: Mapping[str, Any] = (
                ep.metadata if isinstance(ep.metadata, Mapping) else {}
            )
            data["equity_performance"] = {
                "equity_irr": ep.equity_irr,
                "equity_npv": ep.equity_npv,
                "equity_multiple": ep.equity_multiple,
                "moic": ep_meta.get("moic"),
                "dpi": ep_meta.get("dpi"),
                "rvpi": ep_meta.get("rvpi"),
                "tvpi": ep_meta.get("tvpi"),
                "average_coc": ep_meta.get("average_coc"),
                "payback_period_years": ep_meta.get("payback_period_years"),
                "downside": downside_dict,
            }

    return data


def _sensitivity_to_dict(suite: SensitivitySuite | None) -> dict[str, Any] | None:
    """
    Convert SensitivitySuite to a JSON-friendly dict.

    Keeps only metric names and IRR deltas – enough for tornado charts
    and lender one-pagers, without re-embedding full engine outputs.
    """
    if suite is None:
        return None

    # base_metric: baseline value of the suite's headline metric, taken from
    # base_kpis (SensitivitySuite no longer carries a dedicated base_metric field).
    base_metric = suite.base_kpis.get(suite.metric)

    # Per-variable tornado rows live in each TornadoResult's shock_results; the
    # suite-level tornado_results are per-metric containers.
    tornado: list[dict[str, Any]] = []
    for tr in suite.tornado_results:
        for sr in tr.shock_results:
            tornado.append(
                {
                    "variable": sr.label or sr.variable_name,
                    "base_irr": (
                        sr.base_case if sr.base_case is not None else tr.base_metric
                    ),
                    "low_irr": sr.low_case,
                    "high_irr": sr.high_case,
                    "impact_abs": sr.impact_abs,
                    "impact_pct": sr.impact,
                }
            )

    return {
        "metric": suite.metric,
        "base_metric": base_metric,
        "base_config_path": suite.base_config_path,
        "tornado": tornado,
    }


def _monte_carlo_to_dict(mc: MonteCarloResult | None) -> dict[str, Any] | None:
    """
    Convert MonteCarloResult into a lean JSON shape.

    Notes:
    - Does *not* emit raw per-draw results by default; that stays in the
      engine outputs and regression tests.
    - Includes success rate and percentile spreads; standard-error fields are
      not part of the current MonteCarloResult contract and are omitted.
    """
    if mc is None:
        return None

    return {
        "scenario_name": mc.scenario_name,
        "iterations": mc.iterations,
        "failed_iterations": mc.failed_iterations,
        "success_rate_pct": mc.success_rate(),
        "irr": {
            "mean": mc.project_irr_mean,
            "std": mc.project_irr_std,
            "p10": mc.project_irr_p10,
            "p50": mc.project_irr_p50,
            "p90": mc.project_irr_p90,
        },
        "npv": {
            "mean": mc.project_npv_mean,
            "p10": mc.project_npv_p10,
            "p50": mc.project_npv_p50,
            "p90": mc.project_npv_p90,
        },
        "dscr_min": {
            "p10": mc.dscr_min_p10,
            "p50": mc.dscr_min_p50,
        },
    }


def _generation_to_dict(
    gen: MultiTechGenerationResult | None,
) -> dict[str, Any] | None:
    """
    Convert MultiTechGenerationResult using its built-in to_dict helper.
    """
    if gen is None:
        return None
    return gen.to_dict()


def _technology_breakdown_to_list(
    breakdown: Sequence[TechnologyBreakdown] | None,
) -> list[dict[str, Any]] | None:
    """
    Convert a sequence of TechnologyBreakdown into JSON-safe dicts.
    """
    if breakdown is None:
        return None

    return [
        {
            "technology": tb.technology,
            "share_of_capex_pct": tb.share_of_capex_pct,
            "share_of_cfads_pct": tb.share_of_cfads_pct,
            "share_of_aep_pct": tb.share_of_aep_pct,
            "notes": tb.notes,
        }
        for tb in breakdown
    ]


def _tail_risk_from_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    """
    Extract a lean tail-risk snapshot from metadata, if available.

    Convention:
    - metadata["tail_risk_summary"] is expected to be a mapping:
        metric_name -> { var, cvar, p10, p50, p90, breach_probability, ... }

    We surface that as the top-level `tail_risk` block in the CASPER payload.
    """
    raw = metadata.get("tail_risk_summary")
    if not isinstance(raw, Mapping):
        return None

    # Shallow copy to ensure JSON-safety; assume inner dicts are already
    # JSON-serialisable (enforced upstream in tail-risk utilities).
    out: dict[str, Any] = {}
    for metric, snapshot in raw.items():
        if isinstance(snapshot, Mapping):
            out[str(metric)] = dict(snapshot)
    return out or None


def _casper_to_dict(casper: CasperResult) -> dict[str, Any]:
    """
    Flatten CasperResult into the canonical CASPER payload shape.

    This is the single place where we define what CASPER returns to the
    outside world. Any future changes should be treated as contract
    changes and guarded by tests + docs.
    """
    metadata = dict(casper.metadata)
    return {
        "contract_version": CASPER_CONTRACT_VERSION,
        "scenario": _scenario_summary_to_dict(casper.scenario, casper.monte_carlo),
        "baseline_kpis": dict(casper.baseline_kpis),
        # Singular key to match the CASPER v1 contract docs
        "sensitivity": _sensitivity_to_dict(casper.sensitivities),
        "monte_carlo": _monte_carlo_to_dict(casper.monte_carlo),
        "generation": _generation_to_dict(casper.generation),
        "technology_breakdown": _technology_breakdown_to_list(
            casper.multi_tech_generation_breakdown
        ),
        # Per-tech cost/return work-breakdown (ARCH-3, #475): additive, read-only.
        "multi_tech_wbs": (
            casper.multi_tech_wbs.to_dict()
            if casper.multi_tech_wbs is not None
            else None
        ),
        "tail_risk": _tail_risk_from_metadata(metadata),
        "metadata": metadata,
    }


__all__ = [
    "CASPER_CONTRACT_VERSION",
    "build_casper_payload",
]
