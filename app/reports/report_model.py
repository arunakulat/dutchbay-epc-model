"""Report content model — projects a ``CaseResult`` into a render-ready context.

Pure presentation: this module formats KPI values per the config display spec
and flags them against lender covenants. It contains **no finance logic**
(Dolphin) — every number originates from the canonical pipeline run, and the
cost-of-capital hurdle is read from the run's own ``discount_rate_used`` KPI
rather than hardcoded. ``generated_at`` is supplied by the caller so the build is
deterministic and unit-testable (CASPER).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.responses import CaseResult
from app.models.inputs import WindFarmInputs
from app.reports.report_config import (
    Covenants,
    KpiKind,
    ReportConfig,
    ReportMeta,
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
        sign = "positive" if equity_positive else "negative"
        notes.append(f"Equity IRR {equity_irr * 100:.2f}% — {sign} to sponsors.")
    if min_dscr is not None:
        rel = "meets" if dscr_covenant_met else "breaches"
        notes.append(
            f"Minimum DSCR {min_dscr:.2f}x {rel} the "
            f"{covenants.min_dscr_floor:.2f}x lender floor "
            f"(target {covenants.min_dscr_target:.2f}x)."
        )
    if balloon_pct is not None:
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


def build_report_context(
    case_result: CaseResult,
    *,
    generated_at: str,
    inputs: Optional[WindFarmInputs] = None,
    config: Optional[ReportConfig] = None,
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

    Returns:
        A fully populated :class:`ReportContext` ready for the renderer.
    """
    cfg = config if config is not None else load_report_config()
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
        manifest=dict(case_result.run_manifest or {}),
    )
