#!/usr/bin/env python3
"""
v14 full-pipeline runner – config in, KPIs out.

This script is the simplest entry point for the v14 engine::

    python run_full_pipeline_v14.py scenarios/example_a.yaml

What it does
------------
1. Loads YAML/JSON config via analytics.scenario_loader
2. Runs pre-flight schema validation (optional)
3. Calls analytics.evaluate_scenario.evaluate_with_overrides
4. Returns flat dict of KPIs suitable for CLI/CI/JSON export

Typical usage
-------------
CLI::

    python run_full_pipeline_v14.py scenarios/example_a.yaml

Programmatic::

    from run_full_pipeline_v14 import run_v14_pipeline

    result = run_v14_pipeline(
        config="scenarios/example_a.yaml",
        validation_mode="strict",
    )
    project_irr = result["kpis"]["project_irr"]
"""

from __future__ import annotations

import json
import logging
from typing import Any

import typer

from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

logger = logging.getLogger(__name__)

app = typer.Typer(
    help=(
        "Run the v14 Dutch Bay EPC finance engine on a single scenario "
        "config and emit KPIs as JSON."
    ),
    no_args_is_help=True,
)


def run_v14_pipeline(
    config: str,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the v14 engine for a single scenario config path.

    Parameters
    ----------
    config : str
        Path to YAML/JSON scenario file, e.g.,
        "scenarios/full_model_variables_updated.yaml".
    validation_mode : {"strict", "off"}, default="strict"
        Pre-flight schema validation mode.
        - "strict": run schema guard before evaluation
        - "off": skip schema guard
    validation_modules : list[str] or None, optional
        Modules to validate. Defaults to ["cashflow", "debt"].

    Returns
    -------
    dict[str, Any]
        ScenarioResult-like dict with keys:
        - validation_mode: effective mode used
        - config_path: config path string
        - config: loaded raw config dict
        - annual_rows: list of annual cashflow rows
        - debt_result: dict of debt metrics
        - kpis: dict of KPI fields (project_npv, project_irr, etc.)

    Raises
    ------
    ValueError
        If validation_mode is not "strict" or "off".
    ConfigValidationError
        If strict mode and config fails validation.
    """
    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: " f"{validation_mode!r}"
        )

    # 1. Load config
    cfg = load_scenario_config(config)

    # 2. Pre-flight validation
    if mode == "strict":
        modules = validation_modules or ["cashflow", "debt"]
        validate_config_for_v14(
            raw_config=cfg,
            config_path=config,
            modules=modules,
        )
        logger.info("Schema validation passed for modules: %s", ", ".join(modules))

    # 3. Full evaluation
    raw_result = evaluate_with_overrides(config, {})

    # 4. Normalize result to dict
    if not isinstance(raw_result, dict):
        raise TypeError(
            f"evaluate_with_overrides must return dict, "
            f"got {type(raw_result).__name__}"
        )

    result: dict[str, Any] = dict(raw_result)

    # 5. Attach metadata
    result.setdefault("config", cfg)
    result.setdefault("config_path", config)
    result["validation_mode"] = mode

    # 6. Ensure structural keys
    result.setdefault("annual_rows", [])
    result.setdefault("debt_result", {})

    # 7. Normalize KPIs
    if "kpis" not in result or not isinstance(result["kpis"], dict):
        # If no nested kpis dict, treat entire result as KPIs
        result["kpis"] = {
            k: v
            for k, v in result.items()
            if k
            not in {
                "config",
                "config_path",
                "validation_mode",
                "annual_rows",
                "debt_result",
            }
        }

    return result


@app.command()
def main(
    config: str = typer.Argument(
        ...,
        help="Path to YAML/JSON scenario config (e.g. scenarios/example_a.yaml).",
    ),
    validation_mode: str = typer.Option(
        "strict",
        "--validation-mode",
        "-m",
        case_sensitive=False,
        help=(
            "Pre-flight schema validation mode. "
            "'strict' (default) runs schema guard; 'off' skips it."
        ),
    ),
    validation_modules: str = typer.Option(
        None,
        "--modules",
        help=(
            "Comma-separated list of modules to validate, e.g. "
            "'cashflow,debt'. Defaults to 'cashflow,debt'."
        ),
    ),
) -> None:
    """
    CLI entry point.

    Example
    -------
    $ python run_full_pipeline_v14.py scenarios/example_a.yaml \\
          --validation-mode strict --modules cashflow,debt
    """
    modules_list = (
        [m.strip() for m in validation_modules.split(",")]
        if validation_modules
        else None
    )

    result = run_v14_pipeline(
        config=config,
        validation_mode=validation_mode,
        validation_modules=modules_list,
    )

    # Emit JSON for CI/tooling
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
# EOF
