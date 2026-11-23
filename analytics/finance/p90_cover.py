"""An opt-in P90 cover term that also sizes the debt against the recomputed P90 case (#1895).

A scenario sizes its debt on P50 (``Financing_Terms.target_dscr``), optionally with a
CFADS-scaled downside case (``bind_downside``). The recomputed P90 case
(:mod:`analytics.finance.p90_recomputed_downside`, #1836) re-runs the cash flow at P90
energy and tests the committed debt; on the lender case at 15.33.0 it covers the debt at a
minimum annual DSCR of about 1.06x against the 1.30x P50 target.

Owner ruling on #1895 (2026-11-22): keep the P50 sizing, disclose the recomputed P90 cover,
and add an opt-in term with no default. ``Financing_Terms.p90_cover_min_dscr`` is that term.

- **Absent** (every committed scenario): nothing happens. The pipeline runs as before and
  its debt result carries no ``p90_cover`` key.
- **Declared**: when the recomputed P90 case already covers the committed debt at the
  declared minimum annual DSCR, nothing changes. Otherwise the P50 sizing target
  (``Financing_Terms.target_dscr``) is raised to the smallest value at which the recomputed
  P90 case meets the cover, found by bracketing and bisection through the canonical
  pipeline, and the run is priced at that target. ``debt_result["p90_cover"]`` says
  whether the cover bound, the target it set, and the recomputed P90 minimum DSCR before
  and after.

The term needs an ``expected_results`` P50/P90 pair, because the recomputed case does, and
a DSCR sizing mode (``Financing_Terms.debt_sizing``). The target is raised rather than the
gearing capped because the debt is sculpted to the target: a lower cap repays the loan
sooner at the same DSCR and leaves the P90 cover where it was. Raising the target shrinks
debt service evenly across the years. A sculpt to the tighter of the P50 and P90 tests in
each year would keep slightly more debt, so the debt cut here is an upper bound on what
such a sculpt would make.

Each declared run that binds re-runs the base and P90 cases at every solver step (about
15 steps). A Monte Carlo or sensitivity trial on such a scenario pays that cost per trial.

The recomputed case is a modelled one-year exceedance on the scenario's own resource
basis, not a lender P90 claim (F-5). Annual figures only.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

#: The opt-in term, read from ``Financing_Terms`` only.
P90_COVER_KEY = "p90_cover_min_dscr"
P90_COVER_PATH = f"Financing_Terms.{P90_COVER_KEY}"

#: The solve stops when the sizing-target bracket is narrower than this (in DSCR, x).
TARGET_TOLERANCE = 1e-4

#: No sizing target above this is tried.
MAX_TARGET_DSCR = 10.0

#: Upper bound on solver steps (bracketing plus bisection).
MAX_SOLVER_STEPS = 40

LABEL = (
    "Debt sized so the recomputed P90 case (a modelled one-year exceedance on the "
    "scenario's own resource basis, against the committed debt and taxed on its interest) "
    "covers the committed debt service at the declared minimum annual DSCR. Not a lender "
    "P90 claim (F-5). Annual figures only (#1895)."
)


def _key_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return key
    for existing in mapping:
        if str(existing).lower() == key.lower():
            return existing
    return None


def _financing_terms(config: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    key = _key_case_insensitive(config, "Financing_Terms")
    section = config.get(key) if key is not None else None
    return section if isinstance(section, Mapping) else None


def resolve_p90_cover(config: Mapping[str, Any]) -> Optional[float]:
    """The declared P90 cover, or ``None`` when the scenario does not declare one.

    A key that is present must hold a finite number of at least 1.0, and the scenario must
    declare an ``expected_results`` P50/P90 pair. A null value is treated as absent.

    Raises:
        ValueError: If the declared value is not a finite number of at least 1.0, or the
            scenario has no P50/P90 pair. The message names the YAML path.
    """
    fin = _financing_terms(config)
    if fin is None or P90_COVER_KEY not in fin or fin[P90_COVER_KEY] is None:
        return None
    raw = fin[P90_COVER_KEY]
    number: Optional[float] = None
    if not isinstance(raw, bool):
        try:
            number = float(raw)
        except (TypeError, ValueError):
            number = None
    if number is None or not math.isfinite(number):
        raise ValueError(
            f"{P90_COVER_PATH} must be a finite number (got {raw!r}) (#1895). Leave it "
            "out to size on the scenario's own terms only."
        )
    if number < 1.0:
        raise ValueError(
            f"{P90_COVER_PATH} must be at least 1 (got {raw!r}): below 1.0x the P90 case "
            "could not pay its debt service (#1895)."
        )
    from analytics.finance.p90_recomputed_downside import p90_energy_ratio

    if p90_energy_ratio(config) is None:
        raise ValueError(
            f"{P90_COVER_PATH} is declared, but the scenario has no expected_results "
            "net_aep_p50_gwh / net_aep_p90_gwh pair, so there is no P90 case to size "
            "against (#1895)."
        )
    return number


def without_p90_cover(config: Mapping[str, Any]) -> Dict[str, Any]:
    """A deep copy of ``config`` without the P90 cover term."""
    out = copy.deepcopy(dict(config))
    fin = _financing_terms(out)
    if isinstance(fin, dict):
        fin.pop(P90_COVER_KEY, None)
    return out


def _at_target(config: Mapping[str, Any], target: float) -> Dict[str, Any]:
    out = copy.deepcopy(dict(config))
    fin = _financing_terms(out)
    assert isinstance(fin, dict)  # resolve_p90_cover found the term in this section
    fin["target_dscr"] = target
    return out


def _declared_sizing_target(config: Mapping[str, Any]) -> float:
    """The P50 sizing target, after checking the scenario sizes its debt on DSCR."""
    from finance.debt_v14 import _DSCR_SIZING_MODES

    fin = _financing_terms(config) or {}
    mode = str(fin.get("debt_sizing", "")).lower()
    if mode not in _DSCR_SIZING_MODES:
        raise ValueError(
            f"{P90_COVER_PATH} sizes the debt by raising Financing_Terms.target_dscr, so "
            f"Financing_Terms.debt_sizing must be one of {', '.join(_DSCR_SIZING_MODES)} "
            f"(got {fin.get('debt_sizing')!r}) (#1895)."
        )
    raw: Any = fin.get("target_dscr")
    target = math.nan
    if raw is not None and not isinstance(raw, bool):
        try:
            target = float(raw)
        except (TypeError, ValueError):
            target = math.nan
    if not math.isfinite(target) or target <= 0.0:
        raise ValueError(
            f"{P90_COVER_PATH} needs a positive Financing_Terms.target_dscr (got {raw!r}) "
            "(#1895)."
        )
    return target


Recompute = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def _recomputed_min(check: Mapping[str, Any]) -> Optional[float]:
    """The recomputed P90 minimum DSCR, or ``None`` when there is no debt service."""
    if check.get("status") != "ok":
        return None
    value = ((check.get("cases") or {}).get("recomputed") or {}).get("min_dscr")
    return float(value) if value is not None else None


def _meets(value: Optional[float], cover: float) -> bool:
    # No debt service at all has nothing to cover.
    return value is None or value >= cover


def solve_p90_cover(
    config: Mapping[str, Any],
    cover: float,
    recompute: Optional[Recompute] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The configuration to price, and the ``p90_cover`` block that describes it.

    The debt is sculpted to the P50 sizing target, so a lower gearing cap only repays the
    loan sooner at the same DSCR. The P50 target is raised instead, until the recomputed
    P90 case meets the cover: the smallest such target, to ``TARGET_TOLERANCE``.

    Args:
        config: The scenario, with or without the term. The term itself is not read here.
        cover: The declared minimum annual DSCR of the recomputed P90 case.
        recompute: The recomputed-P90 function; defaults to
            :func:`analytics.finance.p90_recomputed_downside.recomputed_p90_downside`.

    Returns:
        ``(config_to_price, block)``. ``config_to_price`` has no term, and carries the
        raised sizing target when the cover binds.

    Raises:
        ValueError: If the scenario does not size its debt on DSCR, the recomputed P90
            case is unavailable at the scenario's own sizing, or no target up to
            ``MAX_TARGET_DSCR`` meets the cover.
    """
    if recompute is None:
        from analytics.finance.p90_recomputed_downside import recomputed_p90_downside

        recompute = recomputed_p90_downside
    base = without_p90_cover(config)
    declared_target = _declared_sizing_target(base)
    first = recompute(base)
    before = _recomputed_min(first)
    if before is None:
        raise ValueError(
            f"{P90_COVER_PATH} is declared, but the recomputed P90 case is unavailable "
            f"at the scenario's own sizing: {first.get('reason', 'no debt service')} "
            "(#1895)."
        )
    block: Dict[str, Any] = {
        "label": LABEL,
        "source": P90_COVER_PATH,
        "declared_min_dscr": cover,
        "recomputed_min_dscr_unbound": before,
        "declared_target_dscr": declared_target,
    }
    if before >= cover:
        block.update(
            binding=False,
            target_dscr=declared_target,
            recomputed_min_dscr=before,
            solver_steps=0,
        )
        return base, block

    # The cover binds: ``low`` never meets it. Find a ``high`` that does, then bisect.
    low, steps = declared_target, 0
    high = declared_target
    high_min: Optional[float] = None
    while True:
        high = min(high * 1.25, MAX_TARGET_DSCR)
        steps += 1
        high_min = _recomputed_min(recompute(_at_target(base, high)))
        if _meets(high_min, cover):
            break
        low = high
        if high >= MAX_TARGET_DSCR:
            raise ValueError(
                f"{P90_COVER_PATH} = {cover:g}: no P50 sizing target up to "
                f"{MAX_TARGET_DSCR:g} lets the recomputed P90 case cover its debt "
                "service at that DSCR (#1895)."
            )
    while high - low > TARGET_TOLERANCE and steps < MAX_SOLVER_STEPS:
        steps += 1
        mid = 0.5 * (low + high)
        value = _recomputed_min(recompute(_at_target(base, mid)))
        if _meets(value, cover):
            high, high_min = mid, value
        else:
            low = mid
    block.update(
        binding=True,
        target_dscr=high,
        recomputed_min_dscr=high_min,
        solver_steps=steps,
    )
    return _at_target(base, high), block


def priced_config(
    config: Mapping[str, Any], block: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    """The configuration a run with this ``p90_cover`` block priced, without the term.

    ``block`` is ``debt_result["p90_cover"]``, or ``None`` when the scenario declares no
    cover. A cover that bound priced the scenario at its raised sizing target.
    """
    if not block or not block.get("binding"):
        return without_p90_cover(config)
    return _at_target(without_p90_cover(config), float(block["target_dscr"]))


__all__ = [
    "MAX_TARGET_DSCR",
    "TARGET_TOLERANCE",
    "LABEL",
    "P90_COVER_KEY",
    "P90_COVER_PATH",
    "priced_config",
    "resolve_p90_cover",
    "solve_p90_cover",
    "without_p90_cover",
]
