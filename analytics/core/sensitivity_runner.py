"""
analytics.core.sensitivity_runner

Path-loading entry point for deterministic one-way sensitivity analysis.

GWTF/CASPER: this module owns *no* orchestration of its own. It loads a base
scenario from disk, builds a default set of one-way parameter sweeps when the
caller does not supply explicit ones, and delegates all evaluation + contract
assembly to the canonical engine
(:func:`analytics.sensitivity.engine.run_sensitivity_analysis`). Keeping a single
orchestration hub avoids the duplicate-and-drift failure mode that previously
left this entry point calling a non-existent ``StandardShockLibrary`` API.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.engine import (
    SensitivityRunConfig,
)
from analytics.sensitivity.engine import (
    run_sensitivity_analysis as _run_engine_sensitivity,
)

# Default one-way sensitivity drivers for a v14 wind project-finance scenario.
#
# Each ``config_key`` is an empirically-verified LIVE override path against the
# canonical scenario schema (probed against the v14 pipeline, 2026-06-17): a
# shock on the key actually moves the KPIs rather than silently no-op'ing.
#
# ``Financing_Terms.interest_rate_nominal`` is deliberately EXCLUDED: the
# override does not currently route through the pipeline (proven no-op), and a
# flat bar would misrepresent interest-rate exposure in a lender tornado. This
# is tracked as a follow-up (interest-rate override routing).
#
# ``Financing_Terms.tenor_years`` is included even though it is flat for the
# (unlevered) project IRR — that flatness is *correct*; it moves the levered
# equity IRR, which is the metric a lender stresses tenor against.
#
# (config_key, label, low_pct, high_pct)
_DEFAULT_DRIVERS: tuple[tuple[str, str, float, float], ...] = (
    ("capex.usd_total", "CAPEX", -10.0, 10.0),
    ("opex.usd_per_year", "OPEX", -15.0, 15.0),
    ("project.capacity_factor", "Capacity Factor", -10.0, 10.0),
    ("tariff.lkr_per_kwh", "Tariff", -10.0, 10.0),
    ("tax.corporate_tax_rate", "Corporate Tax Rate", -20.0, 20.0),
    ("Financing_Terms.tenor_years", "Debt Tenor", -20.0, 20.0),
)

# ABSOLUTE-band drivers (config_key, label, low_value, high_value). Used for levers whose
# base value is 0 (a relative band on 0 is flat), e.g. the incremental financed
# curtailment stress: base 0.0, swept 0 -> 13% (= 2-15% total grid curtailment over the
# ~2% physical curtailment already embedded in capacity_factor). Driver is emitted only
# when the key is present in the config (project.curtailment_pct).
_DEFAULT_ABSOLUTE_DRIVERS: tuple[tuple[str, str, float, float], ...] = (
    ("project.curtailment_pct", "Grid Curtailment (incremental)", 0.0, 0.13),
)


def _get_nested(cfg: Mapping[str, Any], dotted_key: str) -> Optional[float]:
    """Resolve a dotted config key to its numeric base value, or None if absent."""
    node: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return float(node)


def _default_parameters(cfg: Mapping[str, Any]) -> List[ParameterRangeConfig]:
    """Build the default one-way driver set from a loaded scenario config.

    Drivers whose key is absent from the config are skipped (no flat bars).
    """
    params: List[ParameterRangeConfig] = []
    for config_key, label, low_pct, high_pct in _DEFAULT_DRIVERS:
        base = _get_nested(cfg, config_key)
        if base is None:
            continue
        params.append(
            ParameterRangeConfig(
                variable_name=config_key,
                base_value=base,
                low_pct=low_pct,
                high_pct=high_pct,
                label=label,
            )
        )
    for config_key, label, low_value, high_value in _DEFAULT_ABSOLUTE_DRIVERS:
        base = _get_nested(cfg, config_key)
        if base is None:
            continue
        params.append(
            ParameterRangeConfig(
                variable_name=config_key,
                base_value=base,
                low_value=low_value,
                high_value=high_value,
                label=label,
            )
        )
    return params


def run_sensitivity_analysis(
    base_config_path: str | Path,
    metric: str = "project_irr",
    parameters: Optional[Sequence[ParameterRangeConfig]] = None,
    *,
    run_cfg: Optional[SensitivityRunConfig] = None,
) -> SensitivitySuite:
    """Run one-way sensitivity analysis for a scenario configuration file.

    Thin path-loading wrapper over the canonical engine. It loads the base
    scenario, builds a default library of empirically-verified LIVE drivers when
    ``parameters`` is not supplied, and delegates orchestration and contract
    assembly to :func:`analytics.sensitivity.engine.run_sensitivity_analysis`.

    Args:
        base_config_path: Path to the base scenario YAML/JSON config.
        metric: Target KPI to analyse (default: ``"project_irr"``).
        parameters: Explicit one-way parameter sweeps. When ``None`` (the
            default), a library of standard drivers is built from the config.
        run_cfg: Optional engine execution knobs.

    Returns:
        :class:`~analytics.contracts_v14.SensitivitySuite` with one
        ``TornadoResult`` per parameter.
    """
    base_path = Path(base_config_path)
    base_cfg: dict[str, Any] = load_scenario_config(base_path)
    params = (
        list(parameters) if parameters is not None else _default_parameters(base_cfg)
    )
    suite = _run_engine_sensitivity(
        base_config=base_cfg,
        base_config_path=str(base_path),
        parameters=params,
        metric_keys=[metric],
        run_cfg=run_cfg or SensitivityRunConfig(),
    )
    # Sprint 18C audit fields (#117): stamp scenario provenance + run time onto
    # the returned suite. The engine is config-agnostic, so these are set here —
    # the one place that knows the originating config + path. SensitivitySuite is
    # a frozen dataclass, so build a new instance via dataclasses.replace.
    scenario_name = base_cfg.get("project", {}).get("name") or base_path.stem
    return replace(
        suite,
        scenario_name=str(scenario_name),
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
    )
