"""
analytics.mc.engine

Canonical Monte Carlo engine for v14 analytics.
GWTF/CASPER-friendly: no CLI code, no side-effectful imports at module import time.

Design goals
- Single public entrypoint: run_monte_carlo_analysis(...)
- Single engine class: MonteCarloEngine
- All production scenario evaluation goes through analytics.evaluation_v14.evaluate_with_overrides
- Correlation + degradation are optional steps (plug-ins), not separate engines.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import hashlib
import json
import logging

import numpy as np

from analytics.contracts_v14 import MonteCarloResult
from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.mc.aggregate import aggregate_trials
from analytics.mc.correlation import (
    CorrelationSpec,
    apply_correlation_structure,
)
from analytics.mc.degradation import apply_degradation_if_enabled
from analytics.mc.samplers import generate_lhs_samples

logger = logging.getLogger(__name__)


class MonteCarloConfigError(ValueError):
    """Raised when a ``monte_carlo`` config block does not match the engine contract.

    CESSPIT (schema strict) / CASPER (predictable error responses): a malformed
    ``monte_carlo.parameters`` block must fail with a clear, actionable message
    rather than a cryptic ``TypeError`` from deep inside the sampler. Subclasses
    :class:`ValueError` so existing ``except ValueError`` callers keep working.
    """


@dataclass(frozen=True)
class MonteCarloRunMeta:
    n_trials: int
    seed: int
    sampler: str
    common_random_numbers: bool
    param_names: Tuple[str, ...]
    config_hash: str


def _stable_config_hash(cfg: Mapping[str, Any]) -> str:
    payload = json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _num_override(overrides: Mapping[str, Any], *keys: str, default: float) -> float:
    """Resolve the first numeric override across the given keys, else ``default``.

    Robust to BOTH the generic smoke-test names ("capex") and the real dotted MC
    parameter names ("capex.usd_total"), and to NESTED override dicts: a value that is
    a mapping (e.g. ``{"capex": {"usd_total": ...}}`` from dotted-key expansion) is
    skipped rather than crashing ``float(dict)`` — which previously defeated this
    deliberately fail-soft fallback (audit R1).
    """
    for key in keys:
        value = overrides.get(key)
        if isinstance(value, bool):  # bool is an int subclass — not a numeric override
            continue
        if isinstance(value, (int, float)):
            return float(value)
    return float(default)


def _toy_metric_fallback(overrides: Mapping[str, Any]) -> dict[str, float]:
    """Return deterministic toy KPIs for MC engine smoke tests.

    This path is used only when the base configuration is intentionally minimal
    and cannot satisfy the full v14 finance schema. It keeps the MC sampler,
    aggregator, and export flow testable without weakening production schema
    validation in evaluation_v14 or pipeline_v14_enhanced.
    """
    capex = _num_override(overrides, "capex", "capex.usd_total", default=100.0)
    tariff = _num_override(overrides, "tariff", "tariff.lkr_per_kwh", default=0.10)
    capacity_factor = _num_override(
        overrides, "capacity_factor", "project.capacity_factor", default=0.35
    )
    opex = _num_override(overrides, "opex_annual", "opex.usd_per_year", default=2.5)

    capex_scale = capex / 100.0 if capex < 1_000_000 else capex / 100_000_000.0
    tariff_scale = tariff / 0.10 if tariff else 1.0
    cf_scale = capacity_factor / 0.35 if capacity_factor else 1.0
    opex_scale = opex / 2.5 if opex < 1_000_000 else opex / 2_500_000.0

    project_irr = max(0.0, 0.13 * tariff_scale * cf_scale / max(capex_scale, 0.01))
    dscr_min = max(0.01, 1.35 * tariff_scale * cf_scale / max(capex_scale, 0.01))
    project_npv = (tariff_scale * cf_scale - capex_scale - 0.05 * opex_scale) * 10_000_000.0

    return {
        "project_irr": float(project_irr),
        "project_npv": float(project_npv),
        # Emit the SAME 7 canonical metric keys a real trial returns (incl. equity_irr /
        # equity_npv) so a run that MIXES real and toy-fallback trials yields uniform-length
        # metric arrays. Previously the toy path omitted the equity keys, so any run with
        # >=1 real trial built ragged arrays and tripped the equal-length guard, crashing
        # the whole MC. These remain toy smoke values (levered slightly off the project KPIs).
        "equity_irr": float(max(0.0, project_irr * 0.95)),
        "equity_npv": float(project_npv * 0.85),
        "dscr_min": float(dscr_min),
        "llcr": float(max(dscr_min * 1.10, 0.01)),
        "plcr": float(max(dscr_min * 1.05, 0.01)),
        # Tag so aggregate_trials can count toy-fallback usage and consumers can
        # detect a degenerate run where real evaluation failed on every trial.
        "_toy_fallback": True,
    }


class MonteCarloEngine:
    """Canonical Monte Carlo engine."""

    def __init__(
        self,
        base_config: Mapping[str, Any],
        *,
        seed: int = 123,
        common_random_numbers: bool = True,
        correlation: Optional[CorrelationSpec] = None,
    ) -> None:
        # Deep-convert OmegaConf DictConfig to a plain dict so that
        # _deep_merge_config (in evaluation_v14) receives a fully plain
        # mapping.  A shallow dict(OmegaConf_object) leaves nested values
        # as DictConfig, which causes _deep_merge_config to overwrite them
        # with plain dicts on merge, silently dropping sibling keys that
        # were not in the override.  When base_config is already a plain
        # Mapping (the normal case from tests and CLI), this is a no-op.
        try:
            from omegaconf import OmegaConf, DictConfig
            if isinstance(base_config, DictConfig):
                self._base_config: Dict[str, Any] = OmegaConf.to_container(  # type: ignore[assignment]
                    base_config, resolve=True, throw_on_missing=False
                )
            else:
                self._base_config = dict(base_config)
        except ImportError:
            self._base_config = dict(base_config)

        self._seed = int(seed)
        self._crn = bool(common_random_numbers)
        self._correlation = correlation

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
        mc = cfg.get("monte_carlo", {}) if isinstance(cfg, Mapping) else {}
        params = mc.get("parameters", []) or mc.get("params", [])

        # CESSPIT (schema strict): the engine contract is an explicit *list* of
        # ``{name, low, high[, distribution]}`` mappings. A bare mapping (e.g.
        # ``{capacity_factor_std: 0.05, ...}``) is a different, incompatible
        # schema; iterating it would yield string keys and ``p["name"]`` would
        # raise an opaque ``TypeError``. Reject it up-front with a clear message
        # naming the exact field and the expected shape.
        if isinstance(params, Mapping):
            raise MonteCarloConfigError(
                "monte_carlo.parameters must be a LIST of "
                "{name, low, high[, distribution]} mappings, but a mapping "
                f"(dict) was provided with keys {sorted(params)!r}. A dict of "
                "per-parameter scalars is not the engine contract — convert it "
                "to an explicit list of parameter definitions with dotted "
                "config paths as `name` (e.g. "
                "[{name: project.capacity_factor, low: 0.276, high: 0.338}])."
            )

        param_names: List[str] = []
        bounds: List[Tuple[float, float]] = []
        kinds: List[str] = []

        for idx, p in enumerate(params):
            if not isinstance(p, Mapping) or "name" not in p:
                raise MonteCarloConfigError(
                    f"monte_carlo.parameters[{idx}] must be a mapping with a "
                    f"'name' key (a dotted config path), got {type(p).__name__}: "
                    f"{p!r}."
                )
            name = str(p["name"])
            low = float(p.get("low", p.get("min", 0.0)))
            high = float(p.get("high", p.get("max", 1.0)))
            kind = str(p.get("distribution", p.get("kind", "uniform")))

            # A param name that does not resolve to an EXISTING dotted path in the base config
            # is a likely DEAD lever: a non-dotted alias is placed at the top level where the
            # v14 engine never reads it, so every trial falls to the toy metric and the risk
            # distribution is degenerate (the deterministic sensitivity engine hard-fails the
            # identical mistake). We WARN rather than raise because non-dotted names are an
            # accepted (if degenerate) legacy input; the toy_fallback_count surfaces the
            # degeneracy downstream. Surfacing it here makes the silent case visible.
            from analytics.sensitivity.engine import _resolves_in_config

            if not _resolves_in_config(cfg, name):
                logger.warning(
                    "monte_carlo.parameters[%d].name %r does not resolve to an existing "
                    "config path; its sampled override is a likely DEAD key -> trials will "
                    "fall to the toy metric and the MC risk distribution will be degenerate. "
                    "Use a valid dotted path (e.g. capex.usd_total, project.capacity_factor).",
                    idx, name,
                )

            param_names.append(name)
            bounds.append((low, high))
            kinds.append(kind)

        if not param_names:
            raise MonteCarloConfigError(
                "Monte Carlo config has no parameters "
                "(monte_carlo.parameters is empty)."
            )

        return param_names, bounds, kinds

    def run(self, *, n_trials: int) -> MonteCarloResult:
        n = int(n_trials)
        if n <= 0:
            raise ValueError("n_trials must be > 0")

        samples = generate_lhs_samples(
            n_trials=n,
            bounds=self._param_bounds,
            seed=self._seed,
            common_random_numbers=self._crn,
        )

        if self._correlation is not None and self._correlation.enabled:
            samples = apply_correlation_structure(
                lhs_samples=samples,
                correlation=self._correlation,
                seed=self._seed,
            )

        trial_metrics: List[Mapping[str, Any]] = []

        for i in range(n):
            overrides = self._build_overrides_from_sample(samples[i], self._param_names)
            overrides = apply_degradation_if_enabled(base_cfg=self._base_config, overrides=overrides)

            try:
                out = evaluate_with_overrides(
                    config_path=None,
                    raw_config=self._base_config,
                    overrides=overrides,
                )
                if isinstance(out, Mapping):
                    kpis = out.get("kpis", out)
                    trial_metrics.append(kpis if isinstance(kpis, Mapping) else out)
                else:
                    trial_metrics.append({})
            except Exception as exc:
                # WARNING, not DEBUG: on a production scenario a toy fallback
                # means real evaluation FAILED for this trial; silently swallowing
                # it at DEBUG let an all-failing run report success_rate=100% with
                # fabricated KPIs. aggregate_trials surfaces toy_fallback_count.
                logger.warning(
                    "MC trial %d used toy fallback because full v14 evaluation failed: %s",
                    i,
                    exc,
                )
                trial_metrics.append(_toy_metric_fallback(overrides))

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
        """Build a nested override dict from a flat LHS sample row.

        Dot-notation parameter names (e.g. ``"project.capacity_factor"``) are
        expanded into nested dicts so that ``_deep_merge_config`` in
        ``evaluation_v14`` can correctly merge them into the base scenario
        config.  Flat (non-dotted) names are placed at the top level as
        before.

        Example
        -------
        param_names = ["project.capacity_factor", "Financing_Terms.rates.lkr_nominal"]
        sample_row  = [0.42, 0.075]

        Returns
        -------
        {
            "project": {"capacity_factor": 0.42},
            "Financing_Terms": {"rates": {"lkr_nominal": 0.075}},
        }

        Dolphin Strategy note: this is a self-contained static method fix.
        No shim is required because ``_build_overrides_from_sample`` is a
        private helper with no external callers; the public API
        (``MonteCarloEngine.run`` and ``run_monte_carlo_analysis``) is
        unchanged.  Bug: MC trials all fell back to toy-metric fallback
        because flat keys were never found in the nested config and the
        schema guard raised ValidationError on every trial.
        """
        overrides: Dict[str, Any] = {}
        for name, val in zip(param_names, sample_row.tolist()):
            keys = name.split(".")
            if len(keys) == 1:
                # Non-dotted name: place at top level (backward-compatible)
                overrides[name] = val
            else:
                # Dot-notation: expand into nested dict
                d = overrides
                for k in keys[:-1]:
                    d = d.setdefault(k, {})
                d[keys[-1]] = val
        return overrides


def run_monte_carlo_analysis(
    *,
    base_config: Mapping[str, Any],
    n_trials: int,
    seed: int = 123,
    common_random_numbers: bool = True,
    correlation: Optional[CorrelationSpec] = None,
) -> MonteCarloResult:
    """Stable functional entrypoint for the canonical MC engine."""
    engine = MonteCarloEngine(
        base_config=base_config,
        seed=seed,
        common_random_numbers=common_random_numbers,
        correlation=correlation,
    )
    return engine.run(n_trials=int(n_trials))
