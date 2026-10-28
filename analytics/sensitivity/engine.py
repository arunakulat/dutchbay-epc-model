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
import math
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


# Module-level singleton: the default run config is built once at import time and
# shared read-only (SensitivityRunConfig is frozen), which is behaviour-identical
# to the old `run_cfg=SensitivityRunConfig()` argument default but B008-compliant
# (#753). Reused by every function in this module that defaults run_cfg.
_DEFAULT_SENSITIVITY_RUN_CONFIG = SensitivityRunConfig()


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


def _read_sweep_metric(kpis: Mapping[str, Any], metric_key: str, *, case: str) -> float:
    """Read the swept metric off one evaluation, returning ``nan`` when it is undefined.

    ``evaluate_with_overrides`` returns the KPI surface through
    :func:`analytics.evaluation_v14.normalize_kpi_dict`, which drops any entry
    ``float()`` refuses. The pipeline sets ``equity_irr`` to ``None`` on purpose when no
    rate solves the equity cashflows (#1436), so such a point arrives with no key at all,
    and :func:`_extract_scalar_metric` raised ``KeyError``: one undefined point killed the
    whole tornado, and with it the web ``/analysis`` job (#1457). A sweep records that
    point as ``nan`` instead, the treatment ``optimization_v14._read_kpi`` gives the
    optimiser (#782). It never substitutes 0.0, which would read as break-even.

    It sees only the absent-key path (a ``None`` that ``normalize_kpi_dict`` dropped),
    plus a non-finite value. It cannot see a 0.0 the KPI surface substituted upstream:
    ``analytics/core/metrics.py:494`` for an unsolvable ``project_irr`` (``:492`` for
    ``project_npv``) and ``:466`` for an ``equity_irr`` with no equity-distribution
    result. Such a point arrives as 0.0 and is recorded as defined.

    A missing key is also what a mistyped ``metric_key`` looks like, hence the warning
    naming the metric and the case. ``_extract_scalar_metric`` keeps raising for the
    interaction grid, whose base and marginal cells must fail loud.
    """
    raw = kpis.get(metric_key)
    try:
        value = math.nan if raw is None else float(raw)
    except (TypeError, ValueError):
        value = math.nan
    if not math.isfinite(value):
        logger.warning(
            "sensitivity metric %r is undefined at %s (got %r); recording it as NaN.",
            metric_key,
            case,
            raw,
        )
        return math.nan
    return value


def _describe_case(label: str, overrides: Mapping[str, Any]) -> str:
    """``'CAPEX=low (capex.usd_total=135000000.0)'``: the driver, and the value it took."""
    settings = ", ".join(f"{key}={value!r}" for key, value in overrides.items())
    return f"{label} ({settings})" if settings else label


def _flag_undefined_metric(
    suite: SensitivitySuite,
    metric_key: str,
    *,
    undefined_base: bool,
    undefined_cases: Sequence[Sequence[str]],
    n_evaluations: int,
    strict: bool,
) -> SensitivitySuite:
    """Disclose where the metric arrived undefined; refuse when it never was defined.

    ``undefined_cases`` holds, per tornado in ``suite.tornado_results`` order, the case
    labels whose evaluation returned no value. Each such tornado carries them as
    ``metadata['undefined_cases']``; the suite carries ``undefined_base``,
    ``undefined_points`` (evaluations, the base included) and ``undefined_drivers``
    (bars whose swing is undefined because a low or high case was). An undefined base
    leaves ``base_metric`` as ``nan`` rather than a flat or zero bar.

    The counts cover only the absent-key path :func:`_read_sweep_metric` sees. A 0.0 the
    KPI surface substituted (``analytics/core/metrics.py:494`` and ``:466``) counts as
    defined, so ``undefined_points == 0`` does not show that every point solved.

    When no evaluation at all defined the metric there is no tornado to draw, and the
    likeliest cause is a mistyped key, so strict mode raises ``ValueError``.
    """
    n_undefined = int(undefined_base) + sum(len(labels) for labels in undefined_cases)
    if strict and suite.tornado_results and n_undefined == n_evaluations:
        raise ValueError(
            f"sensitivity metric '{metric_key}' is undefined at every one of "
            f"{n_evaluations} evaluations; the key may be mistyped, or the metric has no "
            "value anywhere in this scenario's sweep"
        )
    for tornado, labels in zip(suite.tornado_results, undefined_cases, strict=True):
        if labels:
            tornado.metadata["undefined_cases"] = list(labels)
    undefined_drivers = [
        t.metric_name for t in suite.tornado_results if not math.isfinite(t.impact_abs)
    ]
    suite.metadata["undefined_base"] = undefined_base
    suite.metadata["undefined_points"] = n_undefined
    suite.metadata["undefined_drivers"] = undefined_drivers
    if n_undefined:
        logger.warning(
            "sensitivity metric '%s' is undefined at %d of %d evaluations (base %s); "
            "%d driver bar(s) have an undefined swing: %s",
            metric_key,
            n_undefined,
            n_evaluations,
            "undefined" if undefined_base else "defined",
            len(undefined_drivers),
            undefined_drivers,
        )
    return suite


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

    Sets ``flat_metric`` True only when there is at least one defined bar and every
    defined bar's ``|impact_abs|`` is within ``_FLAT_IMPACT_TOL`` of zero; otherwise
    False. Bars whose swing is undefined (``nan``) are left out of the judgement. When flat,
    adds a ``flat_metric_reason`` (covenant-pinned wording for DSCR-family metrics) and
    logs a loud warning. ``SensitivitySuite.metadata`` is a mutable dict on a frozen
    dataclass, so it is updated in place and the same suite returned.
    """
    # An undefined bar (#1457) is neither flat nor moving; judge only the defined ones.
    impacts = [abs(t.impact_abs) for t in suite.tornado_results]
    defined = [impact for impact in impacts if math.isfinite(impact)]
    max_impact = max(defined, default=0.0)
    is_flat = bool(defined) and max_impact <= _FLAT_IMPACT_TOL
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
            len(defined),
            reason,
        )
    return suite


def build_one_way_sensitivity_suite(
    *,
    base_config: Mapping[str, Any],
    base_config_path: str = "<in-memory>",
    parameter: ParameterRangeConfig,
    metric_key: str,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
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
    base_value = _read_sweep_metric(base_kpis, metric_key, case="the base case")

    # Sweep cases using adapter
    cases: List[Dict[str, Any]] = []
    undefined_labels: List[str] = []
    for label, override_dict in iter_param_cases_from_contract(parameter):
        out = evaluate_with_overrides(
            config_path=None,
            raw_config=base_cfg,
            overrides=override_dict,
        )
        kpis = _coerce_kpis(out)
        val = _read_sweep_metric(
            kpis, metric_key, case=_describe_case(label, override_dict)
        )
        if math.isnan(val):
            undefined_labels.append(label)

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

    suite = _flag_undefined_metric(
        suite,
        metric_key,
        undefined_base=math.isnan(base_value),
        undefined_cases=[undefined_labels],
        n_evaluations=1 + len(cases),
        strict=run_cfg.strict,
    )
    return _flag_degenerate_metric(suite, metric_key)


def run_sensitivity_analysis(
    *,
    base_config: Mapping[str, Any],
    base_config_path: str = "<in-memory>",
    parameters: Sequence[ParameterRangeConfig],
    metric_keys: Sequence[str],
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
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
    base_value = _read_sweep_metric(base_kpis, primary_metric, case="the base case")
    undefined_cases: List[List[str]] = []
    n_evaluations = 1

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
        undefined_labels: List[str] = []
        for label, overrides in iter_param_cases_from_contract(p):
            out = evaluate_with_overrides(
                config_path=None,
                raw_config=base_cfg,
                overrides=overrides,
            )
            kpis = _coerce_kpis(out)
            val = _read_sweep_metric(
                kpis, primary_metric, case=_describe_case(label, overrides)
            )
            n_evaluations += 1
            if math.isnan(val):
                undefined_labels.append(label)

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
            base_value=base_value,
            cases=cases,
        )
        tornado_results.append(tornado)
        undefined_cases.append(undefined_labels)

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

    suite = _flag_undefined_metric(
        suite,
        primary_metric,
        undefined_base=math.isnan(base_value),
        undefined_cases=undefined_cases,
        n_evaluations=n_evaluations,
        strict=run_cfg.strict,
    )
    return _flag_degenerate_metric(suite, primary_metric)
