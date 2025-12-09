from __future__ import annotations

"""
analytics.evaluation_v14

Canonical evaluation gateway for the v14 finance stack.

This module provides a SINGLE, typed entry point for analytics layers
(sensitivity, Monte Carlo, optimization):

- evaluate_with_overrides(config_path, overrides)

Responsibilities
----------------
- Load YAML scenario config from disk
- Deep-merge any in-memory overrides (nested dict)
- Run the v14 pipeline
- Return a flat KPI dict with numeric values (floats)

Important
---------
Only THIS module is allowed to call:
- analytics.scenario_loader.load_scenario_config
- analytics.pipeline_v14.run_v14_pipeline

Analytics modules (sensitivity_v14, monte_carlo_v14, etc.) must
import and use evaluate_with_overrides() instead of touching the
pipeline directly.
"""

import logging
from pathlib import Path
from typing import Any, Mapping

from analytics.pipeline_v14 import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config


def _deep_merge_config(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Recursively deep-merge two configuration dictionaries.

    Values from `overrides` replace or extend values in `base`.
    Nested dicts are merged; other types are overwritten.
    """
    result: dict[str, Any] = dict(base)

    for key, override_value in overrides.items():
        if (
            key in result
            and isinstance(result[key], Mapping)
            and isinstance(override_value, Mapping)
        ):
            result[key] = _deep_merge_config(
                result[key],  # type: ignore[arg-type]
                override_value,
            )
        else:
            result[key] = override_value

    return result


def normalize_kpi_dict(raw_kpis: Mapping[str, Any]) -> dict[str, float]:
    """
    Normalize KPI dict to {str -> float}.

    All values that can be converted to float are kept; non-numeric
    values are skipped to allow label/metadata fields (e.g. scenario_name).
    """
    kpis: dict[str, float] = {}
    logger = logging.getLogger(__name__)

    for key, value in raw_kpis.items():
        try:
            kpis[key] = float(value)
        except (TypeError, ValueError):
            # Allow non-numeric KPIs like scenario_name; skip them.
            logger.debug(
                "normalize_kpi_dict: skipping non-numeric KPI %r=%r (type=%s)",
                key,
                value,
                type(value).__name__,
            )
            continue

    return kpis


def _run_pipeline_with_config(
    config: Mapping[str, Any],
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Internal helper: run v14 pipeline and extract normalized KPI dict.

    Assumes run_v14_pipeline returns a payload containing a 'kpis' key
    holding a mapping of KPI name -> numeric value.
    """
    payload = run_v14_pipeline(
        config=config,
        validation_mode="strict",
        validation_modules=validation_modules,
    )

    try:
        raw_kpis = payload["kpis"]  # type: ignore[index]
    except KeyError as exc:
        raise KeyError(
            "run_v14_pipeline payload does not contain 'kpis' key. "
            f"Available keys: {list(payload.keys())}"
        ) from exc

    if not isinstance(raw_kpis, Mapping):
        raise TypeError(
            f"Expected 'kpis' to be a mapping, got {type(raw_kpis).__name__}"
        )

    return normalize_kpi_dict(raw_kpis)


def evaluate_scenario_from_dict(
    config: Mapping[str, Any],
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """
    Evaluate a scenario given an in-memory configuration dict.

    Parameters
    ----------
    config:
        Base configuration dictionary (already loaded from YAML).
    overrides:
        Optional nested dict of overrides to apply to `config`
        before running the pipeline.

    Returns
    -------
    dict[str, float]
        Flat KPI dictionary with numeric values.
    """
    merged_config: Mapping[str, Any]
    if overrides:
        merged_config = _deep_merge_config(config, overrides)
    else:
        merged_config = config

    return _run_pipeline_with_config(merged_config)


def evaluate_with_overrides(
    config_path: str | Path,
    overrides: Mapping[str, Any] | None = None,
    *,
    validation_modules: list[str] | None = None,
) -> dict[str, float]:
    """
    Run a single scenario evaluation through the v14 pipeline.

    This is the CANONICAL entry point for analytics layers:

    - sensitivity_v14
    - monte_carlo_bridge_v14
    - any future evaluation-based tools

    Parameters
    ----------
    config_path:
        Path to YAML scenario configuration file.

    overrides:
        Optional nested dict for in-memory parameter overrides.

        Example
        -------
        overrides = {
            "project": {
                "capex_usd_per_kw": 1600.0,
            },
            "generation": {
                "capacity_factor_pct": 36.5,
            },
        }

    validation_modules:
        Optional list of modules to validate (e.g., ["cashflow", "debt"]).

    Returns
    -------
    dict[str, float]
        Flat KPI dict with numeric values (floats).

    Raises
    ------
    FileNotFoundError
        If the given config_path does not exist.

    KeyError
        If the pipeline payload does not contain a 'kpis' key.

    TypeError
        If load_scenario_config returns non-Mapping or raw_kpis is non-Mapping.
    """
    cfg_path = Path(config_path)

    if not cfg_path.is_file():
        raise FileNotFoundError(f"Scenario config not found: {cfg_path}")

    base_config = load_scenario_config(cfg_path)

    if not isinstance(base_config, Mapping):
        raise TypeError(
            "Expected load_scenario_config to return Mapping, "
            f"got {type(base_config).__name__}"
        )

    merged_config: Mapping[str, Any]
    if overrides:
        merged_config = _deep_merge_config(base_config, overrides)
    else:
        merged_config = base_config

    return _run_pipeline_with_config(
        merged_config, validation_modules=validation_modules
    )


# Backward compatibility alias (defined AFTER function)
evaluate_scenario = evaluate_with_overrides

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario",  # Alias for backward compatibility
    "evaluate_scenario_from_dict",
    "normalize_kpi_dict",
]
