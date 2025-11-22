from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Optional

from .scenario_runner import run_dir  # run_dir(config, out_dir, mode="irr", fmt="csv", save_annual=False)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dutchbay_v13",
        description="DutchBay EPC financial runner (IRR/NPV/DSCR).",
    )
    p.add_argument(
        "--mode",
        choices=["irr"],
        default="irr",
        help="Execution mode. Only 'irr' is supported currently.",
    )
    p.add_argument(
        "--config",
        required=True,
        type=str,
        help="Path to YAML scenario (e.g., full_model_variables_updated.yaml).",
    )
    p.add_argument(
        "--outputs-dir",
        default="outputs",
        type=str,
        help="Directory for artifacts (CSV, etc.). Will be created if missing.",
    )
    p.add_argument(
        "--format",
        dest="format",
        choices=["csv"],
        default="csv",
        help="Output format for annual export.",
    )
    p.add_argument(
        "--save-annual",
        action="store_true",
        help="If set, write annual rows to outputs-dir in the chosen format.",
    )

    # Validation mode toggles (env-aware in scenario_runner -> validate)
    vm = p.add_mutually_exclusive_group()
    vm.add_argument(
        "--strict",
        action="store_true",
        help="Force STRICT validation (VALIDATION_MODE=strict).",
    )
    vm.add_argument(
        "--relaxed",
        action="store_true",
        help="Force RELAXED validation (VALIDATION_MODE=relaxed).",
    )

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Wire validation mode via env for validate.load_params() path.
    if args.strict:
        os.environ["VALIDATION_MODE"] = "strict"
    elif args.relaxed:
        os.environ["VALIDATION_MODE"] = "relaxed"

    # Ensure outputs dir exists (run_dir also mkdirs; doing it here helps early failures).
    out_dir = Path(args.outputs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Execute
    res = run_dir(
        config=Path(args.config),
        out_dir=out_dir,
        mode=args.mode,
        fmt=args.format,
        save_annual=bool(args.save_annual),
    )

    # Simple success signal; richer exit semantics can be added later.
    return 0 if isinstance(res, dict) else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

    