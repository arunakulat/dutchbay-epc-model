#!/usr/bin/env python
"""Run the EPC construction-margin model for an ``epc`` scenario.

A thin CASPER/GWTF-compliant CLI around
:func:`finance.epc_margin.compute_epc_margin`. It loads a scenario YAML carrying an
``epc`` block (e.g. ``scenarios/kolonnawa_epc_100mw.yaml``) and prints the
construction-margin economics — total cost, gross margin, return-on-cost, peak working
capital, and an annualised construction IRR (when defined).

This is a SEPARATE path from the operational v14 cashflow engine: an EPC supply contract
is a construction-margin deal, not an operational CFADS stream, so the scenario is read
with a plain YAML loader (no operational schema validation).

Example::

    python scripts/run_epc_margin.py --config scenarios/kolonnawa_epc_100mw.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from finance.epc_margin import compute_epc_margin  # noqa: E402


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EPC construction-margin model (e.g. the Kolonnawa BESS EPC)."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to a scenario YAML carrying an `epc` block.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 2 on a clean input error."""
    args = parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text())
    if not isinstance(config, dict):
        print(
            f"[run_epc_margin] ERROR: {args.config} is not a mapping.", file=sys.stderr
        )
        return 2
    try:
        result = compute_epc_margin(config)
    except (ValueError, KeyError) as exc:
        print(f"[run_epc_margin] ERROR: {exc}", file=sys.stderr)
        return 2

    irr_str = (
        "n/a (no meaningful IRR for a money-first deal)"
        if result.annualized_irr is None
        else f"{result.annualized_irr:.1%}"
    )
    print(f"EPC contract value  : ${result.contract_value:,.0f}")
    print(f"Total cost          : ${result.total_cost:,.0f}")
    print(
        f"Gross margin        : ${result.gross_margin:,.0f}  "
        f"({result.gross_margin_pct:.1%} of value, {result.return_on_cost_pct:.1%} on cost)"
    )
    print(f"Construction period : {result.construction_months} months")
    print(f"Peak working capital: ${result.peak_working_capital:,.0f}")
    print(f"Construction IRR    : {irr_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
