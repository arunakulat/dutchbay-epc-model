from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from analytics.sensitivity_runner import run_sensitivity_analysis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run sensitivity analysis for a v14 scenario."
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
    suite = run_sensitivity_analysis(args.scenario, metric=args.metric)
    result_dict = asdict(suite)
    if args.output:
        args.output.write_text(json.dumps(result_dict, indent=4))
        print(f"Sensitivity analysis results saved to {args.output}")
    else:
        print(json.dumps(result_dict, indent=4))


if __name__ == "__main__":
    main()
