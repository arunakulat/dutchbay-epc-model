"""Typed *result-surfacing* response models for the wizard client (#844 / #788 P1).

The frontend stack (#843, HTMX vs SPA) is an undecided user gate, so this module ships
the **server-side contract** a future frontend consumes — not any UI. It projects an
already-built :class:`app.reports.report_model.ReportContext` (the same object the HTML /
PDF report routes render) into a compact, chart-ready payload:

* :class:`KpiCard` — the lender KPI cards (projIRR / eqIRR / minDSCR / NPV / CFADS …),
  each carrying the raw value AND the report's own formatted display string, so a client
  renders identical numbers to the PDF without re-formatting.
* :class:`TornadoChart` / :class:`TornadoBar` — the one-at-a-time sensitivity tornado,
  widest-swing-first (the ordering the report builder already applied).
* :class:`GlobalSaChart` / :class:`GlobalSaBar` — the Morris and PAWN global-SA screenings.
* :class:`CapitalRiskSurface` — the #657 capital-risk (Monte-Carlo) headline: covenant-breach
  probabilities against their floors, probability-below-hurdle, and per-metric VaR/CVaR.
* :class:`ArtifactLinks` — the download routes for the executive workbook / HTML / PDF
  artifacts (the artifacts themselves already exist; this only names their endpoints).

Design (Dolphin): this adds NO finance or presentation logic — every field is a read-only
projection of a field the report builder already computed. The supplementary sections
(tornado / global-SA / capital-risk) are ``None`` on the :class:`ReportContext` when their
best-effort compute was omitted, and they project straight through to ``None`` here, so the
surface degrades exactly as the report does (CASPER). Because it only re-shapes existing
outputs, it is KPI-neutral by construction — it cannot move a canonical number.

The public field sets are frozen by ``tests/app/test_surface_contract.py`` and versioned by
:data:`app.api.responses.API_CONTRACT_VERSION`; a breaking change to any model fails there.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.api.responses import API_CONTRACT_VERSION
from app.reports.report_model import (
    CapitalRiskBlock,
    GlobalSABlock,
    ReportContext,
    TornadoBlock,
)


class KpiCard(BaseModel):
    """One lender-KPI card: the machine key, human label, raw value, and display string.

    ``display`` is the report's OWN formatted string (e.g. ``"1.46%"`` / ``"1.29x"`` /
    ``"-$79,273,514"``), so a client shows numbers identical to the PDF/HTML report without
    re-implementing the formatting rules.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    value: float
    display: str


class TornadoBar(BaseModel):
    """One driver's one-at-a-time swing on the target metric (chart bar)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    base: Optional[float] = None
    low_case: Optional[float] = None
    high_case: Optional[float] = None
    impact_abs: Optional[float] = None


class TornadoChart(BaseModel):
    """The sensitivity tornado: the target metric plus its driver bars, widest swing first."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    bars: List[TornadoBar]


class GlobalSaBar(BaseModel):
    """One driver's global-sensitivity result (Morris ``mu_star``/``sigma`` or PAWN KS)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    mu_star: Optional[float] = None
    sigma: Optional[float] = None
    median_ks: Optional[float] = None
    ks_cv: Optional[float] = None


class GlobalSaChart(BaseModel):
    """A global-SA screening: the method (``morris``/``pawn``), metric, and ranked drivers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    method: str
    metric: str
    n_runs: Optional[int] = None
    bars: List[GlobalSaBar]


class CapitalRiskMetric(BaseModel):
    """One MC return-metric's distributional summary (mean + VaR/CVaR) for the surface."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    unit: str  # "pct" | "usd"
    mean: float
    var: float
    cvar: float
    var_label: str
    cvar_label: str


class CapitalRiskSurface(BaseModel):
    """The #657 capital-risk (Monte-Carlo) headline block, projected for the client.

    Covenant-breach probabilities against their floors, the probability equity IRR falls
    below the hurdle, and the per-metric VaR/CVaR — the same numbers the report renders.
    ``npv_distribution_filename`` is the chart basename only (no server path is leaked).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    model_version: str
    method: str
    n_trials: int
    dscr_breach_probability: float
    llcr_breach_probability: float
    plcr_breach_probability: float
    dscr_floor: float
    llcr_floor: float
    plcr_floor: float
    probability_below_hurdle: float
    target_equity_irr: float
    metrics: List[CapitalRiskMetric]
    npv_distribution_filename: str


class ArtifactLinks(BaseModel):
    """Download routes for the run's artifacts (the artifacts already exist elsewhere).

    These are the ``POST`` endpoints a client re-submits the same ``WindFarmInputs`` to in
    order to download each artifact; they are constants (the contract), not per-run URLs —
    the synchronous case surface holds no server-side run state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_html: str = "/v1/cases/report.html"
    report_pdf: str = "/v1/cases/report.pdf"
    workbook_xlsx: str = "/v1/cases/report.xlsx"


class CaseSurface(BaseModel):
    """Chart-ready projection of a completed run for the wizard result view (#844).

    A read-only re-shape of a :class:`ReportContext`: the KPI cards, the tornado and both
    global-SA charts, the capital-risk headline, and the artifact download links. Every
    supplementary chart is ``Optional`` and is ``None`` exactly when the report omitted it,
    so the surface degrades identically to the report (CASPER). Adds no computation — it
    is KPI-neutral by construction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(
        ..., description="Run status projected from the report context."
    )
    scenario_variant: str
    site_name: str
    report_grade: Optional[str] = None
    generated_at: str
    kpi_cards: List[KpiCard]
    tornado: Optional[TornadoChart] = None
    global_sa_morris: Optional[GlobalSaChart] = None
    global_sa_pawn: Optional[GlobalSaChart] = None
    capital_risk: Optional[CapitalRiskSurface] = None
    artifacts: ArtifactLinks = Field(default_factory=ArtifactLinks)
    contract_version: str = Field(
        default=API_CONTRACT_VERSION,
        description="Public API contract version this response conforms to (#841).",
    )

    @classmethod
    def from_report_context(cls, context: ReportContext) -> "CaseSurface":
        """Project a built :class:`ReportContext` into the client-facing case surface.

        Pure re-shaping: reads only fields the report builder already populated; computes
        nothing. Absent supplementary blocks (``None`` on the context) stay ``None`` here.
        """
        kpi_cards = [
            KpiCard(key=row.key, label=row.label, value=row.value, display=row.display)
            for row in context.kpi_rows
        ]
        return cls(
            status=context.status,
            scenario_variant=context.scenario_variant,
            site_name=context.site_name,
            report_grade=context.report_grade,
            generated_at=context.generated_at,
            kpi_cards=kpi_cards,
            tornado=_project_tornado(context.tornado),
            global_sa_morris=_project_global_sa(context.global_sa),
            global_sa_pawn=_project_global_sa(context.global_sa_pawn),
            capital_risk=_project_capital_risk(context.capital_risk),
        )


def _project_tornado(block: Optional[TornadoBlock]) -> Optional[TornadoChart]:
    """Project the report's :class:`TornadoBlock` into a :class:`TornadoChart` (None → None)."""
    if block is None:
        return None
    bars = [
        TornadoBar(
            label=row.label,
            base=row.base,
            low_case=row.low_case,
            high_case=row.high_case,
            impact_abs=row.impact_abs,
        )
        for row in block.rows
    ]
    return TornadoChart(metric=block.metric, bars=bars)


def _project_global_sa(block: Optional[GlobalSABlock]) -> Optional[GlobalSaChart]:
    """Project a report :class:`GlobalSABlock` into a :class:`GlobalSaChart` (None → None)."""
    if block is None:
        return None
    bars = [
        GlobalSaBar(
            name=driver.name,
            mu_star=driver.mu_star,
            sigma=driver.sigma,
            median_ks=driver.median_ks,
            ks_cv=driver.ks_cv,
        )
        for driver in block.drivers
    ]
    return GlobalSaChart(
        method=block.method, metric=block.metric, n_runs=block.n_runs, bars=bars
    )


def _project_capital_risk(
    block: Optional[CapitalRiskBlock],
) -> Optional[CapitalRiskSurface]:
    """Project the report :class:`CapitalRiskBlock` into a :class:`CapitalRiskSurface`.

    Drops the embedded base64 chart image (``npv_distribution_img``) — a JSON surface links
    to the chart by basename rather than inlining a data-URI. ``None`` maps to ``None``.
    """
    if block is None:
        return None
    metrics = [
        CapitalRiskMetric(
            metric=row.metric,
            unit=row.unit,
            mean=row.mean,
            var=row.var,
            cvar=row.cvar,
            var_label=row.var_label,
            cvar_label=row.cvar_label,
        )
        for row in block.metrics
    ]
    return CapitalRiskSurface(
        scenario=block.scenario,
        model_version=block.model_version,
        method=block.method,
        n_trials=block.n_trials,
        dscr_breach_probability=block.dscr_breach_probability,
        llcr_breach_probability=block.llcr_breach_probability,
        plcr_breach_probability=block.plcr_breach_probability,
        dscr_floor=block.dscr_floor,
        llcr_floor=block.llcr_floor,
        plcr_floor=block.plcr_floor,
        probability_below_hurdle=block.probability_below_hurdle,
        target_equity_irr=block.target_equity_irr,
        metrics=metrics,
        npv_distribution_filename=block.npv_distribution_filename,
    )
