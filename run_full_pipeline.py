#!/usr/bin/env python3
"""v14 pipeline entrypoint for DutchBay EPC model.

This module provides a single, testable function:

    run_v14_pipeline(config: str, validation_mode: str = "strict") -> dict

which:

    • Loads a v14-compatible scenario config via `analytics.scenario_loader`.
    • Runs the v14 cashflow + debt stack (`dutchbay_v14chat.finance.*`).
    • Computes KPIs via `analytics.core.metrics.calculate_scenario_kpis`.
    • Returns a structured result dict for tests and CLI use.

It does NOT:

    • Import or call any v13 modules.
    • Implement its own FX logic or defaults.
    • Execute anything on import (safe for pytest).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List, Sequence

from analytics.scenario_loader import load_scenario_config
from analytics.core.metrics import calculate_scenario_kpis
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer


def _extract_cfads_usd(annual_rows: Sequence[Dict[str, Any]]) -> List[float]:
    """Extract CFADS in USD from annual rows.

    This mirrors how the metrics module expects CFADS, but keeps the
    function self-contained and explicit for debugging/tests.
    """
    return [float(row.get("cfads_usd", 0.0) or 0.0) for row in annual_rows]


def run_v14_pipeline(config: str, validation_mode: str = "strict") -> Dict[str, Any]:
    """Run the v14 cashflow + debt pipeline for a single scenario.

    Parameters
    ----------
    config:
        Path to the scenario config file (YAML or JSON). In CI/tests this
        is typically something under `scenarios/`, e.g.:

            "scenarios/dutchbay_lendercase_2025Q4.yaml"

    validation_mode:
        Placeholder for future strict/relaxed validation modes. Accepted
        for API compatibility; currently not wired into the finance
        modules but returned in the result payload.

    Returns
    -------
    Dict[str, Any]
        A structured result containing:

        {
            "config_path": "<absolute path to config>",
            "validation_mode": "<validation_mode>",
            "config": <normalized config dict>,
            "annual_rows": <list[dict]>,
            "debt_result": <dict>,
            "kpis": <dict from calculate_scenario_kpis>,
        }
    """
    path = Path(config)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # 1. Load and normalise config (v13/v14 compatible but v14 is canonical)
    cfg = load_scenario_config(str(path))

    # 2. Build v14 annual cashflows
    annual_rows = build_annual_rows(cfg)

    # 3. Apply the v14 debt layer
    debt_result = apply_debt_layer(cfg, annual_rows)

    # 4. Extract CFADS series (USD) from annual rows
    cfads_series_usd = _extract_cfads_usd(annual_rows)

    # 5. Compute KPIs using the shared metrics engine
    kpis = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=cfg,
        cfads_series_usd=cfads_series_usd,
    )

    return {
        "config_path": str(path.resolve()),
        "validation_mode": validation_mode,
        "config": cfg,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
    }


def _cli_main() -> None:
    """CLI wrapper for manual runs.

    This is deliberately thin and just pretty-prints a small subset of
    the result; full reporting belongs in analytics/export layers.
    """
    parser = argparse.ArgumentParser(
        description="Run the v14 cashflow + debt pipeline for a single scenario file."
    )
    parser.add_argument(
        "--config",
        "-c",
        default="scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to a v14 scenario config (YAML or JSON).",
    )
    parser.add_argument(
        "--validation-mode",
        "-m",
        default="strict",
        help="Validation mode (reserved for future use).",
    )
    args = parser.parse_args()

    result = run_v14_pipeline(
        config=args.config,
        validation_mode=args.validation_mode,
    )

    kpis = result["kpis"]
    print(f"Config: {result['config_path']}")
    print(f"Validation mode: {result['validation_mode']}")
    print("\nCore KPIs (from v14 pipeline, USD-based):")
    for key in ("npv", "irr", "dscr_min", "dscr_mean", "dscr_max"):
        print(f"  {key}: {kpis.get(key)}")


if __name__ == "__main__":
    _cli_main()
