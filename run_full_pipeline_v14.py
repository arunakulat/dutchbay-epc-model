#!/usr/bin/env python3
"""
v14 full-pipeline runner – config in, KPIs out.

This script is the simplest “one-liner” entry point for the v14 engine:

    python run_full_pipeline_v14.py scenarios/example_a.yaml

What it actually does under the hood:

1. Loads the YAML/JSON config using the central loader
   (analytics.scenario_loader.load_scenario_config).
2. Optionally runs a schema guard over the raw config to catch missing or
   obviously broken fields before any heavy finance logic runs.
3. Calls analytics.evaluate_scenario.evaluate_with_overrides, which:
   - Re-loads the config for safety,
   - Runs the v14 finance stack under finance.cashflow_v14 / finance.debt_v14 /
     finance.wacc_v14 / analytics.core.metrics, and
   - Returns a flat dict of KPIs suitable for CLI/CI/JSON export.

Typical usage patterns
----------------------

CLI (human):

    python run_full_pipeline_v14.py scenarios/full_model_variables_updated.yaml

CI / programmatic:

    from run_full_pipeline_v14 import run_v14_pipeline

    result = run_v14_pipeline(
        config="scenarios/full_model_variables_updated.yaml",
        validation_mode="strict",
    )
    project_irr = result["project_irr"]

The cost of loading the config twice (schema guard + evaluation) is tiny
compared to a full analytics run and keeps the pre-flight validation logic
explicit at this boundary.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

app = typer.Typer(
    help=(
        "Run the v14 Dutch Bay EPC finance engine on a single scenario config "
        "and emit KPIs as JSON."
    ),
    no_args_is_help=True,
)


def run_v14_pipeline(
    config: str,
    validation_mode: str = "strict",
) -> dict[str, Any]:
    """
    Run the v14 engine for a single scenario config path.

    This is the function that tests and CI should import.

    Args:
        config:
            Path to the YAML/JSON scenario file, e.g.
            "scenarios/full_model_variables_updated.yaml".
        validation_mode:
            - "strict": run a pre-flight schema guard over the raw config
              before doing *any* finance work.
            - "off": skip the schema guard and go straight to evaluation.

    Returns:
        A flat dict of KPIs and metadata, as returned by
        analytics.evaluate_scenario.evaluate_with_overrides.

    Example:
        >>> result = run_v14_pipeline("scenarios/example_a.yaml")
        >>> round(result["project_irr"], 4)
        0.1234
    """
    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: {validation_mode!r}"
        )

    # 1) Pre-flight: light-weight schema validation on the raw config
    cfg = load_scenario_config(config)

    if mode == "strict":
        # For now we always validate the cashflow surface. You can extend the
        # modules list later (e.g. ["cashflow", "debt", "wacc"]) once those
        # modules register their own RequiredFieldSpecs.
        validate_config_for_v14(
            raw_config=cfg,
            config_path=config,
            modules=["cashflow"],
        )

    # 2) Full evaluation: this will reload the config and run the v14 stacks
    #    under finance.cashflow_v14 / finance.debt_v14 / analytics.core.metrics.
    return evaluate_with_overrides(config, {})


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
            "'strict' (default) runs analytics.schema_guard.validate_config_for_v14 "
            "before evaluation; 'off' skips the guard."
        ),
    ),
) -> None:
    """
    CLI entry point.

    Example:
        $ python run_full_pipeline_v14.py scenarios/example_a.yaml \\
              --validation-mode strict
    """
    result = run_v14_pipeline(
        config=config,
        validation_mode=validation_mode,
    )

    # Emit deterministic, machine-friendly JSON for CI and downstream tools.
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()

# EOF
