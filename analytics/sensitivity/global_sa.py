"""Global (variance-based) sensitivity analysis — Morris screening + Sobol indices (SALib).

The existing tornado (:mod:`analytics.sensitivity`) is a **local, one-at-a-time** sweep:
it varies a single driver while holding the rest at base, so by construction it cannot see
**interactions** between drivers. For a flat-LKR / hard-currency-debt structure the drivers
are coupled (CF↔revenue, FX↔LKR-tariff erosion, capex↔gearing↔DSCR-sculpt), so the
defensible answer to "what actually drives outcome variance" is variance-based:

* **Sobol** first-order ``S1`` (a driver acting alone) vs total-order ``ST`` (the driver +
  all its interactions). ``ST ≫ S1`` is the diagnostic that interactions are material — the
  variance-based analogue of the one-way tornado's ``flat_metric`` flag.
* **Morris** elementary effects (``mu_star`` / ``sigma``) — the cheap *screening* pass
  (``N·(D+1)`` runs) to rank drivers before paying for Sobol (``N·(D+2)`` runs here).

This is **additive and KPI-neutral**: it reuses the SAME ``monte_carlo.parameters`` driver
list the MC engine reads (CESSPIT: config-first, no new authored constants; CCCDIR: one
contract) and evaluates each sample through the canonical
:func:`analytics.evaluation_v14.evaluate_with_overrides` gateway (ARCH-04 — the same path
``capital_risk_layer_v14`` uses). It never touches the deterministic base case; it produces
a new read-only analysis artifact only.

CASPER: SALib is an optional dependency (the ``[dev]`` toolchain / the pinned lock carry it);
:func:`_require_salib` fails loud with an actionable message if it is absent, so the base
finance install never needs it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config

logger = logging.getLogger(__name__)

#: An evaluator maps a dotted-path override dict to a metric dict. Default = the engine
#: gateway; tests inject a closed-form function (Ishigami) to validate the pipeline.
EvaluateFn = Callable[[Mapping[str, float]], Mapping[str, Any]]

#: Default KPIs to decompose. Each must be a numeric scalar in the canonical KPI dict.
DEFAULT_METRICS: Tuple[str, ...] = ("project_irr", "equity_irr", "min_dscr")

#: ``ST - S1`` above this fraction flags a driver whose effect is materially interactive
#: (the variance-based analogue of the one-way tornado's flat-metric flag).
INTERACTION_TOL: float = 0.05


def _require_salib() -> None:
    """Fail loud (CASPER) when the optional SALib dependency is missing."""
    try:
        import SALib  # noqa: F401
    except (
        ImportError
    ) as exc:  # pragma: no cover - exercised via the importorskip-gated tests
        raise ImportError(
            "Global sensitivity analysis requires SALib. Install the dev toolchain "
            '(`pip install -e ".[dev]"`) or `pip install SALib`. It is an OPTIONAL '
            "dependency — the base finance install does not need it."
        ) from exc


@dataclass(frozen=True)
class GlobalSAProblem:
    """The SALib problem built from a scenario's ``monte_carlo.parameters``."""

    names: List[str]
    bounds: List[Tuple[float, float]]
    skipped: List[str] = field(
        default_factory=list
    )  # e.g. fx_calibrated (no clean bound)

    @property
    def num_vars(self) -> int:
        return len(self.names)

    def as_salib(self) -> Dict[str, Any]:
        return {
            "num_vars": self.num_vars,
            "names": list(self.names),
            "bounds": [list(b) for b in self.bounds],
        }


def build_problem(
    config_path: str, params: Optional[Sequence[Mapping[str, Any]]] = None
) -> GlobalSAProblem:
    """Build a SALib problem from the scenario's ``monte_carlo.parameters`` (CCCDIR: one contract).

    Reuses the engine's parameter contract — a list of ``{name, low, high[, distribution]}``
    mappings whose ``name`` is a dotted config path. ``fx_calibrated`` drivers are SKIPPED
    (their MC dimension is a unit-uniform mapped through an inverse-CDF inside the sampler, so
    they have no authored ``[low, high]`` bound to sweep via ``evaluate_with_overrides``).
    """
    if params is None:
        cfg = load_scenario_config(config_path)
        mc = cfg.get("monte_carlo") or cfg.get("Monte_Carlo") or {}
        params = mc.get("parameters")
    if not isinstance(params, (list, tuple)) or not params:
        raise ValueError(
            "Global SA needs a non-empty monte_carlo.parameters LIST of "
            "{name, low, high} mappings (the same contract the MC engine reads). "
            f"Got: {type(params).__name__}."
        )

    names: List[str] = []
    bounds: List[Tuple[float, float]] = []
    skipped: List[str] = []
    for p in params:
        if not isinstance(p, Mapping) or "name" not in p:
            raise ValueError(f"monte_carlo.parameters entry must have a 'name': {p!r}")
        name = str(p["name"])
        if str(p.get("distribution", p.get("kind", "uniform"))) == "fx_calibrated":
            skipped.append(name)
            continue
        low = float(p.get("low", p.get("min")))
        high = float(p.get("high", p.get("max")))
        if not high > low:
            raise ValueError(f"{name}: global SA needs high > low, got [{low}, {high}]")
        names.append(name)
        bounds.append((low, high))

    if len(names) < 2:
        raise ValueError(
            f"Global SA needs >=2 sweepable drivers (got {len(names)}); "
            f"skipped (fx_calibrated): {skipped}."
        )
    if skipped:
        logger.warning(
            "Global SA skipping fx_calibrated drivers (no authored bound): %s", skipped
        )
    return GlobalSAProblem(names=names, bounds=bounds, skipped=skipped)


def _engine_evaluate_fn(config_path: str) -> EvaluateFn:
    """The default evaluator: the canonical ARCH-04 gateway, keyed by dotted-path overrides."""

    def _fn(overrides: Mapping[str, float]) -> Mapping[str, Any]:
        return evaluate_with_overrides(config_path, overrides=dict(overrides))

    return _fn


def _resolve(
    config_path: Optional[str],
    params: Optional[Sequence[Mapping[str, Any]]],
    problem: Optional[GlobalSAProblem],
    evaluate_fn: Optional[EvaluateFn],
) -> Tuple[GlobalSAProblem, EvaluateFn]:
    """Resolve the (problem, evaluator) pair — from explicit args, else from config_path."""
    if problem is None:
        if config_path is None:
            raise ValueError("Provide either config_path or an explicit problem.")
        problem = build_problem(config_path, params)
    if evaluate_fn is None:
        if config_path is None:
            raise ValueError("Provide either config_path or an explicit evaluate_fn.")
        evaluate_fn = _engine_evaluate_fn(config_path)
    return problem, evaluate_fn


def _evaluate_rows(
    evaluate_fn: EvaluateFn,
    problem: GlobalSAProblem,
    samples: Any,
    metrics: Sequence[str],
) -> Dict[str, Any]:
    """Evaluate every SALib sample row ONCE and collect each metric's output vector (so the
    ``N·(D+2)`` / ``N·(D+1)`` runs are shared across metrics). ``evaluate_fn`` maps a dotted-
    path override dict to a metric dict — defaults to the engine gateway; tests inject a
    closed-form function (e.g. Ishigami) to validate the SALib pipeline in isolation.
    """
    import numpy as np

    cols: Dict[str, List[float]] = {m: [] for m in metrics}
    for row in samples:
        overrides = {name: float(val) for name, val in zip(problem.names, row)}
        kpis = evaluate_fn(overrides)
        for m in metrics:
            v = kpis.get(m)
            cols[m].append(float(v) if v is not None else float("nan"))
    return {m: np.asarray(vals, dtype=float) for m, vals in cols.items()}


def run_sobol(
    config_path: Optional[str] = None,
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
    n: int = 256,
    calc_second_order: bool = False,
    params: Optional[Sequence[Mapping[str, Any]]] = None,
    seed: Optional[int] = 42,
    problem: Optional[GlobalSAProblem] = None,
    evaluate_fn: Optional[EvaluateFn] = None,
) -> Dict[str, Any]:
    """Variance-based Sobol indices (S1 / ST) per driver per metric.

    Cost is ``n·(D+2)`` evaluations (``calc_second_order=False``). Returns a dict keyed by
    metric → {driver → {S1, S1_conf, ST, ST_conf, interactive}}, plus ``problem`` metadata.
    ``problem``/``evaluate_fn`` override the config-derived defaults (used by closed-form tests).
    """
    _require_salib()
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample

    prob, evfn = _resolve(config_path, params, problem, evaluate_fn)
    salib_problem = prob.as_salib()
    X = sobol_sample.sample(
        salib_problem, n, calc_second_order=calc_second_order, seed=seed
    )
    cols = _evaluate_rows(evfn, prob, X, metrics)

    out: Dict[str, Any] = {
        "method": "sobol",
        "n": n,
        "n_runs": len(X),
        "problem": prob.as_salib(),
    }
    per_metric: Dict[str, Any] = {}
    for m in metrics:
        Si = sobol_analyze.analyze(
            salib_problem,
            cols[m],
            calc_second_order=calc_second_order,
            seed=seed,
            print_to_console=False,
        )
        drivers: Dict[str, Any] = {}
        for i, name in enumerate(prob.names):
            s1, st = float(Si["S1"][i]), float(Si["ST"][i])
            drivers[name] = {
                "S1": s1,
                "S1_conf": float(Si["S1_conf"][i]),
                "ST": st,
                "ST_conf": float(Si["ST_conf"][i]),
                "interactive": (st - s1) > INTERACTION_TOL,
            }
        per_metric[m] = {
            "drivers": drivers,
            "interactions_present": any(d["interactive"] for d in drivers.values()),
        }
    out["metrics"] = per_metric
    return out


def run_morris(
    config_path: Optional[str] = None,
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
    n_trajectories: int = 16,
    params: Optional[Sequence[Mapping[str, Any]]] = None,
    seed: Optional[int] = 42,
    problem: Optional[GlobalSAProblem] = None,
    evaluate_fn: Optional[EvaluateFn] = None,
) -> Dict[str, Any]:
    """Morris elementary-effects screening (mu_star / sigma) per driver per metric.

    Cheap (``n_trajectories·(D+1)`` evaluations) — use it to RANK drivers before paying for
    :func:`run_sobol`. ``mu_star`` ranks importance; high ``sigma`` flags non-linear/interactive.
    ``problem``/``evaluate_fn`` override the config-derived defaults (used by closed-form tests).
    """
    _require_salib()
    from SALib.analyze import morris as morris_analyze
    from SALib.sample import morris as morris_sample

    prob, evfn = _resolve(config_path, params, problem, evaluate_fn)
    salib_problem = prob.as_salib()
    X = morris_sample.sample(salib_problem, N=n_trajectories, seed=seed)
    cols = _evaluate_rows(evfn, prob, X, metrics)

    out: Dict[str, Any] = {
        "method": "morris",
        "n_trajectories": n_trajectories,
        "n_runs": len(X),
        "problem": salib_problem,
    }
    per_metric: Dict[str, Any] = {}
    for m in metrics:
        Si = morris_analyze.analyze(
            salib_problem, X, cols[m], print_to_console=False, seed=seed
        )
        drivers = {
            name: {"mu_star": float(Si["mu_star"][i]), "sigma": float(Si["sigma"][i])}
            for i, name in enumerate(prob.names)
        }
        ranked = sorted(drivers, key=lambda k: drivers[k]["mu_star"], reverse=True)
        per_metric[m] = {"drivers": drivers, "ranking": ranked}
    out["metrics"] = per_metric
    return out
