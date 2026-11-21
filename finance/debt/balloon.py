"""Balloon treatment: maturity, refinance terms and resolution streams."""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.debt.constants import (
    _BALLOON_DEFAULT_TREATMENT,
    _BALLOON_TOL,
    _BALLOON_VALID_TREATMENTS,
    _SERVICE_TOL,
    REFINANCE_TERMS_BASIS,
)
from finance.debt.helpers import (
    _as_float,
    _config_at_debt_ratio,
    _finite_number,
    _required_number,
    _section_case_insensitive,
)
from finance.debt.layer import apply_debt_layer
from finance.debt.terms import _extract_financing_terms

# The engine logged as ``finance.debt_v14`` before the split; keep that name so
# log filters and caplog assertions still see these records.
logger = logging.getLogger("finance.debt_v14")


def _maturity_period_index(
    debt_service_total: Sequence[float], construction_periods: int
) -> int:
    """Period index just AFTER the last scheduled senior service (balloon due here)."""
    nonzero = [
        i for i, s in enumerate(debt_service_total) if _as_float(s, 0.0) > _SERVICE_TOL
    ]
    return (max(nonzero) + 1) if nonzero else int(construction_periods)


def resolve_balloon_treatment(config: Mapping[str, Any]) -> str:
    """The balloon treatment the engine applies (unknown values WARN and fall back).

    The single resolution of ``Financing_Terms.balloon_treatment``, shared by
    :func:`plan_debt` and :func:`resolve_refinance_terms` (and through it the v14
    pre-flight), so the gate and the engine cannot disagree on which path runs.
    """
    fin = _section_case_insensitive(dict(config), "Financing_Terms") or {}
    treatment = str(
        fin.get("balloon_treatment", _BALLOON_DEFAULT_TREATMENT)
        or _BALLOON_DEFAULT_TREATMENT
    ).lower()
    if treatment not in _BALLOON_VALID_TREATMENTS:
        logger.warning(
            "Unknown balloon_treatment %r; falling back to %s",
            treatment,
            _BALLOON_DEFAULT_TREATMENT,
        )
        treatment = _BALLOON_DEFAULT_TREATMENT
    return treatment


def resolve_refinance_terms(config: Mapping[str, Any]) -> Optional[Tuple[int, float]]:
    """``(tenor_years, rate_premium)`` for a balloon refinance, read from YAML only.

    Returns ``None`` unless the resolved treatment is ``refinance``. When it is, both
    ``constraints.refinancing.refinance_tenor_years`` (a whole number of years >= 1)
    and ``constraints.refinancing.refinance_rate_premium`` (a finite decimal added to
    the average debt rate) must be present: there is no code default (#1396, owner
    decision 2026-10-26 "should never be hardcoded"). A missing or malformed value
    raises ``ValueError`` naming the config path, which the v14 pre-flight reuses.
    """
    if resolve_balloon_treatment(config) != "refinance":
        return None
    constraints = _section_case_insensitive(dict(config), "constraints") or {}
    refi = constraints.get("refinancing")
    refi_map: Mapping[str, Any] = refi if isinstance(refi, Mapping) else {}
    tenor_raw = refi_map.get("refinance_tenor_years")
    premium_raw = refi_map.get("refinance_rate_premium")
    problems: List[str] = []
    if tenor_raw is None:
        problems.append("constraints.refinancing.refinance_tenor_years is missing")
    elif (
        isinstance(tenor_raw, bool)
        or not _finite_number(tenor_raw)
        or float(tenor_raw) < 1
        or float(tenor_raw) != int(float(tenor_raw))
    ):
        problems.append(
            "constraints.refinancing.refinance_tenor_years must be a whole number of "
            f"years >= 1, got {tenor_raw!r}"
        )
    if premium_raw is None:
        problems.append("constraints.refinancing.refinance_rate_premium is missing")
    elif isinstance(premium_raw, bool) or not _finite_number(premium_raw):
        problems.append(
            "constraints.refinancing.refinance_rate_premium must be a finite decimal, "
            f"got {premium_raw!r}"
        )
    if problems:
        raise ValueError(
            "Financing_Terms.balloon_treatment is 'refinance', so its terms must come "
            "from YAML (no default): " + "; ".join(problems)
        )
    assert (
        tenor_raw is not None and premium_raw is not None
    )  # narrowed by the checks above
    return int(float(tenor_raw)), float(premium_raw)


def _sweep_cash_at(
    period: int,
    cfads_ext: Sequence[float],
    sweep_cash: Optional[Sequence[Optional[float]]],
) -> float:
    """The cash a cash sweep has in ``period``: the supplied basis, else ``cfads_ext``.

    ``sweep_cash`` is period-indexed like ``cfads_ext``; a ``None`` entry, or a period
    past its end, falls back to ``cfads_ext`` (#1736).
    """
    if sweep_cash is not None and period < len(sweep_cash):
        supplied = sweep_cash[period]
        if supplied is not None:
            return float(supplied)
    return _as_float(cfads_ext[period], 0.0) if period < len(cfads_ext) else 0.0


def _balloon_resolution_path(
    *,
    treatment: str,
    balloon: float,
    cfads_ext: Sequence[float],
    debt_service_total: Sequence[float],
    construction_periods: int,
    timeline_periods: int,
    avg_rate: float,
    refi_tenor_years: int,
    refi_rate_premium: float,
    senior_fee_rate: float = 0.0,
    sweep_cash: Optional[Sequence[Optional[float]]] = None,
) -> Dict[str, Any]:
    """How the balloon is carried and retired after maturity, period by period.

    Every series is PERIOD-indexed on the same axis as ``debt_service_total``:

    - ``resolution[p]``: cash (USD) diverted from equity to the balloon, senior to
      equity: its interest plus whatever principal it retires.
    - ``interest[p]``: interest accrued on the balloon in period ``p``.
    - ``interest_paid[p]``: interest settled in cash in period ``p``, inside
      ``resolution[p]``. A payment settles interest before principal: first any
      interest an earlier period capitalised, then the period's own. It differs
      from ``interest[p]`` only under ``cash_sweep``, when the cash cannot pay the
      interest (it is capitalised) or later pays interest capitalised earlier. Tax
      can deduct balloon interest when it is paid (#1505), so the paid split is
      published beside the accrual.
    - ``outstanding[p]``: the balloon's OPENING balance in period ``p``, or ``None``
      for every period this path does not govern (before maturity, or when the
      treatment produces no stream). Plan_debt overlays it on ``debt_outstanding``.
    - ``senior_fee[p]``: the senior credit-support fee PAID in cash in period ``p``, or
      ``None`` where ``outstanding[p]`` is ``None``. Plan_debt overlays it on
      ``senior_fee_usd``. It equals ``senior_fee_rate`` x ``outstanding[p]`` except under
      ``cash_sweep`` when the period's cash cannot pay the fee due (see below).
    - ``senior_fee_deferred[p]``: fee charged but not yet paid, carried forward at the
      end of period ``p`` (#1539); ``None`` where ``outstanding[p]`` is ``None``. Only
      ``cash_sweep`` defers a fee; every other treatment carries 0.0.
    - ``senior_fee_deferred_residual``: fee still deferred at the end of the timeline.
    - ``residual``: the balloon still outstanding at the end of the timeline,
      including any interest the cash could not pay (0.0 when fully resolved).

    The balloon is the unpaid part of the facility, so after maturity it keeps
    accruing interest at the facility's blended contract rate, ``avg_rate``, and it
    keeps bearing the senior credit-support fee on the balance actually
    outstanding. Before this, ``cash_sweep`` and ``bullet`` retired it interest-free
    and the fee stayed charged on the structural balloon after it was repaid.

    - ``cash_sweep`` (default): each period's post-fee cash pays the interest, then
      principal, until the balloon clears. Interest the cash cannot pay is added to
      the balance (capitalised): the sweep never asks equity for more cash than
      the period generates, and an unpaid balance shows as ``residual``. The fee due
      (this period's fee on the opening balance plus any fee deferred earlier) is paid
      first, up to the period's cash; whatever the cash cannot pay is deferred and
      carried forward as the first claim on later cash (owner ruling on #1539,
      2026-11-15). ASSUMPTION: the deferred fee bears no interest; the ruling does not
      say, and the owner may change it. Before #1539 the full fee was charged even when
      it exceeded the period's cash. The period's cash is ``sweep_cash[p]`` where the
      caller supplies one, else the sizing-basis ``cfads_ext[p]``. The pipeline supplies
      the cash the equity waterfall holds for the sweep (owner ruling on #1736,
      2026-11-15: one cash basis decides both the sweep and the fee deferral), so the
      engine and the waterfall agree on it; ``cfads_ext`` is the basis for a direct
      caller that supplies none.
    - ``bullet``: the balloon and one period's interest are repaid in the maturity
      period, which may exceed the period's cash (a sponsor cash call).
    - ``refinance``: a level annuity over ``refi_tenor_years`` at ``avg_rate`` plus
      ``refi_rate_premium``, as before.
    - ``legacy_ignore`` and ``amortize`` produce no stream (``amortize`` removes the
      balloon by resizing debt upstream), and govern no period.
    """
    n = int(timeline_periods)
    resolution = [0.0] * n
    interest = [0.0] * n
    interest_paid = [0.0] * n
    outstanding: List[Optional[float]] = [None] * n
    senior_fee: List[Optional[float]] = [None] * n
    senior_fee_deferred: List[Optional[float]] = [None] * n
    fee_rate = float(senior_fee_rate)

    def _path(residual: float, fee_deferred_residual: float = 0.0) -> Dict[str, Any]:
        return {
            "resolution": resolution,
            "interest": interest,
            "interest_paid": interest_paid,
            "outstanding": outstanding,
            "senior_fee": senior_fee,
            "senior_fee_deferred": senior_fee_deferred,
            "residual": residual,
            "senior_fee_deferred_residual": fee_deferred_residual,
        }

    if balloon <= _BALLOON_TOL or treatment in ("legacy_ignore", "amortize"):
        return _path(0.0 if balloon <= _BALLOON_TOL else float(balloon))

    maturity = _maturity_period_index(debt_service_total, construction_periods)
    if maturity >= n:
        # No post-maturity period to resolve into → collapse to a terminal bullet in
        # the last scheduled period, which already carries the balance and its fee.
        if n > 0:
            resolution[n - 1] = float(balloon)
        return _path(0.0)

    def _carry(
        p: int,
        opening: float,
        accrued: float,
        paid: float,
        interest_settled: float,
        fee_paid: Optional[float] = None,
        fee_deferred: float = 0.0,
    ) -> None:
        outstanding[p] = opening
        senior_fee[p] = fee_rate * opening if fee_paid is None else fee_paid
        senior_fee_deferred[p] = fee_deferred
        interest[p] = accrued
        interest_paid[p] = interest_settled
        resolution[p] = paid

    def _cleared_from(p: int) -> None:
        for q in range(p, n):
            _carry(q, 0.0, 0.0, 0.0, 0.0)

    if treatment == "bullet":
        opening = float(balloon)
        accrued = opening * max(0.0, float(avg_rate))
        _carry(maturity, opening, accrued, opening + accrued, accrued)
        _cleared_from(maturity + 1)
        return _path(0.0)

    if treatment == "refinance":
        rate = max(0.0, float(avg_rate) + float(refi_rate_premium))
        periods = max(1, int(refi_tenor_years))
        if maturity + periods > n:
            # #1396: this used to compress the overrun annuities into the final period,
            # silently (a 3-year refinance with 2 periods left booked a double payment).
            raise ValueError(
                f"refinance tenor of {periods} years runs past the modelled timeline: the "
                f"balloon falls due in period {maturity} of {n}, leaving {n - maturity} "
                "periods; shorten constraints.refinancing.refinance_tenor_years"
            )
        if rate > 0.0:
            factor = (rate * (1.0 + rate) ** periods) / ((1.0 + rate) ** periods - 1.0)
            annuity = float(balloon) * factor
        else:
            annuity = float(balloon) / periods
        opening = float(balloon)
        for j in range(periods):
            accrued = opening * rate
            # A level annuity is never less than the period's interest, so the
            # refinance pays its interest as it accrues.
            _carry(maturity + j, opening, accrued, annuity, min(accrued, annuity))
            opening = max(0.0, opening + accrued - annuity)
        _cleared_from(maturity + periods)
        return _path(0.0)

    # Default: cash_sweep — trap post-maturity CFADS until the balloon clears.
    # The sweepable headroom is net of the senior credit-support fee (#737): the
    # reported rows already charge equity that fee, so sweeping pre-fee CFADS would
    # double-count the same cash as both fee-paid and balloon-sweepable, overstating
    # how fast equity can retire the balloon. The fee is charged on the balance
    # actually outstanding at the start of the period. Zero fees -> no fee term.
    rate = max(0.0, float(avg_rate))
    remaining = float(balloon)
    # Interest accrued in earlier periods that the cash could not pay. It sits in
    # `remaining` (capitalised) and is the first claim on a later payment.
    capitalised_interest = 0.0
    # Senior fee charged but not yet paid (#1539). It is senior to the sweep: the fee
    # due is paid before any cash reaches the balloon. It carries no interest (an
    # ASSUMPTION; see the docstring).
    deferred_fee = 0.0
    for p in range(maturity, n):
        available = _sweep_cash_at(p, cfads_ext, sweep_cash)
        fee_due = fee_rate * remaining + deferred_fee
        fee_paid = min(fee_due, max(0.0, available))
        deferred_fee = fee_due - fee_paid
        accrued = remaining * rate
        due = remaining + accrued
        pay = min(max(0.0, available - fee_paid), due)
        interest_due = capitalised_interest + accrued
        interest_settled = min(pay, interest_due)
        _carry(
            p,
            remaining,
            accrued,
            pay,
            interest_settled,
            fee_paid=fee_paid,
            fee_deferred=deferred_fee,
        )
        capitalised_interest = interest_due - interest_settled
        remaining = due - pay
        if remaining <= _BALLOON_TOL:
            # Clearing needs cash beyond the fee due, so no fee is left deferred here.
            _cleared_from(p + 1)
            return _path(0.0, deferred_fee)
    return _path(remaining, deferred_fee)


def _balloon_resolution_stream(
    *,
    treatment: str,
    balloon: float,
    cfads_ext: Sequence[float],
    debt_service_total: Sequence[float],
    construction_periods: int,
    timeline_periods: int,
    avg_rate: float,
    refi_tenor_years: int,
    refi_rate_premium: float,
    senior_fee_rate: float = 0.0,
) -> Tuple[List[float], float]:
    """Per-period cash diverted from equity to retire the balloon + residual.

    The ``(resolution, residual)`` pair of :func:`_balloon_resolution_path`, which
    documents each treatment.
    """
    path = _balloon_resolution_path(
        treatment=treatment,
        balloon=balloon,
        cfads_ext=cfads_ext,
        debt_service_total=debt_service_total,
        construction_periods=construction_periods,
        timeline_periods=timeline_periods,
        avg_rate=avg_rate,
        refi_tenor_years=refi_tenor_years,
        refi_rate_premium=refi_rate_premium,
        senior_fee_rate=senior_fee_rate,
    )
    return path["resolution"], path["residual"]


def _refinance_disclosure(
    *,
    config: Mapping[str, Any],
    terms: Tuple[int, float],
    balloon: float,
    resolution: Sequence[float],
    cfads_ext: Sequence[float],
    senior_fee_usd: Sequence[float],
    avg_rate: float,
) -> Dict[str, Any]:
    """The refinanced tranche as published: its YAML terms, their basis, and a coverage test.

    Coverage is tested per refinance-service period as cash available after the senior
    credit-support fee divided by that period's refinance service, which is the same
    sweepable headroom :func:`_balloon_resolution_stream` uses for ``cash_sweep``. The
    floor is the scenario's own DSCR covenant through the shared resolver
    (:func:`analytics.mc.covenant.resolve_min_dscr_covenant`), so this test and the Monte
    Carlo breach test cannot measure against different floors. Balloon service stays
    outside ``min_dscr``, which tests scheduled senior service only (#1396).
    """
    from analytics.mc.covenant import resolve_min_dscr_covenant

    tenor, premium = terms
    rate = max(0.0, float(avg_rate) + premium)
    outstanding = float(balloon)
    coverage: List[Dict[str, Any]] = []
    for period, service in enumerate(resolution):
        if service <= _SERVICE_TOL:
            continue
        cash = _as_float(cfads_ext[period], 0.0) if period < len(cfads_ext) else 0.0
        fee = (
            _as_float(senior_fee_usd[period], 0.0)
            if period < len(senior_fee_usd)
            else 0.0
        )
        # Each level payment is interest on the opening refinanced balance plus
        # principal; the three statements need the split (interest is an expense,
        # only principal retires debt).
        interest = outstanding * rate
        principal = float(service) - interest
        outstanding -= principal
        coverage.append(
            {
                "period": period,
                "service_usd": float(service),
                "interest_usd": interest,
                "principal_usd": principal,
                "cash_available_usd": cash - fee,
                "coverage": (cash - fee) / float(service),
            }
        )
    floor = float(resolve_min_dscr_covenant(dict(config)))
    min_coverage = min((c["coverage"] for c in coverage), default=None)
    return {
        "terms_basis": REFINANCE_TERMS_BASIS,
        "terms_source": {
            "tenor_years": "constraints.refinancing.refinance_tenor_years",
            "rate_premium": "constraints.refinancing.refinance_rate_premium",
        },
        "tenor_years": tenor,
        "rate_premium": premium,
        "rate": rate,
        "principal_usd": float(balloon),
        "total_service_usd": float(sum(resolution)),
        "total_interest_usd": float(sum(c["interest_usd"] for c in coverage)),
        "coverage_by_period": coverage,
        "min_coverage": min_coverage,
        "coverage_floor": floor,
        "coverage_breach": min_coverage is not None and min_coverage < floor,
    }


def _resize_for_amortization(
    config: Dict[str, Any],
    rows: List[Dict[str, Any]],
    core: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Reduce gearing until the sculpt fully amortises within tenor (no balloon).

    Bisects ``Financing_Terms.debt_ratio`` between 0 (always balloon-free) and the
    current solved gearing (has a balloon), returning the largest gearing whose
    ``balloon_remaining`` is ~0. No-op when the current schedule has no balloon.
    """
    if _as_float(core.get("balloon_remaining"), 0.0) <= _BALLOON_TOL:
        return config, core

    # Read the gearing where _config_at_debt_ratio writes it: Financing_Terms when the
    # config has that section, else the top level. Before #1429 this read only
    # Financing_Terms.debt_ratio and fell back to 0.70. Under Financing_Terms the bound
    # is the gearing the debt layer itself used: the extractor applies the debt_pct /
    # leverage_pct aliases and their percent scaling, so pre-flight, the layer and this
    # bisection read one figure (before the #1429 follow-up a gearing declared only
    # through an alias was refused here after pre-flight had accepted it).
    fin = _section_case_insensitive(config, "Financing_Terms")
    if fin is not None:
        hi_raw = _extract_financing_terms(config).get("debt_ratio")
        hi_path = "Financing_Terms.debt_ratio (or debt_pct / leverage_pct)"
    else:
        hi_raw, hi_path = config.get("debt_ratio"), "debt_ratio"
    lo, hi = 0.0, _required_number(hi_raw, hi_path)

    # The 40 bisection trials share one deep copy and path-copy per trial (see
    # _config_at_debt_ratio). The config this function RETURNS is still a full deep copy,
    # because callers keep it and may hand it on.
    base = copy.deepcopy(config)

    for _ in range(40):
        mid = (lo + hi) / 2.0
        trial = apply_debt_layer(
            params=_config_at_debt_ratio(base, mid), annual_rows=rows
        )
        if _as_float(trial.get("balloon_remaining"), 0.0) > _BALLOON_TOL:
            hi = mid
        else:
            lo = mid
    resized_cfg = _config_at_debt_ratio(copy.deepcopy(config), lo)
    return resized_cfg, apply_debt_layer(params=resized_cfg, annual_rows=rows)
