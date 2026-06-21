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

# Adapter layer for contract compatibility
from analytics.sensitivity.adapters import (
    iter_param_cases_from_contract,
    engine_to_tornado_result,
    engine_to_sensitivity_suite,
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


def _extract_scalar_metric(kpis: Mapping[str, Any], metric_key: str) -> float:
    v = kpis.get(metric_key, None)
    if v is None:
        raise KeyError(f"Missing KPI '{metric_key}' in evaluation output.")
    try:
        return float(v)
    except Exception as e:
        raise TypeError(f"KPI '{metric_key}' is not numeric: {v!r}") from e


def _coerce_kpis(out: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the KPI mapping from an evaluation result.

    ``evaluate_with_overrides`` returns either a flat KPI dict or a wrapper dict
    carrying a nested ``"kpis"`` mapping. Normalise to a single ``Mapping`` so
    downstream metric extraction is statically typed (not ``float | Any``).
    """
    inner = out.get("kpis")
    if isinstance(inner, Mapping):
        return inner
    return out


def build_one_way_sensitivity_suite(
    *,
    base_config: Mapping[str, Any],
    base_config_path: str = "<in-memory>",
    parameter: ParameterRangeConfig,
    metric_key: str,
    run_cfg: SensitivityRunConfig = SensitivityRunConfig(),
) -> SensitivitySuite:
    """
    Build a one-way SensitivitySuite for a single parameter and a single metric.
    
    Now uses adapter layer to ensure compatibility with contracts_v14.py.
    """
    base_cfg = _deepcopy_cfg(base_config)

    # Base case evaluation
    base_out = evaluate_with_overrides(
        config_path=None,
        raw_config=base_cfg,
        overrides={},
    )
    base_kpis = _coerce_kpis(base_out)
    base_value = _extract_scalar_metric(base_kpis, metric_key)

    # Sweep cases using adapter
    cases: List[Dict[str, Any]] = []
    for label, override_dict in iter_param_cases_from_contract(parameter):
        out = evaluate_with_overrides(
            config_path=None,
            raw_config=base_cfg,
            overrides=override_dict,
        )
        kpis = _coerce_kpis(out)
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

    # Convert to TornadoResult using adapter
    tornado = engine_to_tornado_result(
        parameter=parameter,
        metric_key=metric_key,
        base_value=base_value,
        cases=cases,
    )

    # Convert to SensitivitySuite using adapter
    suite = engine_to_sensitivity_suite(
        base_config_path=base_config_path,
        metric_key=metric_key,
        tornado_results=[tornado],
        base_kpis=dict(base_kpis),
    )

    if run_cfg.enrich_tail_risk:
        # SensitivitySuite already carries .metadata, so the enricher applies
        # directly (the prior "may need adjustment" TODO was stale — the contract
        # matches). Opting in now actually enriches instead of silently no-op'ing.
        suite = enrich_suite_with_tail_risk(
            suite=suite, base_config=base_cfg, run_cfg=run_cfg.tail_risk
        )

    return suite


def run_sensitivity_analysis(
    *,
    base_config: Mapping[str, Any],
    base_config_path: str = "<in-memory>",
    parameters: Sequence[ParameterRangeConfig],
    metric_keys: Sequence[str],
    run_cfg: SensitivityRunConfig = SensitivityRunConfig(),
) -> SensitivitySuite:
    """
    Multi-parameter, multi-metric orchestration.
    
    NOTE: Currently returns SensitivitySuite (not MultiMetricSensitivitySuite)
    because contracts_v14.py doesn't define MultiMetricSensitivitySuite.
    
    For multi-metric analysis, we'll build multiple TornadoResults and
    return them in a single SensitivitySuite.
    """
    base_cfg = _deepcopy_cfg(base_config)

    # base eval once
    base_out = evaluate_with_overrides(
        config_path=None,
        raw_config=base_cfg,
        overrides={},
    )
    base_kpis = _coerce_kpis(base_out)

    tornado_results: List[TornadoResult] = []

    # For each parameter, build a tornado result for the PRIMARY metric
    primary_metric = metric_keys[0] if metric_keys else "project_irr"
    
    for p in parameters:
        cases: List[Dict[str, Any]] = []
        for label, overrides in iter_param_cases_from_contract(p):
            out = evaluate_with_overrides(
                config_path=None,
                raw_config=base_cfg,
                overrides=overrides,
            )
            kpis = _coerce_kpis(out)
            val = _extract_scalar_metric(kpis, primary_metric)

            record: Dict[str, Any] = {
                "label": label,
                "overrides": dict(overrides),
                "value": val,
            }
            if run_cfg.attach_trial_metadata:
                record["metadata"] = {"kpis": dict(kpis)}
            cases.append(record)

        tornado = engine_to_tornado_result(
            parameter=p,
            metric_key=primary_metric,
            base_value=_extract_scalar_metric(base_kpis, primary_metric),
            cases=cases,
        )
        tornado_results.append(tornado)

    suite = engine_to_sensitivity_suite(
        base_config_path=base_config_path,
        metric_key=primary_metric,
        tornado_results=tornado_results,
        base_kpis=dict(base_kpis),
    )

    if run_cfg.enrich_tail_risk:
        # SensitivitySuite carries .metadata; the enricher applies directly.
        suite = enrich_suite_with_tail_risk(
            suite=suite, base_config=base_cfg, run_cfg=run_cfg.tail_risk
        )

    return suite
