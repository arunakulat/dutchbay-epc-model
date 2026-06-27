#!/usr/bin/env python
"""Inspect the market-calibrated USD/LKR FX driver (drift + vol + regimes).

Loads the provenance-pinned historical vintage (:mod:`analytics.fx.fx_history`),
calibrates the Monte-Carlo FX spec (:mod:`analytics.fx.fx_calibration`), and prints
the regime breakdown + the spot inverse-CDF percentiles. Optionally fetches the
live series to VALIDATE drift against the pinned vintage (network).

Examples
--------
    python scripts/run_fx_calibration.py
    python scripts/run_fx_calibration.py --pinned-spot 333.79 --frequency weekly
    python scripts/run_fx_calibration.py --validate          # live drift check (network)
"""

from __future__ import annotations

import argparse
import json

from analytics.fx.fx_calibration import calibrate_fx
from analytics.fx.fx_history import (
    fetch_live_history_bis,
    load_pinned_history,
    validate_history_drift,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--pinned-spot", type=float, default=333.79, help="anchor spot (LKR/USD)"
    )
    ap.add_argument(
        "--frequency", default="weekly", choices=["daily", "weekly", "monthly"]
    )
    ap.add_argument("--horizon-years", type=float, default=1.0)
    ap.add_argument(
        "--validate", action="store_true", help="fetch live BIS and report drift"
    )
    ap.add_argument("--json", action="store_true", help="emit the calibration as JSON")
    args = ap.parse_args()

    series = load_pinned_history()
    cal = calibrate_fx(
        series,
        pinned_spot=args.pinned_spot,
        horizon_years=args.horizon_years,
        frequency=args.frequency,
    )

    if args.json:
        print(json.dumps(cal.as_dict(), indent=2))
    else:
        print(
            f"FX vintage: {series.provider} {series.frequency} "
            f"{series.date_range[0]}..{series.date_range[1]} (n={len(series.rates)})"
        )
        print(
            f"long-run drift (annual_depr): {cal.annual_depr:.4f}  "
            f"crisis_prob: {cal.crisis_prob:.4f}  crisis_log_shift: {cal.crisis_log_shift:.4f}"
        )
        print(
            f"sigma_normal_1y: {cal.sigma_normal_1y:.4f}  sigma_crisis_1y: {cal.sigma_crisis_1y:.4f}"
        )
        print("regimes:")
        for r in cal.regimes:
            print(
                f"  {r.name:16} n={r.n_returns:4d}  mu_ann={r.mu_annual:+.4f}  "
                f"sigma_ann={r.sigma_annual:.4f}  cum={r.cumulative_log_return:+.4f}"
            )
        smp = cal.sampler()
        print("spot inverse-CDF (LKR/USD):")
        for u in (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99):
            print(f"  P{int(u * 100):>2}: {smp.spot_from_unit(u):8.2f}")

    if args.validate:
        try:
            live = fetch_live_history_bis()
            drift = validate_history_drift(series, live)
            print("VALIDATE (live BIS vs pinned):", json.dumps(drift))
        except Exception as exc:  # network/parse failure — non-fatal
            print(f"VALIDATE skipped (live fetch failed): {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
