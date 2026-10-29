"""Financing terms and period taxonomy extraction (extracted from debt_v14)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.debt.helpers import (
    _as_float,
    _get,
    _lookup_case_insensitive,
    _rate_decimal,
    _section_case_insensitive,
)
from finance.debt.placeholders import _warn_placeholder_once

logger = logging.getLogger("finance.debt_v14")

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
            fallback_drawdown = adapted.get("drawdown_pct")
            if fallback_drawdown is None:
                _warn_placeholder_once(
                    "Financing_Terms.debt_drawdown_pct",
                    "Financing_Terms.debt_drawdown_pct / drawdown_pct absent — using a "
                    "placeholder even draw [0.5, 0.5]; IDC is draw-timing-sensitive, so "
                    "supply the EPC milestone draw schedule for a lender-grade figure.",
                )
                fallback_drawdown = [0.5, 0.5]
            adapted["debt_drawdown_pct"] = fallback_drawdown
        if adapted.get("construction_schedule") is None:
            _warn_placeholder_once(
                "Financing_Terms.construction_schedule",
                "Financing_Terms.construction_schedule absent — using a placeholder "
                "[40, 60] capex phasing; supply the EPC milestone schedule for a "
                "lender-grade figure.",
            )
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

        construction_schedule = debt_cfg.get("construction_schedule")
        if construction_schedule is None:
            _warn_placeholder_once(
                "debt.construction_schedule",
                "debt.construction_schedule absent — using a placeholder [40, 60] "
                "capex phasing; supply the EPC milestone schedule for a "
                "lender-grade figure.",
            )
            construction_schedule = [40.0, 60.0]
        debt_drawdown_pct = debt_cfg.get("debt_drawdown_pct")
        if debt_drawdown_pct is None:
            _warn_placeholder_once(
                "debt.debt_drawdown_pct",
                "debt.debt_drawdown_pct absent — using a placeholder even draw "
                "[0.5, 0.5]; IDC is draw-timing-sensitive, so supply the EPC "
                "milestone draw schedule for a lender-grade figure.",
            )
            debt_drawdown_pct = [0.5, 0.5]

        return {
            "construction_periods": int(
                _as_float(debt_cfg.get("construction_periods"), 2)
            ),
            "construction_schedule": construction_schedule,
            "debt_drawdown_pct": debt_drawdown_pct,
            "debt_ratio": debt_ratio_value,
            "tenor_years": int(_as_float(tenor_value, 15)),
            "interest_only_years": int(
                _as_float(debt_cfg.get("interest_only_years"), 0)
            ),
            "amortization_style": debt_cfg.get("amortization_style", "annuity"),
            "target_dscr": _as_float(debt_cfg.get("target_dscr"), 1.30),
            "mix": debt_cfg.get("mix", {"usd_commercial_min": 1.0}),
            "rates": debt_cfg.get("rates", {"usd_nominal": usd_rate}),
        }

    return params


def _resolve_construction_periods(params: Mapping[str, Any]) -> int:
    """Resolve the debt construction-period count without extraction side effects."""
    financing_terms = _section_case_insensitive(params, "Financing_Terms")
    if financing_terms:
        value = financing_terms.get("construction_periods")
        if value is None:
            value = financing_terms.get("construction_years", 2)
        return max(0, int(_as_float(value, 2)))

    financing = _section_case_insensitive(params, "financing")
    if financing:
        return max(0, int(_as_float(financing.get("construction_periods"), 2)))

    debt_cfg = _section_case_insensitive(params, "debt")
    if debt_cfg is not None:
        return max(0, int(_as_float(debt_cfg.get("construction_periods"), 2)))

    return max(0, int(_as_float(params.get("construction_periods"), 2)))


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


def _resolve_first_operating_period(
    annual_row_debt_period_map: Sequence[Mapping[str, Any]],
    construction_periods: int,
    bridge_debt_period: Optional[int],
) -> int:
    """Resolve the first debt period that carries an operating row."""
    mapped: List[int] = []
    for mapping in annual_row_debt_period_map:
        try:
            mapped.append(int(mapping["debt_period"]))
        except (KeyError, TypeError, ValueError):
            continue
    if mapped:
        return max(0, min(mapped))
    return max(0, int(construction_periods)) + (0 if bridge_debt_period is None else 1)
