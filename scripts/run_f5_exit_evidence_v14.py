#!/usr/bin/env python3
"""Hydra CLI: generate and verify the audited F-5 exit evidence pack (#1893 Dolphin 4).

Reads ``conf/f5_exit_evidence_1893.yaml``, invokes
:func:`analytics.finance.f5_exit_evidence.build_f5_exit_evidence_pack`, and prints one
canonical JSON document (CLI-01, CLI-03). Setting ``f5_exit_evidence.summary_json``
writes the committed JSON evidence file under ``docs/finance/``.

Usage::

    .venv/bin/python scripts/run_f5_exit_evidence_v14.py
    .venv/bin/python scripts/run_f5_exit_evidence_v14.py \\
        f5_exit_evidence.summary_json=docs/finance/f5_exit_evidence_1893.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.finance.f5_exit_evidence import build_f5_exit_evidence_pack

REPO_ROOT = Path(__file__).resolve().parents[1]


@hydra.main(
    version_base="1.3", config_path="../conf", config_name="f5_exit_evidence_1893"
)
def main(cfg: DictConfig) -> None:
    """Build the F-5 exit evidence pack, optionally write JSON, and print JSON."""
    logging.disable(logging.WARNING)
    try:
        raw: Any = OmegaConf.to_container(cfg, resolve=True)
        if not isinstance(raw, dict) or not isinstance(
            raw.get("f5_exit_evidence"), dict
        ):
            raise TypeError(
                "expected Hydra config to contain an 'f5_exit_evidence' mapping"
            )
        block = raw["f5_exit_evidence"]
        result = build_f5_exit_evidence_pack(block, repo_root=REPO_ROOT)
        text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
        out = block.get("summary_json")
        if out:
            target = Path(str(out))
            if not target.is_absolute():
                target = REPO_ROOT / target
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        print(text, end="")
    finally:
        logging.disable(logging.NOTSET)


if __name__ == "__main__":
    main()
