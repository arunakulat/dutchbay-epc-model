#!/usr/bin/env python
"""Run v14 tornado sensitivity from the command line.

A thin, CASPER/GWTF-compliant CLI wrapper around the canonical sensitivity engine
(``analytics.core.sensitivity_runner.run_sensitivity_analysis`` ->
``analytics.sensitivity.engine``). It loads a scenario config and a YAML list of
one-way parameter sweeps, runs a tornado for one or more KPI metrics, and writes a
flat CSV (one row per parameter shock) to a file or stdout.

History: this script previously imported six symbols from the now-deprecated
``analytics.sensitivity_v14`` star-import shim (``SensitivityRequest``, ``run``,
``run_multi_metric_tornado``, ``load_parameters_from_yaml``,
``tornado_suite_to_dataframe``, ``multi_metric_suite_to_dataframe``). None of those
were exported by the shim any more, so the script raised ``ImportError`` on import.
It is repointed here to the live API; the YAML loader and the tornado->DataFrame
flattener are implemented locally (the engine returns typed contracts, not frames).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any, List

import pandas as pd
import yaml

# Optional: repo-root bootstrap for local "python scripts/..." usage.
# This is a belt-and-braces helper; with the editable install of the
# package, imports should already work, but this keeps the script usable
# even before `pip install -e .`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.core.sensitivity_runner import run_sensitivity_analysis

# Keys under which a parameter list may be nested in the YAML (besides a bare list).
_PARAM_LIST_KEYS = ("parameters", "standard_suite", "drivers")


def load_parameters_from_yaml(path: Path) -> List[ParameterRangeConfig]:
    """Load a list of ``ParameterRangeConfig`` from a sensitivity-parameters YAML.

    Accepts either a top-level list of parameter mappings, or a mapping that either
    (a) carries the list under ``parameters``/``standard_suite``/``drivers``, or
    (b) has exactly one list-valued entry (e.g. the ``standard_suite:`` block in
    ``scenarios/sensitivity_parameters_examples.yaml``). Each item is a mapping of
    ``ParameterRangeConfig`` fields; ``variable_name`` and ``base_value`` are
    required, the rest (``low_pct``/``high_pct`` or ``low_value``/``high_value``,
    ``label``, ``points``) are optional.
    """
    raw = yaml.safe_load(path.read_text())

    items: Any
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, Mapping):
        items = next((raw[k] for k in _PARAM_LIST_KEYS if k in raw), None)
        if items is None:
            list_vals = [v for v in raw.values() if isinstance(v, list)]
            if len(list_vals) != 1:
                raise ValueError(
                    f"{path}: could not locate a single parameter list; expected a "
                    f"top-level list, one of {_PARAM_LIST_KEYS}, or exactly one "
                    f"list-valued key (found {len(list_vals)})."
                )
            items = list_vals[0]
    else:
        raise ValueError(
            f"{path}: expected a YAML list or mapping, got {type(raw).__name__}."
        )

    allowed = {f.name for f in fields(ParameterRangeConfig)}
    params: List[ParameterRangeConfig] = []
    for i, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"{path}: parameter #{i} is not a mapping ({item!r}).")
        unknown = set(item) - allowed
        if unknown:
            raise ValueError(
                f"{path}: parameter #{i} has unknown keys {sorted(unknown)}; "
                f"allowed keys are {sorted(allowed)}."
            )
        params.append(ParameterRangeConfig(**dict(item)))

    if not params:
        raise ValueError(f"{path}: no parameters found.")
    return params


def tornado_suite_to_dataframe(
    suite: SensitivitySuite, metric: str, params: List[ParameterRangeConfig]
) -> pd.DataFrame:
    """Flatten a single-metric ``SensitivitySuite`` into a tornado DataFrame.

    One row per parameter, sorted by descending absolute impact (tornado
    convention). Columns: metric, variable_name, label, base_case, low_case,
    high_case, impact_abs.

    The engine emits exactly one ``TornadoResult`` per input parameter, in order
    (it raises rather than silently dropping an unresolved path), so we zip the
    original ``params`` back in to recover both the raw config path
    (``variable_name``) and the human ``label`` — the contract stamps only one of
    those onto the result. ``base_metric`` is the KPI's base value; ``low_case`` /
    ``high_case`` come from the parameter's low/high shock; ``impact_abs`` is the
    engine's tornado-bar magnitude (high-minus-low swing of the KPI).
    """
    results = list(suite.tornado_results)
    rows: List[dict[str, Any]] = []
    for idx, tr in enumerate(results):
        param = params[idx] if idx < len(params) else None
        variable_name = (
            param.variable_name if param is not None else (tr.label or tr.metric_name)
        )
        label = (param.label if param is not None else None) or variable_name
        shock = tr.shock_results[0] if tr.shock_results else None
        rows.append(
            {
                "metric": metric,
                "variable_name": variable_name,
                "label": label,
                "base_case": tr.base_metric,
                "low_case": shock.low_case if shock is not None else None,
                "high_case": shock.high_case if shock is not None else None,
                "impact_abs": tr.impact_abs,
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            "impact_abs", ascending=False, na_position="last"
        ).reset_index(drop=True)
    return df


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """Minimal CLI wrapper for v14 tornado sensitivity.

    Examples
    --------
    Single-metric tornado (project_irr)::

        python scripts/run_tornado_from_cli.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --parameters scenarios/sensitivity_parameters_examples.yaml \\
          --metric project_irr \\
          --output out/tornado_project_irr.csv

    Multi-metric tornado::

        python scripts/run_tornado_from_cli.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --parameters scenarios/sensitivity_parameters_examples.yaml \\
          --metric project_irr \\
          --metric equity_irr \\
          --metric min_dscr \\
          --output out/tornado_multi_metric.csv
    """
    parser = argparse.ArgumentParser(
        description="Run v14 tornado sensitivity from the command line "
        "(CASPER/GWTF-compliant wrapper around analytics.sensitivity)."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to v14 scenario config YAML/JSON (e.g. scenarios/dutchbay_lendercase_2025Q4.yaml)",
    )
    parser.add_argument(
        "--parameters",
        required=True,
        help="Path to sensitivity parameters YAML (e.g. scenarios/sensitivity_parameters_examples.yaml)",
    )
    parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        help=(
            "KPI metric name to analyze (e.g. project_irr, equity_irr, min_dscr). "
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
    metrics: list[str] = list(args.metrics) if args.metrics else ["project_irr"]

    # Load the explicit one-way parameter sweeps from YAML.
    params = load_parameters_from_yaml(params_path)

    # Run a tornado per requested metric and stack the results. The canonical
    # single-metric runner loads the scenario, evaluates the base case once and
    # builds one TornadoResult per parameter; looping gives true multi-metric
    # output with a distinguishing ``metric`` column. The engine raises ValueError
    # for a parameter whose path is absent from the config (a "silent flat bar"); we
    # surface that as a clean CLI error rather than a traceback.
    frames: list[pd.DataFrame] = []
    for metric_name in metrics:
        try:
            suite = run_sensitivity_analysis(
                config_path, metric=metric_name, parameters=params
            )
        except (ValueError, KeyError) as exc:
            print(
                f"[run_tornado_from_cli] ERROR for metric '{metric_name}': {exc}",
                file=sys.stderr,
            )
            return 2
        frames.append(tornado_suite_to_dataframe(suite, metric_name, params))

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

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
