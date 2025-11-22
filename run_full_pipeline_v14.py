#!/usr/bin/env python3
"""v14 pipeline entrypoint for DutchBay EPC model.

This module exposes a single, testable function:

    run_v14_pipeline(config: str, validation_mode: str = "strict") -> dict

Responsibilities:
- Load a v14-compatible scenario config via analytics.scenario_loader.
- Run the v14 cashflow + debt stack (dutchbay_v14chat.finance.*).
- Apply a pre-flight schema guard (analytics.schema_guard) so that
  malformed configs fail fast with actionable error messages.
- Compute KPIs via analytics.core.metrics.calculate_scenario_kpis.
- Return a structured result dict for tests and CLI use.

Non-responsibilities:
- No v13 imports or calls.
- No ad-hoc FX curves or hard-coded financial assumptions.
- No side effects on import (safe for pytest and CI).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from analytics.core.metrics import calculate_scenario_kpis
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from analytics.scenario_loader import load_scenario_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer

logger = logging.getLogger(__name__)


def _extract_cfads_usd(annual_rows: Sequence[Mapping[str, Any]]) -> List[float]:
    """Extract CFADS (USD) from annual rows.

    We keep this helper explicit rather than hiding it in metrics so that
    tests can assert on the exact series we pass into KPI calculation.
    """
    return [float(row.get("cfads_usd", 0.0) or 0.0) for row in annual_rows]


def _validation_modules_for_mode(validation_mode: str) -> List[str]:
    """Decide which logical modules should participate in schema validation.

    For now, the cashflow layer is the canonical consumer of core v14
    config fields. We keep this as a separate helper so that future
    extensions (debt, irr, monte_carlo, etc.) can be wired in centrally.
    """
    mode = (validation_mode or "").strip().lower()

    if mode in {"none", "off", "skip"}:
        return []

    # "strict" and "relaxed" currently share the same module set; if you
    # later want relaxed behaviour, you can down-shift severity in
    # analytics.config_schema instead of changing this switch.
    return ["cashflow"]


def run_v14_pipeline(config: str, validation_mode: str = "strict") -> Dict[str, Any]:
    """Run the v14 cashflow + debt pipeline for a single scenario.

    Parameters
    ----------
    config:
        Path to the scenario config file (YAML or JSON). In CI/tests this
        is typically something under `scenarios/`, e.g.:

            "scenarios/dutchbay_lendercase_2025Q4.yaml"

    validation_mode:
        Logical validation mode string. Recognised values:
            - "strict" (default): run full schema_guard checks.
            - "relaxed": same module set as strict for now, but reserved
              for future softening of rules.
            - "none", "off", "skip": bypass schema_guard entirely.

    Returns
    -------
    Dict[str, Any]
        A structured result containing:

        {
            "config_path": "<absolute path to config>",
            "validation_mode": "<validation_mode>",
            "validated_modules": ["cashflow", ...],
            "config": <normalized config dict>,
            "annual_rows": <list[dict]>,
            "debt_result": <dict>,
            "kpis": <dict from calculate_scenario_kpis>,
        }

    Raises
    ------
    FileNotFoundError
        If the provided config path does not exist.

    ConfigValidationError
        If schema validation fails under the requested validation_mode.
    """
    path = Path(config).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # 1. Load and normalise config (v13/v14 compatible but v14 is canonical)
    logger.debug("Loading scenario config from %s", path)
    cfg = load_scenario_config(str(path))

    # 2. Pre-flight schema validation – fail fast on malformed configs
    modules = _validation_modules_for_mode(validation_mode)
    if modules:
        logger.debug(
            "Running schema_guard for config=%s with modules=%s",
            path,
            ",".join(modules),
        )
        validate_config_for_v14(
            raw_config=cfg,
            config_path=str(path),
            modules=modules,
        )

    # 3. Build v14 annual cashflows
    annual_rows = build_annual_rows(cfg)

    # 4. Apply the v14 debt layer
    debt_result = apply_debt_layer(cfg, annual_rows)

    # 5. Extract CFADS series (USD) from annual rows
    cfads_series_usd = _extract_cfads_usd(annual_rows)

    # 6. Compute KPIs using the shared metrics engine
    kpis = calculate_scenario_kpis(
        annual_rows=annual_rows,
        debt_result=debt_result,
        config=cfg,
        cfads_series_usd=cfads_series_usd,
    )

    return {
        "config_path": str(path.resolve()),
        "validation_mode": validation_mode,
        "validated_modules": modules,
        "config": cfg,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
    }


def _configure_logging(quiet: bool = False) -> None:
    """Configure a sane default logging setup for CLI use.

    We keep this light so that library callers are free to configure
    logging however they like without interference.
    """
    root = logging.getLogger()
    if root.handlers:
        # Assume the application already configured logging.
        return

    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
    )


def _cli_main(argv: Sequence[str] | None = None) -> int:
    """CLI wrapper for manual runs and quick smoke tests.

    This is deliberately thin and just prints a small subset of the
    results; full reporting belongs in analytics/export layers.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run the v14 cashflow + debt pipeline for a single scenario file."
        )
    )
    parser.add_argument(
        "--config",
        "-c",
        default="scenarios/dutchbay_lendercase_2025Q4.yaml",
        help="Path to a v14 scenario config (YAML or JSON).",
    )
    parser.add_argument(
        "--validation-mode",
        "-m",
        default="strict",
        help="Validation mode: strict | relaxed | none.",
    )
    parser.add_argument(
        "--json-output",
        "-j",
        default=None,
        help=(
            "Optional path to write a JSON result payload. Use '-' to "
            "print JSON to stdout."
        ),
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Reduce logging verbosity.",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    _configure_logging(quiet=bool(args.quiet))

    try:
        result = run_v14_pipeline(
            config=args.config,
            validation_mode=args.validation_mode,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except ConfigValidationError as exc:
        # Schema-level failure: tell the user exactly which fields to fix.
        logger.error("%s", exc)
        return 2
    except Exception:  # pragma: no cover - defensive catch-all for CLI
        logger.exception("Unexpected error while running v14 pipeline")
        return 3

    # Pretty-print a compact KPI summary for interactive use
    kpis = result.get("kpis", {}) or {}
    print(f"Config: {result.get('config_path')}")
    print(f"Validation mode: {result.get('validation_mode')}")
    print("\nCore KPIs (from v14 pipeline, USD-based):")
    for key in ("npv", "irr", "equity_irr", "dscr_min", "dscr_mean", "dscr_max"):
        if key in kpis:
            print(f"  {key}: {kpis.get(key)}")

    # Optional JSON export
    if args.json_output:
        payload = {
            "config_path": result.get("config_path"),
            "validation_mode": result.get("validation_mode"),
            "validated_modules": result.get("validated_modules"),
            "kpis": kpis,
        }
        if args.json_output == "-":
            json.dump(payload, sys.stdout, indent=2)
            print()  # newline after JSON
        else:
            out_path = Path(args.json_output).expanduser()
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            logger.info("Wrote JSON summary to %s", out_path)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(_cli_main(sys.argv[1:]))
