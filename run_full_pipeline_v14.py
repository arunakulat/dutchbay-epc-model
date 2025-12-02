#!/usr/bin/env python3
"""
v14 full-pipeline runner – config in, complete result out.

This script is the canonical entry point for the v14 finance engine::

    python run_full_pipeline_v14.py config=scenarios/dutchbay_lendercase_2025Q4.yaml

Architecture (Go With The Flow)
--------------------------------
This pipeline calls the v14 finance engine directly, ensuring a single source
of truth for all calculations:

1. Config → schema_guard.validate_config_for_v14 (R15: defensive validation)
2. Config → finance.cashflow_v14.build_annual_rows (R7: canonical cashflow)
3. Config + annual_rows → finance.debt_v14.apply_debt_layer (R7: canonical debt)
4. All inputs → analytics.core.metrics.calculate_scenario_kpis (R7: canonical KPIs)

Returns: {config, config_path, validation_mode, annual_rows, debt_result, kpis}

This is the FULL output pipeline. For KPI-only analytics (Monte Carlo, sensitivity),
use analytics.evaluate_scenario.evaluate_with_overrides directly.

Typical usage
-------------
CLI (Hydra)::

    python run_full_pipeline_v14.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        validation_mode=strict \\
        validation_modules=cashflow,debt

Programmatic::

    from run_full_pipeline_v14 import run_v14_pipeline

    result = run_v14_pipeline(
        config="scenarios/dutchbay_lendercase_2025Q4.yaml",
        validation_mode="strict",
    )

    # Access full output
    annual_rows = result["annual_rows"]  # List of annual cashflow dicts
    debt_result = result["debt_result"]  # Debt metrics dict
    project_irr = result["kpis"]["project_irr"]  # KPI scalar

Go With The Flow Compliance
----------------------------
R7:  IRR/NPV calculations centralized in finance.irr (singleton)
R15: Schema guard validates before finance engine (defensive)
R22: FX compliance enforced via schema_guard
Data flow: config → validation → cashflow → debt → metrics (canonical path)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


def run_v14_pipeline(
    config: str,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the v14 engine for a single scenario config path.

    This is the canonical pipeline orchestrator. It calls the finance engine
    directly and returns the complete result structure.

    For KPI-only output (Monte Carlo, sensitivity analysis), use
    analytics.evaluate_scenario.evaluate_with_overrides instead.

    Parameters
    ----------
    config : str
        Path to YAML/JSON scenario file, e.g.,
        "scenarios/dutchbay_lendercase_2025Q4.yaml".
    validation_mode : {"strict", "off"}, default="strict"
        Pre-flight schema validation mode.
        - "strict": run schema guard before evaluation (recommended for production)
        - "off": skip schema guard (use only for debugging/trusted configs)
    validation_modules : list[str] or None, optional
        Modules to validate. Defaults to ["cashflow", "debt"].
        Available modules: ["cashflow", "debt", "tax", "fx"]

    Returns
    -------
    dict[str, Any]
        Complete pipeline result with keys:
        - validation_mode: str, effective validation mode used
        - config_path: str, path to config file
        - config: dict, loaded raw config
        - annual_rows: list[dict], annual cashflow rows (20+ years typical)
        - debt_result: dict, debt metrics (dscr_series, max_debt_usd, etc.)
        - kpis: dict, aggregated KPIs (project_npv, project_irr, equity_irr, etc.)

    Raises
    ------
    ValueError
        If validation_mode is not "strict" or "off".
    ConfigValidationError
        If strict mode enabled and config fails validation.
    FileNotFoundError
        If config file does not exist.

    Examples
    --------
    Basic usage with strict validation::

        result = run_v14_pipeline(
            config="scenarios/dutchbay_lendercase_2025Q4.yaml",
            validation_mode="strict",
        )
        print(f"Project IRR: {result['kpis']['project_irr']:.2%}")
        print(f"Min DSCR: {result['debt_result']['dscr_min']:.2f}x")

    Skip validation for debugging::

        result = run_v14_pipeline(
            config="scenarios/test_config.yaml",
            validation_mode="off",
        )

    Custom validation modules::

        result = run_v14_pipeline(
            config="scenarios/example.yaml",
            validation_modules=["cashflow", "debt", "tax", "fx"],
        )
    """
    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: {validation_mode!r}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Load config
    # ─────────────────────────────────────────────────────────────────────────
    cfg = load_scenario_config(config)
    logger.debug("Loaded config from: %s", config)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Pre-flight validation (R15: Schema guard defense)
    # ─────────────────────────────────────────────────────────────────────────
    if mode == "strict":
        modules = validation_modules or ["cashflow", "debt"]
        validate_config_for_v14(
            raw_config=cfg,
            config_path=config,
            modules=modules,
        )
        logger.info("✓ Schema validation passed for modules: %s", ", ".join(modules))
    else:
        logger.warning(
            "Validation SKIPPED (mode='off'). Use only for debugging/trusted configs."
        )

    # ═════════════════════════════════════════════════════════════════════════
    # 3. Canonical v14 finance engine (Sprint 6 - Single Source of Truth)
    # ═════════════════════════════════════════════════════════════════════════
    # ARCHITECTURE:
    # This pipeline calls the same three functions used by all v14 entry points,
    # ensuring consistent calculations across CLI, API, analytics, and tests.
    #
    # Go With The Flow Principles:
    # - R7:  All IRR/NPV calculations via finance.irr singleton
    # - R22: All FX conversions via config["fx"] mapping
    # - Data flow: config → cashflow → debt → metrics (canonical path)
    # - No duplication: evaluate_with_overrides calls same functions
    # ═════════════════════════════════════════════════════════════════════════

    from analytics.core.metrics import calculate_scenario_kpis
    from finance.cashflow_v14 import build_annual_rows
    from finance.debt_v14 import apply_debt_layer

    # Step 3a: Build annual cashflow rows
    annual_rows: list[dict[str, Any]] = build_annual_rows(cfg)
    logger.info("Built %d annual cashflow rows", len(annual_rows))

    # Step 3b: Apply debt layer
    debt_result: dict[str, Any] = apply_debt_layer(cfg, annual_rows)
    logger.info(
        "Debt layer complete: max_debt=%.2fM, dscr_min=%.2fx",
        debt_result.get("max_debt_usd", 0) / 1e6,
        debt_result.get("dscr_min", 0),
    )

    # Step 3c: Calculate aggregated KPIs
    kpis: dict[str, Any] = calculate_scenario_kpis(
        config=cfg,
        annual_rows=annual_rows,
        debt_result=debt_result,
        discount_rate=0.10,  # Default WACC; could extract from config["wacc"]
    )
    logger.info(
        "KPIs calculated: project_irr=%.2f%%, equity_irr=%.2f%%",
        kpis.get("project_irr", 0) * 100,
        kpis.get("equity_irr", 0) * 100,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Package complete result
    # ─────────────────────────────────────────────────────────────────────────
    result: dict[str, Any] = {
        "config": cfg,
        "config_path": config,
        "validation_mode": mode,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
    }

    logger.info(
        "✓ Pipeline complete: %d rows, %d debt metrics, %d KPIs",
        len(annual_rows),
        len(debt_result),
        len(kpis),
    )

    return result


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="run_full_pipeline_v14",
)
def cli(cfg: DictConfig) -> None:
    """
    Hydra CLI entry point for v14 pipeline.

    Usage
    -----
    Basic (strict validation, default modules)::

        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml

    Custom validation modules::

        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            validation_mode=strict \\
            validation_modules=cashflow,debt,tax,fx

    Skip validation (debugging only)::

        python run_full_pipeline_v14.py \\
            config=scenarios/test_config.yaml \\
            validation_mode=off

    Output
    ------
    Prints complete result as JSON to stdout. Suitable for:
    - CI/CD pipelines (pipe to jq, store as artifact)
    - Integration with dashboards (parse JSON)
    - Debugging (inspect annual_rows, debt_result, kpis)

    Exit codes::

        0: Success
        1: Config validation failed (if validation_mode=strict)
        2: Finance engine error (calculation failure)
    """
    # Undo Hydra's job-chdir so relative scenario paths still work from repo root.
    os.chdir(_ORIG_CWD)

    config = cfg.get("config")
    if not config:
        raise SystemExit(
            "Missing required 'config' parameter.\n\n"
            "Usage:\n"
            "  python run_full_pipeline_v14.py "
            "config=scenarios/dutchbay_lendercase_2025Q4.yaml\n\n"
            "Optional parameters:\n"
            "  validation_mode=strict|off (default: strict)\n"
            "  validation_modules=cashflow,debt,tax,fx (default: cashflow,debt)\n\n"
            "Examples:\n"
            "  python run_full_pipeline_v14.py config=scenarios/example.yaml\n"
            "  python run_full_pipeline_v14.py config=scenarios/example.yaml "
            "validation_mode=off\n"
        )

    validation_mode = cfg.get("validation_mode", "strict")

    # Parse validation_modules (support both CSV string and list)
    modules_raw = cfg.get("validation_modules", None)
    if isinstance(modules_raw, str):
        validation_modules = [m.strip() for m in modules_raw.split(",") if m.strip()]
    elif modules_raw is None:
        validation_modules = None
    else:
        # Allow list-style overrides: validation_modules=[cashflow,debt]
        validation_modules = list(modules_raw)

    # Run pipeline
    try:
        result = run_v14_pipeline(
            config=str(config),
            validation_mode=str(validation_mode),
            validation_modules=validation_modules,
        )
    except Exception as exc:
        logger.exception("Pipeline execution failed")
        raise SystemExit(f"ERROR: {exc}") from exc

    # Emit JSON for CI/tooling/debugging
    # Note: annual_rows can be large (20+ years × many fields)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))

    logger.info("✓ Pipeline execution complete (see JSON output above)")


if __name__ == "__main__":
    cli()

# EOF
