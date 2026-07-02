"""Capital risk layer facade (#33).

Aggregates Monte-Carlo outcome distributions into one lender-grade risk view:
VaR/CVaR on equity IRR and NPV (reusing the audited
:class:`analytics.core.risk_metrics.TailRiskAnalyzer`), the min-DSCR distribution
+ covenant-breach probability, and (optionally) the AEP exceedance downside
(P50/P90/P99).

Source-agnostic: feed :func:`compute_capital_risk_layer` samples from any Monte
Carlo — the casper engine, the #24 ``mc_aep_weibull`` AEP MC, or the
:func:`run_driver_mc` convenience here, which samples config drivers through
``evaluate_with_overrides`` (the only finance gateway it touches — CCCDIR/ARCH-04).

Note: AEP is not a config override (the pipeline reads the AEP summary file), so
AEP downside is supplied as samples (e.g. from #24), not produced by the driver MC.

Distributional tail-risk (#657): :func:`run_driver_mc` can additionally collect the
full per-trial metric arrays (``collect_trials=True``), and
:func:`build_driver_mc_tail_snapshot` wires those arrays into the distributional
VaR/CVaR + DSCR covenant-breach path in :mod:`analytics.sensitivity.tail_risk` — a
report-layer surface that the deterministic tornado cannot produce. The trial-array
metadata packaging (:func:`build_case_metadata_from_trials`) is the shared prerequisite
for the two follow-up wires (``tail_risk_report`` render, NPV-distribution PNG).

Context:
    Sprint 11 - Issue #33 (capital_risk_layer_v14 facade).
    Wave 4 - Issue #657 (distributional tail-risk, first slice).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import numpy as np

from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer, VaRCVaRResult
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.sensitivity.tail_risk import TailRiskConfig, _build_case_tail_snapshot

#: Per-trial metric keys collected when ``run_driver_mc(..., collect_trials=True)``.
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
        "prob_breach": float(np.mean(dscr < dscr_covenant)),
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


def run_driver_mc(
    config_path: str,
    *,
    drivers: Mapping[str, Mapping[str, float]],
    n_samples: int = 500,
    seed: int = 42,
    collect_trials: bool = False,
) -> Dict[str, np.ndarray]:
    """Sample config drivers and collect equity/DSCR outcomes via the gateway.

    Args:
        config_path: Path to the v14 scenario config.
        drivers: ``{dotted_param_path: {"mean": float, "std": float}}`` — each
            driver is sampled Gaussian and applied as an override per scenario.
        n_samples: Monte-Carlo sample count.
        seed: RNG seed (reproducible).
        collect_trials: When ``True``, additionally collect the full per-trial
            metric arrays named in :data:`DRIVER_MC_TRIAL_METRICS`
            (``project_irr``/``equity_irr``/``project_npv``/``equity_npv``,
            per-trial ``dscr_min``, and per-trial ``llcr``/``plcr`` scalars) for
            downstream distributional tail-risk (VaR/CVaR + covenant-breach
            probability). Default ``False`` preserves the historical three-key
            return exactly (``equity_irr``, ``equity_npv``, ``min_dscr``) — this
            is an additive, opt-in surface, no shape fork for existing callers.

    Returns:
        Dict of arrays. Always includes ``equity_irr``, ``equity_npv``, and
        ``min_dscr``. When ``collect_trials=True``, each key in
        :data:`DRIVER_MC_TRIAL_METRICS` is additionally present (the returned
        ``equity_irr``/``equity_npv`` are the same arrays; ``min_dscr`` aliases the
        collected ``dscr_min``). Each array has shape ``(n_samples,)``.

    Note:
        The RNG draw sequence is identical whether or not trials are collected —
        ``collect_trials`` only changes which pipeline outputs are recorded per
        draw, never the sampled overrides — so aggregate statistics are
        reproducible across both modes for a given seed.
    """
    # MC-5 (#473): modern isolated Generator (PCG64). rng.normal(...) below is unchanged.
    rng = np.random.default_rng(seed)
    driver_samples = {
        path: rng.normal(spec["mean"], spec["std"], n_samples)
        for path, spec in drivers.items()
    }
    irr = np.empty(n_samples, dtype=float)
    npv = np.empty(n_samples, dtype=float)
    dscr = np.empty(n_samples, dtype=float)

    # Extra per-trial buckets are populated only when requested (opt-in); the
    # scalar KPI reads below are unchanged when collect_trials is False.
    extra: Dict[str, np.ndarray] = (
        {m: np.empty(n_samples, dtype=float) for m in DRIVER_MC_TRIAL_METRICS}
        if collect_trials
        else {}
    )

    for i in range(n_samples):
        overrides = {path: float(driver_samples[path][i]) for path in drivers}
        kpis = evaluate_with_overrides(config_path, overrides=overrides)
        irr[i] = float(kpis["equity_irr"])
        npv[i] = float(kpis["equity_npv"])
        dscr[i] = float(kpis["min_dscr"])
        if collect_trials:
            # Canonical KPI names surface directly in the normalized KPI dict
            # (project_irr/npv, equity_irr/npv, min_dscr, llcr, plcr). dscr_min is
            # the per-trial minimum DSCR (== min_dscr); the per-year DSCR matrix is
            # a separate follow-up for tail_risk_report's (n_scenarios, n_years) shape.
            extra["project_irr"][i] = float(kpis["project_irr"])
            extra["equity_irr"][i] = irr[i]
            extra["project_npv"][i] = float(kpis["project_npv"])
            extra["equity_npv"][i] = npv[i]
            extra["dscr_min"][i] = dscr[i]
            extra["llcr"][i] = float(kpis["llcr"])
            extra["plcr"][i] = float(kpis["plcr"])

    result: Dict[str, np.ndarray] = {
        "equity_irr": irr,
        "equity_npv": npv,
        "min_dscr": dscr,
    }
    result.update(extra)
    return result


def run_capital_risk_layer(
    config_path: str,
    *,
    drivers: Mapping[str, Mapping[str, float]],
    n_samples: int = 500,
    seed: int = 42,
    aep_gwh_samples: Optional[Any] = None,
    confidence: float = 0.95,
    dscr_covenant: float = 1.20,
) -> CapitalRiskLayer:
    """Run a driver Monte Carlo and aggregate it into a capital-risk layer."""
    mc = run_driver_mc(config_path, drivers=drivers, n_samples=n_samples, seed=seed)
    return compute_capital_risk_layer(
        equity_irr_samples=mc["equity_irr"],
        min_dscr_samples=mc["min_dscr"],
        equity_npv_samples=mc["equity_npv"],
        aep_gwh_samples=aep_gwh_samples,
        confidence=confidence,
        dscr_covenant=dscr_covenant,
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
        trials: ``{metric_key: array-like}`` per-trial arrays, e.g. the extra
            buckets returned by ``run_driver_mc(..., collect_trials=True)``.
        label: Case label carried into the snapshot rows.

    Returns:
        A case mapping ``{"label": ..., "metadata": {"trials": {...}}}`` where each
        metric array is a plain ``list[float]`` (JSON-serializable for report
        metadata). Only the canonical metrics in :data:`DRIVER_MC_TRIAL_METRICS`
        are packaged; the driver MC's ``min_dscr`` convenience alias (identical to
        the canonical ``dscr_min``) is dropped so a metric is never double-counted.
    """
    canonical = {
        m: [float(v) for v in np.asarray(trials[m], dtype=float).reshape(-1)]
        for m in DRIVER_MC_TRIAL_METRICS
        if m in trials
    }
    return {"label": label, "metadata": {"trials": canonical}}


def build_driver_mc_tail_snapshot(
    config_path: str,
    *,
    drivers: Mapping[str, Mapping[str, float]],
    n_samples: int = 500,
    seed: int = 42,
    metric_keys: Optional[List[str]] = None,
    run_cfg: Optional[TailRiskConfig] = None,
    label: str = "driver_mc",
) -> Dict[str, Any]:
    """Run the driver MC and render a distributional tail-risk snapshot.

    This wires the previously-unconsumed distributional path
    (:func:`analytics.sensitivity.tail_risk._build_case_tail_snapshot`) onto real
    per-trial Monte-Carlo arrays: it runs :func:`run_driver_mc` with
    ``collect_trials=True``, packages the arrays via
    :func:`build_case_metadata_from_trials`, and produces per-metric VaR (P5/P10),
    CVaR / expected-shortfall, and — for DSCR-like metrics — covenant-breach
    probability. This is an additive, report-layer surface: it computes no new
    IRR/NPV (all evaluation flows through ``evaluate_with_overrides``) and does not
    touch committed-scenario KPIs.

    CESSPIT fail-loud: ``run_cfg.require_trials`` defaults to ``True``, so a metric
    with no trial array yields an explicit ``{"note": "no_trials"}`` row rather than
    a silently fabricated distributional statistic.

    Args:
        config_path: Path to the v14 scenario config.
        drivers: ``{dotted_param_path: {"mean": float, "std": float}}`` driver spec.
        n_samples: Monte-Carlo sample count.
        seed: RNG seed (reproducible).
        metric_keys: Metrics to snapshot; defaults to
            :data:`DRIVER_MC_TRIAL_METRICS`.
        run_cfg: Tail-risk config (percentiles, ``cvar_alpha``, ``dscr_floor``,
            ``require_trials``); defaults to :class:`TailRiskConfig` defaults.
        label: Case label carried into the snapshot rows.

    Returns:
        ``{"rows": [...]}`` — one row per requested metric carrying VaR/CVaR
        (and breach probability for DSCR-like metrics), as produced by
        ``_build_case_tail_snapshot``.
    """
    trials = run_driver_mc(
        config_path,
        drivers=drivers,
        n_samples=n_samples,
        seed=seed,
        collect_trials=True,
    )
    case = build_case_metadata_from_trials(trials, label=label)
    keys = (
        list(metric_keys) if metric_keys is not None else list(DRIVER_MC_TRIAL_METRICS)
    )
    return _build_case_tail_snapshot(
        case=case,
        metric_keys=keys,
        run_cfg=run_cfg if run_cfg is not None else TailRiskConfig(),
    )


__all__ = [
    "CapitalRiskLayer",
    "DRIVER_MC_TRIAL_METRICS",
    "compute_capital_risk_layer",
    "run_driver_mc",
    "run_capital_risk_layer",
    "build_case_metadata_from_trials",
    "build_driver_mc_tail_snapshot",
]
