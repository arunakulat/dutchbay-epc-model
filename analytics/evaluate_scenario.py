"""Central scenario evaluation helper for the v14 pipeline.

This module is the *one-liner* entry point that other layers call when they
need “just give me the KPIs for this config, with a few what-ifs applied”.

Typical callers:
    - Monte Carlo engine (analytics.monte_carlo_v14)
    - Tornado / sensitivity analysis (analytics.sensitivity_v14)
    - CLI tools / notebooks that want quick IRR/NPV/DSCR for a scenario

The contracts are intentionally simple:

    1) High-level KPI dict, with overrides:
        >>> from analytics.evaluate_scenario import evaluate_with_overrides
        >>> kpis = evaluate_with_overrides(
        ...     "scenarios/example_a.yaml",
        ...     overrides={"project": {"capex_usd_per_kw": 900.0}},
        ... )
        >>> kpis["project_irr"]
        0.1375  # for example

    2) Legacy dict adapter used by run_full_pipeline_v14:
        >>> from analytics.evaluate_scenario import evaluate_scenario_as_dict
        >>> result = evaluate_scenario_as_dict("scenarios/example_a.yaml")
        >>> result["project_irr"]
        0.1375

Under the hood we:
    1. Load the YAML/JSON config
    2. Apply nested overrides (if any)
    3. Run the v14 schema guard
    4. Compute WACC
    5. Build cashflow + debt layers
    6. Compute scenario KPIs (IRR / NPV / DSCR / coverage metrics)

The main design goal: keep all this wiring in *one place* so the rest of
the analytics layer only needs to call a single function and reason about
a simple {metric_name -> value} dict or a dict-like result surface.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from analytics.contracts_v14 import ScenarioResult, WaccResult
from analytics.core.metrics import calculate_scenario_kpis
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer
from finance.wacc_v14 import compute_wacc_from_config

logger = logging.getLogger(__name__)

__all__ = [
    "evaluate_with_overrides",
    "evaluate_scenario_as_dict",
    "_apply_nested_overrides",
]


# =====================================================================
# High-level KPI dict API (used by sensitivity / Monte Carlo)
# =====================================================================


def evaluate_with_overrides(
    base_config_path: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    High-level evaluation entry point used across the analytics stack.

    This is the “do the whole v14 dance and just give me the KPIs” function.
    It is intentionally narrow:
        - Input: path to a v14 scenario config (YAML/JSON) + optional overrides
        - Output: a dict of scalar KPIs (project_irr, equity_irr, npv, dscr_min, …)

    Args:
        base_config_path:
            Path to the scenario config file. This should be a v14 config that
            passes the schema guard (or can be made valid with overrides).
            Relative paths are resolved from the current working directory.

        overrides:
            Nested override structure that will be merged into the loaded config.
            This is where sensitivity/Monte Carlo inject their what-ifs.

            Two common patterns:
            1) Already nested, as used by tornado/sensitivity code:
                {"project": {"capex_usd_per_kw": 900.0}}

            2) Generated from dotted paths:
                path: "project.capex_usd_per_kw"
                value: 900.0
                -> sensitivity_v14 converts that into the nested dict above
                   *before* calling this function.

    Returns:
        A plain dictionary of KPIs, suitable for:
            - plotting
            - feeding Monte Carlo post-processing
            - exporting to Excel dashboards
            - comparison across scenarios

        Example keys (exact set depends on calculate_scenario_kpis):
            {
                "project_irr": 0.135,
                "equity_irr": 0.182,
                "project_npv": 1_250_000.0,
                "equity_npv": 850_000.0,
                "dscr_min": 1.35,
                "dscr_avg": 1.52,
                ...
            }

    Raises:
        FileNotFoundError:
            If base_config_path does not exist.

        ValueError:
            If the config fails schema validation or the KPI layer cannot
            compute a sensible result.

    Usage example (for notebooks / scripts):

        >>> kpis = evaluate_with_overrides(
        ...     "scenarios/dutchbay_master_config_v14.yaml",
        ...     overrides={"tariff": {"lkr_per_kwh": 20.30}},
        ... )
        >>> print(f"Project IRR: {kpis['project_irr']:.2%}")
    """
    cfg_path = Path(base_config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(str(cfg_path))

    logger.info("Loading scenario config for evaluation: %s", cfg_path)
    raw_config: Dict[str, Any] = load_scenario_config(str(cfg_path))

    # Work on a copy so that the caller’s config on disk is never mutated.
    config: Dict[str, Any] = copy.deepcopy(raw_config)

    if overrides:
        logger.debug("Applying overrides to config: %s", overrides)
        config = _apply_nested_overrides(config, overrides)

    # Schema guard: this is the gatekeeper that ensures the v14 cashflow/debt
    # surface sees a well-formed config. If it fails, the error message should
    # point directly back to the offending fields in the YAML.
    try:
        validate_config_for_v14(
            raw_config=config,
            config_path=str(cfg_path),
            modules=["cashflow"],
        )
    except TypeError:
        # Backwards-compat shim in case validate_config_for_v14 has the older
        # (config, config_path, modules=...) signature in your local codebase.
        validate_config_for_v14(config, str(cfg_path), modules=["cashflow"])

    # 1) Compute WACC / discount curve, based purely on the config
    logger.info("Computing WACC for scenario: %s", cfg_path.name)
    wacc_result: WaccResult = compute_wacc_from_config(config=config)

    # 2) Build annual cashflow rows (project-level CFADS + bookkeeping)
    logger.info("Building annual cashflow rows for scenario.")
    annual_rows = build_annual_rows(config)

    # 3) Apply the debt layer (amortisation schedule, interest, DSCR inputs)
    logger.info("Applying debt layer to cashflows.")
    debt_result = apply_debt_layer(
        annual_rows=annual_rows,
        config=config,
    )

    # 4) Compute KPIs (IRR, NPV, coverage metrics, lender ratios, etc.)
    logger.info("Calculating scenario KPIs.")
    kpi_result = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        wacc_result=wacc_result,
    )

    # The KPI layer may eventually return a rich ScenarioResult. To keep the
    # public contract stable for Monte Carlo / sensitivity code, we normalise
    # to a dict of plain numbers if needed.
    if isinstance(kpi_result, ScenarioResult):
        # Preferred: a dedicated conversion method on the dataclass
        if hasattr(kpi_result, "as_dict"):
            return kpi_result.as_dict()  # type: ignore[no-any-return]

        # Fallback: assume there is a `.kpis` attribute containing the dict.
        if hasattr(kpi_result, "kpis"):
            return getattr(kpi_result, "kpis")  # type: ignore[no-any-return]

        # As an absolute last resort, expose __dict__ to avoid breaking callers.
        return dict(vars(kpi_result))

    # If calculate_scenario_kpis already returns a plain dict, just pass it through.
    if not isinstance(kpi_result, dict):
        raise ValueError(
            f"Unexpected KPI result type: {type(kpi_result)!r}; "
            "expected ScenarioResult or dict[str, Any]."
        )

    return kpi_result


# =====================================================================
# Legacy adapter for run_full_pipeline_v14 (dict surface)
# =====================================================================


def evaluate_scenario_as_dict(
    config_path: str,
    scenario_name: Optional[str] = None,
    validation_mode: str = "strict",
) -> Dict[str, Any]:
    """
    Backward-compatible adapter used by run_full_pipeline_v14 and similar callers.

    This provides a *richer* dict than evaluate_with_overrides, including:
        - scenario_name
        - config_path
        - key KPIs as top-level fields
        - dscr_series and max_debt_usd
        - flattened WACC information
        - the raw kpis dict (under "kpis")

    Args:
        config_path:
            Path to the scenario config file (YAML/JSON).

        scenario_name:
            Optional override for the scenario name. If not provided, we use:
                - config["scenario_name"], or
                - the filename stem.

        validation_mode:
            Currently unused but kept to maintain the historic signature
            for CLI / pipeline callers ("strict" / "relaxed").

    Returns:
        Dict[str, Any]: a flat dict surface suitable for CLI and older
        consumers that expect to index into result["project_irr"], etc.
    """
    cfg_path = Path(config_path)
    if not cfg_path.exists():
        raise FileNotFoundError(str(cfg_path))

    logger.info("evaluate_scenario_as_dict: loading scenario from %s", cfg_path)
    raw_config: Dict[str, Any] = load_scenario_config(str(cfg_path))
    config: Dict[str, Any] = copy.deepcopy(raw_config)

    try:
        validate_config_for_v14(
            raw_config=config,
            config_path=str(cfg_path),
            modules=["cashflow"],
        )
    except TypeError:
        validate_config_for_v14(config, str(cfg_path), modules=["cashflow"])

    logger.info("evaluate_scenario_as_dict: computing WACC.")
    wacc_result: WaccResult = compute_wacc_from_config(config=config)

    logger.info("evaluate_scenario_as_dict: building annual cashflows.")
    annual_rows = build_annual_rows(config)

    logger.info("evaluate_scenario_as_dict: applying debt layer.")
    debt_result = apply_debt_layer(
        annual_rows=annual_rows,
        config=config,
    )

    logger.info("evaluate_scenario_as_dict: calculating KPIs.")
    kpi_result = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        wacc_result=wacc_result,
    )

    # Normalise KPI surface to a dict (same logic as evaluate_with_overrides).
    if isinstance(kpi_result, ScenarioResult):
        if hasattr(kpi_result, "as_dict"):
            kpis: Dict[str, Any] = kpi_result.as_dict()  # type: ignore[assignment]
        elif hasattr(kpi_result, "kpis"):
            kpis = getattr(kpi_result, "kpis")  # type: ignore[assignment]
        else:
            kpis = dict(vars(kpi_result))
    elif isinstance(kpi_result, dict):
        kpis = kpi_result
    else:
        raise ValueError(
            f"Unexpected KPI result type in evaluate_scenario_as_dict: "
            f"{type(kpi_result)!r}"
        )

    # Scenario name resolution
    if scenario_name is None:
        scenario_name = str(config.get("scenario_name") or cfg_path.stem)

    # Convenience top-level fields for pipeline consumers.
    project_npv = kpis.get("project_npv")
    project_irr = kpis.get("project_irr")
    equity_irr = kpis.get("equity_irr")
    dscr_min = (
        kpis.get("dscr_min")
        if "dscr_min" in kpis
        else kpis.get("min_dscr")
    )

    max_debt_usd = float(debt_result.get("total_debt_usd", 0.0))
    dscr_series = debt_result.get("dscr_series", [])

    result: Dict[str, Any] = {
        "scenario_name": scenario_name,
        "config_path": str(cfg_path),
        "validation_mode": validation_mode,
        "project_npv": project_npv,
        "project_irr": project_irr,
        "equity_irr": equity_irr,
        "dscr_min": dscr_min,
        "max_debt_usd": max_debt_usd,
        "dscr_series": dscr_series,
        "kpis": kpis,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
    }

    # Flatten WACC info into a dict if available.
    if isinstance(wacc_result, WaccResult):
        base = wacc_result.base
        result["wacc"] = {
            "mode": base.mode,
            "wacc_nominal": base.wacc_nominal,
            "wacc_real": base.wacc_real,
            "wacc_prudential": base.wacc_prudential,
            "risk_free_rate": base.risk_free_rate,
            "market_risk_premium": base.market_risk_premium,
            "asset_beta": base.asset_beta,
            "prudential_rate": wacc_result.prudential_rate,
            "prudential_npv": wacc_result.prudential_npv,
        }

    return result


# =====================================================================
# Nested override helper
# =====================================================================


def _apply_nested_overrides(
    config: Dict[str, Any],
    overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge a nested overrides dict into an existing config dict, in-place.

    This is intentionally *dumb but predictable* and is meant to match how
    sensitivity / Monte Carlo build their overrides.

    Shapes:

        base config (already loaded from YAML/JSON):
            {
                "project": {"capex_usd_per_kw": 950.0, "tenor_years": 15},
                "tariff": {"lkr_per_kwh": 19.50},
                ...
            }

        overrides (coming from sensitivity code):
            {
                "project": {"capex_usd_per_kw": 900.0},
                "tariff": {"lkr_per_kwh": 20.30},
            }

        result (after applying overrides):
            {
                "project": {"capex_usd_per_kw": 900.0, "tenor_years": 15},
                "tariff": {"lkr_per_kwh": 20.30},
                ...
            }

    Behaviour:
        - If the override value is a dict *and* the base config already has
          that key, we recurse and merge keys inside that branch.
        - Otherwise we simply assign the override value at that key.

    This makes it safe to:
        - tweak a single parameter under "project" without clobbering the rest
        - build overrides incrementally from multiple sources

    Args:
        config:
            The base configuration dictionary. This is mutated in-place and also
            returned for convenience so you can write:

                config = _apply_nested_overrides(config, overrides)

        overrides:
            Nested dictionary of overrides. Typically constructed in one of two ways:
                - Directly as nested dicts
                - From dotted paths that were converted earlier in the pipeline

    Returns:
        The same config dict, with overrides applied.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and key in config and isinstance(config.get(key), dict):
            # Recursive merge for nested dicts
            config[key] = _apply_nested_overrides(config[key], value)
        else:
            # Direct assignment for leaf values or new branches
            config[key] = value

    return config

    