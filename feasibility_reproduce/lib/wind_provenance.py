#!/usr/bin/env python3
"""Wind provenance for the feasibility kit: fresh bankable AEP + AEP tornado.

Usage:
    wind_provenance.py [outdir]        # default: <kit>/_run_out/wind

Proves the committed AEP is reproducible the long way — from the scenario's own
ERA5-fitted Weibull and power curve — rather than trusted as a pinned number,
and re-derives the AEP tornado that ranks its uncertainty drivers.

Micro-siting runs against an explicitly SYNTHETIC site geometry derived from
committed scenario parameters (``cache/micrositing_synthetic_site.yaml``), because
the real site boundary and baseline layout were never committed. Its uplift
quantifies the OPTIMISER WIRING, not the project's siting headroom, and is
labelled as such in the emitted artefact. Micro-siting is KPI-neutral, so the
finance canon does not depend on it.

Steps 1 and 2 are pure functions of the committed scenario, so they are offline and
deterministic. Expected against cache/expected/: net P50 464.36 GWh, CF 0.3322;
wind-speed bias +/-20.45% dominant, power curve 15.95%, shear 6.64%, losses 6.41%.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict

import yaml
from synthetic_site import load_synthetic_site, turbine_spec_from_power_curve

from analytics.wind.aep_summary_builder import build_aep_summary_from_config
from analytics.wind.aep_tornado import tornado_from_config
from finance.cashflow_v14_utils import get_nested
from wind_resource.layout_optimizer import optimize_layout

KIT = Path(__file__).resolve().parent.parent
REPO = KIT.parent
SCENARIO = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

SYNTHETIC_SITE_CONFIG = KIT / "cache" / "micrositing_synthetic_site.yaml"

SYNTHETIC_BANNER = """\
  NOTE micro-siting ran against a SYNTHETIC site geometry.

  The real site boundary polygon and baseline turbine coordinates are not
  committed anywhere in this repository, so the geometry is DERIVED from
  committed scenario parameters (array centroid, turbine count, spacing,
  orientation) — see cache/micrositing_synthetic_site.yaml.

  It carries NO site physics: no coastline, no exclusion zones, no setbacks or
  land tenure. The uplift below quantifies the OPTIMISER WIRING, not DutchBay's
  siting headroom, and MUST NOT be reported as a project result or used to
  re-baseline cache/expected/layout_optimized.json.
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

    # 3) Micro-siting — against the derived SYNTHETIC geometry (see the banner).
    site = load_synthetic_site(SYNTHETIC_SITE_CONFIG)
    # SLSQP reports convergence only on stdout and LayoutOptimizationResult carries
    # no status field, so capture it. FIN-01: a run that hit the iteration limit is
    # NOT silently presented as a converged optimum.
    optimizer_stdout = io.StringIO()
    turbine = turbine_spec_from_power_curve(
        curve_key=str(
            get_nested(cfg, ["resource", "power_curve_key"], "iea_reference_10mw")
        ),
        rotor_diameter_m=float(cfg["turbine"]["rotor_diameter_m"]),
        hub_height_m=float(cfg["turbine"]["hub_height_m"]),
        curves_path=REPO / "wind_resource" / "config" / "power_curves.yaml",
    )
    wind = cfg["wind_resource"]
    with contextlib.redirect_stdout(optimizer_stdout):
        result = optimize_layout(
            boundary=site.boundary_m,
            turbine=turbine,
            weibull_a=float(wind["weibull_a"]),
            weibull_k=float(wind["weibull_k"]),
            baseline_x_m=site.baseline_x_m,
            baseline_y_m=site.baseline_y_m,
            min_spacing_diameters=site.min_spacing_diameters,
            max_iterations=site.max_iterations,
            use_smart_start=site.use_smart_start,
            random_seed=site.random_seed,
        )
    converged = "Iteration limit reached" not in optimizer_stdout.getvalue()
    # MRM-02: the artefact carries its own provenance, so the number can never be
    # read back without the synthetic caveat attached.
    payload = {
        "provenance": site.provenance,
        "not_site_representative": True,
        "site_config": str(SYNTHETIC_SITE_CONFIG.relative_to(REPO)),
        "scenario": str(SCENARIO.relative_to(REPO)),
        "utm_epsg": site.utm_epsg,
        "baseline_aep_gwh": round(result.baseline_aep_gwh, 3),
        "optimized_aep_gwh": round(result.optimized_aep_gwh, 3),
        "uplift_gwh": round(result.uplift_gwh, 3),
        "uplift_pct": round(result.uplift_pct, 3),
        "converged": converged,
        "max_iterations": site.max_iterations,
        "n_turbines": result.n_turbines,
        "min_spacing_m": result.min_spacing_m,
        "driver": result.driver,
        "n_iterations": result.n_iterations,
        "random_seed": site.random_seed,
        "use_smart_start": site.use_smart_start,
    }
    (outdir / "layout_optimized_synthetic.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    status = "ok  " if converged else "WARN "
    print(
        f"  {status}micro-siting (SYNTHETIC): baseline {result.baseline_aep_gwh:.3f} -> "
        f"{result.optimized_aep_gwh:.3f} GWh ({result.uplift_pct:+.3f}%), "
        f"{result.n_turbines} turbines, min spacing {result.min_spacing_m:.0f} m, "
        f"{result.driver} / {result.n_iterations} iters"
    )
    if not converged:
        print(
            f"      NOT CONVERGED — SLSQP hit the {site.max_iterations}-iteration limit. "
            "The uplift above is the best point reached, NOT an optimum. Raise "
            "micrositing_synthetic.optimizer.max_iterations to pursue convergence."
        )
    print()
    print(SYNTHETIC_BANNER)
    print(f"      artefacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
