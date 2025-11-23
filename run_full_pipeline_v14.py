#!/usr/bin/env python3
"""Backward-compatible v14 pipeline entrypoint.

This module is a thin shim around the v14 scenario evaluator in
:mod:`analytics.evaluate_scenario`.

It provides:
- run_v14_pipeline(config: str, validation_mode: str = "strict") -> dict
  which is what tests and existing scripts import, plus a very small CLI
  for manual runs.

Design constraints
------------------
- No imports from ``dutchbay_v14chat`` (v14 engine lives under finance.*).
- Safe to import under pytest / mypy (no side effects on import).
- Does not attempt to be a multi-mode runner; higher-level orchestration
  belongs in :mod:`run_full_pipeline` and analytics.* modules.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict

from analytics.evaluate_scenario import evaluate_scenario_as_dict


def run_v14_pipeline(config: str, validation_mode: str = "strict") -> Dict[str, Any]:
    """Run the v14 pipeline for a single scenario and return a dict.

    Parameters
    ----------
    config : str
        Path to the scenario config file (YAML or JSON).
    validation_mode : str
        Logical validation mode: "strict" or "relaxed".

    Returns
    -------
    Dict[str, Any]
        Scenario evaluation results including NPV, IRR, DSCR, WACC, etc.
    """
    # FIX: Use config_path not config
    return evaluate_scenario_as_dict(
        config_path=config,
        validation_mode=validation_mode,
    )


def main() -> None:
    """CLI entrypoint for manual testing."""
    parser = argparse.ArgumentParser(
        description="Run DutchBay v14 pipeline for a single scenario"
    )
    parser.add_argument(
        "config",
        type=str,
        help="Path to scenario config (YAML or JSON)",
    )
    parser.add_argument(
        "--validation-mode",
        type=str,
        default="strict",
        choices=["strict", "relaxed"],
        help="Config validation mode (default: strict)",
    )

    args = parser.parse_args()

    result = run_v14_pipeline(
        config=args.config,
        validation_mode=args.validation_mode,
    )

    print(f"✓ Scenario: {result['scenario_name']}")
    print(f"  NPV: ${result['project_npv']/1e6:.2f}M")
    print(f"  IRR: {result['project_irr']*100:.2f}%")
    print(f"  Min DSCR: {result['min_dscr']:.2f}x")
    print(f"  Discount rate: {result['discount_rate_used']*100:.2f}%")
    
    if result.get("wacc"):
        wacc = result["wacc"]
        print(f"  WACC mode: {wacc.get('mode', 'N/A')}")
        print(f"  WACC nominal: {wacc.get('wacc_nominal', 0)*100:.2f}%")
        if wacc.get("wacc_real") is not None:
            print(f"  WACC real: {wacc['wacc_real']*100:.2f}%")


if __name__ == "__main__":
    main()
