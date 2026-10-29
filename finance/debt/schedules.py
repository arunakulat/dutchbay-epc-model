"""Tranche mix and amortization schedules (extracted from debt_v14)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from finance.debt.helpers import _as_float, _pmt, _rate_decimal

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
    # Normalize each tranche rate through _rate_decimal (percent-form -> decimal for any
    # value > 1.0), matching the sibling `debt`-block path (see _extract_financing_terms,
    # which already routes interest_rate_pct through _rate_decimal). Previously these read
    # the rate with a bare _as_float, so a canonical Financing_Terms.rates entry authored in
    # percent form (e.g. lkr_nominal: 13.39 instead of 0.1339) reached _annuity_schedule as
    # interest = balance * 13.39 (1339%/yr) with no error -- the cost-free-debt guard only
    # catches rate <= 0. Every committed scenario declares decimal rates (< 1.0), so this is
    # byte-identical for them; it only rescues a mis-scaled percent-form input, and closes the
    # config-shape asymmetry between the two debt paths (round-2 audit, FIN-02).
    r_lkr = _rate_decimal(rates.get("lkr_nominal") or rates.get("lkr_min"), 0.0)
    r_usd = _rate_decimal(
        rates.get("usd_nominal") or rates.get("usd_commercial_min"), 0.0
    )
    r_dfi = _rate_decimal(rates.get("dfi_nominal") or rates.get("dfi_min"), 0.0)
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
    senior_fee_rate: float = 0.0,
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
        # Fee-inside-the-sculpt (#737): the annual credit-support fee (guarantee + PRI,
        # senior_fee_rate x the OPENING outstanding balance) ranks senior to debt service,
        # so the CFADS available for sculpting is net of it — the bankable-correct
        # treatment (pre-fee sizing oversizes debt). The gearing solve re-runs this whole
        # schedule per candidate, so leverage is re-sized fee-inclusively with no extra
        # loop. apply_debt_layer's reported DSCR nets the SAME rate x opening-outstanding
        # fee, which is what lands the reported DSCR exactly on target. 0.0 rate is
        # byte-identical. NOTE: with interest-only years the first sculpt entry is the
        # synthetic half-year bridge period, which is an IO year for every committed
        # scenario; an io_years=0 config would fee-net the bridge here while the reported
        # series charges it no fee — sizing then errs conservative (DSCR above target).
        fee = senior_fee_rate * sum(obals.values())
        cf_net = cf - fee
        target_svc = max(0.0, cf_net / dscr_target) if dscr_target > 0 else 0.0
        interest_map = {k: obals[k] * tranches[k].rate for k in tranches}
        principal_total = max(0.0, target_svc - sum(interest_map.values()))
        total_bal = sum(obals.values()) or 1.0
        for k in tranches:
            # FIN-5 (#482, reviewed): the sculpted principal is shared across tranches
            # PRO-RATA BY OUTSTANDING BALANCE. This is deliberate — pari-passu pro-rata
            # amortisation is the standard multi-creditor convention; lenders on the cheaper
            # tranches (USD/DFI) will not accept being amortised slower so the expensive LKR
            # tranche can be paid down first. Cost-weighted ("retire the dearest debt first")
            # allocation would lower total interest but is non-standard inter-creditor terms
            # and KPI-moving, so it is NOT the default (a future configurable waterfall could
            # offer it). See the audit FIN-5 "review" note.
            prorata = obals[k] / total_bal if total_bal > 0 else 0.0
            principal_k = min(obals[k], principal_total * prorata)
            obals[k] = max(0.0, obals[k] - principal_k)
            schedules[k].append(
                (interest_map[k], principal_k, interest_map[k] + principal_k)
            )
        year_index += 1
    return schedules
