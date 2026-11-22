"""Lender sensitivities for the command-line lender report (#1825 slice ii).

Four sensitivity analyses that were reachable only from their own scripts feed one opt-in
section of the command-line lender report, with a fifth behind its own flag:

* **DSCR and debt capacity**: the canonical one-at-a-time tornado
  (:func:`app.services.report_tornado.compute_report_tornado`) on the per-period minimum
  DSCR and on the sized debt. It goes through the sweep engine, whose
  :func:`~analytics.sensitivity.engine.coherent_overrides` is the coupled-input seam #1817
  settles. ``analytics/dscr_sensitivity.py`` is *not* wired: it rebuilds CFADS from its own
  proxy inputs (a fourth copy of the capacity-factor coupling, which #1825 rules out), so
  the report reaches the same question through the engine instead.
* **Cost of equity**: :func:`analytics.wacc_sensitivity.ke_band_npv` over a band of the
  build-up WACC's cost of equity.
* **FX**: :meth:`analytics.fx_sensitivity_real.FXSensitivityAnalyzer.analyze_fx_sensitivity`
  over the LKR/USD start rate, the hedge ratio and the hedge spread.
* **Pareto**: :func:`analytics.sensitivity_pareto.optimize_from_sensitivity_insights` over a
  financing grid around the scenario's own terms, on two objectives.
* **Sobol** (own flag, off by default): :func:`analytics.sensitivity.global_sa.run_sobol`
  over the scenario's ``monte_carlo.parameters`` drivers, each sample passed through the
  same coupled-input seam.

What the section is, and is not:

* A **sensitivity** of the committed case. Every point is scored by the canonical evaluation
  gateway (:func:`analytics.evaluation_v14.evaluate_with_overrides`); no finance logic is
  re-implemented, and the committed case, its figures and every KPI are unchanged. Each
  part shows the committed figure it is measured from, and a part whose own base point does
  not reproduce the committed figure says so.
* Universal: the drivers, the FX block, the WACC block and the financing terms come from the
  scenario; the bands and grids are analysis settings from the run configuration
  (``lender_report.sensitivities``). A part that lacks an input is listed with the missing
  key named, and the rest of the section still renders.
* No Monte Carlo engine runs here. Sobol samples the drivers' declared ranges with SALib and
  scores each point deterministically, so the lender Monte Carlo guards (``capital_risk_emit``)
  have nothing to guard: there is no toy fallback on this path.

GWTF:
    - FRAMEWORK-03: one seam; the report model holds the typed block, this module fills it.
    - FRAMEWORK-01: a part that cannot run gets a stated reason, never a default input.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from app.reports.report_model import (
    FxSensitivityPoint,
    FxSensitivitySweep,
    KeBandRow,
    LenderSensitivityBlock,
    LenderTornado,
    ParetoRow,
    ParetoScreen,
    SobolDriverRow,
    SobolMetric,
)

__all__ = [
    "DEFAULT_SENSITIVITY_SETTINGS",
    "LenderSensitivitySettings",
    "ParetoAxis",
    "SECTION_LENDER_SENSITIVITIES",
    "build_lender_sensitivity_section",
    "settings_from_config",
]

#: The section's name in the report's "sections not run" list.
SECTION_LENDER_SENSITIVITIES = "Lender sensitivities"

#: Tornado metrics: the per-period DSCR floor (#790) and the sized debt.
_TORNADO_METRICS: Tuple[Tuple[str, str, str], ...] = (
    ("min_dscr_period", "Minimum period DSCR", "ratio"),
    ("max_debt_usd", "Debt capacity (sized debt)", "usd"),
)


@dataclass(frozen=True)
class ParetoAxis:
    """One Pareto grid axis: a scenario key and offsets added to its committed value."""

    key: str
    offsets: Tuple[float, ...]


@dataclass(frozen=True)
class LenderSensitivitySettings:
    """Bands and grids: analysis settings, not site inputs (``lender_report.sensitivities``)."""

    enabled: bool = False
    ke_values: Tuple[float, ...] = (0.10, 0.12, 0.14, 0.16, 0.18, 0.20)
    fx_variation_pct: float = 10.0
    fx_steps: int = 5
    hedge_ratio_steps: Tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
    spread_variation_bps: float = 100.0
    spread_steps: int = 5
    pareto_objectives: Tuple[Tuple[str, str], ...] = (
        ("equity_npv", "max"),
        ("min_dscr_period", "max"),
    )
    pareto_grid: Tuple[ParetoAxis, ...] = (
        ParetoAxis("Financing_Terms.tenor_years", (-3.0, 0.0, 3.0)),
        ParetoAxis("Financing_Terms.target_dscr", (-0.1, 0.0, 0.1)),
    )
    sobol_enabled: bool = False
    sobol_n: int = 64
    sobol_metrics: Tuple[str, ...] = ("equity_npv", "max_debt_usd")


#: Off by default (#1825: each analytics section is opt-in); Sobol has its own flag.
DEFAULT_SENSITIVITY_SETTINGS = LenderSensitivitySettings()

_PREFIX = "lender_report.sensitivities"


def _floats(raw: Any, name: str, default: Tuple[float, ...]) -> Tuple[float, ...]:
    if raw is None:
        return default
    out = tuple(float(v) for v in raw)
    if not out:
        raise ValueError(f"{_PREFIX}.{name} must not be empty")
    return out


def _objectives(
    raw: Any, default: Tuple[Tuple[str, str], ...]
) -> Tuple[Tuple[str, str], ...]:
    if raw is None:
        return default
    out = []
    for item in raw:
        metric = str(item["metric"])
        direction = str(item.get("direction", "max"))
        if direction not in ("max", "min"):
            raise ValueError(
                f"{_PREFIX}.pareto.objectives: direction must be max or min, not "
                f"{direction!r}"
            )
        out.append((metric, direction))
    if len(out) < 2:
        raise ValueError(f"{_PREFIX}.pareto.objectives needs at least two objectives")
    return tuple(out)


def _grid(raw: Any, default: Tuple[ParetoAxis, ...]) -> Tuple[ParetoAxis, ...]:
    if raw is None:
        return default
    out = tuple(
        ParetoAxis(
            str(item["key"]), _floats(item.get("offsets"), "pareto.grid.offsets", ())
        )
        for item in raw
    )
    if not out:
        raise ValueError(f"{_PREFIX}.pareto.grid must not be empty")
    return out


def settings_from_config(raw: Optional[Mapping[str, Any]]) -> LenderSensitivitySettings:
    """Read ``lender_report.sensitivities`` from the run configuration.

    ``None`` or an empty block keeps every default (switched off).
    """
    if not raw:
        return DEFAULT_SENSITIVITY_SETTINGS
    d = DEFAULT_SENSITIVITY_SETTINGS
    fx = raw.get("fx") or {}
    pareto = raw.get("pareto") or {}
    sobol = raw.get("sobol") or {}
    n = int(sobol.get("n", d.sobol_n))
    if n < 1 or (n & (n - 1)) != 0:
        raise ValueError(f"{_PREFIX}.sobol.n must be a positive power of 2, not {n}")
    return LenderSensitivitySettings(
        enabled=bool(raw.get("enabled", d.enabled)),
        ke_values=_floats(raw.get("ke_values"), "ke_values", d.ke_values),
        fx_variation_pct=float(fx.get("variation_pct", d.fx_variation_pct)),
        fx_steps=int(fx.get("steps", d.fx_steps)),
        hedge_ratio_steps=_floats(
            fx.get("hedge_ratio_steps"), "fx.hedge_ratio_steps", d.hedge_ratio_steps
        ),
        spread_variation_bps=float(
            fx.get("spread_variation_bps", d.spread_variation_bps)
        ),
        spread_steps=int(fx.get("spread_steps", d.spread_steps)),
        pareto_objectives=_objectives(pareto.get("objectives"), d.pareto_objectives),
        pareto_grid=_grid(pareto.get("grid"), d.pareto_grid),
        sobol_enabled=bool(sobol.get("enabled", d.sobol_enabled)),
        sobol_n=n,
        sobol_metrics=tuple(str(m) for m in (sobol.get("metrics") or d.sobol_metrics)),
    )


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        out = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    return out if out is not None and math.isfinite(out) else None


def _get(cfg: Mapping[str, Any], dotted: str) -> Any:
    node: Any = cfg
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def _close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def _reconciles(
    label: str, part: Optional[float], committed: Optional[float]
) -> Optional[str]:
    """A line when the part's own base point does not reproduce the committed figure."""
    if _close(part, committed):
        return None
    return (
        f"Its own base point gives {label} {part!r}, not the committed {committed!r}: "
        "read the swings against that base, not against the committed case."
    )


def _raised(exc: BaseException) -> str:
    return f"not run: the part raised {type(exc).__name__}: {exc}"


def _guarded(fn: Callable[[], Any]) -> Any:
    """Run one part; an exception becomes its "not run" reason so the other parts render."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - one part's failure must not lose the rest
        return _raised(exc)


# --- DSCR and debt-capacity tornadoes ------------------------------------------------------


TornadoComputer = Callable[..., Any]
SweepRunner = Callable[..., Any]


def _default_tornado(
    scenario: Mapping[str, Any], *, metric: str
) -> Tuple[Any, Mapping[str, Any]]:
    """The report tornado on ``metric``, and the sweep's metadata (for its flat flag)."""
    from analytics.core.sensitivity_runner import run_sensitivity_analysis
    from app.services.report_tornado import compute_report_tornado

    meta: Dict[str, Any] = {}

    def _runner(path: str, *, metric: str) -> Any:
        suite = run_sensitivity_analysis(path, metric=metric)
        meta.update(getattr(suite, "metadata", None) or {})
        return suite

    return compute_report_tornado(scenario, metric=metric, runner=_runner), meta


def _tornadoes(
    scenario: Mapping[str, Any],
    base: Mapping[str, Any],
    tornado: Callable[..., Tuple[Any, Mapping[str, Any]]],
) -> Tuple[List[LenderTornado], List[str]]:
    out: List[LenderTornado] = []
    not_run: List[str] = []
    for metric, label, unit in _TORNADO_METRICS:
        try:
            block, meta = tornado(scenario, metric=metric)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - one part's failure must not lose the rest
            not_run.append(f"{label} tornado: {_raised(exc)}")
            continue
        if block is None or not block.rows:
            not_run.append(
                f"{label} tornado: not run: the sweep raised or returned no usable driver "
                "(the run log has the reason)"
            )
            continue
        flat_reason = (
            str(meta.get("flat_metric_reason") or "every driver leaves it unchanged")
            if meta.get("flat_metric")
            else None
        )
        committed = _number(base.get(metric))
        out.append(
            LenderTornado(
                metric=metric,
                label=label,
                unit=unit,
                committed=committed,
                rows=list(block.rows),
                flat_reason=flat_reason,
                reconciliation=_reconciles(
                    metric, _number(block.rows[0].base), committed
                ),
            )
        )
    return out, not_run


# --- Cost of equity band -------------------------------------------------------------------


def _ke_band(
    path: str,
    scenario: Mapping[str, Any],
    base: Mapping[str, Any],
    settings: LenderSensitivitySettings,
    ke_band: Callable[..., List[Mapping[str, Any]]],
) -> Union[Tuple[List[KeBandRow], Optional[float], Optional[str]], str]:
    wacc = scenario.get("wacc")
    if not isinstance(wacc, Mapping):
        return "not run: the scenario declares no wacc block"
    if wacc.get("mode") != "build_up" or not wacc.get("drives_discount_rate"):
        return (
            "not run: the scenario's discount rate is not the build-up WACC (wacc.mode is "
            f"{wacc.get('mode')!r}, wacc.drives_discount_rate is "
            f"{wacc.get('drives_discount_rate')!r}), so a cost-of-equity band would "
            "describe a different discount rate from the committed one"
        )
    ke_committed = _number(wacc.get("cost_of_equity"))
    if ke_committed is None:
        return "not run: the scenario declares no numeric wacc.cost_of_equity"
    values = sorted(set(settings.ke_values) | {ke_committed})
    rows = [
        KeBandRow(
            ke=float(r["ke"]),
            wacc=_number(r.get("wacc")),
            project_npv=_number(r.get("project_npv")),
            equity_npv=_number(r.get("equity_npv")),
            committed=_close(float(r["ke"]), ke_committed),
        )
        for r in ke_band(path, values)
    ]
    at_committed = next((r for r in rows if r.committed), None)
    reconciliation = (
        None
        if at_committed is None
        else _reconciles(
            "equity NPV", at_committed.equity_npv, _number(base.get("equity_npv"))
        )
    )
    return rows, ke_committed, reconciliation


# --- FX ------------------------------------------------------------------------------------


def _fx_point(p: Any, *, base: bool) -> FxSensitivityPoint:
    return FxSensitivityPoint(
        fx_rate=float(p.fx_rate),
        hedge_ratio=float(p.hedge_ratio),
        spread_bps=float(p.spread_bps),
        project_irr=_number(p.project_irr),
        equity_npv=_number(p.equity_npv),
        min_dscr=_number(p.min_dscr),
        base=base,
    )


def _fx(
    path: str,
    scenario: Mapping[str, Any],
    base: Mapping[str, Any],
    settings: LenderSensitivitySettings,
    fx_analyzer: Callable[[str], Any],
) -> Union[Tuple[List[FxSensitivitySweep], Optional[str]], str]:
    fx = scenario.get("fx")
    if not isinstance(fx, Mapping) or not fx.get("enabled", True):
        return "not run: the scenario declares no enabled fx block"
    start = _number(fx.get("start_lkr_per_usd"))
    if start is None:
        return "not run: the scenario declares no numeric fx.start_lkr_per_usd"
    result = fx_analyzer(path).analyze_fx_sensitivity(
        fx_variation_pct=settings.fx_variation_pct,
        fx_steps=settings.fx_steps,
        hedge_ratio_steps=list(settings.hedge_ratio_steps),
        spread_variation_bps=settings.spread_variation_bps,
        spread_steps=settings.spread_steps,
    )
    h0, s0 = float(result.base_hedge_ratio), float(result.base_spread_bps)
    ref_hedge = h0 if h0 > 0 else 1.0
    sweeps = [
        FxSensitivitySweep(
            kind="LKR/USD start rate",
            searched=(
                f"fx.start_lkr_per_usd {start:,.2f} ±{settings.fx_variation_pct:g}%, "
                f"{settings.fx_steps} steps; a higher rate is a weaker rupee"
            ),
            points=[
                _fx_point(p, base=_close(p.fx_rate, result.base_fx_rate))
                for p in result.fx_rate_points
            ],
        ),
        FxSensitivitySweep(
            kind="Hedge ratio",
            searched=f"fx.hedge_ratio over {len(settings.hedge_ratio_steps)} values at the scenario's spread",
            points=[
                _fx_point(p, base=_close(p.hedge_ratio, h0))
                for p in result.hedge_ratio_points
            ],
        ),
        FxSensitivitySweep(
            kind="Hedge spread",
            searched=(
                f"fx.spread_bps {s0:g} to {s0 + settings.spread_variation_bps:g} bps, "
                f"{settings.spread_steps} steps, at hedge ratio {ref_hedge:g}"
                + (
                    " (the scenario is unhedged, so the spread is read under a full "
                    "reference hedge: it costs nothing until a hedge is bought)"
                    if h0 <= 0
                    else ""
                )
            ),
            points=[
                _fx_point(p, base=h0 > 0 and _close(p.spread_bps, s0))
                for p in result.spread_points
            ],
        ),
    ]
    reconciliation = _reconciles(
        "project IRR",
        _number(result.base_project_irr),
        _number(base.get("project_irr")),
    )
    return sweeps, reconciliation


# --- Pareto --------------------------------------------------------------------------------


def _pareto(
    scenario: Mapping[str, Any],
    base: Mapping[str, Any],
    settings: LenderSensitivitySettings,
    pareto: Callable[..., Any],
) -> Union[ParetoScreen, str]:
    from analytics.sensitivity.engine import coherent_overrides
    from analytics.sensitivity_pareto import ObjectiveSpec, ParameterGridSpec

    grid = []
    for axis in settings.pareto_grid:
        committed = _number(_get(scenario, axis.key))
        if committed is None:
            return f"not run: the scenario declares no numeric {axis.key}"
        # Round away float noise (1.3 + 0.1 must equal 1.4), or a grid point that should
        # coincide with a neighbour's value can drift and change the frontier.
        values = tuple(
            sorted(
                {round(committed + off, 9) for off in axis.offsets}
                | {round(committed, 9)}
            )
        )
        for v in values:
            # The coupled-input seam (#1817) is the authority on which keys move other
            # inputs; the Pareto search applies overrides as given, so it may only sweep a
            # key the seam passes unchanged.
            if coherent_overrides(scenario, {axis.key: v}) != {axis.key: v}:
                return (
                    f"not run: {axis.key} is a coupled input (the coupled-input seam moves "
                    "other inputs with it), and the Pareto search applies each override as "
                    "given; sweep an uncoupled key instead"
                )
        grid.append(
            ParameterGridSpec(name=axis.key, override_key=axis.key, values=values)
        )
    objectives = [
        ObjectiveSpec(metric_key=m, direction=d) for m, d in settings.pareto_objectives
    ]
    result = pareto(base_config=dict(scenario), objectives=objectives, grid=grid)
    frontier = {id(p) for p in result.points_pareto}
    committed_point = {
        axis.key: _number(_get(scenario, axis.key)) for axis in settings.pareto_grid
    }
    rows = [
        ParetoRow(
            settings={k: float(v) for k, v in p.overrides.items()},
            objectives={k: float(v) for k, v in p.objectives.items()},
            frontier=id(p) in frontier,
            committed=all(
                _close(float(p.overrides.get(k, math.nan)), v)
                for k, v in committed_point.items()
            ),
        )
        for p in result.points_all
    ]
    at_committed = next((r for r in rows if r.committed), None)
    reconciliation = None
    if at_committed is not None:
        for m, _ in settings.pareto_objectives:
            line = _reconciles(m, at_committed.objectives.get(m), _number(base.get(m)))
            if line is not None:
                reconciliation = line
                break
    return ParetoScreen(
        objectives=[
            f"{m} ({'higher' if d == 'max' else 'lower'} is better)"
            for m, d in settings.pareto_objectives
        ],
        objective_keys=[m for m, _ in settings.pareto_objectives],
        axes=[axis.key for axis in settings.pareto_grid],
        rows=rows,
        n_frontier=sum(1 for r in rows if r.frontier),
        reconciliation=reconciliation,
    )


# --- Sobol ---------------------------------------------------------------------------------


def _sobol(
    path: str,
    scenario: Mapping[str, Any],
    settings: LenderSensitivitySettings,
    sobol: Callable[..., Mapping[str, Any]],
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]],
) -> Union[Tuple[List[SobolMetric], int], str]:
    from analytics.sensitivity.engine import coherent_overrides

    mc = scenario.get("monte_carlo")
    params = mc.get("parameters") if isinstance(mc, Mapping) else None
    if not params:
        return "not run: the scenario declares no monte_carlo.parameters drivers"

    def _seam(overrides: Mapping[str, float]) -> Mapping[str, Any]:
        # Every sample goes through the coupled-input seam (#1817), as the tornado does.
        return evaluate(path, coherent_overrides(scenario, dict(overrides)))

    out = sobol(
        path,
        metrics=list(settings.sobol_metrics),
        n=settings.sobol_n,
        evaluate_fn=_seam,
    )
    metrics: List[SobolMetric] = []
    per_metric = out.get("metrics")
    per_metric = per_metric if isinstance(per_metric, Mapping) else {}
    for m in settings.sobol_metrics:
        res = per_metric.get(m)
        if not isinstance(res, Mapping):
            continue
        reason = res.get("flat_metric_reason") or res.get("nan_poisoned_reason")
        raw_drivers = res.get("drivers")
        drivers: Mapping[str, Any] = (
            raw_drivers if isinstance(raw_drivers, Mapping) else {}
        )
        rows = [
            SobolDriverRow(
                driver=str(name),
                s1=_number(d.get("S1")),
                st=_number(d.get("ST")),
                st_conf=_number(d.get("ST_conf")),
                interactive=bool(d.get("interactive", False)),
            )
            for name, d in drivers.items()
        ]
        rows.sort(key=lambda r: (r.st is None, -(r.st or 0.0)))
        metrics.append(
            SobolMetric(
                metric=m,
                rows=[] if reason else rows,
                flag_reason=None if reason is None else str(reason),
            )
        )
    return metrics, int(out.get("n_runs", 0) or 0)


# --- Builder -------------------------------------------------------------------------------


def _evaluate(config_path: str, overrides: Mapping[str, Any]) -> Mapping[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides

    out = evaluate_with_overrides(config_path, overrides=dict(overrides))
    return out if isinstance(out, Mapping) else {}


def _default_ke_band(path: str, values: Sequence[float]) -> List[Mapping[str, Any]]:
    from analytics.wacc_sensitivity import ke_band_npv

    return list(ke_band_npv(path, values))


def _default_fx(path: str) -> Any:
    from analytics.fx_sensitivity_real import FXSensitivityAnalyzer

    return FXSensitivityAnalyzer(path)


def _default_pareto(**kwargs: Any) -> Any:
    from analytics.sensitivity_pareto import optimize_from_sensitivity_insights

    return optimize_from_sensitivity_insights(**kwargs)


def _default_sobol(path: str, **kwargs: Any) -> Mapping[str, Any]:
    from analytics.sensitivity.global_sa import run_sobol

    return run_sobol(path, **kwargs)


def build_lender_sensitivity_section(
    scenario_config_path: Union[str, Path],
    scenario: Mapping[str, Any],
    settings: LenderSensitivitySettings,
    *,
    evaluate: Callable[[str, Mapping[str, Any]], Mapping[str, Any]] = _evaluate,
    tornado: Callable[..., Tuple[Any, Mapping[str, Any]]] = _default_tornado,
    ke_band: Callable[..., List[Mapping[str, Any]]] = _default_ke_band,
    fx_analyzer: Callable[[str], Any] = _default_fx,
    pareto: Callable[..., Any] = _default_pareto,
    sobol: Callable[..., Mapping[str, Any]] = _default_sobol,
) -> Union[LenderSensitivityBlock, str]:
    """Build the lender sensitivities block, or say why it was not built.

    Args:
        scenario_config_path: The effective scenario the run used (each point perturbs it).
        scenario: The parsed scenario.
        settings: Bands and grids from ``lender_report.sensitivities``.
        evaluate, tornado, ke_band, fx_analyzer, pareto, sobol: Seams for tests; production
            uses the canonical gateway and the analysis modules named in the module docstring.

    Returns:
        The typed block, or a ``"not run: ..."`` reason for "Sections not run". A part that
        cannot run is listed inside the block; the section is not run only when it is
        switched off or no part runs.
    """
    if not settings.enabled:
        return (
            "not run: switched off (lender_report.sensitivities.enabled is false; the "
            "section is opt-in, #1825)"
        )
    path = str(scenario_config_path)
    base = evaluate(path, {})
    not_run: List[str] = []

    tornadoes, tornado_not_run = _tornadoes(scenario, base, tornado)
    not_run.extend(tornado_not_run)

    ke = _guarded(lambda: _ke_band(path, scenario, base, settings, ke_band))
    if isinstance(ke, str):
        not_run.append(f"Cost-of-equity band: {ke}")
        ke_rows, ke_committed, ke_reconciliation = [], None, None
    else:
        ke_rows, ke_committed, ke_reconciliation = ke

    fx = _guarded(lambda: _fx(path, scenario, base, settings, fx_analyzer))
    if isinstance(fx, str):
        not_run.append(f"FX: {fx}")
        fx_sweeps, fx_reconciliation = [], None
    else:
        fx_sweeps, fx_reconciliation = fx

    built_pareto = _guarded(lambda: _pareto(scenario, base, settings, pareto))
    pareto_block: Optional[ParetoScreen] = None
    if isinstance(built_pareto, str):
        not_run.append(f"Pareto screen: {built_pareto}")
    else:
        pareto_block = built_pareto

    sobol_metrics: List[SobolMetric] = []
    sobol_runs: Optional[int] = None
    if not settings.sobol_enabled:
        not_run.append(
            "Sobol indices: not run: switched off (lender_report.sensitivities.sobol."
            "enabled is false; Sobol has its own flag, #1825)"
        )
    else:
        built_sobol = _guarded(
            lambda: _sobol(path, scenario, settings, sobol, evaluate)
        )
        if isinstance(built_sobol, str):
            not_run.append(f"Sobol indices: {built_sobol}")
        else:
            sobol_metrics, sobol_runs = built_sobol

    if not (tornadoes or ke_rows or fx_sweeps or pareto_block or sobol_metrics):
        return "not run: no part could run (" + "; ".join(not_run) + ")"
    return LenderSensitivityBlock(
        committed_equity_npv=_number(base.get("equity_npv")),
        committed_project_irr=_number(base.get("project_irr")),
        committed_min_dscr_period=_number(base.get("min_dscr_period")),
        committed_debt_usd=_number(base.get("max_debt_usd")),
        tornadoes=tornadoes,
        ke_band=ke_rows,
        ke_committed=ke_committed,
        ke_reconciliation=ke_reconciliation,
        fx_sweeps=fx_sweeps,
        fx_reconciliation=fx_reconciliation,
        pareto=pareto_block,
        sobol=sobol_metrics,
        sobol_runs=sobol_runs,
        sobol_n=settings.sobol_n if sobol_metrics else None,
        parts_not_run=not_run,
    )
