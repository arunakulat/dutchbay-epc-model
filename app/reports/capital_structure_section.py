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
* Honest about what a screen can show. A declared covenant the committed case itself fails
  is not screened on; it is shown per candidate, and a candidate that also clears it is
  marked. When debt is re-sized to the DSCR target at every point, the section says the DSCR
  screen cannot fail and shows the headline minimum DSCR beside it (#1859 domain D-1 to D-3).

GWTF:
    - FRAMEWORK-03: one seam; the report model holds the typed block, this module fills it.
    - FRAMEWORK-01: a scenario that cannot build a search gets a stated reason, never a
      default covenant.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

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

#: KPIs every candidate table shows beside the screened covenants: the headline minimum DSCR
#: (the report's KPI, the per-year covenant table, #790) and the sized debt.
_SHOWN_KEYS: Tuple[str, ...] = ("min_dscr", "max_debt_usd")


@dataclass(frozen=True)
class _Covenant:
    """A covenant bound and the scenario key it comes from."""

    constraint: Any
    source: str


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


def _covenants(scenario: Mapping[str, Any]) -> Union[List[_Covenant], str]:
    """The lender covenants from ``constraints``, with their sources, or a reason.

    The refinancing cap (``constraints.refinancing.max_refinance_pct``, #1396) bounds the
    share of principal refinanced at maturity, that is the balloon, so it is screened on
    ``balloon_pct`` when the scenario enables refinancing.
    """
    from analytics.contracts_v14 import CovenantConstraint

    block = scenario.get("constraints")
    if not isinstance(block, Mapping):
        return "not run: the scenario declares no constraints block (lender covenants)"
    dscr = _number(block.get("min_dscr_covenant"))
    if dscr is None or dscr <= 0:
        return (
            "not run: the scenario declares no positive constraints.min_dscr_covenant"
        )
    out = [
        _Covenant(
            CovenantConstraint(key=_DSCR_KEY, minimum=dscr, maximum=None),
            "constraints.min_dscr_covenant",
        )
    ]
    llcr = _number(block.get("min_llcr_covenant"))
    if llcr is not None:
        out.append(
            _Covenant(
                CovenantConstraint(key="llcr", minimum=llcr, maximum=None),
                "constraints.min_llcr_covenant",
            )
        )
    balloon = _number(block.get("max_balloon_pct"))
    if balloon is not None:
        out.append(
            _Covenant(
                CovenantConstraint(key="balloon_pct", minimum=None, maximum=balloon),
                "constraints.max_balloon_pct",
            )
        )
    refi = block.get("refinancing")
    cap = (
        _number(refi.get("max_refinance_pct"))
        if isinstance(refi, Mapping) and refi.get("enabled")
        else None
    )
    if cap is not None:
        out.append(
            _Covenant(
                CovenantConstraint(key="balloon_pct", minimum=None, maximum=cap),
                "constraints.refinancing.max_refinance_pct, the refinancing cap",
            )
        )
    return out


def _split_on_committed(
    base: Mapping[str, Any], covenants: Sequence[_Covenant]
) -> Tuple[List[_Covenant], List[_Covenant]]:
    """Split the covenants into those the committed case clears and those it already fails.

    The searches rank within the covenants the committed case clears. A covenant it already
    fails (the lender case carries a balloon above its declared cap and refinances it, #1396)
    is not screened on: it is shown per candidate, and a candidate that also clears it is
    marked, so a reader can see which alternatives would clear it. A covenant whose KPI the
    evaluation does not publish is kept: the optimizer then fails loud on it.
    """
    from analytics.capital_structure_optimizer_v14 import _apply_constraints

    held: List[_Covenant] = []
    not_screened: List[_Covenant] = []
    for cov in covenants:
        c = cov.constraint
        value = _number(base.get(c.key))
        if value is None:
            held.append(cov)
            continue
        _, ok, _ = _apply_constraints({c.key: value}, [c])
        (held if ok else not_screened).append(cov)
    return held, not_screened


def _bound_text(c: Any) -> str:
    parts = []
    if c.minimum is not None:
        parts.append(f"{c.key} >= {c.minimum:g}")
    if c.maximum is not None:
        parts.append(f"{c.key} <= {c.maximum:g}")
    return " and ".join(parts)


def _covenant_text(cov: _Covenant) -> str:
    return f"{_bound_text(cov.constraint)} ({cov.source})"


def _not_screened_text(cov: _Covenant, base: Mapping[str, Any]) -> str:
    value = _number(base.get(cov.constraint.key))
    reached = "" if value is None else f" reaches {value:.4g}"
    return (
        f"{_covenant_text(cov)}: the committed case itself{reached}, so the searches rank "
        "within the covenants it clears and show this one per candidate; a candidate "
        "that also clears it is marked"
    )


def _display_keys(
    held: Sequence[_Covenant], not_screened: Sequence[_Covenant]
) -> List[str]:
    """KPIs shown per candidate beside the held covenants, never screened on."""
    held_keys = {cov.constraint.key for cov in held}
    keys = [k for k in _SHOWN_KEYS if k not in held_keys]
    for cov in not_screened:
        if cov.constraint.key not in held_keys and cov.constraint.key not in keys:
            keys.append(cov.constraint.key)
    return keys


def _shown_values(
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
    config_path: str,
    overrides: Mapping[str, Any],
    keys: Sequence[str],
) -> Dict[str, float]:
    """Read the shown KPIs back for one candidate through the same gateway."""
    kpis = evaluate(config_path, overrides)
    out: Dict[str, float] = {}
    for k in keys:
        v = _number(kpis.get(k))
        if v is not None:
            out[k] = v
    return out


def _also_clears(
    values: Mapping[str, Any], not_screened: Sequence[_Covenant]
) -> List[str]:
    """The not-screened covenants a candidate's read-back values also clear."""
    from analytics.capital_structure_optimizer_v14 import _apply_constraints

    out = []
    for cov in not_screened:
        value = _number(values.get(cov.constraint.key))
        if value is None:
            continue
        _, ok, _ = _apply_constraints({cov.constraint.key: value}, [cov.constraint])
        if ok:
            out.append(_bound_text(cov.constraint))
    return out


def _candidate(
    point: Any,
    label: str,
    *,
    best: bool,
    not_screened: Sequence[_Covenant] = (),
    shown: Optional[Mapping[str, float]] = None,
) -> CapitalStructureCandidate:
    values = {k: v for k, v in point.constraints.items() if _number(v) is not None}
    for k, v in (shown or {}).items():
        values.setdefault(k, v)
    return CapitalStructureCandidate(
        label=label,
        objective=_number(point.objective),
        constraints=values,
        feasible=bool(point.feasible),
        binding=list(point.binding_constraints),
        best=best,
        also_clears=_also_clears(values, not_screened),
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
    held: Sequence[_Covenant],
    not_screened: Sequence[_Covenant],
    settings: CapitalStructureSettings,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> CapitalStructureSearch:
    from analytics.capital_structure_optimizer_v14 import (
        _MIX_DFI_PATH,
        _MIX_LKR_PATH,
        optimize_debt_mix,
    )

    result = optimize_debt_mix(
        config_path,
        objective_key=OBJECTIVE_KEY,
        direction="max",
        constraints=[c.constraint for c in held],
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
    keys = _display_keys(held, not_screened)
    rows = [
        _candidate(
            p,
            _mix_label(p.value),
            best=p is best,
            not_screened=not_screened,
            shown=_shown_values(
                evaluate,
                config_path,
                {_MIX_LKR_PATH: float(p.value[0]), _MIX_DFI_PATH: float(p.value[1])},
                keys,
            ),
        )
        for p in result.curve
    ]
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
    held: Sequence[_Covenant],
    not_screened: Sequence[_Covenant],
    settings: CapitalStructureSettings,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> Union[CapitalStructureSearch, str]:
    from analytics.capital_structure_optimizer_v14 import optimize_capex_contingency

    capex = scenario.get("capex")
    if isinstance(capex, Mapping) and capex.get("derive_from_breakdown"):
        # #1859 domain D-4: the engine sums capex.breakdown for this scenario, so a
        # capex.usd_total override outside the 0.5% reconciliation tolerance is refused.
        return (
            "not run: the scenario derives capex from its breakdown "
            "(capex.derive_from_breakdown is true), and the contingency search moves "
            "capex.usd_total, which the engine then refuses as a breakdown mismatch"
        )
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
        constraints=[c.constraint for c in held],
        contingency_bounds=settings.contingency_bounds,
        n_steps=settings.contingency_steps,
    )
    keys = _display_keys(held, not_screened)
    rows = [
        _candidate(
            p,
            f"{p.value[0]:.1%} (capex ${base * (1 + p.value[0]) / 1e6:,.1f}M)",
            best=False,
            not_screened=not_screened,
            # The search sets capex.usd_total = base * (1 + f); read the shown KPIs back
            # at the same point.
            shown=_shown_values(
                evaluate,
                config_path,
                {"capex.usd_total": base * (1 + float(p.value[0]))},
                keys,
            ),
        )
        for p in result.curve
    ]
    feasible_fracs = [float(p.value[0]) for p in result.curve if p.feasible]
    # Return-maximising is always the smallest contingency, so no candidate is named. The
    # note says what the search shows: how the debt and the covenants respond to an
    # overrun (#1859 domain D-1 b).
    top = settings.contingency_bounds[1]
    clears_to = max(feasible_fracs) if feasible_fracs else None
    debts = [_number(r.constraints.get("max_debt_usd")) for r in rows]
    finite_debts = [d for d in debts if d is not None]
    parts: List[str] = [f"The scenario carries {line / base:.1%}."]
    if finite_debts and rows:
        lo_capex = base * (1 + float(result.curve[0].value[0]))
        hi_capex = base * (1 + float(result.curve[-1].value[0]))
        parts.append(
            f"Across capex ${lo_capex / 1e6:,.1f}M to ${hi_capex / 1e6:,.1f}M the sized "
            f"debt stays between ${min(finite_debts) / 1e6:,.2f}M and "
            f"${max(finite_debts) / 1e6:,.2f}M: the debt is re-sized at each point, so "
            "equity absorbs the overrun."
        )
    if clears_to is not None:
        parts.append(
            f"Every held covenant clears up to {clears_to:.1%} contingency"
            + (
                ", the top of the searched range."
                if math.isclose(clears_to, top)
                else "; above that a covenant fails."
            )
        )
    note = " ".join(parts)
    return CapitalStructureSearch(
        kind="Capex contingency",
        searched=(
            f"{settings.contingency_bounds[0]:.0%}-{top:.0%} on a base of "
            f"${base / 1e6:,.1f}M (capex.usd_total less capex.breakdown.contingency_usd), "
            f"{settings.contingency_steps} steps"
        ),
        current=f"{line / base:.1%} (${line / 1e6:,.2f}M)",
        best_label=None,
        best_objective=None,
        candidates=rows,
        n_evaluated=len(rows),
        n_feasible=len(feasible_fracs),
        infeasibility=[] if result.feasible else _infeasibility_lines(result),
        note=note,
    )


def _financed_capex(scenario: Mapping[str, Any]) -> Optional[float]:
    """The capex the gearing ceiling is applied to: the financed total the engine sizes on.

    ``Financing_Terms.debt_ratio`` caps debt at a share of the financed capex, which is
    ``capex.usd_total`` escalated by a declared ``capex.price_basis`` (#1569) plus any
    capitalised import levies (#738). Dividing by the stated ``capex.usd_total`` instead
    made a binding ceiling read as breached (30% showing 31.5% under a 5% escalation).
    """
    from analytics.evaluation_v14 import evaluated_scenario_config
    from finance.debt_v14 import _extract_capex_usd

    return _number(_extract_capex_usd(evaluated_scenario_config(scenario)))


def _gearing_search(
    config_path: str,
    scenario: Mapping[str, Any],
    held: Sequence[_Covenant],
    not_screened: Sequence[_Covenant],
    settings: CapitalStructureSettings,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> Union[CapitalStructureSearch, str]:
    from analytics.capital_structure_optimizer_v14 import _apply_constraints
    from analytics.optimization_v14 import optimize_parameter

    capex = scenario.get("capex")
    stated = _number(capex.get("usd_total")) if isinstance(capex, Mapping) else None
    terms = scenario.get("Financing_Terms")
    current = _number(terms.get("debt_ratio")) if isinstance(terms, Mapping) else None
    if stated is None or stated <= 0:
        return "not run: the scenario declares no positive capex.usd_total"
    total = _financed_capex(scenario)
    if total is None or total <= 0:
        return "not run: the scenario's financed capex is not positive"
    if current is None:
        return "not run: the scenario declares no Financing_Terms.debt_ratio"
    constraints = [c.constraint for c in held]
    keys = _display_keys(held, not_screened)
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
        for k in keys:
            v = _number(kpis.get(k))
            if v is not None:
                values.setdefault(k, v)
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
                also_clears=_also_clears(values, not_screened),
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
        if first_top == result.curve[-1].value:
            # #1859 domain D-5: realised gearing still rises at the top of the range.
            note = (
                "The gearing ceiling binds throughout the searched range: realised "
                f"gearing rises with it, to {top:.1%} at the top."
            )
        else:
            note = (
                f"Realised gearing tops out at {top:.1%}: from a {first_top:.0%} ceiling "
                "up, the debt is sized by the DSCR sculpt, not the ceiling, and every "
                "point raises the same debt."
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
            f"{settings.gearing_bounds[1]:.0%}, {settings.gearing_steps} steps; "
            f"realised gearing is the sized debt over the financed capex "
            f"${total / 1e6:,.1f}M, the base the ceiling applies to"
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
            + "; ".join(_not_screened_text(c, base) for c in not_screened)
            + "), so there is no covenant set to rank within"
        )
    searches: List[CapitalStructureSearch] = []
    not_run: List[str] = []
    builders: Tuple[Tuple[str, Callable[[], Any]], ...] = (
        (
            "Debt tranche mix",
            lambda: _mix_search(path, scenario, held, not_screened, settings, evaluate),
        ),
        (
            "Capex contingency",
            lambda: _contingency_search(
                path, scenario, held, not_screened, settings, evaluate
            ),
        ),
        (
            "Gearing ceiling",
            lambda: _gearing_search(
                path, scenario, held, not_screened, settings, evaluate
            ),
        ),
    )
    for kind, build in builders:
        try:
            built = build()
        except Exception as exc:  # noqa: BLE001 - one search must not sink the others
            built = f"not run: the search raised {type(exc).__name__}: {exc}"
        if isinstance(built, str):
            not_run.append(f"{kind}: {built}")
        else:
            searches.append(built)
    held_keys: List[str] = []
    for cov in held:
        if cov.constraint.key not in held_keys:
            held_keys.append(cov.constraint.key)
    shown_keys = _display_keys(held, not_screened)
    return CapitalStructureBlock(
        objective_key=OBJECTIVE_KEY,
        committed_objective=_number(base.get(OBJECTIVE_KEY)),
        committed_dscr=_number(base.get(_DSCR_KEY)),
        committed_headline_dscr=_number(base.get("min_dscr")),
        covenants=[_covenant_text(c) for c in held],
        covenant_keys=held_keys,
        shown_keys=shown_keys,
        covenants_not_screened=[_not_screened_text(c, base) for c in not_screened],
        dscr_held_note=_dscr_held_note(scenario, held, searches),
        searches=searches,
        searches_not_run=not_run,
    )


def _dscr_held_note(
    scenario: Mapping[str, Any],
    held: Sequence[_Covenant],
    searches: Sequence[CapitalStructureSearch],
) -> Optional[str]:
    """Say so when the screened DSCR is held by construction (#1859 domain D-1 a).

    Under sculpted sizing the debt is re-sized to the DSCR target at every point, so the
    per-period floor is the same on every candidate and the DSCR screen cannot fail. The
    note is data-driven: it is written only when every candidate reads back the same value.
    """
    if not any(c.constraint.key == _DSCR_KEY for c in held):
        return None
    values = [
        _number(c.constraints.get(_DSCR_KEY)) for s in searches for c in s.candidates
    ]
    finite = [v for v in values if v is not None]
    if len(finite) < 2 or len(finite) != len(values):
        return None
    if max(finite) - min(finite) > 1e-6:
        return None
    terms = scenario.get("Financing_Terms")
    sizing = terms.get("debt_sizing") if isinstance(terms, Mapping) else None
    how = f" (Financing_Terms.debt_sizing: {sizing})" if sizing else ""
    return (
        f"The minimum period DSCR is {finite[0]:.2f} on every candidate: the debt is "
        f"re-sized to the DSCR target at each point{how}, so the DSCR screen cannot fail "
        'here and "clear" on it says only that the debt was re-sized. The headline '
        "minimum DSCR (min_dscr, the report's KPI and per-year covenant table, #790) is "
        "shown beside it for each candidate."
    )
