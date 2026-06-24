#!/usr/bin/env python
"""Run a per-technology tornado for a hybrid (multi-tech) scenario — Epic 6.1.

A thin, CASPER/GWTF-compliant CLI around
:func:`analytics.portfolio.multi_tech_tornado.run_multi_tech_tornado`. It loads a
multi-tech scenario (one with a ``generation.technologies`` block, e.g.
``scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml``), sweeps each technology's
finance levers (``capex_usd`` / ``capacity_factor`` / ``degradation_pct``) as
*coupled* overrides that keep the scenario reconciled (see the module docstring for
why a plain one-way sweep is a phantom/crash), and writes a flat CSV — one row per
(metric, technology, driver) — sorted by descending absolute impact within each
metric.

It also prints, to stderr, the lender headline: a per-technology volatility ranking
for each metric ("which technology drives the IRR / covenant swing"), plus a note on
any structurally flat metric (``min_dscr`` is pinned by dual-DSCR sculpting; the
covenant-stress signal lives in ``balloon_pct``).

Examples
--------
Default drivers + metrics to a CSV::

    python scripts/run_multi_tech_tornado.py \\
      --config scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml \\
      --output out/multi_tech_tornado.csv

A single metric, ±15% shocks, to stdout::

    python scripts/run_multi_tech_tornado.py \\
      --config scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml \\
      --metric project_irr --shock-pct 0.15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

# Repo-root bootstrap so "python scripts/..." works before an editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.portfolio.multi_tech_tornado import (  # noqa: E402
    DEFAULT_DRIVERS,
    DEFAULT_METRICS,
    DEFAULT_SHOCK_PCT,
    MultiTechTornadoBar,
    flat_metrics,
    impact_by_technology,
    run_multi_tech_tornado,
)
from analytics.scenario_loader import load_scenario_config  # noqa: E402

_CSV_COLUMNS = [
    "metric",
    "technology",
    "driver",
    "label",
    "base_case",
    "low_case",
    "high_case",
    "impact_abs",
    "shock_pct",
]


def bars_to_dataframe(bars: List[MultiTechTornadoBar]) -> pd.DataFrame:
    """Flatten tornado bars into a CSV-ready DataFrame (engine order preserved)."""
    rows = [
        {
            "metric": b.metric,
            "technology": b.technology,
            "driver": b.driver,
            "label": b.label,
            "base_case": b.base_case,
            "low_case": b.low_case,
            "high_case": b.high_case,
            "impact_abs": b.impact_abs,
            "shock_pct": b.shock_pct,
        }
        for b in bars
    ]
    return pd.DataFrame(rows, columns=_CSV_COLUMNS)


def _print_summary(bars: List[MultiTechTornadoBar], metrics: List[str]) -> None:
    """Print the per-technology volatility ranking + flat-metric note to stderr."""
    flat = set(flat_metrics(bars))
    print("\n=== Per-technology volatility ranking (sum of |impact| per tech) ===",
          file=sys.stderr)
    for metric in metrics:
        if metric in flat:
            continue
        ranking = impact_by_technology(bars, metric)
        ranked = "  >  ".join(f"{tech} ({impact:.6f})" for tech, impact in ranking.items())
        leader = next(iter(ranking), None)
        suffix = f"   ← {leader} drives {metric} volatility" if leader else ""
        print(f"  {metric:14s}: {ranked}{suffix}", file=sys.stderr)
    if flat:
        flat_list = ", ".join(sorted(flat))
        print(
            f"\n  NOTE: {flat_list} is structurally flat here — dual-DSCR sizing sculpts "
            "min_dscr to its target on every case, so it carries no tornado signal. "
            "Read covenant-stress from balloon_pct instead.",
            file=sys.stderr,
        )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the multi-tech tornado."""
    parser = argparse.ArgumentParser(
        description="Per-technology tornado for a hybrid scenario "
        "(which tech drives IRR / covenant volatility). CASPER/GWTF-compliant wrapper "
        "around analytics.portfolio.multi_tech_tornado."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to a multi-tech scenario YAML (with a generation.technologies block), "
        "e.g. scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml",
    )
    parser.add_argument(
        "--metric",
        action="append",
        dest="metrics",
        help="KPI to report (e.g. project_irr, equity_irr, min_dscr, balloon_pct). "
        "May be passed multiple times. Defaults to all of: "
        + ", ".join(DEFAULT_METRICS),
    )
    parser.add_argument(
        "--driver",
        action="append",
        dest="drivers",
        help="Per-tech driver to sweep (capex_usd, capacity_factor, degradation_pct). "
        "May be passed multiple times. Defaults to all of: " + ", ".join(DEFAULT_DRIVERS),
    )
    parser.add_argument(
        "--shock-pct",
        type=float,
        default=DEFAULT_SHOCK_PCT,
        help=f"Symmetric shock fraction applied to every driver (default {DEFAULT_SHOCK_PCT}).",
    )
    parser.add_argument(
        "--output",
        help="Optional output CSV path. If omitted, CSV is written to stdout. "
        "Parent directories are created as needed.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 ok, 2 on a clean input error)."""
    args = parse_args(argv)
    metrics: List[str] = list(args.metrics) if args.metrics else list(DEFAULT_METRICS)
    drivers: List[str] = list(args.drivers) if args.drivers else list(DEFAULT_DRIVERS)

    config = load_scenario_config(Path(args.config))
    try:
        bars = run_multi_tech_tornado(
            config, metrics=metrics, drivers=drivers, shock_pct=args.shock_pct
        )
    except (ValueError, KeyError) as exc:
        print(f"[run_multi_tech_tornado] ERROR: {exc}", file=sys.stderr)
        return 2

    if not bars:
        print(
            "[run_multi_tech_tornado] ERROR: no generation technologies found under "
            "generation.technologies — this CLI needs a multi-tech (hybrid) scenario.",
            file=sys.stderr,
        )
        return 2

    df = bars_to_dataframe(bars)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"[run_multi_tech_tornado] Wrote CSV to {output_path}")
    else:
        df.to_csv(sys.stdout, index=False)

    _print_summary(bars, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
