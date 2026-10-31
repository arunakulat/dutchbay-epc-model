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
from finance.debt.helpers import _as_float, _finite_number, _section_case_insensitive
from finance.debt.layer import apply_debt_layer

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
    senior_fee_usd: Sequence[float] = (),
) -> Tuple[List[float], float]:
    """Per-period cash diverted from equity to retire the balloon + residual.

    ``resolution[p]`` (USD) is senior to equity and aligned to the SAME period
    index as ``debt_service_total``. ``residual`` is any balloon still outstanding
    after the treatment (0.0 when fully resolved). ``cash_sweep``/``bullet``/
    ``refinance`` produce a stream; ``legacy_ignore``/``amortize`` produce none
    (``amortize`` removes the balloon by resizing debt upstream).
    """
    n = int(timeline_periods)
    resolution = [0.0] * n
    if balloon <= _BALLOON_TOL or treatment in ("legacy_ignore", "amortize"):
        return resolution, (0.0 if balloon <= _BALLOON_TOL else float(balloon))

    maturity = _maturity_period_index(debt_service_total, construction_periods)
    if maturity >= n:
        # No post-maturity period to resolve into → collapse to a terminal bullet.
        if n > 0:
            resolution[n - 1] = float(balloon)
        return resolution, 0.0

    if treatment == "bullet":
        resolution[maturity] = float(balloon)
        return resolution, 0.0

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
        for j in range(periods):
            resolution[maturity + j] = annuity
        return resolution, 0.0

    # Default: cash_sweep — trap post-maturity CFADS until the balloon clears.
    # The sweepable headroom is net of the senior credit-support fee (#737): the
    # reported rows already charge equity that fee, so sweeping pre-fee CFADS would
    # double-count the same cash as both fee-paid and balloon-sweepable, overstating
    # how fast equity can retire the balloon. (The fee is charged on the UN-swept
    # structural balloon — conservative.) Zero fees -> byte-identical.
    remaining = float(balloon)
    for p in range(maturity, n):
        available = _as_float(cfads_ext[p], 0.0) if p < len(cfads_ext) else 0.0
        fee = _as_float(senior_fee_usd[p], 0.0) if p < len(senior_fee_usd) else 0.0
        pay = min(max(0.0, available - fee), remaining)
        resolution[p] = pay
        remaining -= pay
        if remaining <= _BALLOON_TOL:
            return resolution, 0.0
    return resolution, remaining


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

    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    lo, hi = 0.0, _as_float(fin.get("debt_ratio"), 0.70)

    def _at_ratio(ratio: float) -> Dict[str, Any]:
        cfg = copy.deepcopy(config)
        fin_m = _section_case_insensitive(cfg, "Financing_Terms")
        if isinstance(fin_m, dict):
            fin_m["debt_ratio"] = ratio
        else:
            cfg["debt_ratio"] = ratio
        return cfg

    for _ in range(40):
        mid = (lo + hi) / 2.0
        trial = apply_debt_layer(params=_at_ratio(mid), annual_rows=rows)
        if _as_float(trial.get("balloon_remaining"), 0.0) > _BALLOON_TOL:
            hi = mid
        else:
            lo = mid
    resized_cfg = _at_ratio(lo)
    return resized_cfg, apply_debt_layer(params=resized_cfg, annual_rows=rows)
