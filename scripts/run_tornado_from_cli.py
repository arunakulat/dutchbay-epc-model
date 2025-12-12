#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

# Optional: repo-root bootstrap for local "python scripts/..." usage.
# This is a belt-and-braces helper; with the editable install of the
# package, imports should already work, but this keeps the script usable
# even before `pip install -e .`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.contracts_v14 import ParameterRangeConfig  # type: ignore[import]
from analytics.sensitivity_v14 import (  # type: ignore[import]
    SensitivityRequest,
    load_parameters_from_yaml,
    multi_metric_suite_to_dataframe,
    run,
    run_multi_metric_tornado,
    tornado_suite_to_dataframe,
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """
    Minimal CLI wrapper for v14 tornado sensitivity.

    Examples
    --------
    Single-metric tornado (project_irr)::

        python scripts/run_tornado_from_cli.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --parameters scenarios/sensitivity_parameters.yaml \\
          --metric project_irr \\
          --output out/tornado_project_irr.csv

    Multi-metric tornado::

        python scripts/run_tornado_from_cli.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --parameters scenarios/sensitivity_parameters.yaml \\
          --metric project_irr \\
          --metric equity_irr \\
          --metric dscr_min \\
          --output out/tornado_multi_metric.csv
    """
    parser = argparse.ArgumentParser(
        description="Run v14 tornado sensitivity from the command line "
        "(CASPER/GWTF-compliant wrapper around analytics.sensitivity_v14)."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to v14 scenario config YAML/JSON (e.g. scenarios/dutchbay_lendercase_2025Q4.yaml)",
    )
    parser.add_argument(
        "--parameters",
        required=True,
        help="Path to sensitivity parameters YAML (e.g. scenarios/sensitivity_parameters.yaml)",
    )
    parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        help=(
            "KPI metric name to analyze (e.g. project_irr, equity_irr, dscr_min). "
            "May be passed multiple times for multi-metric tornado. "
            "If omitted, defaults to project_irr."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional output CSV path. If omitted, CSV is written to stdout. "
            "Parent directories are created as needed."
        ),
    )

    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    config_path = args.config
    params_path = Path(args.parameters)

    # Default metric if none explicitly provided
    metrics: list[str]
    if args.metrics:
        metrics = list(args.metrics)
    else:
        metrics = ["project_irr"]

    # Load ParameterRangeConfig list from YAML via sensitivity_v14 helper
    params: list[ParameterRangeConfig] = load_parameters_from_yaml(params_path)

    # Single-metric: use CASPER front door (SensitivityRequest + run)
    if len(metrics) == 1:
        metric_name = metrics[0]
        request = SensitivityRequest(
            base_config_path=config_path,
            parameters=params,
            metric=metric_name,
        )
        suite = run(request)
        df: pd.DataFrame = tornado_suite_to_dataframe(suite)
    else:
        # Multi-metric: SensitivityRequest (+params) + run_multi_metric_tornado
        request = SensitivityRequest(
            base_config_path=config_path,
            parameters=params,
        )
        suite_multi = run_multi_metric_tornado(request, metrics=metrics)
        df = multi_metric_suite_to_dataframe(suite_multi)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"[run_tornado_from_cli] Wrote CSV to {output_path}")
    else:
        # Stream CSV to stdout (no index)
        df.to_csv(sys.stdout, index=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
