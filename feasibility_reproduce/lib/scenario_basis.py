#!/usr/bin/env python3
"""Print a one-line receipt note saying what a scenario YAML models.

Usage:
    scenario_basis.py <scenario.yaml>

The NOV26 runner puts this note on each study-scenario receipt row, so a PASS row
cannot be read as a result for a layout or technology the scenario does not model.
Everything in the note is read from the scenario's own YAML; no site value is
hard-coded. Examples of the shapes it produces:

- "14-turbine layout, wind 148.9 MW"
- "14-turbine layout, wind 148.9 MW + solar 50.0 MW (198.9 MW total)"
- "no turbine layout: solar 150.0 MW at capacity factor 0.1685"
- "no turbine layout: flat 150 MW at capacity factor 0.4, technology not stated"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def turbine_count(cfg: Dict[str, Any]) -> Optional[int]:
    """The turbine count a scenario states, wherever it states it, or None."""
    for block, key in (("turbine", "n_turbines"), ("project", "n_turbines")):
        value = (cfg.get(block) or {}).get(key)
        if value is not None:
            return int(value)
    count = ((cfg.get("resource") or {}).get("turbines") or {}).get("count")
    return None if count is None else int(count)


def _technologies(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    generation = cfg.get("generation") or {}
    techs = generation.get("technologies") if isinstance(generation, dict) else None
    return techs if isinstance(techs, dict) else {}


def basis(cfg: Dict[str, Any]) -> str:
    """Return the receipt note for one loaded scenario mapping."""
    project = cfg.get("project") or {}
    total = project.get("capacity_mw")
    techs = _technologies(cfg)
    count = turbine_count(cfg)
    if count is not None:
        wind = (techs.get("wind") or {}).get("capacity_mw")
        if wind is None:
            wind = (cfg.get("turbine") or {}).get("total_capacity_mw", total)
        parts: List[str] = [f"wind {wind} MW"]
        parts += [
            f"{name} {spec.get('capacity_mw')} MW"
            for name, spec in techs.items()
            if name != "wind"
        ]
        note = f"{count}-turbine layout, " + " + ".join(parts)
        return note + (f" ({total} MW total)" if len(parts) > 1 else "")
    if techs:
        return "no turbine layout: " + " + ".join(
            f"{name} {spec.get('capacity_mw')} MW at capacity factor "
            f"{spec.get('capacity_factor')}"
            for name, spec in techs.items()
        )
    return (
        f"no turbine layout: flat {total} MW at capacity factor "
        f"{project.get('capacity_factor')}, technology not stated"
    )


def main(argv: List[str]) -> int:
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
