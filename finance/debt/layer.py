"""Core debt amortization layer — apply_debt_layer (extracted from debt_v14)."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from finance.debt.capex import _extract_capex_usd
from finance.debt.constants import (
    _AMORT_ANNUITY_STYLES,
    _AMORT_DEFAULT_STYLE,
    _AMORT_SCULPTED_STYLES,
    _AMORT_VALID_STYLES,
    _BALLOON_TOL,
    _SERVICE_TOL,
)
from finance.debt.construction import calculate_construction_drawdowns, calculate_idc
from finance.debt.helpers import _as_float, _npv
from finance.debt.placeholders import _allow_toy_capex_fallback, _warn_placeholder_once
from finance.debt.schedules import (
    Tranche,
    _annuity_schedule,
    _sculpted_schedule,
    _solve_mix,
)
from finance.debt.terms import (
    _build_cfads_timeline,
    _extract_financing_terms,
    _resolve_construction_periods,
    _resolve_first_operating_period,
)

logger = logging.getLogger("finance.debt_v14")

def apply_debt_layer(
    params: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Core v14 debt engine.

    Returns a rich dict used internally by plan_debt and the analytics layer.
    """
    p = _extract_financing_terms(params)

    construction_periods = _resolve_construction_periods(params)
    construction_schedule = p.get("construction_schedule", [40.0, 60.0])
    drawdown_pct = p.get("debt_drawdown_pct", [0.5, 0.5])
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = max(0, int(_as_float(p.get("tenor_years"), 15)))
    years_io = max(0, int(_as_float(p.get("interest_only_years"), 0)))
    amort_raw = p.get("amortization_style", _AMORT_DEFAULT_STYLE)
    if amort_raw is not None and not isinstance(amort_raw, str):
        # A present-but-non-string style (YAML `5`, `true`) is a config error, not
        # a stylistic typo: reject it loudly instead of warn-falling-back (#683 —
        # the #585 cluster's one tolerance increase, reverted to fail-loud).
        raise ValueError(
            "amortization_style (under Financing_Terms / financing / debt) must be "
            f"a string (got {amort_raw!r}); "
            f"valid: {'/'.join(sorted(_AMORT_VALID_STYLES))}"
        )
    amortization = str(amort_raw or _AMORT_DEFAULT_STYLE).lower()
    if amortization not in _AMORT_VALID_STYLES:
        logger.warning(
            "Unknown amortization_style %r; falling back to %s "
            "(valid: %s -> annuity schedule; %s -> DSCR-sculpted schedule)",
            amortization,
            _AMORT_DEFAULT_STYLE,
            "/".join(_AMORT_ANNUITY_STYLES),
            "/".join(_AMORT_SCULPTED_STYLES),
        )
        amortization = _AMORT_DEFAULT_STYLE
    target_dscr = _as_float(p.get("target_dscr"), 1.30)

    # Annual credit-support fees (#737): DFI partial-credit-guarantee fee + PRI premium,
    # each an annual rate on the OUTSTANDING senior debt (ADB PCG convention). Config
    # decimals under Financing_Terms.fees; absent keys -> 0.0 -> byte-identical. The
    # combined rate is charged senior to debt service (reduces the CFADS used for
    # sculpting AND the reported DSCR/LLCR/PLCR coverage bases) and is exposed per
    # period as senior_fee_usd for the pipeline's reported rows. USD throughout — the
    # tranche balances and cfads_usd share the numeraire, so no FX enters here.
    fees_cfg = p.get("fees")
    fees_map: Mapping[str, Any] = fees_cfg if isinstance(fees_cfg, Mapping) else {}
    guarantee_fee_rate = _as_float(fees_map.get("guarantee_fee_pct_per_year"), 0.0)
    pri_premium_rate = _as_float(fees_map.get("pri_premium_pct_per_year"), 0.0)
    senior_fee_rate = guarantee_fee_rate + pri_premium_rate
    if guarantee_fee_rate < 0.0 or pri_premium_rate < 0.0 or senior_fee_rate >= 1.0:
        raise ValueError(
            "Financing_Terms.fees guarantee_fee_pct_per_year / pri_premium_pct_per_year "
            f"must be non-negative decimals well below 1.0 (got {guarantee_fee_rate!r} "
            f"and {pri_premium_rate!r}); e.g. 75 bps -> 0.0075."
        )

    capex = _extract_capex_usd(params)
    debt_total = capex * debt_ratio

    logger.info(
        "V14 Debt: %d-yr construction, %d-yr tenor, CAPEX=%.2f, debt=%.2f",
        construction_periods,
        tenor,
        capex,
        debt_total,
    )

    tranches = _solve_mix(p, debt_total)

    # A1/#65/#93: refuse to silently model COST-FREE debt. _solve_mix falls back to a 0.0
    # tranche rate when a scenario sizes debt but omits an explicit Financing_Terms.rates /
    # debt.rates block — servicing the whole facility at zero interest, which flatters
    # CFADS-after-debt, DSCR and equity IRR (and, separately, defaults the currency split to
    # 100% USD, stripping the LKR natural hedge). Fail loud unless allow_toy_fallback is
    # explicitly set (the same opt-in already guarding toy CAPEX). Canonical scenarios
    # declare their tranche rates, so this never trips for them.
    if debt_total > 0 and not _allow_toy_capex_fallback(params):
        funded_rates = [tr.rate for tr in tranches.values() if tr.principal > 0]
        if funded_rates and all(rate <= 0.0 for rate in funded_rates):
            raise ValueError(
                f"Debt of {debt_total:,.0f} sized but every funded tranche resolves to a "
                "0.0 interest rate — no explicit Financing_Terms.rates / debt.rates block. "
                "Refusing to model cost-free debt; declare the tranche rates "
                "(lkr_nominal / usd_nominal / dfi_nominal) or set allow_toy_fallback=true."
            )

    idc_schedule: Dict[str, List[float]] = {}
    total_idc_by_tranche: Dict[str, float] = {}

    for name, tr in tranches.items():
        drawn = calculate_construction_drawdowns(
            tr.principal, construction_schedule, drawdown_pct
        )
        idc_list, idc_cap = calculate_idc(drawn, tr.rate, construction_periods)
        idc_schedule[name] = idc_list
        total_idc_by_tranche[name] = idc_cap
        tr.principal += idc_cap

    principal_after_idc = {n: t.principal for n, t in tranches.items()}

    cfads = [float(a.get("cfads_usd", 0.0)) for a in annual_rows]
    (
        cfads_ext,
        annual_row_debt_period_map,
        timeline_periods,
        bridge_debt_period,
    ) = _build_cfads_timeline(annual_rows, cfads, construction_periods, tenor)

    amort_years = max(0, tenor - years_io)
    if amortization in _AMORT_ANNUITY_STYLES:
        schedules = {k: _annuity_schedule(t, amort_years) for k, t in tranches.items()}
    else:
        schedules = _sculpted_schedule(
            tranches,
            amort_years,
            cfads_ext[construction_periods:],
            target_dscr,
            senior_fee_rate=senior_fee_rate,
        )

    for k in schedules:
        schedules[k] = [(0.0, 0.0, 0.0)] * construction_periods + schedules[k]

    dscr_series: List[Optional[float]] = []
    debt_service_total: List[float] = []
    # Per-period INTEREST (the [0] element of each (interest, principal, service) tuple),
    # parallel to debt_service_total and on the SAME period index. Used by the equity
    # waterfall to charge a grossed-up non-resident interest WHT (CESSPIT wht_gross_up).
    interest_total: List[float] = []
    debt_outstanding: List[float] = []
    # Per-period senior credit-support fee (#737): senior_fee_rate x the OPENING
    # outstanding balance — the SAME base the sculpt netted, so the reported DSCR lands
    # exactly on the sculpt target. Charged for operating periods only; 0.0 during
    # construction (no operations to bear an ops-period fee) and for the synthetic
    # half-year bridge period (it maps to no operating row, so a fee there could never
    # reach the reported CFADS rows — the consistency requirement wins).
    senior_fee_schedule: List[float] = []

    out_bals = {k: t.principal for k, t in tranches.items()}

    for period in range(timeline_periods):
        opening_outstanding = sum(out_bals.values())
        debt_outstanding.append(opening_outstanding)
        fee_applies = period >= construction_periods and (
            bridge_debt_period is None or period != int(bridge_debt_period)
        )
        fee_period = senior_fee_rate * opening_outstanding if fee_applies else 0.0
        senior_fee_schedule.append(fee_period)
        svc = 0.0
        intr = 0.0
        for k in schedules:
            if period < len(schedules[k]):
                interest_k, princ, service = schedules[k][period]
                svc += service
                intr += interest_k
                out_bals[k] = max(0.0, out_bals[k] - princ)
        debt_service_total.append(svc)
        interest_total.append(intr)
        cf = cfads_ext[period] if period < len(cfads_ext) else 0.0
        cf_net = cf - fee_period

        if period < construction_periods:
            dscr_series.append(None)
        elif svc > 0:
            dscr_series.append(cf_net / svc)
        else:
            dscr_series.append(None)

    # The "bridge" lead-in period carries real scheduled debt service but maps to no
    # operating row. Fold its service into operating year 1's reported DSCR so the
    # per-year covenant coverage matches what equity actually bears (audit finding 2.2):
    # year 1 covers its OWN period's service PLUS the orphaned bridge service. Without
    # this, year 1 read the phantom interest-only period's ~2.6x instead of the ~1.30 it
    # truly achieves once the bridge service is included.
    mapped_periods = {int(m["debt_period"]) for m in annual_row_debt_period_map}
    bridge_extra_service = 0.0
    if (
        bridge_debt_period is not None
        and int(bridge_debt_period) not in mapped_periods
        and 0 <= int(bridge_debt_period) < len(debt_service_total)
    ):
        bridge_extra_service = float(debt_service_total[int(bridge_debt_period)])

    dscr_by_year: Dict[Any, Optional[float]] = {}
    for row_i, mapping in enumerate(annual_row_debt_period_map):
        debt_period = int(mapping["debt_period"])
        year_key = mapping.get("year", mapping["annual_row_index"] + 1)
        if debt_period >= len(dscr_series) or dscr_series[debt_period] is None:
            dscr_by_year[year_key] = None
        elif row_i == 0 and bridge_extra_service > 0.0:
            cf = cfads_ext[debt_period] if debt_period < len(cfads_ext) else 0.0
            # Net year 1's own senior fee (#737), same as dscr_series does; the bridge
            # period itself carries no fee (see senior_fee_schedule above).
            fee = (
                senior_fee_schedule[debt_period]
                if debt_period < len(senior_fee_schedule)
                else 0.0
            )
            svc = float(debt_service_total[debt_period]) + bridge_extra_service
            dscr_by_year[year_key] = ((cf - fee) / svc) if svc > 0 else None
        else:
            dscr_by_year[year_key] = dscr_series[debt_period]

    dscr_op = [
        d
        for i, d in enumerate(dscr_series)
        if i >= construction_periods and d is not None
    ]
    dscr_min = min(dscr_op) if dscr_op else 0.0

    debt_principal_total = sum(principal_after_idc.values())

    if debt_principal_total > 0:
        weighted_rate_num = 0.0
        for name, tr in tranches.items():
            principal = principal_after_idc.get(name, tr.principal)
            weighted_rate_num += principal * tr.rate
        avg_debt_rate = weighted_rate_num / debt_principal_total
    else:
        avg_debt_rate = 0.0

    # LLCR/PLCR discount convention (CCCDIR, single source): coverage ratios discount CFADS
    # at the COST OF DEBT — avg_debt_rate (the weighted tranche rate) — which is the textbook
    # LLCR/PLCR convention. Override per scenario via Financing_Terms.covenants.{llcr,plcr}
    # _discount_rate. NOTE: the old top-level `metrics.{llcr,plcr}_discount_rate: 0.10` keys
    # were DECORATIVE — never read here (this reads Financing_Terms.covenants) so they were
    # silently ignored; they were removed from the scenarios (round-8) rather than honoured,
    # since avg_debt_rate is the intended convention (honouring 0.10 would have understated
    # coverage ~11-12%: LLCR 1.243->1.108, PLCR 1.340->1.174).
    cov_cfg = (p.get("covenants") or {}) if isinstance(p, dict) else {}
    llcr_discount_rate = _as_float(cov_cfg.get("llcr_discount_rate"), avg_debt_rate)
    plcr_discount_rate = _as_float(cov_cfg.get("plcr_discount_rate"), avg_debt_rate)

    # cfads is built from annual_rows, which are OPERATING years only (no construction
    # periods) — see the `cfads = [... for a in annual_rows]` above. The old
    # `cfads[construction_periods:]` therefore dropped the first construction_periods
    # OPERATING years (the highest-CFADS years, which DO carry debt service from operating
    # year 1) and pushed the window past the loan life — understating LLCR/PLCR. The loan
    # amortises over operating years 1..tenor (debt service starts in operating year 1, debt
    # period = construction_periods+1), and the project life is all operating years, so:
    #
    # LLCR-WINDOW CONVENTION (round-5 #2, deliberate — keep tenor window): the LLCR
    # numerator is CFADS over the loan LIFE measured in operating years, i.e. cfads[:tenor]
    # (the first `tenor` operating years). Note this is NOT byte-identical to the set of
    # internal debt-service periods: the sculpting introduces a synthetic half-year "bridge"
    # lead-in period that bears scheduled service but maps to no operating row (its service
    # is folded into operating year 1 for the per-year DSCR — see dscr_by_year above). As a
    # result cfads[:tenor] skips that sub-operating bridge period and includes one trailing
    # operating year beyond the last service period; re-aligning the numerator to the exact
    # debt-service-bearing periods would move LLCR by ~1.7% (≈1.243 -> ~1.222 on the lender
    # case). We KEEP the tenor-in-operating-years window: it is the standard loan-life
    # convention, internally consistent with PLCR (full operating horizon) and the project
    # life, and the divergence is an artifact of the bridge period, not an economic extra
    # year of loan life. PLCR uses the full operating horizon.
    # #737: LLCR/PLCR discount CFADS *available for debt service*, and the senior
    # credit-support fee ranks above debt service — so the numerator nets the SAME
    # per-period fee the DSCR series charges (via the canonical row->debt-period map).
    # Leaving the numerator pre-fee would overstate coverage relative to the reported
    # (fee-netted) CFADS rows and the DSCR series. 0.0 fees -> byte-identical.
    fee_by_row: Dict[int, float] = {}
    for mapping in annual_row_debt_period_map:
        debt_period = int(mapping["debt_period"])
        if 0 <= debt_period < len(senior_fee_schedule):
            fee_by_row[int(mapping["annual_row_index"])] = senior_fee_schedule[
                debt_period
            ]
    project_cfads = [
        value - fee_by_row.get(row_i, 0.0) for row_i, value in enumerate(cfads)
    ]
    cfads_for_llcr = project_cfads[:tenor] if tenor > 0 else []

    llcr = (
        _npv(cfads_for_llcr, llcr_discount_rate) / debt_principal_total
        if debt_principal_total > 0 and cfads_for_llcr
        else 0.0
    )
    plcr = (
        _npv(project_cfads, plcr_discount_rate) / debt_principal_total
        if debt_principal_total > 0 and project_cfads
        else 0.0
    )

    fx_values: List[float] = []
    for row in annual_rows:
        fx_val = row.get("fx_rate")
        if fx_val is not None:
            try:
                fx_values.append(float(fx_val))
            except (TypeError, ValueError):
                continue

    fx_min = min(fx_values) if fx_values else None
    fx_max = max(fx_values) if fx_values else None
    fx_avg = sum(fx_values) / len(fx_values) if fx_values else None

    return {
        "dscr_series": dscr_series,
        "dscr_by_year": dscr_by_year,
        "dscr_min": dscr_min,
        "debt_service_total": debt_service_total,
        "interest_total": interest_total,
        "debt_outstanding": debt_outstanding,
        "senior_fee_usd": senior_fee_schedule,
        "senior_fee_rate": senior_fee_rate,
        "balloon_remaining": sum(out_bals.values()),
        "construction_periods": construction_periods,
        "construction_schedule": construction_schedule,
        "idc_schedule": idc_schedule,
        "idc_by_tranche": total_idc_by_tranche,
        "principal_after_idc": principal_after_idc,
        "total_idc_capitalized": sum(total_idc_by_tranche.values()),
        "timeline_periods": timeline_periods,
        "tenor_years": tenor,
        "cfads_extended": cfads_ext,
        "cfads_bridge_debt_period": bridge_debt_period,
        "annual_row_debt_period_map": annual_row_debt_period_map,
        "debt_schedules": schedules,
        "audit_status": "PASS" if dscr_min >= target_dscr else "REVIEW",
        "debt_total": debt_total,
        "avg_debt_rate": avg_debt_rate,
        "llcr": llcr,
        "plcr": plcr,
        "fx_min": fx_min,
        "fx_max": fx_max,
        "fx_avg": fx_avg,
    }


