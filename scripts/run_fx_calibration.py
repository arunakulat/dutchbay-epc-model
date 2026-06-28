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
    python scripts/run_fx_calibration.py --refresh           # re-pin a trailing-20y vintage as of today (network)
    python scripts/run_fx_calibration.py --refresh --window-years 10 --dry-run   # preview a 10y window, write nothing
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json

from analytics.fx.fx_calibration import calibrate_fx
from analytics.fx.fx_history import (
    DEFAULT_WINDOW_YEARS,
    fetch_live_history_bis,
    load_pinned_history,
    refresh_pinned_vintage,
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
    # Periodic refresh: re-pin a trailing-window vintage as of TODAY (network).
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="re-pin the FX vintage to a trailing window ending today (deliberate dated re-pin; network)",
    )
    ap.add_argument(
        "--window-years",
        type=int,
        default=DEFAULT_WINDOW_YEARS,
        help=f"trailing window for --refresh (default {DEFAULT_WINDOW_YEARS}; 10 = more crisis-weighted)",
    )
    ap.add_argument(
        "--provider",
        default="BIS",
        choices=["BIS", "FRED"],
        help="live source for --refresh (default BIS, keyless/reachable)",
    )
    ap.add_argument(
        "--as-of",
        default=None,
        help="anchor date YYYY-MM-DD for --refresh (default: today)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="with --refresh: fetch + window + report only, write nothing",
    )
    args = ap.parse_args()

    if args.refresh:
        as_of = _dt.date.fromisoformat(args.as_of) if args.as_of else None
        try:
            summary = refresh_pinned_vintage(
                window_years=args.window_years,
                provider=args.provider,
                as_of=as_of,
                dry_run=args.dry_run,
            )
        except Exception as exc:  # network/parse/window failure — non-fatal, reported
            print(f"FX refresh FAILED: {exc}")
            return 1
        print(("DRY-RUN " if args.dry_run else "") + "FX vintage refresh:")
        print(json.dumps(summary, indent=2))
        if args.dry_run:
            print(
                "DRY-RUN: nothing written. Drop --dry-run to commit and recalibrate on the new vintage."
            )
        else:
            print(
                "Re-pinned. NOTE: the deterministic scenario fx.annual_depr scalars are NOT "
                "auto-updated by a refresh — re-adopting a refreshed drift is a separate, "
                "explicit KPI re-baseline. Calibration below reflects the NEW vintage:"
            )

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
