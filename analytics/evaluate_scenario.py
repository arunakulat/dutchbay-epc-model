from __future__ import annotations

"""
analytics.evaluate_scenario

Go-with-the-Flow v14 evaluation gateway.

Responsibility:
- Load base scenario config from YAML
- Apply nested overrides (dot-path style handled upstream)
- Run cashflow + debt stack
- Delegate KPI aggregation to analytics.core.metrics.calculate_scenario_kpis
- Return a flat dict of KPIs for Monte Carlo / sensitivity layers

This module is intentionally thin: it does NOT reimplement finance math.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Sequence

from analytics.contracts_v14 import ScenarioResult
from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _deep_update(
    base: MutableMapping[str, Any], overrides: Mapping[str, Any]
) -> MutableMapping[str, Any]:
    """
    Recursively update a nested dict with overrides.

    Only merges dicts; all other types overwrite.
    Mutates `base` and also returns it for convenience.
    """
    for key, value in overrides.items():
        if (
            key in base
            and isinstance(base[key], MutableMapping)
            and isinstance(value, Mapping)
        ):
            _deep_update(base[key], value)  # type: ignore[arg-type]
        else:
            base[key] = value
    return base


def _normalise_kpi_result(obj: Any) -> Dict[str, Any]:
    """
    Normalise the output of calculate_scenario_kpis into a plain dict.

    Supports:
    - ScenarioResult (contracts_v14)
    - dict-like returns (already normalised upstream)

    Raises:
        TypeError if the return type is not understood.
    """
    if isinstance(obj, ScenarioResult):
        kpis: Dict[str, Any] = {
            "scenario_name": obj.scenario_name,
            "project_npv": obj.project_npv,
            "project_irr": obj.project_irr,
            "dscr_min": obj.min_dscr,
            "max_debt_usd": obj.max_debt_usd,
        }
        # Optional extras that downstream tools might care about
        if obj.discount_rate_used is not None:
            kpis["discount_rate_used"] = obj.discount_rate_used
        if obj.wacc_label is not None:
            kpis["wacc_label"] = obj.wacc_label
        if obj.wacc_is_real is not None:
            kpis["wacc_is_real"] = obj.wacc_is_real
        # Expose any additional KPIs if present
        if obj.kpis:
            kpis.update(obj.kpis)
        return kpis

    if isinstance(obj, dict):
        # Assume it's already a KPI dict
        return dict(obj)

    raise TypeError(
        f"Unsupported KPI result type from calculate_scenario_kpis: {type(obj)!r}"
    )


# ---------------------------------------------------------------------------
# Public gateway
# ---------------------------------------------------------------------------


def evaluate_with_overrides(
    base_config_path: str,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Evaluate a single scenario given a base YAML config and optional overrides.

    This is the canonical entry point for:
    - Monte Carlo (analytics.monte_carlo_v14)
    - Sensitivity / tornado (analytics.sensitivity_v14)
    - Tail-risk overlays

    Args:
        base_config_path:
            Path to the base scenario YAML used as the starting point.
        overrides:
            Nested dict of overrides applied on top of the loaded config.
            Keys are expected to already be "expanded" into nested dicts
            (dot-path expansion is handled by callers such as sensitivity_v14).

    Returns:
        Flat dict of KPI values (e.g. project_irr, project_npv, dscr_min).
    """
    config_path = Path(base_config_path)
    logger.info("Evaluating scenario: %s", config_path)

    # 1) Load base config via central loader (v14 canonical path)
    config = load_scenario_config(str(config_path))
    if not isinstance(config, dict):
        raise TypeError(
            f"Loaded scenario config from {config_path} must be a mapping, "
            f"got {type(config)!r}"
        )

    # 2) Apply nested overrides (if any)
    overrides = overrides or {}
    if overrides:
        logger.debug("Applying overrides to config: %s", overrides)
        # Shallow copy then deep merge so we don't mutate shared state
        config = dict(config)
        _deep_update(config, overrides)

    # 3) Build annual cashflow rows from config
    annual_rows: Sequence[Dict[str, Any]] = build_annual_rows(config)

    # 4) Apply debt layer
    # NOTE: apply_debt_layer expects (params/config, annual_rows)
    debt_result: Dict[str, Any] = apply_debt_layer(config, annual_rows)

    # 5) Aggregate KPIs using the canonical metrics module
    # IMPORTANT: argument order is (annual_rows, debt_result, config)
    # so that `config` inside calculate_scenario_kpis is the config dict,
    # not the annual_rows list.
    raw_kpi_result = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=config,
        # For now we use a stable default discount rate here; if
        # a WACC engine is wired in upstream, that value can be
        # threaded through instead of this constant.
        discount_rate=0.10,
    )

    # 6) Normalise into a plain dict for Monte Carlo / sensitivity
    kpi_dict = _normalise_kpi_result(raw_kpi_result)

    logger.info(
        "Scenario evaluation complete for %s: IRR=%.4f, NPV=%s, DSCR_min=%.3f",
        config_path.name,
        float(kpi_dict.get("project_irr", 0.0)),
        kpi_dict.get("project_npv"),
        float(kpi_dict.get("dscr_min", 0.0)),
    )

    return kpi_dict


__all__ = ["evaluate_with_overrides"]

# EOF
