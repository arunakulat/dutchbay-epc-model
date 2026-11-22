"""Recomputed P90 downside, reported beside the CFADS-ratio approximation (#1836).

A scenario's debt sizing applies its own downside factor to CFADS, and which factor that
is depends on the scenario (``finance.debt.sizing._maybe_autosolve_dscr``). With
``Financing_Terms.bind_downside`` it is ``_resolve_downside_ratio``'s factor (an explicit
``downside_cfads_factor``, else the P90/P50 energy ratio, else the flat factor) and that
case binds the gearing. Without it, the flat ``dscr_p99_downside_factor`` is used, and
only in the dual-DSCR capacity detail; it does not bind the gearing. Scenarios with no
DSCR sizing mode have no sizing downside at all. Whatever the factor, scaling CFADS by
one number is not the same as re-running the cash flow at P90 energy: fixed opex does
not fall with production, and tax, levies, reserves and FX make the response nonlinear.
This module measures the difference.

For a scenario that declares an ``expected_results`` P50/P90 pair it runs two cases
through the canonical gateway (:func:`analytics.evaluation_v14.evaluate_with_overrides`):

* the base case, unchanged, which fixes the committed debt (its service and fee);
* a P90 case: every billed capacity factor (the project headline and each generation
  technology in ``generation.technologies``) scaled by P90/P50, all else unchanged, so
  opex, tax, levies, the waterfall and reserves are recomputed by the engine.

Three scaled or recomputed CFADS series are then set against the base case's FIXED debt
service on the covenant basis
(:func:`analytics.mc.fixed_debt_coverage.fixed_debt_coverage_by_row`):

* ``sizing_downside``: base CFADS x the factor the scenario's own sizing used, read from
  the engine's published ``debt_result["dual_dscr"]`` (``downside_ratio`` and
  ``downside_source``), with whether it binds the gearing (the engine publishes
  ``solved_gearing_p90`` only then); ``None`` when the scenario
  has no DSCR sizing mode;
* ``ratio_method``: base CFADS x P90/P50, the energy-ratio approximation;
* ``recomputed``: the P90 case's own CFADS.

The minimum and average annual DSCR and the LLCR are reported for each, with the
recomputed case's difference from each approximation. Whether the recomputed P90 is
milder or harsher than a scenario's sizing downside depends on that scenario's factor;
the summary reports it per scenario and claims no general direction.

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


def _difference(
    case: Mapping[str, Any], other: Mapping[str, Any]
) -> Dict[str, Optional[float]]:
    """``case - other`` for each covenant figure, ``None`` where either is missing."""
    out: Dict[str, Optional[float]] = {}
    for key in ("min_dscr", "avg_dscr", "llcr"):
        a, b = case.get(key), other.get(key)
        out[key] = float(a) - float(b) if a is not None and b is not None else None
    return out


def _sizing_downside(base_debt: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The downside factor the scenario's own sizing used, as the engine published it.

    Read from ``debt_result["dual_dscr"]`` (``downside_ratio``, ``downside_source``), so
    no sizing rule is restated here. ``None`` when the scenario has no DSCR sizing mode
    (the engine publishes no detail) or the detail carries no factor.
    """
    detail = base_debt.get("dual_dscr")
    if not isinstance(detail, Mapping):
        return None
    factor = _positive(detail.get("downside_ratio"))
    if factor is None:
        return None
    return {
        "factor": factor,
        "source": detail.get("downside_source"),
        # The engine publishes a P90 gearing solve only when the downside binds.
        "binds_gearing": detail.get("solved_gearing_p90") is not None,
    }


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
    sizing = _sizing_downside(base_debt)
    sizing_rows: Optional[List[Tuple[int, float, float]]] = None
    if sizing is not None:
        sizing_view = _cfads_map(base_debt, sizing["factor"])
        sizing_rows = fixed_debt_coverage_by_row(base_debt, sizing_view)
        sizing.update(_summary(sizing_rows))
        sizing["llcr"] = _llcr(sizing_view, base_debt, base_llcr, tenor, rate)
    cases: Dict[str, Any] = {
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
    cases["sizing_downside"] = sizing
    by_row = {r: d for r, _, d in down_rows}
    by_row_ratio = {r: d for r, _, d in ratio_rows}
    by_row_sizing = {r: d for r, _, d in sizing_rows or []}
    return {
        "status": "ok",
        "label": LABEL,
        "net_aep_p50_gwh": p50,
        "net_aep_p90_gwh": p90,
        "p90_over_p50": ratio,
        "llcr_discount_rate": rate,
        "cases": cases,
        "recomputed_minus_ratio": _difference(
            cases["recomputed"], cases["ratio_method"]
        ),
        "recomputed_minus_sizing_downside": (
            _difference(cases["recomputed"], sizing) if sizing is not None else None
        ),
        "dscr_by_operating_year": [
            {
                "operating_year": r + 1,
                "base": d,
                "sizing_downside": by_row_sizing.get(r),
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
