# [File content too long - showing key changes only]
# Line 268-275: Changed from float('inf') to None

from __future__ import annotations

import copy
import logging
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.utils import as_float, get_nested

logger = logging.getLogger(__name__)

"""Debt Planning Module for DutchBay V14 Project Finance.

Author: DutchBay V14 Team, Nov 2025
Version: 3.7 (Dynamic debt timeline + explicit CAPEX guard + balloon treatment)
"""

# ─────────────────────────────────────────────────────────────────────────────
# Balloon treatment
# ─────────────────────────────────────────────────────────────────────────────
# A sculpted schedule pays principal = CFADS/DSCR − interest each year. Over a
# FIXED tenor this need not retire the whole loan; the residual is a BALLOON due
# at maturity. The equity waterfall MUST resolve it — otherwise equity collects
# post-maturity CFADS as a free pass and equity IRR is overstated. The treatment
# is config-selectable via ``Financing_Terms.balloon_treatment``:
#   - "cash_sweep" (default): trap post-maturity CFADS to retire the balloon
#       before any equity distribution (prudent-lender cash-sweep covenant).
#   - "refinance":  refinance the balloon over ``refinance_tenor_years`` at
#       ``avg_debt_rate + refinance_rate_premium``; the refi service reduces
#       equity (and may require a sponsor cash call if it exceeds CFADS).
#   - "bullet":     single lump repayment at maturity (cash call if > CFADS).
#   - "amortize":   resize debt DOWN so the sculpt fully amortises within tenor
#       (no balloon); reported == honest, lowest leverage.
#   - "legacy_ignore": historical (incorrect) behaviour — balloon flagged but
#       never serviced. Retained ONLY to reproduce pre-fix numbers.
_BALLOON_VALID_TREATMENTS = (
    "cash_sweep",
    "refinance",
    "bullet",
    "amortize",
    "legacy_ignore",
)
_BALLOON_DEFAULT_TREATMENT = "cash_sweep"
_BALLOON_TOL = 1.0  # USD; outstanding balances below this are treated as repaid
_SERVICE_TOL = 1.0  # USD; scheduled service above this marks an active debt period
_REFINANCE_TENOR_DEFAULT = 3
_REFINANCE_PREMIUM_DEFAULT = 0.02

# Debt is sized via dual_dscr and split by Financing_Terms.mix proportions at the
# per-currency Financing_Terms.rates. A hand-authored Financing_Terms.debt_tranches
# list (absolute principals / per-tranche tenors) is NOT an engine input — absolute
# principals are incompatible with auto-sizing. We warn once if one is present so the
# redundant block cannot silently drift from the engine's actual schedule. Tests reset
# this flag to assert the warning.
_warned_decorative_tranches = False


def _lookup_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    key_lower = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def _section_case_insensitive(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = _lookup_case_insensitive(mapping, key)
    return value if isinstance(value, Mapping) else None


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    return get_nested(d, path, default)


def _as_float(v: Any, default: Optional[float] = None) -> float:
    base_default = 0.0 if default is None else default
    val = as_float(v, base_default)
    return float(val if val is not None else base_default)


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _allow_toy_capex_fallback(params: Mapping[str, Any]) -> bool:
    """Return true only when toy fallback is explicitly enabled."""
    if _truthy_flag(_lookup_case_insensitive(params, "allow_toy_fallback")):
        return True

    testing_cfg = _section_case_insensitive(params, "testing")
    if testing_cfg is not None:
        if _truthy_flag(_lookup_case_insensitive(testing_cfg, "allow_toy_fallback")):
            return True

    debt_cfg = _section_case_insensitive(params, "debt")
    if debt_cfg is not None:
        if _truthy_flag(_lookup_case_insensitive(debt_cfg, "allow_toy_fallback")):
            return True

    return False


def _pmt(rate: float, nper: int, pv: float) -> float:
    if rate == 0:
        return pv / nper if nper > 0 else 0.0
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)


def _npv(cashflows: Sequence[float], rate: float) -> float:
    """Simple NPV helper (no IRR logic here - IRR stays in finance.irr)."""
    if not cashflows:
        return 0.0
    if rate <= -1.0:
        return 0.0

    df = 1.0 + rate
    pv = 0.0
    for t, cf in enumerate(cashflows, start=1):
        pv += float(cf) / (df**t)
    return pv


def _extract_capex_usd(params: Dict[str, Any]) -> float:
    """Extract CAPEX from config, supporting v14, legacy and compact schemas.

    When ``capex.derive_from_breakdown`` is truthy, CAPEX is computed BOTTOM-UP as the
    sum of the numeric line items under ``capex.breakdown`` (single source of truth, no
    flat-total/breakdown divergence). Otherwise the flat ``capex.usd_total`` (etc.) is
    used. If both a derived sum and an explicit ``usd_total`` are present, they are
    cross-checked and a mismatch >0.5% raises (CESSPIT: the two must not silently differ).
    """
    capex_section = _section_case_insensitive(params, "capex")
    if capex_section and _lookup_case_insensitive(capex_section, "derive_from_breakdown"):
        breakdown = _lookup_case_insensitive(capex_section, "breakdown")
        if not isinstance(breakdown, Mapping):
            raise ValueError(
                "capex.derive_from_breakdown is set but capex.breakdown is missing or "
                "not a mapping of line items"
            )
        line_total = sum(
            float(v) for v in breakdown.values() if isinstance(v, (int, float))
        )
        if line_total <= 0:
            raise ValueError("capex.breakdown sums to <= 0; provide positive line items")

        # AACE QRA contingency: when capex.contingency.method == 'qra', the contingency
        # is RECOMPUTED from the base cost (breakdown minus its contingency line) + the
        # risk inputs, instead of the fixed line item. Otherwise the fixed breakdown sum
        # stands and is cross-asserted against usd_total.
        from analytics.cost.contingency import contingency_is_qra, resolve_contingency

        if contingency_is_qra(capex_section):
            contingency_line = float(_lookup_case_insensitive(breakdown, "contingency_usd") or 0.0)
            base_cost = line_total - contingency_line
            derived = base_cost + resolve_contingency(base_cost, capex_section).contingency_usd
            if derived <= 0:
                raise ValueError("QRA-derived CAPEX is <= 0; check the breakdown / risk inputs")
            return derived

        derived = line_total
        stated = _lookup_case_insensitive(capex_section, "usd_total")
        if isinstance(stated, (int, float)) and stated > 0:
            if abs(float(stated) - derived) / derived > 0.005:
                raise ValueError(
                    f"capex.breakdown sums to {derived:,.0f} but capex.usd_total is "
                    f"{float(stated):,.0f} (>0.5% mismatch) — reconcile the two"
                )
        return derived

    for section_name, keys in (
        ("finance", ("capex_total_usd", "capex_usd")),
        ("capex", ("usd_total", "capex_total_usd", "total_capex_usd", "total_capex")),
        ("costs", ("capex_total_usd", "capex_usd", "total_capex_usd", "total_capex")),
    ):
        section = _section_case_insensitive(params, section_name)
        if not section:
            continue
        for key in keys:
            value = _lookup_case_insensitive(section, key)
            if isinstance(value, (int, float)):
                return float(value)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue

    for key in ("capex_usd_total", "capex_total_usd", "total_capex_usd"):
        value = _lookup_case_insensitive(params, key)
        if isinstance(value, (int, float)):
            return float(value)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue

    if _allow_toy_capex_fallback(params):
        logger.warning(
            "CAPEX extractor: no recognized key found. "
            "Using explicit toy fallback CAPEX=100.0"
        )
        return 100.0

    raise ValueError(
        "CAPEX extractor: no recognized CAPEX key found in finance/capex/costs "
        "sections or top-level CAPEX aliases. Set allow_toy_fallback=true only "
        "for explicit toy/test scenarios."
    )


def _rate_decimal(value: Any, default: float = 0.0) -> float:
    """Normalize a percentage or decimal interest-rate input."""
    raw = _as_float(value, default)
    return raw / 100.0 if raw > 1.0 else raw


def _clean_public_dscr_series(values: Sequence[Any]) -> List[float]:
    """Return lender-facing DSCR values suitable for min/max comparisons.

    Only the *undefined* sentinel is dropped: ``None`` and non-finite values (``inf`` /
    ``nan``), which arise when a period has no debt service (DSCR = CFADS/0). A FINITE
    value <= 0.0 is RETAINED — a 0.0 (CFADS = 0 against live debt service) or a negative
    DSCR is a real total-coverage breach and must surface in the lender-facing min, not be
    hidden behind an at-target headline. (Previously ``<= 0.0`` was filtered, conflating a
    real 0.0 breach with the missing/inf sentinel.)
    """
    clean: List[float] = []
    for value in values:
        if value is None:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(numeric):
            continue
        clean.append(numeric)
    return clean


def _extract_financing_terms(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return canonical financing terms from v14 or simple test schemas."""
    financing_terms = _section_case_insensitive(params, "Financing_Terms")
    if financing_terms:
        adapted = dict(financing_terms)
        if adapted.get("debt_ratio") is None:
            debt_pct = adapted.get("debt_pct")
            if debt_pct is None:
                debt_pct = adapted.get("leverage_pct")
            if debt_pct is not None:
                ratio = _as_float(debt_pct, 0.70)
                adapted["debt_ratio"] = ratio / 100.0 if ratio > 1.0 else ratio
        if adapted.get("construction_periods") is None:
            adapted["construction_periods"] = adapted.get("construction_years", 2)
        if adapted.get("debt_drawdown_pct") is None:
            adapted["debt_drawdown_pct"] = adapted.get("drawdown_pct", [0.5, 0.5])
        if adapted.get("construction_schedule") is None:
            adapted["construction_schedule"] = [40.0, 60.0]
        if adapted.get("mix") is None:
            adapted["mix"] = {"usd_commercial_min": 1.0}
        return adapted

    financing = _section_case_insensitive(params, "financing")
    if financing:
        return dict(financing)

    debt_cfg = _section_case_insensitive(params, "debt")
    if isinstance(debt_cfg, Mapping):
        debt_ratio = debt_cfg.get("debt_ratio")
        if debt_ratio is None:
            debt_ratio = debt_cfg.get("debt_ratio_pct")
        if debt_ratio is None:
            debt_ratio = debt_cfg.get("leverage_pct")
        debt_ratio_value = _as_float(debt_ratio, 0.70)
        if debt_ratio_value > 1.0:
            debt_ratio_value /= 100.0

        tenor_value = debt_cfg.get("tenor_years", debt_cfg.get("term_years", 15))
        rate_value = debt_cfg.get(
            "interest_rate_pct",
            debt_cfg.get("interest_rate", debt_cfg.get("usd_nominal", 0.0)),
        )
        usd_rate = _rate_decimal(rate_value, 0.0)

        return {
            "construction_periods": int(_as_float(debt_cfg.get("construction_periods"), 2)),
            "construction_schedule": debt_cfg.get("construction_schedule", [40.0, 60.0]),
            "debt_drawdown_pct": debt_cfg.get("debt_drawdown_pct", [0.5, 0.5]),
            "debt_ratio": debt_ratio_value,
            "tenor_years": int(_as_float(tenor_value, 15)),
            "interest_only_years": int(_as_float(debt_cfg.get("interest_only_years"), 0)),
            "amortization_style": debt_cfg.get("amortization_style", "annuity"),
            "target_dscr": _as_float(debt_cfg.get("target_dscr"), 1.30),
            "mix": debt_cfg.get("mix", {"usd_commercial_min": 1.0}),
            "rates": debt_cfg.get("rates", {"usd_nominal": usd_rate}),
        }

    return params


def _build_cfads_timeline(
    annual_rows: Sequence[Dict[str, Any]],
    cfads: Sequence[float],
    construction_periods: int,
    tenor: int,
) -> Tuple[List[float], List[Dict[str, Any]], int, Optional[int]]:
    """Build CFADS timeline and explicit annual-row-to-debt-period mapping."""
    cfads_ext: List[float] = [0.0] * construction_periods
    annual_row_debt_period_map: List[Dict[str, Any]] = []
    bridge_debt_period: Optional[int] = None

    if cfads:
        bridge_debt_period = len(cfads_ext)
        cfads_ext.append(float(cfads[0]) * 0.5)

    for row_index, row in enumerate(annual_rows):
        cfads_value = float(cfads[row_index]) if row_index < len(cfads) else 0.0
        debt_period = len(cfads_ext)
        cfads_ext.append(cfads_value)
        annual_row_debt_period_map.append(
            {
                "annual_row_index": row_index,
                "year": row.get("year", row_index + 1),
                "debt_period": debt_period,
                "cfads_usd": cfads_value,
            }
        )

    timeline_periods = max(construction_periods + tenor, len(cfads_ext))
    while len(cfads_ext) < timeline_periods:
        cfads_ext.append(float(cfads[-1]) if cfads else 0.0)

    return cfads_ext, annual_row_debt_period_map, timeline_periods, bridge_debt_period


def calculate_construction_drawdowns(
    total_debt: float,
    construction_schedule: List[float],
    drawdown_pct_per_year: List[float],
) -> List[float]:
    drawn_schedule: List[float] = []
    for i, _ in enumerate(construction_schedule):
        amt = (
            total_debt * float(drawdown_pct_per_year[i])
            if i < len(drawdown_pct_per_year)
            else 0.0
        )
        drawn_schedule.append(amt)
    return drawn_schedule


def calculate_idc(
    debt_drawn_schedule: List[float],
    interest_rate: float,
    construction_periods: int,
) -> Tuple[List[float], float]:
    idc_schedule: List[float] = []
    balance = 0.0
    total_idc = 0.0
    for period in range(len(debt_drawn_schedule)):
        balance += debt_drawn_schedule[period]
        idc = balance * interest_rate
        idc_schedule.append(idc)
        if period < construction_periods:
            total_idc += idc
            balance += idc
    return idc_schedule, total_idc


class Tranche:
    __slots__ = ("name", "rate", "principal", "years_io")

    def __init__(self, name: str, rate: float, principal: float, years_io: int) -> None:
        self.name = name
        self.rate = float(rate)
        self.principal = float(principal)
        self.years_io = int(years_io)


def _solve_mix(p: Dict[str, Any], debt_total: float) -> Dict[str, Tranche]:
    mix = p.get("mix", {})
    rates = p.get("rates", {})
    r_lkr = _as_float(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _as_float(rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0)
    r_dfi = _as_float(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)
    lkr = min(debt_total * _as_float(mix.get("lkr_max"), 0.0), debt_total)
    dfi = min(
        debt_total * _as_float(mix.get("dfi_max"), 0.0), max(0.0, debt_total - lkr)
    )
    usd = max(0.0, debt_total - lkr - dfi)
    years_io = int(_as_float(p.get("interest_only_years"), 0) or 0)
    return {
        "LKR": Tranche("LKR", r_lkr, lkr, years_io),
        "USD": Tranche("USD", r_usd, usd, years_io),
        "DFI": Tranche("DFI", r_dfi, dfi, years_io),
    }


def _annuity_schedule(
    tr: Tranche, amort_years: int
) -> List[Tuple[float, float, float]]:
    bal = tr.principal
    rows: List[Tuple[float, float, float]] = []
    for _ in range(tr.years_io):
        interest = bal * tr.rate
        rows.append((interest, 0.0, interest))
    if amort_years > 0:
        pmt = _pmt(tr.rate, amort_years, bal)
        for _ in range(amort_years):
            interest = bal * tr.rate
            principal = max(0.0, pmt - interest)
            bal = max(0.0, bal - principal)
            rows.append((interest, principal, interest + principal))
    return rows


def _sculpted_schedule(
    tranches: Dict[str, Tranche],
    amort_years: int,
    cfads: List[float],
    dscr_target: float,
) -> Dict[str, List[Tuple[float, float, float]]]:
    obals = {k: tr.principal for k, tr in tranches.items()}
    schedules: Dict[str, List[Tuple[float, float, float]]] = {k: [] for k in tranches}
    io_years = max(tr.years_io for tr in tranches.values())
    year_index = 0
    for _ in range(io_years):
        for k, tr in tranches.items():
            interest = obals[k] * tr.rate
            schedules[k].append((interest, 0.0, interest))
        year_index += 1
    for _ in range(amort_years):
        cf = cfads[year_index] if cfads and year_index < len(cfads) else 0.0
        target_svc = max(0.0, cf / dscr_target) if dscr_target > 0 else 0.0
        interest_map = {k: obals[k] * tranches[k].rate for k in tranches}
        principal_total = max(0.0, target_svc - sum(interest_map.values()))
        total_bal = sum(obals.values()) or 1.0
        for k in tranches:
            prorata = obals[k] / total_bal if total_bal > 0 else 0.0
            principal_k = min(obals[k], principal_total * prorata)
            obals[k] = max(0.0, obals[k] - principal_k)
            schedules[k].append(
                (interest_map[k], principal_k, interest_map[k] + principal_k)
            )
        year_index += 1
    return schedules


def apply_debt_layer(
    params: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Core v14 debt engine.

    Returns a rich dict used internally by plan_debt and the analytics layer.
    """
    p = _extract_financing_terms(params)

    construction_periods = max(0, int(_as_float(p.get("construction_periods"), 2)))
    construction_schedule = p.get("construction_schedule", [40.0, 60.0])
    drawdown_pct = p.get("debt_drawdown_pct", [0.5, 0.5])
    debt_ratio = _as_float(p.get("debt_ratio"), 0.70)
    tenor = max(0, int(_as_float(p.get("tenor_years"), 15)))
    years_io = max(0, int(_as_float(p.get("interest_only_years"), 0)))
    amortization = (p.get("amortization_style", "sculpted") or "sculpted").lower()
    target_dscr = _as_float(p.get("target_dscr"), 1.30)

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
    if amortization in ("annuity", "fixed"):
        schedules = {k: _annuity_schedule(t, amort_years) for k, t in tranches.items()}
    else:
        schedules = _sculpted_schedule(
            tranches,
            amort_years,
            cfads_ext[construction_periods:],
            target_dscr,
        )

    for k in schedules:
        schedules[k] = [(0.0, 0.0, 0.0)] * construction_periods + schedules[k]

    dscr_series: List[Optional[float]] = []
    debt_service_total: List[float] = []
    debt_outstanding: List[float] = []

    out_bals = {k: t.principal for k, t in tranches.items()}

    for period in range(timeline_periods):
        debt_outstanding.append(sum(out_bals.values()))
        svc = 0.0
        for k in schedules:
            if period < len(schedules[k]):
                _, princ, service = schedules[k][period]
                svc += service
                out_bals[k] = max(0.0, out_bals[k] - princ)
        debt_service_total.append(svc)
        cf = cfads_ext[period] if period < len(cfads_ext) else 0.0

        if period < construction_periods:
            dscr_series.append(None)
        elif svc > 0:
            dscr_series.append(cf / svc)
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
            svc = float(debt_service_total[debt_period]) + bridge_extra_service
            dscr_by_year[year_key] = (cf / svc) if svc > 0 else None
        else:
            dscr_by_year[year_key] = dscr_series[debt_period]

    dscr_op = [
        d for i, d in enumerate(dscr_series)
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

    cov_cfg = (p.get("covenants") or {}) if isinstance(p, dict) else {}
    llcr_discount_rate = _as_float(cov_cfg.get("llcr_discount_rate"), avg_debt_rate)
    plcr_discount_rate = _as_float(cov_cfg.get("plcr_discount_rate"), avg_debt_rate)

    project_cfads = (
        cfads[construction_periods:] if construction_periods < len(cfads) else []
    )
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
        "debt_outstanding": debt_outstanding,
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


def _solve_gearing_for_dscr(
    config: Dict[str, Any],
    annual_rows: List[Dict[str, Any]],
    target_dscr: float,
    max_ratio: float,
    *,
    step: float = 0.0025,
    fp_eps: float = 1e-6,
) -> float:
    """Largest gearing whose REAL-schedule min DSCR still meets ``target_dscr``.

    Min DSCR is non-increasing in gearing and PLATEAUS at the sculpt target for low
    gearing, then drops once the debt is too large for the schedule to hold the target.
    The goal is the MAX gearing on that plateau (maximum leverage at the target DSCR), so
    a tolerance ``dscr_tol`` is used to treat the plateau as "meets target" and converge on
    its upper edge rather than chasing floating-point noise deep inside it. Unlike the
    closed-form :func:`size_debt_with_dual_dscr`, this drives the actual amortization engine
    (grace period, declining-CFADS tail), so the achieved DSCR lands on target. If min DSCR
    at ``max_ratio`` already meets the target, ``max_ratio`` is returned unchanged.
    """

    def _min_dscr_at(ratio: float) -> float:
        cfg = copy.deepcopy(config)
        fin = _section_case_insensitive(cfg, "Financing_Terms")
        if isinstance(fin, dict):
            fin["debt_ratio"] = ratio
        else:
            cfg["debt_ratio"] = ratio
        core = apply_debt_layer(params=cfg, annual_rows=annual_rows)
        # Target the SAME public covenant metric plan_debt reports (cleaned series),
        # not the raw operational dscr_min (which includes the balloon/bridge period).
        public = _clean_public_dscr_series(core.get("dscr_series", []) or [])
        return min(public) if public else float(core.get("dscr_min", 0.0))

    # Scan gearing high -> low and return the MAX gearing whose achieved min DSCR meets
    # the target (an FP epsilon absorbs the sculpt's near-target rounding). min DSCR is
    # monotonic in gearing, so the first pass scanning down is the boundary -> max leverage
    # at the target, without the bisection's plateau/FP fragility.
    ratio = max_ratio
    while ratio > 0.0:
        if _min_dscr_at(ratio) >= target_dscr - fp_eps:
            return round(ratio, 6)
        ratio -= step
    return round(max(step, max_ratio - step), 6)


def _resolve_downside_ratio(
    config: Dict[str, Any], fin: Mapping[str, Any]
) -> Tuple[float, str]:
    """Per-period CFADS downside scale for the P90 (bankable downside) sizing case.

    Config-first: an explicit ``Financing_Terms.downside_cfads_factor`` override, else the
    REAL bankable P90/P50 AEP ratio from ``expected_results`` (when
    ``downside_aep_source: p90``), else the legacy flat ``dscr_p99_downside_factor`` (0.80
    proxy). Returns ``(ratio, source)``.
    """
    override = fin.get("downside_cfads_factor")
    if override is not None:
        return _as_float(override, 0.80), "explicit_factor"
    source = str(fin.get("downside_aep_source", "p90")).lower()
    if source == "p90":
        er = _section_case_insensitive(config, "expected_results") or {}
        p50 = _as_float(er.get("net_aep_p50_gwh"), 0.0)
        p90 = _as_float(er.get("net_aep_p90_gwh"), 0.0)
        if p50 > 0.0 and p90 > 0.0:
            return p90 / p50, "p90_aep"
    return _as_float(fin.get("dscr_p99_downside_factor"), 0.80), "flat_factor"


def _maybe_autosolve_dscr(
    config: Dict[str, Any], annual_rows: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Opt-in DSCR-based debt sizing (``Financing_Terms.debt_sizing: dual_dscr``).

    Solves the gearing on the real engine to hit ``target_dscr`` (capped at the configured
    ``debt_ratio``), and computes the dual-DSCR (P50 / P99) debt-capacity detail for the
    lender pack. Returns ``(config, dual_dscr_detail)`` -- ``config`` is resized only when
    the mode is active; ``dual_dscr_detail`` is ``None`` otherwise.

    When ``Financing_Terms.bind_downside`` is true, the bankable P90 (downside) production
    case ALSO binds the gearing: the engine solves a second gearing against a P90 schedule
    (annual CFADS rescaled by the real P90/P50 AEP ratio) at ``target_dscr_p90``, and the
    resized gearing is ``min(P50, P90)`` -- so the structure clears both the base DSCR and a
    downside DSCR floor. Default-off leaves the P50 solve as the sole driver (canonical
    gearing unchanged).
    """
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    mode = str(fin.get("debt_sizing", "")).lower()
    if mode not in ("dual_dscr", "auto_dscr", "dscr_sculpt"):
        return config, None

    target = _as_float(fin.get("target_dscr"), 1.30)
    max_ratio = _as_float(fin.get("debt_ratio"), 0.70)
    solved = _solve_gearing_for_dscr(config, annual_rows, target, max_ratio)

    # Optionally let the bankable P90 (downside) case BIND the gearing: size to
    # min(P50 gearing, P90 gearing). Default-off keeps the P50 solve as sole driver.
    bind_downside = _truthy_flag(fin.get("bind_downside"))
    binding_case = "P50"
    binding_gearing = solved
    solved_p90: Optional[float] = None
    if bind_downside:
        downside_ratio, downside_source = _resolve_downside_ratio(config, fin)
        target_p90 = _as_float(fin.get("target_dscr_p90"), target)
        p90_rows = [
            {**r, "cfads_usd": _as_float(r.get("cfads_usd"), 0.0) * downside_ratio}
            for r in annual_rows
        ]
        solved_p90 = _solve_gearing_for_dscr(config, p90_rows, target_p90, max_ratio)
        if solved_p90 < binding_gearing:
            binding_gearing, binding_case = solved_p90, "P90"
        downside = downside_ratio
    else:
        downside = _as_float(fin.get("dscr_p99_downside_factor"), 0.80)
        downside_source = "flat_factor"

    resized = copy.deepcopy(config)
    fin_resized = _section_case_insensitive(resized, "Financing_Terms")
    if isinstance(fin_resized, dict):
        fin_resized["debt_ratio"] = binding_gearing

    cfads = [_as_float(r.get("cfads_usd"), 0.0) for r in annual_rows]
    tenor = max(1, int(_as_float(fin.get("tenor_years"), 15)))
    capex = _extract_capex_usd(config)
    # NOTE: interest_rate_nominal here only discounts the dual-DSCR *capacity*
    # detail (lender-pack metadata). The real amortization uses the per-tranche
    # rates, so overriding Financing_Terms.interest_rate_nominal does NOT change
    # the achieved schedule or equity_irr.
    rate = _as_float(fin.get("interest_rate_nominal"), 0.08)
    detail: Optional[Dict[str, Any]] = None
    if cfads and capex > 0:
        try:
            detail = size_debt_with_dual_dscr(
                cfads[:tenor],
                [c * downside for c in cfads[:tenor]],
                dscr_target_p50=target,
                dscr_target_p99=_as_float(fin.get("dscr_target_p99"), 1.00),
                capex=capex,
                debt_ratio_max=max_ratio,
                debt_rate=rate,
            )
            detail["solved_gearing"] = binding_gearing
            detail["sizing_mode"] = mode
            detail["binding_production_case"] = binding_case
            detail["solved_gearing_p50"] = solved
            if solved_p90 is not None:
                detail["solved_gearing_p90"] = solved_p90
            detail["downside_ratio"] = round(downside, 6)
            detail["downside_source"] = downside_source
        except ValueError:
            detail = None
    logger.info(
        "DSCR debt sizing (%s): gearing %.3f (P50 %.3f%s) for target DSCR %.2f",
        mode,
        binding_gearing,
        solved,
        f"; P90 {solved_p90:.3f} -> binds {binding_case}" if solved_p90 is not None else "",
        target,
    )
    return resized, detail


def _maturity_period_index(
    debt_service_total: Sequence[float], construction_periods: int
) -> int:
    """Period index just AFTER the last scheduled senior service (balloon due here)."""
    nonzero = [
        i for i, s in enumerate(debt_service_total) if _as_float(s, 0.0) > _SERVICE_TOL
    ]
    return (max(nonzero) + 1) if nonzero else int(construction_periods)


def _refinance_terms(config: Dict[str, Any]) -> Tuple[int, float]:
    """(tenor_years, rate_premium) for a balloon refinance, from config with fallbacks."""
    refi = {}
    constraints = _section_case_insensitive(config, "constraints") or {}
    if isinstance(constraints.get("refinancing"), Mapping):
        refi = dict(constraints["refinancing"])
    tenor = int(_as_float(refi.get("refinance_tenor_years"), _REFINANCE_TENOR_DEFAULT))
    premium = _as_float(refi.get("refinance_rate_premium"), _REFINANCE_PREMIUM_DEFAULT)
    return max(1, tenor), premium


def _balloon_resolution_stream(
    *,
    treatment: str,
    balloon: float,
    cfads_ext: Sequence[float],
    debt_service_total: Sequence[float],
    construction_periods: int,
    timeline_periods: int,
    avg_rate: float,
    refi_tenor_years: int,
    refi_rate_premium: float,
) -> Tuple[List[float], float]:
    """Per-period cash diverted from equity to retire the balloon + residual.

    ``resolution[p]`` (USD) is senior to equity and aligned to the SAME period
    index as ``debt_service_total``. ``residual`` is any balloon still outstanding
    after the treatment (0.0 when fully resolved). ``cash_sweep``/``bullet``/
    ``refinance`` produce a stream; ``legacy_ignore``/``amortize`` produce none
    (``amortize`` removes the balloon by resizing debt upstream).
    """
    n = int(timeline_periods)
    resolution = [0.0] * n
    if balloon <= _BALLOON_TOL or treatment in ("legacy_ignore", "amortize"):
        return resolution, (0.0 if balloon <= _BALLOON_TOL else float(balloon))

    maturity = _maturity_period_index(debt_service_total, construction_periods)
    if maturity >= n:
        # No post-maturity period to resolve into → collapse to a terminal bullet.
        if n > 0:
            resolution[n - 1] = float(balloon)
        return resolution, 0.0

    if treatment == "bullet":
        resolution[maturity] = float(balloon)
        return resolution, 0.0

    if treatment == "refinance":
        rate = max(0.0, float(avg_rate) + float(refi_rate_premium))
        periods = max(1, int(refi_tenor_years))
        if rate > 0.0:
            factor = (rate * (1.0 + rate) ** periods) / ((1.0 + rate) ** periods - 1.0)
            annuity = float(balloon) * factor
        else:
            annuity = float(balloon) / periods
        for j in range(periods):
            p = maturity + j
            resolution[min(p, n - 1)] += annuity  # tail compresses into final period
        return resolution, 0.0

    # Default: cash_sweep — trap post-maturity CFADS until the balloon clears.
    remaining = float(balloon)
    for p in range(maturity, n):
        available = _as_float(cfads_ext[p], 0.0) if p < len(cfads_ext) else 0.0
        pay = min(max(0.0, available), remaining)
        resolution[p] = pay
        remaining -= pay
        if remaining <= _BALLOON_TOL:
            return resolution, 0.0
    return resolution, remaining


def _resize_for_amortization(
    config: Dict[str, Any],
    rows: List[Dict[str, Any]],
    core: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Reduce gearing until the sculpt fully amortises within tenor (no balloon).

    Bisects ``Financing_Terms.debt_ratio`` between 0 (always balloon-free) and the
    current solved gearing (has a balloon), returning the largest gearing whose
    ``balloon_remaining`` is ~0. No-op when the current schedule has no balloon.
    """
    if _as_float(core.get("balloon_remaining"), 0.0) <= _BALLOON_TOL:
        return config, core

    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    lo, hi = 0.0, _as_float(fin.get("debt_ratio"), 0.70)

    def _at_ratio(ratio: float) -> Dict[str, Any]:
        cfg = copy.deepcopy(config)
        fin_m = _section_case_insensitive(cfg, "Financing_Terms")
        if isinstance(fin_m, dict):
            fin_m["debt_ratio"] = ratio
        else:
            cfg["debt_ratio"] = ratio
        return cfg

    for _ in range(40):
        mid = (lo + hi) / 2.0
        trial = apply_debt_layer(params=_at_ratio(mid), annual_rows=rows)
        if _as_float(trial.get("balloon_remaining"), 0.0) > _BALLOON_TOL:
            hi = mid
        else:
            lo = mid
    resized_cfg = _at_ratio(lo)
    return resized_cfg, apply_debt_layer(params=resized_cfg, annual_rows=rows)


def _warn_if_decorative_tranches(config: Dict[str, Any]) -> None:
    """Warn once if a (non-input) ``Financing_Terms.debt_tranches`` block is present.

    The engine sizes debt via dual_dscr and splits it by ``mix`` proportions at the
    ``rates`` per currency; a hand-authored ``debt_tranches`` list is ignored. Flag it
    so the redundant block cannot silently drift from the engine's actual schedule.
    """
    global _warned_decorative_tranches
    if _warned_decorative_tranches:
        return
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    if fin.get("debt_tranches"):
        _warned_decorative_tranches = True
        logger.warning(
            "Financing_Terms.debt_tranches is NOT an engine input and is ignored; "
            "debt is sized via dual_dscr and split by Financing_Terms.mix proportions "
            "at Financing_Terms.rates. Edit mix + rates instead (the realised "
            "per-tranche principals are in debt_result.principal_by_tranche)."
        )


def _build_funding(config: Dict[str, Any], core: Dict[str, Any]) -> Dict[str, Any]:
    """Sources-and-Uses for the project, plus (opt-in) a DSRA funded at financial close.

    Wires the previously-decorative ``Financing_Terms.dsra_months`` / capex financing_fees
    into an explicit funding structure. When ``Financing_Terms.dsra.fund_at_close`` is true,
    the Debt Service Reserve (``target_months`` of year-1 debt service) is funded UP FRONT
    by additional equity — a prudent-lender structure — rather than built from operating
    cash; this raises the equity drawn at close and modestly lowers equity IRR. Default-off:
    ``initial_dsra`` is 0 and the equity investment is unchanged (CAPEX - debt).

    Balanced by construction: senior debt funds CAPEX-gearing + its own IDC; equity funds the
    CAPEX equity portion + the initial DSRA; so uses (CAPEX + IDC + DSRA) == sources.
    """
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    _dsra = fin.get("dsra")
    dsra_cfg: Mapping[str, Any] = _dsra if isinstance(_dsra, Mapping) else {}
    fund_at_close = _truthy_flag(dsra_cfg.get("fund_at_close"))
    target_months = _as_float(dsra_cfg.get("target_months", fin.get("dsra_months")), 6.0)

    construction_periods = int(_as_float(core.get("construction_periods"), 0))
    ds = core.get("debt_service_total", []) or []
    yr1_ds = float(ds[construction_periods]) if len(ds) > construction_periods else 0.0
    initial_dsra = (target_months / 12.0) * yr1_ds if fund_at_close else 0.0

    capex = _extract_capex_usd(config)
    debt_total = _as_float(core.get("debt_total"), 0.0)
    total_idc = _as_float(core.get("total_idc_capitalized"), 0.0)
    equity_total = max(0.0, capex - debt_total) + initial_dsra
    senior_debt = debt_total + total_idc

    financing_fees = 0.0
    cap = config.get("capex")
    if isinstance(cap, Mapping) and isinstance(cap.get("breakdown"), Mapping):
        financing_fees = _as_float(cap["breakdown"].get("financing_fees_usd"), 0.0)

    uses_total = capex + total_idc + initial_dsra
    sources_total = senior_debt + equity_total
    return {
        "fund_at_close": fund_at_close,
        "dsra_target_months": round(target_months, 2),
        "initial_dsra_usd": round(initial_dsra, 2),
        "financing_fees_in_capex_usd": round(financing_fees, 2),
        "sources_and_uses": {
            "uses": {
                "capex_usd": round(capex, 2),
                "idc_usd": round(total_idc, 2),
                "initial_dsra_usd": round(initial_dsra, 2),
            },
            "sources": {
                "senior_debt_usd": round(senior_debt, 2),
                "equity_usd": round(equity_total, 2),
            },
            "uses_total_usd": round(uses_total, 2),
            "sources_total_usd": round(sources_total, 2),
            "balanced": abs(uses_total - sources_total) < 1.0,
        },
    }


def plan_debt(
    *,
    annual_rows: Sequence[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Plan debt for the project using the v14 engine.

    When ``Financing_Terms.debt_sizing`` is ``dual_dscr`` / ``auto_dscr``, the gearing is
    first solved on the real schedule to hit ``target_dscr`` (capped at ``debt_ratio``),
    and the dual-DSCR (P50/P99) capacity detail is attached under ``dual_dscr``.

    The debt mix/rates are governed by ``Financing_Terms.mix`` + ``Financing_Terms.rates``;
    a ``Financing_Terms.debt_tranches`` list is not an engine input (see
    :func:`_warn_if_decorative_tranches`).
    """
    rows = list(annual_rows)
    _warn_if_decorative_tranches(config)
    config, dual_dscr_detail = _maybe_autosolve_dscr(config, rows)
    core = apply_debt_layer(params=config, annual_rows=rows)

    # ── Balloon treatment ──────────────────────────────────────────────────
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    treatment = str(
        fin.get("balloon_treatment", _BALLOON_DEFAULT_TREATMENT)
        or _BALLOON_DEFAULT_TREATMENT
    ).lower()
    if treatment not in _BALLOON_VALID_TREATMENTS:
        logger.warning(
            "Unknown balloon_treatment %r; falling back to %s",
            treatment,
            _BALLOON_DEFAULT_TREATMENT,
        )
        treatment = _BALLOON_DEFAULT_TREATMENT

    if treatment == "amortize":
        config, core = _resize_for_amortization(config, rows, core)

    structural_balloon = _as_float(core.get("balloon_remaining"), 0.0)
    refi_tenor, refi_premium = _refinance_terms(config)
    balloon_resolution, balloon_residual = _balloon_resolution_stream(
        treatment=treatment,
        balloon=structural_balloon,
        cfads_ext=core.get("cfads_extended", []) or [],
        debt_service_total=core.get("debt_service_total", []) or [],
        construction_periods=int(core.get("construction_periods", 0) or 0),
        timeline_periods=int(core.get("timeline_periods", 0) or 0),
        avg_rate=_as_float(core.get("avg_debt_rate"), 0.0),
        refi_tenor_years=refi_tenor,
        refi_rate_premium=refi_premium,
    )
    # balloon_remaining is the residual of the IDC-INCLUSIVE amortizing principal
    # (sum of principal_after_idc), so the fraction must use that same base — not the
    # pre-IDC debt_total, which mixes bases and overstates the balloon.
    amortizing_base = sum(
        _as_float(v, 0.0) for v in (core.get("principal_after_idc", {}) or {}).values()
    )
    if amortizing_base <= 0.0:  # fallback if IDC detail is absent
        amortizing_base = _as_float(core.get("debt_total"), 0.0)
    balloon_pct = structural_balloon / amortizing_base if amortizing_base > 0 else 0.0
    max_balloon_pct = _as_float(
        (_section_case_insensitive(config, "constraints") or {}).get("max_balloon_pct"),
        0.10,
    )
    balloon_covenant_breach = balloon_pct > max_balloon_pct

    principal_by = {
        k.lower(): float(v)
        for k, v in (core.get("principal_after_idc", {}) or {}).items()
    }
    idc_by = {
        k.lower(): float(v) for k, v in (core.get("idc_by_tranche", {}) or {}).items()
    }

    timeline = core.get("timeline_periods", 0)
    debt_outstanding = core.get("debt_outstanding", []) or []
    debt_service_total = core.get("debt_service_total", []) or []
    public_dscr_series = _clean_public_dscr_series(core.get("dscr_series", []) or [])
    min_dscr = min(public_dscr_series) if public_dscr_series else core.get("dscr_min", 0.0)

    return {
        "construction_years": core.get("construction_periods", 0),
        "tenor_years": core.get("tenor_years", 0),
        "timeline_periods": timeline,
        "lkr": {
            "principal": principal_by.get("lkr", 0.0),
            "principal_m": principal_by.get("lkr", 0.0),
            "idc": idc_by.get("lkr", 0.0),
            "idc_m": idc_by.get("lkr", 0.0),
        },
        "usd": {
            "principal": principal_by.get("usd", 0.0),
            "principal_m": principal_by.get("usd", 0.0),
            "idc": idc_by.get("usd", 0.0),
            "idc_m": idc_by.get("usd", 0.0),
        },
        "dfi": {
            "principal": principal_by.get("dfi", 0.0),
            "principal_m": principal_by.get("dfi", 0.0),
            "idc": idc_by.get("dfi", 0.0),
            "idc_m": idc_by.get("dfi", 0.0),
        },
        "total_idc": core.get("total_idc_capitalized", 0.0),
        "total_idc_m": core.get("total_idc_capitalized", 0.0),
        "min_dscr": min_dscr,
        "principal_by_tranche": principal_by,
        "idc_by_tranche": idc_by,
        "audit_status": core.get("audit_status", "REVIEW"),
        "debt_outstanding": debt_outstanding,
        "debt_service_total": debt_service_total,
        "total_service": debt_service_total,
        "dscr_series": public_dscr_series,
        "raw_dscr_series": core.get("dscr_series", []),
        "dscr_by_year": core.get("dscr_by_year", {}),
        "annual_row_debt_period_map": core.get("annual_row_debt_period_map", []),
        "cfads_bridge_debt_period": core.get("cfads_bridge_debt_period"),
        "balloon_remaining": structural_balloon,
        "balloon_treatment": treatment,
        "balloon_resolution": balloon_resolution,
        "balloon_residual": balloon_residual,
        "balloon_pct": balloon_pct,
        "balloon_covenant_breach": balloon_covenant_breach,
        "max_balloon_pct": max_balloon_pct,
        "debt_schedules": core.get("debt_schedules", {}),
        "debt_total": core.get("debt_total", 0.0),
        "avg_debt_rate": core.get("avg_debt_rate", 0.0),
        "llcr": core.get("llcr", 0.0),
        "plcr": core.get("plcr", 0.0),
        "fx_min": core.get("fx_min"),
        "fx_max": core.get("fx_max"),
        "fx_avg": core.get("fx_avg"),
        "dual_dscr": dual_dscr_detail,
        "funding": _build_funding(config, core),
    }


def size_debt_with_dual_dscr(
    cfads_p50: Sequence[float],
    cfads_p99: Sequence[float],
    *,
    dscr_target_p50: float = 1.30,
    dscr_target_p99: float = 1.00,
    capex: float,
    debt_ratio_max: float = 0.70,
    debt_rate: float = 0.08,
) -> Dict[str, Any]:
    """Size project debt under a dual DSCR (P50 / P99) constraint.

    Implements the standard lender dual-DSCR methodology (e.g. Bolinger 2017,
    DNV GL 2019): debt service is sculpted so the achieved DSCR equals the target
    in each scenario, the conservative ``min(Debt_P50, Debt_P99)`` is taken, and
    the result is capped at ``debt_ratio_max * capex``.

    For each period the sustainable debt service is ``CFADS / DSCR_target`` (so
    the achieved DSCR equals the target), and the scenario debt capacity is the
    present value of that debt-service stream discounted at ``debt_rate`` over
    periods 1..N (matching :func:`_npv`).

    Args:
        cfads_p50: Per-period Cash Flow Available for Debt Service, P50 (central)
            scenario. Must be non-empty.
        cfads_p99: Per-period CFADS, P99 (downside) scenario. Must be the same
            length as ``cfads_p50``.
        dscr_target_p50: Minimum DSCR target for the P50 scenario (must be > 0).
        dscr_target_p99: Minimum DSCR target for the P99 scenario (must be > 0).
        capex: Total project capital cost (must be > 0); sets the gearing cap.
        debt_ratio_max: Maximum debt-to-CAPEX gearing, in ``(0, 1]``.
        debt_rate: Periodic cost of debt used to discount debt service.

    Returns:
        Mapping with the sized debt and supporting detail. Keys: ``debt_sized``,
        ``debt_p50``, ``debt_p99``, ``binding_constraint`` (``"P50"`` |
        ``"P99"`` | ``"RATIO_CAP"``), ``debt_service_p50`` / ``debt_service_p99``,
        ``dscr_profile_p50`` / ``dscr_profile_p99``, ``min_dscr_p50`` /
        ``min_dscr_p99``, ``dscr_target_p50`` / ``dscr_target_p99``,
        ``debt_ratio_cap``, ``capex`` and ``downside_impact_pct`` (the P99-vs-P50
        debt-capacity reduction, in percent).

    Raises:
        ValueError: If CFADS arrays are empty or different lengths, if a DSCR
            target is non-positive, if ``debt_ratio_max`` is outside ``(0, 1]``,
            or if ``capex`` is non-positive.
    """
    cfads_p50 = [float(x) for x in cfads_p50]
    cfads_p99 = [float(x) for x in cfads_p99]

    if not cfads_p50 or not cfads_p99:
        raise ValueError("CFADS arrays cannot be empty")
    if len(cfads_p50) != len(cfads_p99):
        raise ValueError("CFADS P50 and P99 arrays must have the same length")
    if dscr_target_p50 <= 0.0 or dscr_target_p99 <= 0.0:
        raise ValueError("DSCR target must be positive")
    if not (0.0 < debt_ratio_max <= 1.0):
        raise ValueError("Debt ratio must be in (0, 1]")
    if capex <= 0.0:
        raise ValueError("CAPEX must be positive")

    def _size_one(
        cfads: Sequence[float], target: float
    ) -> Tuple[List[float], float, List[float], float]:
        service = [cf / target for cf in cfads]
        capacity = _npv(service, debt_rate)
        profile = [
            (cf / svc) if svc > 0 else float("inf")
            for cf, svc in zip(cfads, service)
        ]
        min_dscr = min(profile) if profile else 0.0
        return service, capacity, profile, min_dscr

    service_p50, debt_p50, profile_p50, min_dscr_p50 = _size_one(cfads_p50, dscr_target_p50)
    service_p99, debt_p99, profile_p99, min_dscr_p99 = _size_one(cfads_p99, dscr_target_p99)

    ratio_cap = capex * debt_ratio_max
    debt_uncapped = min(debt_p50, debt_p99)
    debt_sized = min(debt_uncapped, ratio_cap)

    if debt_sized < debt_uncapped:
        binding_constraint = "RATIO_CAP"
    elif debt_p99 <= debt_p50:
        binding_constraint = "P99"
    else:
        binding_constraint = "P50"

    downside_impact_pct = (
        (debt_p50 - debt_p99) / debt_p50 * 100.0 if debt_p50 > 0 else 0.0
    )

    return {
        "debt_sized": debt_sized,
        "debt_p50": debt_p50,
        "debt_p99": debt_p99,
        "binding_constraint": binding_constraint,
        "debt_service_p50": service_p50,
        "debt_service_p99": service_p99,
        "dscr_profile_p50": profile_p50,
        "dscr_profile_p99": profile_p99,
        "min_dscr_p50": min_dscr_p50,
        "min_dscr_p99": min_dscr_p99,
        "dscr_target_p50": dscr_target_p50,
        "dscr_target_p99": dscr_target_p99,
        "debt_ratio_cap": ratio_cap,
        "capex": capex,
        "downside_impact_pct": downside_impact_pct,
    }


# EOF
