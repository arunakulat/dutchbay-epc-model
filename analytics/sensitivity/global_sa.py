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

CESSPIT (#644): a PARTIALLY non-finite metric column (an engine KPI returning ``None`` on a
subset of sample rows) would silently poison SALib's estimators into all-NaN indices plus a
fabricated insertion-order ranking. :func:`_apply_finite_mask` guards all three methods:
non-finite outputs are masked out BEFORE ``analyze`` — whole Saltelli blocks for Sobol,
whole trajectories for Morris, single rows for the given-data PAWN — with a loud disclosure
(dropped count + share, in the log and in the result). Above ``_MASKED_SHARE_POISONED`` the
metric is flagged ``nan_poisoned`` (the NaN analogue of ``flat_metric``) instead of analyzed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

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

#: Tokens that mark a covenant-pinned ratio (mirrors the tornado engine's guard).
_COVENANT_METRIC_TOKENS: Tuple[str, ...] = ("dscr", "llcr", "plcr")

#: A metric output vector is treated as structurally flat (degenerate) when its range is
#: within these tolerances of zero. Variance-based indices (Sobol S1/ST) are undefined on a
#: (near-)constant output and SALib returns garbage — negative S1, ST>1 — so such a metric is
#: flagged rather than decomposed (audit D4, #575; the analogue of the tornado's flat_metric).
_FLAT_ABS_TOL: float = 1e-12
_FLAT_REL_TOL: float = 1e-6

#: NaN-poisoning guards (#644). Issue names no threshold, so these are set here and
#: documented: any drop is disclosed with a WARNING carrying the count/share; above
#: ``_MASKED_SHARE_WARN`` the warning escalates (the finite subsample is materially
#: reduced — treat rankings with caution); above ``_MASKED_SHARE_POISONED`` the metric is
#: flagged ``nan_poisoned`` with zeroed indices (the NaN analogue of ``flat_metric``)
#: instead of analyzing a residue too thin to be representative. Flag-not-raise, per the
#: issue's flat_metric-analogue prescription: one poisoned metric must not destroy the
#: other metrics' indices in the same run.
_MASKED_SHARE_WARN: float = 0.10
_MASKED_SHARE_POISONED: float = 0.50


def _pluralize_unit(unit_label: str) -> str:
    """Human plural for a sample-unit label: 'trajectory' → 'trajectories', 'row' → 'rows'.

    Underscores become spaces ('saltelli_block' → 'saltelli blocks'); a consonant-y
    ending takes '-ies' — the naive '+s' rendered 'trajectorys' in the #644 disclosures.
    """
    human = unit_label.replace("_", " ")
    if human.endswith("y") and len(human) >= 2 and human[-2] not in "aeiou":
        return human[:-1] + "ies"
    return human + "s"


def _flat_metric_reason(metric_key: str) -> str:
    """Covenant-aware explanation for a structurally-flat global-SA metric."""
    if any(tok in metric_key.lower() for tok in _COVENANT_METRIC_TOKENS):
        return (
            "covenant-pinned: debt is sized to the DSCR target, so this ratio is "
            "structurally invariant to the swept drivers — variance-based indices are "
            "undefined; sweep a covenant-relevant lever (gearing, balloon) instead"
        )
    return "the metric does not move under these sweeps; variance-based indices are undefined"


def _is_flat_output(values: Sequence[float]) -> Tuple[bool, float]:
    """Return (is_flat, range) for a metric's output vector across the SA samples.

    Flat when the finite range is within ``_FLAT_ABS_TOL`` or ``_FLAT_REL_TOL`` of the
    output scale — the covenant-pinned/near-constant case that makes Sobol/Morris return
    out-of-[0,1] indices.
    """
    arr = np.asarray(list(values), dtype=float)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return True, 0.0
    spread = float(np.ptp(finite))
    scale = max(abs(float(np.mean(finite))), 1.0)
    return spread <= max(_FLAT_ABS_TOL, _FLAT_REL_TOL * scale), spread


def _apply_finite_mask(
    method: str,
    metric: str,
    X: np.ndarray,
    Y: np.ndarray,
    *,
    block_size: int,
    unit_label: str,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """Mask sample units whose output contains any non-finite value — the shared #644 guard.

    A partially-NaN output column passes :func:`_is_flat_output` (which inspects only the
    FINITE values) and then poisons SALib's estimators into all-NaN indices plus a
    fabricated insertion-order ranking. This helper masks non-finite outputs BEFORE
    ``analyze``, respecting each estimator's sample design:

    * **Sobol / Morris** assume the structured design — Saltelli cross-sample blocks of
      ``D+2`` (or ``2D+2`` with second order) consecutive rows / one-at-a-time
      trajectories of ``D+1`` consecutive rows — so plain row masking silently corrupts
      the estimator pairing. The WHOLE sample unit (``block_size`` consecutive rows) is
      dropped when ANY of its outputs is non-finite; SALib's ``analyze`` then sees fewer
      complete units, which is estimator-valid (verified against SALib 1.5.2's block
      indexing: ``A = Y[0::step]``, ``AB_j = Y[j+1::step]``, ``B = Y[step-1::step]``).
    * **PAWN** is a given-data method, so ``block_size=1`` (row-wise masking) is valid.

    Deterministic (MRM-01): the mask is a pure function of ``Y``. Disclosure is loud
    (CESSPIT — no silent truncation): any drop logs a WARNING with the metric name and
    the dropped unit/row counts, and the returned disclosure dict is attached to the
    per-metric result. Above ``_MASKED_SHARE_POISONED`` the disclosure carries
    ``nan_poisoned=True`` and an ERROR is logged; the caller must then flag the metric
    (zeroed indices — the NaN analogue of ``flat_metric``) instead of analyzing, and the
    inputs are returned unmasked since they will not be analyzed at all.

    Returns ``(X_masked, Y_masked, disclosure)``; the inputs are returned unchanged
    (same objects, pairing untouched) when every output is finite.
    """
    n_rows = int(Y.shape[0])
    if block_size < 1 or n_rows < block_size or n_rows % block_size:
        raise ValueError(
            f"global SA ({method}) metric '{metric}': sample of {n_rows} rows is not a "
            f"whole number of {_pluralize_unit(unit_label)} of {block_size} rows — "
            "cannot mask by sample unit."
        )
    n_units = n_rows // block_size
    finite_rows = np.isfinite(Y)
    unit_keep = finite_rows.reshape(n_units, block_size).all(axis=1)
    n_units_dropped = int(n_units - int(unit_keep.sum()))
    dropped_share = n_units_dropped / n_units
    disclosure: Dict[str, Any] = {
        "unit": unit_label,
        "block_size": int(block_size),
        "n_rows": n_rows,
        "n_rows_dropped": n_units_dropped * int(block_size),
        "n_nonfinite_rows": int(np.count_nonzero(~finite_rows)),
        "n_units": n_units,
        "n_units_dropped": n_units_dropped,
        "dropped_share": float(dropped_share),
        "nan_poisoned": dropped_share > _MASKED_SHARE_POISONED,
    }
    if n_units_dropped == 0:
        return X, Y, disclosure
    human_units = _pluralize_unit(unit_label)
    if disclosure["nan_poisoned"]:
        logger.error(
            "global SA (%s) metric '%s' is NaN-POISONED: %d of %d %s (%.1f%%, %d rows) "
            "contain non-finite outputs (%d non-finite values), above the %.0f%% guard "
            "— flagging nan_poisoned and zeroing indices (the NaN analogue of "
            "flat_metric) instead of analyzing the residue.",
            method,
            metric,
            n_units_dropped,
            n_units,
            human_units,
            100.0 * dropped_share,
            disclosure["n_rows_dropped"],
            disclosure["n_nonfinite_rows"],
            100.0 * _MASKED_SHARE_POISONED,
        )
        return X, Y, disclosure
    escalation = ""
    if dropped_share > _MASKED_SHARE_WARN:
        escalation = (
            f"; the dropped share exceeds {_MASKED_SHARE_WARN:.0%} — treat the "
            "resulting indices and rankings with caution"
        )
    logger.warning(
        "global SA (%s) metric '%s': dropping %d of %d %s (%.1f%%, %d rows) containing "
        "%d non-finite outputs before analyze() — indices are computed on the finite "
        "subset only%s.",
        method,
        metric,
        n_units_dropped,
        n_units,
        human_units,
        100.0 * dropped_share,
        disclosure["n_rows_dropped"],
        disclosure["n_nonfinite_rows"],
        escalation,
    )
    row_keep = np.repeat(unit_keep, block_size)
    return X[row_keep], Y[row_keep], disclosure


def _nan_poisoned_reason(masked: Mapping[str, Any]) -> str:
    """Human-readable reason attached to a ``nan_poisoned`` metric (#644)."""
    units = _pluralize_unit(str(masked["unit"]))
    return (
        f"{masked['n_units_dropped']} of {masked['n_units']} {units} "
        f"({masked['dropped_share']:.0%}) contain non-finite outputs — above the "
        f"{_MASKED_SHARE_POISONED:.0%} guard, indices computed on the finite residue "
        "would be unrepresentative; fix the evaluator (why is this KPI None/NaN over so "
        "much of the sweep box?) or narrow the driver bounds"
    )


def _zeroed_sobol_drivers(names: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Zeroed, in-band Sobol driver entries for a flagged (flat / nan_poisoned) metric."""
    return {
        name: {
            "S1": 0.0,
            "S1_conf": 0.0,
            "ST": 0.0,
            "ST_conf": 0.0,
            "interactive": False,
        }
        for name in names
    }


def _zeroed_morris_drivers(names: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Zeroed Morris driver entries for a flagged (flat / nan_poisoned) metric."""
    return {name: {"mu_star": 0.0, "sigma": 0.0} for name in names}


def _zeroed_pawn_drivers(names: Sequence[str]) -> Dict[str, Dict[str, float]]:
    """Zeroed PAWN driver entries for a flagged (flat / nan_poisoned) metric."""
    return {name: {"median": 0.0, "mean": 0.0, "cv": 0.0} for name in names}


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

    The skip is by design, not a gap (#582). Skipped names are surfaced in
    ``GlobalSAProblem.skipped`` and logged as a warning; no committed scenario authors an
    ``fx_calibrated`` entry in ``monte_carlo.parameters`` (FX is swept via the explicit
    uniform ``fx.start_lkr_per_usd`` driver), so nothing is skipped in practice. Because
    :func:`run_morris`, :func:`run_sobol` and :func:`run_pawn` all sample the SAME problem
    built here, an ``fx_calibrated`` driver is excluded from all three methods alike. If a
    future SA run must sweep one, derive a proxy bound from the calibrated inverse-CDF —
    ``analytics.fx.fx_calibration.CalibratedFXSampler.spot_from_unit`` at the 1st/99th
    percentiles, ``[spot_from_unit(0.01), spot_from_unit(0.99)]`` — and author it as an
    explicit ``{name, low, high}`` entry. Limitation: the SA sweep is then uniform over
    that range; the two-regime mixture shape itself remains a Monte-Carlo-only feature.
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
        low_raw = p.get("low", p.get("min"))
        high_raw = p.get("high", p.get("max"))
        if low_raw is None or high_raw is None:
            raise ValueError(
                f"{name}: global SA needs both a low/min and a high/max bound to "
                f"sweep (got low={low_raw!r}, high={high_raw!r})."
            )
        low = float(low_raw)
        high = float(high_raw)
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

    Non-finite outputs (#644): whole Saltelli blocks (``D+2`` rows, ``2D+2`` with second
    order) containing any non-finite output are dropped before ``analyze`` — never single
    rows, which would corrupt the A/B/AB pairing — with a ``masked`` disclosure in the
    per-metric result; above ``_MASKED_SHARE_POISONED`` the metric is flagged
    ``nan_poisoned`` with zeroed indices (see :func:`_apply_finite_mask`). A flagged
    (``flat_metric`` / ``nan_poisoned``) metric carries ``interactions_present=None``:
    no indices were computed, so no interaction claim — definitive ``False`` would be one.

    ``n`` MUST be a positive power of 2 (default 256 = 2**8): SALib's ``sobol`` sampler
    draws a base-2 Sobol' sequence, whose balance properties (and therefore the index
    accuracy) only hold at powers of 2 — SALib itself merely warns and degrades, so we
    fail loud here instead (#586).
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1 or (n & (n - 1)) != 0:
        raise ValueError(
            f"run_sobol requires n to be a positive power of 2 (e.g. 128, 256, 512); "
            f"got {n!r}. SALib's base-2 Sobol' sequence loses its balance properties "
            f"at other sizes, silently degrading the S1/ST estimates."
        )
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
    # Saltelli sample-unit size: [A, AB_1..AB_D, B] (+ BA_1..BA_D with second order).
    block_rows = 2 * prob.num_vars + 2 if calc_second_order else prob.num_vars + 2
    per_metric: Dict[str, Any] = {}
    for m in metrics:
        is_flat, spread = _is_flat_output(cols[m])
        if is_flat:
            reason = _flat_metric_reason(m)
            logger.warning(
                "global SA metric '%s' is structurally FLAT (range=%.2e across %d runs): "
                "%s — emitting zeroed indices instead of undefined Sobol values.",
                m,
                spread,
                len(X),
                reason,
            )
            per_metric[m] = {
                "drivers": _zeroed_sobol_drivers(prob.names),
                # Indices are undefined on a flat output, so no interaction claim can
                # be made either way: None = "not computed", not a definitive False.
                "interactions_present": None,
                "flat_metric": True,
                "flat_metric_reason": reason,
                "nan_poisoned": False,
            }
            continue
        _, y_masked, masked = _apply_finite_mask(
            "sobol",
            m,
            X,
            cols[m],
            block_size=block_rows,
            unit_label="saltelli_block",
        )
        if masked["nan_poisoned"]:
            per_metric[m] = {
                "drivers": _zeroed_sobol_drivers(prob.names),
                # Nothing was analyzed, so no interaction claim can be made either
                # way: None = "not computed", not a definitive False.
                "interactions_present": None,
                "flat_metric": False,
                "nan_poisoned": True,
                "nan_poisoned_reason": _nan_poisoned_reason(masked),
                "masked": masked,
            }
            continue
        Si = sobol_analyze.analyze(
            salib_problem,
            y_masked,
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
        entry: Dict[str, Any] = {
            "drivers": drivers,
            "interactions_present": any(d["interactive"] for d in drivers.values()),
            "flat_metric": False,
            "nan_poisoned": False,
        }
        if masked["n_units_dropped"]:
            entry["masked"] = masked
        per_metric[m] = entry
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

    Non-finite outputs (#644): whole trajectories (``D+1`` consecutive rows) containing any
    non-finite output are dropped from BOTH ``X`` and ``Y`` before ``analyze`` — never
    single rows, which would corrupt the elementary-effect pairing — with a ``masked``
    disclosure in the per-metric result; above ``_MASKED_SHARE_POISONED`` the metric is
    flagged ``nan_poisoned`` with zeroed indices (see :func:`_apply_finite_mask`).
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
        is_flat, spread = _is_flat_output(cols[m])
        if is_flat:
            reason = _flat_metric_reason(m)
            logger.warning(
                "global SA metric '%s' is structurally FLAT (range=%.2e across %d runs): "
                "%s — Morris elementary effects are all ~0.",
                m,
                spread,
                len(X),
                reason,
            )
            per_metric[m] = {
                "drivers": _zeroed_morris_drivers(prob.names),
                "ranking": list(prob.names),
                "flat_metric": True,
                "flat_metric_reason": reason,
                "nan_poisoned": False,
            }
            continue
        x_masked, y_masked, masked = _apply_finite_mask(
            "morris",
            m,
            X,
            cols[m],
            block_size=prob.num_vars + 1,
            unit_label="trajectory",
        )
        if masked["nan_poisoned"]:
            per_metric[m] = {
                "drivers": _zeroed_morris_drivers(prob.names),
                "ranking": list(prob.names),
                "flat_metric": False,
                "nan_poisoned": True,
                "nan_poisoned_reason": _nan_poisoned_reason(masked),
                "masked": masked,
            }
            continue
        Si = morris_analyze.analyze(
            salib_problem, x_masked, y_masked, print_to_console=False, seed=seed
        )
        drivers = {
            name: {"mu_star": float(Si["mu_star"][i]), "sigma": float(Si["sigma"][i])}
            for i, name in enumerate(prob.names)
        }
        ranked = sorted(drivers, key=lambda k: drivers[k]["mu_star"], reverse=True)
        entry: Dict[str, Any] = {
            "drivers": drivers,
            "ranking": ranked,
            "flat_metric": False,
            "nan_poisoned": False,
        }
        if masked["n_units_dropped"]:
            entry["masked"] = masked
        per_metric[m] = entry
    out["metrics"] = per_metric
    return out


def run_pawn(
    config_path: Optional[str] = None,
    *,
    metrics: Sequence[str] = DEFAULT_METRICS,
    n: int = 256,
    s: int = 10,
    params: Optional[Sequence[Mapping[str, Any]]] = None,
    seed: Optional[int] = 42,
    problem: Optional[GlobalSAProblem] = None,
    evaluate_fn: Optional[EvaluateFn] = None,
) -> Dict[str, Any]:
    """PAWN (moment-independent, KS-based) global SA — robust on skewed / covenant-pinned KPIs.

    PAWN (Pianosi & Wagener 2018) measures a driver's influence by the Kolmogorov-Smirnov
    distance between the unconditional output CDF and the CDFs conditioned on that driver's
    ``s`` slices — a *distribution*-based index, not a *variance*-based one. Unlike Sobol it
    stays bounded in [0,1] and does not misbehave on bimodal / DSCR-floor-pinned outputs, which
    is exactly the DutchBay case, so it is the right complement to the variance-based tornado /
    Sobol. It is a GIVEN-DATA method (``SALib.analyze.pawn``): here it is driven by its own LHS
    sample (``n`` rows), but the same (X, Y) could be reused from any prior sweep. Reports the
    **median** KS statistic per driver (with mean / CV of the KS across slices).

    A structurally-flat metric (a covenant-pinned ``min_dscr`` carrying only FP jitter) yields
    SPURIOUS non-zero PAWN indices — verified empirically — so the same ``_is_flat_output`` /
    ``_flat_metric_reason`` guard the Sobol path uses is applied here, flagging and zeroing rather
    than reporting noise. Note a finite-sample noise floor: at the defaults (``n=256``, ``s=10``)
    an inert driver still measures a median KS of ~0.15, so low-end ranking positions are not
    evidence of influence (the floor roughly halves as ``n`` doubles). ``problem``/``evaluate_fn``
    override the config-derived defaults (used by closed-form tests).

    Non-finite outputs (#644): PAWN is given-data, so rows with a non-finite output are
    masked from BOTH ``X`` and ``Y`` row-wise (estimator-valid, unlike Sobol/Morris) with a
    ``masked`` disclosure in the per-metric result; above ``_MASKED_SHARE_POISONED`` the
    metric is flagged ``nan_poisoned`` with zeroed KS (see :func:`_apply_finite_mask`).
    """
    _require_salib()
    from SALib.analyze import pawn as pawn_analyze
    from SALib.sample import latin as latin_sample

    prob, evfn = _resolve(config_path, params, problem, evaluate_fn)
    salib_problem = prob.as_salib()
    X = latin_sample.sample(salib_problem, n, seed=seed)
    cols = _evaluate_rows(evfn, prob, X, metrics)

    out: Dict[str, Any] = {
        "method": "pawn",
        "n": n,
        "s": int(s),
        "n_runs": len(X),
        "problem": salib_problem,
    }
    per_metric: Dict[str, Any] = {}
    for m in metrics:
        is_flat, spread = _is_flat_output(cols[m])
        if is_flat:
            reason = _flat_metric_reason(m)
            logger.warning(
                "global SA metric '%s' is structurally FLAT (range=%.2e across %d runs): "
                "%s — PAWN indices on FP jitter are spurious; emitting zeroed KS instead.",
                m,
                spread,
                len(X),
                reason,
            )
            per_metric[m] = {
                "drivers": _zeroed_pawn_drivers(prob.names),
                "ranking": list(prob.names),
                "flat_metric": True,
                "flat_metric_reason": reason,
                "nan_poisoned": False,
            }
            continue
        x_masked, y_masked, masked = _apply_finite_mask(
            "pawn",
            m,
            X,
            np.asarray(cols[m], dtype=float),
            block_size=1,
            unit_label="row",
        )
        if masked["nan_poisoned"]:
            per_metric[m] = {
                "drivers": _zeroed_pawn_drivers(prob.names),
                "ranking": list(prob.names),
                "flat_metric": False,
                "nan_poisoned": True,
                "nan_poisoned_reason": _nan_poisoned_reason(masked),
                "masked": masked,
            }
            continue
        # PAWN is deterministic given (X, Y); ``seed`` is not passed to ``analyze`` because
        # SALib forwards it to a global ``np.random.seed`` (a process-wide RNG side effect) while
        # leaving the KS computation unchanged. The seed that matters is on ``latin.sample`` above.
        Si = pawn_analyze.analyze(
            salib_problem,
            x_masked,
            y_masked,
            S=int(s),
            print_to_console=False,
        )
        drivers = {
            name: {
                "median": float(Si["median"][i]),
                "mean": float(Si["mean"][i]),
                "cv": float(Si["CV"][i]),
            }
            for i, name in enumerate(prob.names)
        }
        ranked = sorted(drivers, key=lambda k: drivers[k]["median"], reverse=True)
        entry: Dict[str, Any] = {
            "drivers": drivers,
            "ranking": ranked,
            "flat_metric": False,
            "nan_poisoned": False,
        }
        if masked["n_units_dropped"]:
            entry["masked"] = masked
        per_metric[m] = entry
    out["metrics"] = per_metric
    return out
