#!/usr/bin/env python3
"""Generate one public financing questionnaire using Hydra."""

from __future__ import annotations

import json
import sys
from typing import Any, cast

import hydra
from omegaconf import DictConfig, OmegaConf

from analysis_tools.financing_questionnaire import (
    QuestionnaireError,
    export_questionnaire,
)


@hydra.main(
    version_base="1.3",
    config_path="../conf",
    config_name="blue_whale_financing_questionnaire",
)
def main(cfg: DictConfig) -> None:
    """Export one selected project and emit a concise JSON receipt."""
    try:
        config = OmegaConf.to_container(cfg, resolve=True)
        if not isinstance(config, dict):
            raise QuestionnaireError("configuration must be a mapping")
        receipt = export_questionnaire(cast(dict[str, Any], config))
    except (QuestionnaireError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from exc
    print(json.dumps(receipt, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    # Do not allow Hydra overrides to enable logging, chdir, or configuration writes.
    if any(not arg.startswith(("project=", "output_name=")) for arg in sys.argv[1:]):
        print(json.dumps({"error": "unsupported CLI override"}), file=sys.stderr)
        raise SystemExit(2)
    main()
