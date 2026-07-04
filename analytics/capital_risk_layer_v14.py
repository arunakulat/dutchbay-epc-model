"""Capital risk layer facade (#33).

Aggregates Monte-Carlo outcome distributions into one lender-grade risk view:
VaR/CVaR on equity IRR and NPV (reusing the audited
:class:`analytics.core.risk_metrics.TailRiskAnalyzer`), the min-DSCR distribution
+ covenant-breach probability, and (optionally) the AEP exceedance downside
(P50/P90/P99).

Source-agnostic: feed :func:`compute_capital_risk_layer` samples from any Monte
Carlo — the canonical engine (``analytics.mc.engine``) or the #24 ``mc_aep_weibull``
AEP MC. AEP is not a config override (the pipeline reads the AEP summary file), so
AEP downside is supplied as samples, not produced by an MC here.

Distributional tail-risk (#657): the trials→surface cores are MC-source-agnostic —
the trial-array metadata packaging (:func:`build_case_metadata_from_trials`),
:func:`_tail_report_from_trials` (the full canonical
:class:`~analytics.core.risk_metrics.TailRiskReport`, wire b/#715), and
:func:`emit_npv_distribution_from_trials` (the NPV-distribution PNG, wire c/#716).
:func:`build_capital_risk_report_from_trials` assembles all three surfaces into the
unified :class:`CapitalRiskReport`, and :func:`build_capital_risk_report_from_mc_result`
feeds it from the CANONICAL :class:`~analytics.contracts_v14.MonteCarloResult`
(``analytics.mc.engine`` — LHS + Iman-Conover correlation, the real lender MC; the
opt-in production caller is :mod:`app.reports.capital_risk_emit`, #779).

History (#780): the module once carried a toy Gaussian driver-MC runner
(``run_driver_mc``, with ``run_capital_risk_layer`` /
``build_driver_mc_tail_snapshot`` / ``build_driver_mc_tail_report`` on top —
independent normals, no LHS/correlation). It was superseded end-to-end by the
canonical MC path above and retired (user-approved dead-code removal); only the
MC-source-agnostic cores remain.

Context:
    Sprint 11 - Issue #33 (capital_risk_layer_v14 facade).
    Wave 4 - Issue #657 (distributional tail-risk); #780 (toy runner retired).
"""

from __future__ import annotations

from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from analytics.core.covenant_breach import prob_breach
from analytics.core.risk_metrics import (
    RiskConfig,
    TailRiskAnalyzer,
    TailRiskReport,
    VaRCVaRResult,
)
from analytics.sensitivity.tail_risk import TailRiskConfig, _build_case_tail_snapshot

#: Canonical per-trial metric keys for the distributional tail-risk surfaces.
#: These follow the canonical KPI naming used by ``analytics.mc.aggregate`` and the
#: distributional tail-risk reader ``analytics.sensitivity.tail_risk`` (so downstream
#: consumers read the same buckets): ``dscr_min`` (per-trial minimum DSCR, not the
#: per-year series), ``project_irr``/``equity_irr``/``project_npv``/``equity_npv``, and
#: ``llcr``/``plcr`` (per-trial scalars — finance/debt_v14 computes coverage ratios as
#: scenario scalars, so one value per trial is the correct per-trial shape).
DRIVER_MC_TRIAL_METRICS: tuple[str, ...] = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "equity_npv",
    "dscr_min",
    "llcr",
    "plcr",
)

#: The NPV buckets a capital-risk report can plot. Single source for the ``npv_metric`` guard here
#: and for any caller that wants to fail fast before running a bounded MC (e.g.
#: :func:`app.reports.capital_risk_emit.build_capital_risk_report_for_scenario`).
NPV_METRICS: tuple[str, ...] = ("equity_npv", "project_npv")


@dataclass(frozen=True)
class CapitalRiskLayer:
    """Unified capital-risk view aggregated from MC outcome distributions."""

    n_samples: int
    confidence: float
    equity_irr_var_cvar: VaRCVaRResult
    equity_npv_var_cvar: Optional[VaRCVaRResult]
    dscr: Dict[str, float]  # min, p5, p50, prob_breach
    aep: Optional[Dict[str, float]]  # p50, p90, p99 (exceedance)


def _analyzer(
    confidence: float, dscr_covenant: float, target_return: float
) -> TailRiskAnalyzer:
    config = RiskConfig(
        confidence_level=confidence,
        target_return=target_return,
        min_dscr=dscr_covenant,
        min_llcr=1.0,
        min_plcr=1.0,
    )
    return TailRiskAnalyzer(config)


def compute_capital_risk_layer(
    *,
    equity_irr_samples: Any,
    min_dscr_samples: Any,
    equity_npv_samples: Optional[Any] = None,
    aep_gwh_samples: Optional[Any] = None,
    confidence: float = 0.95,
    dscr_covenant: float = 1.20,
    target_return: float = 0.0,
) -> CapitalRiskLayer:
    """Aggregate outcome samples into a :class:`CapitalRiskLayer`.

    CVaR throughout this layer is the Expected Shortfall (ES) — the same statistic
    under its other standard name (labelled ``CVaR/ES(..%)`` by the underlying
    :class:`analytics.core.risk_metrics.TailRiskAnalyzer`).

    Small-sample caveat: CVaR/ES is a tail mean estimated from only the
    ``(1 - confidence) * n`` worst samples — at n=1000 a 99% ES averages ~10 raw
    samples and a 95% ES ~50, which is noisy for a covenant or pricing input. ES
    converges slower than the mean, so a tight mean confidence interval from the
    post-hoc convergence diagnostic (``analytics.mc.convergence``, #643) does not
    certify the tail. The sample floor enforced below is a degeneracy guard (the
    tail must hold at least one sample), NOT a sufficiency certificate — size the
    Monte Carlo so the tail itself carries enough samples for the use at hand.

    Args:
        equity_irr_samples: Array of equity IRR outcomes (decimal).
        min_dscr_samples: Array of per-scenario minimum DSCR outcomes.
        equity_npv_samples: Optional array of equity NPV outcomes.
        aep_gwh_samples: Optional array of net AEP outcomes (GWh) for the
            exceedance downside (e.g. from #24 ``mc_aep_weibull``).
        confidence: VaR/CVaR confidence level (e.g. 0.95).
        dscr_covenant: DSCR covenant floor for the breach probability.
        target_return: Downside-risk target threshold (decimal).

    Returns:
        The aggregated :class:`CapitalRiskLayer`.

    Raises:
        ValueError: If fewer than max(20, 1/(1-confidence)) samples are supplied
            (the CVaR/ES tail needs at least one sample; this floor is a
            degeneracy guard, not statistical sufficiency).
    """
    irr = np.asarray(equity_irr_samples, dtype=float)
    dscr = np.asarray(min_dscr_samples, dtype=float)
    min_needed = int(1.0 / (1.0 - confidence)) if confidence < 1.0 else 20
    if irr.size < max(20, min_needed) or dscr.size < max(20, min_needed):
        raise ValueError(
            f"Need >= {max(20, min_needed)} samples for a stable {confidence:.0%} "
            f"VaR/CVaR tail; got irr={irr.size}, dscr={dscr.size}"
        )

    analyzer = _analyzer(confidence, dscr_covenant, target_return)
    irr_vc = analyzer.calculate_var_cvar(irr, return_type="equity_irr")

    npv_vc: Optional[VaRCVaRResult] = None
    if equity_npv_samples is not None:
        npv = np.asarray(equity_npv_samples, dtype=float)
        npv_vc = analyzer.calculate_var_cvar(npv, return_type="equity_npv")

    dscr_block = {
        "min": float(dscr.min()),
        "p5": float(np.percentile(dscr, 5)),
        "p50": float(np.percentile(dscr, 50)),
        # Noise-tolerant so a covenant == dual-DSCR-sculpt-floor case is not
        # reported as a spurious ~85-93% breach (#725; true value 0.0).
        "prob_breach": prob_breach(dscr, dscr_covenant),
    }

    aep_block: Optional[Dict[str, float]] = None
    if aep_gwh_samples is not None:
        aep = np.asarray(aep_gwh_samples, dtype=float)
        aep_block = {
            "p50": float(np.percentile(aep, 50)),
            "p90": float(np.percentile(aep, 10)),  # exceedance: P90 = 10th pct
            "p99": float(np.percentile(aep, 1)),
        }

    return CapitalRiskLayer(
        n_samples=int(irr.size),
        confidence=confidence,
        equity_irr_var_cvar=irr_vc,
        equity_npv_var_cvar=npv_vc,
        dscr=dscr_block,
        aep=aep_block,
    )


def build_case_metadata_from_trials(
    trials: Mapping[str, Any],
    *,
    label: str = "driver_mc",
) -> Dict[str, Any]:
    """Package per-trial metric arrays into the tail-risk ``trials`` case shape.

    This is the metadata-plumbing bridge the distributional tail-risk readers in
    :mod:`analytics.sensitivity.tail_risk` expect: those helpers read per-case
    Monte-Carlo arrays out of ``case["metadata"]["trials"][metric_key]`` (see
    :func:`analytics.sensitivity.tail_risk._extract_trials_from_case`). Building the
    bucket here — rather than at each call site — keeps a single canonical shape so
    the three distributional consumers (VaR/CVaR snapshot, ``tail_risk_report``,
    NPV-distribution PNG) attach to the exact same arrays without a shape fork.

    Args:
        trials: ``{metric_key: array-like}`` per-trial arrays, e.g.
            ``MonteCarloResult.trials`` from the canonical engine.
        label: Case label carried into the snapshot rows.

    Returns:
        A case mapping ``{"label": ..., "metadata": {"trials": {...}}}`` where each
        metric array is a plain ``list[float]`` (JSON-serializable for report
        metadata). Only the canonical metrics in :data:`DRIVER_MC_TRIAL_METRICS`
        are packaged; a legacy ``min_dscr`` convenience alias (identical to the
        canonical ``dscr_min``) is dropped so a metric is never double-counted.
    """
    canonical = {
        m: [float(v) for v in np.asarray(trials[m], dtype=float).reshape(-1)]
        for m in DRIVER_MC_TRIAL_METRICS
        if m in trials
    }
    return {"label": label, "metadata": {"trials": canonical}}


def _risk_config_from_scenario(config_path: str) -> RiskConfig:
    """Build a :class:`RiskConfig` from a scenario config (config-first, CESSPIT).

    Mirrors :func:`analytics.pipeline_analytics_v14._calculate_risk_analysis` exactly:
    ``confidence_level`` from ``risk.confidence_level`` (default 0.95), ``target_return``
    from ``returns.equity_discount_rate`` (default 0.0), ``min_dscr`` from
    ``constraints.min_dscr_covenant`` (default 1.0), and ``min_{llcr,plcr}`` from
    ``constraints.min_{llcr,plcr}_covenant`` when the scenario declares them, else the
    NON-BINDING coverage-of-one floor (1.0, as in :func:`_analyzer`).

    Note (the #715 review lesson): LLCR/PLCR do NOT fall back to the DSCR covenant. The
    deterministic risk block (:func:`analytics.pipeline_analytics_v14._calculate_risk_analysis`)
    borrows the DSCR floor for its LLCR/PLCR fields, but it never calls
    ``covenant_breach_probability`` — those fields are inert there. This function is the FIRST
    consumer that actually breaches LLCR/PLCR against their floor, so borrowing the (typically
    higher) DSCR covenant would FABRICATE a lender covenant-breach against a floor the scenario
    never declared. A scenario wanting a real LLCR/PLCR covenant declares it (or passes an
    explicit ``risk_config``); an undeclared covenant flags only genuine sub-1.0 coverage.
    """
    from analytics.scenario_loader import (  # local: avoid import cycle
        load_scenario_config,
    )

    cfg = load_scenario_config(config_path)
    constraints = cfg.get("constraints", {})
    dscr_cov = float(constraints.get("min_dscr_covenant", 1.0))
    return RiskConfig(
        confidence_level=float(cfg.get("risk", {}).get("confidence_level", 0.95)),
        target_return=float(cfg.get("returns", {}).get("equity_discount_rate", 0.0)),
        min_dscr=dscr_cov,
        min_llcr=float(constraints.get("min_llcr_covenant", 1.0)),
        min_plcr=float(constraints.get("min_plcr_covenant", 1.0)),
    )


def _tail_report_from_trials(
    trials: Mapping[str, np.ndarray], risk_config: RiskConfig
) -> TailRiskReport:
    """Render a :class:`TailRiskReport` from already-collected per-trial arrays.

    The shared MC-source-agnostic trials→report core. Shape bridge (the #657 slice-2
    design): ``tail_risk_report`` takes the four return metrics as 1-D MC distributions
    and the three covenant metrics as ``(n_scenarios, n_years)`` time series over which
    ``covenant_breach_probability`` takes a per-scenario minimum (``np.min(..., axis=1)``).
    Per-trial covenants arrive as SCALARS (``dscr_min``/``llcr``/``plcr``), so each is
    reshaped to ``(n_trials, 1)`` — a faithful, not lossy, adaptation: ``dscr_min`` is
    already the per-trial minimum DSCR (exactly what the axis-1 min of the per-year
    series would return), and ``llcr``/``plcr`` are loan-/project-life scenario scalars
    with no per-year series, so the axis-1 min is a no-op for all three.
    """
    analyzer = TailRiskAnalyzer(config=risk_config)

    def _covenant_column(key: str) -> np.ndarray:
        # per-trial scalar (n_trials,) -> (n_trials, 1); axis-1 min is then a no-op.
        return np.asarray(trials[key], dtype=float).reshape(-1, 1)

    return analyzer.tail_risk_report(
        equity_irr=np.asarray(trials["equity_irr"], dtype=float),
        project_irr=np.asarray(trials["project_irr"], dtype=float),
        equity_npv=np.asarray(trials["equity_npv"], dtype=float),
        project_npv=np.asarray(trials["project_npv"], dtype=float),
        dscr_results=_covenant_column("dscr_min"),
        llcr_results=_covenant_column("llcr"),
        plcr_results=_covenant_column("plcr"),
    )


def _npv_distribution_png_from_trials(
    trials: Mapping[str, np.ndarray],
    output_path: "PathLike[Any] | str",
    *,
    npv_metric: str = "equity_npv",
    title: Optional[str] = None,
    bins: int = 20,
) -> Path:
    """Emit the NPV-distribution histogram PNG from a collected per-trial NPV array (#716).

    Uses :meth:`analytics.export_helpers.ChartGenerator.plot_npv_distribution`, which carries
    the CASPER call-time matplotlib guard: when matplotlib is absent ``_get_plt()`` returns
    ``None`` and the resolved path is returned WITHOUT writing (no import-time failure), so
    this degrades gracefully. ``title`` carries the MRM-02 scenario/version annotation.
    """
    from analytics.export_helpers import (  # local: optional matplotlib dep
        ChartGenerator,
    )

    if npv_metric not in NPV_METRICS:
        raise ValueError(f"npv_metric must be one of {NPV_METRICS}; got {npv_metric!r}")
    out = Path(output_path)
    values = np.asarray(trials[npv_metric], dtype=float)
    finite = values[np.isfinite(values)]
    generator = ChartGenerator(out.parent)
    if finite.size == 0:
        # No finite NPVs to plot — return the resolved path WITHOUT writing a blank
        # histogram (same graceful-degradation contract as the matplotlib-absent path).
        return generator._resolve_path(out.name)
    return generator.plot_npv_distribution(
        finite.tolist(),
        out.name,
        bins=bins,
        title=title if title is not None else f"NPV distribution ({npv_metric})",
    )


def emit_npv_distribution_from_trials(
    trials: Mapping[str, Any],
    output_path: PathLike[Any] | str,
    *,
    npv_metric: str = "equity_npv",
    title: Optional[str] = None,
    bins: int = 20,
) -> Path:
    """Emit the NPV-distribution PNG from a collected per-trial NPV array (#657 wire c / #716).

    The public, MC-source-agnostic NPV-distribution emitter: it plots ``trials[npv_metric]``
    (``equity_npv`` or ``project_npv``) regardless of which Monte-Carlo produced the arrays —
    the canonical :class:`~analytics.contracts_v14.MonteCarloResult` (LHS + correlation) or any
    other. matplotlib absence degrades gracefully (path returned, nothing written).
    """
    return _npv_distribution_png_from_trials(
        trials, output_path, npv_metric=npv_metric, title=title, bins=bins
    )


#: Minimum trial count for a stable VaR/CVaR tail — matches the degeneracy floor in
#: :func:`compute_capital_risk_layer`. Below this the tail is a single-sample coin-flip and
#: ``calculate_var_cvar`` would index past the array end; fail loud instead.
_MIN_TRIALS = 20

#: The per-trial metric keys :func:`build_capital_risk_report_from_trials` requires.
_REQUIRED_TRIAL_KEYS: tuple[str, ...] = (
    "equity_irr",
    "project_irr",
    "equity_npv",
    "project_npv",
    "dscr_min",
    "llcr",
    "plcr",
)


@dataclass(frozen=True)
class CapitalRiskReport:
    """The unified capital-risk output (#657): the three distributional surfaces from ONE MC.

    Assembled by :func:`build_capital_risk_report_from_trials` (and its
    :func:`build_capital_risk_report_from_mc_result` convenience) so a lender-facing consumer
    reads one object: the per-metric distributional ``snapshot`` (VaR/CVaR + DSCR
    covenant-breach, slice 1), the full ``tail_report`` (:class:`TailRiskReport`, slice 2 /
    #715), and the ``npv_distribution_png`` path (slice 3 / #716). ``scenario`` /
    ``model_version`` carry the MRM-02 provenance; ``n_trials`` records the MC size.

    Source-agnostic: fed from the per-trial arrays of ANY Monte-Carlo — the canonical
    :class:`~analytics.contracts_v14.MonteCarloResult` (LHS + Iman-Conover correlation, the
    real lender MC) is the intended production source.
    """

    snapshot: Dict[str, Any]
    tail_report: TailRiskReport
    npv_distribution_png: Path
    n_trials: int
    npv_metric: str
    scenario: str
    model_version: str
    #: The MC method provenance (MRM-02), e.g. "lhs sampling, rank correlation" for the
    #: canonical engine — carried so a lender-facing renderer states the ACTUAL method
    #: rather than assuming one (source-agnostic report).
    method: str = "monte_carlo"


def build_capital_risk_report_from_trials(
    trials: Mapping[str, Any],
    output_dir: PathLike[Any] | str,
    *,
    risk_config: RiskConfig,
    scenario: str,
    model_version: Optional[str] = None,
    npv_metric: str = "equity_npv",
    metric_keys: Optional[List[str]] = None,
    run_cfg: Optional[TailRiskConfig] = None,
    method: str = "monte_carlo",
) -> CapitalRiskReport:
    """Assemble the unified :class:`CapitalRiskReport` from collected per-trial arrays (#657).

    MC-source-agnostic: derives all three distributional surfaces from ONE set of trial
    arrays — the snapshot (:func:`analytics.sensitivity.tail_risk._build_case_tail_snapshot`),
    the full :class:`TailRiskReport` (:func:`_tail_report_from_trials`), and the
    NPV-distribution PNG (:func:`emit_npv_distribution_from_trials`). The intended production
    source is the canonical :class:`~analytics.contracts_v14.MonteCarloResult` (LHS +
    Iman-Conover correlation) via :func:`build_capital_risk_report_from_mc_result`.

    ``trials`` must carry the seven canonical per-trial metric keys
    (:data:`_REQUIRED_TRIAL_KEYS`); a missing key fails loud. Computes no new IRR/NPV (the MC
    already produced the trials) and touches no committed KPI. matplotlib absence degrades
    gracefully (the PNG path is returned without writing).

    Args:
        trials: ``{metric_key: per-trial array}`` (e.g. ``MonteCarloResult.trials``).
        output_dir: Directory for the NPV-distribution PNG.
        risk_config: Covenant/target thresholds (source config-first at the call site, e.g.
            via :func:`_risk_config_from_scenario`).
        scenario: Scenario label for provenance.
        model_version: Engine version for provenance; defaults to :func:`engine_version`.
        npv_metric: Which NPV bucket to plot (``equity_npv`` or ``project_npv``).
        metric_keys: Snapshot metrics; defaults to :data:`DRIVER_MC_TRIAL_METRICS`.
        run_cfg: Tail-risk snapshot config; defaults to :class:`TailRiskConfig`.

    Returns:
        The unified :class:`CapitalRiskReport`.
    """
    from analytics.run_manifest import engine_version  # local: avoid import cycle

    missing = [k for k in _REQUIRED_TRIAL_KEYS if k not in trials]
    if missing:
        raise KeyError(
            "capital-risk report needs the canonical per-trial keys; missing: "
            f"{', '.join(missing)}"
        )
    version = model_version if model_version is not None else engine_version()
    n_trials = int(len(np.asarray(trials["equity_npv"], dtype=float).reshape(-1)))
    if n_trials < _MIN_TRIALS:
        # Fail loud rather than crash deep inside VaR/CVaR (an n=1 tail indexes past the
        # array end) or fabricate a lender number from a coin-flip tail.
        raise ValueError(
            f"capital-risk report needs >= {_MIN_TRIALS} trials for a stable VaR/CVaR "
            f"tail; got {n_trials}"
        )

    case = build_case_metadata_from_trials(trials, label=scenario)
    keys = (
        list(metric_keys) if metric_keys is not None else list(DRIVER_MC_TRIAL_METRICS)
    )
    # Snapshot DSCR floor comes from the SAME config-first covenant as the tail_report
    # (risk_config.min_dscr), so one report never shows two different DSCR floors (CESSPIT).
    snap_cfg = (
        run_cfg
        if run_cfg is not None
        else TailRiskConfig(dscr_floor=risk_config.min_dscr)
    )
    snapshot = _build_case_tail_snapshot(
        case=case,
        metric_keys=keys,
        run_cfg=snap_cfg,
    )
    tail_report = _tail_report_from_trials(trials, risk_config)
    png = emit_npv_distribution_from_trials(
        trials,
        Path(output_dir) / f"npv_distribution_{npv_metric}.png",
        npv_metric=npv_metric,
        title=f"NPV distribution ({npv_metric}) — {scenario} · v{version}",
    )

    return CapitalRiskReport(
        snapshot=snapshot,
        tail_report=tail_report,
        npv_distribution_png=png,
        n_trials=n_trials,
        npv_metric=npv_metric,
        scenario=scenario,
        model_version=version,
        method=method,
    )


def _mc_method_label(result: Any) -> str:
    """A faithful MC-method provenance string from a MonteCarloResult's metadata (MRM-02).

    Reads ``metadata['sampler']`` and ``metadata['correlation_enabled']`` so the report states
    the ACTUAL method (e.g. ``"lhs sampling, rank correlation"``) rather than assuming one.
    """
    metadata = getattr(result, "metadata", None)
    if not isinstance(metadata, Mapping):
        return "monte_carlo"
    sampler = str(metadata.get("sampler", "monte_carlo"))
    label = f"{sampler} sampling"
    if bool(metadata.get("correlation_enabled", False)):
        label += ", rank correlation"
    return label


def build_capital_risk_report_from_mc_result(
    result: Any,
    output_dir: PathLike[Any] | str,
    *,
    config_path: Optional[str] = None,
    risk_config: Optional[RiskConfig] = None,
    npv_metric: str = "equity_npv",
    metric_keys: Optional[List[str]] = None,
    run_cfg: Optional[TailRiskConfig] = None,
) -> CapitalRiskReport:
    """Assemble the capital-risk report from a canonical :class:`MonteCarloResult` (#657).

    The production entry: the real lender Monte-Carlo (``analytics.mc.engine`` — LHS +
    Iman-Conover correlation, reading the scenario's ``monte_carlo.parameters``) produces a
    :class:`~analytics.contracts_v14.MonteCarloResult` whose ``.trials`` carry the seven
    canonical per-trial metric keys. This wires those into
    :func:`build_capital_risk_report_from_trials`. Covenant floors come from ``risk_config``
    if supplied, else config-first from ``config_path`` (:func:`_risk_config_from_scenario`);
    one of the two must be given.

    Fails loud on a **toy-fallback-contaminated** result. When a trial's full v14 evaluation
    raises, the engine (``monte_carlo.allow_toy_fallback: true``, the default) substitutes a
    FABRICATED toy metric that emits the same seven keys and is stored into ``.trials`` — its
    off-floor ``dscr_min`` would poison the lender covenant-breach / VaR-CVaR / NPV numbers
    with no disclosure. A lender-grade report must not be built over fabricated trials, so
    this refuses when ``metadata['toy_fallback_count'] > 0`` and directs the caller to re-run
    with ``allow_toy_fallback: false`` (the toy values cannot be surgically removed from the
    aggregated ``.trials`` arrays post-hoc).
    """
    if risk_config is None and config_path is None:
        raise ValueError(
            "build_capital_risk_report_from_mc_result needs a risk_config or a config_path "
            "to source the covenant floors (config-first)"
        )
    metadata = getattr(result, "metadata", None)
    toy = (
        int(metadata.get("toy_fallback_count", 0))
        if isinstance(metadata, Mapping)
        else 0
    )
    if toy > 0:
        raise ValueError(
            f"MonteCarloResult has {toy} toy-fallback trial(s): a full v14 evaluation failed "
            "and the engine substituted fabricated KPIs, which would poison the lender "
            "covenant-breach / VaR-CVaR / NPV numbers. Re-run the MC with "
            "monte_carlo.allow_toy_fallback: false (so a failed trial raises) before building "
            "a lender-grade capital-risk report."
        )
    rc = (
        risk_config
        if risk_config is not None
        else _risk_config_from_scenario(str(config_path))
    )
    scenario = getattr(result, "scenario_name", None) or (
        Path(config_path).stem if config_path is not None else "monte_carlo"
    )
    return build_capital_risk_report_from_trials(
        result.trials,
        output_dir,
        risk_config=rc,
        scenario=scenario,
        npv_metric=npv_metric,
        metric_keys=metric_keys,
        run_cfg=run_cfg,
        method=_mc_method_label(result),
    )


__all__ = [
    "CapitalRiskLayer",
    "CapitalRiskReport",
    "DRIVER_MC_TRIAL_METRICS",
    "NPV_METRICS",
    "compute_capital_risk_layer",
    "build_case_metadata_from_trials",
    "emit_npv_distribution_from_trials",
    "build_capital_risk_report_from_trials",
    "build_capital_risk_report_from_mc_result",
]
