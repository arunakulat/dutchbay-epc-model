#!/usr/bin/env python
"""Thin CLI for the capital-risk layer (driver Monte Carlo -> VaR/CVaR/DSCR tail).

Wires :func:`analytics.capital_risk_layer_v14.run_capital_risk_layer` to a live
entrypoint. The module was previously orphaned (reachable only from its own unit test):
it samples the scenario's key risk drivers, runs each sample through the canonical
``evaluate_with_overrides`` gateway, and aggregates equity-IRR / equity-NPV VaR & CVaR
plus the DSCR tail (min, p5, p50, prob_breach) — a lender-grade capital-at-risk view.

This is a heavy Monte-Carlo analysis, so it is intentionally NOT run on every pipeline
call; invoke it on demand here.

Usage:
    python scripts/run_capital_risk_layer.py \\
        --config scenarios/dutchbay_lendercase_2025Q4.yaml \\
        --n-samples 500 --seed 42 --confidence 0.95 --dscr-covenant 1.20

    # explicit drivers (dotted engine paths -> {mean, std}); absolute override values:
    python scripts/run_capital_risk_layer.py --config scenarios/x.yaml \\
        --drivers '{"project.capacity_factor": {"mean": 0.34, "std": 0.02}}'

With no --drivers, a default set is derived from the scenario's own base values
(project.capacity_factor, tariff.lkr_per_kwh, capex.usd_total) at a 5% Gaussian std.
JSON is printed to stdout.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

# Repo-root bootstrap so "python scripts/..." works before an editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analytics.capital_risk_layer_v14 import run_capital_risk_layer  # noqa: E402
from analytics.scenario_loader import load_scenario_config  # noqa: E402

_DEFAULT_STD_FRACTION = 0.05  # 5% Gaussian std around each driver's scenario base value


def _nested_get(cfg: Mapping[str, Any], *path: str) -> Any:
    cur: Any = cfg
    for key in path:
        if not isinstance(cur, Mapping):
            return None
        cur = cur.get(key)
    return cur


def default_drivers(config_path: str) -> Dict[str, Dict[str, float]]:
    """Derive a default driver set from the scenario's own base values.

    Each driver is sampled Gaussian about its base at a 5% std (absolute-override values).
    Only drivers whose base value resolves to a positive number are included.
    """
    cfg = load_scenario_config(config_path)
    candidates = {
        "project.capacity_factor": _nested_get(cfg, "project", "capacity_factor"),
        "tariff.lkr_per_kwh": _nested_get(cfg, "tariff", "lkr_per_kwh"),
        "capex.usd_total": _nested_get(cfg, "capex", "usd_total"),
    }
    drivers: Dict[str, Dict[str, float]] = {}
    for path, base in candidates.items():
        try:
            mean = float(base)
        except (TypeError, ValueError):
            continue
        if mean > 0.0:
            drivers[path] = {"mean": mean, "std": abs(mean) * _DEFAULT_STD_FRACTION}
    if not drivers:
        raise SystemExit(
            "Could not derive default drivers from the scenario; pass --drivers explicitly."
        )
    return drivers


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the capital-risk layer for a scenario.")
    p.add_argument("--config", required=True, help="Path to the v14 scenario YAML.")
    p.add_argument(
        "--drivers",
        default=None,
        help='JSON: {"dotted.path": {"mean": float, "std": float}}. Default: derived from the scenario.',
    )
    p.add_argument("--n-samples", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--confidence", type=float, default=0.95)
    p.add_argument("--dscr-covenant", type=float, default=1.20)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    drivers = json.loads(args.drivers) if args.drivers else default_drivers(args.config)

    layer = run_capital_risk_layer(
        args.config,
        drivers=drivers,
        n_samples=int(args.n_samples),
        seed=int(args.seed),
        confidence=float(args.confidence),
        dscr_covenant=float(args.dscr_covenant),
    )

    payload = {
        "config": args.config,
        "drivers": drivers,
        "n_samples": int(args.n_samples),
        "seed": int(args.seed),
        "capital_risk_layer": dataclasses.asdict(layer),
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
