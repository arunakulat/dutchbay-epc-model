#!/usr/bin/env python
"""Run the v14 FX sensitivity surface from the command line.

A thin, CASPER/GWTF-compliant CLI wrapper around the real-engine FX sensitivity
analyzer (``analytics.fx_sensitivity_real.FXSensitivityAnalyzer.analyze_fx_sensitivity``).
It loads a scenario config, sweeps the three LIVE engine FX levers around the
scenario's own base — the USD/LKR rate (``fx.start_lkr_per_usd``), the forward
``fx.hedge_ratio`` and the forward ``fx.spread_bps`` (all wired to the cashflow engine
by the FX-forward-hedging build, #652/#666) — and emits a SINGLE JSON object to a file
or stdout (#659).

This mirrors the shape of ``scripts/run_tornado_from_cli.py``: a thin ``scripts/``
utility that wraps one library call. Per the deliberate entrypoint-policy split
(``tests/lint/test_entrypoints_hydra_only.py`` / ``test_no_argparse_anywhere.py``),
``scripts/`` tools that read one ``--config`` YAML, call one function and print
structured output are an accepted **argparse** carve-out — Hydra (which changes the
working directory and writes ``outputs/`` + ``.hydra/`` dirs) is intrusive ceremony for
a tool whose only job is to emit JSON. The canonical *pipeline* CLIs remain Hydra-only.

The JSON payload carries the three swept point series
(``fx_rate_points`` / ``hedge_ratio_points`` / ``spread_points``), each point a flat
mapping of the swept lever value and the resulting KPIs, plus the six engine-driven
linear-fit summary sensitivities (``fx_rate_irr`` / ``fx_rate_npv`` /
``hedge_ratio_irr`` / ``hedge_ratio_npv`` / ``spread_irr`` / ``spread_npv``) and the
scenario base metrics. The ``fx_rate`` IRR/NPV slopes are negative for the flat-LKR
scenarios (a weaker LKR — higher LKR-per-USD — erodes USD returns), which is the core
bankability risk this surface exists to quantify.

Notes on the spread convention (inherited from the analyzer, #659): the spread lever
bites only under an ACTIVE hedge (the engine prices a spread on the hedged fraction),
so the spread sweep runs at the scenario's own base hedge when it hedges, else at a
documented reference FULL hedge (h=1.0); ``spread`` sensitivities then read "per bp of
hedging cost, if fully hedged". A negative ``--spread-variation-bps`` fails loud (the
engine rejects negative absolute spreads — no silent clamping, CESSPIT).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, List

# Optional: repo-root bootstrap for local "python scripts/..." usage.
# Belt-and-braces — with the editable install imports already resolve, but this keeps
# the script runnable before ``pip install -e .`` (mirrors run_tornado_from_cli.py).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.fx_sensitivity_real import (  # noqa: E402
    FXSensitivityAnalyzer,
    RealFXSensitivityResult,
)
from analytics.pipeline_v14_enhanced import (  # noqa: E402
    PipelineConfigError,
    PipelineValidationError,
)

# Exceptions that mean "this scenario cannot be evaluated" — surfaced as a clean CLI
# error (exit 2), never a raw traceback (CESSPIT fail-loud). The analyzer's own guards
# raise ValueError (bad grid / negative spread band); the evaluation gateway raises the
# pipeline errors below for a missing/invalid scenario (PipelineValidationError is a bare
# Exception, NOT a ValueError, so it must be named explicitly), and a truly absent path
# raises FileNotFoundError / KeyError on a missing metric.
_SCENARIO_ERRORS = (
    ValueError,
    KeyError,
    FileNotFoundError,
    PipelineValidationError,
    PipelineConfigError,
)


def result_to_payload(result: RealFXSensitivityResult) -> dict[str, Any]:
    """Flatten a ``RealFXSensitivityResult`` into a JSON-serializable payload.

    Emits the three swept point series (each an ``asdict`` list of
    ``FXSensitivityPoint``), the six linear-fit summary sensitivities under
    ``summary_sensitivities`` (the same slopes ``calculate_summary_metrics`` fits:
    ``fx_rate_irr``/``fx_rate_npv``/``hedge_ratio_irr``/``hedge_ratio_npv``/
    ``spread_irr``/``spread_npv``), and the scenario ``base`` metrics the sweeps
    anchor on. Every leaf is a plain float / None so ``json.dumps`` needs no custom
    encoder.
    """
    return {
        "base": {
            "fx_rate": result.base_fx_rate,
            "hedge_ratio": result.base_hedge_ratio,
            "spread_bps": result.base_spread_bps,
            "project_irr": result.base_project_irr,
            "project_npv": result.base_project_npv,
            "equity_irr": result.base_equity_irr,
            "min_dscr": result.base_min_dscr,
        },
        "fx_rate_points": [asdict(p) for p in result.fx_rate_points],
        "hedge_ratio_points": [asdict(p) for p in result.hedge_ratio_points],
        "spread_points": [asdict(p) for p in result.spread_points],
        "summary_sensitivities": {
            "fx_rate_irr": result.fx_rate_irr_sensitivity,
            "fx_rate_npv": result.fx_rate_npv_sensitivity,
            "hedge_ratio_irr": result.hedge_ratio_irr_sensitivity,
            "hedge_ratio_npv": result.hedge_ratio_npv_sensitivity,
            "spread_irr": result.spread_irr_sensitivity,
            "spread_npv": result.spread_npv_sensitivity,
        },
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """Minimal CLI wrapper for the v14 FX sensitivity surface.

    Examples
    --------
    Default sweep (±10% FX, 5 steps; hedge 0..1; spread 0..+100 bps) to stdout::

        python scripts/run_fx_sensitivity.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml

    Custom grids to a file::

        python scripts/run_fx_sensitivity.py \\
          --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
          --fx-variation-pct 15 --fx-steps 7 \\
          --spread-variation-bps 150 --spread-steps 4 \\
          --output out/fx_sensitivity.json
    """
    parser = argparse.ArgumentParser(
        description="Run the v14 FX sensitivity surface from the command line "
        "(CASPER/GWTF-compliant wrapper around "
        "analytics.fx_sensitivity_real.FXSensitivityAnalyzer)."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to v14 scenario config YAML/JSON "
        "(e.g. scenarios/dutchbay_lendercase_2025Q4.yaml).",
    )
    parser.add_argument(
        "--fx-variation-pct",
        type=float,
        default=10.0,
        help="Relative FX-rate band around the scenario base rate, in percent "
        "(default: 10.0 -> sweep base*[0.90 .. 1.10]).",
    )
    parser.add_argument(
        "--fx-steps",
        type=int,
        default=5,
        help="Number of FX-rate sweep points (default: 5).",
    )
    parser.add_argument(
        "--spread-variation-bps",
        type=float,
        default=100.0,
        help="Upward spread band in basis points, swept as deltas from the scenario "
        "base fx.spread_bps (default: 100.0). Must be >= 0 (the engine rejects "
        "negative absolute spreads).",
    )
    parser.add_argument(
        "--spread-steps",
        type=int,
        default=5,
        help="Number of spread sweep points (default: 5).",
    )
    parser.add_argument(
        "--output",
        help="Optional output JSON path. If omitted, JSON is written to stdout. "
        "Parent directories are created as needed.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    # Fail loud on a bad grid BEFORE touching the engine (CESSPIT): a non-positive
    # step count would make the underlying np.linspace degenerate or empty, and the
    # analyzer's own guard rejects a negative spread band with the offending arg named.
    if args.fx_steps < 2 or args.spread_steps < 2:
        print(
            "[run_fx_sensitivity] ERROR: --fx-steps and --spread-steps must each be "
            ">= 2 (a linear-fit slope needs at least two swept points).",
            file=sys.stderr,
        )
        return 2

    analyzer = FXSensitivityAnalyzer(base_config_path=args.config)
    try:
        result = analyzer.analyze_fx_sensitivity(
            fx_variation_pct=args.fx_variation_pct,
            fx_steps=args.fx_steps,
            spread_variation_bps=args.spread_variation_bps,
            spread_steps=args.spread_steps,
        )
    except _SCENARIO_ERRORS as exc:
        # The analyzer fails loud on a bad scenario / metric / negative spread band; we
        # surface that as a clean CLI error (exit 2) rather than a raw traceback.
        print(f"[run_fx_sensitivity] ERROR: {exc}", file=sys.stderr)
        return 2

    return _emit(result_to_payload(result), args.output)


def _emit(payload: dict[str, Any], output: str | None) -> int:
    """Write the FX-sensitivity ``payload`` to ``output`` (or stdout) as JSON; return 0."""
    text = json.dumps(payload, indent=2)
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text + "\n")
        print(f"[run_fx_sensitivity] Wrote JSON to {output_path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
