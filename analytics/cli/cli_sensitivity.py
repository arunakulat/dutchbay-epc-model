"""⚠️ DEPRECATED: Use analytics/cli/cli_sensitivity_hydra.py instead.

This script uses argparse (not Hydra-compliant) and will be removed in Sprint 18.

MIGRATION PATH:

OLD (argparse):
    python analytics/cli/cli_sensitivity.py \\
        scenarios/dutchbay_lendercase_2025Q4.yaml \\
        --metric project_irr \\
        --output sensitivity_results.json

NEW (Hydra):
    python analytics/cli/cli_sensitivity_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        output_dir=_out/sensitivity \\
        write_artifacts=true

BENEFITS OF MIGRATION:
- ✅ GWTF R3 compliant (Hydra-only)
- ✅ Config-driven parameters (CCCDIR)
- ✅ Richer shock definitions
- ✅ Multiple metrics tracked
- ✅ JSON-first output (CLI-03)

CANONICAL LOCATION:
    analytics/cli/cli_sensitivity_hydra.py

REMOVAL PLANNED: Sprint 18 (Q1 2026)

Status: LEGACY (Argparse-based)
GWTF: R3 VIOLATION (Use Hydra wrapper instead)
DSGCCCG: Deprecated (Dolphins Swim Gracefully Capturing Clean Current Groups)
"""

from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import asdict
from pathlib import Path

from analytics.core.sensitivity_runner import run_sensitivity_analysis

# Issue deprecation warning on import
warnings.warn(
    "analytics.cli.cli_sensitivity is DEPRECATED and will be removed in Sprint 18. "
    "Use analytics.cli.cli_sensitivity_hydra.py instead (Hydra-based). "
    "See module docstring for migration path.",
    DeprecationWarning,
    stacklevel=2,
)


def main() -> None:
    """Legacy argparse entry point (DEPRECATED).
    
    ⚠️ DEPRECATED: Use analytics/cli/cli_sensitivity_hydra.py instead.
    This function uses argparse and violates GWTF R3 (Hydra-only).
    """
    parser = argparse.ArgumentParser(
        description="[DEPRECATED] Run sensitivity analysis for a v14 scenario. "
        "Use cli_sensitivity_hydra.py instead."
    )
    parser.add_argument("scenario", type=str, help="Path to the base scenario config.")
    parser.add_argument(
        "--metric",
        type=str,
        default="project_irr",
        help="Metric for sensitivity (default: project_irr).",
    )
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file path to save results (optional)."
    )
    args = parser.parse_args()
    
    # Print deprecation notice
    print(
        "⚠️  WARNING: cli_sensitivity.py is DEPRECATED (argparse-based).\n"
        "    Use: python analytics/cli/cli_sensitivity_hydra.py config=... instead\n"
        "    This script will be removed in Sprint 18.\n"
    )
    
    suite = run_sensitivity_analysis(args.scenario, metric=args.metric)
    result_dict = asdict(suite)
    if args.output:
        args.output.write_text(json.dumps(result_dict, indent=4))
        print(f"Sensitivity analysis results saved to {args.output}")
    else:
        print(json.dumps(result_dict, indent=4))


if __name__ == "__main__":
    main()
