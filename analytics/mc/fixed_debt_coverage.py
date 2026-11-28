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
    try:
        out = float(value)
    except OverflowError:
        return None
    return out if math.isfinite(out) else None


def _index(value: Any) -> Optional[int]:
    """A nonnegative integral row/period identity; never truncate floats."""
    number = _finite(value)
    if number is None or number < 0 or not number.is_integer():
        return None
    return int(number)


def fixed_debt_coverage_by_row(
    base_debt_result: Mapping[str, Any], trial_debt_result: Mapping[str, Any]
) -> List[Tuple[int, float, float]]:
    """``(annual_row_index, net_cfads_usd, dscr)`` per covenant row, against FIXED debt.

    For each operating row of the base ``annual_row_debt_period_map`` (operating periods
    only; construction, the bridge and post-tenor padding map to no row), the coverage is

        (trial row CFADS - base senior fee of that period) / base debt service of that period

    and operating year 1 also carries the base bridge period's service, exactly as
    ``finance.debt.layer`` folds it into ``dscr_by_year``. A row whose base period carries
    no service (including any allocated bridge service) is not a covenant observation (``dscr_by_year`` holds ``None`` there). With
    trial = base the DSCRs are the base ``dscr_by_year``.

    The senior fee is the BASE (committed-debt) fee, not the fee the trial charged on its
    own re-sized debt, so a committed loan's fee does not shrink with the trial (#1728 L-1).
    Stated limits: the trial's CFADS is its own pipeline's figure, so any CFADS term that
    depends on the trial's own debt is not re-based; and the base debt service is zero
    after the balloon period, so a refinanced balloon falls outside the stress (#1728 L-2;
    its coverage is disclosed separately under ``debt_result.refinance``).

    Reads ``annual_row_debt_period_map``, ``debt_service_total``, ``senior_fee_usd`` and
    ``bridge_debt_period``; never the deprecated ``raw_dscr_series`` alias (REFACTOR-04).
    Returns an empty list when no operating row carries base service, or when
    any required covenant row is missing, ambiguous, or nonfinite. Never return
    a partial covenant-year series. Zero-service rows need no trial CFADS.
    """
    base_map = base_debt_result.get("annual_row_debt_period_map") or []
    base_svc = base_debt_result.get("debt_service_total") or []
    base_fee = base_debt_result.get("senior_fee_usd") or []
    if not all(isinstance(v, (list, tuple)) for v in (base_map, base_svc, base_fee)):
        return []
    # A complete committed service vector is the independent coverage oracle.
    # Any unmapped positive service other than the documented bridge fails closed.
    service: list[float] = []
    for value in base_svc:
        amount = _finite(value)
        if amount is None or amount < 0:
            return []
        service.append(amount)

    mapped_periods: set[int] = set()
    base_rows: set[int] = set()
    row_period: dict[int, int] = {}
    for entry in base_map:
        if not isinstance(entry, Mapping):
            return []
        period = _index(entry.get("debt_period"))
        row = _index(entry.get("annual_row_index"))
        if period is None or row is None or period >= len(base_svc):
            return []
        if period in mapped_periods or row in base_rows:
            return []
        mapped_periods.add(period)
        base_rows.add(row)
        row_period[row] = period

    if base_rows != set(range(len(base_rows))):
        return []
    if base_rows:
        first = row_period[0]
        if any(period != first + row for row, period in row_period.items()):
            return []
    published = base_debt_result.get("dscr_by_year")
    if published is not None and (
        not isinstance(published, Mapping) or len(published) != len(base_rows)
    ):
        return []
    bridge_raw = base_debt_result.get("bridge_debt_period")
    bridge = _index(bridge_raw)
    if bridge_raw is not None and (bridge is None or bridge >= len(base_svc)):
        return []
    construction_raw = base_debt_result.get("construction_periods")
    if construction_raw is not None:
        construction = _index(construction_raw)
        if construction is None:
            return []
        if bridge is not None and bridge != construction:
            return []
        first_operating_period = construction + (1 if bridge is not None else 0)
        if base_rows and row_period[0] != first_operating_period:
            return []
    if bridge is not None and base_rows and bridge != row_period[0] - 1:
        return []
    bridge_extra = 0.0
    if bridge is not None and bridge not in mapped_periods:
        bridge_value = _finite(base_svc[bridge])
        if bridge_value is None or bridge_value < 0:
            return []
        bridge_extra = bridge_value

    allowed = mapped_periods | ({bridge} if bridge is not None else set())
    if any(value > 0 and i not in allowed for i, value in enumerate(service)):
        return []
    if bridge_extra > 0 and 0 not in base_rows:
        return []
    # Determine required rows from the checked committed service, not trial debt.
    required: List[Tuple[int, float, float]] = []
    for entry in base_map:
        period = _index(entry.get("debt_period"))
        row = _index(entry.get("annual_row_index"))
        if period is None or row is None:
            return []
        svc = service[period] + (bridge_extra if row == 0 else 0.0)
        if svc == 0:
            continue
        if period >= len(base_fee):
            return []
        fee = _finite(base_fee[period])
        if fee is None or fee < 0 or not math.isfinite(svc):
            return []
        required.append((row, svc, fee))
    required_ids = {row for row, _, _ in required}
    trial_cfads: dict[int, float] = {}
    trial_map = trial_debt_result.get("annual_row_debt_period_map") or []
    if not isinstance(trial_map, (list, tuple)):
        return []
    for entry in trial_map:
        if not isinstance(entry, Mapping):
            return []
        row = _index(entry.get("annual_row_index"))
        if row is None:
            return []
        if row not in required_ids:
            continue
        cfads = _finite(entry.get("cfads_usd"))
        if cfads is None or row in trial_cfads:
            return []
        trial_cfads[row] = cfads
    if set(trial_cfads) != required_ids:
        return []

    out: List[Tuple[int, float, float]] = []
    for row, svc, fee in sorted(required):
        net = trial_cfads[row] - fee
        dscr = net / svc
        if not math.isfinite(net) or not math.isfinite(dscr):
            return []
        out.append((row, net, dscr))
    return out


__all__ = ["fixed_debt_coverage_by_row"]
