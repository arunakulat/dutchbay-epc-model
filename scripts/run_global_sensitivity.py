#!/usr/bin/env python
"""Run a GLOBAL (variance-based) sensitivity analysis on a scenario — review chunk C6.

A thin, CASPER/GWTF-compliant CLI around :mod:`analytics.sensitivity.global_sa`. Unlike the
one-way tornado (``scripts/run_multi_tech_tornado.py`` / ``analytics.sensitivity``), which is
LOCAL and cannot see driver interactions, this runs SALib **Morris** screening (cheap, ranks
drivers) or **Sobol** indices (first-order ``S1`` vs total-order ``ST`` — ``ST >> S1`` flags
interactions) over the SAME ``monte_carlo.parameters`` drivers via the canonical
``evaluate_with_overrides`` gateway. Opt-in, additive, KPI-neutral.

Examples
--------
Morris screening (default, cheap) to stdout::

    python scripts/run_global_sensitivity.py \\
      --config scenarios/dutchbay_lendercase_2025Q4.yaml --method morris

Sobol indices for one metric to a CSV (cost ~ n*(D+2) pipeline runs)::

    python scripts/run_global_sensitivity.py \\
      --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
      --method sobol --metric project_irr --n 256 --output out/global_sa.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

# Repo-root bootstrap so "python scripts/..." works before an editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.sensitivity.global_sa import DEFAULT_METRICS  # noqa: E402


def _parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Global (Morris/Sobol) sensitivity analysis.")
    p.add_argument("--config", required=True, help="Scenario YAML (with a monte_carlo.parameters block).")
    p.add_argument("--method", choices=["morris", "sobol"], default="morris",
                   help="morris = cheap screening (default); sobol = S1/ST variance decomposition.")
    p.add_argument("--metric", action="append", dest="metrics",
                   help=f"KPI to decompose (repeatable). Default: {', '.join(DEFAULT_METRICS)}.")
    p.add_argument("--n", type=int, default=None,
                   help="Sobol base sample N (default 256) or Morris trajectories (default 16).")
    p.add_argument("--output", default=None, help="CSV output path (default: stdout).")
    return p.parse_args(argv)


def _rows(result: dict) -> List[dict]:
    out: List[dict] = []
    method = result["method"]
    for metric, block in result["metrics"].items():
        for driver, vals in block["drivers"].items():
            row = {"metric": metric, "driver": driver, "method": method}
            row.update({k: round(v, 6) if isinstance(v, float) else v for k, v in vals.items()})
            out.append(row)
    return out


def main(argv: List[str] | None = None) -> int:
    args = _parse_args(argv)
    metrics = tuple(args.metrics) if args.metrics else DEFAULT_METRICS

    # CASPER: SALib is optional — fail with a clear, actionable message, not a stack trace.
    try:
        from analytics.sensitivity.global_sa import run_morris, run_sobol
        if args.method == "morris":
            result = run_morris(args.config, metrics=metrics, n_trajectories=args.n or 16)
        else:
            result = run_sobol(args.config, metrics=metrics, n=args.n or 256)
    except ImportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    import pandas as pd

    df = pd.DataFrame(_rows(result))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.output, index=False)
        print(f"Wrote {len(df)} rows to {args.output} ({result['n_runs']} pipeline evals).", file=sys.stderr)
    else:
        print(df.to_string(index=False))

    # Lender headline to stderr.
    for metric, block in result["metrics"].items():
        if args.method == "sobol":
            flag = " (INTERACTIONS present: ST >> S1)" if block.get("interactions_present") else ""
            ranked = sorted(block["drivers"], key=lambda k: block["drivers"][k]["ST"], reverse=True)
            print(f"[{metric}] total-order (ST) ranking: {ranked}{flag}", file=sys.stderr)
        else:
            print(f"[{metric}] mu_star ranking: {block['ranking']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
