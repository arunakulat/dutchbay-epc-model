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

Context:
    Sprint 11 - Issue #33 (capital_risk_layer_v14 facade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np

from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer, VaRCVaRResult
from analytics.evaluation_v14 import evaluate_with_overrides


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
        ValueError: If fewer than 20 samples are supplied (CVaR needs a tail).
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
) -> Dict[str, np.ndarray]:
    """Sample config drivers and collect equity/DSCR outcomes via the gateway.

    Args:
        config_path: Path to the v14 scenario config.
        drivers: ``{dotted_param_path: {"mean": float, "std": float}}`` — each
            driver is sampled Gaussian and applied as an override per scenario.
        n_samples: Monte-Carlo sample count.
        seed: RNG seed (reproducible).

    Returns:
        Dict of arrays: ``equity_irr``, ``equity_npv``, ``min_dscr``.
    """
    rng = np.random.RandomState(seed)
    driver_samples = {
        path: rng.normal(spec["mean"], spec["std"], n_samples)
        for path, spec in drivers.items()
    }
    irr = np.empty(n_samples, dtype=float)
    npv = np.empty(n_samples, dtype=float)
    dscr = np.empty(n_samples, dtype=float)
    for i in range(n_samples):
        overrides = {path: float(driver_samples[path][i]) for path in drivers}
        kpis = evaluate_with_overrides(config_path, overrides=overrides)
        irr[i] = float(kpis["equity_irr"])
        npv[i] = float(kpis["equity_npv"])
        dscr[i] = float(kpis["min_dscr"])
    return {"equity_irr": irr, "equity_npv": npv, "min_dscr": dscr}


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


__all__ = [
    "CapitalRiskLayer",
    "compute_capital_risk_layer",
    "run_driver_mc",
    "run_capital_risk_layer",
]
