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

Presets (#658): ``--preset tax`` / ``--preset dscr`` are opt-in built-in driver sets
that route through the sanctioned one-way wrappers ``analytics.sensitivity.tax.
run_tax_one_way`` / ``analytics.sensitivity.dscr.run_dscr_one_way`` (which take an
in-memory ``base_config`` mapping, so the preset path loads the YAML itself). They are
purely additive: without ``--preset`` the CLI behaves byte-identically to before,
delegating to the path-based ``run_sensitivity_analysis``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any, List, Optional, Tuple

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
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.dscr import DscrSensitivityConfig, run_dscr_one_way
from analytics.sensitivity.tax import TaxSensitivityConfig, run_tax_one_way

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


# ─────────────────────────────────────────────────────────────────────────────
# Built-in presets (#658): opt-in driver sets routed through the sanctioned one-way
# wrappers. Each driver is (config_key, label, low, high, is_absolute):
#   is_absolute=False -> low/high are pct bands around the resolved base value
#   is_absolute=True  -> low/high are absolute sweep endpoints (used where base==0,
#                        e.g. a tax_holiday_years lever whose base is 0 so a pct band
#                        would be flat — mirrors sensitivity_runner._DEFAULT_ABSOLUTE_DRIVERS).
#
# Config keys are the LIVE resolving paths verified against the canonical scenario
# schema (2026-07-02), NOT the shorthand names in the issue text (tax.corporate_rate /
# tax.holiday_years do NOT resolve; tax.corporate_tax_rate / tax.tax_holiday_years do).
# Non-resolving keys are skipped (no silent flat bars), like the default driver library.
_PresetDriver = Tuple[str, str, float, float, bool]

_TAX_PRESET_DRIVERS: Tuple[_PresetDriver, ...] = (
    ("tax.corporate_tax_rate", "Corporate Tax Rate", -20.0, 20.0, False),
    # Base is 0 years; sweep 0 -> 10 absolutely so the depreciation/loss-carryforward
    # kink (tax only bites after ~year 6) is visible rather than a flat 0->5 bar.
    ("tax.tax_holiday_years", "Tax Holiday Years", 0.0, 10.0, True),
)

# DSCR covenant preset. Under dual_dscr sizing the min-DSCR is pinned AT the target,
# so gearing / tenor bars come back structurally flat (the engine flags them, which is
# itself the lender signal "this covenant is sized, not slack"); target_dscr moves it
# 1:1. Sweeping both surfaces exactly what is pinned vs live.
_DSCR_PRESET_DRIVERS: Tuple[_PresetDriver, ...] = (
    ("Financing_Terms.target_dscr", "Target DSCR", -10.0, 10.0, False),
    ("Financing_Terms.debt_ratio", "Gearing (debt ratio)", -10.0, 10.0, False),
    ("Financing_Terms.tenor_years", "Debt Tenor", -20.0, 20.0, False),
)

# The metric each preset targets. The DSCR preset uses ``min_dscr`` — the canonical
# lender KPI key that the gateway ALWAYS emits (analytics/core/metrics.py sets both
# ``min_dscr`` and its ``dscr_min`` alias). DscrSensitivityConfig's field default is
# ``dscr_min``; the preset overrides it to ``min_dscr`` so the sweep pins to the key
# that unambiguously resolves through evaluate_with_overrides (CESSPIT fail-loud — no
# reliance on the alias, no silent KeyError path).
_TAX_PRESET_METRIC = "project_irr"
_DSCR_PRESET_METRIC = "min_dscr"


def _resolve_base_value(cfg: Mapping[str, Any], dotted_key: str) -> Optional[float]:
    """Resolve a dotted config key to its numeric base value, or None if absent/non-numeric."""
    node: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return float(node)


def _preset_parameters(
    cfg: Mapping[str, Any], drivers: Tuple[_PresetDriver, ...]
) -> List[ParameterRangeConfig]:
    """Build ``ParameterRangeConfig`` sweeps for a preset, skipping non-resolving keys.

    Skipping absent keys (rather than failing) matches the default driver library in
    ``analytics.core.sensitivity_runner`` — a driver the scenario does not carry is
    simply not swept, never a silent flat bar.
    """
    params: List[ParameterRangeConfig] = []
    for config_key, label, low, high, is_absolute in drivers:
        base = _resolve_base_value(cfg, config_key)
        if base is None:
            continue
        if is_absolute:
            params.append(
                ParameterRangeConfig(
                    variable_name=config_key,
                    base_value=base,
                    low_value=low,
                    high_value=high,
                    label=label,
                )
            )
        else:
            params.append(
                ParameterRangeConfig(
                    variable_name=config_key,
                    base_value=base,
                    low_pct=low,
                    high_pct=high,
                    label=label,
                )
            )
    return params


def _run_preset_one_way(
    preset: str,
    cfg: Mapping[str, Any],
    parameter: ParameterRangeConfig,
    metric: str,
) -> SensitivitySuite:
    """Route a single preset driver through the sanctioned one-way wrapper.

    Both wrappers take an in-memory ``base_config`` Mapping (not a path), so the caller
    has already loaded the YAML. The metric is pinned on the wrapper's config dataclass:
    ``TaxSensitivityConfig.metric_key`` for tax, ``DscrSensitivityConfig.dscr_metric_key``
    for DSCR (set to the canonical live ``min_dscr`` key, not the field's ``dscr_min``
    default — CESSPIT fail-loud on the key that unambiguously resolves).
    """
    if preset == "tax":
        return run_tax_one_way(
            base_config=cfg,
            parameter=parameter,
            cfg=TaxSensitivityConfig(metric_key=metric),
        )
    if preset == "dscr":
        return run_dscr_one_way(
            base_config=cfg,
            parameter=parameter,
            cfg=DscrSensitivityConfig(dscr_metric_key=metric),
        )
    raise ValueError(f"unknown preset {preset!r}")  # pragma: no cover


def run_preset(
    preset: str, config_path: str
) -> Tuple[str, List[ParameterRangeConfig], pd.DataFrame]:
    """Run a built-in ``tax`` / ``dscr`` preset and return (metric, params, tornado df).

    Loads the scenario YAML into an in-memory mapping (the one-way wrappers take a
    ``base_config`` Mapping, unlike the path-based default runner), builds the preset's
    driver sweeps, routes each through the sanctioned wrapper (``run_tax_one_way`` /
    ``run_dscr_one_way``), and flattens the per-driver suites into one tornado DataFrame
    via the same :func:`tornado_suite_to_dataframe` the default path uses.

    Raises:
        ValueError: if the preset resolves to no drivers for this scenario.
    """
    cfg = load_scenario_config(Path(config_path))
    if preset == "tax":
        metric = _TAX_PRESET_METRIC
        drivers = _TAX_PRESET_DRIVERS
    elif preset == "dscr":
        metric = _DSCR_PRESET_METRIC
        drivers = _DSCR_PRESET_DRIVERS
    else:  # pragma: no cover - argparse choices guard this
        raise ValueError(f"unknown preset {preset!r}")

    params = _preset_parameters(cfg, drivers)
    if not params:
        raise ValueError(
            f"preset '{preset}' resolved no drivers for config {config_path!r}; "
            "none of its config keys are present in this scenario."
        )

    frames: List[pd.DataFrame] = []
    for p in params:
        suite = _run_preset_one_way(preset, cfg, p, metric)
        frames.append(tornado_suite_to_dataframe(suite, metric, [p]))
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not df.empty:
        df = df.sort_values(
            "impact_abs", ascending=False, na_position="last"
        ).reset_index(drop=True)
    return metric, params, df


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

    Built-in tax / DSCR presets (no --parameters needed; #658)::

        python scripts/run_tornado_from_cli.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --preset dscr --output out/tornado_dscr.csv
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
        required=False,
        default=None,
        help=(
            "Path to sensitivity parameters YAML "
            "(e.g. scenarios/sensitivity_parameters_examples.yaml). "
            "Required UNLESS --preset is given (a preset supplies its own drivers)."
        ),
    )
    parser.add_argument(
        "--preset",
        choices=["tax", "dscr"],
        default=None,
        help=(
            "Built-in driver set (opt-in). 'tax' sweeps tax.corporate_tax_rate + "
            "tax.tax_holiday_years on project_irr; 'dscr' sweeps the covenant levers "
            "(target_dscr / gearing / tenor) on min_dscr. Mutually exclusive with "
            "--parameters; --metric is ignored (the preset fixes its own metric)."
        ),
    )
    parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        help=(
            "KPI metric name to analyze (e.g. project_irr, equity_irr, min_dscr). "
            "May be passed multiple times for multi-metric tornado. "
            "If omitted, defaults to project_irr. Ignored when --preset is given."
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

    # CESSPIT fail-loud: --preset and --parameters are mutually exclusive, and exactly
    # one source of drivers must be supplied — no silent default-to-example path.
    if args.preset is not None and args.parameters is not None:
        print(
            "[run_tornado_from_cli] ERROR: --preset and --parameters are mutually "
            "exclusive (a preset supplies its own drivers).",
            file=sys.stderr,
        )
        return 2
    if args.preset is None and args.parameters is None:
        print(
            "[run_tornado_from_cli] ERROR: provide --parameters <yaml> or --preset "
            "{tax,dscr}.",
            file=sys.stderr,
        )
        return 2

    if args.preset is not None:
        # Opt-in built-in preset: fixes its own metric, loads its own drivers.
        try:
            _metric, _params, df = run_preset(args.preset, config_path)
        except (ValueError, KeyError) as exc:
            print(
                f"[run_tornado_from_cli] ERROR for preset '{args.preset}': {exc}",
                file=sys.stderr,
            )
            return 2
        return _emit(df, args.output)

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

    return _emit(df, args.output)


def _emit(df: pd.DataFrame, output: str | None) -> int:
    """Write the tornado DataFrame to ``output`` (or stdout) as CSV; return exit code 0."""
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"[run_tornado_from_cli] Wrote CSV to {output_path}")
    else:
        # Stream CSV to stdout (no index)
        df.to_csv(sys.stdout, index=False)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
