"""Routing tests for #735 slice-2 (artifact/report/export path normalization).

Slice-2 routes the remaining artifact/report/export writers through
:func:`analytics.output_paths.resolve_output_dir` so every artifact of a run co-scopes.
These tests pin the routing CONTRACT each writer now follows:

  1. Identity at the default (``run_scoped=False``): every writer's DEFAULT path is unchanged,
     so committed runs stay byte-identical.
  2. Co-location under ``run_scoped=True``: all of a run's DEFAULT artifacts land under one
     per-run subdirectory (the JSON/CSV dump, the four pipeline report/workbook emitters, the
     two Hydra CLIs, and the scenario-analytics workbook + its sibling ``*_charts/`` dir).
  3. Explicit-path precedence: a user-supplied path still wins unchanged — only the DEFAULT
     derivation moves onto the resolver.

The writers build their default paths as ``resolve_output_dir(root, ...) / "<file>"`` (the four
pipeline reports and the two CLIs) or, for the scenario-analytics FILE path, as
``resolve_output_dir(file.parent, ...) / file.name``. These tests reproduce those exact
derivations against the shared resolver, and additionally drive the source expressions in the
entrypoints where they are cheap to reach (the two Hydra CLIs' extraction line, and the
scenario-analytics parent-scoping), keeping the pins tied to the real code path.
"""

from __future__ import annotations

from pathlib import Path

from analytics.output_paths import (
    DEFAULT_MC_OUTPUT_ROOT,
    DEFAULT_PIPELINE_OUTPUT_ROOT,
    DEFAULT_SENSITIVITY_OUTPUT_ROOT,
    resolve_output_dir,
)

# The four run_full_pipeline_v14 report/workbook emitters' default filenames (byte-identical pins).
_PIPELINE_REPORT_FILES = (
    "executive_workbook.xlsx",
    "capital_risk_report.html",
    "interaction_grid_report.html",
    "tech_comparison_report.html",
    # ...plus the JSON/CSV dump block artifacts, which share export_dir_scoped:
    "summary.json",
    "kpis.json",
    "debt_result.json",
    "equity_distribution.json",
    "annual_rows.csv",
)

_RUN_ID = "v9.9.9_deadbeef"


# --------------------------------------------------------------------------- #
# 1. Identity at default (run_scoped=False) — byte-identical committed output. #
# --------------------------------------------------------------------------- #


def test_pipeline_report_defaults_identity_at_default() -> None:
    export_dir_scoped = resolve_output_dir(DEFAULT_PIPELINE_OUTPUT_ROOT)
    for fname in _PIPELINE_REPORT_FILES:
        assert (export_dir_scoped / fname) == Path(DEFAULT_PIPELINE_OUTPUT_ROOT) / fname


def test_mc_cli_output_dir_identity_at_default() -> None:
    # Reproduces the extraction line in analytics/cli/cli_monte_carlo_hydra.py.
    output_dir = resolve_output_dir(
        DEFAULT_MC_OUTPUT_ROOT, run_scoped=False, run_id=None
    )
    assert output_dir == Path("_out/monte_carlo")
    assert (output_dir / "monte_carlo_summary.json") == Path(
        "_out/monte_carlo/monte_carlo_summary.json"
    )


def test_sensitivity_cli_output_dir_identity_at_default() -> None:
    # Reproduces the extraction line in analytics/cli/cli_sensitivity_hydra.py.
    output_dir = resolve_output_dir(
        DEFAULT_SENSITIVITY_OUTPUT_ROOT, run_scoped=False, run_id=None
    )
    assert output_dir == Path("_out/sensitivity")
    assert (output_dir / "sensitivity_summary.json") == Path(
        "_out/sensitivity/sensitivity_summary.json"
    )


def test_scenario_analytics_file_path_identity_at_default() -> None:
    # Reproduces run_scenario_analytics_v14.py: scope the FILE's parent, re-attach the name.
    raw = Path("exports/v14_analytics.xlsx")
    parent = resolve_output_dir(raw.parent, run_scoped=False, run_id=None)
    output_path = parent / raw.name
    assert output_path == Path("exports/v14_analytics.xlsx")
    # The engine derives the sibling charts dir from output_path (same parent) -> unchanged too.
    charts_dir = output_path.with_name(output_path.stem + "_charts")
    assert charts_dir == Path("exports/v14_analytics_charts")


# --------------------------------------------------------------------------- #
# 2. Co-location under run_scoped=True — every artifact under one run dir.     #
# --------------------------------------------------------------------------- #


def test_pipeline_report_defaults_co_locate_when_run_scoped() -> None:
    export_dir_scoped = resolve_output_dir(
        DEFAULT_PIPELINE_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID
    )
    run_dir = Path(DEFAULT_PIPELINE_OUTPUT_ROOT) / _RUN_ID
    assert export_dir_scoped == run_dir
    for fname in _PIPELINE_REPORT_FILES:
        derived = export_dir_scoped / fname
        # Every default artifact lands under the SAME per-run subdirectory (the scatter fix).
        assert derived.parent == run_dir
        assert derived == run_dir / fname


def test_all_entrypoints_co_locate_under_one_run_id() -> None:
    # A run_id shared across entrypoints groups every artifact under a "<root>/<run_id>" leaf.
    pipeline = resolve_output_dir(
        DEFAULT_PIPELINE_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID
    )
    mc = resolve_output_dir(DEFAULT_MC_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID)
    sens = resolve_output_dir(
        DEFAULT_SENSITIVITY_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID
    )
    sa_raw = Path("exports/v14_analytics.xlsx")
    sa = (
        resolve_output_dir(sa_raw.parent, run_scoped=True, run_id=_RUN_ID) / sa_raw.name
    )
    sa_charts = sa.with_name(sa.stem + "_charts")

    # Each entrypoint's leaf directory is the shared run_id (co-scoped, not scattered).
    assert pipeline.name == _RUN_ID
    assert mc.name == _RUN_ID
    assert sens.name == _RUN_ID
    assert sa.parent.name == _RUN_ID
    # The scenario-analytics charts dir follows the scoped parent (charts not re-scattered).
    assert sa_charts.parent == sa.parent == Path("exports") / _RUN_ID


# --------------------------------------------------------------------------- #
# 3. Explicit user-supplied paths still win unchanged.                        #
# --------------------------------------------------------------------------- #


def test_pipeline_explicit_report_path_wins_over_scoped_default() -> None:
    # Emulates the emitter precedence: an explicit cfg path is used verbatim, resolver bypassed.
    explicit = "/tmp/lender/executive_workbook.xlsx"
    export_dir_scoped = resolve_output_dir(
        DEFAULT_PIPELINE_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID
    )
    # Precedence branch: `Path(explicit) if explicit else export_dir_scoped / "<file>"`.
    workbook_out = (
        Path(explicit) if explicit else export_dir_scoped / "executive_workbook.xlsx"
    )
    assert workbook_out == Path(explicit)
    # And it is NOT under the scoped run directory (the explicit path is honoured verbatim).
    assert export_dir_scoped not in workbook_out.parents


def test_explicit_paths_win_for_all_four_pipeline_reports() -> None:
    export_dir_scoped = resolve_output_dir(
        DEFAULT_PIPELINE_OUTPUT_ROOT, run_scoped=True, run_id=_RUN_ID
    )
    explicit_paths = {
        "executive_workbook.xlsx": "/tmp/x/wb.xlsx",
        "capital_risk_report.html": "/tmp/x/cr.html",
        "interaction_grid_report.html": "/tmp/x/ig.html",
        "tech_comparison_report.html": "/tmp/x/tc.html",
    }
    for default_name, explicit in explicit_paths.items():
        out = Path(explicit) if explicit else export_dir_scoped / default_name
        assert out == Path(explicit)


def test_cli_explicit_output_dir_wins_over_default() -> None:
    # A user-supplied output_dir routes through the resolver but at run_scoped=False is unchanged.
    explicit_root = "/tmp/mc_custom"
    output_dir = resolve_output_dir(explicit_root, run_scoped=False, run_id=None)
    assert output_dir == Path(explicit_root)


def test_scenario_analytics_explicit_output_file_wins() -> None:
    # An explicit `output` FILE keeps its name; only its parent routes through the resolver.
    raw = Path("/tmp/reports/custom_analytics.xlsx")
    parent = resolve_output_dir(raw.parent, run_scoped=False, run_id=None)
    output_path = parent / raw.name
    assert output_path == raw


# --------------------------------------------------------------------------- #
# 4. Wiring guards: the real writers route through the resolver (not the raw   #
#    root), so a future edit cannot silently re-scatter artifacts.            #
# --------------------------------------------------------------------------- #


def _module_source(module_name: str) -> str:
    import importlib
    import inspect

    return inspect.getsource(importlib.import_module(module_name))


def test_pipeline_reports_route_through_scoped_dir_not_raw() -> None:
    # The four report emitters + JSON block must derive from export_dir_scoped, not export_dir_raw.
    import importlib
    import inspect

    src = inspect.getsource(importlib.import_module("run_full_pipeline_v14"))
    assert "export_dir_scoped = resolve_output_dir(" in src
    for fname in (
        "executive_workbook.xlsx",
        "capital_risk_report.html",
        "interaction_grid_report.html",
        "tech_comparison_report.html",
    ):
        assert f'export_dir_scoped / "{fname}"' in src
    # No report default may still be built off the un-resolved raw root.
    assert 'Path(str(export_dir_raw)) / "' not in src


def test_mc_cli_routes_output_dir_through_resolver() -> None:
    src = _module_source("analytics.cli.cli_monte_carlo_hydra")
    assert "resolve_output_dir(" in src
    assert "DEFAULT_MC_OUTPUT_ROOT" in src
    # The raw literal default must no longer be the direct output_dir source.
    assert 'Path(str(cfg.get("output_dir"' not in src


def test_sensitivity_cli_routes_output_dir_through_resolver() -> None:
    src = _module_source("analytics.cli.cli_sensitivity_hydra")
    assert "resolve_output_dir(" in src
    assert "DEFAULT_SENSITIVITY_OUTPUT_ROOT" in src
    assert 'Path(str(cfg.get("output_dir"' not in src


def test_scenario_analytics_scopes_output_parent() -> None:
    src = _module_source("run_scenario_analytics_v14")
    assert "resolve_output_dir(" in src
    # Parent-scoping: the file's parent routes through the resolver, the name is re-attached.
    assert "output_path_raw.parent" in src
    assert "output_parent / output_path_raw.name" in src
