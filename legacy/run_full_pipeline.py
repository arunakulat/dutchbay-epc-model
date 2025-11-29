#!/usr/bin/env python3
"""
Compatibility CLI for the DutchBay v14 pipeline.

This script preserves the historic `run_full_pipeline.py` entrypoint
for CI and external tooling. It parses CLI arguments and delegates to
the v14 pipeline runner (`run_v14_pipeline`).

Tests call it roughly as:

    python run_full_pipeline.py \
        --mode base \
        --config scenarios/dutchbay_lendercase_2025Q4.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _resolve_run_v14_pipeline() -> Callable[..., Any]:
    """
    Resolve the v14 pipeline entrypoint in a robust way.

    We try a few likely import paths so this shim keeps working even if the
    implementation module moves slightly in future refactors.
    """
    # 1) Top-level helper module in repo root
    try:
        from run_full_pipeline_v14 import run_v14_pipeline  # type: ignore

        logger.debug("Resolved run_v14_pipeline from run_full_pipeline_v14")
        return run_v14_pipeline
    except Exception:
        pass

    # 2) Package-style import under dutchbay_v14chat
    try:
        from dutchbay_v14chat.run_full_pipeline_v14 import (  # type: ignore
            run_v14_pipeline,
        )

        logger.debug(
            "Resolved run_v14_pipeline from dutchbay_v14chat.run_full_pipeline_v14"
        )
        return run_v14_pipeline
    except Exception:
        pass

    # 3) Fallback: if you ever rename it to v14_pipeline.py etc, wire it here.
    raise ImportError(
        "Could not locate `run_v14_pipeline` in run_full_pipeline_v14 "
        "or dutchbay_v14chat.run_full_pipeline_v14. "
        "Please update run_full_pipeline.py shim to match the new path."
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for the v14 pipeline."""
    parser = argparse.ArgumentParser(
        description="DutchBay v14 full pipeline runner (legacy CLI shim)."
    )

    parser.add_argument(
        "--mode",
        default="base",
        choices=["base", "strict"],
        help=(
            "Legacy execution mode flag. "
            "Currently both 'base' and 'strict' map to validation_mode='strict' "
            "for the v14 pipeline. Kept for backwards compatibility."
        ),
    )

    parser.add_argument(
        "--config",
        required=True,
        help=(
            "Path to scenario/config YAML "
            "(e.g. scenarios/dutchbay_lendercase_2025Q4.yaml)."
        ),
    )

    parser.add_argument(
        "--validation-mode",
        choices=["strict", "base"],
        default=None,
        help=(
            "Optional explicit validation mode passed to run_v14_pipeline. "
            "If omitted, we derive it from --mode; for now both effectively "
            "use 'strict' under the hood."
        ),
    )

    # Tests only depend on --mode and --config today, but this leaves room
    # for future flags (--output-dir, --log-level, etc.).
    return parser


def _derive_validation_mode(args: argparse.Namespace) -> str:
    """
    Map CLI args to the internal validation_mode used by run_v14_pipeline.

    For now, all paths lead to 'strict', but wiring is explicit so we can
    easily evolve semantics later without touching tests.
    """
    if args.validation_mode:
        return args.validation_mode

    # Legacy mapping: both 'base' and 'strict' use strict validations.
    if args.mode in {"base", "strict"}:
        return "strict"

    # Defensive default; should never really hit with current choices.
    return "strict"


def main(argv: list[str] | None = None) -> int:
    """
    CLI entrypoint.

    Parses arguments, resolves the v14 pipeline function, and runs it with
    a strict validation guard. Returns 0 on success, non-zero on failure,
    so tests can treat this as a true smoke test.
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    run_v14_pipeline = _resolve_run_v14_pipeline()
    validation_mode = _derive_validation_mode(args)

    logger.info(
        "Running v14 pipeline via run_full_pipeline.py shim "
        "(mode=%s, validation_mode=%s, config=%s)",
        args.mode,
        validation_mode,
        args.config,
    )

    try:
        # Contract per tests/test_v14_pipeline_smoke.py:
        #   run_v14_pipeline(config=<path>, validation_mode=<mode>)
        _result = run_v14_pipeline(
            config=args.config,
            validation_mode=validation_mode,
        )
    except SystemExit as exc:
        # If the underlying code still calls sys.exit, propagate its code.
        code = int(getattr(exc, "code", 1) or 1)
        logger.error("Pipeline exited with SystemExit(%s)", code)
        return code
    except Exception as exc:  # pragma: no cover
        # For CLI smoke we log and return non-zero, so pytest sees a clean failure.
        logger.exception("v14 pipeline failed in CLI shim: %s", exc)
        return 1

    # If we get here without exceptions, treat as success.
    print(
        f"v14 pipeline completed successfully for config: {args.config} "
        f"(mode={args.mode}, validation_mode={validation_mode})"
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s\t| %(message)s",
    )
    raise SystemExit(main())
