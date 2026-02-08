from __future__ import annotations

"""
analytics.mc.engine

Canonical Monte Carlo engine for v14 analytics.
GWTF/CASPER-friendly: no CLI code, no side-effectful imports at module import time.

Design goals
- Single public entrypoint: run_monte_carlo_analysis(...)
- Single engine class: MonteCarloEngine
- All scenario evaluation MUST go through analytics.evaluation_v14.evaluate_with_overrides
- Correlation + degradation are optional steps (plug-ins), not separate engines.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import hashlib
import json
import numpy as np

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.contracts_v14 import MonteCarloResult  # keep your contract surface stable

from analytics.mc.samplers import generate_lhs_samples
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.correlation import (
    CorrelationSpec,
    apply_correlation_structure,
)
from analytics.mc.degradation import apply_degradation_if_enabled


@dataclass(frozen=True)
class MonteCarloRunMeta:
    n_trials: int
    seed: int
    sampler: str
    common_random_numbers: bool
    param_names: Tuple[str, ...]
    config_hash: str


def _stable_config_hash(cfg: Mapping[str, Any]) -> str:
    # Stable hash for regressions; avoid non-deterministic dict ordering issues.
    payload = json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


class MonteCarloEngine:
    """
    Canonical engine. Keep this surface stable.

    Typical usage:
        eng = MonteCarloEngine(base_config=cfg, seed=123)
        result = eng.run(n_trials=1000)
    """

    def __init__(
        self,
        base_config: Mapping[str, Any],
        *,
        seed: int = 123,
        common_random_numbers: bool = True,
        correlation: Optional[CorrelationSpec] = None,
    ) -> None:
        self._base_config: Dict[str, Any] = dict(base_config)
        self._seed = int(seed)
        self._crn = bool(common_random_numbers)
        self._correlation = correlation

        # Extract param definitions once (fast + deterministic)
        self._param_names, self._param_bounds, self._param_kinds = self._extract_param_definitions(
            self._base_config
        )

        self._meta = MonteCarloRunMeta(
            n_trials=0,
            seed=self._seed,
            sampler="lhs",
            common_random_numbers=self._crn,
            param_names=tuple(self._param_names),
            config_hash=_stable_config_hash(self._base_config),
        )

    @staticmethod
    def _extract_param_definitions(
        cfg: Mapping[str, Any],
    ) -> Tuple[List[str], List[Tuple[float, float]], List[str]]:
        """
        Convert your MC config section into:
          - param_names: stable ordering
          - param_bounds: [(low, high), ...]
          - param_kinds: distribution/kind tags (optional)

        Replace this with your existing extraction logic from monte_carlo_v14.py.
        """
        mc = cfg.get("monte_carlo", {}) if isinstance(cfg, Mapping) else {}
        params = mc.get("parameters", []) or mc.get("params", [])

        param_names: List[str] = []
        bounds: List[Tuple[float, float]] = []
        kinds: List[str] = []

        for p in params:
            name = str(p["name"])
            low = float(p.get("low", p.get("min", 0.0)))
            high = float(p.get("high", p.get("max", 1.0)))
            kind = str(p.get("distribution", p.get("kind", "uniform")))

            param_names.append(name)
            bounds.append((low, high))
            kinds.append(kind)

        if not param_names:
            # Fail fast: MC with no parameters is almost always a misconfig.
            raise ValueError("Monte Carlo config has no parameters (monte_carlo.parameters is empty).")

        return param_names, bounds, kinds

    def run(self, *, n_trials: int) -> MonteCarloResult:
        n = int(n_trials)
        if n <= 0:
            raise ValueError("n_trials must be > 0")

        # 1) sample
        samples = generate_lhs_samples(
            n_trials=n,
            bounds=self._param_bounds,
            seed=self._seed,
            common_random_numbers=self._crn,
        )  # shape: [n_trials, n_params]

        # 2) correlate (optional)
        if self._correlation is not None and self._correlation.enabled:
            samples = apply_correlation_structure(
                lhs_samples=samples,
                correlation=self._correlation,
                seed=self._seed,
            )

        # 3) evaluate trials
        trial_metrics: List[Mapping[str, Any]] = []
        trial_meta: List[Mapping[str, Any]] = []

        for i in range(n):
            overrides = self._build_overrides_from_sample(samples[i], self._param_names)

            # Optional degradation hook (can adjust overrides or post-process rows)
            overrides = apply_degradation_if_enabled(base_cfg=self._base_config, overrides=overrides)

            # All evaluations go through the gateway
            out = evaluate_with_overrides(
                config_path=None,
                raw_config=self._base_config,
                overrides=overrides,
            )

            # Expect out to include kpis/metrics; normalize here
            trial_metrics.append(out.get("kpis", out))
            trial_meta.append({"trial": i})

        # 4) aggregate
        result = aggregate_trials(
            trial_metrics=trial_metrics,
            base_config=self._base_config,
            param_names=self._param_names,
            samples=samples,
            meta={
                "seed": self._seed,
                "sampler": "lhs",
                "common_random_numbers": self._crn,
                "n_trials": n,
                "config_hash": self._meta.config_hash,
                "param_names": list(self._param_names),
                "correlation_enabled": bool(self._correlation and self._correlation.enabled),
            },
        )
        return result

    @staticmethod
    def _build_overrides_from_sample(sample_row: np.ndarray, param_names: Sequence[str]) -> Dict[str, Any]:
        """
        Convert a sampled vector into scenario overrides.
        This must match your v14 override schema (Hydra/OmegaConf style or dict patching).

        Replace with your existing mapping logic (often dotted-key patches).
        """
        overrides: Dict[str, Any] = {}
        for name, val in zip(param_names, sample_row.tolist()):
            overrides[name] = val
        return overrides


def run_monte_carlo_analysis(
    *,
    base_config: Mapping[str, Any],
    n_trials: int,
    seed: int = 123,
    common_random_numbers: bool = True,
    correlation: Optional[CorrelationSpec] = None,
) -> MonteCarloResult:
    """
    Stable functional entrypoint.
    Keep this import path stable for CASPER + CLI.
    """
    engine = MonteCarloEngine(
        base_config=base_config,
        seed=seed,
        common_random_numbers=common_random_numbers,
        correlation=correlation,
    )
    return engine.run(n_trials=int(n_trials))
