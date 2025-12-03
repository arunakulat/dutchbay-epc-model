from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

import hydra
from omegaconf import DictConfig

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


def run_v14_pipeline(
    config: str | Mapping[str, Any],
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the v14 engine for a single scenario.

    Parameters
    ----------
    config
        Either:
        - Path to YAML/JSON scenario file (str or Path), or
        - A pre-loaded config mapping (dict-like).
    validation_mode : {"strict", "off"}, default "strict"
        - "strict": run schema guard before evaluation
        - "off": skip schema guard
    validation_modules : list[str] or None
        Modules to validate. Defaults to ["cashflow", "debt"].

    Returns
    -------
    dict[str, Any]
        ScenarioResult-like dict with keys:
        - validation_mode
        - config_path
        - config
        - annual_rows
        - debt_result
        - kpis
    """
    mode = validation_mode.lower()
    if mode not in {"strict", "off"}:
        raise ValueError(
            f"validation_mode must be 'strict' or 'off', got: {validation_mode!r}"
        )

    # ------------------------------------------------------------------
    # 1. Resolve config + label
    # ------------------------------------------------------------------
    if isinstance(config, (str, Path)):
        config_path_label = str(config)
        cfg = load_scenario_config(str(config))
    elif isinstance(config, Mapping):
        config_path_label = "<inline_config>"
        # Shallow copy to decouple from callers
        cfg = dict(config)
    else:
        raise TypeError(
            "config must be a path (str/Path) or a mapping, "
            f"got {type(config).__name__}"
        )

    # ------------------------------------------------------------------
    # 2. Pre-flight validation
    # ------------------------------------------------------------------
    if mode == "strict":
        modules = validation_modules or ["cashflow", "debt"]
        validate_config_for_v14(
            raw_config=cfg,
            config_path=config_path_label,
            modules=modules,
        )
        logger.info("Schema validation passed for modules: %s", ", ".join(modules))

    # ------------------------------------------------------------------
    # 3. Canonical v14 finance engine
    # ------------------------------------------------------------------
    from analytics.core.metrics import calculate_scenario_kpis
    from finance.cashflow_v14 import build_annual_rows
    from finance.debt_v14 import apply_debt_layer

    annual_rows = build_annual_rows(cfg)
    logger.debug("Built %d annual rows", len(annual_rows))

    debt_result = apply_debt_layer(cfg, annual_rows)
    logger.debug("Debt result contains %d keys", len(debt_result))

    kpis = calculate_scenario_kpis(
        config=cfg,
        annual_rows=annual_rows,
        debt_result=debt_result,
        # TODO: wire discount rate from WACC engine / config
        discount_rate=0.10,
    )
    logger.debug("Calculated %d KPIs", len(kpis))

    # ------------------------------------------------------------------
    # 4. Package result
    # ------------------------------------------------------------------
    result: dict[str, Any] = {
        "config": cfg,
        "config_path": config_path_label,
        "validation_mode": mode,
        "annual_rows": annual_rows,
        "debt_result": debt_result,
        "kpis": kpis,
    }

    logger.info(
        "Pipeline complete: config_path=%s, annual_rows=%d, debt_metrics=%d, kpis=%d",
        config_path_label,
        len(annual_rows),
        len(debt_result),
        len(kpis),
    )

    return result


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="run_full_pipeline_v14",
)
def cli(cfg: DictConfig) -> None:
    """
    Hydra CLI entry point.

    Usage
    -----
    Basic::

        python run_full_pipeline_v14.py config=scenarios/example_a.yaml

    With explicit validation options::

        python run_full_pipeline_v14.py \\
            config=scenarios/example_a.yaml \\
            validation_mode=strict \\
            validation_modules=cashflow,debt
    """
    # Undo Hydra's job-chdir so relative scenario paths still work from repo root.
    os.chdir(_ORIG_CWD)

    config = cfg.get("config")
    if not config:
        raise SystemExit(
            "Missing 'config' value.\n"
            "Usage: python run_full_pipeline_v14.py "
            "config=scenarios/example_a.yaml [validation_mode=strict] "
            "[validation_modules=cashflow,debt]"
        )

    validation_mode = cfg.get("validation_mode", "strict")

    modules_raw = cfg.get("validation_modules", None)
    if isinstance(modules_raw, str):
        validation_modules = [m.strip() for m in modules_raw.split(",") if m.strip()]
    elif modules_raw is None:
        validation_modules = None
    else:
        validation_modules = list(modules_raw)

    result = run_v14_pipeline(
        config=str(config),
        validation_mode=str(validation_mode),
        validation_modules=validation_modules,
    )

    # Emit JSON for CI/tooling
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    cli()
# EOF
