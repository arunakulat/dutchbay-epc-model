"""Funding / sources-and-uses packaging (extracted from debt_v14)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from finance.debt.helpers import _as_float, _section_case_insensitive
from finance.debt.placeholders import _truthy_flag
from finance.debt.capex import _extract_capex_usd, _extract_capex_base_usd
from finance.debt.terms import _build_cfads_timeline, _extract_financing_terms
from finance.import_levies import compute_capex_uplift_usd, resolve_indirect_taxes

logger = logging.getLogger("finance.debt_v14")

_warned_decorative_tranches = False

def _warn_if_decorative_tranches(config: Dict[str, Any]) -> None:
    """Warn once if a (non-input) ``Financing_Terms.debt_tranches`` block is present."""
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
    """Sources-and-Uses for the project, plus (opt-in) a DSRA funded at financial close."""
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    _dsra = fin.get("dsra")
    dsra_cfg: Mapping[str, Any] = _dsra if isinstance(_dsra, Mapping) else {}
    fund_at_close = _truthy_flag(dsra_cfg.get("fund_at_close"))
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
