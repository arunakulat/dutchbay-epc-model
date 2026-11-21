"""Capital-structure screening for the lender report (#1825 slice i).

Three analysis optimizers that were reachable only from their own command-line tool now feed
one opt-in section of the command-line lender report:

* the debt tranche mix search (:func:`analytics.capital_structure_optimizer_v14.optimize_debt_mix`),
* the capex contingency search (:func:`~analytics.capital_structure_optimizer_v14.optimize_capex_contingency`),
* the gearing-ceiling search (:func:`analytics.optimization_v14.optimize_parameter` on
  ``Financing_Terms.debt_ratio``),

each held to the scenario's own lender covenants, with the infeasibility register
(:mod:`analytics.infeasibility_diagnostics`) shown when no candidate clears them.

What the section is, and is not:

* A **screening** of alternatives around the committed case. Every candidate is scored by the
  canonical evaluation gateway (:func:`analytics.evaluation_v14.evaluate_with_overrides`); no
  finance logic is re-implemented, and the committed case, its figures and every KPI are
  unchanged. The section never replaces the committed capital structure.
* Universal: the covenants, the current mix, the capex and its contingency line come from the
  scenario; the search lattice is an analysis setting from the run configuration
  (``lender_report.capital_structure``). A scenario that lacks a required input gets the
  section listed under "Sections not run" with the missing key named.
* Ranked on equity NPV (#1456): equity IRR can rank options backwards when equity cash flows
  change sign more than once.

GWTF:
    - FRAMEWORK-03: one seam; the report model holds the typed block, this module fills it.
    - FRAMEWORK-01: a scenario that cannot build a search gets a stated reason, never a
      default covenant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, Mapping, Optional, Sequence, Tuple, Union

from app.reports.report_model import (
    CapitalStructureBlock,
    CapitalStructureCandidate,
    CapitalStructureSearch,
)

__all__ = [
    "CapitalStructureSettings",
    "DEFAULT_CAPITAL_STRUCTURE_SETTINGS",
    "OBJECTIVE_KEY",
    "SECTION_CAPITAL_STRUCTURE",
    "build_capital_structure_section",
    "settings_from_config",
]

#: The section's name in the report's "sections not run" list.
SECTION_CAPITAL_STRUCTURE = "Capital structure screening"

#: Ranking objective (#1456).
OBJECTIVE_KEY = "equity_npv"

#: The per-period sculpt floor the covenant is tested on (#790: the fold-corrected headline
#: min_dscr can sit below the target under an interest-only lead-in even when every operating
#: period holds it).
_DSCR_KEY = "min_dscr_period"

#: Config paths the searches perturb.
_GEARING_PATH = "Financing_Terms.debt_ratio"


@dataclass(frozen=True)
class CapitalStructureSettings:
    """The search lattice: analysis settings, not site inputs (``lender_report.capital_structure``)."""

    enabled: bool = False
    lkr_bounds: Tuple[float, float] = (0.0, 0.6)
    dfi_bounds: Tuple[float, float] = (0.0, 0.4)
    mix_steps: int = 6
    contingency_bounds: Tuple[float, float] = (0.0, 0.20)
    contingency_steps: int = 11
    gearing_bounds: Tuple[float, float] = (0.30, 0.80)
    gearing_steps: int = 11


#: Off by default (#1825: each analytics section is opt-in).
DEFAULT_CAPITAL_STRUCTURE_SETTINGS = CapitalStructureSettings()


def _pair(raw: Any, name: str, default: Tuple[float, float]) -> Tuple[float, float]:
    if raw is None:
        return default
    seq = list(raw)
    if len(seq) != 2:
        raise ValueError(f"lender_report.capital_structure.{name} must be [low, high]")
    return float(seq[0]), float(seq[1])


def settings_from_config(raw: Optional[Mapping[str, Any]]) -> CapitalStructureSettings:
    """Read ``lender_report.capital_structure`` from the run configuration.

    ``None`` or an empty block keeps every default (switched off).
    """
    if not raw:
        return DEFAULT_CAPITAL_STRUCTURE_SETTINGS
    d = DEFAULT_CAPITAL_STRUCTURE_SETTINGS
    return CapitalStructureSettings(
        enabled=bool(raw.get("enabled", d.enabled)),
        lkr_bounds=_pair(raw.get("lkr_bounds"), "lkr_bounds", d.lkr_bounds),
        dfi_bounds=_pair(raw.get("dfi_bounds"), "dfi_bounds", d.dfi_bounds),
        mix_steps=int(raw.get("mix_steps", d.mix_steps)),
        contingency_bounds=_pair(
            raw.get("contingency_bounds"), "contingency_bounds", d.contingency_bounds
        ),
        contingency_steps=int(raw.get("contingency_steps", d.contingency_steps)),
        gearing_bounds=_pair(
            raw.get("gearing_bounds"), "gearing_bounds", d.gearing_bounds
        ),
        gearing_steps=int(raw.get("gearing_steps", d.gearing_steps)),
    )


def _number(value: Any) -> Optional[float]:
    try:
        out = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    return out if out is not None and math.isfinite(out) else None


def _covenants(scenario: Mapping[str, Any]) -> Union[List[Any], str]:
    """The lender covenants from ``constraints``, as optimizer constraints, or a reason."""
    from analytics.contracts_v14 import CovenantConstraint

    block = scenario.get("constraints")
    if not isinstance(block, Mapping):
        return "not run: the scenario declares no constraints block (lender covenants)"
    dscr = _number(block.get("min_dscr_covenant"))
    if dscr is None or dscr <= 0:
        return (
            "not run: the scenario declares no positive constraints.min_dscr_covenant"
        )
    out = [CovenantConstraint(key=_DSCR_KEY, minimum=dscr, maximum=None)]
    llcr = _number(block.get("min_llcr_covenant"))
    if llcr is not None:
        out.append(CovenantConstraint(key="llcr", minimum=llcr, maximum=None))
    balloon = _number(block.get("max_balloon_pct"))
    if balloon is not None:
        out.append(CovenantConstraint(key="balloon_pct", minimum=None, maximum=balloon))
    return out


def _split_on_committed(
    base: Mapping[str, Any], constraints: Sequence[Any]
) -> Tuple[List[Any], List[str]]:
    """Split the covenants into those the committed case clears and those it already fails.

    A screen against a bound the committed case itself fails names no candidate, so such a
    covenant is shown with the committed value and not screened on (the lender case, for
    one, carries a balloon above its declared cap and refinances it, #1396). A covenant whose
    KPI the evaluation does not publish is kept: the optimizer then fails loud on it.
    """
    from analytics.capital_structure_optimizer_v14 import _apply_constraints

    held: List[Any] = []
    not_screened: List[str] = []
    for c in constraints:
        value = _number(base.get(c.key))
        if value is None:
            held.append(c)
            continue
        _, ok, _ = _apply_constraints({c.key: value}, [c])
        if ok:
            held.append(c)
        else:
            text = _constraint_text([c])[0]
            not_screened.append(
                f"{text}: the committed case itself reaches {value:.4g}, so the searches "
                "do not screen on it"
            )
    return held, not_screened


def _constraint_text(constraints: Sequence[Any]) -> List[str]:
    lines = []
    for c in constraints:
        if c.minimum is not None:
            lines.append(f"{c.key} >= {c.minimum:g}")
        if c.maximum is not None:
            lines.append(f"{c.key} <= {c.maximum:g}")
    return lines


def _candidate(point: Any, label: str, *, best: bool) -> CapitalStructureCandidate:
    return CapitalStructureCandidate(
        label=label,
        objective=_number(point.objective),
        constraints={
            k: v for k, v in point.constraints.items() if _number(v) is not None
        },
        feasible=bool(point.feasible),
        binding=list(point.binding_constraints),
        best=best,
    )


def _infeasibility_lines(result: Any) -> List[str]:
    """The infeasibility register (#741) as report lines, worst shortfall first."""
    lines: List[str] = []
    diagnostics = getattr(result, "diagnostics", None)
    summary = getattr(diagnostics, "binding_summary", "") or getattr(
        result, "infeasible_reason", None
    )
    for v in getattr(diagnostics, "violations", None) or ():
        side = ">=" if v.bound_kind == "minimum" else "<="
        lines.append(
            f"{v.key} {side} {v.required:g}: closest candidate reached {v.achieved:.4g}, "
            f"short by {v.shortfall:.4g}; violated by {v.candidates_violating} of "
            f"{v.candidates_total} candidates"
        )
    if not lines and summary:
        lines.append(str(summary))
    return lines


def _mix_label(value: Sequence[float]) -> str:
    lkr, dfi = float(value[0]), float(value[1])
    return f"LKR {lkr:.0%} / DFI {dfi:.0%} / USD {max(0.0, 1.0 - lkr - dfi):.0%}"


def _mix_search(
    config_path: str,
    scenario: Mapping[str, Any],
    constraints: Sequence[Any],
    settings: CapitalStructureSettings,
) -> CapitalStructureSearch:
    from analytics.capital_structure_optimizer_v14 import optimize_debt_mix

    result = optimize_debt_mix(
        config_path,
        objective_key=OBJECTIVE_KEY,
        direction="max",
        constraints=constraints,
        lkr_bounds=settings.lkr_bounds,
        dfi_bounds=settings.dfi_bounds,
        n_steps=settings.mix_steps,
    )
    terms = scenario.get("Financing_Terms") or {}
    mix = terms.get("mix") if isinstance(terms, Mapping) else None
    current = None
    if isinstance(mix, Mapping):
        lkr, dfi = _number(mix.get("lkr_max")), _number(mix.get("dfi_max"))
        if lkr is not None and dfi is not None:
            current = (
                f"LKR {lkr:.0%} / DFI {dfi:.0%} / USD commercial "
                f"{max(0.0, 1 - lkr - dfi):.0%}"
            )
    best = result.best
    rows = [_candidate(p, _mix_label(p.value), best=p is best) for p in result.curve]
    return CapitalStructureSearch(
        kind="Debt tranche mix",
        searched=(
            f"LKR share {settings.lkr_bounds[0]:.0%}-{settings.lkr_bounds[1]:.0%}, DFI "
            f"share {settings.dfi_bounds[0]:.0%}-{settings.dfi_bounds[1]:.0%}, "
            f"{settings.mix_steps} steps each; USD commercial takes the rest"
        ),
        current=current,
        best_label=None if best is None else next(r.label for r in rows if r.best),
        best_objective=None if best is None else _number(best.objective),
        candidates=rows,
        n_evaluated=len(rows),
        n_feasible=sum(1 for r in rows if r.feasible),
        infeasibility=[] if result.feasible else _infeasibility_lines(result),
        note=(
            "Only the tranche shares change; each tranche keeps the scenario's own rate, "
            "tenor and currency terms. The search does not test whether lenders would "
            "offer that mix."
        ),
    )


def _contingency_search(
    config_path: str,
    scenario: Mapping[str, Any],
    constraints: Sequence[Any],
    settings: CapitalStructureSettings,
) -> Union[CapitalStructureSearch, str]:
    from analytics.capital_structure_optimizer_v14 import optimize_capex_contingency

    capex = scenario.get("capex")
    total = _number(capex.get("usd_total")) if isinstance(capex, Mapping) else None
    breakdown = capex.get("breakdown") if isinstance(capex, Mapping) else None
    line = (
        _number(breakdown.get("contingency_usd"))
        if isinstance(breakdown, Mapping)
        else None
    )
    if total is None or total <= 0:
        return "not run: the scenario declares no positive capex.usd_total"
    if line is None:
        return "not run: the scenario declares no capex.breakdown.contingency_usd line"
    base = total - line
    result = optimize_capex_contingency(
        config_path,
        base_capex_usd=base,
        objective_key=OBJECTIVE_KEY,
        direction="max",
        constraints=constraints,
        contingency_bounds=settings.contingency_bounds,
        n_steps=settings.contingency_steps,
    )
    rows = [
        _candidate(
            p,
            f"{p.value[0]:.1%} (capex ${base * (1 + p.value[0]) / 1e6:,.1f}M)",
            best=False,
        )
        for p in result.curve
    ]
    feasible_fracs = [float(p.value[0]) for p in result.curve if p.feasible]
    # Return-maximising is always the smallest contingency, so the section reports the
    # covenant headroom instead: the largest contingency every covenant still clears.
    headroom = max(feasible_fracs) if feasible_fracs else None
    rows = [
        (
            r.model_copy(update={"best": True})
            if headroom is not None and float(p.value[0]) == headroom
            else r
        )
        for r, p in zip(rows, result.curve, strict=True)
    ]
    top = settings.contingency_bounds[1]
    note = (
        None
        if headroom is None
        else (
            f"Every covenant holds up to {headroom:.1%} contingency"
            + (
                ", the top of the searched range."
                if math.isclose(headroom, top)
                else "; above that a covenant fails."
            )
            + f" The scenario carries {line / base:.1%}."
        )
    )
    return CapitalStructureSearch(
        kind="Capex contingency",
        searched=(
            f"{settings.contingency_bounds[0]:.0%}-{top:.0%} on a base of "
            f"${base / 1e6:,.1f}M (capex.usd_total less capex.breakdown.contingency_usd), "
            f"{settings.contingency_steps} steps"
        ),
        current=f"{line / base:.1%} (${line / 1e6:,.2f}M)",
        best_label=None if headroom is None else f"{headroom:.1%} (covenant headroom)",
        best_objective=None,
        candidates=rows,
        n_evaluated=len(rows),
        n_feasible=len(feasible_fracs),
        infeasibility=[] if result.feasible else _infeasibility_lines(result),
        note=note,
    )


def _gearing_search(
    config_path: str,
    scenario: Mapping[str, Any],
    constraints: Sequence[Any],
    settings: CapitalStructureSettings,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> Union[CapitalStructureSearch, str]:
    from analytics.capital_structure_optimizer_v14 import _apply_constraints
    from analytics.optimization_v14 import optimize_parameter

    capex = scenario.get("capex")
    total = _number(capex.get("usd_total")) if isinstance(capex, Mapping) else None
    terms = scenario.get("Financing_Terms")
    current = _number(terms.get("debt_ratio")) if isinstance(terms, Mapping) else None
    if total is None or total <= 0:
        return "not run: the scenario declares no positive capex.usd_total"
    if current is None:
        return "not run: the scenario declares no Financing_Terms.debt_ratio"
    dscr = next((c for c in constraints if c.key == _DSCR_KEY), None)
    result = optimize_parameter(
        config_path,
        param_path=_GEARING_PATH,
        objective_key=OBJECTIVE_KEY,
        lower=settings.gearing_bounds[0],
        upper=settings.gearing_bounds[1],
        direction="max",
        n_steps=settings.gearing_steps,
        constraint_key=None if dscr is None else _DSCR_KEY,
        constraint_min=None if dscr is None else dscr.minimum,
    )
    rows: List[CapitalStructureCandidate] = []
    realised: List[Optional[float]] = []
    for p in result.curve:
        kpis = evaluate(config_path, {_GEARING_PATH: float(p.value)})
        debt = _number(kpis.get("max_debt_usd"))
        gearing = None if debt is None else debt / total
        realised.append(gearing)
        # optimize_parameter holds one constraint (the DSCR); every other held covenant is
        # read back from the same evaluation with the debt-mix optimizer's own test, so the
        # three searches screen against the same covenants.
        values, feasible, binding = _apply_constraints(kpis, constraints)
        feasible = feasible and bool(p.feasible)
        rows.append(
            CapitalStructureCandidate(
                label=(
                    f"ceiling {p.value:.0%}"
                    + ("" if gearing is None else f", realised {gearing:.1%}")
                ),
                objective=_number(p.objective),
                constraints={k: v for k, v in values.items() if _number(v) is not None},
                feasible=feasible,
                binding=list(binding) or ([] if p.feasible else [_DSCR_KEY]),
                best=False,
            )
        )
    finite = [g for g in realised if g is not None]
    binds = len(finite) > 1 and (max(finite) - min(finite)) > 1e-6
    note: Optional[str]
    best_label: Optional[str] = None
    best_objective: Optional[float] = None
    feasible_rows = [
        i for i, r in enumerate(rows) if r.feasible and r.objective is not None
    ]
    if not binds:
        # #1785 domain D-1: when the ceiling binds nowhere, every point raises the same
        # debt and the report must not name a gearing the sweep did not reach.
        note = (
            "The gearing ceiling does not bind anywhere in the searched range: the debt is "
            "sized by the DSCR sculpt, so every point raises the same debt and no gearing "
            "optimum is reported."
        )
    else:
        top = max(finite)
        first_top = next(
            p.value
            for p, g in zip(result.curve, realised, strict=True)
            if g is not None and math.isclose(g, top, abs_tol=1e-6)
        )
        note = (
            f"Realised gearing tops out at {top:.1%}: from a {first_top:.0%} ceiling up, "
            "the debt is sized by the DSCR sculpt, not the ceiling, and every point raises "
            "the same debt."
        )
        if feasible_rows:
            # First of equal objectives in lattice order, as the optimizer breaks ties.
            i = max(feasible_rows, key=lambda j: (rows[j].objective or 0.0, -j))
            rows[i] = rows[i].model_copy(update={"best": True})
            best_label = rows[i].label
            best_objective = rows[i].objective
    return CapitalStructureSearch(
        kind="Gearing ceiling",
        searched=(
            f"Financing_Terms.debt_ratio {settings.gearing_bounds[0]:.0%}-"
            f"{settings.gearing_bounds[1]:.0%}, {settings.gearing_steps} steps"
        ),
        current=f"ceiling {current:.0%}",
        best_label=best_label,
        best_objective=best_objective,
        candidates=rows,
        n_evaluated=len(rows),
        n_feasible=sum(1 for r in rows if r.feasible),
        infeasibility=(
            []
            if feasible_rows
            else _infeasibility_lines(result)
            or ["No ceiling in the searched range clears every held covenant."]
        ),
        note=note,
    )


def _evaluate(config_path: str, overrides: Mapping[str, Any]) -> Mapping[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides

    out = evaluate_with_overrides(config_path, dict(overrides))
    return out if isinstance(out, Mapping) else {}


def build_capital_structure_section(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    settings: CapitalStructureSettings,
    *,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] = _evaluate,
) -> Union[CapitalStructureBlock, str]:
    """Build the capital-structure screening block, or say why it was not built.

    Args:
        scenario_config_path: The effective scenario the run used (each candidate perturbs it).
        scenario: The parsed scenario.
        settings: The search lattice from ``lender_report.capital_structure``.
        evaluate: Seam for tests; production uses the canonical evaluation gateway.

    Returns:
        The typed block, or a ``"not run: ..."`` reason for "Sections not run".
    """
    if not settings.enabled:
        return (
            "not run: switched off (lender_report.capital_structure.enabled is false; "
            "the section is opt-in, #1825)"
        )
    constraints = _covenants(scenario)
    if isinstance(constraints, str):
        return constraints
    path = str(scenario_config_path)
    base = evaluate(path, {})
    held, not_screened = _split_on_committed(base, constraints)
    if not held:
        return (
            "not run: the committed case itself fails every declared covenant ("
            + "; ".join(not_screened)
            + "), so no screen against them can name a candidate"
        )
    searches: List[CapitalStructureSearch] = [
        _mix_search(path, scenario, held, settings)
    ]
    not_run: List[str] = []
    for kind, built in (
        (
            "Capex contingency",
            _contingency_search(path, scenario, held, settings),
        ),
        (
            "Gearing ceiling",
            _gearing_search(path, scenario, held, settings, evaluate),
        ),
    ):
        if isinstance(built, str):
            not_run.append(f"{kind}: {built}")
        else:
            searches.append(built)
    return CapitalStructureBlock(
        objective_key=OBJECTIVE_KEY,
        committed_objective=_number(base.get(OBJECTIVE_KEY)),
        committed_dscr=_number(base.get(_DSCR_KEY)),
        covenants=_constraint_text(held),
        covenant_keys=[c.key for c in held],
        covenants_not_screened=not_screened,
        searches=searches,
        searches_not_run=not_run,
    )
