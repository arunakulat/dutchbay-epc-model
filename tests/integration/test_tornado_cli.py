"""Integration tests for ``scripts/run_tornado_from_cli.py``.

Regression guard for the breakage where the CLI imported six symbols from the
retired ``analytics.sensitivity_v14`` star-import shim (``SensitivityRequest``,
``run``, ``run_multi_metric_tornado``, ``load_parameters_from_yaml``,
``tornado_suite_to_dataframe``, ``multi_metric_suite_to_dataframe``) — none of
which the shim exported, so ``python scripts/run_tornado_from_cli.py`` raised
``ImportError`` on import. The CLI is now repointed to the live
``analytics.core.sensitivity_runner`` API; these tests pin (1) that the module
imports, (2) the YAML parameter loader, (3) the tornado->CSV flatten/column
contract, and (4) clean multi-metric and error behaviour.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_CONFIG = _REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_PARAMS_EXAMPLE = _REPO / "scenarios" / "sensitivity_parameters_examples.yaml"

pd = pytest.importorskip("pandas")


def _load_cli():
    """Import the script as a module (it lives in scripts/, not an installed pkg)."""
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    spec = importlib.util.spec_from_file_location(
        "run_tornado_from_cli", _REPO / "scripts" / "run_tornado_from_cli.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # would raise ImportError under the old breakage
    return mod


def test_module_imports_without_error():
    cli = _load_cli()
    for name in ("load_parameters_from_yaml", "tornado_suite_to_dataframe", "main"):
        assert hasattr(cli, name)


def _write_params(tmp_path: Path, *, nested: bool = True) -> Path:
    body = ("parameters:\n" if nested else "") + (
        "  - variable_name: capex.usd_total\n"
        "    base_value: 159600000.0\n"
        "    low_pct: -10.0\n"
        "    high_pct: 10.0\n"
        "  - variable_name: tariff.lkr_per_kwh\n"
        "    base_value: 20.3\n"
        "    low_pct: -10.0\n"
        "    high_pct: 10.0\n"
    )
    if not nested:
        # top-level list form (dedent the two items)
        body = body.replace("  - ", "- ").replace("    ", "  ")
    p = tmp_path / "params.yaml"
    p.write_text(body)
    return p


def test_load_parameters_from_yaml_nested_and_list(tmp_path: Path):
    cli = _load_cli()
    for nested in (True, False):
        params = cli.load_parameters_from_yaml(_write_params(tmp_path, nested=nested))
        assert [p.variable_name for p in params] == [
            "capex.usd_total",
            "tariff.lkr_per_kwh",
        ]
        assert params[0].base_value == pytest.approx(159_600_000.0)


def test_load_parameters_rejects_unknown_keys(tmp_path: Path):
    cli = _load_cli()
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "parameters:\n  - variable_name: x\n    base_value: 1.0\n    bogus_key: 5\n"
    )
    with pytest.raises(ValueError, match="unknown keys"):
        cli.load_parameters_from_yaml(bad)


def test_single_metric_tornado_csv(tmp_path: Path):
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "tornado.csv"
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--parameters",
            str(_write_params(tmp_path)),
            "--metric",
            "project_irr",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    df = pd.read_csv(out)
    assert list(df.columns) == [
        "metric",
        "variable_name",
        "label",
        "base_case",
        "low_case",
        "high_case",
        "impact_abs",
    ]
    assert set(df["variable_name"]) == {"capex.usd_total", "tariff.lkr_per_kwh"}
    assert (df["metric"] == "project_irr").all()
    # base_case is the unlevered project IRR (a finite fraction), identical across rows.
    # ~2.75% under the 5.9% FX-drift re-baseline (was ~5.05% at the old 3% drift).
    assert df["base_case"].nunique() == 1
    assert df["base_case"].iloc[0] == pytest.approx(-0.00117, abs=0.01)
    # tornado convention: rows sorted by descending |impact|.
    assert df["impact_abs"].is_monotonic_decreasing


def test_multi_metric_tags_each_metric(tmp_path: Path):
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "multi.csv"
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--parameters",
            str(_write_params(tmp_path)),
            "--metric",
            "project_irr",
            "--metric",
            "min_dscr",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    df = pd.read_csv(out)
    assert set(df["metric"]) == {"project_irr", "min_dscr"}


def test_shipped_example_command_runs(tmp_path: Path):
    """The exact command advertised in --help / the module docstring must work.

    Regression guard: every path in scenarios/sensitivity_parameters_examples.yaml
    must RESOLVE in the lendercase scenario (the engine rejects unresolved paths),
    so the copy-pasteable example cannot silently exit 2 with an empty CSV.
    """
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    assert (
        _PARAMS_EXAMPLE.exists()
    ), f"committed example params missing: {_PARAMS_EXAMPLE}"
    cli = _load_cli()
    out = tmp_path / "example.csv"
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--parameters",
            str(_PARAMS_EXAMPLE),
            "--metric",
            "project_irr",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    df = pd.read_csv(out)
    assert not df.empty
    assert set(df["variable_name"]) == {
        "capex.usd_total",
        "tariff.lkr_per_kwh",
        "opex.usd_per_year",
        "project.capacity_factor",
    }


def test_unresolvable_parameter_path_exits_clean(tmp_path: Path, capsys):
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    bad = tmp_path / "unresolvable.yaml"
    bad.write_text(
        "parameters:\n  - variable_name: finance.does_not_exist\n"
        "    base_value: 1.0\n    low_pct: -10.0\n    high_pct: 10.0\n"
    )
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--parameters",
            str(bad),
            "--metric",
            "project_irr",
        ]
    )
    assert rc == 2  # clean non-zero exit, not an uncaught traceback
    assert "ERROR" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# #658 — built-in --preset tax / --preset dscr (opt-in; report-only, KPI-neutral)
# ---------------------------------------------------------------------------

_TORNADO_COLUMNS = [
    "metric",
    "variable_name",
    "label",
    "base_case",
    "low_case",
    "high_case",
    "impact_abs",
]


def test_preset_tax_sweeps_rate_and_holiday_on_project_irr(tmp_path: Path):
    """`--preset tax` sweeps tax.corporate_tax_rate + tax.tax_holiday_years on project_irr,
    with no --parameters needed."""
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "tax.csv"
    rc = cli.main(["--config", str(_CONFIG), "--preset", "tax", "--output", str(out)])
    assert rc == 0
    df = pd.read_csv(out)
    assert list(df.columns) == _TORNADO_COLUMNS
    assert (df["metric"] == "project_irr").all()
    assert set(df["variable_name"]) == {
        "tax.corporate_tax_rate",
        "tax.tax_holiday_years",
    }
    # Both tax drivers genuinely move project_irr (not silent flat bars).
    assert (df["impact_abs"] > 0).all()
    # Tornado convention: descending |impact|.
    assert df["impact_abs"].is_monotonic_decreasing


def test_preset_dscr_targets_min_dscr_kpi(tmp_path: Path):
    """`--preset dscr` targets the live min_dscr KPI key (the canonical key the gateway
    always emits), NOT the DscrSensitivityConfig 'dscr_min' field default. target_dscr
    moves the covenant metric; gearing/tenor are (correctly) covenant-pinned flat."""
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    out = tmp_path / "dscr.csv"
    rc = cli.main(["--config", str(_CONFIG), "--preset", "dscr", "--output", str(out)])
    assert rc == 0
    df = pd.read_csv(out)
    assert list(df.columns) == _TORNADO_COLUMNS
    assert (df["metric"] == "min_dscr").all()
    assert "Financing_Terms.target_dscr" in set(df["variable_name"])
    # target_dscr moves min_dscr 1:1 (covenant sculpt target); it must be a non-flat bar.
    target_row = df[df["variable_name"] == "Financing_Terms.target_dscr"].iloc[0]
    assert target_row["impact_abs"] > 0
    # base_case is the pinned covenant DSCR (~1.30).
    assert target_row["base_case"] == pytest.approx(1.30, abs=0.02)


def test_preset_and_parameters_are_mutually_exclusive(tmp_path: Path, capsys):
    assert _CONFIG.exists(), f"committed lendercase scenario missing: {_CONFIG}"
    cli = _load_cli()
    rc = cli.main(
        [
            "--config",
            str(_CONFIG),
            "--preset",
            "tax",
            "--parameters",
            str(_write_params(tmp_path)),
        ]
    )
    assert rc == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_no_preset_and_no_parameters_errors_clean(capsys):
    """Neither --preset nor --parameters is a clean exit 2 (no silent default path)."""
    cli = _load_cli()
    rc = cli.main(["--config", str(_CONFIG)])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err


def test_preset_stdout_when_no_output(capsys):
    """A preset with no --output streams the CSV to stdout (same as the default path)."""
    cli = _load_cli()
    rc = cli.main(["--config", str(_CONFIG), "--preset", "tax"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "tax.corporate_tax_rate" in out
    assert out.splitlines()[0].split(",") == _TORNADO_COLUMNS
