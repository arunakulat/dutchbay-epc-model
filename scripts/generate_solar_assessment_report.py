#!/usr/bin/env python
"""Generate the solar PV assessment report for a scenario (DBPL PDF).

A thin command line over :mod:`app.reports.solar_assessment`, which reads every input from
the scenario it is given (#1784). The PDF follows the DutchBay Presentation Layer print
contract (``DBPL-01``) and needs the complete ``[report]`` extra plus ``[solar]`` for the
resource step.

Usage::

    python scripts/generate_solar_assessment_report.py --scenario scenarios/example.yaml \\
        [--out DIR] [--trials N] [--no-maps]

The maps fetch NASA POWER and imagery tiles over the network; ``--no-maps`` skips them. An
analysis that cannot run on the scenario is listed in the report with its reason.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main(argv: list[str] | None = None) -> int:
    from app.reports.solar_assessment import write_report

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenario", required=True, help="Path to a solar scenario YAML")
    ap.add_argument("--out", default="solar_assessment_report", help="Output folder")
    ap.add_argument("--trials", type=int, default=1000, help="Monte Carlo trials")
    ap.add_argument(
        "--no-maps", action="store_true", help="Skip the network-sourced maps"
    )
    args = ap.parse_args(argv)
    outputs = write_report(
        args.scenario,
        Path(args.out),
        trials=args.trials,
        issue_date=_dt.date.today().isoformat(),
        draw_maps=not args.no_maps,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
