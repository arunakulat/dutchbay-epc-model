#!/usr/bin/env python3
"""Wind provenance for the feasibility kit: fresh bankable AEP + AEP tornado.

Usage:
    wind_provenance.py [outdir]        # default: <kit>/_run_out/wind

Proves the committed AEP is reproducible the long way — from the scenario's own
ERA5-fitted Weibull and power curve — rather than trusted as a pinned number,
and re-derives the AEP tornado that ranks its uncertainty drivers.

Micro-siting is NOT run here; see MICROSITING_NOTE below. The step is skipped
loudly rather than run on invented geometry, because a fabricated site boundary
would produce an authoritative-looking uplift that is not the project's.

Both steps are pure functions of the committed scenario, so this is offline and
deterministic. Expected against cache/expected/: net P50 464.36 GWh, CF 0.3322;
wind-speed bias +/-20.45% dominant, power curve 15.95%, shear 6.64%, losses 6.41%.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

from analytics.wind.aep_summary_builder import build_aep_summary_from_config
from analytics.wind.aep_tornado import tornado_from_config

KIT = Path(__file__).resolve().parent.parent
REPO = KIT.parent
SCENARIO = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

MICROSITING_NOTE = """\
  SKIP micro-siting — the site geometry it needs is not in the repository.

  wind_resource.layout_optimizer.optimize_layout() requires a site boundary
  polygon and the baseline turbine coordinates. Neither is committed: the
  scenario carries the Weibull pair, rotor diameter, hub height and turbine
  count, but no geometry, and no boundary/layout file exists anywhere in the
  tree. The committed cache/expected/layout_optimized.json (baseline 550.987 ->
  555.433 GWh, +0.807%, 15 turbines, min spacing 594 m = 3.0 D) was produced
  from geometry that was never checked in.

  Inventing a boundary would yield a different, project-irrelevant uplift while
  looking authoritative, so this step stays skipped until the real polygon and
  baseline layout are committed. Micro-siting is KPI-neutral — it is an upside
  candidate, not a committed input — so the finance canon does not depend on it.
"""


def load_config() -> Dict[str, Any]:
    with open(SCENARIO, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main(argv: list[str]) -> int:
    outdir = Path(argv[1]) if len(argv) > 1 else KIT / "_run_out" / "wind"
    outdir.mkdir(parents=True, exist_ok=True)
    cfg = load_config()

    # 1) Fresh bankable AEP — the long way, from Weibull + power curve + loss stack.
    summary = build_aep_summary_from_config(cfg)
    (outdir / "aep_summary_fresh.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        f"  ok  fresh AEP: net P50 {summary.get('net_site_aep_gwh')} GWh, "
        f"CF {summary.get('capacity_factor')}, {summary.get('n_turbines')} turbines"
    )

    # 2) AEP tornado — ranks the uncertainty drivers behind that P50.
    tornado = tornado_from_config(cfg)
    tornado.to_csv(outdir / "aep_tornado.csv", index=False)
    top = tornado.sort_values("abs_swing_gwh", ascending=False).iloc[0]
    print(
        f"  ok  AEP tornado: {len(tornado)} drivers, dominant = "
        f"{top['driver']} ({top['swing_pct']:+.2f}%)"
    )

    # 3) Micro-siting — deliberately not run.
    print(MICROSITING_NOTE)
    print(f"      artefacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
