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

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

# Contracts: use your canonical contracts_v14 surfaces.
from analytics.contracts_v14 import (
    ParameterRangeConfig,
    SensitivitySuite,
    TornadoResult,
)
from analytics.evaluation_v14 import evaluate_with_overrides

# Adapter layer for contract compatibility
from analytics.sensitivity.adapters import (
    engine_to_sensitivity_suite,
    engine_to_tornado_result,
    iter_param_cases_from_contract,
)
from analytics.sensitivity.tail_risk import (
    TailRiskConfig,
    enrich_suite_with_tail_risk,
)

logger = logging.getLogger(__name__)


def _resolves_in_config(cfg: Mapping[str, Any], dotted_key: str) -> bool:
    """True if a dotted override key resolves to an existing value in ``cfg``."""
    node: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return False
        node = node[part]
    return True


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


# DSCR/LLCR/PLCR are covenant-pinned under dual_dscr (target-DSCR) debt sizing: the
# debt quantum is sized to hold the min ratio AT the covenant target, so a CAPEX/OPEX/
# CF/tariff/tenor shock that would move the ratio is absorbed into the debt amount and
# every tornado bar comes back ~0. A lender reading an all-zero DSCR tornado must be
# told it is *structurally* flat (sweep gearing/balloon instead), not that the project
# is risk-free. The _resolves_in_config guard only catches non-resolving KEYS; this
# catches a resolving metric that simply cannot move.
_COVENANT_METRIC_TOKENS = ("dscr", "llcr", "plcr")
_FLAT_IMPACT_TOL = 1e-9


def _flag_degenerate_metric(
    suite: SensitivitySuite, metric_key: str
) -> SensitivitySuite:
    """Stamp ``metadata['flat_metric']`` and warn when a metric's whole tornado is flat.

    Sets ``flat_metric`` True only when there is at least one bar and every bar's
    ``|impact_abs|`` is within ``_FLAT_IMPACT_TOL`` of zero; otherwise False. When flat,
    adds a ``flat_metric_reason`` (covenant-pinned wording for DSCR-family metrics) and
    logs a loud warning. ``SensitivitySuite.metadata`` is a mutable dict on a frozen
    dataclass, so it is updated in place and the same suite returned.
    """
    bars = suite.tornado_results
    max_impact = max((abs(t.impact_abs) for t in bars), default=0.0)
    is_flat = bool(bars) and max_impact <= _FLAT_IMPACT_TOL
    suite.metadata["flat_metric"] = is_flat
    if is_flat:
        covenant = any(tok in metric_key.lower() for tok in _COVENANT_METRIC_TOKENS)
        reason = (
            "covenant-pinned: debt is sized to the DSCR target under dual_dscr, so this "
            "ratio is structurally invariant to the swept drivers — sweep a "
            "covenant-relevant lever (gearing, balloon) instead"
            if covenant
            else "every driver bar is ~0 impact; the metric does not move under these sweeps"
        )
        suite.metadata["flat_metric_reason"] = reason
        logger.warning(
            "sensitivity metric '%s' is structurally FLAT (max |impact|=%.2e across "
            "%d driver(s)): %s",
            metric_key,
            max_impact,
            len(bars),
            reason,
        )
    return suite


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

    # Validate the parameter resolves to an EXISTING config path. Otherwise the override
    # creates a new, unused key and the sweep silently produces a FLAT/zero tornado bar —
    # which misleads a lender's sensitivity read (audit R1: 'opex_annual', bare
    # 'capacity_factor' etc. produced 0.0 impact silently). Fail loud in strict mode.
    if not _resolves_in_config(base_cfg, parameter.variable_name):
        message = (
            f"sensitivity parameter '{parameter.variable_name}' does not resolve to an "
            "existing config path; its sweep would be a silent flat bar. Use a valid "
            "dotted path (e.g. project.capacity_factor, capex.usd_total, tariff.lkr_per_kwh)."
        )
        if run_cfg.strict:
            raise ValueError(message)
        logger.warning(message)

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

    return _flag_degenerate_metric(suite, metric_key)


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
        # Reject parameters that don't resolve to a real config path (else a silent flat
        # tornado bar; audit R1). Same contract as build_one_way_sensitivity_suite.
        if not _resolves_in_config(base_cfg, p.variable_name):
            message = (
                f"sensitivity parameter '{p.variable_name}' does not resolve to an "
                "existing config path; its sweep would be a silent flat bar."
            )
            if run_cfg.strict:
                raise ValueError(message)
            logger.warning(message)
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

    return _flag_degenerate_metric(suite, primary_metric)
