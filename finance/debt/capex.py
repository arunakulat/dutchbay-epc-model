"""CAPEX extraction for debt sizing (extracted from debt_v14)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from finance.import_levies import (
    compute_capex_uplift_usd,
    resolve_indirect_taxes,
)
from finance.debt.helpers import (
    _lookup_case_insensitive,
    _section_case_insensitive,
)
from finance.debt.placeholders import (
    _allow_toy_capex_fallback,
)

logger = logging.getLogger("finance.debt_v14")


def _extract_capex_base_usd(params: Dict[str, Any]) -> float:
    """Extract the PRE-LEVY CAPEX base from config (v14, legacy and compact schemas).

    When ``capex.derive_from_breakdown`` is truthy, CAPEX is computed BOTTOM-UP as the
    sum of the numeric line items under ``capex.breakdown`` (single source of truth, no
    flat-total/breakdown divergence). Otherwise the flat ``capex.usd_total`` (etc.) is
    used. If both a derived sum and an explicit ``usd_total`` are present, they are
    cross-checked and a mismatch >0.5% raises (CESSPIT: the two must not silently differ).

    #738: this is the pre-``taxes_indirect`` base — ``capex.usd_total`` stays the
    PRE-LEVY figure (the WBS breakdown-sums-to-usd_total invariant and the 0.5%
    cross-check both keep operating on it, with no tolerance interaction from the
    levies). The financed, levy-inclusive total is the :func:`_extract_capex_usd`
    wrapper below.
    """
    capex_section = _section_case_insensitive(params, "capex")
    if capex_section and _lookup_case_insensitive(
        capex_section, "derive_from_breakdown"
    ):
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
            raise ValueError(
                "capex.breakdown sums to <= 0; provide positive line items"
            )

        # AACE QRA contingency: when capex.contingency.method == 'qra', the contingency
        # is RECOMPUTED from the base cost (breakdown minus its contingency line) + the
        # risk inputs, instead of the fixed line item. Otherwise the fixed breakdown sum
        # stands and is cross-asserted against usd_total.
        from analytics.cost.contingency import contingency_is_qra, resolve_contingency

        if contingency_is_qra(capex_section):
            # QRA intentionally OVERRIDES any stated capex.usd_total (the contingency is
            # recomputed from the risk inputs), so there is no usd_total cross-check here.
            # The NPV/IRR capex base is kept consistent by routing metrics._derive_capex_usd
            # through this same resolver when derive_from_breakdown is set (no divergence).
            contingency_line = float(
                _lookup_case_insensitive(breakdown, "contingency_usd") or 0.0
            )
            base_cost = line_total - contingency_line
            derived = (
                base_cost
                + resolve_contingency(base_cost, capex_section).contingency_usd
            )
            if derived <= 0:
                raise ValueError(
                    "QRA-derived CAPEX is <= 0; check the breakdown / risk inputs"
                )
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


def _extract_capex_usd(
    params: Dict[str, Any], *, include_import_levies: bool = True
) -> float:
    """Financed CAPEX in USD: the pre-levy base plus capitalized import levies (#738).

    THE single capex resolution seam (debt sizing, dual-DSCR detail, sources &
    uses / equity, and — by delegation — ``analytics.core.metrics`` NPV base and
    ``finance.equity_distribution_v14_hydra``). When the config declares a
    ``taxes_indirect:`` block, the import duties + unrecoverable capex VAT
    capitalize on top of the base (single uplift source:
    ``finance.import_levies``), so debt sizing, IDC (financed duties attract IDC),
    gearing, equity and the depreciable base all gross the identical uplift.
    ABSENT block => the base, byte-identical.

    ``include_import_levies=False`` returns the PRE-LEVY base — used by the capex
    Monte Carlo (``analytics.cost.mc_capex``) so a trial perturbs the base and the
    pipeline re-applies levies on the perturbed base, instead of levying an
    already-grossed total twice.
    """
    base = _extract_capex_base_usd(params)
    if not include_import_levies:
        return base
    indirect = resolve_indirect_taxes(params)
    if indirect is None or not indirect.has_capex_lines:
        return base
    return base + compute_capex_uplift_usd(base, indirect)
