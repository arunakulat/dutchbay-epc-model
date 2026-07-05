"""Report content model — projects a ``CaseResult`` into a render-ready context.

Pure presentation: this module formats KPI values per the config display spec
and flags them against lender covenants. It contains **no finance logic**
(Dolphin) — every number originates from the canonical pipeline run, and the
cost-of-capital hurdle is read from the run's own ``discount_rate_used`` KPI
rather than hardcoded. ``generated_at`` is supplied by the caller so the build is
deterministic and unit-testable (CASPER).

All section models are frozen (``ConfigDict(frozen=True)``, #608), extending the
frozen-contract pattern of the analytics/core returns contracts: a context is
built once in :func:`build_report_context` and consumed read-only by the renderer
and the API, so post-construction mutation is a bug and now raises. Derive a
variant with ``model_copy(update=...)`` instead of assignment.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field

from analytics.capital_risk_layer_v14 import CapitalRiskReport
from analytics.conditions_precedent import CpReport, build_cp_report
from analytics.contracts_v14 import ProjectEquityIrrBridge, TwoFactorInteractionGrid
from analytics.development_readiness import build_readiness_report
from analytics.evidence_register import build_evidence_report
from analytics.evidence_score import build_evidence_score
from analytics.feasibility_sections import build_feasibility_report
from analytics.irr_bridge import build_project_equity_irr_bridge_from_run
from analytics.portfolio.generation_aggregator import build_multi_tech_from_run
from analytics.portfolio.poi_curtailment import resolve_shared_poi_curtailment
from analytics.portfolio.tech_wbs import build_multi_tech_wbs
from analytics.three_statement import (
    ThreeStatementResult,
    build_cashflow_waterfall,
    build_three_statement_from_run,
)
from api.pipeline_api import FinanceReportBlocks, extract_finance_report_blocks
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_config import (
    Covenants,
    KpiKind,
    LimitationItem,
    ReportConfig,
    ReportMeta,
    RiskItem,
    load_report_config,
)
from app.services.report_global_sa import GlobalSABlock
from app.services.report_tornado import TornadoBlock


def format_kpi_value(value: float, kind: KpiKind) -> str:
    """Format a numeric KPI for display per its ``kind``.

    Args:
        value: The raw KPI value from the run (IRRs/rates as ratios, DSCR/LLCR/
            MOIC as multiples, NPV/CFADS in USD).
        kind: ``"pct"``, ``"multiple"``, or ``"usd"``.

    Returns:
        A display string, e.g. ``"4.22%"``, ``"1.30x"``, ``"-$57,994,286"``.
    """
    if kind == "pct":
        return f"{value * 100:.2f}%"
    if kind == "multiple":
        return f"{value:.2f}x"
    # usd — accounting-style sign on the dollar marker
    if value < 0:
        return f"-${abs(value):,.0f}"
    return f"${value:,.0f}"


#: Em-dash placeholder for an absent (None) value in the finance tables.
_ABSENT = "—"


def fmt_usd(value: Optional[float]) -> str:
    """Whole-dollar display with an accounting-style sign (None -> em-dash)."""
    if value is None:
        return _ABSENT
    if value < 0:
        return f"-${abs(value):,.0f}"
    return f"${value:,.0f}"


def fmt_gwh(value: Optional[float]) -> str:
    """GWh display to one decimal (None -> em-dash)."""
    return _ABSENT if value is None else f"{value:,.1f} GWh"


def fmt_x(value: Optional[float]) -> str:
    """Multiple display, e.g. ``1.30x`` (None -> em-dash)."""
    return _ABSENT if value is None else f"{value:.2f}x"


def fmt_ratio_pct(value: Optional[float]) -> str:
    """Display a RATIO as a percentage, e.g. ``0.332 -> 33.20%`` (None -> em-dash)."""
    return _ABSENT if value is None else f"{value * 100:.2f}%"


def fmt_pct(value: Optional[float]) -> str:
    """Display an ALREADY-percentage number, e.g. ``13.39 -> 13.39%`` (None -> em-dash)."""
    return _ABSENT if value is None else f"{value:.2f}%"


def fmt_pp(value: Optional[float]) -> str:
    """Display a decimal IRR DELTA as SIGNED percentage points, e.g. ``0.012 -> +1.20 pp``.

    Used for the IRR-bridge leg contributions, where the sign carries meaning (a lift vs a drag);
    ``None -> em-dash``.
    """
    return _ABSENT if value is None else f"{value * 100:+.2f} pp"


class KpiRow(BaseModel):
    """One rendered KPI line: raw value plus its formatted display string."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    value: float
    display: str


class AssumptionRow(BaseModel):
    """One assumptions-register line: value + evidence source/as-of + a model-impact note."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    display: str
    source: str = ""
    as_of: str = ""
    impact: str = ""


class RiskRow(BaseModel):
    """One rendered risk-register line (category, risk, mitigation, residual severity)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    category: str
    risk: str
    mitigation: str
    severity: str  # low | medium | high — drives the badge class in the template
    #: TCFD/EP4 climate-risk class (physical | transition); None when the risk is untagged,
    #: in which case the template renders no climate tag. Additive presentation only.
    climate_risk_category: Optional[str] = None


class LimitationRow(BaseModel):
    """One rendered model-limitation line (topic + detail) — #734."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    topic: str
    detail: str


class ReadinessRow(BaseModel):
    """One rendered development-readiness line (workstream, R/A/G status, note)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workstream: str
    status: str  # green | amber | red — drives the badge class in the template
    note: str = ""


class CpItemRow(BaseModel):
    """One rendered conditions-precedent line (item, workstream, status, note) — #708."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    workstream: str
    status: str  # satisfied | waived | pending — drives the badge class
    note: str = ""
    waived_reason: str = ""


class CpChecklistBlock(BaseModel):
    """Conditions-precedent checklist gating first drawdown (#708, slice 5/5 of #616).

    A read-only projection of :class:`analytics.conditions_precedent.CpReport`: the declared
    CP line items with their satisfied/waived/pending status, the outstanding rollup, and the
    canonical items still missing from the checklist. ``all_satisfied`` is the headline gate.
    None (section omitted) for legacy callers or a malformed checklist.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: List[CpItemRow]
    n_outstanding: int
    n_satisfied: int
    n_waived: int
    missing: List[str]
    #: Declared conditions the register flagged (unknown item, off-scale status, missing
    #: status) — surfaced so a declared line is NEVER silently dropped from every view.
    flagged: List[str]
    #: True only when the register recorded NO finding. The "no outstanding conditions"
    #: pass-badge requires this AND all_satisfied, so a green badge cannot render over a
    #: declared-but-unrenderable (e.g. typo'd-status) condition.
    is_clean: bool
    all_satisfied: bool


class FeasibilitySectionRow(BaseModel):
    """One rendered feasibility-report section line (title, group, status) — #708."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    title: str
    group: str
    status: str  # complete | draft | not_applicable


class FeasibilitySectionsBlock(BaseModel):
    """Feasibility-report section coverage against the 20-section skeleton (#708, #616).

    A read-only projection of :class:`analytics.feasibility_sections.FeasibilityReport`
    (slice 1, #705): the scenario's declared section coverage in report order, the
    complete/draft/not-applicable counts, and the canonical sections still missing.
    ``all_complete`` is the IC-readiness gate. None (section omitted) for legacy callers or a
    malformed declaration.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: List[FeasibilitySectionRow]
    n_complete: int
    n_draft: int
    n_not_applicable: int
    missing: List[str]
    #: Declared sections the register flagged (unknown section, off-scale status, missing
    #: status) — surfaced so a declared section is NEVER silently dropped from every view.
    flagged: List[str]
    #: The canonical section count (always the fixed 20-section skeleton), independent of how
    #: many were declared — so the displayed "of N" is never understated by a dropped item.
    total: int
    #: True only when the register recorded NO finding; the "Complete" pass-badge requires
    #: this AND all_complete, so a green badge cannot render over a typo'd/dropped section.
    is_clean: bool
    all_complete: bool


class Verdict(BaseModel):
    """Covenant/return flags and a one-line headline, all config-thresholded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    headline: str
    project_viable: bool
    equity_positive: bool
    dscr_covenant_met: bool
    balloon_within_limit: bool
    notes: List[str] = Field(default_factory=list)


class RedFlag(BaseModel):
    """One explicit negative signal surfaced (not recomputed) from the run (#706).

    ``kind`` is the machine key (covenant_breach | negative_equity | below_hurdle |
    cp_outstanding | readiness_red); ``severity`` is presentation triage only —
    ``high`` for value/covenant signals the engine published, ``medium`` for
    execution-gate signals from the scenario registers — not a new risk model.
    ``source`` names where the signal was read from, for the audit trail.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: str
    severity: str  # medium | high — drives the badge class in the template
    detail: str
    source: str


class IcSummaryBlock(BaseModel):
    """IC executive summary — the verdict plus every explicit red flag (#706).

    A pure read-only projection for the Investment Committee: the headline verdict
    (single source: :class:`Verdict` — never re-derived here), the explicit
    red-flag list, and the two execution-gate rollups (outstanding conditions
    precedent, development-readiness reds). ``is_clean`` is True only when no red
    flag fired. Every flag is presence-gated: an ABSENT KPI or register never
    fabricates a flag (an IC pack must not report a breach it has no evidence for).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    headline: str
    red_flags: List[RedFlag] = Field(default_factory=list)
    #: Outstanding (pending) conditions precedent — 0 when none declared.
    cp_outstanding: int = 0
    #: Outstanding CP count per workstream (empty when none outstanding).
    cp_outstanding_by_workstream: Dict[str, int] = Field(default_factory=dict)
    #: Development-readiness workstreams declared RED (empty when none).
    readiness_reds: List[str] = Field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not self.red_flags


class EvidenceRow(BaseModel):
    """One material assumption's declared evidence (source / as-of / tier)."""

    model_config = ConfigDict(frozen=True)

    assumption: str
    source: str
    as_of: str
    tier: str
    note: str = ""


class EvidenceBlock(BaseModel):
    """Coverage of a scenario's assumption-evidence register (#435 → RPT-1)."""

    model_config = ConfigDict(frozen=True)

    rows: List[EvidenceRow]
    missing: List[str]  # material assumptions with no declared evidence
    covered: int
    total: int


class EvidenceScoreRow(BaseModel):
    """One material assumption's contribution to the evidence-completeness score (#707)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption: str
    tier: str  # declared tier, or "" when missing / ungradeable
    strength: float  # credited strength in [0, 1]
    covered: bool


class EvidenceScoreBlock(BaseModel):
    """Bankability evidence-completeness score for a scenario (#707, slice 4/5 of #616).

    A read-only projection of :class:`analytics.evidence_score.EvidenceScore`: the 0-100
    score and its plain band label, the coverage counts, the mean strength over covered
    entries, and the per-assumption breakdown. Pure surfacing — no finance metric is
    recomputed. None (section omitted) for legacy callers or a malformed register.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    score: float
    band: str
    covered: int
    total: int
    missing: List[str]
    coverage_pct: float
    mean_covered_strength: float
    rows: List[EvidenceScoreRow]


class MultiTechRow(BaseModel):
    """One technology's line in the multi-technology breakdown (ARCH-4, #476)."""

    model_config = ConfigDict(frozen=True)

    technology: str
    aep_gwh: Optional[float] = None
    share_of_aep_pct: Optional[float] = None
    share_of_cfads_pct: Optional[float] = None
    capex_usd: Optional[float] = None
    share_of_capex_pct: Optional[float] = None
    opex_usd_per_year: Optional[float] = None
    cost_of_equity: Optional[float] = None
    wacc_basis: str = "blended"


class MultiTechBlock(BaseModel):
    """Per-technology production/economics breakdown for a hybrid plant (ARCH-4, #476).

    Reuses the additive multi-tech generation view (ARCH-2, #488) and the per-tech
    cost/return work-breakdown (ARCH-3, #475) — pure presentation, no finance logic. The
    CFADS share is apportioned by operating margin; the financed-vs-allocated residual is
    the shared / balance-of-plant bucket. Rendered only for genuine hybrids (2+ generation
    technologies).
    """

    model_config = ConfigDict(frozen=True)

    rows: List[MultiTechRow]
    total_aep_gwh: Optional[float] = None
    financed_capex_usd: Optional[float] = None
    allocated_capex_usd: Optional[float] = None
    capex_residual_usd: Optional[float] = None
    capex_reconciled: bool = False
    project_wacc_nominal: Optional[float] = None
    #: Shared-POI curtailment (ARCH-5, #476) — populated only when the scenario declares a
    #: POI limit and per-tech hourly profiles; None (omitted) otherwise.
    poi_limit_mw: Optional[float] = None
    poi_curtailment_pct: Optional[float] = None
    poi_curtailed_energy_mwh: Optional[float] = None


class ThreeStatementBlock(BaseModel):
    """Three articulating financial statements + their tie-out status (#479).

    P&L / cash flow / balance sheet assembled from the engine's annual + debt outputs
    (analytics.three_statement), presented in USD. Pure presentation; the tie-out flags are
    the lender-relevant signal that the statements articulate.
    """

    model_config = ConfigDict(frozen=True)

    currency: str
    tie_outs_pass: bool
    balance_sheet_balances: bool
    debt_retires_to_residual: bool
    cashflow_reconciles: bool
    retained_earnings_rolls: bool
    max_abs_balance_residual: float
    income_statement: List[Dict[str, Any]]
    cash_flow: List[Dict[str, Any]]
    balance_sheet: List[Dict[str, Any]]


class WaterfallRow(BaseModel):
    """One operating year of the cash-flow waterfall by payment priority (#481, RPT-2)."""

    model_config = ConfigDict(frozen=True)

    year: int
    cfads: float
    scheduled_debt_service: float
    balloon_sweep: float
    cash_to_equity: float


class WaterfallBlock(BaseModel):
    """Cash-flow waterfall (CFADS → scheduled debt service → balloon → equity) + totals (#481, RPT-2).

    Sourced from the engine's own published per-row figures, so the cascade ties line-for-line to
    the rest of the report (CCCDIR — one source of truth): ``cfads`` equals the CFADS the DSCR
    numerator uses (``total_cfads`` = the report's headline CFADS) and ``scheduled_debt_service``
    equals the Debt Structure & DSCR Profile section's debt service. The balloon is a SEPARATE line
    (senior to equity but excluded from the scheduled DSCR, so the two sections do not present
    contradictory coverage). The model sweeps 100% of post-senior cash to equity, so
    ``cash_to_equity`` is the distribution (no reserve build-up beyond the DSRA funded at close).
    """

    model_config = ConfigDict(frozen=True)

    currency: str
    rows: List[WaterfallRow]
    total_cfads: float
    total_scheduled_debt_service: float
    total_balloon_sweep: float
    total_cash_to_equity: float


class ResourceTrendRow(BaseModel):
    """One (Metric, Value) line of the long-term resource & trend summary (#178 → #656)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    value: str


class ResourceTrendBlock(BaseModel):
    """Long-term wind-resource & trend commentary for the lender report (#178 → #656).

    A VALIDATE / disclose-only section: it surfaces the Mann-Kendall + Sen's-slope trend test,
    the net-AEP-by-reference-period table, and the forward-looking P50-basis recommendation from
    :func:`wind_resource.long_term_trend.analyze_long_term_resource` (IEC 61400-15-1 / MEASNET
    basis). It NEVER overwrites the committed/frozen scenario P50 — the ``recommended_p50_gwh`` is
    a disclosed forward basis, not a driver of any KPI. Every field is projected from the live
    analysis output (``render_trend_markdown`` / ``trend_summary_dataframe``); nothing is
    re-derived here (CCCDIR — one source of truth). Rendered only when a caller supplies the live
    ERA5 series (existing report callers pass none, so the section is omitted → byte-identical).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The rendered Markdown commentary section verbatim from ``render_trend_markdown`` — the
    #: authoritative narrative, kept intact so the report cannot drift from the analysis.
    markdown: str
    #: The tidy (Metric, Value) table verbatim from ``trend_summary_dataframe`` — one source of
    #: truth shared with the lender-workbook "ResourceTrend" sheet.
    summary_rows: List[ResourceTrendRow]
    reference_period: str
    classification: str
    classification_note: str
    trend_significant: bool
    mk_tau: float
    mk_pvalue: float
    sen_slope_per_decade: float
    ols_r2: float
    #: Forward-looking recommended P50 basis + values — DISCLOSED, never applied to the frozen
    #: committed P50 (report/VALIDATE-only).
    recommended_basis: str
    recommended_p50_gwh: Optional[float] = None
    recommended_p50_cf: Optional[float] = None
    downside_p50_gwh: Optional[float] = None
    upside_p50_gwh: Optional[float] = None


class IrrBridgeLeg(BaseModel):
    """One labelled step of the project→equity IRR bridge (#621, IC disclosure)."""

    model_config = ConfigDict(frozen=True)

    name: str
    contribution: float
    irr_after: Optional[float] = None
    detail: Optional[str] = None


class IrrBridgeBlock(BaseModel):
    """Project→equity IRR bridge: the leverage uplift decomposed for the IC (#621, disclosure).

    A disclosure-only reconciliation of the engine's PUBLISHED ``project_irr`` to its published
    ``equity_irr`` (CCCDIR — one source of truth; the two endpoints are the headline KPIs, not
    recomputed here). The named legs (leverage, cost of debt, tax shield) plus the explicit
    ``residual`` sum exactly to ``total_uplift = equity_irr − project_irr`` — the residual carries
    the IRR interaction term and the equity-waterfall effects (principal timing, covenant lockup,
    DSRA, WHT, terminal value) the four legs do not model in isolation. Rendered only when the run
    supplies a computed equity distribution; the section is otherwise omitted (additive,
    default-off — no committed KPI is moved).
    """

    model_config = ConfigDict(frozen=True)

    currency: str
    project_irr: Optional[float] = None
    equity_irr: Optional[float] = None
    total_uplift: Optional[float] = None
    legs: List[IrrBridgeLeg]
    residual: float
    residual_label: str
    reconciled: bool


class CapitalRiskMetricRow(BaseModel):
    """One MC return-metric's distributional summary (mean + VaR/CVaR) — #776 / #657."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str  # equity_irr | project_irr | equity_npv | project_npv
    unit: (
        str  # "pct" (IRR ratios) | "usd" (NPV dollars) — drives the display formatting
    )
    mean: float
    var: float
    cvar: float
    var_label: str  # e.g. "VaR(95%)"
    cvar_label: str  # e.g. "CVaR/ES(95%)"


class CapitalRiskBlock(BaseModel):
    """Capital-risk (Monte-Carlo) block for the lender report (#776, surfacing #657).

    A read-only projection of :class:`analytics.capital_risk_layer_v14.CapitalRiskReport` —
    the unified output of the CANONICAL Monte-Carlo (LHS + Iman-Conover correlation): the
    covenant-breach probabilities (DSCR/LLCR/PLCR) against their floors, the probability equity
    IRR falls below the hurdle, the per-metric VaR/CVaR for the four return metrics, and the
    path to the NPV-distribution chart. Provenance (``scenario`` / ``model_version`` /
    ``n_trials``) is carried for the audit trail (MRM-02). Rendered only when a caller supplies
    the pre-computed report (the MC is heavy and runs out-of-band, not in the report builder) —
    otherwise the section is omitted (additive, default-off; committed reports byte-identical).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    model_version: str
    method: (
        str  # the ACTUAL MC method provenance (e.g. "lhs sampling, rank correlation")
    )
    n_trials: int
    dscr_breach_probability: float
    llcr_breach_probability: float
    plcr_breach_probability: float
    dscr_floor: float
    llcr_floor: float
    plcr_floor: float
    probability_below_hurdle: float
    target_equity_irr: float
    metrics: List[CapitalRiskMetricRow]
    #: The NPV-distribution chart's basename (no absolute path — avoids leaking the server
    #: filesystem layout into a lender document) and, when the PNG exists, an embedded
    #: base64 data-URI so the chart renders self-contained. None when matplotlib degraded.
    npv_distribution_filename: str
    npv_distribution_img: Optional[str] = None


class InteractionGridCell(BaseModel):
    """One (row-A, col-B) cell of the two-factor interaction grid — #739 slice-2.

    ``value`` is the RAW metric at this driver pair (``None`` for a failed/non-finite cell,
    counted in the block's ``n_failed_cells`` — never silently substituted). ``interaction`` is
    the deviation of that cell from the additive combination of the two one-way effects (the
    coupling term), likewise ``None`` when the value failed. ``intensity`` is a signed heatmap
    shade in ``[-1, 1]`` (interaction normalised by the grid's ``max_abs_interaction``) that the
    template maps to a CSS background; ``None`` for a failed cell, which renders neutral.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Optional[float] = None
    interaction: Optional[float] = None
    intensity: Optional[float] = None


class InteractionGridRow(BaseModel):
    """One grid row: driver-A case label plus the per-column cells — #739 slice-2."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    cells: List[InteractionGridCell]


class InteractionGridBlock(BaseModel):
    """Two-factor sensitivity interaction grid for the lender report — #739 slice-2.

    A read-only, heatmap-ready projection of
    :class:`analytics.contracts_v14.TwoFactorInteractionGrid` (the slice-1 primitive). Each cell
    carries the raw metric, the interaction (deviation from one-way additivity, in the metric's
    own units), and a signed heatmap intensity. The grid is N×M full-pipeline evaluations, so it
    is computed OUT-OF-BAND (like the tornado / global-SA / capital-risk blocks) and passed in;
    ``None`` (the default on :class:`ReportContext`) omits the section — the synchronous API
    report route and every committed scenario stay byte-identical (the #645 latency ledger).

    The honesty metadata is surfaced as first-class fields, not buried in a dict, so the template
    always DISCLOSES them (the #657 lesson — a heatmap that hides failed cells or a mis-declared
    base is a lender-facing defect): ``n_failed_cells`` counts cells that failed to evaluate (shown
    as em-dashes, never zero-filled), ``base_mismatch`` flags a driver whose declared base drifted
    from the live config, and ``unresolved_drivers`` lists any driver that did not resolve to a
    config path (non-strict emitters only — the strict emitter fails loud instead).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str
    param_a_name: str
    param_b_name: str
    param_a_label: str
    param_b_label: str
    b_labels: List[str]
    rows: List[InteractionGridRow]
    base_metric: float
    max_abs_interaction: float
    #: True when the metric is an IRR/return ratio shown as a percentage (drives cell formatting);
    #: NPV/dollar metrics render as USD. Mirrors the CapitalRiskMetricRow unit convention.
    is_ratio_metric: bool
    #: Honesty disclosure — always rendered so a lender sees the grid's integrity, not just its
    #: colours (#657): failed-cell count, declared-vs-evaluated base mismatch, unresolved drivers.
    n_failed_cells: int
    base_mismatch: bool
    unresolved_drivers: List[str]
    n_evaluations: int
    base_config_path: str


class ReportContext(BaseModel):
    """Everything the Jinja2 template needs to render the report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ReportMeta
    covenants: Covenants
    generated_at: str
    #: Declared run-mode grade stamp (#733c): "screening" / "developer" / "lender" /
    #: "ic" from the scenario's ``run.mode`` policy, or ``None`` when no mode is
    #: declared (byte-identical to pre-#733c reports). It labels the artefact by the
    #: grade it was RUN at rather than the report's implicit lender framing.
    report_grade: Optional[str] = None
    scenario_variant: str
    site_name: str
    status: str
    kpi_rows: List[KpiRow]
    verdict: Verdict
    #: IC executive summary + explicit red-flag block (#706): the verdict headline plus
    #: every presence-gated negative signal (covenant breaches, negative sponsor returns,
    #: below-hurdle project IRR, outstanding CPs, readiness reds). Pure surfacing over
    #: engine-published outputs; None only for callers that construct a context without
    #: this block, in which case the section is omitted (render-when-present).
    ic_summary: Optional[IcSummaryBlock] = None
    assumptions: List[AssumptionRow]
    risk_register: List[RiskRow] = Field(default_factory=list)
    #: Model-limitations / scope caveats surfaced in every report (#734). Config-authored;
    #: default empty so a legacy/minimal config omits the section (render-when-present).
    model_limitations: List[LimitationRow] = Field(default_factory=list)
    readiness: List[ReadinessRow] = Field(default_factory=list)
    overall_readiness: Optional[str] = (
        None  # green | amber | red — worst declared status
    )
    #: Conditions-precedent checklist gating first drawdown (#708). None for legacy callers /
    #: no declared checklist / a malformed one — the section is then omitted.
    cp_checklist: Optional[CpChecklistBlock] = None
    #: Feasibility-report section coverage against the 20-section skeleton (#708 / #705). None
    #: for legacy callers / no declared sections / a malformed declaration — section omitted.
    feasibility_sections: Optional[FeasibilitySectionsBlock] = None
    #: Serialised finance blocks (production P50/P90, sources-and-uses, DSCR profile,
    #: exec KPI callout) — RPT-1. None when the caller supplies no debt_result /
    #: scenario_config (e.g. the legacy KPI-only report path), in which case those
    #: quantitative sections are simply not rendered.
    finance: Optional[FinanceReportBlocks] = None
    #: One-at-a-time sensitivity tornado over the standard drivers (RPT-1). None when
    #: not supplied or when the (best-effort) sweep failed — the section is then omitted.
    tornado: Optional[TornadoBlock] = None
    #: Global (Morris) sensitivity screening over the MC drivers (MC-1). None when not
    #: supplied or the (best-effort) screening failed/has no drivers — section omitted.
    global_sa: Optional[GlobalSABlock] = None
    #: Global (PAWN) sensitivity block over the MC drivers (#645) — the distribution-based
    #: (median-KS) complement to the variance-based Morris screening, robust on the
    #: covenant-pinned / skewed KPIs. None when not supplied or the (best-effort) block
    #: failed/has no drivers — that subsection is then omitted (additive; default absent =
    #: byte-identical to the pre-#645 report).
    global_sa_pawn: Optional[GlobalSABlock] = None
    #: Capital-risk (canonical Monte-Carlo) block (#776 / #657): covenant-breach
    #: probabilities, probability-below-hurdle, per-metric VaR/CVaR, NPV-distribution chart.
    #: Pre-computed out-of-band (the MC is heavy) and passed in; None for callers that supply
    #: no capital-risk report, in which case the section is omitted (default-off, byte-identical).
    capital_risk: Optional[CapitalRiskBlock] = None
    #: Two-factor sensitivity interaction grid (#739 slice-2): a driver-A × driver-B heatmap of
    #: the metric and its interaction (deviation from one-way additivity), with the honesty
    #: disclosures. The grid is N×M full-pipeline evaluations, so it is computed OUT-OF-BAND (like
    #: the tornado / capital-risk blocks) and passed in; None (the default) omits the section — the
    #: synchronous API report route and every committed scenario stay byte-identical (#645).
    interaction_grid: Optional[InteractionGridBlock] = None
    #: Assumption-evidence register coverage (#435 → RPT-1). None for legacy callers
    #: (no scenario config), in which case the section is omitted.
    evidence: Optional[EvidenceBlock] = None
    #: Bankability evidence-completeness score (#707) — the config-weighted score on top of
    #: the evidence-register coverage. None for legacy callers / a malformed register; the
    #: section is then omitted. Additive; committed scenarios byte-identical.
    evidence_score: Optional[EvidenceScoreBlock] = None
    #: Per-technology production/economics breakdown for a hybrid (ARCH-4, #476). None for
    #: single-tech plants or legacy callers — the section is then omitted.
    multi_tech: Optional[MultiTechBlock] = None
    #: Three-statement output + tie-out status (#479). None when the caller supplies no
    #: annual_rows / debt_result — the section is then omitted.
    three_statement: Optional[ThreeStatementBlock] = None
    #: Cash-flow waterfall by payment priority (#481, RPT-2). Sourced from the engine's published
    #: per-row figures (ties to the headline CFADS + DSCR section); None on the legacy KPI-only
    #: path, where the section is omitted.
    cashflow_waterfall: Optional[WaterfallBlock] = None
    #: Long-term wind-resource & trend commentary (#178 → #656). Populated only when a caller
    #: supplies a pre-analyzed trend block sourced from the live ERA5 series; existing callers
    #: (the API report routes) pass none, so the section is omitted and the report is unchanged.
    #: Disclose-only — the recommended P50 basis never overwrites the committed/frozen P50.
    resource_trend: Optional[ResourceTrendBlock] = None
    #: Project→equity IRR bridge (#621). Reconciles the published project IRR to the published
    #: equity IRR via labelled legs (leverage / cost of debt / tax shield) + an explicit residual.
    #: None unless the caller supplies the full run result AND it carries a computed equity
    #: distribution — additive, default-off; the section is otherwise omitted.
    irr_bridge: Optional[IrrBridgeBlock] = None
    #: FX-integration failure warning (#736). Set when the run's FX calibration/integration failed
    #: (a log-only event today), so a stale/fallback FX assumption is surfaced to the reader rather
    #: than buried in logs. None when FX integration succeeded or was not reported — the banner is
    #: then omitted (render-when-present; committed runs succeed, so byte-identical).
    fx_warning: Optional[str] = None
    #: FX silent-fallback note (#785). Set when FX integration SUCCEEDED but one or more FX
    #: surfaces were built from stale/default substitutions (malformed fx block, flat-curve
    #: fallback, degenerate risk profile) — arguably more dangerous than an outright failure
    #: because the numbers look plausible. None when no fallback fired (render-when-present;
    #: the committed scenarios take no fallback, so byte-identical).
    fx_fallback_note: Optional[str] = None
    manifest: Dict[str, Any]


def _build_kpi_rows(kpis: Dict[str, float], config: ReportConfig) -> List[KpiRow]:
    """Render the configured KPI table; silently skip KPIs absent from the run."""
    rows: List[KpiRow] = []
    for spec in config.kpi_table:
        if spec.key not in kpis:
            continue
        value = float(kpis[spec.key])
        rows.append(
            KpiRow(
                key=spec.key,
                label=spec.label,
                value=value,
                display=format_kpi_value(value, spec.kind),
            )
        )
    return rows


def _build_verdict(kpis: Dict[str, float], covenants: Covenants) -> Verdict:
    """Derive covenant/return flags and a headline from the run and config.

    Reads the hurdle from the run (``discount_rate_used``); compares the minimum
    DSCR and balloon share to the configured covenants. This is threshold
    comparison on engine outputs — not a recomputation of any finance metric.
    """
    project_irr = kpis.get("project_irr")
    hurdle = kpis.get("discount_rate_used")
    equity_npv = kpis.get("equity_npv")
    equity_irr = kpis.get("equity_irr")
    min_dscr = kpis.get("min_dscr")
    balloon_pct = kpis.get("balloon_pct")

    project_viable = (
        project_irr is not None and hurdle is not None and project_irr >= hurdle
    )
    if equity_npv is not None:
        equity_positive = equity_npv > 0
    elif equity_irr is not None:
        equity_positive = equity_irr > 0
    else:
        equity_positive = False
    dscr_covenant_met = min_dscr is not None and min_dscr >= covenants.min_dscr_floor
    # Honor the engine's authoritative covenant judgment when it published one: the engine
    # evaluates balloon_pct against the SCENARIO's own max_balloon_pct (e.g. 10%), so the
    # report must NOT re-derive "within limit" against its more lenient presentation default
    # (report_defaults 40%) and silently contradict the engine's breach flag (CCCDIR — the
    # report and engine must not be two sources of truth for the same covenant). Fall back to
    # the report-config ceiling only when the engine did not publish a balloon breach flag.
    balloon_breach = kpis.get("balloon_covenant_breach")
    if balloon_breach is not None:
        balloon_within_limit = not bool(balloon_breach)
    else:
        balloon_within_limit = (
            balloon_pct is None or balloon_pct <= covenants.max_balloon_pct
        )

    notes: List[str] = []
    if project_irr is not None and hurdle is not None:
        rel = "at or above" if project_viable else "below"
        notes.append(
            f"Project IRR {project_irr * 100:.2f}% is {rel} the "
            f"{hurdle * 100:.2f}% cost of capital."
        )
    if equity_irr is not None:
        # The sign word must reflect the IRR's OWN sign, not the equity-NPV value flag
        # (equity_positive). A positive IRR that is still below the equity hurdle has a
        # negative NPV; labelling it "negative to sponsors" off the NPV flag printed a
        # literally false statement (round-11 fix). A break-even 0.00% is likewise not
        # "negative": gate the negative wording on a strict < 0 and give exactly-0.0 its
        # own honest word (#769 — mirrors the #706 _build_ic_summary <= 0 -> < 0 fix;
        # finance.irr / metrics can emit an exact 0.0). Distinguish all four cases.
        if equity_irr < 0:
            desc = "negative to sponsors"
        elif equity_irr == 0:
            desc = "break-even to sponsors"
        elif not equity_positive:
            desc = "positive but below the equity hurdle"
        else:
            desc = "positive to sponsors"
        notes.append(f"Equity IRR {equity_irr * 100:.2f}% — {desc}.")
    if min_dscr is not None:
        rel = "meets" if dscr_covenant_met else "breaches"
        notes.append(
            f"Minimum DSCR {min_dscr:.2f}x {rel} the "
            f"{covenants.min_dscr_floor:.2f}x lender floor "
            f"(target {covenants.min_dscr_target:.2f}x)."
        )
    if balloon_pct is not None:
        if balloon_breach is not None:
            # The engine judged it against the scenario's own covenant.
            rel = "is within" if balloon_within_limit else "BREACHES"
            notes.append(
                f"Balloon/bullet share {balloon_pct * 100:.2f}% {rel} the modeled "
                f"refinance-risk covenant."
            )
        else:
            rel = "within" if balloon_within_limit else "exceeds"
            notes.append(
                f"Balloon/bullet share {balloon_pct * 100:.2f}% {rel} the "
                f"{covenants.max_balloon_pct * 100:.0f}% refinance-risk ceiling."
            )

    # The headline must never contradict the covenant table: a "Bankable" claim
    # requires BOTH hard covenants (DSCR floor and balloon ceiling) to hold, not
    # just the DSCR one. A breach with otherwise-acceptable returns is called out
    # explicitly rather than softened to "Marginal".
    covenants_met = dscr_covenant_met and balloon_within_limit
    returns_ok = project_viable and equity_positive
    if returns_ok and covenants_met:
        headline = "Bankable at the modeled assumptions."
    elif not project_viable and not equity_positive:
        headline = "Value-destructive at the modeled assumptions."
    elif not covenants_met:
        headline = "Not bankable — covenant breach at the modeled assumptions."
    else:
        headline = "Marginal — covenant-sensitive at the modeled assumptions."

    return Verdict(
        headline=headline,
        project_viable=project_viable,
        equity_positive=equity_positive,
        dscr_covenant_met=dscr_covenant_met,
        balloon_within_limit=balloon_within_limit,
        notes=notes,
    )


def _build_ic_summary(
    kpis: Dict[str, float],
    verdict: Verdict,
    scenario_config: Optional[Mapping[str, Any]],
    readiness_rows: Sequence[ReadinessRow],
) -> IcSummaryBlock:
    """Project the run's explicit negative signals into the IC red-flag block (#706).

    Pure surfacing, no recomputation: the covenant/return judgments are read from the
    already-built :class:`Verdict` (single source — this honors the engine-published
    ``balloon_covenant_breach`` flag exactly the way :func:`_build_verdict` does, per the
    CCCDIR precedent), the CP-outstanding rollup from the canonical
    :func:`analytics.conditions_precedent.build_cp_report`, and the readiness reds from
    the rows already built for the readiness section (one register pass, one source).

    Every flag is PRESENCE-GATED on the underlying KPI/register: the verdict's booleans
    deliberately read "absent" as "not met" for the headline, but a red-flag section
    must never fabricate a breach from a missing number — an absent KPI raises no flag
    here (the #657 fabricated-breach lesson applied to the report layer).
    """
    flags: List[RedFlag] = []

    min_dscr = kpis.get("min_dscr")
    if min_dscr is not None and not verdict.dscr_covenant_met:
        flags.append(
            RedFlag(
                kind="covenant_breach",
                severity="high",
                detail=f"Minimum DSCR {min_dscr:.2f}x breaches the lender floor.",
                source="engine KPI min_dscr vs configured DSCR covenant",
            )
        )

    balloon_pct = kpis.get("balloon_pct")
    balloon_breach = kpis.get("balloon_covenant_breach")
    if (
        balloon_breach is not None or balloon_pct is not None
    ) and not verdict.balloon_within_limit:
        if balloon_breach is not None:
            # The engine judged it against the scenario's own covenant (CCCDIR).
            detail = (
                "Balloon/bullet share BREACHES the modeled refinance-risk covenant"
                + (
                    f" ({balloon_pct * 100:.2f}% of debt)."
                    if balloon_pct is not None
                    else "."
                )
            )
            source = "engine flag balloon_covenant_breach"
        else:
            # balloon_breach is None here, so the outer guard implies balloon_pct
            # is not None; the explicit narrowing is for the type checker.
            assert balloon_pct is not None
            detail = (
                f"Balloon/bullet share {balloon_pct * 100:.2f}% exceeds the "
                "report refinance-risk ceiling."
            )
            source = "engine KPI balloon_pct vs report covenant ceiling"
        flags.append(
            RedFlag(
                kind="covenant_breach", severity="high", detail=detail, source=source
            )
        )

    equity_irr = kpis.get("equity_irr")
    equity_npv = kpis.get("equity_npv")
    negative_parts: List[str] = []
    # Strict < 0 (matching the NPV part below): a break-even equity IRR of exactly
    # 0.0 — reachable from a genuine break-even waterfall (finance/irr.py returns
    # 0.0) or the metrics 0.0 no-waterfall sentinel — is NOT negative, so the flag
    # must not print "equity IRR 0.00% is negative" (a literal falsehood that could
    # co-render with a Bankable headline).
    if equity_irr is not None and equity_irr < 0:
        negative_parts.append(f"equity IRR {equity_irr * 100:.2f}% is negative")
    if equity_npv is not None and equity_npv < 0:
        negative_parts.append(f"equity NPV {fmt_usd(equity_npv)} is negative")
    if negative_parts:
        flags.append(
            RedFlag(
                kind="negative_equity",
                severity="high",
                detail="Sponsor returns: " + " and ".join(negative_parts) + ".",
                source="engine KPIs equity_irr / equity_npv",
            )
        )

    project_irr = kpis.get("project_irr")
    hurdle = kpis.get("discount_rate_used")
    if project_irr is not None and hurdle is not None and not verdict.project_viable:
        flags.append(
            RedFlag(
                kind="below_hurdle",
                severity="high",
                detail=(
                    f"Project IRR {project_irr * 100:.2f}% is below the "
                    f"{hurdle * 100:.2f}% cost of capital."
                ),
                source="engine KPIs project_irr vs discount_rate_used",
            )
        )

    cp_outstanding = 0
    cp_by_ws: Dict[str, int] = {}
    if scenario_config is not None:
        # build_cp_report is the tolerant builder, but it still raises on a
        # structurally malformed conditions_precedent.items container. Degrade to
        # "no CP block" on that (like the other best-effort report inputs —
        # tornado/global_sa/evidence are None-on-failure) rather than break the whole
        # report; production configs are validated upstream so this never fires there.
        cp_report: Optional[CpReport]
        try:
            cp_report = build_cp_report(scenario_config)
        except ValueError:
            # ConditionsPrecedentError (malformed items) AND a plain ValueError from a
            # non-bool enforce/require_complete flag both degrade to no CP contribution
            # (matches _build_evidence and _build_cp_checklist) — never crash the report.
            cp_report = None
    else:
        cp_report = None
    if cp_report is not None:
        cp_outstanding = cp_report.n_outstanding
        cp_by_ws = dict(cp_report.by_workstream_outstanding)
        if cp_outstanding > 0:
            per_ws = ", ".join(f"{ws}: {n}" for ws, n in sorted(cp_by_ws.items()))
            flags.append(
                RedFlag(
                    kind="cp_outstanding",
                    severity="medium",
                    detail=(
                        f"{cp_outstanding} condition(s) precedent outstanding "
                        f"({per_ws}) — first drawdown is gated."
                    ),
                    source="conditions_precedent checklist (scenario register)",
                )
            )

    readiness_reds = [r.workstream for r in readiness_rows if r.status == "red"]
    if readiness_reds:
        flags.append(
            RedFlag(
                kind="readiness_red",
                severity="medium",
                detail=(
                    "Development readiness RED in: " + ", ".join(readiness_reds) + "."
                ),
                source="development_readiness register (scenario register)",
            )
        )

    return IcSummaryBlock(
        headline=verdict.headline,
        red_flags=flags,
        cp_outstanding=cp_outstanding,
        cp_outstanding_by_workstream=cp_by_ws,
        readiness_reds=readiness_reds,
    )


#: Wizard assumption label -> (evidence-register key for source/as-of cross-ref, impact note).
#: The impact is the KPI/driver the assumption most directly moves — grounded in the model's
#: sensitivity structure (tariff/resource dominate; capex drives gearing; FX erodes LKR revenue),
#: NOT a live recompute. A ``None`` key means no material assumption maps to the line, so its
#: source/as-of stay blank rather than borrowing an unrelated register entry.
_ASSUMPTION_META: Dict[str, tuple[Optional[str], str]] = {
    "Capacity factor": ("capacity_factor", "Net AEP, hence revenue (P50/P90)"),
    "PPA tariff": ("tariff", "Revenue — the dominant value driver"),
    "PPA term": (None, "Revenue horizon / merchant-tail exposure"),
    "Total CAPEX": ("capex", "Gearing, debt sizing, project IRR"),
    "Annual OPEX": ("opex", "CFADS, hence DSCR"),
    "FX (start)": ("fx", "USD value of LKR-denominated revenue"),
    "Installed capacity": (None, "Scales gross AEP and capex"),
    "Project life": (None, "Operating horizon for NPV / IRR"),
}


def _evidence_lookup(
    scenario_config: Optional[Mapping[str, Any]],
) -> Dict[str, Mapping[str, Any]]:
    """Best-effort ``{material-assumption -> {source, as_of, ...}}`` from the scenario register.

    Returns ``{}`` when no scenario config is supplied or the register is malformed, so the
    assumptions table shows no source/as-of (em-dash) rather than failing the whole report.
    """
    if scenario_config is None:
        return {}
    try:
        report = build_evidence_report(scenario_config)
    except ValueError:
        # EvidenceRegisterError is a ValueError, but build_evidence_report also raises a plain
        # ValueError on a bad min_tier / malformed taxonomy — catch both so a malformed register
        # truly degrades to no source/as-of (em-dash) rather than failing the whole report.
        return {}
    return {
        name: rec for name, rec in report.entries.items() if isinstance(rec, Mapping)
    }


def _assumption_row(
    label: str, display: str, evidence: Mapping[str, Mapping[str, Any]]
) -> AssumptionRow:
    """Build one assumptions-register row, enriched with evidence source/as-of + an impact note.

    Source/as-of come from the scenario's evidence register ONLY where a material assumption maps
    to the line (no fabricated provenance — blank otherwise); the impact is the static,
    model-grounded note for the line.
    """
    key, impact = _ASSUMPTION_META.get(label, (None, ""))
    rec: Mapping[str, Any] = evidence.get(key, {}) if key is not None else {}
    return AssumptionRow(
        label=label,
        display=display,
        source=str(rec.get("source", "")),
        as_of=str(rec.get("as_of", "")),
        impact=impact,
    )


def _build_assumptions(
    inputs: Optional[WindFarmInputs],
    scenario_config: Optional[Mapping[str, Any]] = None,
) -> List[AssumptionRow]:
    """Render the wizard inputs as an assumptions register (value · source · as-of · impact).

    Source and as-of are cross-referenced from the scenario's evidence register where a material
    assumption maps to the line (no fabricated provenance — blank where none is declared); the
    impact is a static, model-grounded note of the KPI each assumption most directly moves.
    """
    if inputs is None:
        return []
    evidence = _evidence_lookup(scenario_config)
    rows = [
        _assumption_row("Site", inputs.site_name, evidence),
        _assumption_row("Installed capacity", f"{inputs.capacity_mw:g} MW", evidence),
        _assumption_row(
            "Capacity factor", f"{inputs.capacity_factor * 100:.1f}%", evidence
        ),
        _assumption_row("Project life", f"{inputs.project_life_years} years", evidence),
        _assumption_row(
            "PPA tariff", f"LKR {inputs.ppa_price_lkr_per_kwh:g}/kWh", evidence
        ),
        _assumption_row("PPA term", f"{inputs.ppa_term_years} years", evidence),
        _assumption_row("Total CAPEX", f"${inputs.capex_total_usd:,.0f}", evidence),
        _assumption_row("Annual OPEX", f"${inputs.opex_annual_usd:,.0f}", evidence),
        _assumption_row(
            "FX (start)", f"LKR {inputs.fx_start_lkr_per_usd:g}/USD", evidence
        ),
    ]
    if inputs.location is not None:
        rows.insert(1, _assumption_row("Location", inputs.location, evidence))
    return rows


def _build_risk_register(risks: List[RiskItem]) -> List[RiskRow]:
    """Project the config-authored risk register into render-ready rows (pure passthrough)."""
    return [
        RiskRow(
            category=r.category,
            risk=r.risk,
            mitigation=r.mitigation,
            severity=r.severity,
            climate_risk_category=r.climate_risk_category,
        )
        for r in risks
    ]


def _build_model_limitations(limits: List[LimitationItem]) -> List[LimitationRow]:
    """Project the config-authored model limitations into render-ready rows (#734, passthrough)."""
    return [LimitationRow(topic=lim.topic, detail=lim.detail) for lim in limits]


def _build_readiness(
    scenario_config: Optional[Mapping[str, Any]],
) -> tuple[List[ReadinessRow], Optional[str]]:
    """Project a scenario's development-readiness register into rows + an overall RAG.

    Reads the register from the SCENARIO config (where the per-workstream R/A/G statuses
    live) via the canonical :func:`analytics.development_readiness.build_readiness_report`.
    Returns ([], None) when no scenario config is supplied or none is declared — so existing
    callers (which pass no scenario config) render no readiness section. Pure presentation.
    """
    if scenario_config is None:
        return [], None
    report = build_readiness_report(scenario_config)
    rows = [
        ReadinessRow(workstream=i.workstream, status=i.status, note=i.note)
        for i in report.items
    ]
    return rows, report.overall_status


def _build_cp_checklist(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[CpChecklistBlock]:
    """Project the conditions-precedent checklist into a report block (#708).

    Reads the declared CP items via the canonical
    :func:`analytics.conditions_precedent.build_cp_report` and renders the full checklist
    (each item's satisfied/waived/pending status) plus the outstanding rollup. Returns
    ``None`` when no scenario config is supplied, none is declared, or the checklist is
    structurally malformed — the section is then omitted. Pure presentation; the IC red-flag
    block (#706) surfaces only the outstanding COUNT, this is the full line-item table.
    """
    if scenario_config is None:
        return None
    try:
        report = build_cp_report(scenario_config)
    except ValueError:
        # ConditionsPrecedentError (malformed items container) AND a plain ValueError from
        # a non-bool enforce/require_complete flag both degrade to no section, matching the
        # sibling _build_evidence — the report never crashes on a malformed CP block.
        return None
    # Render when the scenario declared a checklist — valid items OR flagged declarations
    # (an off-scale/typo'd status is dropped from `items` but must still surface, never
    # vanish). A scenario that authored no CP block has neither, so it gets no section
    # (committed lender reports unchanged); `missing` alone can't signal "declared".
    if not report.items and not report.findings:
        return None
    # Declared conditions the register flagged (unknown item, off-scale status, missing
    # status) — NOT the `incomplete` findings, which are the already-listed missing items.
    flagged = sorted({f.item for f in report.findings if f.kind != "incomplete"})
    return CpChecklistBlock(
        rows=[
            CpItemRow(
                name=i.name,
                workstream=i.workstream,
                status=i.status,
                note=i.note,
                waived_reason=i.waived_reason,
            )
            for i in report.items
        ],
        n_outstanding=report.n_outstanding,
        n_satisfied=report.n_satisfied,
        n_waived=report.n_waived,
        missing=list(report.missing),
        flagged=flagged,
        is_clean=report.is_clean,
        all_satisfied=report.all_satisfied,
    )


def _build_feasibility_sections(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[FeasibilitySectionsBlock]:
    """Project the feasibility-report section coverage into a report block (#708 / #705).

    Reads the declared section coverage via the canonical
    :func:`analytics.feasibility_sections.build_feasibility_report` (the 20-section skeleton)
    and renders the declared sections in report order plus the complete/draft/not-applicable
    counts and the missing set. Returns ``None`` when no scenario config is supplied, none is
    declared, or the declaration is structurally malformed — the section is then omitted.
    Pure presentation.
    """
    if scenario_config is None:
        return None
    try:
        report = build_feasibility_report(scenario_config)
    except ValueError:
        # FeasibilitySectionsError (malformed sections container) AND a plain ValueError from
        # a non-bool enforce/require_complete flag both degrade to no section (as _build_evidence).
        return None
    # Render when the scenario declared sections — valid OR flagged (a dropped off-scale
    # status must still surface). No declaration at all -> no section.
    if not report.sections and not report.findings:
        return None
    flagged = sorted({f.section for f in report.findings if f.kind != "incomplete"})
    return FeasibilitySectionsBlock(
        rows=[
            FeasibilitySectionRow(
                name=s.name, title=s.title, group=s.group, status=s.status
            )
            for s in report.sections
        ],
        n_complete=report.n_complete,
        n_draft=report.n_draft,
        n_not_applicable=report.n_not_applicable,
        missing=list(report.missing),
        flagged=flagged,
        # covered (canonical-declared) + missing (canonical-not-declared) = the full fixed
        # skeleton, INCLUDING a declared item dropped for a bad status — so "of N" is never
        # understated (report.sections would drop it and show 19 of a 20-section skeleton).
        total=len(report.covered) + len(report.missing),
        is_clean=report.is_clean,
        all_complete=report.all_complete,
    )


def _build_evidence(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[EvidenceBlock]:
    """Project a scenario's assumption-evidence register into a report block (#435).

    Reads ``evidence_register.entries`` (assumption → source/as-of/tier) via the canonical
    :func:`analytics.evidence_register.build_evidence_report`, and reports how many of the
    material assumptions carry declared evidence (the ``missing`` set is the lender gap).
    Returns ``None`` when no scenario config is supplied (legacy callers) or the register
    is structurally malformed — the section is then omitted. Pure presentation.
    """
    if scenario_config is None:
        return None
    try:
        report = build_evidence_report(scenario_config)
    except ValueError:
        # As in _evidence_lookup: a malformed register (incl. a bad min_tier / taxonomy that
        # raises a plain ValueError, not just EvidenceRegisterError) degrades to no section.
        return None
    rows = [
        EvidenceRow(
            assumption=name,
            source=str(rec.get("source", "")),
            as_of=str(rec.get("as_of", "")),
            tier=str(rec.get("tier", "")),
            note=str(rec.get("note", "")),
        )
        for name, rec in report.entries.items()
        if isinstance(rec, Mapping)
    ]
    covered = len(report.covered)
    return EvidenceBlock(
        rows=rows,
        missing=list(report.missing),
        covered=covered,
        total=covered + len(report.missing),
    )


def _build_evidence_score(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[EvidenceScoreBlock]:
    """Project the bankability evidence-completeness score into a report block (#707).

    Reads the score via the canonical :func:`analytics.evidence_score.build_evidence_score`
    (config-weighted tier strength over the evidence-register coverage). Returns ``None``
    when no scenario config is supplied (legacy callers) or the register/weights config is
    malformed — the section is then omitted, exactly like :func:`_build_evidence`. Pure
    presentation; recomputes no finance metric.
    """
    if scenario_config is None:
        return None
    try:
        score = build_evidence_score(scenario_config)
    except ValueError:
        # A malformed register or a drifted evidence_score.yaml raises a plain ValueError;
        # degrade to no section rather than break the report (mirrors _build_evidence).
        return None
    return EvidenceScoreBlock(
        score=score.score,
        band=score.band,
        covered=score.n_covered,
        total=score.n_total,
        missing=list(score.missing),
        coverage_pct=round(100.0 * score.coverage_fraction, 2),
        mean_covered_strength=score.mean_covered_strength,
        rows=[
            EvidenceScoreRow(
                assumption=a.assumption,
                tier=a.tier,
                strength=a.strength,
                covered=a.covered,
            )
            for a in score.assumptions
        ],
    )


def _build_finance_blocks(
    case_result: CaseResult,
    scenario_config: Optional[Mapping[str, Any]],
    debt_result: Optional[Mapping[str, Any]],
) -> Optional[FinanceReportBlocks]:
    """Serialise the quantitative finance blocks for the report, or None (RPT-1).

    Returns None when either the scenario config or the debt result is absent — the
    legacy KPI-only report path passes neither, so those sections stay unrendered
    rather than showing empty tables.
    """
    if scenario_config is None or debt_result is None:
        return None
    return extract_finance_report_blocks(scenario_config, debt_result, case_result.kpis)


def _build_capital_risk(
    capital_risk: Optional[CapitalRiskReport],
) -> Optional[CapitalRiskBlock]:
    """Project a pre-computed capital-risk report into a report block (#776 / #657).

    Read-only projection of :class:`analytics.capital_risk_layer_v14.CapitalRiskReport`: the
    covenant-breach probabilities + floors, the probability-below-hurdle, the per-metric
    VaR/CVaR for the four return metrics, and the NPV-distribution chart path. The Monte-Carlo
    that produces the report is heavy, so it is run OUT-OF-BAND and passed in (like the
    tornado / global-SA blocks); ``None`` (the default) omits the section. Pure presentation —
    recomputes no risk number, only reshapes the report's own values for the template.
    """
    if capital_risk is None:
        return None
    cb = capital_risk.tail_report.covenant_breaches
    thresholds = cb.thresholds
    metrics = [
        CapitalRiskMetricRow(
            metric=summary.metric_name,
            # IRR metrics are ratios (shown as %), NPV metrics are USD — so the template
            # never renders a dollar VaR and an IRR VaR in one unit-less column.
            unit="usd" if "npv" in summary.metric_name else "pct",
            mean=summary.mean,
            var=summary.var_cvar.var,
            cvar=summary.var_cvar.cvar,
            var_label=summary.var_cvar.var_label,
            cvar_label=summary.var_cvar.cvar_label,
        )
        for summary in (
            capital_risk.tail_report.equity_irr,
            capital_risk.tail_report.project_irr,
            capital_risk.tail_report.equity_npv,
            capital_risk.tail_report.project_npv,
        )
    ]
    png_path = Path(str(capital_risk.npv_distribution_png))
    img = _png_data_uri(png_path)
    return CapitalRiskBlock(
        scenario=capital_risk.scenario,
        model_version=capital_risk.model_version,
        method=capital_risk.method,
        n_trials=capital_risk.n_trials,
        dscr_breach_probability=cb.dscr_breach_probability,
        llcr_breach_probability=cb.llcr_breach_probability,
        plcr_breach_probability=cb.plcr_breach_probability,
        dscr_floor=float(thresholds.get("min_dscr", 0.0)),
        llcr_floor=float(thresholds.get("min_llcr", 0.0)),
        plcr_floor=float(thresholds.get("min_plcr", 0.0)),
        probability_below_hurdle=capital_risk.tail_report.probability_below_hurdle,
        target_equity_irr=capital_risk.tail_report.target_equity_irr,
        metrics=metrics,
        npv_distribution_filename=png_path.name,
        npv_distribution_img=img,
    )


def _finite_or_none(value: float) -> Optional[float]:
    """Map a non-finite (NaN / inf) cell to ``None`` so the template renders an em-dash.

    A failed interaction cell must never be zero-filled or silently substituted (#657): ``None``
    surfaces as an em-dash and is separately counted in the block's ``n_failed_cells`` disclosure.
    """
    return value if math.isfinite(value) else None


def _build_interaction_grid(
    interaction_grid: Optional[TwoFactorInteractionGrid],
) -> Optional[InteractionGridBlock]:
    """Project a pre-computed two-factor interaction grid into a report block (#739 slice-2).

    Read-only, heatmap-ready projection of
    :class:`analytics.contracts_v14.TwoFactorInteractionGrid`: each cell carries the raw metric,
    the interaction (deviation from one-way additivity, in the metric's units), and a signed
    heatmap intensity (interaction normalised by ``max_abs_interaction``, in ``[-1, 1]``). The
    N×M grid is heavy (each cell is a full pipeline evaluation), so it is computed OUT-OF-BAND
    and passed in (like the tornado / capital-risk blocks); ``None`` (the default) omits the
    section. Pure presentation — recomputes no metric, only reshapes the grid's own values and
    surfaces its honesty metadata (failed cells, base mismatch, unresolved drivers) as first-class
    fields the template always discloses (#657).
    """
    if interaction_grid is None:
        return None
    grid = interaction_grid
    meta = grid.metadata
    max_abs = float(grid.max_abs_interaction)
    # A ratio/return metric (IRR) renders as a percentage; an NPV metric renders as USD. Same
    # unit convention as CapitalRiskMetricRow so the template never mixes a dollar and a ratio.
    is_ratio = "npv" not in grid.metric_name.lower()

    rows: List[InteractionGridRow] = []
    for i, row_label in enumerate(grid.a_labels):
        cells: List[InteractionGridCell] = []
        for j in range(len(grid.b_labels)):
            raw = _finite_or_none(float(grid.values[i][j]))
            inter = _finite_or_none(float(grid.interaction[i][j]))
            # Signed heatmap shade in [-1, 1]; None (neutral) for a failed cell or a flat grid.
            if inter is None or max_abs <= 0.0:
                intensity: Optional[float] = None
            else:
                intensity = max(-1.0, min(1.0, inter / max_abs))
            cells.append(
                InteractionGridCell(value=raw, interaction=inter, intensity=intensity)
            )
        rows.append(InteractionGridRow(label=row_label, cells=cells))

    return InteractionGridBlock(
        metric_name=grid.metric_name,
        param_a_name=grid.param_a_name,
        param_b_name=grid.param_b_name,
        param_a_label=str(meta.get("param_a_label", grid.param_a_name)),
        param_b_label=str(meta.get("param_b_label", grid.param_b_name)),
        b_labels=list(grid.b_labels),
        rows=rows,
        base_metric=float(grid.base_metric),
        max_abs_interaction=max_abs,
        is_ratio_metric=is_ratio,
        n_failed_cells=int(meta.get("n_failed_cells", 0)),
        base_mismatch=bool(meta.get("base_mismatch", False)),
        unresolved_drivers=list(meta.get("unresolved_drivers", []) or []),
        n_evaluations=int(meta.get("n_evaluations", 0)),
        base_config_path=str(meta.get("base_config_path", "<unknown>")),
    )


def _png_data_uri(path: Path) -> Optional[str]:
    """A base64 ``data:image/png`` URI for an existing PNG (self-contained embed), else None.

    Embedding the chart keeps the lender report self-contained and avoids leaking the
    server's absolute filesystem path into the document (MRM). Returns None when the file is
    absent (e.g. matplotlib degraded, no chart written) or unreadable — the section then
    renders without an image rather than a broken reference.
    """
    try:
        if not path.is_file():
            return None
        import base64

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except OSError:
        return None


def _build_multi_tech(
    case_result: CaseResult,
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[MultiTechBlock]:
    """Project a hybrid's per-technology production/economics into a report block (ARCH-4).

    Reuses the additive multi-tech generation view (``build_multi_tech_from_run``, ARCH-2)
    and the per-tech cost/return work-breakdown (``build_multi_tech_wbs``, ARCH-3). Returns
    ``None`` for legacy callers (no scenario config) and for single-technology plants (fewer
    than two generation technologies) — the section is then omitted. Pure presentation; the
    WBS build is best-effort (a malformed per-tech over-attribution degrades to the
    generation-only view rather than failing the whole report).
    """
    if scenario_config is None:
        return None
    result, breakdown = build_multi_tech_from_run(case_result.kpis, scenario_config)
    if result is None or breakdown is None or len(result.technologies) < 2:
        return None

    breakdown_by_tech = {row.technology: row for row in breakdown}

    # Per-tech CAPEX/OPEX/cost-of-equity from the ARCH-3 work-breakdown (best-effort).
    wbs = None
    try:
        wbs = build_multi_tech_wbs(
            scenario_config,
            project_wacc_nominal=case_result.kpis.get("discount_rate_used"),
        )
    except ValueError:
        wbs = None
    wbs_by_tech = dict(wbs.technologies) if wbs is not None else {}

    rows: List[MultiTechRow] = []
    for tech, profile in result.technologies.items():
        bd = breakdown_by_tech.get(tech)
        w = wbs_by_tech.get(tech)
        capex_usd = w.capex_usd if w is not None else None
        rows.append(
            MultiTechRow(
                technology=tech,
                aep_gwh=profile.annual_aep_kwh / 1_000_000.0,
                share_of_aep_pct=bd.share_of_aep_pct if bd is not None else None,
                share_of_cfads_pct=bd.share_of_cfads_pct if bd is not None else None,
                capex_usd=capex_usd,
                # Couple the CAPEX share to the CAPEX value: when the work-breakdown is
                # absent/degraded (capex_usd None) suppress the share too, so the column is
                # not a populated % beside an em-dash dollar figure.
                share_of_capex_pct=(
                    bd.share_of_capex_pct
                    if bd is not None and capex_usd is not None
                    else None
                ),
                opex_usd_per_year=w.opex_usd_per_year if w is not None else None,
                cost_of_equity=w.cost_of_equity if w is not None else None,
                wacc_basis=w.wacc_basis if w is not None else "blended",
            )
        )

    # Shared-POI curtailment (ARCH-5): opt-in; None unless a POI limit + hourly profiles
    # are declared, so committed scenarios omit it.
    curtailment = resolve_shared_poi_curtailment(scenario_config)

    return MultiTechBlock(
        rows=rows,
        total_aep_gwh=result.total_aep_kwh / 1_000_000.0,
        financed_capex_usd=wbs.financed_capex_usd if wbs is not None else None,
        allocated_capex_usd=wbs.allocated_capex_usd if wbs is not None else None,
        capex_residual_usd=wbs.capex_residual_usd if wbs is not None else None,
        capex_reconciled=wbs.capex_reconciled if wbs is not None else False,
        project_wacc_nominal=wbs.project_wacc_nominal if wbs is not None else None,
        poi_limit_mw=curtailment.poi_limit_mw if curtailment is not None else None,
        poi_curtailment_pct=(
            curtailment.curtailment_pct if curtailment is not None else None
        ),
        poi_curtailed_energy_mwh=(
            curtailment.curtailed_energy_mwh if curtailment is not None else None
        ),
    )


def _build_three_statement_result(
    scenario_config: Optional[Mapping[str, Any]],
    debt_result: Optional[Mapping[str, Any]],
    annual_rows: Optional[Sequence[Mapping[str, Any]]],
) -> Optional[ThreeStatementResult]:
    """Assemble the three-statement result once, shared by the statements + waterfall blocks.

    Reuses ``analytics.three_statement.build_three_statement_from_run``. Returns ``None`` when
    the caller supplies no ``annual_rows`` / ``debt_result`` / ``scenario_config`` (legacy
    KPI-only path) or the statements do not tie out — the dependent sections are then omitted.
    """
    if scenario_config is None or debt_result is None or not annual_rows:
        return None
    result = build_three_statement_from_run(
        {"annual_rows": list(annual_rows), "debt_result": dict(debt_result)},
        scenario_config,
    )
    if result is None or result.tie_outs is None:
        return None
    return result


def _three_statement_block(
    result: Optional[ThreeStatementResult],
) -> Optional[ThreeStatementBlock]:
    """Project an assembled three-statement result into its report block (#479)."""
    if result is None or result.tie_outs is None:
        return None
    payload = result.to_dict()
    t = result.tie_outs
    return ThreeStatementBlock(
        currency=result.currency,
        tie_outs_pass=t.all_pass,
        balance_sheet_balances=t.balance_sheet_balances,
        debt_retires_to_residual=t.debt_retires_to_residual,
        cashflow_reconciles=t.cashflow_reconciles,
        retained_earnings_rolls=t.retained_earnings_rolls,
        max_abs_balance_residual=t.max_abs_balance_residual,
        income_statement=payload["income_statement"],
        cash_flow=payload["cash_flow"],
        balance_sheet=payload["balance_sheet"],
    )


def _waterfall_block(
    result: Optional[ThreeStatementResult],
    annual_rows: Optional[Sequence[Mapping[str, Any]]],
) -> Optional[WaterfallBlock]:
    """Project the cash-flow waterfall (by payment priority) into a report block (#481, RPT-2).

    Built from the engine's published per-row figures (``build_cashflow_waterfall``), so every line
    ties to the rest of the report (CCCDIR — one source of truth; the CFADS and scheduled debt
    service match the headline KPI and the DSCR-profile section). Gated on the three-statement
    result so it co-renders with the statements (both depend on the enriched ``annual_rows``);
    ``None`` on the legacy KPI-only path — the section is then omitted.
    """
    if result is None or not annual_rows:
        return None
    wf = build_cashflow_waterfall(annual_rows)
    return WaterfallBlock(
        currency=wf.currency,
        rows=[
            WaterfallRow(
                year=r.year,
                cfads=r.cfads,
                scheduled_debt_service=r.scheduled_debt_service,
                balloon_sweep=r.balloon_sweep,
                cash_to_equity=r.cash_to_equity,
            )
            for r in wf.rows
        ],
        total_cfads=wf.total_cfads,
        total_scheduled_debt_service=wf.total_scheduled_debt_service,
        total_balloon_sweep=wf.total_balloon_sweep,
        total_cash_to_equity=wf.total_cash_to_equity,
    )


def _build_resource_trend(
    analysis: Optional[Mapping[str, Any]],
) -> Optional[ResourceTrendBlock]:
    """Project a live long-term-trend analysis into its report block (#178 → #656).

    Consumes the dict returned by
    :func:`wind_resource.long_term_trend.analyze_long_term_resource` — its ``trend``
    (:class:`~wind_resource.long_term_trend.TrendResult`), ``recommendation``, ``markdown`` and
    ``summary_df``. Nothing is re-derived here (CCCDIR — one source of truth): the narrative is
    the analysis's own ``markdown`` and the table is its own ``summary_df``. Returns ``None`` when
    no analysis is supplied (every existing report caller passes none), so the section is omitted
    and the rendered report is byte-identical. Report/VALIDATE-only: the recommended forward P50
    basis is disclosed, never applied to the committed/frozen scenario P50.
    """
    if analysis is None:
        return None
    trend = analysis["trend"]
    rec = analysis["recommendation"]
    summary_df = analysis["summary_df"]
    summary_rows = [
        ResourceTrendRow(metric=str(m), value=str(v))
        for m, v in zip(summary_df["Metric"], summary_df["Value"], strict=True)
    ]
    return ResourceTrendBlock(
        markdown=str(analysis["markdown"]),
        summary_rows=summary_rows,
        reference_period=f"{trend.start_year}-{trend.end_year} ({trend.n_years} yr)",
        classification=trend.classification.replace("_", " "),
        classification_note=trend.classification_note,
        trend_significant=bool(trend.significant),
        mk_tau=float(trend.mk_tau),
        mk_pvalue=float(trend.mk_pvalue),
        sen_slope_per_decade=float(trend.sen_slope_per_decade),
        ols_r2=float(trend.ols_r2),
        recommended_basis=str(rec["central_basis"]).replace("_", " "),
        recommended_p50_gwh=rec.get("p50_gwh"),
        recommended_p50_cf=rec.get("p50_cf"),
        downside_p50_gwh=rec.get("downside_gwh"),
        upside_p50_gwh=rec.get("upside_gwh"),
    )


def _build_fx_fallback_note(run_result: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Surface the run's SILENT FX fallbacks into the report (#785).

    Distinct from :func:`_build_fx_warning` (the #736 failure path): here FX
    integration SUCCEEDED, but the pipeline's ``fx_integration.degraded_reasons``
    records that one or more FX surfaces were built from stale/default
    substitutions (malformed fx block, flat-curve fallback, degenerate risk
    profile). Plausible-looking numbers on defaulted inputs are more dangerous
    than an outright failure, so they get their own explicit note. ``None`` when
    no fallback fired (render-when-present — the committed scenarios take no
    fallback, so healthy reports are byte-identical).
    """
    if not run_result:
        return None
    fx = run_result.get("fx_integration")
    if not isinstance(fx, Mapping):
        return None
    # A run whose integration ultimately FAILED renders the #736 failure banner;
    # this note must not simultaneously claim the integration "completed" (a
    # direct contradiction in a lender document). Reasons collected before the
    # failure are still available in the block for diagnostics.
    if fx.get("succeeded") is not True:
        return None
    reasons = fx.get("degraded_reasons")
    if not isinstance(reasons, (list, tuple)) or not reasons:
        return None
    joined = "; ".join(str(r) for r in reasons)
    return (
        "FX integration completed on FALLBACK inputs — the figures below look "
        f"normal but rest on default substitutions: {joined}. Supply the missing "
        "FX configuration for a lender-grade FX view."
    )


def _build_fx_warning(run_result: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Surface the run's FX-integration failure warning into the report (#736).

    The pipeline records an ``fx_integration`` status block on its result; when integration
    failed it carries a human ``warning`` (a log-only event before this). Returns that string so
    the report renders an explicit banner, or ``None`` when FX integration succeeded / was not
    reported (banner omitted — render-when-present, so a healthy run is byte-identical).
    """
    if not run_result:
        return None
    fx = run_result.get("fx_integration")
    if not isinstance(fx, Mapping):
        return None
    warning = fx.get("warning")
    return str(warning) if warning else None


def _irr_bridge_block(
    run_result: Optional[Mapping[str, Any]],
) -> Optional[IrrBridgeBlock]:
    """Project the project→equity IRR bridge into a report block (#621, IC disclosure).

    Built from the engine's published surface via
    ``analytics.irr_bridge.build_project_equity_irr_bridge_from_run`` (project/equity IRR are the
    headline KPIs; the legs only explain the gap — CCCDIR one source of truth). ``None`` when the
    caller supplies no full run result, or the run lacks a computed equity distribution / resolvable
    project cost — the section is then omitted (additive, default-off).
    """
    if not run_result:
        return None
    bridge: Optional[ProjectEquityIrrBridge] = build_project_equity_irr_bridge_from_run(
        run_result
    )
    if bridge is None:
        return None
    residual_label = str(
        bridge.metadata.get("residual_label", "cashflow_timing_and_interaction")
    )
    return IrrBridgeBlock(
        currency=bridge.currency,
        project_irr=bridge.project_irr,
        equity_irr=bridge.equity_irr,
        total_uplift=bridge.total_uplift,
        legs=[
            IrrBridgeLeg(
                name=leg.name,
                contribution=leg.contribution,
                irr_after=leg.irr_after,
                detail=leg.detail,
            )
            for leg in bridge.components
        ],
        residual=bridge.residual,
        residual_label=residual_label,
        reconciled=bridge.reconciled,
    )


def _resolve_report_grade(
    scenario_config: Optional[Mapping[str, Any]],
) -> Optional[str]:
    """Return the declared run-mode grade stamp for the report, or ``None`` (#733c).

    Reads the scenario's declared ``run.mode`` / ``run_mode`` via the single
    ``analytics.run_modes`` contract and returns that mode's ``report_grade`` (the
    same policy the #733b debt-engine ceiling reads). An undeclared mode returns
    ``None`` — the report carries no grade stamp and is byte-identical to a
    pre-#733c report. A malformed declaration fails loud in ``resolve_run_mode``
    (already the schema-guard behaviour), so the report never silently mis-grades.
    """
    if not scenario_config:
        return None
    from analytics.run_modes import POLICIES, resolve_run_mode

    mode = resolve_run_mode(scenario_config)
    return POLICIES[mode].report_grade if mode is not None else None


def build_report_context(
    case_result: CaseResult,
    *,
    generated_at: str,
    inputs: Optional[WindFarmInputs] = None,
    config: Optional[ReportConfig] = None,
    scenario_config: Optional[Mapping[str, Any]] = None,
    debt_result: Optional[Mapping[str, Any]] = None,
    annual_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    tornado: Optional[TornadoBlock] = None,
    global_sa: Optional[GlobalSABlock] = None,
    global_sa_pawn: Optional[GlobalSABlock] = None,
    capital_risk: Optional[CapitalRiskReport] = None,
    interaction_grid: Optional[TwoFactorInteractionGrid] = None,
    resource_trend: Optional[Mapping[str, Any]] = None,
    run_result: Optional[Mapping[str, Any]] = None,
) -> ReportContext:
    """Assemble a :class:`ReportContext` from a canonical case result.

    Args:
        case_result: The :class:`~app.api.responses.CaseResult` projection of a
            pipeline run (already filtered to numeric KPIs).
        generated_at: Caller-supplied timestamp string (kept out of this function
            for deterministic tests).
        inputs: The originating wizard submission, used for the assumptions
            register. Optional.
        config: Presentation config; loaded from the committed default when
            omitted.
        scenario_config: The originating scenario config dict, used to surface the
            development-readiness / E&S register (#C11) and the production (P50/P90)
            and CAPEX blocks (RPT-1). Optional — omitted by legacy callers, in which
            case those sections are not rendered.
        debt_result: The pipeline run's ``debt_result`` mapping, used for the
            sources-and-uses and DSCR-profile sections (RPT-1). Optional; omitted by
            legacy callers.
        tornado: A pre-computed sensitivity tornado (RPT-1). Computed upstream (it runs
            a multi-shock sweep) and passed in so this builder stays pure; omitted or
            ``None`` when the best-effort sweep was skipped or failed.
        global_sa: A pre-computed global (Morris) sensitivity block (MC-1). Computed
            upstream (it runs a multi-evaluation screening) and passed in so this builder
            stays pure; ``None`` when the best-effort screening was skipped or failed.
        global_sa_pawn: A pre-computed global (PAWN, median-KS) sensitivity block (#645) —
            the distribution-based complement to the Morris screening. Computed upstream
            and passed in; ``None`` when the best-effort block was skipped or failed, in
            which case only that subsection is omitted.
        interaction_grid: A pre-computed two-factor sensitivity interaction grid (#739
            slice-2). The N×M grid is a full-pipeline evaluation per cell, so it is computed
            OUT-OF-BAND (never in the synchronous report route — the #645 latency ledger) and
            passed in; ``None`` (the default) omits the section, keeping every committed
            scenario and the API report byte-identical.
        resource_trend: A pre-computed long-term wind-resource & trend analysis (#178 →
            #656) — the dict from
            :func:`wind_resource.long_term_trend.analyze_long_term_resource`, run upstream
            from the live ERA5 series (it does its own resource I/O, so it is analyzed at the
            production edge and passed in to keep this builder pure). ``None`` for every
            existing caller (the API report routes supply no ERA5 series), in which case the
            section is omitted. Disclose-only — it never overwrites the committed/frozen P50.
        run_result: The full pipeline run result (``kpis`` / ``annual_rows`` /
            ``debt_result`` / ``equity_distribution``), used solely to build the additive
            project→equity IRR bridge (#621). Optional — ``None`` for legacy callers, in which
            case the bridge section is omitted (default-off).

    Returns:
        A fully populated :class:`ReportContext` ready for the renderer.
    """
    cfg = config if config is not None else load_report_config()
    readiness_rows, overall_readiness = _build_readiness(scenario_config)
    # The verdict is built once and shared: the IC summary reads its covenant/return
    # judgments (single source) rather than re-deriving them.
    verdict = _build_verdict(case_result.kpis, cfg.covenants)
    # Assemble the three-statement result once; both the statements and the payment-priority
    # waterfall blocks derive from it (one engine-output source, no second pass).
    ts_result = _build_three_statement_result(scenario_config, debt_result, annual_rows)
    return ReportContext(
        meta=cfg.report,
        covenants=cfg.covenants,
        generated_at=generated_at,
        report_grade=_resolve_report_grade(scenario_config),
        scenario_variant=case_result.scenario_variant,
        site_name=(
            inputs.site_name if inputs is not None else case_result.scenario_variant
        ),
        status=case_result.status,
        kpi_rows=_build_kpi_rows(case_result.kpis, cfg),
        verdict=verdict,
        ic_summary=_build_ic_summary(
            case_result.kpis, verdict, scenario_config, readiness_rows
        ),
        assumptions=_build_assumptions(inputs, scenario_config),
        risk_register=_build_risk_register(cfg.risk_register),
        model_limitations=_build_model_limitations(cfg.model_limitations),
        readiness=readiness_rows,
        overall_readiness=overall_readiness,
        cp_checklist=_build_cp_checklist(scenario_config),
        feasibility_sections=_build_feasibility_sections(scenario_config),
        finance=_build_finance_blocks(case_result, scenario_config, debt_result),
        tornado=tornado,
        global_sa=global_sa,
        global_sa_pawn=global_sa_pawn,
        capital_risk=_build_capital_risk(capital_risk),
        interaction_grid=_build_interaction_grid(interaction_grid),
        evidence=_build_evidence(scenario_config),
        evidence_score=_build_evidence_score(scenario_config),
        multi_tech=_build_multi_tech(case_result, scenario_config),
        three_statement=_three_statement_block(ts_result),
        cashflow_waterfall=_waterfall_block(ts_result, annual_rows),
        resource_trend=_build_resource_trend(resource_trend),
        irr_bridge=_irr_bridge_block(run_result),
        fx_warning=_build_fx_warning(run_result),
        fx_fallback_note=_build_fx_fallback_note(run_result),
        manifest=dict(case_result.run_manifest or {}),
    )
