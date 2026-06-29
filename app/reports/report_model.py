"""Report content model — projects a ``CaseResult`` into a render-ready context.

Pure presentation: this module formats KPI values per the config display spec
and flags them against lender covenants. It contains **no finance logic**
(Dolphin) — every number originates from the canonical pipeline run, and the
cost-of-capital hurdle is read from the run's own ``discount_rate_used`` KPI
rather than hardcoded. ``generated_at`` is supplied by the caller so the build is
deterministic and unit-testable (CASPER).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field

from analytics.development_readiness import build_readiness_report
from api.pipeline_api import FinanceReportBlocks, extract_finance_report_blocks
from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_config import (
    Covenants,
    KpiKind,
    ReportConfig,
    ReportMeta,
    RiskItem,
    load_report_config,
)


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


class KpiRow(BaseModel):
    """One rendered KPI line: raw value plus its formatted display string."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: float
    display: str


class AssumptionRow(BaseModel):
    """One assumptions-register line (label + formatted value)."""

    model_config = ConfigDict(extra="forbid")

    label: str
    display: str


class RiskRow(BaseModel):
    """One rendered risk-register line (category, risk, mitigation, residual severity)."""

    model_config = ConfigDict(extra="forbid")

    category: str
    risk: str
    mitigation: str
    severity: str  # low | medium | high — drives the badge class in the template


class ReadinessRow(BaseModel):
    """One rendered development-readiness line (workstream, R/A/G status, note)."""

    model_config = ConfigDict(extra="forbid")

    workstream: str
    status: str  # green | amber | red — drives the badge class in the template
    note: str = ""


class Verdict(BaseModel):
    """Covenant/return flags and a one-line headline, all config-thresholded."""

    model_config = ConfigDict(extra="forbid")

    headline: str
    project_viable: bool
    equity_positive: bool
    dscr_covenant_met: bool
    balloon_within_limit: bool
    notes: List[str] = Field(default_factory=list)


class ReportContext(BaseModel):
    """Everything the Jinja2 template needs to render the report."""

    model_config = ConfigDict(extra="forbid")

    meta: ReportMeta
    covenants: Covenants
    generated_at: str
    scenario_variant: str
    site_name: str
    status: str
    kpi_rows: List[KpiRow]
    verdict: Verdict
    assumptions: List[AssumptionRow]
    risk_register: List[RiskRow] = Field(default_factory=list)
    readiness: List[ReadinessRow] = Field(default_factory=list)
    overall_readiness: Optional[str] = None  # green | amber | red — worst declared status
    #: Serialised finance blocks (production P50/P90, sources-and-uses, DSCR profile,
    #: exec KPI callout) — RPT-1. None when the caller supplies no debt_result /
    #: scenario_config (e.g. the legacy KPI-only report path), in which case those
    #: quantitative sections are simply not rendered.
    finance: Optional[FinanceReportBlocks] = None
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
        # literally false statement (round-11 fix). Distinguish all three cases.
        if equity_irr <= 0:
            desc = "negative to sponsors"
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


def _build_assumptions(inputs: Optional[WindFarmInputs]) -> List[AssumptionRow]:
    """Render the wizard inputs as an assumptions register (when available)."""
    if inputs is None:
        return []
    rows = [
        AssumptionRow(label="Site", display=inputs.site_name),
        AssumptionRow(label="Installed capacity", display=f"{inputs.capacity_mw:g} MW"),
        AssumptionRow(
            label="Capacity factor", display=f"{inputs.capacity_factor * 100:.1f}%"
        ),
        AssumptionRow(
            label="Project life", display=f"{inputs.project_life_years} years"
        ),
        AssumptionRow(
            label="PPA tariff",
            display=f"LKR {inputs.ppa_price_lkr_per_kwh:g}/kWh",
        ),
        AssumptionRow(label="PPA term", display=f"{inputs.ppa_term_years} years"),
        AssumptionRow(
            label="Total CAPEX", display=f"${inputs.capex_total_usd:,.0f}"
        ),
        AssumptionRow(
            label="Annual OPEX", display=f"${inputs.opex_annual_usd:,.0f}"
        ),
        AssumptionRow(
            label="FX (start)",
            display=f"LKR {inputs.fx_start_lkr_per_usd:g}/USD",
        ),
    ]
    if inputs.location is not None:
        rows.insert(1, AssumptionRow(label="Location", display=inputs.location))
    return rows


def _build_risk_register(risks: List[RiskItem]) -> List[RiskRow]:
    """Project the config-authored risk register into render-ready rows (pure passthrough)."""
    return [
        RiskRow(
            category=r.category,
            risk=r.risk,
            mitigation=r.mitigation,
            severity=r.severity,
        )
        for r in risks
    ]


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


def build_report_context(
    case_result: CaseResult,
    *,
    generated_at: str,
    inputs: Optional[WindFarmInputs] = None,
    config: Optional[ReportConfig] = None,
    scenario_config: Optional[Mapping[str, Any]] = None,
    debt_result: Optional[Mapping[str, Any]] = None,
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

    Returns:
        A fully populated :class:`ReportContext` ready for the renderer.
    """
    cfg = config if config is not None else load_report_config()
    readiness_rows, overall_readiness = _build_readiness(scenario_config)
    return ReportContext(
        meta=cfg.report,
        covenants=cfg.covenants,
        generated_at=generated_at,
        scenario_variant=case_result.scenario_variant,
        site_name=inputs.site_name if inputs is not None else case_result.scenario_variant,
        status=case_result.status,
        kpi_rows=_build_kpi_rows(case_result.kpis, cfg),
        verdict=_build_verdict(case_result.kpis, cfg.covenants),
        assumptions=_build_assumptions(inputs),
        risk_register=_build_risk_register(cfg.risk_register),
        readiness=readiness_rows,
        overall_readiness=overall_readiness,
        finance=_build_finance_blocks(case_result, scenario_config, debt_result),
        manifest=dict(case_result.run_manifest or {}),
    )
