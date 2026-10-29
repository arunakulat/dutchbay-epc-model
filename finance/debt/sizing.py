"""Dual-DSCR sizing and gearing autosolve (extracted from debt_v14)."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.debt.dscr_contract import _clean_public_dscr_series, _operating_dscr_minimum
from finance.debt.helpers import (
    _as_float,
    _finite_dscr,
    _finite_number,
    _npv,
    _section_case_insensitive,
)
from finance.debt.capex import _extract_capex_usd
from finance.debt.layer import apply_debt_layer
from finance.debt.placeholders import _truthy_flag
from finance.debt.terms import _extract_financing_terms

logger = logging.getLogger("finance.debt_v14")

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
    (interest-only period, declining-CFADS tail), so the achieved DSCR lands on target. If min DSCR
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
        # Target the minimum over every DEFINED period, bridge included. This is NOT
        # plan_debt's published min_dscr: since F-2/F-3 that headline excludes
        # non-operating periods and folds dscr_by_year, whereas the solve deliberately
        # keeps the wider set. Two reasons. (1) Including the bridge can only LOWER the
        # metric, so the solve is weakly MORE conservative — it never sizes debt up on
        # the strength of the exclusion. (2) It is held byte-identical because changing
        # the solver's target changes which trial gearing is accepted, and that moves
        # canon (DOC-02) — out of scope for a KPI-neutral dolphin. Revisiting it is a
        # separate, re-baselined decision.
        # NOTE (#737): deliberately NOT the bridge-corrected per-year fold. With senior
        # credit-support fees, operating year 1 — which covers its own service PLUS the
        # orphaned bridge service out of fee-netted CFADS — can read slightly below the
        # per-period floor (the pre-fee slack absorbed it); binding the fold here was
        # tried and rejected: at interest_only_years=0 the fold is quasi-insensitive to
        # gearing (year 1 is sculpt-targeted, so extra de-leveraging cannot lift it)
        # and the solve degenerates to a near-zero facility. plan_debt's conservative
        # min_dscr (round-5 #3) still REPORTS the fold honestly.
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
    # Non-convergence: no gearing down to the floor holds the target DSCR (an unbankable
    # CFADS profile). Fail LOUD and size DOWN to the conservative floor (least debt) — the
    # old fallback returned max_ratio - step (near-MAXIMUM leverage), silently sizing an
    # unbankable structure UP, the opposite of prudent and with no signal.
    logger.warning(
        "Gearing solver did not converge: no gearing in (0, %.4f] holds min DSCR >= "
        "target %.3f. Falling back to the conservative floor %.4f (least debt).",
        max_ratio,
        target_dscr,
        step,
    )
    return round(step, 6)


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
    target_p90: Optional[float] = None
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
            if target_p90 is not None:
                detail["target_dscr_p90"] = target_p90
            detail["downside_ratio"] = round(downside, 6)
            detail["downside_source"] = downside_source
        except ValueError:
            detail = None
    logger.info(
        "DSCR debt sizing (%s): gearing %.3f (P50 %.3f%s) for target DSCR %.2f",
        mode,
        binding_gearing,
        solved,
        (
            f"; P90 {solved_p90:.3f} -> binds {binding_case}"
            if solved_p90 is not None
            else ""
        ),
        target,
    )
    return resized, detail


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
            for cf, svc in zip(cfads, service, strict=True)
        ]
        min_dscr = min(profile) if profile else 0.0
        return service, capacity, profile, min_dscr

    service_p50, debt_p50, profile_p50, min_dscr_p50 = _size_one(
        cfads_p50, dscr_target_p50
    )
    service_p99, debt_p99, profile_p99, min_dscr_p99 = _size_one(
        cfads_p99, dscr_target_p99
    )

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


