"""Coverage of a case's CFADS against a FIXED, financial-close debt schedule.

A committed loan cannot shrink when production disappoints, but every pipeline run
re-sizes (sculpts) its own debt. To test a stressed case against the debt that was
actually committed, its CFADS is set against the BASE case's debt service, on the basis
the covenant is tested on (#1728): the per-year ``dscr_by_year`` table ``plan_debt``
publishes. The Monte Carlo fixed-debt stress (``analytics.mc.engine``) and the recomputed
P90 downside (#1836, ``analytics.finance.p90_recomputed_downside``) both read it here.
"""

from __future__ import annotations

import math
from typing import Any, List, Mapping, Optional, Tuple


def _finite(value: Any) -> Optional[float]:
    """``value`` as a finite float, else ``None`` (bools are not numbers here)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    out = float(value)
    return out if math.isfinite(out) else None


def fixed_debt_coverage_by_row(
    base_debt_result: Mapping[str, Any], trial_debt_result: Mapping[str, Any]
) -> List[Tuple[int, float, float]]:
    """``(annual_row_index, net_cfads_usd, dscr)`` per covenant row, against FIXED debt.

    For each operating row of the base ``annual_row_debt_period_map`` (operating periods
    only; construction, the bridge and post-tenor padding map to no row), the coverage is

        (trial row CFADS - base senior fee of that period) / base debt service of that period

    and operating year 1 also carries the base bridge period's service, exactly as
    ``finance.debt.layer`` folds it into ``dscr_by_year``. A row whose base period carries
    no service is not a covenant observation (``dscr_by_year`` holds ``None`` there). With
    trial = base the DSCRs are the base ``dscr_by_year``.

    The senior fee is the BASE (committed-debt) fee, not the fee the trial charged on its
    own re-sized debt, so a committed loan's fee does not shrink with the trial (#1728 L-1).
    Stated limits: the trial's CFADS is its own pipeline's figure, so any CFADS term that
    depends on the trial's own debt is not re-based; and the base debt service is zero
    after the balloon period, so a refinanced balloon falls outside the stress (#1728 L-2;
    its coverage is disclosed separately under ``debt_result.refinance``).

    Reads ``annual_row_debt_period_map``, ``debt_service_total``, ``senior_fee_usd`` and
    ``bridge_debt_period``; never the deprecated ``raw_dscr_series`` alias (REFACTOR-04).
    Returns an empty list when no operating row carries base service or the trial
    publishes no CFADS for those rows.
    """
    base_map = base_debt_result.get("annual_row_debt_period_map") or []
    base_svc = list(base_debt_result.get("debt_service_total") or [])
    base_fee = list(base_debt_result.get("senior_fee_usd") or [])

    mapped_periods = set()
    for entry in base_map:
        if isinstance(entry, Mapping) and _finite(entry.get("debt_period")) is not None:
            mapped_periods.add(int(entry["debt_period"]))
    bridge = _finite(base_debt_result.get("bridge_debt_period"))
    bridge_extra = 0.0
    if (
        bridge is not None
        and int(bridge) not in mapped_periods
        and 0 <= int(bridge) < len(base_svc)
    ):
        bridge_extra = _finite(base_svc[int(bridge)]) or 0.0

    trial_cfads = {}
    for entry in trial_debt_result.get("annual_row_debt_period_map") or []:
        if not isinstance(entry, Mapping):
            continue
        row = _finite(entry.get("annual_row_index"))
        cfads = _finite(entry.get("cfads_usd"))
        if row is not None and cfads is not None:
            trial_cfads[int(row)] = cfads

    out: List[Tuple[int, float, float]] = []
    for row_i, entry in enumerate(base_map):
        if not isinstance(entry, Mapping):
            continue
        period = _finite(entry.get("debt_period"))
        row = _finite(entry.get("annual_row_index"))
        if period is None or row is None or not 0 <= int(period) < len(base_svc):
            continue
        svc = _finite(base_svc[int(period)]) or 0.0
        if svc <= 0.0:
            continue  # no base service: not a covenant observation
        if row_i == 0 and bridge_extra > 0.0:
            svc += bridge_extra
        cfads = trial_cfads.get(int(row))
        if cfads is None:
            continue
        fee = (
            _finite(base_fee[int(period)]) or 0.0
            if int(period) < len(base_fee)
            else 0.0
        )
        out.append((int(row), cfads - fee, (cfads - fee) / svc))
    return out


__all__ = ["fixed_debt_coverage_by_row"]
