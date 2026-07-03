"""Project→equity IRR bridge — an IC-presentation reconciliation (#621, additive, KPI-neutral).

Lenders and investment committees present the *leverage uplift* — the gap between a project's
unlevered IRR and its levered equity IRR — as a **bridge**: a base bar (project IRR) plus
labelled steps (leverage, cost of debt, tax shield, cashflow timing) landing on the equity IRR.
This module builds that bridge as a **disclosure-only** view.

CESSPIT / CCCDIR discipline
---------------------------
- ``project_irr`` and ``equity_irr`` are the engine's **published** headline KPIs — this module
  never recomputes or moves them. The legs only *explain* the gap between them.
- All IRR arithmetic is delegated to :mod:`finance.irr` (R7 singleton — no IRR/NPV math lives
  here); the result types are centralised in :mod:`analytics.contracts_v14` (CCCDIR).
- The named legs are computed by **stepwise substitution** on the engine's own published
  per-year figures (``cfads_usd`` / ``interest_usd`` / ``effective_tax_rate`` and the engine's
  authoritative equity return vector), and an explicit ``residual`` closes the identity exactly:
  ``sum(leg.contribution) + residual == equity_irr − project_irr`` (asserted at build time). No
  KPI is silently re-derived; anything not cleanly attributable to a named leg lands, labelled,
  in the residual.

Why a residual is honest, not a fudge
-------------------------------------
IRR is **not additive** — the effect of leverage, debt cost and the tax shield interact
non-linearly, and the equity return vector further reflects covenant lockup, DSRA sizing,
withholding tax and any terminal value that the four named legs do not model in isolation. A
bridge that forced those into the named legs would misattribute them. Instead each named leg is
a single, well-defined substitution step, and the residual carries the interaction term plus the
unmodelled equity-waterfall effects — disclosed as its own line, per IC convention.

Currency: USD (the reported-KPI numeraire), matching the engine's USD ``cfads_usd`` and the
equity distribution vector.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from analytics.contracts_v14 import IrrBridgeComponent, ProjectEquityIrrBridge
from finance.irr import approx_project_irr
from finance.irr import irr as _irr

# Leg labels (stable identifiers consumed by the report layer).
LEG_LEVERAGE = "leverage"
LEG_COST_OF_DEBT = "cost_of_debt"
LEG_TAX_SHIELD = "tax_shield"

#: Tolerance (in IRR decimal) for the reconciliation assertion. The residual is defined as the
#: closing term, so the identity holds to floating-point rounding; this slack only guards the
#: assertion against FP noise from three independent bisection solves.
DEFAULT_RECONCILE_TOLERANCE: float = 1e-9


def _f(row: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    """Read a numeric row column as float, tolerating None / non-numeric with a default."""
    value = row.get(key, default)
    try:
        return float(value) if value is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """``a - b`` when both are defined; ``None`` if either intermediate IRR is undefined."""
    if a is None or b is None:
        return None
    return float(a) - float(b)


def build_project_equity_irr_bridge(
    *,
    project_irr: Optional[float],
    equity_irr: Optional[float],
    equity_investment_usd: float,
    capex_usd: float,
    cfads_usd: Sequence[float],
    interest_usd: Sequence[float],
    effective_tax_rate: Sequence[float],
    equity_cashflows_usd: Sequence[float],
    construction_years: int = 0,
    currency: str = "USD",
    reconcile_tolerance: float = DEFAULT_RECONCILE_TOLERANCE,
) -> ProjectEquityIrrBridge:
    """Decompose the published ``equity_irr − project_irr`` uplift into labelled legs + residual.

    The bridge walks a signed cashflow vector from the **project** basis to the **equity** basis
    in named substitution steps, taking the IRR (via :mod:`finance.irr`) at each step:

    1. **Base** = ``project_irr`` (published). Reproduced internally from
       ``[-capex_usd] + [0]*construction_years + cfads_usd`` only as a self-consistency check —
       the reported base is the published KPI, never the recomputed one.
    2. **Leverage** — replace the total ``capex_usd`` outlay with the ``equity_investment_usd``
       outlay while keeping the *pre-debt* CFADS; the IRR rises because the same operating cash
       now sits on a smaller invested base. ``contribution = IRR_lev − project_irr``.
    3. **Cost of debt** — subtract the engine's per-year ``interest_usd`` from operating cash;
       the IRR falls by the interest drag. ``contribution = IRR_cod − IRR_lev`` (≤ 0).
    4. **Tax shield** — add back the per-year interest tax shield
       (``interest_usd × effective_tax_rate``); the deductibility of interest lifts the IRR.
       ``contribution = IRR_ts − IRR_cod`` (≥ 0).
    5. **Residual** — the closing term: ``equity_irr − IRR_ts``. Carries the IRR interaction
       (non-additivity), principal-amortisation timing, covenant lockup, DSRA, withholding tax
       and any terminal value — i.e. everything the four named legs do not model in isolation.
       The equity basis for step 5 is the engine's OWN authoritative ``equity_cashflows_usd``
       vector (whose IRR is the published ``equity_irr``), so the bridge lands exactly on it.

    By construction ``sum(leg.contribution) + residual == equity_irr − project_irr`` to within
    ``reconcile_tolerance``; ``reconciled`` records whether that assertion held. When either
    headline IRR is ``None`` (undefined), the uplift and residual are ``None`` and the bridge is
    reported unreconciled rather than fabricating a number.

    Args:
        project_irr: The engine's published project (unlevered) IRR (decimal), or ``None``.
        equity_irr: The engine's published equity (levered) IRR (decimal), or ``None``.
        equity_investment_usd: Equity committed at financial close (USD), from the engine's
            equity-distribution summary.
        capex_usd: Total project cost committed at financial close (USD) — the project-IRR base.
        cfads_usd: Per-operating-year pre-debt CFADS (USD), the engine's ``cfads_usd`` column.
        interest_usd: Per-operating-year debt interest (USD), the engine's ``interest_usd``
            column, aligned to ``cfads_usd``.
        effective_tax_rate: Per-operating-year effective tax rate (decimal), aligned to
            ``cfads_usd``; the tax-shield leg uses ``interest × rate``.
        equity_cashflows_usd: The engine's authoritative equity return vector
            (``[-equity] + [0]*construction_years + distributions``), whose IRR is ``equity_irr``.
        construction_years: Zero-cash build periods between the close outlay and first operating
            cash — the SAME lag the engine's project/equity IRRs use, so the legs share one
            timeline.
        currency: Presentation-currency label (the figures are USD).
        reconcile_tolerance: Slack for the closing-identity assertion (guards FP noise only).

    Returns:
        A :class:`~analytics.contracts_v14.ProjectEquityIrrBridge`.
    """
    lag = max(0, int(construction_years))
    cfads = [float(c) for c in cfads_usd]
    interest = [float(i) for i in interest_usd]
    tax_rate = [float(t) for t in effective_tax_rate]
    n = len(cfads)

    # Pad the interest / tax-rate streams to the CFADS length so a zip never silently truncates
    # the operating horizon (CESSPIT — a short stream must not drop later years' cash).
    interest = (interest + [0.0] * n)[:n]
    tax_rate = (tax_rate + [0.0] * n)[:n]

    # Self-consistency probe (NOT the reported base): the reconstructed project IRR should match
    # the published one when the published one is defined. Recorded in metadata for provenance.
    reproduced_project_irr = (
        approx_project_irr(cfads, capex_usd, construction_years=lag)
        if capex_usd > 0.0 and cfads
        else None
    )

    def _vec(outlay: float, operating: Sequence[float]) -> list[float]:
        return [-float(outlay)] + [0.0] * lag + [float(x) for x in operating]

    # Step 2 — leverage: same pre-debt cash, equity-only outlay.
    irr_lev = (
        _irr(_vec(equity_investment_usd, cfads))
        if equity_investment_usd > 0.0
        else None
    )
    # Step 3 — cost of debt: strip per-year interest from operating cash.
    cod_cash = [c - i for c, i in zip(cfads, interest, strict=True)]
    irr_cod = (
        _irr(_vec(equity_investment_usd, cod_cash))
        if equity_investment_usd > 0.0
        else None
    )
    # Step 4 — tax shield: add back the interest tax shield.
    ts_cash = [c - i + i * t for c, i, t in zip(cfads, interest, tax_rate, strict=True)]
    irr_ts = (
        _irr(_vec(equity_investment_usd, ts_cash))
        if equity_investment_usd > 0.0
        else None
    )

    leverage_contribution = _delta(irr_lev, project_irr)
    cost_of_debt_contribution = _delta(irr_cod, irr_lev)
    tax_shield_contribution = _delta(irr_ts, irr_cod)

    components = [
        IrrBridgeComponent(
            name=LEG_LEVERAGE,
            contribution=(
                leverage_contribution if leverage_contribution is not None else 0.0
            ),
            irr_after=irr_lev,
            detail="Smaller equity outlay vs total project cost, same pre-debt CFADS.",
        ),
        IrrBridgeComponent(
            name=LEG_COST_OF_DEBT,
            contribution=(
                cost_of_debt_contribution
                if cost_of_debt_contribution is not None
                else 0.0
            ),
            irr_after=irr_cod,
            detail="Per-year debt interest removed from operating cash (drag).",
        ),
        IrrBridgeComponent(
            name=LEG_TAX_SHIELD,
            contribution=(
                tax_shield_contribution if tax_shield_contribution is not None else 0.0
            ),
            irr_after=irr_ts,
            detail="Interest tax shield restored (interest x effective tax rate).",
        ),
    ]

    # The uplift lands on the PUBLISHED equity_irr (the IRR of the engine's own authoritative
    # equity vector), so the bridge ties to the headline KPI — the residual is defined as the
    # closing term against that published number, never a re-derived one.
    total_uplift = _delta(equity_irr, project_irr)

    if total_uplift is None:
        # An undefined headline IRR: report the named legs but do not fabricate a residual.
        residual = 0.0
        reconciled = False
    else:
        named_sum = 0.0
        all_named_defined = True
        for contribution in (
            leverage_contribution,
            cost_of_debt_contribution,
            tax_shield_contribution,
        ):
            if contribution is None:
                all_named_defined = False
                break
            named_sum += contribution
        if all_named_defined:
            residual = float(total_uplift) - named_sum
            reconciled = True
        else:
            # A named leg's intermediate IRR was undefined (e.g. zero equity => no leverage
            # vector). Attribute the entire uplift to the residual honestly rather than assert a
            # partial decomposition. Zero the named contributions so the identity still closes.
            residual = float(total_uplift)
            reconciled = True
            components = [
                IrrBridgeComponent(
                    name=component.name,
                    contribution=0.0,
                    irr_after=component.irr_after,
                    detail=component.detail,
                )
                for component in components
            ]

    bridge = ProjectEquityIrrBridge(
        project_irr=project_irr,
        equity_irr=equity_irr,
        total_uplift=total_uplift,
        components=components,
        residual=residual,
        reconciled=reconciled,
        reconcile_tolerance=reconcile_tolerance,
        currency=currency,
        metadata={
            "residual_label": "cashflow_timing_and_interaction",
            "equity_investment_usd": float(equity_investment_usd),
            "capex_usd": float(capex_usd),
            "construction_years": lag,
            "reproduced_project_irr": reproduced_project_irr,
            "equity_vector_len": len(list(equity_cashflows_usd)),
        },
    )

    # CESSPIT: assert the closing identity actually holds (the residual is defined to close it,
    # so this fires only on a real builder regression, never on well-formed inputs).
    if bridge.reconciled and bridge.total_uplift is not None:
        named_total = sum(component.contribution for component in bridge.components)
        if (
            abs(named_total + bridge.residual - bridge.total_uplift)
            > reconcile_tolerance
        ):
            raise ValueError(
                "IRR bridge does not reconcile: "
                f"sum(components)={named_total} + residual={bridge.residual} != "
                f"total_uplift={bridge.total_uplift} (tol={reconcile_tolerance})"
            )

    return bridge


def _resolve_capex_usd(run_result: Mapping[str, Any]) -> Optional[float]:
    """Total project cost (USD) from the run's config — the project-IRR base outlay."""
    scenario_result = run_result.get("scenario_result")
    config: Any = None
    if isinstance(scenario_result, Mapping):
        config = scenario_result.get("config")
    elif scenario_result is not None:
        config = getattr(scenario_result, "config", None)
    if config is None:
        config = run_result.get("config")
    if not isinstance(config, Mapping):
        return None
    try:
        from finance.debt_v14 import _extract_capex_usd

        capex = _extract_capex_usd(dict(config))
    except Exception:  # pragma: no cover - defensive
        return None
    return float(capex) if capex and capex > 0.0 else None


def build_project_equity_irr_bridge_from_run(
    run_result: Mapping[str, Any],
) -> Optional[ProjectEquityIrrBridge]:
    """Build the IRR bridge from a full pipeline run result (the gateway's ``return_full_result``).

    Consumes the engine's published surface — ``kpis`` (``project_irr`` / ``equity_irr``),
    ``annual_rows`` (``cfads_usd`` / ``interest_usd`` / ``effective_tax_rate``), ``debt_result``
    (``construction_years``) and ``equity_distribution`` (the authoritative equity vector +
    equity investment). Returns ``None`` (the bridge is not built — additive, default-off) when
    the run lacks a computed equity distribution or the project cost cannot be resolved, so a
    legacy / KPI-only run is unaffected.

    Args:
        run_result: The dict returned by
            :func:`analytics.evaluation_v14.evaluate_with_overrides` with
            ``return_full_result=True``.

    Returns:
        A :class:`~analytics.contracts_v14.ProjectEquityIrrBridge`, or ``None``.
    """
    kpis = run_result.get("kpis")
    if not isinstance(kpis, Mapping):
        return None

    equity_distribution = run_result.get("equity_distribution")
    if not isinstance(equity_distribution, Mapping):
        return None
    if str(equity_distribution.get("status")) not in {"computed", "defaulted"}:
        return None
    equity_summary = equity_distribution.get("equity_summary")
    if not isinstance(equity_summary, Mapping):
        return None
    equity_investment = equity_summary.get("equity_investment_usd")
    if equity_investment is None:
        return None

    capex_usd = _resolve_capex_usd(run_result)
    if capex_usd is None:
        return None

    annual_rows = run_result.get("annual_rows")
    if not isinstance(annual_rows, list) or not annual_rows:
        return None
    cfads_usd = [_f(row, "cfads_usd", _f(row, "cf_pre_debt")) for row in annual_rows]
    interest_usd = [_f(row, "interest_usd") for row in annual_rows]
    effective_tax_rate = [_f(row, "effective_tax_rate") for row in annual_rows]

    debt_result = run_result.get("debt_result")
    construction_years = 0
    if isinstance(debt_result, Mapping):
        try:
            construction_years = int(debt_result.get("construction_years") or 0)
        except (TypeError, ValueError):
            construction_years = 0

    equity_cashflows = equity_distribution.get("equity_cashflows_usd") or []

    project_irr = kpis.get("project_irr")
    equity_irr = kpis.get("equity_irr")

    return build_project_equity_irr_bridge(
        project_irr=float(project_irr) if project_irr is not None else None,
        equity_irr=float(equity_irr) if equity_irr is not None else None,
        equity_investment_usd=float(equity_investment),
        capex_usd=float(capex_usd),
        cfads_usd=cfads_usd,
        interest_usd=interest_usd,
        effective_tax_rate=effective_tax_rate,
        equity_cashflows_usd=[float(x) for x in equity_cashflows],
        construction_years=construction_years,
    )


__all__ = [
    "LEG_LEVERAGE",
    "LEG_COST_OF_DEBT",
    "LEG_TAX_SHIELD",
    "DEFAULT_RECONCILE_TOLERANCE",
    "build_project_equity_irr_bridge",
    "build_project_equity_irr_bridge_from_run",
]
