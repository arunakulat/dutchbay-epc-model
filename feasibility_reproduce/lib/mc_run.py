#!/usr/bin/env python3
"""Run the feasibility kit's Monte-Carlo step and write the summary artefact.

Usage:
    mc_run.py [n_trials] [outdir]      # defaults: 2500, <kit>/_run_out/mc

Thin wrapper over ``analytics/cli/cli_monte_carlo_hydra.py`` (the canonical MC
entry point) that additionally distils the engine's full summary down to the
shape ``cache/expected/mc2500_summary.json`` pins, so a reproduce run can be
diffed against the committed expectation without hand-editing JSON.

Fails loud on a degraded run: a non-zero ``toy_fallback_count`` means the engine
substituted fabricated KPIs for failed trials (FIN-01 exposure, see #962), which
would silently flatter the distribution. The kit refuses to emit such a summary
as if it were evidence.
"""

from __future__ import annotations

import glob
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

KIT = Path(__file__).resolve().parent.parent
REPO = KIT.parent
CONFIG = "scenarios/dutchbay_lendercase_2025Q4.yaml"
SEED = 42

# Distilled into the committed expectation; mirrors cache/expected/mc2500_summary.json.
SUMMARY_KEYS = (
    "dscr_min",
    "project_irr",
    "project_npv",
    "llcr",
    "plcr",
    "equity_irr",
    "equity_npv",
)


def run_mc(n_trials: int, outdir: Path) -> Dict[str, Any]:
    """Invoke the canonical MC CLI and load the summary it writes."""
    cmd = [
        sys.executable,
        str(REPO / "analytics" / "cli" / "cli_monte_carlo_hydra.py"),
        f"config={CONFIG}",
        f"n_trials={n_trials}",
        f"seed={SEED}",
        f"output_dir={outdir}",
        "write_artifacts=true",
        "run_scoped=true",
    ]
    # The MC engine logs one line per trial per tranche; keep it out of the terminal.
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-4000:] + proc.stderr[-4000:])
        raise SystemExit(f"monte-carlo CLI failed (exit {proc.returncode})")

    found = sorted(
        glob.glob(str(outdir / "**" / "monte_carlo_summary.json"), recursive=True)
    )
    if not found:
        raise SystemExit(f"MC reported success but wrote no summary under {outdir}")
    with open(found[-1], encoding="utf-8") as fh:
        return json.load(fh)


def distil(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce the engine summary to the committed expectation's shape."""
    summary = raw.get("summary", {})
    return {
        "n_trials": raw.get("n_trials"),
        "exec_s": round(float(raw.get("execution_time_seconds", 0.0)), 1),
        "success_rate_pct": raw.get("success_rate_pct"),
        "failed_iterations": raw.get("failed_iterations"),
        "seed": raw.get("seed"),
        "summary": {k: summary[k] for k in SUMMARY_KEYS if k in summary},
    }


def main(argv: list[str]) -> int:
    n_trials = int(argv[1]) if len(argv) > 1 else 2500
    outdir = Path(argv[2]) if len(argv) > 2 else KIT / "_run_out" / "mc"
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"  running {n_trials} trials (seed {SEED}) -> {outdir}")
    raw = run_mc(n_trials, outdir)

    toy = int(raw.get("toy_fallback_count") or 0)
    failed = int(raw.get("failed_iterations") or 0)
    if toy:
        raise SystemExit(
            f"  REFUSING to emit: {toy} trial(s) used the toy fallback — fabricated KPIs "
            "would flatter the distribution. Re-run with monte_carlo.allow_toy_fallback=false "
            "to see the real failures."
        )

    out = distil(raw)
    dest = outdir / "mc_summary.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    pct = out["summary"].get("equity_irr", {}).get("percentiles", {})
    print(
        f"  ok  {out['n_trials']} trials, {out['success_rate_pct']}% success, "
        f"{failed} failed, {toy} toy-fallbacks"
    )
    if pct:
        print(
            f"      equity IRR P10/P50/P90 = "
            f"{pct.get('10', float('nan')) * 100:.1f}/"
            f"{pct.get('50', float('nan')) * 100:.1f}/"
            f"{pct.get('90', float('nan')) * 100:.1f}%"
        )
    print(f"      wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
