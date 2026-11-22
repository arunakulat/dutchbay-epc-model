"""Recomputed P90 downside, reported beside the CFADS-ratio approximation (#1836).

The debt sizing builds its downside case by multiplying each year's CFADS by one factor,
the P90/P50 energy ratio (``finance.debt.sizing._resolve_downside_ratio``). Scaling CFADS
by an energy ratio is not the same as re-running the cash flow at P90 energy: fixed opex
does not fall with production, and tax, levies, reserves and FX make the response
nonlinear. This module measures the difference.

For a scenario that declares an ``expected_results`` P50/P90 pair it runs two cases
through the canonical gateway (:func:`analytics.evaluation_v14.evaluate_with_overrides`):

* the base case, unchanged, which fixes the committed debt (its service and fee);
* a P90 case: every billed capacity factor (the project headline and each generation
  technology in ``generation.technologies``) scaled by P90/P50, all else unchanged, so
  opex, tax, levies, the waterfall and reserves are recomputed by the engine.

Both the ratio method (base CFADS x P90/P50) and the recomputed P90 CFADS are then set
against the base case's FIXED debt service on the covenant basis
(:func:`analytics.mc.fixed_debt_coverage.fixed_debt_coverage_by_row`), and the minimum and
average annual DSCR and the LLCR are reported for each, with their difference.

What it is not: it changes no sizing, no input and no KPI. It is a modelled one-year
exceedance on the scenario's own resource basis, not a lender P90 claim. Figures are
annual only (F-5: no quarterly CFADS or intra-year DSCR). Stated limit (as #1728 L-2):
the P90 case's CFADS is its own pipeline's figure, so a CFADS term that depends on its own
re-sized debt (interest deductibility in tax) is not re-based to the committed debt.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.fixed_debt_coverage import fixed_debt_coverage_by_row
from finance.cashflow_v14_utils import CAPACITY_FACTOR_PATHS
from finance.irr import npv
from finance.tech_types import is_storage_type

LABEL = (
    "Modelled 1-year exceedance (P90) on the scenario's own resource basis, against the "
    "base case's committed debt. Not a lender P90 claim. Annual figures only (F-5). "
    "Sizing, inputs and KPIs are unchanged (#1836)."
)


def _section(config: Mapping[str, Any], name: str) -> Optional[Mapping[str, Any]]:
    """A top-level section by case-insensitive name, or ``None``."""
    for key, value in config.items():
        if str(key).lower() == name.lower() and isinstance(value, Mapping):
            return value
    return None


def _positive(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) and out > 0.0 else None


def p90_energy_ratio(config: Mapping[str, Any]) -> Optional[Tuple[float, float, float]]:
    """``(p50_gwh, p90_gwh, p90/p50)`` from ``expected_results``, or ``None`` without a pair."""
    er = _section(config, "expected_results") or {}
    p50 = _positive(er.get("net_aep_p50_gwh"))
    p90 = _positive(er.get("net_aep_p90_gwh"))
    if p50 is None or p90 is None:
        return None
    return p50, p90, p90 / p50


def p90_production_config(config: Mapping[str, Any], ratio: float) -> Dict[str, Any]:
    """A copy of ``config`` producing ``ratio`` x its billed energy, all else unchanged.

    Scales the capacity factor the engine bills off (the first present of
    ``finance.cashflow_v14_utils.CAPACITY_FACTOR_PATHS``, the engine's own resolution) and
    each generation technology's ``capacity_factor``, so the multi-technology
    reconciliation still holds. Storage blocks are not generation and are left alone.
    ``expected_results.net_aep_p50_gwh`` is set to the P90 energy, so the case declares
    the energy it bills.

    Raises:
        ValueError: When no billed capacity factor resolves.
    """
    out: Dict[str, Any] = copy.deepcopy(dict(config))
    scaled = False
    for path in CAPACITY_FACTOR_PATHS:
        keys = (path,) if isinstance(path, str) else tuple(path)
        node: Any = out
        for key in keys[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
        if isinstance(node, dict) and _positive(node.get(keys[-1])) is not None:
            node[keys[-1]] = float(node[keys[-1]]) * ratio
            scaled = True
            break
    if not scaled:
        raise ValueError("no billed capacity factor resolves; cannot build a P90 case")
    generation = out.get("generation")
    techs = generation.get("technologies") if isinstance(generation, dict) else None
    if isinstance(techs, dict):
        for block in techs.values():
            if not isinstance(block, dict) or is_storage_type(block.get("type")):
                continue
            if _positive(block.get("capacity_factor")) is not None:
                block["capacity_factor"] = float(block["capacity_factor"]) * ratio
    er = _section(out, "expected_results")
    if isinstance(er, dict):
        er["net_aep_p50_gwh"] = float(er["net_aep_p90_gwh"])
    return out


def _present_value(values: Sequence[float], rate: float) -> float:
    """Present value of ``values`` received at the end of periods 1, 2, ... (finance.irr)."""
    return float(npv(rate, [0.0, *values]))


def _llcr_discount_rate(config: Mapping[str, Any], debt: Mapping[str, Any]) -> float:
    """The engine's LLCR rate: a declared covenant rate, else the average debt rate."""
    fin = _section(config, "Financing_Terms") or {}
    cov = fin.get("covenants") if isinstance(fin.get("covenants"), Mapping) else {}
    declared = cov.get("llcr_discount_rate") if isinstance(cov, Mapping) else None
    if declared is not None:
        return float(declared)
    return float(debt.get("avg_debt_rate") or 0.0)


def _summary(rows: List[Tuple[int, float, float]]) -> Dict[str, Optional[float]]:
    dscr = [d for _, _, d in rows]
    return {
        "min_dscr": min(dscr) if dscr else None,
        "avg_dscr": sum(dscr) / len(dscr) if dscr else None,
    }


def _cfads_map(debt: Mapping[str, Any], scale: float = 1.0) -> Dict[str, Any]:
    """A debt-result view whose row CFADS is ``scale`` x the given case's."""
    return {
        "annual_row_debt_period_map": [
            {**dict(m), "cfads_usd": float(m["cfads_usd"]) * scale}
            for m in debt.get("annual_row_debt_period_map") or []
            if isinstance(m, Mapping) and m.get("cfads_usd") is not None
        ]
    }


def _llcr(
    rows_case: Dict[str, Any],
    base_debt: Mapping[str, Any],
    base_llcr: float,
    tenor: int,
    rate: float,
) -> Optional[float]:
    """LLCR of a case against the base debt: base LLCR x NPV(case) / NPV(base).

    Same tenor window, fee netting and discount rate as the engine's LLCR
    (``finance.debt.layer._coverage_ratios``), so the base principal cancels.
    """
    fee_by_row: Dict[int, float] = {}
    fees = list(base_debt.get("senior_fee_usd") or [])
    for m in base_debt.get("annual_row_debt_period_map") or []:
        period = int(m["debt_period"])
        if 0 <= period < len(fees):
            fee_by_row[int(m["annual_row_index"])] = float(fees[period] or 0.0)

    def net(view: Mapping[str, Any]) -> List[float]:
        rows = sorted(
            (int(m["annual_row_index"]), float(m["cfads_usd"]))
            for m in view["annual_row_debt_period_map"]
        )
        return [c - fee_by_row.get(r, 0.0) for r, c in rows][:tenor]

    base_npv = _present_value(net(_cfads_map(base_debt)), rate)
    if tenor <= 0 or base_npv <= 0.0:
        return None
    return base_llcr * _present_value(net(rows_case), rate) / base_npv


def _debt_result(full: Mapping[str, Any]) -> Mapping[str, Any]:
    debt = full.get("debt_result")
    return debt if isinstance(debt, Mapping) else {}


def recomputed_p90_downside(config: Mapping[str, Any]) -> Dict[str, Any]:
    """The recomputed P90 downside beside the ratio method, for one scenario config."""
    pair = p90_energy_ratio(config)
    if pair is None:
        return {
            "status": "unavailable",
            "reason": "no expected_results net_aep_p50_gwh / net_aep_p90_gwh pair",
        }
    p50, p90, ratio = pair
    base = evaluate_with_overrides(
        raw_config=dict(config), overrides={}, return_full_result=True
    )
    down = evaluate_with_overrides(
        raw_config=p90_production_config(config, ratio),
        overrides={},
        return_full_result=True,
    )
    base_debt = _debt_result(base)
    down_debt = _debt_result(down)
    base_rows = fixed_debt_coverage_by_row(base_debt, base_debt)
    if not base_rows:
        return {
            "status": "unavailable",
            "reason": "the base case has no operating period with committed debt service",
        }
    ratio_view = _cfads_map(base_debt, ratio)
    down_view = _cfads_map(down_debt)
    ratio_rows = fixed_debt_coverage_by_row(base_debt, ratio_view)
    down_rows = fixed_debt_coverage_by_row(base_debt, down_view)
    tenor = int(base_debt.get("tenor_years") or 0)
    rate = _llcr_discount_rate(config, base_debt)
    base_llcr = float(base_debt.get("llcr") or 0.0)
    cases = {
        "base": {**_summary(base_rows), "llcr": base_llcr},
        "ratio_method": {
            **_summary(ratio_rows),
            "llcr": _llcr(ratio_view, base_debt, base_llcr, tenor, rate),
        },
        "recomputed": {
            **_summary(down_rows),
            "llcr": _llcr(down_view, base_debt, base_llcr, tenor, rate),
        },
    }
    diff = {
        key: (
            cases["recomputed"][key] - cases["ratio_method"][key]  # type: ignore[operator]
            if cases["recomputed"][key] is not None
            and cases["ratio_method"][key] is not None
            else None
        )
        for key in ("min_dscr", "avg_dscr", "llcr")
    }
    by_row = {r: d for r, _, d in down_rows}
    by_row_ratio = {r: d for r, _, d in ratio_rows}
    return {
        "status": "ok",
        "label": LABEL,
        "net_aep_p50_gwh": p50,
        "net_aep_p90_gwh": p90,
        "p90_over_p50": ratio,
        "llcr_discount_rate": rate,
        "cases": cases,
        "recomputed_minus_ratio": diff,
        "dscr_by_operating_year": [
            {
                "operating_year": r + 1,
                "base": d,
                "ratio_method": by_row_ratio.get(r),
                "recomputed": by_row.get(r),
            }
            for r, _, d in base_rows
        ],
    }


__all__ = [
    "LABEL",
    "p90_energy_ratio",
    "p90_production_config",
    "recomputed_p90_downside",
]
