from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import hydra
from omegaconf import DictConfig

from analytics.pipeline_v14 import run_v14_pipeline

logger = logging.getLogger(__name__)

# Remember the original working directory so we can undo Hydra's job chdir.
_ORIG_CWD = Path.cwd()


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
