"""Every committed site-analysis summary matches the tree it was written from (#1824).

A report reads the wind battery options and the PV + BESS sizing from committed summaries
under ``docs/site_analyses/<scenario file stem>/<block>.json`` and marks one stale when its
code or config digest no longer matches. This test keeps every committed summary current, so
a pull request that changes an analysis's code or inputs re-runs it::

    .venv/bin/python scripts/run_site_analysis_v14.py \\
        analysis=<block> scenario=scenarios/<stem>.yaml write=true
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest
import yaml

from analytics.site_analysis_blocks import resolve_site_analysis_block
from analytics.site_analysis_runs import (
    MODE_SUMMARY,
    SITE_ANALYSIS_RUNS,
    SUMMARY_DIR,
    load_summary,
    provenance,
    stale_reasons,
)

ROOT = Path(__file__).resolve().parents[2]
SUMMARIES: List[Path] = sorted((ROOT / SUMMARY_DIR).glob("*/*.json"))


def test_at_least_one_summary_is_checked() -> None:
    # Non-vacuity: the glob below must find the committed summaries.
    assert SUMMARIES, f"no summaries under {SUMMARY_DIR}"


@pytest.mark.parametrize(
    "path", SUMMARIES, ids=[p.relative_to(ROOT).as_posix() for p in SUMMARIES]
)
def test_summary_is_current(path: Path) -> None:
    block = path.stem
    assert block in SITE_ANALYSIS_RUNS, f"{path.name}: not a site analysis"
    assert SITE_ANALYSIS_RUNS[block].mode == MODE_SUMMARY, (
        f"{block} runs live in reports; a committed summary would never be read"
    )
    scenario_path = ROOT / "scenarios" / f"{path.parent.name}.yaml"
    assert scenario_path.is_file(), f"no scenario {scenario_path.name} for {path}"
    scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    block_value = resolve_site_analysis_block(scenario, block)
    assert block_value is not None, f"{scenario_path.name} declares no {block} block"
    summary = load_summary(path)
    assert summary is not None and summary.get("status") == "completed"
    reasons = stale_reasons(
        summary.get("provenance"), provenance(block, block_value, scenario_path)
    )
    assert reasons == [], (
        f"{path.relative_to(ROOT)} is stale; re-run "
        f"scripts/run_site_analysis_v14.py analysis={block} "
        f"scenario={scenario_path.relative_to(ROOT)} write=true: {reasons}"
    )
