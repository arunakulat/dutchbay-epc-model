"""Probabilistic CAPEX — Monte Carlo over the cost distribution through the finance engine.

Best practice (and the AACE QRA spirit) treats CAPEX as a distribution, not a point
estimate, and propagates it to P-level economics. This samples total CAPEX ~ Normal(base,
sigma) — sigma from the QRA (``capex.contingency.base_cost_uncertainty_pct``) or
``capex.uncertainty_pct`` or an explicit override — runs the v14 pipeline per draw (so the
dual-DSCR debt sizer re-solves at each cost), and returns the percentile economics.

Percentile convention: STRAIGHT percentiles (p10/p50/p90 = numpy.percentile(arr, 10/50/90)).
For CAPEX, p90 is the HIGH (adverse) cost; for project/equity IRR, NPV and min DSCR
(higher = better), p10 is the ADVERSE (downside) value.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

logger = logging.getLogger(__name__)


def _apply_estimate_class_floor(config: Mapping[str, Any], sigma_pct: float) -> float:
    """Sanity-floor the CAPEX 1-sigma to the AACE estimate class's implied spread.

    A configured spread tighter than the estimate's class implies understates cost risk;
    the band (config/defaults.yaml) provides the floor and a warning. Resolution failures
    are non-fatal (the floor is a guard, not a gate).
    """
    try:
        from analytics.cost.estimate_class import resolve_accuracy_band

        band = resolve_accuracy_band(config)
    except Exception:  # pragma: no cover - missing/blank config must not break the MC
        return sigma_pct
    implied = band.implied_sigma_pct
    if sigma_pct < implied:
        logger.warning(
            "CAPEX MC sigma %.2f%% is tighter than AACE Class %d implies (%.2f%%); "
            "flooring to the class band.",
            sigma_pct,
            band.estimate_class,
            implied,
        )
        return implied
    return sigma_pct


@dataclass(frozen=True)
class CapexMcResult:
    n_samples: int
    sigma_pct: float
    base_capex_usd: float
    seed: int
    capex_usd: Dict[str, float]
    project_irr: Dict[str, float]
    equity_irr: Dict[str, float]
    project_npv_usd: Dict[str, float]
    min_dscr: Dict[str, float]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "n_samples": self.n_samples,
            "sigma_pct": self.sigma_pct,
            "base_capex_usd": round(self.base_capex_usd, 2),
            "seed": self.seed,
            "capex_usd": self.capex_usd,
            "project_irr": self.project_irr,
            "equity_irr": self.equity_irr,
            "project_npv_usd": self.project_npv_usd,
            "min_dscr": self.min_dscr,
        }


def resolve_capex_sigma_pct(
    config: Mapping[str, Any], override: Optional[float] = None
) -> float:
    """The 1-sigma % on CAPEX: explicit override, else the QRA uncertainty, else uncertainty_pct."""
    if override is not None:
        return float(override)
    capex = config.get("capex")
    capex = capex if isinstance(capex, Mapping) else {}
    cont = capex.get("contingency")
    cont = cont if isinstance(cont, Mapping) else {}
    for candidate in (
        cont.get("base_cost_uncertainty_pct"),
        capex.get("uncertainty_pct"),
    ):
        if candidate is not None:
            return float(candidate)
    raise ValueError(
        "No CAPEX uncertainty found: set capex.contingency.base_cost_uncertainty_pct, "
        "capex.uncertainty_pct, or pass sigma_pct."
    )


def run_capex_mc(
    config: Union[str, Mapping[str, Any]],
    *,
    n_samples: int = 200,
    sigma_pct: Optional[float] = None,
    seed: int = 12345,
    percentiles: Sequence[int] = (10, 50, 90),
) -> CapexMcResult:
    """Monte Carlo the total CAPEX and propagate to percentile finance KPIs."""
    import numpy as np

    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.scenario_loader import load_scenario_config
    from finance.debt_v14 import _extract_capex_usd

    cfg: Dict[str, Any] = (
        dict(load_scenario_config(config)) if isinstance(config, str) else dict(config)
    )
    sigma = resolve_capex_sigma_pct(cfg, sigma_pct)
    sigma = _apply_estimate_class_floor(cfg, sigma)
    base = _extract_capex_usd(cfg)
    if base <= 0:
        raise ValueError("base CAPEX must be > 0 for a probabilistic run")

    rng = np.random.default_rng(seed)
    factors = np.clip(rng.normal(1.0, sigma / 100.0, int(n_samples)), 0.4, 2.5)

    capex_s: List[float] = []
    irr: List[float] = []
    eqirr: List[float] = []
    npv: List[float] = []
    dscr: List[float] = []
    for factor in factors:
        run_cfg = copy.deepcopy(cfg)
        cap = dict(run_cfg.get("capex", {}))
        cap.pop("derive_from_breakdown", None)  # scale the total via usd_total
        cap["usd_total"] = base * float(factor)
        run_cfg["capex"] = cap
        kpis = run_v14_pipeline(config=run_cfg)["kpis"]
        capex_s.append(base * float(factor))
        irr.append(float(kpis["project_irr"]))
        eqirr.append(float(kpis["equity_irr"]))
        npv.append(float(kpis["project_npv"]))
        dscr.append(float(kpis["min_dscr"]))

    def pcts(arr: List[float]) -> Dict[str, float]:
        return {f"p{p}": float(np.percentile(arr, p)) for p in percentiles}

    return CapexMcResult(
        n_samples=int(n_samples),
        sigma_pct=sigma,
        base_capex_usd=base,
        seed=int(seed),
        capex_usd=pcts(capex_s),
        project_irr=pcts(irr),
        equity_irr=pcts(eqirr),
        project_npv_usd=pcts(npv),
        min_dscr=pcts(dscr),
    )


__all__ = ["CapexMcResult", "run_capex_mc", "resolve_capex_sigma_pct"]
