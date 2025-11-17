from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from dutchbay_v13.v14_pipeline import run_v14_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dutchbay_v13.cli",
        description=(
            "DutchBay EPC Model CLI\n\n"
            "Modes:\n"
            "  irr     - run base IRR / DSCR case (legacy v13 pipeline)\n"
            "  matrix  - run scenario matrix (legacy v13 pipeline)\n"
            "  validate- validate YAML config only\n"
            "  v14     - run the new v14 engine + pipeline\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="PATH",
        help="Path to YAML configuration file.",
        default=None,
    )

    parser.add_argument(
        "-m",
        "--mode",
        dest="mode",
        metavar="MODE",
        choices=["irr", "matrix", "validate", "v14"],
        default="irr",
        help="Run mode: irr, matrix, validate, v14 (default: irr).",
    )

    parser.add_argument(
        "-o",
        "--out-dir",
        dest="out_dir",
        metavar="DIR",
        help="Output directory for generated files.",
        default="_out_cli_fast",
    )

    parser.add_argument(
        "--scenario",
        dest="scenario",
        metavar="NAME",
        help="Optional scenario name defined in the YAML.",
        default=None,
    )

    parser.add_argument(
        "--validation-mode",
        dest="validation_mode",
        choices=["strict", "relaxed"],
        default="strict",
        help="Validation mode for YAML parameters (default: strict).",
    )

    return parser


def _ensure_out_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _run_legacy_irr(args: argparse.Namespace) -> None:
    """
    Legacy v13 IRR / DSCR run via scenario_runner.run_dir.

    We lazy-import scenario_runner here so that importing the CLI module
    does not fail even if the legacy pipeline is temporarily broken.
    """
    from dutchbay_v13.scenario_runner import run_dir  # type: ignore

    out_dir = Path(args.out_dir)
    _ensure_out_dir(out_dir)

    run_dir(
        config_path=args.config,
        out_dir=str(out_dir),
        mode="irr",
        validation_mode=args.validation_mode,
    )


def _run_legacy_matrix(args: argparse.Namespace) -> None:
    from dutchbay_v13.scenario_runner import run_dir  # type: ignore

    out_dir = Path(args.out_dir)
    _ensure_out_dir(out_dir)

    run_dir(
        config_path=args.config,
        out_dir=str(out_dir),
        mode="matrix",
        validation_mode=args.validation_mode,
    )


def _run_legacy_validate(args: argparse.Namespace) -> None:
    """
    Lightweight validation mode that just runs the scenario runner in a
    'validate only' mode (no heavy outputs). We rely on run_dir to raise if
    config is invalid.
    """
    from dutchbay_v13.scenario_runner import run_dir  # type: ignore

    out_dir = Path(args.out_dir)
    _ensure_out_dir(out_dir)

    run_dir(
        config_path=args.config,
        out_dir=str(out_dir),
        mode="validate",
        validation_mode=args.validation_mode,
    )


def _run_v14_mode(args: argparse.Namespace) -> None:
    """
    New v14 engine + pipeline entry:
      - uses run_v14_pipeline
      - writes a simple CSV summary
      - prints LLCR / PLCR / DSCR headline to stdout
    """
    out_dir = Path(args.out_dir)
    _ensure_out_dir(out_dir)

    result = run_v14_pipeline(
        config=args.config,
        scenario=args.scenario,
        validation_mode=args.validation_mode,
    )

    years = result["years"]
    cfads = result["cfads_pre_debt"]
    debt_service = result["debt_service"]
    dscr = result["dscr"]
    llcr = result["llcr"]
    plcr = result["plcr"]

    summary_path = out_dir / "v14_summary.csv"
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("year,cfads_pre_debt,debt_service,dscr\n")
        for y, c, d, r in zip(years, cfads, debt_service, dscr):
            f.write(f"{y},{c:.2f},{d:.2f},{r:.6f}\n")

    min_dscr = min(dscr) if dscr else 0.0
    avg_dscr = sum(dscr) / len(dscr) if dscr else 0.0

    print("V14 run complete.")
    print(f"  Output directory   : {out_dir}")
    print(f"  Summary CSV        : {summary_path.name}")
    print(f"  LLCR / PLCR        : {llcr:.3f} / {plcr:.3f}")
    print(f"  DSCR (min / avg)   : {min_dscr:.3f} / {avg_dscr:.3f}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    mode = args.mode

    if mode == "irr":
        _run_legacy_irr(args)
    elif mode == "matrix":
        _run_legacy_matrix(args)
    elif mode == "validate":
        _run_legacy_validate(args)
    elif mode == "v14":
        _run_v14_mode(args)
    else:
        parser.error(f"Unknown mode: {mode!r}")


if __name__ == "__main__":  # pragma: no cover
    main()

    