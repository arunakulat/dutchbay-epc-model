from __future__ import annotations

"""
analytics.sensitivity.engine

Canonical orchestration hub for deterministic sensitivity analysis (v14+).
GWTF/CASPER compliant:
- No CLI code here
- No direct pipeline imports outside evaluation gateway
- All scenario evaluation flows through analytics.evaluation_v14.evaluate_with_overrides()

Responsibilities:
- Load/accept base scenario config (dict-like)
- Build parameter sweep plan (one-way + optional multi-metric)
- Evaluate each override scenario
- Assemble SensitivitySuite / MultiMetricSensitivitySuite-compatible payloads
- Optionally enrich with tail risk snapshots (via analytics.sensitivity.tail_risk)

Public API (keep stable):
- run_sensitivity_analysis(...)
- build_one_way_sensitivity_suite(...)
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import copy

from analytics.evaluation_v14 import evaluate_with_overrides

# Contracts: use your canonical contracts_v14 surfaces.
# These names exist in your uploaded contracts_v14.py (per earlier imports).
from analytics.contracts_v14 import (
    SensitivitySuite,
    TornadoResult,
    ParameterRangeConfig,
    MultiMetricSensitivitySuite,
    MultiMetricTornadoResult,
)

from analytics.sensitivity.tail_risk import (
    TailRiskConfig,
    enrich_suite_with_tail_risk,
)


@dataclass(frozen=True)
class SensitivityRunConfig:
    """
    Execution knobs for the engine.
    Keep these small and deterministic.
    """
    explain: bool = False
    strict: bool = True
    attach_trial_metadata: bool = True
    enrich_tail_risk: bool = False
    tail_risk: TailRiskConfig = TailRiskConfig()


def _deepcopy_cfg(cfg: Mapping[str, Any]) -> Dict[str, Any]:
    # Keep config immutable for callers
    return copy.deepcopy(dict(cfg))


def _apply_overrides(base_cfg: Mapping[str, Any], overrides: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Override application strategy.

    IMPORTANT: Your canonical evaluation gateway already supports "overrides"
    passed separately; so we don't mutate cfg by default.

    This function exists only for cases where you want to bake overrides into cfg
    before calling evaluation. In the default flow we pass overrides directly.
    """
    merged = _deepcopy_cfg(base_cfg)
    # Best-effort shallow merge; replace with dotted-key patching if required.
    for k, v in overrides.items():
        merged[k] = v
    return merged


def _extract_scalar_metric(kpis: Mapping[str, Any], metric_key: str) -> float:
    v = kpis.get(metric_key, None)
    if v is None:
        raise KeyError(f"Missing KPI '{metric_key}' in evaluation output.")
    try:
        return float(v)
    except Exception as e:
        raise TypeError(f"KPI '{metric_key}' is not numeric: {v!r}") from e


def build_one_way_sensitivity_suite(
    *,
    base_config: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    metric_key: str,
    run_cfg: SensitivityRunConfig = SensitivityRunConfig(),
) -> SensitivitySuite:
    """
    Build a one-way SensitivitySuite for a single parameter and a single metric.
    """
    base_cfg = _deepcopy_cfg(base_config)

    # Base case evaluation
    base_out = evaluate_with_overrides(
        config_path=None,
        raw_config=base_cfg,
        overrides={},
    )
    base_kpis = base_out.get("kpis", base_out)
    base_value = _extract_scalar_metric(base_kpis, metric_key)

    # Sweep cases
    cases: List[Dict[str, Any]] = []
    for label, override_dict in _iter_param_cases(parameter):
        out = evaluate_with_overrides(
            config_path=None,
            raw_config=base_cfg,
            overrides=override_dict,
        )
        kpis = out.get("kpis", out)
        val = _extract_scalar_metric(kpis, metric_key)

        record: Dict[str, Any] = {
            "label": label,
            "overrides": dict(override_dict),
            "value": val,
        }
        if run_cfg.attach_trial_metadata:
            record["metadata"] = {
                "kpis": dict(kpis),
            }
        cases.append(record)

    # Convert to TornadoResult (contract-driven)
    tornado = TornadoResult(
        parameter=parameter,  # type: ignore[arg-type]
        metric_key=metric_key,  # type: ignore[arg-type]
        base_value=base_value,  # type: ignore[arg-type]
        cases=cases,  # type: ignore[arg-type]
    )

    suite = SensitivitySuite(
        base_config=dict(base_cfg),  # type: ignore[arg-type]
        tornado=tornado,  # type: ignore[arg-type]
        metadata={
            "engine": "analytics.sensitivity.engine",
            "metric_key": metric_key,
            "parameter_name": getattr(parameter, "name", None),
        },
    )

    if run_cfg.enrich_tail_risk:
        suite = enrich_suite_with_tail_risk(
            suite=suite,
            base_config=base_cfg,
            run_cfg=run_cfg.tail_risk,
        )

    return suite


def run_sensitivity_analysis(
    *,
    base_config: Mapping[str, Any],
    parameters: Sequence[ParameterRangeConfig],
    metric_keys: Sequence[str],
    run_cfg: SensitivityRunConfig = SensitivityRunConfig(),
) -> MultiMetricSensitivitySuite:
    """
    Multi-parameter, multi-metric orchestration.
    Evaluates each parameter sweep once per scenario and computes all requested metrics.

    Returns MultiMetricSensitivitySuite (contracts_v14 surface).
    """
    base_cfg = _deepcopy_cfg(base_config)

    # base eval once
    base_out = evaluate_with_overrides(
        config_path=None,
        raw_config=base_cfg,
        overrides={},
    )
    base_kpis = base_out.get("kpis", base_out)

    base_values: Dict[str, float] = {m: _extract_scalar_metric(base_kpis, m) for m in metric_keys}

    tornados: List[MultiMetricTornadoResult] = []

    for p in parameters:
        cases: List[Dict[str, Any]] = []
        for label, overrides in _iter_param_cases(p):
            out = evaluate_with_overrides(
                config_path=None,
                raw_config=base_cfg,
                overrides=overrides,
            )
            kpis = out.get("kpis", out)
            vals = {m: _extract_scalar_metric(kpis, m) for m in metric_keys}

            record: Dict[str, Any] = {
                "label": label,
                "overrides": dict(overrides),
                "values": vals,
            }
            if run_cfg.attach_trial_metadata:
                record["metadata"] = {"kpis": dict(kpis)}
            cases.append(record)

        tornados.append(
            MultiMetricTornadoResult(
                parameter=p,  # type: ignore[arg-type]
                metric_keys=list(metric_keys),  # type: ignore[arg-type]
                base_values=base_values,  # type: ignore[arg-type]
                cases=cases,  # type: ignore[arg-type]
            )
        )

    suite = MultiMetricSensitivitySuite(
        base_config=dict(base_cfg),  # type: ignore[arg-type]
        tornados=tornados,  # type: ignore[arg-type]
        metadata={
            "engine": "analytics.sensitivity.engine",
            "metric_keys": list(metric_keys),
            "parameters": [getattr(p, "name", None) for p in parameters],
        },
    )

    if run_cfg.enrich_tail_risk:
        suite = enrich_suite_with_tail_risk(
            suite=suite,
            base_config=base_cfg,
            run_cfg=run_cfg.tail_risk,
        )

    return suite


def _iter_param_cases(param: ParameterRangeConfig) -> Iterable[Tuple[str, Dict[str, Any]]]:
    """
    Convert a ParameterRangeConfig into labeled cases.

    Your contracts may define:
      - explicit values list
      - low/base/high
      - pct deltas

    This skeleton supports:
      - param.values (sequence of numeric)
      - param.low / param.high / param.base
      - param.override_key (dotted or plain key)

    Adjust to your real contract fields.
    """
    name = getattr(param, "name", "param")
    key = getattr(param, "override_key", None) or getattr(param, "key", None) or getattr(param, "path", None)
    if key is None:
        raise ValueError(f"ParameterRangeConfig '{name}' lacks override_key/key/path.")

    values = getattr(param, "values", None)
    if values is not None:
        for v in values:
            yield f"{name}={v}", {str(key): v}
        return

    low = getattr(param, "low", None)
    high = getattr(param, "high", None)
    base = getattr(param, "base", None)

    if base is not None:
        yield f"{name}=base", {str(key): base}
    if low is not None:
        yield f"{name}=low", {str(key): low}
    if high is not None:
        yield f"{name}=high", {str(key): high}

    if base is None and low is None and high is None:
        raise ValueError(f"ParameterRangeConfig '{name}' has no values/low/high/base.")
