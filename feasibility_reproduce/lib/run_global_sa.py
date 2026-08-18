#!/usr/bin/env python3
"""Global sensitivity for the feasibility kit: Sobol + Morris + PAWN.

Usage:
    run_global_sa.py [outdir] [--quick]    # default: <kit>/_run_out/global_sa

Drives the repo's canonical CLI (``scripts/run_global_sensitivity.py``) once per
method and merges the three into the combined artefact
``cache/expected/global_sa_combined.json`` pins.

The three are complementary, which is why the kit runs all of them: Morris is
cheap screening that ranks drivers, Sobol separates first-order (S1) from
total-order (ST) so ST >> S1 flags interactions, and PAWN is
moment-independent and stays honest on the covenant-pinned KPIs (min_dscr sits
on its 1.30 floor across most of the distribution) where Sobol misbehaves.

Cost at the committed settings is ~5,300 pipeline evaluations (Sobol n=512 ->
4,096 runs; Morris 32 trajectories -> 224; PAWN n=1024). Pass ``--quick`` for a
smoke-sized run (~1/8th) when checking the plumbing rather than regenerating
evidence.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

KIT = Path(__file__).resolve().parent.parent
REPO = KIT.parent
CLI = REPO / "scripts" / "run_global_sensitivity.py"
CONFIG = "scenarios/dutchbay_lendercase_2025Q4.yaml"

# Committed settings — these reproduce cache/expected/global_sa_combined.json
# (sobol n=512 -> 4096 runs; morris 32 trajectories -> 224 runs; pawn n=1024, s=10).
FULL = {"sobol": ["--n", "512"], "morris": [], "pawn": ["--n", "1024", "--s", "10"]}
QUICK = {"sobol": ["--n", "64"], "morris": [], "pawn": ["--n", "128", "--s", "10"]}

METRICS = ["project_irr", "equity_irr", "min_dscr"]


def run_method(method: str, extra: List[str], outdir: Path) -> Dict[str, Any]:
    """Run one SA method and return its parsed result."""
    out_csv = outdir / f"global_sa_{method}.csv"
    cmd = [sys.executable, str(CLI), "--config", CONFIG, "--method", method]
    for m in METRICS:
        cmd += ["--metric", m]
    cmd += extra + ["--output", str(out_csv)]

    print(
        f"  running {method} ({' '.join(extra) or 'defaults'}) — this drives the full pipeline per sample"
    )
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-3000:] + proc.stderr[-3000:])
        raise SystemExit(f"global-SA {method} failed (exit {proc.returncode})")

    # The CLI writes the indices as CSV; keep the raw rows so the combined
    # artefact carries the per-driver numbers, not just a ranking.
    rows: List[Dict[str, str]] = []
    if out_csv.is_file():
        import csv

        with open(out_csv, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    print(f"  ok  {method}: {len(rows)} index rows -> {out_csv.name}")
    return {"method": method, "rows": rows, "csv": out_csv.name}


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--quick"]
    quick = "--quick" in argv[1:]
    outdir = Path(args[0]) if args else KIT / "_run_out" / "global_sa"
    outdir.mkdir(parents=True, exist_ok=True)

    if not CLI.is_file():
        raise SystemExit(f"missing canonical SA CLI: {CLI}")

    settings = QUICK if quick else FULL
    if quick:
        print(
            "  --quick: smoke-sized samples; NOT evidence-grade, do not commit these numbers"
        )

    combined: Dict[str, Any] = {
        "config": CONFIG,
        "metrics": METRICS,
        "quick": quick,
    }
    for method in ("morris", "sobol", "pawn"):  # cheapest first, so plumbing fails fast
        combined[method] = run_method(method, settings[method], outdir)

    dest = outdir / "global_sa_combined.json"
    dest.write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
