"""The module coverage map must agree with the import scan (#1751).

``docs/MODULE_COVERAGE_MAP.md`` says, for each module in the mapped packages, where its
results end up. ``scripts/module_coverage_map.py`` writes it from a LibCST import scan
and :func:`check_map` compares it with a fresh scan. A new module, a removed module or a
status the import graph no longer supports fails here; ``python
scripts/module_coverage_map.py`` regenerates the map and keeps the hand-written notes.

The negative controls build a small import graph, render its map, change one row and
check that :func:`check_map` names the change.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Set

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "module_coverage_map", ROOT / "scripts" / "module_coverage_map.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mcm = _load()


@pytest.fixture(scope="module")
def found() -> object:
    return mcm.scan(ROOT)


def test_the_committed_map_agrees_with_the_scan(found: object) -> None:
    text = mcm.MAP_PATH.read_text(encoding="utf-8")
    assert mcm.check_map(text, found) == []


def test_the_committed_map_catches_a_dropped_row(found: object) -> None:
    lines = mcm.MAP_PATH.read_text(encoding="utf-8").splitlines()
    dropped = next(line for line in lines if line.startswith("| `finance."))
    module = dropped.split("`")[1]
    text = "\n".join(line for line in lines if line != dropped)
    assert f"`{module}` is not in the map; regenerate it" in mcm.check_map(text, found)


# --- Negative controls on a small graph ----------------------------------------------


def _toy_scan() -> object:
    files: Dict[str, str] = {
        "analytics.pipeline_v14_enhanced": "analytics/pipeline_v14_enhanced.py",
        "finance.engine": "finance/engine.py",
        "analytics.executive_workbook": "analytics/executive_workbook.py",
        "analytics.workbook_helper": "analytics/workbook_helper.py",
        "finance.orphan": "finance/orphan.py",
        "scripts.tool": "scripts/tool.py",
        "finance.tool_only": "finance/tool_only.py",
        "finance.cli": "finance/cli.py",
        "finance.cli_helper": "finance/cli_helper.py",
    }
    edges: Dict[str, Set[str]] = {name: set() for name in files}
    edges["analytics.pipeline_v14_enhanced"] = {"finance.engine"}
    edges["analytics.executive_workbook"] = {"analytics.workbook_helper"}
    edges["scripts.tool"] = {"finance.tool_only"}
    edges["finance.cli"] = {"finance.cli_helper"}
    return mcm.Scan(
        files=files,
        edges=edges,
        edges_outside_emitters=edges,
        dynamic={},
        test_importers={"finance.orphan": {"tests/test_orphan.py"}},
        run_as_script={"finance.cli"},
    )


def test_a_rendered_map_passes_its_own_check() -> None:
    toy = _toy_scan()
    text = mcm.render_map(toy, {})
    assert mcm.check_map(text, toy) == []
    statuses = {row.module: row.status for row in mcm.parse_map(text)}
    assert statuses == {
        "analytics.executive_workbook": "emitter",
        "analytics.pipeline_v14_enhanced": "pipeline",
        "analytics.workbook_helper": "emitter",
        "finance.engine": "pipeline",
        "finance.orphan": "unreached",
        "finance.tool_only": "script",
        # A module with a __main__ block is a script root, and so reaches what it imports.
        "finance.cli": "script",
        "finance.cli_helper": "script",
    }


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        (
            "| `finance.engine` | pipeline |",
            "| `finance.engine` | script |",
            "`finance.engine` is mapped script, but the scan finds pipeline",
        ),
        (
            "| `finance.orphan` | unreached |",
            "| `finance.orphan` | pipeline |",
            "`finance.orphan` is mapped pipeline, but the scan finds unreached",
        ),
        (
            "| `finance.tool_only` | script |",
            "| `finance.tool_only` | unreached |",
            "`finance.tool_only` is mapped unreached, but the scan finds script",
        ),
        (
            "| `finance.engine` | pipeline | `analytics.pipeline_v14_enhanced` |",
            "| `finance.engine` | pipeline | `run_full_pipeline_v14` |",
            "`finance.engine` is not reached from `run_full_pipeline_v14`",
        ),
        (
            "| `finance.engine` | pipeline | `analytics.pipeline_v14_enhanced` |",
            "| `finance.engine` | pipeline | `scripts.tool` |",
            "`finance.engine` names 'scripts.tool', which is not a pipeline root",
        ),
        (
            "| `finance.orphan` | unreached |",
            "| `finance.orphan` | dormant |",
            "`finance.orphan` has unknown status 'dormant'",
        ),
    ],
    ids=[
        "weaker-status",
        "unreached-claimed-live",
        "live-claimed-unreached",
        "entry-root-does-not-reach",
        "entry-root-of-another-class",
        "unknown-status",
    ],
)
def test_a_contradicted_row_is_named(old: str, new: str, problem: str) -> None:
    toy = _toy_scan()
    text = mcm.render_map(toy, {})
    assert old in text
    assert problem in mcm.check_map(text.replace(old, new), toy)


def test_a_new_module_and_a_stale_row_are_named() -> None:
    toy = _toy_scan()
    text = mcm.render_map(toy, {})
    row = next(line for line in text.splitlines() if "`finance.orphan`" in line)
    text = text.replace(row, row.replace("finance.orphan", "finance.removed"))
    problems = mcm.check_map(text, toy)
    assert "`finance.orphan` is not in the map; regenerate it" in problems
    assert "`finance.removed` is in the map but is not a mapped module" in problems


def test_a_duplicate_row_is_named() -> None:
    toy = _toy_scan()
    text = mcm.render_map(toy, {})
    row = next(line for line in text.splitlines() if "`finance.engine`" in line)
    assert "`finance.engine` is listed twice" in mcm.check_map(
        text.replace(row, row + "\n" + row), toy
    )


def test_a_retired_declaration_is_kept_only_while_nothing_reaches_it() -> None:
    toy = _toy_scan()
    text = mcm.render_map(toy, {"finance.orphan": ("retired", "superseded")})
    assert "| `finance.orphan` | retired |" in text
    assert mcm.check_map(text, toy) == []
    live = mcm.render_map(toy, {"finance.engine": ("retired", "")})
    assert "| `finance.engine` | pipeline |" in live
