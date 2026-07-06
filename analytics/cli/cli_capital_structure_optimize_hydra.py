"""Hydra CLI for the OPT-IN capital-structure optimizers (#740).

CANONICAL ENTRYPOINT for running the debt-tranche-mix and capex-contingency
optimizers from the command line. This is an ANALYSIS tool: it is invoked
explicitly and never participates in ``run_v14_pipeline``, so committed
scenarios are byte-identical whether or not this CLI is ever run.

Usage (run with the repo root on PYTHONPATH, as with the sibling Hydra CLIs):
    # Maximize equity IRR over the debt mix, DSCR + LLCR covenants:
    PYTHONPATH=. python analytics/cli/cli_capital_structure_optimize_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        mode=debt_mix objective_key=equity_irr direction=max \\
        'constraints=[{key: min_dscr_period, minimum: 1.30, maximum: null}, {key: llcr, minimum: 1.0, maximum: null}]'

    # Search the capex contingency fraction against the same objective:
    PYTHONPATH=. python analytics/cli/cli_capital_structure_optimize_hydra.py \\
        config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
        mode=capex_contingency base_capex_usd=157206000 \\
        'contingency_bounds=[0.0, 0.15]' n_steps=6

Config:
    See conf/cli_capital_structure_optimize.yaml.

Output:
    Prints the ``CapitalStructureOptimizationResult`` payload as JSON to stdout
    (sorted keys), plus CLI metadata (``status``, ``config_path``, ``mode``).
    On a fail-loud infeasible search the payload still has ``status="success"``
    but ``feasible=false`` and a populated ``infeasible_reason`` (the search
    completed; no candidate met the covenants). Bad input / crashes print
    ``{"status": "error", ...}`` and exit 1. Hydra INFO logging may precede the
    JSON; parse from the first "{" line.

GWTF:
    - R3: Hydra-only (no argparse)
    - CLI-03: JSON outputs
    - CCCDIR/ARCH-04: scores only via analytics.evaluation_v14
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, List, Optional

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.capital_structure_optimizer_v14 import (
    optimize_capex_contingency,
    optimize_debt_mix,
)
from analytics.contracts_v14 import (
    CapitalStructureOptimizationResult,
    CovenantConstraint,
)

logger = logging.getLogger(__name__)

_MODES = ("debt_mix", "capex_contingency")


def _parse_constraints(raw: Any) -> List[CovenantConstraint]:
    """Build ``CovenantConstraint`` objects from the config list.

    Each item is a mapping ``{key, minimum, maximum}`` (either bound optional /
    null). Fail-loud on a missing ``key`` or a non-mapping item.
    """
    items = OmegaConf.to_container(raw, resolve=True) if raw is not None else []
    if not isinstance(items, list):
        raise ValueError(f"'constraints' must be a list, got {type(items).__name__}")
    out: List[CovenantConstraint] = []
    for item in items:
        if not isinstance(item, dict) or "key" not in item:
            raise ValueError(
                f"each constraint must be a mapping with a 'key', got {item!r}"
            )
        minimum = item.get("minimum")
        maximum = item.get("maximum")
        out.append(
            CovenantConstraint(
                key=str(item["key"]),
                minimum=None if minimum is None else float(minimum),
                maximum=None if maximum is None else float(maximum),
            )
        )
    return out


def _pair(raw: Any, name: str) -> tuple[float, float]:
    """Coerce a 2-element config sequence to a ``(low, high)`` float tuple."""
    seq = OmegaConf.to_container(raw, resolve=True) if raw is not None else None
    if not isinstance(seq, (list, tuple)) or len(seq) != 2:
        raise ValueError(f"{name} must be a 2-element [low, high] list, got {raw!r}")
    return float(seq[0]), float(seq[1])


@hydra.main(
    version_base="1.3",
    config_path="../../conf",
    config_name="cli_capital_structure_optimize",
)
def main(cfg: DictConfig) -> None:
    """Hydra entrypoint for the capital-structure optimizers.

    Args:
        cfg: Config from conf/cli_capital_structure_optimize.yaml. Required:
            ``config`` (scenario path). Key knobs: ``mode`` (``debt_mix`` |
            ``capex_contingency``), ``objective_key``, ``direction``,
            ``constraints``, ``n_steps``, the mode-specific bounds, and
            (for capex mode) ``base_capex_usd``.

    Returns:
        None. Prints the JSON result payload to stdout; optionally writes it.

    Raises:
        SystemExit: On missing/invalid config (exit 1).
    """
    config_path = cfg.get("config")
    mode = str(cfg.get("mode", "debt_mix"))
    if not config_path:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "Missing 'config' parameter",
                    "usage": (
                        "python analytics/cli/cli_capital_structure_optimize_hydra.py "
                        "config=scenarios/example.yaml mode=debt_mix"
                    ),
                },
                indent=2,
            )
        )
        raise SystemExit(1)

    try:
        if mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {mode!r}")

        objective_key = str(cfg.get("objective_key", "equity_irr"))
        direction = str(cfg.get("direction", "max"))
        n_steps = int(cfg.get("n_steps", 6))
        constraints = _parse_constraints(cfg.get("constraints"))

        result: CapitalStructureOptimizationResult
        if mode == "debt_mix":
            result = optimize_debt_mix(
                str(config_path),
                objective_key=objective_key,
                direction=direction,
                constraints=constraints,
                lkr_bounds=_pair(cfg.get("lkr_bounds"), "lkr_bounds"),
                dfi_bounds=_pair(cfg.get("dfi_bounds"), "dfi_bounds"),
                n_steps=n_steps,
            )
        else:
            base_capex_usd: Optional[float] = cfg.get("base_capex_usd")
            if base_capex_usd is None:
                raise ValueError(
                    "mode=capex_contingency requires 'base_capex_usd' (the base "
                    "capex USD excluding contingency)"
                )
            result = optimize_capex_contingency(
                str(config_path),
                base_capex_usd=float(base_capex_usd),
                objective_key=objective_key,
                direction=direction,
                constraints=constraints,
                contingency_bounds=_pair(
                    cfg.get("contingency_bounds"), "contingency_bounds"
                ),
                n_steps=n_steps,
            )

        payload: dict[str, Any] = asdict(result)
        payload["status"] = "success"
        payload["config_path"] = str(config_path)
        payload["mode"] = mode

        if bool(cfg.get("write_artifacts", True)):
            output_dir = Path(
                str(cfg.get("output_dir", "_out/capital_structure_optimize"))
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            out_path = output_dir / f"capital_structure_optimize_{mode}.json"
            out_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
            logger.info("Wrote optimizer result to %s", out_path)

        print(json.dumps(payload, indent=2, sort_keys=True))

    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "config_path": str(config_path),
                    "mode": mode,
                },
                indent=2,
            )
        )
        logger.exception("Capital-structure optimization failed")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
