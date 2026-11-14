#!/usr/bin/env python3
"""Print a one-line receipt note saying what a scenario YAML models.

Usage:
    scenario_basis.py <scenario.yaml>

The NOV26 runner puts this note on each study-scenario receipt row, so a PASS row
cannot be read as a result for a layout the scenario does not model. The note is read
from the scenario's own YAML and hard-codes no site value:

- a ``turbine`` block with ``n_turbines`` -> "<n>-turbine layout, <capacity> MW";
- otherwise -> "no turbine layout: flat <capacity> MW at capacity factor <cf>".
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import yaml


def basis(cfg: Dict[str, Any]) -> str:
    """Return the receipt note for one loaded scenario mapping."""
    project = cfg.get("project") or {}
    capacity = project.get("capacity_mw")
    turbine = cfg.get("turbine") or {}
    count = turbine.get("n_turbines")
    if count is not None:
        return f"{int(count)}-turbine layout, {capacity} MW"
    factor = project.get("capacity_factor")
    return f"no turbine layout: flat {capacity} MW at capacity factor {factor}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: scenario_basis.py <scenario.yaml>\n")
        return 2
    cfg = yaml.safe_load(Path(argv[1]).read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        sys.stderr.write(f"not a scenario mapping: {argv[1]}\n")
        return 2
    print(basis(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
