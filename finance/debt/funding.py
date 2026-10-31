"""Sources and uses of funds for the financed project cost."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from finance.debt.capex import _extract_capex_base_usd, _extract_capex_usd
from finance.debt.helpers import _as_float, _section_case_insensitive, _truthy_flag
from finance.import_levies import compute_capex_uplift_usd, resolve_indirect_taxes


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
    # DSRA months precedence: dsra.target_months -> Financing_Terms.dsra_months ->
    # Financing_Terms.reserves.dsra_months -> 6.0. The canonical nests it under `reserves`
    # (the path scenarios actually author); the prior resolver missed that nesting and only
    # matched the 6.0 default by coincidence, so a scenario setting reserves.dsra_months != 6
    # was silently ignored.
    _reserves = fin.get("reserves")
    reserves: Mapping[str, Any] = _reserves if isinstance(_reserves, Mapping) else {}
    target_months = _as_float(
        dsra_cfg.get(
            "target_months", fin.get("dsra_months", reserves.get("dsra_months"))
        ),
        6.0,
    )

    construction_periods = int(_as_float(core.get("construction_periods"), 0))
    ds = core.get("debt_service_total", []) or []
    # Size the DSRA off OPERATING YEAR 1's debt service, not the synthetic half-year
    # "bridge" lead-in period. `debt_service_total` is on the debt timeline built by
    # `_build_cfads_timeline`: when a bridge period is present it sits at index
    # `construction_periods` and operating year 1 is at `construction_periods + 1`, so
    # indexing `construction_periods` directly grabbed the bridge -- which carries only a
    # half-year of interest when `interest_only_years < 2` -- and under-reserved the DSRA
    # (~50% low in the io=0 case), understating equity-at-close and overstating equity IRR.
    # Reuse the engine's own operating-year-1 debt period (row 0 of
    # `annual_row_debt_period_map`, the same period the year-1 DSCR is computed against) so
    # this stays correct whether or not a bridge period exists (audit round-2 DSRA fix).
    period_map = core.get("annual_row_debt_period_map") or []
    op_year1_period = (
        int(period_map[0]["debt_period"])
        if period_map and "debt_period" in period_map[0]
        else construction_periods
    )
    yr1_ds = float(ds[op_year1_period]) if len(ds) > op_year1_period else 0.0
    initial_dsra = (target_months / 12.0) * yr1_ds if fund_at_close else 0.0

    capex = _extract_capex_usd(config)
    debt_total = _as_float(core.get("debt_total"), 0.0)
    total_idc = _as_float(core.get("total_idc_capitalized"), 0.0)
    equity_total = max(0.0, capex - debt_total) + initial_dsra
    senior_debt = debt_total + total_idc

    # #738 disclosure: the import-levy share INSIDE the gross capex_usd above
    # (duties + unrecoverable VAT, from the same pure cascade the resolver
    # applies). A breakdown line, NOT a new addend — uses_total is unchanged.
    indirect = resolve_indirect_taxes(config)
    import_levies = (
        compute_capex_uplift_usd(_extract_capex_base_usd(config), indirect)
        if indirect is not None and indirect.has_capex_lines
        else 0.0
    )

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
                # of-which disclosure (#738): import duties + unrecoverable VAT
                # already inside capex_usd; NOT added to uses_total again.
                "import_levies_usd": round(import_levies, 2),
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
