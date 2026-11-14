"""Financing terms, construction window and the debt-period taxonomy."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from finance.debt.constants import (
    _BRIDGE_DEFAULT_TREATMENT,
    _BRIDGE_VALID_TREATMENTS,
)
from finance.debt.helpers import _as_float, _rate_decimal, _section_case_insensitive
from finance.debt.placeholders import _warn_placeholder_once

# The engine logged as ``finance.debt_v14`` before the split; keep that name so
# log filters and caplog assertions still see these records.
logger = logging.getLogger("finance.debt_v14")


# Debt is sized via dual_dscr and split by Financing_Terms.mix proportions at the
# per-currency Financing_Terms.rates. A hand-authored Financing_Terms.debt_tranches
# list (absolute principals / per-tranche tenors) is NOT an engine input — absolute
# principals are incompatible with auto-sizing. We warn once if one is present so the
# redundant block cannot silently drift from the engine's actual schedule. Tests reset
# this flag to assert the warning.
_warned_decorative_tranches = False


def _extract_financing_terms(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return canonical financing terms from v14 or simple test schemas."""
    financing_terms = _section_case_insensitive(params, "Financing_Terms")
    if financing_terms:
        adapted = dict(financing_terms)
        periods = _resolve_construction_periods(params)
        if adapted.get("debt_ratio") is None:
            debt_pct = adapted.get("debt_pct")
            if debt_pct is None:
                debt_pct = adapted.get("leverage_pct")
            if debt_pct is not None:
                ratio = _as_float(debt_pct, 0.70)
                adapted["debt_ratio"] = ratio / 100.0 if ratio > 1.0 else ratio
        if adapted.get("construction_periods") is None:
            # The resolved count, so this mapping can never publish a count the engine
            # does not use (#1570).
            adapted["construction_periods"] = periods
        if adapted.get("debt_drawdown_pct") is None:
            fallback_drawdown = adapted.get("drawdown_pct")
            if fallback_drawdown is None:
                # A1/#91: no project EPC draw schedule supplied. IDC (capitalised interest)
                # is sensitive to draw timing, so the even placeholder is an unfounded
                # substitution for a missing project-specific input — WARN rather than
                # silently substitute (once per process, #683). Supply
                # Financing_Terms.debt_drawdown_pct from the EPC milestone/payment
                # schedule for an auditable, project-specific draw. The placeholder is
                # sized to the resolved period count (#1570).
                fallback_drawdown = placeholder_debt_drawdown_pct(periods)
                _warn_placeholder_once(
                    "Financing_Terms.debt_drawdown_pct",
                    "Financing_Terms.debt_drawdown_pct / drawdown_pct absent — using a "
                    f"placeholder even draw {fallback_drawdown} for {periods} "
                    "construction period(s); IDC is draw-timing-sensitive, so supply "
                    "the EPC milestone draw schedule for a lender-grade figure.",
                )
            else:
                _validate_explicit_drawdowns(
                    fallback_drawdown, periods, source="Financing_Terms.drawdown_pct"
                )
            adapted["debt_drawdown_pct"] = fallback_drawdown
        else:
            _validate_explicit_drawdowns(
                adapted["debt_drawdown_pct"],
                periods,
                source="Financing_Terms.debt_drawdown_pct",
            )
        if adapted.get("construction_schedule") is None:
            # Same A1/#91 stance as the draw schedule above (#585): the capex phasing
            # is a placeholder, not a project input — WARN rather than silently
            # substitute (once per process, #683). Sized to the period count (#1570).
            adapted["construction_schedule"] = placeholder_construction_schedule(
                periods
            )
            _warn_placeholder_once(
                "Financing_Terms.construction_schedule",
                "Financing_Terms.construction_schedule absent — using a placeholder "
                f"{adapted['construction_schedule']} capex phasing for {periods} "
                "construction period(s); supply the EPC milestone schedule for a "
                "lender-grade figure.",
            )
        elif len(adapted["construction_schedule"]) < periods:
            raise ValueError(
                f"Financing_Terms.construction_schedule has "
                f"{len(adapted['construction_schedule'])} entries, fewer than "
                f"construction_periods = {periods} (#1507)."
            )
        if adapted.get("mix") is None:
            adapted["mix"] = {"usd_commercial_min": 1.0}
        return adapted

    financing = _section_case_insensitive(params, "financing")
    if financing:
        copied = dict(financing)
        periods = _resolve_construction_periods(params)
        if copied.get("debt_drawdown_pct") is not None:
            _validate_explicit_drawdowns(
                copied["debt_drawdown_pct"],
                periods,
                source="financing.debt_drawdown_pct",
            )
        if (
            copied.get("construction_schedule") is not None
            and len(copied["construction_schedule"]) < periods
        ):
            raise ValueError(
                f"financing.construction_schedule has "
                f"{len(copied['construction_schedule'])} entries, fewer than "
                f"construction_periods = {periods} (#1507)."
            )
        return copied

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

        # #585: the compact ``debt:`` schema must emit the SAME placeholder-
        # substitution WARNs as the Financing_Terms path above (A1/#91) — IDC is
        # draw-timing-sensitive, so a silently substituted even draw / capex
        # phasing is an unfounded stand-in for a missing project input. Both
        # placeholders are sized to the resolved period count (#1570).
        periods = _resolve_construction_periods(params)
        construction_schedule = debt_cfg.get("construction_schedule")
        if construction_schedule is None:
            construction_schedule = placeholder_construction_schedule(periods)
            _warn_placeholder_once(
                "debt.construction_schedule",
                "debt.construction_schedule absent — using a placeholder "
                f"{construction_schedule} capex phasing for {periods} construction "
                "period(s); supply the EPC milestone schedule for a "
                "lender-grade figure.",
            )
        elif len(construction_schedule) < periods:
            raise ValueError(
                f"debt.construction_schedule has {len(construction_schedule)} entries, "
                f"fewer than construction_periods = {periods} (#1507)."
            )
        debt_drawdown_pct = debt_cfg.get("debt_drawdown_pct")
        if debt_drawdown_pct is None:
            debt_drawdown_pct = placeholder_debt_drawdown_pct(periods)
            _warn_placeholder_once(
                "debt.debt_drawdown_pct",
                "debt.debt_drawdown_pct absent — using a placeholder even draw "
                f"{debt_drawdown_pct} for {periods} construction period(s); IDC is "
                "draw-timing-sensitive, so supply the EPC milestone draw schedule "
                "for a lender-grade figure.",
            )
        else:
            _validate_explicit_drawdowns(
                debt_drawdown_pct, periods, source="debt.debt_drawdown_pct"
            )

        return {
            "construction_periods": periods,
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


#: The count used when neither the financing section nor ``timeline`` declares one.
#: Kept for configurations that declare no build time at all (#1570 keeps it so that
#: those configurations do not move).
_DEFAULT_CONSTRUCTION_PERIODS = 2


def _coerce_period_count(value: Any) -> int:
    """Coerce a declared construction-period value the way the engine always has."""
    return max(
        0,
        int(_as_float(value, _DEFAULT_CONSTRUCTION_PERIODS)),
    )


def _declared_timeline_construction_years(
    params: Mapping[str, Any],
) -> Optional[Tuple[Any, int]]:
    """Return ``timeline.construction_years`` as ``(raw, coerced)``, or ``None``."""
    timeline = _section_case_insensitive(params, "timeline")
    if not timeline:
        return None
    raw = timeline.get("construction_years")
    if raw is None:
        return None
    return raw, _coerce_period_count(raw)


def _validate_explicit_drawdowns(drawdowns: Any, periods: int, *, source: str) -> None:
    """Validate explicit user drawdown fractions against period count and sum == 1.0."""
    if not isinstance(drawdowns, Sequence) or isinstance(drawdowns, (str, bytes)):
        raise ValueError(f"{source} must be a sequence of fractions (#1507).")
    values = [float(x) for x in drawdowns]
    if any(not math.isfinite(v) or v < 0.0 for v in values):
        raise ValueError(
            f"{source} {values!r} must contain finite non-negative fractions (#1507)."
        )
    if periods > 0 and len(values) < periods:
        raise ValueError(
            f"{source} has {len(values)} entries, fewer than construction_periods = {periods} (#1507)."
        )
    if periods > 0 and abs(sum(values) - 1.0) > 1e-6:
        raise ValueError(
            f"{source} {values!r} sums to {sum(values):.6f}, expected 1.0 (within 1e-6) (#1507)."
        )


def _resolve_construction_periods(params: Mapping[str, Any]) -> int:
    """Resolve the construction-period count and refuse a contradictory declaration.

    The financing section is chosen with the historical precedence of
    :func:`_extract_financing_terms` (a non-empty ``Financing_Terms``, then a
    non-empty ``financing``, then a present ``debt``, then the top level). Section
    names are case-insensitive; child keys remain case-sensitive to preserve the
    existing configuration contract.

    The count is checked against the scenario's declared build time,
    ``timeline.construction_years`` (#1570):

    * the financing section and ``timeline`` both declare a count and they differ:
      refused, naming both values. The count drives the debt draw, IDC, the CFADS
      timeline, the FX period offset and the project NPV/IRR lag, so it must equal
      the build time the scenario states;
    * ``Financing_Terms`` declares both ``construction_periods`` and
      ``construction_years`` and they differ: refused, naming both values;
    * only ``timeline`` declares a count: that count is used. Before #1570 the
      engine ignored ``timeline`` and fell back to two periods;
    * neither declares one: the historical default of two periods.

    Args:
        params: Complete scenario configuration or a compact debt test mapping.

    Returns:
        The construction-period count, coerced to an integer and clamped to zero.

    Raises:
        ValueError: If two declared counts disagree.
    """
    declared: Any = None
    source = "construction_periods"
    financing_terms = _section_case_insensitive(params, "Financing_Terms")
    financing = _section_case_insensitive(params, "financing")
    debt_cfg = _section_case_insensitive(params, "debt")
    if financing_terms:
        periods_raw = financing_terms.get("construction_periods")
        years_raw = financing_terms.get("construction_years")
        if (
            periods_raw is not None
            and years_raw is not None
            and _coerce_period_count(periods_raw) != _coerce_period_count(years_raw)
        ):
            raise ValueError(
                f"Financing_Terms.construction_periods = {periods_raw!r} and "
                f"Financing_Terms.construction_years = {years_raw!r} disagree; "
                "declare one construction-period count (#1570)."
            )
        if periods_raw is not None:
            declared, source = periods_raw, "Financing_Terms.construction_periods"
        elif years_raw is not None:
            declared, source = years_raw, "Financing_Terms.construction_years"
    elif financing:
        declared = financing.get("construction_periods")
        source = "financing.construction_periods"
    elif debt_cfg is not None:
        declared = debt_cfg.get("construction_periods")
        source = "debt.construction_periods"
    else:
        declared = params.get("construction_periods")

    timeline = _declared_timeline_construction_years(params)
    if declared is None:
        if timeline is not None:
            return timeline[1]
        return _DEFAULT_CONSTRUCTION_PERIODS

    count = _coerce_period_count(declared)
    if timeline is not None and timeline[1] != count:
        raise ValueError(
            f"{source} = {declared!r} gives {count} construction period(s), but "
            f"timeline.construction_years = {timeline[0]!r} gives {timeline[1]}. "
            "The engine's count drives the debt draw, IDC, the CFADS timeline, the FX "
            "start and the project NPV/IRR lag, so it must equal the declared build "
            "time; make the two agree (#1570)."
        )
    return count


def placeholder_construction_schedule(construction_periods: int) -> List[float]:
    """Return the placeholder capex phasing, one entry per construction period.

    Used only when a scenario supplies no ``construction_schedule``; the engine
    warns when it substitutes it. Two periods keep the historical ``[40, 60]``. Any
    other count is phased evenly. The entries' values do not enter the IDC
    arithmetic: :func:`finance.debt.construction.calculate_construction_drawdowns`
    uses the phasing only for its length, and the draw schedule sets the amounts.

    Args:
        construction_periods: The resolved construction-period count.

    Returns:
        Percentages of capex per construction period, summing to 100 (empty for a
        zero-period build).
    """
    n = max(0, int(construction_periods))
    if n == 0:
        return []
    if n == 2:
        return [40.0, 60.0]
    return [100.0 / n] * n


def placeholder_debt_drawdown_pct(construction_periods: int) -> List[float]:
    """Return the placeholder debt draw, one entry per construction period.

    Used only when a scenario supplies no ``debt_drawdown_pct``; the engine warns
    when it substitutes it. The IDC convention is
    :func:`finance.debt.construction.calculate_idc`'s: each entry is drawn at the
    start of its period and accrues a full period's interest, capitalised through
    the build, and debt not drawn inside the build is drawn at COD and accrues none.

    * One period: ``[0.5]``. A one-year build draws evenly through the year. The
      placeholder represents that by drawing half the debt at financial close and
      the rest at COD, so IDC is ``0.5 * D * r``: a year's interest on the average
      outstanding balance, the usual one-year approximation. This is the figure the
      engine gave before #1570, when it came from a two-entry draw list meeting a
      one-period window; it is now the stated convention.
    * Two or more periods: equal draws at the start of each period (``[0.5, 0.5]``
      for two, the historical placeholder). Each draw accrues a full period, so the
      figure is conservative against an average-balance approximation.
    * Zero periods: no draw inside the build, so no IDC.

    Args:
        construction_periods: The resolved construction-period count.

    Returns:
        Fractions of the debt drawn at the start of each construction period.
    """
    n = max(0, int(construction_periods))
    if n == 0:
        return []
    if n == 1:
        return [0.5]
    return [1.0 / n] * n


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
        cfads_ext.append(0.0)

    return cfads_ext, annual_row_debt_period_map, timeline_periods, bridge_debt_period


def _resolve_first_operating_period(
    annual_row_debt_period_map: Sequence[Mapping[str, Any]],
    construction_periods: int,
    bridge_debt_period: Optional[int],
) -> int:
    """Resolve the first debt period that carries an operating row.

    The debt timeline built by :func:`_build_cfads_timeline` is laid out as
    ``[construction] * construction_periods`` + an optional synthetic half-year
    ``bridge`` period + one period per operating row + post-tenor padding. The
    operating window therefore opens at
    ``construction_periods + (1 if a bridge exists else 0)``, and every period
    strictly below it is NON-operating: it can carry scheduled debt service but
    maps to no operating row, so a DSCR computed there is not a covenant
    observation (see :func:`plan_debt` for the index-space contract).

    The row->period map is the DEFINITIONAL source and is used whenever it holds a
    usable entry; the layout formula is the fallback for the degenerate case of a
    timeline with no operating rows at all, where the answer is the period at which
    the first operating row *would* be placed. The two agree on every committed
    scenario, which ``tests/finance/test_debt_period_taxonomy.py`` pins.

    Args:
        annual_row_debt_period_map: Canonical row->period map from the engine.
        construction_periods: Resolved construction-period count (see
            :func:`_resolve_construction_periods`); the sole authority for the
            construction window.
        bridge_debt_period: Synthetic bridge period index, or ``None`` when the
            timeline carries no bridge.

    Returns:
        The earliest debt-period index that maps to an operating row, clamped to
        zero. Never ``None``: the operating window always has a first period, even
        when no row currently occupies it.
    """
    mapped: List[int] = []
    for mapping in annual_row_debt_period_map:
        try:
            mapped.append(int(mapping["debt_period"]))
        except (KeyError, TypeError, ValueError):
            continue
    if mapped:
        return max(0, min(mapped))
    return max(0, int(construction_periods)) + (0 if bridge_debt_period is None else 1)


def _warn_if_decorative_tranches(config: Dict[str, Any]) -> None:
    """Warn once if a (non-input) ``Financing_Terms.debt_tranches`` block is present.

    The engine sizes debt via dual_dscr and splits it by ``mix`` proportions at the
    ``rates`` per currency; a hand-authored ``debt_tranches`` list is ignored. Flag it
    so the redundant block cannot silently drift from the engine's actual schedule.
    """
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


def resolve_bridge_period_treatment(config: Mapping[str, Any]) -> str:
    """Resolve the bridge-period debt/equity waterfall treatment (#1564).

    Reads ``Financing_Terms.bridge_period_treatment`` (or ``debt.bridge_period_treatment``,
    ``finance.debt.bridge_period_treatment``, or ``financing.bridge_period_treatment``).

    Returns:
        One of ``'historical_fold'``, ``'equity_cfads_match'``, or
        ``'construction_capitalized'``. Defaults to ``'historical_fold'`` for
        complete backward compatibility.

    Raises:
        ValueError: If an unknown treatment string is provided (CESSPIT fail-loud).
    """
    fin = _section_case_insensitive(config, "Financing_Terms") or {}
    debt_cfg = _section_case_insensitive(config, "debt") or {}
    financing = _section_case_insensitive(config, "financing") or {}
    finance_sec = _section_case_insensitive(config, "finance") or {}
    finance_debt = (
        _section_case_insensitive(finance_sec, "debt")
        if isinstance(finance_sec, Mapping)
        else {}
    )

    treatment_raw = (
        fin.get("bridge_period_treatment")
        or debt_cfg.get("bridge_period_treatment")
        or (
            finance_debt.get("bridge_period_treatment")
            if isinstance(finance_debt, Mapping)
            else None
        )
        or financing.get("bridge_period_treatment")
        or _BRIDGE_DEFAULT_TREATMENT
    )
    treatment = str(treatment_raw).lower().strip()
    if treatment not in _BRIDGE_VALID_TREATMENTS:
        raise ValueError(
            f"Unknown bridge_period_treatment {treatment_raw!r}; "
            f"expected one of {sorted(_BRIDGE_VALID_TREATMENTS)}"
        )
    return treatment
